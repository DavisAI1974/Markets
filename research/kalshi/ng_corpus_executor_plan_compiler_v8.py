#!/usr/bin/env python3
"""Compile the stable corpus plan against readiness v11's exact causal wall."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v7 as v7
import ng_historical_refinement_executor_v9 as executor
import ng_historical_refinement_readiness_v11 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v8"
STATUS = "G16_EXACT_COUNTERFACTUAL_CAUSAL_BOUND_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v7.CONFIGURED_STAGES
PARTITION_REPLAY_STAGE = v7.PARTITION_REPLAY_STAGE
WINDOW_STAGE = v7.WINDOW_STAGE
G16_PARTITION_REPLAY_STAGE = v7.G16_PARTITION_REPLAY_STAGE
G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE = (
    "g16_exact_counterfactual_causal_authorization"
)
V7_SCHEMA = v7.SCHEMA


class CorpusExecutorPlanCompilerV8Error(ValueError):
    """Raised when a readiness-v11 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV8Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV8Error(
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
    saved = (v7.executor, v7.readiness)
    v7.executor = executor
    v7.readiness = readiness
    try:
        yield
    finally:
        v7.executor, v7.readiness = saved


def _commands(
    artifact_dir: Path, slice_path: Path, inspection_path: Path
) -> dict[str, list[str]]:
    return v7._commands(artifact_dir, slice_path, inspection_path)


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v11_boundary(
    plan: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    if keys != _stage_order():
        raise CorpusExecutorPlanCompilerV8Error(
            "execution plan is not the exact readiness-v11 stage contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV8Error(
            "duplicate execution-plan stage keys"
        )
    if not (
        keys.index(G16_PARTITION_REPLAY_STAGE)
        < keys.index("g16_exact_causal")
        < keys.index("g16_prepared_causal_authorization")
        < keys.index("g16_counterfactual_causal_authorization")
        < keys.index(G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE)
        < keys.index("g16_prepared_curve_authorization")
        < keys.index("g16_counterfactual_curve_authorization")
    ):
        raise CorpusExecutorPlanCompilerV8Error(
            "G16 exact corpus/counterfactual causal authorization is not between causal lineage and curve authorization"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    exact_row = rows[G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE]
    if exact_row.get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV8Error(
            "G16 exact counterfactual causal authorization must remain disabled in the compiled corpus plan"
        )
    if exact_row.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPlanCompilerV8Error(
            "G16 exact counterfactual causal authorization must remain pre-outcome"
        )
    return rows


def _base_v7_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v7_fingerprint = base.pop("compiler_v7_fingerprint", None)
    for field in (
        "g16_exact_counterfactual_causal_authorization_required",
        "g16_exact_counterfactual_causal_stage_present",
        "g16_exact_counterfactual_causal_stage_enabled",
        "g16_exact_counterfactual_causal_stage_pre_outcome",
        "g16_exact_replay_provenance_must_join_counterfactual_lineage",
        "g16_prepared_curve_blocked_until_exact_counterfactual_causal_authorized",
        "g16_counterfactual_curve_blocked_until_exact_counterfactual_causal_authorized",
        "exact_g16_counterfactual_causal_output",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V7_SCHEMA
    base["status"] = v7.STATUS
    base["fingerprint"] = v7_fingerprint
    return base


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v11_context():
        plan, base = v7.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            slice_bundle_path=slice_bundle_path,
            inspection_plan_path=inspection_plan_path,
        )
    rows = _validate_v11_boundary(plan)
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["compiler_v7_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        _stage_order()
    )
    receipt["g16_exact_counterfactual_causal_authorization_required"] = True
    receipt["g16_exact_counterfactual_causal_stage_present"] = (
        G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE in rows
    )
    receipt["g16_exact_counterfactual_causal_stage_enabled"] = False
    receipt["g16_exact_counterfactual_causal_stage_pre_outcome"] = True
    receipt[
        "g16_exact_replay_provenance_must_join_counterfactual_lineage"
    ] = True
    receipt[
        "g16_prepared_curve_blocked_until_exact_counterfactual_causal_authorized"
    ] = True
    receipt[
        "g16_counterfactual_curve_blocked_until_exact_counterfactual_causal_authorized"
    ] = True
    receipt["exact_g16_counterfactual_causal_output"] = str(
        artifact_dir.resolve(strict=False)
        / "g16_exact_counterfactual_causal_authorization.json"
    )
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(
        receipt,
        plan=plan,
        commands=_commands(artifact_dir, slice_bundle_path, inspection_plan_path),
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
        raise CorpusExecutorPlanCompilerV8Error(
            "compiler v8 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    rows = _validate_v11_boundary(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV8Error("compiler v8 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV8Error(
            "readiness-v11 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        _stage_order()
    ):
        raise CorpusExecutorPlanCompilerV8Error(
            "readiness-v11 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_counterfactual_causal_authorization_required",
        "g16_exact_counterfactual_causal_stage_present",
        "g16_exact_counterfactual_causal_stage_pre_outcome",
        "g16_exact_replay_provenance_must_join_counterfactual_lineage",
        "g16_prepared_curve_blocked_until_exact_counterfactual_causal_authorized",
        "g16_counterfactual_curve_blocked_until_exact_counterfactual_causal_authorized",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPlanCompilerV8Error(
                f"compiler v8 mandatory field mismatch: {field}"
            )
    if checked.get("g16_exact_counterfactual_causal_stage_enabled") is not False:
        raise CorpusExecutorPlanCompilerV8Error(
            "compiled plan must not pre-enable G16 exact counterfactual causal authorization"
        )
    base = _base_v7_receipt(value)
    if base.get("fingerprint") != checked.get("compiler_v7_fingerprint"):
        raise CorpusExecutorPlanCompilerV8Error(
            "embedded compiler v7 fingerprint mismatch"
        )
    with _v11_context():
        v7.validate_receipt(base, plan=plan, commands=commands)
    if rows[G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV8Error(
            "G16 exact counterfactual causal stage may not be armed by corpus compilation"
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
            {
                "status": receipt["status"],
                "enabled_stage": receipt["enabled_stage"],
                "plan": str(args.plan_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
