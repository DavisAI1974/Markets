#!/usr/bin/env python3
"""Causal batch-size-1 temporal-graph adapter plumbing for Frankie.

The adapter is inspired by the message/memory shape of TGN and the temporal
attention shape of TGAT.  It is not a trained implementation or a paper-faithful
replication.  Every callback is injected, read-only, side-effect-free by caller
attestation, and bounded.  Results are disposable SHADOW artifacts with no
mutation, execution, apply, or promotion authority.

The defining runtime invariant is predict-before-update at batch size one.  A
prediction sees an immutable snapshot of the scoped node memories and the
active prior-event history.  The current event payload, message, aggregation,
and memory update are withheld until after that prediction is frozen.  Generic
TGN batching does not by itself guarantee per-event or per-second causality;
this adapter fixes batch size to one for that reason.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from frankie_cognition import sha256_json
from frankie_gdl_p0_controls import (
    GDLControlError,
    build_one_wl_control_receipt,
    validate_edgeless_deep_sets_control,
)


VERSION = "FRANKIE_TEMPORAL_GRAPH_P0_ADAPTER_V1_PROVISIONAL"
ZERO_HASH = "0" * 64
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
CALLBACK_STAGES = (
    "time_encode",
    "attention",
    "predict",
    "message",
    "aggregate",
    "memory_update",
)
MODEL_EVENT_TYPES = frozenset({"OBSERVATION", "INTERACTION", "CORRECTION"})
INVALIDATION_EVENT_TYPES = frozenset({"INVALIDATION", "DELETION"})
ALL_EVENT_TYPES = MODEL_EVENT_TYPES | INVALIDATION_EVENT_TYPES
FORBIDDEN_PREBIRTH_FIELDS = frozenset(
    {
        "target_t0",
        "target_birth_at",
        "seconds_to_target_birth",
        "prior_h_identity",
        "target_polarity",
        "target_family",
        "target_depth",
        "future_target_exists",
        "outcome",
        "label",
    }
)
MATCH_FIELDS = (
    "feature_schema_hash",
    "split_hash",
    "case_manifest_hash",
    "compute_budget_hash",
)

IMPLEMENTATION_AUDIT = {
    "depth": "BOUNDED_CAUSAL_BATCH_SIZE_1_MESSAGE_MEMORY_ADAPTER",
    "paper_inspired_mechanisms": [
        "persistent node memory over a chronological typed event stream",
        "event messages and deterministic/injected aggregation",
        "time encoding and temporal attention callbacks",
        "memory reset and chronological replay",
    ],
    "frankie_added_controls": [
        "prediction frozen from a pre-event memory snapshot",
        "batch size fixed to one",
        "separate source/effective/knowable and target-birth firewalls",
        "stream/lane-isolated state",
        "hash-bound immutable events and replay chain",
        "source-sequence tie policy for equal availability times",
        "invalidation/descendant withdrawal with scoped reset-replay",
        "callback mutation, failure, determinism, budget, and fault checks",
        "matched frozen-static, edgeless Deep Sets, and 1-WL controls",
    ],
    "not_implemented": [
        "trained TGN or TGAT parameters, samplers, losses, embeddings, or paper batching",
        "paper-exact message, memory, attention, or neighborhood modules",
        "paper datasets or benchmark replication",
        "held-out performance, calibration, contamination, retention, or live rollback evidence",
    ],
}


class TemporalGraphContractError(ValueError):
    """Malformed event, callback, replay, or matched-control contract."""


class _Stop(RuntimeError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _clone(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise TemporalGraphContractError(f"{label} must be finite JSON data") from exc


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not ID_RE.fullmatch(text):
        raise TemporalGraphContractError(f"invalid {label}: {value!r}")
    return text


def _sha(value: Any, label: str) -> str:
    text = str(value or "")
    if not SHA256_RE.fullmatch(text):
        raise TemporalGraphContractError(f"{label} must be a lowercase SHA-256 value")
    return text


def _parse_time(value: Any, label: str) -> dt.datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise TemporalGraphContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise TemporalGraphContractError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_int(value: Any, label: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TemporalGraphContractError(f"{label} must be a positive integer")
    if maximum is not None and value > maximum:
        raise TemporalGraphContractError(f"{label} exceeds {maximum}")
    return value


def _nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            keys.update(str(key) for key in current)
            pending.extend(current.values())
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            pending.extend(current)
    return keys


def _id_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise TemporalGraphContractError(f"{label} must be a list")
    result = [_identifier(item, f"{label} item") for item in value]
    if len(set(result)) != len(result):
        raise TemporalGraphContractError(f"{label} contains duplicates")
    if not result and not allow_empty:
        raise TemporalGraphContractError(f"{label} must not be empty")
    return result


def temporal_event_content_hash(event: Mapping[str, Any]) -> str:
    """Hash the immutable event body, excluding only ``event_hash``."""
    if not isinstance(event, Mapping):
        raise TemporalGraphContractError("event must be an object")
    return sha256_json({key: value for key, value in event.items() if key != "event_hash"})


@dataclass(frozen=True)
class TemporalCallbackResult:
    payload: Mapping[str, Any]
    read_only: bool = False
    side_effect_free: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise TemporalGraphContractError("callback payload must be an object")
        if self.read_only is not True or self.side_effect_free is not True:
            raise TemporalGraphContractError(
                "callback must attest read_only=True and side_effect_free=True"
            )


Callback = Callable[[Mapping[str, Any]], TemporalCallbackResult]


def _result(payload: Mapping[str, Any]) -> TemporalCallbackResult:
    return TemporalCallbackResult(payload, read_only=True, side_effect_free=True)


def _default_time_encode(request: Mapping[str, Any]) -> TemporalCallbackResult:
    current = _parse_time(request["event_context"]["causal_at"], "causal_at")
    deltas: dict[str, float | None] = {}
    for node_id in request["endpoint_node_ids"]:
        memory = request["pre_event_memory"].get(node_id)
        if not memory or memory.get("updated_at") is None:
            deltas[node_id] = None
        else:
            previous = _parse_time(memory["updated_at"], "memory.updated_at")
            deltas[node_id] = max(0.0, (current - previous).total_seconds())
    return _result(
        {
            "encoding": {
                "seconds_since_endpoint_update": deltas,
                "transform": "LOG1P_AVAILABLE_TO_DOWNSTREAM_CALLBACK",
            }
        }
    )


def _default_attention(request: Mapping[str, Any]) -> TemporalCallbackResult:
    history = list(request["active_prior_event_ids"])
    weights = ({event_id: 1.0 / len(history) for event_id in history} if history else {})
    return _result({"attention": {"prior_event_weights": weights, "learned": False}})


def _default_predict(request: Mapping[str, Any]) -> TemporalCallbackResult:
    basis = {
        "event_context": request["event_context"],
        "pre_event_memory_hash": request["pre_event_memory_hash"],
        "time_encoding": request["time_encoding"],
        "attention": request["attention"],
    }
    return _result(
        {
            "prediction": {
                "abstain": True,
                "score": 0.5,
                "basis_hash": sha256_json(basis),
                "performance_claim": False,
            }
        }
    )


def _default_message(request: Mapping[str, Any]) -> TemporalCallbackResult:
    return _result(
        {
            "message": {
                "event_id": request["event"]["event_id"],
                "event_hash": request["event"]["event_hash"],
                "payload_hash": sha256_json(request["event"]["payload"]),
                "pre_event_memory_hash": request["pre_event_memory_hash"],
            }
        }
    )


def _default_aggregate(request: Mapping[str, Any]) -> TemporalCallbackResult:
    messages = request["messages"]
    return _result(
        {
            "aggregate": {
                "message_hashes": [sha256_json(message) for message in messages],
                "aggregation": "ORDERED_BATCH_SIZE_1",
            }
        }
    )


def _default_memory_update(request: Mapping[str, Any]) -> TemporalCallbackResult:
    updated: dict[str, Any] = {}
    for node_id in request["endpoint_node_ids"]:
        previous = request["pre_event_memory"].get(node_id)
        updated[node_id] = {
            "node_id": node_id,
            "updated_at": request["event_context"]["causal_at"],
            "last_event_id": request["event_context"]["event_id"],
            "previous_memory_hash": sha256_json(previous),
            "aggregate_hash": sha256_json(request["aggregate"]),
        }
    return _result({"node_memories": updated})


DEFAULT_CALLBACKS: Mapping[str, Callback] = {
    "time_encode": _default_time_encode,
    "attention": _default_attention,
    "predict": _default_predict,
    "message": _default_message,
    "aggregate": _default_aggregate,
    "memory_update": _default_memory_update,
}
DEFAULT_CALLBACK_VERSION_HASHES = {
    stage: sha256_json({"adapter_version": VERSION, "default_callback": stage})
    for stage in CALLBACK_STAGES
}


class _Run:
    def __init__(
        self,
        callbacks: Mapping[str, Callback] | None,
        callback_version_hashes: Mapping[str, str] | None,
        *,
        max_callback_calls: int,
        faults: Sequence[str],
    ) -> None:
        supplied = dict(callbacks or {})
        unknown = sorted(set(supplied) - set(CALLBACK_STAGES))
        if unknown:
            raise TemporalGraphContractError("unknown callback stages: " + ", ".join(unknown))
        self.callbacks = {stage: supplied.get(stage, DEFAULT_CALLBACKS[stage]) for stage in CALLBACK_STAGES}
        supplied_versions = dict(callback_version_hashes or {})
        unknown_versions = sorted(set(supplied_versions) - set(CALLBACK_STAGES))
        if unknown_versions:
            raise TemporalGraphContractError(
                "unknown callback version stages: " + ", ".join(unknown_versions)
            )
        self.callback_versions: dict[str, str] = {}
        for stage in CALLBACK_STAGES:
            if stage in supplied:
                if stage not in supplied_versions:
                    raise TemporalGraphContractError(
                        f"injected callback {stage} requires a version hash"
                    )
                self.callback_versions[stage] = _sha(
                    supplied_versions[stage], f"{stage} callback version"
                )
            else:
                if stage in supplied_versions and supplied_versions[stage] != DEFAULT_CALLBACK_VERSION_HASHES[stage]:
                    raise TemporalGraphContractError(
                        f"default callback {stage} cannot be rebound to another version hash"
                    )
                self.callback_versions[stage] = DEFAULT_CALLBACK_VERSION_HASHES[stage]
        self.max_callback_calls = _positive_int(
            max_callback_calls, "max_callback_calls", maximum=1_000_000
        )
        if isinstance(faults, (str, bytes)):
            raise TemporalGraphContractError("faults must be a sequence")
        self.faults = tuple(sorted(set(str(value).strip() for value in faults)))
        self.callback_calls = {stage: 0 for stage in CALLBACK_STAGES}
        self.total_callback_calls = 0
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.determinism_cache: dict[tuple[str, str], str] = {}

    def _fault(self, stage: str, event_id: str) -> None:
        if stage in self.faults or f"{stage}:{event_id}" in self.faults:
            self.events.append({"stage": stage, "event_id": event_id, "event": "FAULT_INJECTED"})
            raise _Stop(stage, f"fault injected at {stage}:{event_id}")

    def local(self, stage: str, event_id: str, payload: Any) -> str:
        frozen = _clone(payload, f"{stage} artifact")
        artifact_hash = sha256_json({"stage": stage, "event_id": event_id, "payload": frozen})
        self.artifacts.append(
            {"stage": stage, "event_id": event_id, "artifact_hash": artifact_hash}
        )
        return artifact_hash

    def call(self, stage: str, event_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        self._fault(stage, event_id)
        if self.total_callback_calls >= self.max_callback_calls:
            raise _Stop(stage, "callback call budget exceeded")
        detached = _clone(dict(request), f"{stage} request")
        request_hash = sha256_json(detached)
        before = request_hash
        try:
            result = self.callbacks[stage](detached)
        except Exception as exc:
            self.events.append(
                {
                    "stage": stage,
                    "event_id": event_id,
                    "event": "CALLBACK_FAILED",
                    "error_type": type(exc).__name__,
                }
            )
            raise _Stop(stage, f"callback failed at {stage}:{event_id}") from exc
        if sha256_json(detached) != before:
            self.events.append(
                {"stage": stage, "event_id": event_id, "event": "CALLBACK_INPUT_MUTATION_DETECTED"}
            )
            raise _Stop(stage, f"callback mutated its detached input at {stage}:{event_id}")
        if not isinstance(result, TemporalCallbackResult):
            raise _Stop(stage, f"callback at {stage}:{event_id} returned the wrong result type")
        try:
            payload = _clone(dict(result.payload), f"{stage} payload")
        except TemporalGraphContractError as exc:
            raise _Stop(stage, str(exc)) from exc
        output_hash = sha256_json(payload)
        cache_key = (stage, request_hash)
        previous = self.determinism_cache.get(cache_key)
        if previous is not None and previous != output_hash:
            raise _Stop(stage, f"callback is nondeterministic on exact replay at {stage}:{event_id}")
        self.determinism_cache[cache_key] = output_hash
        self.total_callback_calls += 1
        self.callback_calls[stage] += 1
        artifact_hash = self.local(stage, event_id, payload)
        self.events.append(
            {
                "stage": stage,
                "event_id": event_id,
                "event": "CALLBACK_ACCEPTED",
                "request_hash": request_hash,
                "output_hash": output_hash,
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
        controls: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        failure_core = {
            "failed": status != "COMPLETED",
            "failed_stage": failed_stage,
            "reason": reason,
            "fault_plan": list(self.faults),
            "event_log_hash": sha256_json(self.events),
        }
        removal_core = {
            "method": "DROP_DISPOSABLE_TEMPORAL_MEMORY_MESSAGES_PREDICTIONS_AND_RECEIPTS",
            "artifact_hashes": [item["artifact_hash"] for item in self.artifacts],
            "canonical_state_changed": False,
            "source_events_changed": False,
            "external_callback_side_effects": "NOT_VERIFIABLE; CALLER MUST ISOLATE CALLBACKS",
        }
        budget_core = {
            "maximum_callback_calls": self.max_callback_calls,
            "actual_total_callback_calls": self.total_callback_calls,
            "actual_by_stage": dict(self.callback_calls),
            "within_budget": self.total_callback_calls <= self.max_callback_calls,
        }
        core = {
            "version": VERSION,
            "status": status,
            "reason": reason,
            "failed_stage": failed_stage,
            "implementation_audit": IMPLEMENTATION_AUDIT,
            "paper_faithful_tgn_or_tgat": False,
            "trained_model": False,
            "performance_evidence": False,
            "batch_size": 1,
            "tgn_batching_causality_warning": (
                "TGN batching semantics do not guarantee per-event or per-second causality; "
                "this bounded adapter requires batch_size=1 and predict-before-update."
            ),
            "execution_enabled": False,
            "automatic_apply": False,
            "promotion_authority": "NONE",
            "mutation_authority": "NONE",
            "canonical_mutation": False,
            "callback_contract": "INJECTED_READ_ONLY_CALLER_ATTESTED_SIDE_EFFECT_FREE",
            "callback_version_hashes": dict(self.callback_versions),
            "callback_budget": {**budget_core, "receipt_hash": sha256_json(budget_core)},
            "events": self.events,
            "artifacts": self.artifacts,
            "control_bindings": _clone(dict(controls or {}), "control bindings result"),
            "failure_receipt": {**failure_core, "receipt_hash": sha256_json(failure_core)},
            "removal_receipt": {**removal_core, "receipt_hash": sha256_json(removal_core)},
            "result": _clone(dict(result), "temporal adapter result"),
        }
        return {**core, "result_hash": sha256_json(core)}


def _normalize_events(
    events: Sequence[Mapping[str, Any]],
    *,
    source_cutoff: dt.datetime,
    effective_cutoff: dt.datetime,
    knowable_cutoff: dt.datetime,
    target_birth: dt.datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)) or not events:
        raise TemporalGraphContractError("events must be a non-empty sequence")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(events):
        if not isinstance(raw, Mapping):
            raise TemporalGraphContractError(f"events[{index}] must be an object")
        event_id = _identifier(raw.get("event_id"), f"events[{index}].event_id")
        if event_id in seen_ids:
            raise TemporalGraphContractError(f"duplicate event_id: {event_id}")
        seen_ids.add(event_id)
        supplied_hash = _sha(raw.get("event_hash"), f"event {event_id}.event_hash")
        expected_hash = temporal_event_content_hash(raw)
        if supplied_hash != expected_hash:
            raise TemporalGraphContractError(f"event {event_id} immutable content hash mismatch")
        source_at = _parse_time(raw.get("source_at"), f"event {event_id}.source_at")
        effective_at = _parse_time(raw.get("effective_at"), f"event {event_id}.effective_at")
        knowable_at = _parse_time(raw.get("knowable_at"), f"event {event_id}.knowable_at")
        causal_at = max(source_at, effective_at, knowable_at)
        event_type = str(raw.get("event_type") or "").strip().upper()
        if event_type not in ALL_EVENT_TYPES:
            raise TemporalGraphContractError(f"event {event_id} has unknown event_type")
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise TemporalGraphContractError(f"event {event_id}.payload must be an object")
        parents = _id_list(
            raw.get("parent_event_ids", []),
            f"event {event_id}.parent_event_ids",
            allow_empty=True,
        )
        sequence = _positive_int(raw.get("source_sequence"), f"event {event_id}.source_sequence")
        item = {
            "event_id": event_id,
            "event_hash": supplied_hash,
            "source_hash": _sha(raw.get("source_hash"), f"event {event_id}.source_hash"),
            "stream_id": _identifier(raw.get("stream_id"), f"event {event_id}.stream_id"),
            "lane_id": _identifier(raw.get("lane_id"), f"event {event_id}.lane_id"),
            "source_node_id": _identifier(
                raw.get("source_node_id"), f"event {event_id}.source_node_id"
            ),
            "target_node_id": _identifier(
                raw.get("target_node_id"), f"event {event_id}.target_node_id"
            ),
            "event_type": event_type,
            "source_sequence": sequence,
            "source_at": _iso(source_at),
            "effective_at": _iso(effective_at),
            "knowable_at": _iso(knowable_at),
            "causal_at": _iso(causal_at),
            "parent_event_ids": parents,
            "payload": _clone(dict(payload), f"event {event_id}.payload"),
            "immutable": raw.get("immutable") is True,
        }
        if not item["immutable"]:
            raise TemporalGraphContractError(f"event {event_id} must be immutable")
        normalized.append(item)

    ordering = sorted(
        normalized,
        key=lambda item: (
            item["causal_at"],
            item["stream_id"],
            item["lane_id"],
            item["source_sequence"],
            item["event_id"],
        ),
    )
    if [item["event_id"] for item in normalized] != [item["event_id"] for item in ordering]:
        raise TemporalGraphContractError(
            "events are out of chronological/source-sequence order; exact ordered replay required"
        )
    per_scope_sequences: dict[tuple[str, str], set[int]] = {}
    equal_time_keys: set[tuple[str, str, str, int]] = set()
    by_id = {item["event_id"]: item for item in normalized}
    position = {item["event_id"]: index for index, item in enumerate(normalized)}
    for item in normalized:
        scope = (item["stream_id"], item["lane_id"])
        sequences = per_scope_sequences.setdefault(scope, set())
        if item["source_sequence"] in sequences:
            raise TemporalGraphContractError(
                f"source_sequence is not unique within stream/lane: {item['event_id']}"
            )
        sequences.add(item["source_sequence"])
        time_key = (*scope, item["causal_at"], item["source_sequence"])
        if time_key in equal_time_keys:
            raise TemporalGraphContractError("equal-time events require distinct source_sequence")
        equal_time_keys.add(time_key)
        for parent_id in item["parent_event_ids"]:
            parent = by_id.get(parent_id)
            if parent is None:
                raise TemporalGraphContractError(
                    f"event {item['event_id']} cites unknown parent {parent_id}"
                )
            if (parent["stream_id"], parent["lane_id"]) != scope:
                raise TemporalGraphContractError(
                    f"event {item['event_id']} cites a cross-stream/lane parent"
                )
            if position[parent_id] >= position[item["event_id"]]:
                raise TemporalGraphContractError(
                    f"event {item['event_id']} cites a future descendant/parent"
                )

    eligible: list[dict[str, Any]] = []
    unavailable: dict[str, str] = {}
    for item in normalized:
        times = {
            "source": _parse_time(item["source_at"], "source_at"),
            "effective": _parse_time(item["effective_at"], "effective_at"),
            "knowable": _parse_time(item["knowable_at"], "knowable_at"),
        }
        if any(value >= target_birth for value in times.values()):
            unavailable[item["event_id"]] = "AT_OR_AFTER_TARGET_BIRTH"
        elif times["source"] > source_cutoff:
            unavailable[item["event_id"]] = "AFTER_SOURCE_CUTOFF"
        elif times["effective"] > effective_cutoff:
            unavailable[item["event_id"]] = "AFTER_EFFECTIVE_CUTOFF"
        elif times["knowable"] > knowable_cutoff:
            unavailable[item["event_id"]] = "AFTER_KNOWABLE_CUTOFF"
        else:
            forbidden = sorted(_nested_keys(item["payload"]).intersection(FORBIDDEN_PREBIRTH_FIELDS))
            if forbidden:
                raise TemporalGraphContractError(
                    f"event {item['event_id']} contains prebirth target-derived fields: {forbidden}"
                )
            eligible.append(item)
    return normalized, eligible, unavailable


def frozen_static_signed_hash_payload(control: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact non-cryptographic manifest payload bound by its SHA-256."""
    if not isinstance(control, Mapping):
        raise TemporalGraphContractError("frozen static control must be an object")
    return {key: value for key, value in control.items() if key != "signed_contract_hash"}


