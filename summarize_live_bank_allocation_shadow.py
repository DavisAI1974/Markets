from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
LIVE_DIR = EVOLUTION_DIR / "live_mock_replay"
STATE_PATH = LIVE_DIR / "live_replay_state.json"
TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
AUDIT_ROWS = LIVE_DIR / "live_hindsight_missed_winner_audit_rows.csv"
AUDIT_SUMMARY = LIVE_DIR / "live_hindsight_missed_winner_audit.json"
PAIRINGS_PATH = EVOLUTION_DIR / "_family_exit_pairings.json"
OUT_JSON = LIVE_DIR / "live_bank_allocation_shadow.json"
OUT_MD = LIVE_DIR / "live_bank_allocation_shadow.md"


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


def _flt(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _trade_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("asset") or "").upper(),
            str(row.get("venue") or "").lower(),
            str(row.get("chunk_id") or ""),
            str(row.get("side") or "").lower(),
        ]
    )


def _source_priority(source: str) -> float:
    source = str(source or "")
    if source == "oracle_distilled_strategy_context":
        return 5.0
    if source == "oracle_distilled_no_side_context":
        return 4.5
    if source == "context_routing_exact_positive_pnl_instance":
        return 4.0
    if source == "context_routing_exact_instance_avoided_bad_queue":
        return 3.5
    if source.startswith("oracle_distilled"):
        return 4.0
    if source.startswith("context_routing_exact"):
        return 3.0
    return 0.0


def _is_answer_backed(row: dict[str, Any]) -> bool:
    source = str(row.get("trade_strategy_source_queue_action") or "")
    exit_key = str(row.get("exit_config_key") or "")
    risk_tags = {str(tag) for tag in (row.get("trade_strategy_risk_tags") or [])}
    strategy_id = str(row.get("trade_strategy_id") or "")
    return (
        strategy_id not in {"", "NO_TRADE"}
        and (
            _source_priority(source) > 0.0
            or "oracle" in exit_key.lower()
            or "oracle_distilled_context" in risk_tags
            or "historical_route" in risk_tags
        )
    )


def _active_epoch_id(state: dict[str, Any], explicit: str = "") -> str:
    if explicit:
        return explicit
    active = state.get("active_policy_epoch")
    if isinstance(active, dict):
        return str(active.get("policy_epoch_id") or "")
    return ""


def _quote_map(state: dict[str, Any]) -> dict[tuple[str, str], tuple[float, float, float, float]]:
    out: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    for key, value in (state.get("quotes") or {}).items():
        if "|" not in str(key) or not isinstance(value, list) or len(value) != 4:
            continue
        asset, venue = str(key).split("|", 1)
        out[(asset, venue)] = tuple(_flt(v) for v in value)  # type: ignore[assignment]
    return out


def _net_unrealized_bps(trade: dict[str, Any], quote: tuple[float, float, float, float]) -> float:
    bid, ask, mid, _ts = quote
    side = str(trade.get("side") or "").lower()
    exit_price = bid if side == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    entry = _flt(trade.get("fill_price"))
    if entry <= 0 or exit_price <= 0 or side not in {"buy", "sell"}:
        return 0.0
    signed = 1.0 if side == "buy" else -1.0
    gross_bps = signed * (exit_price - entry) / entry * 10000.0
    return gross_bps - (2.0 * _flt(trade.get("fee_bps") or 5.0))


def _base_score(trade: dict[str, Any]) -> float:
    if trade.get("best_position_score") is not None:
        return _flt(trade.get("best_position_score"))
    components = trade.get("best_position_score_components")
    if isinstance(components, dict) and components.get("score") is not None:
        return _flt(components.get("score"))
    target_bps = max(
        _flt(trade.get("exit_tp1_bps")),
        _flt(trade.get("score_exit_min_profit_bps")),
        _flt(trade.get("trade_strategy_take_profit_bps")),
    )
    confidence = _flt(trade.get("trade_strategy_confidence"))
    present = max(_flt(trade.get("trade_present_score")), _flt(trade.get("trade_option_readiness")))
    return (
        _source_priority(str(trade.get("trade_strategy_source_queue_action") or "")) * 25.0
        + confidence * 100.0
        + min(target_bps, 150.0) * 0.25
        + present * 0.15
    )


