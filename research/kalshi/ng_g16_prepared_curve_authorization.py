#!/usr/bin/env python3
"""Bind exact prepared G16 causal authorization to the outcome-blind curve.

This gate closes the final pre-scoring seam. A renderable G16 refined curve is
accepted only when it can be reproduced byte-for-byte from the immutable blind
forecast, the exact pre-cutoff plan, and the authorized posterior stream already
bound to the 23-source prepared NGK26 replay.

No G16 outcomes are read. Random shuffling is forbidden. Blind artifacts and
``ng_brain.json`` remain immutable, CME event contracts remain SHADOW,
tastytrade remains the brokerage contract, and the options lane remains
unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g16_curve_adapter import (
    AUTHORITY as CURVE_AUTHORITY,
    SCHEMA as CURVE_SCHEMA,
    CurveConfig,
    G16CurveError,
    build_refined_forecast,
    validate_refined_forecast,
)
from ng_g16_prepared_causal_authorization import (
    G16PreparedCausalAuthorizationError,
    NEXT_STAGE as CAUSAL_NEXT_STAGE,
    SCHEMA as CAUSAL_AUTH_SCHEMA,
    STATUS_READY as CAUSAL_READY,
    STATUS_STAND_DOWNS as CAUSAL_STAND_DOWNS,
    validate_authorization,
)

SCHEMA = "ng_g16_prepared_curve_authorization.v1"
AUTHORITY = "EXACT_G16_PREPARED_CAUSAL_TO_OUTCOME_BLIND_CURVE_ONLY"
STATUS_READY = "EXACT_G16_PREPARED_CURVE_AUTHORIZED"
STATUS_STAND_DOWNS = "EXACT_G16_PREPARED_CURVE_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "LOCK_G16_REFINED_CURVE_BEFORE_SCORING"


class G16PreparedCurveAuthorizationError(ValueError):
    """Raised when the exact causal authority and refined curve diverge."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_upstream_authorization(
    authorization: Mapping[str, Any],
    *,
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
) -> None:
    try:
        validate_authorization(
            authorization,
            prepared_gate=prepared_gate,
            prepared_index=prepared_index,
            manifest=manifest,
            replay=replay,
            blind_prior=blind_prior,
            causal_artifacts=causal_artifacts,
            blind_forecast=blind_forecast,
            blind_safe_state=blind_safe_state,
            registry_source=registry_source,
        )
    except G16PreparedCausalAuthorizationError as error:
        raise G16PreparedCurveAuthorizationError(
            f"prepared causal authorization invalid: {error}"
        ) from error
    if authorization.get("schema") != CAUSAL_AUTH_SCHEMA:
        raise G16PreparedCurveAuthorizationError("prepared causal authorization schema mismatch")
    if authorization.get("status") not in {CAUSAL_READY, CAUSAL_STAND_DOWNS}:
        raise G16PreparedCurveAuthorizationError("prepared causal authorization is not ready")
    if authorization.get("next_permitted_stage") != CAUSAL_NEXT_STAGE:
        raise G16PreparedCurveAuthorizationError(
            "prepared causal authorization does not permit the curve adapter"
        )


def _curve_config(refined_curve: Mapping[str, Any]) -> CurveConfig:
    raw = dict(refined_curve.get("transform_config") or {})
    try:
        config = CurveConfig(**raw)
        config.validate()
    except (TypeError, G16CurveError) as error:
        raise G16PreparedCurveAuthorizationError(
            f"refined curve transform config invalid: {error}"
        ) from error
    return config


def _reproduce_curve(
    *,
    blind_forecast: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
) -> None:
    try:
        validate_refined_forecast(refined_curve, blind_forecast=blind_forecast)
        expected = build_refined_forecast(
            blind_forecast,
            shadow_plan,
            posterior_stream,
            blind_file_bytes=blind_file_bytes,
            config=_curve_config(refined_curve),
        )
    except G16CurveError as error:
        raise G16PreparedCurveAuthorizationError(f"refined curve invalid: {error}") from error
    if dict(refined_curve) != expected:
        raise G16PreparedCurveAuthorizationError(
            "refined curve is not the deterministic outcome-blind adapter output"
        )


