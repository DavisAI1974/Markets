#!/usr/bin/env python3
"""Compile readiness-v38 only after real stage CLI argument contracts pass.

V29 validates stage order, entrypoints, outputs, and authority policy. V30 additionally
requires a help-only command-contract receipt proving that each configured extension
command supplies the required options exposed by the installed argparse CLI.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v29 as v29
import ng_v38_execution_command_contract_gate as command_gate

SCHEMA = "ng_corpus_executor_plan_compiler.v30"
STATUS = "G16_ATTRIBUTION_BOUND_V38_EXECUTOR_PLAN_COMMAND_CONTRACT_COMPILED"

CorpusExecutorPlanCompilerV30Error = ValueError

# Compatibility exports consumed by versioned arm/preflight wrappers.
READINESS_STAGES = v29.READINESS_STAGES
PREFIX_STAGES = v29.PREFIX_STAGES
EXTENSION_STAGES = v29.EXTENSION_STAGES
readiness = v29.readiness
executor = v29.executor
_fp = v29._fp
_authority = v29._authority
_validate_plan = v29._validate_plan


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV30Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV30Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    return v29._commands_from_plan(plan, READINESS_STAGES)


def _validate_contract_link(
    contract: Mapping[str, Any],
    *,
    extension_manifest: Mapping[str, Any],
    working_directory: Path,
    verify_runtime: bool,
) -> dict[str, Any]:
    try:
        checked = command_gate.validate_gate(
            contract,
            verify_runtime=verify_runtime,
            require_ready=True,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV30Error(
            f"v38 execution command contract is invalid: {error}"
        ) from error
    if checked.get("extension_manifest_fingerprint") != extension_manifest.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV30Error(
            "command contract does not bind the supplied extension manifest"
        )
    expected_working_directory = str(working_directory.resolve(strict=False))
    if checked.get("working_directory") != expected_working_directory:
        raise CorpusExecutorPlanCompilerV30Error(
            "command contract working directory differs from the compiled plan"
        )
    if checked.get("help_only_probe") is not True:
        raise CorpusExecutorPlanCompilerV30Error("command contract must remain help-only")
    if checked.get("corpus_files_opened") is not False or checked.get("outcome_files_opened") is not False:
        raise CorpusExecutorPlanCompilerV30Error("command contract opened protected data")
    return checked


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    upstream_plan: Mapping[str, Any],
    upstream_receipt: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
    command_contract: Mapping[str, Any],
    verify_files: bool = True,
    verify_runtime_contract: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = v29.validate_extension_manifest(extension_manifest, require_ready=True)
    contract = _validate_contract_link(
        command_contract,
        extension_manifest=manifest,
        working_directory=working_directory,
        verify_runtime=verify_runtime_contract,
    )
    try:
        plan, v29_receipt = v29.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            upstream_plan=upstream_plan,
            upstream_receipt=upstream_receipt,
            extension_manifest=manifest,
            verify_files=verify_files,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV30Error(
            f"v29 plan compilation failed after command-contract validation: {error}"
        ) from error
    commands = _commands(plan)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": _fp(commands),
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "command_contract_fingerprint": contract["fingerprint"],
        "v29_compiler_receipt_fingerprint": v29_receipt["fingerprint"],
        "v29_compiler_receipt": copy.deepcopy(v29_receipt),
        "command_contract": copy.deepcopy(contract),
        "working_directory": str(working_directory.resolve(strict=False)),
        "all_required_cli_options_verified": True,
        "help_only_command_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "max_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "ARM_COMMAND_CONTRACT_VALIDATED_V38_G16_BLIND_CHAIN",
    }
    receipt["fingerprint"] = _fp(receipt)
    validate_receipt(
        receipt,
        plan=plan,
        verify_files=False,
        verify_runtime_contract=False,
    )
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    verify_files: bool = True,
    verify_runtime_contract: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPlanCompilerV30Error("compiler v30 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    try:
        _authority(checked, label="compiler v30 receipt")
    except Exception as error:
        raise CorpusExecutorPlanCompilerV30Error(str(error)) from error
    if checked.get("paid_live_data_assumed") is not False:
        raise CorpusExecutorPlanCompilerV30Error("compiler v30 cannot assume paid live data")
    commands = _commands(plan)
    _validate_plan(plan, commands, compiled=True)
    v29_receipt = checked.get("v29_compiler_receipt")
    contract = checked.get("command_contract")
    if not isinstance(v29_receipt, Mapping) or not isinstance(contract, Mapping):
        raise CorpusExecutorPlanCompilerV30Error("compiler v30 lacks embedded provenance")
    try:
        v29.validate_receipt(
            v29_receipt,
            plan=plan,
            commands=commands,
            verify_files=verify_files,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV30Error(
            f"embedded v29 compiler provenance is invalid: {error}"
        ) from error
    manifest = v29_receipt.get("extension_manifest")
    if not isinstance(manifest, Mapping):
        raise CorpusExecutorPlanCompilerV30Error("embedded v29 receipt lacks extension manifest")
    validated_contract = _validate_contract_link(
        contract,
        extension_manifest=manifest,
        working_directory=Path(str(checked.get("working_directory"))),
        verify_runtime=verify_runtime_contract,
    )
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": _fp(commands),
        "extension_manifest_fingerprint": manifest.get("fingerprint"),
        "command_contract_fingerprint": validated_contract.get("fingerprint"),
        "v29_compiler_receipt_fingerprint": v29_receipt.get("fingerprint"),
        "all_required_cli_options_verified": True,
        "help_only_command_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV30Error(f"compiler v30 field mismatch: {field}")
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--artifact-dir", type=Path, required=True)
    compile_parser.add_argument("--working-directory", type=Path, required=True)
    compile_parser.add_argument("--upstream-plan", type=Path, required=True)
    compile_parser.add_argument("--upstream-receipt", type=Path, required=True)
    compile_parser.add_argument("--extension-manifest", type=Path, required=True)
    compile_parser.add_argument("--command-contract", type=Path, required=True)
    compile_parser.add_argument("--plan-out", type=Path, required=True)
    compile_parser.add_argument("--receipt-out", type=Path, required=True)
    compile_parser.add_argument("--skip-file-verification", action="store_true")
    compile_parser.add_argument("--skip-runtime-contract-verification", action="store_true")
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        upstream_plan=_load(args.upstream_plan),
        upstream_receipt=_load(args.upstream_receipt),
        extension_manifest=_load(args.extension_manifest),
        command_contract=_load(args.command_contract),
        verify_files=not args.skip_file_verification,
        verify_runtime_contract=not args.skip_runtime_contract_verification,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(
        "[ng_corpus_executor_plan_compiler_v30] "
        f"{receipt['status']} stages={len(READINESS_STAGES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
