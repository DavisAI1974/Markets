# Markets / dipole — Phase 2 handoff: autoresearch

**Date**: 2026-05-04
**From**: Architect (Claude)
**To**: Code
**Branch**: `davisai1974/markets @ claude/new-session-o3vnm`
**Status**: GATED on Phase 1 (HANDOFF_TO_CODE.md) producing structure. Do NOT start until Phase 1 stop gates A and B both pass.

## Scope

Same product thread as Phase 1. This document covers the autoresearch addition only.

The apr5 OD autoresearch branch (piecewise Liouvillian recovery on QD3SET-1, R²=0.999997) is structurally identical to what markets needs: it discovers the best-fitting operator per regime without being told regimes exist. Phase 2 ports that capability into the markets adapter as a second pass on top of Phase 1's dipole-trajectory output.

## Why run it at all

Three specific roles. None of them justify running before Phase 1 produces structure.

1. **Operator discovery without bias.** Phase 1 hand-specifies H_a / H_b because the dipole worked across the 4 sciences. Autoresearch removes that prior and lets the data pick. If autoresearch independently rediscovers the dipole on markets, that is a much stronger transfer claim than forcing it. If it picks a different operator family, that points at the right operator for this domain.

2. **Per-chunk operator selection.** Run autoresearch on each PELT chunk independently. The operator family selected per chunk becomes its own diagnostic. Same operator across chunks = one regime with smooth coefficient drift. Different operators across chunks = regime-switching at the operator-form level, not just coefficient level. Either answer is informative.

3. **Sanity check on the dipole.** If dipole-trajectory and autoresearch agree on chunk-level structure, confidence goes up. If they disagree, the dipole isn't the right operator for markets and we save weeks of chasing a dead lead.

## Honest limits

Flag these explicitly so we don't overcredit the result:

- **No ground truth in markets.** QD3SET-1 R²=0.999997 was the search converging on the generating equation. Markets have no clean generating equation. Success criterion has to shift from "recovered the truth" to "forward predictive R² on held-out data." Different game.
- **Overfit risk is severe.** Markets are feature-rich and autoresearch is a search procedure. It will find something that fits any chunk. Symbolic regression on financial data is a decades-old graveyard for exactly this reason.
- **Compute cost.** Per-chunk autoresearch across ~240 chunks is non-trivial. Budget unknown until one feasibility chunk runs.

## Non-negotiable guards

- **Train / test split.** Autoresearch on chunks 1 through N/2. Validate recovered operators on chunks N/2+1 through N. No exceptions.
- **Success criterion = forward predictive R² on held-out chunks**, not in-sample fit. In-sample R² of 0.99 means nothing here.
- **Complexity penalty.** Autoresearch should prefer simpler operators when fits are comparable. Bias toward the dipole's level of complexity unless something materially better shows up.
- **Feasibility chunk first.** Run autoresearch on one chunk before scaling to all 240. Measure compute cost and result quality. Only then scale.

## Phase 2 stop gates

For autoresearch to be declared productive on this thread:

- D. Forward predictive R² on held-out chunks > Phase 1 dipole-trajectory baseline by at least 50% relative
- E. Recovered operator family is stable across at least 60% of chunks (i.e., not picking a totally different operator each chunk — that's overfit)
- F. Cross-venue replication on Kraken: autoresearch picks same or related operator family on Kraken chunks during the same wall-clock window

D + E = signal candidate, run F. D + E + F = autoresearch is the right second pass for this product. Any fail = document and stay with hand-specified dipole.

## Sequencing within Phase 2

1. Wait for Phase 1 to produce coefficient trajectory across ~240 chunks with at least one PELT-boundary discontinuity passing perm-95 control.
2. Pick one chunk from the trajectory (preferably one with clear structure). Run autoresearch on it as feasibility test. Measure: wall-clock time, compute cost, in-sample R², recovered operator form.
3. If feasibility chunk completes within reasonable budget and recovers something interpretable: scale to chunks 1 through N/2 (training half).
4. Validate on chunks N/2+1 through N (test half). Compute forward predictive R².
5. If gate D passes: check operator stability across chunks (gate E).
6. If D + E pass: run on Kraken chunks during overlapping wall-clock window for cross-venue check (gate F).

## Concrete next action when triggered

Build `markets_autoresearch_chunk.py`:

1. Take a single `MarketChunk` produced by Phase 1's PELT chunker
2. Convert to the format autoresearch expects (port from apr5 branch's QD3SET-1 loader, adapt feature names)
3. Run autoresearch with complexity penalty enabled
4. Record: recovered operator (symbolic form), in-sample R², coefficients, search wall-clock, search compute cost
5. Output: JSON record per chunk with all of the above

Then build `markets_autoresearch_train_test.py` that:

1. Iterates over chunks 1 through N/2, calling the per-chunk script
2. Aggregates recovered operator forms — counts of each family, distribution of coefficients
3. Picks the modal operator family across training chunks
4. Validates that operator on chunks N/2+1 through N: forward predictive R²
5. Outputs full report with gates D and E evaluated

Cross-venue (gate F) gets its own script after D and E pass.

## Save locations

- `E:\information_layer\markets\HANDOFF_TO_CODE_PHASE2.md`
- `F:\Factory\knowledge\information_layer\markets\HANDOFF_TO_CODE_PHASE2.md`
