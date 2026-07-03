"""_s55_dump_legs_dipole.py — leg tables WITH dipole descriptor columns (R1 of the S55 multi-role
registry; Greg: "use it as a descriptor of trades... it should describe how deep or steep the dive
is too — wire that description in").

Regenerates the zigzag leg tables on the 30d Bybit bins with, per leg, the dipole read at the
OPENING flip (all causal — computed from data at/before the pivot, which precedes the confirm):
  dive_depth   |lean@pivot|, 60s rolling flow imbalance — the S40/S47 validated size descriptor
               (deeper dive -> bigger |move|; deployed in the swing_maker SIZE axis)
  lean_pivot   signed lean at the pivot (sign-aligned = lean * -side: positive = flow leaning
               INTO the old leg at its extreme, the S40 anti-symmetry handled per Never-pool-sign-blind)
  steepness    |d lean / 10s| at the pivot — S40 verdict: NOISE (kept as a column to re-confirm)
  dipole_class divergence() expect at the pivot window (reversal/flip_risk/weakening/continue)
  rev_conv     divergence() reversal_conviction
Validation printed per coin: corr(dive_depth, |gross|) — expect +0.05..+0.17 sign-consistent
(S40/S47); corr(steepness, |gross|) — expect ~0.

Needs bins in /tmp/backfill/ (see S55 kickoff). Output: _s55_legs_zigzag_bybit30d_dipole.csv
"""
import csv
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS          # noqa: E402
from _s52_accum_vs_oneshot import _price_zigzag, DIVW     # noqa: E402
from odcore.info_dipole import divergence                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAN_W = 60
STEEP_D = 10
RT = 11.0


def _iso(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main():
    rows = []
    print(f"{'coin':<6}{'theta':>7}{'legs':>6}{'corr(depth,|move|)':>20}{'corr(steep,|move|)':>20}")
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] no bins — skipped (re-pull per kickoff)")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        import json
        with open(p) as f:
            t0 = min(float(k) for k in json.load(f).keys())
        mid = np.asarray(mid, float)
        b, s_ = np.asarray(buy, float), np.asarray(sell, float)
        cb, cs = np.cumsum(b), np.cumsum(s_)

        def lean_at(t):
            t = max(t, LEAN_W)
            bw, sw = cb[t] - cb[t - LEAN_W], cs[t] - cs[t - LEAN_W]
            tot = bw + sw
            return (bw - sw) / tot if tot > 0 else 0.0

        for th in (150.0, 100.0):
            fl = _price_zigzag(mid, th)
            depth_v, steep_v, move_v = [], [], []
            for a, bb in zip(fl[:-1], fl[1:]):
                ci, pi, side = int(a[0]), int(a[1]), int(a[2])
                cj = int(bb[0])
                lo = max(0, pi - DIVW)
                if pi - lo < 12 or pi < LEAN_W + STEEP_D:
                    continue
                ln = lean_at(pi)
                depth = abs(ln)
                steep = abs(ln - lean_at(pi - STEEP_D))
                d = divergence(b[lo:pi + 1], s_[lo:pi + 1], float(mid[pi] - mid[lo]))
                gross = side * (mid[cj] - mid[ci]) / mid[ci] * 1e4
                rows.append([f"{coin}_bybit_perp", f"zz{th:.0f}",
                             "LONG" if side > 0 else "SHORT",
                             _iso(t0 + ci), _iso(t0 + cj),
                             round((cj - ci) / 3600.0, 2),
                             round(mid[ci], 6), round(mid[cj], 6),
                             round(gross, 1), round(gross - RT, 1),
                             round(depth, 4), round(ln * -side, 4), round(steep, 4),
                             d["expect"] if d else "n/a",
                             d["reversal_conviction"] if d else ""])
                depth_v.append(depth); steep_v.append(steep); move_v.append(abs(gross))
            if len(move_v) > 10:
                cd = np.corrcoef(depth_v, move_v)[0, 1]
                cst = np.corrcoef(steep_v, move_v)[0, 1]
                print(f"{coin:<6}{th:>7.0f}{len(move_v):>6}{cd:>20.3f}{cst:>20.3f}")

    out = os.path.join(ROOT, "_s55_legs_zigzag_bybit30d_dipole.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "engine", "side", "entry_utc", "exit_utc", "hold_h",
                    "entry_px", "exit_px", "gross_bps", "net_bps_taker",
                    "dive_depth", "lean_pivot_signed", "steepness",
                    "dipole_class", "rev_conv"])
        w.writerows(rows)
    print(f"\n-> {out} ({len(rows)} legs)")


if __name__ == "__main__":
    main()
