from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_s3_materializer_provenance_gate as gate
import ng_historical_refinement_executor_v25 as executor
import ng_historical_refinement_readiness_v29 as readiness


def _fixtures():
    authority = gate._authority_fields()
    spec = {"schema": "test.materialization", "corpora": [], **authority}
    runtime = {
        "status": gate.runtime_capture.READY_STATUS,
        "receipt_fingerprint": "r" * 64,
        "materialization_spec": spec,
        "materialization_spec_fingerprint": gate._fp(spec),
        "blockers": [],
        **authority,
    }
    exact = {
        "status": gate.exact_materializer.READY_STATUS,
        "receipt_fingerprint": "e" * 64,
        "runtime_inventory_capture_fingerprint": runtime["receipt_fingerprint"],
        "source_spec": spec,
        "source_spec_fingerprint": gate._fp(spec),
        "source_materializations_fingerprint": "s" * 64,
        "source_count": 2,
        "downstream_materialization_receipt_fingerprint": "d" * 64,
        "canonical_inventory_spec_fingerprint": "c" * 64,
        "materialization_evidence_fingerprint": "m" * 64,
        "plan_fingerprint": "p" * 64,
        "inventory_compiler_receipt_fingerprint": "i" * 64,
        "identity_from_s3_keys_inferred": False,
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "blockers": [],
        **authority,
    }
    return runtime, exact


def _passthrough(value):
    return copy.deepcopy(dict(value))


def test_gate_binds_complete_runtime_capture_to_exact_bytes():
    runtime, exact = _fixtures()
    receipt = gate.build_gate(
        runtime,
        exact,
        runtime_validator=_passthrough,
        materializer_validator=_passthrough,
    )
    assert receipt["status"] == gate.READY_STATUS
    assert receipt["runtime_capture_receipt"] == runtime
    assert receipt["exact_materializer_receipt"] == exact
    assert receipt["exact_materialized_bytes_bound_to_runtime_inventory"] is True
    gate.validate_gate(
        receipt,
        runtime_validator=_passthrough,
        materializer_validator=_passthrough,
    )


def test_gate_blocks_detached_runtime_fingerprint():
    runtime, exact = _fixtures()
    exact["runtime_inventory_capture_fingerprint"] = "x" * 64
    receipt = gate.build_gate(
        runtime,
        exact,
        runtime_validator=_passthrough,
        materializer_validator=_passthrough,
    )
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert "EXACT_MATERIALIZER_RUNTIME_CAPTURE_FINGERPRINT_MISMATCH" in receipt["blockers"]


def test_gate_blocks_materialization_spec_substitution():
    runtime, exact = _fixtures()
    exact["source_spec"] = {**exact["source_spec"], "substituted": True}
    exact["source_spec_fingerprint"] = gate._fp(exact["source_spec"])
    receipt = gate.build_gate(
        runtime,
        exact,
        runtime_validator=_passthrough,
        materializer_validator=_passthrough,
    )
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert "MATERIALIZATION_SPEC_CONTENT_MISMATCH" in receipt["blockers"]


def test_nested_runtime_tampering_cannot_be_refingerprinted():
    runtime, exact = _fixtures()
    receipt = gate.build_gate(
        runtime,
        exact,
        runtime_validator=_passthrough,
        materializer_validator=_passthrough,
    )
    tampered = copy.deepcopy(receipt)
    tampered["runtime_capture_receipt"]["receipt_fingerprint"] = "z" * 64
    tampered.pop("fingerprint")
    tampered["fingerprint"] = gate._fp(tampered)
    with pytest.raises(gate.CorpusS3MaterializerProvenanceError):
        gate.validate_gate(
            tampered,
            runtime_validator=_passthrough,
            materializer_validator=_passthrough,
        )


def test_authority_escalation_is_rejected():
    runtime, exact = _fixtures()
    exact["options_lane_started"] = True
    with pytest.raises(gate.CorpusS3MaterializerProvenanceError):
        gate.build_gate(
            runtime,
            exact,
            runtime_validator=_passthrough,
            materializer_validator=_passthrough,
        )


def test_readiness_inserts_provenance_before_broad_inspection():
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[:7] == [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_coverage",
    ]
    assert readiness._MATERIALIZER_PROVENANCE.pre_outcome is True


def test_readiness_blocks_at_missing_provenance(tmp_path: Path):
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        if spec.key == "corpus_s3_materialization_provenance":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "corpus_s3_materialization_provenance"
    assert report["broad_corpus_verified"] is False


def test_executor_exposes_operational_provenance_entrypoint(tmp_path: Path):
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["corpus_s3_materialization_provenance"]["suggested_entrypoint"] == [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    ]
    assert rows["corpus_s3_materialization_provenance"]["requires_fixed_outcomes"] is False
    executor.validate_plan(plan)


def test_executor_rejects_removed_provenance_stage(tmp_path: Path):
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    broken = copy.deepcopy(plan)
    broken["stages"] = [
        row for row in broken["stages"] if row["key"] != "corpus_s3_materialization_provenance"
    ]
    broken.pop("fingerprint")
    broken["fingerprint"] = executor.legacy_executor._fingerprint(broken)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(broken)


def test_permanent_controls_remain_closed(tmp_path: Path):
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False
