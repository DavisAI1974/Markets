#!/usr/bin/env python3
"""Close G15 only when exact-replay provenance survives publication.

This gate is downstream of ``ng_g15_exact_refinement_gate``. It binds the
exact matched L1+MBO authorization to the immutable blind forecast, the
outcome-blind refined curve, outcome-only blind/refined scorecards, the scored
comparison, conservative lesson adjudication, and both canonical
``continuous_rt.py`` render products.

The gate never creates a forecast, never reads evidence early, never updates
``knowledge/ng_brain.json``, and never grants execution authority. G16 access
is limited to a fingerprinted pre-cutoff SHADOW lesson registry; G16 outcomes
remain forbidden.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "ng_g15_exact_publication_completion.v1"
AUTH_SCHEMA = "ng_g15_exact_refinement_authorization.v1"
REFINED_SCHEMA = "ng_g15_refined_curve.v1"
SCORE_SCHEMA = "ng_g15_path_score.v1"
COMPARISON_SCHEMA = "ng_g15_path_comparison.v1"
ADJUDICATION_SCHEMA = "ng_g15_lesson_adjudication.v1"
REGISTRY_SCHEMA = "ng_g16_shadow_lesson_registry.v1"
READY = "EXACT_G15_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = "EXACT_G15_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
AUTH_READY = {
    "EXACT_G15_REFINEMENT_READY",
    "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS",
}
G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_RENDER_BYTES = 4096


class ExactPublicationError(ValueError):
    """Raised when a published G15 artifact loses exact causal provenance."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(payload):
        raise ExactPublicationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _validate_dates(days: Any, *, label: str) -> list[dict[str, Any]]:
    rows = [copy.deepcopy(dict(row)) for row in days or []]
    dates = [str(row.get("date") or "") for row in rows]
    if dates != list(G15_DATES):
        raise ExactPublicationError(
            f"{label}: canonical G15 dates are incomplete or out of order"
        )
    return rows


def _validate_curve_days(forecast: Mapping[str, Any], *, label: str) -> list[dict[str, Any]]:
    if int(forecast.get("group") or 0) != 15:
        raise ExactPublicationError(f"{label}: group must be 15")
    rows = _validate_dates(forecast.get("days"), label=label)
    for row in rows:
        date = str(row["date"])
        curve = list(row.get("guess_curve") or [])
        if len(curve) != len(GRID_HOURS):
            raise ExactPublicationError(
                f"{label}:{date}: expected {len(GRID_HOURS)} curve points"
            )
        if tuple(int(point[0]) for point in curve) != GRID_HOURS:
            raise ExactPublicationError(f"{label}:{date}: curve grid mismatch")
        try:
            values = [float(point[1]) for point in curve]
        except (TypeError, ValueError, IndexError) as error:
            raise ExactPublicationError(f"{label}:{date}: invalid curve value") from error
        if abs(values[0]) > 1e-12:
            raise ExactPublicationError(f"{label}:{date}: curve must begin at zero")
        if abs(float(row.get("guessed_net_usd")) - values[-1]) > 1e-9:
            raise ExactPublicationError(
                f"{label}:{date}: guessed_net_usd differs from endpoint"
            )
    return rows


def _validate_authorization(
    authorization: Mapping[str, Any], blind_bytes: bytes
) -> dict[str, Any]:
    value = _verify_fingerprint(
        authorization, "authorization_fingerprint", label="authorization"
    )
    if value.get("schema") != AUTH_SCHEMA or value.get("status") not in AUTH_READY:
        raise ExactPublicationError("authorization is not exact-refinement ready")
    if value.get("authority") != "EXACT_G15_REFINEMENT_AUTHORIZATION_ONLY":
        raise ExactPublicationError("authorization authority mismatch")
    for field in (
        "execution_authority", "actual_outcomes_used", "may_change_blind_prior",
        "may_change_blind_forecast", "may_change_posterior", "may_update_ng_brain",
        "g16_authorized",
    ):
        if value.get(field) is not False:
            raise ExactPublicationError(f"authorization must keep {field}=false")
    if value.get("days") != list(G15_DATES):
        raise ExactPublicationError("authorization lost canonical G15 dates")
    if value.get("blind_forecast_sha256") != _sha256_bytes(blind_bytes):
        raise ExactPublicationError(
            "authorization references a different blind forecast"
        )
    if not value.get("refine_stream_fingerprint"):
        raise ExactPublicationError("authorization lacks refine stream fingerprint")
    return value


