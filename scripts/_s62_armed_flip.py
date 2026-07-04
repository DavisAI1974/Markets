"""_s62_armed_flip.py — S62 Greg's ARMED FLIP: arm early at -10/-15, fire only when CONFIRMED.

Greg's design: the flip must be sent EARLIER (catch the move before the -90 loss). As soon as a
leg moves -X_arm (10 or 15bp) underwater it ARMS; then it waits for a CONFIRMATION (the coeff /
the trend signal) to say "yes, this is a real mislabeled-direction death" before firing. Confirmed
-> FLIP at the arm cell (reverse, ride the trend). Not confirmed -> HOLD (spare the dip-recoveries).

Why this beats the fixed-E300 stop (from the SOL render): the huge losers are SMOOTH steady adverse
trends (short into an uptrend) — at -10/-15 the trend is already established and the confirmation
fires; the dip-recovery winners are CHOPPY at -10/-15 and the confirmation says no. So arming early
+ confirming captures the trend most of the way instead of eating -90 first.

Confirmation features at the arm cell (all causal, <= arm cell):
  t_arm       cells to reach -X_arm (fast = strong trend)
  eff_arm     in-leg trend efficiency |disp|/pathlen over [entry, arm] (smooth = trend/death)
  mom_arm     recent 60c momentum at the arm (accelerating adverse = trend)
  run         pre-entry side-adjusted move faded (freight-train context)
  coeff_dir   entry-coeff win-long/win-short direction projection (sol/eth/btc; "verified by coeff")
Classifier (per-week OOS) -> P(death); FIRE flip when P >= cutoff.
FLIP pnl = -(gross - r_arm) - FC (reverse at the arm cell, ride to the natural exit; taker cross).

Usage:  python scripts/_s62_armed_flip.py [--xarm 10]
"""
from __future__ import annotations

import argparse
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
BINS = "/tmp/backfill"; CACHE = "/tmp/s62cache"
CELLS = [("sol", "SOLUSDT", 100.0), ("eth", "ETHUSDT", 80.0), ("btc", "BTCUSDT", 80.0),
         ("xrp", "XRPUSDT", 80.0), ("doge", "DOGEUSDT", 100.0)]


def coeff_dir_map(coin):
    """entry-coeff win-long/win-short direction score per entry cell (if the coeff cache exists)."""
    p = f"{CACHE}/{coin}_coefs.npz"
    if not os.path.exists(p):
        return None
    import gzip
    import json
    z = np.load(p); C = z["coefs"]; ecell = z["ecell"]; side = z["side"]
    d = json.load(gzip.open("fingerprint_dataset/coeffs/coeff_index.json.gz"))["by_source_id"]
    if coin not in ("btc", "eth"):        # only btc/eth have git centroids -> re-derive from current wins
        gr = z["gross"]; wl = C[(side > 0) & (gr > 0)]; ws = C[(side < 0) & (gr > 0)]
        if len(wl) < 10 or len(ws) < 10:
            return None
        cwl, cws = wl.mean(0), ws.mean(0)
    else:
        def cf(cell, lab):
            return np.array([r["coef"] for r in d.values() if r["cell"] == cell
                             and r["label"] == lab and r["lineage"] in ("cand_sp", "onset", "cs2000_clean")], float)
        cwl = cf(f"{coin}_coinbase_buy", "win").mean(0); cws = cf(f"{coin}_coinbase_sell", "win").mean(0)
    cm = (cwl + cws) / 2; axis = (cwl - cws) / (np.linalg.norm(cwl - cws) + 1e-9)
    score = (C - cm) @ axis
    return {int(c): float(s) for c, s in zip(ecell, score)}


CROSS = {"sol": "BTCUSDT", "eth": "BTCUSDT", "btc": "ETHUSDT", "xrp": "BTCUSDT", "doge": "BTCUSDT"}


