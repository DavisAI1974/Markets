#!/usr/bin/env python3
"""Arm the prepared-normalized-identity historical prefix under readiness v31."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v26 as compiler
import ng_historical_refinement_executor_v27 as executor
import ng_historical_refinement_readiness_v31 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v26"
STATUS = "G15_PREPARED_NORMALIZED_IDENTITY_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES


class CorpusExecutorPipelineArmV26Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV26Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV26Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        compiler._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPipelineArmV26Error(str(error)) from error


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    commands: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        argv = (rows.get(key) or {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise CorpusExecutorPipelineArmV26Error(
                f"{key}: compiled command is missing or invalid"
            )
        commands[key] = list(argv)
    return commands


def _validated_compiled(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    source_plan = copy.deepcopy(dict(plan))
    source_receipt = copy.deepcopy(dict(receipt))
    commands = _commands(source_plan)
    compiler.validate_receipt(
        source_receipt,
        plan=source_plan,
        commands=commands,
        verify_files=False,
    )
    executor.validate_plan(source_plan)
    if source_plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV26Error("historical plan may not reference outcomes")
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
        "prepared_normalized_identity_armed_after_exact_broad_alignment": True,
        "prepared_normalized_identity_armed_before_g15_replay": True,
        "prepared_identity_command_bound_to_bridge_index_and_output": True,
        "prepared_publishers_explicit_and_positive_required": True,
        "prepared_rows_exact_manifest_identity_required": True,
        "prepared_event_time_bounds_and_chronology_required": True,
        "prepared_definitions_before_trade_and_mbo_required": True,
        "g15_replay_still_disabled": True,
        "all_armed_stages_pre_outcome": True,
        "all_downstream_g15_g16_stages_disabled": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_PREPARED_IDENTITY_PIPELINE",
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
        raise CorpusExecutorPipelineArmV26Error(
            "pipeline arm v26 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline arm v26 receipt")
    source_plan, source_receipt, commands = _validated_compiled(
        compiled_plan, compiler_receipt
    )
    expected_plan = _arm(source_plan, commands)
    if fingerprinting._canonical(armed_plan) != fingerprinting._canonical(expected_plan):
        raise CorpusExecutorPipelineArmV26Error(
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
        "prepared_normalized_identity_armed_after_exact_broad_alignment": True,
        "prepared_normalized_identity_armed_before_g15_replay": True,
        "prepared_identity_command_bound_to_bridge_index_and_output": True,
        "prepared_publishers_explicit_and_positive_required": True,
        "prepared_rows_exact_manifest_identity_required": True,
        "prepared_event_time_bounds_and_chronology_required": True,
        "prepared_definitions_before_trade_and_mbo_required": True,
        "g15_replay_still_disabled": True,
        "all_armed_stages_pre_outcome": True,
        "all_downstream_g15_g16_stages_disabled": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPipelineArmV26Error(
                f"pipeline arm v26 field mismatch: {field}"
            )
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True or rows[key].get(
            "requires_fixed_outcomes"
        ) is not False:
            raise CorpusExecutorPipelineArmV26Error(
                f"{key}: armed historical stage contract mismatch"
            )
    for spec in readiness.STAGES[len(ARMED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmV26Error(
                f"{spec.key}: downstream stage was prematurely armed"
            )
    if rows["g15_exact_replay"].get("enabled"):
        raise CorpusExecutorPipelineArmV26Error("G15 replay must remain disabled")
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-plan", type=Path, required=True)
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    armed, receipt = build_armed_plan(_load(args.compiled_plan), _load(args.compiler_receipt))
    _write(args.plan_out, armed)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