def _validate_controls(bindings: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bindings, Mapping):
        raise TemporalGraphContractError("control_bindings must be an object")
    candidate = bindings.get("candidate_contract")
    frozen = bindings.get("frozen_static_control")
    deep_sets = bindings.get("edgeless_deep_sets_control")
    one_wl = bindings.get("one_wl_control")
    if not all(isinstance(value, Mapping) for value in (candidate, frozen, deep_sets, one_wl)):
        raise TemporalGraphContractError("all four matched control objects are required")
    for field in MATCH_FIELDS:
        candidate_value = _sha(candidate.get(field), f"candidate.{field}")
        for label, control in (("frozen_static", frozen), ("one_wl", one_wl)):
            if control.get(field) != candidate_value:
                raise TemporalGraphContractError(f"{label} control differs on {field}")
    if str(frozen.get("architecture") or "").strip().upper() != "FROZEN_STATIC":
        raise TemporalGraphContractError("frozen static control has the wrong architecture")
    required_frozen = {
        "frozen": True,
        "uses_temporal_memory": False,
        "uses_future_events": False,
    }
    for field, expected in required_frozen.items():
        if frozen.get(field) is not expected:
            raise TemporalGraphContractError(f"frozen static control requires {field}={expected}")
    _sha(frozen.get("model_version_hash"), "frozen static model_version_hash")
    signed = _sha(frozen.get("signed_contract_hash"), "frozen static signed_contract_hash")
    expected_signed = sha256_json(frozen_static_signed_hash_payload(frozen))
    if signed != expected_signed:
        raise TemporalGraphContractError("frozen static signed contract hash mismatch")
    try:
        deep_sets_receipt = validate_edgeless_deep_sets_control(candidate, deep_sets)
        one_wl_receipt = build_one_wl_control_receipt(
            str(one_wl.get("control_id") or ""),
            one_wl.get("graph_a"),
            one_wl.get("graph_b"),
        )
    except GDLControlError as exc:
        raise TemporalGraphContractError(str(exc)) from exc
    if one_wl_receipt.get("valid_control_case") is not True:
        raise TemporalGraphContractError("1-WL control pair is not a valid limitation case")
    core = {
        "candidate_contract_hash": sha256_json(dict(candidate)),
        "frozen_static": {
            "control_hash": sha256_json(dict(frozen)),
            "signed_contract_hash": signed,
            "signature_semantics": "SHA256_MANIFEST_BINDING_NOT_CRYPTOGRAPHIC_SIGNATURE",
            "matched": True,
        },
        "edgeless_deep_sets": deep_sets_receipt,
        "one_wl": {
            "matched_fields": {field: candidate[field] for field in MATCH_FIELDS},
            "control_receipt": one_wl_receipt,
        },
        "all_controls_bound": True,
        "controls_executed_for_performance": False,
        "performance_comparison": False,
    }
    return {**core, "control_binding_hash": sha256_json(core)}


