#!/usr/bin/env python3
"""Arm the six readiness-v7 corpus stages under one stable executor plan.

The guarded executor still runs only the first blocking readiness stage.  The
order is byte inspection, exact daily basis regeneration, replay catalog export,
broad scope verification, exact cross-lane overlap, and exact same-lane source
partition verification.  G15 and later stages stay disabled.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v4 as compiler
import ng_historical_refinement_executor_v5 as executor
import ng_historical_refinement_readiness_v7 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v4"
ARMED_STAGES = compiler.CONFIGURED_STAGES
STATUS = "BROAD_CORPUS_EXACT_PARTITION_PIPELINE_ARMED"


class CorpusExecutorPipelineArmV4Error(ValueError):
    """Raised when the exact-partition corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV4Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV4Error(f"JSON artifact must be an object: {path}")
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
            raise CorpusExecutorPipelineArmV4Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPipelineArmV4Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPipelineArmV4Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPipelineArmV4Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPipelineArmV4Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    result: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        argv = rows.get(key, {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise CorpusExecutorPipelineArmV4Error(
                f"{key}: compiled command is missing or invalid"
            )
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
        raise CorpusExecutorPipelineArmV4Error("compiler receipt schema mismatch")
    if receipt.get("configured_stages") != list(ARMED_STAGES):
        raise CorpusExecutorPipelineArmV4Error("compiler stage order mismatch")
    if plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV4Error(
            "corpus plan must not reference outcomes"
        )
    return plan, receipt, commands


def _arm_plan(
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
) -> dict[str, Any]:
    armed = copy.deepcopy(dict(plan))
    for key in ARMED_STAGES:
        armed = executor.configure_stage(
            armed, key, commands[key], enabled=True
        )
    executor.validate_plan(armed)
    rows = {str(row.get("key")): row for row in armed.get("stages") or []}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True:
            raise CorpusExecutorPipelineArmV4Error(f"{key}: stage was not armed")
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPipelineArmV4Error(
                f"{key}: stage must remain pre-outcome"
            )
    for spec in readiness.STAGES[len(ARMED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmV4Error(
                f"{spec.key}: downstream stage must remain disabled"
            )
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, commands = _validate_compiled(
        compiled_plan, compiler_receipt
    )
    armed_plan = _arm_plan(source_plan, commands)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": armed_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": [
            spec.key for spec in readiness.STAGES[: len(ARMED_STAGES)]
        ],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_target_broad_overlap_and_partition_stages": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_gate_armed_before_g15": True,
        "broad_exact_overlap_gate_armed_before_g15": True,
        "broad_exact_partition_gate_armed_before_g15": True,
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
    }
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_arm_receipt(
        receipt,
        compiled_plan=source_plan,
        compiler_receipt=source_receipt,
        armed_plan=armed_plan,
    )
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
        raise CorpusExecutorPipelineArmV4Error(
            "pipeline arm v4 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline arm v4 receipt")
    source_plan, source_receipt, commands = _validate_compiled(
        compiled_plan, compiler_receipt
    )
    expected_plan = _arm_plan(source_plan, commands)
    executor.validate_plan(armed_plan)
    if fingerprinting._canonical(armed_plan) != fingerprinting._canonical(
        expected_plan
    ):
        raise CorpusExecutorPipelineArmV4Error(
            "armed plan differs from deterministic transformation"
        )
    expected_fields = {
        "status": STATUS,
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": list(ARMED_STAGES),
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_target_broad_overlap_and_partition_stages": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_gate_armed_before_g15": True,
        "broad_exact_overlap_gate_armed_before_g15": True,
        "broad_exact_partition_gate_armed_before_g15": True,
        "target_day_subset_cannot_satisfy_broad_scope": True,
        "broad_scope_alone_cannot_satisfy_exact_overlap": True,
        "cross_lane_overlap_alone_cannot_satisfy_source_partition": True,
    }
    for field, expected in expected_fields.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPipelineArmV4Error(
                f"pipeline arm v4 field mismatch: {field}"
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
        _load(args.compiled_plan),
        _load(args.compiler_receipt),
    )
    _write(args.plan_out, armed)
    _write(args.receipt_out, receipt)
    print(
        json.dumps(
            {"status": receipt["status"], "plan": str(args.plan_out)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
