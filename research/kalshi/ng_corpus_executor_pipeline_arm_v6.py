#!/usr/bin/env python3
"""Arm the six corpus stages under one stable readiness-v9 executor plan.

Only the corpus prefix is armed. Exact G15 replay, partition-to-replay byte
authorization, replay-window authorization, refinement, scoring, publication,
G16, and every execution-authority stage remain disabled.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v6 as compiler
import ng_historical_refinement_executor_v7 as executor
import ng_historical_refinement_readiness_v9 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v6"
ARMED_STAGES = compiler.CONFIGURED_STAGES
STATUS = "BROAD_CORPUS_EXACT_PARTITION_REPLAY_BYTE_BOUND_PIPELINE_ARMED"
PARTITION_REPLAY_STAGE = compiler.PARTITION_REPLAY_STAGE
WINDOW_STAGE = compiler.WINDOW_STAGE


class CorpusExecutorPipelineArmV6Error(ValueError):
    """Raised when the readiness-v9 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV6Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV6Error(f"JSON artifact must be an object: {path}")
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
            raise CorpusExecutorPipelineArmV6Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPipelineArmV6Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPipelineArmV6Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPipelineArmV6Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPipelineArmV6Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    result: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        argv = rows.get(key, {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
            raise CorpusExecutorPipelineArmV6Error(f"{key}: compiled command is missing or invalid")
        result[key] = list(argv)
    return result


def _validate_compiled(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    plan = copy.deepcopy(dict(compiled_plan))
    receipt = copy.deepcopy(dict(compiler_receipt))
    executor.validate_plan(plan)
    commands = _commands(plan)
    compiler.validate_receipt(receipt, plan=plan, commands=commands)
    if receipt.get("schema") != compiler.SCHEMA:
        raise CorpusExecutorPipelineArmV6Error("compiler receipt schema mismatch")
    if receipt.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV6Error("compiler did not bind readiness v9")
    if receipt.get("configured_stages") != list(ARMED_STAGES):
        raise CorpusExecutorPipelineArmV6Error("compiler stage order mismatch")
    if plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV6Error("corpus plan must not reference outcomes")
    return plan, receipt, commands


def _arm_plan(plan: Mapping[str, Any], commands: Mapping[str, list[str]]) -> dict[str, Any]:
    armed = copy.deepcopy(dict(plan))
    for key in ARMED_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=True)
    executor.validate_plan(armed)
    rows = {str(row.get("key")): row for row in armed.get("stages") or []}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True:
            raise CorpusExecutorPipelineArmV6Error(f"{key}: stage was not armed")
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPipelineArmV6Error(f"{key}: stage must remain pre-outcome")
    for spec in readiness.STAGES[len(ARMED_STAGES):]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmV6Error(f"{spec.key}: downstream stage must remain disabled")
    for key, label in (
        (PARTITION_REPLAY_STAGE, "partition-to-replay authorization"),
        (WINDOW_STAGE, "replay-window authorization"),
    ):
        if rows[key].get("enabled") is not False or rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPipelineArmV6Error(f"exact {label} must remain disabled and pre-outcome")
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, commands = _validate_compiled(compiled_plan, compiler_receipt)
    armed_plan = _arm_plan(source_plan, commands)
    order = [spec.key for spec in readiness.STAGES]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(order),
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": armed_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": order[: len(ARMED_STAGES)],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_target_broad_overlap_partition_and_replay_authorization_contract": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_gate_armed_before_g15": True,
        "broad_exact_overlap_gate_armed_before_g15": True,
        "broad_exact_partition_gate_armed_before_g15": True,
        "exact_g15_partition_replay_authorization_required_before_window": True,
        "exact_g15_partition_replay_stage_present": PARTITION_REPLAY_STAGE in order,
        "exact_g15_partition_replay_stage_enabled": False,
        "exact_g15_replay_window_authorization_required_before_refinement": True,
        "exact_g15_replay_window_stage_present": WINDOW_STAGE in order,
        "exact_g15_replay_window_stage_enabled": False,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_EXACT_PARTITION_CORPUS_PIPELINE",
        "after_exact_partition_gate": "CONFIGURE_EXACT_G15_REPLAY_ONLY_IF_VERIFIED",
        "after_exact_g15_replay": "RUN_EXACT_PARTITION_REPLAY_AUTHORIZATION_BEFORE_WINDOW",
        "after_exact_partition_replay_authorization": "RUN_EXACT_REPLAY_WINDOW_AUTHORIZATION_BEFORE_REFINEMENT",
    }
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_arm_receipt(receipt, compiled_plan=source_plan, compiler_receipt=source_receipt, armed_plan=armed_plan)
    return armed_plan, receipt


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
        raise CorpusExecutorPipelineArmV6Error("pipeline arm v6 schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline arm v6 receipt")
    source_plan, source_receipt, commands = _validate_compiled(compiled_plan, compiler_receipt)
    expected_plan = _arm_plan(source_plan, commands)
    executor.validate_plan(armed_plan)
    if fingerprinting._canonical(armed_plan) != fingerprinting._canonical(expected_plan):
        raise CorpusExecutorPipelineArmV6Error("armed plan differs from deterministic transformation")
    order = [spec.key for spec in readiness.STAGES]
    expected_fields = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(order),
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": order[: len(ARMED_STAGES)],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_target_broad_overlap_partition_and_replay_authorization_contract": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_gate_armed_before_g15": True,
        "broad_exact_overlap_gate_armed_before_g15": True,
        "broad_exact_partition_gate_armed_before_g15": True,
        "exact_g15_partition_replay_authorization_required_before_window": True,
        "exact_g15_partition_replay_stage_present": True,
        "exact_g15_partition_replay_stage_enabled": False,
        "exact_g15_replay_window_authorization_required_before_refinement": True,
        "exact_g15_replay_window_stage_present": True,
        "exact_g15_replay_window_stage_enabled": False,
        "target_day_subset_cannot_satisfy_broad_scope": True,
        "broad_scope_alone_cannot_satisfy_exact_overlap": True,
        "cross_lane_overlap_alone_cannot_satisfy_source_partition": True,
    }
    for field, expected in expected_fields.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPipelineArmV6Error(f"pipeline arm v6 field mismatch: {field}")
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
