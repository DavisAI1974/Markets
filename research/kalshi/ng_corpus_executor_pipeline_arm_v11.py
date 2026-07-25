#!/usr/bin/env python3
"""Arm the seven-stage corpus prefix under readiness v15 byte binding.

The durable plan arms byte inspection, definition-to-byte binding, basis
regeneration, replay export, and broad alignment gates under one immutable plan
and ledger. G15 replay, refinement, scoring, every G16 stage, and execution
remain disabled until the guarded executor observes upstream readiness.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_pipeline_arm_v6 as v6
import ng_corpus_executor_pipeline_arm_v10 as v10
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v11 as compiler
import ng_historical_refinement_executor_v12 as executor
import ng_historical_refinement_readiness_v15 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v11"
STATUS = "CORPUS_DEFINITION_BYTE_BOUND_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES
DEFINITION_BYTE_BINDING_STAGE = compiler.DEFINITION_BYTE_BINDING_STAGE
V10_SCHEMA = v10.SCHEMA


class CorpusExecutorPipelineArmV11Error(ValueError):
    """Raised when the readiness-v15 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV11Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV11Error(
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
def _v15_context() -> Iterator[None]:
    saved = (
        v10.compiler,
        v10.executor,
        v10.readiness,
        v6.ARMED_STAGES,
    )
    v10.compiler = compiler
    v10.executor = executor
    v10.readiness = readiness
    v6.ARMED_STAGES = ARMED_STAGES
    try:
        yield
    finally:
        (
            v10.compiler,
            v10.executor,
            v10.readiness,
            v6.ARMED_STAGES,
        ) = saved


def _base_v10_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v10_fingerprint = base.pop("pipeline_arm_v10_fingerprint", None)
    for field in (
        "seven_stage_corpus_prefix_armed",
        "corpus_definition_byte_binding_required_before_basis_regeneration",
        "corpus_definition_byte_binding_stage_present",
        "corpus_definition_byte_binding_stage_enabled",
        "corpus_definition_byte_binding_stage_pre_outcome",
        "inspection_only_route_rejected",
        "after_corpus_coverage",
        "after_corpus_definition_byte_binding",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V10_SCHEMA
    base["status"] = v10.STATUS
    base["fingerprint"] = v10_fingerprint
    return base


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v15_context():
        armed_plan, base = v10.build_armed_plan(compiled_plan, compiler_receipt)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    binding = rows.get(DEFINITION_BYTE_BINDING_STAGE) or {}
    if binding.get("enabled") is not True:
        raise CorpusExecutorPipelineArmV11Error(
            "definition-byte binding was not armed with the corpus prefix"
        )
    if binding.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPipelineArmV11Error(
            "definition-byte binding must remain pre-outcome"
        )
    order = [spec.key for spec in readiness.STAGES]
    if list(ARMED_STAGES) != order[: len(ARMED_STAGES)]:
        raise CorpusExecutorPipelineArmV11Error(
            "armed stages are not the exact readiness-v15 corpus prefix"
        )

    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["pipeline_arm_v10_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(order)
    receipt["seven_stage_corpus_prefix_armed"] = True
    receipt[
        "corpus_definition_byte_binding_required_before_basis_regeneration"
    ] = True
    receipt["corpus_definition_byte_binding_stage_present"] = True
    receipt["corpus_definition_byte_binding_stage_enabled"] = True
    receipt["corpus_definition_byte_binding_stage_pre_outcome"] = True
    receipt["inspection_only_route_rejected"] = True
    receipt[
        "after_corpus_coverage"
    ] = "RUN_DEFINITION_BYTE_BINDING_BEFORE_BASIS_REGENERATION"
    receipt[
        "after_corpus_definition_byte_binding"
    ] = "RUN_BASIS_REGENERATION_ONLY_IF_DEFINITION_BYTES_BOUND"
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_arm_receipt(
        receipt,
        compiled_plan=compiled_plan,
        compiler_receipt=compiler_receipt,
        armed_plan=armed_plan,
    )
    return armed_plan, receipt


def validate_arm_receipt(
    value: Mapping[str, Any],
    *,
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
    armed_plan: Mapping[str, Any],
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPipelineArmV11Error(
            "pipeline arm v11 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("status") != STATUS:
        raise CorpusExecutorPipelineArmV11Error("pipeline arm v11 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV11Error(
            "pipeline arm v11 readiness-v15 contract mismatch"
        )
    order = [spec.key for spec in readiness.STAGES]
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        order
    ):
        raise CorpusExecutorPipelineArmV11Error(
            "pipeline arm v11 stage-contract fingerprint mismatch"
        )
    for field in (
        "seven_stage_corpus_prefix_armed",
        "corpus_definition_byte_binding_required_before_basis_regeneration",
        "corpus_definition_byte_binding_stage_present",
        "corpus_definition_byte_binding_stage_enabled",
        "corpus_definition_byte_binding_stage_pre_outcome",
        "inspection_only_route_rejected",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPipelineArmV11Error(
                f"pipeline arm v11 mandatory field mismatch: {field}"
            )
    if checked.get("after_corpus_coverage") != (
        "RUN_DEFINITION_BYTE_BINDING_BEFORE_BASIS_REGENERATION"
    ):
        raise CorpusExecutorPipelineArmV11Error(
            "pipeline arm v11 coverage transition mismatch"
        )
    if checked.get("after_corpus_definition_byte_binding") != (
        "RUN_BASIS_REGENERATION_ONLY_IF_DEFINITION_BYTES_BOUND"
    ):
        raise CorpusExecutorPipelineArmV11Error(
            "pipeline arm v11 binding transition mismatch"
        )
    base = _base_v10_receipt(value)
    if base.get("fingerprint") != checked.get("pipeline_arm_v10_fingerprint"):
        raise CorpusExecutorPipelineArmV11Error(
            "embedded pipeline arm v10 fingerprint mismatch"
        )
    with _v15_context():
        v10.validate_arm_receipt(
            base,
            compiled_plan=compiled_plan,
            compiler_receipt=compiler_receipt,
            armed_plan=armed_plan,
        )
    executor.validate_plan(armed_plan)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in ARMED_STAGES:
        row = rows.get(key) or {}
        if row.get("enabled") is not True:
            raise CorpusExecutorPipelineArmV11Error(
                f"armed corpus prefix lost stage: {key}"
            )
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPipelineArmV11Error(
                f"armed corpus stage became post-outcome: {key}"
            )
    for spec in readiness.STAGES[len(ARMED_STAGES) :]:
        if (rows.get(spec.key) or {}).get("enabled"):
            raise CorpusExecutorPipelineArmV11Error(
                f"downstream stage was prematurely armed: {spec.key}"
            )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-plan", type=Path, required=True)
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    armed, receipt = build_armed_plan(
        _load(args.compiled_plan), _load(args.compiler_receipt)
    )
    _write(args.plan_out, armed)
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
