#!/usr/bin/env python3
"""Compile the stable corpus executor plan against exact-materialization readiness v28.

This module keeps the v27 runtime-observed inventory contract intact, but replaces the
validation-only local materialization seam with the operational exact-version S3
materializer. The prior compiler plan and receipt are embedded and revalidated so the
upgrade cannot discard any earlier provenance wall.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v22 as v22
import ng_corpus_s3_exact_materializer as exact_materializer
import ng_historical_refinement_executor_v24 as executor
import ng_historical_refinement_readiness_v28 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v23"
STATUS = "EXACT_S3_MATERIALIZATION_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v22.CONFIGURED_STAGES


class CorpusExecutorPlanCompilerV23Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV23Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV23Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v22._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV23Error(str(error)) from error


def _validate_exact_materialization(
    *,
    runtime_receipt: Mapping[str, Any],
    materialization_spec: Mapping[str, Any],
    materialization_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        checked = exact_materializer.validate_receipt(materialization_receipt)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV23Error(
            f"exact S3 materialization receipt is invalid: {error}"
        ) from error
    required = {
        "status": exact_materializer.READY_STATUS,
        "blockers": [],
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "identity_from_s3_keys_inferred": False,
    }
    for field, expected in required.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPlanCompilerV23Error(
                f"exact S3 materialization field mismatch: {field}"
            )
    if checked.get("runtime_inventory_capture_fingerprint") != runtime_receipt.get(
        "receipt_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization is not bound to the supplied runtime inventory receipt"
        )
    if checked.get("source_spec") != dict(materialization_spec):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization is not derived from the supplied materialization specification"
        )
    if checked.get("source_spec_fingerprint") != exact_materializer._fp(
        dict(materialization_spec)
    ):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization source-spec fingerprint mismatch"
        )
    if not checked.get("source_materializations_fingerprint"):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization lacks source-byte evidence fingerprint"
        )
    if not isinstance(checked.get("source_count"), int) or checked.get("source_count", 0) <= 0:
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization source count must be positive"
        )
    nested = checked.get("downstream_materialization_receipt")
    if not isinstance(nested, Mapping):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization lacks the downstream inspection-plan attestation"
        )
    if not checked.get("downstream_materialization_receipt_fingerprint"):
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization lacks downstream attestation fingerprint"
        )
    return copy.deepcopy(dict(checked))


@contextmanager
def _v28_context() -> Iterator[None]:
    saved = (v22.executor, v22.readiness)
    v22.executor, v22.readiness = executor, readiness
    try:
        yield
    finally:
        v22.executor, v22.readiness = saved


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
    with _v28_context():
        commands = v22._commands(
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
    root = artifact_dir.resolve(strict=False)
    commands["corpus_s3_materialization"] = [
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
        "--runtime-capture",
        str(capture_receipt_path.resolve(strict=False)),
        "--materialization-spec",
        str(materialization_spec_path.resolve(strict=False)),
        "--inventory-spec-out",
        str(root / "ng_corpus_inventory_spec.json"),
        "--plan-out",
        str(broad_plan_path.resolve(strict=False)),
        "--inventory-receipt-out",
        str(inventory_receipt_path.resolve(strict=False)),
        "--materialization-receipt-out",
        str(root / "ng_corpus_s3_materialization_attestation.json"),
        "--receipt-out",
        str(materialization_receipt_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    with _v28_context():
        try:
            rows = v22._validate_plan(plan, commands, compiled=compiled)
        except Exception as error:
            raise CorpusExecutorPlanCompilerV23Error(str(error)) from error
    row = rows["corpus_s3_materialization"]
    if row.get("expected_output") != "ng_corpus_s3_exact_materializer_receipt.json":
        raise CorpusExecutorPlanCompilerV23Error(
            "legacy validation-only materialization artifact was substituted"
        )
    if row.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    ]:
        raise CorpusExecutorPlanCompilerV23Error(
            "exact S3 materializer entrypoint was substituted"
        )
    if row.get("argv") != commands["corpus_s3_materialization"]:
        raise CorpusExecutorPlanCompilerV23Error(
            "exact S3 materializer command vector mismatch"
        )
    if row.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPlanCompilerV23Error(
            "exact S3 materialization must remain pre-outcome"
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
    runtime_receipt = _load(capture_receipt_path)
    materialization_spec = _load(materialization_spec_path)
    exact = _validate_exact_materialization(
        runtime_receipt=runtime_receipt,
        materialization_spec=materialization_spec,
        materialization_receipt=_load(materialization_receipt_path),
    )
    nested = copy.deepcopy(dict(exact["downstream_materialization_receipt"]))
    with tempfile.TemporaryDirectory(prefix="ng-v28-compiler-") as temporary:
        nested_path = Path(temporary) / "ng_corpus_s3_materialization_attestation.json"
        _write(nested_path, nested)
        with _v28_context():
            upstream_plan, upstream_receipt = v22.build_compiled_plan(
                artifact_dir=artifact_dir,
                working_directory=working_directory,
                resolution_spec_path=resolution_spec_path,
                expected_day_receipt_path=expected_day_receipt_path,
                finalization_receipt_path=finalization_receipt_path,
                resolution_receipt_path=resolution_receipt_path,
                capture_spec_path=capture_spec_path,
                capture_receipt_path=capture_receipt_path,
                materialization_spec_path=materialization_spec_path,
                materialization_receipt_path=nested_path,
                inventory_receipt_path=inventory_receipt_path,
                broad_plan_path=broad_plan_path,
                slice_bundle_path=slice_bundle_path,
                target_plan_path=target_plan_path,
            )
    upstream_commands = {
        str(row["key"]): list(row.get("argv") or [])
        for row in upstream_plan.get("stages") or []
        if str(row.get("key")) in CONFIGURED_STAGES
    }
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
    plan = copy.deepcopy(upstream_plan)
    plan = executor.configure_stage(
        plan,
        "corpus_s3_materialization",
        commands["corpus_s3_materialization"],
        enabled=False,
    )
    _validate_plan(plan, commands, compiled=True)
    receipt = copy.deepcopy(upstream_receipt)
    receipt.pop("fingerprint", None)
    receipt.update(
        {
            "schema": SCHEMA,
            "status": STATUS,
            "readiness_contract": readiness.SCHEMA,
            "readiness_stage_contract_fingerprint": fingerprinting._fp(
                [spec.key for spec in readiness.STAGES]
            ),
            "execution_plan_fingerprint": plan["fingerprint"],
            "commands_fingerprint": fingerprinting._fp(commands),
            "exact_materializer_receipt_fingerprint": exact["receipt_fingerprint"],
            "exact_materializer_source_spec_fingerprint": exact[
                "source_spec_fingerprint"
            ],
            "source_materializations_fingerprint": exact[
                "source_materializations_fingerprint"
            ],
            "exact_materialized_source_count": exact["source_count"],
            "downstream_materialization_receipt_fingerprint": exact[
                "downstream_materialization_receipt_fingerprint"
            ],
            "upstream_v27_compiler_receipt": copy.deepcopy(upstream_receipt),
            "upstream_v27_execution_plan": copy.deepcopy(upstream_plan),
            "upstream_v27_commands": copy.deepcopy(upstream_commands),
            "exact_version_get_object_required": True,
            "checksum_mode_enabled": True,
            "atomic_local_replacement_required": True,
            "identity_from_s3_keys_inferred": False,
            "exact_materialization_required_before_broad_inspection": True,
            "legacy_validation_only_materialization_rejected": True,
            "next_permitted_stage": "RUN_BRANCH_GUARDED_EXACT_MATERIALIZATION_CORPUS_PIPELINE",
        }
    )
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV23Error(
            "compiler v23 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v23 receipt")
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
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "identity_from_s3_keys_inferred": False,
        "exact_materialization_required_before_broad_inspection": True,
        "legacy_validation_only_materialization_rejected": True,
        "all_corpus_stages_pre_outcome": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV23Error(
                f"compiler v23 field mismatch: {field}"
            )
    for field in (
        "exact_materializer_receipt_fingerprint",
        "exact_materializer_source_spec_fingerprint",
        "source_materializations_fingerprint",
        "downstream_materialization_receipt_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV23Error(
                f"compiler v23 missing field: {field}"
            )
    if not isinstance(checked.get("exact_materialized_source_count"), int) or checked.get(
        "exact_materialized_source_count", 0
    ) <= 0:
        raise CorpusExecutorPlanCompilerV23Error(
            "compiler v23 exact materialized source count is invalid"
        )
    upstream_receipt = checked.get("upstream_v27_compiler_receipt")
    upstream_plan = checked.get("upstream_v27_execution_plan")
    upstream_commands = checked.get("upstream_v27_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV23Error(
            "compiler v23 lacks embedded v27 provenance"
        )
    with _v28_context():
        try:
            v22.validate_receipt(
                upstream_receipt,
                plan=upstream_plan,
                commands={str(key): list(argv) for key, argv in upstream_commands.items()},
            )
        except Exception as error:
            raise CorpusExecutorPlanCompilerV23Error(
                f"embedded v27 compiler provenance is invalid: {error}"
            ) from error
    if rows["corpus_expected_day_contract"].get("enabled") is not True:
        raise CorpusExecutorPlanCompilerV23Error(
            "compiled plan must enable only the expected-day contract first"
        )
    if rows["corpus_s3_materialization"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV23Error(
            "exact materialization may not be enabled before prior corpus contracts"
        )
    if rows["corpus_coverage"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV23Error(
            "broad inspection may not be enabled before exact materialization"
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
