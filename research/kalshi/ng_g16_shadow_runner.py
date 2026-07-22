#!/usr/bin/env python3
"""Outcome-blind G16 posterior runner for gate-authorized causal states."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from ng_g16_shadow_gate import (
    G16_DATES,
    STREAM_SCHEMA as AUTH_STREAM_SCHEMA,
    validate_authorization_token,
    validate_blind_forecast,
    validate_shadow_plan,
)
from ng_rt_feature_state import validate_feature_state

SCHEMA = "ng_g16_shadow_posterior.v1"
STREAM_SCHEMA = "ng_g16_shadow_posterior_stream.v1"
AUTHORITY = "G16_CAUSAL_SHADOW_POSTERIOR_ONLY"
STREAM_AUTHORITY = "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY"
KNOWN = {
    "g15_mbo.signed_flow",
    "g15_mbo.far_side_recruitment",
    "g15_mbo.divergence_exhaustion",
}


class G16ShadowRunnerError(ValueError):
    pass


def _fp(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _norm(value: Mapping[str, Any]) -> dict[str, float]:
    result = {key: max(0.0, _finite(value.get(key))) for key in ("up", "flat", "down")}
    total = sum(result.values())
    if total <= 0:
        raise G16ShadowRunnerError("probabilities must carry positive mass")
    return {key: result[key] / total for key in result}


def _output_fp(output: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(output))
    payload.pop("output_fingerprint", None)
    return _fp(payload)


def _blind_day(forecast: Mapping[str, Any], day: str) -> dict[str, Any]:
    rows = [dict(row) for row in forecast.get("days") or [] if row.get("date") == day]
    if len(rows) != 1:
        raise G16ShadowRunnerError(f"{day}: one blind day required")
    return rows[0]


def _queue_sign(queue: Mapping[str, Any]) -> float:
    return {"ASK": 1.0, "BID": -1.0}.get(str(queue.get("consumed_side") or "").upper(), 0.0)


def run_state(plan: Mapping[str, Any], forecast: Mapping[str, Any],
              state: Mapping[str, Any], token: Mapping[str, Any]) -> dict[str, Any]:
    originals = [copy.deepcopy(dict(value)) for value in (plan, forecast, state, token)]
    validate_shadow_plan(plan)
    validate_blind_forecast(forecast)
    validate_feature_state(dict(state))
    validate_authorization_token(token, plan=plan, feature_state=state)
    if plan.get("blind_forecast_fingerprint") != _fp(dict(forecast)):
        raise G16ShadowRunnerError("plan/blind forecast mismatch")

    day = str(state.get("session_day") or "")
    if day not in G16_DATES or token.get("session_day") != day:
        raise G16ShadowRunnerError("state/token day mismatch")
    day_plan = dict(plan["days"][day])
    blind_day_fp = _fp(_blind_day(forecast, day))
    if day_plan.get("blind_forecast_day_fingerprint") != blind_day_fp:
        raise G16ShadowRunnerError("blind day fingerprint mismatch")

    availability = dict(state.get("availability") or {})
    allowed = bool(availability.get("refine_update_allowed"))
    if bool((token.get("gate") or {}).get("posterior_update_allowed")) != allowed:
        raise G16ShadowRunnerError("token/feature update gate mismatch")
    requested = sorted(set(str(value) for value in token.get("authorized_candidate_ids") or []))
    if not set(requested).issubset(set(day_plan.get("allowed_candidate_ids") or [])):
        raise G16ShadowRunnerError("unregistered lesson requested")

    prior = _norm(state.get("blind_prior") or {})
    evidence = dict(state.get("evidence") or {})
    onset = dict(evidence.get("move_onset_pressure") or {})
    flow = dict(evidence.get("signed_flow") or {}) if isinstance(evidence.get("signed_flow"), Mapping) else {}
    queue = dict(evidence.get("mbo_queue") or {})
    div = dict(evidence.get("divergence_exhaustion") or {}) if isinstance(evidence.get("divergence_exhaustion"), Mapping) else {}
    flow_ok = bool(availability.get("flow_update_allowed"))
    queue_ok = bool(availability.get("queue_update_allowed"))
    direction = 0.0
    flat = 0.0
    attribution = []

    regime = str(onset.get("regime") or "").lower()
    activity = _finite(onset.get("activity_ratio"), 1.0)
    efficiency = _clip(_finite(onset.get("price_efficiency")), 0.0, 1.0)
    if regime in {"equilibrium", "depleted", "recirculating_watch", "insufficient_data"}:
        flat += 0.20
    if efficiency < 0.12:
        flat += 0.15
    if activity < 0.55:
        flat += 0.15

    for identifier in requested:
        contribution = 0.0
        used = False
        value: Any = None
        if identifier == "g15_mbo.signed_flow":
            value = {"imb_level": flow.get("imb_level"), "imb_flow": flow.get("imb_flow")}
            used = flow_ok
            if used:
                contribution = 1.10 * _clip(_finite(flow.get("imb_level")), -1.0, 1.0)
                contribution += 0.40 * _clip(_finite(flow.get("imb_flow")), -1.0, 1.0)
        elif identifier == "g15_mbo.far_side_recruitment":
            value = {"consumed_side": queue.get("consumed_side"),
                     "far_side_recruitment": queue.get("far_side_recruitment")}
            sign = _queue_sign(queue)
            used = queue_ok and sign != 0 and queue.get("far_side_recruitment") is not None
            if used:
                contribution = sign * 0.35 * _clip(_finite(queue.get("far_side_recruitment")), -1.0, 1.0)
        elif identifier == "g15_mbo.divergence_exhaustion":
            value = str(div.get("expect") or "").lower() or None
            sign = _queue_sign(queue)
            used = queue_ok and sign != 0 and value is not None
            if used and value in {"continuation", "continue"}:
                contribution = sign * 0.25
            elif used and value in {"flip_risk", "reversal", "reverse"}:
                contribution = -sign * 0.45
                flat += 0.15
            else:
                used = False
        attribution.append({
            "candidate_id": identifier,
            "implemented_handler": identifier in KNOWN,
            "used": used,
            "value": value,
            "directional_contribution": round(contribution, 8),
        })
        direction += contribution

    strength = 0.20 + 0.80 * _clip(_finite(onset.get("value")), 0.0, 1.0)
    strength *= _clip(0.75 + 0.25 * activity, 0.50, 1.50)
    strength *= 0.75 + 0.25 * efficiency
    if not allowed:
        strength = 0.0
    direction = _clip(direction * strength, -2.0, 2.0)
    flat = _clip(flat - 0.20 * abs(direction), -0.5, 1.0)
    posterior = prior if not allowed else _norm({
        "up": prior["up"] * math.exp(direction),
        "down": prior["down"] * math.exp(-direction),
        "flat": prior["flat"] * math.exp(flat),
    })
    status = "STAND_DOWN" if not allowed else (
        "UPDATED" if posterior != prior else "NO_CHANGE")

    output = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "session_day": day,
        "sequence": int(state.get("sequence") or 0),
        "horizon": state.get("horizon"),
        "as_of_event_s": float(state["as_of_event_s"]),
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "status": status,
        "blind_prior": prior,
        "posterior": posterior,
        "scores": {"directional_log_weight": round(direction, 8),
                   "flat_log_weight": round(flat, 8),
                   "update_strength": round(strength, 8)},
        "attribution": attribution,
        "authorized_candidate_ids": requested,
        "implemented_candidate_ids": sorted(set(requested) & KNOWN),
        "unhandled_candidate_ids": sorted(set(requested) - KNOWN),
        "stand_down_reasons": copy.deepcopy(list(availability.get("stand_down_reasons") or [])),
        "provenance": {
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "day_plan_fingerprint": day_plan.get("day_plan_fingerprint"),
            "authorization_fingerprint": token.get("authorization_fingerprint"),
            "feature_fingerprint": state.get("feature_fingerprint"),
            "blind_prior_fingerprint": state.get("blind_prior_fingerprint"),
            "blind_forecast_day_fingerprint": blind_day_fp,
        },
    }
    output["output_fingerprint"] = _output_fp(output)
    validate_output(output)
    if [dict(value) for value in (plan, forecast, state, token)] != originals:
        raise G16ShadowRunnerError("runner mutated source artifacts")
    return output


def validate_output(output: Mapping[str, Any]) -> None:
    if output.get("schema") != SCHEMA or output.get("authority") != AUTHORITY:
        raise G16ShadowRunnerError("posterior schema/authority mismatch")
    for field in ("execution_authority", "actual_g16_outcomes_used",
                  "may_update_ng_brain", "may_change_g16_blind_prior"):
        if output.get(field) is not False:
            raise G16ShadowRunnerError(f"{field} must remain false")
    if output.get("session_day") not in G16_DATES:
        raise G16ShadowRunnerError("invalid G16 day")
    if output.get("status") == "STAND_DOWN" and _norm(output["posterior"]) != _norm(output["blind_prior"]):
        raise G16ShadowRunnerError("stand-down changed blind prior")
    if output.get("output_fingerprint") != _output_fp(output):
        raise G16ShadowRunnerError("posterior fingerprint mismatch")
    requested = set(output.get("authorized_candidate_ids") or [])
    implemented = set(output.get("implemented_candidate_ids") or [])
    unhandled = set(output.get("unhandled_candidate_ids") or [])
    if implemented | unhandled != requested or implemented & unhandled:
        raise G16ShadowRunnerError("candidate accounting mismatch")


def run_stream(plan: Mapping[str, Any], forecast: Mapping[str, Any],
               states: Iterable[Mapping[str, Any]], auth_stream: Mapping[str, Any]) -> dict[str, Any]:
    validate_shadow_plan(plan)
    validate_blind_forecast(forecast)
    state_rows = [copy.deepcopy(dict(row)) for row in states]
    if auth_stream.get("schema") != AUTH_STREAM_SCHEMA or auth_stream.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16ShadowRunnerError("authorization stream mismatch")
    tokens = [dict(row) for row in auth_stream.get("authorizations") or []]
    if len(tokens) != len(state_rows) or auth_stream.get("n_authorizations") != len(tokens):
        raise G16ShadowRunnerError("authorization/state count mismatch")
    payload = copy.deepcopy(dict(auth_stream))
    observed = payload.pop("stream_fingerprint", None)
    if observed != _fp(payload):
        raise G16ShadowRunnerError("authorization stream fingerprint mismatch")

    outputs = []
    last_day = -1
    last_by_day = {}
    for state, token in zip(state_rows, tokens):
        validate_authorization_token(token, plan=plan, feature_state=state)
        day = state.get("session_day")
        index = G16_DATES.index(day)
        current = (float(state["as_of_event_s"]), int(state.get("sequence") or 0))
        if index < last_day or (day in last_by_day and current <= last_by_day[day]):
            raise G16ShadowRunnerError("posterior stream is not chronological")
        last_day = index
        last_by_day[day] = current
        outputs.append(run_state(plan, forecast, state, token))
    result = {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": STREAM_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "authorization_stream_fingerprint": auth_stream.get("stream_fingerprint"),
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    result["stream_fingerprint"] = _fp(result)
    return result


def selftest() -> int:
    from ng_g16_shadow_gate import (
        _fixture_blind_state, _fixture_feature, _fixture_forecast, _fixture_registry,
        authorize_feature_stream, build_shadow_plan,
    )
    forecast = _fixture_forecast()
    plan = build_shadow_plan(forecast, _fixture_blind_state(), _fixture_registry())
    state = _fixture_feature()
    result = run_stream(plan, forecast, [state], authorize_feature_stream(plan, [state]))
    assert result["n_outputs"] == 1 and result["outputs"][0]["execution_authority"] is False
    print("[ng_g16_shadow_runner] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--blind-forecast", type=Path)
    parser.add_argument("--states", type=Path)
    parser.add_argument("--authorizations", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(getattr(args, name) is None for name in ("plan", "blind_forecast", "states", "authorizations", "out")):
        parser.error("--plan --blind-forecast --states --authorizations --out are required")
    states_payload = json.loads(args.states.read_text())
    states = states_payload if isinstance(states_payload, list) else states_payload.get("states") or []
    result = run_stream(json.loads(args.plan.read_text()),
                        json.loads(args.blind_forecast.read_text()),
                        states, json.loads(args.authorizations.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"[ng_g16_shadow_runner] wrote {result['n_outputs']} outputs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
