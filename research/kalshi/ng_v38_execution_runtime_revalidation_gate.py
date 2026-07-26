#!/usr/bin/env python3
"""Revalidate readiness-v38 command code and lineage immediately before execution.

Compiler v31 proves the installed argparse contracts and exact artifact bindings when the
plan is compiled. This gate closes the time-of-check/time-of-use seam by recursively
revalidating the armed plan, rerunning the help-only command probes, rehashing every
extension-stage script, and reconstructing exact command lineage immediately before the
branch-guarded executor is allowed to run one stage.

The gate never opens corpus or outcome files and cannot mutate forecasts, posteriors,
``ng_brain.json``, execution state, or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_pipeline_arm_v31 as arm
import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_v38_execution_command_contract_gate as command_gate
import ng_v38_execution_command_lineage_gate as lineage_gate

SCHEMA = "ng_v38_execution_runtime_revalidation_gate.v1"
READY = "V38_EXECUTION_RUNTIME_REVALIDATED_READY"


class V38ExecutionRuntimeRevalidationError(ValueError):
    """Raised when runtime command or lineage evidence is stale or inconsistent."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38ExecutionRuntimeRevalidationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise V38ExecutionRuntimeRevalidationError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any]) -> None:
    compiler._authority(value)
    for field in (
        "paid_live_data_assumed",
        "corpus_files_opened",
        "outcome_files_opened",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise V38ExecutionRuntimeRevalidationError(
                f"runtime revalidation must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation must preserve one signal authority"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation must preserve blind forecasts"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation must preserve tastytrade"
        )


def _validated_inputs(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    *,
    timeout_seconds: float,
    verify_runtime: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_plan = copy.deepcopy(dict(plan))
    source_arm = copy.deepcopy(dict(arm_receipt))
    try:
        checked_arm = arm.validate_arm_receipt(source_arm, armed_plan=source_plan)
    except Exception as error:
        raise V38ExecutionRuntimeRevalidationError(
            f"pipeline arm v31 provenance is invalid: {error}"
        ) from error

    compiler_receipt = checked_arm.get("compiler_receipt")
    extension_manifest = checked_arm.get("extension_manifest")
    if not isinstance(compiler_receipt, Mapping) or not isinstance(extension_manifest, Mapping):
        raise V38ExecutionRuntimeRevalidationError(
            "pipeline arm v31 lacks compiler receipt or extension manifest"
        )

    try:
        checked_compiler = compiler.validate_receipt(
            compiler_receipt,
            plan=source_plan,
            extension_manifest=extension_manifest,
            verify_files=True,
            verify_runtime_contract=verify_runtime,
        )
    except Exception as error:
        raise V38ExecutionRuntimeRevalidationError(
            f"runtime compiler-v31 validation failed: {error}"
        ) from error

    embedded_v30 = checked_compiler.get("v30_compiler_receipt")
    embedded_lineage = checked_compiler.get("command_lineage")
    if not isinstance(embedded_v30, Mapping) or not isinstance(embedded_lineage, Mapping):
        raise V38ExecutionRuntimeRevalidationError(
            "compiler v31 receipt lacks command-contract or lineage provenance"
        )
    command_contract = embedded_v30.get("command_contract")
    if not isinstance(command_contract, Mapping):
        raise V38ExecutionRuntimeRevalidationError(
            "compiler v30 receipt lacks command-contract evidence"
        )

    try:
        checked_contract = command_gate.validate_gate(
            command_contract,
            verify_runtime=verify_runtime,
            require_ready=True,
            timeout_seconds=timeout_seconds,
        )
        checked_lineage = lineage_gate.validate_gate(
            embedded_lineage,
            extension_manifest=extension_manifest,
            artifact_dir=Path(str(source_plan["artifact_dir"])),
            require_ready=True,
        )
    except Exception as error:
        raise V38ExecutionRuntimeRevalidationError(
            f"runtime command evidence is invalid: {error}"
        ) from error

    if checked_contract.get("extension_manifest_fingerprint") != extension_manifest.get(
        "fingerprint"
    ):
        raise V38ExecutionRuntimeRevalidationError(
            "runtime command contract does not bind the armed extension manifest"
        )
    if checked_lineage.get("extension_manifest_fingerprint") != extension_manifest.get(
        "fingerprint"
    ):
        raise V38ExecutionRuntimeRevalidationError(
            "runtime command lineage does not bind the armed extension manifest"
        )
    if checked_compiler.get("command_contract_fingerprint") != checked_contract.get(
        "fingerprint"
    ):
        raise V38ExecutionRuntimeRevalidationError(
            "compiler receipt command-contract fingerprint is stale"
        )
    if checked_compiler.get("command_lineage_fingerprint") != checked_lineage.get(
        "fingerprint"
    ):
        raise V38ExecutionRuntimeRevalidationError(
            "compiler receipt command-lineage fingerprint is stale"
        )

    return (
        source_plan,
        copy.deepcopy(dict(checked_arm)),
        copy.deepcopy(dict(checked_compiler)),
        copy.deepcopy(dict(checked_contract)),
        copy.deepcopy(dict(checked_lineage)),
    )


def _script_sha256_map(command_contract: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    probes = command_contract.get("stage_probes")
    if not isinstance(probes, list):
        raise V38ExecutionRuntimeRevalidationError(
            "runtime command contract lacks stage probes"
        )
    for probe in probes:
        if not isinstance(probe, Mapping):
            raise V38ExecutionRuntimeRevalidationError(
                "runtime command-contract probe must be an object"
            )
        stage_key = str(probe.get("stage_key"))
        sha256 = probe.get("script_sha256")
        if not stage_key or not isinstance(sha256, str) or len(sha256) != 64:
            raise V38ExecutionRuntimeRevalidationError(
                f"{stage_key or '<unknown>'}: runtime script SHA-256 is missing"
            )
        result[stage_key] = sha256
    if tuple(result) != tuple(compiler.EXTENSION_STAGES):
        raise V38ExecutionRuntimeRevalidationError(
            "runtime script SHA-256 map is incomplete or reordered"
        )
    return result


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    source_plan, checked_arm, checked_compiler, checked_contract, checked_lineage = (
        _validated_inputs(
            plan, arm_receipt, timeout_seconds=timeout_seconds, verify_runtime=True
        )
    )
    script_sha256 = _script_sha256_map(checked_contract)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "execution_plan_fingerprint": source_plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": checked_arm.get("fingerprint"),
        "compiler_v31_receipt_fingerprint": checked_compiler.get("fingerprint"),
        "extension_manifest_fingerprint": checked_arm.get("extension_manifest_fingerprint"),
        "command_contract_fingerprint": checked_contract.get("fingerprint"),
        "command_lineage_fingerprint": checked_lineage.get("fingerprint"),
        "runtime_script_sha256": script_sha256,
        "runtime_script_sha256_fingerprint": _fp(script_sha256),
        "runtime_help_probes_reexecuted": True,
        "runtime_script_bytes_rehashed": True,
        "runtime_command_lineage_reconstructed": True,
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
        "first_blocking_stage_only": True,
        "help_only_probe": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_FIRST_BLOCKING_STAGE",
    }
    result["fingerprint"] = _fp(result)
    validate_gate(
        result,
        plan=source_plan,
        arm_receipt=checked_arm,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    verify_runtime: bool = True,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38ExecutionRuntimeRevalidationError(
            "runtime revalidation is not ready"
        )
    mandatory = (
        "runtime_help_probes_reexecuted",
        "runtime_script_bytes_rehashed",
        "runtime_command_lineage_reconstructed",
        "all_required_cli_options_verified",
        "exact_command_source_bindings_verified",
        "g16_actual_exposed_only_at_counterfactual_publication",
        "first_blocking_stage_only",
        "help_only_probe",
    )
    for field in mandatory:
        if checked.get(field) is not True:
            raise V38ExecutionRuntimeRevalidationError(
                f"runtime revalidation must keep {field}=true"
            )

    if verify_runtime:
        rebuilt = build_gate(plan, arm_receipt, timeout_seconds=timeout_seconds)
        if checked != rebuilt:
            raise V38ExecutionRuntimeRevalidationError(
                "runtime revalidation differs from current deterministic reconstruction"
            )
    else:
        source_plan, checked_arm, checked_compiler, checked_contract, checked_lineage = (
            _validated_inputs(
                plan, arm_receipt, timeout_seconds=timeout_seconds, verify_runtime=False
            )
        )
        script_sha256 = _script_sha256_map(checked_contract)
        expected = {
            "execution_plan_fingerprint": source_plan.get("fingerprint"),
            "pipeline_arm_receipt_fingerprint": checked_arm.get("fingerprint"),
            "compiler_v31_receipt_fingerprint": checked_compiler.get("fingerprint"),
            "extension_manifest_fingerprint": checked_arm.get(
                "extension_manifest_fingerprint"
            ),
            "command_contract_fingerprint": checked_contract.get("fingerprint"),
            "command_lineage_fingerprint": checked_lineage.get("fingerprint"),
            "runtime_script_sha256": script_sha256,
            "runtime_script_sha256_fingerprint": _fp(script_sha256),
        }
        for field, expected_value in expected.items():
            if checked.get(field) != expected_value:
                raise V38ExecutionRuntimeRevalidationError(
                    f"runtime revalidation field mismatch: {field}"
                )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    result = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, result)
    print(
        "[ng_v38_execution_runtime_revalidation_gate] "
        f"{result['status']} scripts={len(result['runtime_script_sha256'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