def _validate_blind(blind: Mapping[str, Any], blind_bytes: bytes) -> str:
    _validate_curve_days(blind, label="blind")
    if blind.get("actual_outcomes_used") is True:
        raise ExactPublicationError("blind forecast contains outcome authority")
    return _sha256_bytes(blind_bytes)


def _validate_refined(
    refined: Mapping[str, Any],
    refined_bytes: bytes,
    *,
    blind_hash: str,
    refine_stream_fingerprint: str,
) -> tuple[str, str]:
    value = _verify_fingerprint(
        refined, "artifact_fingerprint", label="refined forecast"
    )
    _validate_curve_days(value, label="refined")
    if (
        value.get("schema") != REFINED_SCHEMA
        or value.get("authority") != "REFINED_CURVE_SHADOW_ONLY"
    ):
        raise ExactPublicationError("refined forecast authority mismatch")
    for field in (
        "execution_authority", "actual_outcomes_used", "may_update_ng_brain"
    ):
        if value.get(field) is not False:
            raise ExactPublicationError(
                f"refined forecast must keep {field}=false"
            )
    if value.get("blind_forecast_sha256") != blind_hash:
        raise ExactPublicationError(
            "refined forecast references a different blind file"
        )
    if value.get("refine_stream_fingerprint") != refine_stream_fingerprint:
        raise ExactPublicationError(
            "refined forecast references a different exact posterior stream"
        )
    return str(value["artifact_fingerprint"]), _sha256_bytes(refined_bytes)


def _validate_score(
    score: Mapping[str, Any],
    *,
    kind: str,
    forecast_hash: str,
    actual_fingerprint: str,
) -> dict[str, Any]:
    value = _verify_fingerprint(
        score, "artifact_fingerprint", label=f"{kind} score"
    )
    if (
        value.get("schema") != SCORE_SCHEMA
        or value.get("authority") != "OUTCOME_SCORING_ONLY"
    ):
        raise ExactPublicationError(f"{kind} score authority mismatch")
    if value.get("forecast_kind") != kind:
        raise ExactPublicationError(f"{kind} score forecast_kind mismatch")
    if value.get("forecast_sha256") != forecast_hash:
        raise ExactPublicationError(
            f"{kind} score references a different forecast file"
        )
    if value.get("actual_artifact_fingerprint") != actual_fingerprint:
        raise ExactPublicationError(
            f"{kind} score references a different actual substrate"
        )
    if value.get("actual_outcomes_used") is not True:
        raise ExactPublicationError(f"{kind} score must disclose outcome use")
    if (
        value.get("execution_authority") is not False
        or value.get("may_update_ng_brain") is not False
    ):
        raise ExactPublicationError(
            f"{kind} score cannot execute or update the brain"
        )
    _validate_dates(value.get("days"), label=f"{kind} score")
    return value


def _validate_comparison(
    comparison: Mapping[str, Any], *, blind_score_fp: str, refined_score_fp: str
) -> dict[str, Any]:
    value = _verify_fingerprint(
        comparison, "artifact_fingerprint", label="comparison"
    )
    if (
        value.get("schema") != COMPARISON_SCHEMA
        or value.get("authority") != "OUTCOME_SCORING_ONLY"
    ):
        raise ExactPublicationError("comparison authority mismatch")
    if value.get("blind_score_fingerprint") != blind_score_fp:
        raise ExactPublicationError(
            "comparison references a different blind score"
        )
    if value.get("refined_score_fingerprint") != refined_score_fp:
        raise ExactPublicationError(
            "comparison references a different refined score"
        )
    if value.get("actual_outcomes_used") is not True:
        raise ExactPublicationError("comparison must disclose outcome use")
    if (
        value.get("execution_authority") is not False
        or value.get("may_update_ng_brain") is not False
    ):
        raise ExactPublicationError("comparison cannot execute or update the brain")
    _validate_dates(value.get("days"), label="comparison")
    return value


