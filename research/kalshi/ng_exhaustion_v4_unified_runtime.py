#!/usr/bin/env python3
"""Single-registry / single-engine / single-reconciler V4 runtime contract.

This is an isolated implementation skeleton, not an empirical V4 launch. It deliberately
contains no market model and no permanent-Frankie integration. Lane adapters own only the
narrow target-specific surfaces allowed by the 2026-08-20 unified-framework audit; the
shared engine owns chronology, immutable state/probability movies, lock outcome, reveal
wall, update eligibility, sealed handoff, normalized identity, and reconciliation.

D4/D5 case studies are modes of this SAME engine. There is no alternate case-study runner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from research.kalshi.ng_exhaustion_v4_causal_clock import CausalDiscoveryReceipt
from research.kalshi.ng_exhaustion_v4_gate_verifier import DetectorIntensityResolution, SparseStagePolicy
from research.kalshi.ng_exhaustion_v4_history_support import SessionCoverage
from research.kalshi.ng_exhaustion_v4_lock_outcome import recompute_lock_outcome
from research.kalshi.ng_exhaustion_v4_mechanics import (
    ExecutionHandoff,
    FirstLock,
    PredecessorLifecycle,
    ProbabilityEntry,
    StateMovieRow,
    V4ContractError,
    V4LaneSpec,
    seal_execution_handoff,
    validate_execution_binding,
    validate_probability_movie,
    validate_state_movie,
)

SCHEMA_VERSION = "NG_EXHAUSTION_V4_UNIFIED_RUNTIME_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UnifiedV4Error(V4ContractError):
    pass


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _sha(value: str, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise UnifiedV4Error(f"{field} must be lowercase SHA-256")
    return text


def _json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(dict(value), sort_keys=True, separators=(",", ":")))
    except (TypeError, ValueError) as exc:
        raise UnifiedV4Error("lane restrictions must be deterministic JSON") from exc


@dataclass(frozen=True)
class CaseEnvelope:
    case_id: str
    instance_id: str
    group_id: str
    start_timestamp: float
    end_timestamp: float
    reveal_timestamp: float
    discovery: CausalDiscoveryReceipt
    coverage: tuple[SessionCoverage, ...]
    lifecycles: tuple[PredecessorLifecycle, ...]
    sparse_policy: SparseStagePolicy
    intensity: DetectorIntensityResolution
    case_manifest_sha256: str

    def validate(self) -> "CaseEnvelope":
        for name in ("case_id", "instance_id", "group_id"):
            if not str(getattr(self, name) or "").strip():
                raise UnifiedV4Error(f"{name} must be non-empty")
        try:
            start = float(self.start_timestamp)
            end = float(self.end_timestamp)
            reveal = float(self.reveal_timestamp)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UnifiedV4Error("case timestamps must be finite numbers") from exc
        self.discovery.validate()
        if not start <= end < reveal:
            raise UnifiedV4Error("case must satisfy start <= end < reveal")
        if start < self.discovery.event_known_by:
            raise UnifiedV4Error("case start cannot precede event_known_by")
        if not self.coverage:
            raise UnifiedV4Error("case requires explicit channel coverage manifest")
        for item in self.coverage:
            item.validate()
        if not self.lifecycles:
            raise UnifiedV4Error("case requires predecessor lifecycle state")
        for item in self.lifecycles:
            item.validate()
        self.sparse_policy.validate()
        self.intensity.validate()
        _sha(self.case_manifest_sha256, "case_manifest_sha256")
        return self


class LaneAdapter(Protocol):
    """Only lane-specific surfaces are permitted here."""
    lane_id: str

    def population_identity(self) -> str: ...
    def label_identity(self) -> str: ...
    def reveal_policy_identity(self) -> str: ...
    def feature_schema_identity(self) -> str: ...
    def coordinate_schema_identity(self) -> str: ...
    def case_restrictions(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RegisteredLane:
    spec: V4LaneSpec
    adapter_identity_sha256: str
    adapter_population_id: str
    label_identity: str
    coordinate_schema_identity: str
    restrictions: Mapping[str, Any]
    permanently_non_promotable: bool

    def validate(self) -> "RegisteredLane":
        self.spec.validate()
        if self.spec.adapter_sha256 != _sha(self.adapter_identity_sha256, "adapter_identity_sha256"):
            raise UnifiedV4Error("registered adapter hash does not match V4LaneSpec")
        for value, name in (
            (self.adapter_population_id, "adapter_population_id"),
            (self.label_identity, "label_identity"),
            (self.coordinate_schema_identity, "coordinate_schema_identity"),
        ):
            if not str(value or "").strip():
                raise UnifiedV4Error(f"{name} must be non-empty")
        restrictions = _json_copy(self.restrictions)
        if self.spec.mode == "WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED" and not self.permanently_non_promotable:
            raise UnifiedV4Error("posthoc oracle-conditioned lane must be permanently non-promotable")
        if self.spec.mode == "CASE_STUDY_NO_ADAPTATION" and restrictions.get("adaptation_allowed") is not False:
            raise UnifiedV4Error("case-study lane must explicitly prohibit adaptation")
        return self

    def identity_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "spec": asdict(self.spec),
            "adapter_identity_sha256": self.adapter_identity_sha256,
            "adapter_population_id": self.adapter_population_id,
            "label_identity": self.label_identity,
            "coordinate_schema_identity": self.coordinate_schema_identity,
            "restrictions": _json_copy(self.restrictions),
            "permanently_non_promotable": self.permanently_non_promotable,
        }


class V4LaneRegistry:
    def __init__(self) -> None:
        self._lanes: dict[str, RegisteredLane] = {}

    def register(self, lane: RegisteredLane) -> None:
        lane.validate()
        if lane.spec.lane_id in self._lanes:
            raise UnifiedV4Error(f"duplicate lane_id: {lane.spec.lane_id}")
        # Detach all caller-owned mutable metadata before it can enter the registry.
        # MappingProxyType prevents mutation through the value returned by get(), while
        # _json_copy prevents later caller mutation of the original nested structure.
        frozen_rules = MappingProxyType(_json_copy(lane.restrictions))
        stored = RegisteredLane(
            spec=lane.spec,
            adapter_identity_sha256=lane.adapter_identity_sha256,
            adapter_population_id=str(lane.adapter_population_id),
            label_identity=str(lane.label_identity),
            coordinate_schema_identity=str(lane.coordinate_schema_identity),
            restrictions=frozen_rules,
            permanently_non_promotable=bool(lane.permanently_non_promotable),
        )
        stored.validate()
        self._lanes[stored.spec.lane_id] = stored

    def get(self, lane_id: str) -> RegisteredLane:
        try:
            return self._lanes[lane_id]
        except KeyError as exc:
            raise UnifiedV4Error(f"unregistered lane: {lane_id}") from exc

    def ordered(self) -> tuple[RegisteredLane, ...]:
        return tuple(self._lanes[k] for k in sorted(self._lanes))

    @property
    def registry_hash(self) -> str:
        lanes = self.ordered()
        if not lanes:
            raise UnifiedV4Error("lane registry cannot be empty")
        return _stable_hash(
            {"schema": SCHEMA_VERSION, "lanes": [lane.identity_payload() for lane in lanes]}
        )


@dataclass(frozen=True)
class EngineInput:
    lane_id: str
    case: CaseEnvelope
    state_rows: tuple[StateMovieRow, ...]
    probability_entries: tuple[ProbabilityEntry, ...]
    lock_threshold: float
    lock_persistence: int
    lock_policy_sha256: str
    model_sha256: str
    snapshot_sha256: str
    source_manifest_sha256: str
    eligibility_state: str
    candidate_update_requested: bool


@dataclass(frozen=True)
class NormalizedV4Artifact:
    schema_version: str
    registry_hash: str
    lane_id: str
    lane_mode: str
    case_id: str
    instance_id: str
    case_manifest_sha256: str
    state_movie_hash: str
    probability_movie_hash: str
    first_lock: FirstLock
    execution_handoff: ExecutionHandoff
    reveal_timestamp: float
    update_eligible: bool
    update_applied: bool
    permanently_non_promotable: bool
    normalized_artifact_hash: str


class UnifiedV4Engine:
    """One execution contract for walk-forward, case-study and posthoc benchmark lanes."""

    def __init__(self, registry: V4LaneRegistry) -> None:
        if not registry.ordered():
            raise UnifiedV4Error("unified engine requires non-empty registry")
        self.registry = registry

    def evaluate(self, inp: EngineInput) -> NormalizedV4Artifact:
        lane = self.registry.get(inp.lane_id)
        case = inp.case.validate()
        if not inp.state_rows or not inp.probability_entries:
            raise UnifiedV4Error("state and probability movies must be non-empty")
        if case.instance_id != inp.probability_entries[0].instance_id:
            raise UnifiedV4Error("case/probability instance identity mismatch")
        if case.start_timestamp < case.discovery.event_known_by:
            raise UnifiedV4Error("case begins before causal discovery")

        state_hash = validate_state_movie(inp.state_rows)
        probability_hash = validate_probability_movie(inp.probability_entries)
        if any(row.instance_id != case.instance_id for row in inp.state_rows):
            raise UnifiedV4Error("state movie contains wrong instance")
        if any(entry.signal_lane_id != inp.lane_id for entry in inp.probability_entries):
            raise UnifiedV4Error("probability movie contains wrong lane")
        if any(entry.state_movie_hash != state_hash for entry in inp.probability_entries):
            raise UnifiedV4Error("probability entry is not bound to this state movie")
        if any(entry.causal_evaluation_at >= case.reveal_timestamp for entry in inp.probability_entries):
            raise UnifiedV4Error("prediction movie reaches or crosses reveal time")

        _sha(inp.lock_policy_sha256, "lock_policy_sha256")
        _sha(inp.model_sha256, "model_sha256")
        _sha(inp.snapshot_sha256, "snapshot_sha256")
        _sha(inp.source_manifest_sha256, "source_manifest_sha256")
        if any(entry.model_sha256 != inp.model_sha256 for entry in inp.probability_entries):
            raise UnifiedV4Error("engine model identity differs from probability movie")
        if any(entry.snapshot_sha256 != inp.snapshot_sha256 for entry in inp.probability_entries):
            raise UnifiedV4Error("engine snapshot identity differs from probability movie")
        if any(entry.source_manifest_sha256 != inp.source_manifest_sha256 for entry in inp.probability_entries):
            raise UnifiedV4Error("engine source identity differs from probability movie")

        lock = recompute_lock_outcome(
            inp.probability_entries,
            threshold=inp.lock_threshold,
            persistence=inp.lock_persistence,
            lock_policy_sha256=inp.lock_policy_sha256,
        )
        bound = next((e for e in inp.probability_entries if e.entry_hash == lock.entry_hash), None)
        if bound is None:
            raise UnifiedV4Error("lock/no-lock outcome lacks exact probability identity")

        handoff = seal_execution_handoff(
            signal_id=f"{inp.lane_id}:{case.case_id}:{lock.entry_hash[:16]}",
            execution_handoff_id=f"handoff:{inp.lane_id}:{case.case_id}:{lock.lock_hash[:16]}",
            lane_id=inp.lane_id,
            instance_id=case.instance_id,
            probability_entry_hash=bound.entry_hash,
            first_lock_hash=lock.lock_hash,
            state_movie_hash=state_hash,
            model_sha256=inp.model_sha256,
            snapshot_sha256=inp.snapshot_sha256,
            source_manifest_sha256=inp.source_manifest_sha256,
            eligibility_state=inp.eligibility_state,
            decision_available_at=lock.decision_available_at,
        )
        validate_execution_binding(
            handoff, probability_entry=bound, first_lock=lock, state_movie_hash=state_hash
        )

        # No model mutation exists in this module. It computes only whether a future separately
        # authorized post-reveal update stage could even be eligible.
        update_eligible = (
            lane.spec.mode == "WALK_FORWARD"
            and not lane.permanently_non_promotable
            and inp.candidate_update_requested
        )
        if lane.spec.mode in {
            "CASE_STUDY_NO_ADAPTATION",
            "WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED",
        }:
            update_eligible = False

        core = {
            "schema_version": SCHEMA_VERSION,
            "registry_hash": self.registry.registry_hash,
            "lane_id": inp.lane_id,
            "lane_mode": lane.spec.mode,
            "case_id": case.case_id,
            "instance_id": case.instance_id,
            "case_manifest_sha256": case.case_manifest_sha256,
            "state_movie_hash": state_hash,
            "probability_movie_hash": probability_hash,
            "first_lock_hash": lock.lock_hash,
            "execution_handoff_hash": handoff.handoff_hash,
            "reveal_timestamp": case.reveal_timestamp,
            "update_eligible": update_eligible,
            "update_applied": False,
            "permanently_non_promotable": lane.permanently_non_promotable,
        }
        artifact_hash = _stable_hash(core)
        return NormalizedV4Artifact(
            schema_version=SCHEMA_VERSION,
            registry_hash=self.registry.registry_hash,
            lane_id=inp.lane_id,
            lane_mode=lane.spec.mode,
            case_id=case.case_id,
            instance_id=case.instance_id,
            case_manifest_sha256=case.case_manifest_sha256,
            state_movie_hash=state_hash,
            probability_movie_hash=probability_hash,
            first_lock=lock,
            execution_handoff=handoff,
            reveal_timestamp=case.reveal_timestamp,
            update_eligible=update_eligible,
            update_applied=False,
            permanently_non_promotable=lane.permanently_non_promotable,
            normalized_artifact_hash=artifact_hash,
        )


class UnifiedV4Orchestrator:
    """Registry-driven only; no hard-coded D/POX lane lists are permitted."""

    def __init__(self, registry: V4LaneRegistry) -> None:
        self.registry = registry
        self.engine = UnifiedV4Engine(registry)

    def evaluate(self, inp: EngineInput) -> NormalizedV4Artifact:
        self.registry.get(inp.lane_id)
        return self.engine.evaluate(inp)


class UnifiedV4Reconciler:
    """Recomputes material identities instead of trusting asserted booleans."""

    def __init__(self, registry: V4LaneRegistry) -> None:
        self.registry = registry

    def reconcile(self, inp: EngineInput, artifact: NormalizedV4Artifact) -> dict[str, Any]:
        recomputed = UnifiedV4Engine(self.registry).evaluate(inp)
        fields = (
            "schema_version",
            "registry_hash",
            "lane_id",
            "lane_mode",
            "case_id",
            "instance_id",
            "case_manifest_sha256",
            "state_movie_hash",
            "probability_movie_hash",
            "reveal_timestamp",
            "update_eligible",
            "update_applied",
            "permanently_non_promotable",
            "normalized_artifact_hash",
        )
        mismatches = [name for name in fields if getattr(artifact, name) != getattr(recomputed, name)]
        if artifact.first_lock.lock_hash != recomputed.first_lock.lock_hash:
            mismatches.append("first_lock")
        if artifact.execution_handoff.handoff_hash != recomputed.execution_handoff.handoff_hash:
            mismatches.append("execution_handoff")
        if mismatches:
            raise UnifiedV4Error("reconciliation mismatch: " + ", ".join(sorted(set(mismatches))))
        receipt = {
            "schema": "NG_EXHAUSTION_V4_UNIFIED_RECONCILIATION_V1",
            "registry_hash": self.registry.registry_hash,
            "lane_id": artifact.lane_id,
            "case_id": artifact.case_id,
            "normalized_artifact_hash": artifact.normalized_artifact_hash,
            "first_lock_hash": artifact.first_lock.lock_hash,
            "execution_handoff_hash": artifact.execution_handoff.handoff_hash,
            "recomputed": True,
            "v4_empirical_launch_authorized": False,
            "promotion_authorized": False,
        }
        return {**receipt, "receipt_hash": _stable_hash(receipt)}
