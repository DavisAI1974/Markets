"""Deterministic cognitive contracts for Frankie.

This module gives Frankie's reasoning, working memory, and long-term memory
explicit typed boundaries.  It never calls a model, retrieves from the network,
writes canonical memory, promotes a candidate, or enables execution.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

COGNITIVE_CONTRACT_VERSION = "1.0"

ALLOWED_MEMORY_CLASSES = {"WORKING", "EPISODIC", "SEMANTIC", "PROCEDURAL"}
ALLOWED_REASONING_ACTIONS = {"OBSERVE", "RETRIEVE", "REASON", "VERIFY", "ABSTAIN"}
FORBIDDEN_REASONING_ACTIONS = {
    "EXECUTE",
    "TRADE",
    "WRITE_CANONICAL",
    "PROMOTE",
    "CHANGE_PERMISSION",
}
ALLOWED_STEP_STATUS = {"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_APPLICABLE"}
ALLOWED_UNCERTAINTY_LEVELS = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
ALLOWED_MEMORY_AUTHORITIES = {
    "IMMUTABLE_EVIDENCE",
    "RESOLVED_OUTCOME",
    "HUMAN_REVIEWED",
    "SHADOW_DERIVED",
    "RUNTIME_DERIVED",
}
ALLOWED_CHUNK_STATUS = {"PENDING", "ACTIVE", "COMPLETE", "BLOCKED"}

MAX_REASONING_STEPS = 24
MAX_STEP_REFS = 16
MAX_MEMORY_RECORDS = 256
MAX_WORKING_CHUNKS = 32


class CognitiveContractError(ValueError):
    """Raised when a cognitive object violates a deterministic boundary."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _parse_iso(value: Any, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CognitiveContractError(f"{label} is not an ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CognitiveContractError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", text):
        raise CognitiveContractError(f"invalid {label}: {value!r}")
    return text


