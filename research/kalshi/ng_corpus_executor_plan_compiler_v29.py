#!/usr/bin/env python3
"""Compile a complete readiness-v38 executor plan from an explicit command manifest.

V28 configures the historical corpus and G15 chain through fixed-outcome lesson
adjudication. Readiness v38 adds the complete G15-to-G16 lineage, pre-cutoff G16
replay/posterior/curve chain, immutable curve locks, separate G16 scoring, and the
attribution-bound publication gate. This compiler closes the operational gap without
inventing paths: every remaining command must be supplied in a fingerprinted manifest.
Missing commands remain visible blockers and no G16 stage is enabled by compilation.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v28 as v28
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v29"
STATUS = "G16_ATTRIBUTION_BOUND_V38_EXECUTOR_PLAN_COMPILED"
MANIFEST_SCHEMA = "ng_v38_execution_extension_manifest.v1"
MANIFEST_READY = "V38_EXECUTION_EXTENSION_MANIFEST_READY"
MANIFEST_BLOCKED = "V38_EXECUTION_EXTENSION_MANIFEST_BLOCKED"

PREFIX_STAGES = tuple(v28.CONFIGURED_STAGES)
READINESS_STAGES = tuple(spec.key for spec in readiness.STAGES)
if READINESS_STAGES[: len(PREFIX_STAGES)] != PREFIX_STAGES:
    raise RuntimeError("readiness-v38 no longer preserves the durable v33 prefix")
EXTENSION_STAGES = READINESS_STAGES[len(PREFIX_STAGES) :]
if not EXTENSION_STAGES or EXTENSION_STAGES[-1] != "g16_attribution_bound_publication":
    raise RuntimeError("readiness-v38 extension boundary is incomplete")


class CorpusExecutorPlanCompilerV29Error(ValueError):
    pass


def _fp(value: Any) -> str:
    return fingerprinting._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV29Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV29Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    false_fields = (
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in false_fields:
        if value.get(field) is not False:
            raise CorpusExecutorPlanCompilerV29Error(f"{label} must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusExecutorPlanCompilerV29Error(f"{label} must preserve one signal authority")
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusExecutorPlanCompilerV29Error(f"{label} must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusExecutorPlanCompilerV29Error(f"{label} must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusExecutorPlanCompilerV29Error(f"{label} must preserve tastytrade")


def _canonical_output_paths(artifact_dir: Path) -> dict[str, str]:
    by_key = {spec.key: spec for spec in readiness.STAGES}
    return {
        key: str((artifact_dir / by_key[key].filename).resolve(strict=False))
        for key in EXTENSION_STAGES
    }


def _entrypoint(key: str) -> list[str]:
    value = list(executor.SUGGESTED_ENTRYPOINTS.get(key, ()))
    if not value:
        raise CorpusExecutorPlanCompilerV29Error(
            f"{key}: readiness-v38 executor has no canonical entrypoint"
        )
    return value


def _command_blockers(key: str, argv: Sequence[str], output_path: str) -> list[str]:
    blockers: list[str] = []
    if not argv or not all(isinstance(token, str) and token for token in argv):
        return [f"{key}:MISSING_OR_INVALID_COMMAND"]
    expected = _entrypoint(key)
    if list(argv[: len(expected)]) != expected:
        blockers.append(f"{key}:ENTRYPOINT_MISMATCH")
    if output_path not in argv:
        blockers.append(f"{key}:PRIMARY_OUTPUT_NOT_BOUND")
    lowered = " ".join(argv).lower()
    forbidden = {
        "ibkr": "IBKR_FORBIDDEN",
        "interactive_brokers": "IBKR_FORBIDDEN",
        "ng_brain.json": "BRAIN_WRITE_PATH_FORBIDDEN",
        "--random-shuffle": "RANDOM_SHUFFLE_FORBIDDEN",
        "--shuffle": "RANDOM_SHUFFLE_FORBIDDEN",
        "nymex_options": "OPTIONS_IMPLEMENTATION_FORBIDDEN",
        "options_agent": "OPTIONS_IMPLEMENTATION_FORBIDDEN",
        "option_execution": "OPTIONS_IMPLEMENTATION_FORBIDDEN",
    }
    for token, code in forbidden.items():
        if token in lowered:
            blockers.append(f"{key}:{code}")
    return blockers


def build_extension_manifest(
    *, artifact_dir: Path, commands: Mapping[str, Sequence[str]]
) -> dict[str, Any]:
    command_map = {str(key): list(argv) for key, argv in commands.items()}
    outputs = _canonical_output_paths(artifact_dir)
    blockers: list[str] = []
    extra = sorted(set(command_map) - set(EXTENSION_STAGES))
    if extra:
        blockers.extend(f"UNDECLARED_STAGE_COMMAND:{key}" for key in extra)
    normalized: dict[str, list[str]] = {}
    for key in EXTENSION_STAGES:
        argv = command_map.get(key, [])
        normalized[key] = list(argv)
        blockers.extend(_command_blockers(key, argv, outputs[key]))
    by_key = {spec.key: spec for spec in readiness.STAGES}
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "status": MANIFEST_READY if not blockers else MANIFEST_BLOCKED,
        "stage_order": list(EXTENSION_STAGES),
        "commands": normalized,
        "primary_output_paths": outputs,
        "expected_outputs": {key: by_key[key].filename for key in EXTENSION_STAGES},
        "requires_fixed_outcomes": {
            key: (not by_key[key].pre_outcome) for key in EXTENSION_STAGES
        },
        "blockers": blockers,
        "stand_downs": [
            {
                "scope": "G16_EXECUTION_EXTENSION",
                "reason": blocker,
                "action": "SUPPLY_CANONICAL_COMMAND_AND_STAND_DOWN",
            }
            for blocker in blockers
        ],
        "all_extension_stages_disabled_at_compile": True,
        "outcome_paths_exposed_at_compile": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_action": (
            "COMPILE_READINESS_V38_EXECUTOR_PLAN"
            if not blockers
            else "REPAIR_EXTENSION_COMMAND_BLOCKERS_AND_STAND_DOWN"
        ),
    }
    manifest["fingerprint"] = _fp(manifest)
    validate_extension_manifest(manifest, require_ready=False)
    return manifest


def validate_extension_manifest(
    value: Mapping[str, Any], *, require_ready: bool = True
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != MANIFEST_SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPlanCompilerV29Error("extension manifest schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="extension manifest")
    if checked.get("stage_order") != list(EXTENSION_STAGES):
        raise CorpusExecutorPlanCompilerV29Error("extension manifest stage order mismatch")
    commands = checked.get("commands")
    outputs = checked.get("primary_output_paths")
    expected_outputs = checked.get("expected_outputs")
    fixed = checked.get("requires_fixed_outcomes")
    if not all(isinstance(item, Mapping) for item in (commands, outputs, expected_outputs, fixed)):
        raise CorpusExecutorPlanCompilerV29Error("extension manifest mappings are incomplete")
    exact = set(EXTENSION_STAGES)
    for label, mapping in (
        ("commands", commands),
        ("primary outputs", outputs),
        ("expected outputs", expected_outputs),
        ("outcome classification", fixed),
    ):
        if set(mapping) != exact:
            raise CorpusExecutorPlanCompilerV29Error(f"extension manifest {label} keys mismatch")
    by_key = {spec.key: spec for spec in readiness.STAGES}
    rebuilt_blockers: list[str] = []
    for key in EXTENSION_STAGES:
        output_path = outputs[key]
        if not isinstance(output_path, str) or Path(output_path).name != by_key[key].filename:
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: primary output path mismatch")
        if expected_outputs[key] != by_key[key].filename:
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: expected output mismatch")
        if fixed[key] is not (not by_key[key].pre_outcome):
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: outcome classification mismatch")
        argv = commands[key]
        if not isinstance(argv, list):
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: command must be a list")
        rebuilt_blockers.extend(_command_blockers(key, argv, output_path))
    if checked.get("blockers") != rebuilt_blockers:
        raise CorpusExecutorPlanCompilerV29Error("extension manifest blockers were altered")
    expected_status = MANIFEST_READY if not rebuilt_blockers else MANIFEST_BLOCKED
    if checked.get("status") != expected_status:
        raise CorpusExecutorPlanCompilerV29Error("extension manifest status mismatch")
    if checked.get("all_extension_stages_disabled_at_compile") is not True:
        raise CorpusExecutorPlanCompilerV29Error("extension stages must remain disabled at compile")
    if checked.get("outcome_paths_exposed_at_compile") is not False:
        raise CorpusExecutorPlanCompilerV29Error("compile manifest must not expose outcome paths")
    if require_ready and rebuilt_blockers:
        raise CorpusExecutorPlanCompilerV29Error(
            "extension manifest is blocked: " + "; ".join(rebuilt_blockers)
        )
    return copy.deepcopy(dict(value))


def _commands_from_plan(plan: Mapping[str, Any], keys: Sequence[str]) -> dict[str, list[str]]:
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    return {key: list(rows[key].get("argv") or []) for key in keys}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, Sequence[str]], *, compiled: bool
) -> None:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV29Error(str(error)) from error
    rows = list(plan.get("stages") or [])
    if [row.get("key") for row in rows] != list(READINESS_STAGES):
        raise CorpusExecutorPlanCompilerV29Error("compiled plan does not use readiness-v38 order")
    by_key = {spec.key: spec for spec in readiness.STAGES}
    for row in rows:
        key = str(row.get("key"))
        if list(row.get("argv") or []) != list(commands[key]):
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: command vector mismatch")
        if row.get("expected_output") != by_key[key].filename:
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: output contract mismatch")
        if row.get("requires_fixed_outcomes") is not (not by_key[key].pre_outcome):
            raise CorpusExecutorPlanCompilerV29Error(f"{key}: outcome boundary mismatch")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV29Error(f"{key}: compiled enablement mismatch")
    if compiled and plan.get("outcome_paths") != []:
        raise CorpusExecutorPlanCompilerV29Error("compiled v38 plan must not expose outcomes")
    if [row.get("key") for row in rows[-4:]] != [
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        "g16_attribution_bound_publication",
    ]:
        raise CorpusExecutorPlanCompilerV29Error("G16 lock/publication tail changed")


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    upstream_plan: Mapping[str, Any],
    upstream_receipt: Mapping[str, Any],
    extension_manifest: Mapping[str, Any],
    verify_files: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    upstream_commands = _commands_from_plan(upstream_plan, PREFIX_STAGES)
    try:
        v28.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands=upstream_commands,
            verify_files=verify_files,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV29Error(
            f"upstream v33 compiler provenance is invalid: {error}"
        ) from error
    manifest = validate_extension_manifest(extension_manifest, require_ready=True)
    extension_commands = {
        key: list(manifest["commands"][key]) for key in EXTENSION_STAGES
    }
    commands = {**upstream_commands, **extension_commands}
    plan = executor.build_plan(artifact_dir, working_directory)
    for key in READINESS_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    _validate_plan(plan, commands, compiled=True)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": _fp(list(READINESS_STAGES)),
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": _fp(commands),
        "configured_stages": list(READINESS_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "extension_stage_count": len(EXTENSION_STAGES),
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "upstream_v33_plan_fingerprint": upstream_plan.get("fingerprint"),
        "upstream_v33_receipt_fingerprint": upstream_receipt.get("fingerprint"),
        "upstream_v33_plan": copy.deepcopy(dict(upstream_plan)),
        "upstream_v33_receipt": copy.deepcopy(dict(upstream_receipt)),
        "extension_manifest": copy.deepcopy(manifest),
        "all_extension_stages_configured_but_disabled": True,
        "outcome_paths_exposed_at_compile": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_V38_FIRST_BLOCKING_STAGE",
    }
    receipt["fingerprint"] = _fp(receipt)
    validate_receipt(
        receipt,
        plan=plan,
        commands=commands,
        verify_files=False,
    )
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, Sequence[str]],
    verify_files: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExecutorPlanCompilerV29Error("compiler v29 receipt schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v29 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": _fp(list(READINESS_STAGES)),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": _fp(commands),
        "configured_stages": list(READINESS_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "extension_stage_count": len(EXTENSION_STAGES),
        "all_extension_stages_configured_but_disabled": True,
        "outcome_paths_exposed_at_compile": False,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV29Error(f"compiler v29 field mismatch: {field}")
    upstream_plan = checked.get("upstream_v33_plan")
    upstream_receipt = checked.get("upstream_v33_receipt")
    manifest = checked.get("extension_manifest")
    if not all(isinstance(item, Mapping) for item in (upstream_plan, upstream_receipt, manifest)):
        raise CorpusExecutorPlanCompilerV29Error("compiler v29 lacks embedded provenance")
    upstream_commands = _commands_from_plan(upstream_plan, PREFIX_STAGES)
    try:
        v28.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands=upstream_commands,
            verify_files=verify_files,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV29Error(
            f"embedded v33 compiler provenance is invalid: {error}"
        ) from error
    validated_manifest = validate_extension_manifest(manifest, require_ready=True)
    if checked.get("extension_manifest_fingerprint") != validated_manifest.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV29Error("extension manifest fingerprint mismatch")
    if checked.get("upstream_v33_plan_fingerprint") != upstream_plan.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV29Error("upstream plan fingerprint mismatch")
    if checked.get("upstream_v33_receipt_fingerprint") != upstream_receipt.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV29Error("upstream receipt fingerprint mismatch")
    return copy.deepcopy(dict(value))


def _selftest_commands(artifact_dir: Path) -> dict[str, list[str]]:
    outputs = _canonical_output_paths(artifact_dir)
    return {
        key: [*_entrypoint(key), "--out", outputs[key]]
        for key in EXTENSION_STAGES
    }


def selftest() -> int:
    artifact_dir = Path("/tmp/ng-v38-manifest-selftest")
    ready = build_extension_manifest(
        artifact_dir=artifact_dir,
        commands=_selftest_commands(artifact_dir),
    )
    assert ready["status"] == MANIFEST_READY
    assert not ready["blockers"]
    blocked = build_extension_manifest(artifact_dir=artifact_dir, commands={})
    assert blocked["status"] == MANIFEST_BLOCKED
    assert blocked["blockers"]
    bad = copy.deepcopy(ready)
    key = EXTENSION_STAGES[0]
    bad["commands"][key][1] = "substituted.py"
    bad.pop("fingerprint", None)
    bad["fingerprint"] = _fp(bad)
    try:
        validate_extension_manifest(bad)
    except CorpusExecutorPlanCompilerV29Error:
        pass
    else:
        raise AssertionError("entrypoint substitution was not rejected")
    print("[ng_corpus_executor_plan_compiler_v29] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser("manifest", help="build a ready or blocked extension manifest")
    template.add_argument("--artifact-dir", type=Path, required=True)
    template.add_argument("--commands", type=Path, required=True)
    template.add_argument("--out", type=Path, required=True)

    compile_parser = subparsers.add_parser("compile", help="compile the complete v38 plan")
    compile_parser.add_argument("--artifact-dir", type=Path, required=True)
    compile_parser.add_argument("--working-directory", type=Path, required=True)
    compile_parser.add_argument("--upstream-plan", type=Path, required=True)
    compile_parser.add_argument("--upstream-receipt", type=Path, required=True)
    compile_parser.add_argument("--extension-manifest", type=Path, required=True)
    compile_parser.add_argument("--plan-out", type=Path, required=True)
    compile_parser.add_argument("--receipt-out", type=Path, required=True)
    compile_parser.add_argument("--skip-file-verification", action="store_true")

    subparsers.add_parser("selftest")
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    if args.command == "manifest":
        source = _load(args.commands)
        commands = source.get("commands", source)
        if not isinstance(commands, Mapping):
            parser.error("commands JSON must be an object or contain a commands object")
        result = build_extension_manifest(artifact_dir=args.artifact_dir, commands=commands)
        _write(args.out, result)
        print(f"[ng_corpus_executor_plan_compiler_v29] {result['status']} blockers={len(result['blockers'])}")
        return 0 if result["status"] == MANIFEST_READY else 2

    upstream_plan = _load(args.upstream_plan)
    upstream_receipt = _load(args.upstream_receipt)
    extension_manifest = _load(args.extension_manifest)
    plan, receipt = build_compiled_plan(
        artifact_dir=args.artifact_dir,
        working_directory=args.working_directory,
        upstream_plan=upstream_plan,
        upstream_receipt=upstream_receipt,
        extension_manifest=extension_manifest,
        verify_files=not args.skip_file_verification,
    )
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(
        "[ng_corpus_executor_plan_compiler_v29] "
        f"{receipt['status']} stages={len(receipt['configured_stages'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
