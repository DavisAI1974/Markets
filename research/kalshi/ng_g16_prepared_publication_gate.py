#!/usr/bin/env python3
"""Require the exact prepared G16 curve lock before outcome scoring/publication.

This module is the strict outer gate around ``ng_g16_exact_publication_gate``.
It first validates and locks the deterministic, outcome-blind refined curve that
is bound to the 23-source prepared NGK26 replay. Only after that lock succeeds
may the fixed G16 actual substrate, blind/refined scorecards, chronological
forward-holdout validation, and canonical renders be accepted.

The gate never changes a blind prior, blind forecast, posterior, lesson
registry, or ``ng_brain.json``. Random shuffling remains forbidden, CME event
contracts remain SHADOW, tastytrade remains the brokerage contract, and the
options lane remains unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g16_exact_publication_gate import (
    G16ExactPublicationError,
    build_completion as build_exact_publication_completion,
    validate_completion as validate_exact_publication_completion,
)
from ng_g16_prepared_curve_authorization import (
    AUTHORITY as CURVE_AUTHORITY,
    G16PreparedCurveAuthorizationError,
    NEXT_STAGE as CURVE_NEXT_STAGE,
    SCHEMA as CURVE_SCHEMA,
    STATUS_READY as CURVE_READY,
    STATUS_STAND_DOWNS as CURVE_STAND_DOWNS,
    validate_curve_authorization,
)

LOCK_SCHEMA = "ng_g16_prepared_curve_lock.v1"
LOCK_AUTHORITY = "EXACT_G16_PREPARED_CURVE_LOCK_BEFORE_FIXED_SCORING"
LOCK_STATUS = "EXACT_G16_PREPARED_CURVE_LOCKED"
SCHEMA = "ng_g16_prepared_publication_completion.v1"
AUTHORITY = "EXACT_G16_PREPARED_CURVE_TO_SCORED_PUBLICATION_ONLY"
READY = "EXACT_G16_PREPARED_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = "EXACT_G16_PREPARED_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"


class G16PreparedPublicationError(ValueError):
    """Raised when scoring or publication bypasses the prepared-curve lock."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(candidate):
        raise G16PreparedPublicationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _require_false(value: Mapping[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if value.get(field) is not False:
            raise G16PreparedPublicationError(f"{label}: {field} must remain false")


def _decode_exact_json(data: bytes, expected: Mapping[str, Any], *, label: str) -> None:
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G16PreparedPublicationError(f"{label}: file bytes are not valid JSON") from error
    if decoded != dict(expected):
        raise G16PreparedPublicationError(f"{label}: file bytes differ from supplied artifact")


def _validate_curve_authority(
    curve_authorization: Mapping[str, Any],
    *,
    prepared_causal_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
) -> dict[str, Any]:
    try:
        validate_curve_authorization(
            curve_authorization,
            prepared_causal_authorization=prepared_causal_authorization,
            prepared_gate=prepared_gate,
            prepared_index=prepared_index,
            manifest=manifest,
            replay=replay,
            blind_prior=blind_prior,
            causal_artifacts=causal_artifacts,
            blind_forecast=blind_forecast,
            blind_safe_state=blind_safe_state,
            registry_source=registry_source,
            shadow_plan=shadow_plan,
            posterior_stream=posterior_stream,
            refined_curve=refined_curve,
            blind_file_bytes=blind_file_bytes,
        )
    except G16PreparedCurveAuthorizationError as error:
        raise G16PreparedPublicationError(
            f"prepared curve authorization invalid: {error}"
        ) from error
    value = _verify_fingerprint(curve_authorization, "fingerprint", label="prepared curve authorization")
    if value.get("schema") != CURVE_SCHEMA or value.get("authority") != CURVE_AUTHORITY:
        raise G16PreparedPublicationError("prepared curve authorization schema/authority mismatch")
    if value.get("status") not in {CURVE_READY, CURVE_STAND_DOWNS}:
        raise G16PreparedPublicationError("prepared curve authorization is not ready")
    if value.get("next_permitted_stage") != CURVE_NEXT_STAGE:
        raise G16PreparedPublicationError("prepared curve authorization does not permit curve locking")
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
        label="prepared curve authorization",
    )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16PreparedPublicationError("prepared curve authorization must preserve one signal authority")
    if value.get("blind_forecast_immutable") is not True:
        raise G16PreparedPublicationError("prepared curve authorization must preserve the blind forecast")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedPublicationError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedPublicationError("brokerage contract must remain tastytrade")
    return value


def build_curve_lock(
    *,
    curve_authorization: Mapping[str, Any],
    prepared_causal_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
    refined_file_bytes: bytes,
) -> dict[str, Any]:
    """Lock the exact prepared, outcome-blind curve before any outcome access."""
    originals = copy.deepcopy(
        (
            curve_authorization,
            prepared_causal_authorization,
            prepared_gate,
            prepared_index,
            manifest,
            replay,
            blind_prior,
            causal_artifacts,
            blind_forecast,
            blind_safe_state,
            registry_source,
            shadow_plan,
            posterior_stream,
            refined_curve,
        )
    )
    value = _validate_curve_authority(
        curve_authorization,
        prepared_causal_authorization=prepared_causal_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    _decode_exact_json(blind_file_bytes, blind_forecast, label="blind forecast")
    _decode_exact_json(refined_file_bytes, refined_curve, label="refined forecast")
    if value.get("blind_forecast_sha256") != _sha256(blind_file_bytes):
        raise G16PreparedPublicationError("prepared curve authorization blind-file SHA-256 mismatch")
    if value.get("refined_curve_fingerprint") != refined_curve.get("artifact_fingerprint"):
        raise G16PreparedPublicationError("prepared curve authorization refined-curve mismatch")

    stand_down_days = sorted({str(day) for day in value.get("all_stand_down_days") or []})
    result = {
        "schema": LOCK_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": LOCK_STATUS,
        "authority": LOCK_AUTHORITY,
        "prepared_curve_authorization_fingerprint": value["fingerprint"],
        "prepared_causal_authorization_fingerprint": value[
            "prepared_causal_authorization_fingerprint"
        ],
        "prepared_replay_gate_fingerprint": value["prepared_replay_gate_fingerprint"],
        "replay_fingerprint": value["replay_fingerprint"],
        "manifest_fingerprint": value["manifest_fingerprint"],
        "prepared_corpus_fingerprint": value["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": value["blind_prior_fingerprint"],
        "plan_fingerprint": value["plan_fingerprint"],
        "authorization_stream_fingerprint": value["authorization_stream_fingerprint"],
        "posterior_stream_fingerprint": value["posterior_stream_fingerprint"],
        "blind_forecast_fingerprint": value["blind_forecast_fingerprint"],
        "blind_forecast_sha256": _sha256(blind_file_bytes),
        "refined_curve_fingerprint": value["refined_curve_fingerprint"],
        "refined_forecast_sha256": _sha256(refined_file_bytes),
        "transform_config": copy.deepcopy(dict(value.get("transform_config") or {})),
        "registered_candidate_ids": list(value.get("registered_candidate_ids") or []),
        "used_candidate_ids": list(value.get("used_candidate_ids") or []),
        "stand_down_days": stand_down_days,
        "actual_g16_outcomes_used": False,
        "fixed_scoring_may_begin": True,
        "curve_locked_before_fixed_scoring": True,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
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
        "next_permitted_stage": "FIXED_G16_BLIND_REFINED_SCORING_AND_PUBLICATION",
    }
    result["lock_fingerprint"] = _fp(result)
    if (
        curve_authorization,
        prepared_causal_authorization,
        prepared_gate,
        prepared_index,
        manifest,
        replay,
        blind_prior,
        causal_artifacts,
        blind_forecast,
        blind_safe_state,
        registry_source,
        shadow_plan,
        posterior_stream,
        refined_curve,
    ) != originals:
        raise G16PreparedPublicationError("curve locking mutated a source artifact")
    validate_curve_lock(result)
    return result


def validate_curve_lock(lock: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(lock, "lock_fingerprint", label="prepared curve lock")
    if value.get("schema") != LOCK_SCHEMA or value.get("status") != LOCK_STATUS:
        raise G16PreparedPublicationError("prepared curve lock is not ready")
    if value.get("authority") != LOCK_AUTHORITY:
        raise G16PreparedPublicationError("prepared curve lock authority mismatch")
    _require_false(
        value,
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
        label="prepared curve lock",
    )
    for field in (
        "fixed_scoring_may_begin",
        "curve_locked_before_fixed_scoring",
        "one_signal_authority_preserved",
        "blind_forecast_immutable",
    ):
        if value.get(field) is not True:
            raise G16PreparedPublicationError(f"prepared curve lock: {field} must be true")
    required = (
        "prepared_curve_authorization_fingerprint",
        "prepared_causal_authorization_fingerprint",
        "prepared_replay_gate_fingerprint",
        "replay_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "blind_prior_fingerprint",
        "plan_fingerprint",
        "authorization_stream_fingerprint",
        "posterior_stream_fingerprint",
        "blind_forecast_sha256",
        "refined_curve_fingerprint",
        "refined_forecast_sha256",
    )
    if any(not value.get(field) for field in required):
        raise G16PreparedPublicationError("prepared curve lock lacks required provenance")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedPublicationError("prepared curve lock must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedPublicationError("prepared curve lock must keep tastytrade brokerage")
    if value.get("next_permitted_stage") != "FIXED_G16_BLIND_REFINED_SCORING_AND_PUBLICATION":
        raise G16PreparedPublicationError("prepared curve lock next-stage mismatch")


def _validate_lock_against_sources(
    lock: Mapping[str, Any],
    *,
    curve_authorization: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
    refined_file_bytes: bytes,
) -> dict[str, Any]:
    validate_curve_lock(lock)
    value = copy.deepcopy(dict(lock))
    expected = {
        "prepared_curve_authorization_fingerprint": curve_authorization.get("fingerprint"),
        "prepared_causal_authorization_fingerprint": curve_authorization.get(
            "prepared_causal_authorization_fingerprint"
        ),
        "prepared_replay_gate_fingerprint": curve_authorization.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": curve_authorization.get("replay_fingerprint"),
        "manifest_fingerprint": curve_authorization.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": curve_authorization.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": curve_authorization.get("blind_prior_fingerprint"),
        "plan_fingerprint": curve_authorization.get("plan_fingerprint"),
        "authorization_stream_fingerprint": curve_authorization.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": curve_authorization.get("posterior_stream_fingerprint"),
        "blind_forecast_sha256": _sha256(blind_file_bytes),
        "refined_curve_fingerprint": refined_curve.get("artifact_fingerprint"),
        "refined_forecast_sha256": _sha256(refined_file_bytes),
        "stand_down_days": sorted(
            {str(day) for day in curve_authorization.get("all_stand_down_days") or []}
        ),
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise G16PreparedPublicationError(f"prepared curve lock {field} differs from sources")
    return value


def build_completion(
    *,
    curve_lock: Mapping[str, Any],
    curve_authorization: Mapping[str, Any],
    prepared_causal_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    actual: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    chronology: Mapping[str, Any],
    blind_rt: Mapping[str, Any],
    refined_rt: Mapping[str, Any],
    blind_file_bytes: bytes,
    refined_file_bytes: bytes,
    actual_file_bytes: bytes,
    blind_png: Path,
    refined_png: Path,
) -> dict[str, Any]:
    """Publish G16 only after the exact prepared curve has been locked."""
    originals = copy.deepcopy(
        (
            curve_lock,
            curve_authorization,
            prepared_causal_authorization,
            prepared_gate,
            prepared_index,
            manifest,
            replay,
            blind_prior,
            causal_artifacts,
            blind_forecast,
            blind_safe_state,
            registry_source,
            shadow_plan,
            posterior_stream,
            refined_curve,
            adjudication,
            actual,
            blind_score,
            refined_score,
            comparison,
            chronology,
            blind_rt,
            refined_rt,
        )
    )
    _validate_curve_authority(
        curve_authorization,
        prepared_causal_authorization=prepared_causal_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    lock = _validate_lock_against_sources(
        curve_lock,
        curve_authorization=curve_authorization,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
        refined_file_bytes=refined_file_bytes,
    )
    causal_completion = dict(causal_artifacts.get("completion") or {})
    if not causal_completion:
        raise G16PreparedPublicationError("causal artifacts lack the exact causal completion")
    try:
        exact = build_exact_publication_completion(
            causal_completion=causal_completion,
            adjudication=adjudication,
            plan=shadow_plan,
            posterior_stream=posterior_stream,
            blind=blind_forecast,
            refined=refined_curve,
            actual=actual,
            blind_score=blind_score,
            refined_score=refined_score,
            comparison=comparison,
            chronology=chronology,
            blind_rt=blind_rt,
            refined_rt=refined_rt,
            blind_bytes=blind_file_bytes,
            refined_bytes=refined_file_bytes,
            actual_bytes=actual_file_bytes,
            blind_png=blind_png,
            refined_png=refined_png,
        )
        validate_exact_publication_completion(exact)
    except G16ExactPublicationError as error:
        raise G16PreparedPublicationError(f"exact publication completion invalid: {error}") from error

    expected_links = {
        "exact_causal_pipeline_fingerprint": causal_completion.get("fingerprint"),
        "replay_fingerprint": lock.get("replay_fingerprint"),
        "manifest_fingerprint": lock.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": lock.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": lock.get("blind_prior_fingerprint"),
        "plan_fingerprint": lock.get("plan_fingerprint"),
        "authorization_stream_fingerprint": lock.get("authorization_stream_fingerprint"),
        "posterior_stream_fingerprint": lock.get("posterior_stream_fingerprint"),
        "blind_forecast_sha256": lock.get("blind_forecast_sha256"),
        "refined_forecast_sha256": lock.get("refined_forecast_sha256"),
        "refined_curve_fingerprint": lock.get("refined_curve_fingerprint"),
    }
    for field, expected_value in expected_links.items():
        if exact.get(field) != expected_value:
            raise G16PreparedPublicationError(
                f"exact publication {field} bypasses the prepared curve lock"
            )
    if exact.get("actual_g16_outcomes_used") is not True:
        raise G16PreparedPublicationError("exact publication must record fixed outcome scoring")
    if exact.get("random_shuffle_used") is not False:
        raise G16PreparedPublicationError("random-shuffled time-series scoring is forbidden")

    all_stand_downs = sorted(
        set(str(day) for day in lock.get("stand_down_days") or [])
        | set(str(day) for day in exact.get("stand_down_days") or [])
    )
    status = READY_WITH_STAND_DOWNS if all_stand_downs else READY
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": status,
        "authority": AUTHORITY,
        "curve_lock_fingerprint": lock["lock_fingerprint"],
        "prepared_curve_authorization_fingerprint": lock[
            "prepared_curve_authorization_fingerprint"
        ],
        "prepared_causal_authorization_fingerprint": lock[
            "prepared_causal_authorization_fingerprint"
        ],
        "prepared_replay_gate_fingerprint": lock["prepared_replay_gate_fingerprint"],
        "exact_publication_completion_fingerprint": exact["completion_fingerprint"],
        "exact_causal_pipeline_fingerprint": exact["exact_causal_pipeline_fingerprint"],
        "replay_fingerprint": exact["replay_fingerprint"],
        "manifest_fingerprint": exact["manifest_fingerprint"],
        "prepared_corpus_fingerprint": exact["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": exact["blind_prior_fingerprint"],
        "blind_safe_state_fingerprint": exact["blind_safe_state_fingerprint"],
        "g15_lesson_adjudication_fingerprint": exact[
            "g15_lesson_adjudication_fingerprint"
        ],
        "g15_lesson_registry_fingerprint": exact["g15_lesson_registry_fingerprint"],
        "plan_fingerprint": exact["plan_fingerprint"],
        "authorization_stream_fingerprint": exact["authorization_stream_fingerprint"],
        "posterior_stream_fingerprint": exact["posterior_stream_fingerprint"],
        "blind_forecast_sha256": exact["blind_forecast_sha256"],
        "refined_forecast_sha256": exact["refined_forecast_sha256"],
        "refined_curve_fingerprint": exact["refined_curve_fingerprint"],
        "transform_config": copy.deepcopy(dict(lock.get("transform_config") or {})),
        "registered_candidate_ids": list(lock.get("registered_candidate_ids") or []),
        "used_candidate_ids": list(lock.get("used_candidate_ids") or []),
        "actual_sha256": exact["actual_sha256"],
        "actual_core_fingerprint": exact["actual_core_fingerprint"],
        "blind_score_fingerprint": exact["blind_score_fingerprint"],
        "refined_score_fingerprint": exact["refined_score_fingerprint"],
        "comparison_fingerprint": exact["comparison_fingerprint"],
        "chronological_validation_fingerprint": exact[
            "chronological_validation_fingerprint"
        ],
        "curve_lock_stand_down_days": list(lock.get("stand_down_days") or []),
        "publication_stand_down_days": list(exact.get("stand_down_days") or []),
        "stand_down_days": all_stand_downs,
        "renders": copy.deepcopy(dict(exact.get("renders") or {})),
        "post_g16_shadow_registry": copy.deepcopy(
            dict(exact.get("post_g16_shadow_registry") or {})
        ),
        "authorized_next_stages": copy.deepcopy(list(exact.get("authorized_next_stages") or [])),
        "curve_locked_before_fixed_scoring": True,
        "prepared_replay_provenance_preserved_through_scoring": True,
        "actual_g16_outcomes_used": True,
        "outcome_scoring_complete": True,
        "chronological_validation_complete": True,
        "continuous_rt_renders_complete": True,
        "g16_consumed_as_forward_holdout": True,
        "g16_reusable_as_untouched_holdout": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
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
        "note": (
            "The exact prepared NGK26 curve was locked before the fixed G16 actual "
            "substrate was admitted. That same immutable curve then passed separate "
            "blind/refined scoring, fixed chronological validation, and canonical "
            "continuous_rt rendering. G16 is consumed forward-holdout evidence; brain "
            "adoption, options implementation, and execution remain unauthorized."
        ),
    }
    result["completion_fingerprint"] = _fp(result)
    if (
        curve_lock,
        curve_authorization,
        prepared_causal_authorization,
        prepared_gate,
        prepared_index,
        manifest,
        replay,
        blind_prior,
        causal_artifacts,
        blind_forecast,
        blind_safe_state,
        registry_source,
        shadow_plan,
        posterior_stream,
        refined_curve,
        adjudication,
        actual,
        blind_score,
        refined_score,
        comparison,
        chronology,
        blind_rt,
        refined_rt,
    ) != originals:
        raise G16PreparedPublicationError("prepared publication mutated a source artifact")
    validate_completion(result)
    return result


def validate_completion(completion: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(
        completion, "completion_fingerprint", label="prepared G16 publication completion"
    )
    if value.get("schema") != SCHEMA or value.get("status") not in {
        READY,
        READY_WITH_STAND_DOWNS,
    }:
        raise G16PreparedPublicationError("prepared G16 publication completion is not ready")
    if value.get("authority") != AUTHORITY:
        raise G16PreparedPublicationError("prepared G16 publication authority mismatch")
    _require_false(
        value,
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
        label="prepared G16 publication completion",
    )
    for field in (
        "curve_locked_before_fixed_scoring",
        "prepared_replay_provenance_preserved_through_scoring",
        "actual_g16_outcomes_used",
        "outcome_scoring_complete",
        "chronological_validation_complete",
        "continuous_rt_renders_complete",
        "g16_consumed_as_forward_holdout",
        "one_signal_authority_preserved",
        "blind_forecast_immutable",
    ):
        if value.get(field) is not True:
            raise G16PreparedPublicationError(
                f"prepared G16 publication completion: {field} must be true"
            )
    required = (
        "curve_lock_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "prepared_causal_authorization_fingerprint",
        "prepared_replay_gate_fingerprint",
        "exact_publication_completion_fingerprint",
        "exact_causal_pipeline_fingerprint",
        "replay_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "blind_prior_fingerprint",
        "plan_fingerprint",
        "authorization_stream_fingerprint",
        "posterior_stream_fingerprint",
        "blind_forecast_sha256",
        "refined_forecast_sha256",
        "refined_curve_fingerprint",
        "actual_sha256",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
        "chronological_validation_fingerprint",
    )
    if any(not value.get(field) for field in required):
        raise G16PreparedPublicationError("prepared G16 publication lacks required provenance")
    stand_downs = sorted({str(day) for day in value.get("stand_down_days") or []})
    if stand_downs != list(value.get("stand_down_days") or []):
        raise G16PreparedPublicationError("prepared G16 publication stand-down days are not canonical")
    expected_status = READY_WITH_STAND_DOWNS if stand_downs else READY
    if value.get("status") != expected_status:
        raise G16PreparedPublicationError("prepared G16 publication stand-down status mismatch")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedPublicationError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedPublicationError("brokerage contract must remain tastytrade")
    renders = dict(value.get("renders") or {})
    if set(renders) != {"blind", "refined"}:
        raise G16PreparedPublicationError("prepared G16 publication requires both renders")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lock the exact prepared G16 curve, then score and publish it"
    )
    for name in (
        "prepared-curve-authorization",
        "prepared-causal-authorization",
        "prepared-gate",
        "prepared-index",
        "manifest",
        "replay",
        "blind-prior",
        "causal-completion",
        "shadow-plan",
        "authorization-stream",
        "posterior-stream",
        "blind",
        "blind-safe-state",
        "registry",
        "refined",
        "adjudication",
        "actual",
        "blind-score",
        "refined-score",
        "comparison",
        "chronological-validation",
        "blind-rt",
        "refined-rt",
        "blind-png",
        "refined-png",
        "curve-lock-out",
        "out",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()

    blind_file_bytes = args.blind.read_bytes()
    refined_file_bytes = args.refined.read_bytes()
    blind_forecast = json.loads(blind_file_bytes.decode("utf-8"))
    refined_curve = json.loads(refined_file_bytes.decode("utf-8"))
    causal_artifacts = {
        "completion": _load(args.causal_completion),
        "plan": _load(args.shadow_plan),
        "authorization_stream": _load(args.authorization_stream),
        "posterior_stream": _load(args.posterior_stream),
    }
    pre_scoring = {
        "curve_authorization": _load(args.prepared_curve_authorization),
        "prepared_causal_authorization": _load(args.prepared_causal_authorization),
        "prepared_gate": _load(args.prepared_gate),
        "prepared_index": _load(args.prepared_index),
        "manifest": _load(args.manifest),
        "replay": _load(args.replay),
        "blind_prior": _load(args.blind_prior),
        "causal_artifacts": causal_artifacts,
        "blind_forecast": blind_forecast,
        "blind_safe_state": _load(args.blind_safe_state),
        "registry_source": _load(args.registry),
        "shadow_plan": causal_artifacts["plan"],
        "posterior_stream": causal_artifacts["posterior_stream"],
        "refined_curve": refined_curve,
        "blind_file_bytes": blind_file_bytes,
        "refined_file_bytes": refined_file_bytes,
    }
    curve_lock = build_curve_lock(**pre_scoring)
    _atomic(args.curve_lock_out, curve_lock)

    actual_file_bytes = args.actual.read_bytes()
    result = build_completion(
        curve_lock=curve_lock,
        adjudication=_load(args.adjudication),
        actual=json.loads(actual_file_bytes.decode("utf-8")),
        blind_score=_load(args.blind_score),
        refined_score=_load(args.refined_score),
        comparison=_load(args.comparison),
        chronology=_load(args.chronological_validation),
        blind_rt=_load(args.blind_rt),
        refined_rt=_load(args.refined_rt),
        actual_file_bytes=actual_file_bytes,
        blind_png=args.blind_png,
        refined_png=args.refined_png,
        **pre_scoring,
    )
    _atomic(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "curve_lock_out": str(args.curve_lock_out),
                "out": str(args.out),
                "completion_fingerprint": result["completion_fingerprint"],
                "g16_reusable_as_untouched_holdout": False,
                "options_lane_started": False,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
