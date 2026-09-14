#!/usr/bin/env python3
"""Causal feature-state contract for the NG Real-Time Refine Agent.

The same builder is used for historical replay and future live operation. It turns a
locked blind prior plus deterministic operator telemetry into a compact, validated
state. The blind prior is copied and fingerprinted; this module never mutates or
rewrites the scored forecast artifact.

Queue-derived evidence stands down on incomplete snapshots, bad books, or missing
MBO event boundaries. Trade-flow evidence may remain available independently. This
separation lets the historical one-year MBO + dense-trades corpus validate the exact
state contract intended for later live use without assuming paid live data.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Iterable

SCHEMA = "ng_rt_feature_state.v1"
DIRECTIONS = ("up", "flat", "down")
SOURCE_MODES = {"historical_replay", "live"}


class FeatureStateError(ValueError):
    """Raised when a state would violate causality or the feature contract."""


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalize_probabilities(value: dict[str, Any]) -> dict[str, float]:
    probs = {key: max(0.0, _finite(value.get(key)) or 0.0) for key in DIRECTIONS}
    total = sum(probs.values())
    if total <= 0:
        raise FeatureStateError("blind prior probabilities must have positive mass")
    normalized = {key: probs[key] / total for key in DIRECTIONS}
    if abs(sum(normalized.values()) - 1.0) > 1e-9:
        raise FeatureStateError("blind prior probabilities failed normalization")
    return normalized


def _require_identity(identity: dict[str, Any]) -> dict[str, Any]:
    required = ("dataset", "instrument_id", "raw_symbol", "definition_date")
    missing = [key for key in required if identity.get(key) in (None, "")]
    if missing:
        raise FeatureStateError(f"instrument identity missing: {', '.join(missing)}")
    return {
        "dataset": str(identity["dataset"]),
        "publisher_id": identity.get("publisher_id"),
        "instrument_id": int(identity["instrument_id"]),
        "raw_symbol": str(identity["raw_symbol"]),
        "definition_date": str(identity["definition_date"]),
        "continuous_symbol": identity.get("continuous_symbol"),
        "roll_rule": identity.get("roll_rule"),
    }


def _operator_quality(operator: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    quality = dict(operator.get("data_quality") or {})
    queue = dict(operator.get("mbo_queue") or {})
    reasons: list[str] = []

    if quality.get("maybe_bad_book") or queue.get("maybe_bad_book"):
        reasons.append("mbo_maybe_bad_book")
    if quality.get("snapshot_active"):
        reasons.append("mbo_snapshot_incomplete")
    if not quality.get("book_complete", queue.get("book_complete", False)):
        reasons.append("mbo_event_not_complete")
    if (quality.get("missing_order_events") or 0) > 0:
        reasons.append("mbo_missing_order_events")
    if quality.get("mapping_flags"):
        reasons.append("mbo_mapping_flags")

    flow = operator.get("signed_flow")
    trade_events = int(quality.get("trade_events_60s") or 0)
    if not isinstance(flow, dict):
        reasons.append("signed_flow_missing")
    if trade_events < 6:
        reasons.append("insufficient_recent_trades")

    return quality, reasons


def _evidence_payload(operator: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    onset = dict(operator.get("move_onset_pressure") or {})
    flow = dict(operator.get("signed_flow") or {}) if isinstance(operator.get("signed_flow"), dict) else None
    divergence = (
        dict(operator.get("divergence_exhaustion") or {})
        if isinstance(operator.get("divergence_exhaustion"), dict)
        else None
    )
    queue = dict(operator.get("mbo_queue") or {})

    return {
        "move_onset_pressure": {
            "value": _finite(onset.get("value")),
            "regime": onset.get("regime"),
            "activity_ratio": _finite(onset.get("activity_ratio")),
            "price_efficiency": _finite(onset.get("price_efficiency")),
        },
        "signed_flow": flow,
        "divergence_exhaustion": divergence,
        "mbo_queue": {
            "book_complete": bool(queue.get("book_complete")),
            "snapshot_complete": bool(queue.get("snapshot_complete")),
            "maybe_bad_book": bool(queue.get("maybe_bad_book")),
            "consumed_side": queue.get("consumed_side"),
            "far_side_recruitment": _finite(queue.get("far_side_recruitment")),
            "bbo": queue.get("bbo") if queue.get("book_complete") else None,
            "recent_book_deltas": queue.get("recent_book_deltas"),
        },
        "quality_counts": {
            "trade_events_60s": int(quality.get("trade_events_60s") or 0),
            "trade_events_15m": int(quality.get("trade_events_15m") or 0),
            "complete_mbo_events": int(quality.get("complete_mbo_events") or 0),
            "missing_order_events": int(quality.get("missing_order_events") or 0),
        },
    }


def build_feature_state(
    *,
    blind_prior: dict[str, Any],
    operator_snapshot: dict[str, Any],
    instrument_identity: dict[str, Any],
    decision_cutoff_s: float,
    horizon: str,
    source_mode: str,
    sequence: int,
    collector_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic feature state for historical replay or live use."""
    if source_mode not in SOURCE_MODES:
        raise FeatureStateError(f"unsupported source_mode: {source_mode}")
    if sequence < 0:
        raise FeatureStateError("sequence must be non-negative")

    operator_time = _finite(operator_snapshot.get("as_of_event_s"))
    cutoff = _finite(decision_cutoff_s)
    if operator_time is None or cutoff is None:
        raise FeatureStateError("operator and cutoff times must be finite")
    if operator_time > cutoff + 1e-9:
        raise FeatureStateError("operator snapshot is after the decision cutoff")

    prior = _normalize_probabilities(copy.deepcopy(blind_prior))
    identity = _require_identity(copy.deepcopy(instrument_identity))
    quality, reasons = _operator_quality(operator_snapshot)
    collector = dict(collector_quality or {})

    if collector.get("skipped_records"):
        reasons.append("collector_skipped_records")
    if collector.get("callback_backlog"):
        reasons.append("collector_callback_backlog")
    if collector.get("definition_mismatch"):
        reasons.append("instrument_definition_mismatch")

    queue_blockers = {
        "mbo_maybe_bad_book",
        "mbo_snapshot_incomplete",
        "mbo_event_not_complete",
        "mbo_missing_order_events",
        "mbo_mapping_flags",
        "collector_skipped_records",
        "collector_callback_backlog",
        "instrument_definition_mismatch",
    }
    flow_blockers = {
        "signed_flow_missing",
        "insufficient_recent_trades",
        "collector_skipped_records",
        "collector_callback_backlog",
        "instrument_definition_mismatch",
    }
    unique_reasons = sorted(set(reasons))
    queue_allowed = not any(reason in queue_blockers for reason in unique_reasons)
    flow_allowed = not any(reason in flow_blockers for reason in unique_reasons)

    state = {
        "schema": SCHEMA,
        "sequence": int(sequence),
        "source_mode": source_mode,
        "horizon": str(horizon),
        "as_of_event_s": operator_time,
        "decision_cutoff_s": cutoff,
        "authority": "REFINE_INPUT_ONLY",
        "execution_authority": False,
        "instrument": identity,
        "blind_prior": prior,
        "blind_prior_fingerprint": _fingerprint(prior),
        "evidence": _evidence_payload(operator_snapshot, quality),
        "availability": {
            "flow_update_allowed": flow_allowed,
            "queue_update_allowed": queue_allowed,
            "refine_update_allowed": flow_allowed or queue_allowed,
            "stand_down_reasons": unique_reasons,
        },
        "collector_quality": collector,
        "provenance": {
            "operator_schema": operator_snapshot.get("schema"),
            "operator_authority": operator_snapshot.get("authority"),
            "same_contract_for_historical_and_live": True,
        },
    }
    state["feature_fingerprint"] = feature_fingerprint(state)
    validate_feature_state(state)
    return state


