#!/usr/bin/env python3
"""Compile the stable corpus plan against readiness v10's G16 byte/window wall."""
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
import ng_historical_refinement_executor_v8 as executor
import ng_historical_refinement_readiness_v10 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v7"
STATUS = "G16_EXACT_PARTITION_REPLAY_WINDOW_BOUND_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v6.CONFIGURED_STAGES
PARTITION_REPLAY_STAGE = v6.PARTITION_REPLAY_STAGE
WINDOW_STAGE = v6.WINDOW_STAGE
G16_PARTITION_REPLAY_STAGE = "g16_exact_partition_replay_authorization"
V6_SCHEMA = v6.SCHEMA


class CorpusExecutorPlanCompilerV7Error(ValueError):
    """Raised when a readiness-v10 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV7Error(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV7Error(
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
    saved = (v6.executor, v6.readiness)
    v6.executor = executor
    v6.readiness = readiness
    try:
        yield
    finally:
        v6.executor, v6.readiness = saved


def _commands(
    artifact_dir: Path, slice_path: Path, inspection_path: Path
) -> dict[str, list[str]]:
    return v6._commands(artifact_dir, slice_path, inspection_path)


def _stage_order() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _validate_v10_boundary(
    plan: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    executor.validate_plan(plan)
    rows_list = list(plan.get("stages") or [])
    keys = [str(row.get("key")) for row in rows_list]
    if keys != _stage_order():
        raise CorpusExecutorPlanCompilerV7Error(
            "execution plan is not the exact readiness-v10 stage contract"
        )
    if len(keys) != len(set(keys)):
        raise CorpusExecutorPlanCompilerV7Error(
            "duplicate execution-plan stage keys"
        )
    if not (
        keys.index("g16_prepared_replay")
        < keys.index(G16_PARTITION_REPLAY_STAGE)
        < keys.index("g16_exact_causal")
        < keys.index("g16_prepared_causal_authorization")
    ):
        raise CorpusExecutorPlanCompilerV7Error(
            "G16 partition/replay-window authorization is not between prepared replay and causal authorization"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    g16_row = rows[G16_PARTITION_REPLAY_STAGE]
    if g16_row.get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV7Error(
            "G16 partition/replay-window authorization must remain disabled in the compiled corpus plan"
        )
    if g16_row.get("requires_fixed_outcomes") is not False:
        raise CorpusExecutorPlanCompilerV7Error(
            "G16 partition/replay-window authorization must remain pre-outcome"
        )
    return rows


def _base_v6_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v6_fingerprint = base.pop("compiler_v6_fingerprint", None)
    for field in (
        "g16_exact_partition_replay_authorization_required",
        "g16_exact_partition_replay_stage_present",
        "g16_exact_partition_replay_stage_enabled",
        "g16_replay_bytes_must_match_exact_partition",
        "g16_replay_state_windows_must_precede_causal",
        "g16_exact_causal_blocked_until_partition_replay_authorized",
        "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized",
        "exact_g16_partition_replay_output",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V6_SCHEMA
    base["status"] = v6.STATUS
    base["fingerprint"] = v6_fingerprint
    return base


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v10_context():
        plan, base = v6.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            slice_bundle_path=slice_bundle_path,
            inspection_plan_path=inspection_plan_path,
        )
    rows = _validate_v10_boundary(plan)
    receipt = copy.deepcopy(base)
    receipt["schema"] = SCHEMA
    receipt["status"] = STATUS
    receipt["compiler_v6_fingerprint"] = base["fingerprint"]
    receipt["readiness_contract"] = readiness.SCHEMA
    receipt["readiness_stage_contract_fingerprint"] = fingerprinting._fp(
        _stage_order()
    )
    receipt["g16_exact_partition_replay_authorization_required"] = True
    receipt["g16_exact_partition_replay_stage_present"] = (
        G16_PARTITION_REPLAY_STAGE in rows
    )
    receipt["g16_exact_partition_replay_stage_enabled"] = False
    receipt["g16_replay_bytes_must_match_exact_partition"] = True
    receipt["g16_replay_state_windows_must_precede_causal"] = True
    receipt[
        "g16_exact_causal_blocked_until_partition_replay_authorized"
    ] = True
    receipt[
        "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized"
    ] = True
    receipt["exact_g16_partition_replay_output"] = str(
        artifact_dir.resolve(strict=False)
        / "g16_exact_partition_replay_authorization.json"
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
        raise CorpusExecutorPlanCompilerV7Error(
            "compiler v7 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    rows = _validate_v10_boundary(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV7Error("compiler v7 status mismatch")
    if checked.get("readiness_contract") != readiness.SCHEMA:
        raise CorpusExecutorPlanCompilerV7Error(
            "readiness-v10 contract mismatch"
        )
    if checked.get("readiness_stage_contract_fingerprint") != fingerprinting._fp(
        _stage_order()
    ):
        raise CorpusExecutorPlanCompilerV7Error(
            "readiness-v10 stage-contract fingerprint mismatch"
        )
    for field in (
        "g16_exact_partition_replay_authorization_required",
        "g16_exact_partition_replay_stage_present",
        "g16_replay_bytes_must_match_exact_partition",
        "g16_replay_state_windows_must_precede_causal",
        "g16_exact_causal_blocked_until_partition_replay_authorized",
        "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized",
    ):
        if checked.get(field) is not True:
            raise CorpusExecutorPlanCompilerV7Error(
                f"compiler v7 mandatory field mismatch: {field}"
            )
    if checked.get("g16_exact_partition_replay_stage_enabled") is not False:
        raise CorpusExecutorPlanCompilerV7Error(
            "compiled plan must not pre-enable G16 partition/replay-window authorization"
        )
    base = _base_v6_receipt(value)
    if base.get("fingerprint") != checked.get("compiler_v6_fingerprint"):
        raise CorpusExecutorPlanCompilerV7Error(
            "embedded compiler v6 fingerprint mismatch"
        )
    with _v10_context():
        v6.validate_receipt(base, plan=plan, commands=commands)
    if rows[G16_PARTITION_REPLAY_STAGE].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV7Error(
            "G16 partition/replay-window stage may not be armed by corpus compilation"
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
