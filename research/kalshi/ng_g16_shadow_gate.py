#!/usr/bin/env python3
"""Lock G16 refinement behind the immutable blind forecast, blind-safe state, and G15 registry.

This module does not forecast or score G16. It creates a fingerprinted pre-registration
plan and authorizes causal feature states only when:

* the canonical G16 blind forecast remains immutable;
* the decision-state artifact passed the strict pre-cutoff blind wall;
* every requested lesson was pre-registered from G15 outcome adjudication;
* the feature state is a valid REFINE_INPUT_ONLY state for the canonical NGK26 contract;
* the state occurs after the session decision cutoff and contains no G16 outcome authority.

The resulting plan and authorization tokens are SHADOW-only. They cannot update
``knowledge/ng_brain.json``, change the G16 blind prior, read G16 outcomes, or grant
execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from ng_g15_lesson_adjudication import validate_adjudication
from ng_g16_blind_wall import G16_DATES, session_decision_cutoff_utc, validate_blind_safe_state
from ng_rt_feature_state import build_feature_state, validate_feature_state

PLAN_SCHEMA = "ng_g16_shadow_refinement_plan.v1"
TOKEN_SCHEMA = "ng_g16_shadow_state_authorization.v1"
STREAM_SCHEMA = "ng_g16_shadow_authorization_stream.v1"
PLAN_AUTHORITY = "G16_PRE_CUTOFF_SHADOW_REFINEMENT_PLAN_ONLY"
TOKEN_AUTHORITY = "G16_CAUSAL_SHADOW_STATE_ONLY"
REGISTRY_SCHEMA = "ng_g16_shadow_lesson_registry.v1"
CANONICAL_DATASET = "GLBX.MDP3"
CANONICAL_INSTRUMENT_ID = 996
CANONICAL_RAW_SYMBOL = "NGK26"
FORBIDDEN_FORECAST_KEYS = {
    "actual_curve",
    "actual_path",
    "actual_move_usd",
    "actual_net_usd",
    "outcome",
    "score",
    "direction_ok",
    "correct",
}


class G16ShadowGateError(ValueError):
    """Raised when G16 refinement would cross the blind wall or lesson registry."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _artifact_fingerprint(value: Mapping[str, Any], field: str) -> str:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    expected = _fingerprint(payload)
    if not isinstance(observed, str) or observed != expected:
        raise G16ShadowGateError(f"{field} mismatch")
    return observed


def _scan_forbidden_forecast_keys(value: Any, path: str = "forecast") -> None:
    if isinstance(value, Mapping):
        for key, raw in value.items():
            if str(key) in FORBIDDEN_FORECAST_KEYS:
                raise G16ShadowGateError(f"{path}.{key}: outcome/score field is forbidden in blind forecast")
            _scan_forbidden_forecast_keys(raw, f"{path}.{key}")
    elif isinstance(value, list):
        for index, raw in enumerate(value):
            _scan_forbidden_forecast_keys(raw, f"{path}[{index}]")


def validate_blind_forecast(forecast: Mapping[str, Any]) -> None:
    if int(forecast.get("group") or 0) != 16:
        raise G16ShadowGateError("blind forecast group must be 16")
    kind = str(forecast.get("kind") or "").lower()
    if "blind" not in kind:
        raise G16ShadowGateError("G16 forecast must be explicitly blind")
    days = forecast.get("days") or []
    dates = [str(row.get("date") or "") for row in days if isinstance(row, Mapping)]
    if dates != list(G16_DATES):
        raise G16ShadowGateError("blind forecast must contain canonical G16 days in order")
    for row in days:
        if not isinstance(row, Mapping):
            raise G16ShadowGateError("blind forecast day must be an object")
        curve = row.get("guess_curve")
        if not isinstance(curve, list) or not curve:
            raise G16ShadowGateError(f"{row.get('date')}: non-empty guess_curve required")
    _scan_forbidden_forecast_keys(forecast)


