# SESSION HANDOFF — S39 (2026-06-22) — free-historical backfill, 1-second everything, the coeff-engine UNBLOCK, alt coeffs done

Branch `claude/crypto-backfill-validation-31tubb` (all work PUSHED). Continues S37/S38. Memories apply:
crypto platform only; zero synthetic; per-cell deploy; **never flatten/average/smooth — bucket +
trade distinctiveness is the goal**; git is source of truth; falsification-first; never tune off one window.

## THE BREAKTHROUGH (read this first): coeff discovery runs IN-CONTAINER, no box / no torch / no FNO
The 128-dim `operator_coefficients` that made the committed BTC/ETH fingerprints are **unit-L2 and all
non-negative** — the signature of the **DETERMINISTIC decoder tier** (`OperatorDecoder.prefill` = mean of
spectral-magnitude embeds, `refine` = L2-normalize), **NOT** a trained FNO. The manifest's FNO+Bayesian is
the aspirational tier; the actual coeffs are deterministic. That whole pipeline is **vendored in markets**
(`odcore/od_refrag_adapter.py` — chunker/encoder/query/decoder; `markets_adapter.py` is the same port with
`np.fft.rfft`). So:
- **No `E:\refrag`, no torch, no FNO checkpoint needed** to reproduce the production coeffs.
- Verified by signature match (dim 128 / L2 1.0000 / all ≥0 / leading-zeros→spectral-profile) reproducing on
  1-sec bins. Caveat: signature-matched, NOT exact-vector (no original 05-18 bars); the encoder-summary /
  expansion-path variant is the knob to pin for exact BTC/ETH comparability.
- **cs100_v2 config (verbatim from `_markets_gate_v2`):** pre-entry 30-min window → 1-sec mid → log-returns
  → `SpectralChunker(window=192, stride=16)` → `SpectralChunkEncoder(d_enc=128)` →
  `OperatorQuery.from_spectral_target([0.1,0.25], 1.0)` → top_k=8, mixed prefill expand_budget=4 →
  `OperatorDecoder.prefill` → `refine(8)` ⇒ 128-dim unit-L2 coef.
- **Speed:** swapped the pure-Python O(n²) DFT for `np.fft.rfft` (the docstring's prescribed prod path;
  identical magnitudes) → full alt cap-100 discovery = **35 s** in-container.

## 1-SECOND IS THE STANDARD (Greg, load-bearing) — minute bars were a flaw
Aggregating 1-sec→1-min smooths away the sub-minute order-flow structure that carries the timing edge
(S36b). All alt work is now 1-second-native: labeler, oracle exit, micros, AND the coeff pipeline (window=192
samples over the 30-min 1-sec window = fine-resolution). **OPEN:** the existing BTC/ETH coeffs were built on
the coarser path — re-discover them on 1-sec for consistency (now cheap, runs in-container).

## WHAT'S DONE + COMMITTED THIS SESSION
1. **Free-historical backfill suite** on the branch + **`backfill_bybit.py`** (NEW, Bybit public daily dumps).
   Data-integrity verified before any run: timestamps integer-second, NO shift (overlap test vs RT = 0.008 bps
   median); taker buy/sell semantics consistent across all sources + RT collectors. `backfill_oneshot.yml`
   rewritten: 5-coin matrix, gzip-aware (no more 100 MiB stall). (Greg launches GHA runs; my token can't.)
2. **`realbins/` = 9 cells** (local, gitignored): 5 `*_bybit_perp` (21d, contiguous, 0 gaps>1h — the clean
   multi-regime set), 2 kraken (13.9d gap-free), 2 coinbase (gappy — REST walk-back limit).
3. **Multi-regime gated-swing re-run KILLed the S37 single-window deploy map** (`_info_dipole_gated_swing.py`,
   leakage PASS 9/9): only 2/9 cells clear net>0 at maker, both thin; **7/9 stand aside incl. all 5 bybit_perp.
   No capital on this evidence** — the +466/+392/+670 were overfit. (`_info_dipole_gated_swing_results.json`)
4. **1-second alt winner-labels** (`_build_alt_winner_labels.py`) — oracle best-favorable-exit (buy 360 / sell
   60 min, net 10 bps) off 1-sec bins, per cell, buy/sell separate. 6 alt cells (sol/doge/xrp bybit_perp),
   ~2500–2800 winners each. **source_id collision FIXED** (S35 class — embed decision_ts; the earlier "XRP-sell
   = 195 winners" in the S38 note was the STALE collision, real count is 2564).
5. **600 alt coeffs** (`_run_alt_coeffs.py` → `_alt_labels/coeffs/alt_coeff_index.json.gz`): 100/cell, all
   source_ids unique, 128-dim unit-L2, intra-cell cosine ~0.91 (distinct per bucket). Lineage `onset_1s`.

## OPEN / NEXT (priority)
1. **AWS package (IN PROGRESS — `aws/` dir created, not yet filled).** Greg's call: run the heavy jobs on AWS.
   Plan: Dockerfile (CPU numpy) + S3-aware discovery runner (bins↓ / coeff-index↑) + Batch/EC2 launch doc;
   **SageMaker GPU** path for the real **FNO decoder training** (the production tier upgrade). **Bedrock** is
   the AWS-native path (Claude Code via Bedrock + Knowledge Bases on S3/RDS) for running the agent + GPU
   training with data residency. No AWS creds in this container (verified: no CLI/boto3; AWS endpoints
   reachable) → I package, Greg launches with creds. **This is the natural first task for the new chat.**
2. **Re-discover BTC/ETH coeffs on 1-second** (consistency with the alts; cheap in-container now).
3. **Pin the exact-comparability knob** (encoder-summary / expansion variant) if cross-cell (BTC/ETH↔alt) coeff
   comparison is needed; per-cell distinctiveness already holds.
4. **Wire the per-cell distinctive fingerprint predictor** off the coeffs (the S35 goal) — now that alts have
   coeffs, build/stack the per-bucket fingerprint; deploy per cell, never pooled.
5. Default-branch sync NOT done (kept to the assigned dev branch per the hard rule).

## TOOLS ADDED/CHANGED
`backfill_bybit.py`; `backfill_{binance_vision,coinbase_spot,kraken_spot}.py` (vendored); `backfill_oneshot.yml`
(5-coin gzip matrix); `_build_alt_winner_labels.py` (1-sec, unique source_id); `_run_alt_coeffs.py` (in-container
128-dim discovery); `odcore/od_refrag_adapter.py` (vendored engine, numpy FFT); `_info_dipole_gated_swing.py`
(multi-regime, self-documents span). Data: `realbins/` (local), `_alt_labels/` (labels + coeffs, committed).
