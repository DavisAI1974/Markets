#!/usr/bin/env python3
"""Compile the stable corpus plan against readiness v13's exact G16 final wall."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v8 as v8
import ng_historical_refinement_executor_v10 as executor
import ng_historical_refinement_readiness_v13 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v9"
STATUS = "G16_EXACT_CURVE_LOCK_PUBLICATION_BOUND_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v8.CONFIGURED_STAGES
PARTITION_REPLAY_STAGE = v8.PARTITION_REPLAY_STAGE
WINDOW_STAGE = v8.WINDOW_STAGE
G16_PARTITION_REPLAY_STAGE = v8.G16_PARTITION_REPLAY_STAGE
G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE = v8.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE
G16_EXACT_COUNTERFACTUAL_CURVE_STAGE = "g16_exact_counterfactual_curve_authorization"
G16_EXACT_CURVE_LOCK_STAGE = "g16_counterfactual_curve_lock"
G16_EXACT_PUBLICATION_STAGE = "g16_counterfactual_publication"
V8_SCHEMA = v8.SCHEMA


class CorpusExecutorPlanCompilerV9Error(ValueError):
    """Raised when a readiness-v13 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV9Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV9Error(
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
    saved = (v8.executor, v8.readiness)
    v8.executor = executor
    v8.readiness = readiness
    try:
        yield
    finally:
        v8.executor, v8.readiness = saved


def _commands(
    artifact_dir: Path, slice_path: Path, inspection_path: Path
) -> dict[str, list[str]]:
    return v8._commands(artifact_dir, slice_path, inspection_path)


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v13_boundary(
    plan: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    if keys != _stage_order():
        raise CorpusExecutorPlanCompilerV9Error(
            "execution plan is not the exact readiness-v13 stage contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV9Error(
            "duplicate execution-plan stage keys"
        )
    if not (
        keys.index(G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE)
        < keys.index("g16_prepared_curve_authorization")
        < keys.index("g16_counterfactual_curve_authorization")
        < keys.index(G16_EXACT_COUNTERFACTUAL_CURVE_STAGE)
        < keys.index(G16_EXACT_CURVE_LOCK_STAGE)
        < keys.index(G16_EXACT_PUBLICATION_STAGE)
    ):
        raise CorpusExecutorPlanCompilerV9Error(
            "G16 exact causal, curve, lock, and publication stages are out of order"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_EXACT_PUBLICATION_STAGE,
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPlanCompilerV9Error(
                f"{key} must remain disabled in the compiled corpus plan"
            )
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
    ):
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV9Error(
                f"{key} must remain pre-outcome"
            )
    if rows[G16_EXACT_PUBLICATION_STAGE].get("requires_fixed_outcomes") is not True:
        raise CorpusExecutorPlanCompilerV9Error(
            "exact G16 publication must remain post-lock and fixed-outcome"
        )
    lock_spec = next(
        spec for spec in readiness.STAGES if spec.key == G16_EXACT_CURVE_LOCK_STAGE
    )
    publication_spec = next(
        spec for spec in readiness.STAGES if spec.key == G16_EXACT_PUBLICATION_STAGE
    )
    if (
        lock_spec.filename != "g16_exact_counterfactual_curve_lock.json"
        or lock_spec.schema != "ng_g16_exact_counterfactual_curve_lock.v1"
        or publication_spec.filename
        != "g16_exact_counterfactual_publication_completion.json"
        or publication_spec.schema
        != "ng_g16_exact_counterfactual_publication_completion.v1"
    ):
        raise CorpusExecutorPlanCompilerV9Error(
            "readiness v13 must reject the legacy G16 lock/publication route"
        )
    return rows


def _base_v8_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v8_fingerprint = base.pop("compiler_v8_fingerprint", None)
    for field in (
        "g16_exact_counterfactual_curve_authorization_required",
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
        "exact_g16_counterfactual_curve_output",
        "exact_g16_counterfactual_lock_output",
        "exact_g16_counterfactual_publication_output",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V8_SCHEMA
    base["status"] = v8.STATUS
    base["fingerprint"] = v8_fingerprint
    return base


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v13_context():
        plan, base = v8.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            slice_bundle_path=slice_bundle_path,
            inspection_plan_path=inspection_plan_path,
        )
    rows = _validate_v13_boundary(plan)
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["compiler_v8_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        _stage_order()
    )
    receipt["g16_exact_counterfactual_curve_authorization_required"] = True
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
    artifact_root = artifact_dir.resolve(strict=False)
    receipt["exact_g16_counterfactual_curve_output"] = str(
        artifact_root / "g16_exact_counterfactual_curve_authorization.json"
    )
    receipt["exact_g16_counterfactual_lock_output"] = str(
        artifact_root / "g16_exact_counterfactual_curve_lock.json"
    )
    receipt["exact_g16_counterfactual_publication_output"] = str(
        artifact_root / "g16_exact_counterfactual_publication_completion.json"
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
            G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
            G16_EXACT_CURVE_LOCK_STAGE,
            G16_EXACT_PUBLICATION_STAGE,
        )
    ):
        raise CorpusExecutorPlanCompilerV9Error(
            "compiled plan lost an exact G16 final-stage contract"
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
        raise CorpusExecutorPlanCompilerV9Error(
            "compiler v9 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    rows = _validate_v13_boundary(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV9Error("compiler v9 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV9Error(
            "readiness-v13 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        _stage_order()
    ):
        raise CorpusExecutorPlanCompilerV9Error(
            "readiness-v13 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_counterfactual_curve_authorization_required",
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
            raise CorpusExecutorPlanCompilerV9Error(
                f"compiler v9 mandatory field mismatch: {field}"
            )
    for field in (
        "g16_exact_counterfactual_curve_stage_enabled",
        "g16_exact_curve_lock_stage_enabled",
        "g16_exact_publication_stage_enabled",
    ):
        if checked.get(field) is not False:
            raise CorpusExecutorPlanCompilerV9Error(
                f"compiled corpus plan may not activate {field}"
            )
    base = _base_v8_receipt(value)
    if base.get("fingerprint") != checked.get("compiler_v8_fingerprint"):
        raise CorpusExecutorPlanCompilerV9Error(
            "embedded compiler v8 fingerprint mismatch"
        )
    with _v13_context():
        v8.validate_receipt(base, plan=plan, commands=commands)
    for key in (
        G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
        G16_EXACT_CURVE_LOCK_STAGE,
        G16_EXACT_PUBLICATION_STAGE,
    ):
        if rows[key].get("enabled") is not False:
            raise CorpusExecutorPlanCompilerV9Error(
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
