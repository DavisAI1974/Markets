"""_render_one.py — blow up ONE trade and explain WHY it fired (S45, walkthrough).

Reproduces the deployed signal's fills for a cell, ranks the LOSERS (gross<0) worst-first, renders the
chosen one large, and prints the exact signal values behind the decision:
  - WHY this side  : depth_imb (top-of-book bid vs ask size) -> sign -> bid/ask
  - WHY now        : QuietFloor innovation broke the relaxation floor (|innov| > k*sigma)
  - what then      : queue wait, the opposing flow that filled us, and the mid path (d_wait/d_hold/gross)

Run:  python _render_one.py [coin] [rank] [signal]   rank 0 = worst loser; signal=floor|confirm|opposing
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

FLOW_W, TRAIN_FRAC, FILL_WINDOW, HOLD, QUEUE_FRAC, KGATE, PDWIN = 20, 0.6, 10, 1, 1.0, 1.5, 30
CTX = 60
BLUE = "#1414dc"


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    rank = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    mode = sys.argv[3] if len(sys.argv) > 3 else "floor"
    K = 10 if coin == "btc" else 1
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"

    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bd, ad = np.asarray(g["bidK"][K], float), np.asarray(g["askK"][K], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC); hs = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    floor_hat = qf.floor_hat(imb); innov = qf.innovation(imb)
    gated = qf.gated_signal(imb, k=KGATE)

    lm = np.log(np.where(mid > 0, mid, np.nan))
    pd = np.zeros(n); pd[PDWIN:] = np.nan_to_num(lm[PDWIN:] - lm[:-PDWIN])
    if mode in ("confirm", "opposing"):
        aligned = np.sign(imb) * np.sign(pd)
        cond = (aligned > 0) if mode == "confirm" else (aligned < 0)
        gated = np.where((gated != 0) & cond, np.sign(imb), 0.0)

    side = np.zeros(n); side[cut:] = gated[cut:]
    qa = np.where(side > 0, bb, ba) * QUEUE_FRAC
    fa = np.where(side > 0, _first_fill_index(qa, sell, FILL_WINDOW),
                  np.where(side < 0, _first_fill_index(qa, buy, FILL_WINDOW), -1))
    filled = (side != 0) & (fa >= 0) & ((fa + HOLD) <= (n - 1))
    idx = np.where(filled)[0]
    ei = np.clip(fa + HOLD, 0, n - 1)
    hs_price = (hs / 1e4) * mid
    entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    sgn = side[idx]
    gross = sgn * (mid[ei[idx]] - entry[idx]) / mid[idx] * 1e4

    losers = idx[gross < 0]
    lgross = gross[gross < 0]
    o = np.argsort(lgross)                       # worst first
    if rank >= len(o):
        print(f"only {len(o)} losers"); return
    k = o[rank]; t = int(losers[k]); f = int(fa[t]); e = int(ei[t]); is_bid = side[t] > 0
    wait = f - t

    # ---- explanation ----
    print(f"\n# LOSER #{rank+1} of {len(o)}  —  {coin}_coinbase  [{mode} signal, K={K}]")
    print(f"# POST at cell {t} (test slice starts {cut}); mid = {mid[t]:.5f}")
    print(f"#")
    print(f"# WHY THIS SIDE:  depth_imb = {imb[t]:+.4f}  (top-of-book bid {bd[t]:.2f} vs ask {ad[t]:.2f})")
    print(f"#                 sign(depth_imb) = {'+1 -> post BID (buy, expect UP)' if is_bid else '-1 -> post ASK (sell, expect DOWN)'}")
    print(f"# WHY NOW (gate):  floor_hat = {floor_hat[t]:+.4f}  innovation = imb-floor = {innov[t]:+.4f}")
    print(f"#                 |innov| {abs(innov[t]):.4f} > k*sigma {KGATE*qf.sigma:.4f}  (k={KGATE}, sigma={qf.sigma:.4f}) -> GATE OPEN")
    if mode in ("confirm", "opposing"):
        print(f"# FLIP polarity:   trailing price_drift({PDWIN}c) = {pd[t]*1e4:+.2f} bps; "
              f"aligned = {np.sign(imb[t])*np.sign(pd[t]):+.0f} ({mode})")
    print(f"# THEN (fill):     waited {wait} cells ({wait*100}ms) for opposing flow to clear queue "
          f"({'sell' if is_bid else 'buy'} vol >= {qa[t]:.2f})")
    print(f"#                 mid POST {mid[t]:.5f} -> FILL {mid[f]:.5f} -> EXIT {mid[e]:.5f}")
    sd = side[t]                                  # +1 bid / -1 ask (the actual trade's side)
    dwait = sd * (mid[f] - mid[t]) / mid[t] * 1e4
    dhold = sd * (mid[e] - mid[f]) / mid[t] * 1e4
    print(f"#                 half_spread +{hs:.4f} | d_wait {dwait:+.4f} | d_hold {dhold:+.4f} "
          f"=> GROSS {lgross[o[rank]]:+.4f} bps")
    print(f"#  -> we {'BOUGHT' if is_bid else 'SOLD'} because the book leaned "
          f"{'bid-heavy' if is_bid else 'ask-heavy'} and a shock broke the floor; "
          f"the fill came from {'sellers running price DOWN' if is_bid else 'buyers running price UP'} "
          f"against us.\n")

    # ---- render ----
    lo, hi = max(0, t - CTX), min(n - 1, e + CTX)
    xs = np.arange(lo, hi + 1) - t
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.plot(xs, mid[lo:hi + 1], color=BLUE, lw=2.6, solid_capstyle="round")
    col = "#cc1414"
    ax.scatter([0], [mid[t]], s=160, facecolors="none", edgecolors="k", lw=2.4, zorder=5, label="post (quote)")
    ax.scatter([wait], [mid[f]], s=170, color=col, zorder=6, label="fill")
    ax.scatter([e - t], [mid[e]], marker="x", s=200, color=col, lw=3, zorder=6, label="exit (+hold)")
    ax.axhline(entry[t], color=col, ls=":", lw=1.4, alpha=0.85)
    ax.annotate("Buy long" if is_bid else "Sell short", xy=(0, mid[t]),
                xytext=(-CTX * 0.8, mid[t]), fontsize=18, color=BLUE, weight="bold", va="center")
    ax.set_title(f"{coin.upper()} {mode} LOSER #{rank+1}: {'BID' if is_bid else 'ASK'}  "
                 f"depth_imb={imb[t]:+.3f}  wait={wait}c  gross={lgross[o[rank]]:+.2f} bps", fontsize=13)
    ax.set_xlabel("cells from post (100ms each)"); ax.set_ylabel("mid price")
    ax.legend(loc="best"); ax.spines[["top", "right"]].set_visible(False)
    out = f"_loser_{coin}_{mode}_{rank}.png"
    fig.tight_layout(); fig.savefig(out, dpi=120)
    print(f"# wrote {out}")


if __name__ == "__main__":
    main()
