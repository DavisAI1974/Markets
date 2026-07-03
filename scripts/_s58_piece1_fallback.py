"""_s58_piece1_fallback.py — S58 PIECE 1, ROUND 5: the FALLBACK REFINEMENT (Greg: fallback
then reruns).

STRUCTURAL FACT (logged in notes): in the k0 machine the fallback ~never fires (the first
fine dip confirms before adverse reaches theta; XRP agent: "k0 is all-confirm"). The fallback
bleed lives in the VETOED machines (54-63% of k>=3 legs) — and the per-coin member-map
re-runs (next round) will lean on fallbacks harder. Fix the fallback first so the reruns
inherit it.

ONE DEFINED TEST (k>=3 stack machines, both thetas, c=0.5):
  baseline  v2 fallback — flip the instant adverse >= ARM off the favorable extreme
            (S56: structurally sells troughs; BTC worst-fallbacks = short-duration
            trough-sells; SOL: fallback = 62% of legs = the fee/count bleed).
  bounce    fallback-PENDING once adverse >= ARM with no vetted confirm: track the running
            adverse extreme, flip on the first f_fb recovery off it (f_fb in {25%, 50%} of
            theta) — enter on the bounce, not in the hole. Pivot recorded at the original
            favorable extreme (same swing semantics).
RISK ACCOUNTING: the loss bound loosens from ~theta to theta + depth-to-first-bounce -> the
per-leg MAX-ADVERSE distribution (p95/max, bp) is a first-class output; a blown tail kills
the refinement regardless of P&L.

Scoring identical to prior rounds (mid fills, $5k, cb_real 8bp maker x2) + confirm/fallback
split + miss ledger + worst-10 fallback render.

Usage: python scripts/_s58_piece1_fallback.py --venue bins|books
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import CAP, CB_REAL, load_venue, score        # noqa: E402
from _s58_piece1_stack import StackReads                             # noqa: E402
from _s58_piece1_veto_curve import miss_ledger                       # noqa: E402

THETAS = (80.0, 100.0)
C = 0.5
K = 3
FFBS = (0.0, 0.25, 0.5)      # 0.0 = baseline v2 immediate flip


def armed_stack_zigzag_bfb(mid, sr, arm_bp, fine_bp, k, ffb_bp):
    """k>=3 stack machine with a BOUNCE fallback (ffb_bp=0 -> exact round-3 baseline).
    Returns tagged flips (confirm_idx, pivot_idx, side, kind)."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    fb = ffb_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    pend = 0          # 0 none | -1 pending short flip | +1 pending long flip
    pext = 0          # running adverse-extreme idx while pending

    def ok(pi):
        return int(np.sum(sr.reads(pi))) >= k

    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if pend == -1:                                  # waiting to flip short on a bounce
            if m < mid[pext]:
                pext = t
            if m >= mid[pext] * (1 + fb):
                flips.append((t, hi_i, -1, "fallback")); mode = -1; pend = 0; lo_i = t
                continue
        elif pend == +1:
            if m > mid[pext]:
                pext = t
            if m <= mid[pext] * (1 - fb):
                flips.append((t, lo_i, +1, "fallback")); mode = +1; pend = 0; hi_i = t
                continue
        if pend == 0 and mode >= 0:
            armed_dn = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed_dn and m <= mid[hi_i] * (1 - f) and ok(hi_i):
                flips.append((t, hi_i, -1, "confirm")); mode = -1; lo_i = t
                continue
            if armed_dn and m <= mid[hi_i] * (1 - a):
                if fb <= 0:
                    flips.append((t, hi_i, -1, "fallback")); mode = -1; lo_i = t
                    continue
                pend = -1; pext = t
                continue
        if pend == 0 and mode <= 0:
            armed_up = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed_up and m >= mid[lo_i] * (1 + f) and ok(lo_i):
                flips.append((t, lo_i, +1, "confirm")); mode = +1; hi_i = t
                continue
            if armed_up and m >= mid[lo_i] * (1 + a):
                if fb <= 0:
                    flips.append((t, lo_i, +1, "fallback")); mode = +1; hi_i = t
                    continue
                pend = +1; pext = t
    return flips


def max_adverse(mid, flips):
    """Per-leg max adverse excursion (bp) from entry to exit."""
    out = []
    for j in range(len(flips) - 1):
        ci, _pi, sd = flips[j][0], flips[j][1], flips[j][2]
        xi = flips[j + 1][0]
        seg = mid[ci:xi + 1]
        adv = -sd * (seg - mid[ci]) / mid[ci] * 1e4
        out.append(float(np.max(adv)))
    return np.asarray(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    rdir = os.path.join("docs", "renders", "s58")
    os.makedirs(rdir, exist_ok=True)
    rf = open(os.path.join(rdir, f"p1r5_fallback_worst_{args.venue}.txt"), "w")

    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        sr = StackReads(mid, buy, sell)
        print(f"\n=== {coin} {args.venue} ({hrs:.1f}h) — bounce-fallback round "
              f"(k>={K} c{C}, @$5k maker) ===")
        print(f"  {'cell':>16} | {'legs/h':>6} {'fb%':>4} {'gr/leg':>7} {'grCONF':>7} "
              f"{'grFB':>7} {'$real':>8} | {'adv p95':>7} {'advMAX':>7} | {'PART%':>5} {'CAP%':>5}")
        for theta in THETAS:
            for ffb in FFBS:
                fl = armed_stack_zigzag_bfb(mid, sr, theta, C * theta, K, ffb * theta)
                plain = [(c_, p, s) for (c_, p, s, _k2) in fl]
                res = score(mid, plain, hrs)
                if res is None:
                    print(f"  th{theta:.0f} ffb{ffb:.2f} | (no legs)")
                    continue
                kinds = np.asarray([k2 for (_c, _p, _s, k2) in fl[:-1]])
                gross = res["gross"]
                gc = gross[kinds == "confirm"]
                gf = gross[kinds == "fallback"]
                adv = max_adverse(mid, plain)
                n_or, part, cap = miss_ledger(mid, plain, theta)
                dreal = float(np.sum(CAP * (gross - 2 * CB_REAL) / 1e4)) / hrs
                tag = "base" if ffb == 0 else f"bnc{int(ffb * 100)}"
                print(f"  th{theta:.0f} {tag:>6} c{C} | {res['lph']:>6.2f} "
                      f"{100 * np.mean(kinds == 'fallback'):>4.0f} {np.mean(gross):>+7.2f} "
                      f"{np.mean(gc) if len(gc) else 0:>+7.2f} "
                      f"{np.mean(gf) if len(gf) else 0:>+7.2f} {dreal:>+8.2f} | "
                      f"{np.percentile(adv, 95):>7.0f} {np.max(adv):>7.0f} | "
                      f"{part:>5.0f} {cap:>5.0f}")
                if ffb == FFBS[-1] or ffb == 0.0:
                    net = gross - 2 * CB_REAL
                    fbi = np.nonzero(kinds == "fallback")[0]
                    worst = fbi[np.argsort(net[fbi])][:10] if len(fbi) else []
                    rf.write(f"\n[{coin} th{theta:.0f} {tag}] WORST 10 FALLBACK legs:\n")
                    for i in worst:
                        rf.write(f"  entry {res['ei'][i]:>8} net {net[i]:>+8.1f} "
                                 f"adv {adv[i]:>6.0f}\n")
    rf.close()


if __name__ == "__main__":
    main()
