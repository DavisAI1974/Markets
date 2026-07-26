#!/usr/bin/env python3
"""Fail closed when v38 stage commands omit arguments required by their real CLIs.

The probe invokes only ``--help``. It never opens corpus or outcome files.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v29 as compiler

SCHEMA = "ng_v38_execution_command_contract_gate.v1"
READY = "V38_EXECUTION_COMMAND_CONTRACT_READY"
BLOCKED = "V38_EXECUTION_COMMAND_CONTRACT_BLOCKED"
EXTENSION_STAGES = tuple(compiler.EXTENSION_STAGES)


class V38ExecutionCommandContractError(ValueError):
    pass


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V38ExecutionCommandContractError(f"JSON artifact must be an object: {path}")
    return value


def _authority(value: Mapping[str, Any], label: str) -> None:
    compiler._authority(value, label=label)
    for field in ("paid_live_data_assumed", "corpus_files_opened", "outcome_files_opened"):
        if value.get(field) is not False:
            raise V38ExecutionCommandContractError(f"{label} must keep {field}=false")


def _usage(help_text: str) -> str:
    lines = help_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.lower().startswith("usage:")), None)
    if start is None:
        return ""
    result = [lines[start].split(":", 1)[1].strip()]
    for line in lines[start + 1 :]:
        if not line.startswith((" ", "\t")) or not line.strip():
            break
        result.append(line.strip())
    return " ".join(result)


def _without_optional(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\[[^\[\]]*\]", " ", text)
    return text


def required_option_contract(help_text: str) -> tuple[list[str], list[list[str]]]:
    usage = _without_optional(_usage(help_text))
    groups: list[list[str]] = []
    for group in re.findall(r"\(([^()]*)\)", usage):
        if "|" in group:
            options = sorted(set(re.findall(r"--[A-Za-z0-9][A-Za-z0-9_-]*", group)))
            if options:
                groups.append(options)
            usage = usage.replace(f"({group})", " ")
    singles = sorted(
        option
        for option in set(re.findall(r"--[A-Za-z0-9][A-Za-z0-9_-]*", usage))
        if option != "--help"
    )
    return singles, groups


def _present(argv: Sequence[str]) -> set[str]:
    return {
        str(token).split("=", 1)[0]
        for token in argv
        if isinstance(token, str) and token.startswith("--")
    }


def _placeholders(argv: Sequence[str]) -> list[str]:
    bad = []
    for token in map(str, argv):
        lowered = token.lower()
        if ("<" in token and ">" in token) or "${" in token or "{{" in token or lowered in {
            "todo",
            "tbd",
            "replace_me",
            "placeholder",
        }:
            bad.append(token)
    return bad


def _run_help(command: Sequence[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _subcommands(help_text: str) -> set[str]:
    choices: set[str] = set()
    for group in re.findall(r"\{([^{}]+)\}", _usage(help_text)):
        choices.update(part.strip() for part in group.split(",") if part.strip())
    return choices


def probe_command(
    stage_key: str,
    argv: Sequence[str],
    *,
    working_directory: Path,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    cwd = working_directory.resolve(strict=False)
    command = list(map(str, argv))
    blockers: list[str] = []
    script: Path | None = None
    help_command: list[str] = []
    help_text = ""

    if len(command) < 2 or not Path(command[0]).name.startswith("python"):
        blockers.append("PYTHON_ENTRYPOINT_REQUIRED")
    else:
        script = Path(command[1])
        script = (cwd / script).resolve(strict=False) if not script.is_absolute() else script.resolve(strict=False)
        try:
            script.relative_to(cwd)
        except ValueError:
            blockers.append("SCRIPT_PATH_ESCAPES_WORKING_DIRECTORY")
        if not script.is_file():
            blockers.append("SCRIPT_NOT_FOUND")

    placeholders = _placeholders(command)
    if placeholders:
        blockers.append("PLACEHOLDER_ARGUMENTS_FORBIDDEN")

    if not blockers and script is not None:
        executable = sys.executable
        try:
            root = _run_help([executable, str(script), "--help"], cwd, timeout_seconds)
            if root.returncode != 0:
                blockers.append(f"ROOT_HELP_EXIT_{root.returncode}")
            else:
                selected = command[2] if len(command) > 2 and command[2] in _subcommands(root.stdout) else None
                help_command = [executable, str(script), *([selected] if selected else []), "--help"]
                result = _run_help(help_command, cwd, timeout_seconds)
                help_text = result.stdout or ""
                if result.returncode != 0:
                    blockers.append(f"HELP_EXIT_{result.returncode}")
        except (OSError, subprocess.TimeoutExpired) as error:
            blockers.append(f"HELP_PROBE_FAILED:{type(error).__name__}")

    required, groups = required_option_contract(help_text)
    present = _present(command)
    missing = [option for option in required if option not in present]
    missing_groups = [group for group in groups if not present.intersection(group)]
    blockers.extend(f"MISSING_REQUIRED_OPTION:{option}" for option in missing)
    blockers.extend("MISSING_REQUIRED_OPTION_GROUP:" + "|".join(group) for group in missing_groups)

    probe: dict[str, Any] = {
        "stage_key": stage_key,
        "argv": command,
        "working_directory": str(cwd),
        "script_path": str(script) if script else None,
        "script_sha256": _sha256(script) if script and script.is_file() else None,
        "help_command": help_command,
        "help_sha256": hashlib.sha256(help_text.encode()).hexdigest() if help_text else None,
        "required_options": required,
        "required_any_of_groups": groups,
        "present_options": sorted(present),
        "missing_required_options": missing,
        "missing_required_any_of_groups": missing_groups,
        "placeholder_tokens": placeholders,
        "blockers": blockers,
        "ready": not blockers,
    }
    probe["fingerprint"] = _fp(probe)
    return probe


def build_gate(
    extension_manifest: Mapping[str, Any],
    *,
    working_directory: Path,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    manifest = compiler.validate_extension_manifest(extension_manifest, require_ready=True)
    probes = [
        probe_command(
            key,
            manifest["commands"][key],
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
        )
        for key in EXTENSION_STAGES
    ]
    blockers = [f"{p['stage_key']}:{b}" for p in probes for b in p["blockers"]]
    gate: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY if not blockers else BLOCKED,
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "extension_manifest": copy.deepcopy(manifest),
        "working_directory": str(working_directory.resolve(strict=False)),
        "stage_order": list(EXTENSION_STAGES),
        "stage_probes": probes,
        "stage_probe_fingerprints": {p["stage_key"]: p["fingerprint"] for p in probes},
        "blockers": blockers,
        "stand_downs": [
            {
                "scope": "G16_EXECUTION_COMMAND_CONTRACT",
                "reason": blocker,
                "action": "REPAIR_COMMAND_ARGUMENT_CONTRACT_AND_STAND_DOWN",
            }
            for blocker in blockers
        ],
        "help_only_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
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
        "next_action": "COMPILE_V38_PLAN_WITH_VALIDATED_COMMAND_CONTRACT"
        if not blockers
        else "REPAIR_COMMAND_ARGUMENT_CONTRACT_AND_STAND_DOWN",
    }
    gate["fingerprint"] = _fp(gate)
    validate_gate(gate, verify_runtime=False, require_ready=False)
    return gate


def validate_gate(
    value: Mapping[str, Any],
    *,
    verify_runtime: bool = True,
    require_ready: bool = True,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38ExecutionCommandContractError("command-contract gate schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, "command-contract gate")
    manifest = checked.get("extension_manifest")
    if not isinstance(manifest, Mapping):
        raise V38ExecutionCommandContractError("command-contract gate lacks extension manifest")
    manifest = compiler.validate_extension_manifest(manifest, require_ready=True)
    if checked.get("extension_manifest_fingerprint") != manifest.get("fingerprint"):
        raise V38ExecutionCommandContractError("extension manifest fingerprint mismatch")
    if checked.get("stage_order") != list(EXTENSION_STAGES):
        raise V38ExecutionCommandContractError("command-contract stage order mismatch")
    probes = checked.get("stage_probes")
    if not isinstance(probes, list) or [p.get("stage_key") for p in probes] != list(EXTENSION_STAGES):
        raise V38ExecutionCommandContractError("command-contract probes are incomplete or reordered")
    if verify_runtime:
        rebuilt = build_gate(
            manifest,
            working_directory=Path(str(checked.get("working_directory"))),
            timeout_seconds=timeout_seconds,
        )
        for field in ("status", "stage_probes", "stage_probe_fingerprints", "blockers", "stand_downs"):
            if checked.get(field) != rebuilt.get(field):
                raise V38ExecutionCommandContractError(f"runtime command-contract mismatch: {field}")
    blockers = list(checked.get("blockers") or [])
    if checked.get("status") != (READY if not blockers else BLOCKED):
        raise V38ExecutionCommandContractError("command-contract status mismatch")
    if require_ready and blockers:
        raise V38ExecutionCommandContractError("command contract is blocked: " + "; ".join(blockers))
    return copy.deepcopy(dict(value))


def selftest() -> int:
    assert required_option_contract("usage: x [-h] --input INPUT --out OUT") == (["--input", "--out"], [])
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        script = root / "stage.py"
        script.write_text(
            "import argparse\np=argparse.ArgumentParser()\np.add_argument('--input', required=True)\np.add_argument('--out', required=True)\np.parse_args()\n",
            encoding="utf-8",
        )
        blocked = probe_command("stage", ["python", "stage.py", "--out", "x"], working_directory=root)
        assert "MISSING_REQUIRED_OPTION:--input" in blocked["blockers"]
        ready = probe_command(
            "stage", ["python", "stage.py", "--input", "i", "--out", "o"], working_directory=root
        )
        assert ready["ready"] is True
    print("[ng_v38_execution_command_contract_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--extension-manifest", type=Path, required=True)
    build.add_argument("--working-directory", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--timeout-seconds", type=float, default=10.0)
    validate = sub.add_parser("validate")
    validate.add_argument("--gate", type=Path, required=True)
    validate.add_argument("--skip-runtime", action="store_true")
    sub.add_parser("selftest")
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    if args.command == "validate":
        validate_gate(_load(args.gate), verify_runtime=not args.skip_runtime)
        print("[ng_v38_execution_command_contract_gate] VALID")
        return 0
    gate = build_gate(
        _load(args.extension_manifest),
        working_directory=args.working_directory,
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, gate)
    print(f"[ng_v38_execution_command_contract_gate] {gate['status']} blockers={len(gate['blockers'])}")
    return 0 if gate["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
