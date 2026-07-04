"""_s62_stack.py — S62 do-2 STACK: combine the weak-orthogonal loser signals (Greg).

Each in-container piece is individually weak at mid-band (cheap price-shape ~0.55, coeff ~0.49-0.54
pooled but with a faint consistent per-dim residual). Greg's standing principle: tools are
COMPLEMENTARY — stack them; a stack of weak-orthogonal signals can beat any one. This rig combines:
  CHEAP  = 6 strictly-pre-entry price-shape features (pre600 freight-train fade + stack)
  COEFF  = the 128-dim OD coeff (cached from _s62_coeff_bridge --save)
  DIPOLE = (slot) the dipole agent's descriptors — added when the agent's report lands
into one per-week-OOS classifier (GBM: tolerant of noise dims, finds nonlinear combinations),
graded as an ENTRY-FLIP driver in net $/hr @ $5k vs baseline + the entry-flip oracle.

Legs regenerated on the coeff-cache filter (ci >= PRE+2) so cheap features align with the cache.

Usage:  python scripts/_s62_stack.py --coin btc --theta 80 --bigloss 40
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
FC = 22.0
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CACHE_DIR = os.environ.get("S62_CACHE_DIR", "/tmp/s62cache")
SYM = dict(COINS)
PRE = 1800
WK = 7 * 24 * 3600


def cheap_features(mid, legs):
    logmid = np.log(mid)
    cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(logmid)))])
    rows = []
    for ci, xi, side, pivot in legs:
        pre600 = side * (logmid[ci] - logmid[ci - 600]) * 1e4
        pre120 = side * (logmid[ci] - logmid[ci - 120]) * 1e4
        seg = logmid[ci - 600:ci + 1]
        prevol = float(np.std(np.diff(seg))) * 1e4
        pl = cpath[ci] - cpath[ci - 600]
        preeff = abs(seg[-1] - seg[0]) / pl if pl > 0 else 0.0
        retrace = abs(logmid[ci] - logmid[pivot]) * 1e4
        p0 = max(0, pivot - 600)
        armrun = side * (logmid[pivot] - logmid[p0]) * 1e4
        rows.append([pre600, pre120, prevol, preeff, retrace, armrun])
    return np.array(rows, float)


def oos_auc_and_flip(X, y, week, gross, winner, bigloss, ok, hrs, base,
                     coeff_cols=None, sel_k=0):
    """coeff_cols = indices of X that are coeff dims; sel_k>0 = keep only the top-k of those by
    per-fold (TRAIN-only) big-loser-vs-winner |t| — leakage-safe faint-signal extraction."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from scipy import stats
    pred = np.full(len(y), np.nan)
    train = ok & (winner | bigloss)
    for w in sorted(set(week)):
        tr = train & (week != w); te = ok & (week == w)
        if tr.sum() < 40 or len(np.unique(y[tr])) < 2:
            continue
        Xtr, Xte = X, X
        if sel_k and coeff_cols is not None:
            cc = np.asarray(coeff_cols)
            tvals = np.array([abs(stats.ttest_ind(X[tr & bigloss, j], X[tr & winner, j],
                                                  equal_var=False).statistic) for j in cc])
            keep_coeff = cc[np.argsort(tvals)[::-1][:sel_k]]
            noncoeff = np.array([j for j in range(X.shape[1]) if j not in set(cc)], int)
            cols = np.r_[noncoeff, keep_coeff].astype(int)
            Xtr = X[:, cols]; Xte = X[:, cols]
        clf = HistGradientBoostingClassifier(max_depth=3, max_iter=120,
                                             learning_rate=0.06, l2_regularization=1.0)
        clf.fit(Xtr[tr], y[tr])
        pred[te] = clf.predict_proba(Xte[te])[:, 1]
    mm = train & ~np.isnan(pred)
    auc = roc_auc_score(bigloss[mm], pred[mm]) if len(np.unique(bigloss[mm])) > 1 else float("nan")
    best = (-1e9, None)
    okp = ok & ~np.isnan(pred)
    for pctl in (97, 95, 92, 90, 85, 80):
        thr = np.nanpercentile(pred[okp], pctl)
        fl = okp & (pred >= thr)
        d = float(np.sum(CAP * np.where(fl, -gross - FC, gross) / 1e4)) / hrs
        if d > best[0]:
            best = (d, (pctl, int(fl.sum()), int((fl & bigloss).sum()), int((fl & winner).sum())))
    return auc, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="btc")
    ap.add_argument("--theta", type=float, default=80.0)
    ap.add_argument("--bigloss", type=float, default=40.0)
    args = ap.parse_args()

    sym = SYM[args.coin]
    mid, *_r, hrs = load_bins(os.path.join(BINS_DIR, f"{sym}_30d_bins.json"))
    mid = np.asarray(mid, float); logmid = np.log(mid)
    flips = armed_midband_flips(mid, args.theta)
    legs = []
    for k in range(len(flips) - 1):
        ci, pivot, side = flips[k]; xi = flips[k + 1][0]
        ci = int(ci); xi = int(xi); pivot = int(pivot)
        if xi > ci and ci >= PRE + 2:
            legs.append((ci, xi, int(side), pivot))

    cache = np.load(os.path.join(CACHE_DIR, f"{args.coin}_coefs.npz"))
    coefs = cache["coefs"]; ok = cache["ok"]
    ecell = np.array([ci for ci, _, _, _ in legs])
    assert np.array_equal(ecell, cache["ecell"]), "leg/cache misalignment"
    gross = cache["gross"]
    winner = gross > 0; bigloss = gross <= -args.bigloss
    week = (ecell // WK).astype(int)
    y = bigloss.astype(int)
    base = float(np.sum(CAP * gross / 1e4)) / hrs
    orc = float(np.sum(CAP * np.where(bigloss, -gross - FC, gross) / 1e4)) / hrs

    Xc = cheap_features(mid, legs)
    Xco = coefs
    dipole_path = os.path.join(CACHE_DIR, f"{args.coin}_dipole.npz")
    have_dip = os.path.exists(dipole_path)
    Xd = np.load(dipole_path)["feats"] if have_dip else np.zeros((len(legs), 0))

    print(f"[{args.coin}] legs={len(legs)}  winners={int(winner.sum())}  "
          f"big-losers={int(bigloss.sum())}  baseline {base:+.2f}  entry-flip ORACLE {orc:+.2f} $/hr")
    print(f"  dipole features: {'LOADED ' + str(Xd.shape) if have_dip else 'not present yet (slot ready)'}")
    print(f"  {'feature set':22} {'OOS AUC':>8} {'best flip $/hr':>14} {'vs base':>8}  (pctl,nflip,BL,winflip)")
    ncheap = Xc.shape[1]
    Xstack = np.hstack([Xc, Xco])
    coeff_cols = list(range(ncheap, ncheap + Xco.shape[1]))
    sets = [("CHEAP (6)", Xc, None, 0),
            ("COEFF (128)", Xco, None, 0),
            ("CHEAP+COEFF(all)", Xstack, coeff_cols, 0),
            ("CHEAP+COEFF(sel8)", Xstack, coeff_cols, 8),
            ("CHEAP+COEFF(sel16)", Xstack, coeff_cols, 16)]
    if have_dip:
        Xall = np.hstack([Xc, Xco, Xd])
        cc2 = list(range(ncheap, ncheap + Xco.shape[1]))
        sets += [("CHEAP+DIPOLE", np.hstack([Xc, Xd]), None, 0),
                 ("STACK(sel16)", Xall, cc2, 16)]
    for name, X, cc, k in sets:
        auc, (d, info) = oos_auc_and_flip(X, y, week, gross, winner, bigloss, ok, hrs, base,
                                          coeff_cols=cc, sel_k=k)
        print(f"  {name:22} {auc:>8.3f} {d:>+14.2f} {d - base:>+8.2f}  {info}")


if __name__ == "__main__":
    main()
