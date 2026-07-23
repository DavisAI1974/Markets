#!/usr/bin/env python3
"""Resume the hardened historical-first NG refinement chain one stage at a time.

This executor is deliberately conservative. It never guesses remote object presence,
never uses a shell, never random-shuffles time series, and never opens fixed outcome
stages unless the operator explicitly enables that boundary. Before every command it
backs up immutable blind forecasts, ``ng_brain.json``, and all already-ready stage
artifacts. Any mutation or upstream regression is restored and recorded as a failed run.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_historical_refinement_readiness as readiness

PLAN_SCHEMA = "ng_historical_refinement_execution_plan.v1"
LEDGER_SCHEMA = "ng_historical_refinement_execution_ledger.v1"
DEFAULT_TIMEOUT_S = 7200
MAX_LOG_TAIL = 4000


class HistoricalRefinementExecutionError(RuntimeError):
    """Raised when a run would violate chronology, provenance, or authority."""


SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    "corpus_coverage": ("python", "ng_corpus_inspection.py", "inspect"),
    "basis_inventory_regeneration": ("python", "ng_corpus_basis_inventory_regeneration.py"),
    "replay_catalog_export": ("python", "ng_corpus_replay_catalog_export.py"),
    "g15_exact_replay": ("python", "ng_g15_exact_replay_completion.py"),
    "g15_exact_refinement": ("python", "ng_g15_exact_refinement_gate.py"),
    "g15_publication": ("python", "ng_g15_exact_publication_gate.py"),
    "g16_corpus_basis": ("python", "ng_g16_corpus_basis_gate.py"),
    "g16_historical_replay": ("python", "ng_g16_historical_replay.py", "replay"),
    "g16_prepared_replay": ("python", "ng_g16_prepared_replay_gate.py"),
    "g16_exact_causal": ("python", "ng_g16_exact_causal_pipeline.py"),
    "g16_prepared_causal_authorization": ("python", "ng_g16_prepared_causal_authorization.py"),
    "g16_prepared_curve_authorization": ("python", "ng_g16_prepared_curve_authorization.py"),
    "g16_prepared_curve_lock": ("python", "ng_g16_prepared_publication_gate.py", "lock"),
    "g16_prepared_publication": ("python", "ng_g16_prepared_publication_gate.py", "publish"),
}

FORBIDDEN_COMMAND_FRAGMENTS = (
    "--shuffle",
    "random_shuffle",
    "random-shuffle",
    "ibkr",
    "interactive brokers",
    "options_lane_started=true",
    "options-implementation",
    "cme_event_contracts_mode=live",
)
SHELL_LAUNCHERS = {"sh", "bash", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}


@dataclass(frozen=True)
class FileState:
    path: str
    exists: bool
    size_bytes: int | None
    sha256: str | None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HistoricalRefinementExecutionError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise HistoricalRefinementExecutionError(f"JSON artifact must be an object: {path}")
    return value


def _resolve_path(value: str, working_directory: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = working_directory / candidate
    return candidate.resolve(strict=False)


def _file_state(path: Path) -> FileState:
    if not path.is_file():
        return FileState(str(path), False, None, None)
    return FileState(str(path), True, path.stat().st_size, _sha256_file(path))


def _state_dict(state: FileState) -> dict[str, Any]:
    return {
        "path": state.path,
        "exists": state.exists,
        "size_bytes": state.size_bytes,
        "sha256": state.sha256,
    }


def build_plan(
    artifact_dir: Path,
    working_directory: Path,
    *,
    protected_paths: Sequence[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    working_directory = working_directory.resolve(strict=False)
    artifact_dir = artifact_dir.resolve(strict=False)
    defaults = protected_paths or (
        ("g15_blind_forecast", "forecasts/grp15.json"),
        ("g16_blind_forecast", "forecasts/grp16.json"),
        ("ng_brain", "knowledge/ng_brain.json"),
    )
    stages = []
    for spec in readiness.STAGES:
        stages.append(
            {
                "key": spec.key,
                "enabled": False,
                "argv": [],
                "cwd": ".",
                "timeout_s": DEFAULT_TIMEOUT_S,
                "requires_fixed_outcomes": not spec.pre_outcome,
                "suggested_entrypoint": list(SUGGESTED_ENTRYPOINTS.get(spec.key, ())),
                "expected_output": spec.filename,
                "next_action": spec.next_action,
            }
        )
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "market": "NG",
        "historical_first": True,
        "artifact_dir": str(artifact_dir),
        "working_directory": str(working_directory),
        "stages": stages,
        "protected_paths": [
            {"role": role, "path": path} for role, path in defaults
        ],
        "outcome_paths": [],
        "remote_presence_inferred": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "note": (
            "Populate argv only for the exact next stage. Commands run with shell=False; "
            "fixed-outcome stages require an explicit runtime authorization flag."
        ),
    }
    plan["fingerprint"] = _fingerprint(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(plan))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != PLAN_SCHEMA or observed != _fingerprint(value):
        raise HistoricalRefinementExecutionError("execution plan schema or fingerprint mismatch")
    for field in (
        "remote_presence_inferred",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise HistoricalRefinementExecutionError(f"execution plan must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementExecutionError("execution plan must preserve one signal authority")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementExecutionError("execution plan must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementExecutionError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementExecutionError("brokerage contract must remain tastytrade, not IBKR")
    stages = value.get("stages")
    expected_keys = [spec.key for spec in readiness.STAGES]
    if not isinstance(stages, list) or [step.get("key") for step in stages] != expected_keys:
        raise HistoricalRefinementExecutionError("execution plan stage order mismatch")
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("requires_fixed_outcomes") is not (not spec.pre_outcome):
            raise HistoricalRefinementExecutionError(f"{spec.key}: fixed-outcome boundary mismatch")
        argv = step.get("argv")
        if not isinstance(argv, list) or not all(isinstance(part, str) and part for part in argv):
            if step.get("enabled"):
                raise HistoricalRefinementExecutionError(f"{spec.key}: enabled step requires non-empty argv")
            if argv != []:
                raise HistoricalRefinementExecutionError(f"{spec.key}: argv must be a string list")
        if argv:
            first = Path(argv[0]).name.lower()
            if first in SHELL_LAUNCHERS or (first.startswith("python") and len(argv) > 1 and argv[1] == "-c"):
                raise HistoricalRefinementExecutionError(f"{spec.key}: shell and inline-code launchers are forbidden")
            lowered = " ".join(argv).lower()
            for fragment in FORBIDDEN_COMMAND_FRAGMENTS:
                if fragment in lowered:
                    raise HistoricalRefinementExecutionError(f"{spec.key}: forbidden command fragment {fragment!r}")
        timeout = step.get("timeout_s")
        if not isinstance(timeout, int) or timeout < 1 or timeout > 86400:
            raise HistoricalRefinementExecutionError(f"{spec.key}: timeout_s must be 1..86400")
    protected = value.get("protected_paths")
    if not isinstance(protected, list) or not protected:
        raise HistoricalRefinementExecutionError("execution plan requires protected blind/brain paths")
    roles = [row.get("role") for row in protected if isinstance(row, Mapping)]
    if len(roles) != len(set(roles)) or "ng_brain" not in roles:
        raise HistoricalRefinementExecutionError("protected path roles must be unique and include ng_brain")
    for row in protected:
        if not isinstance(row, Mapping) or not row.get("role") or not row.get("path"):
            raise HistoricalRefinementExecutionError("protected path rows require role and path")
    outcome_paths = value.get("outcome_paths")
    if not isinstance(outcome_paths, list) or not all(isinstance(path, str) and path for path in outcome_paths):
        raise HistoricalRefinementExecutionError("outcome_paths must be a string list")


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    *,
    enabled: bool = True,
    cwd: str | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    validate_plan(plan)
    result = copy.deepcopy(dict(plan))
    result.pop("fingerprint", None)
    matches = [step for step in result["stages"] if step["key"] == stage_key]
    if len(matches) != 1:
        raise HistoricalRefinementExecutionError(f"unknown stage {stage_key}")
    step = matches[0]
    step["argv"] = list(argv)
    step["enabled"] = bool(enabled)
    if cwd is not None:
        step["cwd"] = cwd
    if timeout_s is not None:
        step["timeout_s"] = timeout_s
    result["fingerprint"] = _fingerprint(result)
    validate_plan(result)
    return result


def _empty_ledger(plan: Mapping[str, Any]) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema": LEDGER_SCHEMA,
        "market": "NG",
        "plan_fingerprint": plan["fingerprint"],
        "entries": [],
        "random_shuffle_used": False,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    ledger["fingerprint"] = _fingerprint(ledger)
    return ledger


def validate_ledger(ledger: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(ledger))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != LEDGER_SCHEMA or observed != _fingerprint(value):
        raise HistoricalRefinementExecutionError("execution ledger schema or fingerprint mismatch")
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementExecutionError("execution ledger belongs to another plan")
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise HistoricalRefinementExecutionError("execution ledger entries must be a list")
    run_ids = [entry.get("run_id") for entry in entries if isinstance(entry, Mapping)]
    if len(run_ids) != len(entries) or len(run_ids) != len(set(run_ids)):
        raise HistoricalRefinementExecutionError("execution ledger run IDs must be unique")
    for field in ("random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started"):
        if value.get(field) is not False:
            raise HistoricalRefinementExecutionError(f"execution ledger must keep {field}=false")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementExecutionError("execution ledger must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW" or value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementExecutionError("execution ledger authority contract mismatch")


def _load_or_create_ledger(path: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return _empty_ledger(plan)
    ledger = _load_json(path)
    validate_ledger(ledger, plan)
    return ledger


def _snapshot_targets(plan: Mapping[str, Any], report: Mapping[str, Any]) -> list[tuple[str, Path]]:
    workdir = Path(str(plan["working_directory"])).resolve(strict=False)
    targets: list[tuple[str, Path]] = []
    for row in plan["protected_paths"]:
        targets.append((str(row["role"]), _resolve_path(str(row["path"]), workdir)))
    for stage in report.get("stages") or []:
        if stage.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            continue
        path = Path(str(stage.get("path") or "")).resolve(strict=False)
        targets.append((f"ready_stage:{stage.get('key')}", path))
    dedup: dict[str, tuple[str, Path]] = {}
    for role, path in targets:
        dedup[str(path)] = (role, path)
    return list(dedup.values())


def _backup_targets(targets: Sequence[tuple[str, Path]], backup_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, (role, path) in enumerate(targets):
        state = _file_state(path)
        backup = backup_root / f"{index:04d}.bak"
        if state.exists:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
        result[str(path)] = {
            "role": role,
            "before": _state_dict(state),
            "backup": str(backup) if state.exists else None,
        }
    return result


def _restore_mutations(backups: Mapping[str, Mapping[str, Any]]) -> list[str]:
    mutated: list[str] = []
    for path_text, record in backups.items():
        path = Path(path_text)
        before = record["before"]
        after = _state_dict(_file_state(path))
        if after == before:
            continue
        mutated.append(f"{record['role']}:{path_text}")
        if before["exists"]:
            source = Path(str(record["backup"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".restore.tmp")
            shutil.copy2(source, temporary)
            os.replace(temporary, path)
        elif path.exists():
            path.unlink()
    return mutated


def _run_id(stage_key: str, plan_fingerprint: str, entry_index: int) -> str:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return hashlib.sha256(f"{stage_key}|{plan_fingerprint}|{entry_index}|{now}".encode()).hexdigest()[:24]


def _append_ledger(path: Path, ledger: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(ledger))
    result.pop("fingerprint", None)
    result["entries"].append(copy.deepcopy(dict(entry)))
    result["fingerprint"] = _fingerprint(result)
    _atomic_json(path, result)
    return result


def _command_environment() -> dict[str, str]:
    allowed = {
        "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
        "PYTHONPATH", "VIRTUAL_ENV", "TMPDIR", "TEMP", "TMP",
        "AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_CONFIG_FILE", "S3_ENDPOINT_URL",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def execute_next(
    plan: Mapping[str, Any],
    ledger_path: Path,
    *,
    allow_fixed_outcomes: bool = False,
    dry_run: bool = False,
    readiness_out: Path | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
    command_runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    validate_plan(plan)
    artifact_dir = Path(str(plan["artifact_dir"]))
    before = readiness.build_readiness_report(
        artifact_dir,
        validator_overrides=validator_overrides,
    )
    readiness.validate_readiness_report(before)
    if readiness_out is not None:
        _atomic_json(readiness_out, before)
    ledger = _load_or_create_ledger(ledger_path, plan)
    first_key = before.get("first_blocking_stage")
    if first_key is None:
        return {
            "status": "CHAIN_COMPLETE",
            "stage": None,
            "readiness_fingerprint": before["fingerprint"],
            "ledger_fingerprint": ledger["fingerprint"],
        }
    spec = next(spec for spec in readiness.STAGES if spec.key == first_key)
    step = next(step for step in plan["stages"] if step["key"] == first_key)
    if not step.get("enabled") or not step.get("argv"):
        return {
            "status": "CONFIGURATION_REQUIRED",
            "stage": first_key,
            "next_action": spec.next_action,
            "suggested_entrypoint": step.get("suggested_entrypoint") or [],
            "readiness_fingerprint": before["fingerprint"],
            "ledger_fingerprint": ledger["fingerprint"],
        }
    if step["requires_fixed_outcomes"] and not allow_fixed_outcomes:
        raise HistoricalRefinementExecutionError(
            f"{first_key}: fixed outcome access is locked; pass explicit allow_fixed_outcomes only after reviewing the curve lock"
        )
    workdir = Path(str(plan["working_directory"])).resolve(strict=False)
    cwd = _resolve_path(str(step.get("cwd") or "."), workdir)
    if not cwd.is_dir():
        raise HistoricalRefinementExecutionError(f"{first_key}: command cwd does not exist: {cwd}")
    outcome_paths = {_resolve_path(path, workdir) for path in plan.get("outcome_paths") or []}
    argv_resolved_paths = {
        _resolve_path(part, cwd)
        for part in step["argv"]
        if "/" in part or "\\" in part or part.endswith(".json") or part.endswith(".jsonl")
    }
    if spec.pre_outcome and outcome_paths.intersection(argv_resolved_paths):
        raise HistoricalRefinementExecutionError(f"{first_key}: pre-outcome command references a fixed outcome path")
    if dry_run:
        return {
            "status": "DRY_RUN",
            "stage": first_key,
            "argv": list(step["argv"]),
            "cwd": str(cwd),
            "requires_fixed_outcomes": step["requires_fixed_outcomes"],
            "readiness_fingerprint": before["fingerprint"],
            "ledger_fingerprint": ledger["fingerprint"],
        }

    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    targets = _snapshot_targets(plan, before)
    result: Any = None
    run_error: str | None = None
    with tempfile.TemporaryDirectory(prefix="ng-refinement-backup-") as tempdir:
        backups = _backup_targets(targets, Path(tempdir))
        try:
            result = command_runner(
                list(step["argv"]),
                cwd=str(cwd),
                timeout=int(step["timeout_s"]),
                capture_output=True,
                text=True,
                shell=False,
                env=_command_environment(),
                check=False,
            )
        except Exception as error:
            run_error = f"{type(error).__name__}: {error}"
        mutated = _restore_mutations(backups)
    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    stdout = "" if result is None else str(getattr(result, "stdout", "") or "")
    stderr = "" if result is None else str(getattr(result, "stderr", "") or "")
    returncode = None if result is None else int(getattr(result, "returncode", 1))
    after = readiness.build_readiness_report(
        artifact_dir,
        validator_overrides=validator_overrides,
    )
    readiness.validate_readiness_report(after)
    if readiness_out is not None:
        _atomic_json(readiness_out, after)
    before_rows = {row["key"]: row for row in before["stages"]}
    after_rows = {row["key"]: row for row in after["stages"]}
    regressed = [
        key
        for key, row in before_rows.items()
        if row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}
        and after_rows[key]["effective_status"] not in {"READY", "READY_WITH_STAND_DOWNS"}
    ]
    target_status = after_rows[first_key]["effective_status"]
    advanced = target_status in {"READY", "READY_WITH_STAND_DOWNS"}
    if mutated:
        status = "PROTECTED_MUTATION_RESTORED"
    elif regressed:
        status = "UPSTREAM_REGRESSION"
    elif run_error is not None:
        status = "COMMAND_ERROR"
    elif returncode != 0:
        status = "COMMAND_FAILED"
    elif advanced:
        status = "ADVANCED_WITH_STAND_DOWNS" if target_status == "READY_WITH_STAND_DOWNS" else "ADVANCED"
    else:
        status = "STOOD_DOWN"
    entry = {
        "run_id": _run_id(first_key, str(plan["fingerprint"]), len(ledger["entries"])),
        "stage": first_key,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "argv": list(step["argv"]),
        "cwd": str(cwd),
        "shell": False,
        "fixed_outcomes_explicitly_allowed": bool(allow_fixed_outcomes),
        "returncode": returncode,
        "command_error": run_error,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8", errors="replace")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8", errors="replace")).hexdigest(),
        "stdout_tail": stdout[-MAX_LOG_TAIL:],
        "stderr_tail": stderr[-MAX_LOG_TAIL:],
        "before_readiness_fingerprint": before["fingerprint"],
        "after_readiness_fingerprint": after["fingerprint"],
        "target_effective_status": target_status,
        "target_blockers": after_rows[first_key].get("blockers") or [],
        "target_stand_down_days": after_rows[first_key].get("stand_down_days") or [],
        "protected_mutations_restored": mutated,
        "upstream_regressions": regressed,
        "random_shuffle_used": False,
        "blind_forecasts_immutable": not mutated,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    ledger = _append_ledger(ledger_path, ledger, entry)
    validate_ledger(ledger, plan)
    return {
        "status": status,
        "stage": first_key,
        "target_effective_status": target_status,
        "target_blockers": entry["target_blockers"],
        "stand_down_days": entry["target_stand_down_days"],
        "protected_mutations_restored": mutated,
        "upstream_regressions": regressed,
        "readiness_fingerprint": after["fingerprint"],
        "ledger_fingerprint": ledger["fingerprint"],
        "run_id": entry["run_id"],
    }


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        work = root / "work"
        artifacts = root / "artifacts"
        work.mkdir()
        artifacts.mkdir()
        for relative in ("forecasts/grp15.json", "forecasts/grp16.json", "knowledge/ng_brain.json"):
            path = work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        plan = build_plan(artifacts, work)
        validate_plan(plan)
        configured = configure_stage(plan, "corpus_coverage", ["python", "worker.py"])
        validate_plan(configured)
        ledger = _empty_ledger(configured)
        validate_ledger(ledger, configured)
    print("[ng_historical_refinement_executor] selftest PASS")
    return 0


def _parse_protected(values: Sequence[str]) -> list[tuple[str, str]]:
    result = []
    for value in values:
        if "=" not in value:
            raise HistoricalRefinementExecutionError("--protected must be ROLE=PATH")
        role, path = value.split("=", 1)
        if not role or not path:
            raise HistoricalRefinementExecutionError("--protected must be ROLE=PATH")
        result.append((role, path))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init-plan")
    init.add_argument("--artifact-dir", required=True)
    init.add_argument("--working-directory", default=".")
    init.add_argument("--protected", action="append", default=[])
    init.add_argument("--out", required=True)

    configure = subparsers.add_parser("configure-stage")
    configure.add_argument("--plan", required=True)
    configure.add_argument("--stage", required=True)
    configure.add_argument("--argv-json", required=True)
    configure.add_argument("--cwd")
    configure.add_argument("--timeout-s", type=int)
    configure.add_argument("--disable", action="store_true")
    configure.add_argument("--out", required=True)

    run = subparsers.add_parser("run-next")
    run.add_argument("--plan", required=True)
    run.add_argument("--ledger", required=True)
    run.add_argument("--readiness-out")
    run.add_argument("--allow-fixed-outcomes", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command == "init-plan":
        protected = _parse_protected(args.protected)
        plan = build_plan(
            Path(args.artifact_dir),
            Path(args.working_directory),
            protected_paths=protected or None,
        )
        _atomic_json(Path(args.out), plan)
        print(json.dumps({"status": "PLAN_INITIALIZED", "fingerprint": plan["fingerprint"]}))
        return 0
    if args.command == "configure-stage":
        plan = _load_json(Path(args.plan))
        try:
            command_argv = json.loads(args.argv_json)
        except json.JSONDecodeError as error:
            raise HistoricalRefinementExecutionError(f"--argv-json is invalid: {error}") from error
        if not isinstance(command_argv, list):
            raise HistoricalRefinementExecutionError("--argv-json must decode to a list")
        result = configure_stage(
            plan,
            args.stage,
            command_argv,
            enabled=not args.disable,
            cwd=args.cwd,
            timeout_s=args.timeout_s,
        )
        _atomic_json(Path(args.out), result)
        print(json.dumps({"status": "STAGE_CONFIGURED", "stage": args.stage, "fingerprint": result["fingerprint"]}))
        return 0
    if args.command == "run-next":
        plan = _load_json(Path(args.plan))
        result = execute_next(
            plan,
            Path(args.ledger),
            allow_fixed_outcomes=args.allow_fixed_outcomes,
            dry_run=args.dry_run,
            readiness_out=Path(args.readiness_out) if args.readiness_out else None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in {"CHAIN_COMPLETE", "CONFIGURATION_REQUIRED", "DRY_RUN", "ADVANCED", "ADVANCED_WITH_STAND_DOWNS", "STOOD_DOWN"} else 2
    parser.error("choose a command or --selftest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
