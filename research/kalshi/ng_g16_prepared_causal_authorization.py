#!/usr/bin/env python3
"""Bind the exact prepared G16 replay gate to the pre-cutoff causal pipeline.

This is the final authorization seam before the outcome-blind G16 curve adapter.
It independently validates both upstream contracts and refuses to authorize a
causal posterior stream that is not linked to the exact 23-source prepared
NGK26 corpus, immutable blind prior, and pre-registered G15 lesson set.

No G16 outcomes are read. Random shuffling is forbidden. Blind artifacts remain
immutable, ``ng_brain.json`` cannot be updated, CME event contracts remain
SHADOW, tastytrade remains the brokerage contract, and options work remains
unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_g16_exact_causal_pipeline import (
    G16ExactCausalPipelineError,
    NEXT_STAGE as CAUSAL_NEXT_STAGE,
    SCHEMA as CAUSAL_SCHEMA,
    validate_pipeline_artifacts,
)
from ng_g16_prepared_replay_gate import (
    EXPECTED_SOURCE_COUNT,
    G16PreparedReplayGateError,
    SCHEMA as PREPARED_GATE_SCHEMA,
    STATUS_READY as PREPARED_READY,
    STATUS_STAND_DOWNS as PREPARED_STAND_DOWNS,
    validate_gate_artifact,
)

SCHEMA = "ng_g16_prepared_causal_authorization.v1"
AUTHORITY = "EXACT_G16_PREPARED_CORPUS_TO_PRE_CUTOFF_CAUSAL_REFINEMENT_ONLY"
STATUS_READY = "EXACT_G16_PREPARED_CAUSAL_AUTHORIZED"
STATUS_STAND_DOWNS = "EXACT_G16_PREPARED_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "OUTCOME_BLIND_G16_CURVE_ADAPTER"


class G16PreparedCausalAuthorizationError(ValueError):
    """Raised when the prepared-replay and causal-pipeline chains diverge."""


def _fp(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_upstream(
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
) -> Mapping[str, Any]:
    try:
        validate_gate_artifact(
            prepared_gate,
            prepared_index=prepared_index,
            manifest=manifest,
            replay=replay,
            blind_prior=blind_prior,
        )
    except G16PreparedReplayGateError as error:
        raise G16PreparedCausalAuthorizationError(
            f"prepared replay gate invalid: {error}"
        ) from error
    try:
        validate_pipeline_artifacts(
            causal_artifacts,
            replay=replay,
            blind_prior=blind_prior,
            blind_forecast=blind_forecast,
            blind_safe_state=blind_safe_state,
            registry_source=registry_source,
        )
    except G16ExactCausalPipelineError as error:
        raise G16PreparedCausalAuthorizationError(
            f"exact causal pipeline invalid: {error}"
        ) from error

    completion = causal_artifacts.get("completion") or {}
    if prepared_gate.get("schema") != PREPARED_GATE_SCHEMA:
        raise G16PreparedCausalAuthorizationError("prepared replay gate schema mismatch")
    if prepared_gate.get("status") not in {PREPARED_READY, PREPARED_STAND_DOWNS}:
        raise G16PreparedCausalAuthorizationError("prepared replay gate is not ready")
    if completion.get("schema") != CAUSAL_SCHEMA:
        raise G16PreparedCausalAuthorizationError("causal completion schema mismatch")
    if completion.get("next_permitted_stage") != CAUSAL_NEXT_STAGE:
        raise G16PreparedCausalAuthorizationError("causal pipeline has an unexpected next stage")
    return completion


def _cross_chain_checks(
    prepared_gate: Mapping[str, Any],
    replay: Mapping[str, Any],
    causal_completion: Mapping[str, Any],
) -> None:
    links = {
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
    }
    for field, value in links.items():
        if prepared_gate.get(field) != value:
            raise G16PreparedCausalAuthorizationError(
                f"prepared replay gate {field} differs from exact replay"
            )
        if causal_completion.get(field) != value:
            raise G16PreparedCausalAuthorizationError(
                f"causal completion {field} differs from exact replay"
            )
    if int(prepared_gate.get("prepared_source_count") or 0) != EXPECTED_SOURCE_COUNT:
        raise G16PreparedCausalAuthorizationError("prepared replay gate source count is not 23")
    fingerprints = list(prepared_gate.get("prepared_source_fingerprints") or [])
    if len(fingerprints) != EXPECTED_SOURCE_COUNT or len(set(fingerprints)) != EXPECTED_SOURCE_COUNT:
        raise G16PreparedCausalAuthorizationError(
            "prepared replay source fingerprints must contain 23 unique entries"
        )
    if int(prepared_gate.get("n_feature_states") or 0) != int(
        causal_completion.get("n_states") or 0
    ):
        raise G16PreparedCausalAuthorizationError(
            "prepared replay feature-state count differs from causal pipeline"
        )
    if int(prepared_gate.get("completed_mbo_event_boundaries") or 0) != int(
        replay.get("completed_mbo_event_boundaries") or 0
    ):
        raise G16PreparedCausalAuthorizationError(
            "prepared replay boundary count differs from exact replay"
        )
    if not list(causal_completion.get("candidate_ids") or []):
        raise G16PreparedCausalAuthorizationError(
            "causal pipeline has no pre-registered G15 lesson candidates"
        )


def build_authorization(
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
) -> dict[str, Any]:
    """Validate the complete exact-prepared-replay to causal-posterior chain."""
    originals = copy.deepcopy(
        (
            prepared_gate,
            prepared_index,
            manifest,
            replay,
            blind_prior,
            causal_artifacts,
            blind_forecast,
            blind_safe_state,
            registry_source,
        )
    )
    causal_completion = _validate_upstream(
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
    _cross_chain_checks(prepared_gate, replay, causal_completion)

    prepared_stand_downs = sorted(
        {str(day) for day in prepared_gate.get("stand_down_days") or []}
    )
    posterior_stand_downs = sorted(
        {str(day) for day in causal_completion.get("stand_down_days") or []}
    )
    all_stand_downs = sorted(set(prepared_stand_downs) | set(posterior_stand_downs))
    status = STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY

    authorization = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": status,
        "authority": AUTHORITY,
        "prepared_replay_gate_fingerprint": prepared_gate.get("fingerprint"),
        "prepared_replay_status": prepared_gate.get("status"),
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "prepared_source_count": int(prepared_gate.get("prepared_source_count") or 0),
        "prepared_source_fingerprints": list(
            prepared_gate.get("prepared_source_fingerprints") or []
        ),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
        "causal_pipeline_fingerprint": causal_completion.get("fingerprint"),
        "plan_fingerprint": causal_completion.get("plan_fingerprint"),
        "authorization_stream_fingerprint": causal_completion.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": causal_completion.get(
            "posterior_stream_fingerprint"
        ),
        "blind_forecast_fingerprint": causal_completion.get(
            "blind_forecast_fingerprint"
        ),
        "blind_safe_state_fingerprint": causal_completion.get(
            "blind_safe_state_fingerprint"
        ),
        "lesson_registry_fingerprint": causal_completion.get(
            "lesson_registry_fingerprint"
        ),
        "lesson_adjudication_fingerprint": causal_completion.get(
            "lesson_adjudication_fingerprint"
        ),
        "candidate_ids": list(causal_completion.get("candidate_ids") or []),
        "n_feature_states": int(prepared_gate.get("n_feature_states") or 0),
        "n_posterior_outputs": int(causal_completion.get("n_outputs") or 0),
        "n_days": int(causal_completion.get("n_days") or 0),
        "prepared_replay_stand_down_days": prepared_stand_downs,
        "posterior_stand_down_days": posterior_stand_downs,
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
    authorization["fingerprint"] = _fp(authorization)
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
    current = (
        prepared_gate,
        prepared_index,
        manifest,
        replay,
        blind_prior,
        causal_artifacts,
        blind_forecast,
        blind_safe_state,
        registry_source,
    )
    if current != originals:
        raise G16PreparedCausalAuthorizationError("authorization mutated a source artifact")
    return authorization


def validate_authorization(
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
    causal_completion = _validate_upstream(
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
    _cross_chain_checks(prepared_gate, replay, causal_completion)

    candidate = copy.deepcopy(dict(authorization))
    observed = candidate.pop("fingerprint", None)
    if observed != _fp(candidate):
        raise G16PreparedCausalAuthorizationError("authorization fingerprint mismatch")
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16PreparedCausalAuthorizationError("authorization schema/authority mismatch")

    prepared_stand_downs = sorted(
        {str(day) for day in prepared_gate.get("stand_down_days") or []}
    )
    posterior_stand_downs = sorted(
        {str(day) for day in causal_completion.get("stand_down_days") or []}
    )
    all_stand_downs = sorted(set(prepared_stand_downs) | set(posterior_stand_downs))
    expected_status = STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY
    expected_links = {
        "status": expected_status,
        "prepared_replay_gate_fingerprint": prepared_gate.get("fingerprint"),
        "prepared_replay_status": prepared_gate.get("status"),
        "replay_fingerprint": replay.get("fingerprint"),
        "manifest_fingerprint": replay.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": replay.get("prepared_corpus_fingerprint"),
        "prepared_source_count": int(prepared_gate.get("prepared_source_count") or 0),
        "prepared_source_fingerprints": list(
            prepared_gate.get("prepared_source_fingerprints") or []
        ),
        "blind_prior_fingerprint": replay.get("blind_prior_fingerprint"),
        "causal_pipeline_fingerprint": causal_completion.get("fingerprint"),
        "plan_fingerprint": causal_completion.get("plan_fingerprint"),
        "authorization_stream_fingerprint": causal_completion.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": causal_completion.get(
            "posterior_stream_fingerprint"
        ),
        "blind_forecast_fingerprint": causal_completion.get(
            "blind_forecast_fingerprint"
        ),
        "blind_safe_state_fingerprint": causal_completion.get(
            "blind_safe_state_fingerprint"
        ),
        "lesson_registry_fingerprint": causal_completion.get(
            "lesson_registry_fingerprint"
        ),
        "lesson_adjudication_fingerprint": causal_completion.get(
            "lesson_adjudication_fingerprint"
        ),
        "candidate_ids": list(causal_completion.get("candidate_ids") or []),
        "n_feature_states": int(prepared_gate.get("n_feature_states") or 0),
        "n_posterior_outputs": int(causal_completion.get("n_outputs") or 0),
        "n_days": int(causal_completion.get("n_days") or 0),
        "prepared_replay_stand_down_days": prepared_stand_downs,
        "posterior_stand_down_days": posterior_stand_downs,
        "all_stand_down_days": all_stand_downs,
        "next_permitted_stage": NEXT_STAGE,
    }
    for field, value in expected_links.items():
        if candidate.get(field) != value:
            raise G16PreparedCausalAuthorizationError(
                f"authorization {field} differs from the validated authority chain"
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
            raise G16PreparedCausalAuthorizationError(
                f"authorization must keep {field}=false"
            )
    if candidate.get("one_signal_authority_preserved") is not True:
        raise G16PreparedCausalAuthorizationError(
            "authorization must preserve one signal authority"
        )
    if candidate.get("blind_forecast_immutable") is not True:
        raise G16PreparedCausalAuthorizationError(
            "authorization must keep the G16 blind forecast immutable"
        )
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedCausalAuthorizationError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedCausalAuthorizationError(
            "brokerage contract must remain tastytrade_not_ibkr"
        )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G16PreparedCausalAuthorizationError(f"expected JSON object: {path}")
    return value


def _pipeline_artifacts(directory: Path) -> dict[str, Any]:
    return {
        "plan": _load(directory / "g16_shadow_plan.json"),
        "authorization_stream": _load(directory / "g16_shadow_authorization_stream.json"),
        "posterior_stream": _load(directory / "g16_shadow_posterior_stream.json"),
        "completion": _load(directory / "g16_exact_causal_pipeline.json"),
    }


def _selftest() -> None:
    from ng_g16_exact_causal_pipeline import _retime_fixture, build_exact_causal_pipeline
    from ng_g16_historical_replay import (
        _fixture_catalog,
        _fixture_inventory,
        build_manifest,
        prepare_corpus,
    )
    from ng_g16_prepared_replay_gate import run_gate
    from ng_g16_shadow_gate import _fixture_blind_state, _fixture_forecast, _fixture_registry

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        inventory, definition = _fixture_inventory(root)
        manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        prepared = prepare_corpus(manifest, root / "prepared")
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        replay, prepared_gate = run_gate(prepared, manifest, prior)
        _retime_fixture(replay)
        prepared_gate["replay_fingerprint"] = replay["fingerprint"]
        prepared_gate.pop("fingerprint", None)
        prepared_gate["fingerprint"] = _fp(prepared_gate)
        forecast = _fixture_forecast()
        blind_state = _fixture_blind_state()
        registry = _fixture_registry()
        causal = build_exact_causal_pipeline(
            replay, prior, forecast, blind_state, registry
        )
        result = build_authorization(
            prepared_gate=prepared_gate,
            prepared_index=prepared,
            manifest=manifest,
            replay=replay,
            blind_prior=prior,
            causal_artifacts=causal,
            blind_forecast=forecast,
            blind_safe_state=blind_state,
            registry_source=registry,
        )
        assert result["status"] == STATUS_READY
        assert result["prepared_source_count"] == EXPECTED_SOURCE_COUNT
        assert result["n_feature_states"] == result["n_posterior_outputs"]
        assert result["actual_g16_outcomes_used"] is False
        assert result["execution_authority"] is False
        assert result["options_lane_started"] is False
    print("ng_g16_prepared_causal_authorization selftest passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-gate", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--blind-forecast", type=Path)
    parser.add_argument("--blind-safe-state", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--pipeline-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return
    required = (
        args.prepared_gate,
        args.prepared,
        args.manifest,
        args.replay,
        args.blind_prior,
        args.blind_forecast,
        args.blind_safe_state,
        args.registry,
        args.pipeline_dir,
        args.out,
    )
    if any(path is None for path in required):
        parser.error("all artifact paths are required")
    result = build_authorization(
        prepared_gate=_load(args.prepared_gate),
        prepared_index=_load(args.prepared),
        manifest=_load(args.manifest),
        replay=_load(args.replay),
        blind_prior=_load(args.blind_prior),
        causal_artifacts=_pipeline_artifacts(args.pipeline_dir),
        blind_forecast=_load(args.blind_forecast),
        blind_safe_state=_load(args.blind_safe_state),
        registry_source=_load(args.registry),
    )
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "fingerprint": result["fingerprint"]}, sort_keys=True))


if __name__ == "__main__":
    main()
