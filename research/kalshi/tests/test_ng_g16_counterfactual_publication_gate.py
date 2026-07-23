from __future__ import annotations

import copy

import pytest

import ng_g16_counterfactual_publication_gate as module


@pytest.fixture(autouse=True)
def _stub_upstream(monkeypatch):
    def validate_counterfactual(value, **kwargs):
        if value.get("reject"):
            raise module.G16CounterfactualCurveAuthorizationError("reject")

    def build_lock(*, curve_authorization, **kwargs):
        return copy.deepcopy(kwargs["_prepared_lock"])

    def validate_lock(value):
        if not value.get("lock_fingerprint"):
            raise module.G16PreparedPublicationError("bad lock")

    def build_publication(*, curve_lock, **kwargs):
        return copy.deepcopy(kwargs["_prepared_completion"])

    def validate_publication(value):
        if not value.get("completion_fingerprint"):
            raise module.G16PreparedPublicationError("bad completion")

    monkeypatch.setattr(module, "validate_counterfactual_curve_authorization", validate_counterfactual)
    monkeypatch.setattr(module, "build_prepared_curve_lock", build_lock)
    monkeypatch.setattr(module, "validate_prepared_curve_lock", validate_lock)
    monkeypatch.setattr(module, "build_prepared_completion", build_publication)
    monkeypatch.setattr(module, "validate_prepared_completion", validate_publication)


def _counterfactual(stand_downs=None):
    value = {
        "schema": module.COUNTERFACTUAL_SCHEMA,
        "authority": module.COUNTERFACTUAL_AUTHORITY,
        "status": (
            module.COUNTERFACTUAL_STAND_DOWNS
            if stand_downs
            else module.COUNTERFACTUAL_READY
        ),
        "next_permitted_stage": module.COUNTERFACTUAL_NEXT_STAGE,
        "prepared_curve_authorization_fingerprint": "curve-auth-fp",
        "counterfactual_causal_authorization_fingerprint": "causal-fp",
        "counterfactual_lineage_gate_fingerprint": "lineage-fp",
        "counterfactual_lesson_gate_fingerprint": "lesson-fp",
        "counterfactual_attribution_fingerprint": "attr-fp",
        "g15_publication_fingerprint": "g15-pub-fp",
        "g15_adjudication_fingerprint": "adj-fp",
        "g16_registry_fingerprint": "reg-fp",
        "candidate_ids": ["a", "b"],
        "candidate_evidence_fingerprints": {"a": "ea", "b": "eb"},
        "candidate_ids_used_by_curve": ["a"],
        "stand_down_days": list(stand_downs or []),
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "options_lane_started": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
    }
    value["fingerprint"] = module._fp(value)
    return value


def _prepared_authorization():
    return {"fingerprint": "curve-auth-fp"}


def _inner_lock(stand_downs=None):
    return {
        "lock_fingerprint": "inner-lock-fp",
        "prepared_curve_authorization_fingerprint": "curve-auth-fp",
        "replay_fingerprint": "replay-fp",
        "manifest_fingerprint": "manifest-fp",
        "prepared_corpus_fingerprint": "corpus-fp",
        "blind_prior_fingerprint": "prior-fp",
        "plan_fingerprint": "plan-fp",
        "authorization_stream_fingerprint": "auth-stream-fp",
        "posterior_stream_fingerprint": "posterior-fp",
        "blind_forecast_sha256": "blind-sha",
        "refined_curve_fingerprint": "curve-fp",
        "refined_forecast_sha256": "refined-sha",
        "registered_candidate_ids": ["a", "b"],
        "used_candidate_ids": ["a"],
        "stand_down_days": list(stand_downs or []),
    }


def _lock_kwargs(stand_downs=None):
    return {
        "counterfactual_curve_authorization": _counterfactual(stand_downs),
        "counterfactual_causal_authorization": {},
        "counterfactual_kwargs": {},
        "curve_kwargs": {},
        "prepared_curve_authorization": _prepared_authorization(),
        "prepared_lock_kwargs": {"_prepared_lock": _inner_lock(stand_downs)},
    }


def _prepared_completion(stand_downs=None):
    return {
        "completion_fingerprint": "prepared-completion-fp",
        "curve_lock_fingerprint": "inner-lock-fp",
        "prepared_curve_authorization_fingerprint": "curve-auth-fp",
        "g15_lesson_adjudication_fingerprint": "adj-fp",
        "registered_candidate_ids": ["a", "b"],
        "used_candidate_ids": ["a"],
        "replay_fingerprint": "replay-fp",
        "manifest_fingerprint": "manifest-fp",
        "prepared_corpus_fingerprint": "corpus-fp",
        "blind_prior_fingerprint": "prior-fp",
        "plan_fingerprint": "plan-fp",
        "authorization_stream_fingerprint": "auth-stream-fp",
        "posterior_stream_fingerprint": "posterior-fp",
        "blind_forecast_sha256": "blind-sha",
        "refined_forecast_sha256": "refined-sha",
        "refined_curve_fingerprint": "curve-fp",
        "actual_sha256": "actual-sha",
        "blind_score_fingerprint": "blind-score",
        "refined_score_fingerprint": "refined-score",
        "comparison_fingerprint": "comparison",
        "chronological_validation_fingerprint": "chronology",
        "stand_down_days": list(stand_downs or []),
        "renders": {"blind": {}, "refined": {}},
        "post_g16_shadow_registry": {},
    }


