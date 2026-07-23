#!/usr/bin/env python3
"""Require G15 counterfactual lesson lineage through the G16 scoring wall.

The prepared publication gate already proves that an exact, outcome-blind G16
curve was locked before fixed outcomes were admitted. The counterfactual curve
authorization separately proves that the same curve descends from deterministic
G15 full-minus-neutral lesson evidence. This outer gate requires both contracts
at lock time and carries their exact lineage through scoring and publication.

It never reads G16 outcomes while creating the curve lock, never mutates a blind
forecast, posterior, or ``ng_brain.json``, forbids random shuffling, keeps CME
event contracts SHADOW, keeps tastytrade as the brokerage contract, and leaves
the options lane unstarted.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from ng_g16_counterfactual_curve_authorization import (
    AUTHORITY as COUNTERFACTUAL_AUTHORITY,
    G16CounterfactualCurveAuthorizationError,
    NEXT_STAGE as COUNTERFACTUAL_NEXT_STAGE,
    SCHEMA as COUNTERFACTUAL_SCHEMA,
    STATUS_READY as COUNTERFACTUAL_READY,
    STATUS_STAND_DOWNS as COUNTERFACTUAL_STAND_DOWNS,
    validate_authorization as validate_counterfactual_curve_authorization,
)
from ng_g16_prepared_publication_gate import (
    G16PreparedPublicationError,
    build_completion as build_prepared_completion,
    build_curve_lock as build_prepared_curve_lock,
    validate_completion as validate_prepared_completion,
    validate_curve_lock as validate_prepared_curve_lock,
)

LOCK_SCHEMA = "ng_g16_counterfactual_curve_lock.v1"
LOCK_AUTHORITY = "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_CURVE_LOCK_BEFORE_FIXED_SCORING"
LOCK_STATUS = "EXACT_G16_COUNTERFACTUAL_CURVE_LOCKED"
LOCK_NEXT_STAGE = "FIXED_G16_BLIND_REFINED_SCORING_WITH_COUNTERFACTUAL_LINEAGE"

SCHEMA = "ng_g16_counterfactual_publication_completion.v1"
AUTHORITY = "EXACT_G15_COUNTERFACTUAL_LINEAGE_THROUGH_G16_SCORED_PUBLICATION_ONLY"
READY = "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"


class G16CounterfactualPublicationError(ValueError):
    """Raised when scored G16 publication bypasses counterfactual lesson lineage."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(candidate):
        raise G16CounterfactualPublicationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _require_false(value: Mapping[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if value.get(field) is not False:
            raise G16CounterfactualPublicationError(f"{label}: {field} must remain false")


def _validate_counterfactual_authority(
    authorization: Mapping[str, Any],
    *,
    counterfactual_causal_authorization: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
    counterfactual_kwargs: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validate_counterfactual_curve_authorization(
            authorization,
            counterfactual_authorization=counterfactual_causal_authorization,
            prepared_curve_authorization=prepared_curve_authorization,
            counterfactual_kwargs=counterfactual_kwargs,
            curve_kwargs=curve_kwargs,
        )
    except G16CounterfactualCurveAuthorizationError as error:
        raise G16CounterfactualPublicationError(
            f"counterfactual curve authorization invalid: {error}"
        ) from error
    value = _verify_fingerprint(
        authorization, "fingerprint", label="counterfactual curve authorization"
    )
    if value.get("schema") != COUNTERFACTUAL_SCHEMA or value.get("authority") != COUNTERFACTUAL_AUTHORITY:
        raise G16CounterfactualPublicationError(
            "counterfactual curve authorization schema/authority mismatch"
        )
    if value.get("status") not in {COUNTERFACTUAL_READY, COUNTERFACTUAL_STAND_DOWNS}:
        raise G16CounterfactualPublicationError("counterfactual curve authorization is not ready")
    if value.get("next_permitted_stage") != COUNTERFACTUAL_NEXT_STAGE:
        raise G16CounterfactualPublicationError(
            "counterfactual curve authorization does not permit curve locking"
        )
    _require_false(
        value,
        (
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
            "options_lane_started",
        ),
        label="counterfactual curve authorization",
    )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16CounterfactualPublicationError("one signal authority must remain preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise G16CounterfactualPublicationError("blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16CounterfactualPublicationError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16CounterfactualPublicationError("brokerage contract must remain tastytrade")
    return value


def _candidate_lineage(value: Mapping[str, Any]) -> tuple[list[str], dict[str, str], list[str]]:
    candidate_ids = [str(item) for item in value.get("candidate_ids") or []]
    if not candidate_ids or candidate_ids != sorted(candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        raise G16CounterfactualPublicationError(
            "counterfactual candidate ids must be non-empty, unique, and sorted"
        )
    evidence = {
        str(key): str(item)
        for key, item in dict(value.get("candidate_evidence_fingerprints") or {}).items()
    }
    if sorted(evidence) != candidate_ids or any(not item for item in evidence.values()):
        raise G16CounterfactualPublicationError("counterfactual candidate evidence is incomplete")
    used = [str(item) for item in value.get("candidate_ids_used_by_curve") or []]
    if used != sorted(set(used)) or not set(used).issubset(set(candidate_ids)):
        raise G16CounterfactualPublicationError("curve-used candidates bypass counterfactual lineage")
    return candidate_ids, evidence, used


def _build_curve_lock(
    *,
    counterfactual_curve_authorization: Mapping[str, Any],
    counterfactual_causal_authorization: Mapping[str, Any],
    counterfactual_kwargs: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
    prepared_lock_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            counterfactual_curve_authorization,
            counterfactual_causal_authorization,
            counterfactual_kwargs,
            curve_kwargs,
            prepared_curve_authorization,
            prepared_lock_kwargs,
        )
    )
    counterfactual = _validate_counterfactual_authority(
        counterfactual_curve_authorization,
        counterfactual_causal_authorization=counterfactual_causal_authorization,
        prepared_curve_authorization=prepared_curve_authorization,
        counterfactual_kwargs=counterfactual_kwargs,
        curve_kwargs=curve_kwargs,
    )
    if counterfactual.get("prepared_curve_authorization_fingerprint") != prepared_curve_authorization.get(
        "fingerprint"
    ):
        raise G16CounterfactualPublicationError(
            "prepared curve authorization differs from counterfactual lineage"
        )
    candidate_ids, evidence, used = _candidate_lineage(counterfactual)
    try:
        prepared_lock = build_prepared_curve_lock(
            curve_authorization=prepared_curve_authorization,
            **dict(prepared_lock_kwargs),
        )
        validate_prepared_curve_lock(prepared_lock)
    except G16PreparedPublicationError as error:
        raise G16CounterfactualPublicationError(f"prepared curve lock invalid: {error}") from error
    if prepared_lock.get("prepared_curve_authorization_fingerprint") != counterfactual.get(
        "prepared_curve_authorization_fingerprint"
    ):
        raise G16CounterfactualPublicationError("prepared curve lock bypasses counterfactual authorization")
    if list(prepared_lock.get("registered_candidate_ids") or []) != candidate_ids:
        raise G16CounterfactualPublicationError("prepared curve lock candidate registry differs from lineage")
    if list(prepared_lock.get("used_candidate_ids") or []) != used:
        raise G16CounterfactualPublicationError("prepared curve lock used candidates differ from lineage")

    stand_down_days = sorted(
        {str(day) for day in counterfactual.get("stand_down_days") or []}
        | {str(day) for day in prepared_lock.get("stand_down_days") or []}
    )
    result = {
        "schema": LOCK_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": LOCK_STATUS,
        "authority": LOCK_AUTHORITY,
        "counterfactual_curve_authorization_fingerprint": counterfactual["fingerprint"],
        "counterfactual_causal_authorization_fingerprint": counterfactual.get(
            "counterfactual_causal_authorization_fingerprint"
        ),
        "counterfactual_lineage_gate_fingerprint": counterfactual.get(
            "counterfactual_lineage_gate_fingerprint"
        ),
        "counterfactual_lesson_gate_fingerprint": counterfactual.get(
            "counterfactual_lesson_gate_fingerprint"
        ),
        "counterfactual_attribution_fingerprint": counterfactual.get(
            "counterfactual_attribution_fingerprint"
        ),
        "g15_publication_fingerprint": counterfactual.get("g15_publication_fingerprint"),
        "g15_adjudication_fingerprint": counterfactual.get("g15_adjudication_fingerprint"),
        "g16_registry_fingerprint": counterfactual.get("g16_registry_fingerprint"),
        "prepared_curve_authorization_fingerprint": prepared_lock.get(
            "prepared_curve_authorization_fingerprint"
        ),
        "prepared_curve_lock_fingerprint": prepared_lock.get("lock_fingerprint"),
        "replay_fingerprint": prepared_lock.get("replay_fingerprint"),
        "manifest_fingerprint": prepared_lock.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared_lock.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": prepared_lock.get("blind_prior_fingerprint"),
        "plan_fingerprint": prepared_lock.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared_lock.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": prepared_lock.get("posterior_stream_fingerprint"),
        "blind_forecast_sha256": prepared_lock.get("blind_forecast_sha256"),
        "refined_curve_fingerprint": prepared_lock.get("refined_curve_fingerprint"),
        "refined_forecast_sha256": prepared_lock.get("refined_forecast_sha256"),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": used,
        "stand_down_days": stand_down_days,
        "prepared_curve_lock": copy.deepcopy(prepared_lock),
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "fixed_scoring_may_begin": True,
        "curve_locked_before_fixed_scoring": True,
        "counterfactual_lineage_locked_before_fixed_scoring": True,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "curve_mutation_authorized": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": LOCK_NEXT_STAGE,
    }
    result["lock_fingerprint"] = _fp(result)
    current = (
        counterfactual_curve_authorization,
        counterfactual_causal_authorization,
        counterfactual_kwargs,
        curve_kwargs,
        prepared_curve_authorization,
        prepared_lock_kwargs,
    )
    if current != originals:
        raise G16CounterfactualPublicationError("counterfactual curve locking mutated a source")
    return result


def build_curve_lock(**kwargs: Any) -> dict[str, Any]:
    result = _build_curve_lock(**kwargs)
    validate_curve_lock(result, **kwargs)
    return result


def validate_curve_lock(lock: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = _verify_fingerprint(lock, "lock_fingerprint", label="counterfactual curve lock")
    if candidate.get("schema") != LOCK_SCHEMA or candidate.get("authority") != LOCK_AUTHORITY:
        raise G16CounterfactualPublicationError("counterfactual curve lock schema/authority mismatch")
    if candidate.get("status") != LOCK_STATUS or candidate.get("next_permitted_stage") != LOCK_NEXT_STAGE:
        raise G16CounterfactualPublicationError("counterfactual curve lock is not ready")
    _require_false(
        candidate,
        (
            "actual_g16_outcomes_used",
            "random_shuffle_used",
            "curve_mutation_authorized",
            "may_change_g16_blind_prior",
            "may_change_g16_blind_forecast",
            "may_change_posterior",
            "may_select_lessons_from_g16_outcomes",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ),
        label="counterfactual curve lock",
    )
    for field in (
        "actual_g15_outcomes_used",
        "fixed_scoring_may_begin",
        "curve_locked_before_fixed_scoring",
        "counterfactual_lineage_locked_before_fixed_scoring",
        "one_signal_authority_preserved",
        "blind_forecasts_immutable",
    ):
        if candidate.get(field) is not True:
            raise G16CounterfactualPublicationError(f"counterfactual curve lock: {field} must be true")
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16CounterfactualPublicationError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16CounterfactualPublicationError("brokerage contract must remain tastytrade")
    validate_prepared_curve_lock(dict(candidate.get("prepared_curve_lock") or {}))
    rebuilt = _build_curve_lock(**kwargs)
    rebuilt.pop("lock_fingerprint", None)
    candidate.pop("lock_fingerprint", None)
    if candidate != rebuilt:
        raise G16CounterfactualPublicationError(
            "counterfactual curve lock differs from deterministic reconstruction"
        )


def _build_completion(
    *,
    counterfactual_curve_lock: Mapping[str, Any],
    lock_kwargs: Mapping[str, Any],
    prepared_completion_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy((counterfactual_curve_lock, lock_kwargs, prepared_completion_kwargs))
    validate_curve_lock(counterfactual_curve_lock, **dict(lock_kwargs))
    lock = copy.deepcopy(dict(counterfactual_curve_lock))
    inner_lock = copy.deepcopy(dict(lock.get("prepared_curve_lock") or {}))
    try:
        prepared = build_prepared_completion(
            curve_lock=inner_lock,
            **dict(prepared_completion_kwargs),
        )
        validate_prepared_completion(prepared)
    except G16PreparedPublicationError as error:
        raise G16CounterfactualPublicationError(
            f"prepared publication completion invalid: {error}"
        ) from error
    if prepared.get("curve_lock_fingerprint") != lock.get("prepared_curve_lock_fingerprint"):
        raise G16CounterfactualPublicationError("prepared publication bypasses lineage-bound curve lock")
    if prepared.get("prepared_curve_authorization_fingerprint") != lock.get(
        "prepared_curve_authorization_fingerprint"
    ):
        raise G16CounterfactualPublicationError("prepared publication changed curve authorization")
    if prepared.get("g15_lesson_adjudication_fingerprint") != lock.get(
        "g15_adjudication_fingerprint"
    ):
        raise G16CounterfactualPublicationError("prepared publication changed G15 adjudication lineage")
    if list(prepared.get("registered_candidate_ids") or []) != list(lock.get("candidate_ids") or []):
        raise G16CounterfactualPublicationError("prepared publication changed candidate registry")
    if list(prepared.get("used_candidate_ids") or []) != list(
        lock.get("candidate_ids_used_by_curve") or []
    ):
        raise G16CounterfactualPublicationError("prepared publication changed curve-used candidates")

    stand_down_days = sorted(
        {str(day) for day in lock.get("stand_down_days") or []}
        | {str(day) for day in prepared.get("stand_down_days") or []}
    )
    status = READY_WITH_STAND_DOWNS if stand_down_days else READY
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": status,
        "authority": AUTHORITY,
        "counterfactual_curve_lock_fingerprint": lock["lock_fingerprint"],
        "counterfactual_curve_authorization_fingerprint": lock[
            "counterfactual_curve_authorization_fingerprint"
        ],
        "counterfactual_causal_authorization_fingerprint": lock.get(
            "counterfactual_causal_authorization_fingerprint"
        ),
        "counterfactual_lineage_gate_fingerprint": lock.get(
            "counterfactual_lineage_gate_fingerprint"
        ),
        "counterfactual_lesson_gate_fingerprint": lock.get(
            "counterfactual_lesson_gate_fingerprint"
        ),
        "counterfactual_attribution_fingerprint": lock.get(
            "counterfactual_attribution_fingerprint"
        ),
        "g15_publication_fingerprint": lock.get("g15_publication_fingerprint"),
        "g15_adjudication_fingerprint": lock.get("g15_adjudication_fingerprint"),
        "g16_registry_fingerprint": lock.get("g16_registry_fingerprint"),
        "prepared_publication_completion_fingerprint": prepared.get("completion_fingerprint"),
        "prepared_curve_lock_fingerprint": prepared.get("curve_lock_fingerprint"),
        "prepared_curve_authorization_fingerprint": prepared.get(
            "prepared_curve_authorization_fingerprint"
        ),
        "replay_fingerprint": prepared.get("replay_fingerprint"),
        "manifest_fingerprint": prepared.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": prepared.get("blind_prior_fingerprint"),
        "plan_fingerprint": prepared.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared.get("authorization_stream_fingerprint"),
        "posterior_stream_fingerprint": prepared.get("posterior_stream_fingerprint"),
        "blind_forecast_sha256": prepared.get("blind_forecast_sha256"),
        "refined_forecast_sha256": prepared.get("refined_forecast_sha256"),
        "refined_curve_fingerprint": prepared.get("refined_curve_fingerprint"),
        "candidate_ids": list(lock.get("candidate_ids") or []),
        "candidate_evidence_fingerprints": copy.deepcopy(
            dict(lock.get("candidate_evidence_fingerprints") or {})
        ),
        "candidate_ids_used_by_curve": list(lock.get("candidate_ids_used_by_curve") or []),
        "actual_sha256": prepared.get("actual_sha256"),
        "blind_score_fingerprint": prepared.get("blind_score_fingerprint"),
        "refined_score_fingerprint": prepared.get("refined_score_fingerprint"),
        "comparison_fingerprint": prepared.get("comparison_fingerprint"),
        "chronological_validation_fingerprint": prepared.get(
            "chronological_validation_fingerprint"
        ),
        "stand_down_days": stand_down_days,
        "renders": copy.deepcopy(dict(prepared.get("renders") or {})),
        "post_g16_shadow_registry": copy.deepcopy(
            dict(prepared.get("post_g16_shadow_registry") or {})
        ),
        "counterfactual_lineage_preserved_through_fixed_scoring": True,
        "curve_locked_before_fixed_scoring": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": True,
        "outcome_scoring_complete": True,
        "chronological_validation_complete": True,
        "continuous_rt_renders_complete": True,
        "g16_consumed_as_forward_holdout": True,
        "g16_reusable_as_untouched_holdout": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_any_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
    }
    result["completion_fingerprint"] = _fp(result)
    if (counterfactual_curve_lock, lock_kwargs, prepared_completion_kwargs) != originals:
        raise G16CounterfactualPublicationError("counterfactual publication mutated a source")
    return result


def build_completion(**kwargs: Any) -> dict[str, Any]:
    result = _build_completion(**kwargs)
    validate_completion(result, **kwargs)
    return result


def validate_completion(completion: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = _verify_fingerprint(
        completion, "completion_fingerprint", label="counterfactual publication completion"
    )
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16CounterfactualPublicationError(
            "counterfactual publication schema/authority mismatch"
        )
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16CounterfactualPublicationError("counterfactual publication is not complete")
    _require_false(
        candidate,
        (
            "g16_reusable_as_untouched_holdout",
            "random_shuffle_used",
            "may_change_any_blind_prior",
            "may_change_blind_forecast",
            "may_change_posterior",
            "may_select_lessons_from_g16_outcomes",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
            "options_implementation_authorized",
        ),
        label="counterfactual publication completion",
    )
    for field in (
        "counterfactual_lineage_preserved_through_fixed_scoring",
        "curve_locked_before_fixed_scoring",
        "actual_g15_outcomes_used",
        "actual_g16_outcomes_used",
        "outcome_scoring_complete",
        "chronological_validation_complete",
        "continuous_rt_renders_complete",
        "g16_consumed_as_forward_holdout",
        "one_signal_authority_preserved",
        "blind_forecasts_immutable",
    ):
        if candidate.get(field) is not True:
            raise G16CounterfactualPublicationError(
                f"counterfactual publication completion: {field} must be true"
            )
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16CounterfactualPublicationError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16CounterfactualPublicationError("brokerage contract must remain tastytrade")
    stand_downs = sorted({str(day) for day in candidate.get("stand_down_days") or []})
    if stand_downs != list(candidate.get("stand_down_days") or []):
        raise G16CounterfactualPublicationError("stand-down days are not canonical")
    expected_status = READY_WITH_STAND_DOWNS if stand_downs else READY
    if candidate.get("status") != expected_status:
        raise G16CounterfactualPublicationError("stand-down status mismatch")
    rebuilt = _build_completion(**kwargs)
    rebuilt.pop("completion_fingerprint", None)
    candidate.pop("completion_fingerprint", None)
    if candidate != rebuilt:
        raise G16CounterfactualPublicationError(
            "counterfactual publication differs from deterministic reconstruction"
        )
