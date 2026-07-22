#!/usr/bin/env python3
"""Outcome-only G16 path scorer for immutable blind and causal refined forecasts.

This module is deliberately downstream of the G16 blind wall, SHADOW gate,
posterior runner, and posterior-to-curve adapter. It may read target outcomes only
for scoring. It never modifies either forecast, cannot update ``ng_brain.json``,
and cannot grant execution authority.

The scorer emits independent blind and refined scorecards plus a comparison
artifact. G16 is a clean NGK26 block, so any contract roll or seam in the actual
artifact is rejected rather than silently adjusted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from ng_g16_blind_wall import G16_DATES
from ng_g16_curve_adapter import validate_refined_forecast
from ng_g16_shadow_gate import validate_blind_forecast

SCHEMA = "ng_g16_path_score.v1"
COMPARISON_SCHEMA = "ng_g16_path_comparison.v1"
AUTHORITY = "G16_OUTCOME_SCORING_ONLY"
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)


class G16ScoreError(ValueError):
    """Raised when G16 scoring inputs are incomplete, contradictory, or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_fingerprint(value: Mapping[str, Any], field: str) -> str:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    expected = _fingerprint(payload)
    if not isinstance(observed, str) or observed != expected:
        raise G16ScoreError(f"{field} mismatch")
    return observed


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _sign(value: float, *, flat_tolerance: float = 1e-12) -> int:
    if value > flat_tolerance:
        return 1
    if value < -flat_tolerance:
        return -1
    return 0


def _direction_label(value: float) -> str:
    return {1: "up", 0: "flat", -1: "down"}[_sign(value)]


def _validate_curve(curve: Any, *, label: str) -> list[float]:
    points = list(curve or [])
    if len(points) != len(GRID_HOURS):
        raise G16ScoreError(f"{label}: curve must have {len(GRID_HOURS)} points")
    hours = tuple(int(point[0]) for point in points)
    if hours != GRID_HOURS:
        raise G16ScoreError(f"{label}: curve hours differ from canonical grid")
    values: list[float] = []
    for point in points:
        value = _finite(point[1])
        if value is None:
            raise G16ScoreError(f"{label}: curve contains non-finite value")
        values.append(float(value))
    if abs(values[0]) > 1e-12:
        raise G16ScoreError(f"{label}: cumulative-from-open must begin at zero")
    return values


def _validate_forecast(
    forecast: Mapping[str, Any],
    *,
    expected_kind: str,
    blind_forecast: Mapping[str, Any] | None = None,
    blind_bytes: bytes | None = None,
) -> dict[str, dict[str, Any]]:
    if expected_kind == "blind":
        try:
            validate_blind_forecast(forecast)
        except Exception as error:
            raise G16ScoreError(f"blind forecast invalid: {error}") from error
    elif expected_kind == "refined":
        if blind_forecast is None:
            raise G16ScoreError("refined validation requires the source blind forecast")
        try:
            validate_refined_forecast(forecast, blind_forecast=blind_forecast)
        except Exception as error:
            raise G16ScoreError(f"refined forecast invalid: {error}") from error
        if blind_bytes is not None:
            expected_hash = _sha256_bytes(blind_bytes)
            if forecast.get("blind_forecast_sha256") != expected_hash:
                raise G16ScoreError("refined forecast source blind file hash mismatch")
    else:
        raise G16ScoreError(f"unsupported forecast kind: {expected_kind}")

    if int(forecast.get("group") or 0) != 16:
        raise G16ScoreError(f"{expected_kind}: forecast group must be 16")
    days = [copy.deepcopy(dict(day)) for day in forecast.get("days") or []]
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G16_DATES):
        raise G16ScoreError(f"{expected_kind}: forecast must contain canonical G16 days in order")
    for day in days:
        date = str(day["date"])
        values = _validate_curve(day.get("guess_curve"), label=f"{expected_kind}:{date}")
        endpoint = _finite(day.get("guessed_net_usd"))
        if endpoint is None or abs(float(endpoint) - values[-1]) > 1e-9:
            raise G16ScoreError(f"{expected_kind}:{date}: guessed_net_usd differs from curve endpoint")
        if _finite(day.get("overnight_gap_usd", 0)) is None:
            raise G16ScoreError(f"{expected_kind}:{date}: overnight_gap_usd is non-finite")
    return {str(day["date"]): day for day in days}


