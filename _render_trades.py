"""_render_trades.py — render the 10 dissected maker fills as price curves, in the style of Greg's
hand-drawn swing diagram (buy the valleys, sell-short the peaks; mark where we actually got filled).

Reproduces the EXACT fills the deploy map / _dissect_fills.py simulate for one cell, picks the same 10
across the gross distribution, and draws each: the mid curve in a context window, the POST (where we
quoted), the FILL (where opposing flow hit us), and the EXIT (+hold), with the swing label. The point
is visual: the losers are quotes posted mid-trend (filled on the way down for a bid = a falling knife);
the winners are quotes that sat at a real turn (the valley/peak Greg drew).

Run:  python _render_trades.py <coin> [K] [kgate]
"""
from __future__ import annotations

import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _liquidity_dive import build_channels, median_spread_bps
from odcore import quiet_floor
from odcore.maker_book import _first_fill_index

FLOW_W, TRAIN_FRAC, FILL_WINDOW, HOLD, QUEUE_FRAC = 20, 0.6, 10, 1, 1.0
CTX = 60   # context cells each side (6s) so the valley/peak shape is visible

BLUE = "#1414dc"


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    kgate = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"

    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    gated = qf.gated_signal(imb, k=kgate)
    side = np.zeros(n); side[cut:] = gated[cut:]

    qa = np.where(side > 0, bb, ba) * QUEUE_FRAC
    filled_at = np.where(side > 0, _first_fill_index(qa, sell, FILL_WINDOW),
                         np.where(side < 0, _first_fill_index(qa, buy, FILL_WINDOW), -1))
    filled = (side != 0) & (filled_at >= 0) & ((filled_at + HOLD) <= (n - 1))
    idx = np.where(filled)[0]
    fi = filled_at; ei = np.clip(fi + HOLD, 0, n - 1)
    hs_price = (hs_bps / 1e4) * mid
    entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    sgn = side[idx]
    gross = sgn * (mid[ei[idx]] - entry[idx]) / mid[idx] * 1e4

    order = np.argsort(gross)
    picks = order[np.linspace(0, len(idx) - 1, 10).round().astype(int)]

    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle(f"{coin.upper()}_coinbase maker fills (K={K} top-of-book, gate k={kgate})  —  "
                 f"blue=mid; we BUY the valleys / SELL-SHORT the peaks. Green=favorable fill, Red=adverse.",
                 fontsize=13)
    for ax, k in zip(axes.flat, picks):
        t = int(idx[k]); f = int(fi[t]); e = int(ei[t]); is_bid = sgn[k] > 0
        lo, hi = max(0, t - CTX), min(n - 1, e + CTX)
        xs = np.arange(lo, hi + 1) - t              # cells relative to post (x=0)
        ax.plot(xs, mid[lo:hi + 1], color=BLUE, lw=2.4, solid_capstyle="round")
        good = gross[k] > 0
        col = "#0a8f2a" if good else "#cc1414"
        # post / fill / exit markers
        ax.scatter([0], [mid[t]], s=70, facecolors="none", edgecolors="k", lw=1.8, zorder=5)
        ax.scatter([f - t], [mid[f]], s=85, color=col, zorder=6)
        ax.scatter([e - t], [mid[e]], marker="x", s=90, color=col, lw=2.4, zorder=6)
        ax.axhline(entry[t], color=col, ls=":", lw=1.2, alpha=0.8)
        label = "Buy long" if is_bid else "Sell short"
        ax.annotate(label, xy=(0, mid[t]), xytext=(-CTX * 0.9, mid[t]),
                    fontsize=13, color=BLUE, weight="bold",
                    va="center", rotation=12 if is_bid else -12)
        ax.set_title(f"{'BID' if is_bid else 'ASK'}  wait={f-t}c  "
                     f"gross={gross[k]:+.2f} bps", fontsize=10, color=col)
        ax.set_xlabel("cells from post (100ms)"); ax.set_xticks([])
        ax.set_yticks([])
        ax.spines[["top", "right"]].set_visible(False)
    # legend in words
    axes.flat[0].text(0.02, 0.02, "o post   • fill   x exit(+hold)",
                      transform=axes.flat[0].transAxes, fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = f"_render_trades_{coin}.png"
    fig.savefig(out, dpi=110)
    print(f"wrote {out}  (mean gross over all {len(idx)} fills = {gross.mean():+.4f} bps)")


if __name__ == "__main__":
    main()
