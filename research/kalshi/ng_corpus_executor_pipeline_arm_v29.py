#!/usr/bin/env python3
"""Arm readiness-v38 through the attribution-bound G16 curve lock only.

The compiler supplies every command. This arm recursively validates that compiler
receipt, exposes only the fixed G15 outcome bound by ``g15_publication --actual``,
and enables the first-blocking-stage chain through the immutable G16 curve lock.
Both fixed-G16 scoring/publication stages remain disabled.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v29 as compiler
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v29"
STATUS = "G16_V38_ATTRIBUTION_BOUND_BLIND_CHAIN_ARMED"
TERMINAL_STAGE = "g16_attribution_bound_curve_lock"
PUBLICATION_STAGES = (
    "g16_counterfactual_publication",
    "g16_attribution_bound_publication",
)
_STAGE_ORDER = tuple(spec.key for spec in readiness.STAGES)
if TERMINAL_STAGE not in _STAGE_ORDER:
    raise RuntimeError("readiness-v38 lacks the attribution-bound G16 curve lock")
_TERMINAL_INDEX = _STAGE_ORDER.index(TERMINAL_STAGE)
ARMED_STAGES = _STAGE_ORDER[: _TERMINAL_INDEX + 1]
if _STAGE_ORDER[_TERMINAL_INDEX + 1 :] != PUBLICATION_STAGES:
    raise RuntimeError("readiness-v38 G16 publication tail changed")


class CorpusExecutorPipelineArmV29Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV29Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV29Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    result: dict[str, list[str]] = {}
    for key in compiler.READINESS_STAGES:
        argv = (rows.get(key) or {}).get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise CorpusExecutorPipelineArmV29Error(f"{key}: v38 command is missing or invalid")
        result[key] = list(argv)
    return result


def _normalize_g15_outcomes(paths: Sequence[str]) -> list[str]:
    normalized = sorted({str(path).strip() for path in paths if str(path).strip()})
    if not normalized:
        raise CorpusExecutorPipelineArmV29Error("an explicit fixed-G15 outcome path is required")
    for path in normalized:
        lowered = path.lower().replace("\\", "/")
        if "g16" in lowered or "grp16" in lowered:
            raise CorpusExecutorPipelineArmV29Error(
                f"G16 outcome path is forbidden in the G16-blind arm: {path}"
            )
    return normalized


def _flag_values(argv: Sequence[str], flag: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(argv):
        if token != flag:
            continue
        if index + 1 >= len(argv) or not argv[index + 1]:
            raise CorpusExecutorPipelineArmV29Error(f"g15_publication: {flag} lacks a value")
        values.append(str(argv[index + 1]))
    return values


def _expected_g15_outcomes(commands: Mapping[str, Sequence[str]]) -> list[str]:
    values = _flag_values(list(commands.get("g15_publication") or []), "--actual")
    if len(values) != 1:
        raise CorpusExecutorPipelineArmV29Error(
            "g15_publication must bind exactly one fixed outcome through --actual"
        )
    return _normalize_g15_outcomes(values)


def _validated_compiled(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    source_plan = copy.deepcopy(dict(plan))
    source_receipt = copy.deepcopy(dict(receipt))
    commands = _commands(source_plan)
    try:
        compiler.validate_receipt(
            source_receipt, plan=source_plan, commands=commands, verify_files=False
        )
    except Exception as error:
        raise CorpusExecutorPipelineArmV29Error(
            f"compiled readiness-v38 provenance is invalid: {error}"
        ) from error
    executor.validate_plan(source_plan)
    if source_plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV29Error(
            "compiled readiness-v38 plan already exposes outcome paths"
        )
    return source_plan, source_receipt, commands


def _set_outcomes(plan: Mapping[str, Any], outcomes: Sequence[str]) -> dict[str, Any]:
    result = copy.deepcopy(dict(plan))
    result.pop("fingerprint", None)
    result["outcome_paths"] = list(outcomes)
    result["fingerprint"] = compiler._fp(result)
    executor.validate_plan(result)
    return result


def _check_armed_policy(plan: Mapping[str, Any], outcomes: Sequence[str]) -> None:
    executor.validate_plan(plan)
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    if list(rows) != list(_STAGE_ORDER):
        raise CorpusExecutorPipelineArmV29Error("armed plan stage order mismatch")
    if plan.get("outcome_paths") != list(outcomes):
        raise CorpusExecutorPipelineArmV29Error("armed plan G15 outcome paths mismatch")
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True:
            raise CorpusExecutorPipelineArmV29Error(f"{key}: G16-blind stage is not armed")
    for key in PUBLICATION_STAGES:
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPipelineArmV29Error(f"{key}: G16 scoring must remain disabled")
    outcome_tokens = set(outcomes)
    for spec in readiness.STAGES:
        if spec.pre_outcome and outcome_tokens.intersection(rows[spec.key].get("argv") or []):
            raise CorpusExecutorPipelineArmV29Error(
                f"{spec.key}: outcome-blind command references fixed G15 outcomes"
            )
    for field in (
        "remote_presence_inferred",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if plan.get(field) is not False:
            raise CorpusExecutorPipelineArmV29Error(f"armed plan must keep {field}=false")
    if plan.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPipelineArmV29Error("one signal authority must be preserved")
    if plan.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPipelineArmV29Error("blind forecasts must remain immutable")
    if plan.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPipelineArmV29Error("CME event contracts must remain SHADOW")
    if plan.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPipelineArmV29Error("brokerage contract must remain tastytrade")


def _arm(
    plan: Mapping[str, Any], commands: Mapping[str, Sequence[str]], outcomes: Sequence[str]
) -> dict[str, Any]:
    armed = _set_outcomes(plan, outcomes)
    for key in ARMED_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=True)
    for key in PUBLICATION_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=False)
    compiler._validate_plan(armed, commands, compiled=False)
    _check_armed_policy(armed, outcomes)
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
    *,
    g15_outcome_paths: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, commands = _validated_compiled(
        compiled_plan, compiler_receipt
    )
    outcomes = _normalize_g15_outcomes(g15_outcome_paths)
    expected_outcomes = _expected_g15_outcomes(commands)
    if outcomes != expected_outcomes:
        raise CorpusExecutorPipelineArmV29Error(
            "explicit G15 outcomes do not match g15_publication --actual"
        )
    armed = _arm(source_plan, commands, outcomes)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": compiler._fp(list(_STAGE_ORDER)),
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "armed_plan_fingerprint": armed["fingerprint"],
        "commands_fingerprint": compiler._fp(commands),
        "compiled_plan": copy.deepcopy(source_plan),
        "compiler_receipt": copy.deepcopy(source_receipt),
        "g15_outcome_paths": list(outcomes),
        "g15_outcome_paths_fingerprint": compiler._fp(outcomes),
        "g15_publication_actual_paths_fingerprint": compiler._fp(expected_outcomes),
        "g15_outcomes_match_publication_command": True,
        "armed_stages": list(ARMED_STAGES),
        "terminal_stage": TERMINAL_STAGE,
        "publication_stages_disabled": list(PUBLICATION_STAGES),
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_and_ledger": True,
        "fixed_g15_outcomes_explicitly_bound": True,
        "g16_outcomes_forbidden": True,
        "g16_curve_locked_before_g16_scoring": True,
        "g16_counterfactual_publication_disabled": True,
        "g16_attribution_bound_publication_disabled": True,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_V38_G16_BLIND_CHAIN",
    }
    receipt["fingerprint"] = compiler._fp(receipt)
    validate_arm_receipt(receipt, armed_plan=armed)
    return armed, receipt


def validate_arm_receipt(
    value: Mapping[str, Any], *, armed_plan: Mapping[str, Any]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != compiler._fp(checked):
        raise CorpusExecutorPipelineArmV29Error("pipeline arm v29 fingerprint mismatch")
    checked["fingerprint"] = observed
    try:
        compiler._authority(checked, label="pipeline arm v29 receipt")
    except Exception as error:
        raise CorpusExecutorPipelineArmV29Error(str(error)) from error
    source_plan = checked.get("compiled_plan")
    source_receipt = checked.get("compiler_receipt")
    if not isinstance(source_plan, Mapping) or not isinstance(source_receipt, Mapping):
        raise CorpusExecutorPipelineArmV29Error("arm receipt lacks compiler provenance")
    validated_plan, validated_receipt, commands = _validated_compiled(
        source_plan, source_receipt
    )
    outcomes = _normalize_g15_outcomes(checked.get("g15_outcome_paths") or [])
    expected_outcomes = _expected_g15_outcomes(commands)
    if outcomes != expected_outcomes:
        raise CorpusExecutorPipelineArmV29Error(
            "receipt G15 outcomes do not match g15_publication --actual"
        )
    expected_plan = _arm(validated_plan, commands, outcomes)
    if copy.deepcopy(dict(armed_plan)) != expected_plan:
        raise CorpusExecutorPipelineArmV29Error(
            "armed plan differs from deterministic readiness-v38 transformation"
        )
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": compiler._fp(list(_STAGE_ORDER)),
        "compiled_plan_fingerprint": validated_plan["fingerprint"],
        "compiler_receipt_fingerprint": validated_receipt["fingerprint"],
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "commands_fingerprint": compiler._fp(commands),
        "g15_outcome_paths_fingerprint": compiler._fp(outcomes),
        "g15_publication_actual_paths_fingerprint": compiler._fp(expected_outcomes),
        "g15_outcomes_match_publication_command": True,
        "armed_stages": list(ARMED_STAGES),
        "terminal_stage": TERMINAL_STAGE,
        "publication_stages_disabled": list(PUBLICATION_STAGES),
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_and_ledger": True,
        "fixed_g15_outcomes_explicitly_bound": True,
        "g16_outcomes_forbidden": True,
        "g16_curve_locked_before_g16_scoring": True,
        "g16_counterfactual_publication_disabled": True,
        "g16_attribution_bound_publication_disabled": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPipelineArmV29Error(f"arm receipt field mismatch: {field}")
    _check_armed_policy(armed_plan, outcomes)
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-plan", type=Path, required=True)
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--g15-outcome", action="append", required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    armed, receipt = build_armed_plan(
        _load(args.compiled_plan),
        _load(args.compiler_receipt),
        g15_outcome_paths=args.g15_outcome,
    )
    _write(args.plan_out, armed)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
