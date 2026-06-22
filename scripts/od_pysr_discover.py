"""
od_pysr_discover.py — PySR symbolic discovery of the dipole/MI equations from REAL bins.

Builds the windowed operator matrix on a real channel pair, then lets PySR discover:
  (1) the algebraic dipole form   H_a^2 ~ f(H_a*H_b)
  (2) the MI functional family    MI   ~ f(H_a, H_b)
without assuming either (the Piece-1 "re-derive from raw data" step).

Usage: python scripts/od_pysr_discover.py --source btc_coinbase --pair orderflow --limit 150000
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins, align
from odcore.operators import windowed_operator_matrix
from odcore.symbolic import discover, pysr_available
from odcore.dipole_predictor import fit_algebraic_dipole
from scripts.od_real_run import channel_pair

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="btc_coinbase")
    ap.add_argument("--source2", default=None)
    ap.add_argument("--pair", default="orderflow")
    ap.add_argument("--limit", type=int, default=150000)
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=20)
    ap.add_argument("--niter", type=int, default=40)
    args = ap.parse_args()

    if not pysr_available():
        print("PySR not available; skipping symbolic discovery (use numpy fit fallback)")
        return

    src = load_bins(os.path.join(REALBINS, f"{args.source}_bins.json"))
    src2 = load_bins(os.path.join(REALBINS, f"{args.source2}_bins.json")) if args.source2 else None
    if src2 is not None:
        src, src2 = align(src, src2)
    a, b, label = channel_pair(args.pair, src, src2)
    if args.limit and args.limit < len(a):
        a, b = a[:args.limit], b[:args.limit]
    M = windowed_operator_matrix(a, b, window=args.window, stride=args.stride)
    print(f"[{args.source}:{label}] operator matrix {M.shape[0]:,} x 6")

    fit = fit_algebraic_dipole(M)
    print(f"numpy algebraic dipole: H_a^2 = {fit.a:.4f} + {fit.b:.4f}*p + {fit.c:.4f}*p^2  "
          f"R^2={fit.r2:.3f}  (p=H_a*H_b)")

    t = time.time()
    print("\n[PySR] discovering H_a^2 ~ f(H_a*H_b) ... (Julia precompiles on first fit)")
    d1 = discover(M, target="H_a^2", features=["H_a*H_b"], niterations=args.niter)
    print(f"  BEST (complexity {d1.best_complexity}, loss {d1.best_loss:.4g}): {d1.best_equation}")
    for r in d1.pareto:
        print(f"    c={r['complexity']:>2}  loss={r['loss']:.4g}  {r['equation']}")

    print("\n[PySR] discovering MI ~ f(H_a, H_b) ...")
    d2 = discover(M, target="MI", features=["H_a", "H_b"], niterations=args.niter)
    print(f"  BEST (complexity {d2.best_complexity}, loss {d2.best_loss:.4g}): {d2.best_equation}")
    for r in d2.pareto:
        print(f"    c={r['complexity']:>2}  loss={r['loss']:.4g}  {r['equation']}")
    print(f"\n[done in {time.time()-t:.0f}s]")


if __name__ == "__main__":
    main()
