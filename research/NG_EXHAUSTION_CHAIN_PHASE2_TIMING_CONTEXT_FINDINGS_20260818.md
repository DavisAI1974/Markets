# NG Exhaustion Chain Phase 2 — Timing Families and True/False Context Decomposition — 2026-08-18

Status: **EXPLORATORY PHASE-2 CHARACTERIZATION; NO NEW PLAY FROZEN.**

This pass continues the recurrence atlas without changing the frozen detector, canonical rows, frozen SSOS paper play, runway clock, permanent Frankie, Frankie 1, or `research/kalshi/spawn.py`.

## 1. Exact-D2 elapsed time separates into reproducible short / middle / long families

The strict all-model Phase-1 lineage instances were grouped only by their observed origin-to-terminal elapsed time. A Gaussian mixture was fit on log elapsed time for the **pre-held exact-D2 population** and the held week was then assigned to those frozen pre-held components.

For exact D2, one- and two-component fits are materially worse than three components (`BIC 2135.4 / 1468.1 / 1361.6`). The three empirical centers are approximately:

- short: `126.25s`;
- middle: `215.19s`;
- long tail: `797.96s` (~13.3 minutes).

Pre-held exact-D2 assignments: 947 / 380 / 52, or about **68.7% / 27.6% / 3.8%**.

Held exact-D2 assignments using the pre-held model: 156 / 52 / 5, or about **73.2% / 24.4% / 2.35%**.

The held proportions are close enough to support a real short/middle/long timing-family interpretation. These are characterization families, not executable timing cutoffs.

## 2. Exact-D3 also has a short body and a longer tail

For exact D3, a two-component log-time model gives centers near `210.5s` and `609.3s`.

- pre-held: 83 short / 10 long (89.2% / 10.8%);
- held under the pre-held model: 25 short / 6 long (80.6% / 19.4%).

A three-component model has only a marginally better BIC and mainly isolates the single pre-held 3,800-second D3 observation. The simpler two-family interpretation is therefore preferred for characterization.

D4/D5 remain too sparse for a defensible timing-family model.

## 3. The timing family is more stable than the exact module composition

Within pre-held exact-D2 chains, the pair modules feeding each timing family differ.

### Short ~126s family

Examples enriched versus the overall exact-D2 pair mix include:

- `XS|F` ~1.38x;
- `SX|S` ~1.37x;
- `XX|F` ~1.27x;
- `XO|F` ~1.24x.

### Middle ~215s family

Examples enriched include:

- `PP|F` ~1.99x;
- `XP|S` ~1.87x;
- `PX|F` ~1.60x;
- `XP|F` ~1.50x;
- `PP|S` ~1.23x.

### Rare ~798s long tail

The pre-held long tail is especially enriched for:

- `OO|S`: 9/52, ~4.97x;
- `PP|F`: 5/52, ~2.50x;
- `OS|S`: 4/52, ~2.36x;
- `OX|F`: 4/52, ~2.12x.

However, held has only five long-tail exact-D2 cases and their pair composition is different (`SO|S` twice, then `SO|F`, `SS|F`, `SX|S`).

Interpretation: the **existence and approximate share of the timing families replicates better than any one long-tail grammar**. Long-chain timing appears to be a stable family while the specific state/polarity modules populating that family can vary by regime.

## 4. `OOO -> FLIP` is a clean example of why failed folds must be decomposed

The shorter `OOO -> FLIP` motif is positive in all three pre-held aggregate blocks but negative in held. Restoring one additional predecessor shows materially different subtypes:

- `XOOO -> FLIP`: +0.104t / +0.536t / +0.273t pre-held; no held occurrence;
- `POOO -> FLIP`: +0.211t / +0.457t / +0.250t; held n=1 at -3.0t;
- `OOOO -> FLIP`: -0.180t / -0.037t / +0.456t; held n=5 at -2.0t;
- `SOOO -> FLIP`: +0.387t / ~0.000t / -0.273t; held n=7 at +0.429t.

The held failure is therefore not one homogeneous `OOO` event class. The surrounding predecessor changes the realized behavior.

## 5. Other held sign changes also break into heterogeneous contexts

### `O -> FLIP`

Adding one predecessor yields:

- `PO -> FLIP`: positive in all three pre-held blocks, held n=10 at -1.1t;
- `OO -> FLIP`: near-flat/mixed pre-held, held n=55 at +0.2t;
- `SO -> FLIP`: mixed pre-held, held n=73 at -0.808t;
- `XO -> FLIP`: mixed pre-held, held n=11 at -1.091t.

The aggregate held reversal is therefore a mixture of contexts rather than a universal failure of every O-to-flip instance.

### `P -> FLIP`

`OP`, `PP`, `SP`, and `XP` predecessor contexts do not yield one clean stable carve-out across all chronological blocks and held. This remains an investigator family.

### `SS -> SAME`

Restoring a third predecessor (`OSS`, `SSS`, `PSS`, `XSS`) also produces mixed chronological behavior. No simple third-state prefix rescues the shorter aggregate as a universal rule.

### `POX -> SAME`

The two most populated visible four-state prefixes, `PPOX -> SAME` and `OPOX -> SAME`, remain positive pre-held but negative in held. This reinforces the existing conclusion: the same-current P-O-X branch should be modeled as a timing/re-origin branch, not repaired by deleting held losses with an ad hoc predecessor filter.

## 6. Current long/short-chain interpretation

The evidence now supports two separate statements:

1. **Timing families are real.** Exact D2 and D3 contain reproducible short and longer elapsed-time populations, with a rare D2 long tail.
2. **The grammar inside a timing family is not fixed.** Reusable pair/triplet modules exist, but the modules occupying the long tail can change by era/held regime.

That combination is consistent with a rolling/re-origin state machine: there are recurrent building blocks and recurrent lifespan families, but no requirement that one immutable whole-chain template repeat identically.

## 7. Investigator policy remains unchanged

A failed held fold or sign-changing subtype is not a hard fail. The required action is:

**FLAG_AND_DECOMPOSE -> preserve true and false instances -> restore longer context -> inspect timing family -> retest out of time.**

No new recurrence or timing motif in this pass is promoted into the frozen paper-play set.
