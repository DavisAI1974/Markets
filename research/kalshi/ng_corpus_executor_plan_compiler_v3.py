#!/usr/bin/env python3
"""Compile exact target-day, broad-scope, and full-window overlap stages for readiness v6.

The readiness-v5 compiler proved the declared one-year L1/dense-trades and spring/summer
MBO scopes before G15, but it did not configure the new full-window exact-overlap gate.
This compiler adds that fifth pre-outcome stage and binds its command to the verified broad
scope artifact. Only byte inspection is enabled initially; the stable v3 arm step may enable
all five corpus stages without changing command vectors or ledger lineage.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v2 as v2
import ng_historical_refinement_executor_v4 as executor

SCHEMA = "ng_corpus_executor_plan_compiler.v3"
CONFIGURED_STAGES = (
    "corpus_coverage",
    "basis_inventory_regeneration",
    "replay_catalog_export",
    "broad_corpus_scope",
    "broad_corpus_exact_overlap",
)
STATUS = "BROAD_CORPUS_EXACT_OVERLAP_EXECUTOR_PLAN_COMPILED"


class CorpusExecutorPlanCompilerV3Error(ValueError):
    """Raised when a readiness-v6 corpus plan cannot be compiled safely."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV3Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV3Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
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
            raise CorpusExecutorPlanCompilerV3Error(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV3Error(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV3Error(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV3Error(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV3Error(f"{label}: brokerage must remain tastytrade, not IBKR")


def _commands(artifact_dir: Path, slice_path: Path, inspection_path: Path) -> dict[str, list[str]]:
    commands = v2._commands(artifact_dir, slice_path, inspection_path)
    resolved = artifact_dir.resolve(strict=False)
    commands["broad_corpus_exact_overlap"] = [
        "python",
        "ng_broad_corpus_exact_overlap_gate.py",
        "--broad-scope-gate",
        str(resolved / "ng_broad_corpus_scope_gate.json"),
        "--out",
        str(resolved / "ng_broad_corpus_exact_overlap_gate.json"),
    ]
    return commands


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    slice_bundle, inspection_plan = fingerprinting.validate_inputs(
        _load(slice_bundle_path), _load(inspection_plan_path)
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    commands = _commands(artifact_dir, slice_bundle_path, inspection_plan_path)
    for index, key in enumerate(CONFIGURED_STAGES):
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=index == 0,
        )
    executor.validate_plan(plan)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "slice_bundle_fingerprint": slice_bundle["slice_bundle_fingerprint"],
        "inspection_plan_fingerprint": inspection_plan["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": fingerprinting._fp(commands),
        "broad_corpus_scope_gate_required": True,
        "broad_corpus_exact_overlap_gate_required": True,
        "broad_corpus_scope_output": str(
            artifact_dir.resolve(strict=False) / "ng_broad_corpus_scope_gate.json"
        ),
        "broad_corpus_exact_overlap_output": str(
            artifact_dir.resolve(strict=False) / "ng_broad_corpus_exact_overlap_gate.json"
        ),
        "target_day_subset_cannot_satisfy_broad_scope": True,
        "broad_scope_alone_cannot_satisfy_exact_overlap": True,
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
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
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
        raise CorpusExecutorPlanCompilerV3Error("compiler v3 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v3 receipt")
    executor.validate_plan(plan)
    if checked.get("status") != STATUS:
        raise CorpusExecutorPlanCompilerV3Error("compiler v3 status mismatch")
    if checked.get("execution_plan_fingerprint") != plan.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV3Error("execution-plan fingerprint mismatch")
    if checked.get("commands_fingerprint") != fingerprinting._fp(commands):
        raise CorpusExecutorPlanCompilerV3Error("command fingerprint mismatch")
    if checked.get("configured_stages") != list(CONFIGURED_STAGES):
        raise CorpusExecutorPlanCompilerV3Error("configured stage order mismatch")
    if checked.get("broad_corpus_scope_gate_required") is not True:
        raise CorpusExecutorPlanCompilerV3Error("broad-corpus scope gate must remain mandatory")
    if checked.get("broad_corpus_exact_overlap_gate_required") is not True:
        raise CorpusExecutorPlanCompilerV3Error("broad-corpus exact-overlap gate must remain mandatory")
    if checked.get("target_day_subset_cannot_satisfy_broad_scope") is not True:
        raise CorpusExecutorPlanCompilerV3Error("target-day subset may not satisfy broad scope")
    if checked.get("broad_scope_alone_cannot_satisfy_exact_overlap") is not True:
        raise CorpusExecutorPlanCompilerV3Error("broad scope alone may not satisfy exact overlap")
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    if list(rows) != [str(row.get("key")) for row in plan.get("stages") or []]:
        raise CorpusExecutorPlanCompilerV3Error("duplicate execution-plan stage keys")
    for key in CONFIGURED_STAGES:
        if rows.get(key, {}).get("argv") != list(commands[key]):
            raise CorpusExecutorPlanCompilerV3Error(f"{key}: compiled argv mismatch")
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV3Error(f"{key}: corpus stages must remain pre-outcome")
    if rows["corpus_coverage"].get("enabled") is not True:
        raise CorpusExecutorPlanCompilerV3Error("corpus inspection must be enabled initially")
    for key in CONFIGURED_STAGES[1:]:
        if rows[key].get("enabled"):
            raise CorpusExecutorPlanCompilerV3Error(f"{key}: downstream stage must remain disabled")
    later = [row for row in plan.get("stages") or [] if row.get("key") not in CONFIGURED_STAGES]
    if any(row.get("enabled") for row in later):
        raise CorpusExecutorPlanCompilerV3Error("G15/G16 stages must remain disabled")
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
