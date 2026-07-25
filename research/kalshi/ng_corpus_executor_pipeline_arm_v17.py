#!/usr/bin/env python3
"""Arm the latest-version-resolved stable corpus prefix under readiness v22."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v17 as compiler
import ng_historical_refinement_executor_v18 as executor
import ng_historical_refinement_readiness_v22 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v17"
STATUS = "LATEST_VERSION_RESOLVED_CORPUS_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES


class CorpusExecutorPipelineArmV17Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV17Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV17Error(f"JSON artifact must be an object: {path}")
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
            raise CorpusExecutorPipelineArmV17Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPipelineArmV17Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPipelineArmV17Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPipelineArmV17Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPipelineArmV17Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    result: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        argv = (rows.get(key) or {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise CorpusExecutorPipelineArmV17Error(
                f"{key}: compiled command is missing or invalid"
            )
        result[key] = list(argv)
    return result


def _validated_compiled(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    source_plan = copy.deepcopy(dict(plan))
    source_receipt = copy.deepcopy(dict(receipt))
    commands = _commands(source_plan)
    compiler.validate_receipt(source_receipt, plan=source_plan, commands=commands)
    executor.validate_plan(source_plan)
    if source_plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV17Error("corpus plan may not reference outcomes")
    return source_plan, source_receipt, commands


def _arm(plan: Mapping[str, Any], commands: Mapping[str, list[str]]) -> dict[str, Any]:
    armed = copy.deepcopy(dict(plan))
    for key in ARMED_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=True)
    executor.validate_plan(armed)
    compiler._validate_plan(armed, commands, compiled=False)
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any], compiler_receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, commands = _validated_compiled(
        compiled_plan, compiler_receipt
    )
    armed = _arm(source_plan, commands)
    order = [spec.key for spec in readiness.STAGES]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(order),
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": armed["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": order[: len(ARMED_STAGES)],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_and_ledger": True,
        "latest_version_resolution_armed_before_inventory_capture": True,
        "operator_guessed_version_ids_forbidden": True,
        "complete_latest_object_set_required": True,
        "source_identity_may_not_be_inferred_from_s3_keys": True,
        "resolved_capture_spec_bound_to_inventory_capture": True,
        "inventory_capture_armed_before_materialization": True,
        "checksum_enabled_head_required": True,
        "materialization_armed_before_broad_inspection": True,
        "all_corpus_stages_pre_outcome": True,
        "all_downstream_g15_g16_stages_disabled": True,
        "after_latest_version_resolution": "CAPTURE_CHECKSUM_ENABLED_EXACT_S3_INVENTORY",
        "after_s3_inventory_capture": "ATTEST_EXACT_S3_TO_LOCAL_MATERIALIZATION",
        "after_s3_materialization": "RUN_BROAD_BYTE_INSPECTION_FROM_ATTESTED_PLAN",
        "after_target_slice_broad_lineage": "REDERIVE_TARGET_BYTES_FROM_BOUND_BROAD_SOURCES",
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_LATEST_VERSION_RESOLVED_CORPUS_PIPELINE",
    }
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_arm_receipt(
        receipt,
        compiled_plan=source_plan,
        compiler_receipt=source_receipt,
        armed_plan=armed,
    )
    return armed, receipt


def validate_arm_receipt(
    value: Mapping[str, Any],
    *,
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
    armed_plan: Mapping[str, Any],
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPipelineArmV17Error(
            "pipeline arm v17 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline arm v17 receipt")
    source_plan, source_receipt, commands = _validated_compiled(
        compiled_plan, compiler_receipt
    )
    expected_plan = _arm(source_plan, commands)
    if fingerprinting._canonical(armed_plan) != fingerprinting._canonical(expected_plan):
        raise CorpusExecutorPipelineArmV17Error(
            "armed plan differs from deterministic transformation"
        )
    order = [spec.key for spec in readiness.STAGES]
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(order),
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": order[: len(ARMED_STAGES)],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_and_ledger": True,
        "latest_version_resolution_armed_before_inventory_capture": True,
        "operator_guessed_version_ids_forbidden": True,
        "complete_latest_object_set_required": True,
        "source_identity_may_not_be_inferred_from_s3_keys": True,
        "resolved_capture_spec_bound_to_inventory_capture": True,
        "inventory_capture_armed_before_materialization": True,
        "checksum_enabled_head_required": True,
        "materialization_armed_before_broad_inspection": True,
        "all_corpus_stages_pre_outcome": True,
        "all_downstream_g15_g16_stages_disabled": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPipelineArmV17Error(
                f"pipeline arm v17 field mismatch: {field}"
            )
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True or rows[key].get(
            "requires_fixed_outcomes"
        ) is not False:
            raise CorpusExecutorPipelineArmV17Error(
                f"{key}: armed corpus stage contract mismatch"
            )
    for spec in readiness.STAGES[len(ARMED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmV17Error(
                f"{spec.key}: downstream stage was prematurely armed"
            )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-plan", type=Path, required=True)
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    armed, receipt = build_armed_plan(
        _load(args.compiled_plan), _load(args.compiler_receipt)
    )
    _write(args.plan_out, armed)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
