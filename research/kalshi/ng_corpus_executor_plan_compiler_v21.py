#!/usr/bin/env python3
"""Compile the stable corpus executor plan against inventory-finalized readiness v26."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v20 as v20
import ng_corpus_inventory_finalization_contract as finalization
import ng_historical_refinement_executor_v22 as executor
import ng_historical_refinement_readiness_v26 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v21"
STATUS = "INVENTORY_FINALIZATION_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (
    "corpus_expected_day_contract",
    "corpus_inventory_finalization_contract",
    *v20.CONFIGURED_STAGES[1:],
)


class CorpusExecutorPlanCompilerV21Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV21Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV21Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v20._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV21Error(str(error)) from error


def validate_inputs(
    *,
    resolution_spec: Mapping[str, Any],
    expected_day_receipt: Mapping[str, Any],
    finalization_receipt: Mapping[str, Any],
    resolution_receipt: Mapping[str, Any],
    capture_spec: Mapping[str, Any],
    capture_receipt: Mapping[str, Any],
    materialization_spec: Mapping[str, Any],
    materialization_receipt: Mapping[str, Any],
    inventory_receipt: Mapping[str, Any],
    broad_plan: Mapping[str, Any],
    slice_bundle: Mapping[str, Any],
    target_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    contracted, resolved, captured, attested, compiled, broad, bundle, target = v20.validate_inputs(
        resolution_spec=resolution_spec,
        expected_day_receipt=expected_day_receipt,
        resolution_receipt=resolution_receipt,
        capture_spec=capture_spec,
        capture_receipt=capture_receipt,
        materialization_spec=materialization_spec,
        materialization_receipt=materialization_receipt,
        inventory_receipt=inventory_receipt,
        broad_plan=broad_plan,
        slice_bundle=slice_bundle,
        target_plan=target_plan,
    )
    finalized = finalization.validate_receipt(finalization_receipt)
    if (
        finalized.get("status") != finalization.READY_STATUS
        or finalized.get("blockers") != []
        or finalized.get("product_specific_lags_required") is not True
        or finalized.get("lag_policies_evidence_fingerprinted") is not True
        or finalized.get("inventory_must_follow_corpus_end_and_product_lag") is not True
    ):
        raise CorpusExecutorPlanCompilerV21Error(
            "inventory-finalization contract must be blocker-free before S3 resolution"
        )
    if finalized.get("source_spec") != dict(resolution_spec):
        raise CorpusExecutorPlanCompilerV21Error(
            "inventory-finalization receipt is not derived from the supplied resolution specification"
        )
    source_fp = finalized.get("source_spec_fingerprint")
    if source_fp != contracted.get("source_spec_fingerprint"):
        raise CorpusExecutorPlanCompilerV21Error(
            "inventory finalization is not bound to the expected-day contract"
        )
    if source_fp != resolved.get("source_spec_fingerprint"):
        raise CorpusExecutorPlanCompilerV21Error(
            "paginated S3 resolution is not bound to the finalized inventory snapshot"
        )
    return contracted, finalized, resolved, captured, attested, compiled, broad, bundle, target


def _commands(
    *,
    artifact_dir: Path,
    resolution_spec_path: Path,
    expected_day_receipt_path: Path,
    finalization_receipt_path: Path,
    resolution_receipt_path: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v20._commands(
        artifact_dir=artifact_dir,
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    commands["corpus_inventory_finalization_contract"] = [
        "python",
        "ng_corpus_inventory_finalization_contract.py",
        "build",
        "--spec",
        str(resolution_spec_path.resolve(strict=False)),
        "--out",
        str(finalization_receipt_path.resolve(strict=False)),
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
        raise CorpusExecutorPlanCompilerV21Error(
            "execution plan is not the exact readiness-v26 inventory-finalization contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV21Error("duplicate execution-plan stage keys")
    positions = {key: keys.index(key) for key in CONFIGURED_STAGES}
    required_order = (
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "target_slice_broad_lineage",
        "target_slice_derivation",
        "basis_inventory_regeneration",
        "broad_corpus_scope",
    )
    if [positions[key] for key in required_order] != sorted(positions[key] for key in required_order):
        raise CorpusExecutorPlanCompilerV21Error(
            "inventory finalization is not ordered between expected-day verification and all S3/G15 work"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    expected_contracts = {
        "corpus_expected_day_contract": (
            "ng_corpus_expected_day_contract_attestation.json",
            ["python", "ng_corpus_expected_day_contract.py", "build"],
        ),
        "corpus_inventory_finalization_contract": (
            "ng_corpus_inventory_finalization_contract.json",
            ["python", "ng_corpus_inventory_finalization_contract.py", "build"],
        ),
    }
    for key, (output, entrypoint) in expected_contracts.items():
        row = rows[key]
        if row.get("expected_output") != output:
            raise CorpusExecutorPlanCompilerV21Error(f"{key}: canonical artifact was substituted")
        if row.get("suggested_entrypoint") != entrypoint:
            raise CorpusExecutorPlanCompilerV21Error(f"{key}: suggested entrypoint was substituted")
    for index, key in enumerate(CONFIGURED_STAGES):
        row = rows[key]
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV21Error(f"{key}: command vector mismatch")
        expected_enabled = index == 0 if compiled else True
        if row.get("enabled") is not expected_enabled:
            raise CorpusExecutorPlanCompilerV21Error(f"{key}: enabled-state mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV21Error(f"{key}: corpus stage must remain pre-outcome")
    for spec in readiness.STAGES[len(CONFIGURED_STAGES) :]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPlanCompilerV21Error(
                f"{spec.key}: downstream stage must remain disabled"
            )
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    resolution_spec_path: Path,
    expected_day_receipt_path: Path,
    finalization_receipt_path: Path,
    resolution_receipt_path: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    (
        contracted,
        finalized,
        resolved,
        captured,
        attested,
        compiled_inventory,
        broad,
        bundle,
        target,
    ) = validate_inputs(
        resolution_spec=_load(resolution_spec_path),
        expected_day_receipt=_load(expected_day_receipt_path),
        finalization_receipt=_load(finalization_receipt_path),
        resolution_receipt=_load(resolution_receipt_path),
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
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        finalization_receipt_path=finalization_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
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
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "expected_day_receipt_fingerprint": contracted["receipt_fingerprint"],
        "expected_day_source_spec_fingerprint": contracted["source_spec_fingerprint"],
        "inventory_finalization_receipt_fingerprint": finalized["receipt_fingerprint"],
        "inventory_finalization_source_spec_fingerprint": finalized["source_spec_fingerprint"],
        "corpus_finalization_summaries_fingerprint": finalized[
            "corpus_finalization_summaries_fingerprint"
        ],
        "paginated_resolution_receipt_fingerprint": resolved["receipt_fingerprint"],
        "resolved_capture_spec_fingerprint": resolved["capture_spec_fingerprint"],
        "paginated_inventory_receipt_fingerprint": captured["receipt_fingerprint"],
        "captured_materialization_spec_fingerprint": captured[
            "materialization_spec_fingerprint"
        ],
        "s3_materialization_receipt_fingerprint": attested["receipt_fingerprint"],
        "inventory_compiler_receipt_fingerprint": compiled_inventory["receipt_fingerprint"],
        "broad_inspection_plan_fingerprint": broad["plan_fingerprint"],
        "target_slice_bundle_fingerprint": bundle["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": target["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "commands_fingerprint": fingerprinting._fp(commands),
        "complete_canonical_calendar_partition_required": True,
        "product_specific_finalization_lags_required": True,
        "lag_policy_evidence_fingerprints_required": True,
        "inventory_observation_after_corpus_end_and_lag_required": True,
        "finalization_contract_required_before_any_s3_request": True,
        "expected_day_contract_bound_to_finalization_contract": True,
        "s3_resolution_bound_to_finalized_inventory_snapshot": True,
        "complete_resolution_pagination_required": True,
        "complete_inventory_pagination_required": True,
        "paginated_inventory_required_before_materialization": True,
        "s3_materialization_required_before_inspection": True,
        "all_corpus_stages_pre_outcome": True,
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
        "next_permitted_stage": "RUN_BRANCH_GUARDED_INVENTORY_FINALIZED_CORPUS_PIPELINE",
        "inventory_finalization_contract_output": str(
            root / "ng_corpus_inventory_finalization_contract.json"
        ),
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
        raise CorpusExecutorPlanCompilerV21Error(
            "compiler v21 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v21 receipt")
    rows = _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "commands_fingerprint": fingerprinting._fp(commands),
        "complete_canonical_calendar_partition_required": True,
        "product_specific_finalization_lags_required": True,
        "lag_policy_evidence_fingerprints_required": True,
        "inventory_observation_after_corpus_end_and_lag_required": True,
        "finalization_contract_required_before_any_s3_request": True,
        "expected_day_contract_bound_to_finalization_contract": True,
        "s3_resolution_bound_to_finalized_inventory_snapshot": True,
        "complete_resolution_pagination_required": True,
        "complete_inventory_pagination_required": True,
        "paginated_inventory_required_before_materialization": True,
        "s3_materialization_required_before_inspection": True,
        "all_corpus_stages_pre_outcome": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV21Error(
                f"compiler v21 field mismatch: {field}"
            )
    if rows["corpus_expected_day_contract"].get("enabled") is not True:
        raise CorpusExecutorPlanCompilerV21Error(
            "compiled plan must enable only the expected-day contract first"
        )
    if rows["corpus_inventory_finalization_contract"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV21Error(
            "inventory finalization may not be enabled before expected-day verification"
        )
    if rows["corpus_s3_latest_version_resolution"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV21Error(
            "S3 resolution may not be enabled before inventory finalization"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--resolution-spec", type=Path, required=True)
    parser.add_argument("--expected-day-receipt", type=Path, required=True)
    parser.add_argument("--finalization-receipt", type=Path, required=True)
    parser.add_argument("--resolution-receipt", type=Path, required=True)
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
        resolution_spec_path=args.resolution_spec,
        expected_day_receipt_path=args.expected_day_receipt,
        finalization_receipt_path=args.finalization_receipt,
        resolution_receipt_path=args.resolution_receipt,
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
