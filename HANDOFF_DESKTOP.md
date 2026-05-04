# Markets / refrag / dipole — handoff brief for Desktop

**Date**: 2026-05-04 · **Branch**: `davisai1974/markets @ claude/new-session-o3vnm`
**Goal**: tradeable retail-scale predictor (product), not a research artifact. Refrag's operator-discovery machinery as an alpha-discovery factory.

## What we're trying to do — the dipole and the cyber tie-in

The H_a/H_b dipole emerged as a top-ranked operator across 4 sciences (physics, biology, chemistry, geology): taker-buy vs taker-sell normalized as `(H_a − H_b) / (H_a + H_b)`. Working hypothesis: if this is a fundamental pattern of dynamical systems with conservation laws, it should appear in markets too — where conservation = total order flow and sides = aggressive buy / aggressive sell.

**Cyber precedent that motivates this**: in the DARPA project we recovered **moving operator coefficients** on cyber-attack telemetry — operators whose coefficients drift over time, with the drift itself being the diagnostic signal. Cyber is high-noise, adversarial, regime-shifting. Markets are the same shape of problem. If recovery worked there, the methodology should work here. Greg's intuition: "we should be able to find coefficients in a digital market."

The natural mapping: each PELT-aligned regime chunk recovers its own operator coefficients. The trajectory of those coefficients across chunks IS the time-varying operator. **Coefficient discontinuities at PELT boundaries = regime change events.** This is the visualization framework we want.

## Architecture as it stands

### Layer 1 — Canary (operator-pair stress test)
- `coinbase_btcusd_canary.py` — original 2-min canary. **NULL** under the original gate protocol (R²=0.008, sign negative).
- `coinbase_btcusd_canary_v2.py` — same WS collection, two analyses side by side: bin-level (v1 protocol) and PELT-chunk-level via markets_adapter.
- `binance_btcusdt_canary{,_phone}.py` — geo-blocked from sandbox; phone variant tested on Pydroid 3 (BTCUSDT on .US is too thin to canary; produces degenerate samples with H_b ≡ 0).

### Layer 2 — Markets adapter (deepnova surface, `markets_adapter.py`)
Mirror of `od_refrag_adapter.py`, market-data-shaped. Plane-clean: every deepnova control-plane operator wires in without registry/governance changes.

| Component | What it does |
|---|---|
| `MarketBar` / `MarketChunk` / `MarketFeatures` / `SignalCandidate` | Dataclasses paralleling the OD types |
| `pelt_change_points` | PELT change-point detection, normal MV cost, BIC penalty — replaces the brittle fixed-bin chunking that fragmented the canary signal |
| `MarketChunker` | fixed / adaptive / hybrid modes |
| `MarketChunkEncoder` | 64D embedding = 11 summary stats + 3 spectral + 50 FFT magnitudes. Microstructure features include H_a/H_b dipole, OFI, return moments, volume z-score, ATR, lag-1 autocorr |
| `MarketQuery` | `from_candidate / from_regime_target / from_spectral_target` — same three modes as `OperatorQuery.v2` |
| `SignalDecoder` | Bayesian stub mirroring `OperatorDecoder.v2` interface — drop-in slot for FNO + Bayesian deep ensemble per the manifest's training_contract |
| `FeatureScaler` | Per-dim z-score; without it cosine is dominated by largest-magnitude features |

**Verification on synthetic two-regime data** (σ=0.001 → σ=0.005 at bar 300): PELT recovered the regime boundary at bar 300 pixel-accurate. After scaler fix, querying for "volatile regime" correctly returns the 3 most-volatile chunks.

## What we're seeing on real data so far

| Run | n | r_dipole | R²_dipole | gate verdict |
|---|---|---|---|---|
| Coinbase 2-min #1 | 119 bins | −0.090 | 0.008 | NULL |
| Coinbase 2-min #2 | 116 bins | +0.127 | 0.016 | fail (shuffled R²=0.038 *exceeded* test) |
| Coinbase v2 PELT #2 | 3 chunks | — | — | too few chunks |
| Binance.US BTCUSDT 2-min | 43 bins | 0.004 | ~0 | **degenerate** — sell vol ≡ 0 |
| Binance.US BTCUSD 2-min | 54 bins | +0.281 | 0.079 | **invalid** — sell vol ≡ 0, dipole degenerate |

