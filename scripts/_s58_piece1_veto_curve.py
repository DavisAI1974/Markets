"""_s58_piece1_veto_curve.py — S58 PIECE 1, ROUND 2: the PRECISION CURVE + the MISS LEDGER.

Round-1 verdict (`_s58_piece1_entry.py`): the v2 armed machine fires at oracle-class cadence
(the S56 v1 missed-trades problem is gone) but entries are ~coin-flip (win 46%, gross ~0 on
the 30d bins) — the false-fire cost eats the whole R5 lag prize. Greg's steer: the mid-band
$/hr ceiling was always MISSED TRADES — so every refinement must show its cost in coverage,
not just its per-leg lift.

ONE DEFINED TEST: step the confirm-moment veto strength
    none -> not_continue (R4 continue-class veto) -> opposing -> reversal (R4 positive class)
across theta x c on the 30d bins (+ books for venue shape), and print for every cell BOTH
sides of the trade-off:
  PRECISION: legs/hr, win%, gross bp/leg, net $/hr at cb_real + cb_top
  COVERAGE (the miss ledger): oracle legs/hr (hindsight zigzag swings >= theta), PART% =
    fraction of oracle legs the machine holds in the right direction at any point between the
    two pivots, CAP% = machine total gross bp / oracle total available bp.
Plus dive-depth (|60s flow lean| at the pivot candidate) as a GRADED descriptor: per-quartile
net/leg on the no-veto machine — the R5 P(real) axis as a curve, never a gate.

Windows: 30d x 5 Binance spot bins (instrument) + Coinbase books (deploy-venue shape; thin).
Renders: worst-10 losers + smallest-10 winners for the headline cell per coin (Greg's rule).

Usage:
  python scripts/_s58_piece1_veto_curve.py --venue bins
  python scripts/_s58_piece1_veto_curve.py --venue books
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s56_armed_gate import armed_fine_zigzag_v2                     # noqa: E402
from _s58_piece1_entry import (CAP, CB_REAL, DIVW, load_venue, score)  # noqa: E402
from odcore.info_dipole import divergence                            # noqa: E402

THETAS = (60.0, 80.0, 100.0)
CFRACS = (0.25, 0.5)
VETOES = ("none", "not_continue", "opposing", "reversal")
HEADLINE = (100.0, 0.5)          # worst/smallest render cell (mid of the grid, best r1 gross)


def armed_veto(mid, buy, sell, arm_bp, fine_bp, veto, divw=DIVW):
    """v2 arming; a fine dip confirms only if the causal divergence() read at the pivot
    candidate clears `veto`. Trailing-ARM fallback never vetoed (loss stays bounded).
    veto='none' reduces exactly to armed_fine_zigzag_v2."""
    if veto == "none":
        return armed_fine_zigzag_v2(mid, arm_bp, fine_bp)
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    cache = {}

    def gate_ok(pi):
        if pi in cache:
            return cache[pi]
        lo = max(0, pi - divw)
        dv = None
        if pi - lo >= 12:
            dv = divergence(buy[lo:pi + 1], sell[lo:pi + 1], float(mid[pi] - mid[lo]))
        if veto == "not_continue":
            ok = (dv is None) or dv["expect"] != "continue"
        elif veto == "opposing":
            ok = bool(dv) and bool(dv["opposing"])
        else:                                        # "reversal"
            ok = bool(dv) and dv["expect"] == "reversal"
        cache[pi] = ok
        return ok

    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            if mid[hi_i] >= mid[lo_i] * (1 + a) and m <= mid[hi_i] * (1 - f) and gate_ok(hi_i):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if mode == 1 and m <= mid[hi_i] * (1 - a):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
        if mode <= 0:
            if mid[lo_i] <= mid[hi_i] * (1 - a) and m >= mid[lo_i] * (1 + f) and gate_ok(lo_i):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if mode == -1 and m >= mid[lo_i] * (1 + a):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def oracle_legs(mid, theta_bp):
    """Hindsight zigzag pivots (swings >= theta): the available mid-band legs. Returns
    (pivot_idx array, side array, total available bp)."""
    th = theta_bp / 1e4
    piv = [0]
    hi_i = lo_i = 0
    d = 0
    for t in range(1, len(mid)):
        m = mid[t]
        if m > mid[hi_i]:
            hi_i = t
        if m < mid[lo_i]:
            lo_i = t
        if d >= 0 and m <= mid[hi_i] * (1 - th):
            piv.append(hi_i); d = -1; lo_i = t
        elif d <= 0 and m >= mid[lo_i] * (1 + th):
            piv.append(lo_i); d = +1; hi_i = t
    piv = sorted(set(piv))
    pv = np.asarray(piv)
    if len(pv) < 2:
        return pv, np.zeros(0), 0.0
    sw = np.abs(np.diff(mid[pv]) / mid[pv[:-1]]) * 1e4
    sides = np.sign(np.diff(mid[pv]))
    return pv, sides, float(np.sum(sw))


def miss_ledger(mid, flips, theta_bp):
    """PART% (oracle legs held in the right direction at any point) + CAP% (gross bp taken /
    oracle bp available) + oracle legs count."""
    pv, sides, avail = oracle_legs(mid, theta_bp)
    if len(pv) < 2 or len(flips) < 2:
        return 0, 0.0, 0.0
    n = len(mid)
    pos = np.zeros(n, dtype=np.int8)
    for (c, p, s) in flips:
        pos[int(c):] = int(s)
    part = 0
    for k in range(len(pv) - 1):
        d = int(sides[k])
        if d != 0 and np.any(pos[pv[k]:pv[k + 1]] == d):
            part += 1
    res = score(mid, flips, 1.0)
    taken = float(np.sum(res["gross"])) if res else 0.0
    return len(pv) - 1, 100.0 * part / (len(pv) - 1), 100.0 * taken / avail if avail > 0 else 0.0


def lean_series_60(buy, sell):
    """60s rolling signed flow lean (buy-sell)/(buy+sell) — the dive-depth channel."""
    w = 60
    cb = np.concatenate([[0.0], np.cumsum(buy)])
    cs = np.concatenate([[0.0], np.cumsum(sell)])
    n = len(buy)
    i = np.arange(n)
    lo = np.maximum(0, i + 1 - w)
    b = cb[i + 1] - cb[lo]
    s = cs[i + 1] - cs[lo]
    tot = b + s
    return np.where(tot > 0, (b - s) / np.where(tot > 0, tot, 1.0), 0.0)


def dive_quartiles(mid, buy, sell, flips, hrs):
    """No-veto machine legs graded by dive_depth=|lean@pivot| quartile: net bp/leg @cb_real."""
    res = score(mid, flips, hrs)
    if res is None or res["n"] < 20:
        return None
    lean = lean_series_60(buy, sell)
    pv = np.asarray([int(p) for (c, p, s) in flips[:-1]])
    depth = np.abs(lean[pv])
    net = res["gross"] - 2 * CB_REAL
    qs = np.quantile(depth, [0.25, 0.5, 0.75])
    out = []
    lo = -1.0
    for q in list(qs) + [np.inf]:
        m = (depth > lo) & (depth <= q)
        out.append((int(np.sum(m)), float(np.mean(net[m])) if np.any(m) else 0.0))
        lo = q
    return out


def render_worst(coin, mid, flips, hrs, theta, c, fh):
    res = score(mid, flips, hrs)
    if res is None:
        return
    net = res["gross"] - 2 * CB_REAL
    order = np.argsort(net)
    win_i = [i for i in order if net[i] > 0]
    fh.write(f"\n[{coin} th{theta:.0f} c{c} no-veto] WORST 10 LOSERS (net bp @cb_real):\n")
    for i in order[:10]:
        fh.write(f"  entry_idx {res['ei'][i]:>8}  net {net[i]:>+8.1f}\n")
    fh.write(f"[{coin}] SMALLEST 10 WINNERS:\n")
    for i in win_i[:10]:
        fh.write(f"  entry_idx {res['ei'][i]:>8}  net {net[i]:>+8.1f}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    rdir = os.path.join("docs", "renders", "s58")
    os.makedirs(rdir, exist_ok=True)
    rf = open(os.path.join(rdir, f"p1r2_worst_{args.venue}.txt"), "w")

    for coin, mid, buy, sell, hrs, _bucket in load_venue(args.venue):
        print(f"\n=== {coin} {args.venue} ({hrs:.1f}h) — veto curve + miss ledger "
              f"(@$5k, maker both sides) ===")
        print(f"{'th':>4} {'c':>4} {'veto':>13} | {'legs/h':>6} {'win%':>4} {'gr/leg':>7} "
              f"{'$real':>8} {'$top':>7} | {'orcl/h':>6} {'PART%':>5} {'CAP%':>5}")
        for theta in THETAS:
            for c in CFRACS:
                for veto in VETOES:
                    fl = armed_veto(mid, buy, sell, theta, c * theta, veto)
                    res = score(mid, fl, hrs)
                    if res is None:
                        print(f"{theta:>4.0f} {c:>4.2f} {veto:>13} | (no legs)")
                        continue
                    n_or, part, cap = miss_ledger(mid, fl, theta)
                    dreal = float(np.sum(CAP * (res["gross"] - 2 * CB_REAL) / 1e4)) / hrs
                    dtop = float(np.sum(CAP * res["gross"] / 1e4)) / hrs
                    print(f"{theta:>4.0f} {c:>4.2f} {veto:>13} | {res['lph']:>6.2f} "
                          f"{100 * np.mean(res['gross'] > 0):>4.0f} "
                          f"{np.mean(res['gross']):>+7.2f} {dreal:>+8.2f} {dtop:>+7.2f} | "
                          f"{n_or / hrs:>6.2f} {part:>5.0f} {cap:>5.0f}")
                    if veto == "none" and (theta, c) == HEADLINE:
                        render_worst(coin, mid, fl, hrs, theta, c, rf)
        # dive-depth graded curve on the no-veto headline machine
        fl = armed_veto(mid, buy, sell, HEADLINE[0], HEADLINE[1] * HEADLINE[0], "none")
        dq = dive_quartiles(mid, buy, sell, fl, hrs)
        if dq:
            row = "  ".join(f"Q{k + 1}:{n}n/{v:+.1f}bp" for k, (n, v) in enumerate(dq))
            print(f"  dive-depth quartiles (th{HEADLINE[0]:.0f} c{HEADLINE[1]} no-veto, "
                  f"net/leg @cb_real): {row}")
    rf.close()


if __name__ == "__main__":
    main()
