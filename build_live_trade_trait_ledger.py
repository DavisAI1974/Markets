from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
DEFAULT_OPPORTUNITY_LOG = EVOLUTION_DIR / "_live_mock_opportunities.jsonl"
DEFAULT_TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
DEFAULT_COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
DEFAULT_OUT_JSON = EVOLUTION_DIR / "live_mock_replay" / "live_trade_trait_ledger.json"
DEFAULT_OUT_MD = EVOLUTION_DIR / "live_mock_replay" / "live_trade_trait_ledger.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _compare_runs(root: Path, *, limit: int = 5) -> list[Path]:
    if not root.exists():
        return []
    runs = [
        path for path in root.iterdir()
        if path.is_dir()
        and ((path / "family_registry_trades.jsonl").exists() or (path / "family_registry_opportunities.jsonl").exists())
    ]
    if not runs:
        return []
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[:max(1, int(limit))]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _asset(row: dict[str, Any]) -> str:
    return _text(row.get("asset")).upper()


def _venue(row: dict[str, Any]) -> str:
    return _text(row.get("venue")).lower()


def _side(row: dict[str, Any]) -> str:
    return _text(row.get("side")).lower()


def _session(row: dict[str, Any]) -> str:
    value = _text(row.get("bucket_session")).lower()
    if value:
        return value
    bucket = _text(row.get("bucket_id") or row.get("trade_strategy_variant_id")).split("|")
    return bucket[4].lower() if len(bucket) == 5 else ""


def _family(row: dict[str, Any]) -> str:
    value = _text(
        row.get("trade_strategy_id")
        or row.get("resolved_strategy_family")
        or row.get("strategy_id")
    ).upper()
    return value if value and value != "NO_TRADE" else "NO_TRADE"


def _score_band(row: dict[str, Any]) -> str:
    existing = _text(row.get("trade_score_band"))
    if existing:
        return existing
    score = int(_float(row.get("trade_present_score")))
    if score <= 0:
        return "none"
    if score < 40:
        return "0_39"
    if score < 55:
        return "40_54"
    if score < 70:
        return "55_69"
    if score < 85:
        return "70_84"
    return "85_100"


def _signed_bps_band(value: Any) -> str:
    bps = _float(value)
    if bps <= -20:
        return "down_extreme_le_-20"
    if bps <= -10:
        return "down_extended_-20_-10"
    if bps <= -5:
        return "down_edge_-10_-5"
    if bps < 0:
        return "down_small_-5_0"
    if bps == 0:
        return "flat_0"
    if bps < 5:
        return "up_small_0_5"
    if bps < 10:
        return "up_edge_5_10"
    if bps < 20:
        return "up_extended_10_20"
    return "up_extreme_ge_20"


def _dipole_band(value: Any) -> str:
    dipole = _float(value)
    if dipole <= -0.35:
        return "strong_sell"
    if dipole <= -0.15:
        return "sell"
    if dipole < 0.15:
        return "neutral"
    if dipole < 0.35:
        return "buy"
    return "strong_buy"


def _volume_band(value: Any) -> str:
    z = _float(value)
    if z <= -0.75:
        return "quiet"
    if z <= -0.25:
        return "low"
    if z < 0.75:
        return "normal"
    if z < 1.5:
        return "active"
    return "hot"


def _spread_bps(row: dict[str, Any]) -> float:
    direct = row.get("spread_bps")
    if direct is not None:
        return _float(direct)
    ticket = row.get("high_conviction_ticket") or {}
    if isinstance(ticket, dict):
        regime = ticket.get("regime") or {}
        if isinstance(regime, dict):
            snapshot = regime.get("features_snapshot") or {}
            if isinstance(snapshot, dict) and snapshot.get("spread_bps") is not None:
                return _float(snapshot.get("spread_bps"))
    return 0.0


def _spread_band(row: dict[str, Any]) -> str:
    spread = _spread_bps(row)
    if spread <= 0:
        return "unknown"
    if spread <= 0.5:
        return "tight_le_0p5"
    if spread <= 1.5:
        return "normal_0p5_1p5"
    if spread <= 3:
        return "wide_1p5_3"
    return "very_wide_gt_3"


def _pressure_relation(row: dict[str, Any]) -> str:
    side = _side(row)
    pressure = _text(row.get("pressure_watch_direction")).lower()
    if side not in {"buy", "sell"} or pressure not in {"buy", "sell"}:
        return "none"
    return "aligned" if side == pressure else "fade_pressure"


