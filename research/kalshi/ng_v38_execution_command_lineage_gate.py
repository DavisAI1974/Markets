#!/usr/bin/env python3
"""Verify that every readiness-v38 extension command binds its exact upstream artifacts.

The v29 compiler already verifies stage order, entrypoints, primary outputs, and permanent
authority restrictions. This gate closes a remaining operational gap: a command could use
the right executable and output while omitting or substituting the upstream artifacts that
the readiness LINK_RULES require. The gate is observational and fail-closed. It never
executes a stage, opens outcomes, mutates forecasts/posteriors/ng_brain.json, or starts the
options lane.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v29 as compiler
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_v38_execution_command_lineage_gate.v1"
READY = "V38_EXECUTION_COMMAND_LINEAGE_READY"
BLOCKED = "V38_EXECUTION_COMMAND_LINEAGE_BLOCKED"


class V38ExecutionCommandLineageError(ValueError):
    """Raised when a command-line lineage receipt is inconsistent."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38ExecutionCommandLineageError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise V38ExecutionCommandLineageError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any]) -> None:
    for field in (
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise V38ExecutionCommandLineageError(f"command lineage must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise V38ExecutionCommandLineageError("command lineage must preserve one signal authority")
    if value.get("blind_forecasts_immutable") is not True:
        raise V38ExecutionCommandLineageError("command lineage must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38ExecutionCommandLineageError("command lineage must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38ExecutionCommandLineageError("command lineage must preserve tastytrade")


def _canonical_paths(artifact_dir: Path) -> dict[str, str]:
    return {
        spec.key: str((artifact_dir / spec.filename).resolve(strict=False))
        for spec in readiness.STAGES
    }


def _required_sources() -> dict[str, list[str]]:
    extension = set(compiler.EXTENSION_STAGES)
    required: dict[str, list[str]] = {key: [] for key in compiler.EXTENSION_STAGES}
    for source_key, _source_field, target_key, _target_field in readiness.LINK_RULES:
        if target_key not in extension:
            continue
        if source_key not in required[target_key]:
            required[target_key].append(source_key)
    return required


def _actual_values(argv: Sequence[str]) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(argv):
        if token == "--actual":
            if index + 1 >= len(argv):
                values.append("")
            else:
                values.append(str(argv[index + 1]))
        elif token.startswith("--actual="):
            values.append(token.split("=", 1)[1])
    return values


def _rebuild(
    extension_manifest: Mapping[str, Any], *, artifact_dir: Path
) -> dict[str, Any]:
    manifest = compiler.validate_extension_manifest(extension_manifest, require_ready=True)
    commands = manifest["commands"]
    paths = _canonical_paths(artifact_dir)
    required = _required_sources()
    blockers: list[str] = []
    bindings: dict[str, list[dict[str, Any]]] = {}

    for target_key in compiler.EXTENSION_STAGES:
        argv = list(commands[target_key])
        rows: list[dict[str, Any]] = []
        for source_key in required[target_key]:
            source_path = paths[source_key]
            count = argv.count(source_path)
            rows.append(
                {
                    "source_stage": source_key,
                    "source_artifact": source_path,
                    "occurrences": count,
                    "bound_exactly_once": count == 1,
                }
            )
            if count == 0:
                blockers.append(f"{target_key}:MISSING_SOURCE_ARTIFACT_BINDING:{source_key}")
            elif count != 1:
                blockers.append(f"{target_key}:AMBIGUOUS_SOURCE_ARTIFACT_BINDING:{source_key}")
        bindings[target_key] = rows

        actuals = _actual_values(argv)
        if target_key == "g16_counterfactual_publication":
            if len(actuals) != 1 or not actuals[0]:
                blockers.append(f"{target_key}:EXACT_G16_ACTUAL_BINDING_REQUIRED")
        elif actuals:
            blockers.append(f"{target_key}:RAW_ACTUAL_PATH_FORBIDDEN_BEFORE_SCORING")

    publication_actuals = _actual_values(commands["g16_counterfactual_publication"])
    actual_path = publication_actuals[0] if len(publication_actuals) == 1 else None
    status = READY if not blockers else BLOCKED
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": _fp([spec.key for spec in readiness.STAGES]),
        "extension_stage_order": list(compiler.EXTENSION_STAGES),
        "required_source_stages": required,
        "command_source_bindings": bindings,
        "g16_actual_path": actual_path,
        "g16_actual_exposed_only_at_counterfactual_publication": not any(
            _actual_values(commands[key])
            for key in compiler.EXTENSION_STAGES
            if key != "g16_counterfactual_publication"
        ),
        "blockers": blockers,
        "stand_downs": [
            {
                "scope": "V38_EXECUTION_COMMAND_LINEAGE",
                "reason": blocker,
                "action": "REPAIR_EXACT_COMMAND_ARTIFACT_BINDINGS_AND_STAND_DOWN",
            }
            for blocker in blockers
        ],
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
            "COMPILE_V38_PLAN_WITH_EXACT_COMMAND_LINEAGE"
            if not blockers
            else "REPAIR_COMMAND_LINEAGE_BLOCKERS_AND_STAND_DOWN"
        ),
    }
    result["fingerprint"] = _fp(result)
    return result


def build_gate(
    extension_manifest: Mapping[str, Any], *, artifact_dir: Path
) -> dict[str, Any]:
    result = _rebuild(extension_manifest, artifact_dir=artifact_dir)
    validate_gate(result, extension_manifest=extension_manifest, artifact_dir=artifact_dir, require_ready=False)
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    extension_manifest: Mapping[str, Any],
    artifact_dir: Path,
    require_ready: bool = True,
) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fp(candidate):
        raise V38ExecutionCommandLineageError("command lineage schema or fingerprint mismatch")
    candidate["fingerprint"] = observed
    _authority(candidate)
    rebuilt = _rebuild(extension_manifest, artifact_dir=artifact_dir)
    if candidate != rebuilt:
        raise V38ExecutionCommandLineageError(
            "command lineage differs from deterministic reconstruction"
        )
    if require_ready and candidate.get("blockers"):
        raise V38ExecutionCommandLineageError(
            "command lineage is blocked: " + "; ".join(candidate["blockers"])
        )
    return copy.deepcopy(dict(value))


