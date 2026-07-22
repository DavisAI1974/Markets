#!/usr/bin/env python3
"""Bind exact NGK26 replay to the outcome-blind G16 SHADOW chain."""
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
from ng_g16_shadow_gate import (
    STREAM_SCHEMA as AUTH_STREAM_SCHEMA,
    authorize_feature_stream,
    build_shadow_plan,
    validate_authorization_token,
    validate_shadow_plan,
)
from ng_g16_shadow_runner import STREAM_SCHEMA as POSTERIOR_STREAM_SCHEMA, run_stream, validate_output
from ng_rt_feature_state import validate_feature_state

SCHEMA = "ng_g16_exact_causal_pipeline.v1"
AUTHORITY = "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY"
POLICY = "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS"
NEXT_STAGE = "OUTCOME_BLIND_G16_CURVE_ADAPTER"


class G16ExactCausalPipelineError(ValueError):
    pass


def _fp(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _prior(prior: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, float]:
    values = {}
    for key in ("up", "flat", "down"):
        try:
            value = float(prior.get(key))
        except (TypeError, ValueError, OverflowError) as error:
            raise G16ExactCausalPipelineError(f"invalid blind_prior.{key}") from error
        if not math.isfinite(value) or value < 0:
            raise G16ExactCausalPipelineError(f"invalid blind_prior.{key}")
        values[key] = value
    total = sum(values.values())
    if total <= 0 or _fp(dict(prior)) != replay.get("blind_prior_fingerprint"):
        raise G16ExactCausalPipelineError("locked blind prior does not match exact replay")
    return {key: value / total for key, value in values.items()}


def _states(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        validate_replay_output(replay)
    except Exception as error:
        raise G16ExactCausalPipelineError(f"exact G16 replay invalid: {error}") from error
    streams = replay.get("streams") or []
    if len(streams) != 1:
        raise G16ExactCausalPipelineError("single-contract G16 replay requires exactly one stream")
    rows = [copy.deepcopy(dict(row)) for row in streams[0].get("states") or []]
    last_day = -1
    last_by_day: dict[str, tuple[float, int]] = {}
    seen = set()
    for state in rows:
        try:
            validate_feature_state(state)
        except Exception as error:
            raise G16ExactCausalPipelineError(f"invalid replay feature state: {error}") from error
        day = str(state.get("session_day") or "")
        if day not in G16_DATES:
            raise G16ExactCausalPipelineError(f"non-canonical G16 day: {day!r}")
        index = G16_DATES.index(day)
        current = (float(state["as_of_event_s"]), int(state.get("sequence") or 0))
        if index < last_day or (day in last_by_day and current <= last_by_day[day]):
            raise G16ExactCausalPipelineError("exact replay states are not chronological")
        if state.get("blind_prior_fingerprint") != replay.get("blind_prior_fingerprint"):
            raise G16ExactCausalPipelineError(f"{day}: state references another blind prior")
        if state.get("completed_mbo_event_boundary") is not True:
            raise G16ExactCausalPipelineError(f"{day}: state lacks completed MBO boundary")
        last_day, last_by_day[day] = index, current
        seen.add(day)
    if not rows or seen != set(G16_DATES):
        raise G16ExactCausalPipelineError("exact replay lacks canonical G16 state coverage")
    return rows


def _validate_authorizations(auth: Mapping[str, Any], plan: Mapping[str, Any], states: list[Mapping[str, Any]]) -> None:
    if auth.get("schema") != AUTH_STREAM_SCHEMA:
        raise G16ExactCausalPipelineError("authorization stream schema mismatch")
    for field in ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
        if auth.get(field) is not False:
            raise G16ExactCausalPipelineError(f"authorization stream must keep {field}=false")
    if auth.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16ExactCausalPipelineError("authorization plan fingerprint mismatch")
    payload = copy.deepcopy(dict(auth))
    observed = payload.pop("stream_fingerprint", None)
    if observed != _fp(payload):
        raise G16ExactCausalPipelineError("authorization stream fingerprint mismatch")
    tokens = [dict(row) for row in auth.get("authorizations") or []]
    if len(tokens) != len(states) or int(auth.get("n_authorizations") or 0) != len(tokens):
        raise G16ExactCausalPipelineError("authorization/state count mismatch")
    required = list(plan.get("candidate_ids") or [])
    for state, token in zip(states, tokens):
        try:
            validate_authorization_token(token, plan=plan, feature_state=state)
        except Exception as error:
            raise G16ExactCausalPipelineError(f"authorization token invalid: {error}") from error
        if list(token.get("authorized_candidate_ids") or []) != required:
            raise G16ExactCausalPipelineError("authorization did not pre-request every registered candidate")
        if token.get("baseline_microstructure_only") is not False:
            raise G16ExactCausalPipelineError("registered-candidate authorization became baseline-only")


def _validate_posterior(stream: Mapping[str, Any], plan: Mapping[str, Any], auth: Mapping[str, Any], states: list[Mapping[str, Any]]) -> None:
    _validate_authorizations(auth, plan, states)
    if stream.get("schema") != POSTERIOR_STREAM_SCHEMA:
        raise G16ExactCausalPipelineError("posterior stream schema mismatch")
    for field in ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
        if stream.get(field) is not False:
            raise G16ExactCausalPipelineError(f"posterior stream must keep {field}=false")
    payload = copy.deepcopy(dict(stream))
    observed = payload.pop("stream_fingerprint", None)
    if observed != _fp(payload):
        raise G16ExactCausalPipelineError("posterior stream fingerprint mismatch")
    if stream.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise G16ExactCausalPipelineError("posterior plan fingerprint mismatch")
    if stream.get("authorization_stream_fingerprint") != auth.get("stream_fingerprint"):
        raise G16ExactCausalPipelineError("posterior authorization fingerprint mismatch")
    outputs = [dict(row) for row in stream.get("outputs") or []]
    if len(outputs) != len(states) or int(stream.get("n_outputs") or 0) != len(outputs):
        raise G16ExactCausalPipelineError("posterior/state count mismatch")
    for state, output in zip(states, outputs):
        try:
            validate_output(output)
        except Exception as error:
            raise G16ExactCausalPipelineError(f"posterior output invalid: {error}") from error
        provenance = output.get("provenance") or {}
        if provenance.get("feature_fingerprint") != state.get("feature_fingerprint"):
            raise G16ExactCausalPipelineError("posterior references another feature state")
        if (output.get("session_day"), int(output.get("sequence") or 0), float(output.get("as_of_event_s"))) != (
            state.get("session_day"), int(state.get("sequence") or 0), float(state.get("as_of_event_s"))
        ):
            raise G16ExactCausalPipelineError("posterior/state chronology mismatch")


def _audit(states: list[Mapping[str, Any]], outputs: list[Mapping[str, Any]]) -> dict[str, Any]:
    result = {}
    for day in G16_DATES:
        pairs = [(s, o) for s, o in zip(states, outputs) if s.get("session_day") == day]
        shifts = []
        counts = {key: 0 for key in ("onset", "signed_flow", "divergence_exhaustion", "queue", "activity", "price_efficiency")}
        contributions: dict[str, float] = {}
        reasons = set()
        for state, output in pairs:
            prior, posterior = output.get("blind_prior") or {}, output.get("posterior") or {}
            shifts.append(0.5 * sum(abs(float(posterior.get(k, 0)) - float(prior.get(k, 0))) for k in ("up", "flat", "down")))
            evidence, availability = state.get("evidence") or {}, state.get("availability") or {}
            onset = evidence.get("move_onset_pressure") or {}
            counts["onset"] += onset.get("value") is not None
            counts["activity"] += onset.get("activity_ratio") is not None
            counts["price_efficiency"] += onset.get("price_efficiency") is not None
            counts["signed_flow"] += isinstance(evidence.get("signed_flow"), Mapping) and bool(availability.get("flow_update_allowed"))
            counts["divergence_exhaustion"] += isinstance(evidence.get("divergence_exhaustion"), Mapping) and (evidence.get("divergence_exhaustion") or {}).get("expect") is not None
            counts["queue"] += bool(availability.get("queue_update_allowed")) and bool(evidence.get("mbo_queue"))
            reasons.update(str(value) for value in output.get("stand_down_reasons") or [])
            for row in output.get("attribution") or []:
                identifier = str(row.get("candidate_id") or "")
                if identifier:
                    contributions[identifier] = contributions.get(identifier, 0.0) + abs(float(row.get("directional_contribution") or 0.0))
        if not pairs:
            raise G16ExactCausalPipelineError(f"{day}: no state/output pairs")
        strongest = max(range(len(pairs)), key=lambda i: shifts[i])
        row = {
            "date": day,
            "n_states": len(pairs),
            "n_updated": sum(o.get("status") == "UPDATED" for _, o in pairs),
            "n_no_change": sum(o.get("status") == "NO_CHANGE" for _, o in pairs),
            "n_stand_down": sum(o.get("status") == "STAND_DOWN" for _, o in pairs),
            "stand_down_reasons": sorted(reasons),
            "max_posterior_shift_tv": round(max(shifts), 10),
            "mean_posterior_shift_tv": round(sum(shifts) / len(shifts), 10),
            "evidence_available_counts": counts,
            "candidate_absolute_contribution": {key: round(value, 10) for key, value in sorted(contributions.items())},
            "strongest_output_fingerprint": pairs[strongest][1].get("output_fingerprint"),
        }
        row["day_audit_fingerprint"] = _fp(row)
        result[day] = row
    return result


def build_exact_causal_pipeline(replay: Mapping[str, Any], blind_prior: Mapping[str, Any], blind_forecast: Mapping[str, Any], blind_safe_state: Mapping[str, Any], registry_source: Mapping[str, Any]) -> dict[str, Any]:
    originals = copy.deepcopy((replay, blind_prior, blind_forecast, blind_safe_state, registry_source))
    states = _states(replay)
    _prior(blind_prior, replay)
    validate_blind_safe_state(blind_safe_state)
    plan = build_shadow_plan(blind_forecast, blind_safe_state, registry_source)
    validate_shadow_plan(plan, blind_forecast=blind_forecast, blind_safe_state=blind_safe_state, registry_source=registry_source)
    candidate_ids = list(plan.get("candidate_ids") or [])
    if not candidate_ids:
        raise G16ExactCausalPipelineError("no G15-adjudicated candidates are authorized for G16")
    auth = authorize_feature_stream(plan, states, requested_by_day={day: candidate_ids for day in G16_DATES})
    _validate_authorizations(auth, plan, states)
    posterior = run_stream(plan, blind_forecast, states, auth)
    _validate_posterior(posterior, plan, auth, states)
    outputs = [dict(row) for row in posterior.get("outputs") or []]
    days = _audit(states, outputs)
    stand_down_days = [day for day in G16_DATES if days[day]["n_stand_down"]]
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
        "authorization_stream_fingerprint": auth.get("stream_fingerprint"),
        "posterior_stream_fingerprint": posterior.get("stream_fingerprint"),
        "candidate_ids": candidate_ids,
        "candidate_request_policy": POLICY,
        "n_states": len(states),
        "n_outputs": len(outputs),
        "n_days": len(days),
        "stand_down_days": stand_down_days,
        "days": days,
        "next_permitted_stage": NEXT_STAGE,
    }
    completion["fingerprint"] = _fp(completion)
    artifacts = {"plan": plan, "authorization_stream": auth, "posterior_stream": posterior, "completion": completion}
    validate_pipeline_artifacts(artifacts, replay=replay, blind_prior=blind_prior, blind_forecast=blind_forecast, blind_safe_state=blind_safe_state, registry_source=registry_source)
    if (replay, blind_prior, blind_forecast, blind_safe_state, registry_source) != originals:
        raise G16ExactCausalPipelineError("pipeline mutated a source artifact")
    return artifacts


def validate_pipeline_artifacts(artifacts: Mapping[str, Any], *, replay: Mapping[str, Any], blind_prior: Mapping[str, Any], blind_forecast: Mapping[str, Any], blind_safe_state: Mapping[str, Any], registry_source: Mapping[str, Any]) -> None:
    states = _states(replay)
    _prior(blind_prior, replay)
    plan, auth, posterior = artifacts.get("plan") or {}, artifacts.get("authorization_stream") or {}, artifacts.get("posterior_stream") or {}
    validate_shadow_plan(plan, blind_forecast=blind_forecast, blind_safe_state=blind_safe_state, registry_source=registry_source)
    _validate_posterior(posterior, plan, auth, states)
    completion = copy.deepcopy(dict(artifacts.get("completion") or {}))
    observed = completion.pop("fingerprint", None)
    if observed != _fp(completion) or completion.get("schema") != SCHEMA or completion.get("authority") != AUTHORITY:
        raise G16ExactCausalPipelineError("completion fingerprint/schema mismatch")
    for field in ("execution_authority", "actual_g16_outcomes_used", "g16_scoring_authorized", "paid_live_data_assumed", "may_update_ng_brain", "may_change_g16_blind_prior", "may_change_g16_blind_forecast", "may_select_lessons_from_g16_outcomes"):
        if completion.get(field) is not False:
            raise G16ExactCausalPipelineError(f"completion must keep {field}=false")
    expected = {
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
        "blind_forecast_fingerprint": _fp(dict(blind_forecast)),
        "blind_safe_state_fingerprint": blind_safe_state.get("artifact_fingerprint"),
        "lesson_registry_fingerprint": plan.get("lesson_registry_fingerprint"),
        "lesson_adjudication_fingerprint": plan.get("lesson_adjudication_fingerprint"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "authorization_stream_fingerprint": auth.get("stream_fingerprint"),
        "posterior_stream_fingerprint": posterior.get("stream_fingerprint"),
    }
    if any(completion.get(key) != value for key, value in expected.items()):
        raise G16ExactCausalPipelineError("completion provenance mismatch")
    outputs = [dict(row) for row in posterior.get("outputs") or []]
    expected_days = _audit(states, outputs)
    if completion.get("days") != expected_days:
        raise G16ExactCausalPipelineError("completion causal audit differs from locked state/output stream")
    if list(completion.get("candidate_ids") or []) != list(plan.get("candidate_ids") or []):
        raise G16ExactCausalPipelineError("completion candidate set differs from pre-cutoff plan")
    if completion.get("candidate_request_policy") != POLICY or completion.get("next_permitted_stage") != NEXT_STAGE:
        raise G16ExactCausalPipelineError("completion policy/next-stage mismatch")
    if int(completion.get("n_states") or 0) != len(states) or int(completion.get("n_outputs") or 0) != len(outputs) or int(completion.get("n_days") or 0) != len(G16_DATES):
        raise G16ExactCausalPipelineError("completion counts mismatch")
    stand_down_days = [day for day in G16_DATES if int(expected_days[day].get("n_stand_down") or 0)]
    if completion.get("stand_down_days") != stand_down_days:
        raise G16ExactCausalPipelineError("completion stand-down mismatch")
    expected_status = "READY_WITH_STAND_DOWNS" if stand_down_days else "READY"
    if completion.get("status") != expected_status:
        raise G16ExactCausalPipelineError("completion status hides stand-downs")


def _retime_fixture(replay: dict[str, Any]) -> None:
    from ng_g16_blind_wall import session_decision_cutoff_utc
    from ng_rt_feature_state import feature_fingerprint
    for stream in replay["streams"]:
        for state in stream["states"]:
            event_time = session_decision_cutoff_utc(state["session_day"]).timestamp() + 60.0
            state["as_of_event_s"] = event_time
            state["decision_cutoff_s"] = event_time
            state["feature_fingerprint"] = feature_fingerprint(state)
    replay.pop("fingerprint", None)
    replay["fingerprint"] = _fp(replay)


def selftest() -> int:
    from ng_g16_historical_replay import _fixture_catalog, _fixture_inventory, build_manifest, prepare_corpus, replay_prepared
    from ng_g16_shadow_gate import _fixture_blind_state, _fixture_forecast, _fixture_registry
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        inventory, definition = _fixture_inventory(root)
        manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        prepared = prepare_corpus(manifest, root / "prepared")
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        replay = replay_prepared(prepared, manifest, prior)
        _retime_fixture(replay)
        result = build_exact_causal_pipeline(replay, prior, _fixture_forecast(), _fixture_blind_state(), _fixture_registry())
        assert result["completion"]["n_days"] == len(G16_DATES)
    print("[ng_g16_exact_causal_pipeline] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    for name in ("replay", "blind-prior", "blind-forecast", "blind-safe-state", "registry", "out-dir"):
        parser.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(getattr(args, name.replace("-", "_")) is None for name in ("replay", "blind-prior", "blind-forecast", "blind-safe-state", "registry", "out-dir")):
        parser.error("all artifact paths are required")
    result = build_exact_causal_pipeline(_load(args.replay), _load(args.blind_prior), _load(args.blind_forecast), _load(args.blind_safe_state), _load(args.registry))
    _atomic(args.out_dir / "g16_shadow_plan.json", result["plan"])
    _atomic(args.out_dir / "g16_shadow_authorization_stream.json", result["authorization_stream"])
    _atomic(args.out_dir / "g16_shadow_posterior_stream.json", result["posterior_stream"])
    _atomic(args.out_dir / "g16_exact_causal_pipeline.json", result["completion"])
    print(f"[ng_g16_exact_causal_pipeline] {result['completion']['status']} states={result['completion']['n_states']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
