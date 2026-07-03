"""_s58_piece1_reruns.py — S58 PIECE 1, ROUND 6: the per-coin member maps RE-EARNED as
MACHINE configs (Greg's order: fallback round first — verdict: baseline fallback everywhere,
bnc25 carried as a BTC-only candidate).

Leg-slice reads are conditional expectations; an always-in flip machine is path-dependent
(the XRP agent proved the danger: its "stack lift" was composition). So every agent map runs
as an actual machine against its own k0/k3 baselines.

HONESTY FLAG: the member maps were derived from THIS 30d tape (agent leg analysis). This
round tests machine-dynamics validity (composition/path), with per-week stability as the
internal check — it is NOT an OOS verdict; that waits on accrued Coinbase books per venue.

Configs (thresholds = the agents' stated anchors, FIXED, documented — no re-tuning here):
  sol_fadeclmx  confirm iff fade_vel>=27bpm AND b_climax        (bins' only positive confirm region)
  btc_opp       confirm iff agree>=3 AND b_opposing             (opposing-mandatory)
  btc_opp_bnc   same + bnc25 bounce fallback                    (round-5 BTC candidate)
  doge_clmxexh  confirm iff clmx60>=3.4 AND b_exhausting        (climax-led map)
  doge_ce_noopp same AND NOT b_opposing                         (th100 cascade veto variant)
  xrp_dcveto    confirm on any dip EXCEPT the death combo       (opposing & climax & NOT exhausting)
Baselines per coin: k0 (naive, the Coinbase shape) and k>=3 (round-3 stack).
ETH: dropped from the round (board verdict) — not run.

Usage: python scripts/_s58_piece1_reruns.py --venue bins|books
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
WEEK_S = 7 * 24 * 3600


class Reads2(StackReads):
    """StackReads + causal fade-velocity and raw clmx at the pivot candidate."""

    def fade(self, pi, dirn):
        """bp/min of the move being faded over the 120s into the pivot (dirn = NEW side:
        -1 at a peak candidate fades an up-move, +1 at a valley fades a down-move)."""
        p0 = max(0, pi - 120)
        mv = (self.mid[pi] - self.mid[p0]) / self.mid[p0] * 1e4
        return -dirn * mv / 2.0

    def clmx(self, pi):
        vm600 = self._vm(pi, 600)
        return (self._vm(pi, 60) / vm600) if vm600 > 0 else 0.0


def make_pred(name):
    """Returns pred(sr, pi, dirn) -> bool for the confirm gate."""
    if name == "k0":
        return lambda sr, pi, d: True
    if name == "k3":
        return lambda sr, pi, d: int(np.sum(sr.reads(pi))) >= 3
    if name == "sol_fadeclmx":
        return lambda sr, pi, d: sr.fade(pi, d) >= 27.0 and bool(sr.reads(pi)[2])
    if name in ("btc_opp", "btc_opp_bnc"):
        return lambda sr, pi, d: int(np.sum(sr.reads(pi))) >= 3 and bool(sr.reads(pi)[0])
    if name == "doge_clmxexh":
        return lambda sr, pi, d: sr.clmx(pi) >= 3.4 and bool(sr.reads(pi)[1])
    if name == "doge_ce_noopp":
        return lambda sr, pi, d: (sr.clmx(pi) >= 3.4 and bool(sr.reads(pi)[1])
                                  and not bool(sr.reads(pi)[0]))
    if name == "xrp_dcveto":
        def p(sr, pi, d):
            r = sr.reads(pi)
            return not (bool(r[0]) and bool(r[2]) and not bool(r[1]))   # veto the death combo
        return p
    raise ValueError(name)


def machine(mid, sr, arm_bp, fine_bp, pred, ffb_bp=0.0):
    """Armed zigzag, confirm gated by pred, baseline or bounce fallback."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    fb = ffb_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    pend = 0
    pext = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if pend == -1:
            if m < mid[pext]:
                pext = t
            if m >= mid[pext] * (1 + fb):
                flips.append((t, hi_i, -1)); mode = -1; pend = 0; lo_i = t
                continue
        elif pend == +1:
            if m > mid[pext]:
                pext = t
            if m <= mid[pext] * (1 - fb):
                flips.append((t, lo_i, +1)); mode = +1; pend = 0; hi_i = t
                continue
        if pend == 0 and mode >= 0:
            armed_dn = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed_dn and m <= mid[hi_i] * (1 - f) and pred(sr, hi_i, -1):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if armed_dn and m <= mid[hi_i] * (1 - a):
                if fb <= 0:
                    flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                else:
                    pend = -1; pext = t
                continue
        if pend == 0 and mode <= 0:
            armed_up = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed_up and m >= mid[lo_i] * (1 + f) and pred(sr, lo_i, +1):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if armed_up and m >= mid[lo_i] * (1 + a):
                if fb <= 0:
                    flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                else:
                    pend = +1; pext = t
    return flips


COIN_CONFIGS = {
    "sol": ("k0", "k3", "sol_fadeclmx"),
    "btc": ("k0", "k3", "btc_opp", "btc_opp_bnc"),
    "doge": ("k0", "k3", "doge_clmxexh", "doge_ce_noopp"),
    "xrp": ("k0", "k3", "xrp_dcveto"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        if coin not in COIN_CONFIGS:
            continue
        sr = Reads2(mid, buy, sell)
        print(f"\n=== {coin} {args.venue} ({hrs:.1f}h) — member-map machine reruns "
              f"(c{C}, @$5k maker) ===")
        print(f"  {'config':>14} {'th':>4} | {'legs/h':>6} {'win%':>4} {'gr/leg':>7} "
              f"{'$real':>8} {'$top':>7} | {'PART%':>5} {'CAP%':>5} | {'wk+':>4} {'zw':>5}")
        for name in COIN_CONFIGS[coin]:
            pred = make_pred(name)
            ffb = 0.25 * 1 if name == "btc_opp_bnc" else 0.0
            for theta in THETAS:
                fl = machine(mid, sr, theta, C * theta, pred,
                             ffb_bp=(0.25 * theta if name == "btc_opp_bnc" else 0.0))
                res = score(mid, fl, hrs)
                if res is None:
                    print(f"  {name:>14} {theta:>4.0f} | (no legs)")
                    continue
                n_or, part, cap = miss_ledger(mid, fl, theta)
                dollars = CAP * (res["gross"] - 2 * CB_REAL) / 1e4
                dreal = float(np.sum(dollars)) / hrs
                dtop = float(np.sum(CAP * res["gross"] / 1e4)) / hrs
                bkt = (res["ei"] // WEEK_S).astype(int)
                sums = np.bincount(bkt, weights=dollars)
                wk = sums[np.bincount(bkt) > 0]
                zw = float(np.mean(wk) / (np.std(wk, ddof=1) / np.sqrt(len(wk)))) if len(wk) > 1 else 0.0
                print(f"  {name:>14} {theta:>4.0f} | {res['lph']:>6.2f} "
                      f"{100 * np.mean(res['gross'] > 0):>4.0f} {np.mean(res['gross']):>+7.2f} "
                      f"{dreal:>+8.2f} {dtop:>+7.2f} | {part:>5.0f} {cap:>5.0f} | "
                      f"{np.sum(wk > 0):>2d}/{len(wk):<2d} {zw:>+5.1f}")


if __name__ == "__main__":
    main()
