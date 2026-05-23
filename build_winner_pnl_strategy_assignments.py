from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HORIZONS = (10, 30, 60)


def _float(row: dict[str, str], key: str, default: float | None = None) -> float | None:
    raw = row.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _candidate(
    *,
    strategy_id: str,
    strategy_class: str,
    label: str,
    net_pnl_usd: float,
    actual_net_pnl_usd: float,
    risk_usd: float,
    horizon_minutes: int | None = None,
    executable: bool,
    priority: int,
) -> dict[str, Any]:
    return {
        "pnl_strategy_id": strategy_id,
        "pnl_strategy_class": strategy_class,
        "label": label,
        "horizon_minutes": horizon_minutes,
        "executable_without_hindsight": executable,
        "net_pnl_usd": round(float(net_pnl_usd), 6),
        "incremental_vs_actual_usd": round(float(net_pnl_usd - actual_net_pnl_usd), 6),
        "pnl_R": round(float(net_pnl_usd / risk_usd), 6) if risk_usd > 0 else None,
        "_priority": priority,
    }


def _row_candidates(row: dict[str, str]) -> list[dict[str, Any]]:
    actual_net = _float(row, "net_pnl_usd", 0.0) or 0.0
    risk_usd = _float(row, "risk_usd", 0.0) or 0.0
    actual_profile = row.get("exit_strategy_id") or "unknown_exit_profile"
    close_reason = row.get("close_reason") or "actual_close"

    candidates = [
        _candidate(
            strategy_id=f"actual_exit::{actual_profile}",
            strategy_class="actual_exit",
            label=f"Actual replay exit ({close_reason})",
            net_pnl_usd=actual_net,
            actual_net_pnl_usd=actual_net,
            risk_usd=risk_usd,
            executable=True,
            priority=0,
        )
    ]

    for horizon in HORIZONS:
        best_net = _float(row, f"cf_{horizon}m_best_net_usd")
        best_inc = _float(row, f"cf_{horizon}m_best_incremental_usd")
        if best_net is None and best_inc is not None:
            best_net = actual_net + best_inc
        if best_net is not None:
            candidates.append(
                _candidate(
                    strategy_id=f"oracle_best_within_{horizon}m_after_actual_exit",
                    strategy_class="oracle_best_after_exit",
                    label=f"Best observed exit inside {horizon}m after actual exit",
                    net_pnl_usd=best_net,
                    actual_net_pnl_usd=actual_net,
                    risk_usd=risk_usd,
                    horizon_minutes=horizon,
                    executable=False,
                    priority=20 + horizon,
                )
            )

        end_net = _float(row, f"cf_{horizon}m_end_net_usd")
        end_inc = _float(row, f"cf_{horizon}m_end_incremental_usd")
        if end_net is None and end_inc is not None:
            end_net = actual_net + end_inc
        if end_net is not None:
            candidates.append(
                _candidate(
                    strategy_id=f"fixed_hold_{horizon}m_after_actual_exit",
                    strategy_class="fixed_hold_after_exit",
                    label=f"Hold to {horizon}m after actual exit",
                    net_pnl_usd=end_net,
                    actual_net_pnl_usd=actual_net,
                    risk_usd=risk_usd,
                    horizon_minutes=horizon,
                    executable=True,
                    priority=10 + horizon,
                )
            )

    return candidates


def _best(candidates: list[dict[str, Any]], *, executable_only: bool = False) -> dict[str, Any]:
    pool = [
        c for c in candidates
        if not executable_only or bool(c.get("executable_without_hindsight"))
    ]
    if not pool:
        pool = candidates
    return sorted(pool, key=lambda c: (-float(c["net_pnl_usd"]), int(c["_priority"])))[0]


def _bucket_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            (row.get("strategy_id") or "").upper(),
            (row.get("asset") or "").upper(),
            row.get("venue") or "",
            row.get("bucket_session") or "",
        ]
    )


def _load_promoted_buckets(path: Path | None) -> set[str]:
    if not path:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    promoted = set()
    for bucket in payload.get("buckets") or []:
        if str(bucket.get("status") or "") == "promoted":
            promoted.add(str(bucket.get("bucket_key") or ""))
    return promoted


def _summarize(assignments: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "trades": 0,
        "actual_net_pnl_usd": 0.0,
        "best_any_net_pnl_usd": 0.0,
        "best_executable_net_pnl_usd": 0.0,
        "best_any_incremental_usd": 0.0,
        "best_executable_incremental_usd": 0.0,
    })
    for row in assignments:
        name = str(row.get(key) or "")
        item = grouped[name]
        item["trades"] += 1
        item["actual_net_pnl_usd"] += float(row["actual_net_pnl_usd"])
        item["best_any_net_pnl_usd"] += float(row["best_any_net_pnl_usd"])
        item["best_executable_net_pnl_usd"] += float(row["best_executable_net_pnl_usd"])
        item["best_any_incremental_usd"] += float(row["best_any_incremental_vs_actual_usd"])
        item["best_executable_incremental_usd"] += float(row["best_executable_incremental_vs_actual_usd"])
    out = []
    for name, item in grouped.items():
        item[key] = name
        for amount_key in [
            "actual_net_pnl_usd",
            "best_any_net_pnl_usd",
            "best_executable_net_pnl_usd",
            "best_any_incremental_usd",
            "best_executable_incremental_usd",
        ]:
            item[amount_key] = round(float(item[amount_key]), 6)
        out.append(item)
    return sorted(out, key=lambda row: (-float(row["best_executable_incremental_usd"]), -int(row["trades"]), str(row[key])))


