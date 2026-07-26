#!/usr/bin/env python3
"""Bind attribution-scored G15 lesson lineage into the outcome-blind G16 curve.

The gate recursively validates the attribution-bound G16 posterior and the existing
counterfactual curve authorization, then proves that the deterministic prepared curve,
its candidate usage, and its refined-curve fingerprint descend from the same separately
scored G15 lesson lineage. Fixed G15 outcomes are disclosed; G16 outcomes remain closed.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "ng_g16_attribution_bound_curve_authorization_gate.v1"
BUNDLE_SCHEMA = "ng_g16_attribution_bound_curve_validation_bundle.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_LESSONS_TO_G16_OUTCOME_BLIND_CURVE_ONLY"
READY = "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED"
READY_WITH_STAND_DOWNS = "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "LOCK_G16_REFINED_CURVE_WITH_ATTRIBUTION_BOUND_LINEAGE_BEFORE_SCORING"
BOUND_SCHEMA = "ng_g16_attribution_bound_causal_authorization_gate.v1"
LEGACY_CURVE_SCHEMA = "ng_g16_counterfactual_curve_authorization.v1"
PREPARED_CURVE_SCHEMA = "ng_g16_prepared_curve_authorization.v1"


class G16AttributionBoundCurveAuthorizationError(ValueError):
    """Raised when the G15 score lineage and deterministic G16 curve diverge."""


def _fingerprint(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_fp = _fingerprint


def _signed(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    observed = result.pop("fingerprint", None)
    if not isinstance(observed, str) or observed != _fingerprint(result):
        raise G16AttributionBoundCurveAuthorizationError(f"{label} fingerprint mismatch")
    result["fingerprint"] = observed
    return result


def _controls(
    value: Mapping[str, Any],
    label: str,
    *,
    require_fixed_g15: bool,
    blind_immutability_field: str,
) -> None:
    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "g16_outcome_access_authorized",
        "options_lane_started",
    )
    for field in false_fields:
        if field in value and value.get(field) is not False:
            raise G16AttributionBoundCurveAuthorizationError(
                f"{label} must keep {field}=false"
            )
    if require_fixed_g15 and value.get("actual_g15_outcomes_used") is not True:
        raise G16AttributionBoundCurveAuthorizationError(
            f"{label} must disclose fixed G15 outcome use"
        )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16AttributionBoundCurveAuthorizationError(
            f"{label} must preserve one signal authority"
        )
    if value.get(blind_immutability_field) is not True:
        raise G16AttributionBoundCurveAuthorizationError(
            f"{label} must keep {blind_immutability_field}=true"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16AttributionBoundCurveAuthorizationError(
            f"{label} must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16AttributionBoundCurveAuthorizationError(
            f"{label} must preserve tastytrade rather than IBKR"
        )


def _normalize_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(dict(value))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise G16AttributionBoundCurveAuthorizationError(
            "validation bundle schema mismatch"
        )
    observed = bundle.pop("fingerprint", None)
    if observed != _fingerprint(bundle):
        raise G16AttributionBoundCurveAuthorizationError(
            "validation bundle fingerprint mismatch"
        )
    bundle["fingerprint"] = observed
    for field in ("bound_causal_validation", "legacy_curve_validation"):
        if not isinstance(bundle.get(field), Mapping):
            raise G16AttributionBoundCurveAuthorizationError(
                f"validation bundle lacks {field} mapping"
            )
    legacy = dict(bundle["legacy_curve_validation"])
    required = (
        "counterfactual_authorization",
        "prepared_curve_authorization",
        "counterfactual_kwargs",
        "curve_kwargs",
    )
    if any(not isinstance(legacy.get(field), Mapping) for field in required):
        raise G16AttributionBoundCurveAuthorizationError(
            "legacy curve validation bundle is incomplete"
        )
    return bundle


def _default_bound_validator(
    value: Mapping[str, Any], validation_kwargs: Mapping[str, Any]
) -> None:
    from ng_g16_attribution_bound_causal_authorization_gate import validate_gate

    validate_gate(value, **dict(validation_kwargs))


def _decoded_legacy_kwargs(value: Mapping[str, Any]) -> dict[str, Any]:
    kwargs = copy.deepcopy(dict(value))
    curve_kwargs = copy.deepcopy(dict(kwargs.get("curve_kwargs") or {}))
    encoded = curve_kwargs.pop("blind_file_bytes_base64", None)
    if encoded is not None:
        try:
            curve_kwargs["blind_file_bytes"] = base64.b64decode(
                str(encoded).encode("ascii"), validate=True
            )
        except (ValueError, UnicodeEncodeError, binascii.Error) as error:
            raise G16AttributionBoundCurveAuthorizationError(
                "legacy curve blind-file base64 is invalid"
            ) from error
    kwargs["curve_kwargs"] = curve_kwargs
    return kwargs


def _default_legacy_curve_validator(
    value: Mapping[str, Any], validation_kwargs: Mapping[str, Any]
) -> None:
    from ng_g16_counterfactual_curve_authorization import validate_authorization

    validate_authorization(value, **_decoded_legacy_kwargs(validation_kwargs))


def _cross_checks(
    bound: Mapping[str, Any],
    legacy: Mapping[str, Any],
    prepared: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> tuple[list[str], dict[str, str], list[str], list[str]]:
    legacy_validation = dict(bundle["legacy_curve_validation"])
    bundled_prepared = legacy_validation.get("prepared_curve_authorization")
    if dict(bundled_prepared or {}) != dict(prepared):
        raise G16AttributionBoundCurveAuthorizationError(
            "validation bundle substituted the prepared curve authorization"
        )
    bundled_causal = dict(legacy_validation.get("counterfactual_authorization") or {})
    if bundled_causal.get("fingerprint") != bound.get(
        "legacy_counterfactual_causal_authorization_fingerprint"
    ):
        raise G16AttributionBoundCurveAuthorizationError(
            "validation bundle legacy causal authorization is outside attribution-bound lineage"
        )

    links = {
        "legacy causal": (
            bound.get("legacy_counterfactual_causal_authorization_fingerprint"),
            legacy.get("counterfactual_causal_authorization_fingerprint"),
        ),
        "prepared causal": (
            bound.get("prepared_causal_authorization_fingerprint"),
            legacy.get("prepared_causal_authorization_fingerprint"),
            prepared.get("prepared_causal_authorization_fingerprint"),
        ),
        "prepared replay": (
            bound.get("prepared_replay_gate_fingerprint"),
            legacy.get("prepared_replay_gate_fingerprint"),
            prepared.get("prepared_replay_gate_fingerprint"),
        ),
        "historical replay": (
            bound.get("replay_fingerprint"),
            legacy.get("replay_fingerprint"),
            prepared.get("replay_fingerprint"),
        ),
        "G16 plan": (
            bound.get("g16_plan_fingerprint"),
            legacy.get("g16_plan_fingerprint"),
            prepared.get("plan_fingerprint"),
        ),
        "posterior stream": (
            bound.get("posterior_stream_fingerprint"),
            legacy.get("posterior_stream_fingerprint"),
            prepared.get("posterior_stream_fingerprint"),
        ),
        "authorization stream": (
            bound.get("authorization_stream_fingerprint"),
            legacy.get("authorization_stream_fingerprint"),
            prepared.get("authorization_stream_fingerprint"),
        ),
        "blind forecast": (
            bound.get("g16_blind_forecast_fingerprint"),
            legacy.get("g16_blind_forecast_fingerprint"),
            prepared.get("blind_forecast_fingerprint"),
        ),
        "refined curve": (
            legacy.get("refined_curve_fingerprint"),
            prepared.get("refined_curve_fingerprint"),
        ),
        "prepared curve authorization": (
            legacy.get("prepared_curve_authorization_fingerprint"),
            prepared.get("fingerprint"),
        ),
    }
    for label, values in links.items():
        normalized = [str(item or "") for item in values]
        if any(not item for item in normalized) or len(set(normalized)) != 1:
            raise G16AttributionBoundCurveAuthorizationError(
                f"{label} lineage mismatch"
            )

    candidate_ids = [str(item) for item in bound.get("candidate_ids") or []]
    if (
        not candidate_ids
        or candidate_ids != sorted(candidate_ids)
        or len(candidate_ids) != len(set(candidate_ids))
    ):
        raise G16AttributionBoundCurveAuthorizationError(
            "candidate ids must be non-empty, sorted, and unique"
        )
    if int(bound.get("candidate_count") or 0) != len(candidate_ids):
        raise G16AttributionBoundCurveAuthorizationError("candidate_count mismatch")
    if [str(item) for item in legacy.get("candidate_ids") or []] != candidate_ids:
        raise G16AttributionBoundCurveAuthorizationError(
            "legacy curve candidate set mismatch"
        )
    if [str(item) for item in prepared.get("registered_candidate_ids") or []] != candidate_ids:
        raise G16AttributionBoundCurveAuthorizationError(
            "prepared curve candidate registry mismatch"
        )

    evidence = {
        str(key): str(item)
        for key, item in dict(
            bound.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    if sorted(evidence) != candidate_ids or any(not item for item in evidence.values()):
        raise G16AttributionBoundCurveAuthorizationError(
            "candidate evidence is incomplete"
        )
    posterior_used = {
        str(item)
        for item in bound.get("candidate_ids_observed_in_posterior_attribution") or []
    }
    curve_used = sorted(
        {str(item) for item in legacy.get("candidate_ids_used_by_curve") or []}
    )
    if curve_used != sorted(
        {str(item) for item in prepared.get("used_candidate_ids") or []}
    ):
        raise G16AttributionBoundCurveAuthorizationError(
            "curve used-candidate sets differ"
        )
    if not set(curve_used).issubset(posterior_used):
        raise G16AttributionBoundCurveAuthorizationError(
            "curve used a candidate absent from authorized posterior attribution"
        )

    stand_downs = sorted(
        {str(item) for item in bound.get("stand_down_days") or []}
        | {str(item) for item in legacy.get("stand_down_days") or []}
        | {str(item) for item in prepared.get("all_stand_down_days") or []}
    )
    return candidate_ids, evidence, curve_used, stand_downs


def _build_gate(
    *,
    attribution_bound_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
    validation_bundle: Mapping[str, Any],
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_validator,
    legacy_curve_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_legacy_curve_validator,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            attribution_bound_causal_authorization,
            counterfactual_curve_authorization,
            prepared_curve_authorization,
            validation_bundle,
        )
    )
    bundle = _normalize_bundle(validation_bundle)
    try:
        bound_validator(
            attribution_bound_causal_authorization,
            dict(bundle["bound_causal_validation"]),
        )
        legacy_curve_validator(
            counterfactual_curve_authorization,
            dict(bundle["legacy_curve_validation"]),
        )
    except Exception as error:
        raise G16AttributionBoundCurveAuthorizationError(str(error)) from error

    bound = _signed(
        attribution_bound_causal_authorization,
        "attribution-bound causal authorization",
    )
    legacy = _signed(
        counterfactual_curve_authorization,
        "counterfactual curve authorization",
    )
    prepared = _signed(prepared_curve_authorization, "prepared curve authorization")
    if bound.get("schema") != BOUND_SCHEMA or bound.get("status") not in {
        "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED",
        "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCurveAuthorizationError(
            "attribution-bound causal authorization is not ready"
        )
    if legacy.get("schema") != LEGACY_CURVE_SCHEMA or legacy.get("status") not in {
        "G16_COUNTERFACTUAL_CURVE_AUTHORIZED",
        "G16_COUNTERFACTUAL_CURVE_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCurveAuthorizationError(
            "counterfactual curve authorization is not ready"
        )
    if prepared.get("schema") != PREPARED_CURVE_SCHEMA or prepared.get("status") not in {
        "EXACT_G16_PREPARED_CURVE_AUTHORIZED",
        "EXACT_G16_PREPARED_CURVE_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCurveAuthorizationError(
            "prepared curve authorization is not ready"
        )

    _controls(
        bound,
        "attribution-bound causal authorization",
        require_fixed_g15=True,
        blind_immutability_field="blind_forecasts_immutable",
    )
    _controls(
        legacy,
        "counterfactual curve authorization",
        require_fixed_g15=True,
        blind_immutability_field="blind_forecasts_immutable",
    )
    _controls(
        prepared,
        "prepared curve authorization",
        require_fixed_g15=False,
        blind_immutability_field="blind_forecast_immutable",
    )
    for field in (
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "g16_posterior_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
    ):
        if bound.get(field) is not True:
            raise G16AttributionBoundCurveAuthorizationError(
                f"attribution-bound causal authorization lost {field}"
            )

    candidate_ids, evidence, curve_used, stand_downs = _cross_checks(
        bound, legacy, prepared, bundle
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_downs else READY,
        "authority": AUTHORITY,
        "attribution_bound_causal_authorization_fingerprint": bound["fingerprint"],
        "counterfactual_curve_authorization_fingerprint": legacy["fingerprint"],
        "prepared_curve_authorization_fingerprint": prepared["fingerprint"],
        "validation_bundle_fingerprint": bundle["fingerprint"],
        "attribution_bound_lineage_fingerprint": bound[
            "attribution_bound_lineage_fingerprint"
        ],
        "attribution_bound_publication_fingerprint": bound[
            "attribution_bound_publication_fingerprint"
        ],
        "attribution_authorization_fingerprint": bound[
            "attribution_authorization_fingerprint"
        ],
        "publication_completion_fingerprint": bound[
            "publication_completion_fingerprint"
        ],
        "counterfactual_attribution_fingerprint": bound[
            "counterfactual_attribution_fingerprint"
        ],
        "counterfactual_lesson_gate_fingerprint": bound[
            "counterfactual_lesson_gate_fingerprint"
        ],
        "legacy_lineage_fingerprint": bound["legacy_lineage_fingerprint"],
        "blind_score_fingerprint": bound["blind_score_fingerprint"],
        "refined_score_fingerprint": bound["refined_score_fingerprint"],
        "comparison_fingerprint": bound["comparison_fingerprint"],
        "g15_adjudication_fingerprint": bound["g15_adjudication_fingerprint"],
        "g16_registry_fingerprint": bound["g16_registry_fingerprint"],
        "g16_plan_fingerprint": bound["g16_plan_fingerprint"],
        "prepared_causal_authorization_fingerprint": bound[
            "prepared_causal_authorization_fingerprint"
        ],
        "prepared_replay_gate_fingerprint": bound[
            "prepared_replay_gate_fingerprint"
        ],
        "replay_fingerprint": bound["replay_fingerprint"],
        "manifest_fingerprint": bound["manifest_fingerprint"],
        "prepared_corpus_fingerprint": bound["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": bound["blind_prior_fingerprint"],
        "authorization_stream_fingerprint": bound[
            "authorization_stream_fingerprint"
        ],
        "posterior_stream_fingerprint": bound["posterior_stream_fingerprint"],
        "g16_blind_forecast_fingerprint": bound[
            "g16_blind_forecast_fingerprint"
        ],
        "refined_curve_fingerprint": legacy["refined_curve_fingerprint"],
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": curve_used,
        "stand_down_days": stand_downs,
        "all_six_factors_authorized_before_scoring": True,
        "separate_blind_refined_scores_verified": True,
        "scored_lessons_bound_to_attribution_publication": True,
        "g16_plan_bound_to_validated_g15_lessons": True,
        "g16_posterior_bound_to_attribution_scored_g15_lessons": True,
        "g16_curve_bound_to_attribution_scored_g15_lessons": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_outcome_access_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": NEXT_STAGE,
        "attribution_bound_causal_authorization": copy.deepcopy(bound),
        "counterfactual_curve_authorization": copy.deepcopy(legacy),
        "prepared_curve_authorization": copy.deepcopy(prepared),
        "validation_bundle": copy.deepcopy(bundle),
        "note": (
            "The deterministic outcome-blind G16 curve is recursively bound to the "
            "same six-factor-authorized, separately scored G15 lessons used by the "
            "pre-cutoff G16 posterior. G16 outcomes and scoring remain closed."
        ),
    }
    result["fingerprint"] = _fingerprint(result)
    if (
        attribution_bound_causal_authorization,
        counterfactual_curve_authorization,
        prepared_curve_authorization,
        validation_bundle,
    ) != originals:
        raise G16AttributionBoundCurveAuthorizationError(
            "curve lineage gate mutated an input artifact"
        )
    return result


def build_gate(**kwargs: Any) -> dict[str, Any]:
    result = _build_gate(**kwargs)
    validate_gate(
        result,
        bound_validator=kwargs.get("bound_validator", _default_bound_validator),
        legacy_curve_validator=kwargs.get(
            "legacy_curve_validator", _default_legacy_curve_validator
        ),
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_validator,
    legacy_curve_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_legacy_curve_validator,
) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fingerprint(candidate):
        raise G16AttributionBoundCurveAuthorizationError(
            "gate schema or fingerprint mismatch"
        )
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16AttributionBoundCurveAuthorizationError("gate is not ready")
    if candidate.get("authority") != AUTHORITY:
        raise G16AttributionBoundCurveAuthorizationError("gate authority mismatch")
    _controls(
        candidate,
        "attribution-bound curve gate",
        require_fixed_g15=True,
        blind_immutability_field="blind_forecasts_immutable",
    )
    if candidate.get("g16_curve_bound_to_attribution_scored_g15_lessons") is not True:
        raise G16AttributionBoundCurveAuthorizationError(
            "G16 curve is not bound to attribution-scored G15 lessons"
        )
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16AttributionBoundCurveAuthorizationError("gate next stage mismatch")

    bound = candidate.get("attribution_bound_causal_authorization")
    legacy = candidate.get("counterfactual_curve_authorization")
    prepared = candidate.get("prepared_curve_authorization")
    bundle = candidate.get("validation_bundle")
    if not all(isinstance(item, Mapping) for item in (bound, legacy, prepared, bundle)):
        raise G16AttributionBoundCurveAuthorizationError(
            "gate lacks recursively embedded authorization or validation evidence"
        )
    rebuilt = _build_gate(
        attribution_bound_causal_authorization=bound,
        counterfactual_curve_authorization=legacy,
        prepared_curve_authorization=prepared,
        validation_bundle=bundle,
        bound_validator=bound_validator,
        legacy_curve_validator=legacy_curve_validator,
    )
    if dict(value) != rebuilt:
        raise G16AttributionBoundCurveAuthorizationError(
            "gate differs from deterministic recursive reconstruction"
        )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _synthetic_fixture() -> dict[str, Any]:
    candidate_ids = ["g15_counterfactual.activity"]
    evidence = {candidate_ids[0]: "e" * 64}
    false_controls = {
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
        "g16_outcome_access_authorized": False,
        "options_lane_started": False,
        "one_signal_authority_preserved": True,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
    }
    bound: dict[str, Any] = {
        "schema": BOUND_SCHEMA,
        "status": "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED",
        "authority": "G15_ATTRIBUTION_BOUND_LESSONS_TO_G16_PRE_CUTOFF_CAUSAL_ONLY",
        "legacy_counterfactual_causal_authorization_fingerprint": "c" * 64,
        "attribution_bound_lineage_fingerprint": "l" * 64,
        "attribution_bound_publication_fingerprint": "p" * 64,
        "attribution_authorization_fingerprint": "u" * 64,
        "publication_completion_fingerprint": "q" * 64,
        "counterfactual_attribution_fingerprint": "a" * 64,
        "counterfactual_lesson_gate_fingerprint": "k" * 64,
        "legacy_lineage_fingerprint": "x" * 64,
        "blind_score_fingerprint": "b" * 64,
        "refined_score_fingerprint": "r" * 64,
        "comparison_fingerprint": "m" * 64,
        "g15_adjudication_fingerprint": "j" * 64,
        "g16_registry_fingerprint": "g" * 64,
        "g16_plan_fingerprint": "n" * 64,
        "prepared_causal_authorization_fingerprint": "d" * 64,
        "prepared_replay_gate_fingerprint": "t" * 64,
        "replay_fingerprint": "h" * 64,
        "manifest_fingerprint": "i" * 64,
        "prepared_corpus_fingerprint": "o" * 64,
        "blind_prior_fingerprint": "v" * 64,
        "authorization_stream_fingerprint": "z" * 64,
        "posterior_stream_fingerprint": "s" * 64,
        "g16_blind_forecast_fingerprint": "f" * 64,
        "candidate_count": 1,
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_observed_in_posterior_attribution": candidate_ids,
        "stand_down_days": [],
        "all_six_factors_authorized_before_scoring": True,
        "separate_blind_refined_scores_verified": True,
        "scored_lessons_bound_to_attribution_publication": True,
        "g16_plan_bound_to_validated_g15_lessons": True,
        "g16_posterior_bound_to_attribution_scored_g15_lessons": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "blind_forecasts_immutable": True,
        **false_controls,
    }
    bound["fingerprint"] = _fingerprint(bound)

    prepared: dict[str, Any] = {
        "schema": PREPARED_CURVE_SCHEMA,
        "status": "EXACT_G16_PREPARED_CURVE_AUTHORIZED",
        "authority": "EXACT_G16_PREPARED_CAUSAL_TO_OUTCOME_BLIND_CURVE_ONLY",
        "prepared_causal_authorization_fingerprint": "d" * 64,
        "prepared_replay_gate_fingerprint": "t" * 64,
        "replay_fingerprint": "h" * 64,
        "manifest_fingerprint": "i" * 64,
        "prepared_corpus_fingerprint": "o" * 64,
        "blind_prior_fingerprint": "v" * 64,
        "blind_forecast_fingerprint": "f" * 64,
        "plan_fingerprint": "n" * 64,
        "authorization_stream_fingerprint": "z" * 64,
        "posterior_stream_fingerprint": "s" * 64,
        "refined_curve_fingerprint": "y" * 64,
        "registered_candidate_ids": candidate_ids,
        "used_candidate_ids": candidate_ids,
        "all_stand_down_days": [],
        "blind_forecast_immutable": True,
        **false_controls,
    }
    prepared.pop("g16_outcome_access_authorized", None)
    prepared["fingerprint"] = _fingerprint(prepared)

    legacy: dict[str, Any] = {
        "schema": LEGACY_CURVE_SCHEMA,
        "status": "G16_COUNTERFACTUAL_CURVE_AUTHORIZED",
        "authority": "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_OUTCOME_BLIND_CURVE_ONLY",
        "counterfactual_causal_authorization_fingerprint": "c" * 64,
        "prepared_curve_authorization_fingerprint": prepared["fingerprint"],
        "prepared_causal_authorization_fingerprint": "d" * 64,
        "prepared_replay_gate_fingerprint": "t" * 64,
        "replay_fingerprint": "h" * 64,
        "manifest_fingerprint": "i" * 64,
        "prepared_corpus_fingerprint": "o" * 64,
        "blind_prior_fingerprint": "v" * 64,
        "g16_blind_forecast_fingerprint": "f" * 64,
        "g16_plan_fingerprint": "n" * 64,
        "authorization_stream_fingerprint": "z" * 64,
        "posterior_stream_fingerprint": "s" * 64,
        "refined_curve_fingerprint": "y" * 64,
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": candidate_ids,
        "stand_down_days": [],
        "actual_g15_outcomes_used": True,
        "blind_forecasts_immutable": True,
        **false_controls,
    }
    legacy["fingerprint"] = _fingerprint(legacy)

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "bound_causal_validation": {},
        "legacy_curve_validation": {
            "counterfactual_authorization": {"fingerprint": "c" * 64},
            "prepared_curve_authorization": copy.deepcopy(prepared),
            "counterfactual_kwargs": {},
            "curve_kwargs": {},
        },
    }
    bundle["fingerprint"] = _fingerprint(bundle)
    return {
        "attribution_bound_causal_authorization": bound,
        "counterfactual_curve_authorization": legacy,
        "prepared_curve_authorization": prepared,
        "validation_bundle": bundle,
        "bound_validator": _noop,
        "legacy_curve_validator": _noop,
    }


def selftest() -> int:
    fixture = _synthetic_fixture()
    result = build_gate(**fixture)
    assert result["status"] == READY
    assert result["g16_curve_bound_to_attribution_scored_g15_lessons"] is True
    validate_gate(result, bound_validator=_noop, legacy_curve_validator=_noop)
    print("[ng_g16_attribution_bound_curve_authorization_gate] selftest PASS")
    return 0


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16AttributionBoundCurveAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16AttributionBoundCurveAuthorizationError(
            f"artifact must be an object: {path}"
        )
    return value


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-bound-causal", type=Path)
    parser.add_argument("--counterfactual-curve", type=Path)
    parser.add_argument("--prepared-curve", type=Path)
    parser.add_argument("--validation-bundle", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(
        value is None
        for value in (
            args.attribution_bound_causal,
            args.counterfactual_curve,
            args.prepared_curve,
            args.validation_bundle,
            args.out,
        )
    ):
        parser.error(
            "--attribution-bound-causal, --counterfactual-curve, --prepared-curve, "
            "--validation-bundle, and --out are required"
        )
    result = build_gate(
        attribution_bound_causal_authorization=_load(args.attribution_bound_causal),
        counterfactual_curve_authorization=_load(args.counterfactual_curve),
        prepared_curve_authorization=_load(args.prepared_curve),
        validation_bundle=_load(args.validation_bundle),
    )
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
