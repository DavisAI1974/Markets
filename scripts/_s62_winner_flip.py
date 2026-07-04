"""_s62_winner_flip.py — S62 do-2 Greg's reframe: model the WINNER, flip the not-winners.

The loser class is diffuse ("everything that isn't a winner") -> no coherent loser coeff (shown).
Greg: model the WINNER signature instead; if a leg is NOT winner-like it's a loser and we flip it
-> no loser coeff needed. The flip economics favor this: flipping a WINNER is the expensive mistake
(-gross-22), so a winner model with high RECALL (correctly HELD winners) protects against exactly
that error while flipping the rest (big losers profit, small losers cost a little).

Target = winner(1) vs loser(0, all gross<=0). Per-week OOS classifier predicts P(winner). HOLD the
most-winner-like; FLIP the least-winner-like (bottom-q by P(winner)). Grade net $/hr @ $5k vs
baseline + entry-flip oracle; report winner RECALL (winners correctly held) at each cutoff.

Usage:  python scripts/_s62_winner_flip.py --coin eth --theta 80 --bigloss 40
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
from _s62_stack import cheap_features                                  # noqa: E402

CAP = 5000.0; FC = 22.0
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CACHE_DIR = os.environ.get("S62_CACHE_DIR", "/tmp/s62cache")
SYM = dict(COINS); PRE = 1800; WK = 7 * 24 * 3600


def pred_winner(X, y, week, ok):
    """per-week OOS P(winner). train on ALL legs (winner vs loser)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    pred = np.full(len(y), np.nan)
    for w in sorted(set(week)):
        tr = ok & (week != w); te = ok & (week == w)
        if tr.sum() < 40 or len(np.unique(y[tr])) < 2:
            continue
        clf = HistGradientBoostingClassifier(max_depth=3, max_iter=120,
                                             learning_rate=0.06, l2_regularization=1.0)
        clf.fit(X[tr], y[tr])
        pred[te] = clf.predict_proba(X[te])[:, 1]
    return pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="eth"); ap.add_argument("--theta", type=float, default=80.0)
    ap.add_argument("--bigloss", type=float, default=40.0)
    args = ap.parse_args()
    sym = SYM[args.coin]
    mid, *_r, hrs = load_bins(os.path.join(BINS_DIR, f"{sym}_30d_bins.json"))
    mid = np.asarray(mid, float)
    flips = armed_midband_flips(mid, args.theta)
    legs = []
    for k in range(len(flips) - 1):
        ci, pivot, side = flips[k]; xi = flips[k + 1][0]
        ci = int(ci); xi = int(xi); pivot = int(pivot)
        if xi > ci and ci >= PRE + 2:
            legs.append((ci, xi, int(side), pivot))
    cache = np.load(os.path.join(CACHE_DIR, f"{args.coin}_coefs.npz"))
    assert np.array_equal(np.array([c for c, _, _, _ in legs]), cache["ecell"])
    coefs = cache["coefs"]; ok = cache["ok"]; gross = cache["gross"]
    winner = gross > 0; loser = gross <= 0; bigloss = gross <= -args.bigloss
    week = (np.array([c for c, _, _, _ in legs]) // WK).astype(int)
    y = winner.astype(int)
    base = float(np.sum(CAP * gross / 1e4)) / hrs
    orc = float(np.sum(CAP * np.where(bigloss, -gross - FC, gross) / 1e4)) / hrs
    Xc = cheap_features(mid, legs)

    from sklearn.metrics import roc_auc_score
    print(f"[{args.coin}] legs={len(legs)}  winners={int(winner.sum())}  losers={int(loser.sum())} "
          f"(big={int(bigloss.sum())})  baseline {base:+.2f}  entry-flip ORACLE {orc:+.2f} $/hr")
    for name, X in [("CHEAP", Xc), ("COEFF", coefs), ("CHEAP+COEFF", np.hstack([Xc, coefs]))]:
        pred = pred_winner(X, y, week, ok)
        okp = ok & ~np.isnan(pred)
        auc = roc_auc_score(winner[okp], pred[okp]) if len(np.unique(winner[okp])) > 1 else np.nan
        best = (-1e9, None)
        for q in (5, 10, 15, 20, 30, 40):        # flip the least-winner-like bottom q%
            thr = np.nanpercentile(pred[okp], q)
            fl = okp & (pred <= thr)
            d = float(np.sum(CAP * np.where(fl, -gross - FC, gross) / 1e4)) / hrs
            if d > best[0]:
                recall = (okp & winner & (pred > thr)).sum() / max((okp & winner).sum(), 1)
                best = (d, (q, int(fl.sum()), int((fl & bigloss).sum()), int((fl & winner).sum()), recall))
        d, info = best
        q, nf, bl, wf, rec = info
        print(f"  {name:12} winner-AUC {auc:.3f}  flip bottom-{q}%: n={nf} bigL={bl} winFlip={wf} "
              f"winRecall={rec:.2f}  -> {d:+.2f} $/hr ({d - base:+.2f} vs base)")


if __name__ == "__main__":
    main()
