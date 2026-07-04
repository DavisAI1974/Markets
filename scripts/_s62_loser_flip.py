"""_s62_loser_flip.py — S62 the LOSING-TRADE-SIGNATURE piece as an ENTRY-FLIP driver.

Greg (S62): the baseline->oracle gap IS the big losing trades; flip them at entry and they
turn into big winners (entry-flip oracle: sol +30 / eth +23 / doge +22 / xrp +22 / btc +14 $/hr
@ -40 threshold). The oracle cheats with the outcome; this builds the CAUSAL classifier that
recognizes a big-loser ENTRY STATE before the leg fires, then flips it.

Same-period, leakage-clean (the honest test — no S34 date confound): current 30d-bins legs of the
promoted mid-band machine, strictly-pre-entry features only, per-week OOS (train on 3 weeks,
predict the 4th, rotate). Label big-loser = gross <= -T ; winner = gross > 0. The driver flips
legs the classifier flags; grade net $/hr @ $5k vs baseline (hold-all) and the entry-flip oracle,
counting winners wrongly flipped (the cost the classifier must control).

Fee frame = Coinbase (Greg handles fees) -> fee=0; FLIP = 22bp taker cross (locked S62 convention).

Features (STRICTLY causal — computed from mid[..ci] and the pivot only):
  pre600   signed pre-entry return over the 600 cells into entry (R13 freight-train fade: a big
           loser fades a move still running against it -> pre600 negative)
  pre120   shorter signed pre-entry return
  prevol   trailing 600-cell realized vol (bp/cell)
  preeff   trailing-600 trend efficiency |net|/pathlen (Greg's smoothness signal, causal)
  retrace  the confirm move |mid[ci]-mid[pivot]| in bp (~theta; kind proxy)
  armrun   signed run into the pivot (side*ret pivot-600..pivot) — the move being faded
  hod      hour-of-day (cyclical -> sin/cos)

Usage:
    python scripts/_s62_loser_flip.py --coin btc --theta 80 --bigloss 40
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

CAP = 5000.0
FC = 22.0                          # flip taker cross (bp), locked S62
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
SYM = dict(COINS)
WK_S = 7 * 24 * 3600.0             # week in seconds (1s cells -> cells)
W = 600                            # pre-entry window (cells)


def leg_table(mid, theta, c=0.5):
    """Return (feats[n,k], gross[n], entry_cell[n], week[n], featnames)."""
    flips = armed_midband_flips(mid, theta, c)
    logmid = np.log(mid)
    # cumulative abs-log-return path for efficiency denominators
    cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(logmid)))])
    rows, gross, ecell = [], [], []
    for k in range(len(flips) - 1):
        ci, pivot, side = flips[k]
        xi = flips[k + 1][0]
        ci = int(ci); pivot = int(pivot); xi = int(xi)
        if xi <= ci or ci < W + 1:
            continue
        g = side * (logmid[xi] - logmid[ci]) * 1e4
        # strictly pre-entry (<= ci) features
        pre600 = side * (logmid[ci] - logmid[ci - 600]) * 1e4
        pre120 = side * (logmid[ci] - logmid[ci - 120]) * 1e4
        seg = logmid[ci - W:ci + 1]
        prevol = float(np.std(np.diff(seg))) * 1e4
        pathlen = cpath[ci] - cpath[ci - W]
        preeff = abs(seg[-1] - seg[0]) / pathlen if pathlen > 0 else 0.0
        retrace = abs(logmid[ci] - logmid[pivot]) * 1e4
        p0 = max(0, pivot - 600)
        armrun = side * (logmid[pivot] - logmid[p0]) * 1e4
        rows.append([pre600, pre120, prevol, preeff, retrace, armrun])
        gross.append(g); ecell.append(ci)
    feats = np.array(rows, float)
    gross = np.array(gross, float)
    ecell = np.array(ecell, int)
    week = (ecell // int(WK_S)).astype(int)     # 1s cells -> week bucket
    names = ["pre600", "pre120", "prevol", "preeff", "retrace", "armrun"]
    return feats, gross, ecell, week, names


def logistic_oos(X, y, week):
    """Per-week OOS predicted P(class1): train on other weeks, predict held-out. Standardized."""
    from sklearn.linear_model import LogisticRegression
    pred = np.full(len(y), np.nan)
    wks = np.unique(week)
    for w in wks:
        tr = week != w; te = week == w
        if tr.sum() < 20 or te.sum() == 0 or len(np.unique(y[tr])) < 2:
            continue
        mu = X[tr].mean(0); sd = X[tr].std(0) + 1e-9
        clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        clf.fit((X[tr] - mu) / sd, y[tr])
        pred[te] = clf.predict_proba((X[te] - mu) / sd)[:, 1]
    return pred


def dph(pnl, hrs):
    return float(np.sum(CAP * pnl / 1e4)) / hrs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="btc")
    ap.add_argument("--theta", type=float, default=80.0)
    ap.add_argument("--bigloss", type=float, default=40.0, help="big-loser threshold -T (bp)")
    args = ap.parse_args()

    sym = SYM[args.coin]
    path = os.path.join(BINS_DIR, f"{sym}_30d_bins.json")
    if not os.path.exists(path):
        sys.exit(f"[{args.coin}] bins missing at {path}")
    mid, *_rest, hrs = load_bins(path)
    mid = np.asarray(mid, float)
    X, gross, ecell, week, names = leg_table(mid, args.theta)
    n = len(gross)
    winner = gross > 0
    bigloss = gross <= -args.bigloss
    print(f"[{args.coin}] {sym} th{args.theta:.0f}  legs={n}  hrs={hrs:.1f}  "
          f"winners={winner.sum()}  big-losers(<=-{args.bigloss:.0f})={bigloss.sum()}  "
          f"small={n - winner.sum() - bigloss.sum()}")

    base = dph(gross, hrs)
    orc_pnl = np.where(bigloss, -gross - FC, gross)
    oracle = dph(orc_pnl, hrs)
    print(f"  BASELINE {base:+.2f} $/hr   |   ENTRY-FLIP ORACLE {oracle:+.2f} $/hr "
          f"(flip the {bigloss.sum()} true big-losers)")

    # causal classifier: big-loser (1) vs winner (0); small losers excluded from TRAINING
    # but scored/acted at inference (they are neither clean pos nor neg)
    train_mask = winner | bigloss
    y = bigloss.astype(int)
    Xtr = X.copy()
    pred = logistic_oos(Xtr[train_mask], y[train_mask], week[train_mask])
    # score all legs OOS: refit per-week on train_mask legs, predict every held-out leg
    from sklearn.linear_model import LogisticRegression
    full_pred = np.full(n, np.nan)
    for w in np.unique(week):
        tr = (week != w) & train_mask
        te = week == w
        if tr.sum() < 20 or len(np.unique(y[tr])) < 2:
            continue
        mu = X[tr].mean(0); sd = X[tr].std(0) + 1e-9
        clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit((X[tr] - mu) / sd, y[tr])
        full_pred[te] = clf.predict_proba((X[te] - mu) / sd)[:, 1]

    ok = ~np.isnan(full_pred)
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(bigloss[ok & train_mask], full_pred[ok & train_mask]) \
        if len(np.unique(bigloss[ok & train_mask])) > 1 else float("nan")
    print(f"  classifier OOS AUC (big-loser vs winner): {auc:.3f}")

    # entry-flip driver: flip legs with P(big-loser) >= q-quantile; sweep the cutoff
    print("  flip-cutoff sweep (flip legs above the P-percentile):")
    print(f"    {'pctl':>5} {'nflip':>5} {'true_bl':>7} {'winners_flipped':>15} {'$/hr':>8} {'vs base':>8}")
    for pctl in (95, 90, 85, 80, 70, 60, 50):
        thr = np.nanpercentile(full_pred[ok], pctl)
        flip = ok & (full_pred >= thr)
        pnl = np.where(flip, -gross - FC, gross)
        d = dph(pnl, hrs)
        tb = int((flip & bigloss).sum()); wf = int((flip & winner).sum())
        print(f"    {pctl:>5} {int(flip.sum()):>5} {tb:>7} {wf:>15} {d:>+8.2f} {d - base:>+8.2f}")


if __name__ == "__main__":
    main()
