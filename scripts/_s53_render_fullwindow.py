"""_s53_render_fullwindow.py — full-window mid-price shape per cell, NO trade marks (Greg, S53).

Zoom-out sanity view: the entire collected window per cell (35h Coinbase / ~6h Bybit), price only.
Title carries window hours, median spread, total high-low range in bps, and net drift in bps so the
shapes can be compared across cells without axis-scale illusions (the L1 lesson: autoscale makes a
29bps wiggle look like a mountain). PNGs -> docs/renders/s53/fullwindow/.
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from _capacity_model import FLOW_W
from _s53_accum_sandbox import CELLS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "renders", "s53", "fullwindow")


def main():
    os.makedirs(OUT, exist_ok=True)
    for (cell, path, k, grace, mk, tk) in CELLS:
        if not os.path.exists(path):
            print(f"[{cell}] no book"); continue
        raw = load_book(path)
        ch, g = build_channels(path, k, FLOW_W, raw=raw)
        mid = np.asarray(g["mid"], float)
        hs2 = median_spread_bps(path, raw=raw)
        hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
        t = np.linspace(0.0, hrs, len(mid))
        rng_bps = (mid.max() - mid.min()) / mid.min() * 1e4
        drift_bps = (mid[-1] - mid[0]) / mid[0] * 1e4
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(t, mid, lw=0.5, color="#334", alpha=0.9)
        ax.set_title(f"{cell} — FULL WINDOW {hrs:.1f}h   spread {hs2:.2f}bps   "
                     f"hi-lo range {rng_bps:.0f}bps   net drift {drift_bps:+.0f}bps", fontsize=10)
        ax.set_xlabel("hours from window start"); ax.set_ylabel("mid")
        ax.grid(alpha=0.25, lw=0.4)
        f = os.path.join(OUT, f"{cell}_fullwindow.png")
        fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
        print(f"[{cell}] {hrs:.1f}h range {rng_bps:.0f}bps drift {drift_bps:+.0f}bps -> {f}")


if __name__ == "__main__":
    main()
