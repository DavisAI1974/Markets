#!/usr/bin/env python3
"""Execute governing H contracts on each corrected marked prefix.

Compatible contracts execute directly. Pilot/result-bearing paths that the corrected
paired runtime replaces execute their invariant validators and record an explicit
semantic-equivalence comparison; they never acquire launch or lock authority.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any, Mapping

from research.kalshi.frankie_causal_operational_context_20260824 import DecisionStateSnapshot
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import CausalPrefixBinding
from research.kalshi.frankie_v4_authority_runtime_validation_20260824 import H_RUNTIME_MODULES
SCHEMA = "FRANKIE_V4_GOVERNING_PREFIX_EXECUTION_V1_20260824"
EXPECTED_H_MODULE_IDENTITIES = frozenset(name for name, _ in H_RUNTIME_MODULES)
EXPECTED_H_DISPOSITIONS = frozenset(
    {
        "DIRECT_OPERATIONAL_EXECUTION",
        "SUPERSEDED_BY_CORRECTED_RUNTIME_EQUIVALENCE",
    }
)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _module_evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [str(row.get("module", "")) for row in rows]
    identity_set = set(identities)
    if (
        len(rows) != len(EXPECTED_H_MODULE_IDENTITIES)
        or len(identity_set) != len(rows)
        or identity_set != EXPECTED_H_MODULE_IDENTITIES
    ):
        missing = sorted(EXPECTED_H_MODULE_IDENTITIES - identity_set)
        extra = sorted(identity_set - EXPECTED_H_MODULE_IDENTITIES)
        raise ValueError(
            f"governing H execution identity mismatch: missing={missing}, extra={extra}"
        )
    dispositions: dict[str, int] = {name: 0 for name in sorted(EXPECTED_H_DISPOSITIONS)}
    for row in rows:
        disposition = str(row.get("disposition", ""))
        if disposition not in EXPECTED_H_DISPOSITIONS:
            raise ValueError(f"invalid governing H disposition: {disposition}")
        if not isinstance(row.get("execution_hash"), str) or len(row["execution_hash"]) != 64:
            raise ValueError(f"invalid governing H execution hash: {row.get('module')}")
        dispositions[disposition] += 1
    sorted_identities = sorted(identity_set)
    return {
        "module_count": len(rows),
        "module_identities": sorted_identities,
        "module_identity_hash": _hash(sorted_identities),
        "disposition_counts": dispositions,
    }


def validate_v4_governing_runtime_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed on exact H identity/disposition evidence and content identity."""
    rows = receipt.get("modules")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("governing H module evidence is not a list of records")
    evidence = _module_evidence(rows)
    for key, expected in evidence.items():
        if receipt.get(key) != expected:
            raise ValueError(f"governing H receipt {key} drift")
    core = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if receipt.get("receipt_hash") != _hash(core):
        raise ValueError("governing H receipt content hash drift")
    return dict(receipt)


