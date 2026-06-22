"""
test_smoke.py — SMOKE test of the OD-BOOK pipeline on a single short window.

THIS IS NOT THE KILL-GATE T_TEST. It is an early plumbing + sanity read on one
short local sample: does the full path (book_state -> splits -> champion vs
challenger -> OOS R²) run end-to-end on real data, and does the OD operator at
least tie the VAR one-step? The frozen T_test (KILL_GATE.md) runs ONCE on
multi-day data — never tune off a single window (hard project rule).

Usage: python research/od_book/test_smoke.py <sample.jsonl.gz>
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import book_state          # noqa: E402
import champion            # noqa: E402
import challenger_od       # noqa: E402
import splits              # noqa: E402

KEY = ["mid_ret", "spread", "tob_imb", "depth_imb", "flow"]


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "research/od_book/sample/btc_coinbase_book_smoke.jsonl.gz"
    bs = book_state.build_state(path)
    print(f"[smoke] {bs.n} states, {len(bs.cols)} dims, dropped {bs.n_dropped}, "
          f"span {(bs.ts[-1]-bs.ts[0])/60:.1f} min" if bs.n else "[smoke] EMPTY")
    if bs.n < 200:
        print("[smoke] too few states for a meaningful read; collect longer.")
        return

    sp = splits.three_way(bs.n, 0.6, 0.2)
    Xtr, Xte = bs.X[sp.train], bs.X[sp.test]
    print(f"[smoke] train={len(sp.train)} val={len(sp.val)} test={len(sp.test)}")

    # champions
    var1 = champion.fit_var(Xtr, p=1, alpha=0.0)
    var2 = champion.fit_var(Xtr, p=2, alpha=0.0)
    ridge = champion.fit_var(Xtr, p=1, alpha=10.0)
    # challenger (OD): exact-DMD, rank by 99.9% energy
    dmd = challenger_od.fit_dmd(Xtr, rank=None, h=1, energy=0.999)
    spec = challenger_od.spectrum_summary(dmd)

    horizons = [1, 5]   # 100ms, 500ms on the 100ms grid
    print("\n[smoke] OUT-OF-SAMPLE R² vs persistence  (NOT the gated T_test)")
    idx = [bs.cols.index(k) for k in KEY]
    for h in horizons:
        print(f"\n  horizon {h} step ({h*100}ms):")
        rows = {
            "VAR(1)": champion.oos_r2(var1, Xte, h, bs.cols),
            "VAR(2)": champion.oos_r2(var2, Xte, h, bs.cols),
            "ridge ": champion.oos_r2(ridge, Xte, h, bs.cols),
            f"DMD r{spec.get('rank','?')}": champion.oos_r2(dmd, Xte, h, bs.cols),
        }
        hdr = "    %-9s " % "model" + " ".join("%10s" % k for k in KEY)
        print(hdr)
        for name, r in rows.items():
            cells = " ".join("%10.4f" % r.get(k, float("nan")) for k in KEY)
            print("    %-9s %s  (n=%d)" % (name, cells, r.get("_n", 0)))

    print("\n[smoke] DMD spectrum:", spec)
    # head-to-head one-step on mid_ret (the money component)
    r_var = champion.oos_r2(var1, Xte, 1, bs.cols).get("mid_ret", float("nan"))
    r_dmd = champion.oos_r2(dmd, Xte, 1, bs.cols).get("mid_ret", float("nan"))
    print(f"\n[smoke] mid_ret one-step: VAR(1)={r_var:+.4f}  DMD={r_dmd:+.4f}  "
          f"-> {'DMD ahead' if r_dmd > r_var else 'VAR ahead/tie'}")
    print("[smoke] reminder: one window only; informative for plumbing + early "
          "read, NOT a KILL-gate decision.")


if __name__ == "__main__":
    main()