def _validate_actual(actual: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if actual.get("market") != "NG":
        raise G16ScoreError("actual: market must be NG")
    if int(actual.get("n_days") or 0) != len(G16_DATES):
        raise G16ScoreError("actual: n_days must equal canonical G16 session count")
    if actual.get("roll_adjusted") not in (False, None):
        raise G16ScoreError("actual: G16 RT path must remain unadjusted")
    if list(actual.get("rolls") or []) or list(actual.get("seams") or []):
        raise G16ScoreError("actual: canonical G16 is a clean NGK26 block with no roll or seam")
    anchor = dict(actual.get("anchor") or {})
    if str(anchor.get("date") or "") != "20260327":
        raise G16ScoreError("actual: canonical G16 anchor date must be 20260327")
    if _finite(anchor.get("price")) is None:
        raise G16ScoreError("actual: anchor price is missing")

    days = [copy.deepcopy(dict(day)) for day in actual.get("days") or []]
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G16_DATES):
        raise G16ScoreError("actual: sessions must match canonical G16 dates in order")
    for day in days:
        date = str(day["date"])
        values = _validate_curve(day.get("curve_2h"), label=f"actual:{date}")
        net = _finite(day.get("net_usd"))
        if net is None or abs(float(net) - values[-1]) > 1e-9:
            raise G16ScoreError(f"actual:{date}: net_usd differs from curve endpoint")
        if _finite(day.get("overnight_gap_usd")) is None:
            raise G16ScoreError(f"actual:{date}: overnight_gap_usd is non-finite")
        if _finite(day.get("cum_from_anchor_close_usd")) is None:
            raise G16ScoreError(f"actual:{date}: cumulative close is non-finite")
        if day.get("instrument") not in (None, "NGK26"):
            raise G16ScoreError(f"actual:{date}: instrument must remain NGK26")
    return {str(day["date"]): day for day in days}


def _increments(values: Sequence[float]) -> list[float]:
    return [float(values[index]) - float(values[index - 1]) for index in range(1, len(values))]


def _regime(values: Sequence[float]) -> tuple[str, float]:
    increments = _increments(values)
    travel = sum(abs(value) for value in increments)
    net = abs(float(values[-1]) - float(values[0]))
    efficiency = 0.0 if travel <= 1e-12 else net / travel
    return ("trend" if efficiency >= 0.55 else "chop"), efficiency


def _major_move_index(values: Sequence[float]) -> int | None:
    increments = _increments(values)
    if not increments:
        return None
    return max(range(len(increments)), key=lambda index: (abs(increments[index]), -index)) + 1


def _dominant_turn_index(values: Sequence[float]) -> int | None:
    increments = _increments(values)
    best: tuple[float, int] | None = None
    for index in range(1, len(increments)):
        left = increments[index - 1]
        right = increments[index]
        if _sign(left) == 0 or _sign(right) == 0 or _sign(left) == _sign(right):
            continue
        candidate = (min(abs(left), abs(right)), -index)
        if best is None or candidate > best:
            best = candidate
    return None if best is None else -best[1]


def _probability_metrics(day: Mapping[str, Any], actual_net: float) -> dict[str, Any] | None:
    probabilities = (day.get("refinement_audit") or {}).get("refined_direction_probabilities")
    if not isinstance(probabilities, Mapping):
        return None
    labels = ("up", "flat", "down")
    values: dict[str, float] = {}
    for label in labels:
        value = _finite(probabilities.get(label))
        if value is None or value < 0:
            return None
        values[label] = float(value)
    total = sum(values.values())
    if total <= 0:
        return None
    values = {label: value / total for label, value in values.items()}
    actual_label = _direction_label(actual_net)
    brier = sum((values[label] - (1.0 if label == actual_label else 0.0)) ** 2 for label in labels)
    log_loss = -math.log(max(values[actual_label], 1e-15))
    return {
        "actual_class": actual_label,
        "probabilities": {label: round(values[label], 12) for label in labels},
        "brier_multiclass": round(brier, 12),
        "log_loss": round(log_loss, 12),
    }


