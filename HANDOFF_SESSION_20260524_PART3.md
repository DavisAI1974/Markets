# Handoff — Part 3: Quantum landed, hardening, OD KB seeds, arch-map handoff (2026-05-24)

Continues from `HANDOFF_SESSION_20260524_PART2.md`. This session ran the quantum side to completion, hardened the orchestrator's I/O against killed-mid-write states, settled the admission-gate open question, and seeded a few JSON findings into the OD knowledge base directory.

## NEW-CHAT DIRECTIVE — read this first

**The next chat exercises the rest of the arch map.** Authoritative spec: `E:\refrag\docs\architecture_spec_v21.docx` (text dump at `E:\refrag\_arch_spec_v21_extracted.txt`). The control-plane operators (gap_finder, manifest_synthesizer, chain_builder, composability_scorer, benchmark_suite, pipeline_performance_optimizer, exploration_policy_controller, task_meta_learner, lifecycle_tracker, lineage_tracker, promotion_recommender) were built to do automatically what this session and the previous two did by hand: ingest discoveries, surface gaps, score compositions, optimize policies, generalize across domains.

**Greg's framing**: *"the point of the rest of refrag is to do what we are doing now so we'll give it a crack."* Translation: stop hand-rolling the analysis, run the control plane against the discoveries we now have and see what it surfaces.

Apply `feedback_arch_doc_authority.md` strictly. Don't invent knobs the doc doesn't sanction. If a control-plane operator needs a manifest + adapter to fire (per `reference_refrag_discovery_meta_tools.md`), build the manifest + adapter, don't call the operator as a plain function.

Starting points for the new chat (in topological order, all CONTROL plane):
1. **operator_lineage_tracker** — already firing implicitly via orchestrator runs; verify its state is consistent across the 1500+ runs this session generated.
2. **operator_benchmark_suite** — should ingest the per-domain summary.jsons and produce a structured benchmark report instead of the ad-hoc statistics scripts we've been writing.
3. **operator_gap_finder** — should look at the 3.1 GB of discoveries and surface what's missing (e.g., the absence of qd3set trajectories should jump out).
4. **operator_chain_builder + composability_scorer** — could surface that Markets and Quantum are running THE SAME pipeline with different scalar inputs, which is exactly what cross-domain transfer needs.
5. **cross_domain_transfer_detector** in `spectral_similarity` mode — the manual call we never got to this session. Should be one of the first things to fire.

Do NOT enable `operator_graph_rewriter` (Phase 6, doc explicitly says "must remain disabled until Phase 6. Self-rewriting systems are dangerous early").

## TL;DR