def _open_candidates(
    trades: list[dict[str, Any]],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    *,
    epoch_id: str,
    bank_usd: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for trade in trades:
        if trade.get("status") != "open":
            continue
        if epoch_id and str(trade.get("policy_epoch_id") or "") != epoch_id:
            continue
        if not _is_answer_backed(trade):
            continue
        quote = quotes.get((str(trade.get("asset") or ""), str(trade.get("venue") or "")))
        if not quote:
            continue
        net_bps = _net_unrealized_bps(trade, quote)
        base = _base_score(trade)
        notional = _flt(trade.get("notional")) or bank_usd
        candidates.append(
            {
                "key": _trade_key(trade),
                "asset": str(trade.get("asset") or ""),
                "venue": str(trade.get("venue") or ""),
                "side": str(trade.get("side") or ""),
                "strategy_id": str(trade.get("trade_strategy_id") or ""),
                "chunk_id": str(trade.get("chunk_id") or ""),
                "market_entry_ts_utc": _flt(trade.get("market_entry_ts_utc") or trade.get("ts_utc")),
                "policy_epoch_id": str(trade.get("policy_epoch_id") or ""),
                "base_position_score": round(base, 6),
                "current_position_score": round(base + net_bps, 6),
                "net_unrealized_bps_after_fees": round(net_bps, 6),
                "net_unrealized_pnl_usd_at_full_bank": round(bank_usd * net_bps / 10000.0, 8),
                "mock_trade_notional_usd": round(notional, 8),
                "exit_config_key": str(trade.get("exit_config_key") or ""),
                "opened_after_position_rotation": bool(trade.get("opened_after_position_rotation")),
            }
        )
    return sorted(
        candidates,
        key=lambda row: (
            _flt(row.get("current_position_score")),
            _flt(row.get("base_position_score")),
            _flt(row.get("net_unrealized_bps_after_fees")),
        ),
        reverse=True,
    )


def _weighted_model(
    name: str,
    description: str,
    selected: list[dict[str, Any]],
    weights: list[float],
    *,
    bank_usd: float,
) -> dict[str, Any]:
    total_weight = sum(weights)
    if total_weight <= 0 and selected:
        weights = [1.0 / len(selected)] * len(selected)
    elif total_weight > 0:
        weights = [w / total_weight for w in weights]
    holdings = []
    total_pnl = 0.0
    weighted_bps = 0.0
    for row, weight in zip(selected, weights):
        allocated = bank_usd * weight
        net_bps = _flt(row.get("net_unrealized_bps_after_fees"))
        pnl = allocated * net_bps / 10000.0
        total_pnl += pnl
        weighted_bps += weight * net_bps
        holdings.append(
            {
                "key": row["key"],
                "asset": row["asset"],
                "venue": row["venue"],
                "side": row["side"],
                "strategy_id": row["strategy_id"],
                "weight_pct": round(weight * 100.0, 4),
                "allocated_notional_usd": round(allocated, 8),
                "current_position_score": row["current_position_score"],
                "net_unrealized_bps_after_fees": row["net_unrealized_bps_after_fees"],
                "estimated_net_pnl_usd": round(pnl, 8),
            }
        )
    return {
        "model": name,
        "description": description,
        "bank_deployed_pct": 100.0 if selected else 0.0,
        "unallocated_pct": 0.0 if selected else 100.0,
        "slots_used": len(selected),
        "max_position_weight_pct": round(max(weights) * 100.0, 4) if weights else 0.0,
        "estimated_open_net_pnl_usd_after_fees": round(total_pnl, 8),
        "weighted_net_unrealized_bps_after_fees": round(weighted_bps, 6),
        "holdings": holdings,
    }


def _allocation_models(candidates: list[dict[str, Any]], bank_usd: float) -> list[dict[str, Any]]:
    if not candidates:
        return []

    models: list[dict[str, Any]] = []
    top1 = candidates[:1]
    top5 = candidates[:5]
    top10 = candidates[:10]
    by_mtm = sorted(candidates, key=lambda row: _flt(row.get("net_unrealized_bps_after_fees")), reverse=True)

    models.append(
        _weighted_model(
            "single_best_current_score",
            "100% bank on the highest current position score.",
            top1,
            [1.0],
            bank_usd=bank_usd,
        )
    )
    models.append(
        _weighted_model(
            "top_5_equal_score",
            "100% bank split equally across the top 5 current scores.",
            top5,
            [1.0] * len(top5),
            bank_usd=bank_usd,
        )
    )
    models.append(
        _weighted_model(
            "top_10_equal_score",
            "100% bank split equally across the top 10 current scores.",
            top10,
            [1.0] * len(top10),
            bank_usd=bank_usd,
        )
    )

    min5 = min((_flt(row.get("current_position_score")) for row in top5), default=0.0)
    models.append(
        _weighted_model(
            "top_5_score_weighted",
            "100% bank across top 5 with larger weights for larger score gaps.",
            top5,
            [max(1.0, _flt(row.get("current_position_score")) - min5 + 1.0) for row in top5],
            bank_usd=bank_usd,
        )
    )
    min10 = min((_flt(row.get("current_position_score")) for row in top10), default=0.0)
    models.append(
        _weighted_model(
            "top_10_score_weighted",
            "100% bank across top 10 with larger weights for larger score gaps.",
            top10,
            [max(1.0, _flt(row.get("current_position_score")) - min10 + 1.0) for row in top10],
            bank_usd=bank_usd,
        )
    )

    converge = top5
    weights = [1.0] * len(converge)
    if len(converge) >= 2:
        lead = _flt(converge[0].get("current_position_score")) - _flt(converge[1].get("current_position_score"))
        leader_net = _flt(converge[0].get("net_unrealized_bps_after_fees"))
        if lead >= 35.0 and leader_net >= 5.0:
            weights = [0.85] + ([0.15 / (len(converge) - 1)] * (len(converge) - 1))
        elif lead >= 20.0 and leader_net >= 0.0:
            weights = [0.70] + ([0.30 / (len(converge) - 1)] * (len(converge) - 1))
    models.append(
        _weighted_model(
            "converge_top_5_when_clear",
            "Start diversified; shift 70-85% to the leader only when score lead and MTM are both clear.",
            converge,
            weights,
            bank_usd=bank_usd,
        )
    )
    models.append(
        _weighted_model(
            "diagnostic_single_best_mtm",
            "Diagnostic only: 100% bank on the best current MTM after fees.",
            by_mtm[:1],
            [1.0],
            bank_usd=bank_usd,
        )
    )
    return models


def _audit_rows() -> list[dict[str, Any]]:
    if not AUDIT_ROWS.exists():
        return []
    with AUDIT_ROWS.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _batch_selection_backtest(
    trades: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    *,
    epoch_id: str,
) -> dict[str, Any]:
    winners = {
        _trade_key(row): row
        for row in audit_rows
        if _truthy(row.get("is_oracle_winner_after_fees")) and _flt(row.get("oracle_net_pnl_usd")) > 0.0
    }

    def build_rows(selected_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for trade in selected_trades:
            audit = winners.get(_trade_key(trade))
            if not audit:
                continue
            out.append(
                {
                    "key": _trade_key(trade),
                    "market_ts": _flt(trade.get("market_entry_ts_utc") or trade.get("chunk_end_ts_utc") or trade.get("ts_utc")),
                    "score": _base_score(trade),
                    "oracle_net_pnl_usd": _flt(audit.get("oracle_net_pnl_usd")),
                    "strategy_id": str(trade.get("trade_strategy_id") or ""),
                    "asset": str(trade.get("asset") or ""),
                    "venue": str(trade.get("venue") or ""),
                    "side": str(trade.get("side") or ""),
                    "status": str(trade.get("status") or ""),
                }
            )
        return out

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            minute_ts = int(round(_flt(row.get("market_ts")) / 60.0) * 60)
            groups[minute_ts].append(row)
        batches = [group for group in groups.values() if len(group) >= 2]
        if not batches:
            return {
                "matched_rows": len(rows),
                "candidate_batches": 0,
                "single_best_score_exact_hit_pct": None,
                "oracle_best_in_top5_score_pct": None,
                "models": [],
            }

        exact = 0
        top3 = 0
        top5 = 0
        top10 = 0
        oracle_total = 0.0
        single_total = 0.0
        model_totals = {
            "single_best_score": 0.0,
            "top_3_equal_score": 0.0,
            "top_5_equal_score": 0.0,
            "top_10_equal_score": 0.0,
            "top_5_score_weighted": 0.0,
        }
        examples: list[dict[str, Any]] = []
        for group in batches:
            by_oracle = sorted(group, key=lambda row: _flt(row.get("oracle_net_pnl_usd")), reverse=True)
            by_score = sorted(group, key=lambda row: (_flt(row.get("score")), _flt(row.get("oracle_net_pnl_usd"))), reverse=True)
            oracle_best = by_oracle[0]
            score_pick = by_score[0]
            oracle_total += _flt(oracle_best.get("oracle_net_pnl_usd"))
            single_total += _flt(score_pick.get("oracle_net_pnl_usd"))
            model_totals["single_best_score"] += _flt(score_pick.get("oracle_net_pnl_usd"))
            if oracle_best["key"] == score_pick["key"]:
                exact += 1
            if oracle_best["key"] in {row["key"] for row in by_score[:3]}:
                top3 += 1
            if oracle_best["key"] in {row["key"] for row in by_score[:5]}:
                top5 += 1
            if oracle_best["key"] in {row["key"] for row in by_score[:10]}:
                top10 += 1
            for size in (3, 5, 10):
                selected = by_score[:size]
                if selected:
                    model_totals[f"top_{size}_equal_score"] += sum(_flt(row.get("oracle_net_pnl_usd")) for row in selected) / len(selected)
            selected5 = by_score[:5]
            if selected5:
                min_score = min(_flt(row.get("score")) for row in selected5)
                weights = [max(1.0, _flt(row.get("score")) - min_score + 1.0) for row in selected5]
                total_weight = sum(weights)
                model_totals["top_5_score_weighted"] += sum(
                    _flt(row.get("oracle_net_pnl_usd")) * weight / total_weight
                    for row, weight in zip(selected5, weights)
                )
            if oracle_best["key"] != score_pick["key"] and len(examples) < 5:
                examples.append(
                    {
                        "market_ts_utc": int(_flt(oracle_best.get("market_ts"))),
                        "candidate_count": len(group),
                        "score_pick": {
                            key: score_pick[key]
                            for key in ("key", "strategy_id", "asset", "venue", "side", "score", "oracle_net_pnl_usd")
                        },
                        "oracle_best": {
                            key: oracle_best[key]
                            for key in ("key", "strategy_id", "asset", "venue", "side", "score", "oracle_net_pnl_usd")
                        },
                        "oracle_regret_usd": round(
                            _flt(oracle_best.get("oracle_net_pnl_usd")) - _flt(score_pick.get("oracle_net_pnl_usd")),
                            8,
                        ),
                    }
                )

        batch_count = len(batches)
        model_rows = []
        for name, total in model_totals.items():
            model_rows.append(
                {
                    "model": name,
                    "oracle_pnl_usd": round(total, 8),
                    "oracle_best_capture_pct": round((total / oracle_total * 100.0) if oracle_total else 0.0, 4),
                }
            )
        return {
            "matched_rows": len(rows),
            "candidate_batches": batch_count,
            "single_best_score_exact_hit_count": exact,
            "single_best_score_exact_hit_pct": round(exact / batch_count * 100.0, 4),
            "oracle_best_in_top3_score_pct": round(top3 / batch_count * 100.0, 4),
            "oracle_best_in_top5_score_pct": round(top5 / batch_count * 100.0, 4),
            "oracle_best_in_top10_score_pct": round(top10 / batch_count * 100.0, 4),
            "single_best_score_oracle_pnl_usd": round(single_total, 8),
            "oracle_best_possible_pnl_usd": round(oracle_total, 8),
            "single_best_score_capture_pct": round((single_total / oracle_total * 100.0) if oracle_total else 0.0, 4),
            "average_oracle_regret_per_batch_usd": round((oracle_total - single_total) / batch_count, 8),
            "models": model_rows,
            "miss_examples": examples,
        }

    all_rows = build_rows([trade for trade in trades if _is_answer_backed(trade)])
    epoch_rows = build_rows(
        [
            trade
            for trade in trades
            if _is_answer_backed(trade) and (not epoch_id or str(trade.get("policy_epoch_id") or "") == epoch_id)
        ]
    )
    return {
        "definition": "Within each same-minute decision batch, rank opened answer-backed candidates by position score and compare that pick to the highest oracle_net_pnl_usd candidate.",
        "all_matched_history": summarize(all_rows),
        "selected_epoch": summarize(epoch_rows),
    }


def _coverage_table(audit_summary: dict[str, Any], pairings: dict[str, Any]) -> list[dict[str, Any]]:
    families = pairings.get("families") if isinstance(pairings.get("families"), dict) else {}
    rows = audit_summary.get("by_pattern_family")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        family = str(row.get("pattern_family") or "")
        cfg = families.get(family) if isinstance(families.get(family), dict) else {}
        execution_enabled = bool(cfg.get("execution_enabled")) if cfg else False
        status = str(cfg.get("status") or "")
        if execution_enabled:
            build_state = "active_oracle_main"
            next_action = "keep sidecar challengers running and measure allocation"
        elif cfg:
            build_state = "shadow_or_watch_only"
            next_action = "keep in sidecar; create/promote exit only after live-positive evidence"
        else:
            build_state = "missing_pairing"
            next_action = "add family pairing or quarantine note"
        out.append(
            {
                "pattern_family": family,
                "build_state": build_state,
                "pairing_status": status,
                "active_candidate_id": str(cfg.get("active_candidate_id") or ""),
                "rows": int(row.get("rows") or 0),
                "missed_entry_rows": int(row.get("missed_entry_rows") or 0),
                "oracle_net_pnl_usd": round(_flt(row.get("oracle_net_pnl_usd")), 8),
                "oracle_incremental_vs_actual_usd": round(_flt(row.get("oracle_incremental_vs_actual_usd")), 8),
                "next_action": next_action,
            }
        )
    return out


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Live Bank Allocation Shadow",
        "",
        f"Created: {summary['created_at']}",
        "",
        "This report keeps total bank usage at 100% in every allocation model. It only changes where the bank is placed.",
        "",
        "## Selection Quality",
        "",
    ]
    quality = summary.get("selection_quality") or {}
    for label in ("all_matched_history", "selected_epoch"):
        row = quality.get(label) or {}
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Matched rows: {row.get('matched_rows')}",
                f"- Candidate batches: {row.get('candidate_batches')}",
                f"- 100% single-trade exact oracle-best hit rate: {row.get('single_best_score_exact_hit_pct')}%",
                f"- Oracle-best inside top 5 score-ranked candidates: {row.get('oracle_best_in_top5_score_pct')}%",
                f"- Single-trade oracle capture: {row.get('single_best_score_capture_pct')}%",
                f"- Average regret per batch: ${row.get('average_oracle_regret_per_batch_usd')}",
                "",
            ]
        )
        models = row.get("models") if isinstance(row.get("models"), list) else []
        if models:
            lines.extend(["| Model | Oracle PnL | Capture vs oracle-best |", "|---|---:|---:|"])
            for model in models:
                lines.append(
                    f"| `{model['model']}` | ${model['oracle_pnl_usd']} | {model['oracle_best_capture_pct']}% |"
                )
            lines.append("")

    lines.extend(["## Current Open Allocation", ""])
    candidates = summary.get("current_open_candidates") or {}
    lines.extend(
        [
            f"- Open answer-backed candidates: {candidates.get('count')}",
            f"- Bank used by every model: {summary.get('bank_usd')}",
            f"- Runtime embedded model: `{(summary.get('runtime_embedded_allocation') or {}).get('model') or ''}`",
            "",
        ]
    )
    models = summary.get("allocation_models") if isinstance(summary.get("allocation_models"), list) else []
    if models:
        lines.extend(["| Model | Slots | Max weight | Est open net PnL | Weighted net bps |", "|---|---:|---:|---:|---:|"])
        for model in models:
            lines.append(
                f"| `{model['model']}` | {model['slots_used']} | {model['max_position_weight_pct']}% | "
                f"${model['estimated_open_net_pnl_usd_after_fees']} | {model['weighted_net_unrealized_bps_after_fees']} |"
            )
        lines.append("")

    lines.extend(["## Build Coverage", ""])
    coverage = summary.get("oracle_pattern_family_coverage") if isinstance(summary.get("oracle_pattern_family_coverage"), list) else []
    if coverage:
        lines.extend(
            [
                "| Pattern family | Build state | Rows | Missed | Oracle PnL | Active candidate | Next action |",
                "|---|---|---:|---:|---:|---|---|",
            ]
        )
        for row in coverage:
            lines.append(
                f"| `{row['pattern_family']}` | `{row['build_state']}` | {row['rows']} | "
                f"{row['missed_entry_rows']} | ${row['oracle_net_pnl_usd']} | "
                f"`{row['active_candidate_id']}` | {row['next_action']} |"
            )
        lines.append("")
    return "\n".join(lines)


