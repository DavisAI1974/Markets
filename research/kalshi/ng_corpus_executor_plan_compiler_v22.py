#!/usr/bin/env python3
"""Compile the stable corpus executor plan against runtime-observed readiness v27."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v21 as v21
import ng_corpus_s3_runtime_observed_inventory_capture as runtime_capture
import ng_historical_refinement_executor_v23 as executor
import ng_historical_refinement_readiness_v27 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v22"
STATUS = "RUNTIME_OBSERVED_INVENTORY_BOUND_CORPUS_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = v21.CONFIGURED_STAGES


class CorpusExecutorPlanCompilerV22Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV22Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV22Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v21._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV22Error(str(error)) from error


def _validate_runtime_capture(
    *,
    capture_spec: Mapping[str, Any],
    finalization_receipt: Mapping[str, Any],
    capture_receipt: Mapping[str, Any],
    materialization_spec: Mapping[str, Any],
) -> dict[str, Any]:
    captured = runtime_capture.validate_receipt(capture_receipt)
    if (
        captured.get("status") != runtime_capture.READY_STATUS
        or captured.get("blockers") != []
        or captured.get("actual_runtime_capture_bound_to_product_lags") is not True
        or captured.get("declared_observations_bound_to_runtime_interval") is not True
        or captured.get("complete_pagination_attested") is not True
        or captured.get("checksum_enabled_heads_attested") is not True
    ):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory capture must be blocker-free before materialization"
        )
    if captured.get("source_spec") != dict(capture_spec):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory receipt is not derived from the supplied capture specification"
        )
    if captured.get("finalization_contract") != dict(finalization_receipt):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory receipt is not bound to the supplied finalization receipt"
        )
    if captured.get("materialization_spec") != dict(materialization_spec):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory receipt is not bound to the supplied materialization specification"
        )
    nested = captured.get("paginated_inventory_receipt")
    if not isinstance(nested, Mapping):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory receipt lacks embedded paginated evidence"
        )
    return captured


@contextmanager
def _v27_context(
    *,
    runtime_receipt: Mapping[str, Any],
    finalization_receipt_path: Path,
    materialization_spec_path: Path,
    capture_receipt_path: Path,
) -> Iterator[None]:
    saved = (v21.executor, v21.readiness, v21.validate_inputs, v21._commands)
    original_validate_inputs = v21.validate_inputs
    original_commands = v21._commands

    def validate_inputs_adapter(**kwargs: Any) -> tuple[dict[str, Any], ...]:
        captured = _validate_runtime_capture(
            capture_spec=kwargs["capture_spec"],
            finalization_receipt=kwargs["finalization_receipt"],
            capture_receipt=kwargs["capture_receipt"],
            materialization_spec=kwargs["materialization_spec"],
        )
        forwarded = dict(kwargs)
        forwarded["capture_receipt"] = captured["paginated_inventory_receipt"]
        return original_validate_inputs(**forwarded)

    def commands_adapter(**kwargs: Any) -> dict[str, list[str]]:
        commands = original_commands(**kwargs)
        commands["corpus_s3_inventory_capture"] = [
            "python",
            "ng_corpus_s3_runtime_observed_inventory_capture.py",
            "capture",
            "--spec",
            str(Path(kwargs["capture_spec_path"]).resolve(strict=False)),
            "--finalization",
            str(finalization_receipt_path.resolve(strict=False)),
            "--materialization-spec-out",
            str(materialization_spec_path.resolve(strict=False)),
            "--receipt-out",
            str(capture_receipt_path.resolve(strict=False)),
        ]
        return {key: commands[key] for key in CONFIGURED_STAGES}

    v21.executor = executor
    v21.readiness = readiness
    v21.validate_inputs = validate_inputs_adapter
    v21._commands = commands_adapter
    try:
        yield
    finally:
        v21.executor, v21.readiness, v21.validate_inputs, v21._commands = saved


def _commands(
    *,
    artifact_dir: Path,
    resolution_spec_path: Path,
    expected_day_receipt_path: Path,
    finalization_receipt_path: Path,
    resolution_receipt_path: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> dict[str, list[str]]:
    commands = v21._commands(
        artifact_dir=artifact_dir,
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        finalization_receipt_path=finalization_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    commands["corpus_s3_inventory_capture"] = [
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
        "--spec",
        str(capture_spec_path.resolve(strict=False)),
        "--finalization",
        str(finalization_receipt_path.resolve(strict=False)),
        "--materialization-spec-out",
        str(materialization_spec_path.resolve(strict=False)),
        "--receipt-out",
        str(capture_receipt_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    old_executor, old_readiness = v21.executor, v21.readiness
    v21.executor, v21.readiness = executor, readiness
    try:
        rows = v21._validate_plan(plan, commands, compiled=compiled)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV22Error(str(error)) from error
    finally:
        v21.executor, v21.readiness = old_executor, old_readiness
    capture_row = rows["corpus_s3_inventory_capture"]
    if capture_row.get("expected_output") != (
        "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json"
    ):
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory artifact was substituted"
        )
    if capture_row.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
    ]:
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed inventory entrypoint was substituted"
        )
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    resolution_spec_path: Path,
    expected_day_receipt_path: Path,
    finalization_receipt_path: Path,
    resolution_receipt_path: Path,
    capture_spec_path: Path,
    capture_receipt_path: Path,
    materialization_spec_path: Path,
    materialization_receipt_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_receipt = _load(capture_receipt_path)
    captured = _validate_runtime_capture(
        capture_spec=_load(capture_spec_path),
        finalization_receipt=_load(finalization_receipt_path),
        capture_receipt=runtime_receipt,
        materialization_spec=_load(materialization_spec_path),
    )
    with _v27_context(
        runtime_receipt=captured,
        finalization_receipt_path=finalization_receipt_path,
        materialization_spec_path=materialization_spec_path,
        capture_receipt_path=capture_receipt_path,
    ):
        plan, base = v21.build_compiled_plan(
            artifact_dir=artifact_dir,
            working_directory=working_directory,
            resolution_spec_path=resolution_spec_path,
            expected_day_receipt_path=expected_day_receipt_path,
            finalization_receipt_path=finalization_receipt_path,
            resolution_receipt_path=resolution_receipt_path,
            capture_spec_path=capture_spec_path,
            capture_receipt_path=capture_receipt_path,
            materialization_spec_path=materialization_spec_path,
            materialization_receipt_path=materialization_receipt_path,
            inventory_receipt_path=inventory_receipt_path,
            broad_plan_path=broad_plan_path,
            slice_bundle_path=slice_bundle_path,
            target_plan_path=target_plan_path,
        )
    commands = _commands(
        artifact_dir=artifact_dir,
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        finalization_receipt_path=finalization_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    _validate_plan(plan, commands, compiled=True)
    receipt = copy.deepcopy(base)
    receipt.pop("fingerprint", None)
    receipt.update(
        {
            "schema": SCHEMA,
            "status": STATUS,
            "readiness_contract": readiness.SCHEMA,
            "readiness_stage_contract_fingerprint": fingerprinting._fp(
                [spec.key for spec in readiness.STAGES]
            ),
            "runtime_observed_inventory_receipt_fingerprint": captured[
                "receipt_fingerprint"
            ],
            "embedded_paginated_inventory_receipt_fingerprint": captured[
                "paginated_inventory_receipt_fingerprint"
            ],
            "runtime_capture_started_at_utc": captured["capture_started_at_utc"],
            "runtime_capture_completed_at_utc": captured["capture_completed_at_utc"],
            "runtime_finalization_checks_fingerprint": captured[
                "runtime_finalization_checks_fingerprint"
            ],
            "declared_observation_checks_fingerprint": captured[
                "declared_observation_checks_fingerprint"
            ],
            "actual_runtime_capture_bound_to_product_lags": True,
            "declared_inventory_observations_bound_to_runtime_interval": True,
            "runtime_observed_inventory_required_before_materialization": True,
            "inventory_capture_command_is_runtime_observed": True,
            "next_permitted_stage": "RUN_BRANCH_GUARDED_RUNTIME_OBSERVED_CORPUS_PIPELINE",
        }
    )
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV22Error(
            "compiler v22 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v22 receipt")
    rows = _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "commands_fingerprint": fingerprinting._fp(commands),
        "actual_runtime_capture_bound_to_product_lags": True,
        "declared_inventory_observations_bound_to_runtime_interval": True,
        "runtime_observed_inventory_required_before_materialization": True,
        "inventory_capture_command_is_runtime_observed": True,
        "all_corpus_stages_pre_outcome": True,
    }
    for field, item in expected.items():
        if checked.get(field) != item:
            raise CorpusExecutorPlanCompilerV22Error(
                f"compiler v22 field mismatch: {field}"
            )
    for field in (
        "runtime_observed_inventory_receipt_fingerprint",
        "embedded_paginated_inventory_receipt_fingerprint",
        "runtime_capture_started_at_utc",
        "runtime_capture_completed_at_utc",
        "runtime_finalization_checks_fingerprint",
        "declared_observation_checks_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV22Error(f"compiler v22 missing field: {field}")
    if rows["corpus_s3_inventory_capture"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV22Error(
            "runtime-observed capture may not be enabled before prior corpus contracts"
        )
    if rows["corpus_s3_materialization"].get("enabled") is not False:
        raise CorpusExecutorPlanCompilerV22Error(
            "materialization may not be enabled before runtime-observed capture"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--resolution-spec", type=Path, required=True)
    parser.add_argument("--expected-day-receipt", type=Path, required=True)
    parser.add_argument("--finalization-receipt", type=Path, required=True)
    parser.add_argument("--resolution-receipt", type=Path, required=True)
    parser.add_argument("--capture-spec", type=Path, required=True)
    parser.add_argument("--capture-receipt", type=Path, required=True)
    parser.add_argument("--materialization-spec", type=Path, required=True)
    parser.add_argument("--materialization-receipt", type=Path, required=True)
    parser.add_argument("--inventory-receipt", type=Path, required=True)
    parser.add_argument("--broad-plan", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--target-plan", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        resolution_spec_path=args.resolution_spec,
        expected_day_receipt_path=args.expected_day_receipt,
        finalization_receipt_path=args.finalization_receipt,
        resolution_receipt_path=args.resolution_receipt,
        capture_spec_path=args.capture_spec,
        capture_receipt_path=args.capture_receipt,
        materialization_spec_path=args.materialization_spec,
        materialization_receipt_path=args.materialization_receipt,
        inventory_receipt_path=args.inventory_receipt,
        broad_plan_path=args.broad_plan,
        slice_bundle_path=args.slice_bundle,
        target_plan_path=args.target_plan,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
