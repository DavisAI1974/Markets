#!/usr/bin/env python3
"""Close G16 only when exact causal provenance survives publication.

The gate is downstream of ``ng_g16_exact_causal_pipeline``. It binds the
exact NGK26 historical replay and pre-cutoff SHADOW posterior to the immutable
blind forecast, the outcome-blind refined curve, separate outcome scorecards,
fixed chronological G15->G16 validation, and both canonical ``continuous_rt``
renders.

G16 is consumed as scored forward-holdout evidence after this gate. It may not
be recycled as an untouched holdout. Nothing here can modify a blind prior,
update ``knowledge/ng_brain.json``, start the options lane, or grant execution
authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_chronological_validation import (
    build_chronological_validation,
    validate_chronological_validation,
    validate_g15_adjudication,
    validate_g16_plan,
    validate_g16_posterior_stream,
)
from ng_g16_blind_wall import G16_DATES
from ng_g16_curve_adapter import build_refined_forecast, validate_refined_forecast
from ng_g16_path_score import (
    build_comparison,
    build_scorecard,
    validate_comparison,
    validate_scorecard,
)
from ng_g16_shadow_gate import validate_blind_forecast

SCHEMA = "ng_g16_exact_publication_completion.v1"
CAUSAL_SCHEMA = "ng_g16_exact_causal_pipeline.v1"
CAUSAL_AUTHORITY = "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY"
REFINED_SCHEMA = "ng_g16_refined_curve.v1"
REFINED_AUTHORITY = "G16_REFINED_CURVE_SHADOW_ONLY"
SCORE_SCHEMA = "ng_g16_path_score.v1"
COMPARISON_SCHEMA = "ng_g16_path_comparison.v1"
CHRONOLOGY_SCHEMA = "ng_chronological_validation.v1"
POST_G16_REGISTRY_SCHEMA = "ng_post_g16_shadow_candidate_registry.v1"
READY = "EXACT_G16_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = "EXACT_G16_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_RENDER_BYTES = 4096


class G16ExactPublicationError(ValueError):
    """Raised when exact G16 causal provenance is lost before publication."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise G16ExactPublicationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _require_false(value: Mapping[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if value.get(field) is not False:
            raise G16ExactPublicationError(f"{label}: {field} must remain false")


def _validate_curve_days(forecast: Mapping[str, Any], *, label: str) -> list[dict[str, Any]]:
    if int(forecast.get("group") or 0) != 16:
        raise G16ExactPublicationError(f"{label}: group must be 16")
    rows = [copy.deepcopy(dict(row)) for row in forecast.get("days") or []]
    if [str(row.get("date") or "") for row in rows] != list(G16_DATES):
        raise G16ExactPublicationError(f"{label}: canonical G16 dates are incomplete or out of order")
    for row in rows:
        day = str(row["date"])
        curve = list(row.get("guess_curve") or [])
        if len(curve) != len(GRID_HOURS) or tuple(int(point[0]) for point in curve) != GRID_HOURS:
            raise G16ExactPublicationError(f"{label}:{day}: curve grid mismatch")
        try:
            values = [float(point[1]) for point in curve]
        except (TypeError, ValueError, IndexError) as error:
            raise G16ExactPublicationError(f"{label}:{day}: invalid curve value") from error
        if abs(values[0]) > 1e-12:
            raise G16ExactPublicationError(f"{label}:{day}: cumulative curve must begin at zero")
        if abs(float(row.get("guessed_net_usd")) - values[-1]) > 1e-9:
            raise G16ExactPublicationError(f"{label}:{day}: guessed_net_usd differs from endpoint")
    return rows