def _validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    value = _verify_fingerprint(
        registry, "registry_fingerprint", label="G16 registry"
    )
    if value.get("schema") != REGISTRY_SCHEMA:
        raise ExactPublicationError("G16 registry schema mismatch")
    if value.get("source_group") != 15 or value.get("target_group") != 16:
        raise ExactPublicationError("G16 registry group mapping mismatch")
    if value.get("authority") != "G16_PRE_CUTOFF_SHADOW_TEST_ONLY":
        raise ExactPublicationError("G16 registry authority mismatch")
    for field in (
        "execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if value.get(field) is not False:
            raise ExactPublicationError(f"G16 registry must keep {field}=false")
    candidates = list(value.get("candidates") or [])
    if int(value.get("candidate_count") or 0) != len(candidates):
        raise ExactPublicationError("G16 registry candidate_count mismatch")
    identifiers = [str(row.get("proposal_id") or "") for row in candidates]
    if (
        any(not identifier for identifier in identifiers)
        or len(set(identifiers)) != len(identifiers)
    ):
        raise ExactPublicationError(
            "G16 registry has missing or duplicate candidate ids"
        )
    gate = dict(value.get("gate") or {})
    if bool(gate.get("g16_refinement_authorized")) != bool(candidates):
        raise ExactPublicationError(
            "G16 registry gate differs from candidate availability"
        )
    if gate.get("g16_outcome_access_authorized") is not False:
        raise ExactPublicationError("G16 outcome access must remain false")
    return value


def _validate_adjudication(
    adjudication: Mapping[str, Any],
    *,
    authorization: Mapping[str, Any],
    comparison_fp: str,
    blind_score_fp: str,
    refined_score_fp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = _verify_fingerprint(
        adjudication, "artifact_fingerprint", label="adjudication"
    )
    if (
        value.get("schema") != ADJUDICATION_SCHEMA
        or value.get("authority") != "LESSON_ADJUDICATION_ONLY"
    ):
        raise ExactPublicationError("adjudication authority mismatch")
    if value.get("actual_outcomes_used") is not True:
        raise ExactPublicationError("adjudication must disclose G15 outcome use")
    if (
        value.get("execution_authority") is not False
        or value.get("may_update_ng_brain") is not False
    ):
        raise ExactPublicationError(
            "adjudication cannot execute or update the brain"
        )
    source = dict(value.get("source") or {})
    if source.get("audit_fingerprint") != authorization.get(
        "daily_audit_fingerprint"
    ):
        raise ExactPublicationError(
            "adjudication references a different exact daily audit"
        )
    if source.get("proposal_fingerprint") != authorization.get(
        "lesson_proposal_fingerprint"
    ):
        raise ExactPublicationError(
            "adjudication references different exact lesson proposals"
        )
    if source.get("comparison_fingerprint") != comparison_fp:
        raise ExactPublicationError(
            "adjudication references a different comparison"
        )
    if source.get("blind_score_fingerprint") != blind_score_fp:
        raise ExactPublicationError(
            "adjudication references a different blind score"
        )
    if source.get("refined_score_fingerprint") != refined_score_fp:
        raise ExactPublicationError(
            "adjudication references a different refined score"
        )
    registry = _validate_registry(
        dict(value.get("g16_shadow_registry") or {})
    )
    eligible = {
        str(row.get("id") or "")
        for row in value.get("adjudications") or []
        if bool((row.get("g16_shadow_test") or {}).get("eligible"))
    }
    registry_ids = {
        str(row.get("proposal_id") or "")
        for row in registry.get("candidates") or []
    }
    if eligible != registry_ids:
        raise ExactPublicationError(
            "G16 registry differs from eligible adjudications"
        )
    return value, registry


def _actual_core(actual: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if (
        actual.get("market") != "NG"
        or int(actual.get("n_days") or 0) != len(G15_DATES)
    ):
        raise ExactPublicationError(
            f"{label}: actual substrate must contain 12 NG sessions"
        )
    anchor = dict(actual.get("anchor") or {})
    if str(anchor.get("date") or "") != "20260313":
        raise ExactPublicationError(f"{label}: anchor must be 20260313")
    days = _validate_dates(actual.get("days"), label=label)
    for row in days:
        curve = list(row.get("curve_2h") or [])
        if (
            len(curve) != len(GRID_HOURS)
            or tuple(int(point[0]) for point in curve) != GRID_HOURS
        ):
            raise ExactPublicationError(
                f"{label}:{row['date']}: actual curve grid mismatch"
            )
    return {
        "market": actual.get("market"),
        "anchor": anchor,
        "seams": copy.deepcopy(actual.get("seams") or []),
        "n_days": int(actual.get("n_days") or 0),
        "rolls": copy.deepcopy(actual.get("rolls") or []),
        "roll_adjusted": actual.get("roll_adjusted"),
        "days": days,
    }


def _validate_render_rt(
    rt: Mapping[str, Any], *, tag: str, expected_core_fp: str
) -> str:
    if rt.get("tag") != tag:
        raise ExactPublicationError(f"{tag}: render RT tag mismatch")
    core_fp = _fingerprint(_actual_core(rt, label=f"{tag} render RT"))
    if core_fp != expected_core_fp:
        raise ExactPublicationError(
            f"{tag}: render uses a different actual substrate"
        )
    return core_fp


def _png_receipt(path: Path, *, expected_name: str) -> dict[str, Any]:
    if path.name != expected_name:
        raise ExactPublicationError(
            f"render filename must be {expected_name}"
        )
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExactPublicationError(f"render is unreadable: {path}") from error
    if len(data) < MIN_RENDER_BYTES:
        raise ExactPublicationError(
            f"render is too small to be a canonical plot: {path}"
        )
    if data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ExactPublicationError(
            f"render is not a valid PNG header: {path}"
        )
    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise ExactPublicationError(f"render has invalid dimensions: {path}")
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
    authorization: Mapping[str, Any],
    blind: Mapping[str, Any],
    refined: Mapping[str, Any],
    actual: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    blind_rt: Mapping[str, Any],
    refined_rt: Mapping[str, Any],
    blind_bytes: bytes,
    refined_bytes: bytes,
    blind_png: Path,
    refined_png: Path,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            authorization, blind, refined, actual, blind_score, refined_score,
            comparison, adjudication, blind_rt, refined_rt,
        )
    )
    blind_hash = _validate_blind(blind, blind_bytes)
    auth = _validate_authorization(authorization, blind_bytes)
    refined_fp, refined_hash = _validate_refined(
        refined,
        refined_bytes,
        blind_hash=blind_hash,
        refine_stream_fingerprint=str(auth["refine_stream_fingerprint"]),
    )
    actual_fp = _fingerprint(actual)
    actual_core_fp = _fingerprint(_actual_core(actual, label="scoring actual"))
    blind_score_value = _validate_score(
        blind_score,
        kind="blind",
        forecast_hash=blind_hash,
        actual_fingerprint=actual_fp,
    )
    refined_score_value = _validate_score(
        refined_score,
        kind="refined",
        forecast_hash=refined_hash,
        actual_fingerprint=actual_fp,
    )
    comparison_value = _validate_comparison(
        comparison,
        blind_score_fp=str(blind_score_value["artifact_fingerprint"]),
        refined_score_fp=str(refined_score_value["artifact_fingerprint"]),
    )
    adjudication_value, registry = _validate_adjudication(
        adjudication,
        authorization=auth,
        comparison_fp=str(comparison_value["artifact_fingerprint"]),
        blind_score_fp=str(blind_score_value["artifact_fingerprint"]),
        refined_score_fp=str(refined_score_value["artifact_fingerprint"]),
    )
    _validate_render_rt(
        blind_rt, tag="g15_mbo_blind", expected_core_fp=actual_core_fp
    )
    _validate_render_rt(
        refined_rt, tag="g15_mbo_refined", expected_core_fp=actual_core_fp
    )
    blind_render = _png_receipt(
        blind_png, expected_name="g15_mbo_blind_continuous.png"
    )
    refined_render = _png_receipt(
        refined_png, expected_name="g15_mbo_refined_continuous.png"
    )
    blind_render.update(
        {
            "tag": "g15_mbo_blind",
            "forecast_sha256": blind_hash,
            "rt_json_fingerprint": _fingerprint(blind_rt),
            "actual_core_fingerprint": actual_core_fp,
        }
    )
    refined_render.update(
        {
            "tag": "g15_mbo_refined",
            "forecast_sha256": refined_hash,
            "refined_curve_fingerprint": refined_fp,
            "rt_json_fingerprint": _fingerprint(refined_rt),
            "actual_core_fingerprint": actual_core_fp,
        }
    )
    stand_down_days = list(auth.get("stand_down_days") or [])
    g16_shadow_ready = bool(
        (registry.get("gate") or {}).get("g16_refinement_authorized")
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": "G15_EXACT_PUBLICATION_AUDIT_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "exact_g15_publication_complete": True,
        "outcome_scoring_complete": True,
        "lesson_adjudication_complete": True,
        "continuous_rt_renders_complete": True,
        "exact_refinement_authorization_fingerprint": auth[
            "authorization_fingerprint"
        ],
        "exact_replay_completion_fingerprint": auth[
            "exact_replay_completion_fingerprint"
        ],
        "manifest_fingerprint": auth["manifest_fingerprint"],
        "prepared_corpus_fingerprint": auth["prepared_corpus_fingerprint"],
        "anchor_fingerprint": auth["anchor_fingerprint"],
        "blind_prior_fingerprint": auth["blind_prior_fingerprint"],
        "refine_stream_fingerprint": auth["refine_stream_fingerprint"],
        "blind_forecast_sha256": blind_hash,
        "refined_forecast_sha256": refined_hash,
        "refined_curve_fingerprint": refined_fp,
        "actual_artifact_fingerprint": actual_fp,
        "actual_core_fingerprint": actual_core_fp,
        "blind_score_fingerprint": blind_score_value["artifact_fingerprint"],
        "refined_score_fingerprint": refined_score_value[
            "artifact_fingerprint"
        ],
        "comparison_fingerprint": comparison_value["artifact_fingerprint"],
        "lesson_adjudication_fingerprint": adjudication_value[
            "artifact_fingerprint"
        ],
        "daily_audit_fingerprint": auth["daily_audit_fingerprint"],
        "lesson_proposal_fingerprint": auth["lesson_proposal_fingerprint"],
        "stand_down_days": stand_down_days,
        "renders": {"blind": blind_render, "refined": refined_render},
        "g16_shadow_registry": {
            "registry_fingerprint": registry["registry_fingerprint"],
            "candidate_count": registry["candidate_count"],
            "candidate_ids": [
                str(row["proposal_id"])
                for row in registry.get("candidates") or []
            ],
            "pre_cutoff_shadow_refinement_authorized": g16_shadow_ready,
            "g16_outcome_access_authorized": False,
            "may_change_g16_blind_prior": False,
            "may_update_ng_brain": False,
        },
        "authorized_next_stages": (
            [
                "ng_g16_blind_wall",
                "ng_g16_shadow_gate",
                "chronological G16 SHADOW refinement",
            ]
            if g16_shadow_ready
            else [
                "G16 baseline microstructure replay with no carried G15 lesson candidates"
            ]
        ),
        "note": (
            "Exact matched L1+MBO G15 provenance remains attached through the "
            "refined curve, outcome scoring, conservative lesson adjudication, "
            "and both canonical continuous_rt renders. Only pre-cutoff G16 "
            "SHADOW testing may follow; G16 outcomes and live execution remain "
            "forbidden."
        ),
    }
    result["completion_fingerprint"] = _fingerprint(result)
    if (
        authorization, blind, refined, actual, blind_score, refined_score,
        comparison, adjudication, blind_rt, refined_rt,
    ) != originals:
        raise ExactPublicationError(
            "publication validation mutated a source artifact"
        )
    validate_completion(result)
    return result


def validate_completion(completion: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(
        completion, "completion_fingerprint", label="publication completion"
    )
    if (
        value.get("schema") != SCHEMA
        or value.get("status") not in {READY, READY_WITH_STAND_DOWNS}
    ):
        raise ExactPublicationError("publication completion is not ready")
    if value.get("authority") != "G15_EXACT_PUBLICATION_AUDIT_ONLY":
        raise ExactPublicationError("publication completion authority mismatch")
    for field in (
        "execution_authority", "may_change_blind_prior",
        "may_change_blind_forecast", "may_change_posterior",
        "may_update_ng_brain",
    ):
        if value.get(field) is not False:
            raise ExactPublicationError(
                f"publication completion must keep {field}=false"
            )
    for field in (
        "actual_outcomes_used", "exact_g15_publication_complete",
        "outcome_scoring_complete", "lesson_adjudication_complete",
        "continuous_rt_renders_complete",
    ):
        if value.get(field) is not True:
            raise ExactPublicationError(
                f"publication completion must keep {field}=true"
            )
    renders = dict(value.get("renders") or {})
    if set(renders) != {"blind", "refined"}:
        raise ExactPublicationError(
            "publication completion must contain blind and refined renders"
        )
    for name, expected in (
        ("blind", "g15_mbo_blind_continuous.png"),
        ("refined", "g15_mbo_refined_continuous.png"),
    ):
        row = dict(renders[name])
        if (
            row.get("filename") != expected
            or int(row.get("size_bytes") or 0) < MIN_RENDER_BYTES
        ):
            raise ExactPublicationError(f"{name} render receipt is invalid")
        if (
            int(row.get("width_px") or 0) <= 0
            or int(row.get("height_px") or 0) <= 0
        ):
            raise ExactPublicationError(f"{name} render dimensions are invalid")
    registry = dict(value.get("g16_shadow_registry") or {})
    if registry.get("g16_outcome_access_authorized") is not False:
        raise ExactPublicationError(
            "publication completion cannot authorize G16 outcomes"
        )
    if (
        registry.get("may_change_g16_blind_prior") is not False
        or registry.get("may_update_ng_brain") is not False
    ):
        raise ExactPublicationError(
            "publication completion cannot mutate G16 prior or ng_brain"
        )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _png_fixture(width: int = 1800, height: int = 500) -> bytes:
    header = (
        PNG_SIGNATURE
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )
    return (
        header
        + b"\x08\x02\x00\x00\x00"
        + b"x" * (MIN_RENDER_BYTES - len(header) - 5)
    )


def _fixture(tmp: Path) -> dict[str, Any]:
    days = []
    actual_days = []
    running = 0
    for index, date in enumerate(G15_DATES):
        values = [0] + [
            10 * (index + 1) * point
            for point in range(1, len(GRID_HOURS))
        ]
        refined_values = [0] + [
            value + 5 * point
            for point, value in enumerate(values[1:], 1)
        ]
        common = {"date": date, "dow": "X", "overnight_gap_usd": 0}
        days.append(
            {
                **common,
                "guess_curve": [
                    [hour, value]
                    for hour, value in zip(GRID_HOURS, values)
                ],
                "guessed_net_usd": values[-1],
            }
        )
        running += refined_values[-1]
        actual_days.append(
            {
                "date": date,
                "dow": "X",
                "group": 15,
                "open": 3.0,
                "close": 3.0 + refined_values[-1] / 10000,
                "net_usd": refined_values[-1],
                "overnight_gap_usd": 0,
                "cum_from_anchor_close_usd": running,
                "curve_2h": [
                    [hour, value]
                    for hour, value in zip(GRID_HOURS, refined_values)
                ],
            }
        )
    blind = {
        "group": 15,
        "tag": "g15",
        "brain_version": "test",
        "days": days,
    }
    blind_bytes = (json.dumps(blind, indent=2) + "\n").encode()
    blind_hash = _sha256_bytes(blind_bytes)
    refined = copy.deepcopy(blind)
    refined.update(
        {
            "schema": REFINED_SCHEMA,
            "tag": "g15_mbo_refined",
            "authority": "REFINED_CURVE_SHADOW_ONLY",
            "execution_authority": False,
            "actual_outcomes_used": False,
            "may_update_ng_brain": False,
            "blind_forecast_sha256": blind_hash,
            "refine_stream_fingerprint": "stream-fp",
        }
    )
    for day, actual_day in zip(refined["days"], actual_days):
        day["guess_curve"] = copy.deepcopy(actual_day["curve_2h"])
        day["guessed_net_usd"] = actual_day["net_usd"]
    refined["artifact_fingerprint"] = _fingerprint(refined)
    refined_bytes = (
        json.dumps(refined, indent=2, sort_keys=True) + "\n"
    ).encode()
    actual = {
        "market": "NG",
        "tag": "g15",
        "anchor": {
            "date": "20260313",
            "price": 3.132,
            "last_hour_dir": "down",
        },
        "seams": [],
        "n_days": len(G15_DATES),
        "rolls": [],
        "roll_adjusted": False,
        "days": actual_days,
    }
    actual_fp = _fingerprint(actual)
    authorization = {
        "schema": AUTH_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": "EXACT_G15_REFINEMENT_READY",
        "authority": "EXACT_G15_REFINEMENT_AUTHORIZATION_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "g16_authorized": False,
        "exact_replay_completion_fingerprint": "replay-completion-fp",
        "pipeline_fingerprint": "pipeline-fp",
        "replay_fingerprint": "replay-fp",
        "manifest_fingerprint": "manifest-fp",
        "prepared_corpus_fingerprint": "prepared-fp",
        "anchor_fingerprint": "anchor-fp",
        "blind_prior_fingerprint": "prior-fp",
        "blind_forecast_sha256": blind_hash,
        "refine_stream_fingerprint": "stream-fp",
        "daily_audit_fingerprint": "audit-fp",
        "lesson_proposal_fingerprint": "proposal-fp",
        "emitted_feature_states": 12,
        "posterior_outputs": 12,
        "days": list(G15_DATES),
        "stand_down_days": [],
        "authorized_next_stages": [],
        "note": "fixture",
    }
    authorization["authorization_fingerprint"] = _fingerprint(authorization)

    def score(kind: str, forecast_hash: str) -> dict[str, Any]:
        value = {
            "schema": SCORE_SCHEMA,
            "market": "NG",
            "group": 15,
            "tag": f"g15_mbo_{kind}",
            "forecast_kind": kind,
            "authority": "OUTCOME_SCORING_ONLY",
            "execution_authority": False,
            "actual_outcomes_used": True,
            "may_update_ng_brain": False,
            "forecast_sha256": forecast_hash,
            "actual_artifact_fingerprint": actual_fp,
            "days": [{"date": day} for day in G15_DATES],
            "block": {},
            "note": "fixture",
        }
        value["artifact_fingerprint"] = _fingerprint(value)
        return value

    blind_score = score("blind", blind_hash)
    refined_score = score("refined", _sha256_bytes(refined_bytes))
    comparison = {
        "schema": COMPARISON_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "OUTCOME_SCORING_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "blind_score_fingerprint": blind_score["artifact_fingerprint"],
        "refined_score_fingerprint": refined_score["artifact_fingerprint"],
        "days": [{"date": day} for day in G15_DATES],
        "block": {},
        "lesson_gate": {"may_update_ng_brain": False},
        "note": "fixture",
    }
    comparison["artifact_fingerprint"] = _fingerprint(comparison)
    evidence = {
        "id": "g15_mbo.signed_flow",
        "g16_shadow_test": {"eligible": True},
        "may_update_ng_brain": False,
    }
    evidence["evidence_fingerprint"] = _fingerprint(evidence)
    registry = {
        "schema": REGISTRY_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "candidate_count": 1,
        "candidates": [{"proposal_id": "g15_mbo.signed_flow"}],
        "gate": {
            "g16_refinement_authorized": True,
            "g16_outcome_access_authorized": False,
        },
    }
    registry["registry_fingerprint"] = _fingerprint(registry)
    adjudication = {
        "schema": ADJUDICATION_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "LESSON_ADJUDICATION_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "source": {
            "audit_fingerprint": "audit-fp",
            "proposal_fingerprint": "proposal-fp",
            "comparison_fingerprint": comparison["artifact_fingerprint"],
            "blind_score_fingerprint": blind_score["artifact_fingerprint"],
            "refined_score_fingerprint": refined_score[
                "artifact_fingerprint"
            ],
        },
        "method": {},
        "adjudications": [evidence],
        "g16_shadow_registry": registry,
        "note": "fixture",
    }
    adjudication["artifact_fingerprint"] = _fingerprint(adjudication)
    blind_rt = copy.deepcopy(actual)
    blind_rt["tag"] = "g15_mbo_blind"
    refined_rt = copy.deepcopy(actual)
    refined_rt["tag"] = "g15_mbo_refined"
    blind_png = tmp / "g15_mbo_blind_continuous.png"
    refined_png = tmp / "g15_mbo_refined_continuous.png"
    blind_png.write_bytes(_png_fixture())
    refined_png.write_bytes(_png_fixture())
    return locals()


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        fixture = _fixture(Path(directory))
        result = build_completion(
            authorization=fixture["authorization"],
            blind=fixture["blind"],
            refined=fixture["refined"],
            actual=fixture["actual"],
            blind_score=fixture["blind_score"],
            refined_score=fixture["refined_score"],
            comparison=fixture["comparison"],
            adjudication=fixture["adjudication"],
            blind_rt=fixture["blind_rt"],
            refined_rt=fixture["refined_rt"],
            blind_bytes=fixture["blind_bytes"],
            refined_bytes=fixture["refined_bytes"],
            blind_png=fixture["blind_png"],
            refined_png=fixture["refined_png"],
        )
        assert result["status"] == READY
        assert result["g16_shadow_registry"][
            "pre_cutoff_shadow_refinement_authorized"
        ] is True
        validate_completion(result)
    print("[ng_g15_exact_publication_gate] selftest PASS")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    parser = argparse.ArgumentParser(
        description=(
            "Close exact-basis G15 publication and authorize only pre-cutoff "
            "G16 SHADOW testing"
        )
    )
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--blind", type=Path, required=True)
    parser.add_argument("--refined", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--blind-score", type=Path, required=True)
    parser.add_argument("--refined-score", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--blind-render-rt", type=Path, required=True)
    parser.add_argument("--refined-render-rt", type=Path, required=True)
    parser.add_argument("--blind-render-png", type=Path, required=True)
    parser.add_argument("--refined-render-png", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    result = build_completion(
        authorization=load(args.authorization),
        blind=load(args.blind),
        refined=load(args.refined),
        actual=load(args.actual),
        blind_score=load(args.blind_score),
        refined_score=load(args.refined_score),
        comparison=load(args.comparison),
        adjudication=load(args.adjudication),
        blind_rt=load(args.blind_render_rt),
        refined_rt=load(args.refined_render_rt),
        blind_bytes=args.blind.read_bytes(),
        refined_bytes=args.refined.read_bytes(),
        blind_png=args.blind_render_png,
        refined_png=args.refined_render_png,
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "out": str(args.out),
                "g16_shadow_candidates": result[
                    "g16_shadow_registry"
                ]["candidate_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
