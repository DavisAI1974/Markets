#!/usr/bin/env python3
"""Arm the CLI- and lineage-validated readiness-v38 G16-blind chain.

This wrapper upgrades the durable arm from compiler v29 to compiler v31. It
recursively validates the command-contract and exact artifact-lineage receipts,
binds the one fixed G15 actual path used by G15 publication, arms every stage
through the immutable attribution-bound G16 curve lock, and leaves both fixed
G16 scoring/publication stages disabled.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_pipeline_arm_v29 as legacy_arm
import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v31"
STATUS = "G16_V38_CLI_AND_LINEAGE_VALIDATED_BLIND_CHAIN_ARMED"
TERMINAL_STAGE = legacy_arm.TERMINAL_STAGE
PUBLICATION_STAGES = legacy_arm.PUBLICATION_STAGES
_STAGE_ORDER = tuple(spec.key for spec in readiness.STAGES)
_TERMINAL_INDEX = _STAGE_ORDER.index(TERMINAL_STAGE)
ARMED_STAGES = _STAGE_ORDER[: _TERMINAL_INDEX + 1]
if _STAGE_ORDER[_TERMINAL_INDEX + 1 :] != PUBLICATION_STAGES:
    raise RuntimeError("readiness-v38 G16 publication tail changed")


class CorpusExecutorPipelineArmV31Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV31Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV31Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    try:
        return compiler._commands(plan)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(str(error)) from error


def _normalize_g15_outcomes(paths: Sequence[str]) -> list[str]:
    try:
        return legacy_arm._normalize_g15_outcomes(paths)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(str(error)) from error


def _expected_g15_outcomes(commands: Mapping[str, Sequence[str]]) -> list[str]:
    try:
        return legacy_arm._expected_g15_outcomes(commands)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(str(error)) from error


def _validated_compiled(
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    source_plan = copy.deepcopy(dict(plan))
    source_receipt = copy.deepcopy(dict(receipt))
    source_manifest = copy.deepcopy(dict(extension_manifest))
    commands = _commands(source_plan)
    try:
        checked_receipt = compiler.validate_receipt(
            source_receipt,
            plan=source_plan,
            extension_manifest=source_manifest,
            verify_files=False,
            verify_runtime_contract=False,
        )
        executor.validate_plan(source_plan)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(
            f"compiled readiness-v38 CLI/lineage provenance is invalid: {error}"
        ) from error
    if source_plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmV31Error(
            "compiled readiness-v38 plan already exposes outcome paths"
        )
    expected_manifest_fp = source_manifest.get("fingerprint")
    if checked_receipt.get("extension_manifest_fingerprint") != expected_manifest_fp:
        raise CorpusExecutorPipelineArmV31Error(
            "compiler v31 receipt does not bind the supplied extension manifest"
        )
    for field in (
        "all_required_cli_options_verified",
        "exact_command_source_bindings_verified",
        "g16_actual_exposed_only_at_counterfactual_publication",
    ):
        if checked_receipt.get(field) is not True:
            raise CorpusExecutorPipelineArmV31Error(
                f"compiler v31 receipt must keep {field}=true"
            )
    return source_plan, copy.deepcopy(dict(checked_receipt)), source_manifest, commands


def _set_outcomes(plan: Mapping[str, Any], outcomes: Sequence[str]) -> dict[str, Any]:
    result = copy.deepcopy(dict(plan))
    result.pop("fingerprint", None)
    result["outcome_paths"] = list(outcomes)
    result["fingerprint"] = compiler._fp(result)
    executor.validate_plan(result)
    return result


def _check_armed_policy(plan: Mapping[str, Any], outcomes: Sequence[str]) -> None:
    try:
        legacy_arm._check_armed_policy(plan, outcomes)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(str(error)) from error
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    if list(rows) != list(_STAGE_ORDER):
        raise CorpusExecutorPipelineArmV31Error("armed plan stage order mismatch")
    if rows[TERMINAL_STAGE].get("enabled") is not True:
        raise CorpusExecutorPipelineArmV31Error(
            "attribution-bound G16 curve lock must be armed"
        )
    for key in PUBLICATION_STAGES:
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPipelineArmV31Error(
                f"{key}: fixed G16 publication must remain disabled"
            )


def _arm(
    plan: Mapping[str, Any], commands: Mapping[str, Sequence[str]], outcomes: Sequence[str]
) -> dict[str, Any]:
    armed = _set_outcomes(plan, outcomes)
    for key in ARMED_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=True)
    for key in PUBLICATION_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=False)
    compiler.v30._validate_plan(armed, commands, compiled=False)
    _check_armed_policy(armed, outcomes)
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
    *,
    g15_outcome_paths: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, source_manifest, commands = _validated_compiled(
        compiled_plan, compiler_receipt, extension_manifest
    )
    outcomes = _normalize_g15_outcomes(g15_outcome_paths)
    expected_outcomes = _expected_g15_outcomes(commands)
    if outcomes != expected_outcomes:
        raise CorpusExecutorPipelineArmV31Error(
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
        "extension_manifest_fingerprint": source_manifest.get("fingerprint"),
        "command_contract_fingerprint": source_receipt.get("command_contract_fingerprint"),
        "command_lineage_fingerprint": source_receipt.get("command_lineage_fingerprint"),
        "armed_plan_fingerprint": armed["fingerprint"],
        "commands_fingerprint": compiler._fp(commands),
        "compiled_plan": copy.deepcopy(source_plan),
        "compiler_receipt": copy.deepcopy(source_receipt),
        "extension_manifest": copy.deepcopy(source_manifest),
        "g15_outcome_paths": list(outcomes),
        "g15_outcome_paths_fingerprint": compiler._fp(outcomes),
        "g15_publication_actual_paths_fingerprint": compiler._fp(expected_outcomes),
        "g15_outcomes_match_publication_command": True,
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_V38_CLI_LINEAGE_VALIDATED_G16_BLIND_CHAIN",
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
        raise CorpusExecutorPipelineArmV31Error("pipeline arm v31 fingerprint mismatch")
    checked["fingerprint"] = observed
    try:
        compiler._authority(checked)
    except Exception as error:
        raise CorpusExecutorPipelineArmV31Error(str(error)) from error
    source_plan = checked.get("compiled_plan")
    source_receipt = checked.get("compiler_receipt")
    source_manifest = checked.get("extension_manifest")
    if not all(isinstance(item, Mapping) for item in (source_plan, source_receipt, source_manifest)):
        raise CorpusExecutorPipelineArmV31Error(
            "arm receipt lacks compiler v31 and extension-manifest provenance"
        )
    validated_plan, validated_receipt, validated_manifest, commands = _validated_compiled(
        source_plan, source_receipt, source_manifest
    )
    outcomes = _normalize_g15_outcomes(checked.get("g15_outcome_paths") or [])
    expected_outcomes = _expected_g15_outcomes(commands)
    if outcomes != expected_outcomes:
        raise CorpusExecutorPipelineArmV31Error(
            "receipt G15 outcomes do not match g15_publication --actual"
        )
    expected_plan = _arm(validated_plan, commands, outcomes)
    if copy.deepcopy(dict(armed_plan)) != expected_plan:
        raise CorpusExecutorPipelineArmV31Error(
            "armed plan differs from deterministic compiler-v31 transformation"
        )
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": compiler._fp(list(_STAGE_ORDER)),
        "compiled_plan_fingerprint": validated_plan["fingerprint"],
        "compiler_receipt_fingerprint": validated_receipt["fingerprint"],
        "extension_manifest_fingerprint": validated_manifest.get("fingerprint"),
        "command_contract_fingerprint": validated_receipt.get("command_contract_fingerprint"),
        "command_lineage_fingerprint": validated_receipt.get("command_lineage_fingerprint"),
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "commands_fingerprint": compiler._fp(commands),
        "g15_outcome_paths_fingerprint": compiler._fp(outcomes),
        "g15_publication_actual_paths_fingerprint": compiler._fp(expected_outcomes),
        "g15_outcomes_match_publication_command": True,
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
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
            raise CorpusExecutorPipelineArmV31Error(f"arm receipt field mismatch: {field}")
    _check_armed_policy(armed_plan, outcomes)
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-plan", type=Path, required=True)
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--extension-manifest", type=Path, required=True)
    parser.add_argument("--g15-outcome", action="append", required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    armed, receipt = build_armed_plan(
        _load(args.compiled_plan),
        _load(args.compiler_receipt),
        _load(args.extension_manifest),
        g15_outcome_paths=args.g15_outcome,
    )
    _write(args.plan_out, armed)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
