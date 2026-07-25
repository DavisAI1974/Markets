#!/usr/bin/env python3
"""Compile a plan-bound target-derivation corpus plan against readiness v19."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v13 as v13
import ng_historical_refinement_executor_v15 as executor
import ng_historical_refinement_readiness_v19 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v14"
STATUS = "PLAN_BOUND_TARGET_DERIVATION_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (
    "corpus_coverage",
    "corpus_definition_byte_binding",
    "target_slice_coverage",
    "target_slice_broad_lineage",
    "target_slice_derivation",
    "basis_inventory_regeneration",
    "replay_catalog_export",
    "broad_corpus_scope",
    "broad_corpus_exact_overlap",
    "broad_corpus_exact_partition",
)


class CorpusExecutorPlanCompilerV14Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV14Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV14Error(f"JSON artifact must be an object: {path}")
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
            raise CorpusExecutorPlanCompilerV14Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV14Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV14Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV14Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV14Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def validate_inputs(
    *,
    inventory_receipt: Mapping[str, Any],
    broad_plan: Mapping[str, Any],
    slice_bundle: Mapping[str, Any],
    target_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return v13.validate_inputs(
        inventory_receipt=inventory_receipt,
        broad_plan=broad_plan,
        slice_bundle=slice_bundle,
        target_plan=target_plan,
    )


def _commands(
    *,
    artifact_dir: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v13._commands(
        artifact_dir=artifact_dir,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    root = artifact_dir.resolve(strict=False)
    commands["target_slice_derivation"] = [
        "python",
        "ng_target_slice_derivation_gate_v2.py",
        "build",
        "--lineage-gate",
        str(root / "ng_target_slice_broad_lineage_gate.json"),
        "--out",
        str(root / "ng_target_slice_derivation_gate_v2.json"),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    expected = [spec.key for spec in readiness.STAGES]
    if keys != expected or keys[: len(CONFIGURED_STAGES)] != list(CONFIGURED_STAGES):
        raise CorpusExecutorPlanCompilerV14Error(
            "execution plan is not the exact readiness-v19 plan-bound derivation contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV14Error("duplicate execution-plan stage keys")
    positions = {key: keys.index(key) for key in CONFIGURED_STAGES}
    if not (
        positions["corpus_definition_byte_binding"]
        < positions["target_slice_coverage"]
        < positions["target_slice_broad_lineage"]
        < positions["target_slice_derivation"]
        < positions["basis_inventory_regeneration"]
        < positions["broad_corpus_scope"]
    ):
        raise CorpusExecutorPlanCompilerV14Error(
            "plan-bound target derivation is not between lineage and basis regeneration"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for index, key in enumerate(CONFIGURED_STAGES):
        row = rows[key]
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV14Error(f"{key}: command vector mismatch")
        expected_enabled = index == 0 if compiled else True
        if row.get("enabled") is not expected_enabled:
            raise CorpusExecutorPlanCompilerV14Error(f"{key}: enabled-state mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV14Error(f"{key}: corpus stage must remain pre-outcome")
    for spec in readiness.STAGES[len(CONFIGURED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPlanCompilerV14Error(
                f"{spec.key}: downstream stage must remain disabled"
            )
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compiled, broad, bundle, target = validate_inputs(
        inventory_receipt=_load(inventory_receipt_path),
        broad_plan=_load(broad_plan_path),
        slice_bundle=_load(slice_bundle_path),
        target_plan=_load(target_plan_path),
    )
    commands = _commands(
        artifact_dir=artifact_dir,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    for index, key in enumerate(CONFIGURED_STAGES):
        plan = executor.configure_stage(plan, key, commands[key], enabled=index == 0)
    _validate_plan(plan, commands, compiled=True)
    root = artifact_dir.resolve(strict=False)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "inventory_compiler_receipt_fingerprint": compiled["receipt_fingerprint"],
        "broad_inspection_plan_fingerprint": broad["plan_fingerprint"],
        "target_slice_bundle_fingerprint": bundle["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": target["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": fingerprinting._fp(commands),
        "broad_and_target_inspection_paths_separated": True,
        "definition_byte_binding_uses_broad_receipt": True,
        "target_slice_broad_lineage_required": True,
        "target_slice_derivation_required": True,
        "target_slice_derivation_stage_present": True,
        "target_slice_derivation_stage_enabled": False,
        "target_slice_derivation_stage_pre_outcome": True,
        "target_slice_derivation_output": str(root / "ng_target_slice_derivation_gate_v2.json"),
        "target_bytes_rederived_from_definition_bound_broad_sources": True,
        "target_inspection_plan_bound_through_derivation": True,
        "basis_regeneration_blocked_until_target_derivation": True,
        "basis_target_plan_substitution_rejected": True,
        "unrelated_or_metadata_only_target_route_rejected": True,
        "basis_regeneration_uses_target_receipt": True,
        "replay_export_uses_target_catalog_and_audit": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_BROAD_CORPUS_INSPECTION",
    }
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV14Error(
            "compiler v14 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v14 receipt")
    rows = _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": fingerprinting._fp(commands),
        "broad_and_target_inspection_paths_separated": True,
        "definition_byte_binding_uses_broad_receipt": True,
        "target_slice_broad_lineage_required": True,
        "target_slice_derivation_required": True,
        "target_slice_derivation_stage_present": True,
        "target_slice_derivation_stage_enabled": False,
        "target_slice_derivation_stage_pre_outcome": True,
        "target_bytes_rederived_from_definition_bound_broad_sources": True,
        "target_inspection_plan_bound_through_derivation": True,
        "basis_regeneration_blocked_until_target_derivation": True,
        "basis_target_plan_substitution_rejected": True,
        "unrelated_or_metadata_only_target_route_rejected": True,
        "basis_regeneration_uses_target_receipt": True,
        "replay_export_uses_target_catalog_and_audit": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV14Error(
                f"compiler v14 field mismatch: {field}"
            )
    if rows["target_slice_derivation"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV14Error(
            "compiled plan may not pre-enable target derivation"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--inventory-receipt", type=Path, required=True)
    parser.add_argument("--broad-plan", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--target-plan", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        inventory_receipt_path=args.inventory_receipt,
        broad_plan_path=args.broad_plan,
        slice_bundle_path=args.slice_bundle,
        target_plan_path=args.target_plan,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