def _validate_causal_completion(
    completion: Mapping[str, Any],
    *,
    blind_forecast: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> dict[str, Any]:
    value = _verify_fingerprint(completion, "fingerprint", label="exact causal completion")
    if value.get("schema") != CAUSAL_SCHEMA or value.get("authority") != CAUSAL_AUTHORITY:
        raise G16ExactPublicationError("exact causal completion schema/authority mismatch")
    if value.get("status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
        raise G16ExactPublicationError("exact causal completion is not ready")
    if int(value.get("group") or 0) != 16 or int(value.get("n_days") or 0) != len(G16_DATES):
        raise G16ExactPublicationError("exact causal completion G16 coverage mismatch")
    _require_false(
        value,
        (
            "execution_authority",
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "paid_live_data_assumed",
            "may_update_ng_brain",
            "may_change_g16_blind_prior",
            "may_change_g16_blind_forecast",
            "may_select_lessons_from_g16_outcomes",
        ),
        label="exact causal completion",
    )
    required = (
        "replay_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "blind_prior_fingerprint",
        "blind_safe_state_fingerprint",
        "lesson_registry_fingerprint",
        "lesson_adjudication_fingerprint",
        "plan_fingerprint",
        "authorization_stream_fingerprint",
        "posterior_stream_fingerprint",
    )
    if any(not value.get(field) for field in required):
        raise G16ExactPublicationError("exact causal completion lacks required provenance")
    if value.get("blind_forecast_fingerprint") != _fp(dict(blind_forecast)):
        raise G16ExactPublicationError("exact causal completion references another blind forecast")
    if value.get("lesson_adjudication_fingerprint") != adjudication.get("artifact_fingerprint"):
        raise G16ExactPublicationError("exact causal completion references another G15 adjudication")
    registry = dict(adjudication.get("g16_shadow_registry") or {})
    if value.get("lesson_registry_fingerprint") != registry.get("registry_fingerprint"):
        raise G16ExactPublicationError("exact causal completion references another G15 lesson registry")
    if value.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16ExactPublicationError("exact causal completion references another G16 plan")
    if value.get("posterior_stream_fingerprint") != posterior_stream.get("stream_fingerprint"):
        raise G16ExactPublicationError("exact causal completion references another posterior stream")
    if list(value.get("candidate_ids") or []) != list(plan.get("candidate_ids") or []):
        raise G16ExactPublicationError("exact causal completion candidate set differs from plan")
    stand_down_days = [str(day) for day in value.get("stand_down_days") or []]
    if any(day not in G16_DATES for day in stand_down_days):
        raise G16ExactPublicationError("exact causal completion contains non-G16 stand-down days")
    expected_status = "READY_WITH_STAND_DOWNS" if stand_down_days else "READY"
    if value.get("status") != expected_status:
        raise G16ExactPublicationError("exact causal completion hides or invents stand-downs")
    if value.get("next_permitted_stage") != "OUTCOME_BLIND_G16_CURVE_ADAPTER":
        raise G16ExactPublicationError("exact causal completion next-stage contract mismatch")
    return value


def _validate_blind(blind: Mapping[str, Any], blind_bytes: bytes) -> str:
    try:
        validate_blind_forecast(blind)
    except Exception as error:
        raise G16ExactPublicationError(f"blind forecast invalid: {error}") from error
    _validate_curve_days(blind, label="blind")
    return _sha256_bytes(blind_bytes)


def _validate_refined(
    refined: Mapping[str, Any],
    refined_bytes: bytes,
    *,
    blind: Mapping[str, Any],
    blind_hash: str,
    plan_fingerprint: str,
    posterior_stream_fingerprint: str,
) -> tuple[str, str]:
    try:
        validate_refined_forecast(refined, blind_forecast=blind)
    except Exception as error:
        raise G16ExactPublicationError(f"refined forecast invalid: {error}") from error
    value = _verify_fingerprint(refined, "artifact_fingerprint", label="refined forecast")
    if value.get("schema") != REFINED_SCHEMA or value.get("authority") != REFINED_AUTHORITY:
        raise G16ExactPublicationError("refined forecast schema/authority mismatch")
    if value.get("blind_forecast_sha256") != blind_hash:
        raise G16ExactPublicationError("refined forecast references another blind file")
    if value.get("shadow_plan_fingerprint") != plan_fingerprint:
        raise G16ExactPublicationError("refined forecast references another G16 plan")
    if value.get("posterior_stream_fingerprint") != posterior_stream_fingerprint:
        raise G16ExactPublicationError("refined forecast references another posterior stream")
    _validate_curve_days(value, label="refined")
    return str(value["artifact_fingerprint"]), _sha256_bytes(refined_bytes)


def _validate_score(
    score: Mapping[str, Any],
    *,
    role: str,
    forecast_hash: str,
    actual_hash: str,
) -> dict[str, Any]:
    try:
        validate_scorecard(score)
    except Exception as error:
        raise G16ExactPublicationError(f"{role} score invalid: {error}") from error
    value = _verify_fingerprint(score, "score_fingerprint", label=f"{role} score")
    if value.get("schema") != SCORE_SCHEMA or value.get("role") != role:
        raise G16ExactPublicationError(f"{role} score schema/role mismatch")
    if value.get("forecast_sha256") != forecast_hash:
        raise G16ExactPublicationError(f"{role} score references another forecast file")
    if value.get("actual_sha256") != actual_hash:
        raise G16ExactPublicationError(f"{role} score references another actual substrate")
    return value


def _validate_comparison(
    comparison: Mapping[str, Any],
    *,
    actual_hash: str,
    blind_score_fingerprint: str,
    refined_score_fingerprint: str,
) -> dict[str, Any]:
    try:
        validate_comparison(comparison)
    except Exception as error:
        raise G16ExactPublicationError(f"comparison invalid: {error}") from error
    value = _verify_fingerprint(comparison, "comparison_fingerprint", label="comparison")
    if value.get("schema") != COMPARISON_SCHEMA:
        raise G16ExactPublicationError("comparison schema mismatch")
    if value.get("actual_sha256") != actual_hash:
        raise G16ExactPublicationError("comparison references another actual substrate")
    if value.get("blind_score_fingerprint") != blind_score_fingerprint:
        raise G16ExactPublicationError("comparison references another blind score")
    if value.get("refined_score_fingerprint") != refined_score_fingerprint:
        raise G16ExactPublicationError("comparison references another refined score")
    return value


def _validate_chronology(
    chronology: Mapping[str, Any],
    *,
    causal: Mapping[str, Any],
    comparison_fingerprint: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        validate_chronological_validation(chronology)
    except Exception as error:
        raise G16ExactPublicationError(f"chronological validation invalid: {error}") from error
    value = _verify_fingerprint(chronology, "artifact_fingerprint", label="chronological validation")
    if value.get("schema") != CHRONOLOGY_SCHEMA:
        raise G16ExactPublicationError("chronological validation schema mismatch")
    source = dict(value.get("source") or {})
    expected = {
        "g15_adjudication_fingerprint": causal.get("lesson_adjudication_fingerprint"),
        "g15_registry_fingerprint": causal.get("lesson_registry_fingerprint"),
        "g16_plan_fingerprint": causal.get("plan_fingerprint"),
        "g16_posterior_stream_fingerprint": causal.get("posterior_stream_fingerprint"),
        "g16_comparison_fingerprint": comparison_fingerprint,
    }
    if any(source.get(field) != expected_value for field, expected_value in expected.items()):
        raise G16ExactPublicationError("chronological validation references another causal/scoring chain")
    partition = dict(value.get("partition") or {})
    if partition.get("policy") != "FIXED_CHRONOLOGICAL_BLOCKS_NO_SHUFFLE":
        raise G16ExactPublicationError("chronological validation partition policy mismatch")
    if value.get("random_shuffle_used") is not False or value.get("random_shuffle_allowed") is not False:
        raise G16ExactPublicationError("random-shuffled time-series validation is forbidden")
    block = dict(value.get("block") or {})
    if block.get("g16_reusable_as_untouched_holdout") is not False:
        raise G16ExactPublicationError("G16 cannot remain an untouched holdout after outcome scoring")
    registry = dict(value.get("post_g16_shadow_registry") or {})
    if registry.get("schema") != POST_G16_REGISTRY_SCHEMA:
        raise G16ExactPublicationError("post-G16 registry schema mismatch")
    return value, registry


def _actual_core(actual: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if actual.get("market") != "NG" or int(actual.get("n_days") or 0) != len(G16_DATES):
        raise G16ExactPublicationError(f"{label}: actual substrate must contain canonical G16 sessions")
    if actual.get("roll_adjusted") not in (False, None):
        raise G16ExactPublicationError(f"{label}: G16 actual substrate cannot be roll-adjusted")
    if list(actual.get("rolls") or []) or list(actual.get("seams") or []):
        raise G16ExactPublicationError(f"{label}: G16 must remain a clean NGK26 block")
    anchor = dict(actual.get("anchor") or {})
    if str(anchor.get("date") or "") != "20260327":
        raise G16ExactPublicationError(f"{label}: anchor must be 20260327")
    days = [copy.deepcopy(dict(row)) for row in actual.get("days") or []]
    if [str(row.get("date") or "") for row in days] != list(G16_DATES):
        raise G16ExactPublicationError(f"{label}: canonical G16 date order required")
    for row in days:
        day = str(row["date"])
        curve = list(row.get("curve_2h") or [])
        if len(curve) != len(GRID_HOURS) or tuple(int(point[0]) for point in curve) != GRID_HOURS:
            raise G16ExactPublicationError(f"{label}:{day}: actual curve grid mismatch")
        if row.get("instrument") not in (None, "NGK26"):
            raise G16ExactPublicationError(f"{label}:{day}: actual instrument must remain NGK26")
    return {
        "market": actual.get("market"),
        "anchor": anchor,
        "seams": copy.deepcopy(actual.get("seams") or []),
        "rolls": copy.deepcopy(actual.get("rolls") or []),
        "roll_adjusted": actual.get("roll_adjusted"),
        "n_days": int(actual.get("n_days") or 0),
        "days": days,
    }


def _validate_render_rt(rt: Mapping[str, Any], *, tag: str, expected_core_fingerprint: str) -> str:
    if rt.get("tag") != tag:
        raise G16ExactPublicationError(f"{tag}: render RT tag mismatch")
    core_fingerprint = _fp(_actual_core(rt, label=f"{tag} render RT"))
    if core_fingerprint != expected_core_fingerprint:
        raise G16ExactPublicationError(f"{tag}: render uses another actual substrate")
    return core_fingerprint


def _png_receipt(path: Path, *, expected_name: str) -> dict[str, Any]:
    if path.name != expected_name:
        raise G16ExactPublicationError(f"render filename must be {expected_name}")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise G16ExactPublicationError(f"render is unreadable: {path}") from error
    if len(data) < MIN_RENDER_BYTES:
        raise G16ExactPublicationError(f"render is too small to be canonical: {path}")
    if data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise G16ExactPublicationError(f"render is not a valid PNG header: {path}")
    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise G16ExactPublicationError(f"render dimensions are invalid: {path}")
    return {
        "path": str(path),
        "filename": path.name,
        "sha256": _sha256_bytes(data),
        "size_bytes": len(data),
        "width_px": width,
        "height_px": height,
    }


def build_completion(
    *,
    causal_completion: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    blind: Mapping[str, Any],
    refined: Mapping[str, Any],
    actual: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    chronology: Mapping[str, Any],
    blind_rt: Mapping[str, Any],
    refined_rt: Mapping[str, Any],
    blind_bytes: bytes,
    refined_bytes: bytes,
    actual_bytes: bytes,
    blind_png: Path,
    refined_png: Path,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            causal_completion,
            adjudication,
            plan,
            posterior_stream,
            blind,
            refined,
            actual,
            blind_score,
            refined_score,
            comparison,
            chronology,
            blind_rt,
            refined_rt,
        )
    )
    try:
        validate_g15_adjudication(adjudication)
        validate_g16_plan(plan, adjudication=adjudication)
        validate_g16_posterior_stream(posterior_stream, plan=plan)
    except Exception as error:
        raise G16ExactPublicationError(f"causal authority chain invalid: {error}") from error
    causal = _validate_causal_completion(
        causal_completion,
        blind_forecast=blind,
        adjudication=adjudication,
        plan=plan,
        posterior_stream=posterior_stream,
    )
    blind_hash = _validate_blind(blind, blind_bytes)
    refined_fingerprint, refined_hash = _validate_refined(
        refined,
        refined_bytes,
        blind=blind,
        blind_hash=blind_hash,
        plan_fingerprint=str(causal["plan_fingerprint"]),
        posterior_stream_fingerprint=str(causal["posterior_stream_fingerprint"]),
    )
    actual_hash = _sha256_bytes(actual_bytes)
    actual_core_fingerprint = _fp(_actual_core(actual, label="scoring actual"))
    blind_score_value = _validate_score(
        blind_score, role="blind", forecast_hash=blind_hash, actual_hash=actual_hash
    )
    refined_score_value = _validate_score(
        refined_score, role="refined", forecast_hash=refined_hash, actual_hash=actual_hash
    )
    comparison_value = _validate_comparison(
        comparison,
        actual_hash=actual_hash,
        blind_score_fingerprint=str(blind_score_value["score_fingerprint"]),
        refined_score_fingerprint=str(refined_score_value["score_fingerprint"]),
    )
    chronology_value, post_registry = _validate_chronology(
        chronology,
        causal=causal,
        comparison_fingerprint=str(comparison_value["comparison_fingerprint"]),
    )
    _validate_render_rt(
        blind_rt, tag="g16_mbo_blind", expected_core_fingerprint=actual_core_fingerprint
    )
    _validate_render_rt(
        refined_rt, tag="g16_mbo_refined", expected_core_fingerprint=actual_core_fingerprint
    )
    blind_render = _png_receipt(
        blind_png, expected_name="g16_mbo_blind_continuous.png"
    )
    refined_render = _png_receipt(
        refined_png, expected_name="g16_mbo_refined_continuous.png"
    )
    blind_render.update(
        {
            "tag": "g16_mbo_blind",
            "forecast_sha256": blind_hash,
            "rt_json_fingerprint": _fp(blind_rt),
            "actual_core_fingerprint": actual_core_fingerprint,
        }
    )
    refined_render.update(
        {
            "tag": "g16_mbo_refined",
            "forecast_sha256": refined_hash,
            "refined_curve_fingerprint": refined_fingerprint,
            "rt_json_fingerprint": _fp(refined_rt),
            "actual_core_fingerprint": actual_core_fingerprint,
        }
    )
    stand_down_days = list(causal.get("stand_down_days") or [])
    candidate_ids = [
        str(row.get("candidate_id") or "")
        for row in post_registry.get("candidates") or []
    ]
    next_shadow_authorized = bool(
        (post_registry.get("gate") or {}).get("next_untouched_shadow_test_authorized")
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": "G16_EXACT_PUBLICATION_AUDIT_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": True,
        "may_change_any_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "random_shuffle_used": False,
        "options_lane_started": False,
        "options_implementation_authorized": False,
        "exact_g16_publication_complete": True,
        "outcome_scoring_complete": True,
        "chronological_validation_complete": True,
        "continuous_rt_renders_complete": True,
        "g16_consumed_as_forward_holdout": True,
        "g16_reusable_as_untouched_holdout": False,
        "exact_causal_pipeline_fingerprint": causal["fingerprint"],
        "replay_fingerprint": causal["replay_fingerprint"],
        "manifest_fingerprint": causal["manifest_fingerprint"],
        "prepared_corpus_fingerprint": causal["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": causal["blind_prior_fingerprint"],
        "blind_safe_state_fingerprint": causal["blind_safe_state_fingerprint"],
        "g15_lesson_adjudication_fingerprint": causal["lesson_adjudication_fingerprint"],
        "g15_lesson_registry_fingerprint": causal["lesson_registry_fingerprint"],
        "plan_fingerprint": causal["plan_fingerprint"],
        "authorization_stream_fingerprint": causal["authorization_stream_fingerprint"],
        "posterior_stream_fingerprint": causal["posterior_stream_fingerprint"],
        "blind_forecast_sha256": blind_hash,
        "refined_forecast_sha256": refined_hash,
        "refined_curve_fingerprint": refined_fingerprint,
        "actual_sha256": actual_hash,
        "actual_core_fingerprint": actual_core_fingerprint,
        "blind_score_fingerprint": blind_score_value["score_fingerprint"],
        "refined_score_fingerprint": refined_score_value["score_fingerprint"],
        "comparison_fingerprint": comparison_value["comparison_fingerprint"],
        "chronological_validation_fingerprint": chronology_value["artifact_fingerprint"],
        "stand_down_days": stand_down_days,
        "renders": {"blind": blind_render, "refined": refined_render},
        "post_g16_shadow_registry": {
            "registry_fingerprint": post_registry.get("registry_fingerprint"),
            "candidate_count": int(post_registry.get("candidate_count") or 0),
            "candidate_ids": candidate_ids,
            "next_untouched_shadow_test_authorized": next_shadow_authorized,
            "brain_adoption_authorized": False,
            "execution_authorized": False,
            "may_change_any_blind_prior": False,
            "may_update_ng_brain": False,
        },
        "authorized_next_stages": (
            ["POST_G16_UNTOUCHED_OR_FORWARD_LIVE_SHADOW_TEST"]
            if next_shadow_authorized
            else ["POST_G16_BASELINE_ONLY_OR_NEW_PRE_REGISTERED_DISCOVERY"]
        ),
        "note": (
            "Exact NGK26 replay provenance remains attached through outcome-blind G16 "
            "refinement, separate outcome scoring, fixed chronological validation, and "
            "both canonical renders. G16 is now consumed evidence; only a new untouched "
            "or forward-live SHADOW test may follow. Brain adoption, options implementation, "
            "and execution remain unauthorized."
        ),
    }
    result["completion_fingerprint"] = _fp(result)
    if (
        causal_completion,
        adjudication,
        plan,
        posterior_stream,
        blind,
        refined,
        actual,
        blind_score,
        refined_score,
        comparison,
        chronology,
        blind_rt,
        refined_rt,
    ) != originals:
        raise G16ExactPublicationError("publication validation mutated a source artifact")
    validate_completion(result)
    return result


def validate_completion(completion: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(completion, "completion_fingerprint", label="G16 publication completion")
    if value.get("schema") != SCHEMA or value.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16ExactPublicationError("G16 publication completion is not ready")
    if value.get("authority") != "G16_EXACT_PUBLICATION_AUDIT_ONLY":
        raise G16ExactPublicationError("G16 publication completion authority mismatch")
    _require_false(
        value,
        (
            "execution_authority",
            "may_change_any_blind_prior",
            "may_change_blind_forecast",
            "may_change_posterior",
            "may_update_ng_brain",
            "random_shuffle_used",
            "options_lane_started",
            "options_implementation_authorized",
            "g16_reusable_as_untouched_holdout",
        ),
        label="G16 publication completion",
    )
    for field in (
        "actual_g16_outcomes_used",
        "exact_g16_publication_complete",
        "outcome_scoring_complete",
        "chronological_validation_complete",
        "continuous_rt_renders_complete",
        "g16_consumed_as_forward_holdout",
    ):
        if value.get(field) is not True:
            raise G16ExactPublicationError(f"G16 publication completion: {field} must be true")
    stand_down_days = list(value.get("stand_down_days") or [])
    expected_status = READY_WITH_STAND_DOWNS if stand_down_days else READY
    if value.get("status") != expected_status:
        raise G16ExactPublicationError("G16 publication completion stand-down status mismatch")
    renders = dict(value.get("renders") or {})
    if set(renders) != {"blind", "refined"}:
        raise G16ExactPublicationError("G16 publication completion requires both renders")
    for name, expected in (
        ("blind", "g16_mbo_blind_continuous.png"),
        ("refined", "g16_mbo_refined_continuous.png"),
    ):
        row = dict(renders[name])
        if row.get("filename") != expected or int(row.get("size_bytes") or 0) < MIN_RENDER_BYTES:
            raise G16ExactPublicationError(f"{name} render receipt is invalid")
        if int(row.get("width_px") or 0) <= 0 or int(row.get("height_px") or 0) <= 0:
            raise G16ExactPublicationError(f"{name} render dimensions are invalid")
    registry = dict(value.get("post_g16_shadow_registry") or {})
    if registry.get("brain_adoption_authorized") is not False or registry.get("execution_authorized") is not False:
        raise G16ExactPublicationError("post-G16 registry cannot authorize brain adoption or execution")
    if registry.get("may_change_any_blind_prior") is not False or registry.get("may_update_ng_brain") is not False:
        raise G16ExactPublicationError("post-G16 registry cannot mutate blind priors or ng_brain")
    if bool(registry.get("next_untouched_shadow_test_authorized")) != bool(registry.get("candidate_count")):
        raise G16ExactPublicationError("post-G16 registry authorization differs from candidate availability")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _png_fixture(width: int = 1800, height: int = 500) -> bytes:
    header = PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    return header + b"\x08\x02\x00\x00\x00" + b"x" * (MIN_RENDER_BYTES - len(header) - 5)


def _fixture(tmp: Path) -> dict[str, Any]:
    from ng_g15_lesson_adjudication import _fixture as g15_fixture, build_adjudication
    from ng_g16_curve_adapter import _fixture_forecast, _fixture_output
    from ng_g16_path_score import _fixture_actual
    from ng_g16_shadow_gate import _fixture_blind_state, build_shadow_plan

    audit, proposals, g15_comparison = g15_fixture()
    adjudication = build_adjudication(audit, proposals, g15_comparison)
    blind = _fixture_forecast()
    blind_bytes = (json.dumps(blind, indent=2, sort_keys=True) + "\n").encode("utf-8")
    plan = build_shadow_plan(blind, _fixture_blind_state(), adjudication)
    outputs = [_fixture_output(day, blind, plan) for day in G16_DATES]
    posterior_stream = {
        "schema": "ng_g16_shadow_posterior_stream.v1",
        "market": "NG",
        "group": 16,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan["plan_fingerprint"],
        "authorization_stream_fingerprint": "auth-stream-fixture",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    posterior_stream["stream_fingerprint"] = _fp(posterior_stream)
    refined = build_refined_forecast(
        blind,
        plan,
        posterior_stream,
        blind_file_bytes=blind_bytes,
    )
    refined_bytes = (json.dumps(refined, indent=2, sort_keys=True) + "\n").encode("utf-8")
    actual = _fixture_actual()
    actual_bytes = (json.dumps(actual, indent=2, sort_keys=True) + "\n").encode("utf-8")
    blind_score = build_scorecard(
        blind,
        actual,
        role="blind",
        forecast_bytes=blind_bytes,
        actual_bytes=actual_bytes,
    )
    refined_score = build_scorecard(
        refined,
        actual,
        role="refined",
        blind_forecast=blind,
        forecast_bytes=refined_bytes,
        blind_bytes=blind_bytes,
        actual_bytes=actual_bytes,
    )
    comparison = build_comparison(blind_score, refined_score)
    chronology = build_chronological_validation(
        adjudication, plan, posterior_stream, comparison
    )
    days = {
        day: {
            "date": day,
            "n_states": 1,
            "n_updated": 1,
            "n_no_change": 0,
            "n_stand_down": 0,
        }
        for day in G16_DATES
    }
    causal_completion = {
        "schema": CAUSAL_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "READY",
        "authority": CAUSAL_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_select_lessons_from_g16_outcomes": False,
        "replay_fingerprint": "replay-fixture",
        "manifest_fingerprint": "manifest-fixture",
        "prepared_corpus_fingerprint": "prepared-fixture",
        "blind_prior_fingerprint": "prior-fixture",
        "blind_forecast_fingerprint": _fp(blind),
        "blind_safe_state_fingerprint": plan["blind_safe_state_fingerprint"],
        "lesson_registry_fingerprint": plan["lesson_registry_fingerprint"],
        "lesson_adjudication_fingerprint": plan["lesson_adjudication_fingerprint"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "authorization_stream_fingerprint": posterior_stream["authorization_stream_fingerprint"],
        "posterior_stream_fingerprint": posterior_stream["stream_fingerprint"],
        "candidate_ids": list(plan["candidate_ids"]),
        "candidate_request_policy": "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS",
        "n_states": len(outputs),
        "n_outputs": len(outputs),
        "n_days": len(G16_DATES),
        "stand_down_days": [],
        "days": days,
        "next_permitted_stage": "OUTCOME_BLIND_G16_CURVE_ADAPTER",
    }
    causal_completion["fingerprint"] = _fp(causal_completion)
    blind_rt = copy.deepcopy(actual)
    blind_rt["tag"] = "g16_mbo_blind"
    refined_rt = copy.deepcopy(actual)
    refined_rt["tag"] = "g16_mbo_refined"
    blind_png = tmp / "g16_mbo_blind_continuous.png"
    refined_png = tmp / "g16_mbo_refined_continuous.png"
    blind_png.write_bytes(_png_fixture())
    refined_png.write_bytes(_png_fixture())
    return {
        "causal_completion": causal_completion,
        "adjudication": adjudication,
        "plan": plan,
        "posterior_stream": posterior_stream,
        "blind": blind,
        "refined": refined,
        "actual": actual,
        "blind_score": blind_score,
        "refined_score": refined_score,
        "comparison": comparison,
        "chronology": chronology,
        "blind_rt": blind_rt,
        "refined_rt": refined_rt,
        "blind_bytes": blind_bytes,
        "refined_bytes": refined_bytes,
        "actual_bytes": actual_bytes,
        "blind_png": blind_png,
        "refined_png": refined_png,
    }


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tempdir:
        fixture = _fixture(Path(tempdir))
        completion = build_completion(**fixture)
        assert completion["status"] == READY
        assert completion["g16_consumed_as_forward_holdout"] is True
        assert completion["g16_reusable_as_untouched_holdout"] is False
        assert completion["options_lane_started"] is False
    print("[ng_g16_exact_publication_gate] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exact G16 publication completion")
    parser.add_argument("--selftest", action="store_true")
    for name in (
        "causal-completion",
        "adjudication",
        "plan",
        "posterior-stream",
        "blind",
        "refined",
        "actual",
        "blind-score",
        "refined-score",
        "comparison",
        "chronological-validation",
        "blind-rt",
        "refined-rt",
        "blind-png",
        "refined-png",
        "out",
    ):
        parser.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        "causal_completion",
        "adjudication",
        "plan",
        "posterior_stream",
        "blind",
        "refined",
        "actual",
        "blind_score",
        "refined_score",
        "comparison",
        "chronological_validation",
        "blind_rt",
        "refined_rt",
        "blind_png",
        "refined_png",
        "out",
    )
    if any(getattr(args, name) is None for name in required):
        parser.error("all artifact and render paths are required")
    blind_bytes = args.blind.read_bytes()
    refined_bytes = args.refined.read_bytes()
    actual_bytes = args.actual.read_bytes()
    result = build_completion(
        causal_completion=_load(args.causal_completion),
        adjudication=_load(args.adjudication),
        plan=_load(args.plan),
        posterior_stream=_load(args.posterior_stream),
        blind=json.loads(blind_bytes.decode("utf-8")),
        refined=json.loads(refined_bytes.decode("utf-8")),
        actual=json.loads(actual_bytes.decode("utf-8")),
        blind_score=_load(args.blind_score),
        refined_score=_load(args.refined_score),
        comparison=_load(args.comparison),
        chronology=_load(args.chronological_validation),
        blind_rt=_load(args.blind_rt),
        refined_rt=_load(args.refined_rt),
        blind_bytes=blind_bytes,
        refined_bytes=refined_bytes,
        actual_bytes=actual_bytes,
        blind_png=args.blind_png,
        refined_png=args.refined_png,
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "out": str(args.out),
                "completion_fingerprint": result["completion_fingerprint"],
                "post_g16_candidate_count": result["post_g16_shadow_registry"]["candidate_count"],
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
