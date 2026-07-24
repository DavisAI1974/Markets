#!/usr/bin/env python3
"""Compile the verified target-day corpus chain into the guarded v4 executor.

This module removes manual argv wiring for the three immediate historical-corpus
stages.  It accepts an explicit, fingerprinted target-day slice bundle and its
exact embedded inspection plan, verifies all 24 UTC target days have one matched
L1/MBO pair, then configures the readiness-v4 executor for inspection, daily
basis regeneration, and replay-catalog export.  Only corpus inspection is enabled;
the later stages remain configured but disabled until readiness advances.

It never lists or downloads remote objects, infers identity from filenames, opens
outcomes, mutates blind forecasts or ng_brain.json, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer
import ng_historical_refinement_executor_v2 as executor

SCHEMA = "ng_corpus_executor_plan_compiler.v1"
READY_STATUS = "ANCHOR_G15_G16_TARGET_SLICES_READY"


class CorpusExecutorPlanCompilerError(ValueError):
    """Raised when corpus provenance cannot safely enter the executor."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerError(f"JSON artifact must be an object: {path}")
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
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "may_change_posterior",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusExecutorPlanCompilerError(f"{label}: {field} must remain false")
    if value.get("random_shuffle_used", False) is not False:
        raise CorpusExecutorPlanCompilerError(f"{label}: random shuffle is forbidden")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerError(f"{label}: brokerage must remain tastytrade, not IBKR")


