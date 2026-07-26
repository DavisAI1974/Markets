#!/usr/bin/env python3
"""Build, validate, and emit the stable readiness-v32 executor plan."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler_v27_core as core

SCHEMA = core.SCHEMA
STATUS = core.STATUS
CONFIGURED_STAGES = core.CONFIGURED_STAGES
CorpusExecutorPlanCompilerV27Error = core.CorpusExecutorPlanCompilerV27Error
fingerprinting = core.fingerprinting
v26 = core.v26
executor = core.executor
readiness = core.readiness
_load = core._load
_write = core._write
_sha256_bytes = core._sha256_bytes
_authority = core._authority
_validate_g15_chain = core._validate_g15_chain
_commands = core._commands
_validate_plan = core._validate_plan

def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    bridge = _load(g15_bridge_path)
    prepared_index = _load(prepared_index_path)
    replay = _load(g15_replay_path)
    anchor = _load(g15_anchor_path)
    blind_prior = _load(g15_blind_prior_path)
    pipeline = _load(g15_pipeline_path)
    refine_stream = _load(g15_refine_stream_path)
    completion = _load(g15_completion_path)
    refinement_authorization = _load(g15_refinement_authorization_path)
    attribution = _load(g15_attribution_path)
    attribution_authorization = _load(g15_attribution_authorization_path)
    blind_forecast_bytes = g15_blind_forecast_path.read_bytes()

    chain = _validate_g15_chain(
        bridge=bridge,
        prepared_index=prepared_index,
        replay=replay,
        anchor=anchor,
        blind_prior=blind_prior,
        blind_forecast_bytes=blind_forecast_bytes,
        completion=completion,
        pipeline=pipeline,
        refinement_authorization=refinement_authorization,
        refine_stream=refine_stream,
        attribution=attribution,
        attribution_authorization=attribution_authorization,
    )
    upstream_plan, upstream_receipt = v26.build_compiled_plan(
        artifact_dir=artifact_dir,
        working_directory=working_directory,
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
    command_kwargs = dict(
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
        g15_replay_path=g15_replay_path,
        g15_anchor_path=g15_anchor_path,
        g15_blind_prior_path=g15_blind_prior_path,
        g15_blind_forecast_path=g15_blind_forecast_path,
        g15_pipeline_path=g15_pipeline_path,
        g15_refine_stream_path=g15_refine_stream_path,
        g15_completion_path=g15_completion_path,
        g15_refinement_authorization_path=g15_refinement_authorization_path,
        g15_attribution_path=g15_attribution_path,
        g15_attribution_authorization_path=g15_attribution_authorization_path,
    )
    commands = _commands(**command_kwargs)
    plan = executor.build_plan(artifact_dir, working_directory)
    for key in CONFIGURED_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    _validate_plan(plan, commands, compiled=True)
    upstream_commands = {
        str(row["key"]): list(row.get("argv") or [])
        for row in upstream_plan.get("stages") or []
        if str(row.get("key")) in v26.CONFIGURED_STAGES
    }
    receipt: dict[str, Any] = {
        **copy.deepcopy(upstream_receipt),
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "blind_forecast_path": str(g15_blind_forecast_path.resolve(strict=False)),
        "blind_forecast_sha256": _sha256_bytes(blind_forecast_bytes),
        **{key: value for key, value in chain.items() if key not in {
            "completion", "pipeline", "refinement_authorization", "attribution", "attribution_authorization"
        }},
        "g15_exact_replay_completion": chain["completion"],
        "g15_pipeline": chain["pipeline"],
        "g15_exact_refinement_authorization": chain["refinement_authorization"],
        "g15_counterfactual_attribution": chain["attribution"],
        "g15_counterfactual_attribution_authorization": chain[
            "attribution_authorization"
        ],
        "g15_replay": copy.deepcopy(replay),
        "g15_anchor": copy.deepcopy(anchor),
        "g15_blind_prior": copy.deepcopy(blind_prior),
        "g15_refine_stream": copy.deepcopy(refine_stream),
        "upstream_v31_compiler_receipt": copy.deepcopy(upstream_receipt),
        "upstream_v31_execution_plan": copy.deepcopy(upstream_plan),
        "upstream_v31_commands": copy.deepcopy(upstream_commands),
        "g15_exact_replay_armed_only_after_prepared_identity": True,
        "g15_exact_refinement_bound_to_exact_replay": True,
        "g15_six_factor_attribution_deterministic": True,
        "g15_attribution_authorization_required_before_publication": True,
        "g15_lesson_proposals_brain_write_forbidden": True,
        "g15_publication_remains_disabled": True,
        "all_configured_stages_pre_outcome": True,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_G15_ATTRIBUTION_AUTHORIZATION_PIPELINE",
    }
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands, verify_files=False)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
    verify_files: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV27Error(
            "compiler v27 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v27 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "g15_exact_replay_armed_only_after_prepared_identity": True,
        "g15_exact_refinement_bound_to_exact_replay": True,
        "g15_six_factor_attribution_deterministic": True,
        "g15_attribution_authorization_required_before_publication": True,
        "g15_lesson_proposals_brain_write_forbidden": True,
        "g15_publication_remains_disabled": True,
        "all_configured_stages_pre_outcome": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV27Error(
                f"compiler v27 field mismatch: {field}"
            )

    required_artifacts = (
        "g15_exact_replay_completion",
        "g15_pipeline",
        "g15_exact_refinement_authorization",
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_replay",
        "g15_anchor",
        "g15_blind_prior",
        "g15_refine_stream",
    )
    if not all(isinstance(checked.get(name), Mapping) for name in required_artifacts):
        raise CorpusExecutorPlanCompilerV27Error(
            "compiler v27 lacks embedded G15 authorization provenance"
        )
    blind_bytes: bytes | None = None
    if verify_files:
        blind_path = Path(str(checked.get("blind_forecast_path") or ""))
        if not blind_path.is_file():
            raise CorpusExecutorPlanCompilerV27Error("blind forecast file is missing")
        blind_bytes = blind_path.read_bytes()
        if checked.get("blind_forecast_sha256") != _sha256_bytes(blind_bytes):
            raise CorpusExecutorPlanCompilerV27Error("blind forecast fingerprint changed")

    bridge = checked.get("g15_bridge")
    prepared_index = checked.get("prepared_index")
    if not isinstance(bridge, Mapping) or not isinstance(prepared_index, Mapping):
        raise CorpusExecutorPlanCompilerV27Error(
            "compiler v27 lacks embedded bridge/prepared index provenance"
        )
    chain = _validate_g15_chain(
        bridge=bridge,
        prepared_index=prepared_index,
        replay=checked["g15_replay"],
        anchor=checked["g15_anchor"],
        blind_prior=checked["g15_blind_prior"],
        blind_forecast_bytes=blind_bytes,
        completion=checked["g15_exact_replay_completion"],
        pipeline=checked["g15_pipeline"],
        refinement_authorization=checked[
            "g15_exact_refinement_authorization"
        ],
        refine_stream=checked["g15_refine_stream"],
        attribution=checked["g15_counterfactual_attribution"],
        attribution_authorization=checked[
            "g15_counterfactual_attribution_authorization"
        ],
    )
    fingerprint_fields = {
        "completion_fingerprint": chain["completion_fingerprint"],
        "pipeline_fingerprint": chain["pipeline_fingerprint"],
        "refinement_authorization_fingerprint": chain[
            "refinement_authorization_fingerprint"
        ],
        "attribution_fingerprint": chain["attribution_fingerprint"],
        "attribution_authorization_fingerprint": chain[
            "attribution_authorization_fingerprint"
        ],
        "replay_fingerprint": chain["replay_fingerprint"],
        "anchor_fingerprint": chain["anchor_fingerprint"],
        "refine_stream_fingerprint": chain["refine_stream_fingerprint"],
        "factor_summary_fingerprint": chain["factor_summary_fingerprint"],
        "per_day_fingerprint": chain["per_day_fingerprint"],
        "rows_fingerprint": chain["rows_fingerprint"],
        "lesson_proposals_fingerprint": chain["lesson_proposals_fingerprint"],
        "n_states": chain["n_states"],
        "n_days": chain["n_days"],
        "factors": chain["factors"],
    }
    for field, expected_value in fingerprint_fields.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV27Error(
                f"compiler v27 G15 chain mismatch: {field}"
            )

    upstream_receipt = checked.get("upstream_v31_compiler_receipt")
    upstream_plan = checked.get("upstream_v31_execution_plan")
    upstream_commands = checked.get("upstream_v31_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV27Error(
            "compiler v27 lacks embedded v31 compiler provenance"
        )
    try:
        v26.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands={str(key): list(argv) for key, argv in upstream_commands.items()},
            verify_files=False,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV27Error(
            f"embedded v31 compiler provenance is invalid: {error}"
        ) from error
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in (
        "artifact-dir", "working-directory", "resolution-spec", "expected-day-receipt",
        "finalization-receipt", "resolution-receipt", "capture-spec", "capture-receipt",
        "materialization-spec", "materialization-receipt", "materialization-provenance",
        "source-identity", "inventory-receipt", "broad-plan", "slice-bundle", "target-plan",
        "g15-bridge", "prepared-index", "prepared-identity", "g15-replay", "g15-anchor",
        "g15-blind-prior", "g15-blind-forecast", "g15-pipeline", "g15-refine-stream",
        "g15-completion", "g15-refinement-authorization", "g15-attribution",
        "g15-attribution-authorization", "plan-out", "receipt-out",
    ):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        resolution_spec_path=args.resolution_spec,
        expected_day_receipt_path=args.expected_day_receipt,
        finalization_receipt_path=args.finalization_receipt,
        resolution_receipt_path=args.resolution_receipt,
        capture_spec_path=args.capture_spec,
        capture_receipt_path=args.capture_receipt,
        materialization_spec_path=args.materialization_spec,
        materialization_receipt_path=args.materialization_receipt,
        materialization_provenance_path=args.materialization_provenance,
        source_identity_path=args.source_identity,
        inventory_receipt_path=args.inventory_receipt,
        broad_plan_path=args.broad_plan,
        slice_bundle_path=args.slice_bundle,
        target_plan_path=args.target_plan,
        g15_bridge_path=args.g15_bridge,
        prepared_index_path=args.prepared_index,
        prepared_identity_path=args.prepared_identity,
        g15_replay_path=args.g15_replay,
        g15_anchor_path=args.g15_anchor,
        g15_blind_prior_path=args.g15_blind_prior,
        g15_blind_forecast_path=args.g15_blind_forecast,
        g15_pipeline_path=args.g15_pipeline,
        g15_refine_stream_path=args.g15_refine_stream,
        g15_completion_path=args.g15_completion,
        g15_refinement_authorization_path=args.g15_refinement_authorization,
        g15_attribution_path=args.g15_attribution,
        g15_attribution_authorization_path=args.g15_attribution_authorization,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
