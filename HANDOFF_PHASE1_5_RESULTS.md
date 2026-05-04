# Markets / dipole — Phase 1.5 results: first GHA-collected ETH evaluation

**Date**: 2026-05-04
**From**: prior session (notes captured by next-agent handoff)
**To**: next agent picking up from commit `8243ca9` on `claude/new-session-o3vnm`
**Companion spec**: `HANDOFF_PHASE1_5.md` (gate definitions G / H / I)
**Companion spec**: `HANDOFF_TO_CODE_PHASE2.md` (Phase 2 trigger gate D)

This file captures the first real evaluation of the Phase 1.5 actor-aware
regime classifier against multi-hour ETH bins collected by the durable
GitHub Actions workflow. It is descriptive, not prescriptive — the spec
files above remain the source of truth for definitions.

## Collection status

- **Where**: branch `data/eth-bins`, latest commit `31cc247` ("ETH bins
  update 2026-05-04T18:39:34Z")
- **Source**: `.github/workflows/eth_collectors_durable.yml` running
  `coinbase_eth_collector.py` and `kraken_eth_collector.py` in parallel
- **Window captured**: ~5.8 hours of ETH NY-session 1-second bins on both
  Coinbase and Kraken
- **Pipeline used for evaluation**: `phase1_5_evaluator.py` (rule-based
  classifier from `HANDOFF_PHASE1_5.md` §Classifier)
- **GHA workflow continues to run** — this is a snapshot, not a final read.

## Phase 1.5 stop-gate results

Gate definitions are in `HANDOFF_PHASE1_5.md` (lines 150–166). Snapshot
status from this run:

| Gate | Coinbase ETH | Kraken ETH | Notes |
|---|---|---|---|
| **G** classifier diversity | pass | pass | ≥4 distinct regime classes; ORGANIC modal as expected |
| **H** cross-venue agreement | pass (with informative disagreement) | — | single-venue WHALEs are common — see Findings #3 |
| **I** per-regime predictive R² | **pass (first time)** | **pass (first time)** | regimes differ significantly in forward predictive R² |

`G + H + I` is the "holy grail" criterion in `HANDOFF_PHASE1_5.md` line 162
("regime decomposition adds predictive value beyond raw dipole"). This is
the first evaluation pass to clear it on either venue.

For exact per-regime R² values, look back in the previous chat log — raw
`phase1_5_evaluator.py` output was reviewed there but not persisted in
the repo.

## Key findings

### 1. Gate I passes on both venues

Forward predictive R² (chunk-level dipole vs next-chunk return) differs
significantly across regime classes on both Coinbase and Kraken. This is
the criterion in `HANDOFF_PHASE1_5.md` line 158 — meeting it means the
6-class regime decomposition is doing predictive work that raw dipole
alone does not. It also means the conditions for triggering Phase 2
autoresearch (gate D in `HANDOFF_TO_CODE_PHASE2.md`) are now testable
against a non-trivial baseline.

### 2. WHALE regimes carry a stronger mean-reversion edge than EQUILIBRIUM

WHALE_UP / WHALE_DOWN chunks show stronger mean-reversion signal than
ORGANIC_TWO_SIDED ("EQUILIBRIUM" in conversation shorthand) chunks.
Operationally this points at WHALE chunks as the right hunting ground
for an operator-form discovery pass — that's where the edge concentrates,
not in the modal organic state.

Implication for Phase 2: when `markets_autoresearch_chunk.py` is built
(see `HANDOFF_TO_CODE_PHASE2.md` §"Concrete next action when triggered"),
prioritize WHALE-class chunks for the feasibility run rather than
sampling uniformly across regime classes.

### 3. Cross-venue divergence is real and informative

Single-venue WHALE signatures are common in this corpus — i.e., a chunk
classifies as WHALE on one venue while the wall-clock-aligned chunk on
the other venue does not. This matches the design intent of feature F6
(`cross_venue_dipole_corr_lag` in `HANDOFF_PHASE1_5.md` lines 102–113),
where `peak_lag != 0` with `|peak_corr| > 0.3` was specified as the
single-venue origin signature for whale activity. The disagreement is
the signal, not noise.

### 4. Sample sizes are still thin

Per-regime n is currently around 3–5. The R² differentiation is real on
this corpus but statistically fragile. **Do not tune classifier
thresholds yet**, and do not even start the DPGMM auto-taxonomy migration
(`TODO.md` line 64 already gates that on N≥200 labeled chunks; we have
~50 across both venues). Let the durable GHA workflow keep running.

Recommended next-evaluation trigger: rerun `phase1_5_evaluator.py` once
n≥30 per regime is reached on each venue.

## What this unlocks for Phase 2

`HANDOFF_TO_CODE_PHASE2.md` gates Phase 2 on Phase 1 producing structure
*and* on having a non-trivial baseline R² to measure against (gate D:
"forward predictive R² on held-out chunks > Phase 1 dipole-trajectory
baseline by at least 50% relative"). With Gate I passing, a baseline now
exists. Concretely:

1. The feasibility run for `markets_autoresearch_chunk.py` (Phase 2 step 2)
   can be scheduled — pick a WHALE chunk for it per Finding #2.
2. The held-out evaluation set for Phase 2 step 4 should be stratified
   by regime class so per-regime R² uplift is measurable, not just
   pooled R².
3. Phase 2 should still wait for n per regime to grow — running
   autoresearch on 5 WHALE chunks won't survive any honest train/test
   split.

## What's still blocked or deferred

- **DPGMM migration** — gated on N≥200 labeled chunks (`TODO.md` line 65).
  Current corpus is well short.
- **F4 (size multimodality), F5 (inter-trade burstiness)** —
  `TODO.md` lines 69–74. Bin-level trade retention is in place (per the
  same TODO file), but multi-week corpus is needed to make the
  multimodality test meaningful.
- **Per-(asset, session_phase, day_of_week) baselines** — `TODO.md`
  line 67. Needs multi-week corpus.
- **Threshold recalibration** — premature; see Finding #4.

## Pointer for the next agent

If exact per-regime R² values, per-venue chunk counts, or the
classifier confusion matrix are needed and not present in the repo,
look back in the previous chat log. The raw `phase1_5_evaluator.py`
console output was reviewed there but only the qualitative findings
(this document) were captured in-tree.
