from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_historical_refinement_readiness_v19 as readiness
import ng_target_slice_derivation_gate as v1
import ng_target_slice_derivation_gate_v2 as derivation


def _parent() -> dict[str, object]:
    return {
        "fingerprint": "lineage-fingerprint",
        "target_inspection_plan_fingerprint": "target-plan",
    }


def _base_result() -> dict[str, object]:
    value = {
        "schema": v1.SCHEMA,
        "status": v1.READY_STATUS,
        "target_slice_broad_lineage_fingerprint": "lineage-fingerprint",
        "broad_definition_byte_binding_fingerprint": "broad-binding",
        "target_slice_bundle_fingerprint": "slice-bundle",
        "target_inspection_receipt_fingerprint": "target-receipt",
        "target_catalog_fingerprint": "target-catalog",
        "target_audit_fingerprint": "target-audit",
        "lineage_set_fingerprint": "lineage-set",
        "derivation_algorithm": v1.ALGORITHM,
        "expected_target_source_count": 2,
        "derived_target_source_count": 2,
        "exact_derivation_count": 2,
        "derivation_rows": [],
        "derivation_set_fingerprint": "derivation-set",
        "blockers": [],
        "stand_down_required": False,
        "source_files_verified": True,
        "next_action": "REGENERATE_G15_G16_BASIS_FROM_DERIVATION_ATTESTED_TARGET_SHARDS",
        "target_slice_broad_lineage_gate": _parent(),
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    value["fingerprint"] = v1._fp(value)
    return value


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        derivation.v1,
        "build_gate",
        lambda value, verify_files=True: copy.deepcopy(_base_result()),
    )


def test_v2_binds_target_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    result = derivation.build_gate(_parent(), verify_files=True)
    assert result["status"] == derivation.READY_STATUS
    assert result["target_inspection_plan_fingerprint"] == "target-plan"
    assert result["target_plan_bound_to_derivation"] is True
    assert result["basis_may_substitute_target_plan"] is False


def test_missing_plan_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _base_result()
    base["target_slice_broad_lineage_gate"].pop("target_inspection_plan_fingerprint")
    monkeypatch.setattr(
        derivation.v1,
        "build_gate",
        lambda value, verify_files=True: copy.deepcopy(base),
    )
    with pytest.raises(derivation.TargetSliceDerivationV2Error, match="missing target inspection plan"):
        derivation.build_gate({}, verify_files=True)


def test_refingerprinted_plan_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch)
    result = derivation.build_gate(_parent(), verify_files=True)
    result["target_inspection_plan_fingerprint"] = "replacement-plan"
    result["fingerprint"] = v1._fp(
        {key: value for key, value in result.items() if key != "fingerprint"}
    )
    with pytest.raises(derivation.TargetSliceDerivationV2Error, match="differs from broad-lineage"):
        derivation.validate_gate(result, verify_files=True)


def test_authority_escalation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    result = derivation.build_gate(_parent(), verify_files=True)
    result["execution_authority"] = True
    result["fingerprint"] = v1._fp(
        {key: value for key, value in result.items() if key != "fingerprint"}
    )
    with pytest.raises(v1.TargetSliceDerivationError, match="execution_authority"):
        derivation.validate_gate(result, verify_files=True)


def test_v2_is_deterministic_and_input_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    parent = _parent()
    before = copy.deepcopy(parent)
    first = derivation.build_gate(parent, verify_files=True)
    second = derivation.build_gate(parent, verify_files=True)
    assert first == second
    assert parent == before


def _write_chain(root: Path, values: dict[str, dict[str, object]]) -> None:
    for spec in readiness.STAGES:
        (root / spec.filename).write_text(
            json.dumps(values[spec.key], sort_keys=True) + "\n", encoding="utf-8"
        )


def test_readiness_v19_links_plan_through_derivation(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V19"
    assert report["target_slice_derivation_plan_bound"] is True
    assert (
        "target_slice_derivation",
        "target_inspection_plan_fingerprint",
        "basis_inventory_regeneration",
        "inspection_plan_fingerprint",
    ) in readiness.LINK_RULES


def test_readiness_v19_blocks_without_plan_bound_derivation(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    (tmp_path / readiness._TARGET_SLICE_DERIVATION_V2.filename).unlink()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "target_slice_derivation"
    assert "basis_inventory_regeneration" not in report["ready_stages"]


def test_permanent_authority_controls() -> None:
    fixture = readiness._linked_fixture_chain()["target_slice_derivation"]
    assert fixture["actual_outcomes_used"] is False
    assert fixture["paid_live_data_assumed"] is False
    assert fixture["random_shuffle_used"] is False
    assert fixture["blind_forecasts_immutable"] is True
    assert fixture["may_update_ng_brain"] is False
    assert fixture["execution_authority"] is False
    assert fixture["cme_event_contracts_mode"] == "SHADOW"
    assert fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fixture["options_lane_started"] is False
