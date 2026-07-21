#!/usr/bin/env python3
"""Deterministic SHADOW posterior contract for NG real-time refinement."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from ng_g15_anchor import assert_anchor_precedes_state, validate_anchor
from ng_rt_feature_state import validate_feature_state

SCHEMA = "ng_rt_refine_output.v1"
STREAM_SCHEMA = "ng_rt_refine_stream.v1"
DIRECTIONS = ("up", "flat", "down")


class RefineError(ValueError):
    """Raised when a posterior would violate the refine contract."""


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalize(value: dict[str, Any]) -> dict[str, float]:
    probs = {key: max(0.0, _finite(value.get(key)) or 0.0) for key in DIRECTIONS}
    total = sum(probs.values())
    if total <= 0:
        raise RefineError("probabilities must carry positive mass")
    return {key: probs[key] / total for key in DIRECTIONS}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def output_fingerprint(output: dict[str, Any]) -> str:
    payload = copy.deepcopy(output)
    payload.pop("output_fingerprint", None)
    return _fingerprint(payload)


def _current_direction_sign(queue: dict[str, Any]) -> float:
    side = str(queue.get("consumed_side") or "").upper()
    return 1.0 if side == "ASK" else -1.0 if side == "BID" else 0.0


def _attribution(name: str, value: Any, contribution: float, used: bool, note: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "contribution": round(float(contribution), 8),
        "used": bool(used),
        "note": note,
    }


def refine_feature_state(feature_state: dict[str, Any], anchor: dict[str, Any]) -> dict[str, Any]:
    """Produce one deterministic posterior from one validated causal state."""
    validate_feature_state(feature_state)
    validate_anchor(anchor)
    assert_anchor_precedes_state(anchor, feature_state)

    state = copy.deepcopy(feature_state)
    prior = _normalize(dict(state.get("blind_prior") or {}))
    prior_before = copy.deepcopy(prior)
    availability = dict(state.get("availability") or {})
    evidence = dict(state.get("evidence") or {})
    onset = dict(evidence.get("move_onset_pressure") or {})
    flow = dict(evidence.get("signed_flow") or {}) if isinstance(evidence.get("signed_flow"), dict) else {}
    divergence = (
        dict(evidence.get("divergence_exhaustion") or {})
        if isinstance(evidence.get("divergence_exhaustion"), dict)
        else {}
    )
    queue = dict(evidence.get("mbo_queue") or {})

    flow_allowed = bool(availability.get("flow_update_allowed"))
    queue_allowed = bool(availability.get("queue_update_allowed"))
    refine_allowed = bool(availability.get("refine_update_allowed"))
    stand_down = list(availability.get("stand_down_reasons") or [])

    attribution: list[dict[str, Any]] = []
    directional_score = 0.0
    flat_score = 0.0
    onset_value = _clip(_finite(onset.get("value")) or 0.0, 0.0, 1.0)
    activity_ratio = _finite(onset.get("activity_ratio"))
    efficiency = _clip(_finite(onset.get("price_efficiency")) or 0.0, 0.0, 1.0)
    regime = str(onset.get("regime") or "unknown")

    imb_level = _clip(_finite(flow.get("imb_level")) or 0.0, -1.0, 1.0)
    imb_flow = _clip(_finite(flow.get("imb_flow")) or 0.0, -1.0, 1.0)
    flow_contribution = 1.25 * imb_level + 0.50 * imb_flow if flow_allowed else 0.0
    directional_score += flow_contribution
    attribution.append(
        _attribution(
            "signed_flow",
            {"imb_level": flow.get("imb_level"), "imb_flow": flow.get("imb_flow")},
            flow_contribution,
            flow_allowed,
            "positive favors up; negative favors down; unavailable flow contributes zero",
        )
    )

    current_sign = _current_direction_sign(queue)
    recruitment = _finite(queue.get("far_side_recruitment"))
    queue_contribution = 0.0
    if queue_allowed and recruitment is not None and current_sign:
        queue_contribution = current_sign * 0.35 * _clip(recruitment, -1.0, 1.0)
        directional_score += queue_contribution
    attribution.append(
        _attribution(
            "far_side_recruitment",
            {"consumed_side": queue.get("consumed_side"), "value": recruitment},
            queue_contribution,
            queue_allowed and recruitment is not None and bool(current_sign),
            "recruitment supports the consumed-side direction; depletion weakens it",
        )
    )

    expectation = str(divergence.get("expect") or "").lower()
    divergence_contribution = 0.0
    if expectation in {"continuation", "continue"} and current_sign:
        divergence_contribution = current_sign * 0.25
    elif expectation in {"flip_risk", "reversal", "reverse"} and current_sign:
        divergence_contribution = -current_sign * 0.45
        flat_score += 0.20
    directional_score += divergence_contribution
    attribution.append(
        _attribution(
            "divergence_exhaustion",
            expectation or None,
            divergence_contribution,
            bool(expectation and current_sign),
            "continuation reinforces current direction; reversal opposes it and raises flat risk",
        )
    )

    if regime in {"equilibrium", "depleted", "recirculating_watch", "insufficient_data"}:
        flat_score += 0.25
    if efficiency < 0.12:
        flat_score += 0.20
    if activity_ratio is not None and activity_ratio < 0.55:
        flat_score += 0.20

    update_strength = 0.25 + 0.75 * onset_value
    if activity_ratio is not None:
        update_strength *= _clip(0.75 + 0.25 * activity_ratio, 0.50, 1.50)
    update_strength *= 0.75 + 0.25 * efficiency
    if not refine_allowed:
        update_strength = 0.0
    directional_score = _clip(directional_score * update_strength, -2.0, 2.0)
    flat_score = _clip(flat_score - 0.20 * abs(directional_score), -0.5, 1.0)

    if not refine_allowed:
        posterior = prior
        status = "STAND_DOWN"
    else:
        weights = {
            "up": prior["up"] * math.exp(directional_score),
            "down": prior["down"] * math.exp(-directional_score),
            "flat": prior["flat"] * math.exp(flat_score),
        }
        posterior = _normalize(weights)
        status = "UPDATED" if any(abs(posterior[key] - prior[key]) > 1e-12 for key in DIRECTIONS) else "NO_CHANGE"

    output = {
        "schema": SCHEMA,
        "source_mode": state.get("source_mode"),
        "session_day": state.get("session_day"),
        "sequence": state.get("sequence"),
        "horizon": state.get("horizon"),
        "as_of_event_s": state.get("as_of_event_s"),
        "authority": "REFINE_POSTERIOR_ONLY",
        "execution_authority": False,
        "blind_prior": prior,
        "blind_prior_fingerprint": state.get("blind_prior_fingerprint"),
        "feature_fingerprint": state.get("feature_fingerprint"),
        "anchor_fingerprint": anchor.get("anchor_fingerprint"),
        "posterior": posterior,
        "status": status,
        "scores": {
            "directional_log_weight": round(directional_score, 8),
            "flat_log_weight": round(flat_score, 8),
            "update_strength": round(update_strength, 8),
        },
        "attribution": attribution,
        "availability": {
            "flow_update_allowed": flow_allowed,
            "queue_update_allowed": queue_allowed,
            "refine_update_allowed": refine_allowed,
            "stand_down_reasons": stand_down,
        },
        "provenance": {
            "feature_schema": state.get("schema"),
            "anchor_schema": anchor.get("schema"),
            "blind_artifact_mutated": False,
            "same_contract_for_historical_and_live": True,
            "threshold_status": "SHADOW_UNTIL_WALK_FORWARD_CALIBRATION",
        },
    }
    if prior != prior_before:
        raise RefineError("blind prior mutated during refinement")
    output["output_fingerprint"] = output_fingerprint(output)
    validate_refine_output(output)
    return output


def validate_refine_output(output: dict[str, Any]) -> None:
    if output.get("schema") != SCHEMA:
        raise RefineError(f"unexpected output schema: {output.get('schema')}")
    if output.get("authority") != "REFINE_POSTERIOR_ONLY" or output.get("execution_authority") is not False:
        raise RefineError("refine output authority is invalid")
    prior = _normalize(dict(output.get("blind_prior") or {}))
    posterior = _normalize(dict(output.get("posterior") or {}))
    if abs(sum(posterior.values()) - 1.0) > 1e-9:
        raise RefineError("posterior failed normalization")
    if not output.get("blind_prior_fingerprint") or not output.get("feature_fingerprint"):
        raise RefineError("refine output lacks causal fingerprints")
    if output_fingerprint(output) != output.get("output_fingerprint"):
        raise RefineError("refine output fingerprint mismatch")
    if output.get("status") == "STAND_DOWN" and posterior != prior:
        raise RefineError("stand-down output must preserve the blind prior")


def refine_stream(states: Iterable[dict[str, Any]], anchor: dict[str, Any]) -> dict[str, Any]:
    validate_anchor(anchor)
    outputs: list[dict[str, Any]] = []
    previous_time: float | None = None
    for state in states:
        validate_feature_state(state)
        event_time = _finite(state.get("as_of_event_s"))
        if event_time is None:
            raise RefineError("stream state lacks finite event time")
        if previous_time is not None and event_time < previous_time:
            raise RefineError("refine stream moved backwards")
        previous_time = event_time
        outputs.append(refine_feature_state(state, anchor))
    return {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": anchor.get("anchor_fingerprint"),
        "n_outputs": len(outputs),
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic SHADOW refinement to replay feature states")
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    anchor = json.loads(args.anchor.read_text(encoding="utf-8"))
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    states = [state for stream in replay.get("streams") or [] for state in stream.get("states") or []]
    states.sort(key=lambda row: (float(row["as_of_event_s"]), int(row.get("sequence") or 0)))
    result = refine_stream(states, anchor)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[ng_rt_refiner] wrote {result['n_outputs']} outputs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
