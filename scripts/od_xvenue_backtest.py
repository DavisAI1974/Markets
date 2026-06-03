"""
od_xvenue_backtest.py — HONEST cross-venue reversion backtest on REAL BTC bins.

A lower-frequency OD signal: trade only when one venue dislocates from the multi-venue
consensus (z-scored spread band entry/exit), betting on convergence. Few trades => cost
doesn't dominate. Reported with walk-forward OOS, real fees+slippage, and the tautology null.

Align at 1s FIRST, then resample (correct phase). No synthetic data.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins, BinSeries
from odcore.validation import backtest_signal, tautology_signal_null, walk_forward_splits

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")


def common_grid_1s(series: list[BinSeries]) -> list[BinSeries]:
    lo = max(int(s.ts[0]) for s in series)
    hi = min(int(s.ts[-1]) for s in series)
    out = []
    for s in series:
        i0, i1 = lo - int(s.ts[0]), hi - int(s.ts[0]) + 1
        out.append(BinSeries(s.ts[i0:i1], s.buy[i0:i1], s.sell[i0:i1], s.mid[i0:i1],
                             s.volume[i0:i1], s.spread[i0:i1], s.n_trades[i0:i1]))
    return out


def band_signal(spread: np.ndarray, entry: float, exit: float, win: int) -> np.ndarray:
    z = np.zeros_like(spread)
    for t in range(win, len(spread)):
        w = spread[t - win:t]
        sd = w.std()
        z[t] = (spread[t] - w.mean()) / sd if sd > 1e-9 else 0.0
    sig = np.zeros_like(spread)
    pos = 0.0
    for t in range(len(spread)):
        if pos == 0 and abs(z[t]) > entry:
            pos = -np.sign(z[t])          # fade the dislocation (expect reversion)
        elif pos != 0 and abs(z[t]) < exit:
            pos = 0.0
        sig[t] = pos
    return sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="btc_coinbase")
    ap.add_argument("--venues", nargs="*",
                    default=["btc_coinbase", "btc_kraken", "btc_bybit_perp"])
    ap.add_argument("--resample", type=int, default=60)
    ap.add_argument("--fee", type=float, default=2.0)
    ap.add_argument("--slip", type=float, default=1.0)
    ap.add_argument("--win", type=int, default=120)
    args = ap.parse_args()

    raw = [load_bins(os.path.join(REALBINS, f"{v}_bins.json")) for v in args.venues]
    grid = common_grid_1s(raw)
    res = [s.resample(args.resample) for s in grid]
    logs = []
    for s in res:
        m = np.where(s.mid > 0, s.mid, np.nan)
        x = np.log(m)
        logs.append(np.nan_to_num(x, nan=np.nanmean(x[np.isfinite(x)])))
    n = min(len(x) for x in logs)
    logs = [x[:n] for x in logs]
    consensus = np.mean(logs, axis=0)
    ti = args.venues.index(args.target)
    tgt = logs[ti]
    ret = np.zeros(n); ret[1:] = tgt[1:] - tgt[:-1]
    spread = tgt - consensus

    bh = float(np.sum(ret[1:]))
    print(f"== cross-venue reversion: {args.target} vs consensus{tuple(args.venues)} ==")
    print(f"   resample={args.resample}s bars={n:,} fee={args.fee} slip={args.slip} bps  "
          f"buy&hold={bh*100:+.2f}%\n")
    print(f"{'entry':>5} {'exit':>5} {'full_net':>9} {'WF_net':>9} {'hit%':>6} {'trades':>7} {'taut_z':>7}")
    for entry in (1.5, 2.0, 2.5, 3.0):
        sig = band_signal(spread, entry=entry, exit=0.4, win=args.win)
        full = backtest_signal(ret, sig, args.fee, args.slip)
        taut = tautology_signal_null(ret, sig, args.fee, args.slip, n_null=100)
        nn = min(ret.size - 1, sig.size)
        wf = sum(backtest_signal(ret[ts:te + 1], sig[ts:te], args.fee, args.slip).net_return
                 for _, (ts, te) in walk_forward_splits(nn, 5))
        print(f"{entry:>5.1f} {0.4:>5.1f} {full.net_return*100:>8.2f}% {wf*100:>8.2f}% "
              f"{full.hit_rate*100:>5.1f} {full.n_trades:>7,} {taut['z']:>7.2f}")


if __name__ == "__main__":
    main()
