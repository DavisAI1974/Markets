#!/usr/bin/env python3
"""Arm the three exact historical-corpus stages under one stable executor plan.

The corpus plan compiler deliberately enables only byte-level inspection.  Rewriting the
plan after every successful stage would change the plan fingerprint and invalidate the
append-only executor ledger.  This module closes that operational seam by validating the
compiler receipt and producing one stable plan in which only the first three pre-outcome
corpus stages are armed.  The guarded executor still selects the first blocking readiness
stage, so basis regeneration cannot run before inspection and replay-catalog export cannot
run before exact daily inventories are ready.

G15 and every later stage remain disabled.  Full one-year L1/dense-trades and spring/summer
MBO scope verification remains an explicit prerequisite before G15 replay is configured.
This module never opens outcomes, assumes paid live data, mutates blind forecasts or
``ng_brain.json``, grants execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as compiler
import ng_historical_refinement_executor_v2 as executor
import ng_historical_refinement_readiness_v4 as readiness

SCHEMA = "ng_corpus_executor_pipeline_arm.v1"
ARMED_STAGES = (
    "corpus_coverage",
    "basis_inventory_regeneration",
    "replay_catalog_export",
)
STATUS = "EXACT_CORPUS_PIPELINE_ARMED"


class CorpusExecutorPipelineArmError(ValueError):
    """Raised when a compiled corpus plan cannot be safely armed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPipelineArmError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPipelineArmError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "remote_presence_inferred",
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusExecutorPipelineArmError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPipelineArmError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPipelineArmError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPipelineArmError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPipelineArmError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(plan: Mapping[str, Any]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    result: dict[str, list[str]] = {}
    for key in ARMED_STAGES:
        row = rows.get(key)
        argv = None if row is None else row.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
            raise CorpusExecutorPipelineArmError(f"{key}: compiled command is missing or invalid")
        result[key] = list(argv)
    return result


def _validate_compiled_inputs(
    compiled_plan: Mapping[str, Any], compiler_receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    plan = copy.deepcopy(dict(compiled_plan))
    receipt = copy.deepcopy(dict(compiler_receipt))
    executor.validate_plan(plan)
    commands = _commands(plan)
    try:
        compiler.validate_receipt(receipt, plan=plan, commands=commands)
    except Exception as error:
        raise CorpusExecutorPipelineArmError(f"compiled corpus plan or receipt is invalid: {error}") from error
    if receipt.get("schema") != compiler.SCHEMA or receipt.get("status") != "CORPUS_EXECUTOR_PLAN_COMPILED":
        raise CorpusExecutorPipelineArmError("compiler receipt contract mismatch")
    if receipt.get("configured_stages") != list(ARMED_STAGES):
        raise CorpusExecutorPipelineArmError("compiler receipt corpus-stage order mismatch")
    rows = {str(row.get("key")): row for row in plan["stages"]}
    later = [spec.key for spec in readiness.STAGES if spec.key not in ARMED_STAGES]
    enabled_later = [key for key in later if rows[key].get("enabled")]
    if enabled_later:
        raise CorpusExecutorPipelineArmError(
            "compiled plan may not pre-enable downstream stages: " + ", ".join(enabled_later)
        )
    if plan.get("outcome_paths") != []:
        raise CorpusExecutorPipelineArmError("compiled corpus plan must not reference outcome paths")
    return plan, receipt, commands


def _arm_plan(compiled_plan: Mapping[str, Any], commands: Mapping[str, list[str]]) -> dict[str, Any]:
    armed = copy.deepcopy(dict(compiled_plan))
    for key in ARMED_STAGES:
        armed = executor.configure_stage(armed, key, commands[key], enabled=True)
    executor.validate_plan(armed)
    rows = {str(row.get("key")): row for row in armed["stages"]}
    for key in ARMED_STAGES:
        if rows[key].get("enabled") is not True or rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPipelineArmError(f"{key}: corpus stage was not safely armed")
    for spec in readiness.STAGES[len(ARMED_STAGES):]:
        if rows[spec.key].get("enabled"):
            raise CorpusExecutorPipelineArmError(f"{spec.key}: downstream stage must remain disabled")
    return armed


def build_armed_plan(
    compiled_plan: Mapping[str, Any], compiler_receipt: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_plan, source_receipt, commands = _validate_compiled_inputs(compiled_plan, compiler_receipt)
    armed_plan = _arm_plan(source_plan, commands)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": armed_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": [spec.key for spec in readiness.STAGES[: len(ARMED_STAGES)]],
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_all_corpus_stages": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_verification_required_before_g15_replay": True,
        "required_broad_scope": {
            "l1_dense_trades": "ONE_YEAR",
            "mbo": "SPRING_SUMMER",
        },
        "actual_outcomes_used": False,
        "remote_presence_inferred": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_EXACT_CORPUS_PIPELINE",
        "after_replay_catalog_export": "VERIFY_BROAD_CORPUS_SCOPE_BEFORE_CONFIGURING_G15_REPLAY",
    }
    receipt["fingerprint"] = _fp(receipt)
    validate_arm_receipt(
        receipt,
        compiled_plan=source_plan,
        compiler_receipt=source_receipt,
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
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPipelineArmError("pipeline-arm receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="pipeline-arm receipt")
    source_plan, source_receipt, commands = _validate_compiled_inputs(compiled_plan, compiler_receipt)
    expected_plan = _arm_plan(source_plan, commands)
    executor.validate_plan(armed_plan)
    if _canonical(armed_plan) != _canonical(expected_plan):
        raise CorpusExecutorPipelineArmError("armed plan differs from deterministic compiler-plan transformation")
    expected_fields = {
        "status": STATUS,
        "compiler_receipt_fingerprint": source_receipt["fingerprint"],
        "compiled_plan_fingerprint": source_plan["fingerprint"],
        "armed_plan_fingerprint": expected_plan["fingerprint"],
        "armed_stages": list(ARMED_STAGES),
        "stage_order_prefix": list(ARMED_STAGES),
        "selection_rule": "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        "single_stable_plan_for_all_corpus_stages": True,
        "single_stable_ledger_supported": True,
        "downstream_stages_enabled": False,
        "broad_corpus_verification_required_before_g15_replay": True,
    }
    for field, expected in expected_fields.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPipelineArmError(f"pipeline-arm receipt field mismatch: {field}")
    if checked.get("required_broad_scope") != {
        "l1_dense_trades": "ONE_YEAR",
        "mbo": "SPRING_SUMMER",
    }:
        raise CorpusExecutorPipelineArmError("required broad corpus scope mismatch")
    return copy.deepcopy(dict(value))


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        work = root / "work"
        artifacts = root / "artifacts"
        work.mkdir()
        artifacts.mkdir()
        plan = executor.build_plan(artifacts, work)
        commands = {
            "corpus_coverage": ["python", "ng_corpus_inspection.py", "inspect"],
            "basis_inventory_regeneration": ["python", "ng_corpus_basis_inventory_regeneration.py"],
            "replay_catalog_export": ["python", "ng_corpus_replay_catalog_export.py"],
        }
        plan = executor.configure_stage(plan, "corpus_coverage", commands["corpus_coverage"], enabled=True)
        plan = executor.configure_stage(plan, "basis_inventory_regeneration", commands["basis_inventory_regeneration"], enabled=False)
        plan = executor.configure_stage(plan, "replay_catalog_export", commands["replay_catalog_export"], enabled=False)
        receipt = {
            "schema": compiler.SCHEMA,
            "status": "CORPUS_EXECUTOR_PLAN_COMPILED",
            "slice_bundle_fingerprint": "fixture-slice",
            "inspection_plan_fingerprint": "fixture-inspection",
            "execution_plan_fingerprint": plan["fingerprint"],
            "configured_stages": list(commands),
            "enabled_stage": "corpus_coverage",
            "commands_fingerprint": compiler._fp(commands),
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": "RUN_BRANCH_GUARDED_CORPUS_INSPECTION",
        }
        receipt["fingerprint"] = compiler._fp(receipt)
        armed, arm_receipt = build_armed_plan(plan, receipt)
        validate_arm_receipt(
            arm_receipt,
            compiled_plan=plan,
            compiler_receipt=receipt,
            armed_plan=armed,
        )
    print("[ng_corpus_executor_pipeline_arm] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--compiled-plan", type=Path)
    parser.add_argument("--compiler-receipt", type=Path)
    parser.add_argument("--plan-out", type=Path)
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not all((args.compiled_plan, args.compiler_receipt, args.plan_out, args.receipt_out)):
        parser.error("--compiled-plan, --compiler-receipt, --plan-out, and --receipt-out are required")
    armed_plan, receipt = build_armed_plan(
        _load(args.compiled_plan),
        _load(args.compiler_receipt),
    )
    _write(args.plan_out, armed_plan)
    _write(args.receipt_out, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "armed_stages": receipt["armed_stages"],
                "plan": str(args.plan_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
