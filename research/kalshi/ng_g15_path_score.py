#!/usr/bin/env python3
"""Outcome-only G15 path scorer for immutable blind and causal refined forecasts.

This module is deliberately downstream of the blind wall and posterior-to-curve
adapter. It reads target outcomes only for scoring. It never modifies either
forecast and cannot update ``ng_brain.json`` or grant execution authority.

Outputs:
- one per-forecast scorecard (blind or refined);
- one blind-vs-refined comparison;
- explicit per-day path, timing, excursion, regime, and cumulative-drift metrics.

The scorer uses the canonical 13-point two-hour grid from ``continuous_rt.py``.
The March 19 -> March 20 contract seam is removed from skill drift by applying
the committed roll offset from the actual artifact.
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

from ng_historical_manifest import G15_DATES

SCHEMA = "ng_g15_path_score.v1"
COMPARISON_SCHEMA = "ng_g15_path_comparison.v1"
AUTHORITY = "OUTCOME_SCORING_ONLY"
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
MULT = 10000.0


class ScoreError(ValueError):
    """Raised when scoring inputs are incomplete, contradictory, or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _direction_label(value: float, *, flat_tolerance: float = 1e-12) -> str:
    return {1: "up", 0: "flat", -1: "down"}[_sign(value, flat_tolerance=flat_tolerance)]


def _validate_curve(curve: Any, *, label: str) -> list[float]:
    points = list(curve or [])
    if len(points) != len(GRID_HOURS):
        raise ScoreError(f"{label}: curve must have {len(GRID_HOURS)} points")
    hours = tuple(int(point[0]) for point in points)
    if hours != GRID_HOURS:
        raise ScoreError(f"{label}: curve hours differ from canonical grid")
    values: list[float] = []
    for point in points:
        value = _finite(point[1])
        if value is None:
            raise ScoreError(f"{label}: curve contains non-finite value")
        values.append(float(value))
    if abs(values[0]) > 1e-12:
        raise ScoreError(f"{label}: cumulative-from-open must begin at zero")
    return values


def _validate_forecast(
    forecast: Mapping[str, Any],
    *,
    expected_kind: str,
    blind_bytes: bytes | None = None,
) -> dict[str, dict[str, Any]]:
    if int(forecast.get("group") or 0) != 15:
        raise ScoreError(f"{expected_kind}: forecast group must be 15")
    days = [copy.deepcopy(dict(day)) for day in forecast.get("days") or []]
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G15_DATES):
        raise ScoreError(f"{expected_kind}: forecast must contain canonical G15 days in order")
    for day in days:
        date = str(day["date"])
        values = _validate_curve(day.get("guess_curve"), label=f"{expected_kind}:{date}")
        endpoint = _finite(day.get("guessed_net_usd"))
        if endpoint is None or abs(float(endpoint) - values[-1]) > 1e-9:
            raise ScoreError(f"{expected_kind}:{date}: guessed_net_usd differs from curve endpoint")
        gap = _finite(day.get("overnight_gap_usd", 0))
        if gap is None:
            raise ScoreError(f"{expected_kind}:{date}: overnight_gap_usd is non-finite")

    if expected_kind == "refined":
        if forecast.get("schema") != "ng_g15_refined_curve.v1":
            raise ScoreError(f"refined: unexpected schema {forecast.get('schema')}")
        if forecast.get("authority") != "REFINED_CURVE_SHADOW_ONLY":
            raise ScoreError("refined: authority is invalid")
        if forecast.get("execution_authority") is not False:
            raise ScoreError("refined: execution authority must remain false")
        if forecast.get("actual_outcomes_used") is not False:
            raise ScoreError("refined: curve artifact must remain outcome-blind")
        if forecast.get("may_update_ng_brain") is not False:
            raise ScoreError("refined: curve artifact cannot update ng_brain")
        payload = copy.deepcopy(dict(forecast))
        artifact_fingerprint = payload.pop("artifact_fingerprint", None)
        if artifact_fingerprint != _fingerprint(payload):
            raise ScoreError("refined: artifact fingerprint mismatch")
        if blind_bytes is not None:
            expected_hash = _sha256_bytes(blind_bytes)
            if forecast.get("blind_forecast_sha256") != expected_hash:
                raise ScoreError("refined: source blind file hash mismatch")
    return {str(day["date"]): day for day in days}


