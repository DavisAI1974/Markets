"""_s63_kraken_deepstop.py — fire ONLY at BIG negative depth (Greg): eat the first drop, then bail/flip.

Greg's correction: the biggest losers drop big & keep going; once a trade is deep it's already a dead
loss, not a dip that recovers to a WIN. So DON'T fire at all depths (that clips recoveries) — fire only
at BIG negative depth. Two questions, measured cleanly per depth D on the Kraken tape (retime entries):

  1. CONDITIONAL on reaching -D, what happens by the exit?
       cont%   = ends worse than -D (kept going)
       recL%   = recovers but still a LOSS (final in (-D, 0])
       WIN%    = recovers to PROFIT (final > 0)   <-- the crux: if ~0, bailing at -D clips NO winners
  2. Net $/hr of firing ONLY at -D (honest Kraken taker): BAIL (flatten at -D) vs FLIP (reverse at -D,
       ride the continuation), vs ride-all.

If WIN% ~ 0 at big D, a deep bail is free tail-control; if cont% >> 50 at big D, a deep FLIP wins.

Usage:  python scripts/_s63_kraken_deepstop.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import retime_flips                          # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1; BAIL_TK, FLIP_TK = 11.0, 22.0
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
DEPTHS = [40, 60, 80, 100, 120]


def legs(mid, entries, sgn):
    """List of (gross, r_path) per swing."""
    out = []
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        r = side * np.log(mid[ci:nci + 1] / mid[ci]) * 1e4
        out.append(r)
    return out


def main():
    print("=== FIRE ONLY AT BIG DEPTH — conditional outcome + deep bail/flip, Kraken kr_mk0 ===")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
        R = legs(mid, entries, sgn)
        gross = np.array([r[-1] for r in R])
        ride = gross.sum() / 1e4 * CAP / hrs
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  ride-all {ride:+.2f} $/hr   (n={len(R)})")
        print(f"   {'depth':>6}{'reach':>6}{'cont%':>6}{'recL%':>6}{'WIN%':>6} | "
              f"{'bail$/h':>8}{'flip$/h':>8}   (vs ride {ride:+.1f})")
        for D in DEPTHS:
            reach = 0; cont = recL = win = 0
            bail_pnl = []; flip_pnl = []
            for r in R:
                g = float(r[-1])
                u = np.where(r <= -D)[0]
                if len(u) == 0:
                    bail_pnl.append(g); flip_pnl.append(g); continue
                reach += 1
                if g <= -D:
                    cont += 1
                elif g <= 0:
                    recL += 1
                else:
                    win += 1
                r_at = float(r[int(u[0])])                    # ~ -D
                bail_pnl.append(r_at - BAIL_TK)               # flatten at the deep stop (taker)
                flip_pnl.append(r_at - (g - r_at) - FLIP_TK)  # reverse at -D, ride continuation (taker)
            if reach == 0:
                print(f"   -{D:<5}{0:>6}   —"); continue
            bail = np.array(bail_pnl).sum() / 1e4 * CAP / hrs
            flip = np.array(flip_pnl).sum() / 1e4 * CAP / hrs
            print(f"   -{D:<5}{reach:>6}{100*cont/reach:>6.0f}{100*recL/reach:>6.0f}{100*win/reach:>6.0f} | "
                  f"{bail:>+8.2f}{flip:>+8.2f}")
    print("\n  WIN% = of trades reaching -D, how many still end in PROFIT (clip risk).")
    print("  cont% = kept going past -D. bail/flip fire ONLY at -D, honest taker.")


if __name__ == "__main__":
    main()
