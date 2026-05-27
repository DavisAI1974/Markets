# Handoff — Full Pipeline Adapter (2026-05-24)

## TL;DR

Markets refrag adapter shipped at `E:\refrag\adapters\markets_refrag_adapter.py`. Bridges all 1600 entries of `oracle_winner_trade_list.json` to refrag's 8-runtime-operator pipeline (`od_spectral_retrieval_pipeline`) via log_returns. Smoke test NOT yet run — next chat's first action. Bin coverage problem from earlier in the session was a directory mistake: use `E:\Markets\live_data\` (fresh), not `E:\Markets\` root (stale).

**Architect review completed and 2 must-do fixes applied** (see ARCHITECT REVIEW section below). Adapter is ready for smoke test as-is.

## Recommended new-chat opener

> Run the smoke test for the full-pipeline adapter:
> `python E:\refrag\adapters\markets_refrag_adapter.py --smoke`
> Check `E:\Markets\_full_pipeline_winners\summary.json` for 10 results, no errors, sensible validity probabilities. If clean, run full 1600.

## What shipped this session

### 1. `E:\refrag\adapters\markets_refrag_adapter.py` (NEW, ~250 lines)
The single adapter file. Loads winner JSON, loads bars from `live_data/`, per-winner slices bars by `[entry_ts_utc, entry_ts_utc + horizon_minutes*60]`, converts to log_returns, calls `OperatorOrchestrator.execute(pipeline_id="od_spectral_retrieval_pipeline")`. Persists summary at `E:\Markets\_full_pipeline_winners\summary.json`. Per-run discoveries auto-persist at `E:\refrag\artifacts\discoveries\{run_id}.json` (orchestrator default).

Flags: `--smoke` (10 winners), `--limit N`, `--out-dir PATH`.

Pipeline config (chosen, can revisit):
- chunker: window_size=32, stride=16, min_segment_length=16
- query_mode: from_spectral_target, target_frequencies=[0.1, 0.25], target_energy=1.0
- top_k=8, expand_budget=4
- max_iterations=1 (single pass, not the full closed loop)

### 2. Memory updates (3 entries)
- `reference_refrag_discovery_meta_tools.md` (NEW) — refrag_discovery operators are registry-bound meta-tools; need manifest+adapter pair to execute, not directly callable.
- `project_markets_bin_coverage_gap.md` (NEW initially, then UPDATED) — the bin gap from earlier in the session was a directory mistake; live_data/ has fresh bins.
- `project_markets_funding_oi_join_broken.md` (NEW) — cross-venue funding/OI join bug; fix before any future stack-feature analysis.

## Active PIDs to preserve (do not kill)

Verify at chat start with `Get-Process` / `ps -ef | grep python`:
- **PID 76100** — `hindsight_worker` (keeps winner JSON fresh; without it the input goes stale)
- **PID 89876** — `wilson`
- **PID 96124** — `protective`
- **PID 102120** — `in_flight_promote`

(These were carried over from prior session's handoff `HANDOFF_SESSION_20260524_OPERATOR_GAP_AUDIT.md`. If any has died, note it before restarting — they may have been intentionally stopped.)

## Open work — priority order

### 1. Smoke test (immediate, ~30-60s)
```
python E:\refrag\adapters\markets_refrag_adapter.py --smoke
```
Validate `summary.json` has:
- 10 results
- errors == 0
- `validity_probability` not all 0 or all 1 (would indicate degenerate decoder/evidence_graph)
- `pipeline_latency_s` < 5s per run (sanity)
- `n_log_returns` ≥ 16 on all 10
- `selected_retrieval_mode` populated

If anything degenerate, debug the adapter's data path before scaling. Likely issues if smoke fails:
- `load_closes` not handling some bar's price field → returns empty
- `data_sources` shape wrong → orchestrator raises in stage 1
- Pipeline DAG resolution fails → check `operator_query.resolve_pipeline_dag("od_spectral_retrieval_pipeline")` against the manifest at `E:\refrag\manifests\od_spectral_retrieval_pipeline.v2.json`

### 2. Full 1600-winner run
```
python E:\refrag\adapters\markets_refrag_adapter.py
```
Expected runtime: 30-90 min (smoke will reveal per-run latency to extrapolate). Consider `run_in_background` if >15 min. Persistence is per-run so partial runs leave usable state.

### 3. Aggregate analysis (separate script, not yet written)
Read summary.json + per-run discoveries, produce:
- **Prototype operator coefficients** per `(asset, venue, side)` — mean + std across winners in each cell
- **Validity probability distribution** — winners SHOULD cluster high. Outliers (low validity_probability) are "lucky winners" that don't share archetype with the rest.
- **Cross-trade evidence graph similarity** — find clusters of trades whose evidence graphs overlap (shared archetype signal)
- **`canonical_trade_key × validity` heat map** — does the canonical key partition match the validity partition? If yes, our keys are already capturing the archetype. If no, the pipeline is finding structure the keys don't.
- **`strategy_id × horizon × validity`** — does any strategy/horizon combo systematically score low validity? Those are the strategies that produce "non-archetypal winners" — possibly noise or possibly novel patterns.

### 4. Then decide extensions
- **Multi-channel `data_sources`** — send `{src: log_returns, src+":dipole": dipole_stream, src+":signed_vol": signed_volume}` so the pipeline sees microstructure too. Cleaner than substituting MarketChunker.
- **Per-canonical-key batched runs** — instead of 1600 single-trade runs, do 32 runs (one per context_key) feeding all the key's trades as separate data_sources to a single orchestrator call. Pools evidence; faster.
- **Live in-flight prediction** — the actual destination. Once we have winner archetype library + per-trade decoded operators, an in-flight trade gets chunked on entry, queried against the index, returns operator_validity_probability as a real-time "is this a winner?" score.

## Critical context (everything next chat needs to be efficient)

### Data sources
- **Winner JSON**: `E:\Markets\research\strategy_evolution\oracle_winner_trade_list.json`
  - Schema: dict with `entries` key (list of 1600 trade dicts)
  - Each entry: `source_id`, `asset` (BTC/ETH only), `venue` (Bybit/Coinbase/Kraken), `side` (buy/sell), `canonical_trade_key`, `entry_ts_utc` (float UTC seconds), `horizon_minutes` (float), `net_bps`, `strategy_id`, `merged_duplicate_sources` (list), plus trade-context fields (chunk_id, mean_dipole, dipole_acl1, volume_zscore, etc.)
  - Generated 2026-05-24 02:48:28 UTC by hindsight_worker
  - Timestamp range: 2026-05-23 20:44 → 2026-05-24 02:39 UTC (~6 hours of trades)
  - Schema id: `oracle_winner_trade_list_v1`

- **Bars**: `E:\Markets\live_data\*_bins.json` — 5 assets × 3 venues, dict-keyed by ts_str
  - First ts: ~2026-05-23 21:00 UTC → entries from 20:44-20:59 (~75 min) won't have coverage
  - Bar fields: `mid, high, low, buy, sell, n_trades, bid, ask, bid_qty, ask_qty, last_aggressor`
  - Irregular spacing (~1-6s per bar)

### Architecture choices made

| Choice | Why |
|---|---|
| Single-channel (log_returns only) | First pass simplicity. Pipeline is domain-agnostic on floats. |
| Per-trade execution (not batched) | Clean per-winner attribution. 1600 separate discoveries. |
| Use refrag's `spectral_chunker` (not MarketChunker) | Greg's direction: "we have all the files" — keep it minimal, no new orchestrator subclass. |
| pipeline_id="od_spectral_retrieval_pipeline" (existing manifest) | No new manifest needed; the OD pipeline DAG works for any 1D float stream. |
| max_iterations=1 | Single forward pass through stages 1-9. Closed loop disabled until we know baseline behavior. |
| query_mode="from_spectral_target" with [0.1, 0.25] | Generic probe; no markets-specific prior. Revisit if results lack signal. |

### Scope from architecture v2.1 paper

We're doing **the full runtime plane** = 8 runtime operators:
1. `spectral_chunker` (Representation)
2. `spectral_chunk_encode` (Representation)
3. `operator_query` (Registry)
4. `retrieval_policy_learner` (Execution)
5. `evidence_graph_builder` (Execution)
6. `falsification_prioritizer` (Evaluation)
7. `operator_decoder` (Representation)
8. `operator_orchestrator` (Orchestration)

Plus refrag-core primitives (`MLPProjector`, `FaissIndex`, `SimilaritySelector`, `build_mixed_prompt`, `ChunkEmbeddingCache`) called by the runtime operators internally.

Greg's framing that crystallized: RT Markets ALREADY has both runtime/control planes — the live mock RT engine + in-flight ops are runtime; the hindsight worker + winner curation + strategy evolution are control. Refrag formalizes this via `execution_class` on every manifest. We're building the runtime-plane integration.

## Files of interest

| Path | Role |
|---|---|
| `E:\refrag\adapters\markets_refrag_adapter.py` | **NEW** — the adapter shipped this session |
| `E:\refrag\adapters\od_refrag_adapter.py` | Reference template (OD pattern) |
| `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py` | The orchestrator we call |
| `E:\refrag\refrag_discovery\runtime\*.py` | 8 runtime operator implementations |
| `E:\refrag\manifests\od_spectral_retrieval_pipeline.v2.json` | The pipeline DAG manifest |
| `E:\refrag\manifests\*.v2.json` | 22 total: 21 operators + 1 pipeline template |
| `E:\refrag\artifacts\discoveries\{run_id}.json` | Per-run discoveries (orchestrator writes) |
| `E:\Markets\markets_adapter.py` | Markets primitives (MarketChunker etc) — preserved for future use, NOT in current pipeline path |
| `E:\Markets\markets_refrag_winner_index.py` | Prior partial Layer-1-only script (chunker+encoder only) |
| `E:\Markets\research\strategy_evolution\oracle_winner_trade_list.json` | Winner JSON input (1600 entries) |
| `E:\Markets\live_data\*_bins.json` | **USE THESE** — fresh bins |
| `E:\Markets\*_bins.json` (root) | STALE — do not use |

## ARCHITECT REVIEW (post-build, fixes applied)

`feature-dev:code-architect` reviewed the adapter end-to-end against the orchestrator, manifests, and v2.1 architecture rules. Findings:

### Validated (no changes needed)
- Pipeline wiring is correct: `orch.execute()` signature, `data_sources` shape, `task_config` keys, result-extraction paths all match the orchestrator's expectations.
- Plane separation clean — adapter only calls `OperatorOrchestrator.execute()`, no direct reach into refrag_core or refrag_discovery operators.
- Adapter location (`E:\refrag\adapters\`) matches the existing `od_refrag_adapter.py` pattern.
- `max_iterations=1` is functionally fine — the current orchestrator implementation is single-pass DAG anyway; `max_iterations` only affects trace metadata.

### Must-do fixes — APPLIED in this session
1. **`MIN_RETURNS = 16` → `MIN_RETURNS = 32`** (matching `CHUNKER_WINDOW_SIZE`).
   - Bug: the sliding-window chunker silently produces ZERO chunks if input length < window_size. Trades with 16-31 log_returns would reach the chunker and emit empty output → `operator_coefficients=[0.0]`, empty evidence graph, garbage validity_probability — with NO exception raised. Hardest class of bug to detect post-hoc.
   - Fix: `MIN_RETURNS` constant is now bound to `CHUNKER_WINDOW_SIZE` so changing one always updates both. Trades with <32 log_returns get correctly skipped at the `n_skipped_too_short` counter.

2. **`evidence_graph_builder.existing_graph = None`** added to `task_config`.
   - Bug: by default the orchestrator calls `_load_accumulated_evidence_graph_state(pipeline_id)` and merges it into every run's graph via `setdefault("existing_graph", ...)`. For 1600 sequential per-trade runs this means run N's evidence graph contains evidence from runs 1..N-1 → per-trade attribution is contaminated, `evidence_graph_n_nodes` grows monotonically across runs (meaningless metric), and per-run discovery files in `artifacts/discoveries/{run_id}.json` bloat to 10s of MB by the end.
   - Fix: explicitly setting `existing_graph: None` bypasses the `setdefault` and gives each trade an isolated evidence graph. Per-trade attribution restored; discovery files stay compact.

### Known risks — DO NOT yet fixed; monitor or address in next chat

3. **`policy_history.jsonl` read-back-and-rewrite at scale.** Orchestrator re-reads the full JSONL after every run to rebuild `retrieval_policy_benchmark.json`. At run 1600 that's a 1600-line read+rewrite per run. Tail latency will inflate vs early runs, which corrupts the efficiency-component of the policy reward signal. Not a smoke-test blocker but distorts cross-run benchmarks. Fix later: batch-write the benchmark once at end-of-run, not after every trade.

4. **`validity_probability` may be near-uniform / uninformative.** The evidence_graph_builder's `operator_validity_posterior` formula depends heavily on node/edge count. With ~7-bar/min live_data bars and 5-30 min trade horizons, most winners produce 1-3 chunks → small graphs → posterior dominated by "how many chunks" rather than archetype signal. Watch the validity_probability distribution in the smoke output: if it's tightly clustered or perfectly correlated with `n_log_returns`, the signal is dimensional rather than semantic. Mitigation: switch to per-batch (group by `canonical_trade_key`) runs so each evidence graph has more nodes to reason over.

5. **Console output of skipped counts is misleading.** Adapter loops by (asset, venue) group and breaks at `n_processed >= max_winners` per group. On `--smoke` if the first group has high `skipped_no_coverage`, you might see e.g. `processed: 10, skipped_no_coverage: 47` and conclude coverage is bad. It's just that the smoke cap hit before exhausting other groups. Real coverage check requires running without cap or using `--limit 1600`.

### Recommended (not blocking)

- **Add a pre-flight DAG print.** ~10 lines before the main loop: `print(orch.operator_query.resolve_pipeline_dag("od_spectral_retrieval_pipeline"))`. Catches "pipeline_id not found in registry" before the first trade fires. Cheap insurance for the next developer.

### Rules check (v2.1 architecture paper)
- **Rule 1 Plane separation:** clean (adapter only talks to orchestrator)
- **Rule 2 Registry through operator_query:** clean (orchestrator mediates)
- **Rule 3 Deterministic-first:** mild caveat — retrieval_policy_learner reads `policy_history.jsonl` so run order affects individual results. Fine for winner analysis but be aware results aren't perfectly reproducible if you re-run in different order.
- **Rule 4 Refrag-core untouched:** clean
- **Rule 7 Refrag-core stays untouched:** clean

### Domain marker (cosmetic)
Orchestrator hardcodes `domain: "operator-discovery"` in telemetry routing (line ~255 of `operator_orchestrator.py`). Our runs will show as OD-domain in `task_meta_learner` records. Pure observability issue, not functional. Fixing requires either a new markets pipeline manifest with `domain: "markets"` OR patching the orchestrator constructor — both out of scope for first pass.

---

## Anti-drift checklist

- **Do NOT use stale bins** at `E:\Markets\*_bins.json` root. Use `E:\Markets\live_data\` only.
- **Do NOT modify refrag-core or refrag_discovery operators**. The adapter pattern IS the integration point.
- **Do NOT add MarketChunker/MarketChunkEncoder to the orchestrator path in v1.** First pass is log_returns through refrag's chunker. Switch only if smoke + full run results justify the rebuild.
- **Do NOT skip the smoke test.** 30 seconds to validate the data path saves 30+ minutes of bad full runs.
- **Do NOT push to git without explicit ask.** Greg's standing rule.
- **DO commit locally periodically** (Greg works from phone; mid-session checkpoints help — per `feedback_periodic_git_push.md`).
- **DO verify PIDs at chat start** before any action that touches RT state.
- **The 92.6%-on-disagreements number from prior session is small-sample.** Don't anchor the full pipeline's value on beating it. Full pipeline's value is calibrated uncertainty + evidence graph + cross-trade discovery, not just incremental accuracy.

## Memory entries (this session)

- `reference_refrag_discovery_meta_tools.md` (NEW)
- `project_markets_bin_coverage_gap.md` (NEW → UPDATED)
- `project_markets_funding_oi_join_broken.md` (NEW)

## Why this is the right move (summary of reasoning)

Greg's vision is: build winner archetype library via full pipeline → use it for in-flight prediction on new trades. The full 10-stage pipeline produces per-trade `{operator_coefficients, posterior, evidence_graph, validity_probability}` — every one of those is an input the live prediction loop needs. Layer-1-only (the prior `markets_refrag_winner_index.py` output) gives you the indexed library but not the validity-decoder machinery. The full pipeline gives both. Once the library is built, in-flight prediction is a fourth file (later): chunks the in-flight trade, queries against the index, returns validity_probability in real time.

The full pipeline runs per-winner here because we're in control-plane mode (offline discovery on accumulated winners). At inference time it'll run per-trade in runtime mode. Same operators, different deployment context — exactly what the v2.1 plane separation enforces.

---

End of handoff. Next chat: run the smoke test, validate, then full 1600, then aggregate.