def _completion_kwargs(stand_downs=None):
    lock_kwargs = _lock_kwargs(stand_downs)
    lock = module.build_curve_lock(**lock_kwargs)
    return {
        "counterfactual_curve_lock": lock,
        "lock_kwargs": lock_kwargs,
        "prepared_completion_kwargs": {
            "_prepared_completion": _prepared_completion(stand_downs)
        },
    }


def test_valid_lock_is_lineage_bound_before_scoring():
    result = module.build_curve_lock(**_lock_kwargs())
    assert result["actual_g16_outcomes_used"] is False
    assert result["fixed_scoring_may_begin"] is True
    assert result["counterfactual_lineage_locked_before_fixed_scoring"] is True
    assert result["candidate_evidence_fingerprints"] == {"a": "ea", "b": "eb"}


def test_prepared_authorization_substitution_is_rejected():
    kwargs = _lock_kwargs()
    kwargs["prepared_curve_authorization"] = {"fingerprint": "replacement"}
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.build_curve_lock(**kwargs)


def test_candidate_registry_substitution_is_rejected():
    kwargs = _lock_kwargs()
    kwargs["prepared_lock_kwargs"]["_prepared_lock"]["registered_candidate_ids"] = [
        "legacy"
    ]
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.build_curve_lock(**kwargs)


def test_candidate_evidence_incomplete_is_rejected():
    kwargs = _lock_kwargs()
    candidate = kwargs["counterfactual_curve_authorization"]
    candidate["candidate_evidence_fingerprints"].pop("b")
    candidate.pop("fingerprint")
    candidate["fingerprint"] = module._fp(candidate)
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.build_curve_lock(**kwargs)


def test_refingerprinted_lock_tampering_is_rejected():
    kwargs = _lock_kwargs()
    result = module.build_curve_lock(**kwargs)
    result["g16_registry_fingerprint"] = "replacement"
    result.pop("lock_fingerprint")
    result["lock_fingerprint"] = module._fp(result)
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.validate_curve_lock(result, **kwargs)


def test_valid_completion_preserves_lineage_through_scoring():
    kwargs = _completion_kwargs()
    result = module.build_completion(**kwargs)
    assert result["actual_g16_outcomes_used"] is True
    assert result["counterfactual_lineage_preserved_through_fixed_scoring"] is True
    assert result["g16_reusable_as_untouched_holdout"] is False


def test_prepared_completion_lock_bypass_is_rejected():
    kwargs = _completion_kwargs()
    kwargs["prepared_completion_kwargs"]["_prepared_completion"][
        "curve_lock_fingerprint"
    ] = "replacement"
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.build_completion(**kwargs)


def test_adjudication_lineage_substitution_is_rejected():
    kwargs = _completion_kwargs()
    kwargs["prepared_completion_kwargs"]["_prepared_completion"][
        "g15_lesson_adjudication_fingerprint"
    ] = "replacement"
    with pytest.raises(module.G16CounterfactualPublicationError):
        module.build_completion(**kwargs)


def test_stand_downs_are_unionized_and_visible():
    lock_kwargs = _lock_kwargs(["2026-03-30"])
    lock = module.build_curve_lock(**lock_kwargs)
    kwargs = {
        "counterfactual_curve_lock": lock,
        "lock_kwargs": lock_kwargs,
        "prepared_completion_kwargs": {
            "_prepared_completion": _prepared_completion(["2026-03-31"])
        },
    }
    result = module.build_completion(**kwargs)
    assert result["stand_down_days"] == ["2026-03-30", "2026-03-31"]
    assert result["status"] == module.READY_WITH_STAND_DOWNS


def test_authority_escalation_is_rejected():
    kwargs = _completion_kwargs()
    result = module.build_completion(**kwargs)
    for field in (
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        altered = copy.deepcopy(result)
        altered[field] = True
        altered.pop("completion_fingerprint")
        altered["completion_fingerprint"] = module._fp(altered)
        with pytest.raises(module.G16CounterfactualPublicationError):
            module.validate_completion(altered, **kwargs)


def test_sources_are_immutable():
    lock_kwargs = _lock_kwargs()
    before = copy.deepcopy(lock_kwargs)
    module.build_curve_lock(**lock_kwargs)
    assert lock_kwargs == before

    completion_kwargs = _completion_kwargs()
    before = copy.deepcopy(completion_kwargs)
    module.build_completion(**completion_kwargs)
    assert completion_kwargs == before


def test_outputs_are_deterministic():
    lock_kwargs = _lock_kwargs()
    assert module.build_curve_lock(**lock_kwargs) == module.build_curve_lock(**lock_kwargs)

    completion_kwargs = _completion_kwargs()
    assert module.build_completion(**completion_kwargs) == module.build_completion(
        **completion_kwargs
    )