def _validate_actual(actual: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if actual.get("market") != "NG":
        raise ScoreError("actual: market must be NG")
    if int(actual.get("n_days") or 0) != len(G15_DATES):
        raise ScoreError("actual: n_days must equal canonical G15 session count")
    days = [copy.deepcopy(dict(day)) for day in actual.get("days") or []]
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G15_DATES):
        raise ScoreError("actual: sessions must match canonical G15 dates in order")
    for day in days:
        date = str(day["date"])
        values = _validate_curve(day.get("curve_2h"), label=f"actual:{date}")
        net = _finite(day.get("net_usd"))
        if net is None or abs(float(net) - values[-1]) > 1e-9:
            raise ScoreError(f"actual:{date}: net_usd differs from curve endpoint")
        if _finite(day.get("overnight_gap_usd")) is None:
            raise ScoreError(f"actual:{date}: overnight_gap_usd is non-finite")
        if _finite(day.get("cum_from_anchor_close_usd")) is None:
            raise ScoreError(f"actual:{date}: cumulative close is non-finite")
    anchor = dict(actual.get("anchor") or {})
    if str(anchor.get("date") or "") != "20260313":
        raise ScoreError("actual: canonical anchor date must be 20260313")
    if _finite(anchor.get("price")) is None:
        raise ScoreError("actual: anchor price is missing")
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
    """Return the strongest interior reversal index, or None when no sign reversal exists."""
    increments = _increments(values)
    best: tuple[float, int] | None = None
    for index in range(1, len(increments)):
        left = increments[index - 1]
        right = increments[index]
        if _sign(left) == 0 or _sign(right) == 0 or _sign(left) == _sign(right):
            continue
        strength = min(abs(left), abs(right))
        candidate = (strength, -index)
        if best is None or candidate > best:
            best = candidate
    return None if best is None else -best[1]


def _horizon_direction_hits(guess: Sequence[float], actual: Sequence[float]) -> list[dict[str, Any]]:
    rows = []
    for index, hour in enumerate(GRID_HOURS):
        if index == 0:
            continue
        g = float(guess[index])
        a = float(actual[index])
        rows.append(
            {
                "grid_index": index,
                "hour_et": hour,
                "guess_direction": _direction_label(g),
                "actual_direction": _direction_label(a),
                "direction_ok": _sign(g) == _sign(a),
            }
        )
    return rows


def _probability_metrics(day: Mapping[str, Any], actual_net: float) -> dict[str, Any] | None:
    audit = dict(day.get("refinement_audit") or {})
    probabilities = audit.get("refined_direction_probabilities")
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
    cumulative_roll_usd: float,
) -> tuple[dict[str, Any], float]:
    guess = _validate_curve(forecast_day.get("guess_curve"), label=f"score:{forecast_day['date']}")
    actual = _validate_curve(actual_day.get("curve_2h"), label=f"actual:{actual_day['date']}")
    residuals = [guess[index] - actual[index] for index in range(len(guess))]
    mae = sum(abs(value) for value in residuals) / len(residuals)
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))

    guess_net = float(guess[-1])
    actual_net = float(actual[-1])
    guess_gap = float(forecast_day.get("overnight_gap_usd", 0))
    actual_gap = float(actual_day.get("overnight_gap_usd", 0))
    guess_open_cum = running_guess_close + guess_gap
    guess_close_cum = guess_open_cum + guess_net
    actual_close_adj = float(actual_day["cum_from_anchor_close_usd"]) - cumulative_roll_usd

    guess_regime, guess_efficiency = _regime(guess)
    actual_regime, actual_efficiency = _regime(actual)
    guess_major = _major_move_index(guess)
    actual_major = _major_move_index(actual)
    guess_turn = _dominant_turn_index(guess)
    actual_turn = _dominant_turn_index(actual)

    horizon_rows = _horizon_direction_hits(guess, actual)
    probability_metrics = _probability_metrics(forecast_day, actual_net)

    row = {
        "date": str(forecast_day["date"]),
        "dow": forecast_day.get("dow") or actual_day.get("dow"),
        "instrument": actual_day.get("instrument"),
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
        "major_move_grid_index_guess": guess_major,
        "major_move_grid_index_actual": actual_major,
        "major_move_timing_error_steps": None if guess_major is None or actual_major is None else abs(guess_major - actual_major),
        "dominant_turn_grid_index_guess": guess_turn,
        "dominant_turn_grid_index_actual": actual_turn,
        "dominant_turn_timing_error_steps": None if guess_turn is None or actual_turn is None else abs(guess_turn - actual_turn),
        "horizon_direction": horizon_rows,
        "horizon_direction_hits": sum(int(item["direction_ok"]) for item in horizon_rows),
        "horizon_direction_total": len(horizon_rows),
        "guess_close_cum_roll_free_usd": round(guess_close_cum, 8),
        "actual_close_cum_roll_adjusted_usd": round(actual_close_adj, 8),
        "cumulative_drift_usd": round(guess_close_cum - actual_close_adj, 8),
        "probability_score": probability_metrics,
    }
    return row, guess_close_cum


