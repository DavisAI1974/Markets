"""_s56_render_worst.py — the S56 walkthrough loop (Greg: "print the 10 worst losers and the
10 smallest winners... we're going to do this every time until it's right").

Renders the CURRENT candidate's legs: tight dipole-gated armed_fine_zigzag_v2 (reversal-class
veto), ARM60/FINE25, pooled across coins (BTC absent this round — mode-0 deadlock, fix queued).
Two contact sheets -> docs/renders/s56/legs/: worst10.png (by net@MM3 blend) + smallwin10.png
(smallest positive). Panel = price context (green long / red short shading, entry ^ exit v,
* = pivot) over a 60s flow-lean strip; title carries gross / net@mm3 / duration / confirm type
(fine|fallback) / dipole class + rev_conv at the open pivot.

Usage: python scripts/_s56_render_worst.py [--arm 60] [--fine 25]
"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS               # noqa: E402
from odcore.info_dipole import divergence                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s56", "legs")
RT_MM3 = -1.15          # 10%-taker blend at MM3 (Greg S56 scoring)
RT_TK = 11.0
LEAN_W = 60
DIVW = 600


def gated_v2_tagged(mid, buy, sell, arm_bp, fine_bp, mode_gate="reversal"):
    """Tight-gated v2 with per-flip tags + dipole read at the pivot. Mirrors
    _s56_armed_gate.armed_fine_zigzag_v2_gated exactly (assert-checked there)."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    cache = {}

    def gate(pi):
        if pi in cache:
            return cache[pi]
        lo = max(0, pi - DIVW)
        dv = None
        if pi - lo >= 12:
            dv = divergence(buy[lo:pi + 1], sell[lo:pi + 1], float(mid[pi] - mid[lo]))
        ok = bool(dv) and dv["expect"] == "reversal" if mode_gate == "reversal" \
            else ((dv is None) or dv["expect"] != "continue")
        cache[pi] = (ok, dv)
        return cache[pi]

    flips = []
    lo_i = hi_i = 0
    mode = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            if mid[hi_i] >= mid[lo_i] * (1 + a) and m <= mid[hi_i] * (1 - f):
                ok, dv = gate(hi_i)
                if ok:
                    flips.append((t, hi_i, -1, "fine", dv)); mode = -1; lo_i = t
                    continue
            if mode == 1 and m <= mid[hi_i] * (1 - a):
                flips.append((t, hi_i, -1, "fallback", cache.get(hi_i, (0, None))[1]))
                mode = -1; lo_i = t
                continue
        if mode <= 0:
            if mid[lo_i] <= mid[hi_i] * (1 - a) and m >= mid[lo_i] * (1 + f):
                ok, dv = gate(lo_i)
                if ok:
                    flips.append((t, lo_i, +1, "fine", dv)); mode = +1; hi_i = t
                    continue
            if mode == -1 and m >= mid[lo_i] * (1 + a):
                flips.append((t, lo_i, +1, "fallback", cache.get(lo_i, (0, None))[1]))
                mode = +1; hi_i = t
    return flips


def legs_for_coin(coin, sym, arm, fine):
    p = f"/tmp/backfill/{sym}_30d_bins.json"
    if not os.path.exists(p):
        return [], None
    mid, buy, sell, cov, hrs = load_bins(p)
    mid = np.asarray(mid, float)
    buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    fl = gated_v2_tagged(mid, buy, sell, arm, fine)
    legs = []
    for (c1, p1, s1, tag, dv), (c2, p2, s2, _t2, _d2) in zip(fl[:-1], fl[1:]):
        gross = s1 * (mid[c2] - mid[c1]) / mid[c1] * 1e4
        legs.append(dict(coin=coin, entry_i=int(c1), exit_i=int(c2), pivot_i=int(p1),
                         side=int(s1), gross=float(gross),
                         net_mm3=float(gross - RT_MM3), net_tk=float(gross - RT_TK),
                         tag=tag,
                         dcls=(dv["expect"] if dv else "None"),
                         rconv=(float(dv["reversal_conviction"]) if dv else float("nan"))))
    return legs, (mid, buy, sell)


