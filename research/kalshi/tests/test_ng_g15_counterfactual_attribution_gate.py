from __future__ import annotations

import copy

import pytest

import ng_g15_counterfactual_attribution_gate as gate


def _patched_build(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    monkeypatch.setattr(
        gate,
        "build_refinement_authorization",
        lambda **kwargs: copy.deepcopy(refinement),
    )
    monkeypatch.setattr(
        gate, "validate_refinement_authorization", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        gate,
        "build_attribution_report",
        lambda *args, **kwargs: copy.deepcopy(attribution),
    )
    monkeypatch.setattr(
        gate, "validate_attribution_report", lambda *args, **kwargs: None
    )
    result = gate.build_authorization(
        completion=completion,
        pipeline=pipeline,
        refinement_authorization=refinement,
        attribution=attribution,
    )
    return completion, pipeline, refinement, attribution, result


def _refingerprint(value):
    value = copy.deepcopy(value)
    value.pop("authorization_fingerprint", None)
    value["authorization_fingerprint"] = gate._fingerprint(value)
    return value


def _refingerprint_attribution(value):
    value = copy.deepcopy(value)
    value.pop("fingerprint", None)
    value["fingerprint"] = gate._fingerprint(value)
    return value


def test_authorizes_exact_six_factor_attribution(monkeypatch):
    _, _, _, _, result = _patched_build(monkeypatch)
    assert result["status"] == gate.READY
    assert result["factors"] == list(gate.FACTORS)
    assert result["all_six_factors_quantified"] is True
    assert result["lesson_proposals_brain_write_forbidden"] is True
    assert result["next_permitted_stage"] == (
        "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY"
    )
    gate.validate_authorization(result)


def test_rejects_incomplete_factor_set(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    attribution["factors"] = attribution["factors"][:-1]
    attribution = _refingerprint_attribution(attribution)
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(refinement)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement,
            attribution=attribution,
        )


def test_rejects_state_missing_one_factor(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    attribution["rows"][0]["factors"].pop()
    attribution = _refingerprint_attribution(attribution)
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(refinement)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement,
            attribution=attribution,
        )


def test_rejects_brain_writing_lesson(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    attribution["lesson_proposals"][0]["may_update_ng_brain"] = True
    attribution = _refingerprint_attribution(attribution)
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(refinement)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement,
            attribution=attribution,
        )


def test_rejects_refinement_authorization_substitution(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    expected = copy.deepcopy(refinement)
    substituted = copy.deepcopy(refinement)
    substituted["pipeline_fingerprint"] = "x" * 64
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(expected)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=substituted,
            attribution=attribution,
        )


def test_rejects_nonreproducible_attribution(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    rebuilt = copy.deepcopy(attribution)
    rebuilt["overall"][gate.FACTORS[0]] = {"changed_states": 99}
    rebuilt = _refingerprint_attribution(rebuilt)
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(refinement)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    monkeypatch.setattr(gate, "validate_attribution_report", lambda *a, **k: None)
    monkeypatch.setattr(
        gate, "build_attribution_report", lambda *a, **k: copy.deepcopy(rebuilt)
    )
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement,
            attribution=attribution,
        )


def test_rejects_refingerprinted_authority_escalation(monkeypatch):
    _, _, _, _, result = _patched_build(monkeypatch)
    result["execution_authority"] = True
    result = _refingerprint(result)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.validate_authorization(result)


def test_rejects_refingerprinted_options_start(monkeypatch):
    _, _, _, _, result = _patched_build(monkeypatch)
    result["options_lane_started"] = True
    result = _refingerprint(result)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.validate_authorization(result)


def test_recursive_validation_requires_all_upstreams(monkeypatch):
    completion, _, _, _, result = _patched_build(monkeypatch)
    with pytest.raises(gate.CounterfactualAttributionAuthorizationError):
        gate.validate_authorization(result, completion=completion)


def test_inputs_remain_immutable(monkeypatch):
    completion, pipeline, refinement, attribution = gate._synthetic_fixture()
    originals = copy.deepcopy((completion, pipeline, refinement, attribution))
    monkeypatch.setattr(
        gate, "build_refinement_authorization", lambda **kwargs: copy.deepcopy(refinement)
    )
    monkeypatch.setattr(gate, "validate_refinement_authorization", lambda *a, **k: None)
    monkeypatch.setattr(
        gate, "build_attribution_report", lambda *a, **k: copy.deepcopy(attribution)
    )
    monkeypatch.setattr(gate, "validate_attribution_report", lambda *a, **k: None)
    gate.build_authorization(
        completion=completion,
        pipeline=pipeline,
        refinement_authorization=refinement,
        attribution=attribution,
    )
    assert (completion, pipeline, refinement, attribution) == originals