def build_scorecard(
    forecast: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    forecast_kind: str,
    forecast_bytes: bytes | None = None,
    blind_bytes: bytes | None = None,
) -> dict[str, Any]:
    if forecast_kind not in {"blind", "refined"}:
        raise ScoreError("forecast_kind must be blind or refined")
    forecast_before = copy.deepcopy(dict(forecast))
    actual_before = copy.deepcopy(dict(actual))
    forecast_days = _validate_forecast(
        forecast,
        expected_kind=forecast_kind,
        blind_bytes=blind_bytes if forecast_kind == "refined" else None,
    )
    actual_days = _validate_actual(actual)

    roll_by_date: dict[str, float] = {}
    running_roll = 0.0
    for date in G15_DATES:
        running_roll += sum(
            float(roll["offset"]) * MULT
            for roll in actual.get("rolls") or []
            if str(roll.get("date") or "") == date
        )
        roll_by_date[date] = running_roll

    rows: list[dict[str, Any]] = []
    running_guess = 0.0
    for date in G15_DATES:
        row, running_guess = _score_day(
            forecast_days[date],
            actual_days[date],
            running_guess_close=running_guess,
            cumulative_roll_usd=roll_by_date[date],
        )
        rows.append(row)

    final = rows[-1]
    scorecard = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "tag": f"g15_mbo_{forecast_kind}",
        "forecast_kind": forecast_kind,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "forecast_sha256": _sha256_bytes(
            forecast_bytes if forecast_bytes is not None else (_canonical(forecast) + "\n").encode("utf-8")
        ),
        "actual_artifact_fingerprint": _fingerprint(actual),
        "anchor": copy.deepcopy(actual.get("anchor")),
        "rolls": copy.deepcopy(actual.get("rolls") or []),
        "scoring_rules": {
            "path_grid": list(GRID_HOURS),
            "path_error": "unweighted error across the canonical 13-point two-hour cumulative-from-open curve",
            "regime": "trend when abs(net)/total_path_travel >= 0.55, otherwise chop",
            "major_move": "grid endpoint of the largest absolute two-hour increment",
            "dominant_turn": "strongest interior sign reversal ranked by the smaller adjacent increment",
            "cumulative_drift": "forecast cumulative gap+net minus actual cumulative close after removing marked roll offsets",
            "probability_scores": "multiclass Brier and log loss only when auditable direction probabilities are present",
        },
        "days": rows,
        "block": {
            "final_guess_close_cum_roll_free_usd": final["guess_close_cum_roll_free_usd"],
            "final_actual_close_cum_roll_adjusted_usd": final["actual_close_cum_roll_adjusted_usd"],
            "final_cumulative_drift_usd": final["cumulative_drift_usd"],
            "net_direction_hits": sum(int(row["net_direction_ok"]) for row in rows),
            "net_direction_total": len(rows),
            "horizon_direction_hits": sum(int(row["horizon_direction_hits"]) for row in rows),
            "horizon_direction_total": sum(int(row["horizon_direction_total"]) for row in rows),
            "regime_hits": sum(int(row["regime_ok"]) for row in rows),
            "regime_total": len(rows),
            "path_absolute_error_sum_usd": round(sum(row["path_mae_usd"] * len(GRID_HOURS) for row in rows), 8),
            "endpoint_absolute_error_sum_usd": round(sum(row["endpoint_abs_error_usd"] for row in rows), 8),
        },
        "note": (
            "Outcome-only scorecard. It cannot feed the blind forecast, refined posterior, "
            "or ng_brain. Per-day rows remain the primary evidence; block totals are descriptive."
        ),
    }
    scorecard["artifact_fingerprint"] = _fingerprint(scorecard)
    if dict(forecast) != forecast_before:
        raise ScoreError("forecast mutated during scoring")
    if dict(actual) != actual_before:
        raise ScoreError("actual artifact mutated during scoring")
    validate_scorecard(scorecard)
    return scorecard


