"""Read-only adapter for NG forecast prior, live dipole update, and proper score.

One authority is preserved:
- forecast = locked blind prior from the existing forecaster;
- live_update = later dipole likelihood update;
- score = calibration telemetry.

No dashboard value grants execution authority.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any

from . import paths

FORECAST_DIR = os.path.join(paths.KALSHI_RESEARCH, "forecasts")
SCORE_DIR = os.path.join(paths.KALSHI_RESEARCH, "renders", "ng_refine_s95")
LIVE_UPDATE_PATH = os.environ.get(
    "NG_LIVE_UPDATE_PATH",
    os.path.join(paths.REPO, "scratchpad", "live_ng_update.json"),
)


def _load(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _candidate_forecasts() -> list[str]:
    paths_found = []
    for path in glob.glob(os.path.join(FORECAST_DIR, "grp*.json")):
        name = os.path.basename(path)
        if any(token in name for token in ("_agent", "_refined", "_proposal")):
            continue
        paths_found.append(path)
    return sorted(paths_found, key=os.path.getmtime, reverse=True)


def _forecast_for_day(day8: str | None) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    fallback = None
    for path in _candidate_forecasts():
        payload = _load(path)
        if not payload:
            continue
        if fallback is None:
            fallback = (path, payload, None)
        for row in payload.get("days", []):
            if isinstance(row, dict) and (day8 is None or row.get("date") == day8):
                return path, payload, row
    return fallback or (None, None, None)


def _latest_score(day8: str | None) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    candidates = sorted(
        glob.glob(os.path.join(SCORE_DIR, "*_proper_score.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    fallback = None
    for path in candidates:
        payload = _load(path)
        if not payload:
            continue
        if fallback is None:
            fallback = (path, payload, None)
        for row in payload.get("rows", []):
            if isinstance(row, dict) and (day8 is None or row.get("date") == day8):
                return path, payload, row
    return fallback or (None, None, None)


def snapshot(day8: str | None = None) -> dict[str, Any]:
    forecast_path, forecast_payload, forecast_day = _forecast_for_day(day8)
    score_path, score_payload, score_day = _latest_score(day8)
    live = _load(LIVE_UPDATE_PATH)
    if live and day8 and live.get("date") not in (None, day8):
        live = None

    schema = forecast_payload.get("forecast_schema_version") if forecast_payload else None
    prior = None
    if forecast_day:
        prior = {
            "date": forecast_day.get("date"),
            "direction_probabilities": forecast_day.get("direction_probabilities"),
            "move_size_distribution_usd": forecast_day.get("move_size_distribution_usd"),
            "shape_probabilities": forecast_day.get("shape_probabilities"),
            "continuation_reversal_probabilities": forecast_day.get("continuation_reversal_probabilities"),
            "confidence": forecast_day.get("confidence"),
            "data_quality": forecast_day.get("data_quality"),
            "regime": forecast_day.get("regime"),
            "guessed_net_usd": forecast_day.get("guessed_net_usd"),
            "legacy": schema != "ng.v2",
        }

    return {
        "available": forecast_payload is not None,
        "day": day8,
        "forecast_schema_version": schema,
        "brain_version": forecast_payload.get("brain_version") if forecast_payload else None,
        "forecast_file": os.path.relpath(forecast_path, paths.REPO) if forecast_path else None,
        "blind_prior": prior,
        "live_update": live,
        "proper_score": score_day,
        "proper_score_summary": score_payload.get("summary") if score_payload else None,
        "score_file": os.path.relpath(score_path, paths.REPO) if score_path else None,
        "authority": {
            "blind_prior": "forecast authority; scored blind",
            "live_update": "likelihood update only; scored separately",
            "proper_score": "calibration telemetry only",
            "execution": "none; CME event contracts remain SHADOW",
        },
        "data_quality_flags": [
            "legacy forecast lacks ng.v2 probabilities" if forecast_payload and schema != "ng.v2" else None,
            "live dipole update not present" if live is None else None,
            "proper score not present" if score_payload is None else None,
        ],
    }
