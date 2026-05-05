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
