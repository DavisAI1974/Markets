#!/usr/bin/env python3
"""Bounded HippoRAG-inspired retrieval-to-reader plumbing for Frankie.

This module constructs a disposable associative graph from immutable source
chunks, runs deterministic Personalized PageRank, and gives the selected
chunks to an injected read-only reader.  It is a SHADOW mechanism adapter, not
a reproduction of HippoRAG and not evidence that the mechanism improves
Frankie.  In particular, graph links and graph proximity are associations;
they carry no causal meaning or authority.

All model-like behavior is callback-injected.  A callback must return a typed
``HippoCallbackResult`` and attest that it is read-only and side-effect-free.
The adapter gives callbacks detached inputs and rejects callbacks that mutate
even those detached inputs.  The attestation cannot prove the absence of
external side effects, so callers still have to isolate callbacks.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
import unicodedata
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from frankie_cognition import canonical_json, sha256_json


VERSION = "FRANKIE_HIPPORAG_P0_RETRIEVAL_V1_PROVISIONAL"
COMPONENT = "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
MAX_JSON_BYTES = 2_000_000
ALLOWED_FAULTS = frozenset({"ingest", "open_ie", "graph", "query_entity", "ppr", "reader"})
ALLOWED_CONTROL_METHODS = frozenset({"FLAT_LEXICAL", "FLAT_VECTOR_LIKE"})

IMPLEMENTATION_AUDIT = {
    "depth": "BOUNDED_SHADOW_RETRIEVAL_TO_READER_PIPELINE",
    "hipporag_inspired_mechanisms": [
        "callback-proposed open-IE entities and triples",
        "knowledge-graph construction over source chunks and normalized entities",
        "callback-recognized query entities",
        "deterministic fixed-iteration Personalized PageRank associative retrieval",
        "top-k retrieved source chunks passed to a reader",
    ],
    "frankie_added_governance_and_causality_controls": [
        "immutable content and source hash binding",
        "point-in-time and target-birth firewall",
        "active, invalidation, and descendant withdrawal filtering",
        "exact generated-link provenance and citation-path validation",
        "matched flat-control budget contract",
        "fault, failure, and disposable-removal receipts",
        "no mutation, execution, apply, or promotion authority",
    ],
    "not_implemented": [
        "the paper's extraction prompts, models, synonymy recognition, or corpora",
        "the paper's exact graph schema, retrieval stack, reader, or benchmark replication",
        "learned graph construction or retrieval",
        "held-out answer-quality, calibration, contamination, retention, or rollback evidence",
    ],
}


class HippoRAGContractError(ValueError):
    """Invalid configuration or a failed shadow-pipeline contract."""


class _Rejected(RuntimeError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _json_clone(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HippoRAGContractError(f"{label} must be finite JSON data") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise HippoRAGContractError(f"{label} exceeds the JSON byte limit")
    return json.loads(encoded)


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not IDENTIFIER_RE.fullmatch(text):
        raise HippoRAGContractError(f"invalid {label}: {value!r}")
    return text


def _nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HippoRAGContractError(f"{label} must be non-empty")
    return text


def _sha(value: Any, label: str) -> str:
    text = str(value or "")
    if not SHA256_RE.fullmatch(text):
        raise HippoRAGContractError(f"{label} must be a lowercase SHA-256 value")
    return text


def _parse_time(value: Any, label: str) -> dt.datetime:
    text = _nonempty(value, label)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise HippoRAGContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise HippoRAGContractError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_int(value: Any, label: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HippoRAGContractError(f"{label} must be a positive integer")
    if maximum is not None and value > maximum:
        raise HippoRAGContractError(f"{label} exceeds {maximum}")
    return value


def _normalized_entity(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _nonempty(value, "entity label")).casefold()
    text = " ".join(text.split())
    if len(text) > 240:
        raise HippoRAGContractError("normalized entity label exceeds 240 characters")
    return text


def _entity_id(normalized: str) -> str:
    return "entity:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _chunk_node_id(chunk_id: str) -> str:
    return "chunk:" + chunk_id


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _string_ids(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise HippoRAGContractError(f"{label} must be a sequence")
    values = tuple(_identifier(item, f"{label} item") for item in value)
    if len(set(values)) != len(values):
        raise HippoRAGContractError(f"{label} contains duplicates")
    if not values and not allow_empty:
        raise HippoRAGContractError(f"{label} must not be empty")
    return values


@dataclass(frozen=True)
class HippoCallbackResult:
    """Typed callback output with caller-supplied isolation attestations."""

    payload: Mapping[str, Any]
    read_only: bool = False
    side_effect_free: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise HippoRAGContractError("callback payload must be an object")
        if self.read_only is not True or self.side_effect_free is not True:
            raise HippoRAGContractError(
                "callback must attest read_only=True and side_effect_free=True"
            )


Callback = Callable[[Mapping[str, Any]], HippoCallbackResult]


class _Run:
    def __init__(self, faults: Sequence[str]) -> None:
        if isinstance(faults, (str, bytes)):
            raise HippoRAGContractError("faults must be a sequence")
        self.faults = tuple(sorted(set(str(value).strip() for value in faults)))
        unknown = sorted(set(self.faults) - ALLOWED_FAULTS)
        if unknown:
            raise HippoRAGContractError("unknown fault stages: " + ", ".join(unknown))
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.callback_counts = {"open_ie": 0, "query_entity": 0, "reader": 0}

    def enter(self, stage: str) -> None:
        if stage in self.faults:
            self.events.append({"stage": stage, "event": "FAULT_INJECTED"})
            raise _Rejected(stage, f"fault injected at {stage}")
        self.events.append({"stage": stage, "event": "STAGE_ENTERED"})

    def artifact(self, stage: str, payload: Any) -> str:
        frozen = _json_clone(payload, f"{stage} artifact")
        artifact_hash = sha256_json({"stage": stage, "payload": frozen})
        self.artifacts.append({"stage": stage, "artifact_hash": artifact_hash})
        return artifact_hash

    def callback(self, stage: str, fn: Callback, request: Mapping[str, Any]) -> dict[str, Any]:
        self.enter(stage)
        if not callable(fn):
            raise _Rejected(stage, f"{stage} callback is not callable")
        detached = _json_clone(dict(request), f"{stage} callback request")
        before_hash = sha256_json(detached)
        try:
            result = fn(detached)
        except Exception as exc:  # callback is an isolation boundary
            self.events.append(
                {"stage": stage, "event": "CALLBACK_FAILED", "error_type": type(exc).__name__}
            )
            raise _Rejected(stage, f"callback failed at {stage}") from exc
        if sha256_json(detached) != before_hash:
            self.events.append({"stage": stage, "event": "CALLBACK_INPUT_MUTATION_DETECTED"})
            raise _Rejected(stage, f"callback mutated its detached input at {stage}")
        if not isinstance(result, HippoCallbackResult):
            raise _Rejected(stage, f"callback at {stage} returned the wrong result type")
        try:
            payload = _json_clone(dict(result.payload), f"{stage} callback payload")
        except HippoRAGContractError as exc:
            raise _Rejected(stage, str(exc)) from exc
        self.callback_counts[stage] += 1
        artifact_hash = self.artifact(stage, payload)
        self.events.append(
            {
                "stage": stage,
                "event": "CALLBACK_ACCEPTED",
                "request_hash": before_hash,
                "artifact_hash": artifact_hash,
            }
        )
        return payload

    def finish(
        self,
        status: str,
        reason: str,
        *,
        failed_stage: str | None,
        result: Mapping[str, Any],
        matched_control: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        artifact_hashes = [item["artifact_hash"] for item in self.artifacts]
        removal_core = {
            "method": "DROP_DISPOSABLE_GRAPH_INDEX_RETRIEVAL_AND_READER_OUTPUT",
            "artifact_hashes": artifact_hashes,
            "canonical_state_changed": False,
            "source_chunks_changed": False,
            "external_callback_side_effects": "NOT_VERIFIABLE; CALLER MUST ISOLATE CALLBACKS",
        }
        failure_core = {
            "failed": status != "COMPLETED",
            "failed_stage": failed_stage,
            "reason": reason,
            "fault_plan": list(self.faults),
            "events_hash": sha256_json(self.events),
        }
        core = {
            "version": VERSION,
            "component": COMPONENT,
            "status": status,
            "reason": reason,
            "failed_stage": failed_stage,
            "implementation_audit": IMPLEMENTATION_AUDIT,
            "paper_faithful": False,
            "performance_evidence": False,
            "association_is_causality": False,
            "graph_authority": "DISPOSABLE_DERIVED_ASSOCIATIVE_VIEW_ONLY",
            "execution_enabled": False,
            "automatic_apply": False,
            "promotion_authority": "NONE",
            "mutation_authority": "NONE",
            "canonical_mutation": False,
            "callback_contract": "INJECTED_READ_ONLY_CALLER_ATTESTED_SIDE_EFFECT_FREE",
            "callback_counts": dict(self.callback_counts),
            "events": self.events,
            "artifacts": self.artifacts,
            "matched_control": _json_clone(dict(matched_control or {}), "matched control result"),
            "failure_receipt": {**failure_core, "receipt_hash": sha256_json(failure_core)},
            "removal_receipt": {**removal_core, "receipt_hash": sha256_json(removal_core)},
            "result": _json_clone(dict(result), "pipeline result"),
        }
        return {**core, "result_hash": sha256_json(core)}


def _control_receipt(
    control: Mapping[str, Any],
    *,
    storage_budget_bytes: int,
    top_k: int,
    token_budget: int,
    reader_version_hash: str,
) -> dict[str, Any]:
    if not isinstance(control, Mapping):
        raise HippoRAGContractError("matched_control must be an object")
    method = str(control.get("method") or "").strip().upper()
    if method not in ALLOWED_CONTROL_METHODS:
        raise HippoRAGContractError("matched control must be flat lexical or vector-like retrieval")
    expected = {
        "storage_budget_bytes": storage_budget_bytes,
        "top_k": top_k,
        "token_budget": token_budget,
        "reader_call_budget": 1,
        "reader_version_hash": reader_version_hash,
    }
    for name, expected_value in expected.items():
        if control.get(name) != expected_value:
            raise HippoRAGContractError(f"matched control differs on {name}")
    core = {
        "method": method,
        "candidate_method": "ASSOCIATIVE_GRAPH_PPR",
        "matched_budget_ceilings": expected,
        "same_storage_ceiling": True,
        "same_top_k": True,
        "same_token_budget": True,
        "same_reader_call_budget": True,
        "same_reader_version": True,
        "control_executed": False,
        "performance_comparison": False,
        "scope": "BUDGET_CONTRACT_ONLY; HELD_OUT PAIRED EXECUTION STILL REQUIRED",
    }
    return {**core, "control_receipt_hash": sha256_json(core)}


def _ingest_chunks(
    raw_chunks: Sequence[Mapping[str, Any]],
    invalidations: Sequence[Mapping[str, Any]],
    *,
    decision_cutoff: dt.datetime,
    target_birth: dt.datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(raw_chunks, Sequence) or isinstance(raw_chunks, (str, bytes)) or not raw_chunks:
        raise HippoRAGContractError("source_chunks must be a non-empty sequence")
    records: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_chunks):
        if not isinstance(raw, Mapping):
            raise HippoRAGContractError(f"source_chunks[{index}] must be an object")
        chunk_id = _identifier(raw.get("chunk_id"), f"source_chunks[{index}].chunk_id")
        if chunk_id in records:
            raise HippoRAGContractError(f"duplicate chunk_id: {chunk_id}")
        text = _nonempty(raw.get("text"), f"chunk {chunk_id}.text")
        content_hash = _sha(raw.get("content_hash"), f"chunk {chunk_id}.content_hash")
        if content_hash != _text_hash(text):
            raise HippoRAGContractError(f"chunk {chunk_id} content_hash does not match exact text")
        if raw.get("immutable") is not True:
            raise HippoRAGContractError(f"chunk {chunk_id} must be immutable")
        created_at = _parse_time(raw.get("created_at"), f"chunk {chunk_id}.created_at")
        knowable_at = _parse_time(raw.get("knowable_at"), f"chunk {chunk_id}.knowable_at")
        if knowable_at < created_at:
            raise HippoRAGContractError(f"chunk {chunk_id} is knowable before creation")
        token_count = _positive_int(raw.get("token_count"), f"chunk {chunk_id}.token_count")
        parents = _string_ids(
            raw.get("parent_chunk_ids", []),
            f"chunk {chunk_id}.parent_chunk_ids",
            allow_empty=True,
        )
        if chunk_id in parents:
            raise HippoRAGContractError(f"chunk {chunk_id} cannot parent itself")
        records[chunk_id] = {
            "chunk_id": chunk_id,
            "text": text,
            "source_path": _nonempty(raw.get("source_path"), f"chunk {chunk_id}.source_path"),
            "source_hash": _sha(raw.get("source_hash"), f"chunk {chunk_id}.source_hash"),
            "content_hash": content_hash,
            "created_at": _iso(created_at),
            "knowable_at": _iso(knowable_at),
            "token_count": token_count,
            "parent_chunk_ids": sorted(parents),
            "immutable": True,
        }

    children = {chunk_id: [] for chunk_id in records}
    indegree = {chunk_id: 0 for chunk_id in records}
    for chunk_id, record in records.items():
        for parent_id in record["parent_chunk_ids"]:
            if parent_id not in records:
                raise HippoRAGContractError(f"chunk {chunk_id} cites unknown parent {parent_id}")
            children[parent_id].append(chunk_id)
            indegree[chunk_id] += 1
    pending = deque(sorted(chunk_id for chunk_id, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    while pending:
        chunk_id = pending.popleft()
        visited.append(chunk_id)
        for child_id in sorted(children[chunk_id]):
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                pending.append(child_id)
    if len(visited) != len(records):
        raise HippoRAGContractError("chunk ancestry contains a cycle")

    direct_invalidated: set[str] = set()
    active_invalidations: list[dict[str, Any]] = []
    ignored_future_invalidations: list[str] = []
    if not isinstance(invalidations, Sequence) or isinstance(invalidations, (str, bytes)):
        raise HippoRAGContractError("invalidations must be a sequence")
    seen_invalidations: set[str] = set()
    for index, raw in enumerate(invalidations):
        if not isinstance(raw, Mapping):
            raise HippoRAGContractError(f"invalidations[{index}] must be an object")
        invalidation_id = _identifier(raw.get("invalidation_id"), "invalidation_id")
        if invalidation_id in seen_invalidations:
            raise HippoRAGContractError(f"duplicate invalidation_id: {invalidation_id}")
        seen_invalidations.add(invalidation_id)
        invalidates_id = _identifier(raw.get("invalidates_chunk_id"), "invalidates_chunk_id")
        if invalidates_id not in records:
            raise HippoRAGContractError(f"invalidation cites unknown chunk: {invalidates_id}")
        invalidated_at = _parse_time(raw.get("invalidated_at"), "invalidated_at")
        source_hash = _sha(raw.get("source_hash"), "invalidation.source_hash")
        reason = _nonempty(raw.get("reason"), "invalidation.reason")
        if invalidated_at < _parse_time(records[invalidates_id]["created_at"], "created_at"):
            raise HippoRAGContractError(f"invalidation predates chunk creation: {invalidates_id}")
        item = {
            "invalidation_id": invalidation_id,
            "invalidates_chunk_id": invalidates_id,
            "invalidated_at": _iso(invalidated_at),
            "source_hash": source_hash,
            "reason": reason,
        }
        if invalidated_at <= decision_cutoff and invalidated_at < target_birth:
            direct_invalidated.add(invalidates_id)
            active_invalidations.append(item)
        else:
            ignored_future_invalidations.append(invalidation_id)

    withdrawn = set(direct_invalidated)
    withdrawal_paths = {chunk_id: [chunk_id] for chunk_id in sorted(direct_invalidated)}
    queue = deque(sorted(direct_invalidated))
    while queue:
        parent_id = queue.popleft()
        for child_id in sorted(children[parent_id]):
            candidate = [*withdrawal_paths[parent_id], child_id]
            if child_id not in withdrawal_paths or tuple(candidate) < tuple(withdrawal_paths[child_id]):
                withdrawal_paths[child_id] = candidate
                queue.append(child_id)
            withdrawn.add(child_id)

    unavailable: dict[str, str] = {}
    active: list[dict[str, Any]] = []
    for chunk_id in sorted(records):
        record = records[chunk_id]
        created_at = _parse_time(record["created_at"], "created_at")
        knowable_at = _parse_time(record["knowable_at"], "knowable_at")
        if created_at >= target_birth or knowable_at >= target_birth:
            unavailable[chunk_id] = "AT_OR_AFTER_TARGET_BIRTH"
        elif created_at > decision_cutoff or knowable_at > decision_cutoff:
            unavailable[chunk_id] = "AFTER_DECISION_CUTOFF"
        elif chunk_id in withdrawn:
            unavailable[chunk_id] = "INVALIDATED_OR_DESCENDANT"
        else:
            active.append(record)
    if not active:
        raise HippoRAGContractError("no point-in-time active source chunks remain")

    receipt_core = {
        "source_registry_hash": sha256_json([records[key] for key in sorted(records)]),
        "decision_cutoff_at": _iso(decision_cutoff),
        "target_birth_at": _iso(target_birth),
        "active_chunk_ids": [record["chunk_id"] for record in active],
        "unavailable_chunks": dict(sorted(unavailable.items())),
        "directly_invalidated_chunk_ids": sorted(direct_invalidated),
        "withdrawn_chunk_ids": sorted(withdrawn),
        "withdrawal_paths": {key: withdrawal_paths[key] for key in sorted(withdrawal_paths)},
        "active_invalidations_hash": sha256_json(
            sorted(active_invalidations, key=lambda item: item["invalidation_id"])
        ),
        "ignored_future_invalidation_ids": sorted(ignored_future_invalidations),
        "active_only": True,
        "future_nodes_served": [],
        "withdrawn_nodes_served": [],
    }
    return active, {**receipt_core, "receipt_hash": sha256_json(receipt_core)}


def _construct_graph(
    active_chunks: Sequence[Mapping[str, Any]],
    proposal: Mapping[str, Any],
    *,
    max_entities: int,
    max_triples: int,
) -> dict[str, Any]:
    active_by_id = {str(record["chunk_id"]): record for record in active_chunks}
    raw_entities = proposal.get("entities")
    raw_triples = proposal.get("triples")
    if not isinstance(raw_entities, list) or not raw_entities:
        raise HippoRAGContractError("open-IE proposal requires entities")
    if not isinstance(raw_triples, list):
        raise HippoRAGContractError("open-IE proposal requires a triples list")
    if len(raw_entities) > max_entities or len(raw_triples) > max_triples:
        raise HippoRAGContractError("open-IE proposal exceeds entity or triple bound")

    entities: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_entities):
        if not isinstance(raw, Mapping):
            raise HippoRAGContractError(f"entities[{index}] must be an object")
        normalized = _normalized_entity(raw.get("label"))
        sources = _string_ids(raw.get("source_chunk_ids"), f"entity {normalized} sources")
        unknown = sorted(set(sources) - set(active_by_id))
        if unknown:
            raise HippoRAGContractError(
                f"entity {normalized} cites unavailable source chunks: {', '.join(unknown)}"
            )
        entity_id = _entity_id(normalized)
        existing = entities.get(entity_id)
        if existing is None:
            entities[entity_id] = {
                "node_id": entity_id,
                "node_kind": "ENTITY",
                "normalized_label": normalized,
                "source_chunk_ids": sorted(sources),
            }
        else:
            existing["source_chunk_ids"] = sorted(set(existing["source_chunk_ids"]).union(sources))
    if len(entities) > max_entities:
        raise HippoRAGContractError("normalized entity count exceeds bound")

    triple_edges: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_triples):
        if not isinstance(raw, Mapping):
            raise HippoRAGContractError(f"triples[{index}] must be an object")
        subject_label = _normalized_entity(raw.get("subject"))
        object_label = _normalized_entity(raw.get("object"))
        subject_id = _entity_id(subject_label)
        object_id = _entity_id(object_label)
        if subject_id not in entities or object_id not in entities:
            raise HippoRAGContractError("triple creates a dangling generated-link endpoint")
        predicate = _nonempty(raw.get("predicate"), f"triple {index}.predicate")
        sources = _string_ids(raw.get("source_chunk_ids"), f"triple {index} sources")
        unknown = sorted(set(sources) - set(active_by_id))
        if unknown:
            raise HippoRAGContractError(
                "generated link cites unavailable source chunks: " + ", ".join(unknown)
            )
        if not set(sources).intersection(entities[subject_id]["source_chunk_ids"]):
            raise HippoRAGContractError("generated link lacks subject source provenance")
        if not set(sources).intersection(entities[object_id]["source_chunk_ids"]):
            raise HippoRAGContractError("generated link lacks object source provenance")
        edge_core = {
            "edge_kind": "EXTRACTED_ASSOCIATION",
            "source": subject_id,
            "target": object_id,
            "relation_text": predicate,
            "source_chunk_ids": sorted(sources),
            "generated": True,
            "causal_authority": "NONE",
        }
        triple_edges.append({**edge_core, "edge_id": "edge:" + sha256_json(edge_core)})

    mention_edges: list[dict[str, Any]] = []
    for entity_id in sorted(entities):
        for chunk_id in entities[entity_id]["source_chunk_ids"]:
            edge_core = {
                "edge_kind": "SOURCE_MENTION_ASSOCIATION",
                "source": entity_id,
                "target": _chunk_node_id(chunk_id),
                "source_chunk_ids": [chunk_id],
                "generated": True,
                "causal_authority": "NONE",
            }
            mention_edges.append({**edge_core, "edge_id": "edge:" + sha256_json(edge_core)})

    chunk_nodes = [
        {
            "node_id": _chunk_node_id(str(record["chunk_id"])),
            "node_kind": "IMMUTABLE_SOURCE_CHUNK",
            "chunk_id": record["chunk_id"],
            "source_path": record["source_path"],
            "source_hash": record["source_hash"],
            "content_hash": record["content_hash"],
        }
        for record in sorted(active_chunks, key=lambda item: str(item["chunk_id"]))
    ]
    nodes = sorted([*chunk_nodes, *entities.values()], key=lambda item: item["node_id"])
    edges = sorted([*mention_edges, *triple_edges], key=lambda item: item["edge_id"])
    edge_ids = [item["edge_id"] for item in edges]
    if len(set(edge_ids)) != len(edge_ids):
        raise HippoRAGContractError("knowledge graph contains duplicate generated associations")
    node_ids = {item["node_id"] for item in nodes}
    dangling = sorted(
        item["edge_id"]
        for item in edges
        if item["source"] not in node_ids or item["target"] not in node_ids
    )
    if dangling:
        raise HippoRAGContractError("knowledge graph contains dangling edges")
    if not edges:
        raise HippoRAGContractError("knowledge graph requires at least one association")
    graph_core = {
        "nodes": nodes,
        "edges": edges,
        "edge_direction_for_retrieval": "UNDIRECTED_ASSOCIATION",
        "association_is_causality": False,
        "generated_links_disposable": True,
        "unknown_endpoints": [],
        "active_source_chunk_ids": sorted(active_by_id),
    }
    return {**graph_core, "graph_hash": sha256_json(graph_core)}


def _personalized_page_rank(
    graph: Mapping[str, Any],
    seed_ids: Sequence[str],
    *,
    damping: float,
    iterations: int,
) -> dict[str, Any]:
    node_ids = sorted(str(item["node_id"]) for item in graph["nodes"])
    known = set(node_ids)
    seeds = sorted(set(str(seed) for seed in seed_ids))
    if not seeds or set(seeds) - known:
        raise HippoRAGContractError("PPR seeds must be known and non-empty")
    adjacency: dict[str, dict[str, float]] = {node_id: {} for node_id in node_ids}
    for edge in graph["edges"]:
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in known or target not in known:
            raise HippoRAGContractError("PPR graph contains a dangling edge")
        adjacency[source][target] = adjacency[source].get(target, 0.0) + 1.0
        adjacency[target][source] = adjacency[target].get(source, 0.0) + 1.0
    teleport = {node_id: (1.0 / len(seeds) if node_id in seeds else 0.0) for node_id in node_ids}
    scores = dict(teleport)
    for _ in range(iterations):
        next_scores = {node_id: (1.0 - damping) * teleport[node_id] for node_id in node_ids}
        dangling_mass = sum(scores[node_id] for node_id in node_ids if not adjacency[node_id])
        for node_id in node_ids:
            next_scores[node_id] += damping * dangling_mass * teleport[node_id]
        for source in node_ids:
            links = adjacency[source]
            if not links:
                continue
            total = sum(links.values())
            for target in sorted(links):
                next_scores[target] += damping * scores[source] * links[target] / total
        scores = next_scores
    ordered = sorted(node_ids, key=lambda node_id: (-scores[node_id], node_id))
    core = {
        "seed_node_ids": seeds,
        "scores": {node_id: scores[node_id] for node_id in ordered},
        "ranked_node_ids": ordered,
        "damping": damping,
        "iterations": iterations,
        "tie_break": "NODE_ID_ASCENDING",
        "deterministic": True,
        "association_is_causality": False,
    }
    return {**core, "ppr_hash": sha256_json(core)}


def _select_chunks(
    ppr: Mapping[str, Any],
    active_chunks: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    token_budget: int,
) -> list[dict[str, Any]]:
    scores = ppr["scores"]
    ranked = sorted(
        active_chunks,
        key=lambda item: (-float(scores[_chunk_node_id(str(item["chunk_id"]))]), str(item["chunk_id"])),
    )
    selected: list[dict[str, Any]] = []
    used_tokens = 0
    for record in ranked:
        token_count = int(record["token_count"])
        if used_tokens + token_count > token_budget:
            continue
        selected.append(dict(record))
        used_tokens += token_count
        if len(selected) == top_k:
            break
    if not selected:
        raise HippoRAGContractError("no ranked source chunk fits the token budget")
    for rank, record in enumerate(selected, start=1):
        record["rank"] = rank
        record["ppr_score"] = float(scores[_chunk_node_id(str(record["chunk_id"]))])
    return selected


def _validate_reader_output(
    payload: Mapping[str, Any], selected: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    answer = _nonempty(payload.get("answer"), "reader answer")
    raw_citations = payload.get("citations")
    if not isinstance(raw_citations, list) or not raw_citations:
        raise HippoRAGContractError("reader must return exact source citations")
    by_id = {str(item["chunk_id"]): item for item in selected}
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_citations):
        if not isinstance(raw, Mapping):
            raise HippoRAGContractError(f"reader citations[{index}] must be an object")
        chunk_id = _identifier(raw.get("chunk_id"), "citation.chunk_id")
        if chunk_id in seen:
            raise HippoRAGContractError(f"duplicate reader citation: {chunk_id}")
        seen.add(chunk_id)
        source = by_id.get(chunk_id)
        if source is None:
            raise HippoRAGContractError(f"reader cites an unretrieved chunk: {chunk_id}")
        expected = {
            "chunk_id": chunk_id,
            "source_path": source["source_path"],
            "source_hash": source["source_hash"],
            "content_hash": source["content_hash"],
        }
        if any(raw.get(name) != value for name, value in expected.items()):
            raise HippoRAGContractError(f"reader citation path/hash mismatch for {chunk_id}")
        citations.append(expected)
    return {"answer": answer, "citations": sorted(citations, key=lambda item: item["chunk_id"])}


def run_hipporag_shadow_pipeline(
    *,
    source_chunks: Sequence[Mapping[str, Any]],
    invalidations: Sequence[Mapping[str, Any]],
    query: str,
    decision_cutoff_at: str,
    target_birth_at: str,
    open_ie_fn: Callback,
    query_entity_fn: Callback,
    reader_fn: Callback,
    open_ie_version_hash: str,
    query_entity_version_hash: str,
    reader_version_hash: str,
    matched_control: Mapping[str, Any],
    storage_budget_bytes: int,
    top_k: int = 4,
    token_budget: int = 1024,
    damping: float = 0.85,
    iterations: int = 30,
    max_entities: int = 128,
    max_triples: int = 256,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Run a disposable HippoRAG-inspired SHADOW retrieval pipeline.

    The matched flat control is validated as a budget contract only.  This
    function does not execute that control or create comparative-performance
    evidence.  Source chunks are never modified or installed into canonical
    memory.
    """

    run = _Run(faults)
    control_receipt: dict[str, Any] | None = None
    partial: dict[str, Any] = {}
    try:
        query_text = _nonempty(query, "query")
        cutoff = _parse_time(decision_cutoff_at, "decision_cutoff_at")
        target_birth = _parse_time(target_birth_at, "target_birth_at")
        if cutoff >= target_birth:
            raise _Rejected("ingest", "decision cutoff must be strictly before target birth")
        storage_limit = _positive_int(storage_budget_bytes, "storage_budget_bytes")
        selected_top_k = _positive_int(top_k, "top_k", maximum=32)
        selected_token_budget = _positive_int(token_budget, "token_budget", maximum=1_000_000)
        ppr_iterations = _positive_int(iterations, "iterations", maximum=200)
        entity_limit = _positive_int(max_entities, "max_entities", maximum=4096)
        triple_limit = _positive_int(max_triples, "max_triples", maximum=8192)
        if isinstance(damping, bool) or not isinstance(damping, (int, float)):
            raise _Rejected("ppr", "damping must be numeric")
        damping_value = float(damping)
        if not math.isfinite(damping_value) or not 0.0 < damping_value < 1.0:
            raise _Rejected("ppr", "damping must be finite and within (0, 1)")
        versions = {
            "open_ie_version_hash": _sha(open_ie_version_hash, "open_ie_version_hash"),
            "query_entity_version_hash": _sha(
                query_entity_version_hash, "query_entity_version_hash"
            ),
            "reader_version_hash": _sha(reader_version_hash, "reader_version_hash"),
        }
        control_receipt = _control_receipt(
            matched_control,
            storage_budget_bytes=storage_limit,
            top_k=selected_top_k,
            token_budget=selected_token_budget,
            reader_version_hash=versions["reader_version_hash"],
        )

        run.enter("ingest")
        active_chunks, availability = _ingest_chunks(
            source_chunks,
            invalidations,
            decision_cutoff=cutoff,
            target_birth=target_birth,
        )
        partial["availability_receipt"] = availability
        run.artifact("ingest", availability)

        open_ie_request = {
            "operation": "PROPOSE_OPEN_IE_ASSOCIATIONS",
            "source_chunks": active_chunks,
            "source_registry_hash": availability["source_registry_hash"],
            "cutoff_at": _iso(cutoff),
            "target_birth_at": _iso(target_birth),
            "version_hash": versions["open_ie_version_hash"],
            "read_only": True,
        }
        proposal = run.callback("open_ie", open_ie_fn, open_ie_request)

        run.enter("graph")
        graph = _construct_graph(
            active_chunks,
            proposal,
            max_entities=entity_limit,
            max_triples=triple_limit,
        )
        derived_storage_bytes = len(
            canonical_json({"active_chunks": active_chunks, "knowledge_graph": graph})
        )
        if derived_storage_bytes > storage_limit:
            raise _Rejected("graph", "derived graph/index exceeds matched storage budget")
        graph["derived_storage_bytes"] = derived_storage_bytes
        graph["storage_budget_bytes"] = storage_limit
        partial["graph"] = graph
        run.artifact("graph", graph)

        entity_catalog = [
            {
                "entity_id": node["node_id"],
                "normalized_label": node["normalized_label"],
                "source_chunk_ids": node["source_chunk_ids"],
            }
            for node in graph["nodes"]
            if node["node_kind"] == "ENTITY"
        ]
        recognition = run.callback(
            "query_entity",
            query_entity_fn,
            {
                "operation": "RECOGNIZE_QUERY_ENTITIES",
                "query": query_text,
                "entity_catalog": entity_catalog,
                "graph_hash": graph["graph_hash"],
                "version_hash": versions["query_entity_version_hash"],
                "read_only": True,
            },
        )
        raw_query_entities = recognition.get("entities")
        if not isinstance(raw_query_entities, list) or not raw_query_entities:
            raise _Rejected("query_entity", "query entity callback returned no entities")
        seed_ids = sorted({_entity_id(_normalized_entity(label)) for label in raw_query_entities})
        known_entity_ids = {item["entity_id"] for item in entity_catalog}
        unknown_seeds = sorted(set(seed_ids) - known_entity_ids)
        if unknown_seeds:
            raise _Rejected("query_entity", "query recognizer returned unknown graph entities")

        run.enter("ppr")
        ppr = _personalized_page_rank(
            graph,
            seed_ids,
            damping=damping_value,
            iterations=ppr_iterations,
        )
        selected = _select_chunks(
            ppr,
            active_chunks,
            top_k=selected_top_k,
            token_budget=selected_token_budget,
        )
        selection_core = {
            "ppr": ppr,
            "selected_chunk_ids": [item["chunk_id"] for item in selected],
            "selected_token_count": sum(int(item["token_count"]) for item in selected),
            "top_k_budget": selected_top_k,
            "token_budget": selected_token_budget,
            "deterministic_order": True,
            "tie_break": "PPR_SCORE_DESC_THEN_CHUNK_ID_ASC",
            "active_only": True,
            "association_is_causality": False,
        }
        partial["retrieval"] = {
            **selection_core,
            "retrieval_hash": sha256_json(selection_core),
        }
        run.artifact("ppr", partial["retrieval"])

        reader_payload = run.callback(
            "reader",
            reader_fn,
            {
                "operation": "READ_RETRIEVED_IMMUTABLE_SOURCES",
                "query": query_text,
                "retrieved_chunks": selected,
                "retrieval_hash": partial["retrieval"]["retrieval_hash"],
                "reader_version_hash": versions["reader_version_hash"],
                "reader_call_budget": 1,
                "read_only": True,
            },
        )
        answer = _validate_reader_output(reader_payload, selected)
        answer_core = {
            **answer,
            "reader_version_hash": versions["reader_version_hash"],
            "reader_calls": 1,
            "exact_citation_paths_validated": True,
        }
        partial["reader_output"] = {**answer_core, "reader_output_hash": sha256_json(answer_core)}
        run.artifact("reader_output", partial["reader_output"])
        partial["callback_version_hashes"] = versions
        partial["matched_budget_actuals"] = {
            "derived_storage_bytes": derived_storage_bytes,
            "storage_budget_bytes": storage_limit,
            "returned_chunks": len(selected),
            "top_k_budget": selected_top_k,
            "returned_tokens": selection_core["selected_token_count"],
            "token_budget": selected_token_budget,
            "reader_calls": 1,
            "reader_call_budget": 1,
            "within_all_candidate_ceilings": True,
        }
        return run.finish(
            "COMPLETED",
            "bounded shadow retrieval completed",
            failed_stage=None,
            result=partial,
            matched_control=control_receipt,
        )
    except _Rejected as exc:
        return run.finish(
            "REJECTED",
            exc.reason,
            failed_stage=exc.stage,
            result=partial,
            matched_control=control_receipt,
        )
    except HippoRAGContractError as exc:
        stage = "ingest" if not run.events else str(run.events[-1].get("stage") or "contract")
        return run.finish(
            "REJECTED",
            str(exc),
            failed_stage=stage,
            result=partial,
            matched_control=control_receipt,
        )