def _selftest_manifest(artifact_dir: Path) -> dict[str, Any]:
    commands = compiler._selftest_commands(artifact_dir)
    paths = _canonical_paths(artifact_dir)
    for target_key, sources in _required_sources().items():
        for index, source_key in enumerate(sources):
            commands[target_key].extend([f"--source-{index}", paths[source_key]])
    commands["g16_counterfactual_publication"].extend(
        ["--actual", str((artifact_dir / "g16_actual_fixed.json").resolve(strict=False))]
    )
    return compiler.build_extension_manifest(artifact_dir=artifact_dir, commands=commands)


def selftest() -> int:
    artifact_dir = Path("/tmp/ng-v38-command-lineage-selftest")
    manifest = _selftest_manifest(artifact_dir)
    ready = build_gate(manifest, artifact_dir=artifact_dir)
    validate_gate(ready, extension_manifest=manifest, artifact_dir=artifact_dir)
    assert ready["status"] == READY

    broken_manifest = copy.deepcopy(manifest)
    target = next(key for key, rows in ready["command_source_bindings"].items() if rows)
    source_path = ready["command_source_bindings"][target][0]["source_artifact"]
    broken_manifest["commands"][target].remove(source_path)
    broken_manifest.pop("fingerprint", None)
    broken_manifest["fingerprint"] = _fp(broken_manifest)
    blocked = build_gate(broken_manifest, artifact_dir=artifact_dir)
    assert blocked["status"] == BLOCKED
    assert blocked["blockers"]
    print("[ng_v38_execution_command_lineage_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.manifest is None or args.artifact_dir is None or args.out is None:
        parser.error("--manifest, --artifact-dir, and --out are required")
    result = build_gate(_load(args.manifest), artifact_dir=args.artifact_dir)
    _write(args.out, result)
    print(
        "[ng_v38_execution_command_lineage_gate] "
        f"{result['status']} blockers={len(result['blockers'])}"
    )
    return 0 if result["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
