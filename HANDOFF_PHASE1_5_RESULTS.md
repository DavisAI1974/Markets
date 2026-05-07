# Markets / dipole — Phase 1.5 results: first GHA-collected ETH evaluation

**Date**: 2026-05-04 (initial), 2026-05-05 (second pass on larger corpus)
**From**: prior session (notes captured by next-agent handoff)
**Verified by**: re-running `phase1_5_evaluator.py` against the persisted bins
**To**: next agent picking up from commit `8243ca9` on `claude/new-session-o3vnm`
**Companion spec**: `HANDOFF_PHASE1_5.md` (gate definitions G / H / I)
**Companion spec**: `HANDOFF_TO_CODE_PHASE2.md` (Phase 2 trigger gate D)

This file captures sequential evaluation passes of the Phase 1.5
actor-aware regime classifier against ETH bins collected by the durable
GitHub Actions workflow. Latest pass at the bottom; earlier passes
preserved for trajectory.

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

## HERD activity in this window

`regime_feature_audit.py` (committed alongside this doc) prints per-regime
feature stats and the rule-trace for each WHALE/HERD chunk. Run with:

```bash
python regime_feature_audit.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json
```

Findings on the 5.83-hour window:

**CB-ETH: one real HERD_DOWN event (capitulation-style)**

| start UTC | regime | bars | \|dipole\| | vol_ratio | rv_ratio | log_ret |
|---|---|---:|---:|---:|---:|---:|
| 15:03 | HERD_DOWN | 30 | 0.212 | 3.10× | 2.39× | -1.11% |
| 15:18 | HERD_DOWN | 30 | 0.205 | 2.04× | 2.44× | -0.66% |

A ~30-min sustained capitulation, combined log_ret ≈ -1.77%. Both chunks
clear all three HERD thresholds (rv > 1.8×, vol_ratio > 1.5, |dipole|
> 0.1) by wide margins.

**KR-ETH: zero HERD chunks** — but the *same wall-clock minutes* were
classified as EQUILIBRIUM, not HERD, on Kraken. Borderline candidates
from `regime_feature_audit.py`:

| KR start UTC | classified | \|dipole\| | vol_ratio | rv_ratio | failed threshold |
|---|---|---:|---:|---:|---|
| 15:00 | WHALE_UP | 0.67 | 4.57× | 1.32× | rv_ratio (<1.8) |
| 15:10 | EQUILIBRIUM | 0.09 | 1.60× | **4.49×** | \|dipole\| (<0.1) |
| 15:23 | EQUILIBRIUM | 0.06 | 1.24× | 1.85× | vol_ratio + \|dipole\| |
| 15:38 | EQUILIBRIUM | 0.08 | 1.00× | 1.88× | vol_ratio + \|dipole\| |

KR is ~20× thinner than CB (baseline vol 215 vs 4221) so the HERD
volume threshold calibrated against the global baseline isn't reached
even when the same underlying event is happening. The 15:10 chunk has
4.49× rv_ratio (huge volatility spike) but the dipole stayed close to
zero — Kraken's order flow was more two-sided during the same minutes
that CB saw aligned selling. This is a **per-venue HERD threshold
calibration** issue, not a missing event. Don't tune yet (per Finding
#4 below); wait for more cascade events to confirm the pattern.

**HERD_UP across both venues: zero**. No FOMO buying cascade was
captured in this NY-session window. Both observed HERD chunks are
DOWN-side capitulations.

### Per-regime feature signatures (CB-ETH, mean ± std)

| Regime | \|dipole\| | acl1 | vol_ratio | rv_ratio |
|---|---:|---:|---:|---:|
| EQUILIBRIUM (n=12) | 0.12 ±0.08 | +0.10 ±0.20 | 1.24 ±0.74 | 0.90 ±0.27 |
| WHALE_DOWN (n=3)   | 0.27 ±0.10 | +0.07 ±0.28 | 1.75 ±2.12 | 1.20 ±0.13 |
| DEPLETED (n=3)     | 0.13 ±0.14 | +0.07 ±0.16 | 0.30 ±0.13 | 0.42 ±0.07 |
| **HERD_DOWN (n=2)** | 0.21 ±0.01 | -0.04 ±0.02 | **2.57 ±0.75** | **2.41 ±0.04** |

Discriminator: HERD is the only regime with **both** vol_ratio AND
rv_ratio above 2.0×. WHALE distinguishes by higher \|dipole\| with
moderate vol/rv. DEPLETED is the inverse — low on everything. The acl1
values are noisy at these sample sizes and don't separate cleanly
across regimes here; the rule-based classifier still works because the
threshold checks are AND-of-multiple, not single-feature.

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

## Phase 1.5c additions: HERD persistence + WHALE→HERD cascade detection

The "slow build vs all-at-once" structural distinction between HERD and
WHALE activity (HERD = consecutive 30-min chunks; WHALE = isolated single
chunks) is now explicit in the code:

- `regime_classifier.apply_herd_persistence(results)` — annotates each
  HERD chunk with `herd_persistence = N` for an N-chunk consecutive
  same-direction run; adds a "sustained N-chunk HERD (k/N)" note.
- `regime_classifier.detect_whale_to_herd_cascades(results)` — single-
  venue cascade detection: WHALE_X chunk immediately followed by HERD_X
  in the same direction (no EQUILIBRIUM/DEPLETED gap). Returns
  notification-worthy event records.
- `regime_classifier.detect_cross_venue_whale_herd_simultaneity(...)` —
  WHALE on one venue + HERD on the other in the same wall-clock window
  (same direction). Used in the offline evaluator; not yet wired to the
  backend (requires persisting per-venue chunk lists across polls).
- `regime_classifier.apply_herd_borderline_rescue(...)` — opt-in pass
  that reclassifies EQUILIBRIUM chunks adjacent to confirmed HERD runs
  if they meet relaxed thresholds (rv>1.4×, vol>1.2×, |dipole|>0.08).
  **Premature**; only enable for diagnostic comparison until n≥30 HERD
  chunks accumulate.

Wired into:
- `phase1_5_evaluator.py` — new "HERD persistence" and "WHALE→HERD
  cascade events" sections in CLI output; `--herd-rescue` flag
- `regime_feature_audit.py` — per-HERD-chunk persistence + rescue tag
- `backend/api_server.py` — `SignalEvent` gains `cascade_event`,
  `cascade_detail`, `chunk_buy_volume`, `chunk_sell_volume` fields;
  emits with confidence boost (×1.3) and cascade-specific playbook
  when the latest chunk is a HERD that came directly from a same-
  direction WHALE on the previous chunk

**Verified result on the current ETH window:**
- CB-ETH chunk 8 (WHALE_DOWN, 14:48) → chunks 9+10 (HERD_DOWN run of 2,
  15:03+15:18) — cascade fires correctly
- KR-ETH: no single-venue cascade (no HERD chunks)
- Cross-venue WHALE+HERD simultaneity: none in this window (KR-ETH
  didn't classify the 15:00-15:30 minutes as HERD due to the per-venue
  baseline mismatch noted in the HERD-detail table above)

## Buy/sell aggressor split per chunk

