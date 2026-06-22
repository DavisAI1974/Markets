"""
od_backtest.py — HONEST backtest of OD signals on REAL bins.

For each signal: walk-forward OOS net return + sharpe (real fees+slippage), the
random-vs-walkforward gap (stationarity signature), and the tautology-killing null z.
Compared to buy-and-hold. No synthetic data, no in-sample cherry-picking.

Usage: python scripts/od_backtest.py --source btc_coinbase --resample 60 --fee 2 --slip 1
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins
from odcore.generators import SIGNALS
from odcore.validation import (backtest_signal, walk_forward_splits,
                               random_vs_walkforward_gap, tautology_signal_null)

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")


def walk_forward_oos(returns, signal, fee, slip, n_folds=5):
    nets, sharpes = [], []
    n = min(returns.size - 1, signal.size)
    for _, (ts, te) in walk_forward_splits(n, n_folds):
        m = backtest_signal(returns[ts:te + 1], signal[ts:te], fee, slip)
        nets.append(m.net_return); sharpes.append(m.sharpe)
    return float(np.sum(nets)), float(np.mean(sharpes)) if sharpes else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="btc_coinbase")
    ap.add_argument("--resample", type=int, default=60)
    ap.add_argument("--fee", type=float, default=2.0)
    ap.add_argument("--slip", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    s = load_bins(os.path.join(REALBINS, f"{args.source}_bins.json")).resample(args.resample)
    r = s.log_return()
    if args.limit:
        r = r[:args.limit]
    bars = len(r)
    bh = float(np.sum(r[1:]))  # buy-and-hold over the window
    print(f"== {args.source} resample={args.resample}s  bars={bars:,}  "
          f"fee={args.fee} slip={args.slip} bps ==")
    print(f"buy-and-hold net log-return over window: {bh*100:+.2f}%\n")
    print(f"{'signal':<18} {'WF_net':>9} {'WF_sharpe':>9} {'rnd_gap':>8} {'taut_z':>7} {'hit%':>6} {'trades':>7}")

    for name, fn in SIGNALS.items():
        sig = fn(s)
        if args.limit:
            sig = sig[:args.limit]
        wf_net, wf_sharpe = walk_forward_oos(r, sig, args.fee, args.slip)
        gap = random_vs_walkforward_gap(r, sig, args.fee, args.slip)
        taut = tautology_signal_null(r, sig, args.fee, args.slip, n_null=100)
        full = backtest_signal(r, sig, args.fee, args.slip)
        print(f"{name:<18} {wf_net*100:>8.2f}% {wf_sharpe:>9.2f} {gap['gap']:>8.2f} "
              f"{taut['z']:>7.1f} {full.hit_rate*100:>5.1f} {full.n_trades:>7,}")
    print("\n(WF = walk-forward OOS; rnd_gap = random_sharpe - walkforward_sharpe, large => "
          "non-stationary/optimistic; taut_z = real net vs circular-shift null)")


if __name__ == "__main__":
    main()
