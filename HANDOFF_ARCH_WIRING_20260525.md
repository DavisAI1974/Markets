# Handoff — Arch v2.1 phase wiring (2026-05-25, evening)

## TL;DR

Tonight's session moved the markets refrag adapter from a partial-arch single-pass run to **arch §8 Phase 1 + Phase 2 complete**. Phases 3, 4, 6 are next and have clear entry points. The 24 per-bucket JSON inputs are split and ready. The smallest bucket (`markets_eth_coinbase_sell_win`, 31 entries) runs end-to-end cleanly in ~50-75s and now lifts evidence to per-cell `_evidence.json` correctly.

## Recommended new-chat opener

> Continue arch wiring per `HANDOFF_ARCH_WIRING_20260525.md`. Phase 1 + Phase 2 done. Start Phase 3: pre-bucket Composition Loop in the adapter (call `operator_chain_builder` + `operator_composability_scorer` BEFORE the per-winner loop in `markets_refrag_adapter.py`). Read `reference_arch_doc_v21.md` first.

## What got fixed this session (in order)

### Phase 1: Foundation + Registry (FINISHED)

**File:** `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py`

Two edits:

1. **Lifecycle tracker invocation for all 8 runtime operators + pipeline.** Was: zero. Now: per-execution `operator_lifecycle_tracker` call in a loop over the runtime operator list, persisted to `artifacts/control_plane/lifecycle/<op>.json`.
2. **Benchmark suite `operator_ids` expanded.** Was: hardcoded `["retrieval_policy_learner"]` (one operator). Now: full runtime list (`spectral_chunker, spectral_chunk_encode, operator_query, retrieval_policy_learner, falsification_prioritizer, operator_decoder, evidence_graph_builder, operator_orchestrator`). This cascades — benchmark_suite triggers per-op lineage_tracker writes too.

**Verification:** ran `markets_eth_coinbase_sell_win` bucket (31 entries) end-to-end. After-run state:
- `artifacts/control_plane/lifecycle/` → 9 files (8 ops + pipeline). Was 1.
- `artifacts/control_plane/lineage/` → 8 files (all runtime ops). Was 1.

Phase 1 milestone "Operator state tracking active" now genuinely met.

### Phase 2: Core pipeline + closed-loop falsification (INFRASTRUCTURE DONE)

**Files modified:**
- `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py`
- `E:\refrag\refrag_discovery\runtime\falsification_prioritizer.py`
- `E:\refrag\refrag_discovery\runtime\operator_decoder.py`
- `E:\refrag\adapters\markets_refrag_adapter.py`

Five edits forming the arch §5 Falsification Loop:

1. **Orchestrator: closed-loop iteration block.** Replaced single-pass `for wave in execution_waves: …` with: initial full-pass, then `while not converged: re-run stages 5-9 (falsification, decoder, evidence_graph)`. Termination = **"no new coefficients produced"** (max |coef[N] - coef[N-1]| < `delta_threshold=1e-6`). `max_iterations` is a safety cap only (default 100_000), NOT the stopping criterion. Replaces the legacy `min(1, …)` cap + `"single_pass_bootstrap"` string.
2. **Orchestrator: `_run_stage["falsification_prioritizer"]`** now passes `operator_posterior=context["operator_decoder"]["coefficient_posterior"]` — closes the decoder→falsification feedback per arch §6 dep table.
3. **`falsification_prioritizer.execute()`** now USES `operator_posterior` via new `_bald_posterior_contribution()` helper (was: declared as a kwarg but never read). Implements BALD-style per-chunk uncertainty alignment per the v2 manifest's `acquisition_function="bald"` default. Term weight is `0.20 * posterior_contribution`.
4. **`operator_decoder.execute()`** now returns **non-uniform per-dim `posterior_std`** (was: uniform constant `1/N_prefill`). Heuristic: dims with larger |coefficient| get smaller std (more confident), near-zero coefs get larger std. Still a stub per arch §8 ("Deterministic stub first") but informative enough for BALD to differentiate.
5. **Adapter:** explicit `termination_config={"max_iterations": 100_000, "delta_threshold": 1e-6}`. Previously `{}` got replaced by orchestrator's `or {"max_iterations": 1}` fallback (Python empty-dict is falsy).

**Verification:** ran the small bucket. All 31 discoveries terminated at `iter=2` with `max_delta=0.0`. Loop runs, sees zero change in coefs, stops cleanly — exactly the "stop when no new ones produced" rule.

**Known gap (acknowledged in arch):** decoder is deterministic stub, so even with BALD wiring the closed loop converges fast. Per arch §8 the decoder gets the FNO upgrade after 100+ training pairs; that's when iteration variation becomes real. The infrastructure is in place to take advantage when FNO lands.