def _cross_chain_checks(
    authorization: Mapping[str, Any],
    *,
    blind_forecast: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
) -> tuple[list[str], list[str], int]:
    if refined_curve.get("schema") != CURVE_SCHEMA or refined_curve.get("authority") != CURVE_AUTHORITY:
        raise G16PreparedCurveAuthorizationError("refined curve schema/authority mismatch")
    links = {
        "shadow_plan_fingerprint": authorization.get("plan_fingerprint"),
        "posterior_stream_fingerprint": authorization.get("posterior_stream_fingerprint"),
        "authorization_stream_fingerprint": authorization.get(
            "authorization_stream_fingerprint"
        ),
    }
    for field, expected in links.items():
        if refined_curve.get(field) != expected:
            raise G16PreparedCurveAuthorizationError(
                f"refined curve {field} differs from prepared causal authorization"
            )
    if shadow_plan.get("plan_fingerprint") != authorization.get("plan_fingerprint"):
        raise G16PreparedCurveAuthorizationError("shadow plan differs from authorization")
    if posterior_stream.get("stream_fingerprint") != authorization.get(
        "posterior_stream_fingerprint"
    ):
        raise G16PreparedCurveAuthorizationError("posterior stream differs from authorization")
    if posterior_stream.get("authorization_stream_fingerprint") != authorization.get(
        "authorization_stream_fingerprint"
    ):
        raise G16PreparedCurveAuthorizationError(
            "posterior authorization stream differs from prepared causal authorization"
        )
    if authorization.get("blind_forecast_fingerprint") != _fp(dict(blind_forecast)):
        raise G16PreparedCurveAuthorizationError(
            "prepared causal authorization differs from the supplied blind forecast"
        )
    blind_sha = _sha256(blind_file_bytes)
    if refined_curve.get("blind_forecast_sha256") != blind_sha:
        raise G16PreparedCurveAuthorizationError("refined curve blind-file SHA-256 mismatch")

    authorized_candidates = set(str(value) for value in authorization.get("candidate_ids") or [])
    output_fingerprints = {
        str(output.get("output_fingerprint"))
        for output in posterior_stream.get("outputs") or []
    }
    used_candidates: set[str] = set()
    curve_stand_down_days: list[str] = []
    total_used = 0
    for day in refined_curve.get("days") or []:
        audit = dict(day.get("refinement_audit") or {})
        if audit.get("plan_fingerprint") != authorization.get("plan_fingerprint"):
            raise G16PreparedCurveAuthorizationError(
                f"{day.get('date')}: curve audit plan fingerprint mismatch"
            )
        if audit.get("posterior_stream_fingerprint") != authorization.get(
            "posterior_stream_fingerprint"
        ):
            raise G16PreparedCurveAuthorizationError(
                f"{day.get('date')}: curve audit posterior fingerprint mismatch"
            )
        candidates = {str(value) for value in audit.get("authorized_candidate_ids_used") or []}
        if not candidates.issubset(authorized_candidates):
            raise G16PreparedCurveAuthorizationError(
                f"{day.get('date')}: curve used a candidate not pre-registered by G15"
            )
        used_candidates.update(candidates)
        source_outputs = [str(value) for value in audit.get("source_output_fingerprints") or []]
        if any(value not in output_fingerprints for value in source_outputs):
            raise G16PreparedCurveAuthorizationError(
                f"{day.get('date')}: curve audit references an unknown posterior output"
            )
        outputs_seen = int(audit.get("outputs_seen") or 0)
        outputs_used = int(audit.get("outputs_used") or 0)
        ignored = int(audit.get("outputs_ignored_or_stood_down") or 0)
        if outputs_seen != outputs_used + ignored:
            raise G16PreparedCurveAuthorizationError(
                f"{day.get('date')}: curve audit output counts do not reconcile"
            )
        if outputs_seen > 0 and outputs_used == 0:
            curve_stand_down_days.append(str(day.get("date")))
        total_used += outputs_used
    return sorted(used_candidates), sorted(set(curve_stand_down_days)), total_used


