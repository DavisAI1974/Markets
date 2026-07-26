#!/usr/bin/env python3
"""Arm the complete pre-outcome G15 attribution-authorization prefix under v32."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v27 as compiler
import ng_historical_refinement_executor_v28 as executor
import ng_historical_refinement_readiness_v32 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v27"
STATUS = "G15_ATTRIBUTION_AUTHORIZATION_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES


class CorpusExecutorPipelineArmV27Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV27Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV27Error(f"JSON artifact must be an object: {path}")
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
        raise CorpusExecutorPipelineArmV27Error(str(error)) from error


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    commands: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        argv = (rows.get(key) or {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise CorpusExecutorPipelineArmV27Error(
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
        raise CorpusExecutorPipelineArmV27Error("pre-outcome plan may not reference outcomes")
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
        "g15_exact_replay_armed_after_prepared_identity": True,
        "g15_exact_refinement_armed_after_exact_replay": True,
        "g15_six_factor_attribution_armed_after_refinement": True,
        "g15_attribution_authorization_armed_before_publication": True,
        "all_six_factors_required_on_every_causal_state": True,
        "lesson_proposals_brain_write_forbidden": True,
        "g15_publication_still_disabled": True,
        "all_armed_stages_pre_outcome": True,
        "all_fixed_outcome_and_g16_stages_disabled": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_G15_ATTRIBUTION_AUTHORIZATION_PIPELINE",
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
        raise CorpusExecutorPipelineArmV27Error(
            "pipeline arm v27 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline arm v27 receipt")
    source_plan, source_receipt, commands = _validated_compiled(
        compiled_plan, compiler_receipt
    )
    expected_plan = _arm(source_plan, commands)
    if fingerprinting._canonical(armed_plan) != fingerprinting._canonical(expected_plan):
        raise CorpusExecutorPipelineArmV27Error(
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
        "g15_exact_replay_armed_after_prepared_identity": True,
        "g15_exact_refinement_armed_after_exact_replay": True,
        "g15_six_factor_attribution_armed_after_refinement": True,
        "g15_attribution_authorization_armed_before_publication": True,
        "all_six_factors_required_on_every_causal_state": True,
        "lesson_proposals_brain_write_forbidden": True,
        "g15_publication_still_disabled": True,
        "all_armed_stages_pre_outcome": True,
        "all_fixed_outcome_and_g16_stages_disabled": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPipelineArmV27Error(
                f"pipeline arm v27 field mismatch: {field}"
            )
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True or rows[key].get(
            "requires_fixed_outcomes"
        ) is not False:
            raise CorpusExecutorPipelineArmV27Error(
                f"{key}: armed pre-outcome stage contract mismatch"
            )
    for spec in readiness.STAGES[len(ARMED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmV27Error(
                f"{spec.key}: downstream stage was prematurely armed"
            )
    if rows["g15_publication"].get("enabled"):
        raise CorpusExecutorPipelineArmV27Error(
            "fixed-outcome G15 publication must remain disabled"
        )
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
