from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
LIVE_DIR = EVOLUTION_DIR / "live_mock_replay"
COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
LIVE_DATA_DIR = REPO_ROOT / "live_data"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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


def _age(path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def _process_snapshot() -> dict[str, list[int]]:
    patterns = [
        "live_collectors.py",
        "live_mock_trade_replay.py",
        "live_family_registry_compare.py",
        "live_hindsight_evolve_worker.py",
        "summarize_live_bank_allocation_shadow.py",
        "build_live_sidecar_exit_restatement.py",
        "live_stack_health.py",
        "live_hourly_analysis_report.py",
    ]
    script = (
        "$rows = Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'live_collectors.py|live_mock_trade_replay.py|live_family_registry_compare.py|"
        "live_hindsight_evolve_worker.py|summarize_live_bank_allocation_shadow.py|live_stack_health.py|"
        "live_hourly_analysis_report.py|build_live_sidecar_exit_restatement.py' } | "
        "Select-Object ProcessId,Name,CommandLine; "
        "$rows | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    rows: list[dict[str, Any]] = []
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
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
    out: dict[str, list[int]] = {}
    for pattern in patterns:
        matches = [
            int(row.get("ProcessId"))
            for row in rows
            if pattern.lower() in str(row.get("CommandLine") or "").lower()
        ]
        out[pattern] = matches
    return out


def _allowed_horizons(raw: Any) -> set[int]:
    if raw is None:
        raw = [10, 30, 60]
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = [raw]
    out: set[int] = set()
    for value in values:
        try:
            minutes = int(float(value or 0))
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            out.add(minutes)
    return out


def main() -> None:
    errors: list[str] = []
    warnings: list[str] = []

    from oracle_runtime_preflight import run_startup_preflight

    run_startup_preflight("final_live_mock_preflight")

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def warn(condition: bool, message: str) -> None:
        if not condition:
            warnings.append(message)

    latest_live_data = _latest_file(LIVE_DATA_DIR, "*_bins.json")
    require(_age(latest_live_data) is not None and _age(latest_live_data) <= 120.0, "live_data bins are missing or stale")

    state_path = LIVE_DIR / "live_replay_state.json"
    state = _read_json(state_path)
    require(_age(state_path) is not None and _age(state_path) <= 240.0, "live_replay_state.json is missing or stale")
    active = state.get("active_policy_epoch") if isinstance(state.get("active_policy_epoch"), dict) else {}
    active_epoch_id = str(active.get("policy_epoch_id") or "")
    require(
        str(active.get("policy_epoch_version") or "") == "oracle_runtime_answer_backed_v6_quality_gated",
        "active policy epoch is not v6 quality-gated",
    )
    require(str(active.get("position_manager_version") or "") == "best_answer_backed_position_v1", "best-position manager version is missing")
    counterfactual_exit_test_ok = False
    stale_closed: list[str] = []
    rotation_closed: list[str] = []
    disallowed_horizons: list[str] = []
    for account_id, account in (state.get("accounts") or {}).items():
        scenario = account.get("scenario") if isinstance(account, dict) else {}
        trades = account.get("trades") if isinstance(account, dict) else []
        for trade in trades or []:
            if not isinstance(trade, dict):
                continue
            if (
                active_epoch_id
                and trade.get("status") == "closed"
                and str(trade.get("policy_epoch_id") or "") != active_epoch_id
            ):
                stale_closed.append(str(trade.get("cell_id") or f"{account_id}:{trade.get('asset')}:{trade.get('venue')}"))
        if (
            isinstance(scenario, dict)
            and bool(scenario.get("counterfactual_exit_selector_enabled"))
            and bool(scenario.get("counterfactual_exit_selector_blocks_rotation"))
        ):
            require(
                bool(scenario.get("oracle_winner_exact_entry_required"))
                and bool(scenario.get("oracle_winner_proven_entries_only")),
                f"{account_id} does not require exact proven oracle winner entries",
            )
            require(
                float(scenario.get("oracle_winner_min_bank_entry_net_bps_per_min") or 0.0) >= 0.30,
                f"{account_id} bank entry bps/min floor is below 0.30",
            )
            require(
                bool(scenario.get("oracle_bank_no_side_context_shadow_only")),
                f"{account_id} can still bank-count no-side oracle rescue rows",
            )
            require(
                bool(scenario.get("oracle_bank_require_live_trade_shape")),
                f"{account_id} does not require live trade shape for bank allocation",
            )
            require(
                bool(scenario.get("oracle_bank_progress_exit_enabled")),
                f"{account_id} bank progress exit guard is disabled",
            )
            require(
                bool(scenario.get("oracle_bank_peak_exit_enabled")),
                f"{account_id} bank peak/giveback exit guard is disabled",
            )
            require(
                float(scenario.get("oracle_bank_peak_exit_min_net_bps") or 0.0) == 20.0,
                f"{account_id} oracle_bank_peak_exit_min_net_bps drifted from policy (20.0)",
            )
            require(
                float(scenario.get("oracle_bank_peak_exit_giveback_bps") or 0.0) == 12.0,
                f"{account_id} oracle_bank_peak_exit_giveback_bps drifted from policy (12.0)",
            )
            require(
                float(scenario.get("oracle_bank_peak_exit_giveback_fraction") or 0.0) == 0.25,
                f"{account_id} oracle_bank_peak_exit_giveback_fraction drifted from policy (0.25)",
            )
            require(
                float(scenario.get("oracle_bank_fee_cover_cut_minutes") or 0.0) == 15.0,
                f"{account_id} oracle_bank_fee_cover_cut_minutes drifted from policy (15.0)",
            )
            require(
                not bool(scenario.get("oracle_bank_require_20bps_by_30m")),
                f"{account_id} oracle_bank_require_20bps_by_30m is activated — dead-code arm should remain off",
            )
            require(
                not bool(scenario.get("best_position_rotation_enabled")),
                f"{account_id} counterfactual exit test still has best-position rotation enabled",
            )
            require(
                bool(scenario.get("counterfactual_exit_selector_policy_epoch_only")),
                f"{account_id} counterfactual selector is not restricted to the active policy epoch",
            )
            require(
                float(scenario.get("counterfactual_exit_selector_min_net_usd_at_target_notional") or 0.0) >= 0.0,
                f"{account_id} counterfactual selector can promote negative absolute PnL candidates",
            )
            require(
                float(scenario.get("counterfactual_exit_selector_min_win_rate") or 0.0) >= 0.45,
                f"{account_id} counterfactual selector win-rate floor is too loose",
            )
            allowed = _allowed_horizons(scenario.get("counterfactual_exit_selector_allowed_horizons_minutes"))
            open_trades = [
                trade for trade in (trades or [])
                if isinstance(trade, dict) and trade.get("status") == "open"
            ]
            selected_open = [
                trade for trade in open_trades
                if isinstance(trade.get("runtime_counterfactual_exit_selection"), dict)
                and trade.get("runtime_counterfactual_exit_selection")
            ]
            quality_gated = (
                bool(scenario.get("counterfactual_exit_selector_policy_epoch_only"))
                and float(scenario.get("counterfactual_exit_selector_min_net_usd_at_target_notional") or 0.0) >= 0.0
                and float(scenario.get("counterfactual_exit_selector_min_win_rate") or 0.0) >= 0.45
            )
            if not open_trades or selected_open or quality_gated:
                counterfactual_exit_test_ok = True
            if open_trades and not selected_open:
                warn(
                    False,
                    f"{account_id} has open trades but no qualifying profitable counterfactual selections; base/oracle exits remain active",
                )
            silent_fallback_trades = [
                trade for trade in open_trades
                if str(trade.get("runtime_counterfactual_exit_selection_status") or "") == "oracle_winner_match_without_runtime_exit"
            ]
            require(
                not silent_fallback_trades,
                f"{account_id} has {len(silent_fallback_trades)} open trade(s) with oracle_winner_match_without_runtime_exit — silent fallback to historic parity, no horizon protection",
            )
            for trade in trades or []:
                if not isinstance(trade, dict):
                    continue
                selection = trade.get("runtime_counterfactual_exit_selection")
                if not isinstance(selection, dict) or not selection:
                    continue
                close_reason = str(trade.get("close_reason") or trade.get("runner_exit_reason") or "")
                if trade.get("status") == "closed" and active_epoch_id and str(trade.get("policy_epoch_id") or "") == active_epoch_id:
                    if "rotation" in close_reason:
                        rotation_closed.append(str(trade.get("cell_id") or f"{account_id}:{trade.get('asset')}:{trade.get('venue')}"))
                    oracle_source = str(selection.get("source_scope") or "") == "oracle_winner_source_of_truth"
                    if (
                        close_reason.startswith("runtime_counterfactual_fixed_hold")
                        and float(trade.get("realized_pnl_usd") or 0.0) < 0.0
                        and not oracle_source
                    ):
                        disallowed_horizons.append(
                            f"{account_id}:{trade.get('asset')}:{trade.get('venue')}:{close_reason}:negative_realized"
                        )
                if str(selection.get("selected_counterfactual_class") or "").startswith("fixed_hold"):
                    horizon = int(float(selection.get("fixed_hold_minutes") or 0))
                    oracle_source = str(selection.get("source_scope") or "") == "oracle_winner_source_of_truth"
                    if horizon and horizon not in allowed and not oracle_source:
                        disallowed_horizons.append(
                            f"{account_id}:{trade.get('asset')}:{trade.get('venue')}:{selection.get('selected_counterfactual_id')}"
                        )
                    cf_net = selection.get("counterfactual_net_usd_at_target_notional")
                    if cf_net is not None and float(cf_net or 0.0) <= 0.0:
                        disallowed_horizons.append(
                            f"{account_id}:{trade.get('asset')}:{trade.get('venue')}:{selection.get('selected_counterfactual_id')}:negative_net"
                        )
    require(
        counterfactual_exit_test_ok,
        "no stamped counterfactual exit test account is active",
    )
    require(not stale_closed, f"active accounts still include prior-epoch closed trades: {stale_closed[:5]}")
    require(not rotation_closed, f"counterfactual-selected trades were closed by rotation in active epoch: {rotation_closed[:5]}")
    require(not disallowed_horizons, f"runtime selector chose horizons outside the validation allow-list: {disallowed_horizons[:5]}")

    allocation = state.get("bank_allocation") if isinstance(state.get("bank_allocation"), dict) else {}
    require(str(allocation.get("version") or "") == "per_venue_full_bank_slots_v1", "runtime bank allocation version is missing")
    require(str(allocation.get("model") or "") == "one_full_venue_bank_trade_when_free", "runtime bank allocation model is missing")
    accounts = allocation.get("accounts") if isinstance(allocation.get("accounts"), dict) else {}
    for account_id, row in accounts.items():
        if not isinstance(row, dict):
            continue
        if int(row.get("open_answer_backed_candidates") or 0) > 0:
            require(
                int(row.get("allocated_slots") or 0) <= 3,
                f"{account_id} has more than one allocated slot per venue",
            )

    freshness = {
        "bank_allocation_shadow": (LIVE_DIR / "live_bank_allocation_shadow.json", 300.0, False),
        "live_stack_health": (LIVE_DIR / "live_stack_health.json", 960.0, False),
        "live_hourly_analysis": (LIVE_DIR / "live_hourly_analysis.json", 3900.0, False),
        "hindsight_worker_status": (EVOLUTION_DIR / "_live_hindsight_evolve_worker_status.json", 720.0, True),
        "hindsight_audit": (LIVE_DIR / "live_hindsight_missed_winner_audit.json", 720.0, True),
        "sidecar_exit_restatement": (LIVE_DIR / "live_sidecar_exit_restatement.json", 420.0, False),
        "oracle_policy_epoch_summary": (LIVE_DIR / "live_oracle_policy_epoch_summary.json", 3900.0, False),
        "live_mock_replay_report": (LIVE_DIR / "live_mock_replay_report.md", 3900.0, False),
    }
    for name, (path, max_age, hard) in freshness.items():
        ok = _age(path) is not None and _age(path) <= max_age
        if hard:
            require(ok, f"{name} is missing or stale")
        else:
            warn(ok, f"{name} is missing or stale")

    processes = _process_snapshot()
    required_processes = {
        "live_collectors.py",
        "live_mock_trade_replay.py",
        "live_hindsight_evolve_worker.py",
    }
    for pattern in required_processes:
        require(bool(processes[pattern]), f"process not running: {pattern}")

    result = {
        "schema": "final_live_mock_preflight_v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "active_policy_epoch": active,
        "bank_allocation": {
            "version": allocation.get("version"),
            "model": allocation.get("model"),
            "open_answer_backed_candidates": allocation.get("open_answer_backed_candidates"),
            "allocated_positions": allocation.get("allocated_positions"),
        },
        "processes": processes,
    }
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
