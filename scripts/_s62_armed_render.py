"""_s62_armed_render.py — SOL render of the ARMED-FLIP decisions (Greg): 10 biggest losers +
10 smallest winners, with the arm point (-Xarm) and whether the flip FIRED marked, so we can
SEE what the early-arm+confirm flips (and why it also catches the dip-recoveries)."""
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
from _s62_armed_flip import build                                      # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier            # noqa: E402

COIN, SYM, TH, XARM = "sol", "SOLUSDT", 100.0, 15.0
WK = 7 * 24 * 3600
RDIR = "docs/renders/s62"


def main():
    X, gross, r_arm, ec, armed, hrs = build(COIN, SYM, TH, XARM)
    armd = np.array([x is not None for x in X]); death = gross <= -40; week = (ec // WK).astype(int)
    Xa = np.array([x for x in X if x is not None]); ya = death[armd].astype(int); wa = week[armd]
    pred = np.full(armd.sum(), np.nan)
    for w in sorted(set(wa)):
        tr = wa != w; te = wa == w
        if tr.sum() < 40 or len(np.unique(ya[tr])) < 2:
            continue
        c = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.05,
                                           l2_regularization=2.0).fit(Xa[tr], ya[tr])
        pred[te] = c.predict_proba(Xa[te])[:, 1]
    pf = np.full(len(gross), np.nan); pf[np.where(armd)[0]] = pred
    thr = np.nanpercentile(pf[~np.isnan(pf)], 70)
    fired = ~np.isnan(pf) & (pf >= thr)

    m, *_r, hrs = load_bins(f"/tmp/backfill/{SYM}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    fl = armed_midband_flips(m, TH, 0.5)
    legs = []
    kk = 0
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < 1802 or xi >= min(len(m), len(m)):
            continue
        legs.append((ci, xi, side, gross[kk], fired[kk], r_arm[kk])); kk += 1
    order_l = sorted([l for l in legs if l[3] <= 0], key=lambda l: l[3])[:10]
    order_w = sorted([l for l in legs if l[3] > 0], key=lambda l: l[3])[:10]

    def panel(ax, leg):
        ci, xi, side, g, fire, ra = leg
        pad = max(120, (xi - ci) // 8); a, b = max(0, ci - pad), min(len(m), xi + pad)
        t = (np.arange(a, b) - ci) / 60.0
        ax.plot(t, m[a:b], lw=0.6, color="#1f77b4")
        ax.plot(0, m[ci], "g^" if side > 0 else "gv", ms=5)
        # arm point: first cell reaching -XARM
        r = side * (lm[ci:xi + 1] - lm[ci]) * 1e4; und = np.where(r <= -XARM)[0]
        if len(und):
            aj = int(und[0]); ax.plot(aj / 60.0, m[ci + aj], "o", color="#ff7f0e", ms=5)
        ax.plot((xi - ci) / 60.0, m[xi], "x", color=("#2ca02c" if g > 0 else "#d62728"), ms=7, mew=2)
        tag = "FLIP" if fire else "hold"
        col = "#d62728" if (fire and g > 0) else ("#2ca02c" if (fire and g <= 0) else "#333")
        ax.set_title(f"{'B' if side > 0 else 'S'} net {g:+.0f} | {tag}", fontsize=7, color=col)
        ax.tick_params(labelsize=5)

    fig = plt.figure(figsize=(20, 11)); gs = fig.add_gridspec(4, 5, hspace=0.5, wspace=0.25)
    for j, l in enumerate(order_l):
        panel(fig.add_subplot(gs[j // 5, j % 5]), l)
    for j, l in enumerate(order_w):
        panel(fig.add_subplot(gs[2 + j // 5, j % 5]), l)
    good = sum(1 for l in order_l if l[4]); bad = sum(1 for l in order_w if l[4])
    fig.suptitle(f"SOL armed-flip (arm -{XARM:.0f}, dipole+coeff confirm) | biggest losers flipped "
                 f"{good}/10 (GOOD), smallest winners flipped {bad}/10 (BAD=collateral) | "
                 f"orange o = arm point, X exit, title green=correct flip red=wrong flip", fontsize=11)
    os.makedirs(RDIR, exist_ok=True); fp = f"{RDIR}/armed_sol.png"
    fig.savefig(fp, dpi=100, bbox_inches="tight"); plt.close(fig)
    print(f"biggest-losers flipped {good}/10, smallest-winners flipped {bad}/10 -> {fp}")


if __name__ == "__main__":
    main()
