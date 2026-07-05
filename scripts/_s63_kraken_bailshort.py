"""_s63_kraken_bailshort.py — deep bail then RESET + fire a CONFIRMED short (Greg: catch the rest of the slide).

After a deep bail (dead-loss long exited at -D while price still slides down), reset and fire a NEW
short to catch the rest of the downslide -- but ONLY when the flow LEAN confirms the continuation
(fire CORRECTLY, not blindly). Compares, per depth D, at kr_mk0:
  bail-flat  : exit at -D, sit flat to the flow-turn (the S63 deep bail)
  blind-flip : exit at -D, reverse to short, ride to the turn regardless (the tested flip)
  conf-short : exit at -D, reverse to short ONLY if lean@bail confirms the continuation side, else flat
The short rides bail-cell -> the leg's flow-turn (nci). Honest taker: bail 11bp, flip/short cross 22bp.

Usage:  python scripts/_s63_kraken_bailshort.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1; BAIL_TK, FLIP_TK = 11.0, 22.0
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
DEPTHS = [60, 80, 100]


def main():
    print("=== deep bail -> RESET + CONFIRMED short (Greg: catch the rest of the slide, fire correctly) ===")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); lm = np.log(mid)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        lean = lean_series(buy, sell, WFLIP)
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
        ride = 0.0
        rows = []  # (ci, nci, side, r)
        for k in range(len(entries) - 1):
            ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
            if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
                continue
            r = side * np.log(mid[ci:nci + 1] / mid[ci]) * 1e4
            rows.append((ci, nci, side, r)); ride += float(r[-1])
        ride_dph = ride / 1e4 * CAP / hrs
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  ride-all {ride_dph:+.2f} $/hr")
        print(f"   {'depth':>6}{'flat':>8}{'blind':>8}{'confShort':>10}{'conf#':>6}{'confWin%':>9}")
        for D in DEPTHS:
            flat = blind = conf = 0.0; nconf = 0; confwin = 0
            for ci, nci, side, r in rows:
                g = float(r[-1])
                u = np.where(r <= -D)[0]
                if len(u) == 0:
                    flat += g; blind += g; conf += g; continue
                j = ci + int(u[0]); r_at = float(r[int(u[0])])
                cont_side = -side                         # continuation of the slide = opposite our side
                # short leg bail->nci in cont_side terms:
                short_leg = cont_side * (lm[nci] - lm[j]) * 1e4
                flat += r_at - BAIL_TK
                blind += r_at + short_leg - FLIP_TK
                # confirmed: lean@j must agree with the continuation side (lean sign == cont_side)
                lean_conf = (np.sign(lean[j]) == cont_side) and (abs(lean[j]) > 0)
                if lean_conf:
                    conf += r_at + short_leg - FLIP_TK; nconf += 1; confwin += short_leg > FLIP_TK
                else:
                    conf += r_at - BAIL_TK
            f = flat / 1e4 * CAP / hrs; b = blind / 1e4 * CAP / hrs; c = conf / 1e4 * CAP / hrs
            cw = 100 * confwin / nconf if nconf else 0.0
            print(f"   -{D:<5}{f:>+8.2f}{b:>+8.2f}{c:>+10.2f}{nconf:>6}{cw:>8.0f}%")
    print("\n  flat=bail flat; blind=always short; confShort=short only when lean confirms continuation.")
    print("  confWin% = of confirmed shorts, how many the short leg won (net of the 22bp cross).")


if __name__ == "__main__":
    main()
