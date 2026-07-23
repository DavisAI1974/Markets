#!/usr/bin/env python3
"""Deterministic read-only Coach/VOXA adapter for NG SHADOW refinement.

The adapter converts validated G15 or G16 posterior outputs into concise coach
packets and VOXA-ready display/voice envelopes. It never reads actual outcomes,
changes a blind prior or forecast, mutates ``ng_brain.json``, issues a trade
instruction, or grants delivery/execution authority.

Product lag is explicit:
- HISTORICAL_REPLAY: lag is marked not applicable.
- LIVE: an observed wall-clock time and NG-specific maximum event lag are
  required. Stale packets become visible stand-downs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "ng_refine_coach_voxa_stream.v1"
PACKET_SCHEMA = "ng_refine_coach_packet.v1"
VOXA_SCHEMA = "voxa.coach_message.v1"
LAG_SCHEMA = "ng_product_lag_policy.v1"
AUTHORITY = "READ_ONLY_COACH_VOXA_ADAPTER"
PRODUCT = "NG"
DIRECTIONS = ("up", "flat", "down")
MODES = {"HISTORICAL_REPLAY", "LIVE"}
SOURCE_G15 = "G15_EXACT_HISTORICAL_REFINE"
SOURCE_G16 = "G16_EXACT_PRE_CUTOFF_SHADOW_REFINE"


class CoachVoxaAdapterError(ValueError):
    """Raised when an adapter input or output violates the read-only contract."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _finite(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CoachVoxaAdapterError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise CoachVoxaAdapterError(f"{label} must be finite")
    return number