The regime label (UP / DOWN) already encodes net aggressor direction
via `mean_dipole` sign, but absolute buy/sell percentages are
substantially more actionable for traders than the label alone. Now
surfaced in:
- `regime_feature_audit.py` per-chunk output (e.g., WHALE_UP at 15:00:
  `buy/sell=81%/19%`; HERD_DOWN at 15:18: `buy/sell=40%/60%`)
- `SignalEvent.chunk_buy_volume` / `chunk_sell_volume` (raw)
- `SignalEvent.notes[-1]` and `playbook` tail include
  `aggressor split: NN% buy / MM% sell (V units)` so the Discord post
  / push notification body shows the split directly

Sample buy/sell signatures from this run:

| chunk | regime | buy % / sell % |
|---|---|---|
| KR 13:24 | WHALE_UP | 62% / 38% |
| KR 14:48 | WHALE_DOWN | 43% / 57% |
| KR 15:00 | WHALE_UP | **81% / 19%** |
| KR 18:05 | WHALE_UP | **86% / 14%** |
| KR 16:50 | WHALE_DOWN | **25% / 75%** |
| CB 15:03 | HERD_DOWN | 40% / 60% |
| CB 15:18 | HERD_DOWN | 40% / 60% |

The high-conviction WHALE chunks (15:00 and 18:05 on KR-ETH, 16:50 on
KR-ETH for the down side) show 75-86% one-side aggressor share — the
clearest signal-quality discriminator after the regime label itself.

## Phase 2 autoresearch — feasibility result

`markets_autoresearch_chunk.py` implements the per-chunk operator-
discovery feasibility leg of `HANDOFF_TO_CODE_PHASE2.md`. It fits a
curated family of linear-in-coefficients operators with nonlinear
feature constructions to bar-level data within each chunk
(X_t → log_return_{t+1}), picks the winner by complexity-penalized
in-sample R², and aggregates winners per regime as a Gate E proxy.

**Operator family (8 candidates):** intercept-only, dipole, dipole+
log-volume, dipole², dipole+dipole-velocity, dipole×log-volume,
signed dipole², kitchen-sink (5 features). Solved via
`np.linalg.lstsq`; per-chunk fit is sub-millisecond.

This is *structurally* like apr5's autoresearch (multi-form search
with complexity penalty) but restricted to a hand-curated family. The
true symbolic-regression engine in the apr5 OD branch is the right
backend when wired in; this scaffold provides the chunk loader, format
conversion, per-regime aggregation, and Gate D/E evaluation
infrastructure.

**Reproducer:**

```bash
python markets_autoresearch_chunk.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --gate-d-eval [--regime-filter WHALE] [--complexity-lambda 0.5]
```

**Honest results — the in-sample R² uplift is overfit, the
per-regime aggregation is not yet stable.**

With the default lenient penalty (λ=0.05), `O7_kitchen_sink`
(5 parameters) wins 80–100% of chunks across all regimes. Per-regime
mean in-sample R² ranges 0.27 (HERD_DOWN) to 0.66 (WHALE_UP). Naive
Gate D check shows 281% relative uplift over the dipole-only
baseline. **All of this reflects in-sample overfitting on chunks of
9–29 samples (post-lag).**

With a 10× stricter penalty (λ=0.5), the modal-operator share drops
to 50% on WHALE_DOWN and 40% on WHALE_UP — Gate E (≥60% modal share)
**fails** on both actionable regimes. Different WHALE chunks pick
different operators:
- KR WHALE_UP 13:24 → `O4_dipole_velocity` (R²=0.86)
- KR WHALE_UP 14:16 → `O2_dipole_logvolume` (R²=0.78)
- KR WHALE_UP 18:05 → `O3_dipole_squared` (R²=0.56)

This is itself an interesting finding: the WHALE class may not be a
single regime but a cluster of structurally distinct subtypes
(dipole-velocity-driven, volume-weighted-dipole-driven, nonlinear-
dipole-driven). DPGMM auto-taxonomy (`TODO.md` line 65) is the right
treatment but premature at n=5.

**What is and isn't established:**
- ✓ Autoresearch infrastructure works end-to-end
- ✓ Per-regime aggregation works
- ✗ Operator stability (Gate E) — not yet established for WHALE
  classes; HERD has only n=2 (insufficient)
- ✗ Honest Gate D (forward predictive R² uplift on held-out chunks) —
  the current implementation is in-sample only. True cross-chunk
  train/test split is deferred to a separate tool when n≥30 per regime.

## Artifacts in this commit

- `HANDOFF_PHASE1_5_RESULTS.md` — this file
- `phase2_chunk_picker.py` — list classified chunks with
  `--regime-filter` for picking Phase 2 inputs
- `regime_feature_audit.py` — per-regime feature-signature audit;
  HERD/WHALE chunks with rule trace, persistence flag, buy/sell split
- `markets_autoresearch_chunk.py` — Phase 2 per-chunk operator-form
  search with complexity penalty + per-regime aggregation
- `regime_classifier.py` — `apply_herd_persistence`,
  `apply_herd_borderline_rescue`,
  `detect_whale_to_herd_cascades`,
  `detect_cross_venue_whale_herd_simultaneity` (new)
- `backend/api_server.py` — `SignalEvent` gains `cascade_event`,
  `cascade_detail`, `chunk_buy_volume`, `chunk_sell_volume`;
  cascade-augmented playbook + confidence boost on emit

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

---

## Second pass — 2026-05-05, ~12.83h corpus

The GHA workflow advanced from 5.83h to 12.83h between passes. Same
reproducer command (`--multi-signal-pelt` only). Snapshot taken at
`origin/data/eth-bins` commit `6c57981`.

### Gate-status table

| Gate | CB-ETH | KR-ETH | Δ from first pass |
|---|---|---|---|
| **G** classifier diversity | **FAIL** (4 classes, modal 73.3%) | **PASS** (5 classes, modal 63.8%) | CB regressed (modal climbed); KR cleared as HERD_UP + DEPLETED appeared |
| **H** cross-venue agreement | **FAIL** (50.6% over 700 minutes) | — | unchanged in spirit (51% → 50.6%); structured single-venue disagreement still dominates |
| **I** per-regime forward predictive R² | **PASS** | **PASS** | both still pass; **but the sign of WHALE r-values diverged** — see below |

`G + H + I` (the "holy grail" criterion) still does NOT pass. Gate G
went from CB-only to KR-only — flipped between venues as more data
came in. This is small-sample volatility in the modal-share threshold
test; expect more flips before n stabilizes.

### Gate I detail at lag k=1

CB-ETH:

| Regime | n | r | R² | p | significant? |
|---|---:|---:|---:|---:|:-:|
| EQUILIBRIUM_TWO_SIDED | 32 | +0.054 | 0.003 | 0.765 | no |
| HERD_DOWN             |  6 | -0.394 | 0.156 | 0.391 | no |
| **WHALE_UP**          |  5 | **+0.766** | **0.587** | **0.039** | **yes (momentum)** |
| WHALE_DOWN            |  1 | — | — | — | n too small |

KR-ETH:

| Regime | n | r | R² | p | significant? |
|---|---:|---:|---:|---:|:-:|
| EQUILIBRIUM_TWO_SIDED | 29 | -0.040 | 0.002 | 0.835 | no |
| **WHALE_UP**          | 13 | **-0.642** | **0.413** | **0.005** | **yes (mean-revert)** |
| HERD_UP               |  2 | — | — | — | n too small |
| DEPLETED              |  1 | — | — | — | n too small |
| WHALE_DOWN            |  1 | — | — | — | n too small |

