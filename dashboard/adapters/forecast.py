"""Read-only NG forecast authority-chain adapter for Mission Control.

The dashboard is a presentation plane only. This adapter reads locked blind,
causal-posterior, refined-curve, and coach artifacts; validates them through the
canonical research modules; and reports missing or invalid artifacts explicitly.
It never reads target outcomes, changes a posterior, writes a signal-core file,
or grants execution authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import paths

SCHEMA = "ng_dashboard_forecast_snapshot.v1"
DAY_SCHEMA = "ng_dashboard_forecast_day.v1"
AUTHORITY = "DASHBOARD_READ_ONLY_PRESENTATION"
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
G16_DATES = (
    "20260329", "20260330", "20260331", "20260401", "20260402", "20260405",
    "20260406", "20260407", "20260408", "20260409", "20260410",
)


class ForecastAdapterError(ValueError):
    """Raised when a requested dashboard forecast view is unsafe or contradictory."""


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    candidates: tuple[str, ...]


_SPECS: dict[int, dict[str, ArtifactSpec]] = {
    15: {
        "blind": ArtifactSpec("blind", ("forecasts/grp15.json",)),
        "refined": ArtifactSpec("refined", ("forecasts/grp15_mbo_refined.json",)),
        "posterior": ArtifactSpec(
            "posterior", ("renders/ng_refine_s95/g15_mbo_refine_stream.json",)
        ),
        "coach": ArtifactSpec(
            "coach",
            (
                "renders/ng_refine_s95/g15_mbo_coach_stream.json",
                "renders/ng_refine_s95/g15_coach_stream.json",
            ),
        ),
        "blind_render": ArtifactSpec(
            "blind_render", ("renders/ng_refine_s95/g15_mbo_blind_continuous.png",)
        ),
        "refined_render": ArtifactSpec(
            "refined_render", ("renders/ng_refine_s95/g15_mbo_refined_continuous.png",)
        ),
    },
    16: {
        "blind": ArtifactSpec("blind", ("forecasts/grp16.json",)),
        "refined": ArtifactSpec("refined", ("forecasts/grp16_mbo_refined.json",)),
        "posterior": ArtifactSpec(
            "posterior", ("renders/ng_refine_s95/g16_shadow_posterior_stream.json",)
        ),
        "coach": ArtifactSpec(
            "coach",
            (
                "renders/ng_refine_s95/g16_mbo_coach_stream.json",
                "renders/ng_refine_s95/g16_coach_stream.json",
            ),
        ),
        "blind_render": ArtifactSpec(
            "blind_render", ("renders/ng_refine_s95/g16_mbo_blind_continuous.png",)
        ),
        "refined_render": ArtifactSpec(
            "refined_render", ("renders/ng_refine_s95/g16_mbo_refined_continuous.png",)
        ),
    },
}


def _root(root: str | os.PathLike[str] | None = None) -> Path:
    configured = root or os.environ.get("MARKETS_DASH_FORECAST_ROOT") or paths.KALSHI_RESEARCH
    return Path(configured).resolve()


def _dates(group: int) -> tuple[str, ...]:
    if group == 15:
        return G15_DATES
    if group == 16:
        return G16_DATES
    raise ForecastAdapterError("group must be 15 or 16")


def _safe_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ForecastAdapterError(f"artifact path escapes forecast root: {relative}") from error
    return candidate


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _find(spec: ArtifactSpec, root: Path) -> tuple[Path | None, list[str]]:
    tried: list[str] = []
    for relative in spec.candidates:
        path = _safe_path(root, relative)
        tried.append(relative)
        if path.is_file():
            return path, tried
    return None, tried


def _read_json(spec: ArtifactSpec, root: Path) -> dict[str, Any]:
    path, tried = _find(spec, root)
    if path is None:
        return {
            "available": False,
            "status": "MISSING",
            "path": None,
            "candidates_tried": tried,
            "error": None,
        }
    raw = path.read_bytes()
    relative = str(path.relative_to(root))
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "status": "CORRUPT",
            "path": relative,
            "candidates_tried": tried,
            "size_bytes": len(raw),
            "sha256": _sha256_bytes(raw),
            "error": f"{type(error).__name__}: {error}",
        }
    return {
        "available": True,
        "status": "PRESENT",
        "path": relative,
        "candidates_tried": tried,
        "size_bytes": len(raw),
        "sha256": _sha256_bytes(raw),
        "payload": payload,
        "error": None,
    }


def _read_render(spec: ArtifactSpec, root: Path) -> dict[str, Any]:
    path, tried = _find(spec, root)
    if path is None:
        return {
            "available": False,
            "status": "MISSING",
            "path": None,
            "candidates_tried": tried,
            "size_bytes": 0,
        }
    size = path.stat().st_size
    relative = str(path.relative_to(root))
    if size <= 0:
        return {
            "available": False,
            "status": "CORRUPT",
            "path": relative,
            "candidates_tried": tried,
            "size_bytes": size,
        }
    return {
        "available": True,
        "status": "PRESENT",
        "path": relative,
        "candidates_tried": tried,
        "size_bytes": size,
    }


def _validate_curve_shape(forecast: Mapping[str, Any], group: int, *, blind: bool) -> None:
    if int(forecast.get("group") or 0) != group:
        raise ForecastAdapterError(f"forecast group must be {group}")
    days = list(forecast.get("days") or [])
    expected = list(_dates(group))
    observed = [str(day.get("date") or "") for day in days]
    if observed != expected:
        raise ForecastAdapterError(f"forecast must contain canonical G{group} days in order")
    if blind:
        prohibited = {
            "actual", "actuals", "actual_curve", "actual_outcomes", "outcome",
            "score", "scorecard", "scoring", "comparison",
        }
        for key in forecast:
            if str(key).lower() in prohibited:
                raise ForecastAdapterError(f"blind forecast contains prohibited outcome field: {key}")
    for day in days:
        date = str(day.get("date") or "")
        curve = list(day.get("guess_curve") or [])
        if len(curve) != len(GRID_HOURS):
            raise ForecastAdapterError(f"{date}: forecast curve must have 13 points")
        if tuple(int(point[0]) for point in curve) != GRID_HOURS:
            raise ForecastAdapterError(f"{date}: forecast curve uses a noncanonical grid")
        try:
            values = [float(point[1]) for point in curve]
        except (TypeError, ValueError, IndexError) as error:
            raise ForecastAdapterError(f"{date}: forecast curve contains invalid values") from error
        if values[0] != 0.0:
            raise ForecastAdapterError(f"{date}: cumulative curve must begin at zero")


def _research_import(name: str):
    if paths.KALSHI_RESEARCH not in sys.path:
        sys.path.insert(0, paths.KALSHI_RESEARCH)
    return __import__(name)


def _validate_blind(payload: Mapping[str, Any], group: int) -> None:
    _validate_curve_shape(payload, group, blind=True)


def _validate_refined(payload: Mapping[str, Any], group: int, blind: Mapping[str, Any]) -> None:
    _validate_curve_shape(payload, group, blind=False)
    module_name = "ng_g15_curve_adapter" if group == 15 else "ng_g16_curve_adapter"
    module = _research_import(module_name)
    module.validate_refined_forecast(payload, blind_forecast=blind)


def _validate_posterior(payload: Mapping[str, Any], group: int) -> dict[str, Any]:
    module = _research_import("ng_coach_voxa_adapter")
    clean = module.validate_posterior_stream(payload)
    if int(clean.get("group") or 0) != group:
        raise ForecastAdapterError("posterior stream group mismatch")
    clean.pop("_source_stream_fingerprint", None)
    return clean


def _validate_coach(payload: Mapping[str, Any], group: int) -> dict[str, Any]:
    module = _research_import("ng_coach_voxa_adapter")
    clean = module.validate_coach_stream(payload)
    if int(clean.get("group") or 0) != group:
        raise ForecastAdapterError("coach stream group mismatch")
    return clean


def _mark_invalid(record: dict[str, Any], error: Exception) -> dict[str, Any]:
    clean = {key: value for key, value in record.items() if key != "payload"}
    clean.update(
        available=False,
        status="INVALID",
        error=f"{type(error).__name__}: {error}",
    )
    return clean


def _blind_summary(record: dict[str, Any], group: int) -> dict[str, Any]:
    if not record["available"]:
        return record
    try:
        _validate_blind(record["payload"], group)
    except Exception as error:
        return _mark_invalid(record, error)
    payload = record["payload"]
    return {
        **{key: value for key, value in record.items() if key != "payload"},
        "tag": payload.get("tag"),
        "kind": payload.get("kind"),
        "brain_version": payload.get("brain_version"),
        "n_days": len(payload.get("days") or []),
        "anchor": copy.deepcopy(payload.get("anchor")),
        "immutable_source": True,
    }


def _refined_summary(
    record: dict[str, Any], group: int, blind_payload: Mapping[str, Any] | None
) -> dict[str, Any]:
    if not record["available"]:
        return record
    if blind_payload is None:
        return _mark_invalid(record, ForecastAdapterError("refined curve requires a valid blind forecast"))
    try:
        _validate_refined(record["payload"], group, blind_payload)
    except Exception as error:
        return _mark_invalid(record, error)
    payload = record["payload"]
    audits = [dict(day.get("refinement_audit") or {}) for day in payload.get("days") or []]
    return {
        **{key: value for key, value in record.items() if key != "payload"},
        "schema": payload.get("schema"),
        "tag": payload.get("tag"),
        "authority": payload.get("authority"),
        "calibration_status": payload.get("calibration_status"),
        "n_days": len(payload.get("days") or []),
        "days_with_usable_posterior": sum(int(row.get("outputs_used") or 0) > 0 for row in audits),
        "max_abs_endpoint_adjustment_usd": max(
            [abs(int(row.get("endpoint_adjustment_usd") or 0)) for row in audits] or [0]
        ),
        "outcome_blind": True,
    }


def _posterior_summary(record: dict[str, Any], group: int) -> dict[str, Any]:
    if not record["available"]:
        return record
    try:
        clean = _validate_posterior(record["payload"], group)
    except Exception as error:
        return _mark_invalid(record, error)
    outputs = list(clean.get("outputs") or [])
    latest_by_day: dict[str, dict[str, Any]] = {}
    for output in outputs:
        latest_by_day[str(output["session_day"])] = {
            "session_day": output["session_day"],
            "sequence": output["sequence"],
            "as_of_event_s": output["as_of_event_s"],
            "status": output["status"],
            "blind_prior": copy.deepcopy(output.get("blind_prior")),
            "posterior": copy.deepcopy(output.get("posterior")),
            "stand_down_reasons": sorted(
                set(
                    ((output.get("availability") or {}).get("stand_down_reasons") or [])
                    if group == 15
                    else (output.get("stand_down_reasons") or [])
                )
            ),
            "output_fingerprint": output.get("output_fingerprint"),
        }
    return {
        **{key: value for key, value in record.items() if key != "payload"},
        "schema": clean.get("schema"),
        "authority": clean.get("authority"),
        "n_outputs": len(outputs),
        "n_updated": sum(output.get("status") == "UPDATED" for output in outputs),
        "n_stand_down": sum(output.get("status") == "STAND_DOWN" for output in outputs),
        "latest_by_day": {day: latest_by_day[day] for day in sorted(latest_by_day)},
        "outcomes_used": False,
    }


def _coach_summary(record: dict[str, Any], group: int) -> dict[str, Any]:
    if not record["available"]:
        return record
    try:
        clean = _validate_coach(record["payload"], group)
    except Exception as error:
        return _mark_invalid(record, error)
    messages = list(clean.get("messages") or [])
    latest_by_day: dict[str, dict[str, Any]] = {}
    for message in messages:
        latest_by_day[str(message["session_day"])] = {
            "session_day": message["session_day"],
            "sequence": message["sequence"],
            "event_type": message["event_type"],
            "priority": message["priority"],
            "top_direction": message["top_direction"],
            "top_probability": message["top_probability"],
            "stand_down_reasons": copy.deepcopy(message.get("stand_down_reasons") or []),
            "display_text": message.get("display_text"),
            "transport_status": message.get("transport_status"),
            "message_fingerprint": message.get("message_fingerprint"),
        }
    return {
        **{key: value for key, value in record.items() if key != "payload"},
        "schema": clean.get("schema"),
        "authority": clean.get("authority"),
        "n_messages": len(messages),
        "n_suppressed": int(clean.get("n_suppressed") or 0),
        "latest_by_day": {day: latest_by_day[day] for day in sorted(latest_by_day)},
        "transport_status": clean.get("transport_status"),
        "delivery_authority": False,
    }


def _raw_payload(record: dict[str, Any]) -> Mapping[str, Any] | None:
    return record.get("payload") if record.get("available") else None


def summary(group: int, *, root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Return the locked blind -> posterior -> refined -> coach presentation chain."""
    group = int(group)
    _dates(group)
    base = _root(root)
    specs = _SPECS[group]
    raw_blind = _read_json(specs["blind"], base)
    blind = _blind_summary(raw_blind, group)
    blind_payload = _raw_payload(raw_blind) if blind.get("available") else None
    raw_refined = _read_json(specs["refined"], base)
    raw_posterior = _read_json(specs["posterior"], base)
    raw_coach = _read_json(specs["coach"], base)
    artifacts = {
        "blind": blind,
        "posterior": _posterior_summary(raw_posterior, group),
        "refined": _refined_summary(raw_refined, group, blind_payload),
        "coach": _coach_summary(raw_coach, group),
        "blind_render": _read_render(specs["blind_render"], base),
        "refined_render": _read_render(specs["refined_render"], base),
    }
    invalid = sorted(
        name for name, row in artifacts.items()
        if row.get("status") in {"CORRUPT", "INVALID"}
    )
    unavailable = sorted(name for name, row in artifacts.items() if not row.get("available"))
    if not artifacts["blind"].get("available") or invalid:
        stage = "BLOCKED"
    elif artifacts["coach"].get("available"):
        stage = "COACH_READY"
    elif artifacts["refined"].get("available"):
        stage = "REFINED_READY"
    elif artifacts["posterior"].get("available"):
        stage = "POSTERIOR_READY"
    else:
        stage = "BLIND_ONLY"
    current_states = list((artifacts["posterior"].get("latest_by_day") or {}).values())
    stand_down = [row for row in current_states if row.get("status") == "STAND_DOWN"]
    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "market": "NG",
        "group": group,
        "stage": stage,
        "signal_status": "STAND_DOWN" if stand_down else "AVAILABLE",
        "one_signal_authority_chain": [
            "immutable_blind_prior",
            "authorized_causal_posterior",
            "outcome_blind_refined_curve",
            "material_change_only_coach_presentation",
        ],
        "artifacts": artifacts,
        "unavailable_artifacts": unavailable,
        "invalid_artifacts": invalid,
        "stand_down_days": [row["session_day"] for row in stand_down],
        "actual_outcomes_loaded": False,
        "score_artifacts_loaded": False,
        "execution_authority": False,
        "may_update_ng_brain": False,
        "may_change_posterior": False,
        "may_change_blind_prior": False,
        "delivery_authority": False,
        "note": (
            "Dashboard presentation only. Missing files remain visible; actual curves and outcome "
            "scorecards are deliberately outside this authority-chain endpoint."
        ),
    }


