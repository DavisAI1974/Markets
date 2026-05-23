from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mock_trade_replay import VENUES
from phase1_5_evaluator import load_bars


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
DEFAULT_MAIN_TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
DEFAULT_COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
DEFAULT_PAIRINGS_PATH = EVOLUTION_DIR / "_family_exit_pairings.json"
DEFAULT_OUT_DIR = EVOLUTION_DIR / "live_mock_replay"
DEFAULT_STATE_PATH = DEFAULT_OUT_DIR / "live_replay_state.json"
DEFAULT_OUT_JSON = DEFAULT_OUT_DIR / "live_sidecar_exit_restatement.json"
DEFAULT_OUT_MD = DEFAULT_OUT_DIR / "live_sidecar_exit_restatement.md"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "live_sidecar_exit_restatement_rows.csv"
DEFAULT_POLICY_CSV = DEFAULT_OUT_DIR / "live_counterfactual_exit_policy_rows.csv"
DEFAULT_DATA_DIR = REPO_ROOT / "live_data"
TARGET_NOTIONAL_USD = 10000.0
NY_TZ = ZoneInfo("America/New_York")
HORIZONS_MINUTES = (10, 30, 60, 120, 240, 360)
RUNTIME_SELECTOR_HORIZONS_MINUTES = (10, 30, 60)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_start_utc() -> float:
    today_ny = datetime.now(NY_TZ).date()
    midnight_ny = datetime.combine(today_ny, time.min, tzinfo=NY_TZ)
    return midnight_ny.astimezone(timezone.utc).timestamp()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _read_state_trades(path: Path, *, state: dict[str, Any] | None = None, include_retired: bool = False) -> list[dict[str, Any]]:
    state = state if isinstance(state, dict) else _read_json(path)
    rows: list[dict[str, Any]] = []
    sections = ["accounts"]
    if include_retired:
        sections.append("retired_accounts")
    for section in sections:
        accounts = state.get(section) if isinstance(state.get(section), dict) else {}
        for account_id, account in accounts.items():
            if not isinstance(account, dict):
                continue
            for trade in account.get("trades") or []:
                if not isinstance(trade, dict):
                    continue
                row = dict(trade)
                row.setdefault("_state_account_id", account_id)
                row.setdefault("_state_section", section)
                rows.append(row)
    return rows