def _score_day(
    forecast_day: Mapping[str, Any],
    actual_day: Mapping[str, Any],
    *,
    running_guess_close: float,
) -> tuple[dict[str, Any], float]:
    guess = _validate_curve(forecast_day.get("guess_curve"), label=f"score:{forecast_day['date']}")
    actual = _validate_curve(actual_day.get("curve_2h"), label=f"actual:{actual_day['date']}")
    residuals = [guess[index] - actual[index] for index in range(len(guess))]
    guess_gap = float(forecast_day.get("overnight_gap_usd", 0))
    actual_gap = float(actual_day.get("overnight_gap_usd", 0))
    guess_net = float(guess[-1])
    actual_net = float(actual[-1])
    guess_open_cum = running_guess_close + guess_gap
    guess_close_cum = guess_open_cum + guess_net
    actual_close_cum = float(actual_day["cum_from_anchor_close_usd"])

    guess_regime, guess_efficiency = _regime(guess)
    actual_regime, actual_efficiency = _regime(actual)
    guess_major = _major_move_index(guess)
    actual_major = _major_move_index(actual)
    guess_turn = _dominant_turn_index(guess)
    actual_turn = _dominant_turn_index(actual)
    horizon = []
    for index in range(1, len(GRID_HOURS)):
        horizon.append(
            {
                "grid_index": index,
                "hour_et": GRID_HOURS[index],
                "guess_direction": _direction_label(guess[index]),
                "actual_direction": _direction_label(actual[index]),
                "direction_ok": _sign(guess[index]) == _sign(actual[index]),
            }
        )

    mae = sum(abs(value) for value in residuals) / len(residuals)
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    row = {
        "date": str(forecast_day["date"]),
        "dow": forecast_day.get("dow") or actual_day.get("dow"),
        "instrument": actual_day.get("instrument") or "NGK26",
        "guess_gap_usd": round(guess_gap, 8),
        "actual_gap_usd": round(actual_gap, 8),
        "gap_abs_error_usd": round(abs(guess_gap - actual_gap), 8),
        "gap_direction_ok": _sign(guess_gap) == _sign(actual_gap),
        "guess_net_usd": round(guess_net, 8),
        "actual_net_usd": round(actual_net, 8),
        "net_abs_error_usd": round(abs(guess_net - actual_net), 8),
        "net_direction_ok": _sign(guess_net) == _sign(actual_net),
        "path_mae_usd": round(mae, 8),
        "path_rmse_usd": round(rmse, 8),
        "endpoint_abs_error_usd": round(abs(residuals[-1]), 8),
        "max_positive_guess_usd": round(max(guess), 8),
        "max_positive_actual_usd": round(max(actual), 8),
        "max_positive_abs_error_usd": round(abs(max(guess) - max(actual)), 8),
        "max_negative_guess_usd": round(min(guess), 8),
        "max_negative_actual_usd": round(min(actual), 8),
        "max_negative_abs_error_usd": round(abs(min(guess) - min(actual)), 8),
        "guess_regime": guess_regime,
        "actual_regime": actual_regime,
        "regime_ok": guess_regime == actual_regime,
        "guess_path_efficiency": round(guess_efficiency, 12),
        "actual_path_efficiency": round(actual_efficiency, 12),
        "major_move_guess_grid_index": guess_major,
        "major_move_actual_grid_index": actual_major,
        "major_move_timing_error_intervals": None if guess_major is None or actual_major is None else abs(guess_major - actual_major),
        "dominant_turn_guess_grid_index": guess_turn,
        "dominant_turn_actual_grid_index": actual_turn,
        "dominant_turn_timing_error_intervals": None if guess_turn is None or actual_turn is None else abs(guess_turn - actual_turn),
        "horizon_direction": horizon,
        "horizon_direction_hits": sum(int(item["direction_ok"]) for item in horizon),
        "horizon_direction_count": len(horizon),
        "guess_cum_close_usd": round(guess_close_cum, 8),
        "actual_cum_close_usd": round(actual_close_cum, 8),
        "cumulative_drift_usd": round(guess_close_cum - actual_close_cum, 8),
        "direction_probability_score": _probability_metrics(forecast_day, actual_net),
    }
    row["day_fingerprint"] = _fingerprint(row)
    return row, guess_close_cum


