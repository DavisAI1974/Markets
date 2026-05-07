"""
forward_paper.py — auto paper-trade emitter for the candidate cells under
out-of-sample evaluation (per HANDOFF_PHASE1_5_RESULTS.md fifth pass).

Cells currently wired (chunk-level, runs in the same poll loop):
  - eth_kr_nascent_up_momo : ETH KR WHALE_NASCENT_UP -> long-momentum
  - eth_kr_herd_up_volq3_fade : ETH KR HERD_UP with volume-z >= 0.67
                               (proxy for vol-Q3) -> short-fade

Cells deferred (not wired here):
  - btc_perp_lead : BN-perp 1-min imbalance leads KR-spot. Lives on the
    per-second perp stream, not the chunk-level path; needs a separate
    minute-level evaluator before we can paper-trade it.

Each opened trade is appended to backend_practice_trades.jsonl with
auto=True and a cell_id tag so the existing /api/practice-trades
endpoint surfaces them alongside manual trades, and they show up in
aggregate win-rate / realized-pnl stats. Closure runs as a sweep at the
top of every poll cycle: anything with status='open' AND auto=True AND
elapsed >= hold_minutes gets exit_price stamped at the current bid/ask
and realized P&L computed (same fee math as the manual-close path).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CellSpec:
    cell_id: str
    asset: str
    venue: str
    side: str               # "buy" (long-momentum) or "sell" (short-fade)
    notional_usd: float     # fixed notional per opened trade
    hold_minutes: float     # auto-close after this many minutes
    note: str
    # Predicate: returns True iff the cell should fire on this chunk.
    # Args: regime (str), feat (MarketFeatures-like), chunk (MarketChunk-like).
    predicate: Callable[[str, object, object], bool]


def _is_eth_kr_nascent_up(regime: str, feat: object, chunk: object) -> bool:
    return regime == "WHALE_NASCENT_UP"


def _is_eth_kr_herd_up_volq3(regime: str, feat: object, chunk: object) -> bool:
    if regime != "HERD_UP":
        return False
    vz = getattr(feat, "volume_zscore", 0.0)
    # ~Q3 cut on a standard-normal corpus z-score; matches the
    # sub-window finding (recent_pass5: r=-0.20 within vol-Q3 for ETH
    # KR HERD_UP at n=168, p=0.008).
    return vz is not None and float(vz) >= 0.67


CELLS: list[CellSpec] = [
    CellSpec(
        cell_id="eth_kr_nascent_up_momo",
        asset="ETH", venue="KR",
        side="buy",
        notional_usd=1000.0,
        hold_minutes=10.0,
        note="forward paper: ETH KR WHALE_NASCENT_UP momentum (cell pass 5: "
             "r=+0.21 over 30d, r=+0.58 in recent 9d)",
        predicate=_is_eth_kr_nascent_up,
    ),
    CellSpec(
        cell_id="eth_kr_herd_up_volq3_fade",
        asset="ETH", venue="KR",
        side="sell",
        notional_usd=1000.0,
        hold_minutes=10.0,
        note="forward paper: ETH KR HERD_UP fade within vol-Q3 (cell pass 5: "
             "r=-0.20 at n=168, p=0.008)",
        predicate=_is_eth_kr_herd_up_volq3,
    ),
]


_PRACTICE_FEE_BPS = 25.0


def find_matching_cells(asset: str, venue: str, regime: str,
                          feat: object, chunk: object) -> list[CellSpec]:
    out = []
    for cell in CELLS:
        if cell.asset != asset or cell.venue != venue:
            continue
        try:
            if cell.predicate(regime, feat, chunk):
                out.append(cell)
        except Exception:
            # Predicate failure shouldn't kill the poll loop.
            continue
    return out


def open_paper_trade(cell: CellSpec, fill_price: float) -> dict:
    """Build the open-trade dict matching backend_practice_trades.jsonl
    schema (same shape as the manual practice path in api_server.py).
    Caller persists via _persist_practice_trade()."""
    qty = cell.notional_usd / fill_price if fill_price > 0 else 0.0
    notional = fill_price * qty
    fee_usd = notional * (_PRACTICE_FEE_BPS / 10000.0)
    return {
        "intent_id": str(uuid.uuid4())[:12],
        "asset": cell.asset,
        "venue": cell.venue,
        "side": cell.side,
        "price": float(fill_price),
        "qty": float(qty),
        "notional": float(notional),
        "note": cell.note,
        "ts_utc": time.time(),
        "practice": True,
        "auto": True,
        "cell_id": cell.cell_id,
        "kind": "practice",
        "status": "open",
        "fill_price": float(fill_price),
        "fees_usd": float(fee_usd),
        "fee_bps": _PRACTICE_FEE_BPS,
        "exit_price": 0.0,
        "exit_ts_utc": 0.0,
        "realized_pnl_usd": 0.0,
        "hold_minutes": float(cell.hold_minutes),
    }


def is_expired(trade: dict, now_utc: float) -> bool:
    if trade.get("status") != "open":
        return False
    if not trade.get("auto"):
        return False
    hold = float(trade.get("hold_minutes") or 0.0)
    if hold <= 0:
        return False
    return (now_utc - float(trade.get("ts_utc", 0.0))) / 60.0 >= hold


def close_paper_trade(trade: dict, bid: float, ask: float, mid: float) -> None:
    """Mutates `trade` in place to closed status with exit_price + realized P&L.
    Mirrors the math of /api/practice-trade/close in api_server.py."""
    side = trade.get("side")
    exit_price = bid if side == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    if exit_price <= 0:
        # Can't close without a quote; leave open.
        return
    fill_price = float(trade.get("fill_price", 0.0))
    qty = float(trade.get("qty", 0.0))
    signed = +1 if side == "buy" else -1
    gross_pnl = signed * (exit_price - fill_price) * qty
    notional_out = exit_price * qty
    exit_fee = notional_out * (_PRACTICE_FEE_BPS / 10000.0)
    realized = gross_pnl - float(trade.get("fees_usd", 0.0)) - exit_fee
    trade["status"] = "closed"
    trade["exit_price"] = float(exit_price)
    trade["exit_ts_utc"] = time.time()
    trade["fees_usd"] = float(trade.get("fees_usd", 0.0)) + float(exit_fee)
    trade["realized_pnl_usd"] = float(realized)
    trade["close_reason"] = "auto_hold_elapsed"
