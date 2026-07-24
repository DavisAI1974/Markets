#!/usr/bin/env python3
"""Arm only the corpus prefix under readiness v13's exact G16 final wall."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_pipeline_arm_v8 as v8
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v9 as compiler
import ng_historical_refinement_executor_v10 as executor
import ng_historical_refinement_readiness_v13 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v9"
STATUS = "G16_EXACT_CURVE_LOCK_PUBLICATION_BOUND_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES
G16_EXACT_COUNTERFACTUAL_CURVE_STAGE = compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE
G16_EXACT_CURVE_LOCK_STAGE = compiler.G16_EXACT_CURVE_LOCK_STAGE
G16_EXACT_PUBLICATION_STAGE = compiler.G16_EXACT_PUBLICATION_STAGE
V8_SCHEMA = v8.SCHEMA


class CorpusExecutorPipelineArmV9Error(ValueError):
    """Raised when the readiness-v13 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV9Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV9Error(
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
def _v13_context() -> Iterator[None]:
    saved = (v8.compiler, v8.executor, v8.readiness)
    v8.compiler = compiler
    v8.executor = executor
    v8.readiness = readiness
    try:
        yield
    finally:
        v8.compiler, v8.executor, v8.readiness = saved


def _base_v8_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v8_fingerprint = base.pop("pipeline_arm_v8_fingerprint", None)
    for field in (
        "g16_exact_counterfactual_curve_authorization_required_before_lock",
        "g16_exact_counterfactual_curve_stage_present",
        "g16_exact_counterfactual_curve_stage_enabled",
        "g16_exact_counterfactual_curve_stage_pre_outcome",
        "g16_exact_curve_lock_required_before_scoring",
        "g16_exact_curve_lock_stage_present",
        "g16_exact_curve_lock_stage_enabled",
        "g16_exact_curve_lock_stage_pre_outcome",
        "g16_exact_publication_required_after_scoring",
        "g16_exact_publication_stage_present",
        "g16_exact_publication_stage_enabled",
        "g16_exact_publication_stage_requires_fixed_outcomes",
        "legacy_g16_lock_publication_route_rejected",
        "after_g16_counterfactual_curve_authorization",
        "after_g16_exact_counterfactual_curve_authorization",
        "after_g16_exact_counterfactual_curve_lock",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V8_SCHEMA
    base["status"] = v8.STATUS
    base["fingerprint"] = v8_fingerprint
    return base


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v13_context():
        armed_plan, base = v8.build_armed_plan(compiled_plan, compiler_receipt)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_EXACT_PUBLICATION_STAGE,
    ):
        if (rows.get(key) or {}).get("enabled") is not False:
            raise CorpusExecutorPipelineArmV9Error(
                f"{key} must remain disabled in the armed corpus plan"
            )
    if rows[G16_EXACT_COUNTERFACTUAL_CURVE_STAGE].get(
        "requires_fixed_outcomes"
    ) is not False:
        raise CorpusExecutorPipelineArmV9Error(
            "G16 exact counterfactual curve authorization must remain pre-outcome"
        )
    if rows[G16_EXACT_CURVE_LOCK_STAGE].get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPipelineArmV9Error(
            "G16 exact curve lock must remain pre-outcome"
        )
    if rows[G16_EXACT_PUBLICATION_STAGE].get("requires_fixed_outcomes") is not True:
        raise CorpusExecutorPipelineArmV9Error(
            "G16 exact publication must remain fixed-outcome"
        )
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["pipeline_arm_v8_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    )
    receipt[
        "g16_exact_counterfactual_curve_authorization_required_before_lock"
    ] = True
    receipt["g16_exact_counterfactual_curve_stage_present"] = True
    receipt["g16_exact_counterfactual_curve_stage_enabled"] = False
    receipt["g16_exact_counterfactual_curve_stage_pre_outcome"] = True
    receipt["g16_exact_curve_lock_required_before_scoring"] = True
    receipt["g16_exact_curve_lock_stage_present"] = True
    receipt["g16_exact_curve_lock_stage_enabled"] = False
    receipt["g16_exact_curve_lock_stage_pre_outcome"] = True
    receipt["g16_exact_publication_required_after_scoring"] = True
    receipt["g16_exact_publication_stage_present"] = True
    receipt["g16_exact_publication_stage_enabled"] = False
    receipt["g16_exact_publication_stage_requires_fixed_outcomes"] = True
    receipt["legacy_g16_lock_publication_route_rejected"] = True
    receipt[
        "after_g16_counterfactual_curve_authorization"
    ] = "RUN_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZATION_BEFORE_LOCK"
    receipt[
        "after_g16_exact_counterfactual_curve_authorization"
    ] = "LOCK_EXACT_G16_CURVE_BEFORE_OPENING_FIXED_OUTCOMES"
    receipt[
        "after_g16_exact_counterfactual_curve_lock"
    ] = "OPEN_FIXED_G16_OUTCOMES_ONLY_FOR_SEPARATE_SCORING_AND_EXACT_PUBLICATION"
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
        raise CorpusExecutorPipelineArmV9Error(
            "pipeline arm v9 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("status") != STATUS:
        raise CorpusExecutorPipelineArmV9Error("pipeline arm v9 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV9Error(
            "pipeline arm v9 readiness-v13 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    ):
        raise CorpusExecutorPipelineArmV9Error(
            "pipeline arm v9 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_counterfactual_curve_authorization_required_before_lock",
        "g16_exact_counterfactual_curve_stage_present",
        "g16_exact_counterfactual_curve_stage_pre_outcome",
        "g16_exact_curve_lock_required_before_scoring",
        "g16_exact_curve_lock_stage_present",
        "g16_exact_curve_lock_stage_pre_outcome",
        "g16_exact_publication_required_after_scoring",
        "g16_exact_publication_stage_present",
        "g16_exact_publication_stage_requires_fixed_outcomes",
        "legacy_g16_lock_publication_route_rejected",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPipelineArmV9Error(
                f"pipeline arm v9 mandatory field mismatch: {field}"
            )
    for field in (
        "g16_exact_counterfactual_curve_stage_enabled",
        "g16_exact_curve_lock_stage_enabled",
        "g16_exact_publication_stage_enabled",
    ):
        if checked.get(field) is not False:
            raise CorpusExecutorPipelineArmV9Error(
                f"pipeline arm v9 may not activate {field}"
            )
    base = _base_v8_receipt(value)
    if base.get("fingerprint") != checked.get("pipeline_arm_v8_fingerprint"):
        raise CorpusExecutorPipelineArmV9Error(
            "embedded pipeline arm v8 fingerprint mismatch"
        )
    with _v13_context():
        v8.validate_arm_receipt(
            base,
            compiled_plan=compiled_plan,
            compiler_receipt=compiler_receipt,
            armed_plan=armed_plan,
        )
    executor.validate_plan(armed_plan)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_EXACT_PUBLICATION_STAGE,
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPipelineArmV9Error(
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
    print(
        json.dumps(
            {"status": receipt["status"], "plan": str(args.plan_out)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
