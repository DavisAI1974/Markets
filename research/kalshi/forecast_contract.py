#!/usr/bin/env python3
"""Versioned output contract for the existing NG blind forecaster.

The contract does not forecast. It validates that the existing agent output is
numerically defined, internally coherent, and suitable for calibration scoring.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "ng.v2"
HORIZONS = ("overnight", "us_open", "settle", "close")
DIRECTION_KEYS = ("up", "flat", "down")
SHAPE_KEYS = ("trend", "chop")
PATH_KEYS = ("p10", "p50", "p90")
CONTINUATION_KEYS = ("continuation", "reversal", "hold")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _probability_map(value: Any, keys: tuple[str, ...], path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return
    missing = [key for key in keys if key not in value]
    if missing:
        errors.append(f"{path}: missing {missing}")
        return
    vals = []
    for key in keys:
        raw = value.get(key)
        if not _finite(raw) or not 0.0 <= float(raw) <= 1.0:
            errors.append(f"{path}.{key}: expected probability in [0,1]")
        else:
            vals.append(float(raw))
    if len(vals) == len(keys) and abs(sum(vals) - 1.0) > 1e-6:
        errors.append(f"{path}: probabilities sum to {sum(vals):.8f}, not 1.0")


def _check_quantiles(dist: Any, path: str, errors: list[str]) -> None:
    if not isinstance(dist, dict):
        errors.append(f"{path}: expected object")
        return
    required = ("flat_band", "mean", "stdev", "p10", "p25", "p50", "p75", "p90", "bins")
    for key in required:
        if key not in dist:
            errors.append(f"{path}: missing {key}")
    numeric = [dist.get(key) for key in ("flat_band", "mean", "stdev", "p10", "p25", "p50", "p75", "p90")]
    if any(not _finite(value) for value in numeric):
        errors.append(f"{path}: non-finite numeric field")
        return
    if float(dist["flat_band"]) < 0 or float(dist["stdev"]) < 0:
        errors.append(f"{path}: flat_band and stdev must be non-negative")
    q = [float(dist[key]) for key in ("p10", "p25", "p50", "p75", "p90")]
    if q != sorted(q):
        errors.append(f"{path}: quantiles are not monotone: {q}")
    bins = dist.get("bins")
    if not isinstance(bins, list) or not bins:
        errors.append(f"{path}.bins: expected non-empty list")
    else:
        total = 0.0
        for idx, row in enumerate(bins):
            if not isinstance(row, dict):
                errors.append(f"{path}.bins[{idx}]: expected object")
                continue
            p = row.get("probability")
            if not _finite(p) or not 0.0 <= float(p) <= 1.0:
                errors.append(f"{path}.bins[{idx}].probability: invalid")
            else:
                total += float(p)
        if abs(total - 1.0) > 1e-6:
            errors.append(f"{path}.bins: probabilities sum to {total:.8f}, not 1.0")


def _check_path(rows: Any, path: str, errors: list[str]) -> None:
    if not isinstance(rows, list) or not rows:
        errors.append(f"{path}: expected non-empty list")
        return
    last_hr: float | None = None
    for idx, row in enumerate(rows):
        p = f"{path}[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{p}: expected object")
            continue
        if not _finite(row.get("et_hr")):
            errors.append(f"{p}.et_hr: expected finite number")
            continue
        hour = float(row["et_hr"])
        if last_hr is not None and hour == last_hr:
            errors.append(f"{p}.et_hr: duplicate adjacent grid hour")
        last_hr = hour
        vals = [row.get(key) for key in PATH_KEYS]
        if any(not _finite(value) for value in vals):
            errors.append(f"{p}: p10/p50/p90 must be finite")
            continue
        if not float(vals[0]) <= float(vals[1]) <= float(vals[2]):
            errors.append(f"{p}: uncertainty bands are not ordered")


def validate_day(day: dict[str, Any], idx: int) -> list[str]:
    path = f"days[{idx}]"
    errors: list[str] = []
    required = (
        "date", "dow", "archetype", "regime", "rule_trace", "direction_probabilities",
        "move_size_distribution_usd", "timing_windows", "shape_probabilities",
        "continuation_reversal_probabilities", "path_distribution", "guess_curve",
        "guessed_net_usd", "confidence", "data_quality",
    )
    for key in required:
        if key not in day:
            errors.append(f"{path}: missing {key}")

    probs = day.get("direction_probabilities")
    if not isinstance(probs, dict):
        errors.append(f"{path}.direction_probabilities: expected object")
    else:
        for horizon in HORIZONS:
            _probability_map(probs.get(horizon), DIRECTION_KEYS, f"{path}.direction_probabilities.{horizon}", errors)

    _probability_map(day.get("shape_probabilities"), SHAPE_KEYS, f"{path}.shape_probabilities", errors)
    _probability_map(
        day.get("continuation_reversal_probabilities"),
        CONTINUATION_KEYS,
        f"{path}.continuation_reversal_probabilities",
        errors,
    )
    _check_quantiles(day.get("move_size_distribution_usd"), f"{path}.move_size_distribution_usd", errors)
    _check_path(day.get("path_distribution"), f"{path}.path_distribution", errors)

    trace = day.get("rule_trace")
    if not isinstance(trace, list) or not trace:
        errors.append(f"{path}.rule_trace: expected at least one evaluated rule")
    else:
        for ridx, row in enumerate(trace):
            if not isinstance(row, dict) or not row.get("rule_id"):
                errors.append(f"{path}.rule_trace[{ridx}]: missing rule_id")
            if isinstance(row, dict) and "scope_pass" not in row:
                errors.append(f"{path}.rule_trace[{ridx}]: missing scope_pass")

    confidence = day.get("confidence")
    if not isinstance(confidence, dict):
        errors.append(f"{path}.confidence: expected object")
    else:
        for key in ("overall", "direction", "magnitude", "timing"):
            value = confidence.get(key)
            if not _finite(value) or not 0.0 <= float(value) <= 1.0:
                errors.append(f"{path}.confidence.{key}: expected probability in [0,1]")

    quality = day.get("data_quality")
    if not isinstance(quality, dict):
        errors.append(f"{path}.data_quality: expected object")
    else:
        if "blind_wall_passed" not in quality:
            errors.append(f"{path}.data_quality: missing blind_wall_passed")
        if not isinstance(quality.get("flags", []), list):
            errors.append(f"{path}.data_quality.flags: expected list")

    point = day.get("guessed_net_usd")
    dist = day.get("move_size_distribution_usd")
    if _finite(point) and isinstance(dist, dict) and _finite(dist.get("p50")):
        if abs(float(point) - float(dist["p50"])) > 1e-6:
            errors.append(f"{path}: guessed_net_usd must equal distribution p50")
    return errors


def validate_forecast(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("forecast_schema_version") != SCHEMA_VERSION:
        errors.append(
            f"forecast_schema_version: expected {SCHEMA_VERSION}, got {payload.get('forecast_schema_version')!r}"
        )
    days = payload.get("days")
    if not isinstance(days, list) or not days:
        errors.append("days: expected non-empty list")
    else:
        for idx, day in enumerate(days):
            if not isinstance(day, dict):
                errors.append(f"days[{idx}]: expected object")
            else:
                errors.extend(validate_day(day, idx))
    return {
        "schema": "forecast_contract_validation.v1",
        "forecast_schema_version": payload.get("forecast_schema_version"),
        "passed": not errors,
        "n_errors": len(errors),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an NG blind forecast against ng.v2")
    parser.add_argument("--forecast", required=True)
    parser.add_argument("--report-out")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = json.loads(Path(args.forecast).read_text(encoding="utf-8"))
    report = validate_forecast(payload)
    if args.report_out:
        Path(args.report_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