def _scope_key(event: Mapping[str, Any]) -> tuple[str, str]:
    return str(event["stream_id"]), str(event["lane_id"])


def _event_context(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: event[key]
        for key in (
            "event_id",
            "event_hash",
            "stream_id",
            "lane_id",
            "source_node_id",
            "target_node_id",
            "event_type",
            "source_sequence",
            "source_at",
            "effective_at",
            "knowable_at",
            "causal_at",
            "parent_event_ids",
        )
    }


def run_temporal_graph_shadow_adapter(
    *,
    events: Sequence[Mapping[str, Any]],
    source_cutoff_at: str,
    effective_cutoff_at: str,
    knowable_cutoff_at: str,
    target_birth_at: str,
    control_bindings: Mapping[str, Any],
    callbacks: Mapping[str, Callback] | None = None,
    callback_version_hashes: Mapping[str, str] | None = None,
    max_callback_calls: int = 10_000,
    batch_size: int = 1,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Replay typed directed events with predict-before-update causal memory."""

    try:
        run = _Run(
            callbacks,
            callback_version_hashes,
            max_callback_calls=max_callback_calls,
            faults=faults,
        )
    except TemporalGraphContractError:
        raise
    partial: dict[str, Any] = {}
    controls: dict[str, Any] | None = None
    chain: list[dict[str, Any]] = []
    global_previous_hash = ZERO_HASH
    try:
        if batch_size != 1:
            raise _Stop("configuration", "batch_size must equal 1 to prevent same-batch leakage")
        source_cutoff = _parse_time(source_cutoff_at, "source_cutoff_at")
        effective_cutoff = _parse_time(effective_cutoff_at, "effective_cutoff_at")
        knowable_cutoff = _parse_time(knowable_cutoff_at, "knowable_cutoff_at")
        target_birth = _parse_time(target_birth_at, "target_birth_at")
        if any(
            cutoff >= target_birth
            for cutoff in (source_cutoff, effective_cutoff, knowable_cutoff)
        ):
            raise _Stop("configuration", "all replay cutoffs must be strictly before target birth")
        controls = _validate_controls(control_bindings)
        universe, eligible, unavailable = _normalize_events(
            events,
            source_cutoff=source_cutoff,
            effective_cutoff=effective_cutoff,
            knowable_cutoff=knowable_cutoff,
            target_birth=target_birth,
        )
        partial["event_universe_hash"] = sha256_json(universe)
        partial["eligible_event_ids"] = [event["event_id"] for event in eligible]
        partial["unavailable_events"] = unavailable
        partial["cutoff_receipt"] = {
            "source_cutoff_at": _iso(source_cutoff),
            "effective_cutoff_at": _iso(effective_cutoff),
            "knowable_cutoff_at": _iso(knowable_cutoff),
            "target_birth_at": _iso(target_birth),
            "eligible_event_hashes": [event["event_hash"] for event in eligible],
            "future_events_served": [],
            "target_derived_events_served": [],
        }

        memories: dict[tuple[str, str], dict[str, Any]] = {}
        histories: dict[tuple[str, str], list[str]] = {}
        processed: dict[tuple[str, str], list[dict[str, Any]]] = {}
        withdrawn: dict[tuple[str, str], set[str]] = {}
        withdrawal_paths: dict[tuple[str, str], dict[str, list[str]]] = {}
        prediction_rows: list[dict[str, Any]] = []

        def process_model_event(
            event: Mapping[str, Any],
            *,
            emit_prediction: bool,
            record_prediction: bool,
        ) -> dict[str, Any]:
            scope = _scope_key(event)
            scope_memory = memories.setdefault(scope, {})
            history = histories.setdefault(scope, [])
            event_id = str(event["event_id"])
            endpoint_ids = sorted({str(event["source_node_id"]), str(event["target_node_id"])})
            pre_memory = _clone(scope_memory, "pre-event memory snapshot")
            pre_memory_hash = sha256_json(pre_memory)
            context = _event_context(event)
            common = {
                "event_context": context,
                "endpoint_node_ids": endpoint_ids,
                "pre_event_memory": pre_memory,
                "pre_event_memory_hash": pre_memory_hash,
                "active_prior_event_ids": list(history),
                "active_prior_event_ids_hash": sha256_json(history),
                "batch_size": 1,
            }
            stage_order = ["SNAPSHOT_FROZEN"]
            snapshot_artifact_hash = run.local(
                "snapshot", event_id, {"memory": pre_memory, "memory_hash": pre_memory_hash}
            )
            time_output = run.call("time_encode", event_id, common)
            if "encoding" not in time_output:
                raise _Stop("time_encode", "time encoding callback omitted encoding")
            stage_order.append("TIME_ENCODING")
            attention_output = run.call(
                "attention", event_id, {**common, "time_encoding": time_output["encoding"]}
            )
            if "attention" not in attention_output:
                raise _Stop("attention", "attention callback omitted attention")
            stage_order.append("ATTENTION")
            prediction_output: dict[str, Any] | None = None
            prediction_artifact_hash: str | None = None
            if emit_prediction:
                prediction_output = run.call(
                    "predict",
                    event_id,
                    {
                        **common,
                        "time_encoding": time_output["encoding"],
                        "attention": attention_output["attention"],
                        "current_event_payload_available": False,
                        "current_event_message_available": False,
                    },
                )
                if "prediction" not in prediction_output:
                    raise _Stop("predict", "prediction callback omitted prediction")
                prediction_artifact_hash = run.local(
                    "prediction_frozen", event_id, prediction_output["prediction"]
                )
                stage_order.append("PREDICTION_FROZEN")
            message_output = run.call(
                "message",
                event_id,
                {
                    **common,
                    "event": dict(event),
                    "time_encoding": time_output["encoding"],
                    "attention": attention_output["attention"],
                    "prediction_already_frozen": emit_prediction,
                },
            )
            if "message" not in message_output:
                raise _Stop("message", "message callback omitted message")
            stage_order.append("MESSAGE_AFTER_PREDICTION")
            aggregate_output = run.call(
                "aggregate",
                event_id,
                {
                    "event_context": context,
                    "messages": [message_output["message"]],
                    "message_count": 1,
                    "batch_size": 1,
                },
            )
            if "aggregate" not in aggregate_output:
                raise _Stop("aggregate", "aggregate callback omitted aggregate")
            stage_order.append("AGGREGATE_BATCH_SIZE_1")
            update_output = run.call(
                "memory_update",
                event_id,
                {
                    **common,
                    "aggregate": aggregate_output["aggregate"],
                    "prediction_already_frozen": emit_prediction,
                },
            )
            node_memories = update_output.get("node_memories")
            if not isinstance(node_memories, Mapping) or set(node_memories) != set(endpoint_ids):
                raise _Stop(
                    "memory_update", "memory update must return exactly the endpoint node memories"
                )
            for node_id in endpoint_ids:
                scope_memory[node_id] = _clone(node_memories[node_id], f"memory {node_id}")
            history.append(event_id)
            post_memory_hash = sha256_json(scope_memory)
            stage_order.append("MEMORY_UPDATE_AFTER_EVENT")
            event_result = {
                "event_id": event_id,
                "scope": {"stream_id": scope[0], "lane_id": scope[1]},
                "event_hash": event["event_hash"],
                "pre_event_memory_hash": pre_memory_hash,
                "pre_event_memory": pre_memory,
                "snapshot_artifact_hash": snapshot_artifact_hash,
                "prediction": prediction_output["prediction"] if prediction_output else None,
                "prediction_artifact_hash": prediction_artifact_hash,
                "post_event_memory_hash": post_memory_hash,
                "stage_order": stage_order,
                "batch_size": 1,
                "current_event_payload_visible_to_prediction": False,
                "current_message_visible_to_prediction": False,
                "update_before_prediction": False,
            }
            if record_prediction:
                prediction_rows.append(event_result)
            return event_result

        for event in eligible:
            scope = _scope_key(event)
            scope_processed = processed.setdefault(scope, [])
            scope_withdrawn = withdrawn.setdefault(scope, set())
            scope_paths = withdrawal_paths.setdefault(scope, {})
            event_id = str(event["event_id"])
            if event["event_type"] in INVALIDATION_EVENT_TYPES:
                target_ids = _id_list(
                    event["payload"].get("invalidates_event_ids"),
                    f"event {event_id}.invalidates_event_ids",
                )
                prior_by_id = {str(item["event_id"]): item for item in scope_processed}
                unknown = sorted(set(target_ids) - set(prior_by_id))
                if unknown:
                    raise _Stop(
                        "invalidation", "invalidation cites unknown, future, or cross-scope events"
                    )
                children: dict[str, list[str]] = {key: [] for key in prior_by_id}
                for prior in scope_processed:
                    for parent_id in prior["parent_event_ids"]:
                        if parent_id in children:
                            children[parent_id].append(str(prior["event_id"]))
                queue = deque(sorted(target_ids))
                for target_id in sorted(target_ids):
                    scope_withdrawn.add(target_id)
                    scope_paths.setdefault(target_id, [target_id])
                while queue:
                    parent_id = queue.popleft()
                    for child_id in sorted(children[parent_id]):
                        candidate = [*scope_paths[parent_id], child_id]
                        if child_id not in scope_paths or tuple(candidate) < tuple(scope_paths[child_id]):
                            scope_paths[child_id] = candidate
                            queue.append(child_id)
                        scope_withdrawn.add(child_id)
                pre_reset_hash = sha256_json(memories.get(scope, {}))
                run._fault("reset", event_id)
                memories[scope] = {}
                histories[scope] = []
                replayed_ids: list[str] = []
                for prior in scope_processed:
                    prior_id = str(prior["event_id"])
                    if prior_id in scope_withdrawn:
                        continue
                    process_model_event(prior, emit_prediction=False, record_prediction=False)
                    replayed_ids.append(prior_id)
                post_reset_hash = sha256_json(memories[scope])
                reset_core = {
                    "event_id": event_id,
                    "event_hash": event["event_hash"],
                    "scope": {"stream_id": scope[0], "lane_id": scope[1]},
                    "invalidates_event_ids": sorted(target_ids),
                    "withdrawn_event_ids": sorted(scope_withdrawn),
                    "withdrawal_paths": {key: scope_paths[key] for key in sorted(scope_paths)},
                    "pre_reset_memory_hash": pre_reset_hash,
                    "initial_reset_memory_hash": sha256_json({}),
                    "replayed_active_event_ids": replayed_ids,
                    "post_replay_memory_hash": post_reset_hash,
                    "future_topology_used": False,
                    "reset_then_chronological_replay": True,
                }
                link_payload = {
                    "kind": "INVALIDATION_RESET_REPLAY",
                    "event": reset_core,
                    "previous_chain_hash": global_previous_hash,
                }
                link_hash = sha256_json(link_payload)
                chain.append({**link_payload, "chain_link_hash": link_hash})
                global_previous_hash = link_hash
                run.local("invalidation_reset_replay", event_id, reset_core)
                continue

            inherited_paths = [
                scope_paths[parent_id]
                for parent_id in event["parent_event_ids"]
                if parent_id in scope_withdrawn
            ]
            if inherited_paths:
                best = min(tuple(path) for path in inherited_paths)
                scope_withdrawn.add(event_id)
                scope_paths[event_id] = [*best, event_id]
                skipped_core = {
                    "event_id": event_id,
                    "event_hash": event["event_hash"],
                    "scope": {"stream_id": scope[0], "lane_id": scope[1]},
                    "reason": "WITHDRAWN_DESCENDANT",
                    "withdrawal_path": scope_paths[event_id],
                    "memory_changed": False,
                    "prediction_emitted": False,
                }
                link_payload = {
                    "kind": "WITHDRAWN_DESCENDANT_SKIPPED",
                    "event": skipped_core,
                    "previous_chain_hash": global_previous_hash,
                }
                link_hash = sha256_json(link_payload)
                chain.append({**link_payload, "chain_link_hash": link_hash})
                global_previous_hash = link_hash
                scope_processed.append(event)
                continue

            event_result = process_model_event(
                event, emit_prediction=True, record_prediction=True
            )
            link_payload = {
                "kind": "PREDICT_THEN_UPDATE",
                "event": event_result,
                "previous_chain_hash": global_previous_hash,
            }
            link_hash = sha256_json(link_payload)
            chain.append({**link_payload, "chain_link_hash": link_hash})
            global_previous_hash = link_hash
            scope_processed.append(event)

        final_memories = {
            f"{scope[0]}::{scope[1]}": memories.get(scope, {})
            for scope in sorted(set(memories) | set(processed))
        }
        reset_identity_core = {
            "initial_memory": {},
            "initial_memory_hash": sha256_json({}),
            "event_universe_hash": partial["event_universe_hash"],
            "eligible_event_ids": partial["eligible_event_ids"],
            "callback_version_hashes": dict(run.callback_versions),
            "batch_size": 1,
            "ordering_policy": (
                "CAUSAL_AT_THEN_STREAM_THEN_LANE_THEN_SOURCE_SEQUENCE_THEN_EVENT_ID; "
                "EQUAL-TIME EVENTS REQUIRE UNIQUE SOURCE_SEQUENCE"
            ),
        }
        partial.update(
            {
                "predictions": prediction_rows,
                "prediction_count": len(prediction_rows),
                "final_scoped_memories": final_memories,
                "final_scoped_memories_hash": sha256_json(final_memories),
                "withdrawn_event_ids_by_scope": {
                    f"{scope[0]}::{scope[1]}": sorted(values)
                    for scope, values in sorted(withdrawn.items())
                },
                "withdrawal_paths_by_scope": {
                    f"{scope[0]}::{scope[1]}": {
                        key: paths[key] for key in sorted(paths)
                    }
                    for scope, paths in sorted(withdrawal_paths.items())
                },
                "hash_chain": chain,
                "hash_chain_head": global_previous_hash,
                "hash_chain_valid": all(
                    link["previous_chain_hash"]
                    == (ZERO_HASH if index == 0 else chain[index - 1]["chain_link_hash"])
                    and link["chain_link_hash"]
                    == sha256_json({key: value for key, value in link.items() if key != "chain_link_hash"})
                    for index, link in enumerate(chain)
                ),
                "stream_lane_isolation": True,
                "cross_scope_reads": [],
                "reset_identity": {
                    **reset_identity_core,
                    "reset_identity_hash": sha256_json(reset_identity_core),
                },
            }
        )
        return run.finish(
            "COMPLETED",
            "causal batch-size-1 temporal replay completed",
            failed_stage=None,
            result=partial,
            controls=controls,
        )
    except _Stop as exc:
        partial["hash_chain"] = chain
        partial["hash_chain_head"] = global_previous_hash
        return run.finish(
            "REJECTED",
            exc.reason,
            failed_stage=exc.stage,
            result=partial,
            controls=controls,
        )
    except TemporalGraphContractError as exc:
        partial["hash_chain"] = chain
        partial["hash_chain_head"] = global_previous_hash
        return run.finish(
            "REJECTED",
            str(exc),
            failed_stage="contract",
            result=partial,
            controls=controls,
        )


__all__ = [
    "DEFAULT_CALLBACK_VERSION_HASHES",
    "IMPLEMENTATION_AUDIT",
    "TemporalCallbackResult",
    "TemporalGraphContractError",
    "VERSION",
    "frozen_static_signed_hash_payload",
    "run_temporal_graph_shadow_adapter",
    "temporal_event_content_hash",
]