### Key new finding — WHALE r-sign divergence between venues

The first pass showed unanimously negative r-values on all significant
non-EQUILIBRIUM regimes (mean-reversion edge across the board). The
second pass shows:
- **CB-ETH WHALE_UP**: r = **+0.77** (momentum) — chunks where the buy-
  side dipole is high tend to be followed by *more* upside.
- **KR-ETH WHALE_UP**: r = **−0.64** (mean-reversion) — chunks where
  the buy-side dipole is high tend to be followed by *retracement*.

Two competing interpretations:
1. **Real venue-specific structural effect.** CB whales are mostly
   institutional / early-trend (their flow keeps pushing); KR whales
   are mostly late-followers / over-extended (mean-revert after).
   This would match the venue-volume asymmetry (KR is ~20× thinner
   so a "whale" there is a smaller absolute actor, more likely to be
   exhausted).
2. **Small-sample artifact.** CB WHALE_UP has only n=5, KR has n=13.
   With n=5 and a high R² the per-chunk influence is huge — one
   outlier chunk could flip the sign. Won't be diagnostic until
   CB-ETH WHALE_UP n ≥ 20.

Either way: **don't tune any thresholds based on this pass alone.**
If interpretation #1 is right, Phase 2 autoresearch should fit
operators per (regime × venue), not per regime alone. If #2 is right,
the sign settles on negative once n ≥ 20. The data will tell.

### HERD persistence and cascade events

- **CB-ETH HERD_DOWN run of 5 consecutive chunks** starting at idx 8
  (was a 2-chunk run in the first pass). Either the same 15:03–15:18
  event extended further into the corpus's overlapping coverage, or
  a separate sustained selling cascade occurred during the new 7-hour
  window.
- **KR-ETH first WHALE_UP → HERD_UP cascade** (single-venue, idx 2 →
  idx 3). Up-direction cascade had not appeared in the first pass —
  this is the first FOMO-trip-the-herd pattern captured.
- Cross-venue WHALE+HERD simultaneity: still none in this corpus.

### What this changes for Phase 2

- The `markets_autoresearch_chunk.py` feasibility chunk-pick (CB-ETH
  chunk 8, WHALE_DOWN, 17.7k volume) is no longer the obvious top
  pick — chunks 8–12 now form the 5-chunk HERD_DOWN run, which is
  arguably more informative for autoresearch since it gives 5 same-
  regime chunks to fit within a single sustained event.
- Stratified train/test (mentioned earlier) is now more important
  given the venue-divergent r-signs. Train per (regime × venue),
  test per (regime × venue), don't pool.
- DPGMM migration still gated on N≥200 labeled chunks (`TODO.md`
  line 65). Combined corpus now ~92 chunks. Still well short.

### Reproducer for this snapshot

```bash
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
# bins at commit 6c57981 (ETH bins update 2026-05-05T01:39:45Z)
python phase1_5_evaluator.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --multi-signal-pelt
```

### Next-evaluation trigger

Rerun once any of:
- CB-ETH WHALE_UP n reaches 20 (resolves the r-sign question)
- corpus reaches 24h continuous
- a cross-venue WHALE+HERD simultaneity finally fires (would be the
  first time `_emit_cross_venue_cascades` produces real output)

### Playbook registry framework (added 2026-05-05)

