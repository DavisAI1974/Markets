# S62 — Dipole-Paper Features on BTC/ETH Mid-Band Entry Legs

**Source framework:** `docs/DIPOLE_PAPER_S60.md` (D1–D8 + M1). **Job:** score each mid-band entry
leg (armed_midband_flips, theta=80bp, c=0.5) as big-loser (gross ≤ −40bp) vs winner (gross > 0),
strictly causal at the entry cell, to drive an ENTRY-FLIP. Per-cell, never pooled across coins.
Nulls on every claim (label-perm for AUC, circular-shift for $/hr). $/hr leads; bp = diagnostics.

**Legs:** BTC 671 (200 big-losers, 338 winners); ETH 1026 (302, 536). 720h each, 5 weeks.
**Cache:** `/tmp/s62cache/{btc,eth}_dipole_paper.npz` — `ecell`, `feats[n,8]`, `names` (+ gross/side/exit_i/t0/hrs). Zero NaN.

## The eight features (paper operators, all causal, trailing windows ending AT the entry cell)

| name | paper op | construction (data ≤ ci only) |
|---|---|---|
| F1_lean | D4 | trailing-300s signed taker imbalance (B−S)/(B+S) — the deployed lean |
| F2_xflow_corr | INFO-040 / M1 cheap-equal | rolling 400s Pearson corr of this coin's signed flow vs the other major's — coupled vs decoupled to the market |
| F3_xret_corr | regime descriptor | rolling 400s corr of this coin's 1s log-returns vs cross-coin's |
| F4_aligned_flow | D5 divergence | lean_level · sign(300s price drift) |
| F5_exhaustion | D5 exhaustion | \|late-half lean\| − \|early-half lean\| over 300s (neg = decaying to balance) |
| F6_dMI | D1 flow dipole | MI(buy,sell) late-half − early-half over 300s (dMI/dt) |
| F7_leadlag | D6 raw cross-cov | signed argmax-lag of cc(this flow, cross flow), ±30s — does this coin lead or lag the market |
| F8_entdipole | D7 | (H_buy − H_sell)/(H_buy + H_sell), windowed histogram entropies over 300s |

## Results

### BTC  (baseline hold-all = −1.18 $/hr | entry-flip ORACLE = +15.84 $/hr | 5 weeks)

| feature | mean per-wk AUC | wk-std | pooled AUC | AUC z(perm) | LOO flip $/hr | Δ vs base | $/hr z(shift) |
|---|---|---|---|---|---|---|---|
| F1_lean | 0.520 | 0.089 | 0.541 | +1.2 | −1.87 | −0.68 | +0.1 |
| **F2_xflow_corr** | **0.542** | **0.017** | 0.539 | +1.0 | −1.77 | −0.59 | +0.3 |
| F3_xret_corr | 0.527 | 0.038 | 0.527 | +0.4 | −2.20 | −1.02 | −0.3 |
| F4_aligned_flow | 0.444 | 0.060 | 0.462 | +1.1 | −0.91 | +0.27 | +1.4 |
| F5_exhaustion | 0.447 | 0.070 | 0.469 | +0.7 | −4.01 | −2.83 | −2.8 |
| F6_dMI | 0.469 | 0.051 | 0.468 | +0.7 | −2.04 | −0.86 | −0.1 |
| F7_leadlag | 0.471 | 0.072 | 0.554 | +1.0 | −1.01 | +0.18 | +1.2 |
| F8_entdipole | 0.496 | 0.092 | 0.510 | −0.7 | −1.83 | −0.65 | +0.2 |

### ETH  (baseline hold-all = +0.56 $/hr | entry-flip ORACLE = +26.06 $/hr | 5 weeks)

