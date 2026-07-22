#!/usr/bin/env python3
"""Convert authorized G16 SHADOW posterior telemetry into renderable daily curves.

The adapter is outcome-blind. It requires the immutable canonical G16 blind
forecast, the fingerprinted G16 SHADOW refinement plan, and a posterior stream
produced by :mod:`ng_g16_shadow_runner`. It never reads target-day actual prices.

Rules:
- the G16 blind object and original file bytes remain immutable;
- the plan and posterior stream must share the same fingerprinted authority chain;
- overnight gaps and the cumulative session-open point are never changed;
- evidence may affect only grid points after its event timestamp;
- STAND_DOWN states are ignored and cannot erase a prior valid adjustment;
- every adjustment is bounded by an explicit SHADOW-only fraction of blind scale;
- outputs cannot update ``ng_brain.json`` or grant execution authority.
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

from ng_g16_shadow_gate import G16_DATES, validate_blind_forecast, validate_shadow_plan
from ng_g16_shadow_runner import (
    STREAM_AUTHORITY,
    STREAM_SCHEMA,
    validate_output as validate_posterior_output,
)

SCHEMA = "ng_g16_refined_curve.v1"
AUTHORITY = "G16_REFINED_CURVE_SHADOW_ONLY"
ET = ZoneInfo("America/New_York")
GRID_HOURS = (20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)


class G16CurveError(ValueError):
    """Raised when the G16 causal curve authority chain cannot be verified."""


@dataclass(frozen=True)
class CurveConfig:
    """Visible, uncalibrated SHADOW transform controls."""

    max_adjustment_fraction: float = 0.50

    def validate(self) -> None:
        if not math.isfinite(self.max_adjustment_fraction):
            raise G16CurveError("max_adjustment_fraction must be finite")
        if not 0.0 <= self.max_adjustment_fraction <= 1.0:
            raise G16CurveError("max_adjustment_fraction must be between 0 and 1")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _artifact_fingerprint(value: Mapping[str, Any], field: str) -> str:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    expected = _fingerprint(payload)
    if not isinstance(observed, str) or observed != expected:
        raise G16CurveError(f"{field} mismatch")
    return observed


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _direction_score(probabilities: Mapping[str, Any]) -> float:
    up = _finite(probabilities.get("up")) or 0.0
    down = _finite(probabilities.get("down")) or 0.0
    return up - down


def _session_grid(day: str) -> list[float]:
    try:
        session_date = datetime.strptime(day, "%Y%m%d").date()
    except ValueError as error:
        raise G16CurveError(f"invalid session day: {day!r}") from error
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


def _validate_curve_shape(
    forecast: Mapping[str, Any], *, require_blind_authority: bool = True
) -> None:
    if require_blind_authority:
        try:
            validate_blind_forecast(forecast)
        except Exception as error:
            raise G16CurveError(f"blind forecast invalid: {error}") from error
    elif int(forecast.get("group") or 0) != 16:
        raise G16CurveError("curve artifact group must be 16")
    days = list(forecast.get("days") or [])
    dates = [str(day.get("date") or "") for day in days]
    if dates != list(G16_DATES):
        raise G16CurveError("curve artifact must contain canonical G16 days in order")
    for day in days:
        date = str(day.get("date") or "")
        curve = list(day.get("guess_curve") or [])
        if len(curve) != len(GRID_HOURS):
            raise G16CurveError(f"{date}: guess_curve must have {len(GRID_HOURS)} points")
        hours = tuple(int(point[0]) for point in curve)
        if hours != GRID_HOURS:
            raise G16CurveError(f"{date}: guess_curve hours differ from canonical grid")
        values = [_finite(point[1]) for point in curve]
        if any(value is None for value in values):
            raise G16CurveError(f"{date}: guess_curve contains a non-finite value")
        if abs(float(values[0])) > 1e-12:
            raise G16CurveError(f"{date}: cumulative-from-open must begin at zero")


def _validate_stream(
    stream: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        validate_shadow_plan(plan)
    except Exception as error:
        raise G16CurveError(f"shadow plan invalid: {error}") from error
    _validate_curve_shape(blind_forecast)
    if plan.get("blind_forecast_fingerprint") != _fingerprint(dict(blind_forecast)):
        raise G16CurveError("plan/blind forecast mismatch")
    if stream.get("schema") != STREAM_SCHEMA or stream.get("authority") != STREAM_AUTHORITY:
        raise G16CurveError("posterior stream schema/authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if stream.get(field) is not False:
            raise G16CurveError(f"posterior stream {field} must remain false")
    if int(stream.get("group") or 0) != 16:
        raise G16CurveError("posterior stream group must be 16")
    if stream.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16CurveError("posterior stream/plan fingerprint mismatch")
    _artifact_fingerprint(stream, "stream_fingerprint")

    outputs = [copy.deepcopy(dict(row)) for row in stream.get("outputs") or []]
    if int(stream.get("n_outputs") or 0) != len(outputs):
        raise G16CurveError("posterior stream n_outputs mismatch")
    blind_by_day = {str(row["date"]): dict(row) for row in blind_forecast["days"]}
    last_day = -1
    last_by_day: dict[str, tuple[float, int]] = {}
    for output in outputs:
        try:
            validate_posterior_output(output)
        except Exception as error:
            raise G16CurveError(f"posterior output invalid: {error}") from error
        day = str(output.get("session_day") or "")
        if day not in G16_DATES:
            raise G16CurveError(f"posterior carries non-G16 day: {day!r}")
        event_time = _finite(output.get("as_of_event_s"))
        if event_time is None:
            raise G16CurveError(f"{day}: posterior lacks finite event time")
        sequence = int(output.get("sequence") or 0)
        index = G16_DATES.index(day)
        current = (event_time, sequence)
        if index < last_day or (day in last_by_day and current <= last_by_day[day]):
            raise G16CurveError("posterior stream is not chronological")
        last_day = index
        last_by_day[day] = current
        day_plan = dict((plan.get("days") or {}).get(day) or {})
        provenance = dict(output.get("provenance") or {})
        if provenance.get("plan_fingerprint") != plan.get("plan_fingerprint"):
            raise G16CurveError(f"{day}: posterior plan provenance mismatch")
        if provenance.get("day_plan_fingerprint") != day_plan.get("day_plan_fingerprint"):
            raise G16CurveError(f"{day}: posterior day-plan provenance mismatch")
        if provenance.get("blind_forecast_day_fingerprint") != _fingerprint(blind_by_day[day]):
            raise G16CurveError(f"{day}: posterior blind-day provenance mismatch")
    return outputs


def _event_grid_index(day: str, event_time: float) -> int:
    grid = _session_grid(day)
    grace_s = 2 * 3600.0
    if event_time < grid[0] - grace_s or event_time > grid[-1] + grace_s:
        raise G16CurveError(f"{day}: posterior event falls outside session grid")
    for index in range(1, len(grid)):
        if event_time <= grid[index]:
            return index
    return len(grid) - 1


def _blind_day_scale(day: Mapping[str, Any]) -> float:
    values = [float(point[1]) for point in day["guess_curve"]]
    net = abs(float(day.get("guessed_net_usd", values[-1])))
    path_range = max(values) - min(values)
    return max(1.0, net, max(abs(value) for value in values), path_range)


def _posterior_target(
    output: Mapping[str, Any], scale: float, config: CurveConfig
) -> float | None:
    if output.get("status") == "STAND_DOWN":
        return None
    shift = _direction_score(dict(output.get("posterior") or {})) - _direction_score(
        dict(output.get("blind_prior") or {})
    )
    strength = _clip(
        _finite((output.get("scores") or {}).get("update_strength")) or 0.0,
        0.0,
        1.0,
    )
    cap = scale * config.max_adjustment_fraction
    return _clip(shift * cap * strength, -cap, cap)


def _curve_with_causal_adjustments(
    day: Mapping[str, Any],
    outputs: Sequence[Mapping[str, Any]],
    config: CurveConfig,
    *,
    plan_fingerprint: str,
    stream_fingerprint: str,
) -> tuple[list[list[int]], dict[str, Any]]:
    date = str(day["date"])
    base = [float(point[1]) for point in day["guess_curve"]]
    scale = _blind_day_scale(day)
    scheduled: dict[int, list[tuple[Mapping[str, Any], float]]] = {}
    used: list[Mapping[str, Any]] = []
    ignored = 0
    for output in sorted(
        outputs,
        key=lambda row: (float(row["as_of_event_s"]), int(row.get("sequence") or 0)),
    ):
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
            latest_used, active_target = scheduled[index][-1]
            active_start_adjustment = adjustments[index - 1]
            active_start_index = index
        denominator = max(1, len(base) - active_start_index)
        progress = _clip((index - active_start_index + 1) / denominator, 0.0, 1.0)
        adjustments[index] = active_start_adjustment + (
            active_target - active_start_adjustment
        ) * progress

    refined_values = [int(round(base[index] + adjustments[index])) for index in range(len(base))]
    refined_values[0] = 0
    curve = [
        [int(day["guess_curve"][index][0]), refined_values[index]]
        for index in range(len(base))
    ]
    blind_probabilities = dict(outputs[0].get("blind_prior") or {}) if outputs else None
    refined_probabilities = (
        dict(latest_used.get("posterior") or {}) if latest_used is not None else blind_probabilities
    )
    candidate_ids = sorted(
        {
            str(identifier)
            for output in used
            for identifier in output.get("authorized_candidate_ids") or []
        }
    )
    audit = {
        "schema": "ng_g16_curve_day_audit.v1",
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
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
        "authorized_candidate_ids_used": candidate_ids,
        "source_output_fingerprints": [str(row.get("output_fingerprint")) for row in used],
        "plan_fingerprint": plan_fingerprint,
        "posterior_stream_fingerprint": stream_fingerprint,
        "causal_rule": (
            "Each authorized non-stand-down posterior sets a bounded close adjustment at the next "
            "two-hour grid boundary; the adjustment ramps only through future points."
        ),
    }
    audit["audit_fingerprint"] = _fingerprint(audit)
    return curve, audit


def build_refined_forecast(
    blind_forecast: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    *,
    blind_file_bytes: bytes | None = None,
    config: CurveConfig | None = None,
) -> dict[str, Any]:
    """Return a ``continuous_rt.py``-compatible G16 SHADOW refined forecast."""
    config = config or CurveConfig()
    config.validate()
    _validate_curve_shape(blind_forecast)
    outputs = _validate_stream(
        posterior_stream, plan=shadow_plan, blind_forecast=blind_forecast
    )
    before = copy.deepcopy(dict(blind_forecast))
    blind_bytes = (
        blind_file_bytes
        if blind_file_bytes is not None
        else (_canonical(blind_forecast) + "\n").encode("utf-8")
    )
    blind_hash = _sha256_bytes(blind_bytes)
    by_day: dict[str, list[dict[str, Any]]] = {day: [] for day in G16_DATES}
    for output in outputs:
        by_day[str(output["session_day"])].append(output)

    refined_days: list[dict[str, Any]] = []
    for raw_day in blind_forecast["days"]:
        day = copy.deepcopy(dict(raw_day))
        curve, audit = _curve_with_causal_adjustments(
            day,
            by_day[day["date"]],
            config,
            plan_fingerprint=str(shadow_plan.get("plan_fingerprint") or ""),
            stream_fingerprint=str(posterior_stream.get("stream_fingerprint") or ""),
        )
        day["guess_curve"] = curve
        day["guessed_net_usd"] = curve[-1][1]
        day["refinement_audit"] = audit
        refined_days.append(day)

    result = copy.deepcopy(dict(blind_forecast))
    result.update(
        {
            "schema": SCHEMA,
            "tag": "g16_mbo_refined",
            "kind": "causal_shadow_refinement",
            "authority": AUTHORITY,
            "execution_authority": False,
            "actual_g16_outcomes_used": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
            "calibration_status": "SHADOW_UNCALIBRATED",
            "source_blind_tag": blind_forecast.get("tag"),
            "source_blind_kind": blind_forecast.get("kind"),
            "source_brain_version": blind_forecast.get("brain_version"),
            "brain_version": blind_forecast.get("brain_version"),
            "blind_forecast_sha256": blind_hash,
            "shadow_plan_fingerprint": shadow_plan.get("plan_fingerprint"),
            "posterior_stream_fingerprint": posterior_stream.get("stream_fingerprint"),
            "authorization_stream_fingerprint": posterior_stream.get(
                "authorization_stream_fingerprint"
            ),
            "transform_config": asdict(config),
            "days": refined_days,
            "note": (
                "Outcome-blind authorized G16 posterior-to-curve transform for continuous_rt.py. "
                "Overnight gaps and the committed blind artifact remain unchanged."
            ),
        }
    )
    if dict(blind_forecast) != before:
        raise G16CurveError("blind forecast object mutated during curve construction")
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_refined_forecast(result, blind_forecast=blind_forecast)
    return result


def validate_refined_forecast(
    artifact: Mapping[str, Any],
    *,
    blind_forecast: Mapping[str, Any] | None = None,
) -> None:
    if artifact.get("schema") != SCHEMA or artifact.get("authority") != AUTHORITY:
        raise G16CurveError("refined curve schema/authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if artifact.get(field) is not False:
            raise G16CurveError(f"refined curve {field} must remain false")
    _artifact_fingerprint(artifact, "artifact_fingerprint")
    _validate_curve_shape(artifact, require_blind_authority=False)
    if blind_forecast is None:
        return
    _validate_curve_shape(blind_forecast)
    blind_by_day = {day["date"]: day for day in blind_forecast["days"]}
    for day in artifact["days"]:
        blind = blind_by_day[day["date"]]
        if day.get("overnight_gap_usd", 0) != blind.get("overnight_gap_usd", 0):
            raise G16CurveError(f"{day['date']}: refinement changed the overnight gap")
        if day["guess_curve"][0][1] != 0:
            raise G16CurveError(f"{day['date']}: refinement changed cumulative open")
        audit = dict(day.get("refinement_audit") or {})
        if audit.get("actual_g16_outcomes_used") is not False:
            raise G16CurveError(f"{day['date']}: day audit is not outcome-blind")
        if audit.get("may_update_ng_brain") is not False:
            raise G16CurveError(f"{day['date']}: day audit can update brain")
        if audit.get("may_change_g16_blind_prior") is not False:
            raise G16CurveError(f"{day['date']}: day audit can change blind prior")
        if int(audit.get("outputs_used") or 0) == 0 and day["guess_curve"] != blind["guess_curve"]:
            raise G16CurveError(f"{day['date']}: curve changed without usable posterior evidence")
        if day["guessed_net_usd"] != day["guess_curve"][-1][1]:
            raise G16CurveError(f"{day['date']}: guessed net differs from curve endpoint")
        _artifact_fingerprint(audit, "audit_fingerprint")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _fixture_forecast() -> dict[str, Any]:
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
                "guess_curve": [[hour, -25 * point] for point, hour in enumerate(GRID_HOURS)],
                "guessed_net_usd": -300,
            }
            for day in G16_DATES
        ],
    }


def _fixture_output(day: str, forecast: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    blind_day = next(row for row in forecast["days"] if row["date"] == day)
    candidate_ids = list((plan.get("days") or {}).get(day, {}).get("allowed_candidate_ids") or [])
    output = {
        "schema": "ng_g16_shadow_posterior.v1",
        "market": "NG",
        "group": 16,
        "session_day": day,
        "sequence": 1,
        "horizon": "close",
        "as_of_event_s": _session_grid(day)[7] - 60,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "status": "UPDATED",
        "blind_prior": {"up": 0.4, "flat": 0.2, "down": 0.4},
        "posterior": {"up": 0.7, "flat": 0.1, "down": 0.2},
        "scores": {
            "directional_log_weight": 0.5,
            "flat_log_weight": 0.0,
            "update_strength": 1.0,
        },
        "attribution": [],
        "authorized_candidate_ids": candidate_ids,
        "implemented_candidate_ids": [],
        "unhandled_candidate_ids": candidate_ids,
        "stand_down_reasons": [],
        "provenance": {
            "plan_fingerprint": plan["plan_fingerprint"],
            "day_plan_fingerprint": plan["days"][day]["day_plan_fingerprint"],
            "authorization_fingerprint": "auth",
            "feature_fingerprint": "feature",
            "blind_prior_fingerprint": "prior",
            "blind_forecast_day_fingerprint": _fingerprint(blind_day),
        },
    }
    output["output_fingerprint"] = _fingerprint(output)
    return output


def selftest() -> int:
    forecast = _fixture_forecast()
    from ng_g16_shadow_gate import _fixture_blind_state, _fixture_registry, build_shadow_plan

    plan = build_shadow_plan(forecast, _fixture_blind_state(), _fixture_registry())
    output = _fixture_output(G16_DATES[0], forecast, plan)
    stream = {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": STREAM_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan["plan_fingerprint"],
        "authorization_stream_fingerprint": "auth-stream",
        "n_outputs": 1,
        "outputs": [output],
    }
    stream["stream_fingerprint"] = _fingerprint(stream)
    before = copy.deepcopy(forecast)
    result = build_refined_forecast(forecast, plan, stream)
    assert forecast == before
    assert result["days"][0]["guess_curve"][0][1] == 0
    assert result["days"][0]["guessed_net_usd"] > forecast["days"][0]["guessed_net_usd"]
    assert result["days"][1]["guess_curve"] == forecast["days"][1]["guess_curve"]
    validate_refined_forecast(result, blind_forecast=forecast)
    print("[ng_g16_curve_adapter] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build outcome-blind G16 refined curves from authorized SHADOW posteriors"
    )
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--posterior-stream", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-adjustment-fraction", type=float, default=0.50)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(getattr(args, name) is None for name in ("blind", "plan", "posterior_stream", "out")):
        parser.error("--blind --plan --posterior-stream --out are required")
    blind_bytes = args.blind.read_bytes()
    blind = json.loads(blind_bytes.decode("utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    stream = json.loads(args.posterior_stream.read_text(encoding="utf-8"))
    result = build_refined_forecast(
        blind,
        plan,
        stream,
        blind_file_bytes=blind_bytes,
        config=CurveConfig(max_adjustment_fraction=args.max_adjustment_fraction),
    )
    _atomic_json(args.out, result)
    changed = sum(
        int(day["refinement_audit"]["outputs_used"] > 0) for day in result["days"]
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "artifact_fingerprint": result["artifact_fingerprint"],
                "blind_forecast_sha256": result["blind_forecast_sha256"],
                "days_with_usable_updates": changed,
                "actual_g16_outcomes_used": False,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