def validate_scorecard(scorecard: Mapping[str, Any]) -> None:
    if scorecard.get("schema") != SCHEMA:
        raise ScoreError("scorecard schema mismatch")
    if scorecard.get("authority") != AUTHORITY:
        raise ScoreError("scorecard authority mismatch")
    if scorecard.get("execution_authority") is not False:
        raise ScoreError("scorecard cannot grant execution authority")
    if scorecard.get("actual_outcomes_used") is not True:
        raise ScoreError("scorecard must disclose outcome use")
    if scorecard.get("may_update_ng_brain") is not False:
        raise ScoreError("scorecard cannot update ng_brain")
    dates = [str(day.get("date") or "") for day in scorecard.get("days") or []]
    if dates != list(G15_DATES):
        raise ScoreError("scorecard days are incomplete or out of order")
    payload = copy.deepcopy(dict(scorecard))
    fingerprint = payload.pop("artifact_fingerprint", None)
    if fingerprint != _fingerprint(payload):
        raise ScoreError("scorecard fingerprint mismatch")


def build_comparison(
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
) -> dict[str, Any]:
    validate_scorecard(blind_score)
    validate_scorecard(refined_score)
    if blind_score.get("forecast_kind") != "blind":
        raise ScoreError("comparison blind score has wrong forecast_kind")
    if refined_score.get("forecast_kind") != "refined":
        raise ScoreError("comparison refined score has wrong forecast_kind")
    blind_by_day = {day["date"]: day for day in blind_score["days"]}
    refined_by_day = {day["date"]: day for day in refined_score["days"]}
    rows: list[dict[str, Any]] = []
    for date in G15_DATES:
        blind = blind_by_day[date]
        refined = refined_by_day[date]
        rows.append(
            {
                "date": date,
                "blind_path_mae_usd": blind["path_mae_usd"],
                "refined_path_mae_usd": refined["path_mae_usd"],
                "path_mae_improvement_usd": round(blind["path_mae_usd"] - refined["path_mae_usd"], 8),
                "blind_endpoint_abs_error_usd": blind["endpoint_abs_error_usd"],
                "refined_endpoint_abs_error_usd": refined["endpoint_abs_error_usd"],
                "endpoint_improvement_usd": round(
                    blind["endpoint_abs_error_usd"] - refined["endpoint_abs_error_usd"], 8
                ),
                "blind_net_direction_ok": blind["net_direction_ok"],
                "refined_net_direction_ok": refined["net_direction_ok"],
                "direction_changed": blind["net_direction_ok"] != refined["net_direction_ok"],
                "blind_regime_ok": blind["regime_ok"],
                "refined_regime_ok": refined["regime_ok"],
                "regime_changed": blind["regime_ok"] != refined["regime_ok"],
                "blind_major_move_timing_error_steps": blind["major_move_timing_error_steps"],
                "refined_major_move_timing_error_steps": refined["major_move_timing_error_steps"],
                "blind_turn_timing_error_steps": blind["dominant_turn_timing_error_steps"],
                "refined_turn_timing_error_steps": refined["dominant_turn_timing_error_steps"],
                "blind_cumulative_drift_usd": blind["cumulative_drift_usd"],
                "refined_cumulative_drift_usd": refined["cumulative_drift_usd"],
            }
        )

    blind_block = dict(blind_score["block"])
    refined_block = dict(refined_score["block"])
    result = {
        "schema": COMPARISON_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "blind_score_fingerprint": blind_score["artifact_fingerprint"],
        "refined_score_fingerprint": refined_score["artifact_fingerprint"],
        "days": rows,
        "block": {
            "blind_final_cumulative_drift_usd": blind_block["final_cumulative_drift_usd"],
            "refined_final_cumulative_drift_usd": refined_block["final_cumulative_drift_usd"],
            "absolute_final_drift_improvement_usd": round(
                abs(blind_block["final_cumulative_drift_usd"])
                - abs(refined_block["final_cumulative_drift_usd"]),
                8,
            ),
            "blind_net_direction_hits": blind_block["net_direction_hits"],
            "refined_net_direction_hits": refined_block["net_direction_hits"],
            "blind_horizon_direction_hits": blind_block["horizon_direction_hits"],
            "refined_horizon_direction_hits": refined_block["horizon_direction_hits"],
            "blind_regime_hits": blind_block["regime_hits"],
            "refined_regime_hits": refined_block["regime_hits"],
            "path_absolute_error_improvement_usd": round(
                blind_block["path_absolute_error_sum_usd"]
                - refined_block["path_absolute_error_sum_usd"],
                8,
            ),
            "endpoint_absolute_error_improvement_usd": round(
                blind_block["endpoint_absolute_error_sum_usd"]
                - refined_block["endpoint_absolute_error_sum_usd"],
                8,
            ),
        },
        "lesson_gate": {
            "may_update_ng_brain": False,
            "status": "SCORED_EVIDENCE_ONLY",
            "requirements_before_adoption": [
                "G16 chronological pre-cutoff validation",
                "untouched holdout validation",
                "forward-live validation",
            ],
        },
        "note": "Positive improvement values mean the causal refined curve reduced error versus the immutable blind curve.",
    }
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_comparison(result)
    return result


