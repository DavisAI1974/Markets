#!/usr/bin/env python3
"""Compile the stable readiness-v9 corpus plan with exact replay-byte binding.

The first six corpus stages remain the historical-first prefix. The generated
plan is built by the readiness-v9 executor, so exact partition-to-replay byte
authorization is present, pre-outcome, disabled, and ordered between completed
G15 replay and replay-window authorization.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v5 as v5
import ng_historical_refinement_executor_v7 as executor
import ng_historical_refinement_readiness_v9 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v6"
CONFIGURED_STAGES = v5.CONFIGURED_STAGES
STATUS = "BROAD_CORPUS_EXACT_PARTITION_REPLAY_BYTE_BOUND_EXECUTOR_PLAN_COMPILED"
PARTITION_REPLAY_STAGE = "g15_exact_partition_replay_authorization"
WINDOW_STAGE = v5.WINDOW_STAGE


class CorpusExecutorPlanCompilerV6Error(ValueError):
    """Raised when a readiness-v9 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV6Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV6Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusExecutorPlanCompilerV6Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV6Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV6Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV6Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV6Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(artifact_dir: Path, slice_path: Path, inspection_path: Path) -> dict[str, list[str]]:
    return v5._commands(artifact_dir, slice_path, inspection_path)


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v9_boundary(plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    expected = _stage_order()
    if keys != expected:
        raise CorpusExecutorPlanCompilerV6Error("execution plan is not the exact readiness-v9 stage contract")
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV6Error("duplicate execution-plan stage keys")
    if not (
        keys.index("g15_exact_replay")
        < keys.index(PARTITION_REPLAY_STAGE)
        < keys.index(WINDOW_STAGE)
        < keys.index("g15_exact_refinement")
    ):
        raise CorpusExecutorPlanCompilerV6Error(
            "exact partition binding and replay-window authorization are not between replay and refinement"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key, label in (
        (PARTITION_REPLAY_STAGE, "partition-to-replay authorization"),
        (WINDOW_STAGE, "replay-window authorization"),
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPlanCompilerV6Error(f"{label} must remain disabled in the compiled corpus plan")
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV6Error(f"{label} must remain pre-outcome")
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    slice_bundle, inspection_plan = fingerprinting.validate_inputs(
        _load(slice_bundle_path), _load(inspection_plan_path)
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    commands = _commands(artifact_dir, slice_bundle_path, inspection_plan_path)
    for index, key in enumerate(CONFIGURED_STAGES):
        plan = executor.configure_stage(plan, key, commands[key], enabled=index == 0)
    rows = _validate_v9_boundary(plan)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(_stage_order()),
        "slice_bundle_fingerprint": slice_bundle["slice_bundle_fingerprint"],
        "inspection_plan_fingerprint": inspection_plan["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": fingerprinting._fp(commands),
        "broad_corpus_scope_gate_required": True,
        "broad_corpus_exact_overlap_gate_required": True,
        "broad_corpus_exact_partition_gate_required": True,
        "exact_g15_partition_replay_authorization_required": True,
        "exact_g15_partition_replay_stage_present": PARTITION_REPLAY_STAGE in rows,
        "exact_g15_partition_replay_stage_enabled": False,
        "exact_g15_replay_window_authorization_required": True,
        "exact_g15_replay_window_stage_present": WINDOW_STAGE in rows,
        "exact_g15_replay_window_stage_enabled": False,
        "g15_replay_cannot_authorize_window_without_exact_partition_bytes": True,
        "g15_replay_cannot_authorize_refinement_without_exact_partition_and_window": True,
        "exact_g15_partition_replay_output": str(
            artifact_dir.resolve(strict=False) / "g15_exact_partition_replay_authorization.json"
        ),
        "exact_g15_replay_window_output": str(
            artifact_dir.resolve(strict=False) / "g15_exact_replay_window_authorization.json"
        ),
        "target_day_subset_cannot_satisfy_broad_scope": True,
        "broad_scope_alone_cannot_satisfy_exact_overlap": True,
        "cross_lane_overlap_alone_cannot_satisfy_source_partition": True,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_CORPUS_INSPECTION",
    }
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV6Error("compiler v6 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v6 receipt")
    rows = _validate_v9_boundary(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV6Error("compiler v6 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV6Error("readiness-v9 contract mismatch")
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(_stage_order()):
        raise CorpusExecutorPlanCompilerV6Error("readiness-v9 stage-contract fingerprint mismatch")
    if checked.get("execution_plan_fingerprint") != plan.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV6Error("execution-plan fingerprint mismatch")
    if checked.get("commands_fingerprint") != fingerprinting._fp(commands):
        raise CorpusExecutorPlanCompilerV6Error("command fingerprint mismatch")
    if checked.get("configured_stages") != list(CONFIGURED_STAGES):
        raise CorpusExecutorPlanCompilerV6Error("configured stage order mismatch")
    for field in (
        "broad_corpus_scope_gate_required",
        "broad_corpus_exact_overlap_gate_required",
        "broad_corpus_exact_partition_gate_required",
        "exact_g15_partition_replay_authorization_required",
        "exact_g15_partition_replay_stage_present",
        "exact_g15_replay_window_authorization_required",
        "exact_g15_replay_window_stage_present",
        "g15_replay_cannot_authorize_window_without_exact_partition_bytes",
        "g15_replay_cannot_authorize_refinement_without_exact_partition_and_window",
        "target_day_subset_cannot_satisfy_broad_scope",
        "broad_scope_alone_cannot_satisfy_exact_overlap",
        "cross_lane_overlap_alone_cannot_satisfy_source_partition",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPlanCompilerV6Error(f"compiler v6 mandatory field mismatch: {field}")
    if checked.get("exact_g15_partition_replay_stage_enabled") is not False:
        raise CorpusExecutorPlanCompilerV6Error("compiled plan must not pre-enable partition-to-replay authorization")
    if checked.get("exact_g15_replay_window_stage_enabled") is not False:
        raise CorpusExecutorPlanCompilerV6Error("compiled plan must not pre-enable replay-window authorization")
    for key in CONFIGURED_STAGES:
        if rows.get(key, {}).get("argv") != list(commands[key]):
            raise CorpusExecutorPlanCompilerV6Error(f"{key}: compiled argv mismatch")
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV6Error(f"{key}: corpus stages must remain pre-outcome")
    if rows["corpus_coverage"].get("enabled") is not True:
        raise CorpusExecutorPlanCompilerV6Error("corpus inspection must be enabled initially")
    for key in CONFIGURED_STAGES[1:]:
        if rows[key].get("enabled"):
            raise CorpusExecutorPlanCompilerV6Error(f"{key}: downstream corpus stage must remain disabled")
    if any(row.get("enabled") for row in plan.get("stages") or [] if row.get("key") not in CONFIGURED_STAGES):
        raise CorpusExecutorPlanCompilerV6Error("G15/G16 stages must remain disabled")
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--inspection-plan", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        slice_bundle_path=args.slice_bundle,
        inspection_plan_path=args.inspection_plan,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "enabled_stage": receipt["enabled_stage"], "plan": str(args.plan_out)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
