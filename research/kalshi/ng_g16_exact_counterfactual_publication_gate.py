#!/usr/bin/env python3
"""Lock and publish G16 only through exact corpus and lesson provenance.

The existing counterfactual publication gate locks the deterministic refined G16
curve before fixed scoring and preserves G15 lesson lineage.  This outer gate
makes the newer exact curve authorization mandatory at that boundary, so the
lock and scored publication also carry the verified replay-byte binding and exact
common L1/MBO event-window contract.

The lock is pre-outcome.  The completion is post-outcome but cannot mutate blind
forecasts, posterior state, or ``ng_brain.json``; it never grants execution or
options authority, keeps CME event contracts SHADOW, and keeps tastytrade as the
brokerage contract.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from ng_g16_exact_counterfactual_curve_authorization import (
    AUTHORITY as EXACT_CURVE_AUTHORITY,
    G16ExactCounterfactualCurveAuthorizationError,
    NEXT_STAGE as EXACT_CURVE_NEXT_STAGE,
    SCHEMA as EXACT_CURVE_SCHEMA,
    STATUS_READY as EXACT_CURVE_READY,
    STATUS_STAND_DOWNS as EXACT_CURVE_STAND_DOWNS,
    validate_authorization as validate_exact_curve_authorization,
)
from ng_g16_counterfactual_publication_gate import (
    G16CounterfactualPublicationError,
    build_completion as build_legacy_completion,
    build_curve_lock as build_legacy_curve_lock,
    validate_completion as validate_legacy_completion,
    validate_curve_lock as validate_legacy_curve_lock,
)

LOCK_SCHEMA = "ng_g16_exact_counterfactual_curve_lock.v1"
LOCK_AUTHORITY = "EXACT_G16_CORPUS_WINDOWS_AND_G15_LESSONS_LOCKED_BEFORE_SCORING"
LOCK_STATUS = "EXACT_G16_CORPUS_COUNTERFACTUAL_CURVE_LOCKED"
LOCK_NEXT_STAGE = "FIXED_G16_BLIND_REFINED_SCORING_WITH_EXACT_CORPUS_LINEAGE"

SCHEMA = "ng_g16_exact_counterfactual_publication_completion.v1"
AUTHORITY = "EXACT_G16_CORPUS_AND_G15_LESSON_LINEAGE_THROUGH_SCORED_PUBLICATION"
READY = "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = (
    "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
)
EXPECTED_REPLAY_SOURCE_COUNT = 22


class G16ExactCounterfactualPublicationError(ValueError):
    """Raised when G16 locking or publication bypasses exact corpus provenance."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _verified(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(candidate):
        raise G16ExactCounterfactualPublicationError(f"{label}: {field} mismatch")
    candidate[field] = observed
    return candidate


