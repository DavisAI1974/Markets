#!/usr/bin/env python3
"""Compile readiness-v38 only after CLI and exact artifact-lineage contracts pass.

V30 proves that each configured extension command satisfies the installed argparse CLI
using help-only probes. V31 also requires every command to name each exact upstream
artifact required by readiness LINK_RULES, while exposing the raw G16 actual substrate
only to fixed-outcome G16 publication.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler_v30 as v30
import ng_v38_execution_command_lineage_gate as lineage

SCHEMA = "ng_corpus_executor_plan_compiler.v31"
STATUS = "G16_ATTRIBUTION_BOUND_V38_EXECUTOR_PLAN_CLI_AND_LINEAGE_COMPILED"

CorpusExecutorPlanCompilerV31Error = ValueError
READINESS_STAGES = v30.READINESS_STAGES
PREFIX_STAGES = v30.PREFIX_STAGES
EXTENSION_STAGES = v30.EXTENSION_STAGES
readiness = v30.readiness
executor = v30.executor
_fp = v30._fp


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV31Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV31Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    return v30._commands(plan)


def _authority(value: Mapping[str, Any]) -> None:
    try:
        v30._authority(value, label="compiler v31 receipt")
    except Exception as error:
        raise CorpusExecutorPlanCompilerV31Error(str(error)) from error
    for field in ("paid_live_data_assumed", "corpus_files_opened", "outcome_files_opened"):
        if value.get(field) is not False:
            raise CorpusExecutorPlanCompilerV31Error(f"compiler v31 must keep {field}=false")


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    upstream_plan: Mapping[str, Any],
    upstream_receipt: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
    command_contract: Mapping[str, Any],
    command_lineage: Mapping[str, Any],
    verify_files: bool = True,
    verify_runtime_contract: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        checked_lineage = lineage.validate_gate(
            command_lineage,
            extension_manifest=extension_manifest,
            artifact_dir=artifact_dir,
            require_ready=True,
        )
        plan, v30_receipt = v30.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            upstream_plan=upstream_plan,
            upstream_receipt=upstream_receipt,
            extension_manifest=extension_manifest,
            command_contract=command_contract,
            verify_files=verify_files,
            verify_runtime_contract=verify_runtime_contract,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV31Error(str(error)) from error

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": _fp(_commands(plan)),
        "v30_compiler_receipt_fingerprint": v30_receipt["fingerprint"],
        "command_contract_fingerprint": v30_receipt["command_contract_fingerprint"],
        "command_lineage_fingerprint": checked_lineage["fingerprint"],
        "extension_manifest_fingerprint": extension_manifest.get("fingerprint"),
        "g16_actual_path": checked_lineage.get("g16_actual_path"),
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
        "v30_compiler_receipt": copy.deepcopy(v30_receipt),
        "command_lineage": copy.deepcopy(checked_lineage),
        "working_directory": str(working_directory.resolve(strict=False)),
        "help_only_command_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
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
        "next_permitted_stage": "ARM_CLI_AND_LINEAGE_VALIDATED_V38_G16_BLIND_CHAIN",
    }
    receipt["fingerprint"] = _fp(receipt)
    validate_receipt(
        receipt,
        plan=plan,
        extension_manifest=extension_manifest,
        verify_files=False,
        verify_runtime_contract=False,
    )
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
    verify_files: bool = True,
    verify_runtime_contract: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPlanCompilerV31Error("compiler v31 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked)

    embedded_v30 = checked.get("v30_compiler_receipt")
    embedded_lineage = checked.get("command_lineage")
    if not isinstance(embedded_v30, Mapping) or not isinstance(embedded_lineage, Mapping):
        raise CorpusExecutorPlanCompilerV31Error("compiler v31 embedded provenance is incomplete")
    try:
        v30.validate_receipt(
            embedded_v30,
            plan=plan,
            verify_files=verify_files,
            verify_runtime_contract=verify_runtime_contract,
        )
        validated_lineage = lineage.validate_gate(
            embedded_lineage,
            extension_manifest=extension_manifest,
            artifact_dir=Path(str(plan["artifact_dir"])),
            require_ready=True,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV31Error(str(error)) from error

    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": _fp(_commands(plan)),
        "v30_compiler_receipt_fingerprint": embedded_v30.get("fingerprint"),
        "command_contract_fingerprint": embedded_v30.get("command_contract_fingerprint"),
        "command_lineage_fingerprint": validated_lineage.get("fingerprint"),
        "extension_manifest_fingerprint": extension_manifest.get("fingerprint"),
        "g16_actual_path": validated_lineage.get("g16_actual_path"),
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
        "help_only_command_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "next_permitted_stage": "ARM_CLI_AND_LINEAGE_VALIDATED_V38_G16_BLIND_CHAIN",
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV31Error(f"compiler v31 field mismatch: {field}")
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--upstream-plan", type=Path, required=True)
    parser.add_argument("--upstream-receipt", type=Path, required=True)
    parser.add_argument("--extension-manifest", type=Path, required=True)
    parser.add_argument("--command-contract", type=Path, required=True)
    parser.add_argument("--command-lineage", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--skip-file-verification", action="store_true")
    parser.add_argument("--skip-runtime-contract-verification", action="store_true")
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        upstream_plan=_load(args.upstream_plan),
        upstream_receipt=_load(args.upstream_receipt),
        extension_manifest=_load(args.extension_manifest),
        command_contract=_load(args.command_contract),
        command_lineage=_load(args.command_lineage),
        verify_files=not args.skip_file_verification,
        verify_runtime_contract=not args.skip_runtime_contract_verification,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(
        "[ng_corpus_executor_plan_compiler_v31] "
        f"{receipt['status']} actual={receipt['g16_actual_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
