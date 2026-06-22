"""_build_fingerprint_predictor.py — build + diagnose the per-cell DISTINCTIVE winner fingerprint (S35).

Builds each cell's winner signature (128-dim coeff + 6 micros + 5 flow) from the committed coeff index +
the winner_onsets labels, saves them, and reports DISTINCTIVENESS diagnostics — NOT win/lose separation:

  1. per-cell n + intra-cell cohesion (how tight each cell's winner coeff cloud is).
  2. cross-cell coeff-centroid cosine matrix (are the cells distinct?).
  3. leave-one-out cell IDENTIFICATION: does a held-out winner match its OWN cell best? Reported for
     coeff-only / micros-only / flow-only / STACK — this shows the tools are COMPLEMENTARY (coeff carries
     coin/venue, micros carry side; the stack is the full fingerprint). A "coin/venue-only" accuracy for
     coeff confirms the side-agnostic-coeff story (S35b).

Usage: python _build_fingerprint_predictor.py
       [--coeff-index _alt_labels/coeffs/alt_coeff_index.json.gz] [--labels-dir _alt_labels]
       [--out _alt_labels/fingerprints/cell_signatures.json.gz]
"""
from __future__ import annotations

import argparse

import numpy as np

from odcore.fingerprint_predictor import (assemble, build_signatures, _signature_from, _l2,
                                          coeff_sim, micro_sim, flow_sim, save_signatures)


def _cv(cell: str) -> str:                       # coin_venue (strip the trailing side)
    p = cell.split("_"); return "_".join(p[:-1])


def loo_identify(per_cell: dict, full_sigs: dict):
    """Leave-one-out: assign each winner to argmax-matching cell, per modality. Distinctiveness, not AUC."""
    cells = list(per_cell.keys())
    arrs = {c: {"C": np.array([r["coeff"] for r in per_cell[c]], float),
                "M": np.array([r["micros"] for r in per_cell[c]], float),
                "F": np.array([r["flow"] for r in per_cell[c]], float)} for c in cells}
    tot = {"coeff": 0, "micro": 0, "flow": 0, "stack": 0, "coeff_cv": 0, "stack_cv": 0, "n": 0}
    per = {c: dict(n=0, coeff=0, micro=0, flow=0, stack=0) for c in cells}
    for tc in cells:
        C, M, F = arrs[tc]["C"], arrs[tc]["M"], arrs[tc]["F"]
        n = len(C)
        for i in range(n):
            keep = np.arange(n) != i
            loo_sig = _signature_from(tc, C[keep], M[keep], F[keep])   # own cell minus the point
            sigs = dict(full_sigs); sigs[tc] = loo_sig                  # other cells unchanged
            co = {c: coeff_sim(s, C[i]) for c, s in sigs.items()}
            mi = {c: micro_sim(s, M[i]) for c, s in sigs.items()}
            fl = {c: flow_sim(s, F[i]) for c, s in sigs.items()}
            st = {c: co[c] + mi[c] + fl[c] for c in sigs}
            def hit(d): return max(d, key=d.get) == tc
            def hit_cv(d): return _cv(max(d, key=d.get)) == _cv(tc)
            tot["coeff"] += hit(co); tot["micro"] += hit(mi); tot["flow"] += hit(fl); tot["stack"] += hit(st)
            tot["coeff_cv"] += hit_cv(co); tot["stack_cv"] += hit_cv(st); tot["n"] += 1
            per[tc]["n"] += 1
            per[tc]["coeff"] += hit(co); per[tc]["micro"] += hit(mi)
            per[tc]["flow"] += hit(fl); per[tc]["stack"] += hit(st)
    return tot, per


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coeff-index", default="_alt_labels/coeffs/alt_coeff_index.json.gz")
    ap.add_argument("--labels-dir", default="_alt_labels")
    ap.add_argument("--out", default="_alt_labels/fingerprints/cell_signatures.json.gz")
    args = ap.parse_args()

    per_cell = assemble(args.coeff_index, args.labels_dir)
    if not per_cell:
        print("no stacked records (coeff index + winner_onsets join empty)"); return 1
    sigs = build_signatures(per_cell)
    save_signatures(sigs, args.out)
    cells = sorted(sigs)

    print(f"\n=== per-cell winner fingerprints ({len(cells)} cells) ===")
    print(f"{'cell':28s} {'n':>5s} {'cohesion':>9s}")
    for c in cells:
        print(f"{c:28s} {sigs[c].n:5d} {sigs[c].cohesion:9.3f}")

    print("\n=== cross-cell coeff-centroid cosine (distinctiveness; 1.0=identical) ===")
    print(" " * 28 + "".join(f"{c.split('_')[0]+'_'+c.split('_')[-1]:>14s}" for c in cells))
    cents = {c: np.asarray(sigs[c].coeff_centroid) for c in cells}
    for a in cells:
        row = "".join(f"{float(_l2(cents[a])@_l2(cents[b])):14.3f}" for b in cells)
        print(f"{a:28s}{row}")

    tot, per = loo_identify(per_cell, sigs)
    N = tot["n"]
    print(f"\n=== leave-one-out cell IDENTIFICATION (distinctiveness, NOT win/lose AUC); n={N} ===")
    print(f"  coeff-only      : {tot['coeff']/N:6.1%}   (coin/venue-only: {tot['coeff_cv']/N:6.1%})")
    print(f"  micros-only     : {tot['micro']/N:6.1%}")
    print(f"  flow-only       : {tot['flow']/N:6.1%}")
    print(f"  STACK (all 3)   : {tot['stack']/N:6.1%}   (coin/venue: {tot['stack_cv']/N:6.1%})")
    chance = 1.0 / len(cells)
    print(f"  (chance = {chance:.1%}; coeff is side-AGNOSTIC so it should win on coin/venue, "
          f"micros/stack should add SIDE)")

    # WHITENED coeff: standardize each of the 128 dims across ALL winners so the DISTINCTIVE dims
    # (not the common spectral profile every coeff shares) drive the per-cell signature.
    allC = np.vstack([np.array([r["coeff"] for r in per_cell[c]], float) for c in cells])
    mu, sd = allC.mean(0), allC.std(0) + 1e-9
    wper = {c: [{"coeff": ((np.array(r["coeff"]) - mu) / sd).tolist(),
                 "micros": r["micros"], "flow": r["flow"]} for r in per_cell[c]] for c in cells}
    wsigs = build_signatures(wper)
    wtot, _ = loo_identify(wper, wsigs)
    print(f"  coeff WHITENED  : {wtot['coeff']/N:6.1%}   (coin/venue-only: {wtot['coeff_cv']/N:6.1%})")
    print(f"  STACK WHITENED  : {wtot['stack']/N:6.1%}   (coin/venue: {wtot['stack_cv']/N:6.1%})")

    print("\n  per-cell STACK identification:")
    for c in cells:
        p = per[c]
        print(f"    {c:28s} stack {p['stack']/p['n']:6.1%}  coeff {p['coeff']/p['n']:6.1%}  "
              f"micro {p['micro']/p['n']:6.1%}")
    print(f"\nsaved signatures -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