def _move_shape_category(row: dict[str, Any]) -> str:
    side = _side(row)
    chunk = _signed_bps_band(row.get("trade_current_chunk_bps"))
    recent = _signed_bps_band(row.get("trade_recent_2chunk_bps"))
    onset = _signed_bps_band(row.get("trade_from_onset_bps"))
    pressure = _pressure_relation(row)
    if side == "sell" and chunk == "up_small_0_5" and recent == "up_small_0_5":
        return "small_up_sell_fade"
    if side == "sell" and chunk in {"up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "extended_up_sell_fade"
    if side == "sell" and recent in {"down_small_-5_0", "down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "sell_down_continuation"
    if side == "buy" and chunk == "down_small_-5_0" and recent == "down_small_-5_0":
        return "small_down_buy_fade"
    if side == "buy" and chunk in {"down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "extended_down_buy_fade"
    if side == "buy" and recent in {"up_small_0_5", "up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "buy_up_continuation"
    if side == "sell" and onset == "up_small_0_5":
        return "onset_small_up_sell_fade"
    if side == "sell" and pressure == "fade_pressure":
        return "generic_sell_fade"
    if side == "buy" and pressure == "fade_pressure":
        return "generic_buy_fade"
    return f"{side or 'no_side'}_{chunk}_{recent}"


def _pattern_family_from_move_shape(move_shape: str) -> str:
    shape = _text(move_shape)
    if shape == "small_up_sell_fade":
        return "SMALL_MOVE_FADE"
    if shape == "onset_small_up_sell_fade":
        return "SMALL_MOVE_FADE_NEIGHBOR"
    if shape == "extended_up_sell_fade":
        return "EXTENDED_UP_SELL_FADE"
    if shape == "sell_down_continuation":
        return "SELL_DOWN_CONTINUATION"
    if shape in {"small_down_buy_fade", "extended_down_buy_fade"}:
        return "BUY_FADE"
    if shape == "buy_up_continuation":
        return "BUY_UP_CONTINUATION"
    if shape.startswith("sell_"):
        return "SELL_SHAPE_WATCHLIST"
    if shape.startswith("buy_"):
        return "BUY_SHAPE_WATCHLIST"
    return "UNCATALOGED"


def _pattern_family(row: dict[str, Any]) -> str:
    return _pattern_family_from_move_shape(_move_shape_category(row))


def _promotion_state_for_move_shape(move_shape: str, stats: dict[str, Any]) -> str:
    closed = int(stats.get("closed_trades") or 0)
    pnl = _float(stats.get("realized_pnl_usd_after_fees"))
    win_rate = stats.get("win_rate_after_fees")
    win = _float(win_rate) if win_rate is not None else None
    if move_shape == "small_up_sell_fade" and closed >= 30 and pnl > 0 and win is not None and win >= 0.45:
        return "promote_to_SMALL_MOVE_FADE"
    if closed < 10:
        return "insufficient_sample"
    if pnl > 0 and win is not None and win >= 0.45:
        return "candidate_watch"
    if pnl < 0 and closed >= 10:
        return "quarantine"
    return "watch"


def _news_coupling(row: dict[str, Any]) -> str:
    coupling = row.get("dipole_coupling") or {}
    if not isinstance(coupling, dict):
        coupling = {}
    state = _text(coupling.get("coupling_state")) or "unknown"
    conflicts = coupling.get("conflicts") or []
    if conflicts:
        return state + ":" + ",".join(sorted(_text(x) for x in conflicts if _text(x)))
    daily = row.get("daily_news_status") or {}
    if isinstance(daily, dict) and daily.get("stale") is True:
        return state + ":stale_news"
    return state


def _exit_profile(row: dict[str, Any]) -> str:
    return _text(
        row.get("exit_strategy_id")
        or row.get("exit_profile_id")
        or row.get("exit_management_model")
    ) or "none"


def _exit_shape(row: dict[str, Any]) -> str:
    return "|".join([
        _exit_profile(row),
        f"hold={int(_float(row.get('hold_minutes')))}",
        f"sl={_float(row.get('trade_strategy_stop_loss_bps') or row.get('stop_loss_bps')):g}",
        f"tp={_float(row.get('trade_strategy_take_profit_bps') or row.get('take_profit_bps')):g}",
        f"tp1={_float(row.get('exit_tp1_bps') or row.get('tp1_bps')):g}",
        f"trail={_float(row.get('exit_runner_trail_bps') or row.get('runner_trail_bps')):g}",
        f"maxhold={int(_float(row.get('exit_max_hold_minutes') or row.get('max_hold_minutes')))}",
    ])


def _platform_key(row: dict[str, Any]) -> str:
    return "|".join([_asset(row), _venue(row), _side(row), _session(row)])


def _route_key(row: dict[str, Any]) -> str:
    return "|".join([_family(row), _asset(row), _venue(row), _side(row), _session(row)])


def _entry_trait_key(row: dict[str, Any]) -> str:
    return "|".join([
        _family(row),
        _text(row.get("trade_stage")) or "none",
        _text(row.get("trade_option_state")) or "none",
        _score_band(row),
        _text(row.get("pressure_watch_state")) or "none",
        _pressure_relation(row),
        "onset=" + _signed_bps_band(row.get("trade_from_onset_bps")),
        "chunk=" + _signed_bps_band(row.get("trade_current_chunk_bps")),
        "recent2=" + _signed_bps_band(row.get("trade_recent_2chunk_bps")),
        "dipole=" + _dipole_band(row.get("mean_dipole")),
        "acl1=" + _dipole_band(row.get("dipole_acl1")),
        "volume=" + _volume_band(row.get("volume_zscore")),
        "spread=" + _spread_band(row),
        "news=" + _news_coupling(row),
    ])


def _full_trait_key(row: dict[str, Any]) -> str:
    return " || ".join([_route_key(row), _entry_trait_key(row), _exit_shape(row)])


def _family_exit_pair_key(row: dict[str, Any]) -> str:
    return " || ".join([
        _pattern_family(row),
        _move_shape_category(row),
        _exit_shape(row),
    ])


def _source_kind(row: dict[str, Any]) -> str:
    source = _text(row.get("source"))
    if source:
        return source
    if row.get("compare_account_id"):
        return "live_family_registry_compare"
    return "unknown"


def _normalize_opportunity(row: dict[str, Any], source_file: Path) -> dict[str, Any]:
    out = dict(row)
    out["_record_type"] = "opportunity"
    out["_source_file"] = str(source_file)
    out["_platform_key"] = _platform_key(out)
    out["_route_key"] = _route_key(out)
    out["_entry_trait_key"] = _entry_trait_key(out)
    out["_exit_shape"] = _exit_shape(out)
    out["_full_trait_key"] = _full_trait_key(out)
    out["_move_shape_category"] = _move_shape_category(out)
    out["_pattern_family"] = _pattern_family(out)
    out["_family_exit_pair_key"] = _family_exit_pair_key(out)
    out["_source_kind"] = _source_kind(out)
    out["_net_pnl_usd"] = 0.0
    out["_gross_pnl_usd"] = 0.0
    out["_fees_usd"] = 0.0
    out["_is_closed"] = False
    out["_is_open"] = False
    out["_is_net_win"] = False
    out["_is_gross_win"] = False
    return out


def _normalize_trade(row: dict[str, Any], source_file: Path) -> dict[str, Any]:
    out = dict(row)
    out["_record_type"] = "trade"
    out["_source_file"] = str(source_file)
    out["_platform_key"] = _platform_key(out)
    out["_route_key"] = _route_key(out)
    out["_entry_trait_key"] = _entry_trait_key(out)
    out["_exit_shape"] = _exit_shape(out)
    out["_full_trait_key"] = _full_trait_key(out)
    out["_move_shape_category"] = _move_shape_category(out)
    out["_pattern_family"] = _pattern_family(out)
    out["_family_exit_pair_key"] = _family_exit_pair_key(out)
    out["_source_kind"] = _source_kind(out)
    net = _float(out.get("realized_pnl_usd"))
    gross = _float(out.get("gross_pnl_usd"))
    fees = _float(out.get("fees_usd"))
    status = _text(out.get("status"))
    out["_net_pnl_usd"] = net
    out["_gross_pnl_usd"] = gross
    out["_fees_usd"] = fees
    out["_is_closed"] = status == "closed"
    out["_is_open"] = status == "open"
    out["_is_net_win"] = status == "closed" and net > 0
    out["_is_gross_win"] = status == "closed" and gross > 0
    return out


def _summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trades = [row for row in rows if row["_record_type"] == "trade"]
    opportunities = [row for row in rows if row["_record_type"] == "opportunity"]
    closed = [row for row in trades if row["_is_closed"]]
    open_trades = [row for row in trades if row["_is_open"]]
    opened_opps = [row for row in opportunities if _text(row.get("decision")) == "opened"]
    blocked_opps = [row for row in opportunities if _text(row.get("decision")) == "blocked"]
    skipped_opps = [row for row in opportunities if _text(row.get("decision")) == "skipped"]
    net_pnl = sum(_float(row.get("_net_pnl_usd")) for row in closed)
    gross_pnl = sum(_float(row.get("_gross_pnl_usd")) for row in closed)
    fees = sum(_float(row.get("_fees_usd")) for row in closed)
    wins = sum(1 for row in closed if row["_is_net_win"])
    gross_wins = sum(1 for row in closed if row["_is_gross_win"])
    possible = len(opportunities)
    score = net_pnl
    if len(closed) >= 3:
        score += 2.0 * wins - 1.0 * (len(closed) - wins)
    if possible:
        score += 0.1 * len(opened_opps) - 0.05 * len(blocked_opps)
    return {
        "records": len(rows),
        "opportunities": possible,
        "opened_opportunities": len(opened_opps),
        "blocked_opportunities": len(blocked_opps),
        "skipped_opportunities": len(skipped_opps),
        "trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "net_wins_after_fees": wins,
        "net_losses_after_fees": len(closed) - wins,
        "gross_wins_before_fees": gross_wins,
        "gross_losses_before_fees": len(closed) - gross_wins,
        "win_rate_after_fees": round(wins / len(closed), 6) if closed else None,
        "gross_win_rate": round(gross_wins / len(closed), 6) if closed else None,
        "realized_pnl_usd_after_fees": round(net_pnl, 8),
        "gross_pnl_usd_before_fees": round(gross_pnl, 8),
        "fees_usd": round(fees, 8),
        "edge_score": round(score, 8),
        "families": Counter(_family(row) for row in rows).most_common(10),
        "platforms": Counter(_platform_key(row) for row in rows).most_common(10),
        "exit_profiles": Counter(_exit_profile(row) for row in rows).most_common(10),
        "close_reasons": Counter(_text(row.get("runner_exit_reason") or row.get("close_reason")) for row in closed).most_common(10),
        "blocked_reasons": Counter(_text(row.get("reason")) for row in blocked_opps).most_common(10),
        "example_ids": [
            _text(row.get("cell_id") or row.get("chunk_id") or row.get("intent_id"))
            for row in rows[:5]
            if _text(row.get("cell_id") or row.get("chunk_id") or row.get("intent_id"))
        ],
    }


def _group(rows: list[dict[str, Any]], key_name: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get(key_name)) or "none"].append(row)
    return {
        key: _summarize_group(bucket)
        for key, bucket in sorted(grouped.items())
    }


def _ranked_items(grouped: dict[str, Any], *, min_closed: int = 0, reverse: bool = True, limit: int = 30) -> list[dict[str, Any]]:
    rows = [
        {"key": key, **value}
        for key, value in grouped.items()
        if int(value.get("closed_trades") or 0) >= min_closed
    ]
    rows.sort(
        key=lambda row: (
            _float(row.get("edge_score")),
            _float(row.get("realized_pnl_usd_after_fees")),
            int(row.get("closed_trades") or 0),
            int(row.get("opened_opportunities") or 0),
        ),
        reverse=reverse,
    )
    return rows[:limit]


def _pattern_catalog(by_move_shape: dict[str, Any]) -> dict[str, Any]:
    catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for move_shape, stats in sorted(by_move_shape.items()):
        family = _pattern_family_from_move_shape(move_shape)
        catalog[family].append({
            "move_shape": move_shape,
            "promotion_state": _promotion_state_for_move_shape(move_shape, stats),
            **stats,
        })
    return {
        family: sorted(
            rows,
            key=lambda row: (
                _float(row.get("edge_score")),
                _float(row.get("realized_pnl_usd_after_fees")),
                int(row.get("closed_trades") or 0),
            ),
            reverse=True,
        )
        for family, rows in sorted(catalog.items())
    }


def _exit_pair_state(candidates: list[dict[str, Any]], total: dict[str, Any] | None = None) -> str:
    total = total or {}
    total_closed = int(total.get("closed_trades") or 0)
    total_pnl = _float(total.get("realized_pnl_usd_after_fees"))
    total_win_rate = total.get("win_rate_after_fees")
    total_win = _float(total_win_rate) if total_win_rate is not None else None
    if total_closed >= 20 and total_pnl < 0 and (total_win is None or total_win < 0.45):
        return "evolve_create_exit_from_oracle_solution"
    positive = [
        row for row in candidates
        if _float(row.get("realized_pnl_usd_after_fees")) > 0
        and int(row.get("closed_trades") or 0) > 0
    ]
    if not positive:
        closed = sum(int(row.get("closed_trades") or 0) for row in candidates)
        return "evolve_create_exit" if closed >= 10 else "insufficient_sample"
    top = positive[0]
    top_closed = int(top.get("closed_trades") or 0)
    top_pnl = _float(top.get("realized_pnl_usd_after_fees"))
    top_avg = top_pnl / max(1, top_closed)
    if top_pnl < 2.0 or top_avg < 0.25:
        return "evolve_create_exit_low_margin"
    if len(positive) == 1:
        return "clear_winner" if top_closed >= 20 else "list_top_candidates"
    second = positive[1]
    second_pnl = max(0.0, _float(second.get("realized_pnl_usd_after_fees")))
    lead = top_pnl - second_pnl
    relative_lead = lead / max(abs(second_pnl), 1.0)
    if top_closed >= 20 and lead >= 10.0 and relative_lead >= 0.35:
        return "clear_winner"
    return "list_top_candidates"


def _exit_pair_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trade_rows = [row for row in rows if row["_record_type"] == "trade"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in trade_rows:
        grouped[(_pattern_family(row), _move_shape_category(row))].append(row)

    recommendations: list[dict[str, Any]] = []
    for (family, move_shape), bucket in sorted(grouped.items()):
        exit_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in bucket:
            exit_buckets[_exit_shape(row)].append(row)
        candidates = [
            {"exit_shape": exit_shape, **_summarize_group(exit_rows)}
            for exit_shape, exit_rows in exit_buckets.items()
            if int(_summarize_group(exit_rows).get("closed_trades") or 0) > 0
        ]
        candidates.sort(
            key=lambda row: (
                _float(row.get("realized_pnl_usd_after_fees")),
                _float(row.get("edge_score")),
                int(row.get("closed_trades") or 0),
            ),
            reverse=True,
        )
        if not candidates:
            continue
        total = _summarize_group(bucket)
        state = _exit_pair_state(candidates, total)
        shown = [] if state.startswith("evolve_create_exit") else candidates[:1 if state == "clear_winner" else 4]
        recommendations.append({
            "pattern_family": family,
            "move_shape": move_shape,
            "state": state,
            "closed_trades": total["closed_trades"],
            "open_trades": total["open_trades"],
            "realized_pnl_usd_after_fees": total["realized_pnl_usd_after_fees"],
            "net_wins_after_fees": total["net_wins_after_fees"],
            "win_rate_after_fees": total["win_rate_after_fees"],
            "candidate_exits": shown,
            "evolve_action": (
                (
                    "distill_oracle_horizon_target_and_test_as_shadow_exit"
                    if state == "evolve_create_exit_from_oracle_solution"
                    else "create_new_exit_candidate_for_this_family"
                )
                if state.startswith("evolve_create_exit")
                else ""
            ),
        })
    recommendations.sort(
        key=lambda row: (
            _float(row.get("realized_pnl_usd_after_fees")),
            int(row.get("closed_trades") or 0),
        ),
        reverse=True,
    )
    return recommendations


def build_trait_ledger(
    opportunity_log: Path,
    trade_log: Path,
    compare_root: Path,
    out_json: Path,
    out_md: Path,
    *,
    compare_run_limit: int = 5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    main_opps = [
        _normalize_opportunity(row, opportunity_log)
        for row in _read_jsonl(opportunity_log)
        if _text(row.get("source")) == "live_mock_trade_replay"
    ]
    main_trades = [
        _normalize_trade(row, trade_log)
        for row in _read_jsonl(trade_log)
    ]
    rows.extend(main_opps)
    rows.extend(main_trades)

    compare_runs = _compare_runs(compare_root, limit=compare_run_limit)
    compare_opps: list[dict[str, Any]] = []
    compare_trades: list[dict[str, Any]] = []
    for compare_run in compare_runs:
        opp_path = compare_run / "family_registry_opportunities.jsonl"
        trade_path = compare_run / "family_registry_trades.jsonl"
        run_opps = [_normalize_opportunity(row, opp_path) for row in _read_jsonl(opp_path)]
        run_trades = [_normalize_trade(row, trade_path) for row in _read_jsonl(trade_path)]
        compare_opps.extend(run_opps)
        compare_trades.extend(run_trades)
        rows.extend(run_opps)
        rows.extend(run_trades)

    grouped = {
        "by_platform": _group(rows, "_platform_key"),
        "by_route": _group(rows, "_route_key"),
        "by_entry_traits": _group(rows, "_entry_trait_key"),
        "by_exit_shape": _group(rows, "_exit_shape"),
        "by_move_shape": _group(rows, "_move_shape_category"),
        "by_pattern_family": _group(rows, "_pattern_family"),
        "by_family_exit_pair": _group(rows, "_family_exit_pair_key"),
        "by_full_traits": _group(rows, "_full_trait_key"),
    }
    trait_axis_counts = {
        "families": Counter(_family(row) for row in rows).most_common(),
        "assets": Counter(_asset(row) for row in rows).most_common(),
        "venues": Counter(_venue(row) for row in rows).most_common(),
        "sides": Counter(_side(row) for row in rows).most_common(),
        "sessions": Counter(_session(row) for row in rows).most_common(),
        "stages": Counter(_text(row.get("trade_stage")) or "none" for row in rows).most_common(),
        "score_bands": Counter(_score_band(row) for row in rows).most_common(),
        "pressure_states": Counter(_text(row.get("pressure_watch_state")) or "none" for row in rows).most_common(),
        "pressure_relations": Counter(_pressure_relation(row) for row in rows).most_common(),
        "onset_move_bands": Counter(_signed_bps_band(row.get("trade_from_onset_bps")) for row in rows).most_common(),
        "current_chunk_bands": Counter(_signed_bps_band(row.get("trade_current_chunk_bps")) for row in rows).most_common(),
        "recent_2chunk_bands": Counter(_signed_bps_band(row.get("trade_recent_2chunk_bps")) for row in rows).most_common(),
        "dipole_bands": Counter(_dipole_band(row.get("mean_dipole")) for row in rows).most_common(),
        "volume_bands": Counter(_volume_band(row.get("volume_zscore")) for row in rows).most_common(),
        "spread_bands": Counter(_spread_band(row) for row in rows).most_common(),
        "news_coupling": Counter(_news_coupling(row) for row in rows).most_common(),
        "exit_profiles": Counter(_exit_profile(row) for row in rows).most_common(),
        "move_shape_categories": Counter(_move_shape_category(row) for row in rows).most_common(),
        "pattern_families": Counter(_pattern_family(row) for row in rows).most_common(),
    }
    closed = [row for row in rows if row["_record_type"] == "trade" and row["_is_closed"]]
    gross_fee_losers = [
        row for row in closed
        if row["_is_gross_win"] and not row["_is_net_win"]
    ]
    ledger = {
        "schema": "live_trade_trait_ledger_v1",
        "created_at": _now_iso(),
        "sources": {
            "main_opportunity_log": str(opportunity_log),
            "main_trade_log": str(trade_log),
            "compare_run_dir": str(compare_runs[0]) if compare_runs else "",
            "compare_run_dirs": [str(path) for path in compare_runs],
            "compare_run_limit": int(compare_run_limit),
        },
        "record_counts": {
            "main_opportunities": len(main_opps),
            "main_trades": len(main_trades),
            "compare_runs": len(compare_runs),
            "compare_opportunities": len(compare_opps),
            "compare_trades": len(compare_trades),
            "all_records": len(rows),
            "closed_trades": len(closed),
        },
        "trait_axes": trait_axis_counts,
        "rankings": {
            "best_platforms": _ranked_items(grouped["by_platform"], min_closed=1),
            "worst_platforms": _ranked_items(grouped["by_platform"], min_closed=1, reverse=False),
            "best_routes": _ranked_items(grouped["by_route"], min_closed=1),
            "worst_routes": _ranked_items(grouped["by_route"], min_closed=1, reverse=False),
            "best_entry_traits": _ranked_items(grouped["by_entry_traits"], min_closed=1),
            "worst_entry_traits": _ranked_items(grouped["by_entry_traits"], min_closed=1, reverse=False),
            "best_exit_shapes": _ranked_items(grouped["by_exit_shape"], min_closed=1),
            "worst_exit_shapes": _ranked_items(grouped["by_exit_shape"], min_closed=1, reverse=False),
            "best_move_shapes": _ranked_items(grouped["by_move_shape"], min_closed=1),
            "worst_move_shapes": _ranked_items(grouped["by_move_shape"], min_closed=1, reverse=False),
            "best_pattern_families": _ranked_items(grouped["by_pattern_family"], min_closed=1),
            "worst_pattern_families": _ranked_items(grouped["by_pattern_family"], min_closed=1, reverse=False),
            "best_family_exit_pairs": _ranked_items(grouped["by_family_exit_pair"], min_closed=1),
            "worst_family_exit_pairs": _ranked_items(grouped["by_family_exit_pair"], min_closed=1, reverse=False),
            "best_full_traits": _ranked_items(grouped["by_full_traits"], min_closed=1),
            "worst_full_traits": _ranked_items(grouped["by_full_traits"], min_closed=1, reverse=False),
        },
        "pattern_catalog": _pattern_catalog(grouped["by_move_shape"]),
        "exit_pair_recommendations": _exit_pair_recommendations(rows),
        "fee_drag": {
            "gross_winner_net_loser_count": len(gross_fee_losers),
            "gross_winner_net_loser_routes": Counter(row["_route_key"] for row in gross_fee_losers).most_common(20),
        },
        **grouped,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    out_md.write_text(_render_markdown(ledger), encoding="utf-8")
    return ledger


def _fmt_money(value: Any) -> str:
    return f"${_float(value):+.2f}"


def _render_rank_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Key | Closed | Net wins | Win rate | Net PnL | Gross PnL | Fees | Open | Opened opps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows[:12]:
        win_rate = row.get("win_rate_after_fees")
        win_rate_text = "" if win_rate is None else f"{float(win_rate):.1%}"
        key = str(row.get("key") or "").replace("|", "\\|")
        lines.append(
            f"| `{key}` | {row.get('closed_trades', 0)} | {row.get('net_wins_after_fees', 0)} | "
            f"{win_rate_text} | {_fmt_money(row.get('realized_pnl_usd_after_fees'))} | "
            f"{_fmt_money(row.get('gross_pnl_usd_before_fees'))} | {_fmt_money(row.get('fees_usd'))} | "
            f"{row.get('open_trades', 0)} | {row.get('opened_opportunities', 0)} |"
        )
    lines.append("")
    return lines


def _render_pattern_catalog(catalog: dict[str, Any]) -> list[str]:
    lines = [
        "## Pattern Catalog",
        "",
        "| Family | Move shape | State | Closed | Net wins | Win rate | Net PnL | Open |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    emitted = 0
    for family, rows in catalog.items():
        for row in rows[:4]:
            win_rate = row.get("win_rate_after_fees")
            win_rate_text = "" if win_rate is None else f"{float(win_rate):.1%}"
            lines.append(
                f"| `{family}` | `{row.get('move_shape')}` | `{row.get('promotion_state')}` | "
                f"{row.get('closed_trades', 0)} | {row.get('net_wins_after_fees', 0)} | "
                f"{win_rate_text} | {_fmt_money(row.get('realized_pnl_usd_after_fees'))} | "
                f"{row.get('open_trades', 0)} |"
            )
            emitted += 1
            if emitted >= 24:
                lines.append("")
                return lines
    lines.append("")
    return lines


def _render_exit_pair_recommendations(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Exit Pair Recommendations",
        "",
        "| Pattern family | Move shape | State | Closed | Win rate | Net PnL | Candidate exits | Evolve action |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows[:18]:
        win_rate = row.get("win_rate_after_fees")
        win_rate_text = "" if win_rate is None else f"{float(win_rate):.1%}"
        candidates = []
        for candidate in row.get("candidate_exits") or []:
            candidates.append(
                f"{candidate.get('closed_trades', 0)} closed, "
                f"{_fmt_money(candidate.get('realized_pnl_usd_after_fees'))}: "
                f"{candidate.get('exit_shape')}"
            )
        candidate_text = "<br>".join(str(item).replace("|", "\\|") for item in candidates)
        lines.append(
            f"| `{row.get('pattern_family')}` | `{row.get('move_shape')}` | `{row.get('state')}` | "
            f"{row.get('closed_trades', 0)} | {win_rate_text} | "
            f"{_fmt_money(row.get('realized_pnl_usd_after_fees'))} | "
            f"{candidate_text} | `{row.get('evolve_action') or ''}` |"
        )
    lines.append("")
    return lines


def _render_markdown(ledger: dict[str, Any]) -> str:
    counts = ledger["record_counts"]
    rankings = ledger["rankings"]
    lines = [
        "# Live Trade Trait Ledger",
        "",
        f"Created: {ledger['created_at']}",
        "",
        "## Sources",
        "",
        f"- Main opportunities: `{ledger['sources']['main_opportunity_log']}`",
        f"- Main trades: `{ledger['sources']['main_trade_log']}`",
        f"- Compare run: `{ledger['sources']['compare_run_dir']}`",
        f"- Compare runs included: {len(ledger['sources'].get('compare_run_dirs') or [])}",
        "",
        "## Counts",
        "",
        f"- Main opportunities: {counts['main_opportunities']}",
        f"- Main trades: {counts['main_trades']}",
        f"- Compare runs: {counts.get('compare_runs', 0)}",
        f"- Compare opportunities: {counts['compare_opportunities']}",
        f"- Compare trades: {counts['compare_trades']}",
        f"- Closed trades: {counts['closed_trades']}",
        "",
        "## Trait Axes",
        "",
        "These are the axes now available for organizing possible winners: platform, route, lifecycle, pressure relation, move bands, dipole bands, volume band, spread band, news coupling, and exit shape.",
        "",
    ]
    lines.extend(_render_rank_table("Best Routes", rankings["best_routes"]))
    lines.extend(_render_rank_table("Worst Routes", rankings["worst_routes"]))
    lines.extend(_render_rank_table("Best Entry Trait Bundles", rankings["best_entry_traits"]))
    lines.extend(_render_rank_table("Worst Entry Trait Bundles", rankings["worst_entry_traits"]))
    lines.extend(_render_rank_table("Best Move Shape Categories", rankings["best_move_shapes"]))
    lines.extend(_render_rank_table("Worst Move Shape Categories", rankings["worst_move_shapes"]))
    lines.extend(_render_rank_table("Best Pattern Families", rankings["best_pattern_families"]))
    lines.extend(_render_rank_table("Worst Pattern Families", rankings["worst_pattern_families"]))
    lines.extend(_render_pattern_catalog(ledger.get("pattern_catalog") or {}))
    lines.extend(_render_rank_table("Best Family x Exit Pairs", rankings["best_family_exit_pairs"]))
    lines.extend(_render_rank_table("Worst Family x Exit Pairs", rankings["worst_family_exit_pairs"]))
    lines.extend(_render_exit_pair_recommendations(ledger.get("exit_pair_recommendations") or []))
    lines.extend(_render_rank_table("Best Exit Shapes", rankings["best_exit_shapes"]))
    lines.extend(_render_rank_table("Worst Exit Shapes", rankings["worst_exit_shapes"]))
    lines.extend([
        "## Fee Drag",
        "",
        f"- Gross winners that became net losers after fees: {ledger['fee_drag']['gross_winner_net_loser_count']}",
        "",
        "| Route | Count |",
        "|---|---:|",
    ])
    for route, count in ledger["fee_drag"]["gross_winner_net_loser_routes"][:20]:
        lines.append(f"| `{str(route).replace('|', '\\|')}` | {count} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opportunity-log", default=str(DEFAULT_OPPORTUNITY_LOG))
    parser.add_argument("--trade-log", default=str(DEFAULT_TRADE_LOG))
    parser.add_argument("--compare-root", default=str(DEFAULT_COMPARE_ROOT))
    parser.add_argument("--compare-run-limit", type=int, default=5)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()
    ledger = build_trait_ledger(
        Path(args.opportunity_log),
        Path(args.trade_log),
        Path(args.compare_root),
        Path(args.out_json),
        Path(args.out_md),
        compare_run_limit=int(args.compare_run_limit),
    )
    print(json.dumps({
        "schema": ledger["schema"],
        "created_at": ledger["created_at"],
        "record_counts": ledger["record_counts"],
        "outputs": {
            "json": args.out_json,
            "markdown": args.out_md,
        },
        "best_routes": ledger["rankings"]["best_routes"][:5],
        "worst_routes": ledger["rankings"]["worst_routes"][:5],
    }, indent=2))


if __name__ == "__main__":
    main()