def summarize(epoch_id: str = "", bank_usd: float = 1000.0) -> dict[str, Any]:
    state = _read_json(STATE_PATH)
    trades = _read_jsonl(TRADE_LOG)
    audit_rows = _audit_rows()
    active_epoch_id = _active_epoch_id(state, epoch_id)
    candidates = _open_candidates(trades, _quote_map(state), epoch_id=active_epoch_id, bank_usd=bank_usd)
    summary = {
        "schema": "live_bank_allocation_shadow_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bank_policy": "100% of bank deployed in every model; models differ only by concentration and rotation target.",
        "bank_usd": bank_usd,
        "selected_policy_epoch_id": active_epoch_id,
        "current_open_candidates": {
            "count": len(candidates),
            "top_by_current_score": candidates[:10],
        },
        "allocation_models": _allocation_models(candidates, bank_usd),
        "runtime_embedded_allocation": state.get("bank_allocation") if isinstance(state.get("bank_allocation"), dict) else {},
        "selection_quality": _batch_selection_backtest(trades, audit_rows, epoch_id=active_epoch_id),
        "oracle_pattern_family_coverage": _coverage_table(_read_json(AUDIT_SUMMARY), _read_json(PAIRINGS_PATH)),
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
    parser = argparse.ArgumentParser(description="Summarize live full-bank allocation shadow models.")
    parser.add_argument("--epoch-id", default="")
    parser.add_argument("--bank-usd", type=float, default=1000.0)
    args = parser.parse_args()
    print(json.dumps(summarize(epoch_id=args.epoch_id, bank_usd=args.bank_usd), indent=2))


if __name__ == "__main__":
    main()
