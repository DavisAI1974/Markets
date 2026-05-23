from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_ORACLE_WINNER_LIST_PATH = REPO_ROOT / "research" / "strategy_evolution" / "oracle_winner_trade_list.json"

_CACHE: dict[str, Any] = {"cache_key": "", "payload": {}}
STRICT_RUNTIME_MATCH_LEVELS = ("entry",)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _get(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _score_band(row: Any) -> str:
    existing = _text(_get(row, "trade_score_band"))
    if existing:
        return existing
    score = _int(_get(row, "trade_present_score"))
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


def _band_bps(value: Any) -> str:
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


def _band_signed(value: Any, threshold: float) -> str:
    x = _float(value)
    if x >= threshold:
        return "buy"
    if x <= -threshold:
        return "sell"
    return "neutral"


def _news_state(row: Any) -> str:
    return "none"


def _side(row: Any, side: str = "") -> str:
    return _lower(side or _get(row, "side") or _get(row, "trade_option_side") or _get(row, "pressure_watch_direction"))


def _strategy(row: Any) -> str:
    return _upper(_get(row, "trade_strategy_id") or _get(row, "strategy_id") or _get(row, "entry_strategy_id"))


def _asset(row: Any) -> str:
    return _upper(_get(row, "asset"))


def _venue(row: Any) -> str:
    return _lower(_get(row, "venue"))


def _session(row: Any) -> str:
    return _lower(_get(row, "bucket_session"))


def _token(*parts: Any) -> str:
    return "|".join(_text(part) for part in parts)


def oracle_winner_canonical_trade_key(row: Any) -> str:
    return _token(
        _strategy(row),
        _asset(row),
        _side(row),
        _lower(_get(row, "trade_stage")) or "none",
        _lower(_get(row, "trade_option_state")) or "none",
        _score_band(row),
        _lower(_get(row, "pressure_watch_state")) or "none",
        _text(_get(row, "current_chunk_band")) or _band_bps(_get(row, "trade_current_chunk_bps")),
        _text(_get(row, "recent_2chunk_band")) or _band_bps(_get(row, "trade_recent_2chunk_bps")),
        _text(_get(row, "onset_move_band")) or _band_bps(_get(row, "trade_from_onset_bps")),
        _band_signed(_get(row, "mean_dipole"), 0.25),
        _band_signed(_get(row, "dipole_acl1"), 0.25),
        _band_signed(_get(row, "volume_zscore"), 1.0),
        _news_state(row),
    )


def oracle_winner_route_keys(row: Any, side: str = "") -> list[tuple[str, str]]:
    side_value = _side(row, side)
    strategy = _strategy(row)
    asset = _asset(row)
    venue = _venue(row)
    session = _session(row)
    stage = _lower(_get(row, "trade_stage")) or "none"
    option_state = _lower(_get(row, "trade_option_state")) or "none"
    pressure_state = _lower(_get(row, "pressure_watch_state")) or "none"
    score = _score_band(row)
    move = _text(_get(row, "current_chunk_band")) or _band_bps(_get(row, "trade_current_chunk_bps"))
    recent2 = _text(_get(row, "recent_2chunk_band")) or _band_bps(_get(row, "trade_recent_2chunk_bps"))
    onset = _text(_get(row, "onset_move_band")) or _band_bps(_get(row, "trade_from_onset_bps"))
    dipole = _band_signed(_get(row, "mean_dipole"), 0.25)
    acl1 = _band_signed(_get(row, "dipole_acl1"), 0.25)
    vol = _band_signed(_get(row, "volume_zscore"), 1.0)
    news = _news_state(row)
    base = [strategy, asset, venue, side_value]
    return [
        (
            "trait",
            _token("trait", *base, session, stage, option_state, score, pressure_state, move, recent2, onset, dipole, acl1, vol, news),
        ),
        (
            "shape",
            _token("shape", *base, session, stage, score, pressure_state, move, recent2, onset),
        ),
        ("context", _token("context", *base, session)),
        ("route", _token("route", *base)),
    ]


def load_oracle_winner_list(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_ORACLE_WINNER_LIST_PATH
    try:
        stat = source.stat()
    except OSError:
        return {}
    cache_key = f"{source}:{stat.st_mtime_ns}:{stat.st_size}"
    if _CACHE.get("cache_key") == cache_key:
        return dict(_CACHE.get("payload") or {})
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    _CACHE["cache_key"] = cache_key
    _CACHE["payload"] = payload
    return dict(payload)


def _entry_match_from_payload(row: Any, payload: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    canonical_key = oracle_winner_canonical_trade_key(row)
    if not canonical_key:
        return {}
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        return {}
    winner_entry: dict[str, Any] | None = None
    for entry in entries:
        if isinstance(entry, dict) and _text(entry.get("canonical_trade_key")) == canonical_key:
            winner_entry = entry
            break
    if not winner_entry:
        return {}
    exit_id = _text(winner_entry.get("runtime_exit_id"))
    if not exit_id:
        return {}
    net_bps = _float(winner_entry.get("net_bps"))
    net_pnl = _float(winner_entry.get("net_pnl_usd"))
    selected = {
        "runtime_exit_id": exit_id,
        "runtime_exit_class": _text(winner_entry.get("runtime_exit_class")),
        "horizon_minutes": _int(winner_entry.get("horizon_minutes")),
        "count": 1,
        "total_net_pnl_usd": net_pnl,
        "total_net_bps": net_bps,
        "avg_net_pnl_usd": net_pnl,
        "avg_net_bps": net_bps,
        "best_net_bps": net_bps,
    }
    return {
        "schema": "oracle_winner_trade_match_v1",
        "source_path": str(payload.get("output_path") or payload.get("source_path") or (Path(path) if path else DEFAULT_ORACLE_WINNER_LIST_PATH)),
        "list_created_at": payload.get("created_at"),
        "match_level": "entry",
        "match_key": canonical_key,
        "canonical_trade_key": canonical_key,
        "oracle_winner_count": 1,
        "avg_net_bps": net_bps,
        "total_net_pnl_usd": net_pnl,
        "best_net_bps": net_bps,
        "selected_exit": selected,
        "top_exits": [selected],
        "examples": [{
            "source": winner_entry.get("source"),
            "source_id": winner_entry.get("source_id"),
            "entry_ts_utc": winner_entry.get("entry_ts_utc"),
            "net_bps": winner_entry.get("net_bps"),
            "runtime_exit_id": winner_entry.get("runtime_exit_id"),
            "canonical_trade_key": canonical_key,
        }],
        "entry": dict(winner_entry),
    }


def match_oracle_winner(row: Any, scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario = scenario or {}
    path = scenario.get("oracle_winner_list_path") or None
    payload = load_oracle_winner_list(path)
    exact_entry_required = bool(
        scenario.get("oracle_winner_exact_entry_required")
        or scenario.get("oracle_winner_proven_entries_only")
    )
    if exact_entry_required:
        return _entry_match_from_payload(row, payload, path)
    indices = payload.get("indices") or {}
    if not isinstance(indices, dict) or not indices:
        return {}
    levels_raw = scenario.get("oracle_winner_match_levels") or list(STRICT_RUNTIME_MATCH_LEVELS)
    levels = [str(level).strip() for level in levels_raw if str(level).strip()] if isinstance(levels_raw, (list, tuple)) else list(STRICT_RUNTIME_MATCH_LEVELS)
    if "entry" in levels:
        exact = _entry_match_from_payload(row, payload, path)
        if exact:
            return exact
    min_count = max(1, _int(scenario.get("oracle_winner_min_count"), 1))
    min_avg_net_bps = _float(scenario.get("oracle_winner_min_avg_net_bps"), 0.0)
    keys = oracle_winner_route_keys(row)
    for level, key in keys:
        if level not in levels:
            continue
        level_index = indices.get(level) or {}
        if not isinstance(level_index, dict):
            continue
        group = level_index.get(key)
        if not isinstance(group, dict):
            continue
        if _int(group.get("count")) < min_count:
            continue
        if _float(group.get("avg_net_bps")) < min_avg_net_bps:
            continue
        selected = group.get("selected_exit") if isinstance(group.get("selected_exit"), dict) else {}
        if not selected:
            continue
        return {
            "schema": "oracle_winner_trade_match_v1",
            "source_path": str(payload.get("output_path") or payload.get("source_path") or (Path(path) if path else DEFAULT_ORACLE_WINNER_LIST_PATH)),
            "list_created_at": payload.get("created_at"),
            "match_level": level,
            "match_key": key,
            "oracle_winner_count": _int(group.get("count")),
            "avg_net_bps": _float(group.get("avg_net_bps")),
            "total_net_pnl_usd": _float(group.get("total_net_pnl_usd")),
            "best_net_bps": _float(group.get("best_net_bps")),
            "selected_exit": dict(selected),
            "top_exits": list(group.get("top_exits") or [])[:8],
            "examples": list(group.get("examples") or [])[:8],
        }
    return {}


def exit_selection_from_match(match: dict[str, Any], scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(match, dict) or not match:
        return {}
    selected = match.get("selected_exit")
    if not isinstance(selected, dict):
        return {}
    exit_id = _text(selected.get("runtime_exit_id") or selected.get("id"))
    if not exit_id:
        return {}
    horizon = _int(selected.get("horizon_minutes"))
    selected_class = _text(selected.get("runtime_exit_class"))
    if not selected_class:
        if exit_id.startswith("fixed_hold_") and "_after_" in exit_id:
            start = exit_id.split("m_after_", 1)[1] if "m_after_" in exit_id else ""
            selected_class = "fixed_hold_after_entry" if start == "entry" else "fixed_hold_after_runtime_exit"
        elif exit_id.startswith("actual_exit::"):
            selected_class = "actual_exit"
        else:
            selected_class = "oracle_memory_exit"
    selection = {
        "schema": "runtime_counterfactual_exit_selection_v1",
        "source_scope": "oracle_winner_source_of_truth",
        "source_path": match.get("source_path"),
        "selection_level": match.get("match_level"),
        "selection_key": match.get("match_key"),
        "selected_counterfactual_id": exit_id,
        "selected_counterfactual_class": selected_class,
        "fixed_hold_minutes": horizon,
        "sample_count": _int(match.get("oracle_winner_count")),
        "counterfactual_net_usd_at_target_notional": _float(selected.get("avg_net_pnl_usd")),
        "counterfactual_win_rate": 1.0,
        "oracle_winner_match": {
            "match_level": match.get("match_level"),
            "match_key": match.get("match_key"),
            "oracle_winner_count": _int(match.get("oracle_winner_count")),
            "avg_net_bps": _float(match.get("avg_net_bps")),
        },
    }
    if selected_class == "fixed_hold_after_entry":
        selection["fixed_hold_start"] = "entry"
    elif selected_class == "fixed_hold_after_runtime_exit":
        selection["fixed_hold_start"] = "runtime_exit"
    return selection
