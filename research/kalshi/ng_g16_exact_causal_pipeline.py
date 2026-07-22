#!/usr/bin/env python3
"""Bind exact-basis G16 replay to the pre-registered SHADOW refinement chain.

This module is the outcome-blind orchestration seam between the exact NGK26
historical replay and the existing G16 blind-wall, authorization, and posterior
contracts. It does not score G16, inspect G16 outcomes, select lessons from G16
performance, mutate the blind forecast, update ``ng_brain.json``, or grant
execution authority.

Every G15-supported candidate is requested for every G16 state before any G16
outcome access. Candidate handlers may decline unavailable evidence or contribute
zero, but the requested set cannot be changed after seeing target-session results.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_g16_blind_wall import G16_DATES, validate_blind_safe_state
from ng_g16_historical_replay import validate_replay_output
from ng_g16_shadow_gate import authorize_feature_stream, build_shadow_plan, validate_shadow_plan
from ng_g16_shadow_runner import STREAM_SCHEMA as POSTERIOR_STREAM_SCHEMA, run_stream, validate_output
from ng_rt_feature_state import validate_feature_state

SCHEMA = "ng_g16_exact_causal_pipeline.v1"
AUTHORITY = "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY"


class G16ExactCausalPipelineError(ValueError):
    """Raised when exact replay cannot enter the outcome-blind G16 chain."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise G16ExactCausalPipelineError(f"invalid {name}: {value!r}")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G16ExactCausalPipelineError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(result):
        raise G16ExactCausalPipelineError(f"invalid {name}: {value!r}")
    return result


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_prior(prior: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for key in ("up", "flat", "down"):
        value = _finite(prior.get(key), f"blind_prior.{key}")
        if value < 0:
            raise G16ExactCausalPipelineError("blind-prior probabilities cannot be negative")
        values[key] = value
    total = sum(values.values())
    if total <= 0:
        raise G16ExactCausalPipelineError("blind prior must carry positive probability mass")
    if _fp(dict(prior)) != replay.get("blind_prior_fingerprint"):
        raise G16ExactCausalPipelineError("locked blind prior does not match exact replay")
    return {key: values[key] / total for key in values}


def _flatten_states(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        validate_replay_output(replay)
    except Exception as error:
        raise G16ExactCausalPipelineError(f"exact G16 replay invalid: {error}") from error
    streams = replay.get("streams") or []
    if len(streams) != 1:
        raise G16ExactCausalPipelineError("single-contract G16 replay must contain exactly one stream")
    states = [copy.deepcopy(dict(row)) for row in streams[0].get("states") or []]
    if not states:
        raise G16ExactCausalPipelineError("exact G16 replay contains no causal feature states")
    previous_day_index = -1
    previous_by_day: dict[str, tuple[float, int]] = {}
    days_seen: set[str] = set()
    for state in states:
        try:
            validate_feature_state(state)
        except Exception as error:
            raise G16ExactCausalPipelineError(f"replay feature state invalid: {error}") from error
        day = str(state.get("session_day") or "")
        if day not in G16_DATES:
            raise G16ExactCausalPipelineError(f"non-canonical G16 replay day: {day!r}")
        day_index = G16_DATES.index(day)
        current = (_finite(state.get("as_of_event_s"), "state.as_of_event_s"), int(state.get("sequence") or 0))
        if day_index < previous_day_index:
            raise G16ExactCausalPipelineError("exact replay moved backward across G16 days")
        if day in previous_by_day and current <= previous_by_day[day]:
            raise G16ExactCausalPipelineError(f"{day}: exact replay states are not chronological")
        previous_day_index = day_index
        previous_by_day[day] = current
        days_seen.add(day)
        if state.get("blind_prior_fingerprint") != replay.get("blind_prior_fingerprint"):
            raise G16ExactCausalPipelineError(f"{day}: feature state references another blind prior")
        if state.get("completed_mbo_event_boundary") is not True:
            raise G16ExactCausalPipelineError(f"{day}: feature state lacks completed MBO boundary")
    if days_seen != set(G16_DATES):
        missing = sorted(set(G16_DATES) - days_seen)
        raise G16ExactCausalPipelineError("exact replay lacks canonical G16 coverage: " + ", ".join(missing))
    return states


def _validate_posterior_stream(
    stream: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    authorization_stream: Mapping[str, Any],
    states: list[Mapping[str, Any]],
) -> None:
    if stream.get("schema") != POSTERIOR_STREAM_SCHEMA:
        raise G16ExactCausalPipelineError("posterior stream schema mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if stream.get(field) is not False:
            raise G16ExactCausalPipelineError(f"posterior stream must keep {field}=false")
    if stream.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16ExactCausalPipelineError("posterior stream plan fingerprint mismatch")
    if stream.get("authorization_stream_fingerprint") != authorization_stream.get("stream_fingerprint"):
        raise G16ExactCausalPipelineError("posterior stream authorization fingerprint mismatch")
    outputs = [dict(row) for row in stream.get("outputs") or []]
    if int(stream.get("n_outputs") or 0) != len(outputs) or len(outputs) != len(states):
        raise G16ExactCausalPipelineError("posterior/state count mismatch")
    payload = copy.deepcopy(dict(stream))
    observed = payload.pop("stream_fingerprint", None)
    if observed != _fp(payload):
        raise G16ExactCausalPipelineError("posterior stream fingerprint mismatch")
    for state, output in zip(states, outputs):
        try:
            validate_output(output)
        except Exception as error:
            raise G16ExactCausalPipelineError(f"posterior output invalid: {error}") from error
        provenance = output.get("provenance") or {}
        if provenance.get("feature_fingerprint") != state.get("feature_fingerprint"):
            raise G16ExactCausalPipelineError("posterior output references another feature state")
        if output.get("session_day") != state.get("session_day"):
            raise G16ExactCausalPipelineError("posterior output/state day mismatch")
        if int(output.get("sequence") or 0) != int(state.get("sequence") or 0):
            raise G16ExactCausalPipelineError("posterior output/state sequence mismatch")
        if abs(float(output.get("as_of_event_s")) - float(state.get("as_of_event_s"))) > 1e-9:
            raise G16ExactCausalPipelineError("posterior output/state event-time mismatch")


def _shift(output: Mapping[str, Any]) -> float:
    prior = output.get("blind_prior") or {}
    posterior = output.get("posterior") or {}
    return 0.5 * sum(
        abs(float(posterior.get(key, 0.0)) - float(prior.get(key, 0.0)))
        for key in ("up", "flat", "down")
    )


def _day_audit(states: list[Mapping[str, Any]], outputs: list[Mapping[str, Any]]) -> dict[str, Any]:
    audits: dict[str, Any] = {}
    for day in G16_DATES:
        pairs = [(state, output) for state, output in zip(states, outputs) if state.get("session_day") == day]
        if not pairs:
            raise G16ExactCausalPipelineError(f"{day}: no state/output pairs")
        shifts = [_shift(output) for _, output in pairs]
        contributions: dict[str, float] = {}
        evidence_counts = {
            "onset": 0,
            "signed_flow": 0,
            "divergence_exhaustion": 0,
            "queue": 0,
            "activity": 0,
            "price_efficiency": 0,
        }
        stand_down_reasons: set[str] = set()
        strongest_index = max(range(len(pairs)), key=lambda index: shifts[index])
        for state, output in pairs:
            evidence = state.get("evidence") or {}
            availability = state.get("availability") or {}
            onset = evidence.get("move_onset_pressure") or {}
            flow = evidence.get("signed_flow")
            divergence = evidence.get("divergence_exhaustion")
            queue = evidence.get("mbo_queue") or {}
            if onset.get("value") is not None:
                evidence_counts["onset"] += 1
            if isinstance(flow, Mapping) and bool(availability.get("flow_update_allowed")):
                evidence_counts["signed_flow"] += 1
            if isinstance(divergence, Mapping) and divergence.get("expect") is not None:
                evidence_counts["divergence_exhaustion"] += 1
            if bool(availability.get("queue_update_allowed")) and queue:
                evidence_counts["queue"] += 1
            if onset.get("activity_ratio") is not None:
                evidence_counts["activity"] += 1
            if onset.get("price_efficiency") is not None:
                evidence_counts["price_efficiency"] += 1
            stand_down_reasons.update(str(value) for value in output.get("stand_down_reasons") or [])
            for row in output.get("attribution") or []:
                identifier = str(row.get("candidate_id") or "")
                if identifier:
                    contributions[identifier] = contributions.get(identifier, 0.0) + abs(
                        float(row.get("directional_contribution") or 0.0)
                    )
        strongest_output = pairs[strongest_index][1]
        audits[day] = {
            "date": day,
            "n_states": len(pairs),
            "n_updated": sum(output.get("status") == "UPDATED" for _, output in pairs),
            "n_no_change": sum(output.get("status") == "NO_CHANGE" for _, output in pairs),
            "n_stand_down": sum(output.get("status") == "STAND_DOWN" for _, output in pairs),
            "stand_down_reasons": sorted(stand_down_reasons),
            "max_posterior_shift_tv": round(max(shifts), 10),
            "mean_posterior_shift_tv": round(sum(shifts) / len(shifts), 10),
            "evidence_available_counts": evidence_counts,
            "candidate_absolute_contribution": {
                key: round(value, 10) for key, value in sorted(contributions.items())
            },
            "strongest_output_fingerprint": strongest_output.get("output_fingerprint"),
        }
        audits[day]["day_audit_fingerprint"] = _fp(audits[day])
    return audits


def build_exact_causal_pipeline(
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
) -> dict[str, Any]:
    originals = [
        copy.deepcopy(dict(value))
        for value in (replay, blind_prior, blind_forecast, blind_safe_state, registry_source)
    ]
    states = _flatten_states(replay)
    _validate_prior(blind_prior, replay)
    try:
        validate_blind_safe_state(blind_safe_state)
    except Exception as error:
        raise G16ExactCausalPipelineError(f"blind-safe state invalid: {error}") from error
    try:
        plan = build_shadow_plan(blind_forecast, blind_safe_state, registry_source)
        validate_shadow_plan(
            plan,
            blind_forecast=blind_forecast,
            blind_safe_state=blind_safe_state,
            registry_source=registry_source,
        )
    except Exception as error:
        raise G16ExactCausalPipelineError(f"G16 pre-cutoff SHADOW plan invalid: {error}") from error
    candidate_ids = list(plan.get("candidate_ids") or [])
    if not candidate_ids:
        raise G16ExactCausalPipelineError("no G15-adjudicated candidates are authorized for G16")
    requested_by_day = {day: candidate_ids for day in G16_DATES}
    try:
        authorizations = authorize_feature_stream(plan, states, requested_by_day=requested_by_day)
        posterior = run_stream(plan, blind_forecast, states, authorizations)
    except Exception as error:
        raise G16ExactCausalPipelineError(f"G16 authorization/posterior chain failed: {error}") from error
    _validate_posterior_stream(
        posterior,
        plan=plan,
        authorization_stream=authorizations,
        states=states,
    )
    outputs = [dict(row) for row in posterior.get("outputs") or []]
    audits = _day_audit(states, outputs)
    stand_down_days = [day for day in G16_DATES if audits[day]["n_stand_down"]]
    completion = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "READY_WITH_STAND_DOWNS" if stand_down_days else "READY",
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_select_lessons_from_g16_outcomes": False,
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
        "blind_forecast_fingerprint": _fp(dict(blind_forecast)),
        "blind_safe_state_fingerprint": blind_safe_state.get("artifact_fingerprint"),
        "lesson_registry_fingerprint": plan.get("lesson_registry_fingerprint"),
        "lesson_adjudication_fingerprint": plan.get("lesson_adjudication_fingerprint"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "authorization_stream_fingerprint": authorizations.get("stream_fingerprint"),
        "posterior_stream_fingerprint": posterior.get("stream_fingerprint"),
        "candidate_ids": candidate_ids,
        "candidate_request_policy": "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS",
        "n_states": len(states),
        "n_outputs": len(outputs),
        "n_days": len(audits),
        "stand_down_days": stand_down_days,
        "days": audits,
        "next_permitted_stage": "OUTCOME_BLIND_G16_CURVE_ADAPTER",
        "note": (
            "Exact historical replay is bound to the pre-cutoff G16 SHADOW chain. "
            "G16 outcomes remain unavailable until the refined curve is locked."
        ),
    }
    completion["fingerprint"] = _fp(completion)
    artifacts = {
        "plan": plan,
        "authorization_stream": authorizations,
        "posterior_stream": posterior,
        "completion": completion,
    }
    validate_pipeline_artifacts(
        artifacts,
        replay=replay,
        blind_prior=blind_prior,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
    )
    if [dict(value) for value in (replay, blind_prior, blind_forecast, blind_safe_state, registry_source)] != originals:
        raise G16ExactCausalPipelineError("pipeline mutated a source artifact")
    return artifacts


def validate_pipeline_artifacts(
    artifacts: Mapping[str, Any],
    *,
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
) -> None:
    states = _flatten_states(replay)
    _validate_prior(blind_prior, replay)
    plan = artifacts.get("plan") or {}
    authorizations = artifacts.get("authorization_stream") or {}
    posterior = artifacts.get("posterior_stream") or {}
    completion = copy.deepcopy(dict(artifacts.get("completion") or {}))
    try:
        validate_shadow_plan(
            plan,
            blind_forecast=blind_forecast,
            blind_safe_state=blind_safe_state,
            registry_source=registry_source,
        )
    except Exception as error:
        raise G16ExactCausalPipelineError(f"stored plan invalid: {error}") from error
    _validate_posterior_stream(
        posterior,
        plan=plan,
        authorization_stream=authorizations,
        states=states,
    )
    observed = completion.pop("fingerprint", None)
    if observed != _fp(completion):
        raise G16ExactCausalPipelineError("completion fingerprint mismatch")
    if completion.get("schema") != SCHEMA or completion.get("authority") != AUTHORITY:
        raise G16ExactCausalPipelineError("completion schema/authority mismatch")
    if completion.get("status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
        raise G16ExactCausalPipelineError("completion is not ready")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_select_lessons_from_g16_outcomes",
    ):
        if completion.get(field) is not False:
            raise G16ExactCausalPipelineError(f"completion must keep {field}=false")
    expected = {
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
        "blind_forecast_fingerprint": _fp(dict(blind_forecast)),
        "blind_safe_state_fingerprint": blind_safe_state.get("artifact_fingerprint"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "authorization_stream_fingerprint": authorizations.get("stream_fingerprint"),
        "posterior_stream_fingerprint": posterior.get("stream_fingerprint"),
    }
    for field, value in expected.items():
        if completion.get(field) != value:
            raise G16ExactCausalPipelineError(f"completion {field} mismatch")
    if list(completion.get("candidate_ids") or []) != list(plan.get("candidate_ids") or []):
        raise G16ExactCausalPipelineError("completion candidate set differs from pre-cutoff plan")
    if completion.get("candidate_request_policy") != (
        "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS"
    ):
        raise G16ExactCausalPipelineError("completion candidate-request policy changed")
    outputs = [dict(row) for row in posterior.get("outputs") or []]
    if int(completion.get("n_states") or 0) != len(states) or int(completion.get("n_outputs") or 0) != len(outputs):
        raise G16ExactCausalPipelineError("completion state/output counts mismatch")
    days = completion.get("days") or {}
    if list(days) != list(G16_DATES) or int(completion.get("n_days") or 0) != len(G16_DATES):
        raise G16ExactCausalPipelineError("completion lacks canonical G16 day audit")
    for day in G16_DATES:
        row = copy.deepcopy(dict(days[day]))
        day_fp = row.pop("day_audit_fingerprint", None)
        if day_fp != _fp(row):
            raise G16ExactCausalPipelineError(f"{day}: day audit fingerprint mismatch")
    actual_stand_down_days = [
        day for day in G16_DATES if int(days[day].get("n_stand_down") or 0) > 0
    ]
    if list(completion.get("stand_down_days") or []) != actual_stand_down_days:
        raise G16ExactCausalPipelineError("completion stand-down days mismatch")
    expected_status = "READY_WITH_STAND_DOWNS" if actual_stand_down_days else "READY"
    if completion.get("status") != expected_status:
        raise G16ExactCausalPipelineError("completion status hides stand-downs")


def selftest() -> int:
    from ng_g16_historical_replay import (
        _fixture_catalog,
        _fixture_inventory,
        build_manifest,
        prepare_corpus,
        replay_prepared,
    )
    from ng_g16_shadow_gate import _fixture_blind_state, _fixture_forecast, _fixture_registry

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        inventory, definition = _fixture_inventory(root)
        manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        prepared = prepare_corpus(manifest, root / "prepared")
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        replay = replay_prepared(prepared, manifest, prior)
        artifacts = build_exact_causal_pipeline(
            replay,
            prior,
            _fixture_forecast(),
            _fixture_blind_state(),
            _fixture_registry(),
        )
        assert artifacts["completion"]["n_days"] == len(G16_DATES)
        assert artifacts["completion"]["actual_g16_outcomes_used"] is False
    print("[ng_g16_exact_causal_pipeline] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run exact, outcome-blind G16 historical SHADOW refinement")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--blind-forecast", type=Path)
    parser.add_argument("--blind-safe-state", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = ("replay", "blind_prior", "blind_forecast", "blind_safe_state", "registry", "out_dir")
    if any(getattr(args, name) is None for name in required):
        parser.error("--replay --blind-prior --blind-forecast --blind-safe-state --registry --out-dir are required")
    artifacts = build_exact_causal_pipeline(
        _load(args.replay),
        _load(args.blind_prior),
        _load(args.blind_forecast),
        _load(args.blind_safe_state),
        _load(args.registry),
    )
    _atomic_json(args.out_dir / "g16_shadow_plan.json", artifacts["plan"])
    _atomic_json(args.out_dir / "g16_shadow_authorization_stream.json", artifacts["authorization_stream"])
    _atomic_json(args.out_dir / "g16_shadow_posterior_stream.json", artifacts["posterior_stream"])
    _atomic_json(args.out_dir / "g16_exact_causal_pipeline.json", artifacts["completion"])
    print(
        "[ng_g16_exact_causal_pipeline] "
        f"{artifacts['completion']['status']} "
        f"states={artifacts['completion']['n_states']} -> {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
