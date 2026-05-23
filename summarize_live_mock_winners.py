from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
OPPORTUNITY_LOG = EVOLUTION_DIR / "_live_mock_opportunities.jsonl"
TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
SUMMARY_PATH = EVOLUTION_DIR / "live_mock_replay" / "live_winning_opportunity_summary.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _is_positive_route(row: dict[str, Any]) -> bool:
    strategy_id = str(row.get("trade_strategy_id") or "")
    action = str(row.get("trade_strategy_source_queue_action") or "")
    reasons = " ".join(str(x) for x in row.get("trade_strategy_reasons") or [])
    return (
        strategy_id not in {"", "NO_TRADE"}
        and action.startswith("context_routing_exact")
        and "Historical route winner:" in reasons
    )


def _key(row: dict[str, Any]) -> str:
    return "|".join([
        str(row.get("chunk_id") or ""),
        str(row.get("asset") or ""),
        str(row.get("venue") or ""),
        str(row.get("side") or ""),
        str(row.get("trade_strategy_id") or ""),
    ])


def summarize() -> dict[str, Any]:
    opps = [
        row for row in _read_jsonl(OPPORTUNITY_LOG)
        if row.get("source") == "live_mock_trade_replay"
    ]
    trades = _read_jsonl(TRADE_LOG)
    positive = [row for row in opps if _is_positive_route(row)]
    first_open_ts = min(
        (float(row.get("ts_utc") or 0.0) for row in positive if row.get("decision") == "opened"),
        default=0.0,
    )
    positive_current_policy = [
        row for row in positive
        if not first_open_ts or float(row.get("ts_utc") or 0.0) >= first_open_ts
    ]

    def opportunity_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
        opened = [row for row in rows if row.get("decision") == "opened"]
        missed = [row for row in rows if row.get("decision") != "opened"]
        skipped = [row for row in rows if row.get("decision") == "skipped"]
        blocked = [row for row in rows if row.get("decision") == "blocked"]
        return {
            "possible_winning_route_rows": len(rows),
            "possible_winning_route_unique": len({_key(row) for row in rows}),
            "executed_winning_route_rows": len(opened),
            "executed_winning_route_unique": len({_key(row) for row in opened}),
            "missed_winning_route_rows": len(missed),
            "missed_winning_route_unique": len({_key(row) for row in missed}),
            "skipped_winning_route_rows": len(skipped),
            "blocked_winning_route_rows": len(blocked),
            "missed_reasons": Counter(str(row.get("reason") or "") for row in missed).most_common(20),
            "missed_families": Counter(str(row.get("trade_strategy_id") or "") for row in missed).most_common(20),
            "executed_families": Counter(str(row.get("trade_strategy_id") or "") for row in opened).most_common(20),
        }

    closed = [row for row in trades if row.get("status") == "closed"]
    wins = [row for row in closed if float(row.get("realized_pnl_usd") or 0.0) > 0.0]
    losses = [row for row in closed if float(row.get("realized_pnl_usd") or 0.0) <= 0.0]
    gross_wins = [row for row in closed if float(row.get("gross_pnl_usd") or 0.0) > 0.0]
    gross_losses = [row for row in closed if float(row.get("gross_pnl_usd") or 0.0) <= 0.0]
    all_time = opportunity_counts(positive)
    current_policy = opportunity_counts(positive_current_policy)
    summary = {
        "schema": "live_winning_opportunity_summary_v1",
        "opportunity_rows": len(opps),
        "policy_epoch": {
            "basis": "first live replay opened trade in this log; all older blocked rows are pre-current execution policy",
            "first_open_ts_utc": first_open_ts,
        },
        **all_time,
        "current_policy_counts": current_policy,
        "trade_rows": len(trades),
        "open_trades": sum(1 for row in trades if row.get("status") == "open"),
        "closed_trades": len(closed),
        "closed_net_wins_after_fees": len(wins),
        "closed_net_losses_after_fees": len(losses),
        "closed_gross_wins_before_fees": len(gross_wins),
        "closed_gross_losses_before_fees": len(gross_losses),
        "closed_gross_pnl_usd": round(sum(float(row.get("gross_pnl_usd") or 0.0) for row in closed), 8),
        "closed_fees_usd": round(sum(float(row.get("fees_usd") or 0.0) for row in closed), 8),
        "closed_realized_pnl_usd_after_fees": round(sum(float(row.get("realized_pnl_usd") or 0.0) for row in closed), 8),
        "mock_only": {
            "actual_execution_values": sorted({str(row.get("actual_execution")) for row in trades}),
            "actual_notional_values": sorted({str(row.get("actual_notional")) for row in trades}),
        },
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
