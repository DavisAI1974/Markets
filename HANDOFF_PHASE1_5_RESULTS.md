# Markets / dipole — Phase 1.5 results: first GHA-collected ETH evaluation

**Date**: 2026-05-04
**From**: prior session (notes captured by next-agent handoff)
**Verified by**: re-running `phase1_5_evaluator.py` against the persisted bins
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
- **Window captured**: ~5.83 hours of ETH NY-session 1-second bins on both
  Coinbase (16,609 sec-bins) and Kraken (3,876 sec-bins), wall-clock
  span 2026-05-04 12:49–18:32 UTC
- **Pipeline used for evaluation**: `phase1_5_evaluator.py` (rule-based
  classifier from `HANDOFF_PHASE1_5.md` §Classifier)
- **GHA workflow continues to run** — this is a snapshot, not a final read.

## Reproducer

The numbers below come from this exact command:

```bash
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
python phase1_5_evaluator.py --asset ETH \
    --cb-bins eth_coinbase_bins.json \
    --kr-bins eth_kraken_bins.json \
    --multi-signal-pelt \
    --report-path /tmp/eth_phase1_5_gates_report.json
```

Both bin files and the JSON report are gitignored (large/regenerable);
pull from `data/eth-bins` and re-run to verify any number below.

`--multi-signal-pelt` matters: without it the chunker produces only 2
non-EQUILIBRIUM chunks per venue and Gate I is unreachable for sample-size
reasons. The TODO already calls multi-signal PELT default-on in
`MarketChunker.chunk()`; the evaluator's CLI flag wires that through.

## Phase 1.5 stop-gate results — actual

Gate definitions are in `HANDOFF_PHASE1_5.md` (lines 150–166).

| Gate | CB-ETH | KR-ETH | Notes |
|---|---|---|---|
| **G** classifier diversity (≥4 classes, modal <70%) | **PASS** (4 classes, modal 60%) | **FAIL** (3 classes only, modal 65%) | KR misses the HERD class; needs more data |
| **H** cross-venue agreement (≥60%) | **FAIL** (51.0% over 349 minutes) | — | the 49% disagreement is informative — see Finding #3 |
| **I** per-regime forward predictive R² (≥1 regime with R²>0.05, p<0.10) | **PASS** | **PASS** | first time on either venue |

`G + H + I` together is the "holy grail" criterion (`HANDOFF_PHASE1_5.md`
line 162). **That criterion does NOT yet pass** — only Gate I clears on
both venues; Gate G clears on CB but not KR; Gate H fails. An earlier
draft of this doc overclaimed; corrected here.

### Gate I detail (lag k=1, regime-conditional dipole → next-chunk log-return)

CB-ETH:

| Regime | n | r | R² | p | significant? |
|---|---:|---:|---:|---:|:-:|
| EQUILIBRIUM_TWO_SIDED | 11 | -0.446 | 0.199 | 0.135 | no |
| WHALE_DOWN            |  3 | -0.883 | 0.780 | 0.059 | **yes** |
| DEPLETED              |  3 | -0.993 | 0.986 | 0.000 | **yes** |
| HERD_DOWN             |  2 | — | — | — | n too small |

KR-ETH:

| Regime | n | r | R² | p | significant? |
|---|---:|---:|---:|---:|:-:|
| EQUILIBRIUM_TWO_SIDED | 14 | +0.332 | 0.110 | 0.223 | no |
| WHALE_UP              |  5 | -0.831 | 0.691 | 0.010 | **yes** |
| WHALE_DOWN            |  3 | -0.993 | 0.987 | 0.000 | **yes** |

All four significant WHALE/DEPLETED rows have **negative r** — i.e. higher
mean-dipole in the chunk predicts lower next-chunk return. That's
mean-reversion, not momentum continuation, and it's much stronger than
the EQUILIBRIUM rows (which are both insignificant and split-sign across
venues).

## Key findings

