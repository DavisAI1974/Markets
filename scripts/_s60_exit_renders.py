"""_s60_exit_renders.py — S60 PIECE 2: WORST-GIVEBACK renders (where is the exit bleed?).

One montage PNG per registry cell: the 10 worst legs by GIVEBACK (peak_fav - gross) of the
promoted machine (naive k0, registry theta). Each panel: mid path over the leg (entry confirm
E, peak P, zigzag exit X) + the with-ride lean sl underneath with the R8 collapse (sl<=0 after
arm 0.10, orange) and the dipole DIVE (first sl<=-0.30, purple) trigger marks — showing where
each candidate exit would have fired inside the bleed window.

Usage: MPLBACKEND=Agg python scripts/_s60_exit_renders.py --venue books|bins
Out:   docs/renders/s60/exit_bleed_<coin>_<venue>.png
"""
import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import load_venue                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                 # noqa: E402
from odcore.flip_detector import lean_series                          # noqa: E402

REGISTRY_TH = {"sol": 100.0, "xrp": 80.0, "doge": 100.0, "btc": 80.0}
C, WFLIP = 0.5, 600
ARM, XLO, DIVE = 0.10, 0.0, -0.30
N_WORST = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="books")
    args = ap.parse_args()
    rdir = os.path.join("docs", "renders", "s60")
    os.makedirs(rdir, exist_ok=True)
    grid_s = 1.0 if args.venue == "bins" else 0.1

    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        if coin == "eth":
            continue
        theta = REGISTRY_TH[coin]
        lean = lean_series(buy, sell, WFLIP)
        flips = armed_midband_flips(mid, theta, C)
        if len(flips) < 2:
            continue
        legs = []
        for j in range(len(flips) - 1):
            ci, pi, sd = flips[j]
            xi = flips[j + 1][0]
            seg = mid[ci:xi + 1]
            fav = sd * (seg - mid[ci]) / mid[ci] * 1e4
            pk = int(np.argmax(fav))
            legs.append((float(fav[pk]) - float(fav[-1]), j, ci, xi, sd, pk,
                         float(fav[pk]), float(fav[-1])))
        legs.sort(reverse=True)
        worst = legs[:N_WORST]

        fig, axes = plt.subplots(5, 4, figsize=(22, 16),
                                 gridspec_kw=dict(height_ratios=[3, 1, 3, 1, 3][:5]))
        # layout: rows of (price, lean) pairs -> use 5x4 grid = 10 (price,lean) pairs stacked 2-wide
        fig.suptitle(f"{coin} {args.venue} th{theta:.0f} c{C} — 10 WORST GIVEBACK legs "
                     f"(bleed = peak P -> zigzag exit X; orange=R8 arm.10->0, purple=dive -0.30)",
                     fontsize=13)
        fig.subplots_adjust(hspace=0.5, wspace=0.25)
        axs = axes.ravel()
        # simpler: 10 slots of price panels w/ twin lean strip below via inset
        for a in axs:
            a.axis("off")
        fig2, ax2 = plt.subplots(5, 2, figsize=(20, 22))
        fig2.suptitle(f"{coin} {args.venue} th{theta:.0f} c{C} — 10 WORST GIVEBACK legs "
                      f"(E entry, P peak, X zigzag exit; orange=R8(0.10,0), purple=dive(-0.30))",
                      fontsize=14)
        for slot, (gb, j, ci, xi, sd, pk, pfav, gr) in enumerate(worst):
            ax = ax2.ravel()[slot]
            pad = max(30, (xi - ci) // 10)
            lo, hi = max(0, ci - pad), min(len(mid) - 1, xi + pad)
            t = (np.arange(lo, hi + 1) - ci) * grid_s / 60.0        # minutes from entry
            ax.plot(t, mid[lo:hi + 1], color="#1414dc", lw=0.8)
            ax.axvline(0, color="k", lw=0.8)
            ax.plot(0, mid[ci], "ko", ms=6)
            ax.plot((pk) * grid_s / 60.0, mid[ci + pk], "g^", ms=9)
            ax.plot((xi - ci) * grid_s / 60.0, mid[xi], "rv", ms=9)
            sl = sd * lean[ci:xi + 1]
            armed = np.flatnonzero(sl >= ARM)
            r8t = -1
            if len(armed):
                after = np.flatnonzero(sl[armed[0]:] <= XLO)
                if len(after):
                    r8t = armed[0] + after[0]
            dvt = np.flatnonzero(sl <= DIVE)
            if r8t >= 0:
                ax.axvline(r8t * grid_s / 60.0, color="orange", lw=1.4, alpha=0.9)
            if len(dvt):
                ax.axvline(dvt[0] * grid_s / 60.0, color="purple", lw=1.4, alpha=0.9)
            side = "LONG" if sd > 0 else "SHORT"
            ax.set_title(f"#{slot} {side}  gross {gr:+.0f}bp  peak {pfav:+.0f}  GIVEBACK {gb:.0f}bp"
                         f"  dur {(xi-ci)*grid_s/60.0:.0f}m  peak@{pk*grid_s/60.0:.0f}m",
                         fontsize=10)
            ax.tick_params(labelsize=8)
            # lean strip inset
            axl = ax.inset_axes([0.0, -0.32, 1.0, 0.22], sharex=ax)
            tl = np.arange(0, xi - ci + 1) * grid_s / 60.0
            axl.plot(tl, sl, color="#666", lw=0.7)
            axl.axhline(ARM, color="orange", lw=0.6, ls=":")
            axl.axhline(0.0, color="k", lw=0.5)
            axl.axhline(DIVE, color="purple", lw=0.6, ls=":")
            axl.set_ylim(-1, 1)
            axl.tick_params(labelsize=7)
        plt.close(fig)
        out = os.path.join(rdir, f"exit_bleed_{coin}_{args.venue}.png")
        fig2.subplots_adjust(hspace=0.75)
        fig2.savefig(out, dpi=90)
        plt.close(fig2)
        med_gb = float(np.median([x[0] for x in legs]))
        print(f"[{coin} {args.venue}] {out}  legs={len(legs)} med_giveback={med_gb:.1f} "
              f"(c*theta={C*theta:.0f})")


if __name__ == "__main__":
    main()
