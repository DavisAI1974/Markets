#!/usr/bin/env python3
"""Arm only the corpus prefix under readiness v11's exact causal wall."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_pipeline_arm_v7 as v7
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v8 as compiler
import ng_historical_refinement_executor_v9 as executor
import ng_historical_refinement_readiness_v11 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v8"
STATUS = "G16_EXACT_COUNTERFACTUAL_CAUSAL_BOUND_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES
G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE = (
    compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE
)
V7_SCHEMA = v7.SCHEMA


class CorpusExecutorPipelineArmV8Error(ValueError):
    """Raised when the readiness-v11 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV8Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV8Error(
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
def _v11_context() -> Iterator[None]:
    saved = (v7.compiler, v7.executor, v7.readiness)
    v7.compiler = compiler
    v7.executor = executor
    v7.readiness = readiness
    try:
        yield
    finally:
        v7.compiler, v7.executor, v7.readiness = saved


def _base_v7_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v7_fingerprint = base.pop("pipeline_arm_v7_fingerprint", None)
    for field in (
        "g16_exact_counterfactual_causal_authorization_required_before_curve",
        "g16_exact_counterfactual_causal_stage_present",
        "g16_exact_counterfactual_causal_stage_enabled",
        "g16_exact_counterfactual_causal_stage_pre_outcome",
        "g16_exact_replay_provenance_and_lesson_lineage_locked_before_curve",
        "after_g16_counterfactual_causal_authorization",
        "after_g16_exact_counterfactual_causal_authorization",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V7_SCHEMA
    base["status"] = v7.STATUS
    base["fingerprint"] = v7_fingerprint
    return base


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v11_context():
        armed_plan, base = v7.build_armed_plan(compiled_plan, compiler_receipt)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    exact_row = rows.get(G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE) or {}
    if exact_row.get("enabled") is not False:
        raise CorpusExecutorPipelineArmV8Error(
            "G16 exact counterfactual causal authorization must remain disabled"
        )
    if exact_row.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPipelineArmV8Error(
            "G16 exact counterfactual causal authorization must remain pre-outcome"
        )
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["pipeline_arm_v7_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    )
    receipt[
        "g16_exact_counterfactual_causal_authorization_required_before_curve"
    ] = True
    receipt["g16_exact_counterfactual_causal_stage_present"] = True
    receipt["g16_exact_counterfactual_causal_stage_enabled"] = False
    receipt["g16_exact_counterfactual_causal_stage_pre_outcome"] = True
    receipt[
        "g16_exact_replay_provenance_and_lesson_lineage_locked_before_curve"
    ] = True
    receipt[
        "after_g16_counterfactual_causal_authorization"
    ] = "RUN_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZATION_BEFORE_CURVE"
    receipt[
        "after_g16_exact_counterfactual_causal_authorization"
    ] = "RUN_OUTCOME_BLIND_G16_CURVE_ONLY_IF_AUTHORIZED"
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
        raise CorpusExecutorPipelineArmV8Error(
            "pipeline arm v8 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("status") != STATUS:
        raise CorpusExecutorPipelineArmV8Error("pipeline arm v8 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV8Error(
            "pipeline arm v8 readiness-v11 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    ):
        raise CorpusExecutorPipelineArmV8Error(
            "pipeline arm v8 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_counterfactual_causal_authorization_required_before_curve",
        "g16_exact_counterfactual_causal_stage_present",
        "g16_exact_counterfactual_causal_stage_pre_outcome",
        "g16_exact_replay_provenance_and_lesson_lineage_locked_before_curve",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPipelineArmV8Error(
                f"pipeline arm v8 mandatory field mismatch: {field}"
            )
    if checked.get("g16_exact_counterfactual_causal_stage_enabled") is not False:
        raise CorpusExecutorPipelineArmV8Error(
            "pipeline arm v8 may not enable G16 exact counterfactual causal authorization"
        )
    base = _base_v7_receipt(value)
    if base.get("fingerprint") != checked.get("pipeline_arm_v7_fingerprint"):
        raise CorpusExecutorPipelineArmV8Error(
            "embedded pipeline arm v7 fingerprint mismatch"
        )
    with _v11_context():
        v7.validate_arm_receipt(
            base,
            compiled_plan=compiled_plan,
            compiler_receipt=compiler_receipt,
            armed_plan=armed_plan,
        )
    executor.validate_plan(armed_plan)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    if rows[G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE].get("enabled") is not False:
        raise CorpusExecutorPipelineArmV8Error(
            "armed corpus plan may not activate G16 exact counterfactual causal authorization"
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