- **Quantum run completed** — `_full_pipeline_quantum/summary.json` now has all 1560 trajectories processed through the same `od_spectral_retrieval_pipeline` Markets uses.
- **Pattern is stable across the full set**: only **2 evidence-graph signatures** ((11,45) and (11,46)), 100% `spectral_target` mode, vp tightly clustered. Lambda=500 (strong system-bath coupling) is the deterministic discriminator that pushes trajectories into (11,46) with +1 edge and vp drop of ~0.07.
- **storage.py hardened**: 0-byte and corrupt-JSON files no longer crash the orchestrator. Same quarantine pattern as accumulated_evidence_graph.
- **Both adapters now flush incrementally** every 50 records via atomic tmp+replace. Future kills lose ≤50 records and never produce a 0-byte summary.json.
- **Admission gate (todo #7) verdict: NO BUG.** `avg_net_bps` is genuinely net — fees subtracted upstream at `build_live_hindsight_missed_winner_audit.py:297`. But the audit uses a **flat 10bp round-trip across all venues**, which is wrong per `feedback_fees_in_rate_analysis.md` (Bybit 4 / Coinbase 10 / Kraken 20). Flag as venue-uniform-fee bug for a follow-up.
- **live_data → archive flush** done — 18 novel bins captured from the rolling live snapshots into the durable JSONL archive.
- **$20k per-platform cap memory saved** (Greg interrupted save in prior session; saved formally this session).
- **3 OD KB seeds** written to `E:\od_autoresearch\knowledge_base\` for future autoresearch experiments to reference.

## What shipped this session

### 1. `refrag_discovery/control_plane/storage.py` — HARDENED
`load_json` now treats 0-byte files as missing AND quarantines corrupt-JSON as `<file>.invalid` instead of crashing. Same defensive pattern as `_load_accumulated_evidence_graph_state` in the orchestrator. Triggered originally by the prior session's kill leaving `od_spectral_retrieval_pipeline.json` at 0 bytes in `artifacts/control_plane/lineage/`, which crashed every single trajectory in the first restart attempt.

### 2. `adapters/quantum_refrag_adapter.py` — INCREMENTAL FLUSH + ATOMIC WRITE
- New constant `FLUSH_EVERY = 50`.
- Extracted `_build_payload(...)` helper (same for resume and fresh runs).
- New `_atomic_write_summary(...)` helper writes via `tmp + replace` so a kill never leaves a 0-byte summary.json.
- `_load_existing_summary` now also rejects 0-byte files.
- Loop writes summary every 50 trajectories AND at end.

### 3. `adapters/markets_refrag_adapter.py` — SAME PATTERN
Same `FLUSH_EVERY = 50`, same `_build_payload`/`_atomic_write_summary` helpers (Markets-specific payload keys: `session_elapsed_s` accumulator, `skipped_no_coverage` instead of quantum's `skipped_load_fail`). 0-byte guard added to `_load_existing_summary` too.

### 4. Quantum run completed
Resumed via `quantum_refrag_adapter.py --resume` after deleting the 0-byte lineage file. ~50 min total wall clock for the remaining 912 trajectories. Pace drifted 3.5 → 4.3s/traj as `policy_history.jsonl` and `execution_traces.jsonl` grew; rotation again would help next time, but for this run the wait was acceptable.

### 5. `backfill_split_to_history.py` invoked on `live_data/`
Filled 18 novel bins from the rolling 6h live snapshots into the durable JSONL archive at `live_data_history/<date>/<asset>_<venue>_bins.jsonl`. Idempotent, additive-only, no side effects on source files.

### 6. `feedback_per_platform_capital_cap.md` saved to memory
$20k start-of-day cap per trading platform. Position sizing math uses $20k as the denominator (not intraday balance). Pre-session sweep mandatory. Greg's framing: *"i don't want to be the signal."*

### 7. OD knowledge base seeds — `E:\od_autoresearch\knowledge_base\`
- `quantum_taxonomy_v1.json` — the 2-signature taxonomy + lambda=500 discriminator + per-class vp clusters.
- `cross_domain_signature_map_v1.json` — Markets vs Quantum signature comparison, the saturation overlap at 11 nodes, the vp regime gap.
- `fee_schedule_v1.json` — per-venue round-trip fees + the audit's flat-10bp finding flagged for fix.

## Key findings this session

### Admission gate verdict
- **No bug.** `match["avg_net_bps"]` is net. Fee subtraction happens upstream at [build_live_hindsight_missed_winner_audit.py:297](E:/Markets/build_live_hindsight_missed_winner_audit.py:297): `net_bps = gross_bps - (2.0 * fee_bps)` with `FEE_BPS = 5.0` → round-trip 10 bps. That value flows through the audit CSV → oracle winner list build → `match["avg_net_bps"]` → admission gate.
- **But**: the audit uses a flat 10bp ROUND-TRIP across all venues, while actuals per `feedback_fees_in_rate_analysis.md` are Bybit 4 / Coinbase 10 / Kraken 20. Net effect:
  - **Bybit admissions are too strict** — 10bp deducted vs 4bp actual → real winners get rejected.
  - **Kraken admissions are too lenient** — 10bp deducted vs 20bp actual → some that don't actually clear net get admitted.
- Recommended follow-up: per-venue fee table in the audit, not a single FEE_BPS constant.

### Quantum taxonomy across all 1560 trajectories (CONFIRMED final)
- **2 unique signatures only**: (11, 45) n=1346 (86.3%), (11, 46) n=214 (13.7%). Held across recovered 648 + new 912 — no new signatures emerged.
- **All 100% `spectral_target` mode** — no policy exploration; same as Markets.
- **All 100% twobath source kind** — zero qd3set trajectories ever appeared. The data dir does not have any `2_epsilon-*.npy` files despite the adapter's regex supporting them.
- **vp clusters**:
  - (11, 45): n=1346, vp = 0.8643 ± 0.0031. Range [0.7930, 0.8665].
  - (11, 46): n=214, vp = 0.7931 ± 0.0001. Essentially deterministic.
- **Lambda=500 (strong system-bath coupling) is the deterministic discriminator** for the (11, 46) class:
  - **100% (perfect specificity)**: all 214 (11, 46) trajectories have lambda=500.
  - **68.6% (partial sensitivity)**: of 312 lambda=500 trajectories, 214 land in (11, 46); the other 98 stay in (11, 45). Lambda=500 is necessary but not sufficient for the +1-edge signature.
  - Gamma=500 (strong damping) never appears in (11, 46) — strong damping keeps trajectories in the majority class regardless of coupling.
- **Temperature regime doesn't change the taxonomy**: Tavg span 77 → 500 produced no new signatures.
- **n_steps is None on the 648 recovered** (recovery script artifact); populated correctly on the 912 fresh ones.
- **Run completed in 4188s (~70min)** with 0 errors.

### Quantum vs Markets cross-domain
| | Markets winners | Quantum trajectories |
|---|---|---|
| n | 1690 | 1560 |
| Unique sigs | 7 | 2 |
| Dominant sig | (11, 53) 92% | (11, 45) 84% |
| Saturation cap | 11 nodes (FAISS retrieval cap) | 11 nodes (same cap) |
| Edge count of dominant | 53 | 45 |
| vp mean | ~0.31 | ~0.86 (2.7× higher) |
| Retrieval mode | 100% spectral_target | 100% spectral_target |

Both domains saturate at the 11-node FAISS retrieval cap. Edge counts differ (Markets 53, Quantum 45-46). vp regimes differ by ~2.7×. Implication for cross-domain match: the (n_nodes, n_edges) signature labels DON'T overlap, so spectral_similarity on the operator_coefficients embeddings is the only viable bridge.

## Pending todos — priority order for the next chat

### 1. Run the control-plane stack against the discoveries we have
**This is the new chat's main job.** Per the arch-map directive at the top: use lineage_tracker → benchmark_suite → gap_finder → chain_builder → composability_scorer → cross_domain_transfer_detector. Don't replicate the manual analysis we've been doing in scripts.

### 2. Cross-domain match — markets vs quantum, spectral_similarity
```python
from refrag_discovery.control_plane.cross_domain_transfer_detector import detect_cross_domain_transfer
out = detect_cross_domain_transfer(
    source_domain='markets', target_domain='quantum',
    comparison_mode='spectral_similarity', similarity_threshold=0.7,
)
print(out['source_n'], out['target_n'], len(out['transfer_candidates']))
```
This is the deferred-from-prior-session call. Should be invoked early in the new chat as part of #1.

### 3. Wire `pipeline_marker = (n_nodes, n_edges)` into Markets adapter
Greg's prior-session reframe: the 7 evidence_graph signatures ARE the pipeline's natural taxonomy. Add `pipeline_marker` field to Markets summary entries alongside `canonical_trade_key`. Both stay for traceability. Trivial change to `markets_refrag_adapter.py` build_payload.

### 4. Per-venue fee audit fix
Replace flat `FEE_BPS = 5.0` (round-trip 10) in `build_live_hindsight_missed_winner_audit.py` with per-venue table {Bybit: 2, Coinbase: 5, Kraken: 10} (one-way bps). Re-run the audit. Compare admission counts before/after.

### 5. Hyperliquid data collector
Half-day effort. New file `E:\Markets\hyperliquid_collector.py` parallel to existing perp collectors. Output schema must match `live_data_history/<date>/<asset>_hyperliquid_perp_bins.jsonl` so `markets_bar_loader` picks it up unchanged.

### 6. Hyperliquid executor + risk plumbing
After data validates. Multi-week. Must incorporate from day 1:
- `feedback_trading_visibility_opsec.md` (never #1/#worst long or short on leaderboard, top/bottom 90% OK)
- `feedback_per_platform_capital_cap.md` ($20k start-of-day cap, sized off $20k denominator)
- Separate wallet from `gergd.base.eth` (already publicly tied)

### 7. Backfill 90-day price/trade-tape history per Greg's list
Three HIGH-priority scripts exist (`backfill_coinbase_spot.py`, `backfill_kraken_spot.py`, `backfill_binance_vision.py`). Mislabel: `collect_bybit_perp_history.py` does funding+OI only, NOT price. A new `backfill_bybit_perp.py` against Bybit V5 REST `/v5/market/kline` is needed (~100-150 lines). **This is for a different chat per Greg's earlier message — don't grab it from the next refrag chat.**

## Files of interest

| Path | Role |
|---|---|
| `E:\refrag\docs\architecture_spec_v21.docx` | **THE arch map. New chat reads this first.** |
| `E:\refrag\_arch_spec_v21_extracted.txt` | Plain-text dump of the above |
| `E:\refrag\refrag_discovery\control_plane\storage.py` | **HARDENED** — 0-byte + corrupt-JSON safe |
| `E:\refrag\adapters\quantum_refrag_adapter.py` | **UPDATED** — incremental flush, atomic write |
| `E:\refrag\adapters\markets_refrag_adapter.py` | **UPDATED** — same |
| `E:\refrag\_full_pipeline_quantum\summary.json` | All 1560 quantum trajectories |
| `E:\Markets\_full_pipeline_winners\summary.json` | 1690 Markets winners (unchanged this session) |
| `E:\refrag\artifacts\discoveries\{run_id}.json` | 3200+ per-run discoveries |
| `E:\od_autoresearch\knowledge_base\quantum_taxonomy_v1.json` | **NEW** — 2-class taxonomy + lambda discriminator |
| `E:\od_autoresearch\knowledge_base\cross_domain_signature_map_v1.json` | **NEW** — Markets vs Quantum signature comparison |
| `E:\od_autoresearch\knowledge_base\fee_schedule_v1.json` | **NEW** — per-venue fees + audit flat-fee finding |

## Memory entries added this session

- `feedback_per_platform_capital_cap.md` (NEW) — $20k start-of-day cap per platform. Position-sizing math uses $20k as denominator, not intraday balance.

(All prior session entries still apply.)

## Live constraints (anti-drift — carried forward + reinforced)

- **DO** follow the arch map. Use control-plane operators instead of replicating their work in scripts.
- **DO** use `markets_bar_loader.load_closes(asset, venue, ...)` for bin reads. Never raw `live_data/*.json`.
- **DO** include venue-specific fees in any rate analysis (Bybit 4, Coinbase 10, Kraken 20bp round-trip).
- **DO** target both best long AND best short outcomes (Markets gates maximize EV).
- **DO** treat the $20k per-platform cap as a hard rule from day 1 of executor work.
- **DO** verify a `.npy` file or quoted code reference still exists before recommending action on it (memory facts can stale).
- **DO NOT** modify refrag-core (Rule 7) or refrag_discovery runtime operators (extension via new modes is fine).
- **DO NOT** invent knobs the arch doc doesn't sanction.
- **DO NOT** invoke `markets_refrag_batched_adapter.py` (neutralized in part 2).
- **DO NOT** enable `operator_graph_rewriter` (Phase 6, disabled until then).
- **DO NOT** push to git. Greg confirmed on 2026-05-24: *"don't worry about git we aren't using."* Mirror artifacts across directories (e.g., OD knowledge_base + Markets knowledge_base) rather than relying on git to distribute them. The updated `feedback_periodic_git_push.md` memory is authoritative.
- **DO NOT** appear as #1/#worst long or short on any public leaderboard.

## End of handoff

Next chat: read the arch map, then run the control plane against the discoveries this session produced. If it surfaces gaps the rest of us missed by hand, that's exactly what it's there for.
