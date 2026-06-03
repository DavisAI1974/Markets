"""
od_scan.py — coupling + dipole scan across many channel pairs and timescales on REAL bins.

Loads the available sources once, enumerates channel pairs (orderflow / internal /
cross-venue / cross-asset), and for each builds the windowed operator matrix on the
NORMALIZED channels, then reports the coupling verdict + algebraic-dipole fit. Ranks by
structured-coupling evidence and dipole quadratic content (the chem-dipole signature).

Usage: python scripts/od_scan.py --resample 60 --limit-min 16000 --window 40 --stride 10
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins, align
from odcore.channels import materialize, enumerate_pairs
from odcore.operators import windowed_operator_matrix
from odcore.null_extract import analyze_coupling
from odcore.dipole_predictor import fit_algebraic_dipole

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")
DEFAULT_SOURCES = ["btc_coinbase", "btc_kraken", "btc_bybit_perp", "eth_coinbase"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="*", default=DEFAULT_SOURCES)
    ap.add_argument("--resample", type=int, default=60, help="seconds per bar (60 = minute bars)")
    ap.add_argument("--limit-min", type=int, default=0, help="cap #bars after resample (0=all)")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=10)
    args = ap.parse_args()

    t = time.time()
    series = {}
    for s in args.sources:
        p = os.path.join(REALBINS, f"{s}_bins.json")
        if os.path.exists(p):
            series[s] = load_bins(p).resample(args.resample)
    print(f"loaded {len(series)} sources, resample={args.resample}s, in {time.time()-t:.1f}s")

    rows = []
    for ps in enumerate_pairs(series):
        sa, sb = series[ps.a.source], series[ps.b.source]
        if ps.a.source != ps.b.source:
            sa, sb = align(sa, sb)
        a = materialize(ps.a.source, ps.a.kind, sa)
        b = materialize(ps.b.source, ps.b.kind, sb)
        if args.limit_min and args.limit_min < len(a):
            a, b = a[:args.limit_min], b[:args.limit_min]
        M = windowed_operator_matrix(a, b, window=args.window, stride=args.stride)
        if M.shape[0] < 30:
            continue
        v = analyze_coupling(M)
        fit = fit_algebraic_dipole(M)
        quad = abs(fit.c)  # quadratic content = chem-dipole signature
        rows.append((ps, v, fit, quad))

    # rank: structured first, then chem-residual / mi-frac, then quadratic content
    rows.sort(key=lambda r: (r[1].structured, max(r[1].mi_frac, r[1].chem_residual_frac),
                             r[3]), reverse=True)
    print(f"\n{'pair':<48} {'kind':<11} struct  miF  chemF  dipR2   a       b       c")
    for ps, v, fit, quad in rows:
        print(f"{ps.name:<48} {ps.pair_kind:<11} {str(v.structured):<5} "
              f"{v.mi_frac:4.2f} {v.chem_residual_frac:4.2f}  {fit.r2:5.3f}  "
              f"{fit.a:7.3f} {fit.b:7.3f} {fit.c:7.3f}")


if __name__ == "__main__":
    main()