def _panel(fig, gs_cell, mid, lean, leg):
    gs2 = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs_cell,
                                           height_ratios=[3, 1], hspace=0.05)
    ax = fig.add_subplot(gs2[0]); axl = fig.add_subplot(gs2[1], sharex=ax)
    e, x, pv, s = leg["entry_i"], leg["exit_i"], leg["pivot_i"], leg["side"]
    span = max(x - e, 60)
    pad = max(int(0.7 * span), 900)
    lo, hi = max(0, min(e, pv) - pad), min(len(mid) - 1, x + pad)
    idx = np.arange(lo, hi + 1)
    c = "#0a7a2f" if s > 0 else "#b3121b"
    ax.plot(idx, mid[lo:hi + 1], lw=0.6, color="#334", alpha=0.9, zorder=1)
    ax.axvspan(e, x, color=c, alpha=0.10, zorder=0)
    ax.plot(e, mid[e], marker="^", ms=8, color=c, zorder=3)
    ax.plot(x, mid[x], marker="v", ms=8, color=c, zorder=3)
    ax.plot(pv, mid[pv], marker="*", ms=10, color="#c58f00", zorder=3)
    ax.set_xticks([]); ax.tick_params(labelsize=6)
    dur = (x - e) / 3600.0
    ax.set_title(f"{leg['coin']} {'L' if s>0 else 'S'} gross {leg['gross']:+.1f}bp "
                 f"net@mm3 {leg['net_mm3']:+.1f} dur {dur:.2f}h {leg['tag']} "
                 f"[{leg['dcls']} rc={leg['rconv']:.2f}]", fontsize=6.5)
    axl.plot(idx, lean[lo:hi + 1], lw=0.5, color="#7a4fb0")
    axl.axhline(0, lw=0.4, color="#999")
    axl.axvline(pv, lw=0.4, color="#c58f00")
    axl.axvline(e, lw=0.4, color=c)
    axl.set_ylim(-1, 1); axl.tick_params(labelsize=5)
    axl.set_xticks([])


def sheet(path, title, legs, dat_by_coin):
    rows = int(np.ceil(len(legs) / 2))
    fig = plt.figure(figsize=(13, 3.4 * rows))
    gs = gridspec.GridSpec(rows, 2, hspace=0.5, wspace=0.15)
    for i, leg in enumerate(legs):
        mid, buy, sell = dat_by_coin[leg["coin"]]
        cb = np.concatenate([[0.0], np.cumsum(buy)])
        cs = np.concatenate([[0.0], np.cumsum(sell)])
        bw = cb[LEAN_W:] - cb[:-LEAN_W]; sw = cs[LEAN_W:] - cs[:-LEAN_W]
        tot = bw + sw
        lean = np.zeros(len(mid))
        nz = tot > 0
        lean[LEAN_W - 1:][nz] = (bw[nz] - sw[nz]) / tot[nz]
        _panel(fig, gs[i], mid, lean, leg)
    fig.suptitle(title, fontsize=10)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main():
    arm = float(sys.argv[sys.argv.index("--arm") + 1]) if "--arm" in sys.argv else 60.0
    fine = float(sys.argv[sys.argv.index("--fine") + 1]) if "--fine" in sys.argv else 25.0
    os.makedirs(OUT, exist_ok=True)
    all_legs = []
    dat = {}
    for coin, sym in COINS:
        legs, arrs = legs_for_coin(coin, sym, arm, fine)
        print(f"[{coin}] {len(legs)} legs")
        all_legs += legs
        if arrs is not None:
            dat[coin] = arrs
    worst = sorted(all_legs, key=lambda l: l["net_mm3"])[:10]
    winners = sorted([l for l in all_legs if l["net_mm3"] > 0], key=lambda l: l["net_mm3"])[:10]
    tag = f"tight ARM{arm:.0f}/FINE{fine:.0f} mm3 blend"
    sheet(os.path.join(OUT, "worst10.png"), f"S56 walkthrough — 10 WORST losers ({tag})",
          worst, dat)
    sheet(os.path.join(OUT, "smallwin10.png"), f"S56 walkthrough — 10 SMALLEST winners ({tag})",
          winners, dat)


if __name__ == "__main__":
    main()
