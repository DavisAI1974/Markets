#!/usr/bin/env python3
"""Convert causal G15 SHADOW posterior states into a renderable daily curve.

This adapter is intentionally outcome-blind. It accepts only the immutable blind
forecast and ``ng_rt_refine_stream.v1`` posterior telemetry. Target-day actual
prices are not an input. The output keeps the canonical ``grp15.json`` day shape
used by ``continuous_rt.py`` while attaching an auditable causal transformation.

Rules:
- overnight gaps are never changed by target-session evidence;
- cumulative-from-open remains zero at the first curve point;
- a posterior may affect only grid points after its event timestamp;
- STAND_DOWN states do not create or erase an existing adjustment;
- the adjustment is capped as an explicit fraction of the blind day scale;
- the blind forecast object and file bytes remain immutable.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from ng_historical_manifest import G15_DATES
from ng_rt_refiner import validate_refine_output

SCHEMA = "ng_g15_refined_curve.v1"
STREAM_SCHEMA = "ng_rt_refine_stream.v1"
AUTHORITY = "REFINED_CURVE_SHADOW_ONLY"
ET = ZoneInfo("America/New_York")
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)


class CurveError(ValueError):
    """Raised when a causal curve transformation cannot be verified."""


@dataclass(frozen=True)
class CurveConfig:
    """Explicit uncalibrated transformation controls.

    ``max_adjustment_fraction`` is deliberately visible in every output. It is a
    SHADOW transform bound, not a learned trading threshold.
    """

    max_adjustment_fraction: float = 0.50

    def validate(self) -> None:
        if not math.isfinite(self.max_adjustment_fraction):
            raise CurveError("max_adjustment_fraction must be finite")
        if not 0.0 <= self.max_adjustment_fraction <= 1.0:
            raise CurveError("max_adjustment_fraction must be between 0 and 1")


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


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _direction_score(probabilities: Mapping[str, Any]) -> float:
    up = _finite(probabilities.get("up")) or 0.0
    down = _finite(probabilities.get("down")) or 0.0
    return up - down


def _session_grid(day: str) -> list[float]:
    try:
        session_date = datetime.strptime(day, "%Y%m%d").date()
    except ValueError as error:
        raise CurveError(f"invalid session day: {day!r}") from error
    prior = session_date - timedelta(days=1)
    local = [
        datetime(prior.year, prior.month, prior.day, 20, tzinfo=ET),
        datetime(prior.year, prior.month, prior.day, 22, tzinfo=ET),
    ]
    local.extend(
        datetime(session_date.year, session_date.month, session_date.day, hour, tzinfo=ET)
        for hour in range(0, 21, 2)
    )
    return [value.timestamp() for value in local]


def _validate_blind_forecast(forecast: Mapping[str, Any]) -> None:
    if int(forecast.get("group") or 0) != 15:
        raise CurveError("blind forecast group must be 15")
    days = list(forecast.get("days") or [])
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G15_DATES):
        raise CurveError("blind forecast must contain canonical G15 days in order")
    for day in days:
        date = str(day["date"])
        curve = list(day.get("guess_curve") or [])
        if len(curve) != len(GRID_HOURS):
            raise CurveError(f"{date}: guess_curve must have {len(GRID_HOURS)} points")
        hours = tuple(int(point[0]) for point in curve)
        if hours != GRID_HOURS:
            raise CurveError(f"{date}: guess_curve hours differ from canonical grid")
        values = [_finite(point[1]) for point in curve]
        if any(value is None for value in values):
            raise CurveError(f"{date}: guess_curve contains a non-finite value")
        if abs(float(values[0])) > 1e-12:
            raise CurveError(f"{date}: cumulative-from-open must begin at zero")


def _validate_refine_stream(stream: Mapping[str, Any]) -> list[dict[str, Any]]:
    if stream.get("schema") != STREAM_SCHEMA:
        raise CurveError(f"unexpected refine stream schema: {stream.get('schema')}")
    if int(stream.get("group") or 0) != 15:
        raise CurveError("refine stream group must be 15")
    if stream.get("authority") != "REFINE_POSTERIOR_STREAM_ONLY":
        raise CurveError("refine stream authority is invalid")
    if stream.get("execution_authority") is not False:
        raise CurveError("refine stream cannot grant execution authority")
    outputs = [copy.deepcopy(row) for row in stream.get("outputs") or []]
    previous: float | None = None
    for output in outputs:
        validate_refine_output(output)
        day = str(output.get("session_day") or "")
        if day not in G15_DATES:
            raise CurveError(f"refine output carries non-G15 day: {day!r}")
        event_time = _finite(output.get("as_of_event_s"))
        if event_time is None:
            raise CurveError(f"{day}: refine output lacks finite event time")
        if previous is not None and event_time < previous:
            raise CurveError("refine stream moved backwards")
        previous = event_time
    if int(stream.get("n_outputs") or 0) != len(outputs):
        raise CurveError("refine stream n_outputs mismatch")
    return outputs


def _event_grid_index(day: str, event_time: float) -> int:
    grid = _session_grid(day)
    grace_s = 2 * 3600.0
    if event_time < grid[0] - grace_s or event_time > grid[-1] + grace_s:
        raise CurveError(f"{day}: event falls outside the session grid")
    # Curve point zero is the session open and must remain zero. Evidence observed
    # before the nominal first grid mark may begin affecting point one, never zero.
    for index in range(1, len(grid)):
        if event_time <= grid[index]:
            return index
    return len(grid) - 1


def _blind_day_scale(day: Mapping[str, Any]) -> float:
    values = [float(point[1]) for point in day["guess_curve"]]
    net = abs(float(day.get("guessed_net_usd", values[-1])))
    path_range = max(values) - min(values)
    return max(1.0, net, max(abs(value) for value in values), path_range)


def _posterior_target(output: Mapping[str, Any], scale: float, config: CurveConfig) -> float | None:
    availability = dict(output.get("availability") or {})
    if output.get("status") == "STAND_DOWN" or not availability.get("refine_update_allowed"):
        return None
    shift = _direction_score(dict(output.get("posterior") or {})) - _direction_score(
        dict(output.get("blind_prior") or {})
    )
    strength = _clip(_finite((output.get("scores") or {}).get("update_strength")) or 0.0, 0.0, 1.0)
    cap = scale * config.max_adjustment_fraction
    return _clip(shift * cap * strength, -cap, cap)


def _curve_with_causal_adjustments(
    day: Mapping[str, Any],
    outputs: Sequence[Mapping[str, Any]],
    config: CurveConfig,
) -> tuple[list[list[int]], dict[str, Any]]:
    date = str(day["date"])
    base = [float(point[1]) for point in day["guess_curve"]]
    scale = _blind_day_scale(day)
    scheduled: dict[int, list[tuple[Mapping[str, Any], float]]] = {}
    used: list[Mapping[str, Any]] = []
    ignored = 0
    for output in sorted(outputs, key=lambda row: (float(row["as_of_event_s"]), int(row.get("sequence") or 0))):
        target = _posterior_target(output, scale, config)
        if target is None:
            ignored += 1
            continue
        index = _event_grid_index(date, float(output["as_of_event_s"]))
        scheduled.setdefault(index, []).append((output, target))
        used.append(output)

    adjustments = [0.0 for _ in base]
    active_target = 0.0
    active_start_adjustment = 0.0
    active_start_index = 1
    latest_used: Mapping[str, Any] | None = None
    for index in range(1, len(base)):
        if index in scheduled:
            # The last state at the same grid boundary is the most recent causal view.
            latest_used, active_target = scheduled[index][-1]
            active_start_adjustment = adjustments[index - 1]
            active_start_index = index
        denominator = max(1, len(base) - active_start_index)
        progress = (index - active_start_index + 1) / denominator
        progress = _clip(progress, 0.0, 1.0)
        adjustments[index] = active_start_adjustment + (
            active_target - active_start_adjustment
        ) * progress

    refined_values = [int(round(base[index] + adjustments[index])) for index in range(len(base))]
    refined_values[0] = 0
    curve = [[int(day["guess_curve"][index][0]), refined_values[index]] for index in range(len(base))]
    blind_probabilities = dict(outputs[0].get("blind_prior") or {}) if outputs else None
    refined_probabilities = (
        dict(latest_used.get("posterior") or {}) if latest_used is not None else blind_probabilities
    )
    audit = {
        "schema": "ng_g15_curve_day_audit.v1",
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_outcomes_used": False,
        "date": date,
        "blind_scale_usd": round(scale, 8),
        "max_adjustment_fraction": config.max_adjustment_fraction,
        "outputs_seen": len(outputs),
        "outputs_used": len(used),
        "outputs_ignored_or_stood_down": ignored,
        "first_used_event_s": used[0].get("as_of_event_s") if used else None,
        "last_used_event_s": used[-1].get("as_of_event_s") if used else None,
        "endpoint_adjustment_usd": int(round(adjustments[-1])),
        "max_abs_curve_adjustment_usd": int(round(max(abs(value) for value in adjustments))),
        "blind_direction_probabilities": blind_probabilities,
        "refined_direction_probabilities": refined_probabilities,
        "source_output_fingerprints": [str(row.get("output_fingerprint")) for row in used],
        "causal_rule": (
            "Each valid posterior sets a bounded close target at the next 2-hour grid boundary; "
            "the adjustment ramps only through remaining future points. STAND_DOWN states are ignored."
        ),
    }
    audit["audit_fingerprint"] = _fingerprint(audit)
    return curve, audit


def build_refined_forecast(
    blind_forecast: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    *,
    blind_file_bytes: bytes | None = None,
    config: CurveConfig | None = None,
) -> dict[str, Any]:
    """Return a ``continuous_rt.py``-compatible causal refined forecast."""
    config = config or CurveConfig()
    config.validate()
    _validate_blind_forecast(blind_forecast)
    outputs = _validate_refine_stream(refine_stream)
    before = copy.deepcopy(dict(blind_forecast))
    blind_bytes = blind_file_bytes if blind_file_bytes is not None else (_canonical(blind_forecast) + "\n").encode("utf-8")
    blind_hash = _sha256_bytes(blind_bytes)

    by_day: dict[str, list[dict[str, Any]]] = {day: [] for day in G15_DATES}
    for output in outputs:
        by_day[str(output["session_day"])].append(output)

    refined_days: list[dict[str, Any]] = []
    for raw_day in blind_forecast["days"]:
        day = copy.deepcopy(dict(raw_day))
        curve, audit = _curve_with_causal_adjustments(day, by_day[day["date"]], config)
        day["guess_curve"] = curve
        day["guessed_net_usd"] = curve[-1][1]
        day["refinement_audit"] = audit
        refined_days.append(day)

    result = copy.deepcopy(dict(blind_forecast))
    result.update(
        {
            "schema": SCHEMA,
            "tag": "g15_mbo_refined",
            "authority": AUTHORITY,
            "execution_authority": False,
            "actual_outcomes_used": False,
            "may_update_ng_brain": False,
            "calibration_status": "SHADOW_UNCALIBRATED",
            "source_blind_tag": blind_forecast.get("tag"),
            "source_brain_version": blind_forecast.get("brain_version"),
            "brain_version": blind_forecast.get("brain_version"),
            "blind_forecast_sha256": blind_hash,
            "refine_stream_fingerprint": _fingerprint(refine_stream),
            "transform_config": asdict(config),
            "days": refined_days,
            "note": (
                "Outcome-blind posterior-to-curve transform for continuous_rt.py. "
                "Overnight gaps and the committed blind artifact remain unchanged."
            ),
        }
    )
    if dict(blind_forecast) != before:
        raise CurveError("blind forecast object mutated during curve construction")
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_refined_forecast(result, blind_forecast=blind_forecast)
    return result


def validate_refined_forecast(
    artifact: Mapping[str, Any],
    *,
    blind_forecast: Mapping[str, Any] | None = None,
) -> None:
    if artifact.get("schema") != SCHEMA:
        raise CurveError(f"unexpected refined curve schema: {artifact.get('schema')}")
    if artifact.get("authority") != AUTHORITY or artifact.get("execution_authority") is not False:
        raise CurveError("refined curve authority is invalid")
    if artifact.get("actual_outcomes_used") is not False:
        raise CurveError("refined curve must be outcome-blind")
    if artifact.get("may_update_ng_brain") is not False:
        raise CurveError("refined curve cannot update ng_brain")
    fingerprint = artifact.get("artifact_fingerprint")
    payload = copy.deepcopy(dict(artifact))
    payload.pop("artifact_fingerprint", None)
    if fingerprint != _fingerprint(payload):
        raise CurveError("refined curve fingerprint mismatch")
    _validate_blind_forecast(artifact)
    if blind_forecast is None:
        return
    _validate_blind_forecast(blind_forecast)
    blind_by_day = {day["date"]: day for day in blind_forecast["days"]}
    for day in artifact["days"]:
        blind = blind_by_day[day["date"]]
        if day.get("overnight_gap_usd", 0) != blind.get("overnight_gap_usd", 0):
            raise CurveError(f"{day['date']}: refinement changed the overnight gap")
        if day["guess_curve"][0][1] != 0:
            raise CurveError(f"{day['date']}: refinement changed cumulative open")
        audit = dict(day.get("refinement_audit") or {})
        if audit.get("actual_outcomes_used") is not False:
            raise CurveError(f"{day['date']}: day audit is not outcome-blind")
        if int(audit.get("outputs_used") or 0) == 0 and day["guess_curve"] != blind["guess_curve"]:
            raise CurveError(f"{day['date']}: curve changed without usable posterior evidence")
        if day["guessed_net_usd"] != day["guess_curve"][-1][1]:
            raise CurveError(f"{day['date']}: guessed net differs from curve endpoint")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def selftest() -> int:
    from ng_rt_refiner import output_fingerprint

    days = []
    outputs = []
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    for index, day in enumerate(G15_DATES):
        days.append(
            {
                "date": day,
                "dow": "X",
                "overnight_gap_usd": 0,
                "guess_curve": [[hour, -25 * point] for point, hour in enumerate(GRID_HOURS)],
                "guessed_net_usd": -300,
            }
        )
        output = {
            "schema": "ng_rt_refine_output.v1",
            "source_mode": "historical_replay",
            "session_day": day,
            "sequence": index + 1,
            "horizon": "close",
            "as_of_event_s": _session_grid(day)[7] - 60,
            "authority": "REFINE_POSTERIOR_ONLY",
            "execution_authority": False,
            "blind_prior": prior,
            "blind_prior_fingerprint": "blind",
            "feature_fingerprint": f"feature-{day}",
            "anchor_fingerprint": "anchor",
            "posterior": {"up": 0.7, "flat": 0.1, "down": 0.2},
            "status": "UPDATED",
            "scores": {"directional_log_weight": 0.2, "flat_log_weight": 0.0, "update_strength": 1.0},
            "attribution": [],
            "availability": {
                "flow_update_allowed": True,
                "queue_update_allowed": True,
                "refine_update_allowed": True,
                "stand_down_reasons": [],
            },
            "provenance": {
                "feature_schema": "ng_rt_feature_state.v1",
                "anchor_schema": "ng_g15_anchor.v1",
                "blind_artifact_mutated": False,
                "same_contract_for_historical_and_live": True,
                "threshold_status": "SHADOW_UNTIL_WALK_FORWARD_CALIBRATION",
            },
        }
        output["output_fingerprint"] = output_fingerprint(output)
        outputs.append(output)
    blind = {"group": 15, "tag": "g15", "brain_version": "test", "days": days}
    stream = {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "anchor",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    before = copy.deepcopy(blind)
    result = build_refined_forecast(blind, stream)
    assert blind == before
    assert result["days"][0]["guess_curve"][0][1] == 0
    assert result["days"][0]["guessed_net_usd"] > blind["days"][0]["guessed_net_usd"]
    assert result["actual_outcomes_used"] is False
    validate_refined_forecast(result, blind_forecast=blind)
    print("[ng_g15_curve_adapter] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build outcome-blind G15 refined curves from causal posterior states")
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--refine-stream", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-adjustment-fraction", type=float, default=0.50)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.blind or not args.refine_stream or not args.out:
        parser.error("--blind, --refine-stream, and --out are required")
    blind_bytes = args.blind.read_bytes()
    blind = json.loads(blind_bytes.decode("utf-8"))
    stream = json.loads(args.refine_stream.read_text(encoding="utf-8"))
    result = build_refined_forecast(
        blind,
        stream,
        blind_file_bytes=blind_bytes,
        config=CurveConfig(max_adjustment_fraction=args.max_adjustment_fraction),
    )
    _atomic_json(args.out, result)
    changed = sum(
        int(day["refinement_audit"]["outputs_used"] > 0)
        for day in result["days"]
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "artifact_fingerprint": result["artifact_fingerprint"],
                "blind_forecast_sha256": result["blind_forecast_sha256"],
                "days_with_usable_updates": changed,
                "actual_outcomes_used": False,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
