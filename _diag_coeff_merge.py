"""_diag_coeff_merge.py — why did the per-cell coeffs nearly MERGE? + the buy/sell separation test.

Greg's instinct: the coeffs were "distinct" before but now cross-cell centroids sit at ~0.998 cosine.
Hypothesis: the DETERMINISTIC decoder = L2-normalize(mean of non-negative spectral-magnitude embeds),
so every coeff is dominated by one SHARED common direction; "distinct" (unique vector) != "separated"
(low cosine). This script decomposes the common component and re-tests separation on the RESIDUAL, then
runs the thing that actually matters: BUY vs SELL separation (coeff residual + the directional micros).
(Win vs lose is NOT testable here — the index is all winners; see the note printed at the end.)
"""
from __future__ import annotations
import gzip, json
import numpy as np
from odcore.fingerprint_predictor import assemble, MICRO_KEYS

IDX = "_alt_labels/coeffs/alt_coeff_index.json.gz"
LAB = "_alt_labels"


def _l2(v): v = np.asarray(v, float); n = np.linalg.norm(v); return v / n if n else v


def main():
    per_cell = assemble(IDX, LAB)
    cells = sorted(per_cell)
    C = {c: np.array([r["coeff"] for r in per_cell[c]], float) for c in cells}
    M = {c: np.array([r["micros"] for r in per_cell[c]], float) for c in cells}
    allC = np.vstack([C[c] for c in cells])
    g = allC.mean(0)                                  # global mean coeff (the shared component)
    print(f"cells={len(cells)}  total coeffs={len(allC)}  dim={allC.shape[1]}")

    # 1) HOW DOMINANT is the shared common direction?
    gnorm = float(np.linalg.norm(g))
    # energy of each unit coeff along g-hat vs residual
    gh = _l2(g)
    proj = allC @ gh
    common_energy = float(np.mean(proj**2))           # coeffs are unit-L2 so total energy/coeff = 1
    print(f"\n[1] shared component:  ||global_mean||={gnorm:.4f}   "
          f"mean energy along common dir={common_energy:.4f}  -> residual energy={1-common_energy:.4f}")
    print(f"    (if common_energy ~1.0, ~all of every coeff IS the shared shape; distinctiveness is the "
          f"tiny {1-common_energy:.1%} residual -> that's why raw cosine ~0.99 and centroids 'merge')")

    # 2) separation BEFORE vs AFTER removing the common component
    def centroid_cos_matrix(mats, center):
        cents = {c: _l2((mats[c] - (g if center else 0)).mean(0)) for c in cells}
        offdiag = [float(cents[a] @ cents[b]) for a in cells for b in cells if a < b]
        return float(np.mean(offdiag)), float(np.min(offdiag)), float(np.max(offdiag))
    raw = centroid_cos_matrix(C, center=False)
    cen = centroid_cos_matrix(C, center=True)
    print(f"\n[2] cross-cell centroid cosine (lower = more separated):")
    print(f"    RAW       mean={raw[0]:.3f}  range[{raw[1]:.3f},{raw[2]:.3f}]")
    print(f"    CENTERED  mean={cen[0]:.3f}  range[{cen[1]:.3f},{cen[2]:.3f}]   "
          f"(remove the shared shape -> do cells separate?)")

    # 3) within-cell vs cross-cell similarity on CENTERED coeffs (a real separation ratio)
    Cc = {c: (C[c] - g) for c in cells}
    Ccn = {c: np.array([_l2(x) for x in Cc[c]]) for c in cells}
    wi = np.mean([float(Ccn[c][i] @ Ccn[c][j]) for c in cells for i in range(len(Ccn[c]))
                  for j in range(i+1, len(Ccn[c]))])
    cross = np.mean([float(_l2(Cc[a].mean(0)) @ _l2(Cc[b].mean(0))) for a in cells for b in cells if a < b])
    print(f"\n[3] CENTERED residual: mean within-cell pair cosine={wi:.3f}  vs cross-cell centroid={cross:.3f}")

    # 4) THE ONE THAT MATTERS: BUY vs SELL separation
    print("\n[4] BUY vs SELL (what actually matters):")
    buy = np.vstack([C[c] for c in cells if c.endswith("_buy")])
    sell = np.vstack([C[c] for c in cells if c.endswith("_sell")])
    bc, sc = _l2((buy - g).mean(0)), _l2((sell - g).mean(0))
    print(f"    coeff residual buy-centroid vs sell-centroid cosine = {float(bc @ sc):+.3f}  "
          f"(near +1 = coeff can't tell side; <0 = separable)")
    # nearest-centroid LOO buy/sell on centered coeffs
    lab = np.array([0]*len(buy) + [1]*len(sell)); X = np.vstack([buy, sell]) - g
    hit = 0
    for i in range(len(X)):
        keep = np.arange(len(X)) != i
        cb = _l2(X[keep][lab[keep] == 0].mean(0)); cs = _l2(X[keep][lab[keep] == 1].mean(0))
        pred = 0 if _l2(X[i]) @ cb >= _l2(X[i]) @ cs else 1
        hit += (pred == lab[i])
    print(f"    coeff buy/sell LOO nearest-centroid accuracy = {hit/len(X):.1%}  (50% = coeff is side-blind)")
    # micros buy/sell (directional features) — per micro, mean by side + a LOO accuracy
    Mbuy = np.vstack([M[c] for c in cells if c.endswith("_buy")])
    Msell = np.vstack([M[c] for c in cells if c.endswith("_sell")])
    print("    micro means (buy vs sell):")
    for k, mb, ms in zip(MICRO_KEYS, Mbuy.mean(0), Msell.mean(0)):
        print(f"      {k:26s} buy={mb:+9.3f}  sell={ms:+9.3f}")
    Xm = np.vstack([Mbuy, Msell]); lm = np.array([0]*len(Mbuy) + [1]*len(Msell))
    mu, sd = Xm.mean(0), Xm.std(0)+1e-9; Z = (Xm-mu)/sd
    hit = 0
    for i in range(len(Z)):
        keep = np.arange(len(Z)) != i
        cb = Z[keep][lm[keep] == 0].mean(0); cs = Z[keep][lm[keep] == 1].mean(0)
        pred = 0 if np.linalg.norm(Z[i]-cb) <= np.linalg.norm(Z[i]-cs) else 1
        hit += (pred == lm[i])
    print(f"    micros buy/sell LOO nearest-centroid accuracy = {hit/len(Z):.1%}")

    print("\n[note] WIN vs LOSE is NOT testable here: the coeff index contains only WINNERS. To test it we "
          "must also discover LOSER coeffs (label losers + run _run_alt_coeffs on them), like the S34/S35 "
          "de-confound set. That's the missing half.")


if __name__ == "__main__":
    main()
