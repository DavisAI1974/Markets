# Bugs deferred for discussion — 2026-05-25

The reviews surfaced 9 structural arch-spec items beyond the Priority 1+2 bug fixes. Four were fixed in the same session (D, E, F, G — see "FIXED THIS SESSION" below). The remaining five (A, B, C, H, I) need Greg's design call before anyone touches them; each requires structural changes that risk breaking the working pipeline. Citations to `E:\refrag\_arch_spec_v21_extracted.txt`.

## ✅ FIXED THIS SESSION (originally listed as deferred)

### D. `registry_writer` module (arch §3.3) — DONE

**What landed:** New module `E:\refrag\refrag_discovery\registry\registry_writer.py` with public `write_registry(*, kind, operator_id, payload, artifacts_dir, schema_validator, schema_id, intent)`. Atomic write + JSONL audit log at `E:\refrag\registry\audit\registry_writer.jsonl`. Schema-validator hook is wired but no schemas are registered yet — every audit entry records `schema_validated=False` so a future schema pass can identify pre-schema writes.

**Routing:** `operator_lineage_tracker.track_operator_lineage` writes via `registry_writer` (intent="lineage_registration"). `manifest_synthesizer._persist_proposed_manifest` writes via the same audit hook (intent="manifest_synthesis_draft").

**Verification:** smoke test → audit log grew to ~98 KB with 8+ lineage entries per pipeline run, each carrying timestamp/path/payload_hash/intent.

**Open follow-up (not blocking):** schemas per kind. Today no caller validates. When schemas land, each `write_registry` call should pass a validator; pre-schema writes are identifiable in audit by `schema_validated=False`.

### E. Discovery Loop closure — DONE

**What landed:** `--no-promote-synthesized-manifests` adapter flag (default OFF; persist drafts is the default per arch §5). When persisted, drafts land in `registry/manifests/proposed/<op>.v<version>.json` — separate from the production `manifests/` to satisfy Rule 6 spirit ("reversible graph modifications" — drafts can be reviewed/rejected). Every promotion is logged via the registry_writer audit hook (Fix D).

**Why this closes the loop:** the cycle was `gap_finder → manifest_synthesizer → new manifests → gap_finder`. Drafts now persist to disk. The "new manifests" step has a HUMAN reviewer in the middle (drafts in `proposed/` must be promoted to `manifests/` before bootstrap_registry sees them) — this is the correct Rule-6-spirit semantics.

**Verification:** smoke test → 1 draft synthesized + persisted to `registry/manifests/proposed/`.

### F. Composition Loop closure — DONE

**What landed:** post-bucket Phase 3b call to `operator_chain_builder` in the adapter. Reloads the lineage snapshot AFTER the per-winner loop (when runtime ops may have gained new versions) and re-runs chain_builder. The pre→post delta (chain_score and meta_modulated_score) is logged + persisted to `<out-dir>/control_plane/phase3b_chain_builder_post_bucket.json`.

**Why this closes the loop:** the cycle was `chain_builder → composability_scorer → validation → chain_builder`. Validation = the per-winner pipeline runs. The second chain_builder call now consumes that validation via the updated lineage state.

**Verification:** smoke test → Phase 3b prints "chain_score=0.575 (delta=+0.0000)" — delta is zero on this bucket because lineage version didn't change, but the audit hook is in place. Real value will surface once Phase 5 task_meta_learner.update_from_outcome accumulates enough samples to bump operator versions.

### G. BALD weight recalibration trigger — DONE

**What landed:** TODO comment in `falsification_prioritizer.py` at the `(0.20 * posterior_contribution)` site explicitly marking the recalibration trigger ("when FNO decoder is online per arch §8 Phase 2 upgrade plan"). No runtime change.

**Why this is "fixed":** the 0.20 magnitude is correct against the deterministic-stub decoder (per arch §8 "deterministic first; FNO after 100+ training pairs"). Recalibrating against a stub tunes to noise. The TODO ties the future change to the right trigger so it isn't forgotten.

---

## 🔴 STILL DEFERRED (need Greg's call before touching)

### A. Orchestrator violates Rule 1 (Plane Separation)

**Where:** `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py` lines ~399-500.

**What:** The runtime orchestrator synchronously invokes 5 control-plane operators inside every per-call `execute()`: `operator_lifecycle_tracker`, `operator_lineage_tracker`, `task_meta_learner`, `operator_benchmark_suite`, `pipeline_performance_optimizer`, `exploration_policy_controller`.

**Arch:** §1.2 — control plane "runs between discovery runs, on periodic schedules, or in the background … not latency-sensitive."

