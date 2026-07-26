from __future__ import annotations

import copy

import pytest

import ng_g16_attribution_bound_publication_gate as gate


def _fixture():
    return gate._synthetic_fixture()


def _validators(fixture):
    return {
        key: fixture[key]
        for key in (
            "bound_lock_validator",
            "publication_validator",
            "score_validator",
            "comparison_validator",
        )
    }


def _refingerprint(value, field):
    value.pop(field, None)
    value[field] = gate._fingerprint(value)


def test_builds_exact_attribution_bound_publication():
    fixture = _fixture()
    result = gate.build_gate(**fixture)
    gate.validate_gate(result, **_validators(fixture))
    assert result["status"] == gate.READY
    assert result["actual_g16_outcomes_used"] is True
    assert result["blind_score_fingerprint"] != result["refined_score_fingerprint"]
    assert result["g16_publication_bound_to_attribution_scored_g15_lessons"] is True


def test_rejects_publication_from_different_curve_lock():
    fixture = _fixture()
    publication = copy.deepcopy(fixture["counterfactual_publication"])
    publication["counterfactual_curve_lock_fingerprint"] = "ff" * 32
    _refingerprint(publication, "completion_fingerprint")
    fixture["counterfactual_publication"] = publication
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="legacy curve lock"):
        gate.build_gate(**fixture)


def test_rejects_candidate_evidence_substitution():
    fixture = _fixture()
    publication = copy.deepcopy(fixture["counterfactual_publication"])
    publication["candidate_evidence_fingerprints"]["lesson-1"] = "ee" * 32
    _refingerprint(publication, "completion_fingerprint")
    fixture["counterfactual_publication"] = publication
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="candidate evidence"):
        gate.build_gate(**fixture)


def test_rejects_substituted_blind_score():
    fixture = _fixture()
    score = copy.deepcopy(fixture["blind_score"])
    score["actual_sha256"] = "de" * 32
    _refingerprint(score, "score_fingerprint")
    fixture["blind_score"] = score
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="actual substrate|another blind score"):
        gate.build_gate(**fixture)


def test_rejects_collapsed_score_roles():
    fixture = _fixture()
    score = copy.deepcopy(fixture["refined_score"])
    score["role"] = "blind"
    _refingerprint(score, "score_fingerprint")
    fixture["refined_score"] = score
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="schema/role"):
        gate.build_gate(**fixture)


def test_rejects_comparison_substitution():
    fixture = _fixture()
    comparison = copy.deepcopy(fixture["comparison"])
    comparison["blind_score_fingerprint"] = "cd" * 32
    _refingerprint(comparison, "comparison_fingerprint")
    fixture["comparison"] = comparison
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="blind score"):
        gate.build_gate(**fixture)


def test_rejects_brain_write_escalation_after_outer_refingerprint():
    fixture = _fixture()
    result = gate.build_gate(**fixture)
    result["may_update_ng_brain"] = True
    _refingerprint(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="may_update_ng_brain"):
        gate.validate_gate(result, **_validators(fixture))


def test_rejects_options_escalation_after_outer_refingerprint():
    fixture = _fixture()
    result = gate.build_gate(**fixture)
    result["options_lane_started"] = True
    _refingerprint(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="options_lane_started"):
        gate.validate_gate(result, **_validators(fixture))


def test_rejects_hidden_g16_outcome_flag():
    fixture = _fixture()
    result = gate.build_gate(**fixture)
    result["actual_g16_outcomes_used"] = False
    _refingerprint(result, "fingerprint")
    with pytest.raises(gate.G16AttributionBoundPublicationError, match="actual_g16_outcomes_used"):
        gate.validate_gate(result, **_validators(fixture))


def test_is_deterministic_and_does_not_mutate_inputs():
    fixture = _fixture()
    originals = copy.deepcopy(fixture)
    first = gate.build_gate(**fixture)
    second = gate.build_gate(**fixture)
    assert first == second
    assert fixture == originals