def _extract_registry(source: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    if source.get("schema") == "ng_g15_lesson_adjudication.v1":
        try:
            validate_adjudication(source)
        except Exception as error:
            raise G16ShadowGateError(f"lesson adjudication invalid: {error}") from error
        registry = copy.deepcopy(dict(source.get("g16_shadow_registry") or {}))
        return registry, str(source.get("artifact_fingerprint") or "")
    return copy.deepcopy(dict(source)), None


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise G16ShadowGateError("lesson registry schema mismatch")
    if int(registry.get("source_group") or 0) != 15 or int(registry.get("target_group") or 0) != 16:
        raise G16ShadowGateError("lesson registry must map G15 to G16")
    if registry.get("authority") != "G16_PRE_CUTOFF_SHADOW_TEST_ONLY":
        raise G16ShadowGateError("lesson registry authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if registry.get(field) is not False:
            raise G16ShadowGateError(f"lesson registry {field} must remain false")
    candidates = registry.get("candidates") or []
    if int(registry.get("candidate_count") or 0) != len(candidates):
        raise G16ShadowGateError("lesson registry candidate_count mismatch")
    identifiers: set[str] = set()
    for row in candidates:
        if not isinstance(row, Mapping):
            raise G16ShadowGateError("lesson registry candidate must be an object")
        identifier = str(row.get("proposal_id") or "")
        if not identifier or identifier in identifiers:
            raise G16ShadowGateError("lesson registry candidate ids must be unique and non-empty")
        identifiers.add(identifier)
        if row.get("authority") != "G16_PRE_CUTOFF_SHADOW_TEST_ONLY":
            raise G16ShadowGateError(f"{identifier}: candidate authority mismatch")
        if row.get("pre_registered_before_g16_outcomes") is not True:
            raise G16ShadowGateError(f"{identifier}: candidate was not pre-registered")
        if row.get("may_update_ng_brain") is not False:
            raise G16ShadowGateError(f"{identifier}: brain mutation is forbidden")
        if row.get("may_change_g16_blind_prior") is not False:
            raise G16ShadowGateError(f"{identifier}: blind-prior mutation is forbidden")
        if not row.get("g15_evidence_fingerprint"):
            raise G16ShadowGateError(f"{identifier}: G15 evidence fingerprint is required")
    _artifact_fingerprint(registry, "registry_fingerprint")
    gate = registry.get("gate") or {}
    if bool(gate.get("g16_refinement_authorized")) != bool(candidates):
        raise G16ShadowGateError("lesson registry authorization disagrees with candidate set")
    if gate.get("g16_outcome_access_authorized") is not False:
        raise G16ShadowGateError("G16 outcome access must remain disabled")


def build_shadow_plan(
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
) -> dict[str, Any]:
    forecast_before = copy.deepcopy(dict(blind_forecast))
    state_before = copy.deepcopy(dict(blind_safe_state))
    registry_before = copy.deepcopy(dict(registry_source))

    validate_blind_forecast(blind_forecast)
    try:
        validate_blind_safe_state(blind_safe_state)
    except Exception as error:
        raise G16ShadowGateError(f"blind-safe state invalid: {error}") from error
    registry, adjudication_fingerprint = _extract_registry(registry_source)
    validate_registry(registry)

    forecast_days = {str(row["date"]): copy.deepcopy(dict(row)) for row in blind_forecast["days"]}
    state_days = dict(blind_safe_state.get("days") or {})
    candidate_ids = sorted(str(row["proposal_id"]) for row in registry.get("candidates") or [])
    candidate_evidence = {
        str(row["proposal_id"]): str(row["g15_evidence_fingerprint"])
        for row in registry.get("candidates") or []
    }

    days: dict[str, Any] = {}
    for day in G16_DATES:
        state_row = dict(state_days.get(day) or {})
        cutoff = session_decision_cutoff_utc(day).isoformat()
        if state_row.get("decision_cutoff_utc") != cutoff:
            raise G16ShadowGateError(f"{day}: blind-state cutoff mismatch")
        row = {
            "date": day,
            "decision_cutoff_utc": cutoff,
            "blind_forecast_day_fingerprint": _fingerprint(forecast_days[day]),
            "blind_state_day_fingerprint": state_row.get("day_fingerprint"),
            "allowed_candidate_ids": candidate_ids,
            "candidate_evidence_fingerprints": candidate_evidence,
            "target_session_tape_used": False,
            "actual_g16_outcomes_used": False,
            "execution_authority": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
        }
        row["day_plan_fingerprint"] = _fingerprint(row)
        days[day] = row

    plan = {
        "schema": PLAN_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": PLAN_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "target_session_tape_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "blind_forecast_fingerprint": _fingerprint(forecast_before),
        "blind_safe_state_fingerprint": str(blind_safe_state.get("artifact_fingerprint") or ""),
        "lesson_registry_fingerprint": str(registry.get("registry_fingerprint") or ""),
        "lesson_adjudication_fingerprint": adjudication_fingerprint,
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "n_days": len(days),
        "days": days,
        "gate": {
            "g16_shadow_refinement_authorized": bool(candidate_ids),
            "g16_outcome_access_authorized": False,
            "reason": (
                "Authorized only when at least one G15-supported lesson was pre-registered; "
                "the immutable blind forecast and pre-cutoff decision state remain separate."
            ),
        },
        "note": (
            "Pre-registration plan only. Causal target-session evidence requires a separate "
            "fingerprinted authorization token and remains SHADOW."
        ),
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    validate_shadow_plan(
        plan,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
    )

    if dict(blind_forecast) != forecast_before:
        raise G16ShadowGateError("blind forecast mutated while building plan")
    if dict(blind_safe_state) != state_before:
        raise G16ShadowGateError("blind-safe state mutated while building plan")
    if dict(registry_source) != registry_before:
        raise G16ShadowGateError("lesson registry mutated while building plan")
    return plan


def validate_shadow_plan(
    plan: Mapping[str, Any],
    *,
    blind_forecast: Mapping[str, Any] | None = None,
    blind_safe_state: Mapping[str, Any] | None = None,
    registry_source: Mapping[str, Any] | None = None,
) -> None:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("authority") != PLAN_AUTHORITY:
        raise G16ShadowGateError("shadow plan schema/authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "target_session_tape_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if plan.get(field) is not False:
            raise G16ShadowGateError(f"shadow plan {field} must remain false")
    candidate_ids = [str(value) for value in plan.get("candidate_ids") or []]
    if candidate_ids != sorted(set(candidate_ids)):
        raise G16ShadowGateError("shadow plan candidate ids must be sorted and unique")
    if int(plan.get("candidate_count") or 0) != len(candidate_ids):
        raise G16ShadowGateError("shadow plan candidate_count mismatch")
    if bool((plan.get("gate") or {}).get("g16_shadow_refinement_authorized")) != bool(candidate_ids):
        raise G16ShadowGateError("shadow plan authorization disagrees with candidates")
    if (plan.get("gate") or {}).get("g16_outcome_access_authorized") is not False:
        raise G16ShadowGateError("shadow plan cannot authorize G16 outcome access")
    day_map = plan.get("days") or {}
    if list(day_map) != list(G16_DATES) or int(plan.get("n_days") or 0) != len(G16_DATES):
        raise G16ShadowGateError("shadow plan must contain canonical G16 days")
    for day in G16_DATES:
        row = dict(day_map[day])
        observed = row.pop("day_plan_fingerprint", None)
        if observed != _fingerprint(row):
            raise G16ShadowGateError(f"{day}: day plan fingerprint mismatch")
        if row.get("decision_cutoff_utc") != session_decision_cutoff_utc(day).isoformat():
            raise G16ShadowGateError(f"{day}: decision cutoff mismatch")
        if list(row.get("allowed_candidate_ids") or []) != candidate_ids:
            raise G16ShadowGateError(f"{day}: allowed candidate set mismatch")
        for field in (
            "target_session_tape_used",
            "actual_g16_outcomes_used",
            "execution_authority",
            "may_update_ng_brain",
            "may_change_g16_blind_prior",
        ):
            if row.get(field) is not False:
                raise G16ShadowGateError(f"{day}: {field} must remain false")
    _artifact_fingerprint(plan, "plan_fingerprint")

    if blind_forecast is not None:
        validate_blind_forecast(blind_forecast)
        if plan.get("blind_forecast_fingerprint") != _fingerprint(dict(blind_forecast)):
            raise G16ShadowGateError("shadow plan blind forecast fingerprint mismatch")
    if blind_safe_state is not None:
        try:
            validate_blind_safe_state(blind_safe_state)
        except Exception as error:
            raise G16ShadowGateError(f"blind-safe state invalid: {error}") from error
        if plan.get("blind_safe_state_fingerprint") != blind_safe_state.get("artifact_fingerprint"):
            raise G16ShadowGateError("shadow plan blind-safe state fingerprint mismatch")
    if registry_source is not None:
        registry, adjudication_fingerprint = _extract_registry(registry_source)
        validate_registry(registry)
        if plan.get("lesson_registry_fingerprint") != registry.get("registry_fingerprint"):
            raise G16ShadowGateError("shadow plan lesson registry fingerprint mismatch")
        if plan.get("lesson_adjudication_fingerprint") != adjudication_fingerprint:
            raise G16ShadowGateError("shadow plan lesson adjudication fingerprint mismatch")


def authorize_feature_state(
    plan: Mapping[str, Any],
    feature_state: Mapping[str, Any],
    requested_candidate_ids: Iterable[str] = (),
) -> dict[str, Any]:
    validate_shadow_plan(plan)
    if not bool((plan.get("gate") or {}).get("g16_shadow_refinement_authorized")):
        raise G16ShadowGateError("G16 SHADOW refinement is not authorized: no eligible G15 lessons")
    try:
        validate_feature_state(dict(feature_state))
    except Exception as error:
        raise G16ShadowGateError(f"feature state invalid: {error}") from error
    day = str(feature_state.get("session_day") or "")
    if day not in G16_DATES:
        raise G16ShadowGateError("feature state lacks a canonical G16 session_day")
    day_plan = dict((plan.get("days") or {})[day])
    event_time = float(feature_state["as_of_event_s"])
    cutoff = session_decision_cutoff_utc(day).timestamp()
    if event_time <= cutoff:
        raise G16ShadowGateError(f"{day}: causal feature state must occur after the blind decision cutoff")
    instrument = dict(feature_state.get("instrument") or {})
    if (
        instrument.get("dataset") != CANONICAL_DATASET
        or int(instrument.get("instrument_id") or 0) != CANONICAL_INSTRUMENT_ID
        or instrument.get("raw_symbol") != CANONICAL_RAW_SYMBOL
    ):
        raise G16ShadowGateError(f"{day}: feature state is not canonical NGK26/996")
    requested = sorted(set(str(value) for value in requested_candidate_ids if str(value)))
    allowed = set(day_plan.get("allowed_candidate_ids") or [])
    unknown = sorted(set(requested) - allowed)
    if unknown:
        raise G16ShadowGateError(f"{day}: unregistered G15 lessons requested: {', '.join(unknown)}")

    token = {
        "schema": TOKEN_SCHEMA,
        "market": "NG",
        "group": 16,
        "session_day": day,
        "authority": TOKEN_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "day_plan_fingerprint": day_plan.get("day_plan_fingerprint"),
        "feature_fingerprint": feature_state.get("feature_fingerprint"),
        "blind_prior_fingerprint": feature_state.get("blind_prior_fingerprint"),
        "as_of_event_s": event_time,
        "sequence": int(feature_state.get("sequence") or 0),
        "instrument": copy.deepcopy(instrument),
        "authorized_candidate_ids": requested,
        "baseline_microstructure_only": not bool(requested),
        "stand_down_reasons": copy.deepcopy(
            list((feature_state.get("availability") or {}).get("stand_down_reasons") or [])
        ),
        "gate": {
            "posterior_update_allowed": bool(
                (feature_state.get("availability") or {}).get("refine_update_allowed")
            ),
            "g16_outcome_access_authorized": False,
            "registered_lessons_only": True,
        },
    }
    token["authorization_fingerprint"] = _fingerprint(token)
    validate_authorization_token(token, plan=plan, feature_state=feature_state)
    return token


def validate_authorization_token(
    token: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
    feature_state: Mapping[str, Any] | None = None,
) -> None:
    if token.get("schema") != TOKEN_SCHEMA or token.get("authority") != TOKEN_AUTHORITY:
        raise G16ShadowGateError("authorization token schema/authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if token.get(field) is not False:
            raise G16ShadowGateError(f"authorization token {field} must remain false")
    day = str(token.get("session_day") or "")
    if day not in G16_DATES:
        raise G16ShadowGateError("authorization token has invalid G16 day")
    payload = copy.deepcopy(dict(token))
    observed = payload.pop("authorization_fingerprint", None)
    if observed != _fingerprint(payload):
        raise G16ShadowGateError("authorization token fingerprint mismatch")
    if (token.get("gate") or {}).get("g16_outcome_access_authorized") is not False:
        raise G16ShadowGateError("authorization token cannot grant G16 outcome access")
    if (token.get("gate") or {}).get("registered_lessons_only") is not True:
        raise G16ShadowGateError("authorization token must enforce registered lessons")
    if plan is not None:
        validate_shadow_plan(plan)
        if token.get("plan_fingerprint") != plan.get("plan_fingerprint"):
            raise G16ShadowGateError("authorization token plan fingerprint mismatch")
        day_plan = (plan.get("days") or {})[day]
        if token.get("day_plan_fingerprint") != day_plan.get("day_plan_fingerprint"):
            raise G16ShadowGateError("authorization token day plan fingerprint mismatch")
        allowed = set(day_plan.get("allowed_candidate_ids") or [])
        requested = set(token.get("authorized_candidate_ids") or [])
        if not requested.issubset(allowed):
            raise G16ShadowGateError("authorization token contains an unregistered lesson")
    if feature_state is not None:
        try:
            validate_feature_state(dict(feature_state))
        except Exception as error:
            raise G16ShadowGateError(f"feature state invalid: {error}") from error
        if token.get("feature_fingerprint") != feature_state.get("feature_fingerprint"):
            raise G16ShadowGateError("authorization token feature fingerprint mismatch")
        if token.get("blind_prior_fingerprint") != feature_state.get("blind_prior_fingerprint"):
            raise G16ShadowGateError("authorization token blind prior fingerprint mismatch")


def authorize_feature_stream(
    plan: Mapping[str, Any],
    states: Iterable[Mapping[str, Any]],
    requested_by_day: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    validate_shadow_plan(plan)
    source = [copy.deepcopy(dict(row)) for row in states]
    tokens: list[dict[str, Any]] = []
    previous_day_index = -1
    previous_by_day: dict[str, tuple[float, int]] = {}
    requested_map = dict(requested_by_day or {})
    for state in source:
        day = str(state.get("session_day") or "")
        if day not in G16_DATES:
            raise G16ShadowGateError("feature stream contains a non-G16 day")
        day_index = G16_DATES.index(day)
        if day_index < previous_day_index:
            raise G16ShadowGateError("feature stream moved backward across G16 days")
        previous_day_index = day_index
        current = (float(state.get("as_of_event_s")), int(state.get("sequence") or 0))
        prior = previous_by_day.get(day)
        if prior is not None and (current[0] < prior[0] or current[1] <= prior[1]):
            raise G16ShadowGateError(f"{day}: feature stream is not chronological")
        previous_by_day[day] = current
        tokens.append(authorize_feature_state(plan, state, requested_map.get(day, ())))
    result = {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": "G16_CAUSAL_SHADOW_AUTHORIZATION_STREAM_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "n_authorizations": len(tokens),
        "authorizations": tokens,
    }
    result["stream_fingerprint"] = _fingerprint(result)
    return result


def _fixture_forecast() -> dict[str, Any]:
    return {
        "group": 16,
        "tag": "g16",
        "kind": "blind_panel_synthesis",
        "days": [
            {"date": day, "guess_curve": [[20, 0], [22, -10]], "guessed_net_usd": -10}
            for day in G16_DATES
        ],
    }


def _fixture_blind_state() -> dict[str, Any]:
    from ng_g16_blind_wall import build_blind_safe_state

    source: dict[str, Any] = {"_information_clock": {"globex_reopen_et": "Sun 18:00"}}
    for day in G16_DATES:
        source[day] = {"dow": day, "known": {"as_of": "2026-03-01", "value": 1}}
    return build_blind_safe_state(source)


def _fixture_registry() -> dict[str, Any]:
    registry = {
        "schema": REGISTRY_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "candidate_count": 1,
        "candidates": [
            {
                "proposal_id": "flow_confirmation",
                "mechanism": "signed flow confirms onset direction",
                "g15_status": "G15_SUPPORTED_SHADOW_CANDIDATE",
                "g15_confidence": "LOW_G15_ONLY",
                "g15_evidence_fingerprint": "a" * 64,
                "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
                "may_update_ng_brain": False,
                "may_change_g16_blind_prior": False,
                "pre_registered_before_g16_outcomes": True,
            }
        ],
        "gate": {
            "g16_refinement_authorized": True,
            "g16_outcome_access_authorized": False,
            "reason": "fixture",
        },
    }
    registry["registry_fingerprint"] = _fingerprint(registry)
    return registry


def _fixture_feature(day: str = G16_DATES[0], sequence: int = 1) -> dict[str, Any]:
    event_time = session_decision_cutoff_utc(day).timestamp() + 60.0 + sequence
    operator = {
        "schema": "ng_live_operator.v2",
        "authority": "SHADOW_TELEMETRY",
        "as_of_event_s": event_time,
        "move_onset_pressure": {
            "value": 0.7,
            "regime": "transition",
            "activity_ratio": 1.1,
            "price_efficiency": 0.6,
        },
        "signed_flow": {"imb_level": 0.4, "imb_flow": 0.2},
        "divergence_exhaustion": {"expect": "continuation"},
        "mbo_queue": {
            "book_complete": True,
            "snapshot_complete": True,
            "maybe_bad_book": False,
            "consumed_side": "ASK",
            "far_side_recruitment": 0.5,
        },
        "data_quality": {
            "book_complete": True,
            "snapshot_active": False,
            "maybe_bad_book": False,
            "missing_order_events": 0,
            "mapping_flags": [],
            "trade_events_60s": 8,
            "trade_events_15m": 20,
            "complete_mbo_events": 1,
        },
    }
    state = build_feature_state(
        blind_prior={"up": 0.3, "flat": 0.2, "down": 0.5},
        operator_snapshot=operator,
        instrument_identity={
            "dataset": CANONICAL_DATASET,
            "publisher_id": 1,
            "instrument_id": CANONICAL_INSTRUMENT_ID,
            "raw_symbol": CANONICAL_RAW_SYMBOL,
            "definition_date": "2026-03-20",
            "continuous_symbol": "NG.v.0",
            "roll_rule": "kalshi_settlement_proximity",
        },
        decision_cutoff_s=event_time,
        horizon="close",
        source_mode="historical_replay",
        sequence=sequence,
    )
    state["session_day"] = day
    state["feature_fingerprint"] = __import__("ng_rt_feature_state").feature_fingerprint(state)
    validate_feature_state(state)
    return state


def selftest() -> int:
    forecast = _fixture_forecast()
    blind_state = _fixture_blind_state()
    registry = _fixture_registry()
    plan = build_shadow_plan(forecast, blind_state, registry)
    token = authorize_feature_state(plan, _fixture_feature(), ["flow_confirmation"])
    validate_authorization_token(token, plan=plan, feature_state=_fixture_feature())
    assert token["authorized_candidate_ids"] == ["flow_confirmation"]
    assert token["execution_authority"] is False
    print("[ng_g16_shadow_gate] selftest PASS")
    return 0


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _flatten_feature_states(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload]
    if isinstance(payload, Mapping):
        if isinstance(payload.get("states"), list):
            return [dict(row) for row in payload["states"]]
        if isinstance(payload.get("streams"), list):
            return [
                dict(state)
                for stream in payload["streams"]
                for state in (stream.get("states") or [])
            ]
    raise G16ShadowGateError("feature-state input must be a list, states object, or replay streams object")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and enforce the G16 SHADOW refinement gate")
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--blind-safe-state", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--feature-states", type=Path)
    parser.add_argument("--candidate-plan", type=Path)
    parser.add_argument("--authorization-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if None in (args.blind, args.blind_safe_state, args.registry, args.out):
        parser.error("--blind, --blind-safe-state, --registry, and --out are required")
    forecast = json.loads(args.blind.read_text(encoding="utf-8"))
    blind_state = json.loads(args.blind_safe_state.read_text(encoding="utf-8"))
    registry_source = json.loads(args.registry.read_text(encoding="utf-8"))
    plan = build_shadow_plan(forecast, blind_state, registry_source)
    _atomic_json(args.out, plan)
    result: dict[str, Any] = {
        "status": "ok",
        "plan": str(args.out),
        "candidate_count": plan["candidate_count"],
        "authorized": plan["gate"]["g16_shadow_refinement_authorized"],
        "plan_fingerprint": plan["plan_fingerprint"],
    }
    if args.feature_states is not None:
        if args.authorization_out is None:
            parser.error("--authorization-out is required with --feature-states")
        feature_payload = json.loads(args.feature_states.read_text(encoding="utf-8"))
        requested = (
            json.loads(args.candidate_plan.read_text(encoding="utf-8"))
            if args.candidate_plan is not None
            else {}
        )
        stream = authorize_feature_stream(plan, _flatten_feature_states(feature_payload), requested)
        _atomic_json(args.authorization_out, stream)
        result["authorization_out"] = str(args.authorization_out)
        result["n_authorizations"] = stream["n_authorizations"]
        result["stream_fingerprint"] = stream["stream_fingerprint"]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
