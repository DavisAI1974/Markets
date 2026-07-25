from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor_v12 as executor
import ng_historical_refinement_preflight_v12 as preflight
import ng_historical_refinement_readiness_v15 as readiness


def test_definition_byte_binding_is_between_coverage_and_basis() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys.index("corpus_coverage") < keys.index(
        "corpus_definition_byte_binding"
    ) < keys.index("basis_inventory_regeneration")
    assert keys.index("corpus_definition_byte_binding") < keys.index(
        "broad_corpus_scope"
    ) < keys.index("g15_exact_replay")


def test_definition_byte_stage_contract_is_canonical() -> None:
    spec = next(
        spec
        for spec in readiness.STAGES
        if spec.key == "corpus_definition_byte_binding"
    )
    assert spec.filename == "ng_corpus_definition_byte_binding_gate.json"
    assert spec.schema == "ng_corpus_definition_byte_binding_gate.v1"
    assert spec.pre_outcome is True
    assert spec.ready_statuses == frozenset({"CORPUS_DEFINITION_BYTES_BOUND_READY"})
    assert "audit_fingerprint" in spec.required_fields
    assert "binding_set_fingerprint" in spec.required_fields


def test_readiness_selftest() -> None:
    assert readiness.selftest() == 0


def test_missing_definition_byte_gate_blocks_basis(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "corpus_definition_byte_binding":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["first_blocking_stage"] == "corpus_definition_byte_binding"
    basis = next(
        row
        for row in report["stages"]
        if row["key"] == "basis_inventory_regeneration"
    )
    assert basis["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_definition_byte_gate_must_bind_coverage_fingerprint(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    values["corpus_definition_byte_binding"] = copy.deepcopy(
        values["corpus_definition_byte_binding"]
    )
    values["corpus_definition_byte_binding"]["audit_fingerprint"] = "wrong"
    values["corpus_definition_byte_binding"].pop("fingerprint", None)
    values["corpus_definition_byte_binding"]["fingerprint"] = readiness._fingerprint(
        values["corpus_definition_byte_binding"]
    )
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["first_blocking_stage"] == "corpus_definition_byte_binding"
    row = next(
        row
        for row in report["stages"]
        if row["key"] == "corpus_definition_byte_binding"
    )
    assert row["effective_status"] == "INVALID"


def test_executor_exposes_definition_byte_gate() -> None:
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_definition_byte_binding"] == (
        "python",
        "ng_corpus_definition_byte_binding_gate.py",
        "build",
    )
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    executor.validate_plan(plan)
    keys = [row["key"] for row in plan["stages"]]
    assert keys == [spec.key for spec in readiness.STAGES]


def test_preflight_contract_rejects_readiness_v14_shape() -> None:
    assert preflight.READINESS_CONTRACT == "ng_historical_refinement_readiness.v15"
    assert preflight.EXECUTOR_CONTRACT == "ng_historical_refinement_executor_v12"
    assert "corpus_definition_byte_binding" in preflight.STAGE_ORDER
    assert preflight.STAGE_ORDER.index("corpus_coverage") < preflight.STAGE_ORDER.index(
        "corpus_definition_byte_binding"
    ) < preflight.STAGE_ORDER.index("basis_inventory_regeneration")


def test_permanent_authority_wall() -> None:
    values = readiness._linked_fixture_chain()
    gate = values["corpus_definition_byte_binding"]
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        assert gate[field] is False
    assert gate["one_signal_authority_preserved"] is True
    assert gate["blind_forecasts_immutable"] is True
    assert gate["cme_event_contracts_mode"] == "SHADOW"
    assert gate["brokerage_contract"] == "tastytrade_not_ibkr"


def test_tampered_readiness_summary_fails(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    report["corpus_definition_bytes_bound_before_basis_regeneration"] = False
    report.pop("fingerprint", None)
    report["fingerprint"] = readiness._fingerprint(report)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(report)
