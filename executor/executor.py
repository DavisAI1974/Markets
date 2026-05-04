"""
executor.py — the closed-group signal executor.

Subscribes to the markets-watch backend's SSE signal stream. For each new
signal, runs risk gates, places a paper-trade order via the configured
exchange adapter, schedules the matching exit (after max_hold_minutes or
on stop-loss / take-profit), and records the round-trip P&L.

This is the reference implementation. Friends adapt it for their actual
exchange by writing a real Exchange adapter (see exchanges/base.py).

By design:
- DEFAULTS TO PAPER. No real orders unless the user explicitly swaps in a
  real Exchange adapter and edits this file.
- LOG-ONLY MODE: --dry-run skips order placement entirely; just logs
  decisions. Useful first deployment to verify gates fire correctly.
- AUDIT TRAIL: every signal seen, every gate decision, every order placed
  written to executor/audit.jsonl.

Run:
  python -m executor.executor --config executor/config.example.json
  python -m executor.executor --config my_config.json --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Ensure we can import sibling packages when run as `python -m executor.executor`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp

from executor.risk import RiskConfig, evaluate as risk_evaluate
from executor.exchanges import PaperExchange, Exchange


@dataclass
class Trade:
    trade_id: str
    signal_id: str
    asset: str
    venue: str
    regime: str
    direction: str   # "long" or "short"
    entry_ts_utc: float
    entry_price: float
    entry_size: float
    notional_usd: float
    exit_ts_utc: float = 0.0
    exit_price: float = 0.0
    exit_reason: str = ""
    realized_pnl_usd: float = 0.0
    fees_usd: float = 0.0
    status: str = "open"  # open | closed
    date_utc: str = ""


def audit(audit_path: str, entry: dict) -> None:
    os.makedirs(os.path.dirname(audit_path) or ".", exist_ok=True)
    with open(audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_config(path: str) -> tuple[RiskConfig, dict]:
    with open(path) as f:
        raw = json.load(f)
    risk_dict = raw.get("risk", {})
    cfg = RiskConfig(**{k: v for k, v in risk_dict.items() if k in RiskConfig.__dataclass_fields__})
    settings = raw.get("settings", {})
    return cfg, settings


async def stream_signals(api_base: str):
    """Async generator yielding signal dicts from SSE."""
    timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
    while True:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{api_base}/api/stream") as resp:
                    if resp.status != 200:
                        print(f"[exec] stream status {resp.status}; retry in 5s", flush=True)
                        await asyncio.sleep(5)
                        continue
                    event_type = None
                    async for raw in resp.content:
                        line = raw.decode("utf-8", errors="ignore").rstrip("\n")
                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            payload = line.split(":", 1)[1].strip()
                            if event_type == "signal" and payload:
                                try:
                                    yield json.loads(payload)
                                except Exception:
                                    pass
                            event_type = None
        except Exception as e:
            print(f"[exec] stream error: {e}; reconnect in 5s", flush=True)
            await asyncio.sleep(5)


class Executor:
    def __init__(self, exchange: Exchange, cfg: RiskConfig, settings: dict,
                 audit_path: str, dry_run: bool):
        self.exchange = exchange
        self.cfg = cfg
        self.settings = settings
        self.audit_path = audit_path
        self.dry_run = dry_run
        self.recent_trades: list[Trade] = []   # in-memory; persisted via audit log
        self.open_trades: dict[str, Trade] = {}   # signal_id -> Trade

    async def handle_signal(self, sig: dict):
        # Risk gates
        decision = risk_evaluate(sig, self.cfg, [asdict(t) for t in self.recent_trades])
        audit(self.audit_path, {
            "kind": "signal_received", "signal": sig,
            "gate_allow": decision.allow, "gate_reason": decision.reason,
            "ts": time.time(),
        })
        if not decision.allow:
            print(f"[exec] DENY {sig['signal_id']}: {decision.reason}", flush=True)
            return
        if self.dry_run:
            print(f"[exec] DRY-RUN ALLOW {sig['signal_id']} {sig['asset']}-{sig['venue']} {sig['regime']}", flush=True)
            audit(self.audit_path, {"kind": "dry_run_allow", "signal_id": sig["signal_id"], "ts": time.time()})
            return

        # Determine direction from regime
        direction = self._direction_from_regime(sig)
        if direction is None:
            print(f"[exec] no direction for {sig['regime']}; skipping", flush=True)
            return
        notional = min(self.cfg.position_size_usd, self.cfg.max_position_usd)
        asset = sig["asset"]
        if direction == "long":
            r = self.exchange.market_buy(asset, notional)
        else:
            # For short: use exchange's short capability if available; for paper
            # we treat it as a synthetic "negative position" via market_sell.
            q = self.exchange.get_quote(asset)
            size = notional / q.bid
            r = self.exchange.market_sell(asset, size)
        if not r.success:
            print(f"[exec] order FAILED: {r.error}", flush=True)
            audit(self.audit_path, {"kind": "order_fail", "signal_id": sig["signal_id"],
                                     "error": r.error, "ts": time.time()})
            return

        trade = Trade(
            trade_id=r.exchange_order_id,
            signal_id=sig["signal_id"],
            asset=asset, venue=sig["venue"], regime=sig["regime"],
            direction=direction,
            entry_ts_utc=time.time(),
            entry_price=r.fill_price, entry_size=r.fill_size,
            notional_usd=notional,
            fees_usd=r.fees_usd,
            date_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        self.open_trades[sig["signal_id"]] = trade
        self.recent_trades.append(trade)
        audit(self.audit_path, {"kind": "trade_opened", "trade": asdict(trade), "ts": time.time()})
        print(f"[exec] OPEN {trade.direction.upper()} {asset} @ {r.fill_price:.2f} (signal {sig['signal_id']})", flush=True)

        # Schedule exit
        asyncio.create_task(self._exit_after_hold(trade))

    def _direction_from_regime(self, sig: dict) -> str | None:
        regime = sig["regime"]
        if regime == "WHALE_UP" or regime == "HERD_UP":
            return "long"
        if regime == "WHALE_DOWN" or regime == "HERD_DOWN":
            return "short"
        # Equilibrium fade: direction is OPPOSITE to dipole sign
        if regime in ("EQUILIBRIUM_TWO_SIDED", "EQUILIBRIUM_EXTREME_DEMO"):
            d = sig.get("mean_dipole", 0.0)
            return "short" if d > 0 else "long"
        return None

    async def _exit_after_hold(self, trade: Trade):
        # Wait for max_hold_minutes, polling every 30s for stop/target hits
        end_ts = trade.entry_ts_utc + self.cfg.max_hold_minutes * 60
        stop_bps = self.cfg.stop_loss_bps
        target_bps = self.cfg.take_profit_bps

        while time.time() < end_ts:
            await asyncio.sleep(30)
            try:
                q = self.exchange.get_quote(trade.asset)
            except Exception:
                continue
            mid = q.mid
            ret_bps = ((mid - trade.entry_price) / trade.entry_price) * 10000
            if trade.direction == "short":
                ret_bps = -ret_bps
            if ret_bps >= target_bps:
                await self._close_trade(trade, exit_price=mid, reason="take_profit")
                return
            if ret_bps <= -stop_bps:
                await self._close_trade(trade, exit_price=mid, reason="stop_loss")
                return

        # Time exit
        try:
            q = self.exchange.get_quote(trade.asset)
            await self._close_trade(trade, exit_price=q.mid, reason="time")
        except Exception as e:
            audit(self.audit_path, {"kind": "exit_quote_error",
                                     "signal_id": trade.signal_id, "error": str(e),
                                     "ts": time.time()})

    async def _close_trade(self, trade: Trade, exit_price: float, reason: str):
        # Compute realized PnL
        if trade.direction == "long":
            pnl = (exit_price - trade.entry_price) * trade.entry_size
            r = self.exchange.market_sell(trade.asset, trade.entry_size)
        else:
            # Short: closing means buying back
            pnl = (trade.entry_price - exit_price) * trade.entry_size
            r = self.exchange.market_buy(trade.asset, exit_price * trade.entry_size)
        trade.exit_ts_utc = time.time()
        trade.exit_price = exit_price
        trade.exit_reason = reason
        trade.realized_pnl_usd = pnl - trade.fees_usd - r.fees_usd
        trade.fees_usd += r.fees_usd
        trade.status = "closed"
        if trade.signal_id in self.open_trades:
            del self.open_trades[trade.signal_id]
        audit(self.audit_path, {"kind": "trade_closed", "trade": asdict(trade), "ts": time.time()})
        print(f"[exec] CLOSE {trade.direction.upper()} {trade.asset} @ {exit_price:.2f} "
              f"({reason})  PnL ${trade.realized_pnl_usd:+.2f}", flush=True)


async def amain(args):
    cfg, settings = load_config(args.config)
    api_base = settings.get("api_base", "http://localhost:8000")
    audit_path = settings.get("audit_path", "executor/audit.jsonl")
    paper_log = settings.get("paper_trade_log", "executor/paper_trades.jsonl")
    fee_bps = settings.get("simulated_fee_bps", 25.0)

    exchange = PaperExchange(api_base=api_base, trade_log_path=paper_log, simulated_fee_bps=fee_bps)
    ex = Executor(exchange, cfg, settings, audit_path, dry_run=args.dry_run)

    print(f"[exec] starting; api={api_base}, exchange={exchange.name}, "
          f"dry_run={args.dry_run}, audit={audit_path}", flush=True)
    print(f"[exec] risk config: position=${cfg.position_size_usd}, "
          f"max_trades_today={cfg.max_trades_per_day}, "
          f"min_confidence={cfg.min_confidence}, "
          f"regime_whitelist={cfg.regime_whitelist}", flush=True)

    async for sig in stream_signals(api_base):
        await ex.handle_signal(sig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="path to config JSON")
    p.add_argument("--dry-run", action="store_true",
                   help="run gates and log decisions, but never place orders")
    args = p.parse_args()

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        print("\n[exec] shutting down", flush=True)


if __name__ == "__main__":
    main()
