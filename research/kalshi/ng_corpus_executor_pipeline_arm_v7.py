#!/usr/bin/env python3
"""Arm only the corpus prefix under readiness v10's G16 byte/window wall."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_pipeline_arm_v6 as v6
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v7 as compiler
import ng_historical_refinement_executor_v8 as executor
import ng_historical_refinement_readiness_v10 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v7"
STATUS = "G16_EXACT_PARTITION_REPLAY_WINDOW_BOUND_PIPELINE_ARMED"
ARMED_STAGES = compiler.CONFIGURED_STAGES
G16_PARTITION_REPLAY_STAGE = compiler.G16_PARTITION_REPLAY_STAGE
V6_SCHEMA = v6.SCHEMA


class CorpusExecutorPipelineArmV7Error(ValueError):
    """Raised when the readiness-v10 corpus pipeline cannot be armed safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmV7Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmV7Error(
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
def _v10_context() -> Iterator[None]:
    saved = (v6.compiler, v6.executor, v6.readiness)
    v6.compiler = compiler
    v6.executor = executor
    v6.readiness = readiness
    try:
        yield
    finally:
        v6.compiler, v6.executor, v6.readiness = saved


def _base_v6_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v6_fingerprint = base.pop("pipeline_arm_v6_fingerprint", None)
    for field in (
        "g16_exact_partition_replay_authorization_required_before_causal",
        "g16_exact_partition_replay_stage_present",
        "g16_exact_partition_replay_stage_enabled",
        "g16_exact_partition_replay_stage_pre_outcome",
        "g16_replay_bytes_and_state_windows_locked_before_causal",
        "after_g16_prepared_replay",
        "after_g16_partition_replay_authorization",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V6_SCHEMA
    base["status"] = v6.STATUS
    base["fingerprint"] = v6_fingerprint
    return base


def build_armed_plan(
    compiled_plan: Mapping[str, Any],
    compiler_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v10_context():
        armed_plan, base = v6.build_armed_plan(compiled_plan, compiler_receipt)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    g16_row = rows.get(G16_PARTITION_REPLAY_STAGE) or {}
    if g16_row.get("enabled") is not False:
        raise CorpusExecutorPipelineArmV7Error(
            "G16 partition/replay-window authorization must remain disabled"
        )
    if g16_row.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPipelineArmV7Error(
            "G16 partition/replay-window authorization must remain pre-outcome"
        )
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["pipeline_arm_v6_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    )
    receipt[
        "g16_exact_partition_replay_authorization_required_before_causal"
    ] = True
    receipt["g16_exact_partition_replay_stage_present"] = True
    receipt["g16_exact_partition_replay_stage_enabled"] = False
    receipt["g16_exact_partition_replay_stage_pre_outcome"] = True
    receipt[
        "g16_replay_bytes_and_state_windows_locked_before_causal"
    ] = True
    receipt[
        "after_g16_prepared_replay"
    ] = "RUN_EXACT_G16_PARTITION_REPLAY_AUTHORIZATION_BEFORE_CAUSAL"
    receipt[
        "after_g16_partition_replay_authorization"
    ] = "RUN_PRE_CUTOFF_G16_CAUSAL_ONLY_IF_AUTHORIZED"
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
        raise CorpusExecutorPipelineArmV7Error(
            "pipeline arm v7 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("status") != STATUS:
        raise CorpusExecutorPipelineArmV7Error("pipeline arm v7 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPipelineArmV7Error(
            "pipeline arm v7 readiness-v10 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        [spec.key for spec in readiness.STAGES]
    ):
        raise CorpusExecutorPipelineArmV7Error(
            "pipeline arm v7 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_partition_replay_authorization_required_before_causal",
        "g16_exact_partition_replay_stage_present",
        "g16_exact_partition_replay_stage_pre_outcome",
        "g16_replay_bytes_and_state_windows_locked_before_causal",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPipelineArmV7Error(
                f"pipeline arm v7 mandatory field mismatch: {field}"
            )
    if checked.get("g16_exact_partition_replay_stage_enabled") is not False:
        raise CorpusExecutorPipelineArmV7Error(
            "pipeline arm v7 may not enable G16 partition/replay-window authorization"
        )
    base = _base_v6_receipt(value)
    if base.get("fingerprint") != checked.get("pipeline_arm_v6_fingerprint"):
        raise CorpusExecutorPipelineArmV7Error(
            "embedded pipeline arm v6 fingerprint mismatch"
        )
    with _v10_context():
        v6.validate_arm_receipt(
            base,
            compiled_plan=compiled_plan,
            compiler_receipt=compiler_receipt,
            armed_plan=armed_plan,
        )
    executor.validate_plan(armed_plan)
    rows = {str(row.get("key")): row for row in armed_plan.get("stages") or []}
    if rows[G16_PARTITION_REPLAY_STAGE].get("enabled") is not False:
        raise CorpusExecutorPipelineArmV7Error(
            "armed corpus plan may not activate G16 partition/replay-window authorization"
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
