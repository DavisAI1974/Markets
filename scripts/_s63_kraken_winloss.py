"""_s63_kraken_winloss.py — WIN/LOSS split of the flow-lean flip detector on Kraken (Greg).

For the deployed detector (odcore/flip_detector.py, WFLIP=600 REV=0.1, ARM0 no gates) on the Kraken
tape: split every swing into WINS vs LOSSES so we can see whether the leak is (a) losses too big
(hemorrhage) or (b) wins too small (need to push wins up). Per coin, at kr_mk0 (0bp):

  swings | win% | avg WIN bp | avg LOSS bp | W/L size ratio | wins $/hr | losses $/hr | NET $/hr
  + breakeven fee/swing (bp) — how much per-swing fee the edge can absorb before net<=0 (the fill/fee headroom)

$/hr @ $5k over the tape hours. Wins $/hr = sum of positive swings; losses $/hr = sum of negative
(negative number). NET = wins + losses.

Usage:  python scripts/_s63_kraken_winloss.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1
KTAPE = "/tmp/kraken_backfill"
CELLS = [("sol", f"{KTAPE}/SOLUSD_30d_bins.json"), ("eth", f"{KTAPE}/ETHUSD_30d_bins.json"),
         ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json"), ("btc", f"{KTAPE}/XBTUSD_30d_bins.json"),
         ("doge", f"{KTAPE}/XDGUSD_30d_bins.json")]


def swing_bps(path):
    mid, buy, sell, cover, hrs = load_bins(path)
    mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    r = []
    for k in range(len(flips) - 1):
        ci, _pv, side = flips[k]; nci = flips[k + 1][0]
        if mid[ci] > 0 and mid[nci] > 0:
            r.append(side * np.log(mid[nci] / mid[ci]) * 1e4)
    return np.array(r), hrs, cover


def main():
    print("=== WIN/LOSS split — flow-lean flip detector (WFLIP=600 REV=0.1) on Kraken, kr_mk0 (0bp) ===")
    hdr = (f"{'coin':>5}{'swings':>7}{'win%':>6} | {'avgWIN':>7}{'avgLOSS':>8}{'W/L':>6} | "
           f"{'wins$/h':>8}{'loss$/h':>8}{'NET$/h':>8} | {'BE fee bp':>9}")
    print(hdr)
    for coin, path in CELLS:
        if not os.path.exists(path):
            print(f"{coin:>5}  (tape not present)"); continue
        r, hrs, cover = swing_bps(path)
        if len(r) < 20:
            print(f"{coin:>5}  too few swings ({len(r)})"); continue
        w = r[r > 0]; l = r[r < 0]
        n = len(r); winpct = 100.0 * len(w) / n
        avg_w = w.mean() if len(w) else 0.0
        avg_l = l.mean() if len(l) else 0.0
        wl = avg_w / abs(avg_l) if avg_l != 0 else float("inf")
        wins_hr = w.sum() / 1e4 * CAP / hrs
        loss_hr = l.sum() / 1e4 * CAP / hrs
        net_hr = wins_hr + loss_hr
        # breakeven per-swing fee (bp): net sum bps / n swings
        be_fee = r.sum() / n
        print(f"{coin:>5}{n:>7}{winpct:>6.1f} | {avg_w:>+7.2f}{avg_l:>+8.2f}{wl:>6.2f} | "
              f"{wins_hr:>+8.1f}{loss_hr:>+8.1f}{net_hr:>+8.2f} | {be_fee:>+9.3f}")
    print("\n  W/L>1 with win%<50 = wins bigger than losses (positive skew, the good kind);")
    print("  W/L<1 = hemorrhage (losses bigger). BE fee bp = per-swing fee headroom before net<=0.")


if __name__ == "__main__":
    main()
