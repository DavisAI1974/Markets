#!/usr/bin/env python3
"""Outcome-blind counterfactual attribution for exact G15 causal refinement.

The report reproduces every locked refine output from its exact causal feature state,
then performs deterministic one-factor-at-a-time neutralizations for the six evidence
families requested for G15: onset, signed flow, divergence/exhaustion, queue
 depletion/replenishment, price efficiency, and activity. It quantifies how each
factor changed the posterior relative to the same state with that factor neutralized.

This is a model-decomposition artifact, not isolated causal proof or an outcome score.
It never reads actual outcomes, never changes the blind forecast/prior or posterior
stream, cannot update ``ng_brain.json``, grants no execution authority, keeps CME event
contracts SHADOW, and does not start the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from ng_g15_anchor import anchor_fingerprint, validate_anchor
from ng_historical_manifest import G15_DATES
from ng_rt_feature_state import feature_fingerprint, validate_feature_state
from ng_rt_refiner import refine_feature_state, validate_refine_output

SCHEMA = "ng_g15_counterfactual_attribution.v1"
FACTOR_SCHEMA = "ng_g15_counterfactual_factor.v1"
FACTORS = (
    "move_onset",
    "signed_flow",
    "divergence_exhaustion",
    "queue_depletion_replenishment",
    "price_efficiency",
    "activity",
)
EPSILON = 1e-12


class CounterfactualAttributionError(ValueError):
    """Raised when attribution cannot be reproduced from locked causal inputs."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _direction(probabilities: Mapping[str, Any]) -> float:
    return float(probabilities.get("up") or 0.0) - float(
        probabilities.get("down") or 0.0
    )


