"""_s63_kraken_winners.py — push the WINNERS up: giveback from peak + peak/trail exit test (Greg).

Losers are handled (deep bail). Now the winners: the detector exits a winner at the next FLOW-TURN, but
the price often PEAKS before the lean turns and gives back (S55: flow climaxes at the top, collapses ~60s
later; ~28bp giveback). This measures the giveback (MFE - exit) across winners, renders the 10 biggest
winners (peak ^ vs exit v), and tests a PEAK-TRAIL take-profit (exit when the leg retraces Y bp from its
running peak) — does capturing the peak push winner $/hr up, net of the taker trail exit?

Kraken 30d tape (retime entries; SOL reversed). Honest taker on the trail exit (TP is a cross).

Usage:  python scripts/_s63_kraken_winners.py
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

CAP = 5000.0; WFLIP, REV = 600, 0.1; TRAIL_TK = 11.0
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD", 10.0), ("btc", "XBTUSD", 5.0), ("sol", "SOLUSD", 10.0)]
REVERSED = {"sol"}
TRAILS = [10, 20, 30, 50]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s63")


def legs(mid, entries, sgn):
    out = []
    for k in range(len(entries) - 1):
        ci, _pv, side = entries[k]; nci = entries[k + 1][0]; side *= sgn
        if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci:
            continue
        out.append(side * np.log(mid[ci:nci + 1] / mid[ci]) * 1e4)   # P&L path (bps)
    return out


def trail_pnl(r, Y):
    """Peak-trail take-profit: once in profit, exit when retrace Y bp from running peak (taker); else ride."""
    peak = 0.0; armed = False
    for v in r:
        if v > peak:
            peak = v
        if peak > 0 and (peak - v) >= Y:
            return peak - Y - TRAIL_TK      # exit at peak-Y, taker cross
    return float(r[-1])                       # rode to the turn


def main():
    print("=== PUSH THE WINNERS UP — giveback from peak + peak-trail take-profit, Kraken 30d tape ===")
    for coin, pair, eps in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"\n[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if coin in REVERSED else 1
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
        R = legs(mid, entries, sgn)
        gross = np.array([r[-1] for r in R])
        wins = [r for r in R if r[-1] > 0]
        mfe = np.array([r.max() for r in wins])
        wexit = np.array([r[-1] for r in wins])
        giveback = mfe - wexit
        ride = gross.sum() / 1e4 * CAP / hrs
        tag = f"{coin}{' REV' if coin in REVERSED else ''}"
        print(f"\n[{tag}]  winners={len(wins)}  mean MFE={mfe.mean():+.1f}  mean exit={wexit.mean():+.1f}"
              f"  mean GIVEBACK={giveback.mean():+.1f}bp  (captured {100*wexit.mean()/mfe.mean():.0f}% of peak)"
              f"  ride-all {ride:+.2f}$/hr")
        print(f"   {'trailY':>7}{'net$/h':>9}{'Δride':>8}   (peak-trail TP, taker exit)")
        for Y in TRAILS:
            pnl = np.array([trail_pnl(r, Y) for r in R])
            dph = pnl.sum() / 1e4 * CAP / hrs
            print(f"   -{Y:<6}{dph:>+9.2f}{dph-ride:>+8.2f}")

    # render 10 biggest winners for eth (peak vs exit)
    coin, pair, eps = CELLS[0]
    mid, buy, sell, cover, hrs = load_bins(f"{KTAPE}/{pair}_30d_bins.json")
    mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, eps)
    R = legs(mid, entries, 1)
    order = sorted(range(len(R)), key=lambda i: -R[i][-1])[:10]
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle("ETH — 10 biggest WINNERS (Kraken tape)  |  P&L bps vs s;  ^=peak(MFE)  v=exit  "
                 "giveback = peak−exit", fontsize=12)
    for ax, i in zip(axes.flat, order):
        r = R[i]; t = np.arange(len(r)); pk = int(np.argmax(r))
        ax.axhline(0, color="#888", lw=0.8); ax.plot(t, r, color="#1a9850", lw=1.2)
        ax.plot(pk, r[pk], "^", color="#1a9850", ms=9)
        ax.plot(len(r) - 1, r[-1], "v", color="#d73027", ms=8)
        ax.set_title(f"exit {r[-1]:+.0f}  peak {r[pk]:+.0f}  giveback {r[pk]-r[-1]:.0f}bp  {len(r)}s", fontsize=9)
        ax.set_xlabel("s", fontsize=8); ax.set_ylabel("bps", fontsize=8); ax.tick_params(labelsize=7)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fp = os.path.join(OUT, "winners10_eth.png"); plt.savefig(fp, dpi=110); plt.close()
    print(f"\n   rendered -> {fp}")


if __name__ == "__main__":
    main()