def validate_inputs(
    slice_bundle: Mapping[str, Any], inspection_plan: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = copy.deepcopy(dict(slice_bundle))
    observed = bundle.pop("slice_bundle_fingerprint", None)
    if not isinstance(observed, str) or observed != _fp(bundle):
        raise CorpusExecutorPlanCompilerError("target-day slice bundle fingerprint mismatch")
    bundle["slice_bundle_fingerprint"] = observed
    if bundle.get("schema") != slicer.SCHEMA:
        raise CorpusExecutorPlanCompilerError("target-day slice bundle schema mismatch")
    if bundle.get("status") != READY_STATUS:
        raise CorpusExecutorPlanCompilerError("all anchor, G15, and G16 target-day pairs must be ready")
    _authority(bundle, label="target-day slice bundle")
    if bundle.get("broad_corpus_completeness_asserted") is not False:
        raise CorpusExecutorPlanCompilerError("target slicing may not assert broad corpus completeness")
    if bundle.get("target_days") != list(slicer._target_days()):
        raise CorpusExecutorPlanCompilerError("target-day list mismatch")
    pairs = list(bundle.get("pairs") or [])
    if len(pairs) != len(slicer._target_days()):
        raise CorpusExecutorPlanCompilerError("target-day pair count mismatch")
    if [str(row.get("day")) for row in pairs] != list(slicer._target_days()):
        raise CorpusExecutorPlanCompilerError("target-day pair order mismatch")
    for row in pairs:
        if row.get("status") != "MATCHED_L1_MBO_READY" or row.get("blockers") not in ([], None):
            raise CorpusExecutorPlanCompilerError(f"{row.get('day')}: exact L1/MBO pair is not ready")

    plan = inspection._validate_plan(inspection_plan)
    embedded = bundle.get("inspection_plan")
    if not isinstance(embedded, Mapping):
        raise CorpusExecutorPlanCompilerError("slice bundle is missing its embedded inspection plan")
    if _canonical(embedded) != _canonical(plan):
        raise CorpusExecutorPlanCompilerError("explicit inspection plan differs from slice-bundle plan")
    if bundle.get("inspection_plan_fingerprint") != plan.get("plan_fingerprint"):
        raise CorpusExecutorPlanCompilerError("slice bundle inspection-plan fingerprint mismatch")
    sources = [source for corpus in plan.get("corpora") or [] for source in corpus.get("sources") or []]
    expected = 2 * len(slicer._target_days())
    if len(sources) != expected:
        raise CorpusExecutorPlanCompilerError(f"inspection plan requires {expected} exact daily sources")
    observed_keys = sorted((str(row.get("day")), str(row.get("lane"))) for row in sources)
    expected_keys = sorted((day, lane) for day in slicer._target_days() for lane in ("l1_trades", "mbo"))
    if observed_keys != expected_keys:
        raise CorpusExecutorPlanCompilerError("inspection plan does not contain one exact source per day and lane")
    return copy.deepcopy(dict(slice_bundle)), copy.deepcopy(dict(plan))


def _argv_paths(artifact_dir: Path, slice_path: Path, inspection_path: Path) -> dict[str, list[str]]:
    artifact_dir = artifact_dir.resolve(strict=False)
    return {
        "corpus_coverage": [
            "python", "ng_corpus_inspection.py", "inspect",
            "--plan", str(inspection_path.resolve(strict=False)),
            "--catalog-out", str(artifact_dir / "ng_corpus_catalog.json"),
            "--audit-out", str(artifact_dir / "ng_corpus_coverage_audit.json"),
            "--receipt-out", str(artifact_dir / "ng_corpus_inspection_receipt.json"),
        ],
        "basis_inventory_regeneration": [
            "python", "ng_corpus_basis_inventory_regeneration.py",
            "--slice-bundle", str(slice_path.resolve(strict=False)),
            "--inspection-receipt", str(artifact_dir / "ng_corpus_inspection_receipt.json"),
            "--g15-out", str(artifact_dir / "g15_mbo_l1_manifest.json"),
            "--g16-out", str(artifact_dir / "g16_mbo_l1_inventory.json"),
            "--bundle-out", str(artifact_dir / "ng_corpus_basis_inventory_regeneration.json"),
        ],
        "replay_catalog_export": [
            "python", "ng_corpus_replay_catalog_export.py",
            "--catalog", str(artifact_dir / "ng_corpus_catalog.json"),
            "--audit", str(artifact_dir / "ng_corpus_coverage_audit.json"),
            "--g15-inventory", str(artifact_dir / "g15_mbo_l1_manifest.json"),
            "--g16-inventory", str(artifact_dir / "g16_mbo_l1_inventory.json"),
            "--g15-out", str(artifact_dir / "g15_exact_replay_catalog.json"),
            "--g16-out", str(artifact_dir / "g16_exact_replay_catalog.json"),
            "--bundle-out", str(artifact_dir / "ng_exact_replay_catalog_export.json"),
        ],
    }


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    slice_bundle_path: Path,
    inspection_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    slice_bundle, plan_value = validate_inputs(_load(slice_bundle_path), _load(inspection_plan_path))
    plan = executor.build_plan(artifact_dir, working_directory)
    commands = _argv_paths(artifact_dir, slice_bundle_path, inspection_plan_path)
    plan = executor.configure_stage(plan, "corpus_coverage", commands["corpus_coverage"], enabled=True)
    plan = executor.configure_stage(plan, "basis_inventory_regeneration", commands["basis_inventory_regeneration"], enabled=False)
    plan = executor.configure_stage(plan, "replay_catalog_export", commands["replay_catalog_export"], enabled=False)
    executor.validate_plan(plan)
    receipt = {
        "schema": SCHEMA,
        "status": "CORPUS_EXECUTOR_PLAN_COMPILED",
        "slice_bundle_fingerprint": slice_bundle["slice_bundle_fingerprint"],
        "inspection_plan_fingerprint": plan_value["plan_fingerprint"],
        "execution_plan_fingerprint": plan["fingerprint"],
        "configured_stages": list(commands),
        "enabled_stage": "corpus_coverage",
        "commands_fingerprint": _fp(commands),
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
    receipt["fingerprint"] = _fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any], *, plan: Mapping[str, Any], commands: Mapping[str, list[str]]
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPlanCompilerError("compiler receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="compiler receipt")
    executor.validate_plan(plan)
    if checked.get("execution_plan_fingerprint") != plan.get("fingerprint"):
        raise CorpusExecutorPlanCompilerError("compiler receipt execution-plan fingerprint mismatch")
    if checked.get("commands_fingerprint") != _fp(commands):
        raise CorpusExecutorPlanCompilerError("compiler receipt command fingerprint mismatch")
    rows = {row["key"]: row for row in plan["stages"]}
    for key, argv in commands.items():
        if rows[key]["argv"] != argv:
            raise CorpusExecutorPlanCompilerError(f"{key}: compiled argv mismatch")
    if rows["corpus_coverage"]["enabled"] is not True:
        raise CorpusExecutorPlanCompilerError("corpus inspection must be the only enabled compiled stage")
    if rows["basis_inventory_regeneration"]["enabled"] or rows["replay_catalog_export"]["enabled"]:
        raise CorpusExecutorPlanCompilerError("downstream corpus stages must remain disabled")
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
    print(json.dumps({"status": receipt["status"], "enabled_stage": receipt["enabled_stage"], "plan": str(args.plan_out)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
