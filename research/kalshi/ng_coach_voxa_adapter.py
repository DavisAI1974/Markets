#!/usr/bin/env python3
"""Material-change-only coach and VOXA presentation adapter for NG posteriors.

This module is downstream of the single NG signal authority. It validates locked
G15 or G16 posterior streams and exact-key product-lag lookups, then translates
material changes into auditable coach messages and VOXA-ready payloads.

It never calculates a new market posterior, mutates a blind prior, updates
``ng_brain.json``, sends an order, or sends a VOXA message. Missing product-lag
evidence remains explicit and cannot become a timing claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

G15_OUTPUT_SCHEMA = "ng_rt_refine_output.v1"
G15_STREAM_SCHEMA = "ng_rt_refine_stream.v1"
G16_OUTPUT_SCHEMA = "ng_g16_shadow_posterior.v1"
G16_STREAM_SCHEMA = "ng_g16_shadow_posterior_stream.v1"
MESSAGE_SCHEMA = "ng_coach_message.v1"
STREAM_SCHEMA = "ng_coach_message_stream.v1"
VOXA_SCHEMA = "voxa.ng_coach_message.v1"
AUTHORITY = "NG_COACH_PRESENTATION_ONLY"
STREAM_AUTHORITY = "NG_COACH_PRESENTATION_STREAM_ONLY"
LAG_SCHEMA = "ng_product_lag_lookup.v1"
LAG_AUTHORITY = "PRODUCT_SPECIFIC_LAG_RESEARCH_ONLY"
MEASURED = "MEASURED_WINDOW"
NO_WINDOW = "NO_MEASURED_WINDOW"
NO_LOOKUP = "NO_LOOKUP_ARTIFACT"
DIRECTIONS = ("up", "flat", "down")
LAG_KEY_FIELDS = (
    "venue", "product", "series", "contract", "strike", "liquidity_bucket",
    "move_size_bucket", "time_of_day_bucket", "regime",
)
DEFAULT_CONFIG = {
    "posterior_l1_threshold": 0.12,
    "top_probability_threshold": 0.52,
    "invalidation_drop_threshold": 0.12,
}


class CoachAdapterError(ValueError):
    """Raised for contradictory, unsafe, or tampered coach inputs/outputs."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CoachAdapterError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise CoachAdapterError(f"{name} must be finite")
    return result