### Phase 5 partial: `task_meta_learner` already wired (kept from earlier session)

**File:** `E:\refrag\adapters\markets_refrag_adapter.py`

Per-bucket call to `run_task_meta_learner(query_mode="recommend_config", …)` BEFORE the winner loop. Returns recommended `spectral_chunker.window_size` (current: 192 vs hardcoded 32) + `operator_query.top_k` + `pipeline.expand_budget`. Adapter passes them through `task_config` to orchestrator. Confidence currently 0.58 (`heuristic_bootstrap`) — will improve as `update_from_outcome` observations accumulate.

### Per-bucket input split (DONE)

24 per-bucket JSON files at `E:\Markets\research\strategy_evolution\per_bucket\` matching `oracle_winner_trade_v1` schema:

| Layout | Counts |
|---|---|
| 12 `*_win.json` from `oracle_winner_trade_list.json` (3,415 entries total) | smallest 31 (eth_coinbase_sell), largest 523 (btc_coinbase_buy) |
| 12 `*_lose.json` from `_analysis_historical_rt_trade_shapes_20260523/per_trade.csv` filtered `net_bps < -5` (53,913 entries total) | smallest 3,121 (btc_coinbase_sell), largest 6,295 (eth_kraken_sell) |

Adapter accepts `--winner-json PATH --outcome {win,lose}`. The orchestrator's domain tag becomes `markets_<asset>_<venue>_<side>_<outcome>` and routes per-discovery JSONs + accumulated evidence to the right per-cell paths.

### Evidence-graph accumulation fix (earlier in session)

The adapter previously overrode `evidence_graph_builder.existing_graph = None` which killed the orchestrator's `setdefault` load-from-disk logic. Removed the override. Per-cell evidence graphs now ACCUMULATE across all trades in the bucket instead of holding only the last 1-2.

`markets_eth_coinbase_sell_win_evidence.json` after 31-entry run: 323 nodes / 1574 edges / 29 unique source_ids (was 11/53/2 before fix).

## Phases NOT yet wired

### Phase 3 — Composition Loop (NEXT)

**Where to wire:** `markets_refrag_adapter.py` `main()`, AFTER `task_meta_learner` call, BEFORE the per-winner loop.

**Two calls:**

```python
from refrag_discovery.control_plane import call_control_plane_operator

# Composition Loop per arch §5
chain_recommendation = call_control_plane_operator(
    "operator_chain_builder",
    {
        "task_objective": f"od_spectral_retrieval_pipeline:{bucket_tag}",
        "available_operators": _runtime_operator_ids,  # 8 runtime ops
        "constraints": {"max_chain_length": 8},
        "optimization_target": "accuracy",
        "search_mode": "mcts",
    },
)
# chain_recommendation["chain"] is list of {stage, operator_id, …}
# chain_recommendation["chain_score"] is composability-weighted

# (composability_scorer is called INSIDE chain_builder per arch §5 Composition Loop)
```

Then either use the recommended chain (replace hardcoded `pipeline_id`) OR log it and stick with `od_spectral_retrieval_pipeline` if the recommendation matches. The chain_builder code already resolves to `od_spectral_retrieval_pipeline` when "discovery" appears in the task_objective, so the practical effect is mostly logging the score + alternatives — but the Composition Loop IS engaged (chain_builder internally calls composability_scorer per pair).

### Phase 4 — Discovery Loop (after Phase 3)

**Where to wire:** `markets_refrag_adapter.py` `main()`, AFTER the per-winner loop completes (post-bucket).

**Three calls in sequence (per arch §5 Discovery Loop):**

```python
# gap_finder: identify missing capabilities given current registry
gaps = call_control_plane_operator(
    "operator_gap_finder",
    {
        "registry_snapshot": None,  # uses default registry
        "target_domains": ["operator-discovery", "markets"],
        "known_tasks": [bucket_tag],
        "depth": "geometric",
    },
)

# manifest_synthesizer: propose new operator manifests from successful execution patterns
synthesis = call_control_plane_operator(
    "manifest_synthesizer",
    {
        "execution_logs": read_jsonl(r"E:\refrag\artifacts\execution_traces.jsonl")[-200:],
        "min_occurrences": 5,
        "min_success_rate": 0.9,
        "synthesis_mode": "hybrid",
    },
)

