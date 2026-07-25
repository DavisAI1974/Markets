#!/usr/bin/env python3
"""Compile the stable corpus executor plan against S3-captured readiness v21."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v15 as v15
import ng_corpus_s3_inventory_capture as capture
import ng_historical_refinement_executor_v17 as executor
import ng_historical_refinement_readiness_v21 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v16"
STATUS = "S3_CAPTURED_PLAN_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = ("corpus_s3_inventory_capture", *v15.CONFIGURED_STAGES)


class CorpusExecutorPlanCompilerV16Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV16Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV16Error(f"JSON artifact must be an object: {path}")
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
            raise CorpusExecutorPlanCompilerV16Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV16Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV16Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV16Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV16Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def validate_inputs(
    *,
    capture_spec: Mapping[str, Any],
    capture_receipt: Mapping[str, Any],
    materialization_spec: Mapping[str, Any],
    materialization_receipt: Mapping[str, Any],
    inventory_receipt: Mapping[str, Any],
    broad_plan: Mapping[str, Any],
    slice_bundle: Mapping[str, Any],
    target_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    captured = capture.validate_receipt(capture_receipt)
    if captured.get("status") != capture.READY_STATUS or captured.get("blockers") != []:
        raise CorpusExecutorPlanCompilerV16Error(
            "S3 inventory capture must be blocker-free before compiling the guarded plan"
        )
    if captured.get("source_spec") != dict(capture_spec):
        raise CorpusExecutorPlanCompilerV16Error(
            "capture receipt is not derived from the supplied live inventory specification"
        )
    if captured.get("source_spec_fingerprint") != capture._fp(capture_spec):
        raise CorpusExecutorPlanCompilerV16Error("capture source-spec fingerprint mismatch")
    if captured.get("materialization_spec") != dict(materialization_spec):
        raise CorpusExecutorPlanCompilerV16Error(
            "materialization specification is not the exact output of inventory capture"
        )
    if captured.get("materialization_spec_fingerprint") != capture._fp(materialization_spec):
        raise CorpusExecutorPlanCompilerV16Error(
            "captured materialization-spec fingerprint mismatch"
        )
    attested, compiled, broad, bundle, target = v15.validate_inputs(
        materialization_receipt=materialization_receipt,
        inventory_receipt=inventory_receipt,
        broad_plan=broad_plan,
        slice_bundle=slice_bundle,
        target_plan=target_plan,
    )
    if attested.get("source_spec_fingerprint") != captured.get("materialization_spec_fingerprint"):
        raise CorpusExecutorPlanCompilerV16Error(
            "materialization receipt is not bound to the captured materialization specification"
        )
    return captured, attested, compiled, broad, bundle, target


def _commands(
    *,
    artifact_dir: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v15._commands(
        artifact_dir=artifact_dir,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    commands["corpus_s3_inventory_capture"] = [
        "python",
        "ng_corpus_s3_inventory_capture.py",
        "capture",
        "--spec",
        str(capture_spec_path.resolve(strict=False)),
        "--materialization-spec-out",
        str(materialization_spec_path.resolve(strict=False)),
        "--receipt-out",
        str(capture_receipt_path.resolve(strict=False)),
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
        raise CorpusExecutorPlanCompilerV16Error(
            "execution plan is not the exact readiness-v21 S3-captured contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV16Error("duplicate execution-plan stage keys")
    positions = {key: keys.index(key) for key in CONFIGURED_STAGES}
    if not (
        positions["corpus_s3_inventory_capture"]
        < positions["corpus_s3_materialization"]
        < positions["corpus_coverage"]
        < positions["corpus_definition_byte_binding"]
        < positions["target_slice_coverage"]
        < positions["target_slice_broad_lineage"]
        < positions["target_slice_derivation"]
        < positions["basis_inventory_regeneration"]
        < positions["broad_corpus_scope"]
    ):
        raise CorpusExecutorPlanCompilerV16Error(
            "S3 inventory capture is not the first corpus-provenance stage"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for index, key in enumerate(CONFIGURED_STAGES):
        row = rows[key]
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV16Error(f"{key}: command vector mismatch")
        expected_enabled = index == 0 if compiled else True
        if row.get("enabled") is not expected_enabled:
            raise CorpusExecutorPlanCompilerV16Error(f"{key}: enabled-state mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV16Error(f"{key}: corpus stage must remain pre-outcome")
    for spec in readiness.STAGES[len(CONFIGURED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPlanCompilerV16Error(
                f"{spec.key}: downstream stage must remain disabled"
            )
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    captured, attested, compiled, broad, bundle, target = validate_inputs(
        capture_spec=_load(capture_spec_path),
        capture_receipt=_load(capture_receipt_path),
        materialization_spec=_load(materialization_spec_path),
        materialization_receipt=_load(materialization_receipt_path),
        inventory_receipt=_load(inventory_receipt_path),
        broad_plan=_load(broad_plan_path),
        slice_bundle=_load(slice_bundle_path),
        target_plan=_load(target_plan_path),
    )
    commands = _commands(
        artifact_dir=artifact_dir,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
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
        "readiness_stage_contract_fingerprint": fingerprinting._fp([spec.key for spec in readiness.STAGES]),
        "s3_inventory_capture_receipt_fingerprint": captured["receipt_fingerprint"],
        "captured_inventory_fingerprint": captured["captured_inventory_fingerprint"],
        "normalized_inventory_fingerprint": captured["normalized_inventory_fingerprint"],
        "captured_materialization_spec_fingerprint": captured["materialization_spec_fingerprint"],
        "s3_materialization_receipt_fingerprint": attested["receipt_fingerprint"],
        "s3_materialization_evidence_fingerprint": attested["materialization_evidence_fingerprint"],
        "inventory_compiler_receipt_fingerprint": compiled["receipt_fingerprint"],
        "broad_inspection_plan_fingerprint": broad["plan_fingerprint"],
        "target_slice_bundle_fingerprint": bundle["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": target["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_s3_inventory_capture",
        "commands_fingerprint": fingerprinting._fp(commands),
        "live_inventory_capture_required_before_materialization": True,
        "complete_latest_object_set_required": True,
        "checksum_enabled_head_required": True,
        "source_identity_may_not_be_inferred_from_s3_keys": True,
        "captured_materialization_spec_bound_to_materialization": True,
        "s3_materialization_required_before_inspection": True,
        "all_corpus_stages_pre_outcome": True,
        "target_bytes_rederived_from_definition_bound_broad_sources": True,
        "target_inspection_plan_bound_through_derivation": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_LIVE_S3_INVENTORY_CAPTURE",
        "s3_inventory_capture_output": str(root / "ng_corpus_s3_inventory_capture_attestation.json"),
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
        raise CorpusExecutorPlanCompilerV16Error(
            "compiler v16 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v16 receipt")
    rows = _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp([spec.key for spec in readiness.STAGES]),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_s3_inventory_capture",
        "commands_fingerprint": fingerprinting._fp(commands),
        "live_inventory_capture_required_before_materialization": True,
        "complete_latest_object_set_required": True,
        "checksum_enabled_head_required": True,
        "source_identity_may_not_be_inferred_from_s3_keys": True,
        "captured_materialization_spec_bound_to_materialization": True,
        "s3_materialization_required_before_inspection": True,
        "all_corpus_stages_pre_outcome": True,
        "target_bytes_rederived_from_definition_bound_broad_sources": True,
        "target_inspection_plan_bound_through_derivation": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV16Error(f"compiler v16 field mismatch: {field}")
    if rows["corpus_s3_inventory_capture"].get("enabled") is not True:
        raise CorpusExecutorPlanCompilerV16Error(
            "compiled plan must enable only live S3 inventory capture first"
        )
    if rows["corpus_s3_materialization"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV16Error(
            "materialization may not be enabled before live S3 inventory capture"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--capture-spec", type=Path, required=True)
    parser.add_argument("--capture-receipt", type=Path, required=True)
    parser.add_argument("--materialization-spec", type=Path, required=True)
    parser.add_argument("--materialization-receipt", type=Path, required=True)
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
        capture_spec_path=args.capture_spec,
        capture_receipt_path=args.capture_receipt,
        materialization_spec_path=args.materialization_spec,
        materialization_receipt_path=args.materialization_receipt,
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