def _artifact_payload(group: int, key: str, root: Path) -> Mapping[str, Any] | None:
    record = _read_json(_SPECS[group][key], root)
    return record.get("payload") if record.get("available") else None


def day_snapshot(
    group: int, day: str, *, root: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Return one session's blind/refined/posterior/coach view without outcomes."""
    group = int(group)
    if day not in _dates(group):
        raise ForecastAdapterError(f"{day} is not a canonical G{group} session")
    base = _root(root)
    chain = summary(group, root=base)
    blind_payload = _artifact_payload(group, "blind", base)
    refined_payload = _artifact_payload(group, "refined", base)
    posterior_payload = _artifact_payload(group, "posterior", base)
    coach_payload = _artifact_payload(group, "coach", base)
    blind_day = None
    if blind_payload is not None and chain["artifacts"]["blind"].get("available"):
        blind_day = next(
            (copy.deepcopy(row) for row in blind_payload.get("days") or [] if row.get("date") == day),
            None,
        )
    refined_day = None
    if refined_payload is not None and chain["artifacts"]["refined"].get("available"):
        refined_day = next(
            (copy.deepcopy(row) for row in refined_payload.get("days") or [] if row.get("date") == day),
            None,
        )
    posterior_outputs: list[dict[str, Any]] = []
    if posterior_payload is not None and chain["artifacts"]["posterior"].get("available"):
        clean = _validate_posterior(posterior_payload, group)
        posterior_outputs = [
            copy.deepcopy(row) for row in clean.get("outputs") or []
            if row.get("session_day") == day
        ]
    coach_messages: list[dict[str, Any]] = []
    if coach_payload is not None and chain["artifacts"]["coach"].get("available"):
        clean = _validate_coach(coach_payload, group)
        coach_messages = [
            copy.deepcopy(row) for row in clean.get("messages") or []
            if row.get("session_day") == day
        ]
    latest_posterior = posterior_outputs[-1] if posterior_outputs else None
    latest_coach = coach_messages[-1] if coach_messages else None
    return {
        "schema": DAY_SCHEMA,
        "authority": AUTHORITY,
        "market": "NG",
        "group": group,
        "session_day": day,
        "stage": chain["stage"],
        "blind": blind_day,
        "refined": refined_day,
        "posterior_outputs": posterior_outputs,
        "latest_posterior": latest_posterior,
        "coach_messages": coach_messages,
        "latest_coach_message": latest_coach,
        "stand_down_reasons": [] if latest_posterior is None else sorted(
            set(
                ((latest_posterior.get("availability") or {}).get("stand_down_reasons") or [])
                if group == 15
                else (latest_posterior.get("stand_down_reasons") or [])
            )
        ),
        "render_urls": {
            "blind": (
                f"/api/v1/ng/render/{group}/blind"
                if chain["artifacts"]["blind_render"].get("available") else None
            ),
            "refined": (
                f"/api/v1/ng/render/{group}/refined"
                if chain["artifacts"]["refined_render"].get("available") else None
            ),
        },
        "actual_outcomes_loaded": False,
        "execution_authority": False,
        "may_update_ng_brain": False,
        "may_change_posterior": False,
        "may_change_blind_prior": False,
        "delivery_authority": False,
    }


def render_path(
    group: int, kind: str, *, root: str | os.PathLike[str] | None = None
) -> Path | None:
    group = int(group)
    _dates(group)
    key = {"blind": "blind_render", "refined": "refined_render"}.get(str(kind))
    if key is None:
        raise ForecastAdapterError("render kind must be blind or refined")
    path, _ = _find(_SPECS[group][key], _root(root))
    if path is None or path.stat().st_size <= 0:
        return None
    return path


def snapshot(
    day8: str | None = None, *, root: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Backward-compatible entry point, now bound to the strict authority chain."""
    if day8 is None:
        return summary_all(root=root)
    if day8 in G15_DATES:
        return day_snapshot(15, day8, root=root)
    if day8 in G16_DATES:
        return day_snapshot(16, day8, root=root)
    return {
        "available": False,
        "day": day8,
        "status": "NOT_A_CANONICAL_G15_OR_G16_SESSION",
        "authority": AUTHORITY,
        "actual_outcomes_loaded": False,
        "execution_authority": False,
    }


def summary_all(*, root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return {
        "schema": "ng_dashboard_forecast_groups.v1",
        "authority": AUTHORITY,
        "market": "NG",
        "groups": {str(group): summary(group, root=root) for group in (15, 16)},
        "actual_outcomes_loaded": False,
        "execution_authority": False,
    }
