"""_s58_piece1_legdump.py — S58 PIECE 1: per-leg descriptor dump for the PER-COIN round.

Greg's round: per-coin refinement (Coinbase is the deploy platform), and: "is there any
distinct, unique characteristic of the trade that gets PAST our stack that we can fingerprint
to stop it?" — the S35 fingerprint move aimed at the k>=3 survivors that still lose.

Dumps every leg of the k=0 and k>=3 stack machines (th80/th100, c=0.5) on both tapes with a
full causal descriptor row, one CSV per coin x venue, for the coin-specific agents:

  kind         confirm (stack-passed fine dip) vs fallback (trailing-ARM flip)
  agree        agreement count at the pivot candidate (0-4) + the 4 member bits
  dive_depth   |60s flow lean| at the pivot
  clmx60       vm(60)/vm(600) at the pivot (S40 climax)
  er600        trend-efficiency over the 600s pre-window
  fade_vel     bp/min of the faded move over the 120s into the pivot (freight-train axis)
  lag_bp       pivot -> entry giveback in bp
  dur_s, gross_bp, net_real_bp (cb_real 8bp maker x2), hod/dow (UTC, bins exact; books approx)

Output: scratchpad legs CSVs (regenerable, not committed).
Usage: python scripts/_s58_piece1_legdump.py --venue bins|books
"""
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import CB_REAL, load_venue                     # noqa: E402
from _s58_piece1_stack import MEMBERS, StackReads                     # noqa: E402

OUT_DIR = os.environ.get(
    "S58_LEG_DIR",
    "/tmp/claude-0/-home-user-Markets/ff041bd0-93ad-5cb4-8995-09a39429fe35/scratchpad/s58_legs")
CELLS = ((80.0, 0.5), (100.0, 0.5))


def armed_stack_zigzag_tagged(mid, sr, arm_bp, fine_bp, k):
    """Round-3 machine, flips tagged (confirm_idx, pivot_idx, side, kind, agree)."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed_dn = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed_dn and m <= mid[hi_i] * (1 - f):
                agree = int(np.sum(sr.reads(hi_i)))
                if k == 0 or agree >= k:
                    flips.append((t, hi_i, -1, "confirm", agree)); mode = -1; lo_i = t
                    continue
            if armed_dn and m <= mid[hi_i] * (1 - a):
                flips.append((t, hi_i, -1, "fallback", int(np.sum(sr.reads(hi_i)))))
                mode = -1; lo_i = t
                continue
        if mode <= 0:
            armed_up = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed_up and m >= mid[lo_i] * (1 + f):
                agree = int(np.sum(sr.reads(lo_i)))
                if k == 0 or agree >= k:
                    flips.append((t, lo_i, +1, "confirm", agree)); mode = +1; hi_i = t
                    continue
            if armed_up and m >= mid[lo_i] * (1 + a):
                flips.append((t, lo_i, +1, "fallback", int(np.sum(sr.reads(lo_i)))))
                mode = +1; hi_i = t
    return flips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        sr = StackReads(mid, buy, sell)
        lean = None
        # 60s rolling lean for dive_depth
        w = 60
        cb = np.concatenate([[0.0], np.cumsum(buy)])
        cs = np.concatenate([[0.0], np.cumsum(sell)])
        i = np.arange(len(buy))
        lo = np.maximum(0, i + 1 - w)
        b_ = cb[i + 1] - cb[lo]
        s_ = cs[i + 1] - cs[lo]
        tot = b_ + s_
        lean = np.where(tot > 0, (b_ - s_) / np.where(tot > 0, tot, 1.0), 0.0)
        path = f"{OUT_DIR}/legs_{coin}_{args.venue}.csv"
        with open(path, "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["theta", "c", "k", "side", "kind", "agree",
                         *[f"b_{m}" for m in MEMBERS],
                         "dive_depth", "clmx60", "er600", "fade_vel_bpm", "lag_bp",
                         "dur_s", "gross_bp", "net_real_bp", "hod", "dow", "entry_idx"])
            for theta, c in CELLS:
                for k in (0, 3):
                    fl = armed_stack_zigzag_tagged(mid, sr, theta, c * theta, k)
                    for j in range(len(fl) - 1):
                        ci, pi, sd, kind, agree = fl[j]
                        xi = fl[j + 1][0]
                        ep, xp = mid[ci], mid[xi]
                        gross = sd * (xp - ep) / ep * 1e4
                        r = sr.reads(pi)
                        vm60 = sr._vm(pi, 60)
                        vm600 = sr._vm(pi, 600)
                        p0 = max(0, pi - 600)
                        pathlen = sr.cpath[pi] - sr.cpath[p0]
                        er = abs(mid[pi] - mid[p0]) / pathlen if pathlen > 0 else 0.0
                        f0 = max(0, pi - 120)
                        fade = -sd * (mid[pi] - mid[f0]) / mid[f0] * 1e4 / 2.0  # bp/min of faded move
                        lag = abs(ep - mid[pi]) / mid[pi] * 1e4
                        hod = int((ci // 3600) % 24)
                        dow = int((ci // 86400) % 7)
                        wr.writerow([theta, c, k, sd, kind, agree,
                                     *[int(x) for x in r],
                                     round(abs(lean[pi]), 4), round(vm60 / vm600, 3) if vm600 > 0 else 0,
                                     round(er, 3), round(fade, 2), round(lag, 2),
                                     xi - ci, round(gross, 2),
                                     round(gross - 2 * CB_REAL, 2), hod, dow, ci])
        print(f"[{coin} {args.venue}] wrote {path}")


if __name__ == "__main__":
    main()