def _merge_trade_rows(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in sources:
        for row in rows:
            key = _text(row.get("cell_id")) or _entry_key(row, include_family=True)
            if not key:
                key = hashlib.sha1(json.dumps(row, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            existing = merged.get(key)
            if existing is None or _row_time(row) >= _row_time(existing):
                merged[key] = row
    return list(merged.values())


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _asset(row: dict[str, Any]) -> str:
    return _text(row.get("asset")).upper()


def _venue(row: dict[str, Any]) -> str:
    return _text(row.get("venue")).lower()


def _venue_label(row: dict[str, Any]) -> str:
    return _text(row.get("venue"))


def _side(row: dict[str, Any]) -> str:
    return _text(row.get("side")).lower()


def _family(row: dict[str, Any]) -> str:
    return _text(row.get("trade_strategy_id") or row.get("strategy_id")).upper()


def _session(row: dict[str, Any]) -> str:
    direct = _text(row.get("bucket_session"))
    if direct:
        return direct
    bucket = _text(row.get("bucket_id") or row.get("trade_strategy_variant_id")).split("|")
    return bucket[4] if len(bucket) >= 5 else ""


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


def _memory_trait_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "bucket_session": _session(row),
        "trade_stage": _text(row.get("trade_stage")),
        "trade_score_band": _score_band(row),
        "trade_from_onset_bps": _float(row.get("trade_from_onset_bps")),
        "trade_current_chunk_bps": _float(row.get("trade_current_chunk_bps")),
        "trade_recent_2chunk_bps": _float(row.get("trade_recent_2chunk_bps")),
        "onset_move_band": _signed_bps_band(row.get("trade_from_onset_bps")),
        "current_chunk_band": _signed_bps_band(row.get("trade_current_chunk_bps")),
        "recent_2chunk_band": _signed_bps_band(row.get("trade_recent_2chunk_bps")),
        "pressure_relation": _pressure_relation(row),
        "move_shape_category": _move_shape_category(row),
    }


def _entry_ts(row: dict[str, Any]) -> float:
    return _float(row.get("market_entry_ts_utc") or row.get("ts_utc"))


def _row_time(row: dict[str, Any]) -> float:
    return max(
        _float(row.get("opened_wall_utc")),
        _entry_ts(row),
        _float(row.get("ts_utc")),
    )


def _entry_key(row: dict[str, Any], *, include_family: bool = True) -> str:
    parts = [
        _asset(row),
        _venue(row),
        _side(row),
        str(int(round(_entry_ts(row)))),
    ]
    if include_family:
        parts.append(_family(row))
    return "|".join(parts)


def _route_key(row: dict[str, Any]) -> str:
    return "|".join([_family(row), _asset(row), _venue(row), _side(row), _session(row)])


def _extract_exit_variant_id(row: dict[str, Any]) -> str:
    direct = _text(row.get("exit_variant_id"))
    if direct:
        return direct
    scenario_id = _text(row.get("mock_scenario_id") or row.get("compare_account_id"))
    if "__exit_" in scenario_id:
        return scenario_id.split("__exit_", 1)[1].split("__side_", 1)[0]
    known = {
        "family_registry_fast_exit": "fast_scalp",
        "family_registry_runner_exit": "runner_exit",
        "family_registry_dispatch": "default_gated",
        "family_registry_no_bucket_guard": "default_gated_no_bucket_guard",
        "family_registry_no_bucket_ignore_stale_news": "default_gated_no_bucket_ignore_stale_news",
    }
    return known.get(scenario_id, "")


def _exit_profile(row: dict[str, Any]) -> str:
    return _text(row.get("exit_strategy_id") or row.get("exit_profile_id") or row.get("exit_management_model"))


def _exit_shape(row: dict[str, Any]) -> str:
    return "|".join([
        _exit_profile(row) or "none",
        f"hold={int(_float(row.get('hold_minutes')))}",
        f"sl={_float(row.get('trade_strategy_stop_loss_bps') or row.get('stop_loss_bps')):g}",
        f"tp={_float(row.get('trade_strategy_take_profit_bps') or row.get('take_profit_bps')):g}",
        f"score_hold={_float(row.get('score_exit_min_hold_minutes')):g}",
        f"score_profit={_float(row.get('score_exit_min_profit_bps')):g}",
        f"tp1={_float(row.get('exit_tp1_bps') or row.get('tp1_bps')):g}",
        f"trail={_float(row.get('exit_runner_trail_bps') or row.get('runner_trail_bps')):g}",
        f"maxhold={int(_float(row.get('exit_max_hold_minutes') or row.get('max_hold_minutes')))}",
    ])


def _notional(row: dict[str, Any]) -> float:
    return _float(row.get("notional") or row.get("hypothetical_notional"), TARGET_NOTIONAL_USD)


def _scaled(value: Any, row: dict[str, Any], target_notional_usd: float) -> float:
    notional = _notional(row)
    if notional <= 0:
        return _float(value)
    return _float(value) * target_notional_usd / notional


def _net_pnl(row: dict[str, Any]) -> float:
    if _text(row.get("status")).lower() == "closed":
        return _float(row.get("realized_pnl_usd"))
    return _float(row.get("mark_to_market_pnl_usd") or row.get("unrealized_pnl_usd"))


def _net_pnl_10k(row: dict[str, Any], target_notional_usd: float) -> float:
    return _scaled(_net_pnl(row), row, target_notional_usd)


def _gross_pnl_10k(row: dict[str, Any], target_notional_usd: float) -> float:
    return _scaled(row.get("gross_pnl_usd"), row, target_notional_usd)


def _fees_10k(row: dict[str, Any], target_notional_usd: float) -> float:
    return _scaled(row.get("fees_usd"), row, target_notional_usd)


def _load_market_bars(data_dir: Path) -> dict[tuple[str, str], tuple[list[Any], list[float]]]:
    out: dict[tuple[str, str], tuple[list[Any], list[float]]] = {}
    for asset, venues in VENUES.items():
        for venue, filename in venues.items():
            path = data_dir / filename
            if not path.exists():
                continue
            try:
                bars = load_bars(str(path))
            except Exception:
                bars = []
            if not bars:
                continue
            out[(asset.upper(), venue.lower())] = (bars, [_float(getattr(bar, "ts", 0.0)) for bar in bars])
    return out


def _bar_price(bar: Any, side: str, *, oracle: bool) -> float:
    if oracle:
        if side == "buy":
            return _float(getattr(bar, "high", 0.0)) or _float(getattr(bar, "bid", 0.0)) or _float(getattr(bar, "close", 0.0))
        return _float(getattr(bar, "low", 0.0)) or _float(getattr(bar, "ask", 0.0)) or _float(getattr(bar, "close", 0.0))
    if side == "buy":
        return _float(getattr(bar, "bid", 0.0)) or _float(getattr(bar, "close", 0.0))
    return _float(getattr(bar, "ask", 0.0)) or _float(getattr(bar, "close", 0.0))


def _signed_bps(side: str, entry_price: float, exit_price: float) -> float:
    if entry_price <= 0 or exit_price <= 0:
        return 0.0
    if side == "buy":
        return ((exit_price - entry_price) / entry_price) * 10000.0
    if side == "sell":
        return ((entry_price - exit_price) / entry_price) * 10000.0
    return 0.0


def _candidate_from_exit_price(
    *,
    trade: dict[str, Any],
    candidate_id: str,
    candidate_class: str,
    horizon_minutes: int,
    start_ts: float,
    exit_ts: float,
    entry_price: float,
    exit_price: float,
    fee_bps: float,
    target_notional_usd: float,
    complete: bool,
) -> dict[str, Any]:
    side = _side(trade)
    gross_bps = _signed_bps(side, entry_price, exit_price)
    net_bps = gross_bps - (2.0 * fee_bps)
    return {
        "candidate_id": candidate_id,
        "candidate_class": candidate_class,
        "horizon_minutes": horizon_minutes,
        "complete": bool(complete),
        "start_ts_utc": start_ts,
        "exit_ts_utc": exit_ts,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_bps": round(gross_bps, 8),
        "net_bps": round(net_bps, 8),
        "net_pnl_usd_at_target_notional": round(target_notional_usd * net_bps / 10000.0, 6),
    }


def _bar_at_or_after(bars: list[Any], ts_index: list[float], ts: float) -> Any | None:
    idx = bisect_left(ts_index, ts)
    if idx >= len(bars):
        return None
    return bars[idx]


def _best_oracle_bar(bars: list[Any], ts_index: list[float], start_ts: float, due_ts: float, side: str) -> Any | None:
    start_idx = bisect_left(ts_index, start_ts)
    due_idx = bisect_left(ts_index, due_ts)
    future = bars[start_idx:min(len(bars), max(start_idx + 1, due_idx + 1))]
    if not future:
        return None
    if side == "buy":
        return max(future, key=lambda bar: _bar_price(bar, side, oracle=True))
    return min(future, key=lambda bar: _bar_price(bar, side, oracle=True))


def _runtime_exit_signal_start_ts(trade: dict[str, Any], entry_ts: float, exit_ts: float) -> float:
    elapsed_values: list[float] = []
    for field in (
        "runtime_counterfactual_first_exit_signal_elapsed_min",
        "historic_parity_first_exit_signal_elapsed_min",
    ):
        value = trade.get(field)
        if value is not None:
            elapsed = _float(value, -1.0)
            if elapsed >= 0:
                elapsed_values.append(elapsed)
    for signal in trade.get("deferred_exit_signals") or []:
        if not isinstance(signal, dict):
            continue
        elapsed = _float(signal.get("elapsed_min"), -1.0)
        if elapsed >= 0:
            elapsed_values.append(elapsed)
    for decision_field in ("exit_decision", "last_exit_decision"):
        decision = trade.get(decision_field)
        if not isinstance(decision, dict):
            continue
        if not _text(decision.get("reason")):
            continue
        elapsed = _float(decision.get("elapsed_min"), -1.0)
        if elapsed >= 0:
            elapsed_values.append(elapsed)
    if elapsed_values:
        return float(entry_ts) + min(elapsed_values) * 60.0
    return float(exit_ts) if exit_ts > 0 else 0.0


def _counterfactual_candidates_for_trade(
    trade: dict[str, Any],
    bars_by_market: dict[tuple[str, str], tuple[list[Any], list[float]]],
    target_notional_usd: float,
) -> list[dict[str, Any]]:
    if _text(trade.get("status")).lower() != "closed":
        return []
    side = _side(trade)
    entry_price = _float(trade.get("fill_price"))
    if side not in {"buy", "sell"} or entry_price <= 0:
        return []
    market = bars_by_market.get((_asset(trade), _venue(trade)))
    if not market:
        return []
    bars, ts_index = market
    if not bars:
        return []
    fee_bps = _float(trade.get("fee_bps"), 5.0)
    entry_ts = _entry_ts(trade)
    exit_ts = _float(trade.get("exit_ts_utc"))
    latest_ts = _float(getattr(bars[-1], "ts", 0.0))
    candidates = [{
        "candidate_id": f"actual_exit::{_text(trade.get('exit_strategy_id')) or 'runtime'}",
        "candidate_class": "actual_exit",
        "horizon_minutes": 0,
        "complete": True,
        "start_ts_utc": entry_ts,
        "exit_ts_utc": exit_ts,
        "entry_price": entry_price,
        "exit_price": _float(trade.get("exit_price")),
        "gross_bps": round((_gross_pnl_10k(trade, target_notional_usd) / target_notional_usd) * 10000.0, 8),
        "net_bps": round((_net_pnl_10k(trade, target_notional_usd) / target_notional_usd) * 10000.0, 8),
        "net_pnl_usd_at_target_notional": round(_net_pnl_10k(trade, target_notional_usd), 6),
    }]
    starts = [("after_entry", entry_ts)]
    runtime_signal_ts = _runtime_exit_signal_start_ts(trade, entry_ts, exit_ts)
    if runtime_signal_ts > 0:
        starts.append(("after_runtime_exit", runtime_signal_ts))
    for start_label, start_ts in starts:
        for horizon in HORIZONS_MINUTES:
            due_ts = start_ts + horizon * 60.0
            complete = latest_ts >= due_ts
            fixed_bar = _bar_at_or_after(bars, ts_index, due_ts)
            if fixed_bar is not None:
                fixed_exit_ts = _float(getattr(fixed_bar, "ts", 0.0))
                candidates.append(_candidate_from_exit_price(
                    trade=trade,
                    candidate_id=f"fixed_hold_{horizon}m_{start_label}",
                    candidate_class="fixed_hold",
                    horizon_minutes=horizon,
                    start_ts=start_ts,
                    exit_ts=fixed_exit_ts,
                    entry_price=entry_price,
                    exit_price=_bar_price(fixed_bar, side, oracle=False),
                    fee_bps=fee_bps,
                    target_notional_usd=target_notional_usd,
                    complete=complete,
                ))
            oracle_bar = _best_oracle_bar(bars, ts_index, start_ts, due_ts, side)
            if oracle_bar is not None:
                oracle_exit_ts = _float(getattr(oracle_bar, "ts", 0.0))
                candidates.append(_candidate_from_exit_price(
                    trade=trade,
                    candidate_id=f"oracle_best_within_{horizon}m_{start_label}",
                    candidate_class="oracle_best_within_horizon",
                    horizon_minutes=horizon,
                    start_ts=start_ts,
                    exit_ts=oracle_exit_ts,
                    entry_price=entry_price,
                    exit_price=_bar_price(oracle_bar, side, oracle=True),
                    fee_bps=fee_bps,
                    target_notional_usd=target_notional_usd,
                    complete=complete,
                ))
    return candidates


def _best_counterfactuals(
    main_rows: list[dict[str, Any]],
    bars_by_market: dict[tuple[str, str], tuple[list[Any], list[float]]],
    target_notional_usd: float,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for trade in main_rows:
        cell_id = _text(trade.get("cell_id")) or _entry_key(trade, include_family=True)
        candidates = _counterfactual_candidates_for_trade(trade, bars_by_market, target_notional_usd)
        if not candidates:
            continue
        executable = [
            candidate for candidate in candidates
            if candidate["candidate_class"] in {"actual_exit", "fixed_hold"}
        ]
        runtime_executable = [
            candidate for candidate in executable
            if candidate["candidate_class"] == "actual_exit"
            or int(candidate.get("horizon_minutes") or 0) in RUNTIME_SELECTOR_HORIZONS_MINUTES
        ]
        best_executable = max(executable, key=lambda row: _float(row.get("net_pnl_usd_at_target_notional")))
        best_runtime_executable = (
            max(runtime_executable, key=lambda row: _float(row.get("net_pnl_usd_at_target_notional")))
            if runtime_executable
            else {}
        )
        best_any = max(candidates, key=lambda row: _float(row.get("net_pnl_usd_at_target_notional")))
        out[cell_id] = {
            "cell_id": cell_id,
            "candidate_count": len(candidates),
            "best_executable": best_executable,
            "best_runtime_executable": best_runtime_executable,
            "best_any_oracle": best_any,
        }
    return out


def _exit_config_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "exit_profile_id": _exit_profile(row) or "gated_profitable_score_news_exits_v1",
        "hold_minutes": int(_float(row.get("hold_minutes"))),
        "stop_loss_bps": _float(row.get("trade_strategy_stop_loss_bps") or row.get("stop_loss_bps")),
        "take_profit_bps": _float(row.get("trade_strategy_take_profit_bps") or row.get("take_profit_bps")),
        "score_exit_min_hold_minutes": _float(row.get("score_exit_min_hold_minutes")),
        "score_exit_min_profit_bps": _float(row.get("score_exit_min_profit_bps")),
        "profitable_hold_extension_minutes": _float(row.get("profitable_hold_extension_minutes")),
        "tp1_bps": _float(row.get("exit_tp1_bps") or row.get("tp1_bps")),
        "scale_out_fraction": _float(row.get("exit_scale_out_fraction") or row.get("scale_out_fraction")),
        "runner_trail_bps": _float(row.get("exit_runner_trail_bps") or row.get("runner_trail_bps")),
        "max_hold_minutes": _float(row.get("exit_max_hold_minutes") or row.get("max_hold_minutes")),
        "defer_unprofitable_pressure_exits": bool(row.get("defer_unprofitable_pressure_exits")),
        "news_can_full_flat_profitable": bool(row.get("news_can_full_flat_profitable")),
    }


def _candidate_id(family: str, exit_variant_id: str, exit_shape: str) -> str:
    base = exit_variant_id or hashlib.sha1(exit_shape.encode("utf-8")).hexdigest()[:10]
    return f"sidecar_{family.lower()}_{base}".replace("__", "_")


def _compare_runs(compare_root: Path, start_utc: float, limit: int) -> list[Path]:
    if not compare_root.exists():
        return []
    runs = [
        path for path in compare_root.iterdir()
        if path.is_dir()
        and (path / "family_registry_trades.jsonl").exists()
        and path.stat().st_mtime >= start_utc - 6 * 3600
    ]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[:max(1, int(limit))]


def _summarize_rows(rows: list[dict[str, Any]], target_notional_usd: float) -> dict[str, Any]:
    closed = [row for row in rows if _text(row.get("status")).lower() == "closed"]
    opened = [row for row in rows if _text(row.get("status")).lower() in {"closed", "open"}]
    wins = [row for row in closed if _net_pnl_10k(row, target_notional_usd) > 0]
    return {
        "opened": len(opened),
        "closed": len(closed),
        "open": len(opened) - len(closed),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed), 6) if closed else None,
        "net_pnl_usd_at_target_notional": round(sum(_net_pnl_10k(row, target_notional_usd) for row in closed), 6),
        "gross_pnl_usd_at_target_notional": round(sum(_gross_pnl_10k(row, target_notional_usd) for row in closed), 6),
        "fees_usd_at_target_notional": round(sum(_fees_10k(row, target_notional_usd) for row in closed), 6),
    }