def _normalise_probabilities(value: Mapping[str, Any], name: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for direction in DIRECTIONS:
        probability = _finite(value.get(direction, 0.0), f"{name}.{direction}")
        if probability < 0:
            raise CoachAdapterError(f"{name}.{direction} cannot be negative")
        result[direction] = probability
    total = sum(result.values())
    if total <= 0:
        raise CoachAdapterError(f"{name} must carry positive probability mass")
    return {direction: result[direction] / total for direction in DIRECTIONS}


def _top_direction(probabilities: Mapping[str, float]) -> tuple[str, float]:
    order = {"up": 2, "down": 1, "flat": 0}
    direction = max(DIRECTIONS, key=lambda key: (float(probabilities[key]), order[key]))
    return direction, float(probabilities[direction])


def _output_fingerprint(output: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(output))
    payload.pop("output_fingerprint", None)
    return _fp(payload)


def _stream_fingerprint(stream: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(stream))
    payload.pop("stream_fingerprint", None)
    return _fp(payload)


def validate_posterior_output(raw: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(raw))
    schema = output.get("schema")
    if schema not in {G15_OUTPUT_SCHEMA, G16_OUTPUT_SCHEMA}:
        raise CoachAdapterError(f"unsupported posterior schema: {schema}")
    expected_group = 15 if schema == G15_OUTPUT_SCHEMA else 16
    expected_authority = (
        "REFINE_POSTERIOR_ONLY" if schema == G15_OUTPUT_SCHEMA
        else "G16_CAUSAL_SHADOW_POSTERIOR_ONLY"
    )
    if output.get("authority") != expected_authority:
        raise CoachAdapterError("posterior authority mismatch")
    if output.get("execution_authority") is not False:
        raise CoachAdapterError("posterior cannot grant execution authority")
    if schema == G16_OUTPUT_SCHEMA:
        for field in ("actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
            if output.get(field) is not False:
                raise CoachAdapterError(f"{field} must remain false")
    day = str(output.get("session_day") or "")
    if len(day) != 8 or not day.isdigit():
        raise CoachAdapterError("posterior requires YYYYMMDD session_day")
    sequence = int(output.get("sequence") or 0)
    if sequence < 1:
        raise CoachAdapterError("posterior sequence must be positive")
    event_time = _finite(output.get("as_of_event_s"), "as_of_event_s")
    prior = _normalise_probabilities(output.get("blind_prior") or {}, "blind_prior")
    posterior = _normalise_probabilities(output.get("posterior") or {}, "posterior")
    status = str(output.get("status") or "")
    if status not in {"UPDATED", "NO_CHANGE", "STAND_DOWN"}:
        raise CoachAdapterError("invalid posterior status")
    if status == "STAND_DOWN" and posterior != prior:
        raise CoachAdapterError("stand-down posterior changed blind prior")
    if output.get("output_fingerprint") != _output_fingerprint(output):
        raise CoachAdapterError("posterior output fingerprint mismatch")
    if expected_group == 15:
        if not output.get("feature_fingerprint") or not output.get("blind_prior_fingerprint"):
            raise CoachAdapterError("G15 posterior lacks causal fingerprints")
    else:
        provenance = output.get("provenance") or {}
        if not provenance.get("feature_fingerprint") or not provenance.get("authorization_fingerprint"):
            raise CoachAdapterError("G16 posterior lacks causal authorization fingerprints")
    output["blind_prior"] = prior
    output["posterior"] = posterior
    output["session_day"] = day
    output["sequence"] = sequence
    output["as_of_event_s"] = event_time
    output["_group"] = expected_group
    return output


def validate_posterior_stream(raw: Mapping[str, Any]) -> dict[str, Any]:
    stream = copy.deepcopy(dict(raw))
    schema = stream.get("schema")
    if schema == G15_STREAM_SCHEMA:
        group, authority = 15, "REFINE_POSTERIOR_STREAM_ONLY"
    elif schema == G16_STREAM_SCHEMA:
        group, authority = 16, "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY"
    else:
        raise CoachAdapterError(f"unsupported posterior stream schema: {schema}")
    if int(stream.get("group") or 0) != group or stream.get("market") != "NG":
        raise CoachAdapterError("posterior stream market/group mismatch")
    if stream.get("authority") != authority or stream.get("execution_authority") is not False:
        raise CoachAdapterError("posterior stream authority mismatch")
    if group == 16:
        for field in ("actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
            if stream.get(field) is not False:
                raise CoachAdapterError(f"{field} must remain false")
        if stream.get("stream_fingerprint") != _stream_fingerprint(stream):
            raise CoachAdapterError("G16 posterior stream fingerprint mismatch")
    outputs = [validate_posterior_output(row) for row in stream.get("outputs") or []]
    if int(stream.get("n_outputs") or 0) != len(outputs):
        raise CoachAdapterError("posterior stream count mismatch")
    previous: tuple[float, int] | None = None
    for output in outputs:
        if output["_group"] != group:
            raise CoachAdapterError("posterior output group differs from stream")
        current = (float(output["as_of_event_s"]), int(output["sequence"]))
        if previous is not None and current <= previous:
            raise CoachAdapterError("posterior stream is not chronological")
        previous = current
        output.pop("_group", None)
    stream["outputs"] = outputs
    stream["_source_stream_fingerprint"] = stream.get("stream_fingerprint") or _fp(stream)
    return stream


def _normalise_lag_key(raw: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in LAG_KEY_FIELDS if field not in raw]
    if missing:
        raise CoachAdapterError("lag key missing: " + ", ".join(missing))
    result: dict[str, Any] = {}
    for field in LAG_KEY_FIELDS:
        value = raw.get(field)
        if field == "strike" and value is None:
            result[field] = None
            continue
        text = str(value or "").strip()
        if not text:
            raise CoachAdapterError(f"lag key {field} is required")
        result[field] = text.lower() if field == "venue" else text
    return result


def validate_lag_lookup(raw: Mapping[str, Any]) -> dict[str, Any]:
    lookup = copy.deepcopy(dict(raw))
    supplied = lookup.pop("fingerprint", None)
    if lookup.get("schema") != LAG_SCHEMA or lookup.get("authority") != LAG_AUTHORITY:
        raise CoachAdapterError("unexpected lag lookup schema or authority")
    if lookup.get("status") not in {MEASURED, NO_WINDOW}:
        raise CoachAdapterError("invalid lag lookup status")
    if lookup.get("strictly_pre_cutoff") is not True or lookup.get("fallback_used") is not False:
        raise CoachAdapterError("lag lookup must remain exact-key and pre-cutoff")
    if lookup.get("execution_authority") is not False or lookup.get("may_update_ng_brain") is not False:
        raise CoachAdapterError("lag lookup cannot grant authority")
    key = _normalise_lag_key(lookup.get("key") or {})
    if lookup.get("key_fingerprint") != _fp(key):
        raise CoachAdapterError("lag lookup key fingerprint mismatch")
    cutoff = _finite(lookup.get("as_of_s"), "lag.as_of_s")
    eligible = int(lookup.get("eligible_pre_cutoff_observations") or 0)
    minimum = int(lookup.get("minimum_samples") or 0)
    if minimum < 1:
        raise CoachAdapterError("lag lookup minimum_samples must be positive")
    if lookup.get("status") == MEASURED:
        if eligible < minimum or not isinstance(lookup.get("first_reprice_window"), Mapping):
            raise CoachAdapterError("measured lag lookup lacks a sufficient window")
        if lookup.get("reasons"):
            raise CoachAdapterError("measured lag lookup cannot carry failure reasons")
    else:
        if lookup.get("first_reprice_window") is not None or lookup.get("completion_window") is not None:
            raise CoachAdapterError("NO_MEASURED_WINDOW cannot expose a lag window")
        if not lookup.get("reasons"):
            raise CoachAdapterError("NO_MEASURED_WINDOW requires reasons")
    if supplied != _fp(lookup):
        raise CoachAdapterError("lag lookup fingerprint mismatch")
    lookup["fingerprint"] = supplied
    lookup["key"] = key
    lookup["as_of_s"] = cutoff
    return lookup


def normalise_lag_attachments(raw: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    rows = list(raw.get("attachments") or raw.get("lookups") or []) if isinstance(raw, Mapping) else raw
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        fingerprint = str(row.get("posterior_output_fingerprint") or "").strip()
        if not fingerprint:
            raise CoachAdapterError("lag attachment lacks posterior_output_fingerprint")
        if fingerprint in result:
            raise CoachAdapterError("duplicate lag attachment for posterior output")
        result[fingerprint] = validate_lag_lookup(row.get("lookup") or {})
    return result


def _posterior_distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(abs(float(left[key]) - float(right[key])) for key in DIRECTIONS)


def _stand_down_reasons(output: Mapping[str, Any]) -> list[str]:
    source = ((output.get("availability") or {}).get("stand_down_reasons") or []) if output.get("schema") == G15_OUTPUT_SCHEMA else (output.get("stand_down_reasons") or [])
    return sorted({str(value) for value in source if str(value).strip()})


def _strongest_attribution(output: Mapping[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for row in output.get("attribution") or []:
        if not bool(row.get("used")):
            continue
        if "contribution" in row:
            contribution = _finite(row.get("contribution"), "attribution.contribution")
            name = str(row.get("name") or "")
        else:
            contribution = _finite(row.get("directional_contribution", 0.0), "attribution.directional_contribution")
            name = str(row.get("candidate_id") or "")
        candidates.append({"name": name or "unnamed", "contribution": contribution, "value": copy.deepcopy(row.get("value"))})
    return None if not candidates else max(candidates, key=lambda row: (abs(float(row["contribution"])), row["name"]))


def _lag_summary(lookup: Mapping[str, Any] | None) -> dict[str, Any]:
    if lookup is None:
        return {
            "status": NO_LOOKUP, "timing_claim_allowed": False,
            "text": "Product lag was not supplied; no follower timing claim is made.",
            "lookup_fingerprint": None, "key_fingerprint": None,
            "eligible_pre_cutoff_observations": 0, "first_reprice_p50_ms": None,
            "first_reprice_p90_ms": None, "reasons": ["NO_LOOKUP_ARTIFACT"],
        }
    clean = validate_lag_lookup(lookup)
    if clean["status"] == MEASURED:
        window = clean["first_reprice_window"]
        p50 = _finite(window.get("p50_ms"), "first_reprice_window.p50_ms")
        p90 = _finite(window.get("p90_ms"), "first_reprice_window.p90_ms")
        return {
            "status": MEASURED, "timing_claim_allowed": True,
            "text": f"Exact-product first reprice median {p50:.0f} ms, p90 {p90:.0f} ms from {int(clean['eligible_pre_cutoff_observations'])} pre-cutoff observations.",
            "lookup_fingerprint": clean["fingerprint"], "key_fingerprint": clean["key_fingerprint"],
            "eligible_pre_cutoff_observations": int(clean["eligible_pre_cutoff_observations"]),
            "first_reprice_p50_ms": p50, "first_reprice_p90_ms": p90, "reasons": [],
        }
    return {
        "status": NO_WINDOW, "timing_claim_allowed": False,
        "text": "No measured lag window exists for the exact product key; no follower timing claim is made.",
        "lookup_fingerprint": clean["fingerprint"], "key_fingerprint": clean["key_fingerprint"],
        "eligible_pre_cutoff_observations": int(clean["eligible_pre_cutoff_observations"]),
        "first_reprice_p50_ms": None, "first_reprice_p90_ms": None,
        "reasons": list(clean.get("reasons") or []),
    }


def _direction_label(direction: str) -> str:
    return {"up": "upward", "down": "downward", "flat": "balanced"}[direction]


def _build_text(event_type: str, day: str, posterior: Mapping[str, float], prior: Mapping[str, float], previous_direction: str | None, strongest: Mapping[str, Any] | None, reasons: Sequence[str], lag: Mapping[str, Any]) -> str:
    direction, probability = _top_direction(posterior)
    prior_direction, prior_probability = _top_direction(prior)
    if event_type == "STAND_DOWN":
        lead = f"NG coach is standing down for {day}: {', '.join(reasons) if reasons else 'data-quality gate'}."
    elif event_type == "RECOVERY":
        lead = f"NG causal inputs recovered for {day}. The posterior now favors {_direction_label(direction)} at {probability:.0%}."
    elif event_type == "DIRECTION_CHANGE":
        lead = f"NG direction changed from {_direction_label(previous_direction or prior_direction)} to {_direction_label(direction)} for {day}; probability is {probability:.0%}."
    elif event_type == "INVALIDATION":
        lead = f"The prior {_direction_label(previous_direction or prior_direction)} NG view is invalidated for {day}. Current posterior: {_direction_label(direction)} at {probability:.0%}."
    elif event_type == "LAG_STATUS_CHANGE":
        lead = f"NG product-timing evidence changed for {day}. Current market posterior favors {_direction_label(direction)} at {probability:.0%}."
    else:
        lead = f"NG posterior for {day} favors {_direction_label(direction)} at {probability:.0%}, versus {_direction_label(prior_direction)} at {prior_probability:.0%} in the blind prior."
    if strongest and event_type != "STAND_DOWN":
        lead += f" Strongest causal input: {strongest['name']}."
    return lead + " " + str(lag["text"])


def _message_fingerprint(message: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(message))
    payload.pop("message_fingerprint", None)
    return _fp(payload)


def validate_message(raw: Mapping[str, Any]) -> dict[str, Any]:
    message = copy.deepcopy(dict(raw))
    if message.get("schema") != MESSAGE_SCHEMA or message.get("authority") != AUTHORITY:
        raise CoachAdapterError("unexpected coach message schema or authority")
    if message.get("material_change") is not True:
        raise CoachAdapterError("coach messages must represent material changes")
    for field in ("execution_authority", "may_update_ng_brain", "may_change_posterior", "may_change_blind_prior", "delivery_authority"):
        if message.get(field) is not False:
            raise CoachAdapterError(f"{field} must remain false")
    if message.get("transport_status") != "ADAPTER_ONLY_NOT_SENT":
        raise CoachAdapterError("coach adapter cannot claim message delivery")
    _normalise_probabilities(message.get("posterior") or {}, "message.posterior")
    _normalise_probabilities(message.get("blind_prior") or {}, "message.blind_prior")
    _finite(message.get("as_of_event_s"), "message.as_of_event_s")
    if message.get("message_fingerprint") != _message_fingerprint(message):
        raise CoachAdapterError("coach message fingerprint mismatch")
    voxa = message.get("voxa_payload") or {}
    if voxa.get("schema") != VOXA_SCHEMA or voxa.get("transport_status") != "ADAPTER_ONLY_NOT_SENT":
        raise CoachAdapterError("invalid VOXA payload")
    if voxa.get("speech_text") != message.get("speech_text"):
        raise CoachAdapterError("VOXA speech text mismatch")
    return message


def _priority(event_type: str) -> str:
    return {"STAND_DOWN": "critical", "RECOVERY": "high", "DIRECTION_CHANGE": "high", "INVALIDATION": "high", "LAG_STATUS_CHANGE": "normal", "INITIAL_UPDATE": "normal", "POSTERIOR_SHIFT": "normal"}[event_type]


def _build_message(group: int, source_stream_fingerprint: str, output: Mapping[str, Any], event_type: str, triggers: Sequence[str], previous_direction: str | None, invalidates: str | None, lag: Mapping[str, Any]) -> dict[str, Any]:
    posterior = _normalise_probabilities(output.get("posterior") or {}, "posterior")
    prior = _normalise_probabilities(output.get("blind_prior") or {}, "blind_prior")
    direction, probability = _top_direction(posterior)
    reasons = _stand_down_reasons(output)
    strongest = _strongest_attribution(output)
    text = _build_text(event_type, str(output["session_day"]), posterior, prior, previous_direction, strongest, reasons, lag)
    dedupe_key = _fp({"group": group, "posterior_output_fingerprint": output["output_fingerprint"], "event_type": event_type, "lag_lookup_fingerprint": lag.get("lookup_fingerprint")})
    message: dict[str, Any] = {
        "schema": MESSAGE_SCHEMA, "authority": AUTHORITY, "market": "NG", "group": group,
        "session_day": output["session_day"], "sequence": int(output["sequence"]),
        "as_of_event_s": float(output["as_of_event_s"]), "event_type": event_type,
        "priority": _priority(event_type), "material_change": True,
        "triggers": sorted(set(str(value) for value in triggers)),
        "posterior_status": output["status"], "blind_prior": prior, "posterior": posterior,
        "top_direction": direction, "top_probability": probability,
        "stand_down_reasons": reasons, "strongest_attribution": strongest,
        "lag": copy.deepcopy(dict(lag)), "invalidates_message_fingerprint": invalidates,
        "display_text": text, "speech_text": text, "dedupe_key": dedupe_key,
        "source": {"posterior_output_fingerprint": output["output_fingerprint"], "posterior_stream_fingerprint": source_stream_fingerprint, "lag_lookup_fingerprint": lag.get("lookup_fingerprint")},
        "voxa_payload": {
            "schema": VOXA_SCHEMA, "intent": "markets.ng.coach_update", "speech_text": text,
            "display_text": text, "priority": _priority(event_type), "dedupe_key": dedupe_key,
            "metadata": {"market": "NG", "group": group, "session_day": output["session_day"], "sequence": int(output["sequence"]), "event_type": event_type, "top_direction": direction, "top_probability": probability, "posterior_output_fingerprint": output["output_fingerprint"]},
            "transport_status": "ADAPTER_ONLY_NOT_SENT",
        },
        "transport_status": "ADAPTER_ONLY_NOT_SENT", "execution_authority": False,
        "may_update_ng_brain": False, "may_change_posterior": False,
        "may_change_blind_prior": False, "delivery_authority": False,
    }
    message["message_fingerprint"] = _message_fingerprint(message)
    validate_message(message)
    return message


def _validate_config(raw: Mapping[str, Any] | None) -> dict[str, float]:
    source = dict(DEFAULT_CONFIG)
    source.update(dict(raw or {}))
    result = {key: _finite(source.get(key), f"config.{key}") for key in DEFAULT_CONFIG}
    for key, value in result.items():
        if value < 0 or value > 2:
            raise CoachAdapterError(f"config.{key} is outside a safe range")
    return result


def _stream_payload_fingerprint(stream: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(stream))
    payload.pop("stream_fingerprint", None)
    return _fp(payload)


def validate_coach_stream(raw: Mapping[str, Any]) -> dict[str, Any]:
    stream = copy.deepcopy(dict(raw))
    if stream.get("schema") != STREAM_SCHEMA or stream.get("authority") != STREAM_AUTHORITY:
        raise CoachAdapterError("unexpected coach stream schema or authority")
    for field in ("execution_authority", "may_update_ng_brain", "may_change_posterior", "may_change_blind_prior", "delivery_authority"):
        if stream.get(field) is not False:
            raise CoachAdapterError(f"{field} must remain false")
    if stream.get("transport_status") != "ADAPTER_ONLY_NOT_SENT":
        raise CoachAdapterError("coach stream cannot claim delivery")
    messages = [validate_message(row) for row in stream.get("messages") or []]
    audit = list(stream.get("audit") or [])
    terminal = dict(stream.get("terminal_state_by_day") or {})
    if int(stream.get("n_messages") or 0) != len(messages):
        raise CoachAdapterError("coach stream message count mismatch")
    if int(stream.get("n_posterior_outputs") or 0) != len(audit):
        raise CoachAdapterError("coach stream audit count mismatch")
    audit_fingerprints = {str(row.get("posterior_output_fingerprint") or "") for row in audit}
    for day, state in terminal.items():
        if len(str(day)) != 8 or not str(day).isdigit():
            raise CoachAdapterError("terminal state has invalid session day")
        _normalise_probabilities(state.get("posterior") or {}, "terminal.posterior")
        if state.get("posterior_status") not in {"UPDATED", "NO_CHANGE", "STAND_DOWN"}:
            raise CoachAdapterError("terminal state has invalid posterior status")
        if state.get("lag_status") not in {MEASURED, NO_WINDOW, NO_LOOKUP}:
            raise CoachAdapterError("terminal state has invalid lag status")
        if state.get("active_direction") is not None and state.get("active_direction") not in DIRECTIONS:
            raise CoachAdapterError("terminal state has invalid active direction")
        if str(state.get("posterior_output_fingerprint") or "") not in audit_fingerprints and stream.get("previous_coach_stream_fingerprint") is None:
            raise CoachAdapterError("terminal state lacks a processed posterior audit row")
    fingerprints = [row["message_fingerprint"] for row in messages]
    dedupe = [row["dedupe_key"] for row in messages]
    if len(fingerprints) != len(set(fingerprints)) or len(dedupe) != len(set(dedupe)):
        raise CoachAdapterError("duplicate coach message or dedupe key")
    previous = (-math.inf, -1)
    for message in messages:
        current = (float(message["as_of_event_s"]), int(message["sequence"]))
        if current <= previous:
            raise CoachAdapterError("coach messages are not chronological")
        previous = current
    if stream.get("stream_fingerprint") != _stream_payload_fingerprint(stream):
        raise CoachAdapterError("coach stream fingerprint mismatch")
    stream["messages"] = messages
    return stream


def build_coach_stream(posterior_stream_raw: Mapping[str, Any], *, lag_attachments: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None, config: Mapping[str, Any] | None = None, previous_stream: Mapping[str, Any] | None = None) -> dict[str, Any]:
    original_inputs = copy.deepcopy({"posterior_stream": dict(posterior_stream_raw), "lag_attachments": lag_attachments, "config": config, "previous_stream": previous_stream})
    posterior_stream = validate_posterior_stream(posterior_stream_raw)
    group = int(posterior_stream["group"])
    source_stream_fp = str(posterior_stream.pop("_source_stream_fingerprint"))
    attachments = normalise_lag_attachments(lag_attachments)
    thresholds = _validate_config(config)
    prior_messages: list[dict[str, Any]] = []
    prior_stream_fp: str | None = None
    clean_previous = None
    if previous_stream is not None:
        clean_previous = validate_coach_stream(previous_stream)
        if int(clean_previous.get("group") or 0) != group:
            raise CoachAdapterError("previous coach stream group mismatch")
        prior_messages = list(clean_previous["messages"])
        prior_stream_fp = clean_previous["stream_fingerprint"]
    already_processed: set[str] = set()
    last_message_by_day: dict[str, dict[str, Any]] = {}
    last_posterior_by_day: dict[str, dict[str, float]] = {}
    last_status_by_day: dict[str, str] = {}
    last_lag_by_day: dict[str, str] = {}
    active_direction_by_day: dict[str, str | None] = {}
    terminal_state_by_day: dict[str, dict[str, Any]] = {}
    if clean_previous is not None:
        already_processed = {str(row.get("posterior_output_fingerprint") or "") for row in clean_previous.get("audit") or []}
        terminal_state_by_day = copy.deepcopy(dict(clean_previous.get("terminal_state_by_day") or {}))
        for day, terminal in terminal_state_by_day.items():
            last_posterior_by_day[day] = _normalise_probabilities(terminal.get("posterior") or {}, "previous.terminal.posterior")
            last_status_by_day[day] = str(terminal["posterior_status"])
            last_lag_by_day[day] = str(terminal["lag_status"])
            active_direction_by_day[day] = terminal.get("active_direction")
    for message in prior_messages:
        last_message_by_day[str(message["session_day"])] = message
    messages: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    consumed_attachments: set[str] = set()
    for output in posterior_stream["outputs"]:
        output_fp = str(output["output_fingerprint"])
        day = str(output["session_day"])
        if output_fp in already_processed:
            audit.append({"posterior_output_fingerprint": output_fp, "session_day": day, "as_of_event_s": output["as_of_event_s"], "emitted": False, "suppression_reasons": ["ALREADY_EMITTED_IN_PREVIOUS_STREAM"]})
            continue
        lookup = attachments.get(output_fp)
        if lookup is not None:
            if float(lookup["as_of_s"]) > float(output["as_of_event_s"]):
                raise CoachAdapterError("lag lookup cutoff is after posterior event")
            consumed_attachments.add(output_fp)
        lag = _lag_summary(lookup)
        posterior, prior = dict(output["posterior"]), dict(output["blind_prior"])
        previous_posterior = last_posterior_by_day.get(day)
        previous_status = last_status_by_day.get(day)
        previous_lag = last_lag_by_day.get(day)
        previous_active = active_direction_by_day.get(day)
        previous_message = last_message_by_day.get(day)
        direction, probability = _top_direction(posterior)
        triggers: list[str] = []
        event_type: str | None = None
        invalidates: str | None = None
        if output["status"] == "STAND_DOWN":
            reasons = _stand_down_reasons(output)
            prior_reasons = list(previous_message.get("stand_down_reasons") or []) if previous_message else []
            if previous_status != "STAND_DOWN" or reasons != prior_reasons:
                event_type = "STAND_DOWN"
                triggers.append("STAND_DOWN_TRANSITION" if previous_status != "STAND_DOWN" else "STAND_DOWN_REASON_CHANGE")
                invalidates = None if previous_message is None else previous_message["message_fingerprint"]
        elif previous_status == "STAND_DOWN":
            event_type, triggers = "RECOVERY", ["DATA_QUALITY_RECOVERY"]
        else:
            reference = previous_posterior or prior
            distance = _posterior_distance(posterior, reference)
            reference_direction, _ = _top_direction(reference)
            if previous_posterior is not None and direction != reference_direction and probability >= thresholds["top_probability_threshold"]:
                event_type = "DIRECTION_CHANGE"
                triggers.extend(["TOP_DIRECTION_CHANGED", f"POSTERIOR_L1={distance:.6f}"])
                invalidates = previous_message["message_fingerprint"] if previous_message else None
            elif previous_active is not None:
                drop = float(reference.get(previous_active, 0.0)) - float(posterior.get(previous_active, 0.0))
                if drop >= thresholds["invalidation_drop_threshold"] or (float(posterior.get(previous_active, 0.0)) < thresholds["top_probability_threshold"] and previous_active != direction):
                    event_type = "INVALIDATION"
                    triggers.append(f"ACTIVE_DIRECTION_PROBABILITY_DROP={drop:.6f}")
                    invalidates = previous_message["message_fingerprint"] if previous_message else None
            if event_type is None and previous_lag is not None and lag["status"] != previous_lag:
                event_type = "LAG_STATUS_CHANGE"
                triggers.append(f"LAG_STATUS:{previous_lag}->{lag['status']}")
            if event_type is None and output["status"] == "UPDATED":
                if previous_posterior is None and distance >= thresholds["posterior_l1_threshold"]:
                    event_type, triggers = "INITIAL_UPDATE", [f"BLIND_TO_POSTERIOR_L1={distance:.6f}"]
                elif previous_posterior is not None and distance >= thresholds["posterior_l1_threshold"]:
                    event_type, triggers = "POSTERIOR_SHIFT", [f"POSTERIOR_L1={distance:.6f}"]
            if event_type is None and previous_posterior is None and lag["status"] == MEASURED:
                event_type, triggers = "LAG_STATUS_CHANGE", ["FIRST_EXACT_PRODUCT_LAG_WINDOW"]
        if event_type is None:
            suppression = ["NO_MATERIAL_CHANGE"] + (["POSTERIOR_STATUS_NO_CHANGE"] if output["status"] == "NO_CHANGE" else [])
            audit.append({"posterior_output_fingerprint": output_fp, "session_day": day, "as_of_event_s": output["as_of_event_s"], "emitted": False, "suppression_reasons": suppression, "lag_status": lag["status"]})
        else:
            message = _build_message(group, source_stream_fp, output, event_type, triggers, previous_active, invalidates, lag)
            messages.append(message)
            audit.append({"posterior_output_fingerprint": output_fp, "session_day": day, "as_of_event_s": output["as_of_event_s"], "emitted": True, "message_fingerprint": message["message_fingerprint"], "event_type": event_type, "lag_status": lag["status"]})
            last_message_by_day[day] = message
            active_direction_by_day[day] = None if event_type == "STAND_DOWN" else direction
        last_posterior_by_day[day] = posterior
        last_status_by_day[day] = str(output["status"])
        last_lag_by_day[day] = str(lag["status"])
        terminal_state_by_day[day] = {
            "posterior_output_fingerprint": output_fp, "as_of_event_s": float(output["as_of_event_s"]),
            "sequence": int(output["sequence"]), "posterior": posterior,
            "posterior_status": str(output["status"]), "lag_status": str(lag["status"]),
            "active_direction": active_direction_by_day.get(day),
            "last_message_fingerprint": None if last_message_by_day.get(day) is None else last_message_by_day[day]["message_fingerprint"],
        }
    unused = sorted(set(attachments) - consumed_attachments)
    if unused:
        raise CoachAdapterError("lag attachments reference unknown or unprocessed posterior outputs: " + ", ".join(unused))
    result: dict[str, Any] = {
        "schema": STREAM_SCHEMA, "authority": STREAM_AUTHORITY, "market": "NG", "group": group,
        "source_posterior_stream_schema": posterior_stream["schema"],
        "source_posterior_stream_fingerprint": source_stream_fp,
        "previous_coach_stream_fingerprint": prior_stream_fp, "config": thresholds,
        "material_change_only": True, "one_signal_authority_preserved": True,
        "n_posterior_outputs": len(audit), "n_messages": len(messages),
        "n_suppressed": sum(not bool(row["emitted"]) for row in audit),
        "messages": messages, "audit": audit,
        "terminal_state_by_day": {day: terminal_state_by_day[day] for day in sorted(terminal_state_by_day)},
        "transport_status": "ADAPTER_ONLY_NOT_SENT", "execution_authority": False,
        "may_update_ng_brain": False, "may_change_posterior": False,
        "may_change_blind_prior": False, "delivery_authority": False,
    }
    result["stream_fingerprint"] = _stream_payload_fingerprint(result)
    validate_coach_stream(result)
    current_inputs = {"posterior_stream": dict(posterior_stream_raw), "lag_attachments": lag_attachments, "config": config, "previous_stream": previous_stream}
    if current_inputs != original_inputs:
        raise CoachAdapterError("coach adapter mutated source artifacts")
    return result


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _fixture_output(sequence: int, posterior: Mapping[str, float], *, status: str = "UPDATED") -> dict[str, Any]:
    output: dict[str, Any] = {
        "schema": G15_OUTPUT_SCHEMA, "source_mode": "historical_replay",
        "session_day": "20260318", "sequence": sequence, "horizon": "close",
        "as_of_event_s": float(sequence * 100), "authority": "REFINE_POSTERIOR_ONLY",
        "execution_authority": False, "blind_prior": {"up": 0.4, "flat": 0.2, "down": 0.4},
        "blind_prior_fingerprint": "blind", "feature_fingerprint": f"feature-{sequence}",
        "anchor_fingerprint": "anchor", "posterior": dict(posterior), "status": status,
        "scores": {"directional_log_weight": 0.0, "flat_log_weight": 0.0, "update_strength": 1.0},
        "attribution": [{"name": "signed_flow", "value": {"imb_level": 0.5}, "contribution": 0.5, "used": status != "STAND_DOWN", "note": "fixture"}],
        "availability": {"flow_update_allowed": status != "STAND_DOWN", "queue_update_allowed": status != "STAND_DOWN", "refine_update_allowed": status != "STAND_DOWN", "stand_down_reasons": ["fixture_gap"] if status == "STAND_DOWN" else []},
        "provenance": {"feature_schema": "ng_rt_feature_state.v1", "anchor_schema": "ng_g15_anchor.v1", "blind_artifact_mutated": False, "same_contract_for_historical_and_live": True, "threshold_status": "SHADOW"},
    }
    output["output_fingerprint"] = _output_fingerprint(output)
    return output


def selftest() -> int:
    outputs = [
        _fixture_output(1, {"up": 0.65, "flat": 0.15, "down": 0.20}),
        _fixture_output(2, {"up": 0.66, "flat": 0.14, "down": 0.20}),
        _fixture_output(3, {"up": 0.20, "flat": 0.15, "down": 0.65}),
    ]
    stream = {"schema": G15_STREAM_SCHEMA, "market": "NG", "group": 15, "authority": "REFINE_POSTERIOR_STREAM_ONLY", "execution_authority": False, "anchor_fingerprint": "anchor", "n_outputs": len(outputs), "outputs": outputs}
    result = build_coach_stream(stream)
    assert [row["event_type"] for row in result["messages"]] == ["INITIAL_UPDATE", "DIRECTION_CHANGE"]
    assert result["delivery_authority"] is False
    print("[ng_coach_voxa_adapter] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build material-change-only NG coach/VOXA messages")
    parser.add_argument("--posterior-stream", type=Path)
    parser.add_argument("--lag-attachments", type=Path)
    parser.add_argument("--previous-stream", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--posterior-l1-threshold", type=float, default=DEFAULT_CONFIG["posterior_l1_threshold"])
    parser.add_argument("--top-probability-threshold", type=float, default=DEFAULT_CONFIG["top_probability_threshold"])
    parser.add_argument("--invalidation-drop-threshold", type=float, default=DEFAULT_CONFIG["invalidation_drop_threshold"])
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.posterior_stream is None or args.out is None:
        parser.error("--posterior-stream and --out are required unless --selftest is used")
    posterior_stream = json.loads(args.posterior_stream.read_text(encoding="utf-8"))
    lag_attachments = None if args.lag_attachments is None else json.loads(args.lag_attachments.read_text(encoding="utf-8"))
    previous_stream = None if args.previous_stream is None else json.loads(args.previous_stream.read_text(encoding="utf-8"))
    result = build_coach_stream(
        posterior_stream, lag_attachments=lag_attachments, previous_stream=previous_stream,
        config={"posterior_l1_threshold": args.posterior_l1_threshold, "top_probability_threshold": args.top_probability_threshold, "invalidation_drop_threshold": args.invalidation_drop_threshold},
    )
    atomic_json(args.out, result)
    print(json.dumps({"status": "ok", "messages": result["n_messages"], "suppressed": result["n_suppressed"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