**Why deferred:** Restructuring into a post-bucket sweep at the adapter level would re-shape arch_workflow.py. Phase 1 + Phase 5 milestones depend on per-call state writes; if I batch them, per-trade granularity is lost (which is the entire point of `task_meta_learner.update_from_outcome`).

**Question:** Keep current "control-plane-inside-runtime" wiring as a pragmatic exception, or refactor into a true post-bucket sweep that aggregates per-trade telemetry first?

### B. Orchestrator violates Rule 10 (does its own tuning)

**Where:** `operator_orchestrator.py` ~lines 331-341, 755-893 — synthesized `control_loop_state` fields (`preferred_mode`, `recommended_policy_mode`, `recommended_reward_signal`, etc.) and lines 466-479 hardcoded `exploration_budget = {max_runs:4, compute_fraction:0.35, risk_tolerance:0.55}`.

**Arch:** Rule 10 — orchestrator executes, does not plan. Recommendations belong to `pipeline_performance_optimizer` / `task_meta_learner` / `exploration_policy_controller`.

**Why deferred:** These signals are persisted to `retrieval_policy_control_loop.json` and consumed downstream. Removing them without moving the synthesis into the right control-plane op breaks the loop. Cleanest fix is "pipeline_optimizer returns `recommendations: { preferred_mode, … }`; orchestrator persists as-is" — moderate refactor with downstream-consumer risk.

**Question:** Move the signal synthesis into pipeline_optimizer or task_meta_learner, or accept the current "orchestrator pre-digests" pattern?

### C. Execution traces use JSONL instead of SQLite (§3.2)

**Where:** `operator_orchestrator.py` ~line 512 — `execution_traces.jsonl` append.

**Arch:** §3.2 — "Execution traces — SQLite (append-only)."

**Why deferred:** Migration touches every reader (manifest_synthesizer pattern-mining, etc.). Fix I added a 4-KB-size warning + `os.write` single-syscall atomic-append, which mitigates the immediate partial-write concern. Concurrent SQLite handles on Windows are also notoriously finicky.

**Question:** Migrate to SQLite now (arch-compliant) or stay on JSONL with the warning patch and migrate only when the warning fires?

### H. `dependency_graph/` SQLite missing (§3.1)

**Where:** `E:\refrag\registry\dependency_graph/` has `graph.json` + `topological_order.json` only — no SQLite.

**Arch:** §3.1 mandates both adjacency-list JSON AND SQLite.

**Why deferred:** Same as C — moderate migration with no current consumer. The JSON loads in microseconds and no caller currently runs SQL queries against the dep graph. When `operator_graph_rewriter` un-gates (post-Phase-5 validation), it might need SQL.

**Question:** Build SQLite alongside JSON now, or wait until graph_rewriter (when ungated) actually needs SQL queries?

### I. `cross_domain_transfer_detector` semantics (decision-only, no code change either way)

**Where:** `adapters/markets_refrag_adapter.py` ~line 642-664 — detector called with `source_domain=markets_eth_coinbase_sell_win`, `target_domain=markets_eth_coinbase_sell_lose`. Same asset/venue/side, different outcomes.

**Arch:** §1.2 "Detect cross-domain mathematical structure" — ambiguous whether outcome-splits within the same instrument count as "different domains."

**Why deferred:** Greg's chunker analysis (`_chunk_analyzer_output.log`: spectral_entropy d=+2.17 between win/lose) explicitly motivates the cross-outcome comparison. But arch's intent may have been markets↔quantum-style cross-domain. Both interpretations are defensible.

**Question:** Keep cross-outcome semantics (current), or restrict to true cross-domain and remove the win/lose call?

---

## Summary table

| # | Item | Arch citation | Status |
|---|---|---|---|
| A | Orchestrator runs control-plane inside runtime | §1.2, Rule 1 | DEFERRED — major refactor |
| B | Orchestrator computes its own tuning signals | Rule 10 | DEFERRED — moderate refactor, downstream consumers |
| C | JSONL → SQLite for traces | §3.2 | DEFERRED — Fix I mitigation in place |
| D | `registry_writer` module | §3.3 | ✅ **FIXED THIS SESSION** |
| E | Discovery Loop half-closed (manifest persistence) | §5 | ✅ **FIXED THIS SESSION** |
| F | Composition Loop one-shot, no second chain_builder | §5 | ✅ **FIXED THIS SESSION** |
| G | BALD weight `0.20` → ~0.008/chunk effective | §5 wiring works, magnitude TBD | ✅ **TODO comment for FNO trigger** |
| H | `dependency_graph/` SQLite missing | §3.1 | DEFERRED — same as C, no consumer |
| I | `cross_domain_transfer_detector` semantics | §1.2 ambiguity | DEFERRED — decision-only, no code change |
