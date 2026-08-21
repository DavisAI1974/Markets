#!/usr/bin/env python3
"""Isolated end-to-end NG Exhaustion V4 adapter pipeline.

Flow: event_known_by -> lawful source availability -> immutable state movie ->
prospective predecessor lifecycle -> probability movie -> independently
recomputed first-lock/no-lock -> sealed execution handoff -> reveal wall ->
full recomputation by reconciler.

This module performs no empirical launch, no model training, no holdout access,
and no permanent Frankie mutation. Model evaluation is an injected local
callback so tests can prove the mechanics without external model calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.ng_exhaustion_v4_causal_clock import CausalDiscoveryReceipt, validate_availability_chain
from research.kalshi.ng_exhaustion_v4_lock_outcome import recompute_lock_outcome
from research.kalshi.ng_exhaustion_v4_mechanics import (
    FirstLock,
    PredecessorLifecycle,
    ProbabilityEntry,
    StateMovieRow,
    V4ContractError,
    make_probability_entry,
    seal_execution_handoff,
    validate_execution_binding,
    validate_probability_movie,
    validate_state_movie,
)
from research.kalshi.ng_exhaustion_v4_state_assembler import CausalStateAssembler, FieldPolicy, Observation

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "NG_EXHAUSTION_V4_END_TO_END_ADAPTER_V1"
GENESIS = "0" * 64


class EndToEndV4Error(V4ContractError):
    pass


def _sha(v: Any, field: str) -> str:
    text = str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise EndToEndV4Error(f"{field} must be lowercase SHA-256")
    return text


def _finite(v: Any, field: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EndToEndV4Error(f"{field} must be finite") from exc
    if not math.isfinite(x):
        raise EndToEndV4Error(f"{field} must be finite")
    return x


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class EvaluationClock:
    causal_second: float
    model_evaluated_at: float
    decision_available_at: float

    def validate(self, discovery: CausalDiscoveryReceipt, reveal_timestamp: float) -> "EvaluationClock":
        second = _finite(self.causal_second, "causal_second")
        model = _finite(self.model_evaluated_at, "model_evaluated_at")
        decision = _finite(self.decision_available_at, "decision_available_at")
        reveal = _finite(reveal_timestamp, "reveal_timestamp")
        validate_availability_chain(
            discovery,
            feature_available_at=second,
            model_evaluated_at=model,
            decision_available_at=decision,
        )
        if decision >= reveal:
            raise EndToEndV4Error("reveal wall violated: decision reaches or crosses reveal")
        return self


@dataclass(frozen=True)
class EndToEndInput:
    lane_id: str
    instance_id: str
    discovery: CausalDiscoveryReceipt
    reveal_timestamp: float
    field_policies: tuple[FieldPolicy, ...]
    observations: tuple[Observation, ...]
    evaluation_clocks: tuple[EvaluationClock, ...]
    predecessor_lifecycles: tuple[PredecessorLifecycle, ...]
    source_manifest_sha256: str
    transform_sha256: str
    model_sha256: str
    snapshot_sha256: str
    missingness_manifest_sha256: str
    lock_policy_sha256: str
    lock_threshold: float
    lock_persistence: int
    head_id: str
    eligibility_state: str

    def validate(self) -> "EndToEndInput":
        if not str(self.lane_id or "").strip() or not str(self.instance_id or "").strip():
            raise EndToEndV4Error("lane_id and instance_id are required")
        self.discovery.validate()
        reveal = _finite(self.reveal_timestamp, "reveal_timestamp")
        if reveal <= self.discovery.event_known_by:
            raise EndToEndV4Error("reveal must follow causal event discovery")
        for field in (
            "source_manifest_sha256",
            "transform_sha256",
            "model_sha256",
            "snapshot_sha256",
            "missingness_manifest_sha256",
            "lock_policy_sha256",
        ):
            _sha(getattr(self, field), field)
        if not self.field_policies or not self.evaluation_clocks or not self.predecessor_lifecycles:
            raise EndToEndV4Error("state policies, evaluation clocks and predecessor lifecycle are required")
        for policy in self.field_policies:
            policy.validate()
        for obs in self.observations:
            obs.validate()
        last = float("-inf")
        for clock in self.evaluation_clocks:
            clock.validate(self.discovery, reveal)
            if clock.causal_second <= last:
                raise EndToEndV4Error("evaluation clocks must be strictly increasing")
            last = clock.causal_second
        for lifecycle in self.predecessor_lifecycles:
            lifecycle.validate()
            if lifecycle.instance_id != self.instance_id:
                raise EndToEndV4Error("predecessor lifecycle instance mismatch")
            if lifecycle.evaluated_at >= reveal:
                raise EndToEndV4Error("predecessor lifecycle crosses reveal wall")
        if not 0.0 <= float(self.lock_threshold) <= 1.0 or self.lock_persistence < 1:
            raise EndToEndV4Error("invalid lock policy")
        if not str(self.head_id or "").strip() or not str(self.eligibility_state or "").strip():
            raise EndToEndV4Error("head_id and eligibility_state required")
        return self


@dataclass(frozen=True)
class IntegratedV4Artifact:
    schema: str
    lane_id: str
    instance_id: str
    discovery_receipt_hash: str
    state_rows: tuple[StateMovieRow, ...]
    state_prefix_hashes: tuple[str, ...]
    probability_entries: tuple[ProbabilityEntry, ...]
    probability_movie_hash: str
    predecessor_lifecycle_hash: str
    first_lock: FirstLock
    execution_handoff: Any
    reveal_timestamp: float
    overall_hash: str


ModelCallback = Callable[[tuple[Any, ...], EvaluationClock], Sequence[float]]


def _lifecycle_hash(rows: Sequence[PredecessorLifecycle]) -> str:
    payload = []
    for row in rows:
        row.validate()
        item = asdict(row)
        item["state"] = row.state.value
        payload.append(item)
    return _hash({"schema": SCHEMA, "predecessor_lifecycle": payload})


def run_isolated_adapter(inp: EndToEndInput, model_callback: ModelCallback) -> IntegratedV4Artifact:
    inp.validate()
    assembler = CausalStateAssembler(inp.field_policies, transform_sha256=inp.transform_sha256)
    state_rows: list[StateMovieRow] = []
    prefix_hashes: list[str] = []
    probabilities: list[ProbabilityEntry] = []
    prior_probability_hash = GENESIS

    for clock in inp.evaluation_clocks:
        row = assembler.append_state(
            instance_id=inp.instance_id,
            cutoff=clock.causal_second,
            event_known_by=inp.discovery.event_known_by,
            source_manifest_sha256=inp.source_manifest_sha256,
            observations=inp.observations,
            prior_rows=tuple(state_rows),
        )
        state_rows.append(row)
        prefix_hash = validate_state_movie(tuple(state_rows))
        prefix_hashes.append(prefix_hash)

        raw_probs = tuple(float(x) for x in model_callback(row.fields, clock))
        entry = make_probability_entry(
            signal_lane_id=inp.lane_id,
            instance_id=inp.instance_id,
            head_id=inp.head_id,
            causal_evaluation_at=clock.model_evaluated_at,
            decision_available_at=clock.decision_available_at,
            probabilities=raw_probs,
            state_movie_hash=prefix_hash,
            model_sha256=inp.model_sha256,
            snapshot_sha256=inp.snapshot_sha256,
            source_manifest_sha256=inp.source_manifest_sha256,
            missingness_manifest_sha256=inp.missingness_manifest_sha256,
            prior_entry_hash=prior_probability_hash,
        )
        probabilities.append(entry)
        prior_probability_hash = entry.entry_hash

    state_hash = validate_state_movie(tuple(state_rows))
    probability_hash = validate_probability_movie(tuple(probabilities))
    lock = recompute_lock_outcome(
        tuple(probabilities),
        threshold=inp.lock_threshold,
        persistence=inp.lock_persistence,
        lock_policy_sha256=inp.lock_policy_sha256,
    )
    bound = next((entry for entry in probabilities if entry.entry_hash == lock.entry_hash), None)
    if bound is None:
        raise EndToEndV4Error("recomputed lock/no-lock is not bound to an immutable probability entry")
    if lock.decision_available_at is None or lock.decision_available_at >= inp.reveal_timestamp:
        raise EndToEndV4Error("sealed decision violates reveal wall")

    handoff = seal_execution_handoff(
        signal_id=f"{inp.lane_id}:{inp.instance_id}:{bound.entry_hash[:16]}",
        execution_handoff_id=f"handoff:{inp.lane_id}:{inp.instance_id}:{lock.lock_hash[:16]}",
        lane_id=inp.lane_id,
        instance_id=inp.instance_id,
        probability_entry_hash=bound.entry_hash,
        first_lock_hash=lock.lock_hash,
        state_movie_hash=bound.state_movie_hash,
        model_sha256=inp.model_sha256,
        snapshot_sha256=inp.snapshot_sha256,
        source_manifest_sha256=inp.source_manifest_sha256,
        eligibility_state=inp.eligibility_state,
        decision_available_at=lock.decision_available_at,
    )
    validate_execution_binding(
        handoff,
        probability_entry=bound,
        first_lock=lock,
        state_movie_hash=bound.state_movie_hash,
    )
    lifecycle_hash = _lifecycle_hash(inp.predecessor_lifecycles)
    core = {
        "schema": SCHEMA,
        "lane_id": inp.lane_id,
        "instance_id": inp.instance_id,
        "discovery_receipt_hash": inp.discovery.receipt_hash,
        "state_movie_hash": state_hash,
        "state_prefix_hashes": prefix_hashes,
        "probability_movie_hash": probability_hash,
        "predecessor_lifecycle_hash": lifecycle_hash,
        "first_lock_hash": lock.lock_hash,
        "execution_handoff_hash": handoff.handoff_hash,
        "reveal_timestamp": inp.reveal_timestamp,
        "result_bearing_launch": False,
        "release_holdout_consumed": False,
    }
    return IntegratedV4Artifact(
        schema=SCHEMA,
        lane_id=inp.lane_id,
        instance_id=inp.instance_id,
        discovery_receipt_hash=inp.discovery.receipt_hash,
        state_rows=tuple(state_rows),
        state_prefix_hashes=tuple(prefix_hashes),
        probability_entries=tuple(probabilities),
        probability_movie_hash=probability_hash,
        predecessor_lifecycle_hash=lifecycle_hash,
        first_lock=lock,
        execution_handoff=handoff,
        reveal_timestamp=inp.reveal_timestamp,
        overall_hash=_hash(core),
    )


def reconcile_isolated_adapter(
    inp: EndToEndInput,
    artifact: IntegratedV4Artifact,
    model_callback: ModelCallback,
) -> dict[str, Any]:
    """Recompute the complete isolated pipeline; never trust asserted pass booleans."""
    recomputed = run_isolated_adapter(inp, model_callback)
    mismatches = []
    for field in (
        "schema",
        "lane_id",
        "instance_id",
        "discovery_receipt_hash",
        "state_prefix_hashes",
        "probability_movie_hash",
        "predecessor_lifecycle_hash",
        "reveal_timestamp",
        "overall_hash",
    ):
        if getattr(artifact, field) != getattr(recomputed, field):
            mismatches.append(field)
    if artifact.first_lock.lock_hash != recomputed.first_lock.lock_hash:
        mismatches.append("first_lock")
    if artifact.execution_handoff.handoff_hash != recomputed.execution_handoff.handoff_hash:
        mismatches.append("execution_handoff")
    if mismatches:
        raise EndToEndV4Error("reconciliation mismatch: " + ",".join(mismatches))
    return {
        "schema": SCHEMA,
        "status": "ISOLATED_V4_ADAPTER_RECOMPUTED",
        "overall_hash": artifact.overall_hash,
        "first_lock_hash": artifact.first_lock.lock_hash,
        "execution_handoff_hash": artifact.execution_handoff.handoff_hash,
        "result_bearing_launch_authorized": False,
        "release_holdout_consumed": False,
    }
