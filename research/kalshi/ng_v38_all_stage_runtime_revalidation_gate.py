#!/usr/bin/env python3
"""Revalidate every configured readiness-v38 stage script immediately before execution.

The original runtime gate replays the v31 CLI/lineage checks and hashes the G16 extension
scripts. The guarded executor, however, begins with the historical corpus and G15 prefix.
This gate closes that prefix TOCTOU seam by hashing the executable Python source for every
configured stage in exact plan order, while recursively retaining the existing runtime
receipt. It opens code files only; corpus and outcome files remain untouched.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_historical_refinement_executor_v34 as executor
import ng_v38_execution_runtime_revalidation_gate as prior

SCHEMA = "ng_v38_all_stage_runtime_revalidation_gate.v1"
READY = "V38_ALL_CONFIGURED_STAGE_SCRIPTS_RUNTIME_REVALIDATED_READY"


class V38AllStageRuntimeRevalidationError(ValueError):
    """Raised when any configured stage script is missing, stale, or substituted."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38AllStageRuntimeRevalidationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise V38AllStageRuntimeRevalidationError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _authority(value: Mapping[str, Any]) -> None:
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
            raise V38AllStageRuntimeRevalidationError(
                f"all-stage runtime revalidation must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise V38AllStageRuntimeRevalidationError("one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise V38AllStageRuntimeRevalidationError("blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38AllStageRuntimeRevalidationError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38AllStageRuntimeRevalidationError("brokerage contract must remain tastytrade")


def _script_path(plan: Mapping[str, Any], row: Mapping[str, Any]) -> Path:
    argv = row.get("argv")
    key = str(row.get("key") or "<unknown>")
    if not isinstance(argv, list) or len(argv) < 2:
        raise V38AllStageRuntimeRevalidationError(f"{key}: configured command is missing")
    launcher = Path(str(argv[0])).name.lower()
    if not launcher.startswith("python"):
        raise V38AllStageRuntimeRevalidationError(
            f"{key}: canonical configured stage must use a Python launcher"
        )
    script_token = str(argv[1])
    if script_token.startswith("-") or not script_token.endswith(".py"):
        raise V38AllStageRuntimeRevalidationError(
            f"{key}: canonical Python script path is missing from argv"
        )
    workdir = Path(str(plan.get("working_directory") or ".")).expanduser().resolve(strict=False)
    cwd_value = Path(str(row.get("cwd") or ".")).expanduser()
    cwd = cwd_value if cwd_value.is_absolute() else workdir / cwd_value
    script = Path(script_token).expanduser()
    if not script.is_absolute():
        script = cwd / script
    return script.resolve(strict=False)


def _all_stage_script_sha256(plan: Mapping[str, Any]) -> dict[str, str]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise V38AllStageRuntimeRevalidationError(f"readiness-v38 plan is invalid: {error}") from error
    rows = list(plan.get("stages") or [])
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise V38AllStageRuntimeRevalidationError("execution plan stage row must be an object")
        key = str(row.get("key") or "")
        if not key or key in result:
            raise V38AllStageRuntimeRevalidationError("execution plan stage keys are missing or duplicated")
        path = _script_path(plan, row)
        if not path.is_file():
            raise V38AllStageRuntimeRevalidationError(f"{key}: configured stage script is missing: {path}")
        result[key] = _sha256_file(path)
    if len(result) != len(rows) or not rows:
        raise V38AllStageRuntimeRevalidationError(
            "all readiness-v38 stages must be configured and runtime-hashed"
        )
    return result


def _validate_extension_subset(
    all_hashes: Mapping[str, str], prior_receipt: Mapping[str, Any]
) -> None:
    prior_hashes = prior_receipt.get("runtime_script_sha256")
    if not isinstance(prior_hashes, Mapping):
        raise V38AllStageRuntimeRevalidationError(
            "prior runtime receipt lacks extension-stage script hashes"
        )
    expected = {
        key: all_hashes.get(key)
        for key in compiler.EXTENSION_STAGES
    }
    if None in expected.values() or dict(prior_hashes) != expected:
        raise V38AllStageRuntimeRevalidationError(
            "all-stage hashes disagree with the recursively validated extension hashes"
        )


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    prior_runtime_receipt: Mapping[str, Any],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    try:
        checked_prior = prior.validate_gate(
            prior_runtime_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38AllStageRuntimeRevalidationError(
            f"prior runtime revalidation is invalid: {error}"
        ) from error
    hashes = _all_stage_script_sha256(plan)
    _validate_extension_subset(hashes, checked_prior)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "prior_runtime_revalidation_receipt": copy.deepcopy(dict(checked_prior)),
        "prior_runtime_revalidation_fingerprint": checked_prior.get("fingerprint"),
        "all_stage_script_sha256": hashes,
        "all_stage_script_sha256_fingerprint": _fp(hashes),
        "configured_stage_count": len(hashes),
        "configured_stage_order": list(hashes),
        "historical_and_g15_prefix_scripts_rehashed": True,
        "g16_extension_scripts_rehashed": True,
        "all_configured_stage_scripts_rehashed": True,
        "runtime_revalidation_immediately_before_executor_delegation": True,
        "code_files_only": True,
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
        plan=plan,
        arm_receipt=arm_receipt,
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
        raise V38AllStageRuntimeRevalidationError(
            "all-stage runtime revalidation schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38AllStageRuntimeRevalidationError("all-stage runtime revalidation is not ready")
    for field in (
        "historical_and_g15_prefix_scripts_rehashed",
        "g16_extension_scripts_rehashed",
        "all_configured_stage_scripts_rehashed",
        "runtime_revalidation_immediately_before_executor_delegation",
        "code_files_only",
    ):
        if checked.get(field) is not True:
            raise V38AllStageRuntimeRevalidationError(f"mandatory field mismatch: {field}")
    embedded = checked.get("prior_runtime_revalidation_receipt")
    if not isinstance(embedded, Mapping):
        raise V38AllStageRuntimeRevalidationError("embedded prior runtime receipt is missing")
    try:
        checked_prior = prior.validate_gate(
            embedded,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38AllStageRuntimeRevalidationError(
            f"embedded prior runtime receipt is invalid: {error}"
        ) from error
    if checked.get("prior_runtime_revalidation_fingerprint") != checked_prior.get("fingerprint"):
        raise V38AllStageRuntimeRevalidationError("prior runtime fingerprint mismatch")
    hashes = checked.get("all_stage_script_sha256")
    if not isinstance(hashes, Mapping):
        raise V38AllStageRuntimeRevalidationError("all-stage script hash map is missing")
    if checked.get("configured_stage_order") != list(hashes):
        raise V38AllStageRuntimeRevalidationError("configured stage order mismatch")
    if checked.get("configured_stage_count") != len(hashes):
        raise V38AllStageRuntimeRevalidationError("configured stage count mismatch")
    if checked.get("all_stage_script_sha256_fingerprint") != _fp(hashes):
        raise V38AllStageRuntimeRevalidationError("all-stage script hash fingerprint mismatch")
    _validate_extension_subset(hashes, checked_prior)
    if checked.get("execution_plan_fingerprint") != plan.get("fingerprint"):
        raise V38AllStageRuntimeRevalidationError("execution plan fingerprint mismatch")
    if checked.get("pipeline_arm_receipt_fingerprint") != arm_receipt.get("fingerprint"):
        raise V38AllStageRuntimeRevalidationError("pipeline arm receipt fingerprint mismatch")
    if verify_runtime:
        rebuilt = build_gate(
            plan,
            arm_receipt,
            embedded,
            timeout_seconds=timeout_seconds,
        )
        if checked != rebuilt:
            raise V38AllStageRuntimeRevalidationError(
                "all-stage runtime revalidation differs from current deterministic reconstruction"
            )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--prior-runtime-revalidation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.prior_runtime_revalidation),
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, receipt)
    print(json.dumps({"status": receipt["status"], "fingerprint": receipt["fingerprint"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