def _normalize(value: Mapping[str, Any], *, label: str) -> dict[str, float]:
    result = {key: max(0.0, _finite(value.get(key), label=f"{label}.{key}")) for key in DIRECTIONS}
    total = sum(result.values())
    if total <= 0:
        raise CoachVoxaAdapterError(f"{label} must carry positive probability mass")
    return {key: result[key] / total for key in DIRECTIONS}


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(candidate):
        raise CoachVoxaAdapterError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _assert_outcome_blind(value: Any, *, path: str = "source") -> None:
    """Reject outcome-bearing payloads while allowing explicit false guard flags."""
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).lower()
            child = f"{path}.{raw_key}"
            if key in {
                "actual_g16_outcomes_used",
                "actual_outcomes_used",
                "outcome_scored",
                "g16_scoring_authorized",
                "actual_outcome_scoring_complete",
            }:
                if item is not False:
                    raise CoachVoxaAdapterError(f"{child} must remain false")
                continue
            if key in {
                "actual",
                "actuals",
                "outcome",
                "outcomes",
                "realized",
                "realized_path",
                "actual_net_usd",
                "pnl",
                "profit",
                "loss",
                "scorecard",
            }:
                raise CoachVoxaAdapterError(f"{child} is forbidden in an outcome-blind adapter")
            _assert_outcome_blind(item, path=child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_outcome_blind(item, path=f"{path}[{index}]")


def build_lag_policy(*, mode: str, max_event_lag_s: float | None = None) -> dict[str, Any]:
    normalized = str(mode or "").upper()
    if normalized not in MODES:
        raise CoachVoxaAdapterError(f"unsupported lag mode: {mode!r}")
    if normalized == "LIVE":
        if max_event_lag_s is None:
            raise CoachVoxaAdapterError("LIVE lag policy requires max_event_lag_s")
        maximum = _finite(max_event_lag_s, label="max_event_lag_s")
        if maximum <= 0:
            raise CoachVoxaAdapterError("max_event_lag_s must be positive")
    else:
        if max_event_lag_s is not None:
            raise CoachVoxaAdapterError("historical replay lag policy cannot claim a live threshold")
        maximum = None
    result = {
        "schema": LAG_SCHEMA,
        "product": PRODUCT,
        "mode": normalized,
        "max_event_lag_s": maximum,
        "source": "EXPLICIT_PRODUCT_POLICY",
        "paid_live_data_assumed": False,
        "execution_authority": False,
    }
    result["policy_fingerprint"] = _fp(result)
    return result


def validate_lag_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    value = _verify_fingerprint(policy, "policy_fingerprint", label="lag policy")
    if value.get("schema") != LAG_SCHEMA or value.get("product") != PRODUCT:
        raise CoachVoxaAdapterError("lag policy schema/product mismatch")
    mode = str(value.get("mode") or "")
    if mode not in MODES:
        raise CoachVoxaAdapterError("lag policy mode mismatch")
    if value.get("paid_live_data_assumed") is not False or value.get("execution_authority") is not False:
        raise CoachVoxaAdapterError("lag policy authority escalation")
    maximum = value.get("max_event_lag_s")
    if mode == "LIVE":
        if _finite(maximum, label="lag policy max_event_lag_s") <= 0:
            raise CoachVoxaAdapterError("live lag threshold must be positive")
    elif maximum is not None:
        raise CoachVoxaAdapterError("historical lag policy must not contain a live threshold")
    return value


def _validate_g15_source(pipeline: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    value = _verify_fingerprint(pipeline, "pipeline_fingerprint", label="G15 pipeline")
    if value.get("schema") != "ng_g15_pipeline.v1":
        raise CoachVoxaAdapterError("G15 pipeline schema mismatch")
    if value.get("authority") != "HISTORICAL_REFINE_PIPELINE_ONLY":
        raise CoachVoxaAdapterError("G15 pipeline authority mismatch")
    if value.get("execution_authority") is not False:
        raise CoachVoxaAdapterError("G15 pipeline execution authority must remain false")
    gates = dict(value.get("gates") or {})
    for field in (
        "actual_outcome_scoring_complete",
        "refined_curve_complete",
        "continuous_rt_renders_complete",
        "g16_authorized",
    ):
        if gates.get(field) is not False:
            raise CoachVoxaAdapterError(f"G15 pipeline gate {field} must remain false")
    stream = dict(value.get("refine_stream") or {})
    if stream.get("schema") != "ng_rt_refine_stream.v1":
        raise CoachVoxaAdapterError("G15 refine stream schema mismatch")
    if stream.get("authority") != "REFINE_POSTERIOR_STREAM_ONLY":
        raise CoachVoxaAdapterError("G15 refine stream authority mismatch")
    if stream.get("execution_authority") is not False:
        raise CoachVoxaAdapterError("G15 refine stream execution authority must remain false")
    outputs = [copy.deepcopy(dict(row)) for row in stream.get("outputs") or []]
    if int(stream.get("n_outputs") or 0) != len(outputs) or not outputs:
        raise CoachVoxaAdapterError("G15 refine stream output count mismatch")
    for output in outputs:
        candidate = copy.deepcopy(output)
        observed = candidate.pop("output_fingerprint", None)
        if observed != _fp(candidate):
            raise CoachVoxaAdapterError("G15 refine output fingerprint mismatch")
        if output.get("schema") != "ng_rt_refine_output.v1":
            raise CoachVoxaAdapterError("G15 refine output schema mismatch")
        if output.get("authority") != "REFINE_POSTERIOR_ONLY":
            raise CoachVoxaAdapterError("G15 refine output authority mismatch")
        if output.get("execution_authority") is not False:
            raise CoachVoxaAdapterError("G15 refine output execution authority must remain false")
        prior = _normalize(output.get("blind_prior") or {}, label="G15 blind prior")
        posterior = _normalize(output.get("posterior") or {}, label="G15 posterior")
        if output.get("status") == "STAND_DOWN" and posterior != prior:
            raise CoachVoxaAdapterError("G15 stand-down changed the blind prior")
    _assert_outcome_blind(value, path="G15 pipeline")
    return outputs, str(value["pipeline_fingerprint"])


def _validate_g16_source(
    completion: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    value = _verify_fingerprint(completion, "fingerprint", label="G16 exact causal completion")
    if value.get("schema") != "ng_g16_exact_causal_pipeline.v1":
        raise CoachVoxaAdapterError("G16 completion schema mismatch")
    if value.get("authority") != "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY":
        raise CoachVoxaAdapterError("G16 completion authority mismatch")
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
        if value.get(field) is not False:
            raise CoachVoxaAdapterError(f"G16 completion {field} must remain false")
    stream = _verify_fingerprint(posterior_stream, "stream_fingerprint", label="G16 posterior stream")
    if stream.get("schema") != "ng_g16_shadow_posterior_stream.v1":
        raise CoachVoxaAdapterError("G16 posterior stream schema mismatch")
    if stream.get("authority") != "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY":
        raise CoachVoxaAdapterError("G16 posterior stream authority mismatch")
    for field in ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
        if stream.get(field) is not False:
            raise CoachVoxaAdapterError(f"G16 posterior stream {field} must remain false")
    if value.get("posterior_stream_fingerprint") != stream.get("stream_fingerprint"):
        raise CoachVoxaAdapterError("G16 completion/posterior stream fingerprint mismatch")
    outputs = [copy.deepcopy(dict(row)) for row in stream.get("outputs") or []]
    if int(stream.get("n_outputs") or 0) != len(outputs) or int(value.get("n_outputs") or 0) != len(outputs):
        raise CoachVoxaAdapterError("G16 posterior output count mismatch")
    if not outputs:
        raise CoachVoxaAdapterError("G16 posterior stream is empty")
    for output in outputs:
        candidate = copy.deepcopy(output)
        observed = candidate.pop("output_fingerprint", None)
        if observed != _fp(candidate):
            raise CoachVoxaAdapterError("G16 posterior output fingerprint mismatch")
        if output.get("schema") != "ng_g16_shadow_posterior.v1":
            raise CoachVoxaAdapterError("G16 posterior output schema mismatch")
        if output.get("authority") != "G16_CAUSAL_SHADOW_POSTERIOR_ONLY":
            raise CoachVoxaAdapterError("G16 posterior output authority mismatch")
        for field in ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"):
            if output.get(field) is not False:
                raise CoachVoxaAdapterError(f"G16 posterior output {field} must remain false")
        prior = _normalize(output.get("blind_prior") or {}, label="G16 blind prior")
        posterior = _normalize(output.get("posterior") or {}, label="G16 posterior")
        if output.get("status") == "STAND_DOWN" and posterior != prior:
            raise CoachVoxaAdapterError("G16 stand-down changed the blind prior")
    _assert_outcome_blind(value, path="G16 completion")
    _assert_outcome_blind(stream, path="G16 posterior stream")
    return outputs, str(value["fingerprint"])


def _attribution_rows(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for raw in output.get("attribution") or []:
        row = dict(raw)
        if not row.get("used"):
            continue
        name = str(row.get("candidate_id") or row.get("name") or "")
        if not name:
            continue
        contribution = row.get("directional_contribution")
        if contribution is None:
            contribution = row.get("contribution")
        number = _finite(contribution or 0.0, label=f"attribution {name}")
        result.append(
            {
                "name": name,
                "directional_contribution": round(number, 8),
                "absolute_contribution": round(abs(number), 8),
            }
        )
    return sorted(result, key=lambda row: (-row["absolute_contribution"], row["name"]))


def _stand_down_reasons(output: Mapping[str, Any]) -> list[str]:
    reasons = list(output.get("stand_down_reasons") or [])
    availability = dict(output.get("availability") or {})
    reasons.extend(availability.get("stand_down_reasons") or [])
    return sorted({str(reason) for reason in reasons if str(reason)})


def _lag_state(
    *,
    policy: Mapping[str, Any],
    event_time: float,
    observed_at_s: float | None,
) -> dict[str, Any]:
    mode = str(policy["mode"])
    if mode == "HISTORICAL_REPLAY":
        if observed_at_s is not None:
            raise CoachVoxaAdapterError("historical replay must not supply observed_at_s")
        return {
            "mode": mode,
            "observed_event_lag_s": None,
            "max_event_lag_s": None,
            "status": "NOT_APPLICABLE_HISTORICAL_REPLAY",
            "stale": False,
        }
    if observed_at_s is None:
        raise CoachVoxaAdapterError("LIVE adapter requires observed_at_s")
    observed = _finite(observed_at_s, label="observed_at_s")
    if observed < event_time:
        raise CoachVoxaAdapterError("observed_at_s precedes the event time")
    lag = observed - event_time
    maximum = _finite(policy.get("max_event_lag_s"), label="max_event_lag_s")
    stale = lag > maximum
    return {
        "mode": mode,
        "observed_event_lag_s": round(lag, 6),
        "max_event_lag_s": maximum,
        "status": "STALE" if stale else "FRESH",
        "stale": stale,
    }


def _lead(posterior: Mapping[str, float]) -> tuple[str, float]:
    order = {name: index for index, name in enumerate(DIRECTIONS)}
    direction = sorted(DIRECTIONS, key=lambda name: (-posterior[name], order[name]))[0]
    return direction, posterior[direction]


def _confidence_label(value: float) -> str:
    if value >= 0.60:
        return "HIGH"
    if value >= 0.45:
        return "MODERATE"
    return "LOW"


def _utterance(
    *,
    day: str,
    coach_status: str,
    reasons: list[str],
    lag: Mapping[str, Any],
    lead: str,
    confidence: float,
    shift_points: float,
    top_evidence: str | None,
) -> str:
    if lag.get("stale"):
        seconds = float(lag["observed_event_lag_s"])
        return (
            f"NG data is stale by {seconds:.1f} seconds for {day}. "
            "Stand down; the blind forecast remains unchanged."
        )
    if coach_status == "STAND_DOWN":
        reason_text = ", ".join(reasons) if reasons else "refine update unavailable"
        return (
            f"NG shadow refine is standing down for {day}: {reason_text}. "
            "The blind forecast remains unchanged."
        )
    evidence = top_evidence or "available causal microstructure"
    sign = "+" if shift_points >= 0 else ""
    return (
        f"NG shadow refine for {day} leans {lead} at {confidence * 100:.0f} percent. "
        f"Directional shift versus blind is {sign}{shift_points:.1f} points. "
        f"Main evidence: {evidence}. Informational only."
    )


def _packet(
    output: Mapping[str, Any],
    *,
    group: int,
    source_kind: str,
    source_artifact_fingerprint: str,
    lag_policy: Mapping[str, Any],
    observed_at_s: float | None,
) -> dict[str, Any]:
    event_time = _finite(output.get("as_of_event_s"), label="as_of_event_s")
    prior = _normalize(output.get("blind_prior") or {}, label="blind prior")
    posterior = _normalize(output.get("posterior") or {}, label="posterior")
    reasons = _stand_down_reasons(output)
    lag = _lag_state(policy=lag_policy, event_time=event_time, observed_at_s=observed_at_s)
    source_status = str(output.get("status") or "UNKNOWN")
    if source_status not in {"UPDATED", "NO_CHANGE", "STAND_DOWN"}:
        raise CoachVoxaAdapterError(f"unsupported source status: {source_status!r}")
    coach_status = "STAND_DOWN" if source_status == "STAND_DOWN" or lag["stale"] else "INFORMATIONAL"
    if lag["stale"]:
        reasons = sorted(set(reasons + ["PRODUCT_EVENT_LAG_EXCEEDED"]))
    lead, confidence = _lead(posterior)
    blind_direction = prior["up"] - prior["down"]
    posterior_direction = posterior["up"] - posterior["down"]
    shift_points = 100.0 * (posterior_direction - blind_direction)
    attribution = _attribution_rows(output)
    top_evidence = attribution[0]["name"] if attribution else None
    day = str(output.get("session_day") or "")
    sequence = int(output.get("sequence") or 0)
    source_output_fingerprint = str(output.get("output_fingerprint") or "")
    utterance = _utterance(
        day=day,
        coach_status=coach_status,
        reasons=reasons,
        lag=lag,
        lead=lead,
        confidence=confidence,
        shift_points=shift_points,
        top_evidence=top_evidence,
    )
    packet = {
        "schema": PACKET_SCHEMA,
        "market": PRODUCT,
        "group": group,
        "session_day": day,
        "sequence": sequence,
        "horizon": output.get("horizon"),
        "as_of_event_s": event_time,
        "authority": AUTHORITY,
        "coach_status": coach_status,
        "source_status": source_status,
        "source_kind": source_kind,
        "source_artifact_fingerprint": source_artifact_fingerprint,
        "source_output_fingerprint": source_output_fingerprint,
        "blind_prior": prior,
        "posterior": posterior,
        "posterior_lead": lead,
        "posterior_confidence": round(confidence, 10),
        "confidence_label": _confidence_label(confidence),
        "directional_shift_points": round(shift_points, 6),
        "top_attribution": attribution[:3],
        "stand_down_reasons": reasons,
        "product_lag": lag,
        "voxa": {
            "schema": VOXA_SCHEMA,
            "channel": "VOICE_AND_DASHBOARD",
            "priority": "WARNING" if coach_status == "STAND_DOWN" else "INFORMATIONAL",
            "utterance": utterance,
            "display": {
                "market": PRODUCT,
                "group": group,
                "date": day,
                "status": coach_status,
                "lead": None if coach_status == "STAND_DOWN" else lead,
                "confidence": None if coach_status == "STAND_DOWN" else round(confidence, 10),
                "shift_points": None if coach_status == "STAND_DOWN" else round(shift_points, 6),
                "top_evidence": top_evidence,
                "stand_down_reasons": reasons,
                "lag_status": lag["status"],
            },
            "delivery_authority": False,
            "trade_instruction": None,
        },
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "may_issue_trade_instruction": False,
        "delivery_authority": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    packet["packet_fingerprint"] = _fp(packet)
    validate_packet(packet)
    return packet


def build_g15_stream(
    pipeline: Mapping[str, Any],
    lag_policy: Mapping[str, Any],
    *,
    observed_at_s: float | None = None,
) -> dict[str, Any]:
    outputs, source_fingerprint = _validate_g15_source(pipeline)
    return _build_stream(
        outputs,
        group=15,
        source_kind=SOURCE_G15,
        source_artifact_fingerprint=source_fingerprint,
        lag_policy=lag_policy,
        observed_at_s=observed_at_s,
    )


def build_g16_stream(
    completion: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    lag_policy: Mapping[str, Any],
    *,
    observed_at_s: float | None = None,
) -> dict[str, Any]:
    outputs, source_fingerprint = _validate_g16_source(completion, posterior_stream)
    return _build_stream(
        outputs,
        group=16,
        source_kind=SOURCE_G16,
        source_artifact_fingerprint=source_fingerprint,
        lag_policy=lag_policy,
        observed_at_s=observed_at_s,
    )


def _build_stream(
    outputs: Iterable[Mapping[str, Any]],
    *,
    group: int,
    source_kind: str,
    source_artifact_fingerprint: str,
    lag_policy: Mapping[str, Any],
    observed_at_s: float | None,
) -> dict[str, Any]:
    policy = validate_lag_policy(lag_policy)
    source_rows = [copy.deepcopy(dict(row)) for row in outputs]
    originals = copy.deepcopy(source_rows)
    rows = copy.deepcopy(source_rows)
    packets = [
        _packet(
            output,
            group=group,
            source_kind=source_kind,
            source_artifact_fingerprint=source_artifact_fingerprint,
            lag_policy=policy,
            observed_at_s=observed_at_s,
        )
        for output in rows
    ]
    packets.sort(key=lambda row: (row["session_day"], row["as_of_event_s"], row["sequence"]))
    seen = set()
    last = None
    for packet in packets:
        key = (packet["session_day"], packet["as_of_event_s"], packet["sequence"])
        if last is not None and key <= last:
            raise CoachVoxaAdapterError("coach packets are not strictly chronological")
        if packet["source_output_fingerprint"] in seen:
            raise CoachVoxaAdapterError("duplicate source output fingerprint")
        last = key
        seen.add(packet["source_output_fingerprint"])
    result = {
        "schema": SCHEMA,
        "market": PRODUCT,
        "group": group,
        "authority": AUTHORITY,
        "source_kind": source_kind,
        "source_artifact_fingerprint": source_artifact_fingerprint,
        "lag_policy": copy.deepcopy(policy),
        "n_packets": len(packets),
        "n_informational": sum(row["coach_status"] == "INFORMATIONAL" for row in packets),
        "n_stand_down": sum(row["coach_status"] == "STAND_DOWN" for row in packets),
        "packets": packets,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "may_issue_trade_instruction": False,
        "delivery_authority": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "READ_ONLY_DASHBOARD_OR_VOXA_PRESENTATION",
    }
    result["stream_fingerprint"] = _fp(result)
    if rows != originals:
        raise CoachVoxaAdapterError("adapter mutated source outputs")
    validate_stream(result)
    return result


def validate_packet(packet: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(packet, "packet_fingerprint", label="coach packet")
    if value.get("schema") != PACKET_SCHEMA or value.get("authority") != AUTHORITY:
        raise CoachVoxaAdapterError("coach packet schema/authority mismatch")
    if value.get("market") != PRODUCT or value.get("group") not in {15, 16}:
        raise CoachVoxaAdapterError("coach packet market/group mismatch")
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "may_issue_trade_instruction",
        "delivery_authority",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CoachVoxaAdapterError(f"coach packet {field} must remain false")
    for field in ("one_signal_authority_preserved", "blind_forecast_immutable"):
        if value.get(field) is not True:
            raise CoachVoxaAdapterError(f"coach packet {field} must remain true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CoachVoxaAdapterError("coach packet must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CoachVoxaAdapterError("coach packet must keep tastytrade brokerage")
    prior = _normalize(value.get("blind_prior") or {}, label="coach packet blind prior")
    posterior = _normalize(value.get("posterior") or {}, label="coach packet posterior")
    if value.get("source_status") == "STAND_DOWN" and posterior != prior:
        raise CoachVoxaAdapterError("source stand-down changed the blind prior")
    lag = dict(value.get("product_lag") or {})
    if value.get("coach_status") == "STAND_DOWN":
        display = dict((value.get("voxa") or {}).get("display") or {})
        if display.get("lead") is not None or display.get("confidence") is not None:
            raise CoachVoxaAdapterError("stand-down VOXA display must not issue a directional call")
    voxa = dict(value.get("voxa") or {})
    if voxa.get("schema") != VOXA_SCHEMA:
        raise CoachVoxaAdapterError("VOXA envelope schema mismatch")
    if voxa.get("delivery_authority") is not False or voxa.get("trade_instruction") is not None:
        raise CoachVoxaAdapterError("VOXA envelope cannot deliver or instruct trades")
    if lag.get("stale") and "PRODUCT_EVENT_LAG_EXCEEDED" not in set(value.get("stand_down_reasons") or []):
        raise CoachVoxaAdapterError("stale packet hides product-lag stand-down")
    _assert_outcome_blind(value, path="coach packet")


def validate_stream(stream: Mapping[str, Any]) -> None:
    value = _verify_fingerprint(stream, "stream_fingerprint", label="coach stream")
    if value.get("schema") != SCHEMA or value.get("authority") != AUTHORITY:
        raise CoachVoxaAdapterError("coach stream schema/authority mismatch")
    if value.get("market") != PRODUCT or value.get("group") not in {15, 16}:
        raise CoachVoxaAdapterError("coach stream market/group mismatch")
    validate_lag_policy(value.get("lag_policy") or {})
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "may_issue_trade_instruction",
        "delivery_authority",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CoachVoxaAdapterError(f"coach stream {field} must remain false")
    for field in ("one_signal_authority_preserved", "blind_forecast_immutable"):
        if value.get(field) is not True:
            raise CoachVoxaAdapterError(f"coach stream {field} must remain true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CoachVoxaAdapterError("coach stream must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CoachVoxaAdapterError("coach stream must keep tastytrade brokerage")
    if value.get("next_permitted_stage") != "READ_ONLY_DASHBOARD_OR_VOXA_PRESENTATION":
        raise CoachVoxaAdapterError("coach stream next-stage mismatch")
    packets = [dict(row) for row in value.get("packets") or []]
    if int(value.get("n_packets") or 0) != len(packets) or not packets:
        raise CoachVoxaAdapterError("coach stream packet count mismatch")
    if int(value.get("n_informational") or 0) != sum(row.get("coach_status") == "INFORMATIONAL" for row in packets):
        raise CoachVoxaAdapterError("coach stream informational count mismatch")
    if int(value.get("n_stand_down") or 0) != sum(row.get("coach_status") == "STAND_DOWN" for row in packets):
        raise CoachVoxaAdapterError("coach stream stand-down count mismatch")
    previous = None
    seen = set()
    for packet in packets:
        validate_packet(packet)
        if packet.get("group") != value.get("group"):
            raise CoachVoxaAdapterError("packet/stream group mismatch")
        if packet.get("source_kind") != value.get("source_kind"):
            raise CoachVoxaAdapterError("packet/stream source-kind mismatch")
        if packet.get("source_artifact_fingerprint") != value.get("source_artifact_fingerprint"):
            raise CoachVoxaAdapterError("packet/stream source fingerprint mismatch")
        key = (str(packet.get("session_day") or ""), float(packet.get("as_of_event_s")), int(packet.get("sequence") or 0))
        if previous is not None and key <= previous:
            raise CoachVoxaAdapterError("coach stream is not chronological")
        source_fp = packet.get("source_output_fingerprint")
        if not source_fp or source_fp in seen:
            raise CoachVoxaAdapterError("coach stream has duplicate/missing source output fingerprints")
        previous = key
        seen.add(source_fp)
    _assert_outcome_blind(value, path="coach stream")


def selftest() -> int:
    policy = build_lag_policy(mode="HISTORICAL_REPLAY")
    output = {
        "schema": "ng_rt_refine_output.v1",
        "source_mode": "historical",
        "session_day": "2026-03-15",
        "sequence": 1,
        "horizon": "close",
        "as_of_event_s": 1773500000.0,
        "authority": "REFINE_POSTERIOR_ONLY",
        "execution_authority": False,
        "blind_prior": {"up": 0.4, "flat": 0.2, "down": 0.4},
        "blind_prior_fingerprint": "blind",
        "feature_fingerprint": "feature",
        "anchor_fingerprint": "anchor",
        "posterior": {"up": 0.55, "flat": 0.2, "down": 0.25},
        "status": "UPDATED",
        "scores": {"directional_log_weight": 0.3, "flat_log_weight": 0.0, "update_strength": 0.5},
        "attribution": [
            {"name": "signed_flow", "value": 0.4, "contribution": 0.3, "used": True, "note": "test"}
        ],
        "availability": {
            "flow_update_allowed": True,
            "queue_update_allowed": True,
            "refine_update_allowed": True,
            "stand_down_reasons": [],
        },
        "provenance": {"blind_artifact_mutated": False},
    }
    output["output_fingerprint"] = _fp(output)
    pipeline = {
        "schema": "ng_g15_pipeline.v1",
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_PIPELINE_ONLY",
        "execution_authority": False,
        "refine_stream": {
            "schema": "ng_rt_refine_stream.v1",
            "market": "NG",
            "group": 15,
            "authority": "REFINE_POSTERIOR_STREAM_ONLY",
            "execution_authority": False,
            "n_outputs": 1,
            "outputs": [output],
        },
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
    }
    pipeline["pipeline_fingerprint"] = _fp(pipeline)
    result = build_g15_stream(pipeline, policy)
    assert result["n_packets"] == 1 and result["packets"][0]["posterior_lead"] == "up"
    print("[ng_refine_coach_voxa_adapter] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build read-only Coach/VOXA packets from NG SHADOW refinement")
    parser.add_argument("--selftest", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    policy_parser = subparsers.add_parser("policy")
    policy_parser.add_argument("--mode", choices=sorted(MODES), required=True)
    policy_parser.add_argument("--max-event-lag-s", type=float)
    policy_parser.add_argument("--out", type=Path, required=True)

    for command in ("g15", "g16"):
        child = subparsers.add_parser(command)
        child.add_argument("--lag-policy", type=Path, required=True)
        child.add_argument("--observed-at-s", type=float)
        child.add_argument("--out", type=Path, required=True)
        if command == "g15":
            child.add_argument("--pipeline", type=Path, required=True)
        else:
            child.add_argument("--completion", type=Path, required=True)
            child.add_argument("--posterior-stream", type=Path, required=True)

    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.command == "policy":
        result = build_lag_policy(mode=args.mode, max_event_lag_s=args.max_event_lag_s)
        _atomic(args.out, result)
        print(f"[ng_refine_coach_voxa_adapter] wrote {result['mode']} lag policy -> {args.out}")
        return 0
    if args.command == "g15":
        result = build_g15_stream(
            _load(args.pipeline),
            _load(args.lag_policy),
            observed_at_s=args.observed_at_s,
        )
    elif args.command == "g16":
        result = build_g16_stream(
            _load(args.completion),
            _load(args.posterior_stream),
            _load(args.lag_policy),
            observed_at_s=args.observed_at_s,
        )
    else:
        parser.error("g15 or g16 command required")
    _atomic(args.out, result)
    print(
        f"[ng_refine_coach_voxa_adapter] group={result['group']} "
        f"packets={result['n_packets']} stand_downs={result['n_stand_down']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
