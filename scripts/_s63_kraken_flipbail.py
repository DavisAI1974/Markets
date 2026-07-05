"""_s63_kraken_flipbail.py — FLIP IF WE CAN, BAIL IF NOT (Greg). Loss management on the Kraken detector.

The 10-loser renders showed the big losers are TREND-RUNOVERS: the flow-lean detector re-enters the
wrong side inside one sustained trend and bleeds to the forced exit (MAE@~100%). Fix (Greg): when a
trade goes underwater and a real MULTI-HOUR TREND is running against us -> FLIP to go WITH the trend
(turn the loser into a trend-follow winner). When it's NOT a clear trend (a dip that may recover) ->
BAIL (quick stop). The multi-hour trend is the separator: big losers have the 1h/4h trend against them
(~0.69, S63 diagnostic); dip-recoveries do not.

Mechanics, per swing [entry ci -> next flip nci] (entries from retime_flips = early-arm; SOL reversed):
  walk to first aj where P&L r <= -arm bp.
    none reached          -> RIDE: pnl = gross (maker, 0bp)
    trend AGAINST side & strong (sign(mom_W@aj)==-side and |mom_W|>=thr) -> FLIP: reverse aj->nci,
        pnl = r_arm - (gross - r_arm) - FLIP_FEE      (taker cross to reverse)
    else                  -> BAIL: pnl = r_arm - BAIL_FEE   (taker cross to flatten at the stop)
Honest Kraken taker costs on the managed legs: FLIP_FEE=22bp (close+open cross), BAIL_FEE=11bp (one
cross); RIDE stays maker 0bp. Also shows the 0-fee ceiling. Grade net $/hr @ $5k, per-week.

Usage:  python scripts/_s63_kraken_flipbail.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1; WK = 7 * 24 * 3600
FLIP_FEE, BAIL_FEE = 22.0, 11.0
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
ARMS = [15, 20, 30]
TRENDW = [3600, 14400]        # 1h, 4h trend gate
THR = [0.0, 30.0]             # min |mom_W| (bp) to call it a real trend worth flipping into


def manage(mid, lm, entries, sgn, arm, W, thr, fee0=False):
    """Return per-swing pnl + action tallies for flip-if-can/bail-if-not."""
    ff = 0.0 if fee0 else FLIP_FEE
    bf = 0.0 if fee0 else BAIL_FEE
    pnl = []; eidx = []; nflip = nbail = nride = 0
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        seg = mid[ci:nci + 1]
        r = side * np.log(seg / mid[ci]) * 1e4
        gross = float(r[-1])
        u = np.where(r <= -arm)[0]
        if len(u) == 0:
            pnl.append(gross); nride += 1; eidx.append(ci); continue
        aj_local = int(u[0]); aj = ci + aj_local; r_arm = float(r[aj_local])
        if aj - W >= 0:
            mom = (lm[aj] - lm[aj - W]) * 1e4               # signed trend at the arm point
        else:
            mom = 0.0
        trend_against = (np.sign(mom) == -side) and (abs(mom) >= thr)
        if trend_against:                                   # FLIP: reverse aj->nci, follow the trend
            pnl.append(r_arm - (gross - r_arm) - ff); nflip += 1
        else:                                               # BAIL: flatten at the stop
            pnl.append(r_arm - bf); nbail += 1
        eidx.append(ci)
    return np.array(pnl), np.array(eidx), (nflip, nbail, nride)


def netdph(pnl, hrs):
    return pnl.sum() / 1e4 * CAP / hrs


def main():
    print("=== FLIP-IF-CAN / BAIL-IF-NOT on the Kraken flow-lean detector (retime entries) ===")
    print("    net $/hr @ $5k, kr_mk0 maker rides + taker flip(22)/bail(11); (ceil)=0-fee upper bound\n")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); lm = np.log(mid)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
        # retime baseline (ride everything, no management)
        base = []
        for k in range(len(entries) - 1):
            ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
            if mid[ci] > 0 and mid[nci] > 0 and nci > ci:
                base.append(side * np.log(mid[nci] / mid[ci]) * 1e4)
        base = np.array(base); base_net = netdph(base, hrs)
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"[{tag}]  retime{int(eps)} baseline (ride all) net {base_net:+.2f} $/hr")
        print(f"   {'arm':>4}{'trW':>5}{'thr':>5}{'net$/h':>8}{'ceil':>7}{'flip':>6}{'bail':>6}{'ride':>6}"
              f"   per-week net")
        for arm in ARMS:
            for W in TRENDW:
                for thr in THR:
                    pnl, eidx, (nf, nb, nr) = manage(mid, lm, entries, sgn, arm, W, thr)
                    pnl0, _, _ = manage(mid, lm, entries, sgn, arm, W, thr, fee0=True)
                    week = (eidx // WK).astype(int)
                    pw = []
                    for wk in sorted(set(week)):
                        mk = week == wk
                        if mk.sum() < 2:
                            continue
                        hh = (np.ptp(eidx[mk]) + 1) / 3600.0
                        pw.append(netdph(pnl[mk], hh))
                    print(f"   -{arm:<3}{W//3600:>4}h{thr:>5.0f}{netdph(pnl,hrs):>+8.2f}"
                          f"{netdph(pnl0,hrs):>+7.2f}{nf:>6}{nb:>6}{nr:>6}   "
                          + " ".join(f"{v:+.0f}" for v in pw))
        print()


if __name__ == "__main__":
    main()