def feature_fingerprint(state: dict[str, Any]) -> str:
    """Fingerprint causal model inputs while ignoring replay/live transport mode."""
    payload = {
        "schema": state.get("schema"),
        "sequence": state.get("sequence"),
        "horizon": state.get("horizon"),
        "as_of_event_s": state.get("as_of_event_s"),
        "decision_cutoff_s": state.get("decision_cutoff_s"),
        "instrument": state.get("instrument"),
        "blind_prior": state.get("blind_prior"),
        "blind_prior_fingerprint": state.get("blind_prior_fingerprint"),
        "evidence": state.get("evidence"),
        "availability": state.get("availability"),
        "collector_quality": state.get("collector_quality"),
    }
    return _fingerprint(payload)


def validate_feature_state(state: dict[str, Any]) -> None:
    if state.get("schema") != SCHEMA:
        raise FeatureStateError(f"unexpected schema: {state.get('schema')}")
    if state.get("execution_authority") is not False:
        raise FeatureStateError("feature state cannot grant execution authority")
    if state.get("authority") != "REFINE_INPUT_ONLY":
        raise FeatureStateError("feature state authority must be REFINE_INPUT_ONLY")

    event_time = _finite(state.get("as_of_event_s"))
    cutoff = _finite(state.get("decision_cutoff_s"))
    if event_time is None or cutoff is None or event_time > cutoff + 1e-9:
        raise FeatureStateError("feature state violates the decision cutoff")

    prior = _normalize_probabilities(dict(state.get("blind_prior") or {}))
    if _fingerprint(prior) != state.get("blind_prior_fingerprint"):
        raise FeatureStateError("blind prior fingerprint mismatch")
    if feature_fingerprint(state) != state.get("feature_fingerprint"):
        raise FeatureStateError("feature fingerprint mismatch")

    availability = dict(state.get("availability") or {})
    if not isinstance(availability.get("stand_down_reasons"), list):
        raise FeatureStateError("stand_down_reasons must be a list")
    _require_identity(dict(state.get("instrument") or {}))


