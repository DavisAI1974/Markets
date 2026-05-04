# Markets / dipole — handoff to Code

**Date**: 2026-05-04
**From**: Architect (Claude)
**To**: Code
**Branch**: `davisai1974/markets @ claude/new-session-o3vnm`

## Scope clarification (read first)

This is a **standalone product thread**. Cross-domain probe from SENTINEL machinery — testing whether the OD operator-discovery stack produces tradeable edge on market data.

It is NOT:
- Part of the DARPA Bio Attribution submission
- Part of any defense or government deliverable
- Going to be written up as a paper
- A research artifact

It IS: an attempt to repurpose the refrag / OD machinery as an alpha-discovery factory and ship a paper-trading prototype.

Falsification-first still applies. "Better, stronger, faster, cheaper" still applies. But framing for downstream comms is product, not science.

## Decisions resolved

### 1. PELT chunk length / bar resolution

Move off 1-sec bars / 60-bar windows. At that resolution we are inside the HFT latency envelope and the dipole is dominated by queue-position and maker-taker rebate dynamics, not information.

**Default for first real test: 1-min bars, 30-min chunks.**

Reasons: (a) matches the intraday-momentum timescale where retail edge actually lives, (b) gives ~30 chunks per multi-hour session, enough for trajectory analysis, (c) gets out of microstructure noise.

Keep 1-sec collection capability for a future microstructure layer and for within-chunk shuffle controls. Do not make it the default.

### 2. Encoder dimensionality

Keep `MarketChunkEncoder` at 64D natively. Do NOT bake UMAP into the encoder.

Add `MarketChunkEncoder.reduce(target_dim, method='umap'|'pca')` as a separate downstream operation. Rationale: UMAP is non-deterministic and parameter-sensitive — embedding it in the encoder makes the encoder non-stationary across runs, which breaks reproducibility for falsification work. Different downstream consumers want different dims. Reduce at the consumer, not the source.

### 3. First deepnova operator to wire

**Per-chunk coefficient trajectories first.** This is the direct port of the moving-coefficients view from the cyber project and it is the thing that makes the abstract dipole question visual and tradeable.

Implementation:
- Run `SignalDecoder.prefill` per PELT chunk
- Extract recovered coefficient vector from each chunk
- Plot coefficient trajectory across chunks (one line per coefficient dimension)
- Mark PELT boundaries on the plot
- Look for discontinuities at boundaries

Cheapest single thing on the table per unit of insight produced. Build this before any deepnova operator.

After that lands: `cross_domain_transfer_detector` (MAML + OT) to put a real number on the transfer-from-4-sciences-to-markets question. Skip `falsification_prioritizer` (BALD) for now — it needs an existing predictor to compute info gain over and we don't have one yet.

### 4. Path C vs Path D

**Path C first** (feature-discovery + classical predictor). Three reasons:

1. 3–6 weeks to paper-trading prototype vs Path D's FNO training overhead
2. Path D requires ≥100 pairs per regime — we do not have that data
3. Path C generates the labeled data Path D would later train on

Path D layers on top of C if C produces edge. Substrate stays path-agnostic so this is reversible.

### 5. Data sources

**Stay crypto. Add Kraken as second venue for cross-venue replication.**

Skip Alpaca SPY: IEX-only is ~2% of US equity volume, the order flow is non-representative of the actual book, and the dipole is an order-flow construct. On a 2% slice it goes degenerate the same way Binance.US BTCUSDT did.

Skip Polygon / Databento until edge is demonstrated on free data. Falsification-first means do not pay for data until you have shown signal on free data.

Cross-venue replication test (free, gives a clean sanity check): if the dipole is real, it should appear with the same sign on Coinbase and Kraken simultaneously, on the same wall-clock minute. Disagreement across venues = artifact.

### 6. Manipulation contamination

Do not try to model adversaries. Gate them out.

Add a chunk-level contamination flag:
- Compute within-bin correlation between H_a and H_b inside each PELT chunk
- High correlation = paired-trade / wash-trade signal
- Flag and exclude flagged chunks from training and from trajectory analysis
- Log flag rate per chunk so we can see if a venue is dirty

Do not try to detect spoofing or layering — those are book-level phenomena and we are trade-only. Acknowledge the gap; don't paper over it.

## Critical observation the handoff_desktop.md understated

Coinbase canary run #2:
- r_dipole = +0.127, R² = 0.016
- shuffled R² = 0.038

**Shuffled control gave 2.4× higher R² than real signal.** That is not "weak signal." That is **noise floor exceeds signal at n=116**. The original gate protocol (single shuffled sample, threshold 0.01) is below the actual variance of the shuffled statistic at that n.

Implications:
- Stop reporting R² at n<500 as anything other than "not yet measurable"
- 1000-permutation 95th-percentile control (already in plan) is required, not optional
- 15-min collection at 1-min bars = 15 chunks → way too few for trajectory analysis
- For trajectory work: **4-hour collection during a US equity session** = ~240 chunks at 1-min bars

Use 1-sec collection only inside individual chunks for within-chunk shuffle controls — don't try to extract trajectory from 1-sec data.

## Next concrete action

Build `coinbase_btcusd_4hr_trajectory.py`:

1. WS collect 4 hours of BTC-USD trades and book ticker from Coinbase during a US equity session
2. Bin to 1-min bars (240 bars)
3. PELT chunk the 240-bar series (expect ~8–15 regime chunks at this length)
4. For each chunk: run `SignalDecoder.prefill`, extract coefficient vector
5. Compute 1000-permutation control per chunk; record 95th-percentile R²
6. Compute within-chunk H_a / H_b correlation, flag chunks above threshold (start at 0.7, tune later)
7. Output: per-chunk JSON record with coefficients, R², perm-95, contamination flag
8. Plot coefficient trajectory across chunks with PELT boundaries marked and contaminated chunks shaded

Stop gates for this run (replaces the original canary gates):
- A. At least one coefficient dimension shows discontinuity at ≥1 PELT boundary larger than the within-chunk perm-95 spread
- B. At least 60% of chunks pass contamination gate
- C. Coefficient trajectory on a held-out second 4-hour window shows similar discontinuity pattern (replication)

A + B alone = signal candidate, run the second window. A + B + C = proceed to Kraken cross-venue replication. Any fail = document and rethink operator pair.

Optional same session: spin up a Kraken WS collector in parallel so the cross-venue check is one script-run away when needed.

## Save locations

Save this file to:
- `E:\information_layer\markets\HANDOFF_TO_CODE.md`
- `F:\Factory\knowledge\information_layer\markets\HANDOFF_TO_CODE.md`

(OD knowledge files at E:\, factory knowledge base at F:\Factory\knowledge\, per standing protocol.)
