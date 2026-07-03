"""_s55_render_legs.py — PER-LEG renders of the S54 trade tables for Greg's S55 walkthrough (JOB 0).

One panel per leg: mid price with context padding around the leg, green=long / red=short shading,
entry ▲ / exit ▼, dashed = the actual trendline held (bigline legs, every redraw segment).
Contact sheets (4 panels wide) -> docs/renders/s55/legs/.

Sets rendered:
  coinbase   adaptive big line on the 5 Coinbase book windows + 2 Bybit book windows
             (all 92 legs of _s54_legs_bigline_coinbase.csv, sheet per cell)
  bybit_bl   adaptive big line on 30d x 5 Bybit bins — best 12 + worst 12 cross-coin
  bybit_zz   zigzag flip theta150 on the same bins — best 12 + worst 12 cross-coin
Needs books in /tmp/*_book.jsonl.gz and bins in /tmp/backfill/ (see S55 kickoff to re-pull).
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                      # noqa: E402
from _liquidity_dive import build_channels              # noqa: E402
from _capacity_model import FLOW_W                      # noqa: E402
from _s52_accum_vs_oneshot import _price_zigzag         # noqa: E402
from _s54_bigline_probe import CELLS, DEC, FIXED_AD     # noqa: E402
from _s54_backfill_sweep import load_bins, COINS        # noqa: E402
from odcore.swing_bigline import run_bigline_adaptive   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s55", "legs")


def _utc(t):
    return datetime.fromtimestamp(t, tz=timezone.utc)


def _leg_panel(ax, mid, t0, entry_i, exit_i, side, entry_px, exit_px, gross, rt,
               segments=(), tag=""):
    span = max(exit_i - entry_i, 60)
    pad = max(int(0.5 * span), 900)
    lo, hi = max(0, entry_i - pad), min(len(mid) - 1, exit_i + pad)
    idx = np.arange(lo, hi + 1)
    c = "#0a7a2f" if side > 0 else "#b3121b"
    ax.plot(idx, mid[lo:hi + 1], lw=0.6, color="#334", alpha=0.9, zorder=1)
    ax.axvspan(entry_i, exit_i, color=c, alpha=0.10, zorder=0)
    for (i0, i1, px0, sl) in segments:
        i1c = min(i1, hi)
        if i0 <= hi and i1c >= lo:
            ax.plot([i0, i1c], [px0 + sl * 0, px0 + sl * (i1c - i0)],
                    color=c, lw=1.3, ls="--", zorder=2)
    ax.plot(entry_i, entry_px, marker="^", ms=8, color=c, zorder=3)
    ax.plot(exit_i, exit_px, marker="v", ms=8, color=c, zorder=3)
    net = gross - rt
    d0 = _utc(t0 + entry_i)
    ax.set_title(f"{tag} {'LONG' if side > 0 else 'SHORT'}  net {net:+.0f}bp  "
                 f"{(exit_i - entry_i) / 3600.0:.2f}h  {d0:%m-%d %H:%M}", fontsize=8)
    ticks = np.linspace(lo, hi, 4)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{_utc(t0 + int(x)):%H:%M}" for x in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(alpha=0.25, lw=0.4)


def _sheet(fname, title, panels):
    """panels: list of dicts with keys mid,t0,entry_i,exit_i,side,entry_px,exit_px,gross,rt,segments,tag"""
    n = len(panels)
    cols = 4
    rows = max(1, math.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.1 * rows))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes[n:]:
        ax.axis("off")
    for ax, p in zip(axes, panels):
        _leg_panel(ax, p["mid"], p["t0"], p["entry_i"], p["exit_i"], p["side"],
                   p["entry_px"], p["exit_px"], p["gross"], p["rt"],
                   p.get("segments", ()), p.get("tag", ""))
    fig.suptitle(title, fontsize=12, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    f = os.path.join(OUT, fname)
    fig.savefig(f, dpi=100)
    plt.close(fig)
    print(f"-> {f} ({n} legs)")
    return f


def render_coinbase():
    for (cell, path, K, tk) in CELLS:
        if not os.path.exists(path):
            print(f"[{cell}] no book — skipped")
            continue
        raw = load_book(path)
        ch, g = build_channels(path, K, FLOW_W, raw=raw)
        mid = np.asarray(g["mid"], float)[::DEC]
        t0 = float(raw["ts"][0])
        legs = run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        panels = [dict(mid=mid, t0=t0, entry_i=l.entry_i, exit_i=l.exit_i, side=l.side,
                       entry_px=l.entry_px, exit_px=l.exit_px, gross=l.gross_bps,
                       rt=2 * tk, segments=l.segments,
                       tag=f"#{k + 1}{' F' if l.forced else ''} r{l.n_redraws}")
                  for k, l in enumerate(legs)]
        for s in range(0, len(panels), 16):
            chunk = panels[s:s + 16]
            _sheet(f"cb_{cell}_legs_{s + 1:02d}.png",
                   f"{cell} — ADAPTIVE BIG LINE (Coinbase book window) — legs {s + 1}-{s + len(chunk)} "
                   f"of {len(panels)}   [dashed = line held; F = forced end-of-window]",
                   chunk)


def _bybit_arrays():
    out = {}
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] no bins — skipped")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        with open(p) as f:
            t0 = min(float(k) for k in json.load(f).keys())
        out[coin] = (np.asarray(mid, float), t0)
    return out


def render_bybit(arrays):
    # adaptive big line legs, cross-coin pool
    bl = []
    for coin, (mid, t0) in arrays.items():
        legs = run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        for l in legs:
            bl.append(dict(mid=mid, t0=t0, entry_i=l.entry_i, exit_i=l.exit_i, side=l.side,
                           entry_px=l.entry_px, exit_px=l.exit_px, gross=l.gross_bps,
                           rt=11.0, segments=l.segments,
                           tag=f"{coin} r{l.n_redraws}"))
    bl.sort(key=lambda p: p["gross"], reverse=True)
    _sheet("by_bigline_best12.png",
           "BYBIT 30d x 5 — ADAPTIVE BIG LINE — 12 BEST legs (the waves it does catch)", bl[:12])
    _sheet("by_bigline_worst12.png",
           "BYBIT 30d x 5 — ADAPTIVE BIG LINE — 12 WORST legs (the chop that killed the gate)",
           bl[-12:][::-1])

    # zigzag theta150 legs, cross-coin pool
    zz = []
    for coin, (mid, t0) in arrays.items():
        fl = _price_zigzag(mid, 150.0)
        for a, b in zip(fl[:-1], fl[1:]):
            ci, s, cj = int(a[0]), int(a[2]), int(b[0])
            gross = s * (mid[cj] - mid[ci]) / mid[ci] * 1e4
            zz.append(dict(mid=mid, t0=t0, entry_i=ci, exit_i=cj, side=s,
                           entry_px=float(mid[ci]), exit_px=float(mid[cj]), gross=gross,
                           rt=11.0, tag=f"{coin}"))
    zz.sort(key=lambda p: p["gross"], reverse=True)
    _sheet("by_zz150_best12.png",
           "BYBIT 30d x 5 — ZIGZAG FLIP theta150 — 12 BEST legs (the rides; S55 two-scale baseline)",
           zz[:12])
    _sheet("by_zz150_worst12.png",
           "BYBIT 30d x 5 — ZIGZAG FLIP theta150 — 12 WORST legs (bounded ~ -theta-fees fakeouts)",
           zz[-12:][::-1])


def main():
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "coinbase"):
        render_coinbase()
    if which in ("all", "bybit"):
        arrays = _bybit_arrays()
        if arrays:
            render_bybit(arrays)


if __name__ == "__main__":
    main()