### 1. Gate I clears on both venues for the first time

This is the per-regime predictive-differentiation gate, not the full
holy-grail (G+H+I) bar. It means the regime decomposition is doing
real predictive work for at least one regime per venue at the lag
tested. Necessary, not sufficient.

### 2. WHALE regimes carry the mean-reversion edge

WHALE_DOWN R² = 0.78 (CB) and 0.99 (KR); WHALE_UP R² = 0.69 (KR). All
with strongly negative r (mean reversion). Compare EQUILIBRIUM at
R² = 0.11–0.20 with insignificant p. The edge concentrates in WHALE
chunks, not the modal organic state. DEPLETED (CB only, n=3) also
shows R² = 0.99 — flag for skepticism: with n=3 a near-perfect r is
suggestive of small-sample artifact, worth re-checking once n grows.

Implication for Phase 2: when `markets_autoresearch_chunk.py` is built
(see `HANDOFF_TO_CODE_PHASE2.md` §"Concrete next action when triggered"),
prioritize WHALE-class chunks for the feasibility run rather than
sampling uniformly across regime classes. Concrete pickable chunks are
listed below.

### 3. Cross-venue divergence is real and informative

Gate H fails at 51% — but the disagreement is structured, not random:

| CB regime | KR regime | minutes |
|---|---|---:|
| EQUILIBRIUM_TWO_SIDED | EQUILIBRIUM_TWO_SIDED | 166 (agree) |
| EQUILIBRIUM_TWO_SIDED | WHALE_UP              | 38 (disagree) |
| WHALE_DOWN            | EQUILIBRIUM_TWO_SIDED | 32 (disagree) |
| EQUILIBRIUM_TWO_SIDED | WHALE_DOWN            | 27 (disagree) |
| DEPLETED              | EQUILIBRIUM_TWO_SIDED | 24 (disagree) |

Whale-on-one-venue / organic-on-the-other is exactly the F6 single-venue
origin signature in the spec (`HANDOFF_PHASE1_5.md` line 113). The
disagreement carries information; it's not noise. Gate H probably needs
to be reframed as "agreement OR structured disagreement" once we have
more data, but that's a spec change, not an implementation task right
now.

F6 cross-venue confidence multiplier counts (from the same run):
12/20 CB chunks confirmed by KR (1.5×), 8 disagreement (0.5×); 11/23 KR
chunks confirmed by CB, 12 disagreement.

### 4. Sample sizes are still thin

Per-regime n is currently 3–5 outside EQUILIBRIUM. The R² differentiation
is real on this corpus but statistically fragile, especially the n=3
DEPLETED and WHALE_DOWN rows. **Do not tune classifier thresholds yet**,
and do not start the DPGMM auto-taxonomy migration (`TODO.md` already
gates that on N≥200 labeled chunks; we have ~43 across both venues).
Let the durable GHA workflow keep running.

Recommended next-evaluation trigger: rerun the reproducer once n≥30 per
non-EQUILIBRIUM regime is reached on each venue.

## Pickable WHALE chunks for Phase 2 feasibility

Generated by `phase2_chunk_picker.py --asset ETH ... --regime-filter WHALE`
against the same bins:

CB-ETH WHALE chunks (3):

| chunk idx | regime | start UTC | bars | mean_dipole | log_ret | volume |
|---:|---|---|---:|---:|---:|---:|
|  0 | WHALE_DOWN | 2026-05-04 12:49 | 19 | -0.248 | -0.00340 | 1,685 |
|  5 | WHALE_DOWN | 2026-05-04 14:03 | 14 | -0.376 | +0.00383 | 2,805 |
|  8 | WHALE_DOWN | 2026-05-04 14:48 | 30 | -0.173 | -0.00162 | 17,713 |

KR-ETH WHALE chunks (8):