| feature | mean per-wk AUC | wk-std | pooled AUC | AUC z(perm) | LOO flip $/hr | Δ vs base | $/hr z(shift) |
|---|---|---|---|---|---|---|---|
| F1_lean | 0.490 | 0.058 | 0.511 | −0.4 | −0.82 | −1.38 | −0.4 |
| F2_xflow_corr | 0.477 | 0.018 | 0.484 | −0.0 | −1.06 | −1.62 | −0.8 |
| F3_xret_corr | 0.463 | 0.020 | 0.474 | +0.8 | −0.09 | −0.65 | +0.6 |
| F4_aligned_flow | 0.466 | 0.045 | 0.483 | +0.0 | −0.25 | −0.81 | +0.2 |
| **F5_exhaustion** | 0.488 | 0.018 | 0.492 | −0.8 | **+0.72** | **+0.16** | **+1.7** |
| F6_dMI | 0.501 | 0.037 | 0.501 | −1.3 | −1.72 | −2.28 | −1.6 |
| F7_leadlag | 0.439 | 0.079 | 0.512 | −0.9 | −1.63 | −2.19 | −1.3 |
| F8_entdipole | 0.484 | 0.020 | 0.499 | −1.3 | −0.63 | −1.19 | −0.0 |

### Orthogonality to price (|corr| of each feature with own-coin trailing-300s price momentum)

| | F1_lean | F2_xflow_corr | F3_xret_corr | F4_aligned_flow | F5_exhaustion | F6_dMI | F7_leadlag | F8_entdipole |
|---|---|---|---|---|---|---|---|---|
| BTC | 0.583 | 0.051 | 0.087 | 0.077 | 0.027 | 0.019 | 0.012 | 0.129 |
| ETH | 0.452 | 0.072 | 0.028 | 0.035 | 0.008 | 0.061 | 0.053 | 0.176 |

## Reading (honest, stack-framed)

**No single dipole-paper feature clears its null as a standalone big-loser/winner classifier at the
entry.** Every AUC-perm z is inside ±1.3; every $/hr shift-null z is inside ±2.8 (and the two most
negative — F5/BTC, F6/ETH — are the null firing *against* a naive tail rule, not signal). This is the
**winners-invisible law reproducing at the flow tier**, exactly as the paper's Experiment 3 predicts
(coupling/timing info survives in raw covariance but a big-loser-start and a winner-dip are twins in
flow at the decision moment). The prize (BTC +15.8, ETH +26.1 $/hr entry-flip oracle) is real and the
gap to it is entirely a *classification* gap, not a mechanics gap.

**What IS worth carrying as stack ingredients — the orthogonal ones.** F2–F8 are all essentially
uncorrelated with own-coin price (|corr| ≤ 0.18); only F1 (lean) is price-coupled (0.45–0.58, by
construction). So the cross-coin coupling reads (F2, F3), the flow dipole (F6), the raw-cov lead-lag
(F7), and exhaustion (F5) are genuine *orthogonal* bets — a weak edge here would add, not overlap,
with the in-container price/coeff tier that is itself ~chance at this cut. That orthogonality is the
whole point of stacking; none of these is "dead."

**Single best stack candidate per coin:**

- **BTC → F2_xflow_corr** (the INFO-040 strength meter, cheap cross-coin signed-flow correlation).
  It is the most *consistent* weak lean of the set: mean per-week AUC 0.542 at the tightest week-std
  in the panel (0.017 — above 0.5 in every one of the 5 weeks), pooled AUC 0.539 (perm-z +1.0), and
  |price corr| 0.051. It does not pay on its own ($/hr null), but it is a stable, price-orthogonal
  regime read — "is BTC coupled to the market at entry" — the kind of low-variance descriptor the S61
  notes already flagged (rolling cross-coin corr) and the right first input to a multivariate stack.

- **ETH → F5_exhaustion** (D5, the dipole moving toward balance). The only ETH feature with a
  positive LOO Δ$/hr (+0.16) AND a positive $/hr shift-null z (+1.7), at near-perfect price
  orthogonality (0.008) and a tight week-std (0.018). Weak and null-fragile, but it is the one ETH
  read that survives its own shift null in the right direction — carry it as the exhaustion input.

**Caveat / next tier.** These are single-feature reads. The paper's own prescription (M1, the
multivariate discriminator) and the S61 carry-forward both say the separable signal, if it exists,
is in the **multivariate 128-dim OD coeff signatures + centroid dual-print (D3/D8) at the encoder
tier**, not any one flow descriptor — which is off-container (Greg's E: drive). The value of this
run is (1) the 8-feature causal cache aligned to the exact leg set, ready to concatenate into that
stack, and (2) the confirmation that F2 (BTC) and F5 (ETH) are the stable, price-orthogonal flow
ingredients to seed it with.
