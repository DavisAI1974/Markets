#!/usr/bin/env python3
"""Compile the stable corpus executor plan against recursive-provenance readiness v29.

V28 operationalizes exact versioned S3 materialization. V29 inserts a standalone,
recursively validated provenance gate between exact materialization and broad byte
inspection so the durable plan cannot detach downloaded bytes from the complete
runtime-observed paginated inventory evidence that selected them.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v23 as v23
import ng_corpus_s3_materializer_provenance_gate as provenance_gate
import ng_historical_refinement_executor_v25 as executor
import ng_historical_refinement_readiness_v29 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v24"
STATUS = "RECURSIVE_S3_MATERIALIZER_PROVENANCE_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (
    *v23.CONFIGURED_STAGES[:5],
    "corpus_s3_materialization_provenance",
    *v23.CONFIGURED_STAGES[5:],
)


class CorpusExecutorPlanCompilerV24Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV24Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV24Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v23._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV24Error(str(error)) from error


def _validate_materializer_provenance(
    *,
    runtime_receipt: Mapping[str, Any],
    exact_receipt: Mapping[str, Any],
    provenance_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        checked = provenance_gate.validate_gate(provenance_receipt)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV24Error(
            f"S3 materializer provenance receipt is invalid: {error}"
        ) from error
    required = {
        "status": provenance_gate.READY_STATUS,
        "blockers": [],
        "runtime_capture_recursively_validated": True,
        "exact_materializer_recursively_validated": True,
        "complete_runtime_inventory_embedded": True,
        "exact_materialized_bytes_bound_to_runtime_inventory": True,
        "identity_from_s3_keys_inferred": False,
    }
    for field, expected in required.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPlanCompilerV24Error(
                f"S3 materializer provenance field mismatch: {field}"
            )
    if checked.get("runtime_capture_receipt") != dict(runtime_receipt):
        raise CorpusExecutorPlanCompilerV24Error(
            "materializer provenance does not embed the supplied runtime capture receipt"
        )
    if checked.get("exact_materializer_receipt") != dict(exact_receipt):
        raise CorpusExecutorPlanCompilerV24Error(
            "materializer provenance does not embed the supplied exact materializer receipt"
        )
    if checked.get("runtime_capture_receipt_fingerprint") != runtime_receipt.get(
        "receipt_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV24Error(
            "materializer provenance runtime-capture fingerprint mismatch"
        )
    if checked.get("exact_materializer_receipt_fingerprint") != exact_receipt.get(
        "receipt_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV24Error(
            "materializer provenance exact-materializer fingerprint mismatch"
        )
    if checked.get("exact_materializer_runtime_inventory_capture_fingerprint") != runtime_receipt.get(
        "receipt_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV24Error(
            "exact materializer is detached from the supplied runtime capture"
        )
    for field in (
        "source_materializations_fingerprint",
        "downstream_materialization_receipt_fingerprint",
        "canonical_inventory_spec_fingerprint",
        "materialization_evidence_fingerprint",
        "plan_fingerprint",
        "inventory_compiler_receipt_fingerprint",
        "provenance_lineage_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV24Error(
                f"materializer provenance lacks required field: {field}"
            )
    if not isinstance(checked.get("source_count"), int) or checked.get("source_count", 0) <= 0:
        raise CorpusExecutorPlanCompilerV24Error(
            "materializer provenance source count must be positive"
        )
    return copy.deepcopy(dict(checked))


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
    materialization_provenance_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v23._commands(
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
    commands["corpus_s3_materialization_provenance"] = [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
        "--runtime-capture",
        str(capture_receipt_path.resolve(strict=False)),
        "--exact-materializer",
        str(materialization_receipt_path.resolve(strict=False)),
        "--out",
        str(materialization_provenance_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV24Error(str(error)) from error
    rows = {
        str(row.get("key")): row
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    }
    if [str(row.get("key")) for row in plan.get("stages") or []] != [
        spec.key for spec in readiness.STAGES
    ]:
        raise CorpusExecutorPlanCompilerV24Error(
            "compiled plan does not use the readiness-v29 stage order"
        )
    for key in CONFIGURED_STAGES:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            raise CorpusExecutorPlanCompilerV24Error(f"configured stage missing: {key}")
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV24Error(f"{key}: command vector mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV24Error(f"{key}: must remain pre-outcome")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV24Error(
                    f"{key}: compiled enablement mismatch"
                )
    provenance = rows["corpus_s3_materialization_provenance"]
    if provenance.get("expected_output") != "ng_corpus_s3_materializer_provenance_gate.json":
        raise CorpusExecutorPlanCompilerV24Error(
            "recursive materializer provenance artifact was substituted"
        )
    if provenance.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    ]:
        raise CorpusExecutorPlanCompilerV24Error(
            "recursive materializer provenance entrypoint was substituted"
        )
    order = [spec.key for spec in readiness.STAGES]
    if not (
        order.index("corpus_s3_materialization")
        < order.index("corpus_s3_materialization_provenance")
        < order.index("corpus_coverage")
    ):
        raise CorpusExecutorPlanCompilerV24Error(
            "recursive materializer provenance must remain between materialization and inspection"
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
    materialization_provenance_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_receipt = _load(capture_receipt_path)
    exact_receipt = _load(materialization_receipt_path)
    provenance = _validate_materializer_provenance(
        runtime_receipt=runtime_receipt,
        exact_receipt=exact_receipt,
        provenance_receipt=_load(materialization_provenance_path),
    )
    upstream_plan, upstream_receipt = v23.build_compiled_plan(
        artifact_dir=artifact_dir,
        working_directory=working_directory,
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
        materialization_provenance_path=materialization_provenance_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    for key in CONFIGURED_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    _validate_plan(plan, commands, compiled=True)
    upstream_commands = {
        str(row["key"]): list(row.get("argv") or [])
        for row in upstream_plan.get("stages") or []
        if str(row.get("key")) in v23.CONFIGURED_STAGES
    }
    receipt: dict[str, Any] = {
        **copy.deepcopy(upstream_receipt),
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "materializer_provenance_receipt_fingerprint": provenance["fingerprint"],
        "runtime_capture_receipt_fingerprint": provenance[
            "runtime_capture_receipt_fingerprint"
        ],
        "exact_materializer_receipt_fingerprint": provenance[
            "exact_materializer_receipt_fingerprint"
        ],
        "source_materializations_fingerprint": provenance[
            "source_materializations_fingerprint"
        ],
        "materialized_source_count": provenance["source_count"],
        "provenance_lineage_fingerprint": provenance[
            "provenance_lineage_fingerprint"
        ],
        "inspection_plan_fingerprint": provenance["plan_fingerprint"],
        "inventory_compiler_receipt_fingerprint": provenance[
            "inventory_compiler_receipt_fingerprint"
        ],
        "upstream_v28_compiler_receipt": copy.deepcopy(upstream_receipt),
        "upstream_v28_execution_plan": copy.deepcopy(upstream_plan),
        "upstream_v28_commands": copy.deepcopy(upstream_commands),
        "runtime_capture_recursively_validated": True,
        "exact_materializer_recursively_validated": True,
        "complete_runtime_inventory_embedded": True,
        "recursive_materializer_provenance_required_before_broad_inspection": True,
        "all_corpus_stages_pre_outcome": True,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_RECURSIVE_PROVENANCE_CORPUS_PIPELINE",
    }
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV24Error(
            "compiler v24 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v24 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "runtime_capture_recursively_validated": True,
        "exact_materializer_recursively_validated": True,
        "complete_runtime_inventory_embedded": True,
        "recursive_materializer_provenance_required_before_broad_inspection": True,
        "all_corpus_stages_pre_outcome": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV24Error(
                f"compiler v24 field mismatch: {field}"
            )
    for field in (
        "materializer_provenance_receipt_fingerprint",
        "runtime_capture_receipt_fingerprint",
        "exact_materializer_receipt_fingerprint",
        "source_materializations_fingerprint",
        "provenance_lineage_fingerprint",
        "inspection_plan_fingerprint",
        "inventory_compiler_receipt_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV24Error(
                f"compiler v24 missing field: {field}"
            )
    if not isinstance(checked.get("materialized_source_count"), int) or checked.get(
        "materialized_source_count", 0
    ) <= 0:
        raise CorpusExecutorPlanCompilerV24Error(
            "compiler v24 materialized source count is invalid"
        )
    upstream_receipt = checked.get("upstream_v28_compiler_receipt")
    upstream_plan = checked.get("upstream_v28_execution_plan")
    upstream_commands = checked.get("upstream_v28_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV24Error(
            "compiler v24 lacks embedded v28 compiler provenance"
        )
    try:
        v23.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands={str(key): list(argv) for key, argv in upstream_commands.items()},
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV24Error(
            f"embedded v28 compiler provenance is invalid: {error}"
        ) from error
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
    parser.add_argument("--materialization-provenance", type=Path, required=True)
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
        materialization_provenance_path=args.materialization_provenance,
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
