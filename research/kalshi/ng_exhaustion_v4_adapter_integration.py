#!/usr/bin/env python3
"""End-to-end isolated V4 adapter integration contract.

Binds event-known-by -> lawful source availability -> immutable state movie ->
unresolved predecessor lifecycle -> probability movie -> independently recomputed
first-lock/no-lock -> sealed execution handoff -> reveal wall -> registry-driven
reconciler. This module cannot launch V4 or mutate permanent Frankie.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from research.kalshi.ng_exhaustion_v4_causal_clock import (
    CausalDiscoveryReceipt,
    validate_availability_chain,
)
from research.kalshi.ng_exhaustion_v4_mechanics import (
    ProbabilityEntry,
    StateMovieRow,
    validate_probability_movie,
    validate_state_movie,
)
from research.kalshi.ng_exhaustion_v4_unified_runtime import (
    EngineInput,
    NormalizedV4Artifact,
    UnifiedV4Orchestrator,
    UnifiedV4Reconciler,
    V4LaneRegistry,
)

SCHEMA = "NG_EXHAUSTION_V4_ADAPTER_INTEGRATION_V1"


class AdapterIntegrationError(ValueError):
    pass


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class AdapterAvailability:
    feature_available_at: float
    model_evaluated_at: float
    decision_available_at: float


@dataclass(frozen=True)
class AdapterIntegrationInput:
    discovery: CausalDiscoveryReceipt
    availability: AdapterAvailability
    engine_input: EngineInput


class IntegratedV4Adapter:
    def __init__(self, registry: V4LaneRegistry) -> None:
        self.registry = registry
        self.orchestrator = UnifiedV4Orchestrator(registry)
        self.reconciler = UnifiedV4Reconciler(registry)

    def _validate_state_wall(
        self, discovery: CausalDiscoveryReceipt, rows: tuple[StateMovieRow, ...]
    ) -> str:
        movie_hash = validate_state_movie(rows)
        if any(row.event_known_by != discovery.event_known_by for row in rows):
            raise AdapterIntegrationError("state movie event_known_by drift")
        if any(row.causal_second < discovery.event_known_by for row in rows):
            raise AdapterIntegrationError("state movie predates causal discovery")
        return movie_hash

    def _validate_probability_wall(
        self,
        entries: tuple[ProbabilityEntry, ...],
        *,
        feature_available_at: float,
        reveal_timestamp: float,
    ) -> str:
        movie_hash = validate_probability_movie(entries)
        for entry in entries:
            if entry.causal_evaluation_at < feature_available_at:
                raise AdapterIntegrationError("probability evaluation predates lawful feature availability")
            if entry.decision_available_at < entry.causal_evaluation_at:
                raise AdapterIntegrationError("decision availability predates model evaluation")
            if entry.causal_evaluation_at >= reveal_timestamp:
                raise AdapterIntegrationError("probability movie crosses reveal wall")
        return movie_hash

    def run(self, payload: AdapterIntegrationInput) -> dict[str, Any]:
        discovery = payload.discovery.validate()
        inp = payload.engine_input
        if inp.case.discovery.receipt_hash != discovery.receipt_hash:
            raise AdapterIntegrationError("case discovery receipt differs from integrated discovery receipt")

        clocks = validate_availability_chain(
            discovery,
            feature_available_at=payload.availability.feature_available_at,
            model_evaluated_at=payload.availability.model_evaluated_at,
            decision_available_at=payload.availability.decision_available_at,
        )
        state_hash = self._validate_state_wall(discovery, inp.state_rows)
        probability_hash = self._validate_probability_wall(
            inp.probability_entries,
            feature_available_at=clocks["feature_available_at"],
            reveal_timestamp=inp.case.reveal_timestamp,
        )

        for lifecycle in inp.case.lifecycles:
            lifecycle.validate()
            if lifecycle.evaluated_at < discovery.event_known_by:
                raise AdapterIntegrationError("predecessor lifecycle evaluated before event_known_by")

        artifact: NormalizedV4Artifact = self.orchestrator.evaluate(inp)
        if artifact.state_movie_hash != state_hash or artifact.probability_movie_hash != probability_hash:
            raise AdapterIntegrationError("unified engine artifact hashes differ from integrated movies")
        if artifact.first_lock.lock_decided_at is not None and artifact.first_lock.lock_decided_at >= inp.case.reveal_timestamp:
            raise AdapterIntegrationError("first lock crosses reveal wall")
        if artifact.execution_handoff.decision_available_at >= inp.case.reveal_timestamp:
            raise AdapterIntegrationError("sealed execution handoff crosses reveal wall")

        reconciliation = self.reconciler.reconcile(inp, artifact)
        if reconciliation.get("status") not in {"RECONCILED", "UNIFIED_V4_RECONCILED"}:
            # Current reconciler versions may use either status. Any other value fails closed.
            raise AdapterIntegrationError(f"unexpected reconciliation status: {reconciliation.get('status')!r}")

        core = {
            "schema": SCHEMA,
            "status": "V4_ADAPTER_INTEGRATION_RECONCILED",
            "lane_id": inp.lane_id,
            "case_id": inp.case.case_id,
            "discovery_receipt_hash": discovery.receipt_hash,
            "event_known_by": discovery.event_known_by,
            "availability": clocks,
            "state_movie_hash": state_hash,
            "probability_movie_hash": probability_hash,
            "first_lock_hash": artifact.first_lock.lock_hash,
            "execution_handoff_hash": artifact.execution_handoff.handoff_hash,
            "normalized_artifact_hash": artifact.normalized_artifact_hash,
            "reconciliation_hash": reconciliation.get("reconciliation_hash") or reconciliation.get("receipt_hash"),
            "reveal_wall_preserved": True,
            "first_lock_independently_recomputed": True,
            "execution_handoff_sealed": True,
            "v4_empirical_launch": False,
            "promotion_performed": False,
        }
        return {**core, "integration_receipt_hash": _hash(core)}
