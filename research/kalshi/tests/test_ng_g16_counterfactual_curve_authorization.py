from __future__ import annotations

import copy

import pytest

import ng_g16_counterfactual_curve_authorization as module


def _case():
    fixture = module._fixture()
    kwargs = {key: value for key, value in fixture.items() if not key.startswith("_")}
    result = module.build_authorization(**kwargs)
    return fixture, kwargs, result


def _close(fixture):
    fixture["_temporary"].cleanup()


def test_valid_chain_is_outcome_blind_and_lineage_bound():
    fixture, kwargs, result = _case()
    try:
        module.validate_authorization(result, **kwargs)
        assert result["candidate_count"] > 0
        assert result["candidate_ids"] == sorted(result["candidate_evidence_fingerprints"])
        assert result["actual_g15_outcomes_used"] is True
        assert result["actual_g16_outcomes_used"] is False
        assert result["g16_scoring_authorized"] is False
    finally:
        _close(fixture)


def test_counterfactual_causal_substitution_is_rejected():
    fixture, kwargs, _ = _case()
    try:
        altered = copy.deepcopy(kwargs["counterfactual_authorization"])
        altered["g16_registry_fingerprint"] = "replacement"
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        kwargs["counterfactual_authorization"] = altered
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_prepared_curve_substitution_is_rejected():
    fixture, kwargs, _ = _case()
    try:
        altered = copy.deepcopy(kwargs["prepared_curve_authorization"])
        altered["refined_curve_fingerprint"] = "replacement"
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        kwargs["prepared_curve_authorization"] = altered
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_registered_candidate_substitution_is_rejected():
    fixture, kwargs, _ = _case()
    try:
        altered = copy.deepcopy(kwargs["prepared_curve_authorization"])
        altered["registered_candidate_ids"] = ["legacy_candidate"]
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        kwargs["prepared_curve_authorization"] = altered
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_counterfactual_evidence_tampering_is_rejected():
    fixture, kwargs, _ = _case()
    try:
        altered = copy.deepcopy(kwargs["counterfactual_authorization"])
        first = altered["candidate_ids"][0]
        altered["candidate_evidence_fingerprints"][first] = "replacement"
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        kwargs["counterfactual_authorization"] = altered
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_plan_fingerprint_bypass_is_rejected():
    fixture, kwargs, _ = _case()
    try:
        altered = copy.deepcopy(kwargs["prepared_curve_authorization"])
        altered["plan_fingerprint"] = "replacement"
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        kwargs["prepared_curve_authorization"] = altered
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_top_level_refingerprinted_tampering_is_rejected():
    fixture, kwargs, result = _case()
    try:
        altered = copy.deepcopy(result)
        altered["candidate_ids"] = altered["candidate_ids"][:-1]
        altered.pop("fingerprint", None)
        altered["fingerprint"] = module._fp(altered)
        with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
            module.validate_authorization(altered, **kwargs)
    finally:
        _close(fixture)


def test_authority_escalation_is_rejected():
    fixture, kwargs, result = _case()
    try:
        for field in (
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "random_shuffle_used",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            altered = copy.deepcopy(result)
            altered[field] = True
            altered.pop("fingerprint", None)
            altered["fingerprint"] = module._fp(altered)
            with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
                module.validate_authorization(altered, **kwargs)
    finally:
        _close(fixture)


def test_cme_and_brokerage_substitution_is_rejected():
    fixture, kwargs, result = _case()
    try:
        for field, value in (
            ("cme_event_contracts_mode", "LIVE"),
            ("brokerage_contract", "ibkr"),
        ):
            altered = copy.deepcopy(result)
            altered[field] = value
            altered.pop("fingerprint", None)
            altered["fingerprint"] = module._fp(altered)
            with pytest.raises(module.G16CounterfactualCurveAuthorizationError):
                module.validate_authorization(altered, **kwargs)
    finally:
        _close(fixture)


def test_sources_are_immutable():
    fixture = module._fixture()
    try:
        kwargs = {key: value for key, value in fixture.items() if not key.startswith("_")}
        before = copy.deepcopy(kwargs)
        module.build_authorization(**kwargs)
        assert kwargs == before
    finally:
        _close(fixture)


def test_output_is_deterministic():
    fixture = module._fixture()
    try:
        kwargs = {key: value for key, value in fixture.items() if not key.startswith("_")}
        assert module.build_authorization(**kwargs) == module.build_authorization(**kwargs)
    finally:
        _close(fixture)


def test_curve_candidates_are_subset_of_counterfactual_posterior_candidates():
    fixture, _, result = _case()
    try:
        assert set(result["candidate_ids_used_by_curve"]).issubset(set(result["candidate_ids"]))
        assert result["next_permitted_stage"] == module.NEXT_STAGE
        assert result["may_change_posterior"] is False
        assert result["blind_forecasts_immutable"] is True
    finally:
        _close(fixture)
