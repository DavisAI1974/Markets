"""_s63_e300_trend.py — S63 Job 2: fold the 1h-TREND direction read into the working E300 rig.

S63 Job-1 result: the raw 1h-trend ENTRY flip fails (winners fade the 1h trend too -> selection
wall). But the diagnostic proved the 1h trend IS a real DIRECTION axis conditional on a death
(0.69-0.73). And the E300 depth classifier already SELECTS deaths (AUC 0.69-0.77, BTC +1.29/hr).
So the synthesis: **E300 depth = death SELECTOR, 1h trend = flip-DIRECTION confirm.**

This reproduces `_s62_e300_3piece.py` exactly (row E300) and adds two 1h pieces:
  (F) add mom1h as CLASSIFIER FEATURES (entry + at-E300 1h log-return, signed to our side).
  (G) a flip-DIRECTION GATE: only FLIP a predicted-death if the 1h trend is against our side
      (i.e. flipping to -side FOLLOWS the 1h trend, the 0.69 read). Predicted-deaths whose 1h
      trend does NOT confirm -> FLATTEN (cut) instead of flip.

Compare per coin, per-week: base | E300 (repro) | E300+feat | E300+feat+gate.
Grade: net $/hr @ $5k over 720h; fee=0; flip/flatten = taker cross via FC on the flip.

Usage:  python scripts/_s63_e300_trend.py
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

CAP = 5000.0; FC = 22.0; WK = 7 * 24 * 3600; E = 300; H1 = 3600
BINS = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CELLS = [("eth", "ETHUSDT", "BTCUSDT", 80.0), ("btc", "BTCUSDT", "ETHUSDT", 80.0),
         ("sol", "SOLUSDT", "BTCUSDT", 100.0), ("xrp", "XRPUSDT", "BTCUSDT", 80.0),
         ("doge", "DOGEUSDT", "BTCUSDT", 100.0)]


def build(sym, cross, th):
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    mc, bc, sc, *_ = load_bins(f"{BINS}/{cross}_30d_bins.json")
    bc = np.asarray(bc, float); sc = np.asarray(sc, float)
    n = min(len(m), len(bc)); Bx = np.concatenate([[0], np.cumsum(bc)]); Sx = np.concatenate([[0], np.cumsum(sc)])
    cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(lm)))])
    fl = armed_midband_flips(m, th, 0.5)
    X, Xf, gross, r300, eff, ec, tr1h_side = [], [], [], [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci + E or ci < H1 or ci < 1802 or xi >= n:      # need 1h history
            continue
        rr = side * (lm[ci + E] - lm[ci]) * 1e4
        xo = -side * ((Bx[ci + E + 1] - Bx[ci]) - (Sx[ci + E + 1] - Sx[ci])) / \
            ((Bx[ci + E + 1] - Bx[ci]) + (Sx[ci + E + 1] - Sx[ci]) + 1e-9)
        rn = -side * (lm[ci] - lm[ci - 600]) * 1e4
        pl300 = cpath[ci + E] - cpath[ci]; e300 = abs(lm[ci + E] - lm[ci]) / pl300 if pl300 > 0 else 0.0
        pl150 = cpath[ci + E] - cpath[ci + E - 150]; e150 = abs(lm[ci + E] - lm[ci + E - 150]) / pl150 if pl150 > 0 else 0.0
        adv_eff = e300 * np.sign(rr)
        # 1h trend, signed to OUR side: >0 = 1h trend WITH our side, <0 = trend AGAINST us (the fade)
        mom1h_e = side * (lm[ci + E] - lm[ci + E - H1]) * 1e4        # at E300
        mom1h_c = side * (lm[ci] - lm[ci - H1]) * 1e4                # at entry
        base_feats = [rr, side * (lm[ci + E] - lm[ci + E - 60]) * 1e4, rn, xo, e300, e150, adv_eff]
        X.append(base_feats)
        Xf.append(base_feats + [mom1h_e, mom1h_c])                   # +1h features
        gross.append(side * (lm[xi] - lm[ci]) * 1e4); r300.append(rr); eff.append(e300); ec.append(ci)
        # flip follows the 1h trend when the 1h trend is AGAINST our side (mom1h_e < 0)
        tr1h_side.append(mom1h_e)
    return (np.array(X), np.array(Xf), np.array(gross), np.array(r300),
            np.array(eff), np.array(ec), (np.array(ec) // WK).astype(int), np.array(tr1h_side))


def oos_pred(Xin, y, week):
    pred = np.full(len(y), np.nan)
    for w in sorted(set(week)):
        tr = week != w; te = week == w
        if tr.sum() < 40 or len(np.unique(y[tr])) < 2:
            continue
        c = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.05,
                                           l2_regularization=2.0).fit(Xin[tr], y[tr])
        pred[te] = c.predict_proba(Xin[te])[:, 1]
    return pred


def policy_pnl(pred, gross, r300, eff, mom1h_e, ok, gate):
    """E300 3-piece: predicted-death -> flip(smooth)/flatten(choppy); else hold.
    gate=True adds the 1h flip-direction confirm: flip only if mom1h_e<0 (trend against side)."""
    thr = np.nanpercentile(pred[ok], 85)
    esmooth = np.nanpercentile(eff[ok], 55)
    is_death_pred = ok & (pred >= thr)
    smooth = eff >= esmooth
    if gate:
        confirm = mom1h_e < 0.0             # 1h trend against our side -> flipping follows it
        act_flip = is_death_pred & smooth & confirm
        act_flat = is_death_pred & (~(smooth & confirm))
    else:
        act_flip = is_death_pred & smooth
        act_flat = is_death_pred & (~smooth)
    pnl = np.where(act_flip, -(gross - r300) - FC, np.where(act_flat, r300, gross))
    return pnl, int(act_flip.sum()), int(act_flat.sum())


def perweek(pnl, gross, week, ec, ok):
    pw = []
    for w in sorted(set(week)):
        mk = (week == w) & ok
        hh = (np.ptp(ec[mk]) + 1) / 3600.0 if mk.sum() > 1 else 1.0
        pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
    return pw


def main():
    print(f"{'coin':5}{'open':>6}{'AUC0':>7}{'AUCf':>7}{'base':>8}{'E300':>8}{'E300+f':>8}"
          f"{'+f+gate':>9}   per-week (E300+f+gate)")
    for coin, sym, cross, th in CELLS:
        X, Xf, gross, r300, eff, ec, week, mom1h_e = build(sym, cross, th)
        death = gross <= -40; y = death.astype(int)
        pred0 = oos_pred(X, y, week); predf = oos_pred(Xf, y, week)
        ok = ~np.isnan(pred0) & ~np.isnan(predf)
        auc0 = roc_auc_score(death[ok], pred0[ok]); aucf = roc_auc_score(death[ok], predf[ok])
        base = np.sum(CAP * gross[ok] / 1e4) / 720.0
        # E300 repro (base classifier, no gate)
        p_e300, _, _ = policy_pnl(pred0, gross, r300, eff, mom1h_e, ok, gate=False)
        tot_e300 = np.sum(CAP * p_e300[ok] / 1e4) / 720.0
        # E300 + 1h features (no gate)
        p_ef, _, _ = policy_pnl(predf, gross, r300, eff, mom1h_e, ok, gate=False)
        tot_ef = np.sum(CAP * p_ef[ok] / 1e4) / 720.0
        # E300 + 1h features + flip-direction gate
        p_efg, nfl, nfa = policy_pnl(predf, gross, r300, eff, mom1h_e, ok, gate=True)
        tot_efg = np.sum(CAP * p_efg[ok] / 1e4) / 720.0
        pw = perweek(p_efg, gross, week, ec, ok)
        print(f"{coin:5}{int(ok.sum()):>6}{auc0:>7.3f}{aucf:>7.3f}{base:>+8.2f}{tot_e300:>+8.2f}"
              f"{tot_ef:>+8.2f}{tot_efg:>+9.2f}   " + " ".join(f"{v:+.1f}" for v in pw)
              + f"  (flip{nfl}/flat{nfa})")


if __name__ == "__main__":
    main()
