#!/usr/bin/env python3
"""Bind the existing NG coach/VOXA adapter to exact causal source authority.

``ng_coach_voxa_adapter`` remains the single presentation adapter. This module
is a fail-closed provenance gate around it:

- G15 messages must originate from the exact fingerprinted
  ``ng_g15_pipeline.v1`` and its embedded posterior stream.
- G16 messages must originate from the exact fingerprinted, pre-cutoff
  ``ng_g16_exact_causal_pipeline.v1`` and its linked posterior stream.

The gate is read-only. It cannot use outcomes, calculate a posterior, change a
blind artifact, update ``ng_brain.json``, deliver a VOXA message, or authorize
execution. CME event contracts remain SHADOW and the brokerage contract remains
tastytrade, not IBKR.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_coach_voxa_adapter as coach

SCHEMA = "ng_coach_voxa_source_gate.v1"
AUTHORITY = "EXACT_CAUSAL_POSTERIOR_TO_PRESENTATION_ONLY"
STATUS = "EXACT_SOURCE_AUTHORIZATION_BOUND"
G15_SCHEMA = "ng_g15_pipeline.v1"
G15_AUTHORITY = "HISTORICAL_REFINE_PIPELINE_ONLY"
G16_SCHEMA = "ng_g16_exact_causal_pipeline.v1"
G16_AUTHORITY = "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY"
NEXT_STAGE = "READ_ONLY_DASHBOARD_OR_VOXA_PRESENTATION"


class CoachVoxaSourceGateError(ValueError):
    """Raised when presentation would bypass exact causal provenance."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result.pop(field, None)
    return result


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    observed = result.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(result):
        raise CoachVoxaSourceGateError(f"{label}: {field} mismatch")
    result[field] = observed
    return result


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _require_false(value: Mapping[str, Any], fields: Sequence[str], *, label: str) -> None:
    for field in fields:
        if value.get(field) is not False:
            raise CoachVoxaSourceGateError(f"{label}: {field} must remain false")