def _require_false(value: Mapping[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if value.get(field) is not False:
            raise G16ExactCounterfactualPublicationError(
                f"{label}: {field} must remain false"
            )


def _authority_wall(value: Mapping[str, Any], *, post_outcome: bool) -> None:
    _require_false(
        value,
        (
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
        label="exact G16 publication contract",
    )
    if value.get("actual_g16_outcomes_used") is not post_outcome:
        raise G16ExactCounterfactualPublicationError(
            "actual_g16_outcomes_used does not match the lock/publication boundary"
        )
    for field in (
        "one_signal_authority_preserved",
        "blind_forecasts_immutable",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ):
        if value.get(field) is not True:
            raise G16ExactCounterfactualPublicationError(f"{field} must remain true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactCounterfactualPublicationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactCounterfactualPublicationError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _validate_exact_curve(
    authorization: Mapping[str, Any],
    *,
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validate_exact_curve_authorization(
            authorization,
            exact_causal_authorization=exact_causal_authorization,
            counterfactual_curve_authorization=counterfactual_curve_authorization,
            curve_kwargs=curve_kwargs,
        )
    except G16ExactCounterfactualCurveAuthorizationError as error:
        raise G16ExactCounterfactualPublicationError(
            f"exact counterfactual curve authorization invalid: {error}"
        ) from error
    value = _verified(authorization, "fingerprint", label="exact curve authorization")
    if value.get("schema") != EXACT_CURVE_SCHEMA or value.get("authority") != EXACT_CURVE_AUTHORITY:
        raise G16ExactCounterfactualPublicationError(
            "exact curve authorization schema/authority mismatch"
        )
    if value.get("status") not in {EXACT_CURVE_READY, EXACT_CURVE_STAND_DOWNS}:
        raise G16ExactCounterfactualPublicationError(
            "exact curve authorization is not ready"
        )
    if value.get("next_permitted_stage") != EXACT_CURVE_NEXT_STAGE:
        raise G16ExactCounterfactualPublicationError(
            "exact curve authorization does not permit the pre-scoring lock"
        )
    if value.get("bound_replay_source_count") != EXPECTED_REPLAY_SOURCE_COUNT:
        raise G16ExactCounterfactualPublicationError(
            "exactly 22 G16 replay lanes must remain bound at lock time"
        )
    _authority_wall(value, post_outcome=False)
    return value


def _candidate_lineage(value: Mapping[str, Any]) -> tuple[list[str], dict[str, str], list[str]]:
    ids = [str(item) for item in value.get("candidate_ids") or []]
    if not ids or ids != sorted(ids) or len(ids) != len(set(ids)):
        raise G16ExactCounterfactualPublicationError(
            "candidate ids must be non-empty, unique, and sorted"
        )
    evidence = {
        str(key): str(item)
        for key, item in dict(value.get("candidate_evidence_fingerprints") or {}).items()
    }
    if sorted(evidence) != ids or any(not item for item in evidence.values()):
        raise G16ExactCounterfactualPublicationError(
            "candidate evidence map is incomplete"
        )
    used = [str(item) for item in value.get("candidate_ids_used_by_curve") or []]
    if used != sorted(set(used)) or not set(used).issubset(set(ids)):
        raise G16ExactCounterfactualPublicationError(
            "curve-used candidates bypass the registered lineage"
        )
    return ids, evidence, used


def _build_curve_lock(
    *,
    exact_curve_authorization: Mapping[str, Any],
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
    legacy_lock_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            exact_curve_authorization,
            exact_causal_authorization,
            counterfactual_curve_authorization,
            curve_kwargs,
            legacy_lock_kwargs,
        )
    )
    exact = _validate_exact_curve(
        exact_curve_authorization,
        exact_causal_authorization=exact_causal_authorization,
        counterfactual_curve_authorization=counterfactual_curve_authorization,
        curve_kwargs=curve_kwargs,
    )
    try:
        legacy_lock = build_legacy_curve_lock(**dict(legacy_lock_kwargs))
        validate_legacy_curve_lock(legacy_lock, **dict(legacy_lock_kwargs))
    except G16CounterfactualPublicationError as error:
        raise G16ExactCounterfactualPublicationError(
            f"counterfactual curve lock invalid: {error}"
        ) from error

    ids, evidence, used = _candidate_lineage(exact)
    cross_fields = (
        "counterfactual_curve_authorization_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "replay_fingerprint",
        "refined_curve_fingerprint",
    )
    for field in cross_fields:
        if legacy_lock.get(field) != exact.get(field):
            raise G16ExactCounterfactualPublicationError(
                f"legacy curve lock {field} bypasses exact curve authorization"
            )
    if list(legacy_lock.get("candidate_ids") or []) != ids:
        raise G16ExactCounterfactualPublicationError(
            "legacy curve lock candidate registry differs from exact authorization"
        )
    if dict(legacy_lock.get("candidate_evidence_fingerprints") or {}) != evidence:
        raise G16ExactCounterfactualPublicationError(
            "legacy curve lock candidate evidence differs from exact authorization"
        )
    if list(legacy_lock.get("candidate_ids_used_by_curve") or []) != used:
        raise G16ExactCounterfactualPublicationError(
            "legacy curve lock used candidates differ from exact authorization"
        )

    stand_down_days = sorted(
        {str(day) for day in exact.get("stand_down_days") or []}
        | {str(day) for day in legacy_lock.get("stand_down_days") or []}
    )
    result: dict[str, Any] = {
        "schema": LOCK_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": LOCK_STATUS,
        "authority": LOCK_AUTHORITY,
        "exact_counterfactual_curve_authorization_fingerprint": exact["fingerprint"],
        "exact_counterfactual_causal_authorization_fingerprint": exact.get(
            "exact_counterfactual_causal_authorization_fingerprint"
        ),
        "counterfactual_curve_authorization_fingerprint": exact.get(
            "counterfactual_curve_authorization_fingerprint"
        ),
        "counterfactual_causal_authorization_fingerprint": exact.get(
            "counterfactual_causal_authorization_fingerprint"
        ),
        "exact_partition_replay_authorization_fingerprint": exact.get(
            "exact_partition_replay_authorization_fingerprint"
        ),
        "exact_partition_gate_fingerprint": exact.get("exact_partition_gate_fingerprint"),
        "source_binding_fingerprint": exact.get("source_binding_fingerprint"),
        "window_contract_fingerprint": exact.get("window_contract_fingerprint"),
        "prepared_curve_authorization_fingerprint": exact.get(
            "prepared_curve_authorization_fingerprint"
        ),
        "prepared_causal_authorization_fingerprint": exact.get(
            "prepared_causal_authorization_fingerprint"
        ),
        "prepared_curve_lock_fingerprint": legacy_lock.get(
            "prepared_curve_lock_fingerprint"
        ),
        "legacy_counterfactual_curve_lock_fingerprint": legacy_lock.get(
            "lock_fingerprint"
        ),
        "replay_fingerprint": exact.get("replay_fingerprint"),
        "manifest_fingerprint": exact.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": exact.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": exact.get("blind_prior_fingerprint"),
        "refined_curve_fingerprint": exact.get("refined_curve_fingerprint"),
        "candidate_count": len(ids),
        "candidate_ids": ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": used,
        "bound_replay_source_count": EXPECTED_REPLAY_SOURCE_COUNT,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "stand_down_days": stand_down_days,
        "counterfactual_curve_lock": copy.deepcopy(legacy_lock),
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "fixed_scoring_may_begin": True,
        "curve_locked_before_fixed_scoring": True,
        "exact_corpus_provenance_locked_before_fixed_scoring": True,
        "counterfactual_lineage_locked_before_fixed_scoring": True,
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
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
        "next_permitted_stage": LOCK_NEXT_STAGE,
    }
    result["lock_fingerprint"] = _fp(result)
    if (
        exact_curve_authorization,
        exact_causal_authorization,
        counterfactual_curve_authorization,
        curve_kwargs,
        legacy_lock_kwargs,
    ) != originals:
        raise G16ExactCounterfactualPublicationError(
            "exact curve locking mutated an upstream artifact"
        )
    return result


def build_curve_lock(**kwargs: Any) -> dict[str, Any]:
    result = _build_curve_lock(**kwargs)
    validate_curve_lock(result, **kwargs)
    return result


def validate_curve_lock(lock: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = _verified(lock, "lock_fingerprint", label="exact curve lock")
    if candidate.get("schema") != LOCK_SCHEMA or candidate.get("authority") != LOCK_AUTHORITY:
        raise G16ExactCounterfactualPublicationError(
            "exact curve lock schema/authority mismatch"
        )
    if candidate.get("status") != LOCK_STATUS or candidate.get("next_permitted_stage") != LOCK_NEXT_STAGE:
        raise G16ExactCounterfactualPublicationError("exact curve lock is not ready")
    for field in (
        "fixed_scoring_may_begin",
        "curve_locked_before_fixed_scoring",
        "exact_corpus_provenance_locked_before_fixed_scoring",
        "counterfactual_lineage_locked_before_fixed_scoring",
    ):
        if candidate.get(field) is not True:
            raise G16ExactCounterfactualPublicationError(f"{field} must remain true")
    _authority_wall(candidate, post_outcome=False)
    try:
        validate_legacy_curve_lock(
            dict(candidate.get("counterfactual_curve_lock") or {}),
            **dict(kwargs.get("legacy_lock_kwargs") or {}),
        )
    except G16CounterfactualPublicationError as error:
        raise G16ExactCounterfactualPublicationError(
            f"embedded counterfactual curve lock invalid: {error}"
        ) from error
    rebuilt = _build_curve_lock(**kwargs)
    rebuilt.pop("lock_fingerprint", None)
    candidate.pop("lock_fingerprint", None)
    if candidate != rebuilt:
        raise G16ExactCounterfactualPublicationError(
            "exact curve lock differs from deterministic reconstruction"
        )


def _build_completion(
    *,
    exact_curve_lock: Mapping[str, Any],
    exact_lock_kwargs: Mapping[str, Any],
    legacy_completion_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (exact_curve_lock, exact_lock_kwargs, legacy_completion_kwargs)
    )
    validate_curve_lock(exact_curve_lock, **dict(exact_lock_kwargs))
    lock = copy.deepcopy(dict(exact_curve_lock))
    inner = copy.deepcopy(dict(lock.get("counterfactual_curve_lock") or {}))
    try:
        legacy = build_legacy_completion(
            counterfactual_curve_lock=inner,
            **dict(legacy_completion_kwargs),
        )
        validate_legacy_completion(
            legacy,
            counterfactual_curve_lock=inner,
            **dict(legacy_completion_kwargs),
        )
    except G16CounterfactualPublicationError as error:
        raise G16ExactCounterfactualPublicationError(
            f"counterfactual publication completion invalid: {error}"
        ) from error
    if legacy.get("counterfactual_curve_lock_fingerprint") != inner.get(
        "lock_fingerprint"
    ):
        raise G16ExactCounterfactualPublicationError(
            "scored publication bypasses the embedded counterfactual curve lock"
        )
    for field in (
        "counterfactual_curve_authorization_fingerprint",
        "counterfactual_causal_authorization_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "replay_fingerprint",
        "refined_curve_fingerprint",
    ):
        if legacy.get(field) != lock.get(field):
            raise G16ExactCounterfactualPublicationError(
                f"scored publication changed {field} after exact locking"
            )

    stand_down_days = sorted(
        {str(day) for day in lock.get("stand_down_days") or []}
        | {str(day) for day in legacy.get("stand_down_days") or []}
    )
    status = READY_WITH_STAND_DOWNS if stand_down_days else READY
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": status,
        "authority": AUTHORITY,
        "counterfactual_curve_lock_fingerprint": lock["lock_fingerprint"],
        "exact_counterfactual_curve_lock_fingerprint": lock["lock_fingerprint"],
        "exact_counterfactual_curve_authorization_fingerprint": lock.get(
            "exact_counterfactual_curve_authorization_fingerprint"
        ),
        "exact_counterfactual_causal_authorization_fingerprint": lock.get(
            "exact_counterfactual_causal_authorization_fingerprint"
        ),
        "counterfactual_curve_authorization_fingerprint": lock.get(
            "counterfactual_curve_authorization_fingerprint"
        ),
        "counterfactual_causal_authorization_fingerprint": lock.get(
            "counterfactual_causal_authorization_fingerprint"
        ),
        "exact_partition_replay_authorization_fingerprint": lock.get(
            "exact_partition_replay_authorization_fingerprint"
        ),
        "exact_partition_gate_fingerprint": lock.get("exact_partition_gate_fingerprint"),
        "source_binding_fingerprint": lock.get("source_binding_fingerprint"),
        "window_contract_fingerprint": lock.get("window_contract_fingerprint"),
        "prepared_curve_authorization_fingerprint": lock.get(
            "prepared_curve_authorization_fingerprint"
        ),
        "prepared_curve_lock_fingerprint": legacy.get(
            "prepared_curve_lock_fingerprint"
        ),
        "prepared_publication_completion_fingerprint": legacy.get(
            "prepared_publication_completion_fingerprint"
        ),
        "legacy_counterfactual_publication_fingerprint": legacy.get(
            "completion_fingerprint"
        ),
        "replay_fingerprint": lock.get("replay_fingerprint"),
        "manifest_fingerprint": lock.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": lock.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": lock.get("blind_prior_fingerprint"),
        "refined_curve_fingerprint": lock.get("refined_curve_fingerprint"),
        "candidate_count": lock.get("candidate_count"),
        "candidate_ids": list(lock.get("candidate_ids") or []),
        "candidate_evidence_fingerprints": copy.deepcopy(
            dict(lock.get("candidate_evidence_fingerprints") or {})
        ),
        "candidate_ids_used_by_curve": list(
            lock.get("candidate_ids_used_by_curve") or []
        ),
        "bound_replay_source_count": EXPECTED_REPLAY_SOURCE_COUNT,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "actual_sha256": legacy.get("actual_sha256"),
        "blind_score_fingerprint": legacy.get("blind_score_fingerprint"),
        "refined_score_fingerprint": legacy.get("refined_score_fingerprint"),
        "comparison_fingerprint": legacy.get("comparison_fingerprint"),
        "chronological_validation_fingerprint": legacy.get(
            "chronological_validation_fingerprint"
        ),
        "renders": copy.deepcopy(dict(legacy.get("renders") or {})),
        "stand_down_days": stand_down_days,
        "exact_corpus_provenance_preserved_through_fixed_scoring": True,
        "counterfactual_lineage_preserved_through_fixed_scoring": True,
        "curve_locked_before_fixed_scoring": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": True,
        "outcome_scoring_complete": True,
        "chronological_validation_complete": True,
        "continuous_rt_renders_complete": True,
        "g16_consumed_as_forward_holdout": True,
        "g16_reusable_as_untouched_holdout": False,
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
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
    }
    result["completion_fingerprint"] = _fp(result)
    if (exact_curve_lock, exact_lock_kwargs, legacy_completion_kwargs) != originals:
        raise G16ExactCounterfactualPublicationError(
            "exact publication mutated an upstream artifact"
        )
    return result


def build_completion(**kwargs: Any) -> dict[str, Any]:
    result = _build_completion(**kwargs)
    validate_completion(result, **kwargs)
    return result


def validate_completion(completion: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = _verified(
        completion, "completion_fingerprint", label="exact publication completion"
    )
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16ExactCounterfactualPublicationError(
            "exact publication schema/authority mismatch"
        )
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16ExactCounterfactualPublicationError(
            "exact publication is not complete"
        )
    for field in (
        "exact_corpus_provenance_preserved_through_fixed_scoring",
        "counterfactual_lineage_preserved_through_fixed_scoring",
        "curve_locked_before_fixed_scoring",
        "outcome_scoring_complete",
        "chronological_validation_complete",
        "continuous_rt_renders_complete",
        "g16_consumed_as_forward_holdout",
    ):
        if candidate.get(field) is not True:
            raise G16ExactCounterfactualPublicationError(f"{field} must remain true")
    if candidate.get("g16_reusable_as_untouched_holdout") is not False:
        raise G16ExactCounterfactualPublicationError(
            "G16 cannot remain an untouched holdout after fixed scoring"
        )
    _authority_wall(candidate, post_outcome=True)
    stand_downs = sorted({str(day) for day in candidate.get("stand_down_days") or []})
    expected_status = READY_WITH_STAND_DOWNS if stand_downs else READY
    if stand_downs != list(candidate.get("stand_down_days") or []) or candidate.get(
        "status"
    ) != expected_status:
        raise G16ExactCounterfactualPublicationError(
            "stand-down days or completion status are not canonical"
        )
    rebuilt = _build_completion(**kwargs)
    rebuilt.pop("completion_fingerprint", None)
    candidate.pop("completion_fingerprint", None)
    if candidate != rebuilt:
        raise G16ExactCounterfactualPublicationError(
            "exact publication differs from deterministic reconstruction"
        )


def selftest() -> int:
    print("[ng_g16_exact_counterfactual_publication_gate] import/selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