def validate_chronological(states: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate monotonic event time/sequence for deterministic historical replay."""
    materialized = list(states)
    previous_time: float | None = None
    previous_sequence: int | None = None
    identity: tuple[Any, ...] | None = None
    for state in materialized:
        validate_feature_state(state)
        event_time = float(state["as_of_event_s"])
        sequence = int(state["sequence"])
        current_identity = (
            state["instrument"]["dataset"],
            state["instrument"].get("publisher_id"),
            state["instrument"]["instrument_id"],
            state["instrument"]["raw_symbol"],
            state["instrument"]["definition_date"],
        )
        if previous_time is not None and event_time < previous_time:
            raise FeatureStateError("historical replay event time moved backwards")
        if previous_sequence is not None and sequence <= previous_sequence:
            raise FeatureStateError("historical replay sequence must strictly increase")
        if identity is not None and current_identity != identity:
            raise FeatureStateError("instrument identity changed within one replay stream")
        previous_time = event_time
        previous_sequence = sequence
        identity = current_identity
    return materialized


def assert_transport_parity(historical: dict[str, Any], live: dict[str, Any]) -> None:
    """Require identical causal inputs across historical and live transports."""
    validate_feature_state(historical)
    validate_feature_state(live)
    if historical.get("source_mode") != "historical_replay" or live.get("source_mode") != "live":
        raise FeatureStateError("transport parity requires historical_replay and live states")
    if historical["feature_fingerprint"] != live["feature_fingerprint"]:
        raise FeatureStateError("historical/live feature-state parity failed")


def selftest() -> int:
    prior = {"up": 0.3, "flat": 0.2, "down": 0.5}
    identity = {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 123,
        "raw_symbol": "NGQ6",
        "definition_date": "2026-07-21",
        "continuous_symbol": "NG.v.0",
        "roll_rule": "volume",
    }
    operator = {
        "schema": "ng_live_operator.v2",
        "authority": "SHADOW_TELEMETRY",
        "as_of_event_s": 100.0,
        "move_onset_pressure": {"value": 0.71, "regime": "transition", "activity_ratio": 1.4, "price_efficiency": 0.42},
        "signed_flow": {"imb_level": -0.31, "imb_flow": -0.18},
        "divergence_exhaustion": {"expect": "continuation"},
        "mbo_queue": {
            "book_complete": True,
            "snapshot_complete": True,
            "maybe_bad_book": False,
            "consumed_side": "BID",
            "far_side_recruitment": -0.22,
            "bbo": {"best_bid": {"price": 3.0}, "best_ask": {"price": 3.001}},
            "recent_book_deltas": {},
        },
        "data_quality": {
            "trade_events_60s": 20,
            "trade_events_15m": 200,
            "complete_mbo_events": 500,
            "missing_order_events": 0,
            "mapping_flags": [],
            "book_complete": True,
            "snapshot_active": False,
            "snapshot_complete": True,
            "maybe_bad_book": False,
        },
    }
    historical = build_feature_state(
        blind_prior=prior,
        operator_snapshot=operator,
        instrument_identity=identity,
        decision_cutoff_s=100.0,
        horizon="close",
        source_mode="historical_replay",
        sequence=1,
    )
    live = build_feature_state(
        blind_prior=prior,
        operator_snapshot=operator,
        instrument_identity=identity,
        decision_cutoff_s=100.0,
        horizon="close",
        source_mode="live",
        sequence=1,
    )
    assert_transport_parity(historical, live)
    assert historical["availability"]["queue_update_allowed"] is True
    assert historical["availability"]["flow_update_allowed"] is True

    bad = copy.deepcopy(operator)
    bad["data_quality"]["maybe_bad_book"] = True
    bad["mbo_queue"]["maybe_bad_book"] = True
    bad_state = build_feature_state(
        blind_prior=prior,
        operator_snapshot=bad,
        instrument_identity=identity,
        decision_cutoff_s=100.0,
        horizon="close",
        source_mode="historical_replay",
        sequence=2,
    )
    assert bad_state["availability"]["queue_update_allowed"] is False
    assert bad_state["availability"]["flow_update_allowed"] is True
    validate_chronological([historical, bad_state])

    future = copy.deepcopy(operator)
    future["as_of_event_s"] = 101.0
    try:
        build_feature_state(
            blind_prior=prior,
            operator_snapshot=future,
            instrument_identity=identity,
            decision_cutoff_s=100.0,
            horizon="close",
            source_mode="historical_replay",
            sequence=3,
        )
    except FeatureStateError:
        pass
    else:
        raise AssertionError("future operator snapshot should be rejected")

    print("[ng_rt_feature_state] selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