| chunk idx | regime | start UTC | bars | mean_dipole | log_ret | volume |
|---:|---|---|---:|---:|---:|---:|
|  2 | WHALE_UP   | 2026-05-04 13:24 | 10 | +0.441 | +0.00131 |    20 |
|  5 | WHALE_DOWN | 2026-05-04 14:04 | 12 | -0.174 | +0.00431 |   113 |
|  6 | WHALE_UP   | 2026-05-04 14:16 | 11 | +0.309 | +0.00383 |   281 |
|  9 | WHALE_UP   | 2026-05-04 15:00 | 10 | +0.667 | -0.00118 |   986 |
| 14 | WHALE_DOWN | 2026-05-04 16:20 | 19 | -0.156 | -0.00070 |   259 |
| 15 | WHALE_UP   | 2026-05-04 16:39 | 11 | +0.163 | -0.00040 |    56 |
| 16 | WHALE_DOWN | 2026-05-04 16:50 | 19 | -0.167 | +0.00032 |   244 |
| 20 | WHALE_UP   | 2026-05-04 18:05 | 12 | +0.583 | -0.00036 |    61 |

Suggested feasibility pick: **CB-ETH chunk 8** (WHALE_DOWN, 30 bars,
17.7k volume — largest sample and largest absolute volume; gives the
autoresearch feasibility run the most signal per chunk to fit against).
Backup: **KR-ETH chunk 9** (WHALE_UP, 986 volume — large for Kraken).

## What this unlocks for Phase 2

`HANDOFF_TO_CODE_PHASE2.md` gates Phase 2 on Phase 1 producing structure
*and* on having a non-trivial baseline R² to measure against (gate D:
"forward predictive R² on held-out chunks > Phase 1 dipole-trajectory
baseline by at least 50% relative"). With Gate I passing on WHALE
classes, a per-regime baseline now exists. Concretely:

1. The feasibility run for `markets_autoresearch_chunk.py` (Phase 2
   step 2) can be scheduled on CB-ETH chunk 8 — the WHALE chunks above
   are concrete pickable inputs.
2. The Phase 2 held-out evaluation set should be **stratified by regime
   class** so per-regime R² uplift is measurable, not just pooled R²
   (which would average WHALE signal away against the EQUILIBRIUM
   majority).
3. Phase 2 should still wait for n per regime to grow before any honest
   train/test split — running autoresearch on 3 WHALE chunks won't
   survive even 50/50 split.

## What's still blocked or deferred

- **Gate G on KR-ETH** — needs HERD chunks to appear; either more data
  or threshold recalibration. Defer recalibration per Finding #4.
- **Gate H** — fails at 51%; spec change may be needed (treat structured
  single-venue disagreement as informative rather than disagreement).
  Don't change the spec until more data confirms the pattern is stable.
- **DPGMM migration** — gated on N≥200 labeled chunks (`TODO.md` line 65).
  Current corpus is well short.
- **F4 (size multimodality), F5 (inter-trade burstiness)** —
  `TODO.md` lines 69–74. Bin-level trade retention is in place, but
  multi-week corpus is needed to make the multimodality test meaningful.
- **Per-(asset, session_phase, day_of_week) baselines** — `TODO.md`
  line 67. Needs multi-week corpus.
- **Threshold recalibration** — premature; see Finding #4.

## Artifacts in this commit

- `HANDOFF_PHASE1_5_RESULTS.md` — this file
- `phase2_chunk_picker.py` — small CLI tool to list classified chunks
  with `--regime-filter` for picking Phase 2 inputs

The bin files and the JSON gate report are gitignored — pull them from
`origin/data/eth-bins` and regenerate the report with the reproducer
above.

## Pointer for the next agent

Re-run the reproducer when `data/eth-bins` advances. The expected
trajectory is: G eventually passes on KR (HERD class appears), H either
clears 60% on its own or the spec gets updated to credit structured
single-venue disagreement, I retains significance with larger n. When
n per non-EQUILIBRIUM regime reaches ~30, threshold recalibration and
DPGMM migration become tractable.