def build(coin, sym, th, xarm):
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    b = np.asarray(b, float); s = np.asarray(s, float)
    mc, bc, sc, *_ = load_bins(f"{BINS}/{CROSS[coin]}_30d_bins.json")
    bc = np.asarray(bc, float); sc = np.asarray(sc, float)
    n = min(len(m), len(bc))
    cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(lm)))])
    Bo = np.concatenate([[0.0], np.cumsum(b)]); So = np.concatenate([[0.0], np.cumsum(s)])
    Bx = np.concatenate([[0.0], np.cumsum(bc)]); Sx = np.concatenate([[0.0], np.cumsum(sc)])
    cdir = coeff_dir_map(coin)
    fl = armed_midband_flips(m, th, 0.5)
    X, gross, r_arm, ec, armed = [], [], [], [], 0
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < 1802 or xi >= n:
            continue
        r = side * (lm[ci:xi + 1] - lm[ci]) * 1e4
        und = np.where(r <= -xarm)[0]
        g = float(r[-1])
        if len(und) == 0:                 # never armed -> HOLD
            X.append(None); gross.append(g); r_arm.append(None); ec.append(ci); continue
        aj = ci + int(und[0]); ra = float(r[int(und[0])]); t_arm = int(und[0])
        pl = cpath[aj] - cpath[ci]; eff = abs(lm[aj] - lm[ci]) / pl if pl > 0 else 0.0
        mom = side * (lm[aj] - lm[max(ci, aj - 60)]) * 1e4
        run = -side * (lm[ci] - lm[ci - 600]) * 1e4
        cd = cdir.get(ci, 0.0) if cdir else 0.0
        # DIPOLE "strong trade" signal at the arm: adverse taker-flow lean [entry, arm] (own + cross-major).
        # high = flow is driving HARD against our position = a real strong trend -> confirm the flip.
        Bwin = Bo[aj + 1] - Bo[ci]; Swin = So[aj + 1] - So[ci]
        own_adv = -side * (Bwin - Swin) / (Bwin + Swin + 1e-9)
        Bxw = Bx[aj + 1] - Bx[ci]; Sxw = Sx[aj + 1] - Sx[ci]
        xmaj_adv = -side * (Bxw - Sxw) / (Bxw + Sxw + 1e-9)
        armed += 1
        X.append([t_arm, eff, mom, run, cd, own_adv, xmaj_adv]); gross.append(g); r_arm.append(ra); ec.append(ci)
    return X, np.array(gross), r_arm, np.array(ec), armed, hrs


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--xarm", type=float, default=10.0)
    args = ap.parse_args()
    print(f"ARMED FLIP  (arm at first -{args.xarm:.0f}bp, fire flip when confirmed)  fee=0, flip=22bp taker")
    print(f"{'coin':5}{'armed':>7}{'AUC':>7}{'base':>8}{'armflip':>9}{'Δ':>7}  per-week Δ")
    for coin, sym, th in CELLS:
        X, gross, r_arm, ec, armed, hrs = build(coin, sym, th, args.xarm)
        armd = np.array([x is not None for x in X])
        death = gross <= -40; week = (ec // WK).astype(int)
        Xa = np.array([x for x in X if x is not None]); ya = death[armd].astype(int)
        wa = week[armd]; pred_a = np.full(armd.sum(), np.nan)
        for w in sorted(set(wa)):
            tr = wa != w; te = wa == w
            if tr.sum() < 40 or len(np.unique(ya[tr])) < 2:
                continue
            c = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.05,
                                               l2_regularization=2.0).fit(Xa[tr], ya[tr])
            pred_a[te] = c.predict_proba(Xa[te])[:, 1]
        okp = ~np.isnan(pred_a); auc = roc_auc_score(ya[okp], pred_a[okp]) if len(np.unique(ya[okp])) > 1 else float("nan")
        # map predictions back to all legs; fire flip on confirmed armed legs
        pred_full = np.full(len(gross), np.nan); pred_full[np.where(armd)[0][okp]] = pred_a[okp]
        r_arm_full = np.array([ra if ra is not None else 0.0 for ra in r_arm])
        base = np.sum(CAP * gross / 1e4) / hrs
        thr = np.nanpercentile(pred_full[~np.isnan(pred_full)], 70)
        fire = ~np.isnan(pred_full) & (pred_full >= thr)
        pnl = np.where(fire, -(gross - r_arm_full) - FC, gross)
        tot = np.sum(CAP * pnl / 1e4) / hrs
        pw = []
        for w in sorted(set(week)):
            mk = week == w; hh = (np.ptp(ec[mk]) + 1) / 3600.0 if mk.sum() else 1
            pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
        print(f"{coin:5}{armed:>7}{auc:>7.3f}{base:>+8.2f}{tot:>+9.2f}{tot - base:>+7.2f}  "
              + " ".join(f"{x:+.1f}" for x in pw) + f"  (fire {int(fire.sum())}, death {int((fire & death).sum())})")


if __name__ == "__main__":
    main()
