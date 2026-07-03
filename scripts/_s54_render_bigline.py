"""_s54_render_bigline.py — render the BIG LINE rides on the full-window shapes (Greg walkthrough).

Fixed config tp60/eps10 (chosen in advance in _s54_bigline_probe.py, not tuned). Green = long ride,
red = short ride; the dashed line is the actual trendline the engine was holding (every redraw
segment). Entry ▲ / exit ▼ at the taker prices used in the probe. PNGs -> docs/renders/s54/bigline/.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                      # noqa: E402
from _liquidity_dive import build_channels              # noqa: E402
from _capacity_model import FLOW_W                      # noqa: E402
from _s54_bigline_probe import CELLS, FIXED_BL, FIXED_AD, DEC  # noqa: E402
from odcore.swing_bigline import run_bigline, run_bigline_adaptive  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "renders", "s54", "bigline")


def main():
    os.makedirs(OUT, exist_ok=True)
    tp, eps = FIXED_BL
    for (cell, path, K, tk) in CELLS:
        if not os.path.exists(path):
            continue
        raw = load_book(path)
        ch, g = build_channels(path, K, FLOW_W, raw=raw)
        mid = np.asarray(g["mid"], float)[::DEC]
        hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
        t = np.linspace(0.0, hrs, len(mid))
        variants = [
            (f"tp{tp:.0f}/eps{eps:.0f} aligned", run_bigline(mid, tp, eps), "bigline"),
            (f"ADAPTIVE f{FIXED_AD[0]:.2f}/w{FIXED_AD[1]:.0f}h aligned",
             run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600)), "bigline_adaptive"),
        ]
        for (vlbl, legs, suffix) in variants:
            net = sum(l.gross_bps - 2 * tk for l in legs)
            fig, ax = plt.subplots(figsize=(15, 6))
            ax.plot(t, mid, lw=0.5, color="#334", alpha=0.85, zorder=1)
            for l in legs:
                c = "#0a7a2f" if l.side > 0 else "#b3121b"
                ax.axvspan(t[l.entry_i], t[l.exit_i], color=c, alpha=0.07, zorder=0)
                for (i0, i1, px0, sl) in l.segments:
                    ax.plot([t[i0], t[i1]], [px0, px0 + sl * (i1 - i0)],
                            color=c, lw=1.4, ls="--", zorder=2)
                ax.plot(t[l.entry_i], l.entry_px, marker="^", ms=7, color=c, zorder=3)
                ax.plot(t[l.exit_i], l.exit_px, marker="v", ms=7,
                        color=("#666" if l.forced else c), zorder=3)
            ax.set_title(f"{cell} — BIG LINE {vlbl}   {len(legs)} rides   "
                         f"net {net:+.0f}bps taker-taker   window {hrs:.1f}h", fontsize=10)
            ax.set_xlabel("hours"); ax.set_ylabel("mid")
            ax.grid(alpha=0.25, lw=0.4)
            f = os.path.join(OUT, f"{cell}_{suffix}.png")
            fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
            print(f"[{cell}] {vlbl}: {len(legs)} rides net {net:+.0f}bps -> {f}")


if __name__ == "__main__":
    main()