**Sign flipped between two consecutive Coinbase 2-min samples** → 2 min is too short for any verdict. Path forward when Greg gets your input: 15-min collections during US equity hours, multi-permutation control (1000 perms, 95th percentile), per-chunk decoder coefficient trajectories.

## Possibilities under consideration

**A. Path C — Feature-discovery + classical predictor.** Refrag discovers and ranks market features (`manifest_synthesizer` PrefixSpan+VAE on backtest traces); standard regressor predicts. `falsification_prioritizer` BALD picks high-info windows; `evidence_graph_builder` GATv2 accumulates cross-regime evidence; `lifecycle_tracker` ADWIN+Cox PH detects drift and models alpha half-life. **3–6 weeks to a paper-trading prototype.** Fastest to product.

**B. Path D — Recovery-as-predictor with FNO + Bayesian posterior.** Recovered operator IS the predictor. FNO operates in frequency domain (Black-Scholes is a PDE; FNOs solve PDEs in spectral space). Bayesian posterior width = risk gauge; `underdetermined_flag` → no trade. Requires training FNO on financial data (≥100 pairs per regime). Best layered on path C if path C produces edge.

**C. Per-chunk coefficient trajectories (the cyber analog).** Run `SignalDecoder.prefill` per PELT chunk; plot the recovered coefficient vector across chunks. Discontinuities at PELT boundaries = regime transitions. This is the direct port of the moving-coefficients view from the cyber project. Cheap to add; biggest single value-per-line of code on the table.

**D. 12D manifold embeddings + visual diagnostic.** Reduce 64D chunk embeddings → 12D via UMAP (canonical manifold dim in your system). Then either project further to 3D for visual cluster check (good encoders show separable regime clusters; bad ones look like spaghetti) or use the 12D directly as input to downstream operators that expect 12D. `task_meta_learner`'s DPGMM auto-discovers the regime taxonomy in the 12D space without us hand-labeling.

**E. Cross-domain transfer formalization.** `cross_domain_transfer_detector` (MAML + Optimal Transport on spectral distributions) gives a formal transfer-confidence number for "dipole transfers from physics → markets" — replacing the single-canary-gate verdict with proper machinery. Closes the original 4-sciences-to-markets question with the right tool.

**F. Falsification-driven backtesting.** BALD picks the 50 historical windows that would maximally reduce strategy-edge uncertainty, instead of brute-forcing 5 years. Roughly 10x compute efficiency for retail budgets.

## Key open decisions (Desktop input)

1. **Time scale of moving coefficients in the cyber project**: hours, minutes, seconds? Sets the right PELT chunk length for markets. We're currently looking at 1-second bars chunked into 60-bar (1-min) windows. If cyber drift was minutes, our 1-min windows are right; if hours, we need 1-min bars and 30-min chunks.
2. **12D natively?**: should `MarketChunkEncoder` produce 12D natively (UMAP fit on raw 64D), or keep 64D and let consumers reduce as needed? Affects compatibility with your existing ~12D-input operators.
3. **First deepnova operator to wire**: I lean `falsification_prioritizer` (BALD info-greedy backtest selection) as highest leverage. Alternatives: `evidence_graph_builder` for cross-window accumulation, or `cross_domain_transfer_detector` for the formal physics→markets test.
4. **Path C or D first?**: substrate is path-agnostic; ~3–6 weeks of work points one way.
5. **Data after Coinbase**: SPY via Alpaca free tier (real US equities, IEX-only feed)? Futures via paid Polygon/Databento? Stay crypto and add Kraken/Bitstamp for cross-venue replication?
6. **Regime contamination check**: in the cyber project, did adversary attempts to spoof the operator (i.e., generate fake signal) actually fool the detector, or did the Bayesian posterior catch them? Same question for markets — wash trading, spoofing, layering. Worth knowing what your prior is.

## What runs next (when you weigh in)

15-min Coinbase BTC-USD collection during US equity hours. Per-chunk decoder coefficient extraction added to v2. Multi-permutation control (1000 perms). Optional 12D UMAP projection layer over the chunk embeddings. Then we can plot coefficient trajectories across ~30 PELT chunks and see whether the dipole's coefficients move at regime boundaries the way the cyber operators did.
