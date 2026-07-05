"""_s63_kraken_direction_timing.py — WHEN does the agent know direction? (Greg: "it doesn't have to be at 0")

The E300 breakthrough: a signal invisible at entry is strong MID-LEG. Same test for DIRECTION. For each
base-detector leg [ci -> nci], evaluate the direction agent at several times t INTO the trade and predict
the REMAINING move's direction (from ci+t to the exit nci), causal. If accuracy climbs from ~0.50 at
t=0 to something usable by t=120/300s, then we know direction mid-leg (not at entry) — and can act then.

At eval cell j=ci+t: absolute-frame features (predict UP/DOWN of the remaining move):
  realized-so-far (lm[j]-lm[ci]), mom 600/3600 @j, flow lean imb_level(1h)@j, aligned_flow@j.
Target y = sign(lm[nci]-lm[j]). Per-week OOS. Report accuracy at each t, overall AND conditional on
legs that END as big losers (gross<=-40) — for those, "knowing" = predicting the continued adverse side.

Usage:  python scripts/_s63_kraken_direction_timing.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier           # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

WFLIP, REV = 600, 0.1; WK = 7 * 24 * 3600; H1 = 3600
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD"), ("btc", "XBTUSD"), ("sol", "SOLUSD")]
TIMES = [0, 60, 120, 300, 600]        # seconds into the trade to evaluate
BIGLOSS = -40.0


def imb1h(cb, cs, j):
    lo = max(j + 1 - H1, 0)
    B = cb[j + 1] - cb[lo]; S = cs[j + 1] - cs[lo]; t = B + S
    return (B - S) / t if t > 0 else 0.0


def build_at(mid, lm, cb, cs, flips, t, n):
    X, y, isbig, week = [], [], [], []
    for k in range(len(flips) - 1):
        ci, _pv, side = flips[k]; nci = flips[k + 1][0]; ci = int(ci); nci = int(nci); side = int(side)
        if nci <= ci + t or ci < 14400 or ci < 1802 or nci >= n:
            continue
        j = ci + t
        rem = (lm[nci] - lm[j]) * 1e4                       # remaining move (absolute)
        if rem == 0:
            continue
        sofar = (lm[j] - lm[ci]) * 1e4
        m600 = (lm[j] - lm[j - 600]) * 1e4
        m1h = (lm[j] - lm[j - 3600]) * 1e4
        lvl = imb1h(cb, cs, j)
        aligned = lvl * (1.0 if m1h > 0 else -1.0)
        gross = side * (lm[nci] - lm[ci]) * 1e4
        X.append([sofar, m600, m1h, lvl, aligned]); y.append(1 if rem > 0 else 0)
        isbig.append(gross <= BIGLOSS); week.append(ci // WK)
    return np.array(X), np.array(y), np.array(isbig), np.array(week)


def main():
    print("=== WHEN does the agent know direction? accuracy of the REMAINING move by time-into-trade ===")
    print(f"{'coin':5}{'t=0':>7}{'t=60':>7}{'t=120':>8}{'t=300':>8}{'t=600':>8}   (overall dir-acc)")
    for coin, pair in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"{coin:5} (not present)"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); lm = np.log(mid)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float); n = len(mid)
        cb = np.concatenate([[0.0], np.cumsum(buy)]); cs = np.concatenate([[0.0], np.cumsum(sell)])
        lean = lean_series(buy, sell, WFLIP); flips, _ = detect_flips(lean, REV)
        over = []; big = []; ns = []
        for t in TIMES:
            X, y, isbig, week = build_at(mid, lm, cb, cs, flips, t, n)
            pred = np.full(len(y), np.nan)
            for w in sorted(set(week)):
                tr = week != w; te = week == w
                if tr.sum() < 40 or len(np.unique(y[tr])) < 2:
                    continue
                c = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05,
                                                   l2_regularization=2.0).fit(X[tr], y[tr])
                pred[te] = c.predict_proba(X[te])[:, 1]
            ok = ~np.isnan(pred); ag = np.where(pred >= 0.5, 1, -1); fwd = np.where(y > 0, 1, -1)
            over.append(np.mean(ag[ok] == fwd[ok]))
            bm = ok & isbig
            big.append(np.mean(ag[bm] == fwd[bm]) if bm.sum() else float("nan"))
            ns.append(int(bm.sum()))
        print(f"{coin:5}" + "".join(f"{v:>7.3f}" if i == 0 else f"{v:>8.3f}"
                                     for i, v in enumerate(over)))
        print(f"     big-loser side-known%:" + " ".join(f"{100*v:.0f}%(n{nn})" for v, nn in zip(big, ns)))
    print("\n  If accuracy climbs 0.50 -> higher with t, the agent knows direction MID-LEG, not at entry.")


if __name__ == "__main__":
    main()
