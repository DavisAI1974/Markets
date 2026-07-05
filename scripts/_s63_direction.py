"""_s63_direction.py — S63: the ONLY question — BUY or SELL (Greg's correction).

The machine's entry timing is CORRECT (the "win signal" finds real moves); it just takes the wrong
SIDE on the big losers (shorted clean uptrends). So we do NOT re-solve win/lose selection — we
solve DIRECTION: for each leg the machine already selects, was the correct side BUY or SELL?

Absolute-frame prediction (independent of the machine's own side):
  target y_up = (log(mid[xi]/mid[ci]) > 0)              # did price go UP over the leg
  pred_side  = +1 (buy) if P(up) > 0.5 else -1 (sell)
  machine_side = the machine's chosen side (fl[k][2]); machine acc = winner fraction (~0.51)

Features at entry ci (all ABSOLUTE up/down, causal, no look-ahead):
  price momentum up over W in {300,600,1800,3600,7200,14400}
  cross-major momentum up over the same W
  own order-flow imbalance (buy-sell)/(buy+sell) over {300,600,1800}
  cross-major order-flow imbalance over {300,600,1800}
Per-week OOS (leave-one-week-out), HistGradientBoosting.

Grading (both fee conventions, Greg picks):
  acc         = P(pred_side == fwd_dir)     vs machine ~0.51
  direct $/hr = pred_side * fwd  (side chosen AT entry, no flip fee)   [the deploy frame]
  flip  $/hr  = keep gross if agree, else -gross - 22 (mid-position flip)   [conservative]
Also RAW sign rules and their INVERSES (the "reading correctly but trading opposite" / sign-flip
hypothesis): +/-sign(mom W) for each W, absolute direction accuracy + direct $/hr.

Usage:  python scripts/_s63_direction.py
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

CAP = 5000.0; FC = 22.0; WK = 7 * 24 * 3600
BINS = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CELLS = [("eth", "ETHUSDT", "BTCUSDT", 80.0), ("btc", "BTCUSDT", "ETHUSDT", 80.0),
         ("sol", "SOLUSDT", "BTCUSDT", 100.0), ("xrp", "XRPUSDT", "BTCUSDT", 80.0),
         ("doge", "DOGEUSDT", "BTCUSDT", 100.0)]
MW = [300, 600, 1800, 3600, 7200, 14400]      # momentum windows
FW = [300, 600, 1800]                          # flow windows
MAXW = 14400


def build(sym, cross, th):
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json")
    m = np.asarray(m, float); lm = np.log(m); b = np.asarray(b, float); s = np.asarray(s, float)
    mc, bc, sc, *_ = load_bins(f"{BINS}/{cross}_30d_bins.json")
    mc = np.asarray(mc, float); lmc = np.log(mc); bc = np.asarray(bc, float); sc = np.asarray(sc, float)
    n = min(len(m), len(mc))
    Bo = np.concatenate([[0.0], np.cumsum(b)]); So = np.concatenate([[0.0], np.cumsum(s)])
    Bc = np.concatenate([[0.0], np.cumsum(bc)]); Sc = np.concatenate([[0.0], np.cumsum(sc)])
    fl = armed_midband_flips(m, th, 0.5)
    X, fwd, gross, mside, ec, mom1h = [], [], [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < MAXW or ci < 1802 or xi >= n:
            continue
        feats = []
        for W in MW:                                    # ABSOLUTE up-momentum (own + cross)
            feats.append((lm[ci] - lm[ci - W]) * 1e4)
            feats.append((lmc[ci] - lmc[ci - W]) * 1e4)
        for W in FW:                                    # ABSOLUTE flow imbalance (own + cross)
            bw = Bo[ci] - Bo[ci - W]; sw = So[ci] - So[ci - W]
            feats.append((bw - sw) / (bw + sw + 1e-9))
            bxw = Bc[ci] - Bc[ci - W]; sxw = Sc[ci] - Sc[ci - W]
            feats.append((bxw - sxw) / (bxw + sxw + 1e-9))
        X.append(feats)
        d = (lm[xi] - lm[ci]) * 1e4
        fwd.append(np.sign(d)); gross.append(side * d); mside.append(side); ec.append(ci)
        mom1h.append((lm[ci] - lm[ci - 3600]) * 1e4)
    return (np.array(X), np.array(fwd), np.array(gross), np.array(mside),
            np.array(ec), (np.array(ec) // WK).astype(int), np.array(mom1h), hrs)


def dph_direct(pred_side, gross, mside):
    """side chosen at entry: agree -> gross, disagree -> -gross (no flip fee)."""
    pnl = np.where(pred_side == mside, gross, -gross)
    return np.sum(CAP * pnl / 1e4) / 720.0, pnl


def dph_flip(pred_side, gross, mside):
    """conservative: disagree -> flip an open position, pay 22bp."""
    pnl = np.where(pred_side == mside, gross, -gross - FC)
    return np.sum(CAP * pnl / 1e4) / 720.0, pnl


def main():
    print("=== learned direction classifier (per-week OOS), absolute buy/sell ===")
    print(f"{'coin':5}{'n':>6}{'mAcc':>6}{'AUC':>6}{'pAcc':>6}{'base':>8}{'direct':>8}{'flip':>8}"
          f"   per-week direct-Δ")
    for coin, sym, cross, th in CELLS:
        X, fwd, gross, mside, ec, week, mom1h, hrs = build(sym, cross, th)
        y = (fwd > 0).astype(int)
        pred = np.full(len(y), np.nan)
        for w in sorted(set(week)):
            tr = week != w; te = week == w
            if tr.sum() < 40 or len(np.unique(y[tr])) < 2:
                continue
            c = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05,
                                               l2_regularization=2.0).fit(X[tr], y[tr])
            pred[te] = c.predict_proba(X[te])[:, 1]
        ok = ~np.isnan(pred)
        auc = roc_auc_score(y[ok], pred[ok]) if len(np.unique(y[ok])) > 1 else float("nan")
        pside = np.where(pred >= 0.5, 1, -1)
        macc = np.mean(mside[ok] == fwd[ok])
        pacc = np.mean(pside[ok] == fwd[ok])
        base = np.sum(CAP * gross[ok] / 1e4) / 720.0
        d_direct, pnl_d = dph_direct(pside[ok], gross[ok], mside[ok])
        d_flip, _ = dph_flip(pside[ok], gross[ok], mside[ok])
        pw = []
        for w in sorted(set(week)):
            mk = (week == w) & ok
            if mk.sum() < 2:
                pw.append(0.0); continue
            hh = (np.ptp(ec[mk]) + 1) / 3600.0
            _, pn = dph_direct(pside[mk], gross[mk], mside[mk])
            pw.append((np.sum(CAP * pn / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
        print(f"{coin:5}{int(ok.sum()):>6}{macc:>6.3f}{auc:>6.3f}{pacc:>6.3f}{base:>+8.2f}"
              f"{d_direct:>+8.2f}{d_flip:>+8.2f}   " + " ".join(f"{v:+.1f}" for v in pw))

    print("\n=== raw sign rules + INVERSES (abs direction acc | direct $/hr), pooled all legs ===")
    print(f"{'coin':5} " + "  ".join(f"{('+'+str(W)):>7}/{('-'+str(W)):>7}" for W in [600, 3600, 14400]))
    for coin, sym, cross, th in CELLS:
        X, fwd, gross, mside, ec, week, mom1h, hrs = build(sym, cross, th)
        # recompute per-window momentum sign accuracy vs fwd, and direct $/hr for +sign and -sign
        m, *_ = load_bins(f"{BINS}/{sym}_30d_bins.json"); lm = np.log(np.asarray(m, float))
        cells = []
        for W in [600, 3600, 14400]:
            for sgn in (+1, -1):
                # pred_side = sgn * sign(mom over W); need per-leg mom
                idx = ec
                mom = np.array([(lm[i] - lm[i - W]) * 1e4 for i in idx])
                pside = sgn * np.sign(mom); pside[pside == 0] = 1
                acc = np.mean(pside == fwd)
                d, _ = dph_direct(pside, gross, mside)
                cells.append(f"{acc:.2f}/{d:+.1f}")
        print(f"{coin:5} " + "  ".join(f"{cells[2*i]:>7} {cells[2*i+1]:>7}" for i in range(3)))


if __name__ == "__main__":
    main()