def build_authorization(
    *,
    prepared_causal_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
) -> dict[str, Any]:
    """Authorize the deterministic outcome-blind G16 refined curve."""
    originals = copy.deepcopy(
        (
            prepared_causal_authorization,
            prepared_gate,
            prepared_index,
            manifest,
            replay,
            blind_prior,
            causal_artifacts,
            blind_forecast,
            blind_safe_state,
            registry_source,
            shadow_plan,
            posterior_stream,
            refined_curve,
        )
    )
    _validate_upstream_authorization(
        prepared_causal_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
    )
    _reproduce_curve(
        blind_forecast=blind_forecast,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    used_candidates, curve_stand_downs, total_used = _cross_chain_checks(
        prepared_causal_authorization,
        blind_forecast=blind_forecast,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    upstream_stand_downs = sorted(
        {str(day) for day in prepared_causal_authorization.get("all_stand_down_days") or []}
    )
    all_stand_downs = sorted(set(upstream_stand_downs) | set(curve_stand_downs))
    status = STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": status,
        "authority": AUTHORITY,
        "prepared_causal_authorization_fingerprint": prepared_causal_authorization.get(
            "fingerprint"
        ),
        "prepared_replay_gate_fingerprint": prepared_causal_authorization.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": prepared_causal_authorization.get("replay_fingerprint"),
        "manifest_fingerprint": prepared_causal_authorization.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared_causal_authorization.get(
            "prepared_corpus_fingerprint"
        ),
        "blind_prior_fingerprint": prepared_causal_authorization.get(
            "blind_prior_fingerprint"
        ),
        "blind_forecast_fingerprint": prepared_causal_authorization.get(
            "blind_forecast_fingerprint"
        ),
        "blind_forecast_sha256": _sha256(blind_file_bytes),
        "plan_fingerprint": prepared_causal_authorization.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared_causal_authorization.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": prepared_causal_authorization.get(
            "posterior_stream_fingerprint"
        ),
        "refined_curve_fingerprint": refined_curve.get("artifact_fingerprint"),
        "transform_config": copy.deepcopy(dict(refined_curve.get("transform_config") or {})),
        "registered_candidate_ids": list(prepared_causal_authorization.get("candidate_ids") or []),
        "used_candidate_ids": used_candidates,
        "n_days": len(list(refined_curve.get("days") or [])),
        "n_posterior_outputs": int(prepared_causal_authorization.get("n_posterior_outputs") or 0),
        "n_curve_outputs_used": total_used,
        "upstream_stand_down_days": upstream_stand_downs,
        "curve_stand_down_days": curve_stand_downs,
        "all_stand_down_days": all_stand_downs,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": NEXT_STAGE,
    }
    result["fingerprint"] = _fp(result)
    validate_curve_authorization(
        result,
        prepared_causal_authorization=prepared_causal_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    current = (
        prepared_causal_authorization,
        prepared_gate,
        prepared_index,
        manifest,
        replay,
        blind_prior,
        causal_artifacts,
        blind_forecast,
        blind_safe_state,
        registry_source,
        shadow_plan,
        posterior_stream,
        refined_curve,
    )
    if current != originals:
        raise G16PreparedCurveAuthorizationError("curve authorization mutated a source artifact")
    return result


def validate_curve_authorization(
    authorization: Mapping[str, Any],
    *,
    prepared_causal_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
    blind_forecast: Mapping[str, Any],
    blind_safe_state: Mapping[str, Any],
    registry_source: Mapping[str, Any],
    shadow_plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    refined_curve: Mapping[str, Any],
    blind_file_bytes: bytes,
) -> None:
    _validate_upstream_authorization(
        prepared_causal_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=blind_forecast,
        blind_safe_state=blind_safe_state,
        registry_source=registry_source,
    )
    _reproduce_curve(
        blind_forecast=blind_forecast,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    used_candidates, curve_stand_downs, total_used = _cross_chain_checks(
        prepared_causal_authorization,
        blind_forecast=blind_forecast,
        shadow_plan=shadow_plan,
        posterior_stream=posterior_stream,
        refined_curve=refined_curve,
        blind_file_bytes=blind_file_bytes,
    )
    candidate = copy.deepcopy(dict(authorization))
    observed = candidate.pop("fingerprint", None)
    if observed != _fp(candidate):
        raise G16PreparedCurveAuthorizationError("curve authorization fingerprint mismatch")
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16PreparedCurveAuthorizationError("curve authorization schema/authority mismatch")
    upstream_stand_downs = sorted(
        {str(day) for day in prepared_causal_authorization.get("all_stand_down_days") or []}
    )
    all_stand_downs = sorted(set(upstream_stand_downs) | set(curve_stand_downs))
    expected_status = STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY
    expected = {
        "status": expected_status,
        "prepared_causal_authorization_fingerprint": prepared_causal_authorization.get(
            "fingerprint"
        ),
        "prepared_replay_gate_fingerprint": prepared_causal_authorization.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": prepared_causal_authorization.get("replay_fingerprint"),
        "manifest_fingerprint": prepared_causal_authorization.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared_causal_authorization.get(
            "prepared_corpus_fingerprint"
        ),
        "blind_prior_fingerprint": prepared_causal_authorization.get(
            "blind_prior_fingerprint"
        ),
        "blind_forecast_fingerprint": prepared_causal_authorization.get(
            "blind_forecast_fingerprint"
        ),
        "blind_forecast_sha256": _sha256(blind_file_bytes),
        "plan_fingerprint": prepared_causal_authorization.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared_causal_authorization.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": prepared_causal_authorization.get(
            "posterior_stream_fingerprint"
        ),
        "refined_curve_fingerprint": refined_curve.get("artifact_fingerprint"),
        "transform_config": dict(refined_curve.get("transform_config") or {}),
        "registered_candidate_ids": list(prepared_causal_authorization.get("candidate_ids") or []),
        "used_candidate_ids": used_candidates,
        "n_days": len(list(refined_curve.get("days") or [])),
        "n_posterior_outputs": int(prepared_causal_authorization.get("n_posterior_outputs") or 0),
        "n_curve_outputs_used": total_used,
        "upstream_stand_down_days": upstream_stand_downs,
        "curve_stand_down_days": curve_stand_downs,
        "all_stand_down_days": all_stand_downs,
        "next_permitted_stage": NEXT_STAGE,
    }
    for field, value in expected.items():
        if candidate.get(field) != value:
            raise G16PreparedCurveAuthorizationError(
                f"curve authorization {field} mismatch"
            )
    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in false_fields:
        if candidate.get(field) is not False:
            raise G16PreparedCurveAuthorizationError(
                f"curve authorization {field} must remain false"
            )
    for field in ("one_signal_authority_preserved", "blind_forecast_immutable"):
        if candidate.get(field) is not True:
            raise G16PreparedCurveAuthorizationError(
                f"curve authorization {field} must remain true"
            )
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedCurveAuthorizationError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedCurveAuthorizationError("brokerage contract must remain tastytrade")


def _load(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authorize the exact prepared, outcome-blind G16 refined curve"
    )
    parser.add_argument("--prepared-causal-authorization", type=Path, required=True)
    parser.add_argument("--prepared-gate", type=Path, required=True)
    parser.add_argument("--prepared-index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--blind-prior", type=Path, required=True)
    parser.add_argument("--causal-completion", type=Path, required=True)
    parser.add_argument("--shadow-plan", type=Path, required=True)
    parser.add_argument("--authorization-stream", type=Path, required=True)
    parser.add_argument("--posterior-stream", type=Path, required=True)
    parser.add_argument("--blind-forecast", type=Path, required=True)
    parser.add_argument("--blind-safe-state", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--refined-curve", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    blind_bytes = args.blind_forecast.read_bytes()
    causal_artifacts = {
        "completion": _load(args.causal_completion),
        "plan": _load(args.shadow_plan),
        "authorization_stream": _load(args.authorization_stream),
        "posterior_stream": _load(args.posterior_stream),
    }
    result = build_authorization(
        prepared_causal_authorization=_load(args.prepared_causal_authorization),
        prepared_gate=_load(args.prepared_gate),
        prepared_index=_load(args.prepared_index),
        manifest=_load(args.manifest),
        replay=_load(args.replay),
        blind_prior=_load(args.blind_prior),
        causal_artifacts=causal_artifacts,
        blind_forecast=json.loads(blind_bytes.decode("utf-8")),
        blind_safe_state=_load(args.blind_safe_state),
        registry_source=_load(args.registry),
        shadow_plan=causal_artifacts["plan"],
        posterior_stream=causal_artifacts["posterior_stream"],
        refined_curve=_load(args.refined_curve),
        blind_file_bytes=blind_bytes,
    )
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