def build_v4_governing_input_context(
    *, binding: CausalPrefixBinding, snapshot: DecisionStateSnapshot,
    source_object_id: str, source_object_sha256: str,
) -> dict[str, Any]:
    """Execute pre-decision H contracts and return the shared two-lane input receipt."""
    from research.kalshi import ng_exhaustion_v4_causal_clock as clock
    from research.kalshi import ng_exhaustion_v4_causal_entry_adapter as entry
    from research.kalshi import ng_exhaustion_v4_state_assembler as assembler
    from research.kalshi import ng_exhaustion_v4_mechanics as mechanics
    from research.kalshi import ng_exhaustion_v4_detector_intensity as intensity
    from research.kalshi import ng_exhaustion_v4_detector_intensity_semantics as semantics
    from research.kalshi import ng_exhaustion_v4_history_support as history

    bound = binding.validate()
    snap = snapshot.validate()
    discovery = clock.make_receipt(
        event_id=bound.causal_prefix_hash, session_id=str(source_object_id),
        detector_revision="CORRECTED_CONTINUOUS_V4_MARK",
        detector_source_sha256=source_object_sha256,
        source_manifest_sha256=bound.knowledge_manifest_hash,
        source_object_id=source_object_id, source_range_id=f"prefix:{bound.causal_prefix_hash}",
        source_ts_event=bound.event_known_by, source_ts_recv=bound.event_known_by,
        detector_marked_at=bound.event_known_by, event_known_by=bound.event_known_by,
        canonical_t0=bound.event_known_by, mark_mode="CAUSAL_REPLAY",
    )
    clocks = entry.authorize_v4_evaluation(
        receipt=discovery, feature_available_at=bound.causal_cutoff,
        model_evaluated_at=bound.causal_cutoff, decision_available_at=bound.causal_cutoff,
    )
    policy = assembler.FieldPolicy(
        "complete_s135_present_count", snap.source_snapshot_leaf_hash, 0.0
    )
    observation = assembler.Observation(
        policy.name, snap.present_count, bound.event_known_by, bound.event_known_by,
        bound.causal_cutoff, snap.source_snapshot_leaf_hash, snap.snapshot_hash,
    )
    state_row = assembler.CausalStateAssembler(
        (policy,), transform_sha256=snap.registry_receipt_hash
    ).append_state(
        instance_id=bound.causal_prefix_hash, cutoff=bound.causal_cutoff,
        event_known_by=bound.event_known_by,
        source_manifest_sha256=bound.knowledge_manifest_hash, observations=(observation,),
    )
    state_hash = mechanics.validate_state_movie((state_row,))
    proxy = intensity.default_v4_proxy(
        transform_sha256=snap.registry_receipt_hash, source_sha256=source_object_sha256
    )
    resolved = intensity.resolve_detector_intensity(proxy=proxy)
    semantic = semantics.explicit_proxy(
        proxy_namespace="v4_proxy.corrected_continuous_prefix",
        proxy_source_sha256=source_object_sha256,
        transform_sha256=snap.registry_receipt_hash,
    )
    coverage = history.make_session_coverage(
        session_id=str(source_object_id), requested_symbol="NG.v.0", mbo="VERIFIED",
        mbp10="NOT_APPLICABLE", l1="NOT_APPLICABLE",
        native_object_sha256s=(source_object_sha256,), symbology_binding_hashes=(),
    )
    core = {
        "schema": "FRANKIE_V4_GOVERNING_INPUT_CONTEXT_V1_20260824",
        "causal_prefix_hash": bound.causal_prefix_hash,
        "snapshot_hash": snap.snapshot_hash,
        "same_context_required_both_lanes": True,
        "modules": {
            "ng_exhaustion_v4_causal_clock": discovery.receipt_hash,
            "ng_exhaustion_v4_causal_entry_adapter": _hash(clocks),
            "ng_exhaustion_v4_state_assembler": state_row.row_hash,
            "ng_exhaustion_v4_mechanics": state_hash,
            "ng_exhaustion_v4_detector_intensity": resolved["resolution_hash"],
            "ng_exhaustion_v4_detector_intensity_semantics": semantic["proxy_receipt_sha256"],
            "ng_exhaustion_v4_history_support": coverage.coverage_manifest_hash,
        },
    }
    return {**core, "receipt_hash": _hash(core)}


