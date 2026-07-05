"""_s63_kraken_bail.py — BOTH LEVERS: early-arm timing (push wins up) + quick-bail stop (cut losses).

Greg: attack from both ends. (1) retime_flips = enter at the fast price reversal near the true turn
(bigger wins, smaller losses). (2) quick-bail STOP: if a swing's P&L reaches -stop bp before the next
turn, bail at -stop instead of riding to the turn. Priced across ALL trades (winners included) so the
stop PAYS for the winners it clips — the honest tradeoff the loser-only readout couldn't show.

Per coin (BTC/ETH forward, SOL REVERSED coin-spec, XRP/DOGE too): base (detect_flips, no stop) vs
retime-only vs retime+bail across a stop sweep. Net $/hr @ $5k, win%, per-week. kr_mk0 (0bp).
Per-coin early-arm eps from S63 §11 (eth10 / btc5 / else10).

Usage:  python scripts/_s63_kraken_bail.py
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
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0),
         ("xrp", "XRPUSD", 10.0), ("doge", "XDGUSD", 10.0)]
REVERSED = {"sol"}
STOPS = [None, 15, 20, 30, 40, 60]


def realized(mid, entries, sgn, stop):
    """Per-swing realized bps with optional quick-bail stop (bail at -stop on first touch)."""
    out = []; eidx = []
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        seg = mid[ci:nci + 1]
        r = side * np.log(seg / mid[ci]) * 1e4
        if stop is not None:
            u = np.where(r <= -stop)[0]
            val = -float(stop) if len(u) else float(r[-1])
        else:
            val = float(r[-1])
        out.append(val); eidx.append(ci)
    return np.array(out), np.array(eidx)


def summ(r, hrs):
    if len(r) == 0:
        return dict(net=0, win=0, aw=0, al=0)
    w = r[r > 0]; l = r[r < 0]
    return dict(net=r.sum() / 1e4 * CAP / hrs, win=100 * len(w) / len(r),
                aw=w.mean() if len(w) else 0.0, al=l.mean() if len(l) else 0.0)


def main():
    print("=== BOTH LEVERS: early-arm (retime) + quick-bail stop, across ALL trades, Kraken kr_mk0 ===")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        lean = lean_series(buy, sell, WFLIP)
        base_flips, _ = detect_flips(lean, REV)
        rt_entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)

        rb, _ = realized(mid, base_flips, sgn, None); sb = summ(rb, hrs)
        rr, ridx = realized(mid, rt_entries, sgn, None); sr = summ(rr, hrs)
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  base net {sb['net']:+.2f}   retime{int(eps)} net {sr['net']:+.2f}  "
              f"(win {sr['win']:.0f}% aW {sr['aw']:+.1f} aL {sr['al']:+.1f})")
        print(f"   {'stop':>6}{'net$/h':>8}{'win%':>6}{'avgW':>7}{'avgL':>7}{'Δretime':>8}   per-week net")
        week = (ridx // WK).astype(int)
        for stop in STOPS:
            r, _ = realized(mid, rt_entries, sgn, stop); s = summ(r, hrs)
            pw = []
            for wk in sorted(set(week)):
                mk = week == wk
                if mk.sum() < 2:
                    continue
                hh = (np.ptp(ridx[mk]) + 1) / 3600.0
                pw.append(r[mk].sum() / 1e4 * CAP / hh)
            lbl = "none" if stop is None else f"-{stop}"
            print(f"   {lbl:>6}{s['net']:>+8.2f}{s['win']:>6.0f}{s['aw']:>+7.1f}{s['al']:>+7.1f}"
                  f"{s['net']-sr['net']:>+8.2f}   " + " ".join(f"{v:+.0f}" for v in pw))


if __name__ == "__main__":
    main()