def _best_sidecar_by_entry(sidecar_rows: list[dict[str, Any]], target_notional_usd: float) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sidecar_rows:
        if _text(row.get("status")).lower() != "closed":
            continue
        grouped[_entry_key(row, include_family=True)].append(row)
    best: dict[str, dict[str, Any]] = {}
    for entry_key, rows in grouped.items():
        rows.sort(
            key=lambda row: (
                _net_pnl_10k(row, target_notional_usd),
                _gross_pnl_10k(row, target_notional_usd),
                -_float(row.get("exit_ts_utc")),
            ),
            reverse=True,
        )
        winner = rows[0]
        best[entry_key] = {
            "entry_key": entry_key,
            "variant_count": len({_exit_shape(row) for row in rows}),
            "closed_variant_rows": len(rows),
            "best_row": winner,
            "best_net_pnl_usd_at_target_notional": round(_net_pnl_10k(winner, target_notional_usd), 6),
            "best_gross_pnl_usd_at_target_notional": round(_gross_pnl_10k(winner, target_notional_usd), 6),
            "best_fees_usd_at_target_notional": round(_fees_10k(winner, target_notional_usd), 6),
            "best_exit_variant_id": _extract_exit_variant_id(winner),
            "best_exit_shape": _exit_shape(winner),
            "best_mock_scenario_id": _text(winner.get("mock_scenario_id")),
            "best_run": _text(winner.get("_compare_run")),
        }
    return best


