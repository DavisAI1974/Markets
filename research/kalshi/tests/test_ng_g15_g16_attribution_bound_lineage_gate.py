from __future__ import annotations

import copy

import pytest

import ng_g15_g16_attribution_bound_lineage_gate as gate


def _fixture() -> dict:
    return gate._synthetic_fixture()


def _refingerprint(value: dict, field: str = "fingerprint") -> None:
    value.pop(field, None)
    value[field] = gate._fingerprint(value)


def test_builds_attribution_bound_g16_lineage() -> None:
    result = gate.build_gate(**_fixture())
    assert result["status"] == gate.READY
    assert result["all_six_factors_authorized_before_scoring"] is True
    assert result["separate_blind_refined_scores_verified"] is True
    assert result["g16_plan_bound_to_validated_g15_lessons"] is True
    assert result["actual_g16_outcomes_used"] is False


def test_publication_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["g15_publication"]["completion_fingerprint"] = "x" * 64
    with pytest.raises(gate.AttributionBoundLineageError, match="publication completion"):
        gate.build_gate(**fixture)


def test_attribution_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["counterfactual_lesson_gate"]["source"]["counterfactual_fingerprint"] = "x" * 64
    _refingerprint(fixture["counterfactual_lesson_gate"])
    with pytest.raises(gate.AttributionBoundLineageError, match="counterfactual attribution"):
        gate.build_gate(**fixture)


def test_score_comparison_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["counterfactual_lesson_gate"]["source"]["comparison_fingerprint"] = "x" * 64
    _refingerprint(fixture["counterfactual_lesson_gate"])
    with pytest.raises(gate.AttributionBoundLineageError, match="score comparison"):
        gate.build_gate(**fixture)


def test_blind_score_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["counterfactual_lesson_gate"]["source"]["blind_score_fingerprint"] = "x" * 64
    _refingerprint(fixture["counterfactual_lesson_gate"])
    with pytest.raises(gate.AttributionBoundLineageError, match="blind score"):
        gate.build_gate(**fixture)


def test_lesson_gate_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["legacy_lineage"]["counterfactual_lesson_gate_fingerprint"] = "x" * 64
    _refingerprint(fixture["legacy_lineage"])
    with pytest.raises(gate.AttributionBoundLineageError, match="counterfactual lesson gate"):
        gate.build_gate(**fixture)


def test_g16_plan_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["legacy_lineage"]["g16_plan_fingerprint"] = "x" * 64
    _refingerprint(fixture["legacy_lineage"])
    with pytest.raises(gate.AttributionBoundLineageError, match="G16 plan"):
        gate.build_gate(**fixture)


def test_brain_write_escalation_is_rejected() -> None:
    fixture = _fixture()
    fixture["counterfactual_lesson_gate"]["may_update_ng_brain"] = True
    _refingerprint(fixture["counterfactual_lesson_gate"])
    with pytest.raises(gate.AttributionBoundLineageError, match="ng_brain"):
        gate.build_gate(**fixture)


def test_g16_outcome_or_options_escalation_is_rejected() -> None:
    for field in ("actual_g16_outcomes_used", "options_lane_started"):
        fixture = _fixture()
        fixture["legacy_lineage"][field] = True
        _refingerprint(fixture["legacy_lineage"])
        with pytest.raises(gate.AttributionBoundLineageError, match=field):
            gate.build_gate(**fixture)


def test_output_is_deterministic_and_inputs_are_immutable() -> None:
    fixture = _fixture()
    before = copy.deepcopy(fixture)
    first = gate.build_gate(**fixture)
    second = gate.build_gate(**fixture)
    assert first == second
    assert fixture == before
    assert first["blind_score_fingerprint"] != first["refined_score_fingerprint"]
    assert first["cme_event_contracts_mode"] == "SHADOW"
    assert first["brokerage_contract"] == "tastytrade_not_ibkr"
    assert first["execution_authority"] is False
