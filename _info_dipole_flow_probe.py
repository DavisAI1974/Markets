"""_info_dipole_flow_probe.py — signed information-dipole FLOW operator, evaluated PER CELL.

Motivation (S35b bleed): the 128-dim OD coeff is side-agnostic (built from price log-returns),
so buy & sell trades on the same chunk get byte-identical coeffs (385 buy<->sell groups; a
degenerate core where coeff + all 6 micros are identical yet outcomes differ). The information
dipole (davisai.ai/dipole) measures FLOW and is naturally signed (+ buy-pressure / - sell-pressure),
so it is a candidate tool to add the DIRECTION the coeff/micros lack.

This probe builds several signed flow features from the STRICTLY PRE-ENTRY order-flow window
(`buy_vol`/`sell_vol` in fingerprint_dataset/test_bars/), faithful to the paper's primitives
(discrete Shannon histogram entropy; MI = H(a)+H(b)-H(a,b); the differential dMI/dt flow form;
C = H_self/H_cross), and evaluates each PER CELL (asset x venue x side) against the forward
return sign (validation only — the signal itself uses no post-onset bars). Per
`deploy-signal-per-cell-not-universal`, we keep it on the cells where it clears a bar; partial
coverage is fine. NOTHING is averaged across cells.

Run: python _info_dipole_flow_probe.py
"""
from __future__ import annotations

import bisect
import glob
import json
from collections import defaultdict

import numpy as np

from odcore.info_dipole import signed_flow_features, FEATURES as FEATS

WIN_S = 1800          # pre-entry window (30 min, matches the coeff window)
FWD_S = 1800          # forward window for the validation target (look-ahead; validation only)


def load_bars():
    bars = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp))
        a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        bars[(a, v)] = (
            np.array([b["ts"] for b in B]),
            np.array([b.get("buy_vol", 0.0) for b in B]),
            np.array([b.get("sell_vol", 0.0) for b in B]),
            np.array([b["close"] for b in B]),
        )
    return bars


def features(bars, a, v, onset_ts):
    """Signed info-dipole flow features from the strictly pre-entry window. None if no coverage.

    Slices the order-flow window here (no look-ahead) and delegates the operator math to
    odcore.info_dipole.signed_flow_features (single source of truth, reused live)."""
    if (a, v) not in bars:
        return None
    ts, bv, sv, cl = bars[(a, v)]
    lo = bisect.bisect_left(ts, onset_ts - WIN_S)
    hi = bisect.bisect_right(ts, onset_ts)        # [onset-WIN, onset]  (strictly pre-entry)
    return signed_flow_features(bv[lo:hi], sv[lo:hi])


def fwd_sign(bars, a, v, onset_ts):
    ts, bv, sv, cl = bars[(a, v)]
    hi = bisect.bisect_right(ts, onset_ts)
    f = bisect.bisect_right(ts, onset_ts + FWD_S)
    if f <= hi or hi == 0:
        return None
    d = cl[f - 1] - cl[hi - 1]
    return 0 if d == 0 else (1 if d > 0 else -1)


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))

    # per-cell accumulation: feature sign vs forward-return sign (validation)
    # The honest metric is LIFT over the cell's base rate (majority forward sign): a side-specific
    # bucket's forward returns lean one way, so raw accuracy can be a side-bias mirage. lift>0 =
    # real directional information beyond that bias.
    per_cell = defaultdict(lambda: {f: [0, 0] for f in FEATS})   # cell -> feat -> [correct, n]
    cell_fwd = defaultdict(lambda: [0, 0])                       # cell -> [n_up, n_down]
    overall = {f: [0, 0] for f in FEATS}
    for w in wo:
        a, v = w["asset"].lower(), w["venue"].lower()
        cell = f"{a}_{v}_{w['side']}"
        ot = w.get("true_onset_ts_utc")
        fv = features(bars, a, v, ot)
        if fv is None:
            continue
        tgt = fwd_sign(bars, a, v, ot)
        if not tgt:
            continue
        cell_fwd[cell][0 if tgt > 0 else 1] += 1
        for f in FEATS:
            s = fv[f]
            if s == 0:
                continue
            ok = (1 if s > 0 else -1) == tgt
            per_cell[cell][f][0] += ok; per_cell[cell][f][1] += 1
            overall[f][0] += ok; overall[f][1] += 1

    def base_rate(cell):
        up, dn = cell_fwd[cell]
        return 100 * max(up, dn) / (up + dn) if up + dn else 0.0

    print("Directional accuracy vs forward 30-min return sign (validation; signal is pre-entry).")
    print(f"{'feature':12s} {'overall':>9s}   best per-cell LIFT over base rate (n>=20)")
    print("-" * 90)
    results = {"window_s": WIN_S, "fwd_s": FWD_S, "overall": {}, "per_cell": {}}
    for f in FEATS:
        c, n = overall[f]
        acc = 100 * c / n if n else 0
        results["overall"][f] = {"acc": round(acc, 1), "n": n}
        cells = []
        for cell, d in per_cell.items():
            cc, cn = d[f]
            if cn >= 20:
                a_ = 100 * cc / cn; b_ = base_rate(cell)
                cells.append((cell, a_, b_, a_ - b_, cn))
        cells.sort(key=lambda t: -t[3])
        top = "  ".join(f"{cell.split('_',1)[1]}:{lift:+.0f}" for cell, _, _, lift, _ in cells[:4])
        print(f"{f:12s} {acc:7.1f}% n={n:<4d}  {top}")
        results["per_cell"][f] = {cell: {"acc": round(a_, 1), "base": round(b_, 1),
                                         "lift": round(lf, 1), "n": cn}
                                  for cell, a_, b_, lf, cn in cells}

    # deploy where a signed flow feature has REAL lift (>=+5 over base, n>=40)
    print("\nDEPLOY CANDIDATES (signed flow feature lift >= +5 over base rate, n>=40):")
    hits = 0
    for cell in sorted(per_cell):
        best = max(((f, 100 * per_cell[cell][f][0] / per_cell[cell][f][1], base_rate(cell),
                     per_cell[cell][f][1]) for f in FEATS if per_cell[cell][f][1] >= 40),
                   key=lambda t: t[1] - t[2], default=None)
        if best and best[1] - best[2] >= 5:
            print(f"   {cell:22s} {best[0]:11s} acc={best[1]:.0f}% base={best[2]:.0f}% "
                  f"lift={best[1]-best[2]:+.1f}  (n={best[3]})")
            hits += 1
    if not hits:
        print("   (none with n>=40 — the small-n cells need more onsets before deploying)")
    results["deploy_criterion"] = "lift >= +5 over base rate, n >= 40"
    json.dump(results, open("_info_dipole_flow_probe_results.json", "w"), indent=2)
    print("\nwrote _info_dipole_flow_probe_results.json")


if __name__ == "__main__":
    main()