def execute_v4_governing_prefix(
    *,
    binding: CausalPrefixBinding,
    snapshot: DecisionStateSnapshot,
    paired: Any,
    source_object_id: str,
    source_object_sha256: str,
    source_commit: str,
    governing_input_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # Local imports make each governing module's actual execution visible at prefix time.
    from research.kalshi import ng_exhaustion_v4_causal_clock as clock
    from research.kalshi import ng_exhaustion_v4_causal_entry_adapter as entry
    from research.kalshi import ng_exhaustion_v4_state_assembler as assembler
    from research.kalshi import ng_exhaustion_v4_mechanics as mechanics
    from research.kalshi import ng_exhaustion_v4_detector_intensity as intensity
    from research.kalshi import ng_exhaustion_v4_detector_intensity_semantics as intensity_semantics
    from research.kalshi import ng_exhaustion_v4_history_support as history
    from research.kalshi import ng_exhaustion_v4_lock_outcome as lock_outcome
    from research.kalshi import ng_exhaustion_v4_adapter_integration as adapter_integration
    from research.kalshi import ng_exhaustion_v4_end_to_end_adapter as end_to_end
    from research.kalshi import ng_exhaustion_v4_unified_runtime as unified
    from research.kalshi import ng_exhaustion_v4_exact_candidate_freeze as exact_freeze
    from research.kalshi import ng_exhaustion_v4_gate_verifier as gates
    from research.kalshi import ng_exhaustion_v4_pilot_chunk_guard as pilot_guard
    from research.kalshi import ng_exhaustion_v4_pilot_chunk_guardrail as pilot_guardrail

    bound = binding.validate()
    snap = snapshot.validate()
    if snap.run_id != bound.run_id or snap.evaluated_at != bound.causal_cutoff:
        raise ValueError("governing execution snapshot differs from causal prefix")
    if paired.answer_revealed or not paired.identical_prefix_proof.proved:
        raise ValueError("governing execution requires sealed identical-prefix proof")
    expected_input = build_v4_governing_input_context(
        binding=bound, snapshot=snap, source_object_id=source_object_id,
        source_object_sha256=source_object_sha256,
    )
    supplied_input = dict(governing_input_context or expected_input)
    if supplied_input != expected_input:
        raise ValueError("provider governing input context differs from executed H receipt")

    discovery = clock.make_receipt(
        event_id=bound.causal_prefix_hash,
        session_id=str(source_object_id),
        detector_revision="CORRECTED_CONTINUOUS_V4_MARK",
        detector_source_sha256=source_object_sha256,
        source_manifest_sha256=bound.knowledge_manifest_hash,
        source_object_id=source_object_id,
        source_range_id=f"prefix:{bound.causal_prefix_hash}",
        source_ts_event=bound.event_known_by,
        source_ts_recv=bound.event_known_by,
        detector_marked_at=bound.event_known_by,
        event_known_by=bound.event_known_by,
        canonical_t0=bound.event_known_by,
        mark_mode="CAUSAL_REPLAY",
    )
    lawful_clocks = entry.authorize_v4_evaluation(
        receipt=discovery,
        feature_available_at=bound.causal_cutoff,
        model_evaluated_at=bound.causal_cutoff,
        decision_available_at=bound.causal_cutoff,
    )
    policy = assembler.FieldPolicy(
        name="complete_s135_present_count",
        source_identity_sha256=snap.source_snapshot_leaf_hash,
        stale_after_seconds=0.0,
    )
    observation = assembler.Observation(
        field_name=policy.name,
        value=snap.present_count,
        ts_event=bound.event_known_by,
        ts_recv=bound.event_known_by,
        available_at=bound.causal_cutoff,
        source_identity_sha256=snap.source_snapshot_leaf_hash,
        observation_id=snap.snapshot_hash,
    )
    state_row = assembler.CausalStateAssembler(
        (policy,), transform_sha256=snap.registry_receipt_hash
    ).append_state(
        instance_id=bound.causal_prefix_hash,
        cutoff=bound.causal_cutoff,
        event_known_by=bound.event_known_by,
        source_manifest_sha256=bound.knowledge_manifest_hash,
        observations=(observation,),
    )
    state_movie_hash = mechanics.validate_state_movie((state_row,))
    proxy = intensity.default_v4_proxy(
        transform_sha256=snap.registry_receipt_hash,
        source_sha256=source_object_sha256,
    )
    intensity_resolution = intensity.resolve_detector_intensity(proxy=proxy)
    semantic_proxy = intensity_semantics.explicit_proxy(
        proxy_namespace="v4_proxy.corrected_continuous_prefix",
        proxy_source_sha256=source_object_sha256,
        transform_sha256=snap.registry_receipt_hash,
    )
    coverage = history.make_session_coverage(
        session_id=str(source_object_id),
        requested_symbol="NG.v.0",
        mbo="VERIFIED",
        mbp10="NOT_APPLICABLE",
        l1="NOT_APPLICABLE",
        native_object_sha256s=(source_object_sha256,),
        symbology_binding_hashes=(),
    )

    lock_rows: dict[str, str] = {}
    for lane_name, result in (
        ("S135_CONTROL", paired.control),
        ("FULL_PROVISIONAL_COMBINED", paired.combined),
    ):
        probability = mechanics.make_probability_entry(
            signal_lane_id=lane_name,
            instance_id=bound.causal_prefix_hash,
            head_id="FRANKIE_SOLE_SYNTHESIS",
            causal_evaluation_at=bound.causal_cutoff,
            decision_available_at=bound.causal_cutoff,
            probabilities=tuple(result.synthesis.probabilities),
            state_movie_hash=state_movie_hash,
            model_sha256=_hash("gpt-5.6-sol"),
            snapshot_sha256=snap.snapshot_hash,
            source_manifest_sha256=bound.knowledge_manifest_hash,
            missingness_manifest_sha256=_hash(
                {"null": snap.explicit_null_count, "unavailable": snap.unavailable_count}
            ),
        )
        legacy_lock = lock_outcome.recompute_lock_outcome(
            (probability,), threshold=1.0, persistence=1,
            lock_policy_sha256=_hash("NONAUTHORITATIVE_COMPATIBILITY_PROBE"),
        )
        lock_rows[lane_name] = legacy_lock.lock_hash

    hashes = (snap.snapshot_hash,) * 7
    lane_specs = []
    registry = unified.V4LaneRegistry()
    for lane_name in ("S135_CONTROL", "FULL_PROVISIONAL_COMBINED"):
        spec = mechanics.V4LaneSpec(
            lane_id=lane_name, mode="CASE_STUDY_NO_ADAPTATION",
            population_manifest_sha256=hashes[0], feature_schema_sha256=hashes[1],
            adapter_sha256=hashes[2], reveal_policy_sha256=hashes[3], lock_policy_sha256=hashes[4],
        ).validate()
        lane = unified.RegisteredLane(
            spec=spec, adapter_identity_sha256=hashes[2],
            adapter_population_id=bound.causal_prefix_hash,
            label_identity="SEALED_STEP1", coordinate_schema_identity=snap.registry_receipt_hash,
            restrictions={"adaptation_allowed": False}, permanently_non_promotable=False,
        )
        registry.register(lane)
        lane_specs.append(spec)
    integrated = adapter_integration.IntegratedV4Adapter(registry)
    registry_hash = integrated.registry.registry_hash
    evaluation_clock = end_to_end.EvaluationClock(
        bound.causal_cutoff, bound.causal_cutoff, bound.causal_cutoff
    ).validate(discovery, bound.causal_cutoff + 1.0)

    identity = exact_freeze.ExactFreezeIdentity(
        candidate_commit_sha=source_commit,
        workflow_sha256=hashes[0], ruleset_sha256=hashes[1], engine_sha256=hashes[2],
        adapter_sha256=hashes[3], reconciler_sha256=hashes[4], model_sha256=hashes[5],
        source_manifest_sha256=hashes[6],
    )
    legacy_freeze_identity_hash = identity.identity_hash
    sparse = gates.SparseStagePolicy(0, 0, True, False, False).validate()
    gate_intensity = gates.DetectorIntensityResolution(
        mode="EXPLICIT_PROXY", proxy_namespace="v4_proxy.corrected_continuous_prefix"
    ).validate()

    pg_identity = pilot_guard.ExactCandidateIdentity(
        candidate_sha256=snap.snapshot_hash, workflow_sha256=hashes[0], ruleset_sha256=hashes[1],
        engine_sha256=hashes[2], adapter_sha256=hashes[3], reconciler_sha256=hashes[4],
        model_sha256=hashes[5], source_sha256=source_object_sha256,
    )
    pg_manifest = pilot_guard.PilotChunkManifest(
        pilot_id=bound.causal_prefix_hash, d_lane="D0", year=2021,
        start_date="2021-10-01", end_date_exclusive="2021-11-01", identity=pg_identity,
        selection_manifest_sha256=snap.snapshot_hash,
        membership_manifest_sha256=bound.state_prefix_hash, child_ids=(bound.causal_prefix_hash,),
    ).validate()
    pgr_binding = pilot_guardrail.ExactCandidateBinding(
        candidate_commit=source_commit, workflow_sha256=hashes[0], ruleset_sha256=hashes[1],
        engine_sha256=hashes[2], adapter_sha256=hashes[3], reconciler_sha256=hashes[4],
        model_sha256=hashes[5], source_manifest_sha256=hashes[6],
    )
    pgr_manifest = pilot_guardrail.make_manifest(
        pilot_id=bound.causal_prefix_hash, d_stage="D0", calendar_year=2021,
        start_date="2021-10-01", end_date="2021-10-31",
        selection_manifest_sha256=snap.snapshot_hash,
        membership_manifest_sha256=bound.state_prefix_hash,
        parent_manifest_sha256=bound.causal_prefix_hash,
        binding=pgr_binding, selection_frozen=True, membership_frozen=True,
        release_holdout_consumed=False,
    )

    direct = {
        "ng_exhaustion_v4_causal_clock": discovery.receipt_hash,
        "ng_exhaustion_v4_causal_entry_adapter": _hash(lawful_clocks),
        "ng_exhaustion_v4_state_assembler": state_row.row_hash,
        "ng_exhaustion_v4_mechanics": state_movie_hash,
        "ng_exhaustion_v4_detector_intensity": intensity_resolution["resolution_hash"],
        "ng_exhaustion_v4_detector_intensity_semantics": semantic_proxy["proxy_receipt_sha256"],
        "ng_exhaustion_v4_history_support": coverage.coverage_manifest_hash,
        "ng_exhaustion_v4_lock_outcome": _hash(lock_rows),
        "ng_exhaustion_v4_adapter_integration": registry_hash,
        "ng_exhaustion_v4_end_to_end_adapter": _hash(asdict(evaluation_clock)),
        "ng_exhaustion_v4_unified_runtime": registry_hash,
    }
    superseded = {
        "ng_exhaustion_v4_exact_candidate_freeze": _hash(
            {"legacy_identity_validation": legacy_freeze_identity_hash,
             "corrected_snapshot": snap.snapshot_hash,
             "reason": "corrected paired global freeze owns the experiment; legacy engineering freeze grants no empirical authority"}
        ),
        "ng_exhaustion_v4_gate_verifier": _hash(
            {"legacy_sparse": asdict(sparse), "legacy_intensity": asdict(gate_intensity),
             "corrected_identical_prefix_proof": paired.identical_prefix_proof.proof_hash}
        ),
        "ng_exhaustion_v4_pilot_chunk_guard": _hash(
            {"legacy_manifest": pg_manifest.manifest_hash,
             "corrected_prefix": paired.identical_prefix_proof.proof_hash}
        ),
        "ng_exhaustion_v4_pilot_chunk_guardrail": _hash(
            {"legacy_manifest": pgr_manifest.manifest_hash,
             "corrected_prefix": paired.identical_prefix_proof.proof_hash}
        ),
    }
    rows = [
        {"module": name, "disposition": "DIRECT_OPERATIONAL_EXECUTION", "execution_hash": digest}
        for name, digest in direct.items()
    ] + [
        {"module": name,
         "disposition": "SUPERSEDED_BY_CORRECTED_RUNTIME_EQUIVALENCE",
         "execution_hash": digest,
         "semantic_comparison": "legacy invariant validator and corrected identical-prefix proof both executed"}
        for name, digest in superseded.items()
    ]
    rows.sort(key=lambda row: row["module"])
    module_evidence = _module_evidence(rows)
    core = {
        "schema": SCHEMA, "run_id": bound.run_id,
        "causal_prefix_hash": bound.causal_prefix_hash,
        "snapshot_hash": snap.snapshot_hash,
        "identical_prefix_proof_hash": paired.identical_prefix_proof.proof_hash,
        **module_evidence,
        "modules": rows,
        "same_receipt_required_both_lanes": True,
        "governing_input_context_hash": expected_input["receipt_hash"],
        "answer_revealed": False,
    }
    receipt = {**core, "receipt_hash": _hash(core)}
    return validate_v4_governing_runtime_receipt(receipt)


__all__ = [
    "EXPECTED_H_MODULE_IDENTITIES",
    "build_v4_governing_input_context",
    "execute_v4_governing_prefix",
    "validate_v4_governing_runtime_receipt",
]