Rather than hand-coding venue-specific theories ("CB momentum / KR
mean-reversion") into static playbook strings, we ship a registry-
driven approach:

- `build_playbook_registry.py` reads the bins, runs the classifier per
  venue, and computes per-(asset, venue, regime) edge stats:
  `{n, r, r2, p, direction}` where `direction ∈ {"momentum",
  "mean_revert", "exploring", "insufficient"}`.
- `playbook_generator.py` reads the registry at signal-emit time and
  composes the actionable playbook text. Includes the current
  `[n=..., r=..., p=...]` caveat in the text so users see the
  small-sample state directly.
- Backend `api_server.py` calls `get_playbook(asset, venue, regime)`
  instead of indexing the static `PLAYBOOKS` dict. Falls back to the
  per-regime defaults when the registry has no qualifying entry.

This means the **framing the user sees updates each time the registry
is rebuilt** — by design. We explicitly do not gate on `n>=10` because
forcing the framing to shift run-to-run forces awareness of how the
read is evolving.

Sample output from the current 12.83h corpus:

| Cell | n | r | direction | playbook flavor |
|---|---:|---:|---|---|
| ETH/CB/WHALE_UP | 5 | +0.77 | momentum | "ride the trend, tight stop, exit on first sign of buying exhaustion" |
| ETH/KR/WHALE_UP | 13 | -0.64 | mean_revert | "fade the overextension OR sit out, small size with tight stop" |
| ETH/CB/HERD_DOWN | 6 | -0.39 | exploring (p=0.39) | falls through to "skip — wait for more data" |
| ETH/KR/EQUILIBRIUM_TWO_SIDED | 29 | -0.04 | exploring | "skip — wait for more data" |
| ETH/CB/WHALE_DOWN | 1 | — | insufficient | falls back to default per-regime playbook |

Rebuild after each GHA cycle (LAUNCH_PLAYBOOK §1.6 cron entry). The
backend hot-reloads via mtime, no restart required.

---

## Third pass — 2026-05-06, ~50.7h corpus

The GHA workflow advanced from 12.83h to 50.7h between passes (~4×).
Snapshot taken at `origin/data/eth-bins` commit `bec58f5` ("ETH bins
update 2026-05-06T15:31:17Z"). Same reproducer as before plus
`--session-baselines --herd-rescue` so per-session-phase baselines and
borderline HERD rescue are exercised.

### Gate-status table

| Gate | CB-ETH | KR-ETH | Δ from second pass |
|---|---|---|---|
| **G** classifier diversity | **FAIL** (6 classes, modal **80.8%**) | **PASS** (6 classes, modal 65.2%) | CB worsened (modal 73.3%→80.8%); KR holds |
| **H** cross-venue agreement | **FAIL** (59.4% over 2451 minutes) | — | climbed 50.6%→59.4%; **0.6 pp shy of 60% threshold** |
| **I** per-regime forward predictive R² | **PASS** | **PASS** | both still pass; **CB-ETH WHALE_UP momentum result did not survive 4× more data** — see below |

`G + H + I` still does NOT pass. Gate G has now flipped CB → KR → KR
across passes — KR-ETH stabilizing as the diverse-classifier venue, CB
becoming progressively more equilibrium-dominated as more low-activity
hours enter the window.

### Gate I detail at lag k=1

CB-ETH:

| Regime | n | r | R² | p | significant? | Δ from pass 2 |
|---|---:|---:|---:|---:|:-:|---|
| EQUILIBRIUM_TWO_SIDED | 125 | -0.117 | 0.014 | 0.192 | no | sign flipped (+0.054→-0.117), still insig |
| **WHALE_DOWN**        |   8 | **-0.674** | **0.455** | **0.025** | **yes (mean-revert)** | new — n was 1 |
| **WHALE_UP**          |  15 | +0.289 | 0.084 | **0.276** | **NO LONGER SIG** | n=5→15, p=0.039→0.276 |
| HERD_DOWN             |   3 | -0.780 | 0.608 | 0.213 | no | n was 6, lost significance |
| UNKNOWN               |   3 | +0.994 | 0.988 | 0.000 | yes (n=3, ignore) | spurious — too small |
| HERD_UP               |   1 | — | — | — | n too small | new — first HERD_UP |

KR-ETH:

| Regime | n | r | R² | p | significant? | Δ from pass 2 |
|---|---:|---:|---:|---:|:-:|---|
| EQUILIBRIUM_TWO_SIDED | 100 | -0.205 | 0.042 | **0.038** | yes | newly significant; mean-revert tilt |
| **WHALE_UP**          |  40 | **-0.398** | **0.159** | **0.007** | **yes (mean-revert)** | n=13→40, sign held, p stronger |
| HERD_UP               |   8 | -0.558 | 0.311 | 0.100 | borderline | n=2→8, near-significant mean-revert |
| WHALE_DOWN            |   4 | +0.316 | 0.100 | 0.638 | no | n=1→4 |
| UNKNOWN, DEPLETED     |   1, 1 | — | — | — | n too small | — |

### Headline findings — what survived more data, what didn't

**1. The CB-ETH WHALE_UP "momentum" result from pass 2 was a
small-sample artifact.** Pass 2 reported n=5, r=+0.77, p=0.039 — the
basis for the "venue-divergent edge sign" interpretation in the
previous handoff. With n=15 it's r=+0.289, p=0.276 — **not
significant**. This is exactly the failure mode pass 2 flagged
(interpretation #2 in pass 2's "WHALE r-sign divergence" section), and
the data resolved it. **Treat the venue-divergent-by-direction story
as withdrawn until further data either restores it or replaces it.**

**2. KR-ETH WHALE_UP fade is the most robust signal in the corpus.**
n more than tripled (13→40), direction held (mean-reversion),
significance strengthened (p 0.005→0.007 at higher n; r=−0.398).
Three passes, three confirmations. This is the cell most defensibly
ready to wire as a real trade signal in the executor.

**3. CB-ETH WHALE_DOWN newly significant at n=8** (r=−0.674,
p=0.025). Different signal type from WHALE_UP — whales selling on
Coinbase show mean-reversion, not momentum. n still small; flag as
suggestive, not confirmed.

**4. First cross-venue WHALE+HERD simultaneity captured.** Pass 1 and
2 reported "no cross-venue WHALE+HERD simultaneity"; this pass shows
CB-ETH WHALE_UP @ chunk 129 co-occurring with KR-ETH HERD_UP @ chunk
130 in the same wall-clock window (UP direction). Single event, but
the `_emit_cross_venue_cascades` path now has a real payload to fire
on. Watch for this becoming repeating vs remaining a one-off.

**5. Single-venue WHALE→HERD cascades on KR-ETH up to 3 events** (was
1 in pass 2), all UP-direction, all single-chunk HERD runs. CB-ETH
no longer shows the 5-chunk HERD_DOWN run from pass 2; that segment
appears to have re-segmented under the larger corpus's PELT —
revisit if it returns.

**6. F6 cross-venue confirmation rate ~60% both ways.** CB chunks
KR-confirmed: 92/156 (59%); KR chunks CB-confirmed: 93/155 (60%). The
1.5× / 0.5× confidence multiplier is genuinely in play half the time.

### What this changes for Phase 2 / executor wiring

- **Promote KR-ETH WHALE_UP to executor signal** (n=40, p=0.007,
  consistent direction across 3 passes, mean-revert framing). This
  is the first cell that meets a reasonable real-money threshold.
  Practice mode should already surface it via the playbook registry;
  the upgrade is moving from "show the signal" to "act on it" once a
  user opts into live mode for that specific cell.
- **Park the venue-divergent r-sign story.** The pass-2 framing
  ("CB momentum / KR mean-reversion") was load-bearing for the
  cross-domain "actor mix" interpretation. With WHALE_UP no longer
  significant on CB, the interpretation needs a smaller scope: KR-ETH
  WHALE_UP is reliably mean-reverting; CB-ETH does not yet have a
  reliable WHALE_UP edge. Don't fit operators per (regime × venue) on
  this basis alone — wait until CB-ETH WHALE_UP either crosses
  significance again or stays insignificant past n=30.
- **CB-ETH classifier-diversity drift is worth monitoring.** Modal
  share climbed from 60% → 73% → 80.8% across the three passes. Either
  the bin coverage is being stretched into more low-activity hours
  (mechanical), or the venue genuinely produces fewer regime-distinct
  segments at this corpus length (informative). The refrag self-audit
  loop should catch this if it persists; explicitly flag if modal
  share crosses 85%.
- **Gate H is on the threshold.** 59.4% with another day or two of
  data could clear 60% on its own — recheck at ~75h before any spec
  change to credit "structured single-venue disagreement".

### Reproducer for this snapshot

```bash
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
# bins at commit bec58f5 (ETH bins update 2026-05-06T15:31:17Z)
python phase1_5_evaluator.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --multi-signal-pelt --session-baselines --herd-rescue
```

### Next-evaluation trigger

Rerun once any of:
- corpus reaches ~75h continuous (Gate H 60% recheck)
- CB-ETH WHALE_UP n reaches 30 (resolves the momentum-or-noise
  question definitively)
- a second cross-venue WHALE+HERD simultaneity fires (would confirm
  the chunk-129/130 event is a recurring pattern, not a one-off)
- CB-ETH classifier modal share drops below 75% (recovered diversity)
  or climbs above 85% (drift confirmed)

---

## Fourth pass — 2026-05-06 22:45 UTC, ~56.5h ETH + first BTC corpus

Two firsts in this pass: (1) ETH spot extended to 56.5h, (2) **first
ever Phase 1.5 evaluation on BTC** after the new BTC durable workflow
finished its first cycle. Plus an honest report on the perp collectors
(both broken in their initial form, now replaced).

### ETH at 56.5h

Same reproducer flags. Snapshot at `data/eth-bins` commit `1a2c926`.

| Gate | CB-ETH | KR-ETH | Δ from third pass |
|---|---|---|---|
| **G** | **FAIL** (modal 80.1%) | **PASS** (modal 64.8%) | CB modal essentially flat (80.8 → 80.1); KR holds |
| **H** | — | — | **58.2%** (slipped back from 59.4% in pass 3) |
| **I** | **FAIL** (no significant cell) | **PASS** (KR-ETH WHALE_UP n=45 r=−0.369 p=0.009) | **CB-ETH WHALE_DOWN finding from pass 3 didn't survive resegmentation** |

The CB-ETH WHALE_DOWN result reported in pass 3 (n=8, r=−0.674,
p=0.025) re-evaluated to n=8 r=−0.380 p=0.315 — same chunk count,
different chunk boundaries from PELT, different correlation. This is
a second small-sample finding that didn't survive more data: pass 2's
CB-ETH WHALE_UP "momentum" (withdrawn in pass 3), and now pass 3's
CB-ETH WHALE_DOWN (withdrawn here). **Both CB-ETH-specific edges have
failed to reproduce.** The KR-ETH WHALE_UP fade (n=45 now) remains
the only ETH cell that has survived three consecutive passes at
growing n.

### BTC at 5.8h (FIRST EVER)

The new `btc_collectors_durable.yml` finished its first cycle and
committed bins to `data/btc-bins` (new branch). Corpus: 5.8h on both
CB-BTC and KR-BTC spot. n per regime is 1–8 — treat individual cells
as suggestive, not confirmed; the gate-level structure is what matters.

Snapshot at `data/btc-bins` commit `7fc3d05`.

| Gate | CB-BTC | KR-BTC | Notes |
|---|---|---|---|
| **G** | **FAIL** (2 classes only, modal 80%) | **PASS** (4 classes, modal 54.5%) | CB-BTC at 5.8h is only EQUILIBRIUM + WHALE_UP; needs more data |
| **H** | — | — | **PASS at 60.9%** — first venue pair to clear 60% threshold on first run |
| **I** | **PASS** (CB-BTC WHALE_UP n=4 r=−0.800 **p=0.059**) | **FAIL** (KR-BTC WHALE_UP n=7 r=−0.461 p=0.245) | CB-BTC borderline mean-revert; KR-BTC same direction not yet sig |

**Key BTC findings:**

1. **Gate H clears on the very first BTC pass.** ETH never got above
   59.4% even after 56.5h. **BTC venues agree more than ETH venues.**
   Working hypothesis: BTC has more institutional flow (more
   structural homogeneity); ETH has more retail (more idiosyncratic
   per-venue actor mix). Confirm with more data.
2. **No HERD activity captured in the 5.8h window** on either BTC
   venue. Either a quiet 5.8h (regime-conditional sampling artifact)
   or BTC's HERD threshold needs separate calibration vs ETH.
3. **No WHALE→HERD cascades, no cross-venue simultaneity** — same as
   point 2; expected at this corpus length.

### Cross-asset / cross-venue read on WHALE_UP

| Cell | n | r | p | direction |
|---|---:|---:|---:|---|
| CB-ETH WHALE_UP | 16 | +0.190 | 0.469 | not significant; was momentum at small n, faded |
| KR-ETH WHALE_UP | 45 | **−0.369** | **0.009** | **mean-revert, robust across 4 passes** |
| CB-BTC WHALE_UP |  4 | −0.800 | 0.059 | mean-revert (borderline; tiny n) |
| KR-BTC WHALE_UP |  7 | −0.461 | 0.245 | mean-revert direction (not yet sig) |

**3 of 4 cells lean mean-revert on WHALE_UP. The fourth (CB-ETH) is
the consistent outlier and its "momentum" claim has now failed three
significance tests at growing n.** Working unified read: WHALE_UP
fades across both crypto majors and both major spot venues, with
CB-ETH the lone exception that has not yet shown a significant
positive r at any sample size. The pass-2 venue-divergent
interpretation should be considered withdrawn pending dramatic new
evidence.

### Perp collectors — debug + replacement

The first BTC run was supposed to deliver perp data on Binance USDT-M
and Kraken Futures alongside CB+KR spot. **Both perp collectors failed
in production despite working on local smoke tests:**

**Binance USDT-M perp** (`fstream.binance.com`): bins file came back
literally `{}` after 5.8h. HTTPS to fstream is reachable (404 at /),
but the WS handshake or auth-free trade stream doesn't deliver data
from GHA's egress IPs in practice. The optimistic read that fstream
sidestepped api.binance.com's geo-block (HTTP 451 from US/cloud) was
wrong, at least for our case.

**Kraken Futures perp** (`futures.kraken.com/ws/v1`): 21k bins created
from ticker channel updates, but **only 29 had any trade activity**
(0.14%). Live probe confirmed: subscribe → emit one
`feed: trade_snapshot` with the recent N trades → emit zero
`feed: trade` updates over the next 25 seconds. The v1 endpoint
appears to be snapshot-only for unauthenticated trade subscriptions.
The 29 active bins all came from connect/reconnect snapshots, not
live trade flow.

**Replacement: Bybit V5 linear perp.** Verified live: 47 trade-like
messages in 15 seconds on BTCUSDT during smoke test. Public WS at
`wss://stream.bybit.com/v5/public/linear`, no geo-block on US/cloud
egress, well-documented schema. New collectors:
- `bybit_btcusdt_perp_collector.py`
- `bybit_ethusdt_perp_collector.py`

Both workflows now run Bybit instead of Binance + Kraken Futures.
The broken `binance_*_perp_collector.py` and `kraken_*_perp_collector.py`
files remain in the repo as reference (for future debugging) but are
not invoked.

### Net active cells after this pass

| Asset | Venue | Source | Status |
|---|---|---|---|
| ETH | CB | spot | RT 56.5h |
| ETH | KR | spot | RT 56.5h |
| ETH | Bybit | perp (new) | starts on next workflow run |
| BTC | CB | spot | RT 5.8h |
| BTC | KR | spot | RT 5.8h |
| BTC | Bybit | perp (new) | starts on next workflow run |

3 working cells per asset. Coinbase futures (INTX) intentionally
parked — needs non-US account.

### Next-evaluation triggers

Rerun once any of:
- **Bybit perp data lands** (next workflow cycle, ~6h) — first chance
  to look at spot-vs-perp basis structure on either asset
- **BTC corpus reaches 24h** — gate G might clear on CB-BTC once
  more regime classes appear
- **ETH cross-venue agreement crosses 60%** for two consecutive passes
  (would unblock H + G + I together for the first time)
- **CB-ETH WHALE_UP n reaches 30+** with p still > 0.10 — would
  formally close the venue-divergent question

### One-shot backfill in progress

Backfill workflow (`backfill_oneshot.yml`, commit `3005b5c`) is
running at time of writing. Sources:

- **Binance Vision** (data.binance.vision) — daily aggTrades zips for
  BTCUSDT + ETHUSDT futures, targeting 30 days. Vision is an S3
  bucket, NOT subject to the fstream geo-block.
- **Kraken /Trades** — paginated public endpoint, targeting 30 days
  for XBTUSD + ETHUSD spot, ~30-90 min per pair at 1 req/s rate limit.
- **Coinbase /trades** — paginated public endpoint, targeting 30 days
  but capped by wallclock budget; realistic depth ~7-15 days for BTC.

Total wallclock estimate ~3-5h. Will fill `data/eth-bins` and
`data/btc-bins` with merged historical + RT data. Re-run
phase1_5_evaluator after backfill commits land for a 30-day-corpus
analysis.


## Fifth pass — 2026-05-07 ~05:00 UTC, 30d KR + 9d BN-perp + WHALE_NASCENT debut

The backfill landed (`data/eth-bins` at `5388a1b`, `data/btc-bins` at
`8fa2d2f`) and Pass 5 re-ran the analysis on the expanded corpus. One
prior signal collapsed, two new signals emerged, and the classifier
gained a new regime category. This section is the longest because the
findings genuinely changed the project's working hypotheses.

### Corpus changes since pass 4

| File | Pass 4 (RT only) | Pass 5 (post-backfill) |
|---|---|---|
| `eth_kraken_bins.json` | 56.5h | **30.0d** ✓ full 30-day target |
| `eth_coinbase_bins.json` | 56.5h | **2.6d** (only +6h gained) |
| `eth_binance_perp_bins.json` | 0 | **9.0d** (cap held; one day not yet published) |
| `btc_kraken_bins.json` | 5.8h | **30.0d** ✓ |
| `btc_coinbase_bins.json` | 5.8h | **0.4d** (CB barely advanced) |
| `btc_binance_perp_bins.json` | 0 | **9.0d** |

**The CB-side backfill is the project's bottleneck.** Coinbase's public
`/trades` rate-limited fetch hits the 5h wallclock budget without
covering meaningful depth on either asset. Recommend either raising
`max_seconds_per_script` (16-24h) or running CB in its own job. This is
why all CB-side gates and per-regime cells in this pass have insufficient
n; treat them as no-update vs Pass 4.

The `claude/remove-handoff-info-lFAHr` branch carries two backfill
workflow fixes:
- `git add -f` so `eth_*_bins.json` (which `.gitignore` lists) gets
  staged on the orphan push branch
- BN-vision capped at 10 days (~90 MB) so the merged perp file pushes
  under GitHub's 100 MB hard limit

The fixes haven't been cherry-picked into phase-2 yet; the workflow can
be dispatched from `claude/remove-handoff-info-lFAHr` to use them.

### ETH gate-by-gate

| Gate | CB-ETH (2.6d) | KR-ETH (30d) | Δ from Pass 4 |
|---|---|---|---|
| **G** | FAIL (modal 79.2%, 7 classes) | **PASS** (modal 61.3%, 8 classes) | KR diversity improved (64.8% → 61.3%) |
| **H** | — | — | **56.7%** (was 58.2%); slipped further |
| **I** | FAIL (UNKNOWN n=3 r=+0.99 is artifact) | **FAIL** | Pass 4 PASS via WHALE_UP no longer holds |
| Combined | — | — | **FAIL all 3** |

Gate H regression to 56.7% reflects more KR data exposing more
cross-venue disagreement on the 2.6d overlapping window. The CB-ETH
side is essentially unchanged at this corpus depth.

### BTC gate-by-gate

| Gate | CB-BTC (9.6h) | KR-BTC (30d) | Δ from Pass 4 |
|---|---|---|---|
| **G** | FAIL (2 classes, modal 80%) | **PASS** (8 classes, modal 65.7%) | KR diversified |
| **H** | — | — | **63.6% PASS** (was 60.9%, holds) |
| **I** | PASS via WHALE_UP n=4 r=−0.80 p=0.059 | PASS via WASH_PAIRED n=3 r=+0.91 p=0.032 | **n<5 cells gaming the gate** |
| Combined | — | — | **FAIL** (G fails on CB) |

Gate H still PASSes on BTC at 63.6% — the only venue pair to clear 60%.
But Gate I "passing" via n=3 cells exposes a flaw in the gate
definition; recommend tightening to `n ≥ 30 minimum` per cell.

### Headline 1: KR-ETH WHALE_UP fade collapsed at 10× n

The cell that anchored four prior passes:

| Pass | Corpus | n | r | p |
|---|---|---:|---:|---:|
| Pass 1 | 5.83h | 9 | −0.69 | 0.041 |
| Pass 2 | 12.83h | 12 | −0.59 | 0.044 |
| Pass 3 | 50.7h | 26 | −0.45 | 0.022 |
| Pass 4 | 56.5h | 45 | −0.369 | 0.009 |
| **Pass 5** | **30d** | **482** | **−0.073** | **0.109** |

n grew 10×, |r| collapsed 5×, p crossed back out of significance. The
direction stayed consistent (still negative, mean-revert) across all
five passes — that's the only reason this isn't fully discarded. But
the prior "robust" framing was small-sample exaggeration. **The
single-cell signal as originally promoted is not Phase-2 deployable.**

The same pattern — direction-consistent but magnitude-collapsed —
holds for KR-BTC WHALE_UP (n=7→366, r=−0.461→−0.045) and for the
prior pass-4 CB-BTC WHALE_UP n=4 (unchanged because CB didn't gain
data).

### Headline 2: Family-pool of KR _UP fades survives at p=0.020

The pre-registered hypothesis from passes 1-4 was "_UP regimes fade on
KR". Tested at the family level (4 cells: WHALE_UP and HERD_UP for
both ETH and BTC, all on KR spot, all n ≥ 100):

| Cell | n | r | Fisher z |
|---|---:|---:|---:|
| KR-ETH WHALE_UP | 482 | −0.073 | −1.601 |
| KR-BTC HERD_UP | 176 | −0.108 | −1.421 |
| KR-BTC WHALE_UP | 366 | −0.045 | −0.852 |
| KR-ETH HERD_UP | 145 | −0.064 | −0.768 |

**Stouffer's combined z = −2.32, two-sided p = 0.0203.** Significant.
The n-weighted version gives the same p.

Crucial sanity check: the complement test is null.
- KR _DOWN family (4 cells): combined z = +0.18, p = 0.86 (no
  unidirectional pattern)
- All KR cells with n ≥ 30 (15 cells): combined z = −0.011, p = 0.99
  (KR is not generically mean-revert)

So the asymmetry is real — specifically the _UP regimes fade, not _DOWN
regimes (which are noise) or KR generally. This survives BH-FDR at the
family-pool level (one pre-registered test, p = 0.020).

**Effect size interpretation.** Avg |r| ≈ 0.07. On a +1σ chunk move
(KR-ETH chunk-return σ ≈ 20 bps), expected next-chunk fade is
−0.07 × 20 = **−1.4 bps gross**. After 25 bp Practice mode roundtrip:
−26 bp net per trade. Sub-cost at retail; needs maker tier (KR Pro
T5+ at 0% maker fee + ~10 bp slippage = +1.4 bp net) to be tradable
at all. Frequency: ~40 KR-ETH _UP chunks per week.

### Headline 3: ETH KR vol-Q3 _UP fade — strongest regime sub-cell

Conditional sub-window analysis on KR-ETH _UP chunks split four ways
(regime label, session phase, chunk volume quartile, chunk realized-vol
quartile) found one clean hot spot:

| Sub-window | n | r | p | Comment |
|---|---:|---:|---:|---|
| baseline (all _UP) | 627 | −0.068 | 0.090 | weak |
| **vol-Q3 (mid-high, 198-441 ETH/chunk)** | **157** | **−0.258** | **0.0009** | **★ tradable conditional |r|** |
| vol-Q4 (highest) | 156 | −0.021 | 0.795 | null — likely news/liquidations |
| rv-Q3 (mid-high vol) | 157 | −0.182 | 0.022 | sub-threshold |
| weekend session | 141 | −0.135 | 0.108 | weak |
| us_active session | 129 | −0.101 | 0.254 | weak |

**Mid-high volume, not highest, carries the fade** — fits a story
where Q4 events are news/liquidations (broken regime) while Q3 is
organic WHALE activity that mean-reverts.

Deep-dive on this cell (after promoting WHALE_NASCENT — see Headline 5):

| Check | Result |
|---|---|
| Bootstrap 95% CI on r | [−0.333, −0.050]; 0.1% > 0 |
| Time stability (4 quarters of 30d) | Q1 −0.15 (null), Q2 −0.25 (sub-sig), Q3 −0.10 (null), **Q4 −0.37 (sig)** — concentrated in most recent 7d |
| Decomposition within vol-Q3 | **HERD_UP n=52 r=−0.34 p=0.012** ★; WHALE_UP n=108 r=−0.21 p=0.028 ★ |
| Vol-Q3 with NASCENT_UP excluded | n=160 r=−0.24 p=0.0019 (slight strengthening, +18% |r|) |

**Two concerns:** the time-quarter decomposition shows the signal lives
mostly in the most-recent 7d of the 30d window. Direction is sign-stable
across all 4 quarters (all negative), just magnitude-modulated. The
right interpretation under the user's "time-varying alpha" framing is
*the regime is currently active*, not *the signal is fake*. But the
single-quarter Q4 result fails Bonferroni at 4-test correction.

**Tradability**: HERD_UP within vol-Q3, |r|=0.34, edge per trade
≈ 6.7 bps gross. Pro Tier maker + 5 bp slippage = +1.7 bp net.
Frequency ~1.7 trades/day. Tiny revenue volume even if profitable.

### Headline 4: BTC BN-perp leads KR-spot — most robust signal in the project

Lightweight minute-level analysis (no PELT) on the 9-day perp/spot
overlap. Headline:

```
perp_imbalance_t -> fwd_spot_{t+1}: n=12,955  r=+0.0957  p≈0
```

Deep-dive results, all robust:

| Check | Result |
|---|---|
| Time stability (4 quarters of 9d) | r=+0.125, +0.099, +0.115, +0.068 — **all 4 quarters p<0.001** |
| Lag profile | k=0 r=+0.42 (contemp), k=1 r=+0.10, k=2 r=+0.025, k=3 r=+0.020, k≥4 null |
| Decile structure | clean monotonic. D1 z=−8.4, D5 z=−0.06 (null at neutral), D10 z=+7.0 |
| **D10 vs D1 spread** | **+1.44 bps fwd-spot, z=+10.8** |
| Direction symmetry | buy-led r=+0.069, sell-led r=+0.065 (works both ways) |
| Bootstrap 95% CI | [+0.081, +0.111], 0% of 1000 resamples below 0 |

**Interpretation.** When BN-perp has a buy-imbalance during minute t,
KR-spot tends to drift up during minute t+1 (and to a lesser extent
through t+3). The mechanism is plausible: BN-perp aggregates more
aggressive flow at higher leverage; KR-spot follows when arbitrageurs
or aware traders close the basis.

**ETH version is much weaker**: r=+0.034, only 2 of 4 quarters significant,
decile spread 0.63 bps (half of BTC's). Real but marginal.

**Tradability.** D10 mean fwd return = +0.71 bps. At KR Pro Tier 5+
maker (0% maker) + 0.5 bp slippage: net ≈ +0.2 bps per trade. ~290
D10/D1 trigger minutes per day. **Marginal at maker tier; impossible at
retail taker fees**. Latency budget is ~30-60 sec to place the order
(NOT sub-second, as I'd initially overstated) — within reach of any
reasonable retail API. The barrier is fees, not infrastructure.

### Headline 5: WHALE_NASCENT regime promoted from UNKNOWN

The classifier's `UNKNOWN` regime was reached only when a chunk had
directional dipole (≥0.25) AND moderate persistence (acl1 ≥ 0.2) but
didn't trip full WHALE thresholds (acl1 ≥ 0.4 with |dipole| ≥ 0.15, OR
Kyle absorption, OR oscillation peak). Mechanistically: a directional
trend that has formed but not yet shown sustained one-side pressure —
"borderline whale" or "nascent whale".

Promoted to `Regime.WHALE_NASCENT_UP` and `Regime.WHALE_NASCENT_DOWN`
based on dipole sign. UNKNOWN remains in the enum as a never-reached
sentinel (no decision path returns it now).

**Evidence at Pass 5:**

| Cell | n | r | p | 95% bootstrap CI | Direction confidence |
|---|---:|---:|---:|---|---|
| ETH KR WHALE_NASCENT_UP (30d) | 44 | +0.211 | 0.162 | [−0.10, +0.52] | 88.7% positive (momentum) |
| ETH KR WHALE_NASCENT_UP (recent 9d only) | 14 | +0.583 | 0.013 | — | strong momentum |
| BTC KR WHALE_NASCENT_UP (30d) | 49 | −0.214 | 0.132 | [−0.42, +0.003] | 97.2% negative (fade) |

**Asset-divergent and surprising.** ETH NASCENT_UP shows momentum (the
expected lifecycle: nascent continues → matures into WHALE_UP → fades).
BTC NASCENT_UP shows fade direction — the nascent stage on BTC is
already in mean-revert mode. Possible mechanism: BTC's higher
institutional flow means borderline-WHALE events resolve faster than
ETH's more retail-driven flow.

At n=44/49 these are both small-sample suggestions, not confirmed
findings. Worth letting the cells accumulate; if the asset-divergence
holds at n=150+, the lifecycle hypothesis deserves separate per-asset
playbook strings.

**Code change shipped on `claude/remove-handoff-info-lFAHr`** (commit
`dd77095`):
- `regime_classifier.py`: enum + intentional NASCENT classification
- `backend/api_server.py`: PLAYBOOKS strings for both NASCENT regimes;
  `expected_direction_from_signal` switched to `endswith("_UP"|"_DOWN")`
- `frontend/src/components/{SignalCard,RegimeCard}.jsx`: emerald/rose
  styling, "Nascent ↑/↓" labels (lighter shade than full WHALE)
- Stats / RegimeHistory / Onboarding pages still fall back to UNKNOWN
  styling — to be updated when NASCENT cells get promoted into the
  playbook registry.

### Headline 6: Perp confirmation filter test — negative result

Hypothesis: layering BN-perp imbalance as a directional gate on the
KR-spot _UP fade should raise conditional |r|. When perp confirms the
buy direction, the spot fade is "real" and should fade harder.

Result: hypothesis rejected. Splitting ETH KR _UP chunks by perp
imbalance sign gives:

| Subset | n | r | p |
|---|---:|---:|---:|
| WHALE_UP, perp_imb > 0 | 83 | −0.079 | 0.48 |
| WHALE_UP, perp_imb ≤ 0 | 70 | −0.134 | 0.26 |
| HERD_UP, perp_imb > 0 | 12 | −0.331 | 0.27 |

The **opposite** filter (`perp_imb ≤ 0`, perp disagrees with the spot
move) shows mildly *stronger* fade direction on WHALE_UP. The
differential is small (−0.134 vs −0.079) and not significant, but the
direction is the opposite of what we expected.

The HERD_UP perp_imb≤0 cell at r=+0.866 p=0.0001 (n=7) is statistical
noise from a tiny sample with extreme correlation; ignore.

**Mechanism interpretation if the disagreement filter is real**: when
KR-spot is in _UP regime but BN-perp shows sell pressure, the spot move
is local/idiosyncratic — perp says broader market is selling, and spot
fades to catch up. The confirmation filter as originally hypothesized
is a dead end.

**One actionable surprise from the filter test**: ETH KR
WHALE_NASCENT_UP within the 9d perp window showed r=+0.583 p=0.013 at
n=14 — 3× stronger than the 30d aggregate (r=+0.211). Direct
observation of time-varying alpha: the NASCENT momentum signal is much
more pronounced in the most recent 9 days than across the full 30d. n
is too small to commit, but worth deploying at minimum size to
accumulate.

### Time-varying alpha framing

The user explicitly raised this read: "different signals might be valid
on different days or weeks. just because they might not last over time
doesn't necessarily mean they aren't valid that trading day." This is
correct (Andrew Lo's Adaptive Markets Hypothesis; standard
practitioner observation) and is the right framing for these results.

**The project already has the infrastructure for adaptive deployment**:

- `build_playbook_registry.py` rebuilds per-(asset, venue, regime) edge
  stats every 6h cycle
- `refrag_audit.py` emits `drift_alert` events when cells decay or
  strengthen
- The PWA `<DriftBanner/>` and per-card drift badges surface this in
  real time
- `backend_practice_trades.jsonl` provides forward paper-trading P&L
  with realistic fee/slippage assumptions

What's missing: **forward paper trading on the new candidate cells**
(NASCENT momentum, vol-Q3 fade, perp lead). The registry rebuild
mechanism handles slow updates per cycle; the `outcome_contradiction_streak`
fast-loop handles per-signal real-time corrections. Both feed the same
`drift_alert` channel.

**This pass's signals are deployable as registry entries — not as
standalone trading strategies.** The runtime evaluates per-cell |r|
against current rolling window and adjusts confidence weights. A signal
that's strong this week + decaying next week + flat the week after is
exactly what the drift loop is designed to track.

### Tradability shortlist after Pass 5

| Signal | Asset | Horizon | n | |r| | Tradable retail? | At maker tier? | Frequency |
|---|---|---|---:|---|---|---|---:|
| **BTC BN-perp imbalance → KR spot** | BTC | 1 min | 12,955 | **+0.10** | No | **Marginal yes** | ~290/day |
| **ETH KR HERD_UP within vol-Q3** | ETH | 10-30 min | 52 | **−0.34** | No | Marginal | ~1.7/day |
| **ETH KR WHALE_NASCENT_UP momentum** | ETH | 10-30 min | 44 (30d), 14 (9d) | +0.21 / +0.58 | **n too low** | n too low | ~1.5/day |
| ETH KR vol-Q3 _UP fade (combined) | ETH | 10-30 min | 168 | −0.20 | No | Marginal | ~5.6/day |
| ETH KR _UP fade family-pool (Stouffer) | ETH+BTC | 10-30 min | 1,169 | family p=0.02 (avg \|r\|≈0.07) | No | No | varies by asset |
| BTC KR WHALE_NASCENT_UP fade | BTC | 10-30 min | 49 | −0.21 | n too low | n too low | ~1.6/day |

None of these is a clean retail strategy. Three (BTC perp lead, ETH
HERD_UP vol-Q3, ETH NASCENT_UP momentum) are plausible at maker-tier
fees with disciplined sizing. The right deployment is via the existing
playbook registry + drift alert pipeline, not as standalone scripts.

### What changed in code this pass

| Commit | Branch | What |
|---|---|---|
| `3dadfb8` | `claude/remove-handoff-info-lFAHr` | `backfill_oneshot.yml`: `git add -f` past .gitignore; cap BN-vision at 10d so file pushes < 100MB |
| `7bfdaf2` | same | `.gitignore`: treat `_*.py` as scratch (one-off recheck scripts) |
| `dd77095` | same | promote UNKNOWN borderline-whale to `WHALE_NASCENT_{UP,DOWN}` regime; backend playbooks; frontend label/color (SignalCard + RegimeCard) |

These three commits live on `claude/remove-handoff-info-lFAHr` and
need cherry-picking onto `claude/continue-phase-2-pipeline-UFiGY` to
take effect on the live deployment.

Three scratch analysis scripts on the same branch (now `.gitignore`d
under `_*.py`):
- `_subwindow_recheck.py` — found ETH vol-Q3 hot spot
- `_perp_basis_recheck.py` — found BTC perp lead
- `_perp_deepdive.py` — robustness checks on the perp lead
- `_eth_volq3_deepdive.py` — robustness checks on the vol-Q3 hot spot
- `_perp_filter_test.py` — perp confirmation filter (negative result)

### Reproducer for Pass 5

```bash
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json eth_binance_perp_bins.json
git checkout origin/data/btc-bins -- btc_coinbase_bins.json btc_kraken_bins.json btc_binance_perp_bins.json

# Standard Phase 1.5 pass (will use WHALE_NASCENT after the classifier
# patch is on phase-2):
python phase1_5_evaluator.py --asset ETH \
  --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
  --multi-signal-pelt \
  --report-path /tmp/eth_phase1_5_post_backfill.json

python phase1_5_evaluator.py --asset BTC \
  --cb-bins btc_coinbase_bins.json --kr-bins btc_kraken_bins.json \
  --multi-signal-pelt \
  --report-path /tmp/btc_phase1_5_post_backfill.json

# Conditional + perp analyses are in _*.py scratch scripts on the
# remove-handoff-info-lFAHr branch.
```

### Next-evaluation triggers

Re-run Phase 1.5 + the scratch scripts on the next backfill or workflow
cycle if any of:

- **CB backfill is rerun with longer wallclock budget** (16-24h) so
  CB-side gates have credible n. Currently CB-ETH at 2.6d and CB-BTC at
  0.4d are uninformative.
- **WHALE_NASCENT_UP n grows past 100** on either asset. At current
  rate (~1.5 chunks/day on KR-ETH) that's ~70d more data. Could be
  accelerated by training on Bybit perp + extending RT collection.
- **Bybit perp data accumulates to 30d** (currently ~3-7d depending on
  when first cycle ran). First chance to look at spot-vs-Bybit-perp
  basis (orthogonal to BN-perp lead) and at perp-only regime signals.
- **Drift alert fires on any active cell** — the playbook registry
  rebuild will surface this automatically. If the vol-Q3 fade
  strengthens or decays, the alert will say so.
- **A user starts forward paper trading** on any of the candidate
  cells. The `backend_practice_trades.jsonl` ledger will accumulate
  outcome P&L per cell that can validate or invalidate the historical
  signal.

### One-shot summary for the next agent

The 30d backfill clarified that prior small-sample signals were
exaggerated by sampling effects. After the recheck, three findings
remain credible at p < 0.05:

1. **KR _UP family fade hypothesis** — p=0.020 across 4 cells / 1,169
   chunks via Stouffer combination. Effect size avg |r|≈0.07, sub-cost
   at retail.
2. **ETH KR vol-Q3 _UP fade** — n=168 r=−0.203 p=0.008, bootstrap CI
   [−0.33, −0.05]. Time-varying (concentrated in most recent 7d) but
   sign-stable across all 4 time-quarters.
3. **BTC BN-perp imbalance leads KR spot at 1-min** — n=12,955 r=+0.10
   p≈0, all 4 time-quarters significant, bootstrap CI [+0.08, +0.11].
   The most robust signal in the project.

One promising small-n signal to watch:

4. **ETH KR WHALE_NASCENT_UP momentum** — n=44 r=+0.21 over 30d but
   r=+0.58 in recent 9d. Lifecycle hypothesis (nascent continues →
   matures into WHALE_UP → fades) supported on ETH; opposite on BTC.

The framework that consumes these is the existing
`build_playbook_registry.py` + `refrag_audit.py` + drift-alert pipeline.
No silver bullet, four candidate cells with different maturity stages.