def build_scorecard(
    forecast: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    role: str,
    blind_forecast: Mapping[str, Any] | None = None,
    forecast_bytes: bytes | None = None,
    blind_bytes: bytes | None = None,
    actual_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Score one immutable G16 forecast against the locked outcome artifact."""
    before_forecast = copy.deepcopy(dict(forecast))
    before_actual = copy.deepcopy(dict(actual))
    forecast_by_day = _validate_forecast(
        forecast,
        expected_kind=role,
        blind_forecast=blind_forecast,
        blind_bytes=blind_bytes,
    )
    actual_by_day = _validate_actual(actual)

    running_guess_close = 0.0
    rows: list[dict[str, Any]] = []
    for day in G16_DATES:
        row, running_guess_close = _score_day(
            forecast_by_day[day], actual_by_day[day], running_guess_close=running_guess_close
        )
        rows.append(row)

    horizon_hits = sum(int(row["horizon_direction_hits"]) for row in rows)
    horizon_count = sum(int(row["horizon_direction_count"]) for row in rows)
    probability_rows = [row["direction_probability_score"] for row in rows if row["direction_probability_score"]]
    aggregate = {
        "n_days": len(rows),
        "net_direction_hits": sum(int(row["net_direction_ok"]) for row in rows),
        "gap_direction_hits": sum(int(row["gap_direction_ok"]) for row in rows),
        "regime_hits": sum(int(row["regime_ok"]) for row in rows),
        "horizon_direction_hits": horizon_hits,
        "horizon_direction_count": horizon_count,
        "horizon_direction_accuracy": round(horizon_hits / horizon_count, 12) if horizon_count else None,
        "mean_path_mae_usd": round(sum(row["path_mae_usd"] for row in rows) / len(rows), 8),
        "mean_path_rmse_usd": round(sum(row["path_rmse_usd"] for row in rows) / len(rows), 8),
        "mean_net_abs_error_usd": round(sum(row["net_abs_error_usd"] for row in rows) / len(rows), 8),
        "mean_gap_abs_error_usd": round(sum(row["gap_abs_error_usd"] for row in rows) / len(rows), 8),
        "final_guess_cum_close_usd": rows[-1]["guess_cum_close_usd"],
        "final_actual_cum_close_usd": rows[-1]["actual_cum_close_usd"],
        "final_cumulative_drift_usd": rows[-1]["cumulative_drift_usd"],
        "probability_scored_days": len(probability_rows),
        "mean_brier_multiclass": round(sum(row["brier_multiclass"] for row in probability_rows) / len(probability_rows), 12) if probability_rows else None,
        "mean_log_loss": round(sum(row["log_loss"] for row in probability_rows) / len(probability_rows), 12) if probability_rows else None,
    }
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "role": role,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": True,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "forecast_sha256": _sha256_bytes(forecast_bytes if forecast_bytes is not None else (_canonical(forecast) + "\n").encode()),
        "actual_sha256": _sha256_bytes(actual_bytes if actual_bytes is not None else (_canonical(actual) + "\n").encode()),
        "forecast_artifact_fingerprint": forecast.get("artifact_fingerprint"),
        "actual_tag": actual.get("tag"),
        "days": rows,
        "aggregate": aggregate,
        "note": "Outcome-only G16 scoring. Forecast inputs remain immutable and no lesson or execution authority is granted.",
    }
    if dict(forecast) != before_forecast or dict(actual) != before_actual:
        raise G16ScoreError("scoring mutated an input artifact")
    result["score_fingerprint"] = _fingerprint(result)
    validate_scorecard(result)
    return result


def validate_scorecard(scorecard: Mapping[str, Any]) -> None:
    if scorecard.get("schema") != SCHEMA or scorecard.get("authority") != AUTHORITY:
        raise G16ScoreError("scorecard schema/authority mismatch")
    if scorecard.get("role") not in {"blind", "refined"}:
        raise G16ScoreError("scorecard role must be blind or refined")
    if int(scorecard.get("group") or 0) != 16:
        raise G16ScoreError("scorecard group must be 16")
    if scorecard.get("execution_authority") is not False:
        raise G16ScoreError("scorecard execution authority must remain false")
    if scorecard.get("actual_g16_outcomes_used") is not True:
        raise G16ScoreError("scorecard must disclose outcome use")
    if scorecard.get("may_update_ng_brain") is not False or scorecard.get("may_change_g16_blind_prior") is not False:
        raise G16ScoreError("scorecard cannot update brain or blind prior")
    _artifact_fingerprint(scorecard, "score_fingerprint")
    days = list(scorecard.get("days") or [])
    if [str(row.get("date") or "") for row in days] != list(G16_DATES):
        raise G16ScoreError("scorecard days must match canonical G16 order")
    for row in days:
        _artifact_fingerprint(row, "day_fingerprint")


def build_comparison(
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
) -> dict[str, Any]:
    validate_scorecard(blind_score)
    validate_scorecard(refined_score)
    if blind_score.get("role") != "blind" or refined_score.get("role") != "refined":
        raise G16ScoreError("comparison requires blind then refined scorecards")
    if blind_score.get("actual_sha256") != refined_score.get("actual_sha256"):
        raise G16ScoreError("scorecards used different actual artifacts")
    blind_days = {row["date"]: row for row in blind_score["days"]}
    refined_days = {row["date"]: row for row in refined_score["days"]}
    rows = []
    for day in G16_DATES:
        blind = blind_days[day]
        refined = refined_days[day]
        row = {
            "date": day,
            "path_mae_improvement_usd": round(blind["path_mae_usd"] - refined["path_mae_usd"], 8),
            "path_rmse_improvement_usd": round(blind["path_rmse_usd"] - refined["path_rmse_usd"], 8),
            "net_abs_error_improvement_usd": round(blind["net_abs_error_usd"] - refined["net_abs_error_usd"], 8),
            "endpoint_abs_error_improvement_usd": round(blind["endpoint_abs_error_usd"] - refined["endpoint_abs_error_usd"], 8),
            "blind_net_direction_ok": blind["net_direction_ok"],
            "refined_net_direction_ok": refined["net_direction_ok"],
            "direction_gain": int(refined["net_direction_ok"]) - int(blind["net_direction_ok"]),
            "blind_regime_ok": blind["regime_ok"],
            "refined_regime_ok": refined["regime_ok"],
            "regime_gain": int(refined["regime_ok"]) - int(blind["regime_ok"]),
            "blind_cumulative_drift_usd": blind["cumulative_drift_usd"],
            "refined_cumulative_drift_usd": refined["cumulative_drift_usd"],
        }
        row["comparison_day_fingerprint"] = _fingerprint(row)
        rows.append(row)
    aggregate = {
        "n_days": len(rows),
        "days_path_mae_improved": sum(int(row["path_mae_improvement_usd"] > 0) for row in rows),
        "days_path_mae_worsened": sum(int(row["path_mae_improvement_usd"] < 0) for row in rows),
        "mean_path_mae_improvement_usd": round(sum(row["path_mae_improvement_usd"] for row in rows) / len(rows), 8),
        "mean_path_rmse_improvement_usd": round(sum(row["path_rmse_improvement_usd"] for row in rows) / len(rows), 8),
        "mean_net_abs_error_improvement_usd": round(sum(row["net_abs_error_improvement_usd"] for row in rows) / len(rows), 8),
        "net_direction_gain": refined_score["aggregate"]["net_direction_hits"] - blind_score["aggregate"]["net_direction_hits"],
        "regime_gain": refined_score["aggregate"]["regime_hits"] - blind_score["aggregate"]["regime_hits"],
        "blind_final_cumulative_drift_usd": blind_score["aggregate"]["final_cumulative_drift_usd"],
        "refined_final_cumulative_drift_usd": refined_score["aggregate"]["final_cumulative_drift_usd"],
        "absolute_final_drift_improvement_usd": round(abs(blind_score["aggregate"]["final_cumulative_drift_usd"]) - abs(refined_score["aggregate"]["final_cumulative_drift_usd"]), 8),
    }
    result = {
        "schema": COMPARISON_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": True,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "actual_sha256": blind_score["actual_sha256"],
        "blind_score_fingerprint": blind_score["score_fingerprint"],
        "refined_score_fingerprint": refined_score["score_fingerprint"],
        "days": rows,
        "aggregate": aggregate,
        "note": "Positive improvement values mean the causal refined curve reduced error versus the immutable blind forecast.",
    }
    result["comparison_fingerprint"] = _fingerprint(result)
    validate_comparison(result)
    return result


def validate_comparison(comparison: Mapping[str, Any]) -> None:
    if comparison.get("schema") != COMPARISON_SCHEMA or comparison.get("authority") != AUTHORITY:
        raise G16ScoreError("comparison schema/authority mismatch")
    if comparison.get("execution_authority") is not False or comparison.get("actual_g16_outcomes_used") is not True:
        raise G16ScoreError("comparison authority flags are invalid")
    if comparison.get("may_update_ng_brain") is not False or comparison.get("may_change_g16_blind_prior") is not False:
        raise G16ScoreError("comparison cannot update brain or blind prior")
    _artifact_fingerprint(comparison, "comparison_fingerprint")
    days = list(comparison.get("days") or [])
    if [str(row.get("date") or "") for row in days] != list(G16_DATES):
        raise G16ScoreError("comparison days must match canonical G16 order")
    for row in days:
        _artifact_fingerprint(row, "comparison_day_fingerprint")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _fixture_blind() -> dict[str, Any]:
    return {
        "group": 16,
        "tag": "g16",
        "kind": "blind_panel_synthesis",
        "brain_version": "fixture",
        "days": [
            {
                "date": day,
                "dow": "X",
                "overnight_gap_usd": 0,
                "guess_curve": [[hour, -50 * index] for index, hour in enumerate(GRID_HOURS)],
                "guessed_net_usd": -600,
            }
            for day in G16_DATES
        ],
    }


def _fixture_actual() -> dict[str, Any]:
    return {
        "market": "NG",
        "tag": "g16",
        "anchor": {"date": "20260327", "price": 3.035, "last_hour_dir": "up"},
        "seams": [],
        "rolls": [],
        "roll_adjusted": False,
        "n_days": len(G16_DATES),
        "days": [
            {
                "date": day,
                "dow": "X",
                "instrument": "NGK26",
                "overnight_gap_usd": 0,
                "net_usd": -300,
                "cum_from_anchor_close_usd": -300 * (index + 1),
                "curve_2h": [[hour, -25 * point] for point, hour in enumerate(GRID_HOURS)],
            }
            for index, day in enumerate(G16_DATES)
        ],
    }


def _fixture_refined(blind: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(blind))
    result.update(
        {
            "schema": "ng_g16_refined_curve.v1",
            "tag": "g16_mbo_refined",
            "kind": "causal_shadow_refinement",
            "authority": "G16_REFINED_CURVE_SHADOW_ONLY",
            "execution_authority": False,
            "actual_g16_outcomes_used": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
            "calibration_status": "SHADOW_UNCALIBRATED",
            "source_blind_tag": blind.get("tag"),
            "source_blind_kind": blind.get("kind"),
            "source_brain_version": blind.get("brain_version"),
            "brain_version": blind.get("brain_version"),
            "blind_forecast_sha256": _sha256_bytes((_canonical(blind) + "\n").encode()),
            "shadow_plan_fingerprint": "plan",
            "posterior_stream_fingerprint": "stream",
            "authorization_stream_fingerprint": "auth",
            "transform_config": {"max_adjustment_fraction": 0.5},
            "note": "fixture",
        }
    )
    for day in result["days"]:
        day["guess_curve"] = [[hour, -25 * index] for index, hour in enumerate(GRID_HOURS)]
        day["guessed_net_usd"] = -300
        audit = {
            "schema": "ng_g16_curve_day_audit.v1",
            "authority": "G16_REFINED_CURVE_SHADOW_ONLY",
            "execution_authority": False,
            "actual_g16_outcomes_used": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
            "date": day["date"],
            "blind_scale_usd": 600.0,
            "max_adjustment_fraction": 0.5,
            "outputs_seen": 1,
            "outputs_used": 1,
            "outputs_ignored_or_stood_down": 0,
            "first_used_event_s": 1.0,
            "last_used_event_s": 1.0,
            "endpoint_adjustment_usd": 300,
            "max_abs_curve_adjustment_usd": 300,
            "blind_direction_probabilities": {"up": 0.2, "flat": 0.1, "down": 0.7},
            "refined_direction_probabilities": {"up": 0.1, "flat": 0.1, "down": 0.8},
            "authorized_candidate_ids_used": ["fixture"],
            "source_output_fingerprints": ["output"],
            "plan_fingerprint": "plan",
            "posterior_stream_fingerprint": "stream",
            "causal_rule": "fixture",
        }
        audit["audit_fingerprint"] = _fingerprint(audit)
        day["refinement_audit"] = audit
    result["artifact_fingerprint"] = _fingerprint(result)
    return result


def selftest() -> int:
    blind = _fixture_blind()
    actual = _fixture_actual()
    refined = _fixture_refined(blind)
    blind_before = copy.deepcopy(blind)
    actual_before = copy.deepcopy(actual)
    blind_score = build_scorecard(blind, actual, role="blind")
    refined_score = build_scorecard(
        refined,
        actual,
        role="refined",
        blind_forecast=blind,
        blind_bytes=(_canonical(blind) + "\n").encode(),
    )
    comparison = build_comparison(blind_score, refined_score)
    assert blind == blind_before and actual == actual_before
    assert comparison["aggregate"]["days_path_mae_improved"] == len(G16_DATES)
    assert refined_score["aggregate"]["mean_path_mae_usd"] == 0.0
    validate_scorecard(blind_score)
    validate_scorecard(refined_score)
    validate_comparison(comparison)
    print("[ng_g16_path_score] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Score immutable blind and causal refined G16 paths")
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--refined", type=Path)
    parser.add_argument("--actual", type=Path)
    parser.add_argument("--blind-score-out", type=Path)
    parser.add_argument("--refined-score-out", type=Path)
    parser.add_argument("--comparison-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = ("blind", "refined", "actual", "blind_score_out", "refined_score_out", "comparison_out")
    if any(getattr(args, name) is None for name in required):
        parser.error("--blind --refined --actual --blind-score-out --refined-score-out --comparison-out are required")
    blind_bytes = args.blind.read_bytes()
    refined_bytes = args.refined.read_bytes()
    actual_bytes = args.actual.read_bytes()
    blind = json.loads(blind_bytes.decode("utf-8"))
    refined = json.loads(refined_bytes.decode("utf-8"))
    actual = json.loads(actual_bytes.decode("utf-8"))
    blind_score = build_scorecard(
        blind, actual, role="blind", forecast_bytes=blind_bytes, actual_bytes=actual_bytes
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
    _atomic_json(args.blind_score_out, blind_score)
    _atomic_json(args.refined_score_out, refined_score)
    _atomic_json(args.comparison_out, comparison)
    print(
        json.dumps(
            {
                "blind_score": str(args.blind_score_out),
                "refined_score": str(args.refined_score_out),
                "comparison": str(args.comparison_out),
                "blind_net_direction_hits": blind_score["aggregate"]["net_direction_hits"],
                "refined_net_direction_hits": refined_score["aggregate"]["net_direction_hits"],
                "mean_path_mae_improvement_usd": comparison["aggregate"]["mean_path_mae_improvement_usd"],
                "actual_g16_outcomes_used": True,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
