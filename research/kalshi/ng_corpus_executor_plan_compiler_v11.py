#!/usr/bin/env python3
"""Compile the stable corpus plan against readiness v15 byte-definition binding.

Readiness v15 inserts a mandatory pre-outcome stage immediately after byte-level
inspection. This compiler wires that stage into the durable historical plan and
keeps it disabled until corpus inspection has completed. Basis regeneration and
all downstream G15/G16 work therefore cannot follow an inspection-only route.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v6 as v6
import ng_corpus_executor_plan_compiler_v10 as v10
import ng_historical_refinement_executor_v12 as executor
import ng_historical_refinement_readiness_v15 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v11"
STATUS = "CORPUS_DEFINITION_BYTE_BOUND_EXECUTOR_PLAN_COMPILED"
DEFINITION_BYTE_BINDING_STAGE = "corpus_definition_byte_binding"
CONFIGURED_STAGES = (
    "corpus_coverage",
    DEFINITION_BYTE_BINDING_STAGE,
    "basis_inventory_regeneration",
    "replay_catalog_export",
    "broad_corpus_scope",
    "broad_corpus_exact_overlap",
    "broad_corpus_exact_partition",
)
V10_SCHEMA = v10.SCHEMA
_BASE_V6_COMMANDS = v6._commands


class CorpusExecutorPlanCompilerV11Error(ValueError):
    """Raised when a readiness-v15 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV11Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV11Error(
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


def _commands(
    artifact_dir: Path, slice_path: Path, inspection_path: Path
) -> dict[str, list[str]]:
    commands = _BASE_V6_COMMANDS(artifact_dir, slice_path, inspection_path)
    root = artifact_dir.resolve(strict=False)
    commands[DEFINITION_BYTE_BINDING_STAGE] = [
        "python",
        "ng_corpus_definition_byte_binding_gate.py",
        "build",
        "--compiler-receipt",
        str(root / "ng_corpus_inventory_plan_compiler.json"),
        "--inspection-receipt",
        str(root / "ng_corpus_inspection_receipt.json"),
        "--out",
        str(root / "ng_corpus_definition_byte_binding_gate.json"),
    ]
    return commands


@contextmanager
def _v15_context() -> Iterator[None]:
    saved = (
        v10.executor,
        v10.readiness,
        v6.CONFIGURED_STAGES,
        v6._commands,
    )
    v10.executor = executor
    v10.readiness = readiness
    v6.CONFIGURED_STAGES = CONFIGURED_STAGES
    v6._commands = _commands
    try:
        yield
    finally:
        (
            v10.executor,
            v10.readiness,
            v6.CONFIGURED_STAGES,
            v6._commands,
        ) = saved


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v15_boundary(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    if keys != _stage_order():
        raise CorpusExecutorPlanCompilerV11Error(
            "execution plan is not the exact readiness-v15 stage contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV11Error(
            "duplicate execution-plan stage keys"
        )
    if not (
        keys.index("corpus_coverage")
        < keys.index(DEFINITION_BYTE_BINDING_STAGE)
        < keys.index("basis_inventory_regeneration")
        < keys.index("broad_corpus_scope")
        < keys.index("g15_exact_replay")
    ):
        raise CorpusExecutorPlanCompilerV11Error(
            "definition-byte binding is not between inspection and basis regeneration"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    binding = rows[DEFINITION_BYTE_BINDING_STAGE]
    if binding.get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV11Error(
            "definition-byte binding must remain disabled in the compiled plan"
        )
    if binding.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPlanCompilerV11Error(
            "definition-byte binding must remain pre-outcome"
        )
    expected = commands.get(DEFINITION_BYTE_BINDING_STAGE)
    if not isinstance(expected, list) or binding.get("argv") != expected:
        raise CorpusExecutorPlanCompilerV11Error(
            "definition-byte binding command vector mismatch"
        )
    spec = next(
        spec
        for spec in readiness.STAGES
        if spec.key == DEFINITION_BYTE_BINDING_STAGE
    )
    if (
        spec.filename != "ng_corpus_definition_byte_binding_gate.json"
        or spec.schema != "ng_corpus_definition_byte_binding_gate.v1"
        or spec.pre_outcome is not True
    ):
        raise CorpusExecutorPlanCompilerV11Error(
            "readiness v15 definition-byte artifact contract is not canonical"
        )
    return rows


def _base_v10_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v10_fingerprint = base.pop("compiler_v10_fingerprint", None)
    for field in (
        "corpus_definition_byte_binding_required",
        "corpus_definition_byte_binding_stage_present",
        "corpus_definition_byte_binding_stage_enabled",
        "corpus_definition_byte_binding_stage_pre_outcome",
        "definition_byte_binding_precedes_basis_regeneration",
        "inspection_only_route_rejected",
        "readiness_v14_without_definition_byte_binding_rejected",
        "definition_byte_binding_inventory_compiler_receipt_input",
        "definition_byte_binding_inspection_receipt_input",
        "definition_byte_binding_output",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V10_SCHEMA
    base["status"] = v10.STATUS
    base["fingerprint"] = v10_fingerprint
    return base


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v15_context():
        plan, base = v10.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            slice_bundle_path=slice_bundle_path,
            inspection_plan_path=inspection_plan_path,
        )
        commands = _commands(artifact_dir, slice_bundle_path, inspection_plan_path)
        rows = _validate_v15_boundary(plan, commands)

    root = artifact_dir.resolve(strict=False)
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["compiler_v10_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        _stage_order()
    )
    receipt["corpus_definition_byte_binding_required"] = True
    receipt["corpus_definition_byte_binding_stage_present"] = (
        DEFINITION_BYTE_BINDING_STAGE in rows
    )
    receipt["corpus_definition_byte_binding_stage_enabled"] = False
    receipt["corpus_definition_byte_binding_stage_pre_outcome"] = True
    receipt["definition_byte_binding_precedes_basis_regeneration"] = True
    receipt["inspection_only_route_rejected"] = True
    receipt["readiness_v14_without_definition_byte_binding_rejected"] = True
    receipt["definition_byte_binding_inventory_compiler_receipt_input"] = str(
        root / "ng_corpus_inventory_plan_compiler.json"
    )
    receipt["definition_byte_binding_inspection_receipt_input"] = str(
        root / "ng_corpus_inspection_receipt.json"
    )
    receipt["definition_byte_binding_output"] = str(
        root / "ng_corpus_definition_byte_binding_gate.json"
    )
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
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
        raise CorpusExecutorPlanCompilerV11Error(
            "compiler v11 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    rows = _validate_v15_boundary(plan, commands)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV11Error("compiler v11 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV11Error(
            "compiler v11 readiness-v15 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        _stage_order()
    ):
        raise CorpusExecutorPlanCompilerV11Error(
            "compiler v11 readiness-stage fingerprint mismatch"
        )
    for field in (
        "corpus_definition_byte_binding_required",
        "corpus_definition_byte_binding_stage_present",
        "corpus_definition_byte_binding_stage_pre_outcome",
        "definition_byte_binding_precedes_basis_regeneration",
        "inspection_only_route_rejected",
        "readiness_v14_without_definition_byte_binding_rejected",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPlanCompilerV11Error(
                f"compiler v11 mandatory field mismatch: {field}"
            )
    if checked.get("corpus_definition_byte_binding_stage_enabled") is not False:
        raise CorpusExecutorPlanCompilerV11Error(
            "compiled corpus plan may not activate definition-byte binding"
        )
    root_command = commands[DEFINITION_BYTE_BINDING_STAGE]
    expected_paths = {
        "definition_byte_binding_inventory_compiler_receipt_input": root_command[4],
        "definition_byte_binding_inspection_receipt_input": root_command[6],
        "definition_byte_binding_output": root_command[8],
    }
    for field, expected in expected_paths.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPlanCompilerV11Error(
                f"compiler v11 path mismatch: {field}"
            )
    base = _base_v10_receipt(value)
    if base.get("fingerprint") != checked.get("compiler_v10_fingerprint"):
        raise CorpusExecutorPlanCompilerV11Error(
            "embedded compiler v10 fingerprint mismatch"
        )
    with _v15_context():
        v10.validate_receipt(base, plan=plan, commands=commands)
    if rows[DEFINITION_BYTE_BINDING_STAGE].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV11Error(
            "definition-byte stage was unexpectedly armed"
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
    print(
        json.dumps(
            {"status": receipt["status"], "plan": str(args.plan_out)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
