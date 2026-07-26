from __future__ import annotations

import copy

import pytest

import ng_g16_attribution_bound_curve_lock_gate as gate


def _rehash(value: dict, field: str) -> None:
    value.pop(field, None)
    value[field] = gate._fingerprint(value)


def _fixture_and_result() -> tuple[dict, dict]:
    fixture = gate._synthetic_fixture()
    result = gate.build_gate(**fixture)
    return fixture, result


def test_builds_attribution_bound_immutable_lock() -> None:
    fixture, result = _fixture_and_result()
    assert result["status"] == gate.READY
    assert result["g16_curve_lock_bound_to_attribution_scored_g15_lessons"] is True
    assert result["fixed_scoring_may_begin"] is True
    assert result["actual_g16_outcomes_used"] is False
    gate.validate_gate(
        result,
        bound_validator=fixture["bound_validator"],
        lock_validator=fixture["lock_validator"],
    )


def test_rejects_refined_curve_substitution() -> None:
    fixture = gate._synthetic_fixture()
    fixture["counterfactual_curve_lock"]["refined_curve_fingerprint"] = "x" * 64
    _rehash(fixture["counterfactual_curve_lock"], "lock_fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.build_gate(**fixture)


def test_rejects_candidate_registry_substitution() -> None:
    fixture = gate._synthetic_fixture()
    fixture["counterfactual_curve_lock"]["candidate_ids"] = ["substituted"]
    _rehash(fixture["counterfactual_curve_lock"], "lock_fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.build_gate(**fixture)


def test_rejects_candidate_evidence_substitution() -> None:
    fixture = gate._synthetic_fixture()
    key = fixture["counterfactual_curve_lock"]["candidate_ids"][0]
    fixture["counterfactual_curve_lock"]["candidate_evidence_fingerprints"][key] = "x" * 64
    _rehash(fixture["counterfactual_curve_lock"], "lock_fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.build_gate(**fixture)


def test_rejects_g16_outcome_access_escalation() -> None:
    fixture, result = _fixture_and_result()
    result["actual_g16_outcomes_used"] = True
    _rehash(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.validate_gate(
            result,
            bound_validator=fixture["bound_validator"],
            lock_validator=fixture["lock_validator"],
        )


def test_rejects_ng_brain_write_escalation() -> None:
    fixture, result = _fixture_and_result()
    result["may_update_ng_brain"] = True
    _rehash(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.validate_gate(
            result,
            bound_validator=fixture["bound_validator"],
            lock_validator=fixture["lock_validator"],
        )


def test_rejects_options_lane_escalation() -> None:
    fixture, result = _fixture_and_result()
    result["options_lane_started"] = True
    _rehash(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.validate_gate(
            result,
            bound_validator=fixture["bound_validator"],
            lock_validator=fixture["lock_validator"],
        )


def test_rejects_nested_refingerprinted_lock_tampering() -> None:
    fixture, result = _fixture_and_result()
    nested = result["counterfactual_curve_lock"]
    nested["posterior_stream_fingerprint"] = "x" * 64
    _rehash(nested, "lock_fingerprint")
    _rehash(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.validate_gate(
            result,
            bound_validator=fixture["bound_validator"],
            lock_validator=fixture["lock_validator"],
        )


def test_rejects_incomplete_validation_bundle() -> None:
    fixture = gate._synthetic_fixture()
    fixture["validation_bundle"].pop("legacy_lock_validation")
    _rehash(fixture["validation_bundle"], "fingerprint")
    with pytest.raises(gate.G16AttributionBoundCurveLockError):
        gate.build_gate(**fixture)


def test_is_deterministic_and_does_not_mutate_inputs() -> None:
    fixture = gate._synthetic_fixture()
    before = copy.deepcopy(fixture)
    first = gate.build_gate(**fixture)
    second = gate.build_gate(**fixture)
    assert first == second
    assert fixture == before
