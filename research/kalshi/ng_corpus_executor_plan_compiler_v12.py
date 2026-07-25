#!/usr/bin/env python3
"""Compile a dual-inspection historical corpus plan against readiness v16.

The broad inventory plan is inspected and definition-byte-bound before it may
prove one-year/spring-summer scope. A separate target-day plan is inspected into
separate catalog/audit/receipt artifacts and is the only receipt permitted to
feed basis regeneration and replay-catalog export.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as target_validation
import ng_corpus_inspection as inspection
import ng_corpus_inventory_plan_compiler as inventory
import ng_historical_refinement_executor_v13 as executor
import ng_historical_refinement_readiness_v16 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v12"
STATUS = "DUAL_INSPECTION_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (
    "corpus_coverage",
    "corpus_definition_byte_binding",
    "target_slice_coverage",
    "basis_inventory_regeneration",
    "replay_catalog_export",
    "broad_corpus_scope",
    "broad_corpus_exact_overlap",
    "broad_corpus_exact_partition",
)


class CorpusExecutorPlanCompilerV12Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV12Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV12Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used", "paid_live_data_assumed", "random_shuffle_used",
        "may_change_blind_forecast", "may_change_posterior", "may_update_ng_brain",
        "execution_authority", "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusExecutorPlanCompilerV12Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV12Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV12Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV12Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV12Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _source_ids(plan: Mapping[str, Any]) -> set[str]:
    return {
        str(source.get("source_id") or "")
        for corpus in plan.get("corpora") or []
        for source in corpus.get("sources") or []
    }


def validate_inputs(
    *,
    inventory_receipt: Mapping[str, Any],
    broad_plan: Mapping[str, Any],
    slice_bundle: Mapping[str, Any],
    target_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    compiled = inventory.validate_receipt(inventory_receipt)
    broad = inspection._validate_plan(broad_plan)
    if compiled.get("status") != inventory.READY_STATUS:
        raise CorpusExecutorPlanCompilerV12Error("broad inventory compiler receipt is not ready")
    if target_validation._canonical(compiled.get("compiled_plan")) != target_validation._canonical(broad):
        raise CorpusExecutorPlanCompilerV12Error("broad inspection plan differs from inventory compiler receipt")
    bundle, target = target_validation.validate_inputs(slice_bundle, target_plan)
    if broad.get("target_day_slices_only") is True:
        raise CorpusExecutorPlanCompilerV12Error("broad inspection plan may not be target slices only")
    if target.get("target_day_slices_only") is not True:
        raise CorpusExecutorPlanCompilerV12Error("target inspection plan must identify target-day slices")
    if target.get("broad_corpus_completeness_asserted") is not False:
        raise CorpusExecutorPlanCompilerV12Error("target inspection plan may not assert broad completeness")
    if broad.get("plan_fingerprint") == target.get("plan_fingerprint"):
        raise CorpusExecutorPlanCompilerV12Error("broad and target inspection plans must be distinct")
    if not _source_ids(broad) or not _source_ids(target):
        raise CorpusExecutorPlanCompilerV12Error("both inspection lanes require explicit sources")
    return (
        copy.deepcopy(dict(compiled)), copy.deepcopy(dict(broad)),
        copy.deepcopy(dict(bundle)), copy.deepcopy(dict(target)),
    )


def _commands(
    *, artifact_dir: Path, inventory_receipt_path: Path,
    broad_plan_path: Path, slice_bundle_path: Path, target_plan_path: Path,
) -> dict[str, list[str]]:
    root = artifact_dir.resolve(strict=False)
    return {
        "corpus_coverage": [
            "python", "ng_corpus_inspection.py", "inspect", "--plan", str(broad_plan_path.resolve(strict=False)),
            "--catalog-out", str(root / "ng_corpus_catalog.json"),
            "--audit-out", str(root / "ng_corpus_coverage_audit.json"),
            "--receipt-out", str(root / "ng_corpus_inspection_receipt.json"),
        ],
        "corpus_definition_byte_binding": [
            "python", "ng_corpus_definition_byte_binding_gate.py", "build",
            "--compiler-receipt", str(inventory_receipt_path.resolve(strict=False)),
            "--inspection-receipt", str(root / "ng_corpus_inspection_receipt.json"),
            "--out", str(root / "ng_corpus_definition_byte_binding_gate.json"),
        ],
        "target_slice_coverage": [
            "python", "ng_corpus_inspection.py", "inspect", "--plan", str(target_plan_path.resolve(strict=False)),
            "--catalog-out", str(root / "ng_target_slice_catalog.json"),
            "--audit-out", str(root / "ng_target_slice_coverage_audit.json"),
            "--receipt-out", str(root / "ng_target_slice_inspection_receipt.json"),
        ],
        "basis_inventory_regeneration": [
            "python", "ng_corpus_basis_inventory_regeneration.py",
            "--slice-bundle", str(slice_bundle_path.resolve(strict=False)),
            "--inspection-receipt", str(root / "ng_target_slice_inspection_receipt.json"),
            "--g15-out", str(root / "g15_mbo_l1_manifest.json"),
            "--g16-out", str(root / "g16_mbo_l1_inventory.json"),
            "--bundle-out", str(root / "ng_corpus_basis_inventory_regeneration.json"),
        ],
        "replay_catalog_export": [
            "python", "ng_corpus_replay_catalog_export.py",
            "--catalog", str(root / "ng_target_slice_catalog.json"),
            "--audit", str(root / "ng_target_slice_coverage_audit.json"),
            "--g15-inventory", str(root / "g15_mbo_l1_manifest.json"),
            "--g16-inventory", str(root / "g16_mbo_l1_inventory.json"),
            "--g15-out", str(root / "g15_exact_replay_catalog.json"),
            "--g16-out", str(root / "g16_exact_replay_catalog.json"),
            "--bundle-out", str(root / "ng_exact_replay_catalog_export.json"),
        ],
        "broad_corpus_scope": [
            "python", "ng_broad_corpus_scope_gate.py", "--inspection-receipt", str(root / "ng_corpus_inspection_receipt.json"),
            "--out", str(root / "ng_broad_corpus_scope_gate.json"),
        ],
        "broad_corpus_exact_overlap": [
            "python", "ng_broad_corpus_exact_overlap_gate.py", "--broad-scope-gate", str(root / "ng_broad_corpus_scope_gate.json"),
            "--out", str(root / "ng_broad_corpus_exact_overlap_gate.json"),
        ],
        "broad_corpus_exact_partition": [
            "python", "ng_broad_corpus_exact_partition_gate.py", "--exact-overlap-gate", str(root / "ng_broad_corpus_exact_overlap_gate.json"),
            "--out", str(root / "ng_broad_corpus_exact_partition_gate.json"),
        ],
    }


def _validate_plan(plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    expected = [spec.key for spec in readiness.STAGES]
    if keys != expected or keys[: len(CONFIGURED_STAGES)] != list(CONFIGURED_STAGES):
        raise CorpusExecutorPlanCompilerV12Error("execution plan is not the exact readiness-v16 contract")
    rows = {str(row.get("key")): row for row in rows_list}
    for index, key in enumerate(CONFIGURED_STAGES):
        row = rows[key]
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV12Error(f"{key}: command vector mismatch")
        expected_enabled = index == 0 if compiled else True
        if row.get("enabled") is not expected_enabled:
            raise CorpusExecutorPlanCompilerV12Error(f"{key}: enabled-state mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV12Error(f"{key}: corpus stage must remain pre-outcome")
    for spec in readiness.STAGES[len(CONFIGURED_STAGES):]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPlanCompilerV12Error(f"{spec.key}: downstream stage must remain disabled")
    return rows


def build_compiled_plan(
    *, artifact_dir: Path, working_directory: Path,
    inventory_receipt_path: Path, broad_plan_path: Path,
    slice_bundle_path: Path, target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compiled, broad, bundle, target = validate_inputs(
        inventory_receipt=_load(inventory_receipt_path), broad_plan=_load(broad_plan_path),
        slice_bundle=_load(slice_bundle_path), target_plan=_load(target_plan_path),
    )
    commands = _commands(
        artifact_dir=artifact_dir, inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path, slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    for index, key in enumerate(CONFIGURED_STAGES):
        plan = executor.configure_stage(plan, key, commands[key], enabled=index == 0)
    _validate_plan(plan, commands, compiled=True)
    receipt: dict[str, Any] = {
        "schema": SCHEMA, "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": target_validation._fp([spec.key for spec in readiness.STAGES]),
        "inventory_compiler_receipt_fingerprint": compiled["receipt_fingerprint"],
        "broad_inspection_plan_fingerprint": broad["plan_fingerprint"],
        "target_slice_bundle_fingerprint": bundle["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": target["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": target_validation._fp(commands),
        "broad_and_target_inspection_paths_separated": True,
        "definition_byte_binding_uses_broad_receipt": True,
        "basis_regeneration_uses_target_receipt": True,
        "replay_export_uses_target_catalog_and_audit": True,
        "target_slice_receipt_cannot_satisfy_broad_scope": True,
        "broad_receipt_cannot_satisfy_basis_regeneration": True,
        "actual_outcomes_used": False, "paid_live_data_assumed": False,
        "random_shuffle_used": False, "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True, "may_change_blind_forecast": False,
        "may_change_posterior": False, "may_update_ng_brain": False,
        "execution_authority": False, "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr", "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_BROAD_CORPUS_INSPECTION",
    }
    receipt["fingerprint"] = target_validation._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != target_validation._fp(checked):
        raise CorpusExecutorPlanCompilerV12Error("compiler v12 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v12 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS, "readiness_contract": readiness.SCHEMA,
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "configured_stages": list(CONFIGURED_STAGES), "enabled_stage": "corpus_coverage",
        "commands_fingerprint": target_validation._fp(commands),
        "broad_and_target_inspection_paths_separated": True,
        "definition_byte_binding_uses_broad_receipt": True,
        "basis_regeneration_uses_target_receipt": True,
        "replay_export_uses_target_catalog_and_audit": True,
        "target_slice_receipt_cannot_satisfy_broad_scope": True,
        "broad_receipt_cannot_satisfy_basis_regeneration": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV12Error(f"compiler v12 field mismatch: {field}")
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--inventory-compiler-receipt", type=Path, required=True)
    parser.add_argument("--broad-inspection-plan", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--target-inspection-plan", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir, working_directory=args.working_directory,
        inventory_receipt_path=args.inventory_compiler_receipt,
        broad_plan_path=args.broad_inspection_plan, slice_bundle_path=args.slice_bundle,
        target_plan_path=args.target_inspection_plan,
    )
    _write(args.plan_out, plan); _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
