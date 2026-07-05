"""_s62_armed_trend.py — S62 armed flip, TREND-gated (Greg): arm at -X (sweep earlier depths),
gate the flip on the TREND/MOMENTUM read instead of the coeff.

Structure is Greg's: arm when the leg goes -X underwater; then a GATE decides FLIP vs FLATTEN:
  smooth STRONG adverse trend (the price is trending against us efficiently) -> FLIP (ride it)
  choppy / weak (a dip that will bounce)                                      -> FLATTEN (cut)
  never reached -X                                                            -> HOLD
The gate is a per-week-OOS classifier on the at-arm TREND features (depth, in-leg efficiency,
adverse momentum, time-to-arm, pre-entry run, dipole adverse taker-flow own+cross) predicting
DEATH (final <=-40 = the trend continues). FLIP the predicted-continues, FLATTEN the rest.
This is the direction-carrying signal the coeff couldn't provide.

Sweep earlier arm depths (5..30). fee=0; flip=22bp taker; flatten = exit at the arm depth.
Prints how many of the 10 biggest losers flip (Greg's success test).
Usage:  python scripts/_s62_armed_trend.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier           # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

CAP = 5000.0; FC = 22.0; WK = 7 * 24 * 3600
BINS = "/tmp/backfill"
CELLS = [("sol", "SOLUSDT", "BTCUSDT", 100.0), ("eth", "ETHUSDT", "BTCUSDT", 80.0),
         ("btc", "BTCUSDT", "ETHUSDT", 80.0), ("xrp", "XRPUSDT", "BTCUSDT", 80.0),
         ("doge", "DOGEUSDT", "BTCUSDT", 100.0)]


def load_coin(coin, sym, cross, th):
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    b = np.asarray(b, float); s = np.asarray(s, float)
    mc, bc, sc, *_ = load_bins(f"{BINS}/{cross}_30d_bins.json"); bc = np.asarray(bc, float); sc = np.asarray(sc, float)
    return dict(m=m, lm=lm, hrs=hrs, n=min(len(m), len(bc)),
                cpath=np.concatenate([[0.0], np.cumsum(np.abs(np.diff(lm)))]),
                Bo=np.concatenate([[0.0], np.cumsum(b)]), So=np.concatenate([[0.0], np.cumsum(s)]),
                Bx=np.concatenate([[0.0], np.cumsum(bc)]), Sx=np.concatenate([[0.0], np.cumsum(sc)]),
                flips=armed_midband_flips(m, th, 0.5))


def build(D, xarm):
    lm = D["lm"]; n = D["n"]; cpath = D["cpath"]; Bo = D["Bo"]; So = D["So"]; Bx = D["Bx"]; Sx = D["Sx"]
    fl = D["flips"]
    X, gross, r_arm, ec = [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < 1802 or xi >= n:
            continue
        r = side * (lm[ci:xi + 1] - lm[ci]) * 1e4; und = np.where(r <= -xarm)[0]
        gross.append(float(r[-1])); ec.append(ci)
        if len(und) == 0:
            X.append(None); r_arm.append(None); continue
        aj = ci + int(und[0]); ra = float(r[int(und[0])]); t_arm = int(und[0])
        pl = cpath[aj] - cpath[ci]; eff = abs(lm[aj] - lm[ci]) / pl if pl > 0 else 0.0
        mom = side * (lm[aj] - lm[max(ci, aj - 60)]) * 1e4
        run = -side * (lm[ci] - lm[ci - 600]) * 1e4
        Bw = Bo[aj + 1] - Bo[ci]; Sw = So[aj + 1] - So[ci]; own_adv = -side * (Bw - Sw) / (Bw + Sw + 1e-9)
        Bxw = Bx[aj + 1] - Bx[ci]; Sxw = Sx[aj + 1] - Sx[ci]; xadv = -side * (Bxw - Sxw) / (Bxw + Sxw + 1e-9)
        X.append([ra, eff, mom, t_arm, run, own_adv, xadv]); r_arm.append(ra)
    return X, np.array(gross), r_arm, np.array(ec), D["hrs"]


def run(D, xarm, cutpct=70):
    X, gross, r_arm, ec, hrs = build(D, xarm)
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
    okp = ~np.isnan(pred); auc = roc_auc_score(ya[okp], pred[okp]) if len(np.unique(ya[okp])) > 1 else float("nan")
    pf = np.full(len(gross), np.nan); pf[np.where(armd)[0]] = pred
    thr = np.nanpercentile(pf[~np.isnan(pf)], cutpct)
    ra_full = np.array([r if r is not None else 0.0 for r in r_arm])
    pnl = gross.copy(); nflip = nflat = fb = fw = 0
    for i in range(len(gross)):
        if not armd[i] or np.isnan(pf[i]):
            continue
        if pf[i] >= thr:                          # predicted continue/trend -> FLIP
            pnl[i] = -(gross[i] - ra_full[i]) - FC; nflip += 1; fb += death[i]; fw += gross[i] > 0
        else:                                     # chop/recovery -> FLATTEN
            pnl[i] = ra_full[i]; nflat += 1
    base = np.sum(CAP * gross / 1e4) / hrs; tot = np.sum(CAP * pnl / 1e4) / hrs
    pw = []
    for w in sorted(set(week)):
        mk = week == w; hh = (np.ptp(ec[mk]) + 1) / 3600.0 if mk.sum() else 1
        pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
    order = np.argsort(gross)[:10]
    big10 = sum(1 for i in order if armd[i] and not np.isnan(pf[i]) and pf[i] >= thr)
    return dict(auc=auc, base=base, tot=tot, pw=pw, nflip=nflip, nflat=nflat, fb=fb, fw=fw, big10=big10)


def main():
    for coin, sym, cross, th in CELLS:
        D = load_coin(coin, sym, cross, th)
        print(f"\n[{coin}] TREND-gated armed flip (flip predicted-trend, flatten chop; per-week OOS)")
        print(f"   {'arm':>4}{'AUC':>6}{'base':>8}{'gated':>8}{'Δ':>7}{'flip':>6}{'flat':>6}  big10  fire(big/win)  per-week Δ")
        for x in (5, 7, 10, 15, 20, 30):
            r = run(D, float(x))
            print(f"   -{x:<3}{r['auc']:>6.3f}{r['base']:>+8.2f}{r['tot']:>+8.2f}{r['tot']-r['base']:>+7.2f}"
                  f"{r['nflip']:>6}{r['nflat']:>6}  {r['big10']:>2}/10   {r['fb']:>3}/{r['fw']:<3}    "
                  + " ".join(f"{v:+.1f}" for v in r['pw']))


if __name__ == "__main__":
    main()