def validate_comparison(comparison: Mapping[str, Any]) -> None:
    if comparison.get("schema") != COMPARISON_SCHEMA:
        raise ScoreError("comparison schema mismatch")
    if comparison.get("authority") != AUTHORITY:
        raise ScoreError("comparison authority mismatch")
    if comparison.get("execution_authority") is not False:
        raise ScoreError("comparison cannot grant execution authority")
    if comparison.get("actual_outcomes_used") is not True:
        raise ScoreError("comparison must disclose outcome use")
    if comparison.get("may_update_ng_brain") is not False:
        raise ScoreError("comparison cannot update ng_brain")
    dates = [str(day.get("date") or "") for day in comparison.get("days") or []]
    if dates != list(G15_DATES):
        raise ScoreError("comparison days are incomplete or out of order")
    payload = copy.deepcopy(dict(comparison))
    fingerprint = payload.pop("artifact_fingerprint", None)
    if fingerprint != _fingerprint(payload):
        raise ScoreError("comparison fingerprint mismatch")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bytes]:
    blind_days = []
    refined_days = []
    actual_days = []
    running_actual = 0
    for index, date in enumerate(G15_DATES):
        sign = -1 if index % 3 else 1
        blind_values = [0] + [sign * 20 * point for point in range(1, len(GRID_HOURS))]
        actual_values = [0] + [sign * 30 * point for point in range(1, len(GRID_HOURS))]
        refined_values = [0] + [sign * 28 * point for point in range(1, len(GRID_HOURS))]
        gap = 0
        running_actual += gap + actual_values[-1]
        common = {"date": date, "dow": "X", "overnight_gap_usd": gap}
        blind_days.append({**common, "guess_curve": [[h, v] for h, v in zip(GRID_HOURS, blind_values)], "guessed_net_usd": blind_values[-1]})
        audit = {
            "actual_outcomes_used": False,
            "refined_direction_probabilities": {
                "up": 0.8 if sign > 0 else 0.1,
                "flat": 0.1,
                "down": 0.1 if sign > 0 else 0.8,
            },
        }
        refined_days.append({**common, "guess_curve": [[h, v] for h, v in zip(GRID_HOURS, refined_values)], "guessed_net_usd": refined_values[-1], "refinement_audit": audit})
        actual_days.append(
            {
                "date": date,
                "dow": "X",
                "instrument": 1008 if date <= "20260319" else 996,
                "overnight_gap_usd": gap,
                "net_usd": actual_values[-1],
                "cum_from_anchor_close_usd": running_actual,
                "curve_2h": [[h, v] for h, v in zip(GRID_HOURS, actual_values)],
            }
        )
    blind = {"group": 15, "tag": "g15", "brain_version": "test", "days": blind_days}
    blind_bytes = (json.dumps(blind, indent=2) + "\n").encode("utf-8")
    refined = {
        **copy.deepcopy(blind),
        "schema": "ng_g15_refined_curve.v1",
        "tag": "g15_mbo_refined",
        "authority": "REFINED_CURVE_SHADOW_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_update_ng_brain": False,
        "blind_forecast_sha256": _sha256_bytes(blind_bytes),
        "days": refined_days,
    }
    refined["artifact_fingerprint"] = _fingerprint(refined)
    actual = {
        "market": "NG",
        "tag": "g15",
        "anchor": {"date": "20260313", "price": 3.132, "last_hour_dir": "down"},
        "n_days": len(G15_DATES),
        "rolls": [],
        "days": actual_days,
    }
    return blind, refined, actual, blind_bytes


