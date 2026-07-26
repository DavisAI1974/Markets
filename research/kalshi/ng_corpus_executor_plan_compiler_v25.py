#!/usr/bin/env python3
"""Compile the stable corpus executor plan against source-identity readiness v30.

V29 recursively binds runtime-observed S3 inventory to exact materialized bytes. V30
adds source-native identity attestation between recursive materializer provenance and
broad byte inspection, preventing an otherwise valid plan from trusting manifest-only
identity for dataset, publisher, instrument, raw symbol, definition period, or event
chronology.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v24 as v24
import ng_corpus_source_identity_attestation as identity_gate
import ng_historical_refinement_executor_v26 as executor
import ng_historical_refinement_readiness_v30 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v25"
STATUS = "SOURCE_NATIVE_IDENTITY_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (
    *v24.CONFIGURED_STAGES[:6],
    "corpus_source_identity_attestation",
    *v24.CONFIGURED_STAGES[6:],
)


class CorpusExecutorPlanCompilerV25Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV25Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV25Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v24._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV25Error(str(error)) from error


def _validate_source_identity(
    *,
    provenance_receipt: Mapping[str, Any],
    broad_plan: Mapping[str, Any],
    identity_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        checked = identity_gate.validate_attestation(identity_receipt)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV25Error(
            f"source-native identity receipt is invalid: {error}"
        ) from error
    required = {
        "status": identity_gate.READY_STATUS,
        "blockers": [],
        "all_source_native_identities_attested": True,
        "dataset_publisher_instrument_symbol_and_period_bound_to_source_bytes": True,
        "identity_inferred_from_filename_or_s3_key": False,
        "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
    }
    for field, expected in required.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPlanCompilerV25Error(
                f"source-native identity field mismatch: {field}"
            )
    if checked.get("materializer_provenance_receipt") != dict(provenance_receipt):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity does not embed the supplied materializer provenance receipt"
        )
    if checked.get("plan") != dict(broad_plan):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity does not embed the supplied broad inspection plan"
        )
    if checked.get("materializer_provenance_fingerprint") != provenance_receipt.get(
        "fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity materializer-provenance fingerprint mismatch"
        )
    if checked.get("plan_fingerprint") != broad_plan.get("plan_fingerprint"):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity broad-plan fingerprint mismatch"
        )
    if checked.get("source_materializations_fingerprint") != provenance_receipt.get(
        "source_materializations_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity source-materializations fingerprint mismatch"
        )
    for field in (
        "fingerprint",
        "source_identity_evidence_fingerprint",
        "source_materializations_fingerprint",
        "plan_fingerprint",
        "materializer_provenance_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV25Error(
                f"source-native identity lacks required field: {field}"
            )
    if not isinstance(checked.get("source_count"), int) or checked.get("source_count", 0) <= 0:
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity source count must be positive"
        )
    provenance_count = provenance_receipt.get("source_count")
    if isinstance(provenance_count, int) and checked.get("source_count") != provenance_count:
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity source count differs from materializer provenance"
        )
    _authority(checked, label="source-native identity receipt")
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
    source_identity_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v24._commands(
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
    commands["corpus_source_identity_attestation"] = [
        "python",
        "ng_corpus_source_identity_attestation.py",
        "build",
        "--provenance",
        str(materialization_provenance_path.resolve(strict=False)),
        "--plan",
        str(broad_plan_path.resolve(strict=False)),
        "--out",
        str(source_identity_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV25Error(str(error)) from error
    rows = {
        str(row.get("key")): row
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    }
    if [str(row.get("key")) for row in plan.get("stages") or []] != [
        spec.key for spec in readiness.STAGES
    ]:
        raise CorpusExecutorPlanCompilerV25Error(
            "compiled plan does not use the readiness-v30 stage order"
        )
    for key in CONFIGURED_STAGES:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            raise CorpusExecutorPlanCompilerV25Error(f"configured stage missing: {key}")
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV25Error(f"{key}: command vector mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV25Error(f"{key}: must remain pre-outcome")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV25Error(
                    f"{key}: compiled enablement mismatch"
                )
    identity = rows["corpus_source_identity_attestation"]
    if identity.get("expected_output") != "ng_corpus_source_identity_attestation.json":
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity artifact was substituted"
        )
    if identity.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_source_identity_attestation.py",
        "build",
    ]:
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity entrypoint was substituted"
        )
    order = [spec.key for spec in readiness.STAGES]
    if not (
        order.index("corpus_s3_materialization_provenance")
        < order.index("corpus_source_identity_attestation")
        < order.index("corpus_coverage")
        < order.index("corpus_definition_byte_binding")
    ):
        raise CorpusExecutorPlanCompilerV25Error(
            "source-native identity must remain between recursive provenance and broad inspection"
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
    source_identity_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    provenance = _load(materialization_provenance_path)
    broad_plan = _load(broad_plan_path)
    identity = _validate_source_identity(
        provenance_receipt=provenance,
        broad_plan=broad_plan,
        identity_receipt=_load(source_identity_path),
    )
    upstream_plan, upstream_receipt = v24.build_compiled_plan(
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
        materialization_provenance_path=materialization_provenance_path,
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
        source_identity_path=source_identity_path,
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
        if str(row.get("key")) in v24.CONFIGURED_STAGES
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
        "source_identity_receipt_fingerprint": identity["fingerprint"],
        "source_identity_evidence_fingerprint": identity[
            "source_identity_evidence_fingerprint"
        ],
        "materializer_provenance_receipt_fingerprint": identity[
            "materializer_provenance_fingerprint"
        ],
        "source_materializations_fingerprint": identity[
            "source_materializations_fingerprint"
        ],
        "inspection_plan_fingerprint": identity["plan_fingerprint"],
        "source_identity_count": identity["source_count"],
        "upstream_v29_compiler_receipt": copy.deepcopy(upstream_receipt),
        "upstream_v29_execution_plan": copy.deepcopy(upstream_plan),
        "upstream_v29_commands": copy.deepcopy(upstream_commands),
        "source_native_identity_required_before_broad_inspection": True,
        "dataset_schema_publisher_instrument_symbol_period_and_chronology_attested": True,
        "manifest_only_identity_rejected": True,
        "identity_may_not_be_inferred_from_filename_or_s3_key": True,
        "all_corpus_stages_pre_outcome": True,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_SOURCE_IDENTITY_CORPUS_PIPELINE",
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
        raise CorpusExecutorPlanCompilerV25Error(
            "compiler v25 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v25 receipt")
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
        "source_native_identity_required_before_broad_inspection": True,
        "dataset_schema_publisher_instrument_symbol_period_and_chronology_attested": True,
        "manifest_only_identity_rejected": True,
        "identity_may_not_be_inferred_from_filename_or_s3_key": True,
        "all_corpus_stages_pre_outcome": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV25Error(
                f"compiler v25 field mismatch: {field}"
            )
    for field in (
        "source_identity_receipt_fingerprint",
        "source_identity_evidence_fingerprint",
        "materializer_provenance_receipt_fingerprint",
        "source_materializations_fingerprint",
        "inspection_plan_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV25Error(
                f"compiler v25 missing field: {field}"
            )
    if not isinstance(checked.get("source_identity_count"), int) or checked.get(
        "source_identity_count", 0
    ) <= 0:
        raise CorpusExecutorPlanCompilerV25Error(
            "compiler v25 source identity count is invalid"
        )
    upstream_receipt = checked.get("upstream_v29_compiler_receipt")
    upstream_plan = checked.get("upstream_v29_execution_plan")
    upstream_commands = checked.get("upstream_v29_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV25Error(
            "compiler v25 lacks embedded v29 compiler provenance"
        )
    try:
        v24.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands={str(key): list(argv) for key, argv in upstream_commands.items()},
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV25Error(
            f"embedded v29 compiler provenance is invalid: {error}"
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
    parser.add_argument("--source-identity", type=Path, required=True)
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
        source_identity_path=args.source_identity,
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
