#!/usr/bin/env python3
"""Proper scoring for the existing NG blind forecast artifacts.

Adds calibration-aware metrics beside the legacy direction/drift score:
- multiclass Brier and logarithmic scores by horizon;
- quantile/pinball loss and an approximate CRPS for move size;
- p10-p90 interval coverage and width;
- trend/chop and continuation/reversal categorical scores;
- regime-separated records for later reliability aggregation.

The scorer reads locked forecasts and realized RT files. It never feeds information
back into a blind forecast and does not create a new signal.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

EPS = 1e-12
DIRECTION_KEYS = ("up", "flat", "down")


def _classify(value: float, flat_band: float) -> str:
    if value > flat_band:
        return "up"
    if value < -flat_band:
        return "down"
    return "flat"


def _normalize_probs(probs: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    values = {key: max(0.0, float(probs.get(key, 0.0) or 0.0)) for key in keys}
    total = sum(values.values())
    if total <= 0:
        return {key: 1.0 / len(keys) for key in keys}
    return {key: value / total for key, value in values.items()}


def _categorical_score(probs: dict[str, Any], outcome: str, keys: tuple[str, ...]) -> dict[str, float]:
    p = _normalize_probs(probs, keys)
    brier = sum((p[key] - (1.0 if key == outcome else 0.0)) ** 2 for key in keys)
    log_score = -math.log(max(EPS, p[outcome]))
    return {
        "brier": round(brier, 8),
        "log_score": round(log_score, 8),
        "p_outcome": round(p[outcome], 8),
    }


def _pinball(actual: float, forecast: float, q: float) -> float:
    error = actual - forecast
    return max(q * error, (q - 1.0) * error)


def _path_values(actual_day: dict[str, Any]) -> list[float]:
    rows = actual_day.get("curve_2h") or []
    values: list[float] = []
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            values.append(float(row[1]))
        elif isinstance(row, dict) and row.get("cum_usd") is not None:
            values.append(float(row["cum_usd"]))
    if not values and actual_day.get("net_usd") is not None:
        values.append(float(actual_day["net_usd"]))
    return values


def _actual_shape(actual_day: dict[str, Any], flat_band: float) -> str:
    values = _path_values(actual_day)
    if len(values) < 2:
        return "chop"
    final = values[-1]
    gross = sum(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
    efficiency = abs(final) / gross if gross > 0 else 0.0
    return "trend" if abs(final) > flat_band and efficiency >= 0.55 else "chop"


def _actual_continuation(actual_day: dict[str, Any], flat_band: float) -> str:
    values = _path_values(actual_day)
    if len(values) < 3:
        return "hold"
    mid = values[len(values) // 2]
    final = values[-1]
    if abs(mid) <= flat_band or abs(final) <= flat_band:
        return "hold"
    if mid * final > 0 and abs(final) >= abs(mid):
        return "continuation"
    if mid * final < 0 or abs(final) < 0.5 * abs(mid):
        return "reversal"
    return "hold"


def _actual_horizon_moves(actual_day: dict[str, Any]) -> dict[str, float]:
    values = _path_values(actual_day)
    net = float(actual_day.get("net_usd") or (values[-1] if values else 0.0))
    gap = float(actual_day.get("overnight_gap_usd") or 0.0)
    if values:
        open_idx = min(6, len(values) - 1)
        settle_idx = min(10, len(values) - 1)
        us_open = values[open_idx]
        settle = values[settle_idx]
    else:
        us_open = net
        settle = net
    return {"overnight": gap, "us_open": us_open, "settle": settle, "close": net}


def score_day(forecast_day: dict[str, Any], actual_day: dict[str, Any]) -> dict[str, Any]:
    dist = forecast_day["move_size_distribution_usd"]
    flat_band = float(dist["flat_band"])
    actual_net = float(actual_day.get("net_usd") or 0.0)
    horizon_moves = _actual_horizon_moves(actual_day)

    direction_scores = {}
    for horizon, actual_move in horizon_moves.items():
        outcome = _classify(actual_move, flat_band)
        direction_scores[horizon] = {
            "actual_move_usd": actual_move,
            "outcome": outcome,
            **_categorical_score(
                forecast_day["direction_probabilities"][horizon],
                outcome,
                DIRECTION_KEYS,
            ),
        }

    quantiles = {0.10: float(dist["p10"]), 0.25: float(dist["p25"]), 0.50: float(dist["p50"]),
                 0.75: float(dist["p75"]), 0.90: float(dist["p90"])}
    pinball = {str(q): round(_pinball(actual_net, value, q), 8) for q, value in quantiles.items()}
    approx_crps = 2.0 * sum(_pinball(actual_net, value, q) for q, value in quantiles.items()) / len(quantiles)

    shape_outcome = _actual_shape(actual_day, flat_band)
    continuation_outcome = _actual_continuation(actual_day, flat_band)
    shape_score = _categorical_score(forecast_day["shape_probabilities"], shape_outcome, ("trend", "chop"))
    cont_score = _categorical_score(
        forecast_day["continuation_reversal_probabilities"],
        continuation_outcome,
        ("continuation", "reversal", "hold"),
    )

    return {
        "date": forecast_day["date"],
        "actual_net_usd": actual_net,
        "regime": forecast_day.get("regime"),
        "direction": direction_scores,
        "magnitude": {
            "error_usd": round(float(dist["p50"]) - actual_net, 8),
            "absolute_error_usd": round(abs(float(dist["p50"]) - actual_net), 8),
            "pinball": pinball,
            "approx_crps": round(approx_crps, 8),
            "p10_p90_covered": bool(float(dist["p10"]) <= actual_net <= float(dist["p90"])),
            "p10_p90_width": round(float(dist["p90"]) - float(dist["p10"]), 8),
        },
        "shape": {"outcome": shape_outcome, **shape_score},
        "continuation_reversal": {"outcome": continuation_outcome, **cont_score},
        "confidence": forecast_day.get("confidence"),
        "data_quality": forecast_day.get("data_quality"),
    }


def _mean(rows: list[float]) -> float | None:
    return None if not rows else round(sum(rows) / len(rows), 8)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        regime = row.get("regime") or {}
        key = "|".join(
            str(regime.get(name, "unknown"))
            for name in ("seasonal_state", "curve_regime", "day_class")
        )
        by_regime[key].append(row)

    def aggregate(group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n": len(group),
            "direction_brier_close": _mean([r["direction"]["close"]["brier"] for r in group]),
            "direction_log_close": _mean([r["direction"]["close"]["log_score"] for r in group]),
            "magnitude_mae_usd": _mean([r["magnitude"]["absolute_error_usd"] for r in group]),
            "magnitude_approx_crps": _mean([r["magnitude"]["approx_crps"] for r in group]),
            "p10_p90_coverage": _mean([1.0 if r["magnitude"]["p10_p90_covered"] else 0.0 for r in group]),
            "shape_brier": _mean([r["shape"]["brier"] for r in group]),
            "continuation_brier": _mean([r["continuation_reversal"]["brier"] for r in group]),
        }

    return {
        "overall": aggregate(rows),
        "by_regime": {key: aggregate(group) for key, group in sorted(by_regime.items())},
        "note": "regimes remain separated; no pooled metric grants execution authority",
    }


def score_forecast(forecast: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    actual_by_date = {row["date"]: row for row in actual.get("days", [])}
    rows = []
    missing_actual = []
    for day in forecast.get("days", []):
        real = actual_by_date.get(day["date"])
        if real is None:
            missing_actual.append(day["date"])
            continue
        rows.append(score_day(day, real))
    return {
        "schema": "ng_proper_score.v1",
        "forecast_schema_version": forecast.get("forecast_schema_version"),
        "brain_version": forecast.get("brain_version"),
        "rows": rows,
        "summary": summarize(rows),
        "missing_actual_days": missing_actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Proper-score an ng.v2 blind forecast")
    parser.add_argument("--forecast", required=True)
    parser.add_argument("--actual", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast = json.loads(Path(args.forecast).read_text(encoding="utf-8"))
    actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    result = score_forecast(forecast, actual)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
