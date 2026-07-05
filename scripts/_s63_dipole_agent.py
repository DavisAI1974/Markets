"""_s63_dipole_agent.py — JOB 2: the DIPOLE/TREND agent as a BUY/SELL signal that flips big losers.

Greg: (1) find a good buy/sell signal that turns big losers into winners; (2) spin the dipole/trend
agent (kickoff Job 2 — dipole at the 1h scale + momentum + S36 divergence). Same question: a direction
read good enough that the trades that WOULD be big losers get the right side.

At each base-detector leg entry ci, absolute-frame features (predict fwd UP/DOWN, causal, 1h scale):
  momentum: mom over 600 / 3600 / 14400 s
  S36 dipole (odcore.info_dipole, 1h pre-entry flow window):
    imb_level (flow lean), aligned_flow (flow vs 1h price drift), exhausting, ent_dipole, mi_flow
Target y = sign(fwd move over the leg). Per-week OOS HistGBM -> pred_side.

Reports, per coin:
  overall dir-acc (agent) vs machine ~0.51 vs pure-fade(-sign mom1h)
  BIG-LOSER FLIP RATE: of the base machine's big losers (gross<=-40), what % does the agent's side
    get RIGHT (= would turn winner)? vs fade. THIS is Greg's question.
  $/hr taking the agent's side on every leg (direct, 0bp), vs base.

Usage:  python scripts/_s63_dipole_agent.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.info_dipole import signed_flow_features, divergence       # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier           # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1; WK = 7 * 24 * 3600; H1 = 3600
KTAPE = "/tmp/kraken_backfill"
CELLS = [("eth", "ETHUSD"), ("btc", "XBTUSD"), ("sol", "SOLUSD"),
         ("xrp", "XRPUSD"), ("doge", "XDGUSD")]
BIGLOSS = -40.0


def build(path):
    mid, buy, sell, cover, hrs = load_bins(path)
    mid = np.asarray(mid, float); lm = np.log(mid)
    buy = np.asarray(buy, float); sell = np.asarray(sell, float); n = len(mid)
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    X, y, gross, mside, mom1h, ec = [], [], [], [], [], []
    for k in range(len(flips) - 1):
        ci, _pv, side = flips[k]; nci = flips[k + 1][0]; ci = int(ci); nci = int(nci); side = int(side)
        if nci <= ci or ci < 14400 or ci < 1802 or nci >= n:
            continue
        d = (lm[nci] - lm[ci]) * 1e4
        m600 = (lm[ci] - lm[ci - 600]) * 1e4
        m1h = (lm[ci] - lm[ci - 3600]) * 1e4
        m4h = (lm[ci] - lm[ci - 14400]) * 1e4
        bw = buy[ci - H1:ci]; sw = sell[ci - H1:ci]
        ff = signed_flow_features(bw, sw)
        dv = divergence(bw, sw, m1h)
        imb = ff["imb_level"] if ff else 0.0
        ent = ff["ent_dipole"] if ff else 0.0
        mif = ff["mi_flow"] if ff else 0.0
        aln = dv["aligned_flow"] if dv else 0.0
        exh = 1.0 if (dv and dv["exhausting"]) else 0.0
        X.append([m600, m1h, m4h, imb, aln, exh, ent, mif])
        y.append(1 if d > 0 else 0); gross.append(side * d); mside.append(side)
        mom1h.append(m1h); ec.append(ci)
    return (np.array(X), np.array(y), np.array(gross), np.array(mside),
            np.array(mom1h), np.array(ec), (np.array(ec) // WK).astype(int))


def main():
    print("=== JOB 2: DIPOLE/TREND agent as a BUY/SELL signal — does it flip the big losers? ===")
    print(f"{'coin':5}{'n':>6}{'mAcc':>6}{'AUC':>6}{'agAcc':>7}{'fadeAcc':>8} | "
          f"{'BIGLOSERS':>9}{'ag flip%':>9}{'fade flip%':>11} | {'base$/h':>8}{'ag$/h':>7}")
    for coin, pair in CELLS:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            print(f"{coin:5}  (tape not present)"); continue
        X, y, gross, mside, mom1h, ec, week = build(path)
        if len(y) < 100:
            print(f"{coin:5}  too few legs ({len(y)})"); continue
        fwd = np.where(y > 0, 1, -1)
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
        ag = np.where(pred >= 0.5, 1, -1)
        fade = -np.sign(mom1h); fade[fade == 0] = 1
        macc = np.mean(mside[ok] == fwd[ok])
        agacc = np.mean(ag[ok] == fwd[ok])
        fdacc = np.mean(fade[ok] == fwd[ok])
        big = ok & (gross <= BIGLOSS)                       # base machine's big losers
        nb = int(big.sum())
        ag_flip = 100 * np.mean(ag[big] == fwd[big]) if nb else 0.0     # agent gets loser's side right
        fd_flip = 100 * np.mean(fade[big] == fwd[big]) if nb else 0.0
        base_dph = np.sum(CAP * gross[ok] / 1e4) / 720.0
        ag_dph = np.sum(CAP * (ag[ok] * np.sign(gross[ok]) * np.abs(gross[ok])) / 1e4) / 720.0  # placeholder
        # proper agent $/hr: pred_side * fwd_move; fwd_move magnitude = |gross| (side-independent)
        fwd_move = np.abs(gross)  # |move| over the leg
        ag_dph = np.sum(CAP * (ag[ok] * fwd[ok] * fwd_move[ok]) / 1e4) / 720.0
        print(f"{coin:5}{int(ok.sum()):>6}{macc:>6.3f}{auc:>6.3f}{agacc:>7.3f}{fdacc:>8.3f} | "
              f"{nb:>9}{ag_flip:>8.0f}%{fd_flip:>10.0f}% | {base_dph:>+8.2f}{ag_dph:>+7.2f}")
    print("\n  ag flip% = of base big losers, how many the agent's side gets RIGHT (turns winner).")
    print("  50% = coin flip. Need >>50 to 'turn big losers into winners' at entry.")


if __name__ == "__main__":
    main()
