"""
od_real_run.py — first real-data pass of the OD engine on collector bins.

Loads real bins (realbins/), builds the windowed operator matrix on a channel pair,
and reports the coupling verdict + the algebraic (chem) dipole fit. No synthetic data.

Usage:
    python scripts/od_real_run.py --source btc_coinbase --pair orderflow --limit 150000
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins, align
from odcore.operators import windowed_operator_matrix
from odcore.null_extract import analyze_coupling
from odcore.dipole_predictor import fit_algebraic_dipole

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")


def channel_pair(name: str, src, src2=None):
    """Return (a, b, label) for a named channel pair from BinSeries source(s)."""
    if name == "orderflow":
        return src.buy, src.sell, "buy_vol vs sell_vol"
    if name == "price_vol":
        return src.abs_return(), src.volume, "|return| vs volume"
    if name == "cross_venue":
        return src.log_return(), src2.log_return(), "mid-return venue A vs venue B"
    if name == "cross_asset":
        return src.log_return(), src2.log_return(), "asset A return vs asset B return"
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="btc_coinbase")
    ap.add_argument("--source2", default=None)
    ap.add_argument("--pair", default="orderflow")
    ap.add_argument("--limit", type=int, default=150000, help="seconds of bins to use")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=20)
    args = ap.parse_args()

    t = time.time()
    src = load_bins(os.path.join(REALBINS, f"{args.source}_bins.json"))
    src2 = load_bins(os.path.join(REALBINS, f"{args.source2}_bins.json")) if args.source2 else None
    if src2 is not None:
        src, src2 = align(src, src2)
    print(f"loaded {args.source} ({len(src):,} sec)"
          + (f" + {args.source2} ({len(src2):,} sec)" if src2 else "")
          + f" in {time.time()-t:.1f}s")

    a, b, label = channel_pair(args.pair, src, src2)
    if args.limit and args.limit < len(a):
        a, b = a[:args.limit], b[:args.limit]

    t = time.time()
    M = windowed_operator_matrix(a, b, window=args.window, stride=args.stride)
    print(f"operator matrix: {M.shape[0]:,} windows x 6  ({time.time()-t:.1f}s)")
    if M.shape[0] < 30:
        print("too few windows"); return

    v = analyze_coupling(M)
    fit = fit_algebraic_dipole(M)
    print(f"\n== {args.source} :: {label} ==")
    print(f"  coupling: structured={v.structured}  mi_frac={v.mi_frac:.3f}  "
          f"chem_residual_frac={v.chem_residual_frac:.3f}  eq_entropy={v.eq_entropy_frac:.3f}")
    print(f"  strength: mi_slope={v.mi_slope:.4f} (r2={v.mi_slope_r2:.3f})  "
          f"singular_gap={v.singular_gap:.4f}")
    print(f"  reason  : {v.reason}")
    print(f"  ALGEBRAIC DIPOLE  H_a^2 = {fit.a:.4f} + {fit.b:.4f}*(H_a*H_b) "
          f"+ {fit.c:.4f}*(H_a*H_b)^2   R^2={fit.r2:.3f}  (n={fit.n:,})")
    print(f"  (chem reference: a=0.007 b=-0.093 c=1.309 R^2=0.943)")


if __name__ == "__main__":
    main()
