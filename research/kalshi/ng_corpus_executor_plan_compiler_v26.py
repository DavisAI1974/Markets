#!/usr/bin/env python3
"""Compile the stable historical plan against prepared-normalized identity readiness v31.

V30 proves source-native identity in the materialized raw corpus. V31 additionally
requires the exact normalized G15 files that will enter causal replay to preserve the
manifest dataset, publisher, instrument, raw symbol, definition period, lane type,
and chronological event-time order. The guard is armed only after the exact replay
catalog and broad alignment gates are ready, and before G15 replay.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v25 as v25
import ng_g15_prepared_normalized_identity_guard as prepared_guard
import ng_historical_refinement_executor_v27 as executor
import ng_historical_refinement_readiness_v31 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v26"
STATUS = "G15_PREPARED_NORMALIZED_IDENTITY_BOUND_EXECUTOR_PLAN_COMPILED"
CONFIGURED_STAGES = (*v25.CONFIGURED_STAGES, "g15_prepared_normalized_identity")


class CorpusExecutorPlanCompilerV26Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV26Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV26Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v25._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV26Error(str(error)) from error


def _validate_prepared_identity(
    *,
    bridge: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    guard_receipt: Mapping[str, Any],
    verify_files: bool = True,
) -> dict[str, Any]:
    try:
        prepared_guard.validate_guard(guard_receipt, verify_files=verify_files)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV26Error(
            f"prepared normalized identity guard is invalid: {error}"
        ) from error
    checked = copy.deepcopy(dict(guard_receipt))
    required = {
        "status": prepared_guard.READY,
        "blockers": [],
        "all_publishers_explicit_and_positive": True,
        "all_rows_match_exact_manifest_identity": True,
        "all_events_within_definition_and_lane_periods": True,
        "all_sources_chronological": True,
        "definitions_precede_trade_and_mbo_replay": True,
        "next_action": "RUN_EXACT_G15_CAUSAL_REPLAY",
    }
    for field, expected in required.items():
        if checked.get(field) != expected:
            raise CorpusExecutorPlanCompilerV26Error(
                f"prepared normalized identity field mismatch: {field}"
            )
    if checked.get("bridge") != dict(bridge):
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared normalized identity does not embed the supplied G15 bridge"
        )
    if checked.get("prepared_index") != dict(prepared_index):
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared normalized identity does not embed the supplied prepared index"
        )
    if checked.get("bridge_fingerprint") != bridge.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV26Error("prepared bridge fingerprint mismatch")
    if checked.get("prepared_corpus_fingerprint") != prepared_index.get(
        "prepared_corpus_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV26Error("prepared corpus fingerprint mismatch")
    for field in (
        "fingerprint",
        "bridge_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "source_evidence_fingerprint",
    ):
        if not checked.get(field):
            raise CorpusExecutorPlanCompilerV26Error(
                f"prepared normalized identity lacks required field: {field}"
            )
    source_count = checked.get("source_count")
    expected_count = checked.get("expected_source_count")
    if not isinstance(source_count, int) or source_count <= 0:
        raise CorpusExecutorPlanCompilerV26Error("prepared identity source count is invalid")
    if not isinstance(expected_count, int) or source_count != expected_count:
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared identity source count does not equal the canonical expected count"
        )
    _authority(checked, label="prepared normalized identity guard")
    return checked


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
    materialization_provenance_path: Path,
    source_identity_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
    g15_bridge_path: Path,
    prepared_index_path: Path,
    prepared_identity_path: Path,
) -> dict[str, list[str]]:
    commands = v25._commands(
        artifact_dir=artifact_dir,
        resolution_spec_path=resolution_spec_path,
        expected_day_receipt_path=expected_day_receipt_path,
        finalization_receipt_path=finalization_receipt_path,
        resolution_receipt_path=resolution_receipt_path,
        capture_spec_path=capture_spec_path,
        capture_receipt_path=capture_receipt_path,
        materialization_spec_path=materialization_spec_path,
        materialization_receipt_path=materialization_receipt_path,
        materialization_provenance_path=materialization_provenance_path,
        source_identity_path=source_identity_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
    )
    commands["g15_prepared_normalized_identity"] = [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
        "--bridge",
        str(g15_bridge_path.resolve(strict=False)),
        "--prepared-index",
        str(prepared_index_path.resolve(strict=False)),
        "--out",
        str(prepared_identity_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV26Error(str(error)) from error
    rows_list = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows_list]
    expected_order = [spec.key for spec in readiness.STAGES]
    if keys != expected_order:
        raise CorpusExecutorPlanCompilerV26Error(
            "compiled plan does not use the readiness-v31 stage order"
        )
    if list(CONFIGURED_STAGES) != expected_order[: len(CONFIGURED_STAGES)]:
        raise CorpusExecutorPlanCompilerV26Error(
            "configured stages are not the exact readiness-v31 historical prefix"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key in CONFIGURED_STAGES:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            raise CorpusExecutorPlanCompilerV26Error(f"configured stage missing: {key}")
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV26Error(f"{key}: command vector mismatch")
        if row.get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV26Error(f"{key}: must remain pre-outcome")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV26Error(
                    f"{key}: compiled enablement mismatch"
                )
    guard = rows["g15_prepared_normalized_identity"]
    if guard.get("expected_output") != "g15_prepared_normalized_identity_guard.json":
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared normalized identity artifact was substituted"
        )
    if guard.get("suggested_entrypoint") != [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
    ]:
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared normalized identity entrypoint was substituted"
        )
    guard_index = keys.index("g15_prepared_normalized_identity")
    if keys[guard_index - 1] != "broad_corpus_exact_partition" or keys[
        guard_index + 1
    ] != "g15_exact_replay":
        raise CorpusExecutorPlanCompilerV26Error(
            "prepared normalized identity must remain after exact broad alignment and before G15 replay"
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
    materialization_provenance_path: Path,
    source_identity_path: Path,
    inventory_receipt_path: Path,
    broad_plan_path: Path,
    slice_bundle_path: Path,
    target_plan_path: Path,
    g15_bridge_path: Path,
    prepared_index_path: Path,
    prepared_identity_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bridge = _load(g15_bridge_path)
    prepared_index = _load(prepared_index_path)
    identity = _validate_prepared_identity(
        bridge=bridge,
        prepared_index=prepared_index,
        guard_receipt=_load(prepared_identity_path),
    )
    upstream_plan, upstream_receipt = v25.build_compiled_plan(
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
        materialization_provenance_path=materialization_provenance_path,
        source_identity_path=source_identity_path,
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
        materialization_provenance_path=materialization_provenance_path,
        source_identity_path=source_identity_path,
        inventory_receipt_path=inventory_receipt_path,
        broad_plan_path=broad_plan_path,
        slice_bundle_path=slice_bundle_path,
        target_plan_path=target_plan_path,
        g15_bridge_path=g15_bridge_path,
        prepared_index_path=prepared_index_path,
        prepared_identity_path=prepared_identity_path,
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    for key in CONFIGURED_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    _validate_plan(plan, commands, compiled=True)
    upstream_commands = {
        str(row["key"]): list(row.get("argv") or [])
        for row in upstream_plan.get("stages") or []
        if str(row.get("key")) in v25.CONFIGURED_STAGES
    }
    receipt: dict[str, Any] = {
        **copy.deepcopy(upstream_receipt),
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "prepared_identity_guard_fingerprint": identity["fingerprint"],
        "g15_bridge_fingerprint": identity["bridge_fingerprint"],
        "g15_manifest_fingerprint": identity["manifest_fingerprint"],
        "prepared_corpus_fingerprint": identity["prepared_corpus_fingerprint"],
        "prepared_source_evidence_fingerprint": identity[
            "source_evidence_fingerprint"
        ],
        "prepared_source_count": identity["source_count"],
        "prepared_identity_guard": copy.deepcopy(identity),
        "g15_bridge": copy.deepcopy(bridge),
        "prepared_index": copy.deepcopy(prepared_index),
        "upstream_v30_compiler_receipt": copy.deepcopy(upstream_receipt),
        "upstream_v30_execution_plan": copy.deepcopy(upstream_plan),
        "upstream_v30_commands": copy.deepcopy(upstream_commands),
        "prepared_normalized_identity_required_before_g15_replay": True,
        "prepared_publishers_explicit_and_positive": True,
        "prepared_rows_exact_manifest_identity": True,
        "prepared_events_definition_and_lane_bounded": True,
        "prepared_sources_chronological": True,
        "prepared_definitions_precede_trade_and_mbo_replay": True,
        "g15_replay_remains_disabled": True,
        "all_configured_stages_pre_outcome": True,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_PREPARED_IDENTITY_PIPELINE",
    }
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands, verify_files=False)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
    verify_files: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV26Error(
            "compiler v26 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v26 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "prepared_normalized_identity_required_before_g15_replay": True,
        "prepared_publishers_explicit_and_positive": True,
        "prepared_rows_exact_manifest_identity": True,
        "prepared_events_definition_and_lane_bounded": True,
        "prepared_sources_chronological": True,
        "prepared_definitions_precede_trade_and_mbo_replay": True,
        "g15_replay_remains_disabled": True,
        "all_configured_stages_pre_outcome": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV26Error(
                f"compiler v26 field mismatch: {field}"
            )
    guard = checked.get("prepared_identity_guard")
    bridge = checked.get("g15_bridge")
    prepared_index = checked.get("prepared_index")
    if not all(isinstance(item, Mapping) for item in (guard, bridge, prepared_index)):
        raise CorpusExecutorPlanCompilerV26Error(
            "compiler v26 lacks embedded prepared-identity provenance"
        )
    identity = _validate_prepared_identity(
        bridge=bridge,
        prepared_index=prepared_index,
        guard_receipt=guard,
        verify_files=verify_files,
    )
    fingerprint_fields = {
        "prepared_identity_guard_fingerprint": identity["fingerprint"],
        "g15_bridge_fingerprint": identity["bridge_fingerprint"],
        "g15_manifest_fingerprint": identity["manifest_fingerprint"],
        "prepared_corpus_fingerprint": identity["prepared_corpus_fingerprint"],
        "prepared_source_evidence_fingerprint": identity[
            "source_evidence_fingerprint"
        ],
        "prepared_source_count": identity["source_count"],
    }
    for field, expected_value in fingerprint_fields.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV26Error(
                f"compiler v26 prepared identity mismatch: {field}"
            )
    upstream_receipt = checked.get("upstream_v30_compiler_receipt")
    upstream_plan = checked.get("upstream_v30_execution_plan")
    upstream_commands = checked.get("upstream_v30_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV26Error(
            "compiler v26 lacks embedded v30 compiler provenance"
        )
    try:
        v25.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands={str(key): list(argv) for key, argv in upstream_commands.items()},
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV26Error(
            f"embedded v30 compiler provenance is invalid: {error}"
        ) from error
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
    parser.add_argument("--materialization-provenance", type=Path, required=True)
    parser.add_argument("--source-identity", type=Path, required=True)
    parser.add_argument("--inventory-receipt", type=Path, required=True)
    parser.add_argument("--broad-plan", type=Path, required=True)
    parser.add_argument("--slice-bundle", type=Path, required=True)
    parser.add_argument("--target-plan", type=Path, required=True)
    parser.add_argument("--g15-bridge", type=Path, required=True)
    parser.add_argument("--prepared-index", type=Path, required=True)
    parser.add_argument("--prepared-identity", type=Path, required=True)
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
        materialization_provenance_path=args.materialization_provenance,
        source_identity_path=args.source_identity,
        inventory_receipt_path=args.inventory_receipt,
        broad_plan_path=args.broad_plan,
        slice_bundle_path=args.slice_bundle,
        target_plan_path=args.target_plan,
        g15_bridge_path=args.g15_bridge,
        prepared_index_path=args.prepared_index,
        prepared_identity_path=args.prepared_identity,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
