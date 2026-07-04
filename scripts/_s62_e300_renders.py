"""_s62_e300_renders.py — S62 walkthrough renders: 10 biggest losers + 10 smallest winners,
annotated with the E300 decision (Greg's standing worst-10/smallest-10 rule).

Each panel = one leg's mid path (entry -> exit + pad). Markers: green ^/v = entry (long/short),
blue * = peak favorable, X = exit (red loser / green winner). The vertical dashed line = E300
(the 3-piece decision point); the panel title carries depth@300 vs final net, so you can SEE
whether a big loser was already deep underwater at E300 (catchable by the E300 stop) and whether
a small winner dipped and recovered (a leg the action must NOT flip).

Usage:  python scripts/_s62_e300_renders.py [--coin sol]
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

E = 300
RDIR = "docs/renders/s62"
CELLS = {"sol": ("SOLUSDT", 100.0), "eth": ("ETHUSDT", 80.0), "btc": ("BTCUSDT", 80.0),
         "xrp": ("XRPUSDT", 80.0), "doge": ("DOGEUSDT", 100.0)}


def legs_of(sym, th):
    m, *_r, hrs = load_bins(f"/tmp/backfill/{sym}_30d_bins.json"); m = np.asarray(m, float)
    lm = np.log(m); fl = armed_midband_flips(m, th, 0.5)
    out = []
    for k in range(len(fl) - 1):
        ci, pk, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); pk = int(pk); side = int(side)
        if xi <= ci or ci < 1802:
            continue
        net = side * (lm[xi] - lm[ci]) * 1e4
        d300 = side * (lm[ci + E] - lm[ci]) * 1e4 if xi > ci + E else None   # depth at E300 (None if closed early)
        out.append(dict(ci=ci, xi=xi, side=side, pk=pk, net=net, d300=d300))
    return m, out


def panel(ax, m, leg):
    ci, xi, side, pk = leg["ci"], leg["xi"], leg["side"], leg["pk"]
    pad = max(120, (xi - ci) // 8)
    a, b = max(0, ci - pad), min(len(m), xi + pad)
    t = (np.arange(a, b) - ci) / 60.0                        # minutes from entry
    ax.plot(t, m[a:b], lw=0.6, color="#1f77b4")
    ax.axvline(0, color="#999", lw=0.4)
    ax.plot(0, m[ci], "g^" if side > 0 else "gv", ms=5)
    ax.plot((pk - ci) / 60.0, m[pk], "b*", ms=6)
    ax.plot((xi - ci) / 60.0, m[xi], "x", color=("#2ca02c" if leg["net"] > 0 else "#d62728"), ms=7, mew=2)
    if leg["d300"] is not None:                              # E300 decision line
        ax.axvline(E / 60.0, color="#ff7f0e", ls="--", lw=0.7)
    d3 = f"{leg['d300']:+.0f}" if leg["d300"] is not None else "closed<300"
    ax.set_title(f"{'B' if side > 0 else 'S'} net {leg['net']:+.0f} | d@300 {d3}", fontsize=7)
    ax.tick_params(labelsize=5)


def render(coin, sym, th):
    m, legs = legs_of(sym, th)
    losers = sorted([l for l in legs if l["net"] <= 0], key=lambda l: l["net"])[:10]
    winners = sorted([l for l in legs if l["net"] > 0], key=lambda l: l["net"])[:10]
    net = np.array([l["net"] for l in legs])
    fig = plt.figure(figsize=(20, 11))
    gs = fig.add_gridspec(4, 5, hspace=0.5, wspace=0.25)
    for j, l in enumerate(losers):
        panel(fig.add_subplot(gs[j // 5, j % 5]), m, l)
    for j, l in enumerate(winners):
        panel(fig.add_subplot(gs[2 + j // 5, j % 5]), m, l)
    caught = sum(1 for l in losers if l["d300"] is not None and l["d300"] <= -20)
    fig.suptitle(f"{coin}_coinbase th{th:.0f} — 30d bins | n={len(legs)} net/leg {net.mean():+.2f} "
                 f"win {100*(net>0).mean():.0f}% | rows 1-2: 10 BIGGEST LOSERS "
                 f"({caught}/10 already <=-20 at E300 = catchable), rows 3-4: 10 SMALLEST WINNERS "
                 f"| orange dashed = E300 decision (^/v entry, * peak, X exit)", fontsize=11)
    os.makedirs(RDIR, exist_ok=True)
    fp = f"{RDIR}/e300_{coin}.png"
    fig.savefig(fp, dpi=100, bbox_inches="tight"); plt.close(fig)
    print(f"  {coin}: {fp}  ({caught}/10 biggest losers deep@E300)")
    return fp


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--coin", default="all")
    args = ap.parse_args()
    coins = list(CELLS) if args.coin == "all" else [args.coin]
    for c in coins:
        sym, th = CELLS[c]; render(c, sym, th)


if __name__ == "__main__":
    main()
