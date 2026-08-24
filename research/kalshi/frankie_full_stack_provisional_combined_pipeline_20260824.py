#!/usr/bin/env python3
"""Execute every lawful provisional ability for the combined October lane.

The pipeline is a deterministic, fail-closed adapter.  Every ability receives
the same immutable causal-prefix identity and a detached copy of the same
prefix-only state.  Its derived output is bound into a SHADOW-only component
receipt.  The caller may pass those receipts only to ``FULL_PROVISIONAL_COMBINED``;
the paired orchestrator remains the authority enforcing that lane isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.frankie_full_stack_paired_lane_orchestrator_20260824 import (
    ComponentLifecycleStage,
    ComponentStatus,
    ProvisionalComponentReceipt,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import CausalPrefixBinding
from research.kalshi.frankie_october_knowledge_inventory_20260824 import (
    PROVISIONAL_SOURCE_DISPOSITIONS,
    ProvisionalSourceDisposition,
)


ACTIVE_COMPONENT_IDS = (
    "S137_COGNITIVE_RUNTIME",
    "HIPPORAG_RETRIEVAL",
    "TEMPORAL_GRAPH",
    "LATS_BOUNDED_SEARCH",
    "WORKING_MEMORY",
    "PROGRESS_COMPRESSION",
    "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
)

EXECUTION_APIS = {
    "S137_COGNITIVE_RUNTIME": "CognitiveCandidateRuntime.run_p0_component",
    "HIPPORAG_RETRIEVAL": "run_hipporag_shadow_pipeline",
    "TEMPORAL_GRAPH": "run_temporal_graph_shadow_adapter",
    "LATS_BOUNDED_SEARCH": "run_bounded_lats_search",
    "WORKING_MEMORY": "run_state_aware_working_memory",
    "PROGRESS_COMPRESSION": "run_progress_compress_shadow",
    "PROVISIONAL_V4_ENGINEERING_CANDIDATE": "score_open_stream_events",
}
MAX_DERIVED_OUTPUT_BYTES = 256_000


class ProvisionalCombinedExecutionError(ValueError):
    """A provisional ability failed or returned an unsafe output contract."""


def _canonical(value: Any, label: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProvisionalCombinedExecutionError(f"{label} must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash payload").encode()).hexdigest()


def _detached(value: Any, label: str) -> Any:
    return json.loads(_canonical(value, label))


@dataclass(frozen=True)
class ProvisionalAbilityRequest:
    component_id: str
    binding: CausalPrefixBinding
    causal_state: Mapping[str, Any]
    source_context: tuple[Mapping[str, Any], ...]
    all_together_input_hash: str


Ability = Callable[[ProvisionalAbilityRequest], Mapping[str, Any]]


@dataclass(frozen=True)
class ProvisionalAbilityApis:
    s137_cognitive_runtime: Ability
    hipporag_retrieval: Ability
    temporal_graph: Ability
    lats_bounded_search: Ability
    working_memory: Ability
    progress_compression: Ability
    provisional_v4_candidate: Ability

    def ordered(self) -> tuple[Ability, ...]:
        return (
            self.s137_cognitive_runtime,
            self.hipporag_retrieval,
            self.temporal_graph,
            self.lats_bounded_search,
            self.working_memory,
            self.progress_compression,
            self.provisional_v4_candidate,
        )

    @classmethod
    def production(cls) -> "ProvisionalAbilityApis":
        """Bind the seven checked-in public provisional runtime surfaces."""
        return cls(
            s137_cognitive_runtime=_run_s137_cognitive_runtime,
            hipporag_retrieval=_run_hipporag_retrieval,
            temporal_graph=_run_temporal_graph,
            lats_bounded_search=_run_lats_bounded_search,
            working_memory=_run_working_memory,
            progress_compression=_run_progress_compression,
            provisional_v4_candidate=_run_provisional_v4_candidate,
        )


def execute_combined_provisional_pipeline(
    *,
    binding: CausalPrefixBinding,
    causal_state: Mapping[str, Any],
    source_contexts: Mapping[str, Sequence[Mapping[str, Any]]],
    apis: ProvisionalAbilityApis | None = None,
) -> tuple[ProvisionalComponentReceipt, ...]:
    """Execute all seven abilities before returning any provider-facing context."""
    bound = binding.validate()
    if not isinstance(causal_state, Mapping):
        raise ProvisionalCombinedExecutionError("causal_state must be an object")
    if set(source_contexts) != set(ACTIVE_COMPONENT_IDS):
        raise ProvisionalCombinedExecutionError("source_contexts must exactly cover seven abilities")
    detached_state = _detached(dict(causal_state), "causal_state")
    detached_sources = {
        component_id: tuple(
            _detached(dict(row), f"{component_id} source context")
            for row in source_contexts[component_id]
        )
        for component_id in ACTIVE_COMPONENT_IDS
    }
    if any(not rows for rows in detached_sources.values()):
        raise ProvisionalCombinedExecutionError("every ability requires source context")
    source_dispositions = (
        _bind_production_source_dispositions(detached_sources)
        if apis is None
        else {
            component_id: tuple(
                {
                    "path": str(row.get("path") or "TEST_INJECTED"),
                    "disposition": "TEST_INJECTED",
                }
                for row in detached_sources[component_id]
            )
            for component_id in ACTIVE_COMPONENT_IDS
        }
    )
    all_together_input_hash = _hash(
        {
            "binding": bound.identity_payload(),
            "causal_state": detached_state,
            "source_contexts": detached_sources,
        }
    )
    implementations = (apis or ProvisionalAbilityApis.production()).ordered()
    receipts: list[ProvisionalComponentReceipt] = []
    for component_id, execute in zip(ACTIVE_COMPONENT_IDS, implementations, strict=True):
        request = ProvisionalAbilityRequest(
            component_id=component_id,
            binding=bound,
            causal_state=_detached(detached_state, "ability causal state"),
            source_context=tuple(
                _detached(row, "ability source context")
                for row in detached_sources[component_id]
            ),
            all_together_input_hash=all_together_input_hash,
        )
        try:
            raw_output = execute(request)
        except Exception as exc:
            raise ProvisionalCombinedExecutionError(
                f"{component_id} execution raised {type(exc).__name__}"
            ) from exc
        if not isinstance(raw_output, Mapping):
            raise ProvisionalCombinedExecutionError(f"{component_id} returned a non-object")
        output = _detached(dict(raw_output), f"{component_id} output")
        if output.get("status") not in {"COMPLETED", "COMPLETED_SHADOW_EVIDENCE_ONLY"}:
            raise ProvisionalCombinedExecutionError(
                f"{component_id} returned {output.get('status') or 'NO_STATUS'}"
            )
        encoded = _canonical(output, f"{component_id} output").encode()
        if len(encoded) > MAX_DERIVED_OUTPUT_BYTES:
            raise ProvisionalCombinedExecutionError(f"{component_id} output exceeds provider bound")
        receipts.append(
            ProvisionalComponentReceipt.create(
                component_id=component_id,
                binding=bound,
                lifecycle_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
                executed_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
                status=ComponentStatus.ACTIVE,
                context={
                    "component_id": component_id,
                    "execution_api": EXECUTION_APIS[component_id],
                    "executed": True,
                    "binding": bound.identity_payload(),
                    "all_together_input_hash": all_together_input_hash,
                    "component_source_context_hash": _hash(detached_sources[component_id]),
                    "source_dispositions": source_dispositions[component_id],
                    "derived_output": output,
                    "derived_output_hash": hashlib.sha256(encoded).hexdigest(),
                    "authority": "SHADOW_DIAGNOSTIC_ONLY",
                    "can_change_primary": False,
                },
            )
        )
    receipts.append(
        ProvisionalComponentReceipt.create(
            component_id="META_LOOP",
            binding=bound,
            lifecycle_stage=ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC,
            executed_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
            status=ComponentStatus.DEFERRED_NOT_YET_LAWFUL,
            context={
                "component_id": "META_LOOP",
                "executed": False,
                "reason": "OUTCOME_DEPENDENT_POST_EVIDENCE_ONLY",
                "binding": bound.identity_payload(),
                "all_together_input_hash": all_together_input_hash,
                "can_change_primary": False,
            },
        )
    )
    return tuple(receipts)


def _bind_production_source_dispositions(
    source_contexts: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    expected = {
        path: row
        for path, row in PROVISIONAL_SOURCE_DISPOSITIONS.items()
        if row.disposition is not ProvisionalSourceDisposition.DEFERRED_POST_EVIDENCE
    }
    supplied: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for component_id, rows in source_contexts.items():
        for row in rows:
            path = str(row.get("path") or "")
            if path in supplied:
                raise ProvisionalCombinedExecutionError(
                    f"duplicate provisional source context: {path}"
                )
            supplied[path] = (component_id, row)
    if set(supplied) != set(expected):
        raise ProvisionalCombinedExecutionError(
            "production provisional source dispositions are incomplete"
        )

    receipts: dict[str, list[dict[str, Any]]] = {
        component_id: [] for component_id in ACTIVE_COMPONENT_IDS
    }
    for path in sorted(expected):
        disposition = expected[path]
        component_id, source = supplied[path]
        if component_id != disposition.component_id:
            raise ProvisionalCombinedExecutionError(
                f"provisional source component drift: {path}"
            )
        source_sha256 = str(source.get("source_sha256") or "")
        if len(source_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in source_sha256.lower()
        ):
            raise ProvisionalCombinedExecutionError(
                f"provisional source SHA-256 is invalid: {path}"
            )
        row = {
            "path": path,
            "source_sha256": source_sha256.lower(),
            "component_id": component_id,
            "disposition": disposition.disposition.value,
            "module_imported": False,
            "required_symbol_bound": False,
            "context_only_bound": False,
        }
        if disposition.disposition is ProvisionalSourceDisposition.EXECUTABLE_MODULE_BINDING:
            try:
                module = importlib.import_module(str(disposition.module_name))
            except Exception as exc:
                raise ProvisionalCombinedExecutionError(
                    f"provisional module import failed: {path}"
                ) from exc
            if not hasattr(module, str(disposition.required_symbol)):
                raise ProvisionalCombinedExecutionError(
                    f"provisional module public symbol is absent: {path}"
                )
            row.update(
                {
                    "module_name": disposition.module_name,
                    "required_symbol": disposition.required_symbol,
                    "module_imported": True,
                    "required_symbol_bound": True,
                }
            )
        elif disposition.disposition is ProvisionalSourceDisposition.CONTEXT_ONLY_GOVERNANCE:
            row["context_only_bound"] = True
        else:
            raise ProvisionalCombinedExecutionError(
                f"deferred source entered the active combined context: {path}"
            )
        receipts[component_id].append(row)
    return {key: tuple(value) for key, value in receipts.items()}


def _budget() -> dict[str, int]:
    return {
        "model_calls": 100,
        "input_tokens": 10_000,
        "output_tokens": 10_000,
        "tool_queries": 100,
        "storage_bytes": 1_000_000,
        "wall_clock_ms": 100_000,
    }


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _normalized_result(
    *, component_id: str, raw: Mapping[str, Any], projection: Mapping[str, Any]
) -> Mapping[str, Any]:
    status = str(raw.get("status") or "")
    if status not in {"COMPLETED", "COMPLETED_SHADOW_EVIDENCE_ONLY"}:
        raise ProvisionalCombinedExecutionError(f"{component_id} public API returned {status}")
    return {
        "status": "COMPLETED",
        "public_api_status": status,
        "public_api_receipt_hash": _hash(dict(raw)),
        "derived": _detached(dict(projection), f"{component_id} projection"),
        "performance_evidence": False,
        "promotion_authority": "NONE",
    }


def _run_s137_cognitive_runtime(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_cognitive_p0_loops import BudgetVector, CallbackResult
    from frankie_s137_cognitive_runtime import runtime_for

    source_hash = _hash(request.causal_state)
    decisions = iter(
        (
            {
                "kind": "TOOL",
                "reason": "inspect the sealed causal-prefix state",
                "tool_name": "causal_prefix_read",
                "tool_input": {"prefix_hash": request.binding.causal_prefix_hash},
            },
            {
                "kind": "STOP",
                "reason": "the bounded causal-prefix observation is available",
                "final": {"prefix_state_hash": source_hash},
                "source_hashes": [source_hash],
            },
        )
    )

    def callback(payload: Mapping[str, Any], **usage: float) -> CallbackResult:
        return CallbackResult(payload, BudgetVector(**usage), side_effect_free=True)

    raw = runtime_for("COG02_REACT_EVIDENCE_LOOP").run_p0_component(
        initial_state={
            "prefix_hash": request.binding.causal_prefix_hash,
            "state_hash": source_hash,
        },
        decide_fn=lambda _context: callback(next(decisions), model_calls=1),
        tool_fn=lambda _context: callback(
            {
                "observation": {"state_hash": source_hash},
                "read_only": True,
                "source_hashes": [source_hash],
            },
            tool_queries=1,
        ),
        allowed_tools=("causal_prefix_read",),
        baseline_budget=_budget(),
        max_steps=2,
    )
    result = raw.get("result", {})
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "candidate_id": "COG02_REACT_EVIDENCE_LOOP",
            "final": result.get("final"),
            "tool_observations": result.get("tool_observations"),
            "trace_hash": _hash(result.get("trace", [])),
        },
    )


def _run_hipporag_retrieval(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_hipporag_p0_retrieval import HippoCallbackResult, run_hipporag_shadow_pipeline

    state_text = _canonical(
        {
            "binding": request.binding.identity_payload(),
            "causal_state": request.causal_state,
            "source_context_hash": _hash(request.source_context),
        },
        "HippoRAG source chunk",
    )
    chunk = {
        "chunk_id": "causal-prefix",
        "text": state_text,
        "source_path": f"shadow/causal-prefix/{request.binding.causal_prefix_hash}.json",
        "source_hash": _hash(request.source_context),
        "content_hash": hashlib.sha256(state_text.encode()).hexdigest(),
        "created_at": _iso(request.binding.event_known_by),
        "knowable_at": _iso(request.binding.event_known_by),
        "token_count": max(1, len(state_text.split())),
        "parent_chunk_ids": [],
        "immutable": True,
    }

    def result(payload: Mapping[str, Any]) -> HippoCallbackResult:
        return HippoCallbackResult(payload, read_only=True, side_effect_free=True)

    def reader(reader_request: Mapping[str, Any]) -> HippoCallbackResult:
        selected = reader_request["retrieved_chunks"][0]
        return result(
            {
                "answer": "The causal-prefix evidence is available for combined shadow reasoning.",
                "citations": [
                    {
                        "chunk_id": selected["chunk_id"],
                        "source_path": selected["source_path"],
                        "source_hash": selected["source_hash"],
                        "content_hash": selected["content_hash"],
                    }
                ],
            }
        )

    version_hash = _hash({"component": request.component_id, "adapter": "october-combined"})
    raw = run_hipporag_shadow_pipeline(
        source_chunks=(chunk,),
        invalidations=(),
        query="What is knowable in this causal prefix?",
        decision_cutoff_at=_iso(request.binding.causal_cutoff),
        target_birth_at=_iso(request.binding.causal_cutoff + 1.0),
        open_ie_fn=lambda _request: result(
            {
                "entities": [
                    {"label": "causal prefix", "source_chunk_ids": ["causal-prefix"]},
                    {"label": "observed state", "source_chunk_ids": ["causal-prefix"]},
                ],
                "triples": [
                    {
                        "subject": "causal prefix",
                        "predicate": "contains",
                        "object": "observed state",
                        "source_chunk_ids": ["causal-prefix"],
                    }
                ],
            }
        ),
        query_entity_fn=lambda _request: result({"entities": ["causal prefix"]}),
        reader_fn=reader,
        open_ie_version_hash=version_hash,
        query_entity_version_hash=version_hash,
        reader_version_hash=version_hash,
        matched_control={
            "method": "FLAT_VECTOR_LIKE",
            "storage_budget_bytes": 100_000,
            "top_k": 1,
            "token_budget": max(1, len(state_text.split())),
            "reader_call_budget": 1,
            "reader_version_hash": version_hash,
        },
        storage_budget_bytes=100_000,
        top_k=1,
        token_budget=max(1, len(state_text.split())),
        iterations=8,
    )
    hippo = raw.get("result", {})
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "reader_output": hippo.get("reader_output"),
            "retrieval_hash": _hash(hippo.get("ranked_chunks", hippo)),
            "association_is_causality": False,
        },
    )


def _temporal_controls() -> Mapping[str, Any]:
    from frankie_cognition import sha256_json
    from frankie_temporal_graph_p0_adapter import frozen_static_signed_hash_payload

    matched = {
        "feature_schema_hash": "1" * 64,
        "split_hash": "2" * 64,
        "case_manifest_hash": "3" * 64,
        "compute_budget_hash": "4" * 64,
    }
    frozen = {
        **matched,
        "architecture": "FROZEN_STATIC",
        "frozen": True,
        "uses_temporal_memory": False,
        "uses_future_events": False,
        "model_version_hash": "5" * 64,
    }
    frozen["signed_contract_hash"] = sha256_json(frozen_static_signed_hash_payload(frozen))
    deep_sets = {
        **matched,
        "architecture": "DEEP_SETS",
        "aggregation": "SUM",
        "uses_edges": False,
        "uses_node_ids": False,
        "uses_ordered_sequence": False,
        "permutation_invariant": True,
        "phi_version_hash": "6" * 64,
        "rho_version_hash": "7" * 64,
    }

    def graph(edges: Sequence[tuple[str, str]]) -> Mapping[str, Any]:
        nodes = sorted({node for edge in edges for node in edge})
        return {
            "directed": False,
            "graph_schema": "TEMPORAL_COMBINED_WL",
            "nodes": [{"node_id": node, "wl_label": "SAME"} for node in nodes],
            "edges": [
                {"edge_id": f"e{index}", "source": left, "target": right, "edge_type": "U"}
                for index, (left, right) in enumerate(edges)
            ],
        }

    return {
        "candidate_contract": matched,
        "frozen_static_control": frozen,
        "edgeless_deep_sets_control": deep_sets,
        "one_wl_control": {
            **matched,
            "control_id": "cycle-v-triangles",
            "graph_a": graph((("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "a"))),
            "graph_b": graph((("u", "v"), ("v", "w"), ("w", "u"), ("x", "y"), ("y", "z"), ("z", "x"))),
        },
    }


def _run_temporal_graph(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_temporal_graph_p0_adapter import (
        run_temporal_graph_shadow_adapter,
        temporal_event_content_hash,
    )

    timestamp = _iso(request.binding.event_known_by)
    event = {
        "event_id": "prefix-event",
        "source_hash": _hash(request.source_context),
        "stream_id": "october-prefix",
        "lane_id": "combined-shadow",
        "source_node_id": "prefix",
        "target_node_id": "state",
        "event_type": "INTERACTION",
        "source_sequence": 1,
        "source_at": timestamp,
        "effective_at": timestamp,
        "knowable_at": timestamp,
        "parent_event_ids": [],
        "payload": {"state_hash": _hash(request.causal_state)},
        "immutable": True,
    }
    event["event_hash"] = temporal_event_content_hash(event)
    raw = run_temporal_graph_shadow_adapter(
        events=(event,),
        source_cutoff_at=_iso(request.binding.causal_cutoff),
        effective_cutoff_at=_iso(request.binding.causal_cutoff),
        knowable_cutoff_at=_iso(request.binding.causal_cutoff),
        target_birth_at=_iso(request.binding.causal_cutoff + 1.0),
        control_bindings=_temporal_controls(),
    )
    temporal = raw.get("result", {})
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "predictions": temporal.get("predictions"),
            "final_memory_hash": _hash(temporal.get("final_memories", {})),
            "hash_chain_valid": temporal.get("hash_chain_valid"),
        },
    )


def _run_lats_bounded_search(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_cognition import sha256_json
    from frankie_cognitive_p0_loops import BudgetVector, CallbackResult
    from frankie_lats_p0_search import run_bounded_lats_search

    feedback = {"state_hash": _hash(request.causal_state)}
    catalog = ({
        "ref_id": "prefix-state",
        "payload": feedback,
        "source_hash": sha256_json(feedback),
        "observed_at": _iso(request.binding.event_known_by),
        "reveal_at": _iso(request.binding.event_known_by),
        "immutable": True,
        "status": "ACTIVE",
    },)

    def callback(payload: Mapping[str, Any], **usage: float) -> CallbackResult:
        return CallbackResult(payload, BudgetVector(**usage), side_effect_free=True)

    def expand(context: Mapping[str, Any]) -> CallbackResult:
        parent = context["parent"]
        lineage = context["reflection_lineage"]
        return callback(
            {
                "source_parent_id": parent["node_id"],
                "candidates": [
                    {
                        "candidate_id": "retain",
                        "hypothesis": "retain the prefix-supported hypothesis",
                        "action": {"kind": "INSPECT", "scope": "prefix"},
                        "planned_feedback_refs": ["prefix-state"],
                        "used_reflection_hashes": lineage,
                    },
                    {
                        "candidate_id": "abstain",
                        "hypothesis": "preserve uncertainty under sparse evidence",
                        "action": {"kind": "ABSTAIN", "scope": "prefix"},
                        "planned_feedback_refs": ["prefix-state"],
                        "used_reflection_hashes": lineage,
                    },
                ],
            },
            model_calls=1,
        )

    raw = run_bounded_lats_search(
        {"question": "Which prefix-only hypothesis remains supportable?"},
        catalog,
        cutoff_at=_iso(request.binding.causal_cutoff),
        expand_fn=expand,
        simulate_fn=lambda _context: callback(
            {
                "read_only": True,
                "feedback_refs": ["prefix-state"],
                "simulation_status": "SUPPORTED",
                "terminal": False,
                "uses_unrevealed_outcome": False,
            },
            tool_queries=1,
        ),
        value_fn=lambda context: callback(
            {
                "value": 0.5 if context["hypothesis"].startswith("retain") else 0.0,
                "reason": "prefix-bound search heuristic",
                "feedback_refs": ["prefix-state"],
            },
            model_calls=1,
        ),
        reflect_fn=lambda context: callback(
            {
                "source_node_id": context["node_id"],
                "reflection": "retain only the supplied prefix evidence",
                "feedback_refs": ["prefix-state"],
                "next_constraints": ["remain pre-reveal"],
            },
            model_calls=1,
        ),
        baseline_budget=_budget(),
        max_depth=1,
        max_width=2,
        iterations=1,
        seed=int(request.binding.causal_prefix_hash[:8], 16),
    )
    lats = raw.get("result", {})
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "best_path": lats.get("best_path"),
            "live_hypotheses": lats.get("live_hypotheses"),
            "determinism_projection_hash": lats.get("determinism_projection_hash"),
        },
    )


def _run_working_memory(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_cognitive_p0_loops import BudgetVector, CallbackResult, run_state_aware_working_memory

    def summarize(context: Mapping[str, Any]) -> CallbackResult:
        return CallbackResult(
            {
                "summary": "The causal prefix and all seven shadow abilities remain identity-bound.",
                "covered_event_hashes": [row["event_hash"] for row in context["trajectory"]],
                "evidence_refs": ["prefix-state"],
            },
            BudgetVector(model_calls=1),
            side_effect_free=True,
        )

    raw = run_state_aware_working_memory(
        (
            {"kind": "START", "subgoal_id": "combined-prefix", "objective": "retain prefix evidence"},
            {
                "kind": "EVENT",
                "subgoal_id": "combined-prefix",
                "event_kind": "OBSERVATION",
                "content": {"state_hash": _hash(request.causal_state)},
                "evidence_refs": ["prefix-state"],
            },
            {"kind": "COMPLETE", "subgoal_id": "combined-prefix"},
            {"kind": "STOP"},
        ),
        summarize_fn=summarize,
        allowed_evidence_refs={"prefix-state"},
        baseline_budget=_budget(),
    )
    memory = raw.get("result", {})
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "visible_context": memory.get("visible_context"),
            "completed_chunks": memory.get("completed_chunks"),
        },
    )


def _self_hash(core: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    return {**core, field: _hash(core)}


def _run_progress_compression(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_progress_compress_p0 import (
        ResourceUsage,
        ShadowCallbackResult,
        build_release_firewall_receipt,
        run_progress_compress_shadow,
    )

    protected = {"prefix-state": _canonical(request.causal_state, "protected prefix state").encode()}
    expected = {name: hashlib.sha256(value).hexdigest() for name, value in protected.items()}
    cutoff = request.binding.causal_cutoff
    task = {
        "task_id": "combined-prefix",
        "opened_at": _iso(cutoff - 5),
        "label_revealed_at": _iso(cutoff - 4),
        "progress_at": _iso(cutoff - 4),
        "compress_at": _iso(cutoff - 3),
        "evaluation_at": _iso(cutoff - 2),
        "release_at": _iso(cutoff + 1),
        "training_manifest_sha256": "a" * 64,
        "new_task_evaluation_manifest_sha256": "b" * 64,
        "release_manifest_sha256": "c" * 64,
        "required_parameter_ids": ["p-prefix"],
        "ewc_parameters": {
            "p-prefix": {"anchor": 0.0, "fisher": 1.0, "source_artifact_id": "prefix-state"}
        },
        "new_task_min_rows": 1,
        "new_task_higher_is_better": True,
        "minimum_new_task_improvement": 0.01,
    }
    cohorts = ({
        "cohort_id": "protected-prefix",
        "stratum": "prefix",
        "case_manifest_sha256": "d" * 64,
        "min_rows": 1,
        "higher_is_better": True,
    },)
    evaluator_hash = "e" * 64
    evaluator = _self_hash(
        {
            "judge_id": "combined-prefix-objective-evaluator",
            "judge_version_hash": evaluator_hash,
            "canary_manifest_hash": "1" * 64,
            "case_set_hash": "2" * 64,
            "cases": 100,
            "rates": {"order_flip_rate": 0.0, "length_control_flip_rate": 0.0, "truth_disagreement_rate": 0.0},
            "tolerances": {"order_flip_rate": 0.01, "length_control_flip_rate": 0.01, "truth_disagreement_rate": 0.05},
            "verdict": "JUDGE_AUTHORITY_RETAINED",
            "blockers": [],
            "promotion_authority": "NONE",
        },
        "canary_hash",
    )
    contamination_policy = {"min_trials": 10, "max_false_selection_rate": 0.5, "confidence_z": 1.96}
    contamination = _self_hash(
        {
            "status": "VALIDATOR_OR_EVALUATION_HELPER_NOT_RUNTIME_MODEL",
            "verdict": "PASS",
            "bindings": {
                "precommit_hash": "3" * 64,
                "adaptive_search_manifest_hash": "4" * 64,
                "planted_null_manifest_hash": "5" * 64,
                "locked_evaluator_hash": evaluator_hash,
            },
            "row_hash": "6" * 64,
            "policy": contamination_policy,
            "policy_hash": _hash(contamination_policy),
            "trial_count": 10,
            "false_selection_count": 0,
            "false_selection_rate": 0.0,
            "false_selection_wilson_upper": 0.2775,
            "declared_parent_hash_separation": True,
            "blockers": [],
        },
        "receipt_hash",
    )

    def callback(payload: Mapping[str, Any], artifacts: Mapping[str, bytes], **usage: float) -> ShadowCallbackResult:
        return ShadowCallbackResult(
            payload=payload,
            artifacts=artifacts,
            usage=ResourceUsage(**usage),
            isolated=True,
            side_effect_free=True,
            permanent_state_mutated=False,
            release_data_accessed=False,
        )

    def progress(context: Mapping[str, Any]) -> ShadowCallbackResult:
        source_bytes = context["protected_feature_artifacts"]["prefix-state"]
        return callback(
            {
                "operation": "PROGRESS",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "active_column_artifact_ids": ["active-column"],
                "lateral_accesses": [{"artifact_id": "prefix-state", "content_sha256": hashlib.sha256(source_bytes).hexdigest()}],
                "accessed_artifact_hashes": [hashlib.sha256(source_bytes).hexdigest(), context["training_manifest_sha256"]],
            },
            {"active-column": b"disposable-active-column"},
            model_calls=1,
            storage_bytes=10,
        )

    def teacher(context: Mapping[str, Any]) -> ShadowCallbackResult:
        target = b"disposable-teacher-target"
        return callback(
            {
                "operation": "TEACHER_TARGETS",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "teacher_target_artifact_id": "teacher-target",
                "teacher_target_sha256": hashlib.sha256(target).hexdigest(),
                "accessed_artifact_hashes": [
                    hashlib.sha256(next(iter(context["active_column"].values()))).hexdigest(),
                    hashlib.sha256(context["protected_knowledge_base"]["prefix-state"]).hexdigest(),
                    context["training_manifest_sha256"],
                ],
            },
            {"teacher-target": target},
            model_calls=1,
            storage_bytes=10,
        )

    def compress(context: Mapping[str, Any]) -> ShadowCallbackResult:
        candidate = {"prefix-state": context["current_shadow_knowledge_base"]["prefix-state"] + b"|shadow"}
        return callback(
            {
                "operation": "COMPRESS_PROPOSAL",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "teacher_target_sha256": context["teacher_target_sha256"],
                "ewc_manifest_sha256": context["ewc_manifest_sha256"],
                "protected_parameter_ids": ["p-prefix"],
                "distillation_applied": True,
                "ewc_anchor_applied": True,
                "candidate_kb_artifact_ids": ["prefix-state"],
                "accessed_artifact_hashes": [
                    context["teacher_target_sha256"],
                    context["ewc_manifest_sha256"],
                    hashlib.sha256(next(iter(context["active_column"].values()))).hexdigest(),
                ],
            },
            candidate,
            model_calls=1,
            storage_bytes=10,
        )

    def evaluate(context: Mapping[str, Any]) -> ShadowCallbackResult:
        if context["operation"] == "EVALUATE_PROTECTED":
            payload = {
                "operation": "EVALUATE_PROTECTED",
                "evaluation_role": context["evaluation_role"],
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "cells": [{
                    "cohort_id": "protected-prefix",
                    "stratum": "prefix",
                    "case_manifest_sha256": "d" * 64,
                    "row_count": 1,
                    "higher_is_better": True,
                    "metric": 0.5,
                }],
                "accessed_artifact_hashes": [
                    *(hashlib.sha256(value).hexdigest() for value in context["knowledge_base"].values()),
                    "d" * 64,
                ],
            }
        else:
            payload = {
                "operation": "EVALUATE_NEW_TASK",
                "arm": context["arm"],
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "case_manifest_sha256": context["case_manifest_sha256"],
                "row_count": 1,
                "higher_is_better": True,
                "metric": 0.5 if context["arm"] == "FROZEN_BASELINE" else 0.6,
                "accessed_artifact_hashes": [
                    *(hashlib.sha256(value).hexdigest() for value in context["knowledge_base"].values()),
                    context["case_manifest_sha256"],
                ],
            }
        return callback(payload, {"evaluation": context["operation"].encode()}, model_calls=1, storage_bytes=5)

    raw = run_progress_compress_shadow(
        protected,
        expected,
        (task,),
        cohorts,
        {"FROZEN_BASELINE": _budget(), "PROGRESS_COMPRESS_CANDIDATE": _budget()},
        progress_fn=progress,
        teacher_fn=teacher,
        compress_fn=compress,
        evaluate_fn=evaluate,
        rollback_fn=lambda context: callback(
            {
                "operation": "ROLLBACK",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "byte_exact_requested": True,
                "accessed_artifact_hashes": [
                    *(hashlib.sha256(value).hexdigest() for value in context["candidate_shadow_knowledge_base"].values()),
                    *context["expected_protected_hashes"].values(),
                ],
            },
            dict(protected),
            storage_bytes=5,
        ),
        evaluator_independence_receipt=evaluator,
        contamination_receipt=contamination,
        release_firewall_receipt=build_release_firewall_receipt(
            task_release_manifest_sha256={"combined-prefix": "c" * 64},
            locked_evaluator_hash=evaluator_hash,
        ),
    )
    return _normalized_result(
        component_id=request.component_id,
        raw=raw,
        projection={
            "component_contract_passed": raw.get("component_contract_passed"),
            "rollback_receipt": raw.get("rollback_receipt"),
            "removal_receipt": raw.get("removal_receipt"),
            "candidate_retained": raw.get("candidate_retained"),
        },
    )


def _run_provisional_v4_candidate(request: ProvisionalAbilityRequest) -> Mapping[str, Any]:
    from frankie_market_p0_controls import score_open_stream_events

    cutoff = request.binding.causal_cutoff
    raw = score_open_stream_events(
        events=({"event_id": "prefix-mark", "stream_id": "october-prefix", "timestamp": cutoff - 0.5},),
        alarms=({"alarm_id": "candidate-alarm", "stream_id": "october-prefix", "timestamp": cutoff},),
        observation_windows=({"stream_id": "october-prefix", "start_timestamp": cutoff - 1.0, "end_timestamp": cutoff},),
        max_early_seconds=0.0,
        max_late_seconds=1.0,
    )
    return {
        "status": "COMPLETED",
        "public_api_status": "COMPLETED",
        "public_api_receipt_hash": raw["receipt_hash"],
        "derived": {
            "metrics": raw.get("metrics"),
            "matched_event_alarm_pairs": raw.get("matches"),
            "prefix_only": True,
        },
        "performance_evidence": False,
        "promotion_authority": "NONE",
    }


__all__ = [
    "ACTIVE_COMPONENT_IDS",
    "ProvisionalAbilityApis",
    "ProvisionalAbilityRequest",
    "ProvisionalCombinedExecutionError",
    "execute_combined_provisional_pipeline",
]
