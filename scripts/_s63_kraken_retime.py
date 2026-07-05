"""_s63_kraken_retime.py — PUSH WINS UP: early-arm entry timing on the Kraken flow-lean detector.

Win/loss anatomy (S63 §10): the Kraken flip detector is NOT hemorrhaging (avg win > avg loss) but the
net is a thin residual and entries lag the true turn by ~4-7 bp. `retime_flips` (S47) keeps the flow
lean as the FILTER (which turns, which side) but fires the entry at the first fast PRICE reversal
(eps_bps from the regime extreme) -> enters nearer the true turn. That adds to every win and shrinks
every loss (pushes wins up) without changing which turns we take. eps->inf recovers detect_flips.

Compares base detect_flips vs retime at several eps, per coin, at kr_mk0 (0bp): net $/hr, win%,
avg win/loss, W/L, mean lag bp, breakeven fee/swing. Same tape, WFLIP=600 REV=0.1.

Usage:  python scripts/_s63_kraken_retime.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import (lean_series, detect_flips,          # noqa: E402
                                  retime_flips, backtest_swings)

CAP = 5000.0; WFLIP, REV = 600, 0.1
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", f"{KTAPE}/ETHUSD_30d_bins.json"), ("btc", f"{KTAPE}/XBTUSD_30d_bins.json"),
         ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json"), ("doge", f"{KTAPE}/XDGUSD_30d_bins.json"),
         ("sol", f"{KTAPE}/SOLUSD_30d_bins.json")]
EPS = [5.0, 10.0, 20.0, 40.0]      # price-reversal trigger (bp); inf == base detect_flips


def swings_from(mid, entries):
    r = []
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]
        if mid[ci] > 0 and mid[nci] > 0:
            r.append(side * np.log(mid[nci] / mid[ci]) * 1e4)
    return np.array(r)


def stat(mid, entries, hrs):
    st = backtest_swings(mid, entries, 0.0)
    r = swings_from(mid, entries)
    w = r[r > 0]; l = r[r < 0]
    net = r.sum() / 1e4 * CAP / hrs
    return dict(n=len(r), net=net, win=100 * len(w) / max(len(r), 1),
                aw=w.mean() if len(w) else 0.0, al=l.mean() if len(l) else 0.0,
                wl=(w.mean() / abs(l.mean())) if len(l) and l.mean() != 0 else 0.0,
                lag=st["lag_bps"], be=r.sum() / max(len(r), 1))


def main():
    print("=== PUSH WINS UP: early-arm timing (retime_flips) vs base, Kraken kr_mk0 ===")
    for coin, path in CELLS:
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        lean = lean_series(buy, sell, WFLIP)
        base_flips, _ = detect_flips(lean, REV)
        b = stat(mid, base_flips, hrs)
        print(f"\n[{coin}]  swings={b['n']}  (WFLIP=600 REV=0.1)")
        print(f"   {'variant':>10}{'net$/h':>8}{'win%':>6}{'avgW':>7}{'avgL':>7}{'W/L':>6}"
              f"{'lag':>6}{'BEfee':>7}")
        print(f"   {'base':>10}{b['net']:>+8.2f}{b['win']:>6.1f}{b['aw']:>+7.2f}{b['al']:>+7.2f}"
              f"{b['wl']:>6.2f}{b['lag']:>6.1f}{b['be']:>+7.3f}")
        for eps in EPS:
            entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
            s = stat(mid, entries, hrs)
            print(f"   {('retime'+str(int(eps))):>10}{s['net']:>+8.2f}{s['win']:>6.1f}{s['aw']:>+7.2f}"
                  f"{s['al']:>+7.2f}{s['wl']:>6.2f}{s['lag']:>6.1f}{s['be']:>+7.3f}")


if __name__ == "__main__":
    main()