def _flatten_states(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    states = [
        copy.deepcopy(dict(state))
        for stream in replay.get("streams") or []
        for state in stream.get("states") or []
    ]
    if not states:
        raise CounterfactualAttributionError("replay contains no feature states")
    states.sort(
        key=lambda row: (
            float(row["as_of_event_s"]),
            int(row.get("sequence") or 0),
            str((row.get("instrument") or {}).get("raw_symbol") or ""),
            str(row.get("feature_fingerprint") or ""),
        )
    )
    previous: tuple[float, int] | None = None
    seen: set[str] = set()
    observed_days: set[str] = set()
    for state in states:
        validate_feature_state(state)
        day = str(state.get("session_day") or "")
        if day not in G15_DATES:
            raise CounterfactualAttributionError(
                f"non-canonical G15 session_day: {day!r}"
            )
        observed_days.add(day)
        fingerprint = str(state.get("feature_fingerprint") or "")
        if not fingerprint or fingerprint in seen:
            raise CounterfactualAttributionError(
                "feature states must have unique fingerprints"
            )
        seen.add(fingerprint)
        key = (float(state["as_of_event_s"]), int(state.get("sequence") or 0))
        if previous is not None and (
            key[0] < previous[0]
            or (key[0] == previous[0] and key[1] < previous[1])
        ):
            raise CounterfactualAttributionError(
                "feature-state stream is not chronological"
            )
        previous = key
    missing = [day for day in G15_DATES if day not in observed_days]
    if missing:
        raise CounterfactualAttributionError(
            "replay lacks canonical G15 sessions: " + ", ".join(missing)
        )
    return states


def _outputs(refine_stream: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [
        copy.deepcopy(dict(row)) for row in refine_stream.get("outputs") or []
    ]
    declared = int(refine_stream.get("n_outputs") or 0)
    if declared != len(rows):
        raise CounterfactualAttributionError("refine-stream n_outputs mismatch")
    result: dict[str, dict[str, Any]] = {}
    previous: tuple[float, int] | None = None
    for row in rows:
        validate_refine_output(row)
        feature = str(row.get("feature_fingerprint") or "")
        if not feature or feature in result:
            raise CounterfactualAttributionError(
                "refine outputs must map one-to-one to feature states"
            )
        key = (float(row["as_of_event_s"]), int(row.get("sequence") or 0))
        if previous is not None and (
            key[0] < previous[0]
            or (key[0] == previous[0] and key[1] < previous[1])
        ):
            raise CounterfactualAttributionError(
                "refine-output stream is not chronological"
            )
        previous = key
        result[feature] = row
    return result


def _set_feature_fingerprint(state: dict[str, Any]) -> dict[str, Any]:
    state["feature_fingerprint"] = feature_fingerprint(state)
    validate_feature_state(state)
    return state


def neutralize_factor(state: Mapping[str, Any], factor: str) -> dict[str, Any]:
    """Return a validated state with exactly one evidence family neutralized."""
    if factor not in FACTORS:
        raise CounterfactualAttributionError(f"unsupported factor: {factor}")
    candidate = copy.deepcopy(dict(state))
    evidence = dict(candidate.get("evidence") or {})
    onset = dict(evidence.get("move_onset_pressure") or {})
    queue = dict(evidence.get("mbo_queue") or {})

    if factor == "move_onset":
        onset["value"] = 0.0
        onset["regime"] = "unknown"
        evidence["move_onset_pressure"] = onset
    elif factor == "signed_flow":
        flow = dict(evidence.get("signed_flow") or {})
        flow["imb_level"] = 0.0
        flow["imb_flow"] = 0.0
        evidence["signed_flow"] = flow
    elif factor == "divergence_exhaustion":
        evidence["divergence_exhaustion"] = {}
    elif factor == "queue_depletion_replenishment":
        queue["far_side_recruitment"] = 0.0
        evidence["mbo_queue"] = queue
    elif factor == "price_efficiency":
        onset["price_efficiency"] = 1.0
        evidence["move_onset_pressure"] = onset
    elif factor == "activity":
        onset["activity_ratio"] = 1.0
        evidence["move_onset_pressure"] = onset

    candidate["evidence"] = evidence
    return _set_feature_fingerprint(candidate)


def _factor_available(state: Mapping[str, Any], factor: str) -> bool:
    availability = dict(state.get("availability") or {})
    if not bool(availability.get("refine_update_allowed")):
        return False
    evidence = dict(state.get("evidence") or {})
    onset = dict(evidence.get("move_onset_pressure") or {})
    queue = dict(evidence.get("mbo_queue") or {})
    if factor == "move_onset":
        return _finite(onset.get("value")) is not None
    if factor == "signed_flow":
        flow = evidence.get("signed_flow")
        return (
            bool(availability.get("flow_update_allowed"))
            and isinstance(flow, dict)
            and (
                _finite(flow.get("imb_level")) is not None
                or _finite(flow.get("imb_flow")) is not None
            )
        )
    if factor == "divergence_exhaustion":
        divergence = evidence.get("divergence_exhaustion")
        return (
            isinstance(divergence, dict)
            and bool(divergence.get("expect"))
            and bool(queue.get("consumed_side"))
        )
    if factor == "queue_depletion_replenishment":
        return (
            bool(availability.get("queue_update_allowed"))
            and _finite(queue.get("far_side_recruitment")) is not None
            and bool(queue.get("consumed_side"))
        )
    if factor == "price_efficiency":
        return _finite(onset.get("price_efficiency")) is not None
    if factor == "activity":
        return _finite(onset.get("activity_ratio")) is not None
    return False


def _effect(
    full_output: Mapping[str, Any],
    ablated_output: Mapping[str, Any],
    factor: str,
    available: bool,
) -> dict[str, Any]:
    full = dict(full_output.get("posterior") or {})
    ablated = dict(ablated_output.get("posterior") or {})
    prior = dict(full_output.get("blind_prior") or {})
    deltas = {
        direction: float(full.get(direction) or 0.0)
        - float(ablated.get(direction) or 0.0)
        for direction in ("up", "flat", "down")
    }
    direction_effect = _direction(full) - _direction(ablated)
    l1_effect = sum(abs(value) for value in deltas.values())
    return {
        "schema": FACTOR_SCHEMA,
        "factor": factor,
        "available": bool(available),
        "changed_posterior": l1_effect > EPSILON,
        "direction_effect_full_minus_neutral": round(direction_effect, 10),
        "flat_effect_full_minus_neutral": round(deltas["flat"], 10),
        "up_effect_full_minus_neutral": round(deltas["up"], 10),
        "down_effect_full_minus_neutral": round(deltas["down"], 10),
        "posterior_l1_effect": round(l1_effect, 10),
        "full_direction_shift_from_blind": round(
            _direction(full) - _direction(prior), 10
        ),
        "neutral_direction_shift_from_blind": round(
            _direction(ablated) - _direction(prior), 10
        ),
        "neutralized_feature_fingerprint": ablated_output.get(
            "feature_fingerprint"
        ),
        "neutralized_output_fingerprint": ablated_output.get(
            "output_fingerprint"
        ),
    }


def _summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = [dict(row) for row in rows]
    by_factor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        for item in row.get("factors") or []:
            by_factor[str(item.get("factor") or "")].append(dict(item))
    summary: dict[str, Any] = {}
    for factor in FACTORS:
        items = by_factor.get(factor, [])
        changed_rows = [item for item in items if item.get("changed_posterior")]
        direction_values = [
            float(item.get("direction_effect_full_minus_neutral") or 0.0)
            for item in items
        ]
        summary[factor] = {
            "states": len(items),
            "available_states": sum(
                bool(item.get("available")) for item in items
            ),
            "changed_states": len(changed_rows),
            "signed_direction_effect_sum": round(sum(direction_values), 10),
            "absolute_direction_effect_sum": round(
                sum(abs(value) for value in direction_values), 10
            ),
            "mean_direction_effect": round(
                sum(direction_values) / len(items), 10
            )
            if items
            else 0.0,
            "max_abs_direction_effect": round(
                max((abs(value) for value in direction_values), default=0.0),
                10,
            ),
            "posterior_l1_effect_sum": round(
                sum(float(item.get("posterior_l1_effect") or 0.0) for item in items),
                10,
            ),
        }
    return summary


def _lesson_proposals(
    rows: Iterable[Mapping[str, Any]], overall: Mapping[str, Any]
) -> list[dict[str, Any]]:
    support: dict[str, set[str]] = {factor: set() for factor in FACTORS}
    for row in rows:
        day = str(row.get("session_day") or "")
        for item in row.get("factors") or []:
            if item.get("changed_posterior"):
                support[str(item.get("factor"))].add(day)
    proposals: list[dict[str, Any]] = []
    for factor in FACTORS:
        days = sorted(support[factor])
        if not days:
            continue
        metrics = dict(overall.get(factor) or {})
        proposals.append(
            {
                "id": f"g15_counterfactual.{factor}",
                "status": "UNSCORED_CANDIDATE",
                "authority": "LESSON_PROPOSAL_ONLY",
                "may_update_ng_brain": False,
                "factor": factor,
                "supporting_g15_days": days,
                "changed_states": int(metrics.get("changed_states") or 0),
                "absolute_direction_effect_sum": metrics.get(
                    "absolute_direction_effect_sum"
                ),
                "scope": "Outcome-blind model counterfactual decomposition only",
                "required_validation": [
                    "separate locked G15 blind-versus-refined scoring",
                    "chronological forward test on G16 using only pre-cutoff information",
                    "untouched holdout beyond G16",
                    "forward-live SHADOW validation",
                ],
            }
        )
    return proposals


def _build_report(
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy((replay, anchor, refine_stream))
    validate_anchor(dict(anchor))
    states = _flatten_states(replay)
    outputs = _outputs(refine_stream)
    state_fingerprints = {
        str(state["feature_fingerprint"]) for state in states
    }
    if set(outputs) != state_fingerprints:
        raise CounterfactualAttributionError(
            "refine outputs do not exactly cover replay feature states"
        )

    rows: list[dict[str, Any]] = []
    for state in states:
        feature = str(state["feature_fingerprint"])
        observed = outputs[feature]
        reproduced = refine_feature_state(
            copy.deepcopy(state), copy.deepcopy(dict(anchor))
        )
        if reproduced != observed:
            raise CounterfactualAttributionError(
                "locked refine output cannot be reproduced from its causal state"
            )
        factors: list[dict[str, Any]] = []
        for factor in FACTORS:
            neutral = neutralize_factor(state, factor)
            neutral_output = refine_feature_state(
                neutral, copy.deepcopy(dict(anchor))
            )
            factors.append(
                _effect(
                    observed,
                    neutral_output,
                    factor,
                    _factor_available(state, factor),
                )
            )
        rows.append(
            {
                "session_day": str(state.get("session_day") or ""),
                "as_of_event_s": float(state["as_of_event_s"]),
                "sequence": int(state.get("sequence") or 0),
                "feature_fingerprint": feature,
                "refine_output_fingerprint": observed.get(
                    "output_fingerprint"
                ),
                "status": observed.get("status"),
                "stand_down_reasons": sorted(
                    str(reason)
                    for reason in (
                        (observed.get("availability") or {}).get(
                            "stand_down_reasons"
                        )
                        or []
                    )
                ),
                "blind_prior": copy.deepcopy(observed.get("blind_prior")),
                "posterior": copy.deepcopy(observed.get("posterior")),
                "factors": factors,
            }
        )

    per_day = {
        day: _summarize(
            row for row in rows if row["session_day"] == day
        )
        for day in G15_DATES
    }
    overall = _summarize(rows)
    stand_down_days = sorted(
        {
            row["session_day"]
            for row in rows
            if row["status"] == "STAND_DOWN" or row["stand_down_reasons"]
        }
    )
    report = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": "READY_WITH_STAND_DOWNS"
        if stand_down_days
        else "READY",
        "authority": "OUTCOME_BLIND_COUNTERFACTUAL_ATTRIBUTION_ONLY",
        "replay_fingerprint": replay.get("fingerprint")
        or _fingerprint(replay),
        "anchor_fingerprint": anchor.get("anchor_fingerprint"),
        "refine_stream_fingerprint": _fingerprint(refine_stream),
        "n_states": len(rows),
        "n_days": len(G15_DATES),
        "factors": list(FACTORS),
        "neutral_baselines": {
            "move_onset": {"value": 0.0, "regime": "unknown"},
            "signed_flow": {"imb_level": 0.0, "imb_flow": 0.0},
            "divergence_exhaustion": {"expect": None},
            "queue_depletion_replenishment": {
                "far_side_recruitment": 0.0
            },
            "price_efficiency": 1.0,
            "activity": 1.0,
        },
        "rows": rows,
        "per_day": per_day,
        "overall": overall,
        "stand_down_days": stand_down_days,
        "lesson_proposals": _lesson_proposals(rows, overall),
        "methodology_note": (
            "Each effect is full posterior minus a deterministic one-factor-neutral "
            "posterior on the same causal state. Effects are model decompositions, "
            "not isolated causal proof and not outcome-scored skill claims."
        ),
        "actual_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "LOCKED_G15_BLIND_VERSUS_REFINED_SCORING",
    }
    report["fingerprint"] = _fingerprint(report)
    if (replay, anchor, refine_stream) != originals:
        raise CounterfactualAttributionError(
            "counterfactual attribution mutated an input artifact"
        )
    return report


def build_report(
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
) -> dict[str, Any]:
    report = _build_report(replay, anchor, refine_stream)
    validate_report(
        report,
        replay=replay,
        anchor=anchor,
        refine_stream=refine_stream,
    )
    return report


def validate_report(
    report: Mapping[str, Any],
    *,
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
) -> None:
    candidate = copy.deepcopy(dict(report))
    observed = candidate.pop("fingerprint", None)
    if (
        candidate.get("schema") != SCHEMA
        or candidate.get("authority")
        != "OUTCOME_BLIND_COUNTERFACTUAL_ATTRIBUTION_ONLY"
    ):
        raise CounterfactualAttributionError(
            "unexpected attribution report schema/authority"
        )
    if observed != _fingerprint(candidate):
        raise CounterfactualAttributionError(
            "attribution report fingerprint mismatch"
        )
    for field in (
        "actual_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if candidate.get(field) is not False:
            raise CounterfactualAttributionError(
                f"report must keep {field}=false"
            )
    if (
        candidate.get("one_signal_authority_preserved") is not True
        or candidate.get("blind_forecast_immutable") is not True
    ):
        raise CounterfactualAttributionError(
            "report must preserve one signal authority and blind immutability"
        )
    if (
        candidate.get("cme_event_contracts_mode") != "SHADOW"
        or candidate.get("brokerage_contract") != "tastytrade_not_ibkr"
    ):
        raise CounterfactualAttributionError(
            "report authority contract changed"
        )
    rebuilt = _build_report(replay, anchor, refine_stream)
    rebuilt.pop("fingerprint", None)
    if candidate != rebuilt:
        raise CounterfactualAttributionError(
            "attribution report differs from deterministic reconstruction"
        )


def _fixture_anchor() -> dict[str, Any]:
    anchor = {
        "schema": "ng_g15_anchor.v1",
        "date": "20260313",
        "cutoff_event_s": 100.0,
        "hour_start_event_s": 0.0,
        "hour_end_event_s": 99.0,
        "authority": "REFINE_ANCHOR_ONLY",
        "execution_authority": False,
        "instrument": {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
        },
        "prices": {
            "first": 3.0,
            "last": 3.01,
            "high": 3.02,
            "low": 2.99,
        },
        "trade_count": 10,
    }
    anchor["anchor_fingerprint"] = anchor_fingerprint(anchor)
    return anchor


def _fixture_state(day: str, sequence: int) -> dict[str, Any]:
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    state = {
        "schema": "ng_rt_feature_state.v1",
        "session_day": day,
        "sequence": sequence,
        "source_mode": "historical_replay",
        "horizon": "close",
        "as_of_event_s": 200.0 + sequence,
        "decision_cutoff_s": 200.0 + sequence,
        "authority": "REFINE_INPUT_ONLY",
        "execution_authority": False,
        "instrument": {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
        },
        "blind_prior": prior,
        "blind_prior_fingerprint": _fingerprint(prior),
        "evidence": {
            "move_onset_pressure": {
                "value": 0.8,
                "regime": "active",
                "activity_ratio": 1.2,
                "price_efficiency": 0.7,
            },
            "signed_flow": {"imb_level": 0.6, "imb_flow": 0.2},
            "divergence_exhaustion": {"expect": "continuation"},
            "mbo_queue": {
                "book_complete": True,
                "snapshot_complete": True,
                "maybe_bad_book": False,
                "consumed_side": "ASK",
                "far_side_recruitment": 0.5,
            },
            "quality_counts": {
                "trade_events_60s": 10,
                "trade_events_15m": 20,
                "complete_mbo_events": 1,
                "missing_order_events": 0,
            },
        },
        "availability": {
            "flow_update_allowed": True,
            "queue_update_allowed": True,
            "refine_update_allowed": True,
            "stand_down_reasons": [],
        },
        "collector_quality": {},
        "provenance": {"same_contract_for_historical_and_live": True},
    }
    state["feature_fingerprint"] = feature_fingerprint(state)
    return state


def selftest() -> int:
    anchor = _fixture_anchor()
    states = [
        _fixture_state(day, index + 1)
        for index, day in enumerate(G15_DATES)
    ]
    stream = {
        "schema": "ng_rt_refine_stream.v1",
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": anchor["anchor_fingerprint"],
        "n_outputs": len(states),
        "outputs": [refine_feature_state(state, anchor) for state in states],
    }
    replay = {
        "streams": [{"states": states}],
        "fingerprint": _fingerprint(states),
    }
    report = build_report(replay, anchor, stream)
    assert report["n_days"] == len(G15_DATES)
    assert set(report["overall"]) == set(FACTORS)
    assert report["lesson_proposals"]
    print("[ng_g15_counterfactual_attribution] selftest PASS")
    return 0


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CounterfactualAttributionError(
            f"artifact must be a JSON object: {path}"
        )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Quantify outcome-blind G15 refinement factors by deterministic "
            "neutralization"
        )
    )
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--refine-stream", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(
        value is None
        for value in (args.replay, args.anchor, args.refine_stream, args.out)
    ):
        parser.error(
            "--replay, --anchor, --refine-stream, and --out are required"
        )
    report = build_report(
        _load(args.replay),
        _load(args.anchor),
        _load(args.refine_stream),
    )
    _atomic_json(args.out, report)
    print(
        "[ng_g15_counterfactual_attribution] "
        f"{report['status']} states={report['n_states']} "
        f"proposals={len(report['lesson_proposals'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
