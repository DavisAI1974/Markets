"""
cells_decay_monitor.py — append-mostly registry retirement audit.

Reads cells_registry.json plus realized forward-paper trades and flags cells
whose post-publication realized win rate has decayed materially versus the
discovered win rate stored in provenance.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict


DEFAULT_MIN_TRADES = 8
DEFAULT_ROLLING_TRADES = 20
DEFAULT_RETIRE_THRESHOLD = 0.50
DEFAULT_WATCH_THRESHOLD = 0.80
DEFAULT_CONTROLS_OUTPUT_PATH = "cells_runtime_controls.json"


def _load_json(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _load_trades(path: str) -> list[dict]:
    if not path or not os.path.exists(path):
        return []
    rows: list[dict] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _discovered_baseline(cell: dict) -> float | None:
    prov = cell.get("provenance") or {}
    for key in ("score_point", "score_ci_low"):
        val = prov.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _closed_trade_bps(trade: dict) -> float | None:
    if "outcome_realized_bps" in trade and isinstance(trade.get("outcome_realized_bps"), (int, float)):
        return float(trade.get("outcome_realized_bps"))
    pnl = trade.get("realized_pnl_usd")
    notional = trade.get("notional") or trade.get("notional_usd")
    if isinstance(pnl, (int, float)) and isinstance(notional, (int, float)) and float(notional) > 0:
        return float(pnl) / float(notional) * 10000.0
    return None


def compute_decay_report(
    registry: dict,
    trades: list[dict],
    *,
    min_trades: int = DEFAULT_MIN_TRADES,
    rolling_trades: int = DEFAULT_ROLLING_TRADES,
    retire_threshold: float = DEFAULT_RETIRE_THRESHOLD,
    watch_threshold: float = DEFAULT_WATCH_THRESHOLD,
) -> dict:
    cells = registry.get("cells", [])

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        if trade.get("status") != "closed":
            continue
        cell_id = trade.get("cell_id")
        if isinstance(cell_id, str) and cell_id:
            by_cell[cell_id].append(trade)
    for cell_id in by_cell:
        by_cell[cell_id].sort(key=lambda row: float(
            row.get("exit_ts_utc")
            or row.get("outcome_resolved_utc")
            or row.get("timestamp_utc")
            or 0.0
        ))

    findings: list[dict] = []
    status_counts = defaultdict(int)
    for cell in cells:
        cell_id = cell.get("cell_id")
        if not isinstance(cell_id, str):
            continue
        baseline = _discovered_baseline(cell)
        trades_for_cell = by_cell.get(cell_id, [])
        recent = trades_for_cell[-rolling_trades:]
        n_recent = len(recent)
        if baseline is None:
            status = "no_baseline"
        elif n_recent < min_trades:
            status = "insufficient"
        else:
            wins = sum(
                1 for trade in recent
                if ((_closed_trade_bps(trade) or 0.0) > 0.0)
            )
            realized_win_rate = wins / n_recent if n_recent else 0.0
            retention = realized_win_rate / max(baseline, 1e-9)
            if retention < retire_threshold:
                status = "retire_candidate"
            elif retention < watch_threshold:
                status = "watch"
            else:
                status = "retain"
        status_counts[status] += 1

        bps_vals = [val for val in (_closed_trade_bps(t) for t in recent) if val is not None]
        wins = sum(1 for val in bps_vals if val > 0.0)
        realized_win_rate = (wins / len(bps_vals)) if bps_vals else None
        retention = (
            realized_win_rate / baseline
            if baseline is not None and realized_win_rate is not None and baseline > 0
            else None
        )
        findings.append({
            "cell_id": cell_id,
            "asset": cell.get("asset"),
            "venue": cell.get("venue"),
            "status": status,
            "discovered_win_rate": baseline,
            "n_closed_total": len(trades_for_cell),
            "n_closed_recent": len(recent),
            "realized_win_rate_recent": realized_win_rate,
            "win_rate_retention": retention,
            "mean_realized_bps_recent": (
                sum(bps_vals) / len(bps_vals) if bps_vals else None
            ),
            "recent_last_closed_utc": (
                float(recent[-1].get("exit_ts_utc")
                      or recent[-1].get("outcome_resolved_utc")
                      or recent[-1].get("timestamp_utc")
                      or 0.0)
                if recent else None
            ),
        })

    findings.sort(
        key=lambda row: (
            {"retire_candidate": 0, "watch": 1, "retain": 2, "insufficient": 3, "no_baseline": 4}.get(
                row["status"], 9),
            (row.get("win_rate_retention") if row.get("win_rate_retention") is not None else 999.0),
        )
    )

    return {
        "schema_version": 1,
        "generated_utc": int(time.time()),
        "summary": dict(status_counts),
        "n_cells": len(cells),
        "n_cells_with_closed_trades": sum(1 for row in findings if row["n_closed_total"] > 0),
        "findings": findings,
    }


def build_runtime_controls(
    report: dict,
    *,
    registry_path: str,
    practice_trades_path: str,
) -> dict:
    controls: dict[str, dict] = {}
    for finding in report.get("findings", []):
        cell_id = finding.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            continue
        status = str(finding.get("status") or "")
        if status == "retire_candidate":
            action = "suppress"
        elif status == "watch":
            action = "watch"
        else:
            action = "active"
        controls[cell_id] = {
            "status": status,
            "action": action,
            "reason": (
                f"{status}: realized win-rate retention="
                f"{(finding.get('win_rate_retention') if finding.get('win_rate_retention') is not None else float('nan')):.3f}"
                if finding.get("win_rate_retention") is not None
                else status
            ),
            "n_closed_recent": int(finding.get("n_closed_recent") or 0),
            "realized_win_rate_recent": finding.get("realized_win_rate_recent"),
            "win_rate_retention": finding.get("win_rate_retention"),
            "updated_utc": report.get("generated_utc"),
        }
    return {
        "schema_version": 1,
        "generated_utc": report.get("generated_utc"),
        "registry_path": registry_path,
        "practice_trades_path": practice_trades_path,
        "summary": report.get("summary", {}),
        "controls": controls,
    }


def refresh_runtime_controls(
    *,
    registry_path: str = "cells_registry.json",
    practice_trades_path: str = "backend_practice_trades.jsonl",
    output_path: str = DEFAULT_CONTROLS_OUTPUT_PATH,
    min_trades: int = DEFAULT_MIN_TRADES,
    rolling_trades: int = DEFAULT_ROLLING_TRADES,
    retire_threshold: float = DEFAULT_RETIRE_THRESHOLD,
    watch_threshold: float = DEFAULT_WATCH_THRESHOLD,
) -> tuple[dict, dict]:
    registry = _load_json(registry_path)
    trades = _load_trades(practice_trades_path)
    report = compute_decay_report(
        registry,
        trades,
        min_trades=min_trades,
        rolling_trades=rolling_trades,
        retire_threshold=retire_threshold,
        watch_threshold=watch_threshold,
    )
    report["registry_path"] = registry_path
    report["practice_trades_path"] = practice_trades_path
    controls = build_runtime_controls(
        report,
        registry_path=registry_path,
        practice_trades_path=practice_trades_path,
    )
    if output_path:
        with open(output_path, "w") as fh:
            json.dump(controls, fh, indent=2)
    return report, controls


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--registry-path", default="cells_registry.json")
    p.add_argument("--practice-trades-path", default="backend_practice_trades.jsonl")
    p.add_argument("--min-trades", type=int, default=DEFAULT_MIN_TRADES)
    p.add_argument("--rolling-trades", type=int, default=DEFAULT_ROLLING_TRADES)
    p.add_argument("--retire-threshold", type=float, default=DEFAULT_RETIRE_THRESHOLD,
                   help="Retire when realized win-rate < threshold * discovered win-rate")
    p.add_argument("--watch-threshold", type=float, default=DEFAULT_WATCH_THRESHOLD)
    p.add_argument("--output-path", default="cells_decay_monitor.json")
    p.add_argument("--controls-output-path", default=DEFAULT_CONTROLS_OUTPUT_PATH)
    args = p.parse_args()

    report, controls = refresh_runtime_controls(
        registry_path=args.registry_path,
        practice_trades_path=args.practice_trades_path,
        output_path=args.controls_output_path,
        min_trades=args.min_trades,
        rolling_trades=args.rolling_trades,
        retire_threshold=args.retire_threshold,
        watch_threshold=args.watch_threshold,
    )
    with open(args.output_path, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"[decay-monitor] wrote {args.output_path}")
    print(f"[decay-monitor] wrote {args.controls_output_path}")
    for key in ("retire_candidate", "watch", "retain", "insufficient", "no_baseline"):
        print(f"  {key}: {(report.get('summary') or {}).get(key, 0)}")


if __name__ == "__main__":
    main()
