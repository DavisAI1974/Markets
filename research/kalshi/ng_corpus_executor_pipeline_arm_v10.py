#!/usr/bin/env python3
"""Arm only the corpus prefix under readiness v14 compiler attestations."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_pipeline_arm_v9 as v9
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v10 as compiler
import ng_historical_refinement_executor_v11 as executor
import ng_historical_refinement_readiness_v14 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v10"
STATUS = "G16_COMPILER_ATTESTED_FINAL_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES
G16_LOCK_ATTESTATION_STAGE = compiler.G16_LOCK_ATTESTATION_STAGE
G16_PUBLICATION_ATTESTATION_STAGE = compiler.G16_PUBLICATION_ATTESTATION_STAGE
V9_SCHEMA = v9.SCHEMA


class CorpusExecutorPipelineArmV10Error(ValueError):
    """Raised when the readiness-v14 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV10Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV10Error(
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
    saved = (v9.compiler, v9.executor, v9.readiness)
    v9.compiler = compiler
    v9.executor = executor
    v9.readiness = readiness
    try:
        yield
    finally:
        v9.compiler, v9.executor, v9.readiness = saved


def _base_v9_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v9_fingerprint = base.pop("pipeline_arm_v9_fingerprint", None)
    for field in (
        "g16_exact_lock_context_compilation_required_before_outcomes",
        "g16_exact_lock_context_compilation_stage_present",
        "g16_exact_lock_context_compilation_stage_enabled",
        "g16_exact_lock_context_compilation_stage_pre_outcome",
        "g16_exact_publication_context_compilation_required_after_publication",
        "g16_exact_publication_context_compilation_stage_present",
        "g16_exact_publication_context_compilation_stage_enabled",
        "g16_exact_publication_context_compilation_requires_fixed_outcomes",
        "publication_attestation_binds_pre_outcome_lock",
        "after_g16_exact_counterfactual_curve_lock",
        "after_g16_exact_lock_context_compilation",
        "after_g16_counterfactual_publication",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V9_SCHEMA
    base["status"] = v9.STATUS
    base["fingerprint"] = v9_fingerprint
    return base


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v14_context():
        armed_plan, base = v9.build_armed_plan(compiled_plan, compiler_receipt)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in (G16_LOCK_ATTESTATION_STAGE, G16_PUBLICATION_ATTESTATION_STAGE):
        if (rows.get(key) or {}).get("enabled") is not False:
            raise CorpusExecutorPipelineArmV10Error(
                f"{key} must remain disabled in the armed corpus plan"
            )
    if rows[G16_LOCK_ATTESTATION_STAGE].get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPipelineArmV10Error(
            "G16 lock compiler attestation must remain pre-outcome"
        )
    if rows[G16_PUBLICATION_ATTESTATION_STAGE].get(
        "requires_fixed_outcomes"
    ) is not True:
        raise CorpusExecutorPipelineArmV10Error(
            "G16 publication compiler attestation must remain fixed-outcome"
        )
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["pipeline_arm_v9_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    )
    receipt["g16_exact_lock_context_compilation_required_before_outcomes"] = True
    receipt["g16_exact_lock_context_compilation_stage_present"] = True
    receipt["g16_exact_lock_context_compilation_stage_enabled"] = False
    receipt["g16_exact_lock_context_compilation_stage_pre_outcome"] = True
    receipt[
        "g16_exact_publication_context_compilation_required_after_publication"
    ] = True
    receipt["g16_exact_publication_context_compilation_stage_present"] = True
    receipt["g16_exact_publication_context_compilation_stage_enabled"] = False
    receipt[
        "g16_exact_publication_context_compilation_requires_fixed_outcomes"
    ] = True
    receipt["publication_attestation_binds_pre_outcome_lock"] = True
    receipt[
        "after_g16_exact_counterfactual_curve_lock"
    ] = "ATTEST_EXACT_LOCK_CONTEXT_COMPILATION_BEFORE_OPENING_FIXED_OUTCOMES"
    receipt[
        "after_g16_exact_lock_context_compilation"
    ] = "OPEN_FIXED_G16_OUTCOMES_ONLY_FOR_SEPARATE_SCORING_AND_EXACT_PUBLICATION"
    receipt[
        "after_g16_counterfactual_publication"
    ] = "ATTEST_EXACT_PUBLICATION_CONTEXT_AND_BIND_PRE_OUTCOME_LOCK"
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
        raise CorpusExecutorPipelineArmV10Error(
            "pipeline arm v10 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("status") != STATUS:
        raise CorpusExecutorPipelineArmV10Error("pipeline arm v10 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV10Error(
            "pipeline arm v10 readiness-v14 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    ):
        raise CorpusExecutorPipelineArmV10Error(
            "pipeline arm v10 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_lock_context_compilation_required_before_outcomes",
        "g16_exact_lock_context_compilation_stage_present",
        "g16_exact_lock_context_compilation_stage_pre_outcome",
        "g16_exact_publication_context_compilation_required_after_publication",
        "g16_exact_publication_context_compilation_stage_present",
        "g16_exact_publication_context_compilation_requires_fixed_outcomes",
        "publication_attestation_binds_pre_outcome_lock",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPipelineArmV10Error(
                f"pipeline arm v10 mandatory field mismatch: {field}"
            )
    for field in (
        "g16_exact_lock_context_compilation_stage_enabled",
        "g16_exact_publication_context_compilation_stage_enabled",
    ):
        if checked.get(field) is not False:
            raise CorpusExecutorPipelineArmV10Error(
                f"pipeline arm v10 may not activate {field}"
            )
    base = _base_v9_receipt(value)
    if base.get("fingerprint") != checked.get("pipeline_arm_v9_fingerprint"):
        raise CorpusExecutorPipelineArmV10Error(
            "embedded pipeline arm v9 fingerprint mismatch"
        )
    with _v14_context():
        v9.validate_arm_receipt(
            base,
            compiled_plan=compiled_plan,
            compiler_receipt=compiler_receipt,
            armed_plan=armed_plan,
        )
    executor.validate_plan(armed_plan)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in (G16_LOCK_ATTESTATION_STAGE, G16_PUBLICATION_ATTESTATION_STAGE):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPipelineArmV10Error(
                f"armed corpus plan may not activate {key}"
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
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