# cross_domain_transfer_detector: find quantum↔markets correspondences
transfer = call_control_plane_operator(
    "cross_domain_transfer_detector",
    {
        "source_domain": "markets_eth_coinbase_sell_win",  # or whichever bucket
        "target_domain": "quantum_two_bath_sup_dTon",       # or whichever quantum cell has data
        "comparison_mode": "spectral_similarity",
        "similarity_threshold": 0.7,
    },
)
```

Outputs go to `discoveries/cross_domain_transfers/` (currently empty).

### Phase 6 — Governance Loop closure (after Phase 4)

**Where to wire:** `markets_refrag_adapter.py` `main()`, AFTER Phase 4 calls.

**Per-operator promotion check:**

```python
promotions = {}
for op_id in _runtime_operator_ids:
    promotions[op_id] = call_control_plane_operator(
        "operator_promotion_recommender",
        {
            "operator_id": op_id,
            "evaluation_window": "P30D",
            "include_schema_suggestions": True,
            "run_counterfactual": True,
        },
    )
```

Outputs `promotion_score`, `recommendation`, `blocking_issues` per operator. Closes the Governance Loop (benchmark_suite → lifecycle_tracker → lineage_tracker → promotion_recommender).

`operator_graph_rewriter` STAYS DISABLED per arch Rule 6 ("disabled until Phase 6 validation").

### Final consolidation (after Phase 6)

Per the workflow discussion earlier in the session:
- Build `E:\refrag\adapters\arch_workflow.py` that wraps the adapter as the SINGLE entry point. Pre-bucket: Phase 3. Per-winner: orchestrator (which handles Phase 2 + Phase 5 internally). Post-bucket: Phase 4 + Phase 6.
- Add memory note `reference_arch_workflow.md` saying "always run arch via `arch_workflow.py`; don't call orchestrator directly for production runs."

## Files modified this session

| File | What changed |
|---|---|
| `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py` | Phase 1 lifecycle bootstrap loop + Phase 2 closed-loop block + benchmark_suite operator_ids expansion + falsification gets operator_posterior |
| `E:\refrag\refrag_discovery\runtime\falsification_prioritizer.py` | `_downsample_to` + `_bald_posterior_contribution` helpers; info_gain uses BALD term |
| `E:\refrag\refrag_discovery\runtime\operator_decoder.py` | Non-uniform per-dim `posterior_std` (heuristic stub) |
| `E:\refrag\adapters\markets_refrag_adapter.py` | `--winner-json` + `--outcome` args, `winner_domain()` helper, granular domain routing, meta-learner call, explicit termination_config, removed `existing_graph=None` override |
| `C:\Users\A\.claude\projects\E--\memory\reference_arch_doc_v21.md` | NEW — canonical arch doc reference |
| `C:\Users\A\.claude\projects\E--\memory\MEMORY.md` | Added reference_arch_doc_v21 entry |

## Files NEW this session (data/inputs only)

- `E:\Markets\research\strategy_evolution\per_bucket\markets_<asset>_<venue>_<side>_<win|lose>.json` × 24

## Things explicitly NOT done (per arch / per Greg's calls)

- `operator_graph_rewriter` — disabled per arch Rule 6 until Phase 6 validation
- FNO upgrade on `operator_decoder` — arch §8 says "after 100+ training pairs"
- Re-running the full 3,415-winner sweep — paused at 350/3553 earlier in session, resumable with `--resume`
- Legacy no-suffix cells cleanup (`markets_btc_bybit_buy/` and `markets_btc_bybit_sell/` with 820 stale files) — flagged but Greg said "leave in separate bucket"

## Run knobs that work today

```bash
# smallest bucket smoke (31 entries, ~50-75s, all phases 1-2 active):
cd E:/refrag && python adapters/markets_refrag_adapter.py \
  --winner-json E:/Markets/research/strategy_evolution/per_bucket/markets_eth_coinbase_sell_win.json \
  --outcome win \
  --out-dir E:/Markets/per_bucket_runs/markets_eth_coinbase_sell_win

# resume the paused full run from earlier in session:
cd E:/refrag && python adapters/markets_refrag_adapter.py \
  --resume \
  --out-dir E:/Markets/_full_pipeline_winners_20260525
```

## Background state at end of session

- `run_complete.py` started ~3-4 hours ago, may or may not still be running. Check with `tasklist | grep python`.
- The other chat (per Greg's note "his runs are much smaller") may also be active in refrag. Coordinate before any heavy run.

## End of handoff

Phase 1 + Phase 2 are arch-complete. Phase 3 is the next discrete unit (Composition Loop in adapter, ~20 lines). Phase 4 + Phase 6 follow the same pattern. Final step is consolidating into `arch_workflow.py` so future runs don't accidentally skip phases. The work is laid out — no more guessing what to call when.
