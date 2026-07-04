"""_s62_tune.py — S62 Piece-1: tune the causal ENTRY-FLIP classifier (the in-container payer).

The cheap 6-feature flip got eth +0.80 $/hr; this pushes it with a richer STRICTLY-CAUSAL feature
set + a principled flip rule. The flip breakeven: flip_pnl = -gross-FC, hold_pnl = gross -> flip
better when gross < -FC/2 = -11bp. So a REGRESSION head predicting gross, flipping legs predicted
< -11, is the honest rule (no in-sample percentile cherry-pick). A CLASSIFICATION head (big-loss
vs not) is compared. Per-week OOS throughout; per cell.

Features (all from mid[..ci] and the pivot — causal):
  multi-scale signed pre-entry fade    pre{60,120,300,600,1800}  (freight-train: negative = fading
                                        a move still running against the new position)
  fade acceleration                    accel = pre120 - pre600/5   (building vs exhausting)
  vol regime                           vol60, vol600, volratio=vol60/vol600
  trend efficiency (smoothness)        eff300, eff600, eff1800
  arm quality                          armrun (move into pivot), armeff (its efficiency)
  confirm quality                      retrace_bp, retrace_over_theta
  time                                 hod_sin, hod_cos

Usage:  python scripts/_s62_tune.py --coin eth --theta 80 --bigloss 40
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS                       # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

CAP = 5000.0; FC = 22.0; BREAKEVEN = -FC / 2.0        # gross below which flip beats hold
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
SYM = dict(COINS); WK = 7 * 24 * 3600
DAY = 24 * 3600


def features(mid, theta):
    logmid = np.log(mid)
    cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(logmid)))])
    flips = armed_midband_flips(mid, theta)
    def sret(a, b, side):  # signed return a->b in the leg direction, bp
        return side * (logmid[b] - logmid[a]) * 1e4
    def eff(a, b):
        pl = cpath[b] - cpath[a]
        return abs(logmid[b] - logmid[a]) / pl if pl > 0 else 0.0
    def vol(a, b):
        return float(np.std(np.diff(logmid[a:b + 1]))) * 1e4 if b > a + 1 else 0.0
    rows, gross, ec, sides = [], [], [], []
    for k in range(len(flips) - 1):
        ci, pivot, side = flips[k]; xi = flips[k + 1][0]
        ci = int(ci); pivot = int(pivot); xi = int(xi)
        if xi <= ci or ci < 1801:
            continue
        pre = {w: sret(ci - w, ci, side) for w in (60, 120, 300, 600, 1800)}
        accel = pre[120] - pre[600] / 5.0
        v60, v600 = vol(ci - 60, ci), vol(ci - 600, ci)
        armrun = sret(max(0, pivot - 600), pivot, side)
        armeff = eff(max(0, pivot - 600), pivot)
        retrace = abs(logmid[ci] - logmid[pivot]) * 1e4
        hod = (ci % DAY) / DAY * 2 * np.pi
        rows.append([pre[60], pre[120], pre[300], pre[600], pre[1800], accel,
                     v60, v600, v60 / (v600 + 1e-9), eff(ci - 300, ci), eff(ci - 600, ci),
                     eff(ci - 1800, ci), armrun, armeff, retrace, retrace / theta,
                     np.sin(hod), np.cos(hod)])
        gross.append(sret(ci, xi, side)); ec.append(ci); sides.append(side)
    names = ["pre60", "pre120", "pre300", "pre600", "pre1800", "accel", "vol60", "vol600",
             "volratio", "eff300", "eff600", "eff1800", "armrun", "armeff", "retrace",
             "retr_theta", "hod_sin", "hod_cos"]
    return (np.array(rows, float), np.array(gross, float), np.array(ec, int),
            np.array(sides, int), names)


def flip_dph(flip_mask, gross, hrs):
    return float(np.sum(CAP * np.where(flip_mask, -gross - FC, gross) / 1e4)) / hrs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="eth"); ap.add_argument("--theta", type=float, default=80.0)
    ap.add_argument("--bigloss", type=float, default=40.0)
    args = ap.parse_args()
    mid, *_r, hrs = load_bins(os.path.join(BINS_DIR, f"{SYM[args.coin]}_30d_bins.json"))
    mid = np.asarray(mid, float)
    X, gross, ec, sides, names = features(mid, args.theta)
    week = (ec // WK).astype(int)
    winner = gross > 0; bigloss = gross <= -args.bigloss
    base = float(np.sum(CAP * gross / 1e4)) / hrs
    orc = flip_dph(bigloss, gross, hrs)
    print(f"[{args.coin}] th{args.theta:.0f} legs={len(gross)} feats={X.shape[1]} winners={winner.sum()} "
          f"big={bigloss.sum()}  baseline {base:+.2f}  entry-flip ORACLE {orc:+.2f} $/hr")

    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    # REGRESSION head: predict gross, flip predicted < BREAKEVEN (principled, no cutoff pick)
    rp = np.full(len(gross), np.nan)
    cp = np.full(len(gross), np.nan)
    trainc = winner | bigloss
    for w in sorted(set(week)):
        tr = week != w; te = week == w
        if tr.sum() < 40:
            continue
        reg = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05,
                                            l2_regularization=1.0)
        reg.fit(X[tr], gross[tr]); rp[te] = reg.predict(X[te])
        trc = tr & trainc
        if len(np.unique(bigloss[trc])) > 1:
            clf = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05,
                                                 l2_regularization=1.0)
            clf.fit(X[trc], bigloss[trc].astype(int)); cp[te] = clf.predict_proba(X[te])[:, 1]

    from sklearn.metrics import roc_auc_score
    okr = ~np.isnan(rp)
    reg_auc = roc_auc_score(bigloss[okr & trainc], -rp[okr & trainc])
    flip_reg = okr & (rp < BREAKEVEN)
    d_reg = flip_dph(flip_reg, gross, hrs)
    print(f"  REGRESSION->flip(pred<-11): AUC {reg_auc:.3f}  n={int(flip_reg.sum())} "
          f"big={int((flip_reg & bigloss).sum())} winFlip={int((flip_reg & winner).sum())}  "
          f"{d_reg:+.2f} $/hr ({d_reg - base:+.2f} vs base)")

    okc = ~np.isnan(cp)
    clf_auc = roc_auc_score(bigloss[okc & trainc], cp[okc & trainc])
    print("  CLASSIFY->flip top-q by P(big-loss):")
    for q in (95, 92, 90, 85, 80):
        thr = np.nanpercentile(cp[okc], q); fl = okc & (cp >= thr)
        d = flip_dph(fl, gross, hrs)
        print(f"    top-{100 - q:>2}%  AUC {clf_auc:.3f}  n={int(fl.sum())} big={int((fl & bigloss).sum())} "
              f"winFlip={int((fl & winner).sum())}  {d:+.2f} ({d - base:+.2f} vs base)")


if __name__ == "__main__":
    main()
