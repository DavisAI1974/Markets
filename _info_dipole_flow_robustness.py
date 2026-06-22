"""_info_dipole_flow_robustness.py — is each deploy cell's flow lift stable, or a one-config fluke?

n is capped by the 1,560 onset labels and the only onset-covering bars in git are the 1-min
test_bars (the 1-sec history for 05-22..24 is local-only; the data-branch realbins are a later
period). So re-validation here = ROBUSTNESS: does each deploy cell's lift over base rate survive
(a) different pre-entry window lengths, (b) different forward horizons, and (c) a temporal
(out-of-sample early/late onset) split? A signal that only shows at one setting is fragile.

Run: python _info_dipole_flow_robustness.py
"""
from __future__ import annotations

import bisect
import glob
import json

import numpy as np

from odcore.info_dipole import signed_flow_features, DEPLOY


def load_bars():
    bars = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp))
        a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        bars[(a, v)] = (np.array([b["ts"] for b in B]),
                        np.array([b.get("buy_vol", 0.0) for b in B]),
                        np.array([b.get("sell_vol", 0.0) for b in B]),
                        np.array([b["close"] for b in B]))
    return bars


def sample(bars, a, v, ot, feat, win_s, fwd_s):
    """(pred_sign, fwd_sign) for one onset, or None."""
    if (a, v) not in bars:
        return None
    ts, bv, sv, cl = bars[(a, v)]
    lo = bisect.bisect_left(ts, ot - win_s); hi = bisect.bisect_right(ts, ot)
    f = bisect.bisect_right(ts, ot + fwd_s)
    if f <= hi or hi == 0:
        return None
    feats = signed_flow_features(bv[lo:hi], sv[lo:hi])
    if feats is None or feats[feat] == 0:
        return None
    d = cl[f - 1] - cl[hi - 1]
    if d == 0:
        return None
    return (1 if feats[feat] > 0 else -1), (1 if d > 0 else -1)


def lift(rows):
    if len(rows) < 15:
        return None, len(rows)
    acc = 100 * np.mean([p == t for p, t in rows])
    tg = [t for _, t in rows]
    base = 100 * max(tg.count(1), tg.count(-1)) / len(tg)
    return acc - base, len(rows)


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))
    by_cell = {}
    for w in wo:
        c = f"{w['asset'].lower()}_{w['venue'].lower()}_{w['side']}"
        by_cell.setdefault(c, []).append(w)

    WINS = [1200, 1800, 2400]
    FWDS = [900, 1800, 3600]
    print("Lift over base rate (pp) across window x forward; >0 stable across the grid = robust.\n")
    for cell, (feat, base_lift, base_n) in DEPLOY.items():
        ws = sorted(by_cell.get(cell, []), key=lambda w: w["true_onset_ts_utc"])
        print(f"== {cell}  [{feat}]  (probe: lift +{base_lift}, n={base_n}) ==")
        hdr = "win/fwd"
        print(f"   {hdr:>8s}" + "".join(f"{f//60:>8d}m" for f in FWDS))
        for win in WINS:
            cells_row = []
            for fwd in FWDS:
                rows = [r for w in ws if (r := sample(bars, w['asset'].lower(), w['venue'].lower(),
                                                      w['true_onset_ts_utc'], feat, win, fwd))]
                lf, n = lift(rows)
                cells_row.append(f"{lf:+6.1f}" if lf is not None else "   n/a")
            print(f"   {win//60:>6d}m " + "".join(f"{c:>9s}" for c in cells_row))
        # temporal OOS split at the default win/fwd=1800
        rows = [r for w in ws if (r := sample(bars, w['asset'].lower(), w['venue'].lower(),
                                              w['true_onset_ts_utc'], feat, 1800, 1800))]
        if len(rows) >= 30:
            half = len(rows) // 2
            le, _ = lift(rows[:half]); ll, _ = lift(rows[half:])
            print(f"   temporal split (1800/1800): early lift={le:+.1f} (n={half})  "
                  f"late lift={ll:+.1f} (n={len(rows)-half})")
        print()


if __name__ == "__main__":
    main()