def _string_list(value: Any, label: str, *, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise CognitiveContractError(f"{label} must be a string list")
    items = tuple(dict.fromkeys(item.strip() for item in value))
    if required and not items:
        raise CognitiveContractError(f"{label} must not be empty")
    return items


@dataclass(frozen=True)
class EvidenceReference:
    ref_id: str
    kind: str
    memory_class: str
    source: str
    knowable_at: str | None
    content_hash: str
    payload_hash: str
    immutable: bool
    status: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def build_cognitive_context(
    *,
    event: Mapping[str, Any],
    candidate: Mapping[str, Any],
    qualification: Mapping[str, Any],
    papers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, read-only evidence and authority catalog for one run."""
    observed_at = _parse_iso(event.get("observed_at"), "event.observed_at")
    refs: list[EvidenceReference] = []
    seen: set[str] = set()

    def add(
        ref_id: str,
        *,
        kind: str,
        memory_class: str,
        source: str,
        knowable_at: str | None,
        content_hash: str,
        payload: Any,
        immutable: bool = True,
        status: str = "ACTIVE",
    ) -> None:
        ref_id = _identifier(ref_id, "evidence ref_id")
        if ref_id in seen:
            raise CognitiveContractError(f"duplicate evidence ref_id: {ref_id}")
        if memory_class not in ALLOWED_MEMORY_CLASSES:
            raise CognitiveContractError(f"invalid memory class for {ref_id}: {memory_class}")
        if knowable_at is not None and _parse_iso(knowable_at, f"{ref_id}.knowable_at") > observed_at:
            raise CognitiveContractError(f"future evidence is not available at decision time: {ref_id}")
        if not str(content_hash).strip():
            raise CognitiveContractError(f"empty content hash for {ref_id}")
        seen.add(ref_id)
        refs.append(
            EvidenceReference(
                ref_id=ref_id,
                kind=kind,
                memory_class=memory_class,
                source=str(source),
                knowable_at=knowable_at,
                content_hash=str(content_hash),
                payload_hash=sha256_json(payload),
                immutable=bool(immutable),
                status=status,
            )
        )

    provenance = event.get("source_provenance")
    if not isinstance(provenance, (list, tuple)) or not provenance:
        raise CognitiveContractError("event source_provenance must be non-empty")
    for index, source in enumerate(provenance):
        if not isinstance(source, Mapping):
            raise CognitiveContractError(f"source_provenance[{index}] must be an object")
        add(
            f"source:{index}",
            kind="SOURCE",
            memory_class="WORKING",
            source=str(source.get("source") or f"source-{index}"),
            knowable_at=str(source.get("knowable_at")) if source.get("knowable_at") else None,
            content_hash=str(source.get("content_hash") or ""),
            payload=dict(source),
        )

    event_knowable = str(event.get("knowable_at") or event.get("observed_at"))
    for name in ("contract_identity", "market_state", "causal_state", "cost_state"):
        payload = event.get(name)
        if not isinstance(payload, Mapping):
            raise CognitiveContractError(f"event.{name} must be an object")
        add(
            f"event:{name}",
            kind="EVENT_STATE",
            memory_class="WORKING",
            source=f"event.{name}",
            knowable_at=event_knowable,
            content_hash=sha256_json(payload),
            payload=dict(payload),
        )

    candidate_id = _identifier(candidate.get("id"), "candidate id")
    add(
        f"candidate:{candidate_id}",
        kind="CANDIDATE_CONTRACT",
        memory_class="PROCEDURAL",
        source="candidate_registry",
        knowable_at=None,
        content_hash=sha256_json(candidate),
        payload=dict(candidate),
    )
    add(
        "derived:qualification",
        kind="DETERMINISTIC_DERIVATION",
        memory_class="WORKING",
        source="frankie_core.qualify_event",
        knowable_at=str(event.get("observed_at")),
        content_hash=sha256_json(qualification),
        payload=dict(qualification),
    )

    for paper in papers:
        paper_id = _identifier(paper.get("id"), "paper id")
        add(
            f"paper:{paper_id}",
            kind="RESEARCH_PAPER",
            memory_class="SEMANTIC",
            source=str(paper.get("url") or "paper_manifest"),
            knowable_at=None,
            content_hash=str(paper.get("source_hash") or sha256_json(paper)),
            payload=dict(paper),
        )

    catalog = [ref.as_dict() for ref in refs]
    return {
        "contract_version": COGNITIVE_CONTRACT_VERSION,
        "memory_classes": sorted(ALLOWED_MEMORY_CLASSES),
        "permitted_actions": sorted(ALLOWED_REASONING_ACTIONS),
        "forbidden_actions": sorted(FORBIDDEN_REASONING_ACTIONS),
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "evidence_catalog": catalog,
        "evidence_ref_ids": [ref.ref_id for ref in refs],
        "evidence_catalog_hash": sha256_json(catalog),
    }


@dataclass(frozen=True)
class ReasoningStep:
    step_id: str
    action: str
    claim: str
    evidence_refs: tuple[str, ...]
    depends_on: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class UncertaintyRecord:
    level: str
    drivers: tuple[str, ...]
    calibrated_probability: float | None


def validate_reasoning_contract(
    raw: Mapping[str, Any],
    *,
    allowed_evidence_refs: set[str],
) -> tuple[tuple[ReasoningStep, ...], UncertaintyRecord, str]:
    """Validate an inspectable reasoning trace without treating it as ground truth."""
    steps_raw = raw.get("reasoning_steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise CognitiveContractError("reasoning_steps must be a non-empty list")
    if len(steps_raw) > MAX_REASONING_STEPS:
        raise CognitiveContractError(f"too many reasoning steps: {len(steps_raw)} > {MAX_REASONING_STEPS}")

    steps: list[ReasoningStep] = []
    seen: set[str] = set()
    for index, item in enumerate(steps_raw):
        if not isinstance(item, Mapping):
            raise CognitiveContractError(f"reasoning_steps[{index}] must be an object")
        step_id = _identifier(item.get("step_id"), f"reasoning_steps[{index}].step_id")
        if step_id in seen:
            raise CognitiveContractError(f"duplicate reasoning step_id: {step_id}")
        action = str(item.get("action") or "").strip().upper()
        if action in FORBIDDEN_REASONING_ACTIONS or action not in ALLOWED_REASONING_ACTIONS:
            raise CognitiveContractError(f"forbidden or unknown reasoning action: {action or '<empty>'}")
        claim = str(item.get("claim") or "").strip()
        if not claim or len(claim) > 4000:
            raise CognitiveContractError(f"reasoning step {step_id} requires a bounded claim")
        refs = _string_list(
            item.get("evidence_refs"),
            f"reasoning step {step_id} evidence_refs",
            required=action != "ABSTAIN",
        )
        if len(refs) > MAX_STEP_REFS:
            raise CognitiveContractError(f"reasoning step {step_id} cites too many evidence refs")
        unknown = sorted(set(refs) - allowed_evidence_refs)
        if unknown:
            raise CognitiveContractError(
                f"reasoning step {step_id} cites unknown evidence refs: {', '.join(unknown)}"
            )
        depends_on = _string_list(
            item.get("depends_on"),
            f"reasoning step {step_id} depends_on",
            required=False,
        )
        forward = sorted(set(depends_on) - seen)
        if forward:
            raise CognitiveContractError(
                f"reasoning step {step_id} depends on missing or later steps: {', '.join(forward)}"
            )
        if action == "VERIFY" and not depends_on:
            raise CognitiveContractError(f"VERIFY step {step_id} must identify a prior step")
        status = str(item.get("status") or "").strip().upper()
        if status not in ALLOWED_STEP_STATUS:
            raise CognitiveContractError(f"reasoning step {step_id} has invalid status: {status}")
        seen.add(step_id)
        steps.append(ReasoningStep(step_id, action, claim, refs, depends_on, status))

    uncertainty_raw = raw.get("uncertainty")
    if not isinstance(uncertainty_raw, Mapping):
        raise CognitiveContractError("uncertainty must be an object")
    level = str(uncertainty_raw.get("level") or "").strip().upper()
    if level not in ALLOWED_UNCERTAINTY_LEVELS:
        raise CognitiveContractError(f"invalid uncertainty level: {level}")
    drivers = _string_list(uncertainty_raw.get("drivers"), "uncertainty.drivers")
    probability_raw = uncertainty_raw.get("calibrated_probability")
    probability: float | None
    if probability_raw is None:
        probability = None
    elif isinstance(probability_raw, bool) or not isinstance(probability_raw, (int, float)):
        raise CognitiveContractError("uncertainty.calibrated_probability must be numeric or null")
    else:
        probability = float(probability_raw)
        if not 0.0 <= probability <= 1.0:
            raise CognitiveContractError("uncertainty.calibrated_probability must be within [0, 1]")
    uncertainty = UncertaintyRecord(level, drivers, probability)
    trace_payload = {
        "steps": [dataclasses.asdict(step) for step in steps],
        "uncertainty": dataclasses.asdict(uncertainty),
    }
    return tuple(steps), uncertainty, sha256_json(trace_payload)


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    memory_class: str
    created_at: str
    knowable_at: str
    content_hash: str
    provenance_refs: tuple[str, ...]
    influence_parent_ids: tuple[str, ...]
    payload: dict[str, Any]
    write_authority: str
    record_hash: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MemoryRecord":
        memory_id = _identifier(raw.get("memory_id"), "memory_id")
        memory_class = str(raw.get("memory_class") or "").strip().upper()
        if memory_class not in ALLOWED_MEMORY_CLASSES:
            raise CognitiveContractError(f"memory {memory_id} has invalid class: {memory_class}")
        created = _parse_iso(raw.get("created_at"), f"memory {memory_id}.created_at")
        knowable = _parse_iso(raw.get("knowable_at"), f"memory {memory_id}.knowable_at")
        if created < knowable:
            raise CognitiveContractError(f"memory {memory_id} was created before it was knowable")
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise CognitiveContractError(f"memory {memory_id} payload must be an object")
        content_hash = str(raw.get("content_hash") or "")
        expected_hash = sha256_json(payload)
        if content_hash != expected_hash:
            raise CognitiveContractError(f"memory {memory_id} content hash does not match payload")
        refs = _string_list(raw.get("provenance_refs"), f"memory {memory_id} provenance_refs")
        parent_raw = raw.get("influence_parent_ids", [])
        if not isinstance(parent_raw, list):
            raise CognitiveContractError(
                f"memory {memory_id} influence_parent_ids must be a list"
            )
        parent_ids = tuple(dict.fromkeys(
            _identifier(value, f"memory {memory_id} influence parent") for value in parent_raw
        ))
        if memory_id in parent_ids:
            raise CognitiveContractError(f"memory {memory_id} cannot influence itself")
        authority = str(raw.get("write_authority") or "").strip().upper()
        if authority not in ALLOWED_MEMORY_AUTHORITIES:
            raise CognitiveContractError(f"memory {memory_id} has invalid write authority: {authority}")
        core = {
            "memory_id": memory_id,
            "memory_class": memory_class,
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "knowable_at": knowable.isoformat().replace("+00:00", "Z"),
            "content_hash": content_hash,
            "provenance_refs": refs,
            "influence_parent_ids": parent_ids,
            "payload": dict(payload),
            "write_authority": authority,
        }
        return cls(**core, record_hash=sha256_json(core))


@dataclass(frozen=True)
class MemoryInvalidation:
    memory_id: str
    invalidated_at: str
    reason: str
    evidence_refs: tuple[str, ...]
    invalidation_hash: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MemoryInvalidation":
        memory_id = _identifier(raw.get("memory_id"), "invalidation memory_id")
        invalidated = _parse_iso(raw.get("invalidated_at"), f"invalidation {memory_id}.invalidated_at")
        reason = str(raw.get("reason") or "").strip()
        if not reason:
            raise CognitiveContractError(f"invalidation {memory_id} requires a reason")
        refs = _string_list(raw.get("evidence_refs"), f"invalidation {memory_id} evidence_refs")
        core = {
            "memory_id": memory_id,
            "invalidated_at": invalidated.isoformat().replace("+00:00", "Z"),
            "reason": reason,
            "evidence_refs": refs,
        }
        return cls(**core, invalidation_hash=sha256_json(core))


@dataclass(frozen=True)
class MemorySelection:
    selected: tuple[MemoryRecord, ...]
    excluded: tuple[dict[str, str], ...]
    decision_at: str
    withdrawal_audit_hash: str
    selection_hash: str


def memory_withdrawal_closure(
    records: Sequence[MemoryRecord],
    *,
    invalidations: Sequence[MemoryInvalidation],
    decision_at: str,
) -> tuple[set[str], set[str]]:
    """Return direct and transitive withdrawals at one causal cutoff.

    A direct tombstone is not enough when a summary, embedding, cached answer,
    or learned procedure was derived from the withdrawn memory.  Every derived
    record must therefore declare its direct ``influence_parent_ids``.  The
    historical records remain append-only; the closure is a serving barrier.
    """
    cutoff = _parse_iso(decision_at, "memory withdrawal decision_at")
    by_id = {record.memory_id: record for record in records}
    if len(by_id) != len(records):
        raise CognitiveContractError("memory withdrawal closure requires unique memory ids")

    children: dict[str, set[str]] = {memory_id: set() for memory_id in by_id}
    for record in records:
        for parent_id in record.influence_parent_ids:
            parent = by_id.get(parent_id)
            if parent is None:
                raise CognitiveContractError(
                    f"memory {record.memory_id} cites unknown influence parent: {parent_id}"
                )
            if _parse_iso(parent.knowable_at, f"memory {parent_id}.knowable_at") > _parse_iso(
                record.knowable_at,
                f"memory {record.memory_id}.knowable_at",
            ):
                raise CognitiveContractError(
                    f"memory {record.memory_id} is knowable before influence parent {parent_id}"
                )
            if _parse_iso(parent.created_at, f"memory {parent_id}.created_at") > _parse_iso(
                record.created_at,
                f"memory {record.memory_id}.created_at",
            ):
                raise CognitiveContractError(
                    f"memory {record.memory_id} was created before influence parent {parent_id}"
                )
            children[parent_id].add(record.memory_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(memory_id: str) -> None:
        if memory_id in visiting:
            raise CognitiveContractError("memory influence graph contains a cycle")
        if memory_id in visited:
            return
        visiting.add(memory_id)
        for child_id in children[memory_id]:
            visit(child_id)
        visiting.remove(memory_id)
        visited.add(memory_id)

    for memory_id in by_id:
        visit(memory_id)

    direct: set[str] = set()
    seen_invalidations: set[str] = set()
    for item in invalidations:
        invalidated_at = _parse_iso(item.invalidated_at, "memory invalidated_at")
        if invalidated_at > cutoff:
            continue
        if item.memory_id not in by_id:
            raise CognitiveContractError(
                f"invalidation references unknown memory: {item.memory_id}"
            )
        if item.memory_id in seen_invalidations:
            raise CognitiveContractError(
                f"duplicate invalidation for memory: {item.memory_id}"
            )
        seen_invalidations.add(item.memory_id)
        record = by_id[item.memory_id]
        if invalidated_at < _parse_iso(
            record.created_at,
            f"memory {record.memory_id}.created_at",
        ):
            raise CognitiveContractError(
                f"memory {item.memory_id} was invalidated before it was created"
            )
        direct.add(item.memory_id)

    withdrawn = set(direct)
    pending = list(direct)
    while pending:
        parent_id = pending.pop()
        for child_id in children[parent_id]:
            if child_id not in withdrawn:
                withdrawn.add(child_id)
                pending.append(child_id)
    return direct, withdrawn


def memory_withdrawal_audit(
    records: Sequence[MemoryRecord],
    *,
    invalidations: Sequence[MemoryInvalidation],
    decision_at: str,
) -> dict[str, Any]:
    """Build a hash-bound receipt for every direct and descendant withdrawal."""
    direct, withdrawn = memory_withdrawal_closure(
        records,
        invalidations=invalidations,
        decision_at=decision_at,
    )
    by_id = {record.memory_id: record for record in records}
    children: dict[str, list[str]] = {memory_id: [] for memory_id in by_id}
    for record in records:
        for parent_id in record.influence_parent_ids:
            children[parent_id].append(record.memory_id)
    for values in children.values():
        values.sort()

    paths: dict[str, list[str]] = {memory_id: [memory_id] for memory_id in sorted(direct)}
    pending = sorted(direct)
    while pending:
        parent_id = pending.pop(0)
        for child_id in children[parent_id]:
            candidate = [*paths[parent_id], child_id]
            if child_id not in paths or tuple(candidate) < tuple(paths[child_id]):
                paths[child_id] = candidate
                pending.append(child_id)
                pending.sort()

    active_invalidations = {
        item.memory_id: item
        for item in invalidations
        if item.memory_id in direct
    }
    normalized_cutoff = _parse_iso(
        decision_at,
        "memory withdrawal decision_at",
    ).isoformat().replace("+00:00", "Z")
    core = {
        "decision_at": normalized_cutoff,
        "record_set_hash": sha256_json(sorted(record.record_hash for record in records)),
        "invalidation_set_hash": sha256_json(
            sorted(item.invalidation_hash for item in active_invalidations.values())
        ),
        "direct_withdrawals": [
            {
                "memory_id": memory_id,
                "record_hash": by_id[memory_id].record_hash,
                "invalidation_hash": active_invalidations[memory_id].invalidation_hash,
                "reason": active_invalidations[memory_id].reason,
                "path": paths[memory_id],
            }
            for memory_id in sorted(direct)
        ],
        "descendant_withdrawals": [
            {
                "memory_id": memory_id,
                "record_hash": by_id[memory_id].record_hash,
                "path": paths[memory_id],
            }
            for memory_id in sorted(withdrawn - direct)
        ],
        "withdrawn_ids": sorted(withdrawn),
        "serving_authority": "WITHDRAW_ONLY",
    }
    return {**core, "audit_hash": sha256_json(core)}


def select_active_memories(
    records: Sequence[MemoryRecord],
    *,
    invalidations: Sequence[MemoryInvalidation],
    decision_at: str,
    allowed_classes: Iterable[str] = ALLOWED_MEMORY_CLASSES,
    max_records: int = 32,
) -> MemorySelection:
    """Serve active memories without deleting invalid or future historical records."""
    if len(records) > MAX_MEMORY_RECORDS:
        raise CognitiveContractError(f"too many memory records: {len(records)}")
    if not 1 <= max_records <= MAX_MEMORY_RECORDS:
        raise CognitiveContractError("max_records is outside the allowed range")
    cutoff = _parse_iso(decision_at, "memory selection decision_at")
    classes = {str(item).upper() for item in allowed_classes}
    unknown_classes = classes - ALLOWED_MEMORY_CLASSES
    if unknown_classes:
        raise CognitiveContractError(f"unknown allowed memory classes: {sorted(unknown_classes)}")

    by_id: dict[str, MemoryRecord] = {}
    for record in records:
        if record.memory_id in by_id:
            raise CognitiveContractError(f"duplicate memory id: {record.memory_id}")
        by_id[record.memory_id] = record
    withdrawal_audit = memory_withdrawal_audit(
        records,
        invalidations=invalidations,
        decision_at=decision_at,
    )
    direct_withdrawals = {
        item["memory_id"] for item in withdrawal_audit["direct_withdrawals"]
    }
    withdrawal_closure = set(withdrawal_audit["withdrawn_ids"])

    selected: list[MemoryRecord] = []
    excluded: list[dict[str, str]] = []
    ordered = sorted(records, key=lambda item: (item.knowable_at, item.memory_id), reverse=True)
    for record in ordered:
        if _parse_iso(record.created_at, f"memory {record.memory_id}.created_at") > cutoff:
            excluded.append({"memory_id": record.memory_id, "reason": "FUTURE_CREATED"})
        elif _parse_iso(record.knowable_at, f"memory {record.memory_id}.knowable_at") > cutoff:
            excluded.append({"memory_id": record.memory_id, "reason": "FUTURE_AT_DECISION"})
        elif record.memory_id in direct_withdrawals:
            excluded.append({"memory_id": record.memory_id, "reason": "INVALIDATED"})
        elif record.memory_id in withdrawal_closure:
            excluded.append({"memory_id": record.memory_id, "reason": "ANCESTOR_INVALIDATED"})
        elif record.memory_class not in classes:
            excluded.append({"memory_id": record.memory_id, "reason": "CLASS_NOT_REQUESTED"})
        elif len(selected) >= max_records:
            excluded.append({"memory_id": record.memory_id, "reason": "BUDGET_EXCEEDED"})
        else:
            selected.append(record)
    normalized_cutoff = cutoff.isoformat().replace("+00:00", "Z")
    payload = {
        "selected": [record.record_hash for record in selected],
        "excluded": excluded,
        "decision_at": normalized_cutoff,
        "withdrawal_audit_hash": withdrawal_audit["audit_hash"],
    }
    return MemorySelection(
        tuple(selected),
        tuple(excluded),
        normalized_cutoff,
        withdrawal_audit["audit_hash"],
        sha256_json(payload),
    )


@dataclass(frozen=True)
class WorkingMemoryChunk:
    subgoal_id: str
    status: str
    summary: str
    evidence_refs: tuple[str, ...]
    depends_on: tuple[str, ...]


def validate_working_memory(
    chunks_raw: Sequence[Mapping[str, Any]],
    *,
    allowed_evidence_refs: set[str],
) -> tuple[tuple[WorkingMemoryChunk, ...], str]:
    if not chunks_raw or len(chunks_raw) > MAX_WORKING_CHUNKS:
        raise CognitiveContractError("working memory requires a bounded non-empty chunk list")
    chunks: list[WorkingMemoryChunk] = []
    seen: set[str] = set()
    active = 0
    for index, raw in enumerate(chunks_raw):
        subgoal_id = _identifier(raw.get("subgoal_id"), f"working chunk {index} subgoal_id")
        if subgoal_id in seen:
            raise CognitiveContractError(f"duplicate working-memory subgoal: {subgoal_id}")
        status = str(raw.get("status") or "").strip().upper()
        if status not in ALLOWED_CHUNK_STATUS:
            raise CognitiveContractError(f"working chunk {subgoal_id} has invalid status: {status}")
        active += status == "ACTIVE"
        summary = str(raw.get("summary") or "").strip()
        if not summary:
            raise CognitiveContractError(f"working chunk {subgoal_id} requires a summary")
        refs = _string_list(raw.get("evidence_refs"), f"working chunk {subgoal_id} evidence_refs")
        unknown = sorted(set(refs) - allowed_evidence_refs)
        if unknown:
            raise CognitiveContractError(
                f"working chunk {subgoal_id} cites unknown evidence: {', '.join(unknown)}"
            )
        depends_on = _string_list(
            raw.get("depends_on"),
            f"working chunk {subgoal_id} depends_on",
            required=False,
        )
        forward = sorted(set(depends_on) - seen)
        if forward:
            raise CognitiveContractError(
                f"working chunk {subgoal_id} depends on missing or later chunks: {', '.join(forward)}"
            )
        seen.add(subgoal_id)
        chunks.append(WorkingMemoryChunk(subgoal_id, status, summary, refs, depends_on))
    if active > 1:
        raise CognitiveContractError("working memory may have at most one ACTIVE subgoal")
    payload = [dataclasses.asdict(chunk) for chunk in chunks]
    return tuple(chunks), sha256_json(payload)
