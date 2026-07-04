"""_s61_exit_renders.py — S61 post-build renders: 10 BIGGEST LOSERS + 10 SMALLEST WINNERS
per Coinbase cell (Greg's print order), rendered from the NEW executor code path
(run_stream + exit_spec) so stop/flip exits are visible where they fired.

One montage PNG per cell (base registry cells + S61 exit variants), 4 rows x 5 cols:
rows 1-2 = the 10 biggest losers by net_bps, rows 3-4 = the 10 smallest winners
(the barely-winners — where the toll eats the prize). Each panel: mid over the leg
(pad on both sides), E=open fill, X=close (RED marker when the close was an exit_spec
stop/flip trigger), P=peak-favorable; the 600s-wall with-ride lean strip underneath with
the variant's dive_lo line where applicable.

Usage: MPLBACKEND=Agg python scripts/_s61_exit_renders.py
Out:   docs/renders/s61/legs_<cell>.png
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import replace                                        # noqa: E402
from _birth_probe import load_book                                     # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps          # noqa: E402
from odcore.entry_coinbase import (COINBASE_MIDBAND, COINBASE_MIDBAND_VARIANTS,  # noqa: E402
                                   armed_midband_flips)
from odcore.flip_detector import lean_series                           # noqa: E402
from odcore.platform import run_stream, FLOW_W                         # noqa: E402

GRID_S = 0.1
LEAN_W = int(600 / GRID_S)          # 600s wall-clock on the 0.1s book grid
N_EACH = 10


def cell_legs(cfg):
    """Rerun one cell through the platform executor; return (legs, mid, lean)."""
    p = cfg.path
    if not os.path.exists(p):
        return None
    raw = load_book(p)
    _, g = build_channels(p, cfg.K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(p, raw=raw) / 2.0
    flips = armed_midband_flips(mid, cfg.theta_bp, cfg.c, bounce_frac=cfg.bounce_frac)
    if len(flips) < 2:
        return None
    lean_w = LEAN_W if cfg.exit_spec is not None else None
    res, _ = run_stream(mid, buy, sell, flips, best_bid_sz=bb, best_ask_sz=ba,
                        half_spread_bps=hs, maker_fee=cfg.maker_fee, taker_fee=cfg.taker_fee,
                        exit_spec=cfg.exit_spec, lean_w=lean_w)
    lean = lean_series(buy, sell, LEAN_W)
    return res.legs, mid, lean


def panel(ax_p, ax_l, mid, lean, leg, cfg):
    oi, xi, sd = int(leg.open_idx), int(leg.close_idx), int(leg.side)
    pad = max(300, (xi - oi) // 10)
    lo, hi = max(0, oi - pad), min(len(mid) - 1, xi + pad)
    t = (np.arange(lo, hi + 1) - oi) * GRID_S / 60.0        # minutes from open
    seg = mid[lo:hi + 1]
    ax_p.plot(t, seg, lw=0.6, color="#1f77b4")
    fav = sd * (mid[oi:xi + 1] - mid[oi]) / mid[oi] * 1e4
    pk = oi + int(np.argmax(fav))
    ax_p.plot([(oi - oi) * GRID_S / 60.0], [mid[oi]], "g^" if sd > 0 else "gv", ms=5)
    ax_p.plot([(pk - oi) * GRID_S / 60.0], [mid[pk]], "b*", ms=6)
    xcol = "red" if leg.stop_exit else "black"
    ax_p.plot([(xi - oi) * GRID_S / 60.0], [mid[xi]], "x", color=xcol, ms=7, mew=2)
    tag = " STOP" if leg.stop_exit else ""
    ax_p.set_title(f"{'B' if sd > 0 else 'S'} net {leg.net_bps:+.0f}bp "
                   f"pk {float(fav.max()):+.0f} dur {(xi-oi)*GRID_S/60:.0f}m{tag}", fontsize=7)
    ax_p.tick_params(labelsize=5)
    sl = sd * lean[lo:hi + 1]
    ax_l.plot(t, sl, lw=0.5, color="#7f7f7f")
    ax_l.axhline(0, lw=0.4, color="k")
    if cfg.exit_spec is not None and "dive_lo" in cfg.exit_spec:
        ax_l.axhline(cfg.exit_spec["dive_lo"], lw=0.5, color="purple", ls="--")
    ax_l.set_ylim(-1, 1)
    ax_l.tick_params(labelsize=5)


def render_cell(cfg, rdir):
    out = cell_legs(cfg)
    if out is None:
        print(f"[{cfg.cell}] no tape/legs")
        return None
    legs, mid, lean = out
    losers = sorted([l for l in legs if l.net_bps <= 0], key=lambda l: l.net_bps)[:N_EACH]
    winners = sorted([l for l in legs if l.net_bps > 0], key=lambda l: l.net_bps)[:N_EACH]
    picks = [("BIGGEST LOSERS", losers), ("SMALLEST WINNERS", winners)]
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(4 * 2, 5, height_ratios=[3, 1] * 4, hspace=0.9, wspace=0.3)
    for gi, (label, group) in enumerate(picks):
        for j, leg in enumerate(group):
            row = gi * 2 + j // 5
            ax_p = fig.add_subplot(gs[row * 2, j % 5])
            ax_l = fig.add_subplot(gs[row * 2 + 1, j % 5])
            panel(ax_p, ax_l, mid, lean, leg, cfg)
            if j == 0:
                ax_p.set_ylabel(label, fontsize=8, fontweight="bold")
    net = np.array([l.net_bps for l in legs])
    fires = sum(1 for l in legs if l.stop_exit)
    fig.suptitle(f"{cfg.cell} — books, cb_real frame | n={len(legs)} net/leg {net.mean():+.2f} "
                 f"win {100*(net>0).mean():.0f}% stop_fires {fires} | "
                 f"rows 1-2: 10 biggest losers, rows 3-4: 10 smallest winners "
                 f"(E=open, *=peak, X=close, red X=stop/flip)", fontsize=10)
    fp = os.path.join(rdir, f"legs_{cfg.cell}.png")
    fig.savefig(fp, dpi=110)
    plt.close(fig)
    print(f"[{cfg.cell}] wrote {fp} (n={len(legs)}, fires={fires})")
    return fp


def main():
    rdir = os.path.join("docs", "renders", "s61")
    os.makedirs(rdir, exist_ok=True)
    for cfg in COINBASE_MIDBAND + COINBASE_MIDBAND_VARIANTS:
        render_cell(replace(cfg, active=True), rdir)


if __name__ == "__main__":
    main()
