from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
LIVE_DIR = EVOLUTION_DIR / "live_mock_replay"
COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
LIVE_DATA_DIR = REPO_ROOT / "live_data"
OUT_JSON = LIVE_DIR / "live_stack_health.json"
OUT_MD = LIVE_DIR / "live_stack_health.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _age_seconds(path: Path, now: float) -> float | None:
    try:
        return max(0.0, now - path.stat().st_mtime)
    except OSError:
        return None


def _latest_file(directory: Path, pattern: str) -> Path | None:
    try:
        files = [path for path in directory.glob(pattern) if path.is_file() and not path.name.endswith(".tmp")]
    except OSError:
        return None
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _latest_compare_state() -> Path | None:
    try:
        states = [path for path in COMPARE_ROOT.glob("*/state.json") if path.is_file()]
    except OSError:
        return None
    if not states:
        return None
    return max(states, key=lambda path: path.stat().st_mtime)


def _file_check(label: str, path: Path | None, max_age_seconds: float, *, critical: bool) -> dict[str, Any]:
    now = time.time()
    if path is None:
        return {
            "label": label,
            "path": "",
            "exists": False,
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "critical": critical,
            "status": "missing",
        }
    age = _age_seconds(path, now)
    if age is None:
        status = "missing"
    elif age <= max_age_seconds:
        status = "ok"
    else:
        status = "stale"
    return {
        "label": label,
        "path": str(path),
        "exists": status != "missing",
        "age_seconds": round(age, 3) if age is not None else None,
        "max_age_seconds": max_age_seconds,
        "critical": critical,
        "status": status,
    }


