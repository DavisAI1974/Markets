from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
STATE_PATH = EVOLUTION_DIR / "live_mock_replay" / "live_replay_state.json"
OPPORTUNITY_LOG = EVOLUTION_DIR / "_live_mock_opportunities.jsonl"
TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
SUMMARY_PATH = EVOLUTION_DIR / "live_mock_replay" / "live_oracle_policy_epoch_summary.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


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


def _flt(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bank_fraction(row: dict[str, Any]) -> float:
    notional = _flt(row, "notional") or _flt(row, "hypothetical_notional")
    allocated = _flt(row, "bank_allocated_notional_usd") or _flt(row, "real_mock_notional_usd")
    if notional <= 0.0 or allocated <= 0.0:
        return 0.0
    return max(0.0, allocated / notional)


def _bank_value(row: dict[str, Any], bank_key: str, shadow_key: str) -> float:
    if row.get(bank_key) is not None:
        return _flt(row, bank_key)
    return _flt(row, shadow_key) * _bank_fraction(row)


def _bank_total_fees(row: dict[str, Any]) -> float:
    explicit = _flt(row, "bank_entry_fees_usd") + _flt(row, "bank_exit_fees_usd")
    legs_total = 0.0
    for leg in row.get("exit_legs") or []:
        if isinstance(leg, dict):
            legs_total += _flt(leg, "bank_entry_fee_alloc_usd") + _flt(leg, "bank_exit_fee_usd")
    stored = _flt(row, "bank_fees_usd")
    if explicit > 0.0 or legs_total > 0.0 or stored > 0.0:
        return max(explicit, legs_total, stored)
    return _flt(row, "fees_usd") * _bank_fraction(row)


def _is_answer_backed(row: dict[str, Any]) -> bool:
    source = str(row.get("trade_strategy_source_queue_action") or "")
    exit_key = str(row.get("exit_config_key") or "")
    strategy_id = str(row.get("trade_strategy_id") or "")
    return (
        strategy_id not in {"", "NO_TRADE"}
        and (
            source.startswith("oracle_distilled")
            or source.startswith("context_routing_exact")
            or "oracle" in exit_key.lower()
        )
    )


def _counter(rows: list[dict[str, Any]], key: str, limit: int = 20) -> list[list[Any]]:
    return [[name, count] for name, count in Counter(str(row.get(key) or "") for row in rows).most_common(limit)]


def _scenario_key(row: dict[str, Any]) -> str:
    return str(row.get("mock_scenario_id") or row.get("scenario_id") or "")


def _counter_fn(rows: list[dict[str, Any]], fn: Any, limit: int = 20) -> list[list[Any]]:
    return [[name, count] for name, count in Counter(str(fn(row) or "") for row in rows).most_common(limit)]


def _trade_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("status") == "closed"]
    open_ = [row for row in rows if row.get("status") == "open"]
    bank_open = [row for row in open_ if _flt(row, "bank_allocated_notional_usd") > 0.0]
    bank_closed = [
        row for row in closed
        if _bank_fraction(row) > 0.0 or _bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd") != 0.0
    ]
    rotations = [
        row for row in closed
        if str(row.get("close_reason") or row.get("runner_exit_reason") or "") == "rotation_to_better_answer_backed_position"
    ]
    wins = [row for row in closed if _flt(row, "realized_pnl_usd") > 0.0]
    losses = [row for row in closed if _flt(row, "realized_pnl_usd") <= 0.0]
    gross_wins = [row for row in closed if _flt(row, "gross_pnl_usd") > 0.0]
    gross_losses = [row for row in closed if _flt(row, "gross_pnl_usd") <= 0.0]
    bank_wins = [row for row in bank_closed if _bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd") > 0.0]
    bank_losses = [row for row in bank_closed if _bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd") <= 0.0]
    return {
        "trades": len(rows),
        "open": len(open_),
        "closed": len(closed),
        "bank_open_counted": len(bank_open),
        "oracle_shadow_open": max(0, len(open_) - len(bank_open)),
        "bank_closed_counted": len(bank_closed),
        "oracle_shadow_closed": max(0, len(closed) - len(bank_closed)),
        "closed_net_wins_after_fees": len(wins),
        "closed_net_losses_after_fees": len(losses),
        "closed_gross_wins_before_fees": len(gross_wins),
        "closed_gross_losses_before_fees": len(gross_losses),
        "closed_gross_pnl_usd": round(sum(_flt(row, "gross_pnl_usd") for row in closed), 8),
        "closed_fees_usd": round(sum(_flt(row, "fees_usd") for row in closed), 8),
        "closed_realized_pnl_usd_after_fees": round(sum(_flt(row, "realized_pnl_usd") for row in closed), 8),
        "open_entry_fees_usd": round(sum(_flt(row, "entry_fees_usd") for row in open_), 8),
        "bank_open_entry_fees_usd": round(sum(_flt(row, "entry_fees_usd") * _bank_fraction(row) for row in open_), 8),
        "bank_closed_net_wins_after_fees": len(bank_wins),
        "bank_closed_net_losses_after_fees": len(bank_losses),
        "bank_closed_gross_pnl_usd": round(sum(_bank_value(row, "bank_gross_pnl_usd", "gross_pnl_usd") for row in closed), 8),
        "bank_closed_fees_usd": round(sum(_bank_total_fees(row) for row in closed), 8),
        "bank_closed_realized_pnl_usd_after_fees": round(
            sum(_bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd") for row in closed),
            8,
        ),
        "bank_open_allocated_notional_usd": round(sum(_flt(row, "bank_allocated_notional_usd") for row in open_), 8),
        "position_rotations": len(rotations),
        "position_rotation_realized_pnl_usd": round(
            sum(_bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd") for row in rotations),
            8,
        ),
        "closed_exit_reasons": _counter(closed, "runner_exit_reason"),
        "closed_by_strategy": _pnl_groups(closed, "trade_strategy_id"),
        "closed_by_scenario": _pnl_groups(closed, "mock_scenario_id"),
    }


def _pnl_groups(rows: list[dict[str, Any]], key: str, limit: int = 20) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "bank_count": 0.0, "realized": 0.0, "bank_realized": 0.0, "gross": 0.0, "bank_gross": 0.0, "fees": 0.0, "bank_fees": 0.0}
    )
    for row in rows:
        name = str(row.get(key) or "")
        groups[name]["count"] += 1.0
        bank_realized = _bank_value(row, "bank_realized_pnl_usd", "realized_pnl_usd")
        if _bank_fraction(row) > 0.0 or bank_realized != 0.0:
            groups[name]["bank_count"] += 1.0
        groups[name]["realized"] += _flt(row, "realized_pnl_usd")
        groups[name]["bank_realized"] += bank_realized
        groups[name]["gross"] += _flt(row, "gross_pnl_usd")
        groups[name]["bank_gross"] += _bank_value(row, "bank_gross_pnl_usd", "gross_pnl_usd")
        groups[name]["fees"] += _flt(row, "fees_usd")
        groups[name]["bank_fees"] += _bank_total_fees(row)
    out = [
        {
            "key": name,
            "count": int(values["count"]),
            "bank_count": int(values["bank_count"]),
            "realized_pnl_usd": round(values["realized"], 8),
            "bank_realized_pnl_usd": round(values["bank_realized"], 8),
            "gross_pnl_usd": round(values["gross"], 8),
            "bank_gross_pnl_usd": round(values["bank_gross"], 8),
            "fees_usd": round(values["fees"], 8),
            "bank_fees_usd": round(values["bank_fees"], 8),
        }
        for name, values in groups.items()
    ]
    return sorted(out, key=lambda row: (row["bank_realized_pnl_usd"], row["realized_pnl_usd"]))[:limit]


def _opportunity_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    opened = [row for row in rows if row.get("decision") == "opened"]
    blocked = [row for row in rows if row.get("decision") == "blocked"]
    skipped = [row for row in rows if row.get("decision") == "skipped"]
    rotated = [row for row in rows if row.get("decision") == "rotated"]
    return {
        "rows": len(rows),
        "opened": len(opened),
        "blocked": len(blocked),
        "skipped": len(skipped),
        "rotated": len(rotated),
        "no_side_rows": sum(1 for row in rows if not row.get("side")),
        "decision_counts": _counter(rows, "decision"),
        "blocked_reasons": _counter(blocked, "reason"),
        "opened_sources": _counter(opened, "trade_strategy_source_queue_action"),
        "blocked_sources": _counter(blocked, "trade_strategy_source_queue_action"),
        "opened_by_strategy": _counter(opened, "trade_strategy_id"),
        "blocked_by_strategy": _counter(blocked, "trade_strategy_id"),
        "opened_by_scenario": _counter_fn(opened, _scenario_key),
        "blocked_by_scenario": _counter_fn(blocked, _scenario_key),
    }


def summarize(epoch_id: str = "") -> dict[str, Any]:
    state = _read_json(STATE_PATH)
    active = state.get("active_policy_epoch") if isinstance(state.get("active_policy_epoch"), dict) else {}
    selected_epoch_id = epoch_id or str(active.get("policy_epoch_id") or "")
    epoch_start = _flt(active, "policy_epoch_started_wall_utc")

    all_opps = [row for row in _read_jsonl(OPPORTUNITY_LOG) if row.get("source") == "live_mock_trade_replay"]
    all_trades = _read_jsonl(TRADE_LOG)
    if selected_epoch_id:
        opps = [row for row in all_opps if str(row.get("policy_epoch_id") or "") == selected_epoch_id]
        trades = [row for row in all_trades if str(row.get("policy_epoch_id") or "") == selected_epoch_id]
    else:
        opps = [row for row in all_opps if epoch_start and _flt(row, "ts_utc") >= epoch_start]
        trades = [row for row in all_trades if epoch_start and _flt(row, "opened_wall_utc") >= epoch_start]

    answer_opps = [row for row in opps if _is_answer_backed(row)]
    answer_trades = [row for row in trades if _is_answer_backed(row)]
    legacy_open = [
        row for row in all_trades
        if row.get("status") == "open" and not str(row.get("policy_epoch_id") or "")
    ]
    summary = {
        "schema": "live_oracle_policy_epoch_summary_v1",
        "active_policy_epoch": active,
        "selected_policy_epoch_id": selected_epoch_id,
        "selected_policy_epoch_started_wall_utc": epoch_start,
        "opportunities": _opportunity_totals(opps),
        "answer_backed_opportunities": _opportunity_totals(answer_opps),
        "trades": _trade_totals(trades),
        "answer_backed_trades": _trade_totals(answer_trades),
        "legacy_carry": {
            "open_trades_without_policy_epoch": len(legacy_open),
            "open_answer_backed_without_policy_epoch": sum(1 for row in legacy_open if _is_answer_backed(row)),
        },
        "mock_only": {
            "actual_execution_values": sorted({str(row.get("actual_execution")) for row in trades}),
            "actual_notional_values": sorted({str(row.get("actual_notional")) for row in trades}),
            "pnl_accounting_roles": sorted({str(row.get("pnl_accounting_role") or "") for row in trades}),
        },
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch-id", default="")
    args = parser.parse_args()
    print(json.dumps(summarize(args.epoch_id), indent=2))


if __name__ == "__main__":
    main()
