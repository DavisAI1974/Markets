"""_info_dipole_trend_flip.py — when does trend-following pay vs flip? (order-flow divergence)

The signed flow failed as a DIRECT direction predictor (trend artifact; see _info_dipole_flow_detrend.py).
But the better question (Greg): trend-following is itself a strategy -- WHEN does it pay and WHEN does
it flip? The info dipole answers it as an order-flow DIVERGENCE detector:

  trend (recent price drift) tends to CONTINUE when order flow CONFIRMS it (imb_level sign == drift sign),
  and tends to FLIP when flow DIVERGES (price up but sellers stepping in -- exhaustion).

Finding (committed), pooled n=1560, 1-min test_bars:
  - confirm -> 50% continuation, diverge -> 38%  => +12pp edge (the static imb_level/C_signed; the
    differential mi_flow/imb_flow do NOT detect the flip -- divergence is a level comparison, not a rate).
  - temporally STABLE: positive in both halves (+4 early / +18 late) -- unlike the raw directional lift
    which flipped sign across halves.
  - per-cell distinct: btc_bybit_sell +56, btc_coinbase_buy +25, btc_kraken_sell +17, ... ; two cells
    invert (btc_bybit_buy -10) -- genuine per-bucket heterogeneity (keep per cell, never pool to deploy).
Maps onto the product's 5-state frame: flow-confirmed trend = CHANNELED/CASCADE continuation;
flow divergence = reversal/flip. (Validation uses post-onset bars; the signal itself is pre-entry.)

Run: python _info_dipole_trend_flip.py
"""
from __future__ import annotations

import bisect
import glob
import json

import numpy as np

from odcore.info_dipole import signed_flow_features

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


def rows(bars, ws):
    out = []
    for w in ws:
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
        pre = cl[hi - 1] - cl[lo]; fwd = cl[f - 1] - cl[hi - 1]
        if pre == 0 or fwd == 0:
            continue
        out.append((ot, np.sign(pre), np.sign(fwd), fe))
    return out


def cont(R):
    return 100 * np.mean([r[1] == r[2] for r in R]) if R else float("nan")


def split(R, detector="imb_level"):
    conf = [r for r in R if np.sign(r[3][detector]) == r[1]]
    div = [r for r in R if r[3][detector] != 0 and np.sign(r[3][detector]) != r[1]]
    return conf, div


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))
    by_cell = {}
    for w in wo:
        by_cell.setdefault(f"{w['asset'].lower()}_{w['venue'].lower()}_{w['side']}", []).append(w)

    print("Continuation = next move same sign as recent drift. Split by flow vs drift (imb_level).\n")
    print(f"{'cell':20s} {'n':>4s} {'cont%':>6s} | {'conf':>5s} {'cont%':>6s} | {'div':>5s} {'cont%':>6s} | {'edge':>5s}")
    print("-" * 78)
    for cell in sorted(by_cell):
        R = rows(bars, by_cell[cell])
        if len(R) < 30:
            continue
        conf, div = split(R)
        print(f"{cell:20s} {len(R):>4d} {cont(R):>6.0f} | {len(conf):>5d} {cont(conf):>6.0f} | "
              f"{len(div):>5d} {cont(div):>6.0f} | {cont(conf) - cont(div):>+5.0f}")

    allR = sorted(rows(bars, wo), key=lambda r: r[0])
    conf, div = split(allR)
    print("-" * 78)
    print(f"{'POOLED':20s} {len(allR):>4d} {cont(allR):>6.0f} | {len(conf):>5d} {cont(conf):>6.0f} | "
          f"{len(div):>5d} {cont(div):>6.0f} | {cont(conf) - cont(div):>+5.0f}")

    print("\nBest flip detector (pooled edge): ", end="")
    best = []
    for det in ["imb_level", "imb_flow", "mi_flow", "ent_dipole", "C_signed"]:
        c, d = split(allR, det)
        best.append((det, round(cont(c) - cont(d), 1)))
    print("  ".join(f"{d}:{e:+}" for d, e in best))

    h = len(allR) // 2
    for name, sub in [("early", allR[:h]), ("late", allR[h:])]:
        c, d = split(sub)
        print(f"  temporal {name}: edge {cont(c) - cont(d):+.0f}  (conf {cont(c):.0f}% / div {cont(d):.0f}%)")

    # graded: the edge lives on the divergence side, scaled by opposing-flow strength
    af = np.array([r[3]["imb_level"] * r[1] for r in allR])     # aligned flow
    ct = np.array([r[1] == r[2] for r in allR])
    print("\nGraded by aligned flow (imb_level*sign(drift); + confirms, - opposes):")
    edges = [-1.01, -0.5, -0.2, -0.05, 0.05, 0.2, 1.01]
    labs = ["strong DIVERGE", "mod diverge", "weak diverge", "neutral", "weak confirm", "confirm"]
    for i, lab in enumerate(labs):
        m = (af >= edges[i]) & (af < edges[i + 1])
        if m.sum():
            print(f"   {lab:16s} n={m.sum():>4d}  continuation={100*ct[m].mean():>3.0f}%  "
                  f"reversal={100-100*ct[m].mean():>3.0f}%")
    print(f"\nDIVERGENCE reversal gate (aligned <= -0.2): "
          f"pooled reversal={100-100*ct[af <= -0.2].mean():.0f}% (n={int((af <= -0.2).sum())}); "
          f"per-cell reversal (n>=15):")
    for cell in sorted(by_cell):
        R = rows(bars, by_cell[cell])
        a = np.array([r[3]["imb_level"] * r[1] for r in R]); c2 = np.array([r[1] == r[2] for r in R])
        msk = a <= -0.2
        if msk.sum() >= 15:
            print(f"   {cell:20s} reversal={100-100*c2[msk].mean():>3.0f}%  (n={int(msk.sum())})")


if __name__ == "__main__":
    main()
