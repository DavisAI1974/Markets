"""_s63_fade.py — S63: the BUY/SELL rule = FADE the multi-hour trend (Greg's "trading opposite").

The `_s63_direction.py` sign table showed the machine's side is ~a coin flip (0.51) while a clean
sign structure exists: FOLLOWING the multi-hour trend (+sign mom) is systematically WRONG (0.43-
0.49) and FADING it (-sign mom) is RIGHT (0.52-0.57). That is "reading the move correctly but
trading the opposite side" — the fix is a sign flip: fade the N-hour trend.

This nails it per cell: for each fade horizon W, the side rule is
    pred_side = -sign(mom over W)      (mom up -> SELL, mom down -> BUY)
graded as a DIRECTION-AT-ENTRY decision (no flip fee — Greg's frame: decide buy/sell once at entry):
    pnl = pred_side * (log(mid[xi]/mid[ci])) * 1e4          [$/hr @ $5k over 720h]
Baseline = the machine's own side. Reported: direction accuracy, direct $/hr, per-week (robustness),
and a SIGN-SHUFFLE null (randomize the per-leg side sign N times -> null $/hr; the rule must beat it).
A real edge holds across a BAND of W and across weeks, not one corner (README Phase-0 discipline).

Usage:  python scripts/_s63_fade.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

CAP = 5000.0; WK = 7 * 24 * 3600
BINS = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CELLS = [("sol", "SOLUSDT", 100.0), ("eth", "ETHUSDT", 80.0), ("btc", "BTCUSDT", 80.0),
         ("xrp", "XRPUSDT", 80.0), ("doge", "DOGEUSDT", 100.0)]
FADE_W = [3600, 7200, 10800, 14400, 21600, 28800]     # 1h 2h 3h 4h 6h 8h
MAXW = 28800
N_SHUF = 500
SEED = 7


def build(sym, th):
    m, *_ = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m); n = len(m)
    fl = armed_midband_flips(m, th, 0.5)
    ci_l, d_l, side_l = [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < MAXW or ci < 1802 or xi >= n:
            continue
        ci_l.append(ci); d_l.append((lm[xi] - lm[ci]) * 1e4); side_l.append(side)
    ci = np.array(ci_l); d = np.array(d_l); mside = np.array(side_l)
    return lm, ci, d, mside, (ci // WK).astype(int)


def main():
    rng = np.random.default_rng(SEED)
    for coin, sym, th in CELLS:
        lm, ci, d, mside, week = build(sym, th)
        fwd = np.sign(d); n = len(d)
        base = np.sum(CAP * (mside * d) / 1e4) / 720.0
        macc = np.mean(mside == fwd)
        print(f"\n[{coin}]  n={n}  machine base={base:+.2f} $/hr  machine dir-acc={macc:.3f}")
        print(f"   {'fadeW':>6}{'acc':>6}{'direct$':>9}{'Δbase':>7}{'z_null':>8}{'p':>7}{'wk+':>5}"
              f"   per-week direct-Δ")
        for W in FADE_W:
            mom = np.array([(lm[i] - lm[i - W]) * 1e4 for i in ci])
            pside = -np.sign(mom); pside[pside == 0] = 1
            pnl = pside * d
            tot = np.sum(CAP * pnl / 1e4) / 720.0
            acc = np.mean(pside == fwd)
            # per-week Δ over machine baseline
            pw = []
            for w in sorted(set(week)):
                mk = week == w
                if mk.sum() < 2:
                    pw.append(0.0); continue
                hh = (np.ptp(ci[mk]) + 1) / 3600.0
                pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * (mside[mk] * d[mk]) / 1e4)) / hh)
            wk_pos = sum(1 for v in pw if v > 0)
            # sign-shuffle null: random +/-1 side per leg
            null = np.empty(N_SHUF)
            for j in range(N_SHUF):
                rs = rng.choice((-1, 1), size=n)
                null[j] = np.sum(CAP * (rs * d) / 1e4) / 720.0
            mu = null.mean(); sd = null.std() + 1e-12
            z = (tot - mu) / sd; p = (np.sum(null >= tot) + 1) / (N_SHUF + 1)
            hh = f"{W//3600}h"
            print(f"   {hh:>6}{acc:>6.3f}{tot:>+9.2f}{tot-base:>+7.2f}{z:>+8.2f}{p:>7.3f}"
                  f"{wk_pos:>3}/{len(pw)}   " + " ".join(f"{v:+.1f}" for v in pw))


if __name__ == "__main__":
    main()
