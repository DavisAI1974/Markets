"""_s63_render_losers.py — the 10 biggest LOSER swings of the Kraken flow-lean detector, for QUICK-BAIL design.

Greg: losses are almost as big as wins -> we need a quick bail. This renders the 10 worst losing swings
of the deployed detector (flip_detector WFLIP=600 REV=0.1; SOL uses the REVERSED signal per Greg) so we
can see HOW each loss develops: does it go underwater early and stay (a stop bails it) or round-trip?

Each panel = the P&L path (bps, from OUR side) vs seconds-in-trade for one loser:
  green line = signed excursion r(t) = side * log(mid/entry) * 1e4   (0 = breakeven, down = losing)
  red dot = final exit (the realized loss)   orange x = max adverse excursion (MAE, the worst point)
  the shape tells the bail: if r(t) crosses a floor early and never recovers, a stop there saves most of it.

Usage:  python scripts/_s63_render_losers.py [coin]   (default eth)
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
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402

WFLIP, REV = 600, 0.1
KTAPE = "/tmp/kraken_backfill"
PAIR = {"eth": "ETHUSD", "btc": "XBTUSD", "sol": "SOLUSD", "xrp": "XRPUSD", "doge": "XDGUSD"}
REVERSED = {"sol"}          # coin-spec: SOL detector is anti-predictive -> reverse (Greg)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s63")


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "eth"
    path = f"{KTAPE}/{PAIR[coin]}_30d_bins.json"
    mid, buy, sell, cover, hrs = load_bins(path)
    mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    sgn = -1 if coin in REVERSED else 1

    swings = []      # (loss_bp, entry_i, exit_i, side)
    for k in range(len(flips) - 1):
        ci, _pv, side = flips[k]; nci = flips[k + 1][0]; side *= sgn
        if mid[ci] > 0 and mid[nci] > 0 and nci > ci:
            g = side * np.log(mid[nci] / mid[ci]) * 1e4
            swings.append((g, int(ci), int(nci), int(side)))
    losers = sorted([s for s in swings if s[0] < 0])[:10]     # 10 most negative

    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    tag = f"{coin.upper()}{' (REVERSED)' if coin in REVERSED else ''}"
    fig.suptitle(f"{tag} — 10 biggest LOSER swings (flow-lean detector, kr_mk0)  |  "
                 f"P&L path in bps vs seconds-in-trade  |  where does a quick-bail trigger?",
                 fontsize=13)
    for ax, (loss, ci, xi, side) in zip(axes.flat, losers):
        seg = mid[ci:xi + 1]
        r = side * np.log(seg / mid[ci]) * 1e4          # our P&L path, bps
        t = np.arange(len(r))
        mae_i = int(np.argmin(r)); mae = r[mae_i]
        ax.axhline(0, color="#888", lw=0.8)
        ax.plot(t, r, color="#1a9850", lw=1.3)
        ax.plot(len(r) - 1, r[-1], "o", color="#d73027", ms=7, label=f"exit {r[-1]:+.0f}")
        ax.plot(mae_i, mae, "x", color="#fdae61", ms=9, mew=2, label=f"MAE {mae:+.0f}")
        dur = len(r)
        ax.set_title(f"loss {loss:+.0f}bp  {'LONG' if side>0 else 'SHORT'}  {dur}s  "
                     f"MAE@{100*mae_i/max(dur-1,1):.0f}%", fontsize=9)
        ax.set_xlabel("s in trade", fontsize=8); ax.set_ylabel("P&L bps", fontsize=8)
        ax.legend(fontsize=7, loc="lower left"); ax.tick_params(labelsize=7)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fp = os.path.join(OUT, f"losers10_{coin}.png")
    plt.savefig(fp, dpi=110); plt.close()

    # quick-bail readout: for a grid of stop levels, how much loss is saved (on THESE 10 losers)
    print(f"[{coin}] 10 biggest losers rendered -> {fp}")
    print(f"   raw total loss (these 10): {sum(l for l,_,_,_ in losers):+.0f} bp")
    for stop in (-20, -30, -40, -60, -80):
        saved = 0.0; hit = 0
        for loss, ci, xi, side in losers:
            seg = mid[ci:xi + 1]; r = side * np.log(seg / mid[ci]) * 1e4
            u = np.where(r <= stop)[0]
            realized = stop if len(u) else r[-1]       # bail at first touch of stop, else ride to exit
            saved += (r[-1] - realized); hit += len(u) > 0
        print(f"   stop {stop:>4}bp: bails {hit:>2}/10, saves {saved:+.0f}bp vs no-stop")


if __name__ == "__main__":
    main()
