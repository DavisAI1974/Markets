"""_s58_piece1_stack.py — S58 PIECE 1, ROUND 3: the STACK (tools complementary, not competing).

Round-2 verdict: the divergence veto lifts gross/leg 2-5x at mid-band with ~zero coverage cost
(the fallback keeps PART% at 95-100) — but a single tool leaves CAP% at 3-4% and cb_real
negative. Greg: get back to STACKING. The miners' synthesis (S38-S57 handoffs + code sweep):
mid-band is the untested middle — the archive's tools were killed fine or coarse, as gates or
under the dead rebate regime, almost never as graded stack members at theta 60-100.

ONE DEFINED TEST: at every armed dip candidate, compute FOUR cheap causal reads at the pivot
candidate and confirm the dip only when AGREEMENT >= k; sweep k = 0..4 (k=0 == round-2 "none").
Pure agreement count — no fitted weights, nothing to tune off one window. Members (each reads
different physics; thresholds are UNTUNED anchors from their source sessions, documented):

  B1 OPPOSING    divergence() aligned_flow < 0 — flow opposes the leg being faded (S36b factor
                 1; round-2's best single veto family).
  B2 EXHAUSTING  divergence() late-half |imbalance| < early-half — the leader weakening (S36b
                 factor 2; the RollingFlow.exhausting() deploy form).
  B3 CLIMAX      clmx = vm(60)/vm(600) at the pivot >= 1.5 — capitulation volume spike (S40
                 "~2x at the turn", halved as a conservative untuned anchor; S47's only
                 sign-consistent win/lose lever, killed only as a GATE, never tried mid-band).
  B4 CHOP        trend-efficiency ratio ER = |net move| / path length over the pre-window
                 <= 0.5 — a fine dip inside a high-ER freight trend is the fakeout class
                 (S36b regime gate, parked per-cell, never mid-band).

MODE-0 FIX (S56 deadlock, resurfaced round 2 as BTC/books "(no legs)"): the trailing-ARM
fallback now also fires in mode 0 (bootstrap) — the machine can no longer be stranded forever
by a filter that vetoes the first confirm; loss stays bounded at ~ARM by construction.

Scoring identical to rounds 1-2: always-in-market flip machine, mid fills, $5k flat,
maker-both-sides fee columns, miss ledger (oracle legs, PART%, CAP%). Plus a per-member
marginal table (each member as the sole required read) at the headline cell, so we see which
members carry and which are redundant.

Usage:
  python scripts/_s58_piece1_stack.py --venue bins
  python scripts/_s58_piece1_stack.py --venue books
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import CAP, CB_REAL, DIVW, load_venue, score   # noqa: E402
from _s58_piece1_veto_curve import miss_ledger                        # noqa: E402
from odcore.info_dipole import divergence                             # noqa: E402

THETAS = (80.0, 100.0)
CFRACS = (0.25, 0.5)
KS = (0, 1, 2, 3, 4)
CLMX_ANCHOR = 1.5          # S40: ~2x climax at the turn; halved, untuned
ER_ANCHOR = 0.5            # trend-efficiency: <=0.5 = not a freight trend; untuned
MEMBERS = ("opposing", "exhausting", "climax", "chop")
HEADLINE = (100.0, 0.5)


class StackReads:
    """Causal per-pivot-candidate stack reads, cached. All windows end AT the pivot."""

    def __init__(self, mid, buy, sell, divw=DIVW):
        self.mid = mid
        self.buy = buy
        self.sell = sell
        self.divw = divw
        self.cb = np.concatenate([[0.0], np.cumsum(buy)])
        self.cs = np.concatenate([[0.0], np.cumsum(sell)])
        self.cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(mid)))])
        self.cache = {}

    def _vm(self, t, w):
        lo = max(0, t + 1 - w)
        tot = (self.cb[t + 1] - self.cb[lo]) + (self.cs[t + 1] - self.cs[lo])
        return tot / (t + 1 - lo)

    def reads(self, pi):
        if pi in self.cache:
            return self.cache[pi]
        lo = max(0, pi - self.divw)
        r = np.zeros(4, dtype=bool)
        if pi - lo >= 12:
            dv = divergence(self.buy[lo:pi + 1], self.sell[lo:pi + 1],
                            float(self.mid[pi] - self.mid[lo]))
            if dv is not None:
                r[0] = bool(dv["opposing"])
                r[1] = bool(dv["exhausting"])
            vm60 = self._vm(pi, 60)
            vm600 = self._vm(pi, 600)
            r[2] = vm600 > 0 and (vm60 / vm600) >= CLMX_ANCHOR
            path = self.cpath[pi] - self.cpath[lo]
            net = abs(self.mid[pi] - self.mid[lo])
            r[3] = path > 0 and (net / path) <= ER_ANCHOR
        self.cache[pi] = r
        return r


def armed_stack_zigzag(mid, sr: StackReads, arm_bp, fine_bp, k=0, member=None):
    """v2 arming + agreement->=k stack confirm; mode-0-safe trailing fallback (bootstrap fix).
    member: require that single member instead of the count (marginal table)."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    midx = MEMBERS.index(member) if member else -1

    def ok(pi):
        if k == 0 and member is None:
            return True
        r = sr.reads(pi)
        if member is not None:
            return bool(r[midx])
        return int(np.sum(r)) >= k

    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed_dn = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed_dn and m <= mid[hi_i] * (1 - f) and ok(hi_i):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            # trailing fallback — now ALSO in mode 0 (bootstrap; S56 deadlock fix)
            if armed_dn and m <= mid[hi_i] * (1 - a):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
        if mode <= 0:
            armed_up = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed_up and m >= mid[lo_i] * (1 + f) and ok(lo_i):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if armed_up and m >= mid[lo_i] * (1 + a):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def row(mid, hrs, theta, fl, label):
    res = score(mid, fl, hrs)
    if res is None:
        print(f"  {label:>14} | (no legs)")
        return
    n_or, part, cap = miss_ledger(mid, fl, theta)
    dreal = float(np.sum(CAP * (res["gross"] - 2 * CB_REAL) / 1e4)) / hrs
    dtop = float(np.sum(CAP * res["gross"] / 1e4)) / hrs
    print(f"  {label:>14} | {res['lph']:>6.2f} {100 * np.mean(res['gross'] > 0):>4.0f} "
          f"{np.mean(res['gross']):>+7.2f} {dreal:>+8.2f} {dtop:>+7.2f} | "
          f"{n_or / hrs:>6.2f} {part:>5.0f} {cap:>5.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        sr = StackReads(mid, buy, sell)
        print(f"\n=== {coin} {args.venue} ({hrs:.1f}h) — STACK agreement curve "
              f"(@$5k, maker both sides) ===")
        print(f"  {'cell':>14} | {'legs/h':>6} {'win%':>4} {'gr/leg':>7} {'$real':>8} "
              f"{'$top':>7} | {'orcl/h':>6} {'PART%':>5} {'CAP%':>5}")
        for theta in THETAS:
            for c in CFRACS:
                for k in KS:
                    fl = armed_stack_zigzag(mid, sr, theta, c * theta, k=k)
                    row(mid, hrs, theta, fl, f"th{theta:.0f} c{c:.2f} k>={k}")
        th, c = HEADLINE
        print(f"  -- member marginals (th{th:.0f} c{c}) --")
        for mname in MEMBERS:
            fl = armed_stack_zigzag(mid, sr, th, c * th, member=mname)
            row(mid, hrs, th, fl, mname)


if __name__ == "__main__":
    main()