def build(input_path: Path, output_prefix: Path, exit_resolution_path: Path | None = None) -> dict[str, Any]:
    promoted_buckets = _load_promoted_buckets(exit_resolution_path)
    rows = list(csv.DictReader(input_path.open("r", encoding="utf-8-sig", newline="")))
    assignments: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=1):
        candidates = _row_candidates(row)
        best_any = _best(candidates)
        best_executable = _best(candidates, executable_only=True)
        actual_net = _float(row, "net_pnl_usd", 0.0) or 0.0
        risk_usd = _float(row, "risk_usd", 0.0) or 0.0
        bucket_key = _bucket_key(row)
        assignment = {
            "winner_index": idx,
            "source_file": row.get("source_file") or "",
            "trade_index": row.get("trade_index") or "",
            "entry_strategy_id": row.get("strategy_id") or "",
            "asset": row.get("asset") or "",
            "venue": row.get("venue") or "",
            "side": row.get("side") or "",
            "bucket_session": row.get("bucket_session") or "",
            "bucket_key": bucket_key,
            "bucket_status": "promoted" if bucket_key in promoted_buckets else "unclassified",
            "entry_ts_utc": row.get("entry_ts_utc") or "",
            "exit_ts_utc": row.get("exit_ts_utc") or "",
            "actual_exit_strategy_id": row.get("exit_strategy_id") or "",
            "suggested_exit_strategy_id": row.get("suggested_exit_strategy_id") or "",
            "close_reason": row.get("close_reason") or "",
            "actual_net_pnl_usd": round(actual_net, 6),
            "actual_profit_R": round(actual_net / risk_usd, 6) if risk_usd > 0 else None,
            "best_any_pnl_strategy_id": best_any["pnl_strategy_id"],
            "best_any_pnl_strategy_class": best_any["pnl_strategy_class"],
            "best_any_executable_without_hindsight": best_any["executable_without_hindsight"],
            "best_any_net_pnl_usd": best_any["net_pnl_usd"],
            "best_any_pnl_R": best_any["pnl_R"],
            "best_any_incremental_vs_actual_usd": best_any["incremental_vs_actual_usd"],
            "best_executable_pnl_strategy_id": best_executable["pnl_strategy_id"],
            "best_executable_pnl_strategy_class": best_executable["pnl_strategy_class"],
            "best_executable_net_pnl_usd": best_executable["net_pnl_usd"],
            "best_executable_pnl_R": best_executable["pnl_R"],
            "best_executable_incremental_vs_actual_usd": best_executable["incremental_vs_actual_usd"],
            "candidate_count": len(candidates),
            "pnl_strategy_candidates": [
                {k: v for k, v in candidate.items() if k != "_priority"}
                for candidate in candidates
            ],
        }
        assignments.append(assignment)

    best_any_counts = Counter(row["best_any_pnl_strategy_id"] for row in assignments)
    best_exec_counts = Counter(row["best_executable_pnl_strategy_id"] for row in assignments)
    actual_total = sum(float(row["actual_net_pnl_usd"]) for row in assignments)
    best_any_total = sum(float(row["best_any_net_pnl_usd"]) for row in assignments)
    best_exec_total = sum(float(row["best_executable_net_pnl_usd"]) for row in assignments)

    summary = {
        "schema": "winner_trade_pnl_strategy_assignments_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_winner_csv": str(input_path),
        "source_exit_resolution": str(exit_resolution_path) if exit_resolution_path else "",
        "policy": {
            "best_any_includes_oracle_hindsight": True,
            "best_executable_excludes_oracle_best_within_window": True,
            "actual_exit_is_included_as_candidate": True,
            "counterfactual_windows_after_actual_exit_minutes": list(HORIZONS),
        },
        "counts": {
            "winner_rows": len(assignments),
            "promoted_bucket_rows": sum(1 for row in assignments if row["bucket_status"] == "promoted"),
            "candidate_pnl_strategies_per_trade": max((row["candidate_count"] for row in assignments), default=0),
            "total_candidate_rows": sum(row["candidate_count"] for row in assignments),
        },
        "totals": {
            "actual_net_pnl_usd": round(actual_total, 6),
            "best_any_net_pnl_usd": round(best_any_total, 6),
            "best_any_incremental_vs_actual_usd": round(best_any_total - actual_total, 6),
            "best_executable_net_pnl_usd": round(best_exec_total, 6),
            "best_executable_incremental_vs_actual_usd": round(best_exec_total - actual_total, 6),
        },
        "best_any_strategy_counts": dict(best_any_counts.most_common()),
        "best_executable_strategy_counts": dict(best_exec_counts.most_common()),
        "by_entry_strategy": _summarize(assignments, "entry_strategy_id"),
        "by_asset": _summarize(assignments, "asset"),
        "by_venue": _summarize(assignments, "venue"),
        "by_bucket_session": _summarize(assignments, "bucket_session"),
        "assignments": assignments,
    }

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    csv_path = output_prefix.with_suffix(".csv")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    csv_fields = [
        "winner_index",
        "trade_index",
        "entry_strategy_id",
        "asset",
        "venue",
        "side",
        "bucket_session",
        "bucket_key",
        "bucket_status",
        "actual_exit_strategy_id",
        "suggested_exit_strategy_id",
        "close_reason",
        "actual_net_pnl_usd",
        "actual_profit_R",
        "best_executable_pnl_strategy_id",
        "best_executable_pnl_strategy_class",
        "best_executable_net_pnl_usd",
        "best_executable_pnl_R",
        "best_executable_incremental_vs_actual_usd",
        "best_any_pnl_strategy_id",
        "best_any_pnl_strategy_class",
        "best_any_executable_without_hindsight",
        "best_any_net_pnl_usd",
        "best_any_pnl_R",
        "best_any_incremental_vs_actual_usd",
        "candidate_count",
        "source_file",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in assignments:
            writer.writerow({field: row.get(field) for field in csv_fields})

    lines = [
        "# Winner Trade PnL Strategy Assignments",
        "",
        f"Created: {summary['created_at']}",
        "",
        f"- Winner rows: {summary['counts']['winner_rows']}",
        f"- Promoted bucket rows: {summary['counts']['promoted_bucket_rows']}",
        f"- Candidate PnL strategies per trade: {summary['counts']['candidate_pnl_strategies_per_trade']}",
        f"- Total candidate rows: {summary['counts']['total_candidate_rows']}",
        f"- Actual net PnL: ${summary['totals']['actual_net_pnl_usd']:,.2f}",
        f"- Best executable net PnL: ${summary['totals']['best_executable_net_pnl_usd']:,.2f}",
        f"- Best executable incremental: ${summary['totals']['best_executable_incremental_vs_actual_usd']:,.2f}",
        f"- Best any/oracle net PnL: ${summary['totals']['best_any_net_pnl_usd']:,.2f}",
        f"- Best any/oracle incremental: ${summary['totals']['best_any_incremental_vs_actual_usd']:,.2f}",
        "",
        "## Best Executable Strategy Counts",
        "",
        "| PnL strategy | Trades |",
        "|---|---:|",
    ]
    for strategy_id, count in best_exec_counts.most_common():
        lines.append(f"| `{strategy_id}` | {count} |")

    lines.extend([
        "",
        "## Best Any Strategy Counts",
        "",
        "| PnL strategy | Trades |",
        "|---|---:|",
    ])
    for strategy_id, count in best_any_counts.most_common():
        lines.append(f"| `{strategy_id}` | {count} |")

    lines.extend([
        "",
        "## By Entry Strategy",
        "",
        "| Entry strategy | Trades | Actual PnL | Best executable PnL | Executable improvement | Best any/oracle PnL | Oracle improvement |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in summary["by_entry_strategy"]:
        lines.append(
            "| "
            f"`{row['entry_strategy_id']}` | {row['trades']} | "
            f"${row['actual_net_pnl_usd']:,.2f} | "
            f"${row['best_executable_net_pnl_usd']:,.2f} | "
            f"${row['best_executable_incremental_usd']:,.2f} | "
            f"${row['best_any_net_pnl_usd']:,.2f} | "
            f"${row['best_any_incremental_usd']:,.2f} |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        "- `best_executable_*` chooses among actual exit and fixed holds after actual exit.",
        "- `best_any_*` also includes best-observed exits inside a future window, so it is a research ceiling and not directly tradable without a live signal.",
        "- The per-trade CSV contains the selected PnL strategy. The JSON keeps every candidate evaluated for every trade.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "md": str(md_path),
        "counts": summary["counts"],
        "totals": summary["totals"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign the best PnL strategy to each winning trade.")
    parser.add_argument("--input", required=True, type=Path, help="Winner trade-level CSV.")
    parser.add_argument("--output-prefix", required=True, type=Path, help="Output prefix for .json/.csv/.md.")
    parser.add_argument("--exit-resolution", type=Path, default=None, help="Optional exit resolution JSON with promoted buckets.")
    args = parser.parse_args()
    result = build(args.input, args.output_prefix, args.exit_resolution)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