def _pairing_candidates(sidecar_rows: list[dict[str, Any]], target_notional_usd: float) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sidecar_rows:
        if _text(row.get("status")).lower() != "closed":
            continue
        family = _family(row)
        if not family:
            continue
        grouped[(family, _exit_shape(row))].append(row)

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (family, exit_shape), rows in grouped.items():
        summary = _summarize_rows(rows, target_notional_usd)
        sample = sorted(rows, key=lambda row: _net_pnl_10k(row, target_notional_usd), reverse=True)[0]
        net = _float(summary["net_pnl_usd_at_target_notional"])
        closed = int(summary["closed"])
        avg = net / max(1, closed)
        variant = _extract_exit_variant_id(sample)
        by_family[family].append({
            "id": _candidate_id(family, variant, exit_shape),
            "role": "sidecar_live_candidate",
            "label": f"{family} x sidecar {variant or 'exit_shape'}",
            "shadow_enabled": True,
            "execution_enabled": False,
            "exit_variant_id": variant,
            "exit_shape": exit_shape,
            **_exit_config_from_row(sample),
            "evidence": {
                "source": "live_family_registry_compare",
                "source_run": _text(sample.get("_compare_run")),
                "target_notional_usd": target_notional_usd,
                "closed_trades": closed,
                "wins": int(summary["wins"]),
                "losses": int(summary["losses"]),
                "win_rate": summary["win_rate"],
                "net_pnl_usd_at_target_notional": summary["net_pnl_usd_at_target_notional"],
                "gross_pnl_usd_at_target_notional": summary["gross_pnl_usd_at_target_notional"],
                "fees_usd_at_target_notional": summary["fees_usd_at_target_notional"],
                "avg_net_pnl_usd_at_target_notional": round(avg, 6),
                "route_examples": Counter(_route_key(row) for row in rows).most_common(5),
            },
        })

    out: dict[str, list[dict[str, Any]]] = {}
    for family, candidates in by_family.items():
        candidates.sort(
            key=lambda row: (
                _float(((row.get("evidence") or {}).get("net_pnl_usd_at_target_notional"))),
                _float(((row.get("evidence") or {}).get("avg_net_pnl_usd_at_target_notional"))),
                int(((row.get("evidence") or {}).get("closed_trades") or 0)),
            ),
            reverse=True,
        )
        out[family] = candidates[:5]
    return dict(sorted(out.items()))


