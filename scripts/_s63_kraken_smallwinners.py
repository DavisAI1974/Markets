"""_s63_kraken_smallwinners.py — the 10 SMALLEST winners + the small-winner tail (Greg / S56 walkthrough).

The marginal winners: trades that barely cleared zero. Are they real edge or fragile sub-fee/sub-fill
noise we shouldn't take? Renders the 10 smallest positive legs (P&L path, peak, exit) and buckets the
winner-size distribution: how many winners are tiny, and how much of total winner $ they contribute.
If the small winners are a churn tail that adds nothing (but costs fills/fees), a swing floor helps.

Kraken 30d tape (retime entries; SOL reversed).
Usage:  python scripts/_s63_kraken_smallwinners.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import retime_flips                          # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
BUCKETS = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 1e9)]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s63")


def legs(mid, entries, sgn):
    out = []
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        out.append(side * np.log(mid[ci:nci + 1] / mid[ci]) * 1e4)
    return out


def main():
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        R = legs(mid, entries := retime_flips(mid, buy, sell, WFLIP, REV, eps)[0], sgn)
        g = np.array([r[-1] for r in R])
        wins = g[g > 0]; total_win = wins.sum()
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  winners={len(wins)}  total win={total_win/1e4*CAP:+.0f}$  median winner={np.median(wins):.1f}bp")
        print(f"   {'bucket(bp)':>12}{'#win':>7}{'%win#':>7}{'$share':>8}   (of winner $)")
        for lo, hi in BUCKETS:
            m = (wins >= lo) & (wins < hi)
            share = 100 * wins[m].sum() / total_win if total_win else 0
            lbl = f"{lo:.0f}-{'inf' if hi > 1e8 else int(hi)}"
            print(f"   {lbl:>12}{int(m.sum()):>7}{100*m.sum()/len(wins):>6.0f}%{share:>7.0f}%")

    # render 10 smallest winners for eth
    coin, pair, eps = CELLS[0]
    mid, buy, sell, cover, hrs = load_bins(f"{KTAPE}/{pair}_30d_bins.json")
    mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    R = legs(mid, retime_flips(mid, buy, sell, WFLIP, REV, eps)[0], 1)
    pos = [i for i in range(len(R)) if R[i][-1] > 0]
    order = sorted(pos, key=lambda i: R[i][-1])[:10]
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle("ETH — 10 SMALLEST winners (Kraken tape)  |  P&L bps vs s;  ^=peak v=exit  "
                 "(marginal trades: real edge or sub-fee noise?)", fontsize=12)
    for ax, i in zip(axes.flat, order):
        r = R[i]; t = np.arange(len(r)); pk = int(np.argmax(r))
        ax.axhline(0, color="#888", lw=0.8); ax.plot(t, r, color="#1a9850", lw=1.2)
        ax.plot(pk, r[pk], "^", color="#1a9850", ms=8); ax.plot(len(r) - 1, r[-1], "v", color="#d73027", ms=7)
        ax.set_title(f"exit {r[-1]:+.1f}  peak {r[pk]:+.0f}  {len(r)}s", fontsize=9)
        ax.set_xlabel("s", fontsize=8); ax.set_ylabel("bps", fontsize=8); ax.tick_params(labelsize=7)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fp = os.path.join(OUT, "smallwinners10_eth.png"); plt.savefig(fp, dpi=110); plt.close()
    print(f"\n   rendered -> {fp}")


if __name__ == "__main__":
    main()
