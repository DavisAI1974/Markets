from __future__ import annotations

import copy

import pytest

import ng_g16_attribution_bound_causal_authorization_gate as gate


def _fixture() -> dict:
    return gate._synthetic_fixture()


def _rehash(value: dict) -> None:
    value.pop("fingerprint", None)
    value["fingerprint"] = gate._fingerprint(value)


def test_builds_attribution_bound_g16_causal_authorization() -> None:
    fixture = _fixture()
    original = copy.deepcopy(fixture)
    result = gate.build_gate(**fixture)
    assert result["status"] == gate.READY
    assert result["g16_posterior_bound_to_attribution_scored_g15_lessons"] is True
    assert result["all_six_factors_authorized_before_scoring"] is True
    assert result["separate_blind_refined_scores_verified"] is True
    assert result["actual_g15_outcomes_used"] is True
    assert result["actual_g16_outcomes_used"] is False
    assert result["g16_scoring_authorized"] is False
    assert result["may_update_ng_brain"] is False
    assert result["execution_authority"] is False
    assert result["cme_event_contracts_mode"] == "SHADOW"
    assert result["brokerage_contract"] == "tastytrade_not_ibkr"
    assert result["options_lane_started"] is False
    assert fixture == original


def test_rejects_legacy_lineage_substitution() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["counterfactual_lineage_gate_fingerprint"] = "z" * 64
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_g16_plan_substitution() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["g16_plan_fingerprint"] = "z" * 64
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_candidate_set_substitution() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["candidate_ids"] = ["g15_counterfactual.queue"]
    legacy["candidate_evidence_fingerprints"] = {
        "g15_counterfactual.queue": "e" * 64
    }
    legacy["candidate_ids_observed_in_posterior_attribution"] = [
        "g15_counterfactual.queue"
    ]
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_candidate_evidence_substitution() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["candidate_evidence_fingerprints"] = {
        "g15_counterfactual.activity": "z" * 64
    }
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_posterior_unregistered_candidate() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["candidate_ids_observed_in_posterior_attribution"] = [
        "g15_counterfactual.unregistered"
    ]
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_ng_brain_write_escalation() -> None:
    fixture = _fixture()
    bound = fixture["attribution_bound_lineage"]
    bound["may_update_ng_brain"] = True
    _rehash(bound)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_g16_outcome_access() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["actual_g16_outcomes_used"] = True
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_options_lane_activation() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_causal_authorization"]
    legacy["options_lane_started"] = True
    _rehash(legacy)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_rejects_validation_bundle_tampering() -> None:
    fixture = _fixture()
    fixture["validation_bundle"]["legacy_causal_validation"] = {"wrong": {}}
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.build_gate(**fixture)


def test_validate_reconstructs_embedded_evidence() -> None:
    fixture = _fixture()
    result = gate.build_gate(**fixture)
    gate.validate_gate(
        result,
        bound_validator=gate._noop,
        causal_validator=gate._noop,
    )
    tampered = copy.deepcopy(result)
    tampered["g16_plan_fingerprint"] = "z" * 64
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = gate._fingerprint(tampered)
    with pytest.raises(gate.G16AttributionBoundCausalAuthorizationError):
        gate.validate_gate(
            tampered,
            bound_validator=gate._noop,
            causal_validator=gate._noop,
        )


def test_deterministic_and_input_immutable() -> None:
    fixture = _fixture()
    original = copy.deepcopy(fixture)
    first = gate.build_gate(**fixture)
    second = gate.build_gate(**fixture)
    assert first == second
    assert fixture == original