def _reject_outcomes(value: Any, *, path: str = "source") -> None:
    """Reject outcome-bearing content while allowing explicit false guard flags."""
    false_guards = {
        "actual_g16_outcomes_used",
        "actual_outcomes_used",
        "outcome_scored",
        "g16_scoring_authorized",
        "actual_outcome_scoring_complete",
    }
    forbidden = {
        "actual",
        "actuals",
        "outcome",
        "outcomes",
        "realized",
        "realized_path",
        "actual_net_usd",
        "pnl",
        "scorecard",
    }
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).lower()
            child = f"{path}.{raw_key}"
            if key in false_guards:
                if item is not False:
                    raise CoachVoxaSourceGateError(f"{child} must remain false")
                continue
            if key in forbidden:
                raise CoachVoxaSourceGateError(f"{child} is forbidden before presentation")
            _reject_outcomes(item, path=child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_outcomes(item, path=f"{path}[{index}]")


def _clean_stream(stream: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        clean = coach.validate_posterior_stream(stream)
    except coach.CoachAdapterError as error:
        raise CoachVoxaSourceGateError(f"posterior stream invalid: {error}") from error
    source_fingerprint = str(clean.pop("_source_stream_fingerprint"))
    return clean, source_fingerprint


def _validate_g15_source(
    source: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    value = _verify_fingerprint(source, "pipeline_fingerprint", label="G15 pipeline")
    if value.get("schema") != G15_SCHEMA or value.get("authority") != G15_AUTHORITY:
        raise CoachVoxaSourceGateError("G15 pipeline schema/authority mismatch")
    if int(value.get("group") or 0) != 15 or value.get("market") != "NG":
        raise CoachVoxaSourceGateError("G15 pipeline market/group mismatch")
    _require_false(value, ("execution_authority",), label="G15 pipeline")
    gates = dict(value.get("gates") or {})
    _require_false(
        gates,
        (
            "actual_outcome_scoring_complete",
            "refined_curve_complete",
            "continuous_rt_renders_complete",
            "g16_authorized",
        ),
        label="G15 pipeline gates",
    )
    embedded = copy.deepcopy(dict(value.get("refine_stream") or {}))
    supplied, stream_fingerprint = _clean_stream(posterior_stream)
    if supplied.get("schema") != coach.G15_STREAM_SCHEMA or int(supplied.get("group") or 0) != 15:
        raise CoachVoxaSourceGateError("G15 source requires a G15 posterior stream")
    if embedded != dict(posterior_stream):
        raise CoachVoxaSourceGateError("G15 supplied posterior stream differs from the pipeline stream")
    _reject_outcomes(value, path="G15 pipeline")
    return value, supplied, stream_fingerprint


def _validate_g16_source(
    source: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    value = _verify_fingerprint(source, "fingerprint", label="G16 exact causal completion")
    if value.get("schema") != G16_SCHEMA or value.get("authority") != G16_AUTHORITY:
        raise CoachVoxaSourceGateError("G16 completion schema/authority mismatch")
    if int(value.get("group") or 0) != 16 or value.get("market") != "NG":
        raise CoachVoxaSourceGateError("G16 completion market/group mismatch")
    _require_false(
        value,
        (
            "execution_authority",
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "paid_live_data_assumed",
            "may_update_ng_brain",
            "may_change_g16_blind_prior",
            "may_change_g16_blind_forecast",
            "may_select_lessons_from_g16_outcomes",
        ),
        label="G16 completion",
    )
    supplied, stream_fingerprint = _clean_stream(posterior_stream)
    if supplied.get("schema") != coach.G16_STREAM_SCHEMA or int(supplied.get("group") or 0) != 16:
        raise CoachVoxaSourceGateError("G16 source requires a G16 posterior stream")
    if value.get("posterior_stream_fingerprint") != stream_fingerprint:
        raise CoachVoxaSourceGateError("G16 completion/posterior stream fingerprint mismatch")
    if value.get("plan_fingerprint") != supplied.get("plan_fingerprint"):
        raise CoachVoxaSourceGateError("G16 completion/posterior plan fingerprint mismatch")
    if value.get("authorization_stream_fingerprint") != supplied.get("authorization_stream_fingerprint"):
        raise CoachVoxaSourceGateError("G16 completion/posterior authorization fingerprint mismatch")
    if int(value.get("n_outputs") or 0) != int(supplied.get("n_outputs") or 0):
        raise CoachVoxaSourceGateError("G16 completion/posterior output count mismatch")
    _reject_outcomes(value, path="G16 completion")
    _reject_outcomes(supplied, path="G16 posterior stream")
    return value, supplied, stream_fingerprint


def build_source_gate(
    source_authorization: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one exact source authority to one presentation posterior stream."""
    originals = copy.deepcopy((source_authorization, posterior_stream))
    schema = str(source_authorization.get("schema") or "")
    if schema == G15_SCHEMA:
        source, clean_stream, stream_fingerprint = _validate_g15_source(
            source_authorization, posterior_stream
        )
        group = 15
        source_fingerprint = str(source["pipeline_fingerprint"])
    elif schema == G16_SCHEMA:
        source, clean_stream, stream_fingerprint = _validate_g16_source(
            source_authorization, posterior_stream
        )
        group = 16
        source_fingerprint = str(source["fingerprint"])
    else:
        raise CoachVoxaSourceGateError(f"unsupported source authorization schema: {schema!r}")
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": group,
        "status": STATUS,
        "authority": AUTHORITY,
        "source_authorization_schema": schema,
        "source_authorization_fingerprint": source_fingerprint,
        "posterior_stream_schema": clean_stream["schema"],
        "posterior_stream_fingerprint": stream_fingerprint,
        "n_outputs": int(clean_stream.get("n_outputs") or 0),
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "delivery_authority": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": NEXT_STAGE,
    }
    result["gate_fingerprint"] = _fp(result)
    validate_source_gate(result, posterior_stream=posterior_stream)
    if (source_authorization, posterior_stream) != originals:
        raise CoachVoxaSourceGateError("source gate mutated an input artifact")
    return result


def validate_source_gate(
    gate: Mapping[str, Any],
    *,
    posterior_stream: Mapping[str, Any],
) -> dict[str, Any]:
    value = _verify_fingerprint(gate, "gate_fingerprint", label="coach source gate")
    if value.get("schema") != SCHEMA or value.get("authority") != AUTHORITY:
        raise CoachVoxaSourceGateError("coach source gate schema/authority mismatch")
    if value.get("status") != STATUS or value.get("market") != "NG":
        raise CoachVoxaSourceGateError("coach source gate is not ready")
    _require_false(
        value,
        (
            "actual_outcomes_used",
            "paid_live_data_assumed",
            "random_shuffle_used",
            "may_change_blind_prior",
            "may_change_blind_forecast",
            "may_change_posterior",
            "may_update_ng_brain",
            "delivery_authority",
            "execution_authority",
            "options_lane_started",
        ),
        label="coach source gate",
    )
    for field in ("one_signal_authority_preserved", "blind_forecast_immutable"):
        if value.get(field) is not True:
            raise CoachVoxaSourceGateError(f"coach source gate: {field} must remain true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CoachVoxaSourceGateError("coach source gate must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CoachVoxaSourceGateError("coach source gate must keep tastytrade brokerage")
    if value.get("next_permitted_stage") != NEXT_STAGE:
        raise CoachVoxaSourceGateError("coach source gate next-stage mismatch")
    clean_stream, stream_fingerprint = _clean_stream(posterior_stream)
    expected_group = int(clean_stream.get("group") or 0)
    expected = {
        "group": expected_group,
        "posterior_stream_schema": clean_stream.get("schema"),
        "posterior_stream_fingerprint": stream_fingerprint,
        "n_outputs": int(clean_stream.get("n_outputs") or 0),
    }
    if any(value.get(field) != expected_value for field, expected_value in expected.items()):
        raise CoachVoxaSourceGateError("coach source gate differs from posterior stream")
    if value.get("source_authorization_schema") not in {G15_SCHEMA, G16_SCHEMA}:
        raise CoachVoxaSourceGateError("coach source gate source schema mismatch")
    if not value.get("source_authorization_fingerprint"):
        raise CoachVoxaSourceGateError("coach source gate lacks source authorization fingerprint")
    return value


def build_authorized_coach_stream(
    source_authorization: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    *,
    lag_attachments: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    config: Mapping[str, Any] | None = None,
    previous_stream: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the existing coach stream only after exact provenance is bound."""
    originals = copy.deepcopy(
        (source_authorization, posterior_stream, lag_attachments, config, previous_stream)
    )
    gate = build_source_gate(source_authorization, posterior_stream)
    try:
        result = coach.build_coach_stream(
            posterior_stream,
            lag_attachments=lag_attachments,
            config=config,
            previous_stream=previous_stream,
        )
    except coach.CoachAdapterError as error:
        raise CoachVoxaSourceGateError(f"coach adapter rejected authorized stream: {error}") from error
    result = copy.deepcopy(result)
    result.update(
        {
            "source_gate_schema": SCHEMA,
            "source_gate_fingerprint": gate["gate_fingerprint"],
            "source_authorization_status": STATUS,
            "source_authorization_schema": gate["source_authorization_schema"],
            "source_authorization_fingerprint": gate["source_authorization_fingerprint"],
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "blind_forecast_immutable": True,
            "may_change_blind_forecast": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": NEXT_STAGE,
        }
    )
    result["stream_fingerprint"] = coach._stream_payload_fingerprint(result)
    validate_authorized_coach_stream(result, gate=gate, posterior_stream=posterior_stream)
    current = (source_authorization, posterior_stream, lag_attachments, config, previous_stream)
    if current != originals:
        raise CoachVoxaSourceGateError("authorized coach build mutated an input artifact")
    return result


def validate_authorized_coach_stream(
    stream: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        value = coach.validate_coach_stream(stream)
    except coach.CoachAdapterError as error:
        raise CoachVoxaSourceGateError(f"coach stream invalid: {error}") from error
    gate_value = validate_source_gate(gate, posterior_stream=posterior_stream)
    expected = {
        "source_gate_schema": SCHEMA,
        "source_gate_fingerprint": gate_value["gate_fingerprint"],
        "source_authorization_status": STATUS,
        "source_authorization_schema": gate_value["source_authorization_schema"],
        "source_authorization_fingerprint": gate_value["source_authorization_fingerprint"],
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "blind_forecast_immutable": True,
        "may_change_blind_forecast": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": NEXT_STAGE,
    }
    if any(value.get(field) != expected_value for field, expected_value in expected.items()):
        raise CoachVoxaSourceGateError("authorized coach stream source/control mismatch")
    return value


def selftest() -> int:
    output = coach._fixture_output(1, {"up": 0.65, "flat": 0.15, "down": 0.20})
    stream = {
        "schema": coach.G15_STREAM_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "anchor",
        "n_outputs": 1,
        "outputs": [output],
    }
    pipeline = {
        "schema": G15_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": G15_AUTHORITY,
        "execution_authority": False,
        "refine_stream": copy.deepcopy(stream),
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
    }
    pipeline["pipeline_fingerprint"] = _fp(pipeline)
    result = build_authorized_coach_stream(pipeline, stream)
    assert result["source_authorization_status"] == STATUS
    assert result["delivery_authority"] is False
    print("[ng_coach_voxa_source_gate] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind exact NG causal provenance to Coach/VOXA presentation")
    parser.add_argument("--source-authorization", type=Path)
    parser.add_argument("--posterior-stream", type=Path)
    parser.add_argument("--lag-attachments", type=Path)
    parser.add_argument("--previous-stream", type=Path)
    parser.add_argument("--gate-out", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--posterior-l1-threshold", type=float, default=coach.DEFAULT_CONFIG["posterior_l1_threshold"])
    parser.add_argument("--top-probability-threshold", type=float, default=coach.DEFAULT_CONFIG["top_probability_threshold"])
    parser.add_argument("--invalidation-drop-threshold", type=float, default=coach.DEFAULT_CONFIG["invalidation_drop_threshold"])
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.source_authorization is None or args.posterior_stream is None or args.out is None:
        parser.error("--source-authorization, --posterior-stream, and --out are required")
    source = _load(args.source_authorization)
    posterior = _load(args.posterior_stream)
    lag = None if args.lag_attachments is None else _load(args.lag_attachments)
    previous = None if args.previous_stream is None else _load(args.previous_stream)
    gate = build_source_gate(source, posterior)
    result = build_authorized_coach_stream(
        source,
        posterior,
        lag_attachments=lag,
        previous_stream=previous,
        config={
            "posterior_l1_threshold": args.posterior_l1_threshold,
            "top_probability_threshold": args.top_probability_threshold,
            "invalidation_drop_threshold": args.invalidation_drop_threshold,
        },
    )
    if args.gate_out is not None:
        _atomic(args.gate_out, gate)
    _atomic(args.out, result)
    print(
        json.dumps(
            {
                "status": STATUS,
                "group": result["group"],
                "messages": result["n_messages"],
                "suppressed": result["n_suppressed"],
                "out": str(args.out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