def _process_snapshot() -> dict[str, Any]:
    patterns = {
        "live_collectors": "live_collectors.py",
        "live_mock_trade_replay": "live_mock_trade_replay.py",
        "live_family_registry_compare": "live_family_registry_compare.py",
        "live_hindsight_evolve_worker": "live_hindsight_evolve_worker.py",
        "bank_allocation_shadow": "summarize_live_bank_allocation_shadow.py",
        "hourly_analysis_report": "live_hourly_analysis_report.py",
        "api_server": "uvicorn backend.api_server:app",
        "vite_frontend": "npm run dev",
    }
    script = (
        "$rows = Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'live_collectors.py|live_mock_trade_replay.py|live_family_registry_compare.py|"
        "live_hindsight_evolve_worker.py|summarize_live_bank_allocation_shadow.py|live_hourly_analysis_report.py|"
        "uvicorn backend.api_server:app|npm run dev' } | "
        "Select-Object ProcessId,Name,CommandLine; "
        "$rows | ConvertTo-Json -Depth 3"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except Exception as exc:
        return {"available": False, "error": str(exc), "checks": {}}
    rows_raw = proc.stdout.strip()
    rows: list[dict[str, Any]] = []
    if rows_raw:
        try:
            parsed = json.loads(rows_raw)
            if isinstance(parsed, dict):
                rows = [parsed]
            elif isinstance(parsed, list):
                rows = [row for row in parsed if isinstance(row, dict)]
        except json.JSONDecodeError:
            rows = []
    rows = [
        row for row in rows
        if "Get-CimInstance Win32_Process" not in str(row.get("CommandLine") or "")
        and (
            str(row.get("Name") or "").lower() in {"python.exe", "node.exe"}
            or "-NoExit" in str(row.get("CommandLine") or "")
        )
    ]
    checks = {}
    for name, pattern in patterns.items():
        matches = [row for row in rows if pattern.lower() in str(row.get("CommandLine") or "").lower()]
        checks[name] = {
            "running": bool(matches),
            "process_ids": [row.get("ProcessId") for row in matches],
        }
    return {"available": True, "checks": checks}


def _state_runtime(state: dict[str, Any]) -> dict[str, Any]:
    active = state.get("active_policy_epoch") if isinstance(state.get("active_policy_epoch"), dict) else {}
    allocation = state.get("bank_allocation") if isinstance(state.get("bank_allocation"), dict) else {}
    return {
        "status_count": int(state.get("status_count") or 0),
        "active_policy_epoch_id": str(active.get("policy_epoch_id") or ""),
        "active_policy_epoch_version": str(active.get("policy_epoch_version") or ""),
        "position_manager_version": str(active.get("position_manager_version") or ""),
        "bank_allocation_version": str(allocation.get("version") or ""),
        "bank_allocation_model": str(allocation.get("model") or ""),
        "open_answer_backed_candidates": int(allocation.get("open_answer_backed_candidates") or 0),
        "allocated_positions": int(allocation.get("allocated_positions") or 0),
    }


def _progress_check(previous: dict[str, Any], runtime: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    prev_runtime = previous.get("runtime") if isinstance(previous.get("runtime"), dict) else {}
    prev_status = int(prev_runtime.get("status_count") or -1)
    current_status = int(runtime.get("status_count") or 0)
    previous_ts = float(previous.get("created_wall_utc") or 0.0)
    elapsed = time.time() - previous_ts if previous_ts else 0.0
    live_data_ok = any(row["label"] == "live_data_latest_bin" and row["status"] == "ok" for row in files)
    status = "ok"
    reason = "status_count advanced or this is the first health sample"
    if previous_ts and elapsed >= 840.0 and live_data_ok and current_status <= prev_status:
        status = "stalled"
        reason = "live_data is fresh but live_replay_state status_count did not advance since the previous health sample"
    return {
        "status": status,
        "reason": reason,
        "previous_status_count": prev_status if prev_status >= 0 else None,
        "current_status_count": current_status,
        "elapsed_since_previous_health_seconds": round(elapsed, 3) if elapsed else None,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Live Stack Health",
        "",
        f"Created: {summary['created_at']}",
        f"Overall: `{summary['overall_status']}`",
        "",
        "## Runtime",
        "",
    ]
    runtime = summary.get("runtime") or {}
    for key in (
        "status_count",
        "active_policy_epoch_id",
        "active_policy_epoch_version",
        "position_manager_version",
        "bank_allocation_model",
        "open_answer_backed_candidates",
        "allocated_positions",
    ):
        lines.append(f"- {key}: `{runtime.get(key)}`")
    progress = summary.get("progress_check") or {}
    lines.extend(["", "## Progress", "", f"- Status: `{progress.get('status')}`", f"- Reason: {progress.get('reason')}", ""])
    lines.extend(["## Freshness", "", "| Item | Status | Age seconds | Max age | Critical |", "|---|---|---:|---:|---|"])
    for row in summary.get("freshness_checks") or []:
        lines.append(
            f"| `{row['label']}` | `{row['status']}` | {row.get('age_seconds')} | "
            f"{row.get('max_age_seconds')} | {row.get('critical')} |"
        )
    lines.extend(["", "## Processes", "", "| Process | Running | PIDs |", "|---|---|---|"])
    process_checks = ((summary.get("process_snapshot") or {}).get("checks") or {})
    for name, row in process_checks.items():
        lines.append(f"| `{name}` | `{row.get('running')}` | `{row.get('process_ids')}` |")
    lines.append("")
    return "\n".join(lines)


def summarize() -> dict[str, Any]:
    now = time.time()
    state_path = LIVE_DIR / "live_replay_state.json"
    state = _read_json(state_path)
    files = [
        _file_check("live_data_latest_bin", _latest_file(LIVE_DATA_DIR, "*_bins.json"), 120.0, critical=True),
        _file_check("live_replay_state", state_path, 180.0, critical=True),
        _file_check("live_hindsight_worker_status", EVOLUTION_DIR / "_live_hindsight_evolve_worker_status.json", 720.0, critical=True),
        _file_check("live_hindsight_audit", LIVE_DIR / "live_hindsight_missed_winner_audit.json", 720.0, critical=True),
        _file_check("bank_allocation_shadow", LIVE_DIR / "live_bank_allocation_shadow.json", 300.0, critical=False),
        _file_check("oracle_policy_epoch_summary", LIVE_DIR / "live_oracle_policy_epoch_summary.json", 3900.0, critical=False),
        _file_check("hourly_analysis_report", LIVE_DIR / "live_hourly_analysis.json", 3900.0, critical=False),
        _file_check("live_mock_replay_report", LIVE_DIR / "live_mock_replay_report.md", 3900.0, critical=False),
        _file_check("live_family_registry_compare_state", _latest_compare_state(), 300.0, critical=True),
    ]
    runtime = _state_runtime(state)
    previous = _read_json(OUT_JSON)
    progress = _progress_check(previous, runtime, files)
    process_snapshot = _process_snapshot()
    hard_bad = any(row["critical"] and row["status"] != "ok" for row in files) or progress["status"] != "ok"
    soft_bad = any((not row["critical"]) and row["status"] != "ok" for row in files)
    process_checks = process_snapshot.get("checks") if isinstance(process_snapshot.get("checks"), dict) else {}
    missing_core = [
        name for name in ("live_mock_trade_replay", "live_family_registry_compare", "live_hindsight_evolve_worker")
        if isinstance(process_checks.get(name), dict) and not process_checks[name].get("running")
    ]
    if missing_core:
        hard_bad = True
    overall = "bad" if hard_bad else "warn" if soft_bad else "ok"
    summary = {
        "schema": "live_stack_health_v1",
        "created_at": _now_iso(),
        "created_wall_utc": now,
        "overall_status": overall,
        "runtime": runtime,
        "freshness_checks": files,
        "progress_check": progress,
        "process_snapshot": process_snapshot,
        "missing_core_processes": missing_core,
        "outputs": {
            "json": str(OUT_JSON),
            "markdown": str(OUT_MD),
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUT_MD.write_text(_render_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a live mock stack health report.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    summary = summarize()
    if not args.quiet:
        print(json.dumps({
            "schema": summary["schema"],
            "created_at": summary["created_at"],
            "overall_status": summary["overall_status"],
            "runtime": summary["runtime"],
            "missing_core_processes": summary["missing_core_processes"],
            "outputs": summary["outputs"],
        }, indent=2))


if __name__ == "__main__":
    main()
