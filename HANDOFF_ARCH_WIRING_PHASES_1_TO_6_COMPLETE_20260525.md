# Handoff — Arch v2.1 Phases 1-6 wiring COMPLETE (2026-05-25 late evening)

## TL;DR

All six arch §8 phases are now wired into the production adapter at
`E:\refrag\adapters\markets_refrag_adapter.py` (alias: `arch_workflow.py`).
This session closed the two `chain_builder` arch-§6 dep gaps (lineage_tracker
+ task_meta_learner), wired Phase 4 (Discovery Loop), wired Phase 6
(Governance Loop closure), and fixed the stale `_DISCOVERIES_DIR` path in
`cross_domain_transfer_detector.py`. `operator_graph_rewriter` STAYS DISABLED
per arch Rule 6.

**No smoke test was run this session** (Greg's call — postponed). Two read-only
review agents (code-reviewer for arch v2.1 compliance; debugger for bug hunt)
were spun up in background at end-of-session — their reports land in this
turn's transcript and should be the first thing reviewed in the next chat.

## Recommended new-chat opener

> Continue from `HANDOFF_ARCH_WIRING_PHASES_1_TO_6_COMPLETE_20260525.md`.
> All Phases 1-6 are wired in `markets_refrag_adapter.py` but the debug
> agent found three HIGH-priority bugs to fix before any production run:
> H1 (Phase 6 lineage corruption), H2 (closed-loop runaway risk), H5
> (Phase 4 exception leaves stale summary.json). Fix those first. Read
> the "Critical findings" section below + the `reference_arch_workflow.md`
> memory note. Then smoke test `markets_eth_coinbase_sell_win` (31
> entries, ~50-75s).

## Critical findings from debug agent (read FIRST)

**Three HIGH-priority bugs** to fix before any production run:

### H1. Phase 6 corrupts lineage history (silent data integrity bug)

`operator_promotion_recommender.py:21-25` calls `track_operator_lineage`
with the manifest version every Phase 6 invocation. Inside
`operator_lineage_tracker.py:289` (`versions[version] = record`) and `:291`
(`history.append`), each call APPENDS a `lineage_registered` event to
`history` and overwrites the version record's `recorded_at`. The adapter
loops over all 8 runtime operators × every bucket × every adapter
invocation, so **history grows unboundedly with duplicate events for the
same version string**.

**Fix direction**: either add a `read_only=True` mode to
`track_operator_lineage` (preferred), or refactor `recommend_operator_promotion`
to read lineage state from disk directly (via `operator_state_path` +
`load_json`) instead of calling the write-side function.

### H2. Closed-loop falsification can spin to safety cap (multi-hour stall risk)

`operator_orchestrator.py:194` sets `max_iterations=100_000` from the
adapter; `:214` loops while strictly below it. `last_delta` is only updated
when `prev_coefficients` is non-empty AND `len` matches (`:230`). **If
`prev_coefficients` stays empty (decoder returns 0 coefficients on
degenerate input) OR coefficient length flips between iterations,
`last_delta` is never recomputed, stays `float("inf")`, and the loop runs
99,999 times before hitting the cap.** Each iteration re-runs falsification
→ decoder → graph_builder (multi-second). Worst case: hours per winner.

**Fix direction**: reset `last_delta` defensively each iteration; OR break
out if `prev_coefficients` stays empty for N consecutive iterations
(decoder degenerate); OR check decoder return before continuing the loop.

### H5. Two-stage summary write leaves stale partial state if Phase 4 throws

`markets_refrag_adapter.py:550` writes `summary.json` with only
`phase3_chain_builder` in `control_plane_phases`. If any Phase 4 or
Phase 6 call raises, the final write at `:687` never runs and
`summary.json` permanently advertises Phase 3 only. No `try/finally`
guards the final write.

**Fix direction**: wrap Phase 4 + Phase 6 in `try/finally` so the final
write always happens with whatever phases succeeded.

### Medium-priority findings (M1-M7)

- **M1**: `_lineage_summary_for_step` defensive: handle non-dict `versions`
- **M2**: Adapter assumes `result["retrieval_policy"]` has `.get` — unguarded
- **M3**: `_resolve_domain_summary_path` returns Windows-backslash string
- **M4**: `_load_existing_summary` swallows JSON errors but `KeyError` on
  missing `trade_source_id` in resume crashes
- **M5**: Empty `noise_sample` denominator + falls back to 32/16 chunker
  default that the comment warns produces identical coefficients
- **M6**: Quarantined evidence-graph state returns `graph=None` to builder,
  which then builds from scratch — same regression class as the
  2026-05-25 evidence-graph bug
- **M7**: Cross-domain detector `top_k=8` hardcoded; meta-learner
  recommendation doesn't flow in despite the comment claiming so

Plus 6 low-priority findings (L1-L6) around case-sensitivity edges,
init-time edge cases, race conditions on append-only JSONL files, and
mkdir race-safety on Windows.

## Critical findings from arch-compliance agent (read SECOND)

### CRITICAL — Rule 1 Plane Separation BREACHED

**File:** `operator_orchestrator.py:371, 381, 400, 424, 452, 462`

The runtime orchestrator fires **six control-plane operators** inside every
per-winner `execute()` call: `operator_lifecycle_tracker`,
`operator_lineage_tracker`, `task_meta_learner`,
`operator_benchmark_suite` (with `benchmark_mode="full"`),
`pipeline_performance_optimizer`, `exploration_policy_controller`.

Arch §1 + Rule 1: "Engineers must never call a control plane operator
from within a runtime pipeline execution." Arch §2 narrows the
orchestrator's legitimate control-plane touches to **lineage_tracker
queries (best version per slot) + trace writes** — NOT invoking benchmark
sweeps, optimizers, or exploration controllers per run.

**This is a pre-existing violation** (from the Phase 1+2 session, not
introduced by today's Phase 3/4/6 work) but it's a serious arch contract
break.

**Fix direction**: Move `benchmark_suite`, `pipeline_performance_optimizer`,
`exploration_policy_controller`, and per-call `task_meta_learner.update`
out of the orchestrator and into a new **post-bucket Phase 5 block in
the adapter** (between the per-winner loop and Phase 4). The orchestrator
may keep: (a) `lineage_tracker` writes (Rule 3 allowlist), (b)
`lifecycle_tracker` state init, (c) a trace queue the adapter drains.

### HIGH — Rule 10: orchestrator picks versions from manifest, not lineage

`operator_orchestrator.py:151-154`: `resolved_versions` is derived from
manifest `lineage.version` directly. Arch §2 says orchestrator "queries
the lineage tracker for best version per slot." Should consume
`phase3_chain["chain"][i]["lineage"]["current_best_version"]` (already
computed by the chain_builder gap-1 fix this session) via task_config.

### HIGH — §6 dep: cross_domain_transfer_detector ignores evidence_graph

`cross_domain_transfer_detector.py:51-155`: spectral_similarity mode only
loads `operator_coefficients` (decoder output), never reads
`result.evidence_graph` or the accumulated `<domain>_evidence.json`. Half
the arch §6 declared dep is unwired.

**Fix direction**: add an evidence-graph similarity component (node-set
Jaccard or supports/contradicts ratio diff) into `_spectral_similarity_mode`,
weighted into the candidate score. OR drop `evidence_graph` from the
manifest deps.

### HIGH — §6 dep: manifest_synthesizer ignores lifecycle_tracker

`manifest_synthesizer.py:10-34`: arch §6 row 10 declares the sole upstream
dep is `lifecycle_tracker`. Implementation never reads lifecycle state.
Pattern mining over execution_logs ignores whether stages were
`experimental` / `beta` / `deprecated`.

**Fix direction**: filter `successful_sequences` to chains where every
stage's lifecycle state ≥ `beta`, OR weight `confidence_per_proposal` by
lifecycle maturity.

### HIGH — Phase 5 sequence missing pre/post-bucket

Adapter currently calls `task_meta_learner.recommend_config` pre-bucket
(line 349) but never invokes the full §5 Self-Optimization Cycle
(`benchmark → task_meta_learner → exploration → optimizer →
graph_rewriter[disabled] → benchmark`) as a sequence at the bucket
boundary. The orchestrator fires those operators per-winner (the Rule 1
violation above), but that's the wrong place.

**Fix direction**: after per-winner loop, before Phase 4, add a Phase 5
block calling `operator_benchmark_suite` once over the bucket's
accumulated traces, then `task_meta_learner.update_from_outcome`, then
`exploration_policy_controller`, then `pipeline_performance_optimizer`.

### MEDIUM findings

- **chain_builder default search_mode is "mcts"** (`operator_chain_builder.py:68`).
  Contradicts arch §8 Phase 3 + Rule 5. Adapter overrides to "exhaustive"
  but any other caller gets MCTS without the 200-trace gate. Default
  should be "exhaustive".
- **chain_builder.gap_finder is conditional-only** — only called when
  `constraints["required_operators"]` names absent ops. Arch §6 lists
  gap_finder as an unconditional upstream dep. Should run every chain
  build to influence chain_score.
- **Phase 6 promotion eval includes orchestrator + operator_query**
  (`markets_refrag_adapter.py:94, 659`). Arch §2 marks orchestrator
  `experimental`; promoting it on per-bucket cadence misclassifies. Drop
  `operator_orchestrator` and `operator_query` from the Phase 6 candidate
  set — restrict to the 6 discovery-relevant runtime ops.

### LOW

- Phase 3 task_objective bucket tag is decorative (the "discovery"
  substring short-circuits resolve to canonical pipeline regardless of
  bucket).

### What the arch agent confirmed CORRECT

- chain_builder gap-1 + gap-2 fixes from this session (composability_scorer
  per-pair, lineage_snapshot, task_meta_learner_recommendation modulation)
  are all properly wired.
- Pre-bucket `task_meta_learner.recommend_config → chain_builder →
  per-winner loop` honors Rule 10.
- Per-winner closed-loop falsification implements §5 Falsification Loop
  with coefficient-delta termination.
- `graph_rewriter` never executed in production (Rule 6 honored).
- Evidence graph per-domain accumulation honors arch §4.

## Combined priority order for next session

1. **CRITICAL** — Fix orchestrator Rule 1 plane-separation breach (move
   benchmark/optimizer/exploration/meta_learner.update out to a new
   adapter post-bucket Phase 5 block)
2. **HIGH (debug H1)** — Stop Phase 6 from corrupting lineage history
3. **HIGH (debug H2)** — Add closed-loop safety to prevent 100k-iter spin
4. **HIGH (debug H5)** — Add try/finally to Phase 4/6 so summary writes
5. **HIGH (arch)** — Wire orchestrator's `resolved_versions` to lineage's
   `current_best_version` per chain step
6. **HIGH (arch)** — Have `cross_domain_transfer_detector` consume
   evidence_graph
7. **HIGH (arch)** — Have `manifest_synthesizer` consume lifecycle_tracker
8. **HIGH (arch)** — Add explicit Phase 5 pre/post-bucket block in adapter
9. **MEDIUM** — chain_builder default to "exhaustive", make gap_finder
   unconditional, drop orchestrator+operator_query from Phase 6 eval
10. **THEN** smoke test the small bucket

## Wiring status (Phases 1-6 — all WIRED except graph_rewriter)

| Phase | Where wired | Operators | Mode (Rule 5 deterministic baseline) |
|---|---|---|---|
| 1 | orchestrator-internal | lifecycle_tracker, lineage_tracker | per-call, all 8 runtime ops + pipeline |
| 2 | orchestrator-internal | closed-loop falsification (decoder ↔ falsification_prioritizer ↔ evidence_graph_builder) | delta_threshold=1e-6, max_iter=100_000 safety cap |
| 3 | adapter pre-bucket | operator_chain_builder (internally calls composability_scorer per pair; consumes lineage_snapshot + task_meta_learner_recommendation per §6 deps) | search_mode="exhaustive" |
| 4 | adapter post-bucket | operator_gap_finder, manifest_synthesizer, cross_domain_transfer_detector | depth="surface_type_coverage", synthesis_mode="pattern_mining", comparison_mode="spectral_similarity" |
| 5 | mix | task_meta_learner (pre + per-winner), benchmark_suite, pipeline_optimizer, exploration_controller | heuristic_bootstrap when no data |
| 6 | adapter post-bucket | operator_promotion_recommender per runtime op | evaluation_window="P30D" |

`operator_graph_rewriter` (Composition capstone, depth-4 in arch §6) STAYS
DISABLED per arch Rule 6 ("Reversible Graph Modifications" — max 15%
disruption per pass, approval tokens required) until Phase 6 promotion data
has accumulated and been reviewed.

## What got done this session (chronological)

### 1. Re-read the canonical arch spec
- Canonical text: `E:\refrag\_arch_spec_v21_extracted.txt` (verified matches
  `C:\Users\A\Downloads\architecture_spec_v21 (1) (2).docx`)
- Memory summary: `reference_arch_doc_v21.md`

### 2. Phase 3 wiring (Composition Loop)
- Added `from refrag_discovery.control_plane import call_control_plane_operator`
  + `from refrag_discovery.control_plane.storage import load_json, operator_state_path`
  to adapter imports
- Added `_RUNTIME_OPERATOR_IDS` module-level constant (8 ops per arch §1.1)
- Pre-bucket call to `operator_chain_builder` with:
  - `task_objective="od_spectral_retrieval_pipeline:discovery:<bucket_tag>"`
    (the "discovery" substring triggers the canonical-pipeline resolve path
    at `operator_chain_builder.py:27-28`)
  - `available_operators=_RUNTIME_OPERATOR_IDS`
  - `search_mode="exhaustive"` (arch §8 Phase 3 + Rule 5)
  - `lineage_snapshot=<read from registry/lineage/*.json>` (gap 1 closure)
  - `task_meta_learner_recommendation=meta` (gap 2 closure)
- Output → `<out-dir>/control_plane/phase3_chain_builder.json`

### 3. chain_builder gap fixes (arch §6 dep table compliance)

**Gap 1: lineage_tracker dep not honored.** Arch §6 declares chain_builder
depends on lineage_tracker, but the implementation didn't read lineage state.

**Fix:** Added `lineage_snapshot: dict[str, dict] | None` kwarg to
`build_operator_chain`. New helper `_lineage_summary_for_step` extracts
`latest_version` and `current_best_version` (the highest-`overall_score`
version across saved records). Each chain step now carries a `lineage`
field. Output gains a `lineage_summary` block counting
`stages_with_lineage / total_stages`. Adapter reads lineage state from
`E:\refrag\registry\lineage\<op_id>.json` via `operator_state_path` +
`load_json` (storage helpers).

**Gap 2: task_meta_learner output not consumed.** Arch §6 declares
task_meta_learner feeds chain_builder, but the implementation didn't read
the meta-learner output.

**Fix:** Added `task_meta_learner_recommendation: dict | None` kwarg. If
provided with a `recommended_configuration.confidence` value, chain_builder
computes a new `task_meta_learner_modulated_score` =
`chain_score * confidence + 0.5 * (1 - confidence)`. The raw `chain_score`
is preserved for audit. The full meta input echoes back as
`task_meta_learner_input`.

Both kwargs are optional — legacy callers (none in tree) still work.

### 4. Phase 4 wiring (Discovery Loop)

Adapter post-bucket calls, in order:

```python
gap_finder(depth="surface_type_coverage",
           target_domains=["operator-discovery", "markets"],
           known_tasks=[bucket_tag])

manifest_synthesizer(execution_logs=<last 200 lines of execution_traces.jsonl>,
                     min_occurrences=5, min_success_rate=0.9,
                     synthesis_mode="pattern_mining")

cross_domain_transfer_detector(source_domain=bucket_tag,
                               target_domain=<opposite-outcome bucket>,
                               comparison_mode="spectral_similarity",
                               similarity_threshold=0.7)
```

The opposite-outcome bucket is computed automatically:
`markets_eth_coinbase_sell_win → markets_eth_coinbase_sell_lose` (and vice
versa). If the opposite bucket has no prior run, the detector returns
`insufficient_signal` cleanly.

All three outputs → `<out-dir>/control_plane/phase4_*.json`.

### 5. cross_domain_transfer_detector bug fix (independent of Phase 4 wiring)

- `_DISCOVERIES_DIR` was pointing to the stale `E:\refrag\artifacts\discoveries`
  (which doesn't exist post-Phase-1). Now points to the arch §4 production
  layout: `E:\refrag\discoveries\operator_discoveries\`
- Added `_resolve_domain_summary_path` helper. Resolves:
  1. Coarse domains (`markets`, `quantum`, `spin_boson`) → static registry
  2. Granular markets cells (`markets_<asset>_<venue>_<side>_<outcome>`) →
     `E:\Markets\per_bucket_runs\<bucket>\summary.json`
  3. Unknown → returns None (caller falls back to empty)
- `_load_domain_vectors` now constructs the discovery path as
  `_DISCOVERIES_DIR / <domain> / <run_id>.json` (per-domain subdirectory),
  matching the orchestrator's write layout (`operator_orchestrator.py:310`).

### 6. Two-stage summary write in adapter

Previously the adapter wrote `summary.json` once at the end. Phase 4's
`cross_domain_transfer_detector` needs to read the source bucket's
`summary.json` to load per-trade `operator_coefficients` vectors. Fix:

1. First write: after the per-winner loop, before Phase 4. Includes
   `control_plane_phases.phase3_chain_builder` only.
2. Final write: after Phase 4 + Phase 6. Includes all
   `phase{3,4,6}_*` paths.

### 7. Phase 6 wiring (Governance Loop closure)

Adapter post-bucket, after Phase 4:

```python
for op_id in _RUNTIME_OPERATOR_IDS:
    promotions[op_id] = call_control_plane_operator(
        "operator_promotion_recommender",
        {"operator_id": op_id,
         "evaluation_window": "P30D",
         "include_schema_suggestions": True,
         "run_counterfactual": True},
    )
```

Each op gets `promotion_score`, `recommendation` (hold/promote/retire),
`blocking_issues`, `schema_suggestions`, `counterfactual_analysis`.

Output → `<out-dir>/control_plane/phase6_promotions.json`.

⚠ Note: `recommend_operator_promotion` internally calls
`track_operator_lineage` with the manifest's current version — this WRITES
a lineage record each Phase 6 invocation. Subsequent calls at the same
version overwrite the same record (timestamp refresh). Not pollution per
se but worth knowing.

### 8. arch_workflow.py alias

Created `E:\refrag\adapters\arch_workflow.py` — thin docstring + alias
around `markets_refrag_adapter.main()`. Filename exists so "arch workflow
entry point" is discoverable in the adapters/ directory. Functionally
identical to running the adapter directly.

### 9. Memory updates

- NEW: `C:\Users\A\.claude\projects\E--\memory\reference_arch_workflow.md`
  (full Phase status table, output layout, "always run via adapter"
  reminder)
- NEW: `C:\Users\A\.claude\projects\E--\memory\reference_arch_doc_v21.md`
  (from earlier today — canonical arch v2.1 summary; pointer to
  `_arch_spec_v21_extracted.txt`)
- INDEX: `C:\Users\A\.claude\projects\E--\memory\MEMORY.md` updated with
  both new entries

## Files modified this session

| File | What changed |
|---|---|
| `E:\refrag\adapters\markets_refrag_adapter.py` | Phase 3 pre-bucket + Phase 4 + Phase 6 post-bucket; storage helpers import; `_RUNTIME_OPERATOR_IDS` constant; lineage_snapshot construction; two-stage summary write |
| `E:\refrag\refrag_discovery\control_plane\operator_chain_builder.py` | Full rewrite with `lineage_snapshot` + `task_meta_learner_recommendation` kwargs; `_lineage_summary_for_step` helper; `task_meta_learner_modulated_score`; `lineage_summary` block in output |
| `E:\refrag\refrag_discovery\control_plane\cross_domain_transfer_detector.py` | `_DISCOVERIES_DIR` stale-path fix; `_resolve_domain_summary_path` helper for granular markets routing; per-domain subdir discovery path |
| `C:\Users\A\.claude\projects\E--\memory\reference_arch_workflow.md` | Phase 6 marked WIRED; output layout listed |
| `C:\Users\A\.claude\projects\E--\memory\MEMORY.md` | Updated reference_arch_workflow.md entry |

## Files NEW this session

| File | Purpose |
|---|---|
| `E:\refrag\adapters\arch_workflow.py` | Discoverable arch entry point (thin alias) |
| `C:\Users\A\.claude\projects\E--\memory\reference_arch_workflow.md` | "Always run via adapter" memory note |
| `C:\Users\A\.claude\projects\E--\memory\reference_arch_doc_v21.md` | Canonical arch v2.1 summary (from earlier in this session) |

## Things explicitly NOT done

- **`operator_graph_rewriter` stays DISABLED** per arch Rule 6 — terminal
  node of the self-optimization loop, depth-4 in §6, requires accumulated
  Phase 6 validation data + approval tokens before enabling
- **No smoke test run** — Greg postponed it; first thing to do in next chat
- **No git commits** (per `feedback_periodic_git_push.md` — Greg's not
  using git for this work)
- **Full 3,415-winner sweep paused** (per the prior handoff, may or may
  not still be running in background — check `tasklist | grep python`)
- **Other 23 buckets not run** — Phase 4 cross-domain transfer is most
  meaningful when the opposite-outcome bucket has data. Run order
  suggestion: do each `*_win` bucket, then the matching `*_lose`, then
  re-run the `*_win` to populate the transfer detector with paired data.

## Run knob (smoke test for the next chat)

```bash
cd E:/refrag && python adapters/markets_refrag_adapter.py \
  --winner-json E:/Markets/research/strategy_evolution/per_bucket/markets_eth_coinbase_sell_win.json \
  --outcome win \
  --out-dir E:/Markets/per_bucket_runs/markets_eth_coinbase_sell_win
```

Expected end-of-run state:
- `<out-dir>/summary.json` — per-winner results + `control_plane_phases` paths
- `<out-dir>/control_plane/phase3_chain_builder.json` — chain plan
- `<out-dir>/control_plane/phase4_gap_finder.json` — registry coverage
- `<out-dir>/control_plane/phase4_manifest_synthesizer.json` — pattern proposals
- `<out-dir>/control_plane/phase4_cross_domain_transfer.json` — win vs lose
- `<out-dir>/control_plane/phase6_promotions.json` — per-op promotion scores

Per-trade discoveries continue to land at:
- `E:\refrag\discoveries\operator_discoveries\markets_eth_coinbase_sell_win\<run_id>.json`
- `E:\refrag\discoveries\evidence_graphs\markets_eth_coinbase_sell_win_evidence.json`
  (accumulated across all trades in the bucket)

## Verification status

**Compile checks**: PASSED for all four modified files
(`markets_refrag_adapter.py`, `arch_workflow.py`, `operator_chain_builder.py`,
`cross_domain_transfer_detector.py`).

**Two background review agents spawned at end-of-session (read-only):**

1. **arch-compliance review** (code-reviewer agent) — checks all 21
   operators against arch §6 dep graph, all 5 §5 feedback loops, Rules 1,
   5, 10, and the adapter's Phase 1-6 ordering. Findings will appear in
   the conversation transcript.

2. **Debugger bug hunt** — focuses on the recently-modified code paths
   (Phase 3/4/6 in adapter; orchestrator closed-loop; chain_builder new
   kwargs; cross_domain_transfer_detector path fix; promotion_recommender
   internal lineage writes). Findings will appear in the conversation
   transcript.

**First task in the next chat**: review both agent reports, address any
high-priority findings before running the smoke test.

## Pending validations (for the next chat)

- Smoke test the small bucket end-to-end
- Verify Phase 3 output includes `lineage_summary` + `task_meta_learner_modulated_score`
- Verify Phase 4 `cross_domain_transfer_detector` finds the opposite bucket
  cleanly (if `*_lose` has been run; insufficient_signal otherwise)
- Verify Phase 6 outputs sane `promotion_score` per op (expect mostly "hold"
  with `blocking={Manifest visibility is internal}` since operators are
  internal-only by default)
- Spot-check the closed-loop Phase 2: confirm `iter=2 max_delta=0.0`
  termination still works as in the prior session
- Confirm graph_rewriter remains disabled (no calls anywhere in the adapter)

## Next session priorities

1. **Review the two agent reports** (arch + debug from this turn's transcript)
2. **Fix any high-priority findings**
3. **Smoke test** the small bucket; verify all 5 control-plane outputs
4. **Run a couple of `*_lose` buckets** so Phase 4 cross-domain transfer
   has paired data
5. **Then** rerun a `*_win` bucket to validate the transfer detector finds
   meaningful winner vs loser cross-outcome similarity

## End of handoff

Arch v2.1 Phases 1-6 are wired. `graph_rewriter` stays disabled per Rule 6.
Two arch-§6 dependency gaps in `chain_builder` were closed. The independent
stale-path bug in `cross_domain_transfer_detector` was fixed. Smoke test +
agent findings pending. Always run via `markets_refrag_adapter.py` or
`arch_workflow.py` — calling `OperatorOrchestrator.execute()` directly skips
Phase 3, 4, and 6.