def selftest() -> int:
    blind, refined, actual, blind_bytes = _fixture()
    blind_before = copy.deepcopy(blind)
    refined_before = copy.deepcopy(refined)
    blind_score = build_scorecard(blind, actual, forecast_kind="blind", forecast_bytes=blind_bytes)
    refined_score = build_scorecard(
        refined,
        actual,
        forecast_kind="refined",
        blind_bytes=blind_bytes,
    )
    comparison = build_comparison(blind_score, refined_score)
    assert blind == blind_before
    assert refined == refined_before
    assert comparison["block"]["path_absolute_error_improvement_usd"] > 0
    assert refined_score["days"][0]["probability_score"]["brier_multiclass"] >= 0
    assert comparison["may_update_ng_brain"] is False
    print("[ng_g15_path_score] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Score immutable blind and causal refined G15 paths")
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
    required = (
        args.blind,
        args.refined,
        args.actual,
        args.blind_score_out,
        args.refined_score_out,
        args.comparison_out,
    )
    if any(value is None for value in required):
        parser.error(
            "--blind, --refined, --actual, --blind-score-out, "
            "--refined-score-out, and --comparison-out are required"
        )
    blind_bytes = args.blind.read_bytes()
    refined_bytes = args.refined.read_bytes()
    actual_bytes = args.actual.read_bytes()
    blind = json.loads(blind_bytes.decode("utf-8"))
    refined = json.loads(refined_bytes.decode("utf-8"))
    actual = json.loads(actual_bytes.decode("utf-8"))

    blind_score = build_scorecard(
        blind,
        actual,
        forecast_kind="blind",
        forecast_bytes=blind_bytes,
    )
    refined_score = build_scorecard(
        refined,
        actual,
        forecast_kind="refined",
        forecast_bytes=refined_bytes,
        blind_bytes=blind_bytes,
    )
    comparison = build_comparison(blind_score, refined_score)
    _atomic_json(args.blind_score_out, blind_score)
    _atomic_json(args.refined_score_out, refined_score)
    _atomic_json(args.comparison_out, comparison)
    print(
        json.dumps(
            {
                "blind_score_out": str(args.blind_score_out),
                "refined_score_out": str(args.refined_score_out),
                "comparison_out": str(args.comparison_out),
                "blind_final_drift_usd": blind_score["block"]["final_cumulative_drift_usd"],
                "refined_final_drift_usd": refined_score["block"]["final_cumulative_drift_usd"],
                "path_absolute_error_improvement_usd": comparison["block"]["path_absolute_error_improvement_usd"],
                "may_update_ng_brain": False,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