def _restatement_rows(
    main_rows: list[dict[str, Any]],
    best_by_entry: dict[str, dict[str, Any]],
    counterfactuals_by_cell: dict[str, dict[str, Any]],
    target_notional_usd: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in main_rows:
        status = _text(trade.get("status")).lower()
        actual_net = _net_pnl_10k(trade, target_notional_usd)
        match = best_by_entry.get(_entry_key(trade, include_family=True))
        best = match.get("best_row") if match else None
        cell_id = _text(trade.get("cell_id")) or _entry_key(trade, include_family=True)
        cf = counterfactuals_by_cell.get(cell_id) or {}
        best_exec = cf.get("best_executable") or {}
        best_runtime_exec = cf.get("best_runtime_executable") or {}
        best_any = cf.get("best_any_oracle") or {}
        rt_ledger = trade.get("rt_executable_exit_ledger") if isinstance(trade.get("rt_executable_exit_ledger"), dict) else {}
        rt_best = rt_ledger.get("best_closed_executable") if isinstance(rt_ledger.get("best_closed_executable"), dict) else {}
        memory_traits = _memory_trait_values(trade)
        rows.append({
            "cell_id": cell_id,
            "asset": _asset(trade),
            "venue": _venue_label(trade),
            "side": _side(trade),
            "entry_ts_utc": _entry_ts(trade),
            "status": status,
            "family": _family(trade),
            **memory_traits,
            "mock_scenario_id": _text(trade.get("mock_scenario_id")),
            "policy_epoch_id": _text(trade.get("policy_epoch_id")),
            "opened_wall_utc": _float(trade.get("opened_wall_utc")),
            "state_account_id": _text(trade.get("_state_account_id")),
            "state_section": _text(trade.get("_state_section")),
            "runtime_exit_strategy_id": _text(trade.get("exit_strategy_id")),
            "runtime_close_reason": _text(trade.get("runner_exit_reason") or trade.get("close_reason")),
            "runtime_notional_usd": round(_notional(trade), 6),
            "runtime_net_pnl_usd": round(_net_pnl(trade), 6),
            "runtime_net_pnl_usd_at_target_notional": round(actual_net, 6),
            "rt_ledger_memory_selected_id": _text(rt_ledger.get("memory_selected_counterfactual_id")) if rt_ledger else "",
            "rt_ledger_closed_candidate_count": int(rt_ledger.get("closed_candidate_count") or 0) if rt_ledger else 0,
            "rt_ledger_open_candidate_count": int(rt_ledger.get("open_candidate_count") or 0) if rt_ledger else 0,
            "rt_ledger_best_executable_id": _text(rt_best.get("candidate_id")) if rt_best else "",
            "rt_ledger_best_executable_net_pnl_usd_at_target_notional": rt_best.get("net_pnl_usd_at_target_notional") if rt_best else None,
            "rt_ledger_best_executable_incremental_vs_runtime_usd_at_target_notional": (
                round(_float(rt_best.get("net_pnl_usd_at_target_notional")) - actual_net, 6) if rt_best else None
            ),
            "sidecar_match": bool(best),
            "sidecar_variant_count": int((match or {}).get("variant_count") or 0),
            "sidecar_best_net_pnl_usd_at_target_notional": round(_net_pnl_10k(best, target_notional_usd), 6) if best else None,
            "sidecar_best_incremental_vs_runtime_usd_at_target_notional": (
                round(_net_pnl_10k(best, target_notional_usd) - actual_net, 6) if best else None
            ),
            "sidecar_best_exit_variant_id": _extract_exit_variant_id(best) if best else "",
            "sidecar_best_exit_shape": _exit_shape(best) if best else "",
            "sidecar_best_mock_scenario_id": _text(best.get("mock_scenario_id")) if best else "",
            "sidecar_best_run": _text(best.get("_compare_run")) if best else "",
            "cf_candidate_count": int(cf.get("candidate_count") or 0),
            "cf_best_executable_id": _text(best_exec.get("candidate_id")),
            "cf_best_executable_net_pnl_usd_at_target_notional": best_exec.get("net_pnl_usd_at_target_notional"),
            "cf_best_executable_incremental_vs_runtime_usd_at_target_notional": (
                round(_float(best_exec.get("net_pnl_usd_at_target_notional")) - actual_net, 6) if best_exec else None
            ),
            "cf_best_runtime_executable_id": _text(best_runtime_exec.get("candidate_id")),
            "cf_best_runtime_executable_net_pnl_usd_at_target_notional": best_runtime_exec.get("net_pnl_usd_at_target_notional"),
            "cf_best_runtime_executable_incremental_vs_runtime_usd_at_target_notional": (
                round(_float(best_runtime_exec.get("net_pnl_usd_at_target_notional")) - actual_net, 6)
                if best_runtime_exec else None
            ),
            "cf_best_any_oracle_id": _text(best_any.get("candidate_id")),
            "cf_best_any_oracle_net_pnl_usd_at_target_notional": best_any.get("net_pnl_usd_at_target_notional"),
            "cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional": (
                round(_float(best_any.get("net_pnl_usd_at_target_notional")) - actual_net, 6) if best_any else None
            ),
        })
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "cell_id",
        "asset",
        "venue",
        "side",
        "entry_ts_utc",
        "status",
        "family",
        "bucket_session",
        "trade_stage",
        "trade_score_band",
        "trade_from_onset_bps",
        "trade_current_chunk_bps",
        "trade_recent_2chunk_bps",
        "onset_move_band",
        "current_chunk_band",
        "recent_2chunk_band",
        "pressure_relation",
        "move_shape_category",
        "mock_scenario_id",
        "policy_epoch_id",
        "opened_wall_utc",
        "state_account_id",
        "state_section",
        "runtime_exit_strategy_id",
        "runtime_close_reason",
        "runtime_notional_usd",
        "runtime_net_pnl_usd",
        "runtime_net_pnl_usd_at_target_notional",
        "rt_ledger_memory_selected_id",
        "rt_ledger_closed_candidate_count",
        "rt_ledger_open_candidate_count",
        "rt_ledger_best_executable_id",
        "rt_ledger_best_executable_net_pnl_usd_at_target_notional",
        "rt_ledger_best_executable_incremental_vs_runtime_usd_at_target_notional",
        "sidecar_match",
        "sidecar_variant_count",
        "sidecar_best_net_pnl_usd_at_target_notional",
        "sidecar_best_incremental_vs_runtime_usd_at_target_notional",
        "sidecar_best_exit_variant_id",
        "sidecar_best_mock_scenario_id",
        "sidecar_best_run",
        "sidecar_best_exit_shape",
        "cf_candidate_count",
        "cf_best_executable_id",
        "cf_best_executable_net_pnl_usd_at_target_notional",
        "cf_best_executable_incremental_vs_runtime_usd_at_target_notional",
        "cf_best_runtime_executable_id",
        "cf_best_runtime_executable_net_pnl_usd_at_target_notional",
        "cf_best_runtime_executable_incremental_vs_runtime_usd_at_target_notional",
        "cf_best_any_oracle_id",
        "cf_best_any_oracle_net_pnl_usd_at_target_notional",
        "cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _update_pairings(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    payload = _read_json(path)
    if not payload:
        payload = {"schema": "family_exit_pairings_v1", "families": {}}
    payload.setdefault("schema", "family_exit_pairings_v1")
    payload["updated_at"] = _now_iso()
    policy = payload.setdefault("policy", {})
    policy["sidecar_restatement_report"] = str(report["sources"]["out_json"])
    policy["sidecar_restatement_target_notional_usd"] = report["target_notional_usd"]
    policy["sidecar_pairing_update_rule"] = (
        "Sidecar candidates populate live evidence and shadow candidate exits. "
        "Execution remains controlled by active_candidate_id plus execution_enabled."
    )
    families = payload.setdefault("families", {})
    for family, candidates in (report.get("sidecar_pairing_candidates") or {}).items():
        family_cfg = families.setdefault(family, {
            "status": "sidecar_candidate_only",
            "active_candidate_id": "",
            "candidate_exits": [],
        })
        existing = {
            _text(candidate.get("id")): candidate
            for candidate in family_cfg.get("candidate_exits") or []
            if isinstance(candidate, dict)
        }
        top_candidates = []
        for candidate in candidates[:3]:
            candidate_id = _text(candidate.get("id"))
            if not candidate_id:
                continue
            merged = dict(existing.get(candidate_id) or {})
            merged.update(candidate)
            merged["execution_enabled"] = bool(existing.get(candidate_id, {}).get("execution_enabled", False))
            existing[candidate_id] = merged
            top_candidates.append({
                "id": candidate_id,
                "exit_variant_id": candidate.get("exit_variant_id"),
                "evidence": candidate.get("evidence") or {},
            })
        untouched = [
            candidate for candidate in family_cfg.get("candidate_exits") or []
            if isinstance(candidate, dict) and _text(candidate.get("id")) not in existing
        ]
        ordered_existing = sorted(
            existing.values(),
            key=lambda row: _float((((row.get("evidence") or {}).get("net_pnl_usd_at_target_notional")))),
            reverse=True,
        )
        family_cfg["candidate_exits"] = untouched + ordered_existing
        family_cfg["sidecar_live_evidence"] = {
            "updated_at": report["created_at"],
            "target_notional_usd": report["target_notional_usd"],
            "source_report": str(report["sources"]["out_json"]),
            "top_candidates": top_candidates,
        }
    _write_json(path, payload)
    return payload


def _render_md(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    summary = report["summary"]
    lines = [
        "# Live Sidecar Exit Restatement",
        "",
        f"Created: {report['created_at']}",
        f"Window start UTC: `{report['window_start_utc_iso']}`",
        f"Effective clean-epoch start UTC: `{report['effective_window_start_utc_iso']}`",
        f"Active policy epoch: `{report.get('active_policy_epoch_id') or ''}`",
        f"Target notional: `${report['target_notional_usd']:,.2f}`",
        "",
        "## Summary",
        "",
        f"- Main trades in window: {summary['main_trades']}",
        f"- Main closed trades: {summary['main_closed_trades']}",
        f"- Runtime net PnL at target notional: `${summary['runtime_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Sidecar-matched main trades: {summary['sidecar_matched_main_trades']}",
        f"- Matched runtime net PnL at target notional: `${summary['matched_runtime_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Matched sidecar-best net PnL at target notional: `${summary['matched_sidecar_best_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Matched sidecar incremental: `${summary['matched_sidecar_incremental_usd_at_target_notional']:+,.2f}`",
        f"- Sidecar canonical entries with closed variants: {summary['sidecar_closed_entry_groups']}",
        f"- Sum of best sidecar variant per canonical entry: `${summary['sidecar_best_per_entry_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Main trades with counterfactual exits: {summary['counterfactual_trade_count']}",
        f"- Best executable counterfactual net PnL at target notional: `${summary['counterfactual_best_executable_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Best executable incremental: `${summary['counterfactual_best_executable_incremental_usd_at_target_notional']:+,.2f}`",
        f"- Best runtime-selector executable ({report['runtime_selector_allowed_horizons_minutes']} min) net PnL at target notional: `${summary['counterfactual_best_runtime_executable_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Best runtime-selector executable incremental: `${summary['counterfactual_best_runtime_executable_incremental_usd_at_target_notional']:+,.2f}`",
        f"- Best any/oracle counterfactual net PnL at target notional: `${summary['counterfactual_best_any_oracle_net_pnl_usd_at_target_notional']:+,.2f}`",
        f"- Best any/oracle incremental: `${summary['counterfactual_best_any_oracle_incremental_usd_at_target_notional']:+,.2f}`",
        "",
        "## Best Family Pairing Candidates",
        "",
        "| Family | Candidate | Closed | Win rate | Net at target | Avg/trade | Source run |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for family, candidates in (report.get("sidecar_pairing_candidates") or {}).items():
        for candidate in candidates[:3]:
            ev = candidate.get("evidence") or {}
            win_rate = ev.get("win_rate")
            win_text = "" if win_rate is None else f"{float(win_rate):.1%}"
            lines.append(
                f"| `{family}` | `{candidate.get('id')}` | {ev.get('closed_trades', 0)} | "
                f"{win_text} | `${_float(ev.get('net_pnl_usd_at_target_notional')):+,.2f}` | "
                f"`${_float(ev.get('avg_net_pnl_usd_at_target_notional')):+,.2f}` | "
                f"`{ev.get('source_run') or ''}` |"
            )
    lines.extend([
        "",
        "## Top Matched Main Trade Restatements",
        "",
        "| Trade | Runtime at target | Sidecar best | Incremental | Best variant |",
        "|---|---:|---:|---:|---|",
    ])
    matched = [
        row for row in rows
        if row.get("sidecar_match")
        and row.get("sidecar_best_incremental_vs_runtime_usd_at_target_notional") is not None
    ]
    matched.sort(key=lambda row: _float(row.get("sidecar_best_incremental_vs_runtime_usd_at_target_notional")), reverse=True)
    for row in matched[:20]:
        trade_label = "|".join([
            _text(row.get("asset")),
            _text(row.get("venue")),
            _text(row.get("side")),
            _text(row.get("family")),
            str(int(_float(row.get("entry_ts_utc")))),
        ]).replace("|", "\\|")
        lines.append(
            f"| `{trade_label}` | `${_float(row.get('runtime_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('sidecar_best_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('sidecar_best_incremental_vs_runtime_usd_at_target_notional')):+,.2f}` | "
            f"`{row.get('sidecar_best_exit_variant_id') or row.get('sidecar_best_mock_scenario_id')}` |"
        )
    lines.extend([
        "",
        "## Top Counterfactual Restatements",
        "",
        "| Trade | Runtime at target | Best runtime executable | Runtime incremental | Best executable | Best any/oracle | Oracle incremental |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    cf_rows = [
        row for row in rows
        if row.get("cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional") is not None
    ]
    cf_rows.sort(key=lambda row: _float(row.get("cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional")), reverse=True)
    for row in cf_rows[:20]:
        trade_label = "|".join([
            _text(row.get("asset")),
            _text(row.get("venue")),
            _text(row.get("side")),
            _text(row.get("family")),
            str(int(_float(row.get("entry_ts_utc")))),
        ]).replace("|", "\\|")
        lines.append(
            f"| `{trade_label}` | `${_float(row.get('runtime_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('cf_best_runtime_executable_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('cf_best_runtime_executable_incremental_vs_runtime_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('cf_best_executable_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('cf_best_any_oracle_net_pnl_usd_at_target_notional')):+,.2f}` | "
            f"`${_float(row.get('cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional')):+,.2f}` |"
        )
    lines.append("")
    return "\n".join(lines)


def build_restatement(
    *,
    main_trade_log: Path,
    state_path: Path,
    compare_root: Path,
    data_dir: Path,
    pairings_path: Path,
    out_json: Path,
    out_md: Path,
    out_csv: Path,
    out_policy_csv: Path,
    start_utc: float,
    compare_run_limit: int,
    target_notional_usd: float,
    update_pairings: bool,
) -> dict[str, Any]:
    state = _read_json(state_path)
    active_epoch = state.get("active_policy_epoch") if isinstance(state.get("active_policy_epoch"), dict) else {}
    active_epoch_id = _text(active_epoch.get("policy_epoch_id"))
    active_epoch_start = _float(active_epoch.get("policy_epoch_started_wall_utc"))
    effective_start_utc = max(float(start_utc), active_epoch_start) if active_epoch_start > 0 else float(start_utc)
    main_source_rows = _merge_trade_rows(_read_jsonl(main_trade_log), _read_state_trades(state_path, state=state))
    main_rows = [
        row for row in main_source_rows
        if _row_time(row) >= effective_start_utc
        and (
            not active_epoch_id
            or not _text(row.get("policy_epoch_id"))
            or _text(row.get("policy_epoch_id")) == active_epoch_id
        )
    ]
    policy_source_rows = _merge_trade_rows(
        _read_jsonl(main_trade_log),
        _read_state_trades(state_path, state=state, include_retired=True),
    )
    # Keep the executable oracle-memory source durable across clean epoch
    # restarts. The active scorecard above is windowed; this policy source is
    # intentionally all available solved rows so RT can match new trades to
    # prior oracle-labeled executable templates.
    policy_rows = list(policy_source_rows)
    compare_runs = _compare_runs(compare_root, start_utc, compare_run_limit)
    sidecar_rows: list[dict[str, Any]] = []
    for run in compare_runs:
        for row in _read_jsonl(run / "family_registry_trades.jsonl"):
            if _row_time(row) < start_utc:
                continue
            row["_compare_run"] = run.name
            sidecar_rows.append(row)

    bars_by_market = _load_market_bars(data_dir)
    best_by_entry = _best_sidecar_by_entry(sidecar_rows, target_notional_usd)
    counterfactuals_by_cell = _best_counterfactuals(main_rows, bars_by_market, target_notional_usd)
    restated_rows = _restatement_rows(main_rows, best_by_entry, counterfactuals_by_cell, target_notional_usd)
    policy_counterfactuals_by_cell = _best_counterfactuals(policy_rows, bars_by_market, target_notional_usd)
    policy_restated_rows = _restatement_rows(
        policy_rows,
        best_by_entry,
        policy_counterfactuals_by_cell,
        target_notional_usd,
    )
    pairing_candidates = _pairing_candidates(sidecar_rows, target_notional_usd)

    matched = [row for row in restated_rows if row.get("sidecar_match")]
    sidecar_best_total = sum(_float(item.get("best_net_pnl_usd_at_target_notional")) for item in best_by_entry.values())
    cf_rows = [row for row in restated_rows if row.get("cf_best_executable_net_pnl_usd_at_target_notional") is not None]
    cf_runtime_rows = [
        row for row in restated_rows
        if row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional") is not None
    ]
    cf_best_executable_total = sum(_float(row.get("cf_best_executable_net_pnl_usd_at_target_notional")) for row in cf_rows)
    cf_best_runtime_executable_total = sum(
        _float(row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional"))
        for row in cf_runtime_rows
    )
    cf_best_any_total = sum(_float(row.get("cf_best_any_oracle_net_pnl_usd_at_target_notional")) for row in cf_rows)
    cf_runtime_total = sum(_float(row.get("runtime_net_pnl_usd_at_target_notional")) for row in cf_rows)
    cf_runtime_selector_total = sum(
        _float(row.get("runtime_net_pnl_usd_at_target_notional"))
        for row in cf_runtime_rows
    )
    report = {
        "schema": "live_sidecar_exit_restatement_v1",
        "created_at": _now_iso(),
        "window_start_utc": start_utc,
        "window_start_utc_iso": datetime.fromtimestamp(start_utc, timezone.utc).isoformat().replace("+00:00", "Z"),
        "effective_window_start_utc": effective_start_utc,
        "effective_window_start_utc_iso": datetime.fromtimestamp(effective_start_utc, timezone.utc).isoformat().replace("+00:00", "Z"),
        "active_policy_epoch_id": active_epoch_id,
        "runtime_selector_allowed_horizons_minutes": list(RUNTIME_SELECTOR_HORIZONS_MINUTES),
        "target_notional_usd": float(target_notional_usd),
        "sources": {
            "main_trade_log": str(main_trade_log),
            "state_path": str(state_path),
            "compare_root": str(compare_root),
            "data_dir": str(data_dir),
            "compare_runs": [str(path) for path in compare_runs],
            "pairings_path": str(pairings_path),
            "out_json": str(out_json),
            "out_md": str(out_md),
            "out_csv": str(out_csv),
            "out_policy_csv": str(out_policy_csv),
        },
        "summary": {
            "main_trades": len(main_rows),
            "main_closed_trades": sum(1 for row in main_rows if _text(row.get("status")).lower() == "closed"),
            "runtime_net_pnl_usd_at_target_notional": round(sum(_net_pnl_10k(row, target_notional_usd) for row in main_rows if _text(row.get("status")).lower() == "closed"), 6),
            "sidecar_runs": len(compare_runs),
            "sidecar_trades": len(sidecar_rows),
            "sidecar_closed_trades": sum(1 for row in sidecar_rows if _text(row.get("status")).lower() == "closed"),
            "sidecar_closed_entry_groups": len(best_by_entry),
            "sidecar_best_per_entry_net_pnl_usd_at_target_notional": round(sidecar_best_total, 6),
            "sidecar_matched_main_trades": len(matched),
            "matched_runtime_net_pnl_usd_at_target_notional": round(sum(_float(row.get("runtime_net_pnl_usd_at_target_notional")) for row in matched), 6),
            "matched_sidecar_best_net_pnl_usd_at_target_notional": round(sum(_float(row.get("sidecar_best_net_pnl_usd_at_target_notional")) for row in matched), 6),
            "matched_sidecar_incremental_usd_at_target_notional": round(sum(_float(row.get("sidecar_best_incremental_vs_runtime_usd_at_target_notional")) for row in matched), 6),
            "counterfactual_trade_count": len(cf_rows),
            "counterfactual_runtime_net_pnl_usd_at_target_notional": round(cf_runtime_total, 6),
            "counterfactual_best_executable_net_pnl_usd_at_target_notional": round(cf_best_executable_total, 6),
            "counterfactual_best_executable_incremental_usd_at_target_notional": round(cf_best_executable_total - cf_runtime_total, 6),
            "counterfactual_best_runtime_executable_net_pnl_usd_at_target_notional": round(cf_best_runtime_executable_total, 6),
            "counterfactual_best_runtime_executable_incremental_usd_at_target_notional": round(
                cf_best_runtime_executable_total - cf_runtime_selector_total,
                6,
            ),
            "counterfactual_best_any_oracle_net_pnl_usd_at_target_notional": round(cf_best_any_total, 6),
            "counterfactual_best_any_oracle_incremental_usd_at_target_notional": round(cf_best_any_total - cf_runtime_total, 6),
            "main_trade_families": Counter(_family(row) for row in main_rows).most_common(),
            "policy_source_trades": len(policy_rows),
            "policy_source_closed_trades": sum(1 for row in policy_rows if _text(row.get("status")).lower() == "closed"),
            "policy_source_counterfactual_trade_count": sum(
                1 for row in policy_restated_rows
                if row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional") is not None
            ),
            "sidecar_trade_families": Counter(_family(row) for row in sidecar_rows).most_common(),
        },
        "sidecar_pairing_candidates": pairing_candidates,
        "main_trade_rows_csv": str(out_csv),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(out_csv, restated_rows)
    _write_csv(out_policy_csv, policy_restated_rows)
    _write_json(out_json, report)
    out_md.write_text(_render_md(report, restated_rows), encoding="utf-8")
    if update_pairings:
        _update_pairings(pairings_path, report)
        report["pairings_updated"] = True
        _write_json(out_json, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-trade-log", default=str(DEFAULT_MAIN_TRADE_LOG))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--compare-root", default=str(DEFAULT_COMPARE_ROOT))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--pairings-path", default=str(DEFAULT_PAIRINGS_PATH))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-policy-csv", default=str(DEFAULT_POLICY_CSV))
    parser.add_argument("--start-utc", type=float, default=_default_start_utc())
    parser.add_argument("--compare-run-limit", type=int, default=32)
    parser.add_argument("--target-notional-usd", type=float, default=TARGET_NOTIONAL_USD)
    parser.add_argument("--update-pairings", action="store_true")
    args = parser.parse_args()
    report = build_restatement(
        main_trade_log=Path(args.main_trade_log),
        state_path=Path(args.state_path),
        compare_root=Path(args.compare_root),
        data_dir=Path(args.data_dir),
        pairings_path=Path(args.pairings_path),
        out_json=Path(args.out_json),
        out_md=Path(args.out_md),
        out_csv=Path(args.out_csv),
        out_policy_csv=Path(args.out_policy_csv),
        start_utc=float(args.start_utc),
        compare_run_limit=int(args.compare_run_limit),
        target_notional_usd=float(args.target_notional_usd),
        update_pairings=bool(args.update_pairings),
    )
    print(json.dumps({
        "schema": report["schema"],
        "created_at": report["created_at"],
        "summary": report["summary"],
        "outputs": report["sources"],
        "pairings_updated": bool(report.get("pairings_updated")),
    }, indent=2))


if __name__ == "__main__":
    main()
