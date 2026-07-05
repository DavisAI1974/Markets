"""_s63_kraken_widebail.py — WIDE pure-bail at -40/-50 (Greg): cut the true runovers, spare the dips.

The -15 bail clipped too many recoveries; a WIDE bail should only trigger on the true trend-runovers
(renders: they run to -100..-200) and leave the dips (bounce before -40) riding. Pure BAIL only (no
flip). Per coin (ETH/BTC forward + early-arm eps; SOL reversed), retime entries, ride to the flow-turn
UNLESS the leg reaches -stop -> flatten at -stop (taker cross).

Decomposes every bailed trade so we see the honest tradeoff:
  TRUE SAVE = the leg would have ended worse than -stop (gross <= -stop) -> bail helped
  CLIP      = the leg would have ended ABOVE -stop (gross > -stop) -> bail hurt (clipped a recovery)
Reports net $/hr @ $5k at 0bp AND honest 11bp taker on the bail leg, vs ride-all. per-week.

Usage:  python scripts/_s63_kraken_widebail.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import retime_flips                          # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1; WK = 7 * 24 * 3600; BAIL_TK = 11.0
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
STOPS = [None, 40, 50, 60, 80]


def run(mid, entries, sgn, stop, fee):
    pnl = []; eidx = []; n_save = n_clip = 0; saved = clipped = 0.0
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        r = side * np.log(mid[ci:nci + 1] / mid[ci]) * 1e4
        gross = float(r[-1])
        if stop is None:
            pnl.append(gross); eidx.append(ci); continue
        u = np.where(r <= -stop)[0]
        if len(u) == 0:
            pnl.append(gross); eidx.append(ci); continue
        realized = -float(stop) - fee
        pnl.append(realized); eidx.append(ci)
        if gross <= -stop:
            n_save += 1; saved += (-stop) - gross          # avoided extra loss (bp, +)
        else:
            n_clip += 1; clipped += gross - (-stop)         # gave up recovery (bp, +)
    return np.array(pnl), np.array(eidx), n_save, n_clip, saved, clipped


def dph(pnl, hrs):
    return pnl.sum() / 1e4 * CAP / hrs


def main():
    print("=== WIDE pure-BAIL (no flip) on the Kraken detector — cut runovers, spare dips ===")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
        base, bidx, *_ = run(mid, entries, sgn, None, 0.0)
        base_net = dph(base, hrs)
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  ride-all baseline net {base_net:+.2f} $/hr")
        print(f"   {'stop':>5}{'net@0bp':>8}{'net@11tk':>9}{'save#':>6}{'clip#':>6}"
              f"{'savedbp':>8}{'clipbp':>8}   per-week net@11tk")
        for stop in STOPS[1:]:
            p0, idx, ns, nc, sv, cl = run(mid, entries, sgn, stop, 0.0)
            pf, _, _, _, _, _ = run(mid, entries, sgn, stop, BAIL_TK)
            week = (idx // WK).astype(int)
            pw = []
            for wk in sorted(set(week)):
                mk = week == wk
                if mk.sum() < 2:
                    continue
                hh = (np.ptp(idx[mk]) + 1) / 3600.0
                pw.append(dph(pf[mk], hh))
            print(f"   -{stop:<4}{dph(p0,hrs):>+8.2f}{dph(pf,hrs):>+9.2f}{ns:>6}{nc:>6}"
                  f"{sv:>+8.0f}{-cl:>+8.0f}   " + " ".join(f"{v:+.0f}" for v in pw))
    print("\n  save# = true runovers capped; clip# = recoveries clipped. net@11tk = honest taker bail.")


if __name__ == "__main__":
    main()
