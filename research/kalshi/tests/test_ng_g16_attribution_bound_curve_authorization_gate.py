from __future__ import annotations

import copy

import pytest

import ng_g16_attribution_bound_curve_authorization_gate as gate


def _fixture() -> dict:
    return gate._synthetic_fixture()


def _build(fixture: dict | None = None) -> dict:
    return gate.build_gate(**(fixture or _fixture()))


def _refingerprint(value: dict) -> dict:
    candidate = copy.deepcopy(value)
    candidate.pop("fingerprint", None)
    candidate["fingerprint"] = gate._fingerprint(candidate)
    return candidate


def _rebundle(fixture: dict) -> None:
    bundle = fixture["validation_bundle"]
    bundle.pop("fingerprint", None)
    bundle["fingerprint"] = gate._fingerprint(bundle)


def test_exact_attribution_bound_curve_authorization_passes() -> None:
    value = _build()
    assert value["status"] == gate.READY
    assert value["g16_curve_bound_to_attribution_scored_g15_lessons"] is True
    assert value["blind_score_fingerprint"] != value["refined_score_fingerprint"]
    gate.validate_gate(
        value,
        bound_validator=gate._noop,
        legacy_curve_validator=gate._noop,
    )


def test_refined_curve_substitution_is_rejected() -> None:
    fixture = _fixture()
    prepared = fixture["prepared_curve_authorization"]
    prepared["refined_curve_fingerprint"] = "s" * 64
    fixture["prepared_curve_authorization"] = _refingerprint(prepared)
    fixture["validation_bundle"]["legacy_curve_validation"][
        "prepared_curve_authorization"
    ] = copy.deepcopy(fixture["prepared_curve_authorization"])
    _rebundle(fixture)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="refined curve lineage mismatch",
    ):
        _build(fixture)


def test_validation_bundle_legacy_causal_substitution_is_rejected() -> None:
    fixture = _fixture()
    fixture["validation_bundle"]["legacy_curve_validation"][
        "counterfactual_authorization"
    ]["fingerprint"] = "w" * 64
    _rebundle(fixture)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="outside attribution-bound lineage",
    ):
        _build(fixture)


def test_validation_bundle_prepared_curve_substitution_is_rejected() -> None:
    fixture = _fixture()
    bundled = fixture["validation_bundle"]["legacy_curve_validation"][
        "prepared_curve_authorization"
    ]
    bundled["plan_fingerprint"] = "w" * 64
    bundled = _refingerprint(bundled)
    fixture["validation_bundle"]["legacy_curve_validation"][
        "prepared_curve_authorization"
    ] = bundled
    _rebundle(fixture)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="substituted the prepared curve",
    ):
        _build(fixture)


def test_curve_candidate_outside_posterior_is_rejected() -> None:
    fixture = _fixture()
    bound = fixture["attribution_bound_causal_authorization"]
    bound["candidate_ids_observed_in_posterior_attribution"] = []
    fixture["attribution_bound_causal_authorization"] = _refingerprint(bound)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="absent from authorized posterior",
    ):
        _build(fixture)


def test_brain_write_escalation_is_rejected() -> None:
    fixture = _fixture()
    bound = fixture["attribution_bound_causal_authorization"]
    bound["may_update_ng_brain"] = True
    fixture["attribution_bound_causal_authorization"] = _refingerprint(bound)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="may_update_ng_brain",
    ):
        _build(fixture)


def test_options_lane_escalation_is_rejected() -> None:
    fixture = _fixture()
    legacy = fixture["counterfactual_curve_authorization"]
    legacy["options_lane_started"] = True
    fixture["counterfactual_curve_authorization"] = _refingerprint(legacy)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="options_lane_started",
    ):
        _build(fixture)


def test_g16_outcome_access_is_rejected() -> None:
    fixture = _fixture()
    prepared = fixture["prepared_curve_authorization"]
    prepared["actual_g16_outcomes_used"] = True
    fixture["prepared_curve_authorization"] = _refingerprint(prepared)
    fixture["validation_bundle"]["legacy_curve_validation"][
        "prepared_curve_authorization"
    ] = copy.deepcopy(fixture["prepared_curve_authorization"])
    _rebundle(fixture)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="actual_g16_outcomes_used",
    ):
        _build(fixture)


def test_nested_refingerprinted_tampering_is_rejected() -> None:
    value = _build()
    tampered = copy.deepcopy(value)
    nested = tampered["prepared_curve_authorization"]
    nested["plan_fingerprint"] = "i" * 64
    tampered["prepared_curve_authorization"] = _refingerprint(nested)
    tampered = _refingerprint(tampered)
    with pytest.raises(gate.G16AttributionBoundCurveAuthorizationError):
        gate.validate_gate(
            tampered,
            bound_validator=gate._noop,
            legacy_curve_validator=gate._noop,
        )


def test_score_lineage_outer_tamper_is_rejected_by_reconstruction() -> None:
    value = _build()
    tampered = copy.deepcopy(value)
    tampered["refined_score_fingerprint"] = "n" * 64
    tampered = _refingerprint(tampered)
    with pytest.raises(
        gate.G16AttributionBoundCurveAuthorizationError,
        match="reconstruction",
    ):
        gate.validate_gate(
            tampered,
            bound_validator=gate._noop,
            legacy_curve_validator=gate._noop,
        )


def test_inputs_are_immutable_and_output_is_deterministic() -> None:
    fixture = _fixture()
    original = copy.deepcopy(fixture)
    first = _build(fixture)
    second = _build(fixture)
    assert first == second
    assert fixture == original
