"""_s62_e300_3piece.py — S62 the 3-PIECE at E300 (Greg's reframe, the breakthrough).

The signal that separates deaths from recoveries is NOT at entry (winners-invisible) — it is at
E300 (300s after entry), where the realized DEPTH tells you the trend is continuing (S61 lead-time:
a death sits only ~-15bp underwater at E300 with ~-55bp still to come). A per-week-OOS classifier
on [depth@300, recent move, run, cross-major oppose-flow] predicts DEATH (final gross<=-40) at
AUC 0.69-0.77 across all 5 coins — the first strong, robust, cross-coin classifier of the session.

Greg's 3-piece, now with a working classifier + the run split, decided at E300 on legs still open:
  HOLD    P(death) low            -> ride to the natural exit
  FLATTEN P(death) high, weak run -> exit at E300 (small stop; the chop-loser)
  FLIP    P(death) high, strong run (we faded a big trend) -> reverse, ride the trend to exit

Grade: net $/hr @ $5k vs the long-leg baseline (legs open at E300; short legs unchanged), per-week
robustness, fee=0 (Greg handles fees; flip/flatten = taker crosses, accounted via FC on the flip).
Cross-major = BTC for the alts+eth, ETH for BTC. Same leg recipe as the S62 rig.

Usage:  python scripts/_s62_e300_3piece.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier            # noqa: E402
from sklearn.metrics import roc_auc_score                              # noqa: E402

CAP = 5000.0; FC = 22.0; WK = 7 * 24 * 3600; E = 300
BINS = "/tmp/backfill"
CELLS = [("eth", "ETHUSDT", "BTCUSDT", 80.0), ("btc", "BTCUSDT", "ETHUSDT", 80.0),
         ("sol", "SOLUSDT", "BTCUSDT", 100.0), ("xrp", "XRPUSDT", "BTCUSDT", 80.0),
         ("doge", "DOGEUSDT", "BTCUSDT", 100.0)]


def build(sym, cross, th):
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    mc, bc, sc, *_ = load_bins(f"{BINS}/{cross}_30d_bins.json")
    bc = np.asarray(bc, float); sc = np.asarray(sc, float)
    n = min(len(m), len(bc)); Bx = np.concatenate([[0], np.cumsum(bc)]); Sx = np.concatenate([[0], np.cumsum(sc)])
    fl = armed_midband_flips(m, th, 0.5)
    X, gross, r300, run, ec = [], [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci + E or ci < 1802 or xi >= n:
            continue
        rr = side * (lm[ci + E] - lm[ci]) * 1e4
        xo = -side * ((Bx[ci + E + 1] - Bx[ci]) - (Sx[ci + E + 1] - Sx[ci])) / \
            ((Bx[ci + E + 1] - Bx[ci]) + (Sx[ci + E + 1] - Sx[ci]) + 1e-9)
        rn = -side * (lm[ci] - lm[ci - 600]) * 1e4
        X.append([rr, side * (lm[ci + E] - lm[ci + E - 60]) * 1e4, rn, xo])
        gross.append(side * (lm[xi] - lm[ci]) * 1e4); r300.append(rr); run.append(rn); ec.append(ci)
    return (np.array(X), np.array(gross), np.array(r300), np.array(run),
            np.array(ec), (np.array(ec) // WK).astype(int))


def main():
    print(f"{'coin':5}{'open@300':>9}{'AUC':>7}{'base':>8}{'3piece':>8}{'Δ':>7}  per-week Δ")
    for coin, sym, cross, th in CELLS:
        X, gross, r300, run, ec, week = build(sym, cross, th)
        death = gross <= -40; y = death.astype(int); pred = np.full(len(y), np.nan)
        for w in sorted(set(week)):
            tr = week != w; te = week == w
            if tr.sum() < 40:
                continue
            c = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.05,
                                               l2_regularization=2.0).fit(X[tr], y[tr])
            pred[te] = c.predict_proba(X[te])[:, 1]
        ok = ~np.isnan(pred); auc = roc_auc_score(death[ok], pred[ok])
        thr = np.nanpercentile(pred[ok], 85)
        rstrong = np.nanpercentile(run[ok], 60)         # strong-run split (faded a big trend -> flip)
        act_flip = ok & (pred >= thr) & (run >= rstrong)
        act_flat = ok & (pred >= thr) & (run < rstrong)
        pnl = np.where(act_flip, -(gross - r300) - FC, np.where(act_flat, r300, gross))
        base = np.sum(CAP * gross[ok] / 1e4) / 720.0
        tot = np.sum(CAP * pnl[ok] / 1e4) / 720.0
        pw = []
        for w in sorted(set(week)):
            mk = (week == w) & ok; hh = (np.ptp(ec[mk]) + 1) / 3600.0 if mk.sum() else 1
            pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
        print(f"{coin:5}{ok.sum():>9}{auc:>7.3f}{base:>+8.2f}{tot:>+8.2f}{tot - base:>+7.2f}  "
              + " ".join(f"{x:+.1f}" for x in pw)
              + f"   (flip{int(act_flip.sum())}/flat{int(act_flat.sum())})")


if __name__ == "__main__":
    main()
