"""
backtester.py — Fade-extreme-dipole-in-EQUILIBRIUM strategy backtest.

Implements the strategy implied by Phase 1.5's mean-reversion finding:
- Wait until regime classifier says EQUILIBRIUM
- If |mean_dipole| > threshold and acl1 not too positive, position OPPOSITE the dipole
- Hold one chunk
- Exit at chunk close

Reports gross PnL, fee-adjusted PnL, win rate, Sharpe, drawdown,
fee breakeven, capacity sensitivity. Sweep parameters to find Pareto.

Usage:
    python backtester.py --bins-path phase1_bins.json --label CB-BTC \\
        --fee-bps 25 --dipole-threshold 0.2
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from markets_adapter import (
    MarketBar, MarketChunker, MarketChunkEncoder,
)
from regime_classifier import Regime, classify_regime, baselines_from_corpus


@dataclass
class Trade:
    chunk_idx_entry: int          # chunk we entered at the end of
    chunk_idx_exit: int           # chunk we exited at the end of
    direction: int                # +1 long, -1 short
    entry_price: float
    exit_price: float
    gross_return: float           # log return signed by direction
    fee_drag_bps: float
    net_return: float
    regime_at_entry: str
    dipole_at_entry: float


def load_bars(bins_path: str) -> list[MarketBar]:
    with open(bins_path) as f:
        sec_bins = {float(k): v for k, v in json.load(f).items()}
    minute_groups: dict[float, list[tuple[float, dict]]] = defaultdict(list)
    for ts, b in sec_bins.items():
        if b.get("mid") is None:
            continue
        m_ts = int(ts / 60.0) * 60.0
        minute_groups[m_ts].append((ts, b))
    bars: list[MarketBar] = []
    for m_ts in sorted(minute_groups):
        members = sorted(minute_groups[m_ts], key=lambda x: x[0])
        mids = [b["mid"] for _, b in members if b["mid"] is not None]
        if not mids:
            continue
        bars.append(MarketBar(
            ts=float(m_ts),
            close=float(mids[-1]), open_=float(mids[0]),
            high=float(max(mids)), low=float(min(mids)),
            volume=float(sum(b["buy"] + b["sell"] for _, b in members)),
            buy_vol=float(sum(b["buy"] for _, b in members)),
            sell_vol=float(sum(b["sell"] for _, b in members)),
        ))
    return bars


def backtest(
    bars: list[MarketBar],
    label: str,
    fee_bps_round_trip: float = 50.0,    # 25 bps each side, default Coinbase taker
    dipole_threshold: float = 0.2,
    only_equilibrium: bool = True,
    chunk_max_size: int = 30,
    chunk_min_segment: int = 10,
    strategy: str = "dipole_x_volz",   # "raw_dipole" or "dipole_x_volz" (autoresearch winner)
    vol_z_threshold: float = 0.5,
) -> dict:
    """Simulate fade-the-dipole within EQUILIBRIUM regime, hold one chunk.

    Strategies:
      raw_dipole     - direction = -sign(mean_dipole) when |mean_dipole| > threshold
      dipole_x_volz  - direction = -sign(mean_dipole * volume_zscore) when
                        |mean_dipole| > dipole_threshold AND |volume_zscore| > vol_z_threshold
                        (autoresearch winner; OOS R²=+0.074 vs raw -0.34)

    Costs: fee_bps_round_trip applied as flat drag to net return.
    """
    chunker = MarketChunker(max_window_size=chunk_max_size,
                             stride=chunk_max_size // 2,
                             min_segment=chunk_min_segment, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(label, bars)
    if len(chunks) < 3:
        return {"error": f"too few chunks ({len(chunks)})"}

    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    results = [classify_regime(f, base) for f in feats]

    fee_drag_decimal = fee_bps_round_trip / 10000.0
    trades: list[Trade] = []

    for t in range(len(chunks) - 1):
        f_t = feats[t]
        regime_t = results[t].regime
        if only_equilibrium and regime_t != Regime.EQUILIBRIUM_TWO_SIDED:
            continue
        if abs(f_t.mean_dipole) < dipole_threshold:
            continue
        # Strategy: pick direction
        if strategy == "dipole_x_volz":
            if abs(f_t.volume_zscore) < vol_z_threshold:
                continue   # skip low-volume chunks (per autoresearch finding)
            composite = f_t.mean_dipole * f_t.volume_zscore
            if abs(composite) < 1e-12:
                continue
            direction = -1 if composite > 0 else +1
        else:   # raw_dipole
            direction = -1 if f_t.mean_dipole > 0 else +1
        entry_price = float(chunks[t].bars[-1].close) if chunks[t].bars else 0.0
        exit_price = float(chunks[t + 1].bars[-1].close) if chunks[t + 1].bars else entry_price
        if entry_price <= 0 or exit_price <= 0:
            continue
        gross = direction * math.log(exit_price / entry_price)
        net = gross - fee_drag_decimal
        trades.append(Trade(
            chunk_idx_entry=t,
            chunk_idx_exit=t + 1,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            gross_return=float(gross),
            fee_drag_bps=fee_bps_round_trip,
            net_return=float(net),
            regime_at_entry=regime_t.value,
            dipole_at_entry=float(f_t.mean_dipole),
        ))

    if not trades:
        return {"label": label, "n_trades": 0, "note": "no entries triggered"}

    gross = np.array([t.gross_return for t in trades])
    net = np.array([t.net_return for t in trades])
    n = len(trades)
    win_rate_gross = float(np.sum(gross > 0)) / n
    win_rate_net = float(np.sum(net > 0)) / n
    avg_gross = float(np.mean(gross))
    avg_net = float(np.mean(net))
    std_net = float(np.std(net))
    sharpe_per_trade = avg_net / std_net if std_net > 1e-12 else 0.0
    # Annualized rough estimate: assume 2 trades per hour (1 chunk = 30 min on average)
    # 2 trades/hr * 24 hr/day * 365 days = 17520/yr. Square root for Sharpe scaling.
    sharpe_annualized = sharpe_per_trade * math.sqrt(17520)

    cum_net = np.cumsum(net)
    drawdown = cum_net - np.maximum.accumulate(cum_net)
    max_dd = float(np.min(drawdown)) if len(drawdown) else 0.0

    # Fee breakeven: the round-trip fee at which net mean = 0
    fee_breakeven_bps = avg_gross * 10000.0

    return {
        "label": label,
        "n_chunks_total": len(chunks),
        "n_chunks_equilibrium": sum(1 for r in results if r.regime == Regime.EQUILIBRIUM_TWO_SIDED),
        "n_trades": n,
        "fee_assumption_bps_round_trip": fee_bps_round_trip,
        "dipole_threshold": dipole_threshold,
        "win_rate_gross": round(win_rate_gross, 3),
        "win_rate_net": round(win_rate_net, 3),
        "avg_gross_return_bps": round(avg_gross * 10000, 2),
        "avg_net_return_bps": round(avg_net * 10000, 2),
        "std_net_bps": round(std_net * 10000, 2),
        "sharpe_per_trade": round(sharpe_per_trade, 3),
        "sharpe_annualized_estimate": round(sharpe_annualized, 2),
        "max_drawdown_bps": round(max_dd * 10000, 2),
        "total_pnl_bps": round(np.sum(net) * 10000, 2),
        "fee_breakeven_bps_round_trip": round(fee_breakeven_bps, 2),
        "trades_by_dir": {
            "+1 (long)": int(np.sum([t.direction == 1 for t in trades])),
            "-1 (short)": int(np.sum([t.direction == -1 for t in trades])),
        },
        "note": ("BREAKEVEN POSITIVE: gross edge exceeds assumed fee"
                 if fee_breakeven_bps > fee_bps_round_trip
                 else "BREAKEVEN NEGATIVE: gross edge below assumed fee"),
    }


def parameter_sweep(bars: list[MarketBar], label: str,
                     strategy: str = "dipole_x_volz") -> list[dict]:
    """Sweep dipole threshold × fee assumption × (strategy)."""
    results: list[dict] = []
    for fee in [10, 25, 50, 100]:
        for thr in [0.1, 0.15, 0.2, 0.3, 0.4]:
            r = backtest(bars, label, fee_bps_round_trip=fee,
                         dipole_threshold=thr, strategy=strategy)
            if "n_trades" in r and r["n_trades"] >= 1:
                r["strategy"] = strategy
                results.append(r)
    return results


def comparative_sweep(bars: list[MarketBar], label: str) -> dict:
    """Run both strategies and report side-by-side."""
    return {
        "raw_dipole": parameter_sweep(bars, label, strategy="raw_dipole"),
        "dipole_x_volz": parameter_sweep(bars, label, strategy="dipole_x_volz"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bins-path", required=True)
    p.add_argument("--label", default="dataset")
    p.add_argument("--fee-bps", type=float, default=50.0,
                   help="Round-trip fee assumption in bps (default 50)")
    p.add_argument("--dipole-threshold", type=float, default=0.2)
    p.add_argument("--sweep", action="store_true",
                   help="Sweep over fee × dipole_threshold")
    p.add_argument("--strategy", default="dipole_x_volz",
                   choices=["raw_dipole", "dipole_x_volz"],
                   help="Strategy: raw_dipole (original) or dipole_x_volz (autoresearch winner)")
    p.add_argument("--compare", action="store_true",
                   help="Run both strategies side-by-side")
    p.add_argument("--report-path", default=None)
    args = p.parse_args()

    bars = load_bars(args.bins_path)
    print(f"[{args.label}] loaded {len(bars)} minute bars\n")

    if args.compare:
        comp = comparative_sweep(bars, args.label)
        for strat, rows in comp.items():
            print(f"\n=== STRATEGY: {strat} ===")
            rows.sort(key=lambda r: -r["sharpe_per_trade"])
            for r in rows[:5]:
                print(f"  fee={r['fee_assumption_bps_round_trip']:>3.0f} thr={r['dipole_threshold']:.2f}  "
                      f"n={r['n_trades']:>3}  win={r['win_rate_net']:>5.1%}  "
                      f"avg={r['avg_net_return_bps']:>+7.2f}bp  pnl={r['total_pnl_bps']:>+8.2f}bp")
        if args.report_path:
            with open(args.report_path, "w") as f:
                json.dump(comp, f, indent=2)
            print(f"\nComparison report: {args.report_path}")
    elif args.sweep:
        rows = parameter_sweep(bars, args.label, strategy=args.strategy)
        rows.sort(key=lambda r: -r["sharpe_per_trade"])
        print(f"=== Parameter sweep [{args.strategy}] ({len(rows)} configs ranked by sharpe_per_trade) ===")
        print(f"{'fee':>4} {'thr':>5} {'n':>3} {'win_net':>7} {'avg_bps':>9} {'sharpe':>7} {'pnl_bps':>8} {'note'}")
        for r in rows:
            print(f"{r['fee_assumption_bps_round_trip']:>4.0f} {r['dipole_threshold']:>5.2f} "
                  f"{r['n_trades']:>3} {r['win_rate_net']:>7.2%} {r['avg_net_return_bps']:>+9.2f} "
                  f"{r['sharpe_per_trade']:>+7.3f} {r['total_pnl_bps']:>+8.2f} "
                  f"{'BREAKEVEN+' if 'POSITIVE' in r['note'] else 'BREAKEVEN-'}")
        if args.report_path:
            with open(args.report_path, "w") as f:
                json.dump(rows, f, indent=2)
            print(f"\nSweep report: {args.report_path}")
    else:
        r = backtest(bars, args.label,
                     fee_bps_round_trip=args.fee_bps,
                     dipole_threshold=args.dipole_threshold,
                     strategy=args.strategy)
        print(json.dumps(r, indent=2))
        if args.report_path:
            with open(args.report_path, "w") as f:
                json.dump(r, f, indent=2)


if __name__ == "__main__":
    main()
