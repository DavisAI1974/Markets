#!/usr/bin/env python3
"""Compile the stable corpus plan against readiness v14 compiler attestations."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v9 as v9
import ng_historical_refinement_executor_v11 as executor
import ng_historical_refinement_readiness_v14 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v10"
STATUS = "G16_COMPILER_ATTESTED_FINAL_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v9.CONFIGURED_STAGES
G16_EXACT_COUNTERFACTUAL_CURVE_STAGE = v9.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE
G16_EXACT_CURVE_LOCK_STAGE = v9.G16_EXACT_CURVE_LOCK_STAGE
G16_LOCK_ATTESTATION_STAGE = "g16_exact_lock_context_compilation"
G16_EXACT_PUBLICATION_STAGE = v9.G16_EXACT_PUBLICATION_STAGE
G16_PUBLICATION_ATTESTATION_STAGE = "g16_exact_publication_context_compilation"
V9_SCHEMA = v9.SCHEMA


class CorpusExecutorPlanCompilerV10Error(ValueError):
    """Raised when a readiness-v14 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV10Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV10Error(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


@contextmanager
def _v14_context() -> Iterator[None]:
    saved = (v9.executor, v9.readiness)
    v9.executor = executor
    v9.readiness = readiness
    try:
        yield
    finally:
        v9.executor, v9.readiness = saved


def _commands(
    artifact_dir: Path, slice_path: Path, inspection_path: Path
) -> dict[str, list[str]]:
    return v9._commands(artifact_dir, slice_path, inspection_path)


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v14_boundary(
    plan: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    if keys != _stage_order():
        raise CorpusExecutorPlanCompilerV10Error(
            "execution plan is not the exact readiness-v14 stage contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV10Error("duplicate execution-plan stage keys")
    if not (
        keys.index(G16_EXACT_COUNTERFACTUAL_CURVE_STAGE)
        < keys.index(G16_EXACT_CURVE_LOCK_STAGE)
        < keys.index(G16_LOCK_ATTESTATION_STAGE)
        < keys.index(G16_EXACT_PUBLICATION_STAGE)
        < keys.index(G16_PUBLICATION_ATTESTATION_STAGE)
    ):
        raise CorpusExecutorPlanCompilerV10Error(
            "G16 exact curve, lock, compiler attestations, and publication are out of order"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_LOCK_ATTESTATION_STAGE,
        G16_EXACT_PUBLICATION_STAGE,
        G16_PUBLICATION_ATTESTATION_STAGE,
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPlanCompilerV10Error(
                f"{key} must remain disabled in the compiled corpus plan"
            )
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_LOCK_ATTESTATION_STAGE,
    ):
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV10Error(f"{key} must remain pre-outcome")
    for key in (G16_EXACT_PUBLICATION_STAGE, G16_PUBLICATION_ATTESTATION_STAGE):
        if rows[key].get("requires_fixed_outcomes") is not True:
            raise CorpusExecutorPlanCompilerV10Error(
                f"{key} must remain post-lock and fixed-outcome"
            )
    specs = {spec.key: spec for spec in readiness.STAGES}
    if (
        specs[G16_LOCK_ATTESTATION_STAGE].filename
        != "g16_exact_lock_context_compilation_attestation.json"
        or specs[G16_LOCK_ATTESTATION_STAGE].schema
        != "ng_g16_exact_context_compilation_attestation.v1"
        or specs[G16_PUBLICATION_ATTESTATION_STAGE].filename
        != "g16_exact_publication_context_compilation_attestation.json"
        or specs[G16_PUBLICATION_ATTESTATION_STAGE].schema
        != "ng_g16_exact_context_compilation_attestation.v1"
    ):
        raise CorpusExecutorPlanCompilerV10Error(
            "readiness v14 compiler-attestation artifacts are not canonical"
        )
    return rows


def _base_v9_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v9_fingerprint = base.pop("compiler_v9_fingerprint", None)
    for field in (
        "g16_exact_lock_context_compilation_required",
        "g16_exact_lock_context_compilation_stage_present",
        "g16_exact_lock_context_compilation_stage_enabled",
        "g16_exact_lock_context_compilation_stage_pre_outcome",
        "g16_exact_publication_context_compilation_required",
        "g16_exact_publication_context_compilation_stage_present",
        "g16_exact_publication_context_compilation_stage_enabled",
        "g16_exact_publication_context_compilation_requires_fixed_outcomes",
        "publication_attestation_binds_pre_outcome_lock",
        "readiness_v13_without_attestations_rejected",
        "exact_g16_lock_context_compilation_output",
        "exact_g16_publication_context_compilation_output",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V9_SCHEMA
    base["status"] = v9.STATUS
    base["fingerprint"] = v9_fingerprint
    return base


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v14_context():
        plan, base = v9.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            slice_bundle_path=slice_bundle_path,
            inspection_plan_path=inspection_plan_path,
        )
    rows = _validate_v14_boundary(plan)
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["compiler_v9_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        _stage_order()
    )
    receipt["g16_exact_lock_context_compilation_required"] = True
    receipt["g16_exact_lock_context_compilation_stage_present"] = True
    receipt["g16_exact_lock_context_compilation_stage_enabled"] = False
    receipt["g16_exact_lock_context_compilation_stage_pre_outcome"] = True
    receipt["g16_exact_publication_context_compilation_required"] = True
    receipt["g16_exact_publication_context_compilation_stage_present"] = True
    receipt["g16_exact_publication_context_compilation_stage_enabled"] = False
    receipt[
        "g16_exact_publication_context_compilation_requires_fixed_outcomes"
    ] = True
    receipt["publication_attestation_binds_pre_outcome_lock"] = True
    receipt["readiness_v13_without_attestations_rejected"] = True
    artifact_root = artifact_dir.resolve(strict=False)
    receipt["exact_g16_lock_context_compilation_output"] = str(
        artifact_root / "g16_exact_lock_context_compilation_attestation.json"
    )
    receipt["exact_g16_publication_context_compilation_output"] = str(
        artifact_root / "g16_exact_publication_context_compilation_attestation.json"
    )
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(
        receipt,
        plan=plan,
        commands=_commands(artifact_dir, slice_bundle_path, inspection_plan_path),
    )
    if not all(
        key in rows
        for key in (
            G16_LOCK_ATTESTATION_STAGE,
            G16_PUBLICATION_ATTESTATION_STAGE,
        )
    ):
        raise CorpusExecutorPlanCompilerV10Error(
            "compiled plan lost a compiler-attestation stage"
        )
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV10Error(
            "compiler v10 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    rows = _validate_v14_boundary(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV10Error("compiler v10 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV10Error(
            "readiness-v14 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        _stage_order()
    ):
        raise CorpusExecutorPlanCompilerV10Error(
            "readiness-v14 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_lock_context_compilation_required",
        "g16_exact_lock_context_compilation_stage_present",
        "g16_exact_lock_context_compilation_stage_pre_outcome",
        "g16_exact_publication_context_compilation_required",
        "g16_exact_publication_context_compilation_stage_present",
        "g16_exact_publication_context_compilation_requires_fixed_outcomes",
        "publication_attestation_binds_pre_outcome_lock",
        "readiness_v13_without_attestations_rejected",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPlanCompilerV10Error(
                f"compiler v10 mandatory field mismatch: {field}"
            )
    for field in (
        "g16_exact_lock_context_compilation_stage_enabled",
        "g16_exact_publication_context_compilation_stage_enabled",
    ):
        if checked.get(field) is not False:
            raise CorpusExecutorPlanCompilerV10Error(
                f"compiled corpus plan may not activate {field}"
            )
    base = _base_v9_receipt(value)
    if base.get("fingerprint") != checked.get("compiler_v9_fingerprint"):
        raise CorpusExecutorPlanCompilerV10Error(
            "embedded compiler v9 fingerprint mismatch"
        )
    with _v14_context():
        v9.validate_receipt(base, plan=plan, commands=commands)
    for key in (
        G16_LOCK_ATTESTATION_STAGE,
        G16_PUBLICATION_ATTESTATION_STAGE,
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPlanCompilerV10Error(
                f"corpus compilation may not arm {key}"
            )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--inspection-plan", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        slice_bundle_path=args.slice_bundle,
        inspection_plan_path=args.inspection_plan,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
