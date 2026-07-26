#!/usr/bin/env python3
"""Compile the stable historical plan through G15 attribution authorization v32.

V31 ends at the prepared normalized identity gate immediately before exact G15 replay.
V32 extends the durable, first-blocking-stage plan through exact replay completion,
outcome-blind refinement authorization, deterministic six-factor attribution, and the
recursive attribution authorization. Fixed-outcome publication and every G16 stage stay
disabled.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v26 as v26
import ng_g15_counterfactual_attribution as attribution_module
import ng_g15_counterfactual_attribution_gate as attribution_gate
import ng_g15_exact_refinement_gate as refinement_gate
import ng_g15_exact_replay_completion as replay_completion
import ng_historical_refinement_executor_v28 as executor
import ng_historical_refinement_readiness_v32 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v27"
STATUS = "G15_ATTRIBUTION_AUTHORIZED_EXECUTOR_PLAN_COMPILED"
_AUTH_INDEX = [spec.key for spec in readiness.STAGES].index(
    "g15_counterfactual_attribution_authorization"
)
CONFIGURED_STAGES = tuple(spec.key for spec in readiness.STAGES[: _AUTH_INDEX + 1])


class CorpusExecutorPlanCompilerV27Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV27Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV27Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v26._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV27Error(str(error)) from error


def _validate_g15_chain(
    *,
    bridge: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    blind_forecast_bytes: bytes | None,
    completion: Mapping[str, Any],
    pipeline: Mapping[str, Any],
    refinement_authorization: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    attribution_authorization: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            bridge,
            prepared_index,
            replay,
            anchor,
            blind_prior,
            completion,
            pipeline,
            refinement_authorization,
            refine_stream,
            attribution,
            attribution_authorization,
        )
    )
    try:
        replay_completion.validate_completion(
            dict(completion),
            bridge=dict(bridge),
            prepared_index=dict(prepared_index),
            replay=dict(replay),
            anchor=dict(anchor),
            blind_prior=dict(blind_prior),
        )
        refinement_gate.validate_authorization(
            dict(refinement_authorization),
            completion=dict(completion),
            pipeline=dict(pipeline),
            blind_forecast_bytes=blind_forecast_bytes,
        )
        attribution_module.validate_report(
            dict(attribution),
            replay=dict(replay),
            anchor=dict(anchor),
            refine_stream=dict(refine_stream),
        )
        attribution_gate.validate_authorization(
            dict(attribution_authorization),
            completion=dict(completion),
            pipeline=dict(pipeline),
            refinement_authorization=dict(refinement_authorization),
            attribution=dict(attribution),
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV27Error(f"G15 authorization chain is invalid: {error}") from error

    pipeline_value = dict(pipeline)
    if pipeline_value.get("replay") != dict(replay):
        raise CorpusExecutorPlanCompilerV27Error("pipeline embeds a different exact replay")
    if pipeline_value.get("anchor") != dict(anchor):
        raise CorpusExecutorPlanCompilerV27Error("pipeline embeds a different Friday anchor")
    if pipeline_value.get("refine_stream") != dict(refine_stream):
        raise CorpusExecutorPlanCompilerV27Error("pipeline embeds a different refine stream")

    authorization = copy.deepcopy(dict(attribution_authorization))
    required = {
        "all_six_factors_quantified": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": (
            "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY"
        ),
    }
    for field, expected in required.items():
        if authorization.get(field) != expected:
            raise CorpusExecutorPlanCompilerV27Error(
                f"G15 attribution authorization field mismatch: {field}"
            )
    if tuple(authorization.get("factors") or ()) != tuple(attribution_module.FACTORS):
        raise CorpusExecutorPlanCompilerV27Error("G15 authorization lost the canonical six factors")
    if int(authorization.get("n_days") or 0) != 12:
        raise CorpusExecutorPlanCompilerV27Error("G15 authorization must cover 12 canonical sessions")
    if int(authorization.get("n_states") or 0) <= 0:
        raise CorpusExecutorPlanCompilerV27Error("G15 authorization contains no causal states")
    if blind_forecast_bytes is not None:
        expected_hash = _sha256_bytes(blind_forecast_bytes)
        if refinement_authorization.get("blind_forecast_sha256") != expected_hash:
            raise CorpusExecutorPlanCompilerV27Error(
                "exact refinement authorization references a different blind forecast"
            )
    if (
        bridge,
        prepared_index,
        replay,
        anchor,
        blind_prior,
        completion,
        pipeline,
        refinement_authorization,
        refine_stream,
        attribution,
        attribution_authorization,
    ) != originals:
        raise CorpusExecutorPlanCompilerV27Error("G15 chain validation mutated source artifacts")

    return {
        "completion": copy.deepcopy(dict(completion)),
        "pipeline": copy.deepcopy(dict(pipeline)),
        "refinement_authorization": copy.deepcopy(dict(refinement_authorization)),
        "attribution": copy.deepcopy(dict(attribution)),
        "attribution_authorization": authorization,
        "completion_fingerprint": completion.get("completion_fingerprint"),
        "pipeline_fingerprint": pipeline.get("pipeline_fingerprint"),
        "refinement_authorization_fingerprint": refinement_authorization.get(
            "authorization_fingerprint"
        ),
        "attribution_fingerprint": attribution.get("fingerprint"),
        "attribution_authorization_fingerprint": authorization.get(
            "authorization_fingerprint"
        ),
        "replay_fingerprint": authorization.get("replay_fingerprint"),
        "anchor_fingerprint": authorization.get("anchor_fingerprint"),
        "refine_stream_fingerprint": authorization.get("refine_stream_fingerprint"),
        "factor_summary_fingerprint": authorization.get("factor_summary_fingerprint"),
        "per_day_fingerprint": authorization.get("per_day_fingerprint"),
        "rows_fingerprint": authorization.get("rows_fingerprint"),
        "lesson_proposals_fingerprint": authorization.get(
            "lesson_proposals_fingerprint"
        ),
        "n_states": authorization.get("n_states"),
        "n_days": authorization.get("n_days"),
        "factors": list(authorization.get("factors") or []),
    }


def _commands(
    *,
    artifact_dir: Path,
    resolution_spec_path: Path,
    expected_day_receipt_path: Path,
    finalization_receipt_path: Path,
    resolution_receipt_path: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    materialization_provenance_path: Path,
    source_identity_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
    g15_bridge_path: Path,
    prepared_index_path: Path,
    prepared_identity_path: Path,
    g15_replay_path: Path,
    g15_anchor_path: Path,
    g15_blind_prior_path: Path,
    g15_blind_forecast_path: Path,
    g15_pipeline_path: Path,
    g15_refine_stream_path: Path,
    g15_completion_path: Path,
    g15_refinement_authorization_path: Path,
    g15_attribution_path: Path,
    g15_attribution_authorization_path: Path,
) -> dict[str, list[str]]:
    commands = v26._commands(
        artifact_dir=artifact_dir,
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        finalization_receipt_path=finalization_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        materialization_provenance_path=materialization_provenance_path,
        source_identity_path=source_identity_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
        g15_bridge_path=g15_bridge_path,
        prepared_index_path=prepared_index_path,
        prepared_identity_path=prepared_identity_path,
    )
    commands["g15_exact_replay"] = [
        "python",
        "ng_g15_exact_replay_completion.py",
        "--bridge",
        str(g15_bridge_path.resolve(strict=False)),
        "--prepared-index",
        str(prepared_index_path.resolve(strict=False)),
        "--replay",
        str(g15_replay_path.resolve(strict=False)),
        "--anchor",
        str(g15_anchor_path.resolve(strict=False)),
        "--blind-prior",
        str(g15_blind_prior_path.resolve(strict=False)),
        "--out",
        str(g15_completion_path.resolve(strict=False)),
    ]
    commands["g15_exact_refinement"] = [
        "python",
        "ng_g15_exact_refinement_gate.py",
        "--completion",
        str(g15_completion_path.resolve(strict=False)),
        "--pipeline",
        str(g15_pipeline_path.resolve(strict=False)),
        "--blind-forecast",
        str(g15_blind_forecast_path.resolve(strict=False)),
        "--out",
        str(g15_refinement_authorization_path.resolve(strict=False)),
    ]
    commands["g15_counterfactual_attribution"] = [
        "python",
        "ng_g15_counterfactual_attribution.py",
        "--replay",
        str(g15_replay_path.resolve(strict=False)),
        "--anchor",
        str(g15_anchor_path.resolve(strict=False)),
        "--refine-stream",
        str(g15_refine_stream_path.resolve(strict=False)),
        "--out",
        str(g15_attribution_path.resolve(strict=False)),
    ]
    commands["g15_counterfactual_attribution_authorization"] = [
        "python",
        "ng_g15_counterfactual_attribution_gate.py",
        "--completion",
        str(g15_completion_path.resolve(strict=False)),
        "--pipeline",
        str(g15_pipeline_path.resolve(strict=False)),
        "--refinement-authorization",
        str(g15_refinement_authorization_path.resolve(strict=False)),
        "--attribution",
        str(g15_attribution_path.resolve(strict=False)),
        "--out",
        str(g15_attribution_authorization_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV27Error(str(error)) from error
    rows_list = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows_list]
    expected_order = [spec.key for spec in readiness.STAGES]
    if keys != expected_order:
        raise CorpusExecutorPlanCompilerV27Error(
            "compiled plan does not use the readiness-v32 stage order"
        )
    if list(CONFIGURED_STAGES) != expected_order[: len(CONFIGURED_STAGES)]:
        raise CorpusExecutorPlanCompilerV27Error(
            "configured stages are not the exact readiness-v32 pre-outcome prefix"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key in CONFIGURED_STAGES:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            raise CorpusExecutorPlanCompilerV27Error(f"configured stage missing: {key}")
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV27Error(f"{key}: command vector mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV27Error(f"{key}: must remain pre-outcome")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV27Error(
                    f"{key}: compiled enablement mismatch"
                )

    expected_contracts = {
        "g15_exact_replay": (
            "g15_exact_replay_completion.json",
            ["python", "ng_g15_exact_replay_completion.py"],
        ),
        "g15_exact_refinement": (
            "g15_exact_refinement_authorization.json",
            ["python", "ng_g15_exact_refinement_gate.py"],
        ),
        "g15_counterfactual_attribution": (
            "g15_counterfactual_attribution.json",
            ["python", "ng_g15_counterfactual_attribution.py"],
        ),
        "g15_counterfactual_attribution_authorization": (
            "g15_counterfactual_attribution_authorization.json",
            ["python", "ng_g15_counterfactual_attribution_gate.py"],
        ),
    }
    for key, (output, entrypoint) in expected_contracts.items():
        row = rows[key]
        if row.get("expected_output") != output:
            raise CorpusExecutorPlanCompilerV27Error(f"{key}: artifact was substituted")
        if row.get("suggested_entrypoint") != entrypoint:
            raise CorpusExecutorPlanCompilerV27Error(f"{key}: entrypoint was substituted")

    attribution_index = keys.index("g15_counterfactual_attribution")
    if keys[attribution_index : attribution_index + 3] != [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
    ]:
        raise CorpusExecutorPlanCompilerV27Error(
            "attribution authorization must remain directly before fixed-outcome publication"
        )
    return rows


