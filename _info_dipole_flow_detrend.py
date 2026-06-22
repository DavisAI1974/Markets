"""_info_dipole_flow_detrend.py — separate REAL flow edge from trend artifact via a detrended target.

Why: on the thin 2-day test_bars window the raw forward-return sign is dominated by slow trend
(eth/bybit ran hard up then hard down; the early/late onset halves are ~97% vs ~19% up). A signed
flow that merely leans with the trend then scores a spurious full-sample "lift" purely from
base-rate blending across the two regimes (Simpson's paradox) -- the probe's apparent lifts.

The honest test removes the trend from the TARGET and asks whether the flow still predicts:
  RAW     = sign(fwd_ret)                          (trend-corrupted)
  DETREND = sign(fwd_ret - pre_onset_drift)        (vs the immediate same-length drift)
  EXCESS  = sign(fwd_ret - cell-mean fwd_ret)      (vs the cell's average move)
A feature is a TREND ARTIFACT if RAW is positive but DETREND/EXCESS collapse; it is a REAL edge
if it survives detrending. (Validation only -- the signal itself uses no post-onset bars.)

Finding (committed): only btc_kraken_sell + mi_flow (the true dMI/dt info-dipole flow) survives
(raw +7.8 / detrend +7.1 / excess +7.8, n=141); the static imb_level/C_signed collapse hardest
(pure trend); eth_bybit_buy/btc_coinbase_sell/eth_kraken_sell are trend artifacts.

Run: python _info_dipole_flow_detrend.py
"""
from __future__ import annotations

import bisect
import glob
import json

import numpy as np

from odcore.info_dipole import signed_flow_features, FEATURES

WIN_S = 1800
FWD_S = 1800


def load_bars():
    bars = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp)); a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        bars[(a, v)] = (np.array([b["ts"] for b in B]), np.array([b.get("buy_vol", 0.) for b in B]),
                        np.array([b.get("sell_vol", 0.) for b in B]), np.array([b["close"] for b in B]))
    return bars


def samples(bars, by_cell, cell):
    out = []
    for w in by_cell.get(cell, []):
        a, v = w["asset"].lower(), w["venue"].lower()
        if (a, v) not in bars:
            continue
        ts, bv, sv, cl = bars[(a, v)]; ot = w["true_onset_ts_utc"]
        lo = bisect.bisect_left(ts, ot - WIN_S); hi = bisect.bisect_right(ts, ot)
        f = bisect.bisect_right(ts, ot + FWD_S)
        if f <= hi or hi == 0 or lo >= hi:
            continue
        fe = signed_flow_features(bv[lo:hi], sv[lo:hi])
        if fe is None:
            continue
        out.append((fe, cl[f - 1] - cl[hi - 1], cl[hi - 1] - cl[lo]))   # feats, fwd_ret, pre_drift
    return out


def lift(pred, tgt):
    m = [(p, t) for p, t in zip(pred, tgt) if p != 0 and t != 0]
    if len(m) < 15:
        return None
    acc = 100 * np.mean([p == t for p, t in m]); tg = [t for _, t in m]
    base = 100 * max(tg.count(1), tg.count(-1)) / len(tg)
    return round(acc - base, 1), round(acc, 1), round(base, 1), len(m)


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))
    by_cell = {}
    for w in wo:
        by_cell.setdefault(f"{w['asset'].lower()}_{w['venue'].lower()}_{w['side']}", []).append(w)

    print("RAW=sign(fwd)  DETREND=sign(fwd-pre_drift)  EXCESS=sign(fwd-cell_mean). "
          "Real edge survives DETREND; trend artifact collapses.\n")
    for cell in sorted(by_cell):
        S = samples(bars, by_cell, cell)
        if len(S) < 40:
            continue
        fwd = np.array([s[1] for s in S]); pre = np.array([s[2] for s in S]); mfwd = fwd.mean()
        tgts = {"RAW": np.sign(fwd), "DETREND": np.sign(fwd - pre), "EXCESS": np.sign(fwd - mfwd)}
        shown = False
        for feat in FEATURES:
            pred = [1 if s[0][feat] > 0 else -1 for s in S]
            rl = {k: lift(pred, t) for k, t in tgts.items()}
            raw = rl["RAW"]
            if raw and raw[0] >= 5:                 # candidate by RAW; check if it survives
                det, exc = rl["DETREND"], rl["EXCESS"]
                survives = det and exc and det[0] > 0 and exc[0] > 0
                tag = "REAL (survives detrend)" if survives else "trend artifact"
                if not shown:
                    print(f"== {cell} (n={len(S)}, fwd%up={100*np.mean(fwd > 0):.0f}) =="); shown = True
                print(f"   {feat:11s} RAW={raw[0]:+5.1f}  DETREND={det[0] if det else None:+}  "
                      f"EXCESS={exc[0] if exc else None:+}   -> {tag}")


if __name__ == "__main__":
    main()
