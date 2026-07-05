"""_s63_trend_diag.py — S63 diagnostic: is the 1h-trend a real DIRECTION read?

Verifies the S62-close claim before we trust any flip policy:
  "Among the big losers the 1h trend (mom 3600s) predicts the forward direction at 0.58-0.67,
   while OVERALL momentum is BELOW 0.5 (the market mean-reverts at the machine's 600s scale)."

For each leg (ci, xi, side) from the promoted machine:
  fwd_dir      = sign(log(mid[xi]/mid[ci]))            # the direction that WOULD have won
  trend_dir(W) = sign(log(mid[ci]/mid[ci-W]))          # the W-horizon trend at entry
  acc(W)       = P(trend_dir == fwd_dir)               # does the trend point the winning way?

Reported over three populations:
  ALL legs            (should be < 0.5 at short W = mean-reverting, the machine's edge)
  BIG LOSERS (worst decile by gross, and gross<=-40 deaths)   <- the handoff's 0.58-0.67 claim
  WINNERS (gross>0)   (context)

Also: the machine's OWN side accuracy = P(side == fwd_dir) per population (sanity: winners ~1,
losers ~0), and how concentrated the big losers are (share of total loss).

Usage:  python scripts/_s63_trend_diag.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

BINS = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CELLS = [("sol", "SOLUSDT", 100.0), ("eth", "ETHUSDT", 80.0), ("btc", "BTCUSDT", 80.0),
         ("xrp", "XRPUSDT", 80.0), ("doge", "DOGEUSDT", 100.0)]
WINDOWS = [600, 3600, 7200, 14400]     # 600s (machine scale) / 1h / 2h / 4h


def legs(sym, th):
    m, *_ = load_bins(f"{BINS}/{sym}_30d_bins.json")
    m = np.asarray(m, float); lm = np.log(m); n = len(m)
    fl = armed_midband_flips(m, th, 0.5)
    rows = []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]
        ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < 14400 or ci < 1802 or xi >= n:   # need 4h history for all W
            continue
        gross = side * (lm[xi] - lm[ci]) * 1e4
        fwd = np.sign(lm[xi] - lm[ci])
        moms = {W: np.sign(lm[ci] - lm[ci - W]) for W in WINDOWS}
        rows.append((gross, side, fwd, moms))
    return rows, lm


def acc(rows, mask, W):
    sub = [r for r, m in zip(rows, mask) if m]
    if not sub:
        return float("nan"), 0
    hit = np.mean([1.0 if r[3][W] == r[2] and r[2] != 0 else 0.0 for r in sub])
    return float(hit), len(sub)


def main():
    for coin, sym, th in CELLS:
        path = f"{BINS}/{sym}_30d_bins.json"
        if not os.path.exists(path):
            print(f"[{coin}] bins missing"); continue
        rows, _ = legs(sym, th)
        gross = np.array([r[0] for r in rows])
        fwd = np.array([r[2] for r in rows])
        side = np.array([r[1] for r in rows])
        n = len(rows)
        # populations
        p10 = np.percentile(gross, 10)
        big = gross <= p10
        death = gross <= -40
        win = gross > 0
        allm = np.ones(n, bool)
        # loss concentration
        tot_loss = -gross[gross < 0].sum()
        big_loss = -gross[big & (gross < 0)].sum()
        print(f"\n[{coin}]  legs={n}  winners={int(win.sum())}  losers={int((~win).sum())}  "
              f"deaths(<=-40)={int(death.sum())}  worst-decile cut={p10:.0f}bp  "
              f"big-decile carries {100*big_loss/max(tot_loss,1e-9):.0f}% of all loss")
        print(f"   own-side acc: all={np.mean(side==fwd):.3f}  big={np.mean(side[big]==fwd[big]):.3f}  "
              f"win={np.mean(side[win]==fwd[win]):.3f}")
        print(f"   {'pop':<12}" + "".join(f"{('W='+('600s' if W==600 else str(W//3600)+'h')):>9}" for W in WINDOWS))
        for name, mask in [("ALL", allm), ("BIG-LOSER", big), ("DEATH", death), ("WINNER", win)]:
            cells = []
            for W in WINDOWS:
                a, k = acc(rows, mask, W)
                cells.append(f"{a:>9.3f}")
            print(f"   {name:<12}" + "".join(cells) + f"   (n={int(mask.sum())})")


if __name__ == "__main__":
    main()
