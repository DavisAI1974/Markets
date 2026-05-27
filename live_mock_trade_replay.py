from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import trade_exit_strategy
import oracle_winner_trade_memory
from backend.api_server import _load_mock_trade_settings
from mock_trade_replay import (
    OPEN_DEBUG,
    VENUES,
    account_daily_limit_blocker,
    bank_equity_for,
    bank_realized_pnl_for_trade,
    close_trade,
    close_open_for_status,
    current_status_from_visible,
    maybe_open,
    reset_strategy_debug,
    scenario_blocker,
    session_from_offset_hours,
    stamp_runtime_counterfactual_exit_selection,
    write_replay_outputs,
)
from phase1_5_evaluator import load_bars


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_EXIT_PARAMS = REPO_ROOT / "research" / "strategy_evolution" / "exit_params_h0_h168_v2_promoted_min5.json"
DEFAULT_OUT = REPO_ROOT / "research" / "strategy_evolution" / "live_mock_replay"
OPPORTUNITY_LOG = REPO_ROOT / "research" / "strategy_evolution" / "_live_mock_opportunities.jsonl"
TRADE_SNAPSHOT = REPO_ROOT / "research" / "strategy_evolution" / "_live_replay_mock_trades.jsonl"
LIVE_GUARD_MIN_CLOSED_BY_SIDE = 30
LIVE_GUARD_MAX_WIN_RATE = 0.45
LIVE_GUARD_MAX_PNL_USD = 0.0
ORACLE_POLICY_EPOCH_VERSION = "oracle_runtime_answer_backed_v6_quality_gated"
POSITION_MANAGER_VERSION = "best_answer_backed_position_v1"
ROTATION_CLOSE_REASON = "rotation_to_better_answer_backed_position"
BANK_ALLOCATION_VERSION = "per_venue_full_bank_slots_v1"
BANK_ALLOCATION_MODEL = "one_full_venue_bank_trade_when_free"
BANK_ALLOCATION_TARGET_SLOTS = 1
LIVE_EXECUTION_VENUES = ("Coinbase", "Kraken", "Bybit")
BANK_ALLOCATION_LEADER_70_SCORE_LEAD = 20.0
BANK_ALLOCATION_LEADER_85_SCORE_LEAD = 35.0
BANK_ALLOCATION_LEADER_85_MIN_NET_BPS = 5.0
ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS_PER_MIN = 0.30
ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS = 15.0
ORACLE_WINNER_MIN_BANK_ENTRY_HORIZON_MINUTES = 5.0
HISTORIC_PARITY_FAMILIES = [
    "MEAN_REVERSION_CHOP",
    "NEWS_BREAKOUT",
    "LIQUIDITY_SQUEEZE",
    "VOL_BREAKOUT",
    "BASIS_DISLOCATION",
    "RELATIVE_STRENGTH",
]
EVOLVE_LIVE_FAMILIES = [
    "SMALL_MOVE_FADE",
    "BUY_UP_CONTINUATION",
    "BUY_FADE",
    "SELL_DOWN_CONTINUATION",
    *HISTORIC_PARITY_FAMILIES,
]
STRATEGY_RUNTIME_FLAG_KEYS = [
    "disable_oracle_distilled_context",
    "disable_oracle_distilled_no_side_context",
    "disable_oracle_distilled_strategy_context",
    "exact_context_routing_only",
]


def _run_startup_preflight(source: str) -> None:
    if os.environ.get("MARKETS_SKIP_ORACLE_PREFLIGHT", "").lower() in {"1", "true", "yes"}:
        print(f"[oracle-preflight] {source}: skipped by MARKETS_SKIP_ORACLE_PREFLIGHT", flush=True)
        return
    from oracle_runtime_preflight import run_startup_preflight

    run_startup_preflight(source)


def _json_default(value: Any) -> str:
    return str(value)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _oracle_winner_quality_from_match(
    match: dict[str, Any],
    scenario: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenario = scenario or {}
    selected = match.get("selected_exit") if isinstance(match.get("selected_exit"), dict) else {}
    net_bps = _as_float(match.get("avg_net_bps") or selected.get("avg_net_bps") or selected.get("best_net_bps"))
    horizon = _as_float(selected.get("horizon_minutes"))
    if horizon <= 0:
        examples = match.get("examples") if isinstance(match.get("examples"), list) else []
        for example in examples:
            if isinstance(example, dict):
                horizon = _as_float(example.get("horizon_minutes"))
                if horizon > 0:
                    break
    if horizon <= 0:
        entry = match.get("entry") if isinstance(match.get("entry"), dict) else {}
        horizon = _as_float(entry.get("horizon_minutes"))
    net_bps_per_min = net_bps / horizon if horizon > 0 else 0.0
    min_bank = _as_float(
        scenario.get("oracle_winner_min_bank_entry_net_bps_per_min"),
        ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS_PER_MIN,
    )
    min_abs_bps = _as_float(
        scenario.get("oracle_winner_min_bank_entry_net_bps"),
        ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS,
    )
    min_horizon = _as_float(
        scenario.get("oracle_winner_min_bank_entry_horizon_minutes"),
        ORACLE_WINNER_MIN_BANK_ENTRY_HORIZON_MINUTES,
    )
    return {
        "schema": "oracle_winner_bank_entry_quality_v2",
        "expected_net_bps": round(float(net_bps), 8),
        "expected_hold_minutes": round(float(horizon), 8),
        "expected_net_bps_per_min": round(float(net_bps_per_min), 8),
        "min_bank_entry_net_bps_per_min": round(float(min_bank), 8),
        "min_bank_entry_net_bps": round(float(min_abs_bps), 8),
        "min_bank_entry_horizon_minutes": round(float(min_horizon), 8),
        "bank_quality_eligible": bool(
            horizon >= min_horizon
            and net_bps >= min_abs_bps
            and net_bps_per_min >= min_bank
        ),
    }


def _bank_entry_shadow_reason_for_status(status: Any, scenario: dict[str, Any]) -> str:
    if (
        bool(scenario.get("oracle_bank_no_side_context_shadow_only", True))
        and str(getattr(status, "trade_strategy_source_queue_action", "") or "") == "oracle_distilled_no_side_context"
    ):
        return "oracle_distilled_no_side_context_shadow_only"
    if (
        bool(scenario.get("oracle_bank_require_live_trade_shape", True))
        and int(getattr(status, "trade_present_score", 0) or 0) <= 0
        and not str(getattr(status, "trade_stage", "") or "").strip()
        and not str(getattr(status, "pressure_watch_state", "") or "").strip()
    ):
        return "missing_live_trade_shape_shadow_only"
    return ""


def _bank_entry_shadow_reason_for_trade(trade: dict[str, Any]) -> str:
    # Structural: evidence ledger decision dominates if present. Match returns
    # 'admit_bank' only when per-key Wilson LB clears break-even; anything else
    # forces shadow regardless of legacy flags.
    match = trade.get("oracle_winner_match") or {}
    if isinstance(match, dict) and match.get("evidence_decision"):
        if str(match.get("evidence_decision")) != "admit_bank":
            return f"evidence_decision_{match.get('evidence_decision')}"
    return str(
        trade.get("bank_entry_shadow_reason")
        or trade.get("oracle_bank_shadow_reason")
        or ""
    ).strip()


def _load_state(path: Path, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                return state
        except Exception:
            pass
    return {
        "accounts": {s["id"]: {"scenario": s, "trades": []} for s in scenarios},
        "tracker": {},
        "seen_chunks": [],
        "quotes": {},
        "global_start": 0.0,
        "status_count": 0,
        "started_wall_utc": time.time(),
        "last_report_wall_utc": 0.0,
    }


def _start_policy_epoch(settings: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    active = state.get("active_policy_epoch") if isinstance(state.get("active_policy_epoch"), dict) else {}
    if str((active or {}).get("policy_epoch_version") or "") == ORACLE_POLICY_EPOCH_VERSION:
        epoch = dict(active)
        epoch.update({
            "answer_backed_routes_forced": True,
            "oracle_setup_blockers_defer": True,
            "oracle_long_hold_enforced": True,
            "position_manager_version": POSITION_MANAGER_VERSION,
            "bank_allocation_version": BANK_ALLOCATION_VERSION,
            "bank_allocation_model": BANK_ALLOCATION_MODEL,
            "bank_allocation_target_slots": BANK_ALLOCATION_TARGET_SLOTS,
            "bank_allocation_scope": "per_execution_venue",
            "oracle_winner_admission_venue_agnostic": True,
        })
        settings.update(epoch)
        for scenario in settings.get("scenarios") or []:
            scenario_epoch = dict(epoch)
            if "best_position_rotation_enabled" in scenario:
                scenario_epoch.pop("best_position_rotation_enabled", None)
            scenario.update(scenario_epoch)
        state["active_policy_epoch"] = dict(epoch)
        for row in state.get("policy_epochs") or []:
            if isinstance(row, dict) and str(row.get("policy_epoch_id") or "") == str(epoch.get("policy_epoch_id") or ""):
                row.update(dict(epoch))
        return epoch
    started = time.time()
    epoch_id = f"{ORACLE_POLICY_EPOCH_VERSION}_{time.strftime('%Y%m%d_%H%M%S_utc', time.gmtime(started))}"
    any_rotation_enabled = any(
        bool(scenario.get("best_position_rotation_enabled", scenario.get("rotation_enabled", False)))
        for scenario in (settings.get("scenarios") or [])
        if isinstance(scenario, dict)
    )
    epoch = {
        "policy_epoch_id": epoch_id,
        "policy_epoch_version": ORACLE_POLICY_EPOCH_VERSION,
        "policy_epoch_started_wall_utc": started,
        "answer_backed_routes_forced": True,
        "oracle_setup_blockers_defer": True,
        "oracle_long_hold_enforced": True,
        "best_position_rotation_enabled": any_rotation_enabled,
        "position_manager_version": POSITION_MANAGER_VERSION,
        "bank_allocation_version": BANK_ALLOCATION_VERSION,
        "bank_allocation_model": BANK_ALLOCATION_MODEL,
        "bank_allocation_target_slots": BANK_ALLOCATION_TARGET_SLOTS,
        "bank_allocation_scope": "per_execution_venue",
        "oracle_winner_admission_venue_agnostic": True,
    }
    settings.update(epoch)
    for scenario in settings.get("scenarios") or []:
        scenario_epoch = dict(epoch)
        if "best_position_rotation_enabled" in scenario:
            scenario_epoch.pop("best_position_rotation_enabled", None)
        scenario.update(scenario_epoch)
    state["active_policy_epoch"] = dict(epoch)
    state.setdefault("policy_epochs", []).append(dict(epoch))
    return epoch


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=_json_default), encoding="utf-8")
    tmp.replace(path)


def _tracker_to_tuple_keys(raw: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, value in (raw or {}).items():
        if "|" not in str(key):
            continue
        asset, venue = str(key).split("|", 1)
        if isinstance(value, dict):
            out[(asset, venue)] = value
    return out


def _tracker_to_string_keys(raw: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    return {f"{asset}|{venue}": value for (asset, venue), value in raw.items()}


def _load_account_trackers(state: dict[str, Any], account_ids: list[str]) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    raw_trackers = state.get("trackers") if isinstance(state.get("trackers"), dict) else {}
    legacy = state.get("tracker") if isinstance(state.get("tracker"), dict) else {}
    out: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for account_id in account_ids:
        account_raw = raw_trackers.get(account_id) if isinstance(raw_trackers.get(account_id), dict) else legacy
        out[account_id] = _tracker_to_tuple_keys(account_raw or {})
    return out


def _dump_account_trackers(trackers: dict[str, dict[tuple[str, str], dict[str, Any]]]) -> dict[str, Any]:
    return {
        account_id: _tracker_to_string_keys(tracker)
        for account_id, tracker in trackers.items()
    }


def _strategy_runtime_flags(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        key: scenario[key]
        for key in STRATEGY_RUNTIME_FLAG_KEYS
        if key in scenario
    }


def _quotes_to_tuple_keys(raw: dict[str, Any]) -> dict[tuple[str, str], tuple[float, float, float, float]]:
    out: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    for key, value in (raw or {}).items():
        if "|" not in str(key) or not isinstance(value, list) or len(value) != 4:
            continue
        asset, venue = str(key).split("|", 1)
        out[(asset, venue)] = tuple(float(x or 0.0) for x in value)  # type: ignore[assignment]
    return out


def _quotes_to_string_keys(raw: dict[tuple[str, str], tuple[float, float, float, float]]) -> dict[str, Any]:
    return {f"{asset}|{venue}": list(value) for (asset, venue), value in raw.items()}


def _load_visible_bars(data_dir: Path) -> dict[tuple[str, str], list[Any]]:
    out: dict[tuple[str, str], list[Any]] = {}
    for asset, venues in VENUES.items():
        for venue, filename in venues.items():
            path = data_dir / filename
            if not path.exists():
                continue
            try:
                bars = load_bars(str(path))
            except Exception:
                bars = []
            if bars:
                out[(asset, venue)] = bars
    return out


def _recent_tail_bars(bars: list[Any], *, max_bars: int = 720, max_minutes: float = 180.0) -> list[Any]:
    if not bars:
        return []
    end_ts = float(getattr(bars[-1], "ts", 0.0) or 0.0)
    cutoff = end_ts - float(max_minutes) * 60.0
    tail = [bar for bar in bars if float(getattr(bar, "ts", 0.0) or 0.0) >= cutoff]
    if max_bars > 0 and len(tail) > max_bars:
        tail = tail[-max_bars:]
    return tail or bars[-min(len(bars), max_bars or len(bars)):]


def _chunk_dedupe_key(asset: str, venue: str, inputs: dict[str, Any]) -> str:
    end_ts = float(inputs.get("chunk_end_ts_utc") or inputs.get("market_ts_utc") or 0.0)
    return f"{asset}|{venue}|{end_ts:.6f}" if end_ts > 0 else ""


def _live_cell_suffix(inputs: dict[str, Any]) -> str:
    chunk_id = str(inputs.get("chunk_id") or "")
    end_ts = int(float(inputs.get("chunk_end_ts_utc") or inputs.get("market_ts_utc") or 0.0))
    return f"{chunk_id}_{end_ts}" if end_ts else chunk_id


def _latest_chunk_dedupes(
    data_dir: Path,
    *,
    synthetic_spread_bps: float,
    global_start: float = 0.0,
) -> tuple[set[str], float]:
    raw_bars = _load_visible_bars(data_dir)
    all_ts = [float(b.ts) for bars in raw_bars.values() for b in bars]
    if not all_ts:
        return set(), global_start
    global_start = float(global_start or 0.0) or min(all_ts)
    tracker: dict[tuple[str, str], dict[str, Any]] = {}
    dedupes: set[str] = set()
    for (asset, venue), bars in raw_bars.items():
        visible_bars = _recent_tail_bars(bars)
        status, inputs = current_status_from_visible(
            asset,
            venue,
            visible_bars,
            tracker,
            float(synthetic_spread_bps),
            session_from_offset_hours((float(bars[-1].ts) - global_start) / 3600.0),
            None,
            False,
            False,
        )
        if status is None:
            continue
        dedupe = _chunk_dedupe_key(asset, venue, inputs)
        if dedupe:
            dedupes.add(dedupe)
    return dedupes, global_start


def _opportunity_row(
    *,
    decision: str,
    reason: str,
    status: Any,
    scenario: dict[str, Any],
    settings: dict[str, Any],
    inputs: dict[str, Any],
    trade: dict[str, Any] | None = None,
    position_rotation: dict[str, Any] | None = None,
    planned_notional: float = 0.0,
    fill_price: float = 0.0,
) -> dict[str, Any]:
    sid = str(scenario.get("id") or "")
    row_ts = float(inputs.get("decision_wall_utc") or time.time())
    row = {
        "schema": "live_mock_trade_opportunity_v1",
        "source": "live_mock_trade_replay",
        "ts_utc": row_ts,
        "policy_epoch_id": str(settings.get("policy_epoch_id") or ""),
        "policy_epoch_version": str(settings.get("policy_epoch_version") or ""),
        "policy_epoch_started_wall_utc": float(settings.get("policy_epoch_started_wall_utc") or 0.0),
        "market_ts_utc": float(inputs.get("chunk_end_ts_utc") or getattr(status, "last_update_utc", 0.0) or 0.0),
        "decision": decision,
        "reason": reason,
        "asset": status.asset,
        "venue": status.venue,
        "side": status.trade_option_side or status.pressure_watch_direction,
        "cell_id": f"live_replay_{sid}_{status.asset.lower()}_{status.venue.lower()}_{_live_cell_suffix(inputs)}",
        "chunk_id": str(inputs.get("chunk_id") or ""),
        "chunk_start_ts_utc": float(inputs.get("chunk_start_ts_utc") or 0.0),
        "chunk_end_ts_utc": float(inputs.get("chunk_end_ts_utc") or getattr(status, "last_update_utc", 0.0) or 0.0),
        "chunk_window": list(getattr(status, "chunk_window", ()) or []),
        "bucket_session": str(inputs.get("bucket_session") or ""),
        "scenario_id": sid,
        "scenario_label": str(scenario.get("label") or sid),
        "notional_pct_bank": float(scenario.get("notional_pct_bank") or 0.0),
        "initial_bank_usd": float(settings.get("initial_bank_usd") or 10000.0),
        "planned_notional_usd": float(planned_notional or 0.0),
        "fill_price": float(fill_price or 0.0),
        "actual_execution": False,
        "actual_notional": 0.0,
        "learning_capital_model": "full_bank_hypothetical_no_exposure_lock",
        "exit_params_path": str(settings.get("exit_params_path") or ""),
        "exit_params_loaded": bool(settings.get("exit_params_loaded")),
        "opened_trade_intent_id": str((trade or {}).get("intent_id") or ""),
        "trade_strategy_id": status.trade_strategy_id,
        "trade_strategy_label": status.trade_strategy_label,
        "trade_strategy_mode": "practice",
        "trade_strategy_confidence": status.trade_strategy_confidence,
        "trade_strategy_variant_id": status.trade_strategy_variant_id,
        "trade_strategy_forced": bool(status.trade_strategy_forced),
        "trade_strategy_reasons": list(status.trade_strategy_reasons),
        "trade_strategy_blockers": list(status.trade_strategy_blockers),
        "trade_strategy_risk_tags": list(status.trade_strategy_risk_tags),
        "trade_strategy_source_queue_action": status.trade_strategy_source_queue_action,
        "trade_option_state": status.trade_option_state,
        "trade_option_profile": status.trade_option_profile,
        "trade_option_readiness": status.trade_option_readiness,
        "trade_option_blockers": list(status.trade_option_blockers),
        "trade_stage": str(getattr(status, "trade_stage", "") or inputs.get("trade_stage") or ""),
        "trade_age_chunks": status.trade_age_chunks,
        "trade_present_score": int(getattr(status, "trade_present_score", 0) or inputs.get("trade_present_score") or 0),
        "trade_score_band": str(getattr(status, "trade_score_band", "") or inputs.get("trade_score_band") or ""),
        "trade_from_onset_bps": float(getattr(status, "trade_from_onset_bps", 0.0) or inputs.get("trade_from_onset_bps") or 0.0),
        "trade_current_chunk_bps": float(getattr(status, "trade_current_chunk_bps", 0.0) or inputs.get("trade_current_chunk_bps") or 0.0),
        "trade_recent_2chunk_bps": float(getattr(status, "trade_recent_2chunk_bps", 0.0) or inputs.get("trade_recent_2chunk_bps") or 0.0),
        "pressure_watch_state": status.pressure_watch_state,
        "pressure_watch_label": status.pressure_watch_label,
        "pressure_watch_direction": status.pressure_watch_direction,
        "pressure_watch_reasons": list(status.pressure_watch_reasons),
        "regime": status.regime,
        "confidence": status.confidence,
        "adjusted_confidence": status.adjusted_confidence,
        "mean_dipole": status.mean_dipole,
        "volume_zscore": float(inputs.get("volume_zscore") or 0.0),
        "dipole_acl1": float(inputs.get("dipole_acl1") or 0.0),
        "daily_news_context": dict(status.daily_news_context),
        "daily_news_status": dict(status.daily_news_status),
    }
    if position_rotation:
        row["position_rotation"] = dict(position_rotation)
    oracle_match = inputs.get("oracle_winner_match")
    if isinstance(oracle_match, dict) and oracle_match:
        selected = oracle_match.get("selected_exit") if isinstance(oracle_match.get("selected_exit"), dict) else {}
        quality = inputs.get("oracle_winner_bank_entry_quality") if isinstance(inputs.get("oracle_winner_bank_entry_quality"), dict) else {}
        row["oracle_winner_match_level"] = str(oracle_match.get("match_level") or "")
        row["oracle_winner_match_key"] = str(oracle_match.get("match_key") or "")
        row["oracle_winner_count"] = int(oracle_match.get("oracle_winner_count") or 0)
        row["oracle_winner_avg_net_bps"] = float(oracle_match.get("avg_net_bps") or 0.0)
        row["oracle_winner_expected_hold_minutes"] = float(quality.get("expected_hold_minutes") or selected.get("horizon_minutes") or 0.0)
        row["oracle_winner_expected_net_bps_per_min"] = float(quality.get("expected_net_bps_per_min") or 0.0)
        row["oracle_winner_min_bank_entry_net_bps_per_min"] = float(quality.get("min_bank_entry_net_bps_per_min") or 0.0)
        row["oracle_winner_bank_quality_eligible"] = bool(quality.get("bank_quality_eligible"))
        row["oracle_winner_runtime_exit_id"] = str((selected or {}).get("runtime_exit_id") or "")
    bank_shadow_reason = str(inputs.get("bank_entry_shadow_reason") or inputs.get("oracle_bank_shadow_reason") or "")
    if bank_shadow_reason:
        row["bank_entry_shadow_reason"] = bank_shadow_reason
        row["oracle_bank_shadow_reason"] = bank_shadow_reason
        row["bank_allocation_reason"] = bank_shadow_reason
    return row


def _append_opportunity(row: dict[str, Any]) -> None:
    OPPORTUNITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OPPORTUNITY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")


def _rewrite_trade_snapshot(accounts: dict[str, dict[str, Any]]) -> None:
    TRADE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRADE_SNAPSHOT.with_suffix(TRADE_SNAPSHOT.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for account in accounts.values():
            for trade in account.get("trades") or []:
                f.write(json.dumps(trade, default=_json_default) + "\n")
    tmp.replace(TRADE_SNAPSHOT)


def _trade_matches_policy_epoch(trade: dict[str, Any], policy_epoch_id: str) -> bool:
    if not policy_epoch_id:
        return True
    return str(trade.get("policy_epoch_id") or "") == policy_epoch_id


def _accounts_view_for_policy_epoch(
    accounts: dict[str, dict[str, Any]],
    policy_epoch_id: str,
    *,
    include_open: bool = True,
) -> dict[str, dict[str, Any]]:
    view: dict[str, dict[str, Any]] = {}
    for account_id, account in accounts.items():
        trades = []
        for trade in account.get("trades") or []:
            if _trade_matches_policy_epoch(trade, policy_epoch_id):
                trades.append(trade)
            elif include_open and trade.get("status") == "open":
                trades.append(trade)
        view[account_id] = {
            "scenario": account.get("scenario") or {},
            "trades": trades,
        }
    return view


def _retire_prior_epoch_closed_trades(
    state: dict[str, Any],
    accounts: dict[str, dict[str, Any]],
    policy_epoch_id: str,
) -> int:
    if not policy_epoch_id:
        return 0
    retired = state.setdefault("retired_closed_trades_by_policy_epoch", {})
    retired_count = 0
    for account_id, account in accounts.items():
        keep: list[dict[str, Any]] = []
        for trade in account.get("trades") or []:
            if trade.get("status") == "closed" and not _trade_matches_policy_epoch(trade, policy_epoch_id):
                archived = dict(trade)
                archived["_retired_from_account_id"] = account_id
                archived["_retired_for_policy_epoch_id"] = policy_epoch_id
                retired.setdefault(account_id, []).append(archived)
                retired_count += 1
                continue
            keep.append(trade)
        account["trades"] = keep
    return retired_count


def _apply_live_pnl_guards(
    accounts: dict[str, dict[str, Any]],
    scenarios: list[dict[str, Any]],
    policy_epoch_id: str = "",
) -> dict[str, Any]:
    by_side: dict[str, dict[str, float]] = {}
    by_strategy_side: dict[str, dict[str, float]] = {}
    for account in accounts.values():
        for trade in account.get("trades") or []:
            if trade.get("status") != "closed":
                continue
            if not _trade_matches_policy_epoch(trade, policy_epoch_id):
                continue
            side = str(trade.get("side") or "").lower()
            if side not in {"buy", "sell"}:
                continue
            strategy_id = str(trade.get("trade_strategy_id") or "").upper()
            pnl = bank_realized_pnl_for_trade(trade)
            counted_notional = float(trade.get("bank_allocated_notional_usd") or trade.get("real_mock_notional_usd") or 0.0)
            if counted_notional <= 0.0 and pnl == 0.0:
                continue
            row = by_side.setdefault(side, {"closed": 0.0, "wins": 0.0, "pnl": 0.0})
            row["closed"] += 1.0
            row["wins"] += 1.0 if pnl > 0.0 else 0.0
            row["pnl"] += pnl
            if strategy_id:
                srow = by_strategy_side.setdefault(f"{strategy_id}:{side}", {"closed": 0.0, "wins": 0.0, "pnl": 0.0})
                srow["closed"] += 1.0
                srow["wins"] += 1.0 if pnl > 0.0 else 0.0
                srow["pnl"] += pnl
    side_stats: dict[str, dict[str, float]] = {}
    for side, row in by_side.items():
        closed = int(row["closed"])
        wins = int(row["wins"])
        pnl = float(row["pnl"])
        win_rate = (wins / closed) if closed else 0.0
        side_stats[side] = {
            "closed": float(closed),
            "wins": float(wins),
            "win_rate": round(win_rate, 6),
            "realized_pnl_usd": round(pnl, 8),
            "pnl_accounting": "bank_allocated_only",
        }
    blocked_strategy_sides: list[str] = []
    strategy_side_stats: dict[str, dict[str, float]] = {}
    for key, row in by_strategy_side.items():
        closed = int(row["closed"])
        wins = int(row["wins"])
        pnl = float(row["pnl"])
        win_rate = (wins / closed) if closed else 0.0
        strategy_side_stats[key] = {
            "closed": float(closed),
            "wins": float(wins),
            "win_rate": round(win_rate, 6),
            "realized_pnl_usd": round(pnl, 8),
            "pnl_accounting": "bank_allocated_only",
        }
        if closed >= LIVE_GUARD_MIN_CLOSED_BY_SIDE and pnl < LIVE_GUARD_MAX_PNL_USD and win_rate < LIVE_GUARD_MAX_WIN_RATE:
            blocked_strategy_sides.append(key.lower())
    for scenario in scenarios:
        manual = {str(x).lower() for x in scenario.get("manual_blocked_sides") or [] if str(x).strip()}
        scenario["blocked_sides"] = sorted(manual)
        scenario["blocked_strategy_sides"] = sorted(blocked_strategy_sides)
        scenario["live_pnl_guard"] = {
            "enabled": True,
            "min_closed_by_side": LIVE_GUARD_MIN_CLOSED_BY_SIDE,
            "max_win_rate": LIVE_GUARD_MAX_WIN_RATE,
            "max_pnl_usd": LIVE_GUARD_MAX_PNL_USD,
            "blocked_sides": sorted(manual),
            "blocked_strategy_sides": sorted(blocked_strategy_sides),
            "side_stats": side_stats,
            "strategy_side_stats": strategy_side_stats,
        }
    return {
        "blocked_sides": [],
        "blocked_strategy_sides": sorted(blocked_strategy_sides),
        "side_stats": side_stats,
        "strategy_side_stats": strategy_side_stats,
    }


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


def _is_answer_backed_status(status: Any) -> bool:
    source = str(getattr(status, "trade_strategy_source_queue_action", "") or "")
    risk_tags = {str(tag) for tag in (getattr(status, "trade_strategy_risk_tags", []) or [])}
    return (
        _source_priority(source) > 0.0
        or "oracle_distilled_context" in risk_tags
        or "historical_route" in risk_tags
    )


def _is_answer_backed_trade(trade: dict[str, Any]) -> bool:
    source = str(trade.get("trade_strategy_source_queue_action") or "")
    exit_key = str(trade.get("exit_config_key") or "")
    risk_tags = {str(tag) for tag in (trade.get("trade_strategy_risk_tags") or [])}
    return (
        _source_priority(source) > 0.0
        or "oracle" in exit_key.lower()
        or "oracle_distilled_context" in risk_tags
        or "historical_route" in risk_tags
    )


def _position_score_components_for_candidate(
    status: Any,
    scenario: dict[str, Any],
    settings: dict[str, Any],
    inputs: dict[str, Any],
    side: str,
) -> dict[str, float | str]:
    candidate = {
        "trade_strategy_id": str(getattr(status, "trade_strategy_id", "") or ""),
        "asset": str(getattr(status, "asset", "") or ""),
        "venue": str(getattr(status, "venue", "") or ""),
        "bucket_session": str(inputs.get("bucket_session") or ""),
        "side": side,
        "fee_bps": float(settings.get("mock_fee_bps") or 5.0),
        "hold_minutes": float(scenario.get("hold_minutes") or 0.0),
        "trade_present_score": int(getattr(status, "trade_present_score", 0) or 0),
        "trade_strategy_exit_score_drop": int(getattr(status, "trade_strategy_exit_score_drop", 0) or 0),
    }
    profile, cfg = trade_exit_strategy.exit_profile_for_trade(candidate, scenario)
    target_bps = max(
        float(cfg.get("take_profit_bps") or 0.0),
        float(cfg.get("tp1_bps") or 0.0),
        float(profile.score_exit_min_profit_bps or 0.0),
        float(getattr(status, "trade_strategy_take_profit_bps", 0.0) or 0.0),
    )
    confidence = float(getattr(status, "trade_strategy_confidence", 0.0) or 0.0)
    present_score = float(
        max(
            int(getattr(status, "trade_present_score", 0) or 0),
            int(getattr(status, "trade_option_readiness", 0) or 0),
        )
    )
    source = str(getattr(status, "trade_strategy_source_queue_action", "") or "")
    priority = _source_priority(source)
    score = (priority * 25.0) + (confidence * 100.0) + (min(target_bps, 150.0) * 0.25) + (present_score * 0.15)
    return {
        "score": round(float(score), 6),
        "source_priority": round(float(priority), 3),
        "confidence": round(float(confidence), 6),
        "target_bps": round(float(target_bps), 6),
        "present_score": round(float(present_score), 3),
        "source_queue_action": source,
        "position_manager_version": POSITION_MANAGER_VERSION,
    }


def _position_score_for_trade(
    trade: dict[str, Any],
    quote: tuple[float, float, float, float],
) -> dict[str, float | str]:
    bid, ask, mid, _ts = quote
    unreal = trade_exit_strategy.unrealized_bps(trade, bid, ask, mid)
    net = trade_exit_strategy.net_unrealized_bps(trade, unreal)
    base = trade.get("best_position_score")
    if base is None:
        target_bps = max(
            float(trade.get("exit_tp1_bps") or 0.0),
            float(trade.get("score_exit_min_profit_bps") or 0.0),
            float(trade.get("trade_strategy_take_profit_bps") or 0.0),
        )
        base = (
            _source_priority(str(trade.get("trade_strategy_source_queue_action") or "")) * 25.0
            + float(trade.get("trade_strategy_confidence") or 0.0) * 100.0
            + min(target_bps, 150.0) * 0.25
            + float(trade.get("trade_present_score") or 0.0) * 0.15
        )
    current = float(base) + float(net)
    return {
        "base_score": round(float(base), 6),
        "current_score": round(float(current), 6),
        "unrealized_bps": round(float(unreal), 6),
        "net_unrealized_bps": round(float(net), 6),
    }


def _same_position(trade: dict[str, Any], status: Any, side: str) -> bool:
    return (
        str(trade.get("asset") or "") == str(getattr(status, "asset", "") or "")
        and str(trade.get("venue") or "") == str(getattr(status, "venue", "") or "")
        and str(trade.get("side") or "") == side
        and str(trade.get("trade_strategy_id") or "") == str(getattr(status, "trade_strategy_id", "") or "")
    )


def _maybe_rotate_to_best_position(
    account: dict[str, Any],
    scenario: dict[str, Any],
    status: Any,
    settings: dict[str, Any],
    inputs: dict[str, Any],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    side: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    components = _position_score_components_for_candidate(status, scenario, settings, inputs, side)
    if (
        bool(scenario.get("counterfactual_exit_selector_enabled"))
        and bool(scenario.get("counterfactual_exit_selector_blocks_rotation"))
    ):
        return None, components
    if not bool(scenario.get("best_position_rotation_enabled", True)):
        return None, components
    if not _is_answer_backed_status(status):
        return None, components
    incoming_score = float(components["score"])
    min_advantage = float(scenario.get("best_position_min_score_advantage") or 15.0)
    max_replaced_net_bps = float(scenario.get("best_position_max_replaced_net_bps") or 0.0)
    candidates: list[tuple[float, float, dict[str, Any], tuple[float, float, float, float], dict[str, Any]]] = []
    for trade in account.get("trades") or []:
        if trade.get("status") != "open":
            continue
        if not _is_answer_backed_trade(trade):
            continue
        if _same_position(trade, status, side):
            continue
        quote = quotes.get((str(trade.get("asset") or ""), str(trade.get("venue") or "")))
        if not quote:
            continue
        trade_score = _position_score_for_trade(trade, quote)
        if float(trade_score["net_unrealized_bps"]) > max_replaced_net_bps:
            continue
        candidates.append((float(trade_score["current_score"]), float(trade_score["net_unrealized_bps"]), trade, quote, trade_score))
    if not candidates:
        return None, components
    candidates.sort(key=lambda row: (row[0], row[1]))
    weakest_score, weakest_net, weakest, quote, weakest_components = candidates[0]
    if incoming_score < weakest_score + min_advantage:
        return None, components
    bid, ask, mid, ts = quote
    if not close_trade(weakest, bid, ask, mid, ts, ROTATION_CLOSE_REASON):
        return None, components
    rotation = {
        "position_manager_version": POSITION_MANAGER_VERSION,
        "rotation_reason": ROTATION_CLOSE_REASON,
        "incoming_score": round(float(incoming_score), 6),
        "incoming_components": components,
        "replaced_score": round(float(weakest_score), 6),
        "replaced_components": weakest_components,
        "min_score_advantage": round(float(min_advantage), 6),
        "max_replaced_net_bps": round(float(max_replaced_net_bps), 6),
        "replaced_asset": str(weakest.get("asset") or ""),
        "replaced_venue": str(weakest.get("venue") or ""),
        "replaced_side": str(weakest.get("side") or ""),
        "replaced_strategy_id": str(weakest.get("trade_strategy_id") or ""),
        "replaced_chunk_id": str(weakest.get("chunk_id") or ""),
        "replaced_policy_epoch_id": str(weakest.get("policy_epoch_id") or ""),
        "replacement_asset": str(getattr(status, "asset", "") or ""),
        "replacement_venue": str(getattr(status, "venue", "") or ""),
        "replacement_side": side,
        "replacement_strategy_id": str(getattr(status, "trade_strategy_id", "") or ""),
        "replacement_chunk_id": str(inputs.get("chunk_id") or ""),
    }
    weakest["rotation_to_asset"] = rotation["replacement_asset"]
    weakest["rotation_to_venue"] = rotation["replacement_venue"]
    weakest["rotation_to_side"] = rotation["replacement_side"]
    weakest["rotation_to_strategy_id"] = rotation["replacement_strategy_id"]
    weakest["rotation_to_score"] = rotation["incoming_score"]
    weakest["rotation_from_score"] = rotation["replaced_score"]
    weakest["rotation_from_net_unrealized_bps"] = round(float(weakest_net), 6)
    weakest["position_rotation"] = dict(rotation)
    return rotation, components


def _trade_identity_key(trade: dict[str, Any]) -> str:
    return "|".join(
        [
            str(trade.get("asset") or "").upper(),
            str(trade.get("venue") or "").lower(),
            str(trade.get("chunk_id") or ""),
            str(trade.get("side") or "").lower(),
            str(trade.get("trade_strategy_id") or "").upper(),
            str(trade.get("opened_wall_utc") or trade.get("market_entry_ts_utc") or ""),
        ]
    )


def _allocation_weights(candidates: list[dict[str, Any]]) -> list[float]:
    if not candidates:
        return []
    if len(candidates) == 1:
        return [1.0]
    weights = [1.0] * len(candidates)
    lead = float(candidates[0]["current_score"]) - float(candidates[1]["current_score"])
    leader_net = float(candidates[0]["net_unrealized_bps"])
    if lead >= BANK_ALLOCATION_LEADER_85_SCORE_LEAD and leader_net >= BANK_ALLOCATION_LEADER_85_MIN_NET_BPS:
        weights = [0.85] + ([0.15 / (len(candidates) - 1)] * (len(candidates) - 1))
    elif lead >= BANK_ALLOCATION_LEADER_70_SCORE_LEAD and leader_net >= 0.0:
        weights = [0.70] + ([0.30 / (len(candidates) - 1)] * (len(candidates) - 1))
    total = sum(weights)
    return [weight / total for weight in weights] if total > 0.0 else [1.0 / len(candidates)] * len(candidates)


def _trade_sort_ts(trade: dict[str, Any]) -> float:
    return float(trade.get("opened_wall_utc") or trade.get("market_entry_ts_utc") or trade.get("ts_utc") or 0.0)


def _venue_starting_banks(settings: dict[str, Any]) -> dict[str, float]:
    total = float(settings.get("initial_bank_usd") or 10000.0)
    venues = list(LIVE_EXECUTION_VENUES)
    if not venues:
        return {}
    cents = int(round(total * 100.0))
    base = cents // len(venues)
    out: dict[str, float] = {}
    used = 0
    for venue in venues[:-1]:
        out[venue] = round(base / 100.0, 2)
        used += base
    out[venues[-1]] = round((cents - used) / 100.0, 2)
    return out


def _venue_starting_bank(settings: dict[str, Any], venue: str) -> float:
    banks = _venue_starting_banks(settings)
    return float(banks.get(str(venue) or "", 0.0))


def _venue_bank_realized_pnl(account: dict[str, Any], venue: str) -> float:
    venue = str(venue or "")
    total = 0.0
    for trade in account.get("trades") or []:
        if trade.get("status") != "closed" or str(trade.get("venue") or "") != venue:
            continue
        total += bank_realized_pnl_for_trade(trade)
    return total


def _venue_bank_equity_for(account: dict[str, Any], settings: dict[str, Any], venue: str) -> float:
    return max(0.0, _venue_starting_bank(settings, venue) + _venue_bank_realized_pnl(account, venue))


def _is_bank_allocated_open_trade(trade: dict[str, Any], venue: str = "") -> bool:
    return (
        trade.get("status") == "open"
        and not _bank_entry_shadow_reason_for_trade(trade)
        and trade.get("oracle_winner_bank_quality_eligible") is not False
        and (not venue or str(trade.get("venue") or "") == str(venue))
        and (
            str(trade.get("pnl_accounting_role") or "") == "bank_allocated"
            or bool(trade.get("pnl_counted_as_real"))
            or float(trade.get("bank_allocated_notional_usd") or 0.0) > 0.0
            or float(trade.get("real_mock_notional_usd") or 0.0) > 0.0
        )
    )


def _open_bank_allocated_trades(account: dict[str, Any], venue: str = "") -> list[dict[str, Any]]:
    return sorted(
        [trade for trade in account.get("trades") or [] if _is_bank_allocated_open_trade(trade, venue)],
        key=_trade_sort_ts,
    )


def _stamp_oracle_shadow_trade(trade: dict[str, Any]) -> None:
    trade["bank_allocation_version"] = BANK_ALLOCATION_VERSION
    trade["bank_allocation_model"] = BANK_ALLOCATION_MODEL
    trade["bank_allocation_target_slots"] = BANK_ALLOCATION_TARGET_SLOTS
    trade["pnl_accounting_role"] = "oracle_shadow"
    trade["pnl_counted_as_real"] = False
    trade["real_mock_notional_usd"] = 0.0
    trade["bank_allocation_rank"] = None
    trade["bank_allocation_weight"] = 0.0
    trade["bank_allocated_notional_usd"] = 0.0
    trade["bank_pnl_weight"] = 0.0
    trade["bank_allocation_score"] = None
    trade["bank_allocation_net_unrealized_bps"] = None
    trade["bank_allocation_est_net_pnl_usd"] = 0.0
    trade["execution_venue"] = str(trade.get("venue") or "")


def _stamp_oracle_winner_quality(trade: dict[str, Any], quality: dict[str, Any]) -> None:
    if not quality:
        return
    trade["oracle_winner_bank_entry_quality"] = dict(quality)
    trade["oracle_winner_expected_net_bps"] = float(quality.get("expected_net_bps") or 0.0)
    trade["oracle_winner_expected_hold_minutes"] = float(quality.get("expected_hold_minutes") or 0.0)
    trade["oracle_winner_expected_net_bps_per_min"] = float(quality.get("expected_net_bps_per_min") or 0.0)
    trade["oracle_winner_min_bank_entry_net_bps_per_min"] = float(quality.get("min_bank_entry_net_bps_per_min") or 0.0)
    trade["oracle_winner_bank_quality_eligible"] = bool(quality.get("bank_quality_eligible"))


def _stamp_bank_allocated_trade(
    trade: dict[str, Any],
    *,
    bank_usd: float,
    venue_starting_bank_usd: float = 0.0,
    score_row: dict[str, Any] | None = None,
) -> None:
    notional = max(float(trade.get("notional") or trade.get("hypothetical_notional") or 0.0), 1e-12)
    net_bps = float((score_row or {}).get("net_unrealized_bps") or trade.get("bank_allocation_net_unrealized_bps") or 0.0)
    score = float((score_row or {}).get("current_score") or trade.get("bank_allocation_score") or trade.get("best_position_score") or 0.0)
    trade["bank_allocation_version"] = BANK_ALLOCATION_VERSION
    trade["bank_allocation_model"] = BANK_ALLOCATION_MODEL
    trade["bank_allocation_target_slots"] = BANK_ALLOCATION_TARGET_SLOTS
    trade["pnl_accounting_role"] = "bank_allocated"
    trade["pnl_counted_as_real"] = True
    trade["bank_allocation_rank"] = 1
    trade["bank_allocation_weight"] = 1.0
    trade["bank_allocated_notional_usd"] = round(float(bank_usd), 8)
    trade["real_mock_notional_usd"] = round(float(bank_usd), 8)
    bank_pnl_weight = max(0.0, float(bank_usd) / notional)
    trade["bank_pnl_weight"] = round(bank_pnl_weight, 8)
    trade["bank_entry_fees_usd"] = round(float(trade.get("entry_fees_usd") or 0.0) * bank_pnl_weight, 8)
    trade["bank_exit_fees_usd"] = float(trade.get("bank_exit_fees_usd") or 0.0)
    trade["bank_fees_usd"] = round(
        float(trade.get("bank_entry_fees_usd") or 0.0) + float(trade.get("bank_exit_fees_usd") or 0.0),
        8,
    )
    trade["execution_venue"] = str(trade.get("venue") or "")
    trade["venue_bank_starting_usd"] = round(float(venue_starting_bank_usd), 8)
    trade["venue_bank_equity_usd"] = round(float(bank_usd), 8)
    trade["bank_allocation_score"] = round(score, 6)
    trade["bank_allocation_net_unrealized_bps"] = round(net_bps, 6)
    trade["bank_allocation_est_net_pnl_usd"] = round(float(bank_usd) * net_bps / 10000.0, 8)


def _apply_bank_allocation(
    accounts: dict[str, dict[str, Any]],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    starting_bank_usd = float(settings.get("initial_bank_usd") or 1000.0)
    starting_venue_banks = _venue_starting_banks(settings)
    summary: dict[str, Any] = {
        "schema": "live_bank_allocation_runtime_v1",
        "updated_wall_utc": time.time(),
        "version": BANK_ALLOCATION_VERSION,
        "model": BANK_ALLOCATION_MODEL,
        "target_slots": BANK_ALLOCATION_TARGET_SLOTS,
        "starting_bank_usd": round(starting_bank_usd, 8),
        "starting_venue_banks": dict(starting_venue_banks),
        "bank_usd": round(starting_bank_usd, 8),
        "accounts": {},
    }
    total_candidates = 0
    total_allocated = 0
    total_allocated_notional = 0.0
    for account_id, account in accounts.items():
        candidates: list[dict[str, Any]] = []
        open_answer_trades: list[dict[str, Any]] = []
        for trade in account.get("trades") or []:
            if trade.get("status") != "open" or not _is_answer_backed_trade(trade):
                continue
            open_answer_trades.append(trade)
            quote = quotes.get((str(trade.get("asset") or ""), str(trade.get("venue") or "")))
            if not quote:
                continue
            score = _position_score_for_trade(trade, quote)
            candidates.append({
                "key": _trade_identity_key(trade),
                "trade": trade,
                **score,
            })
        candidate_by_key = {str(row["key"]): row for row in candidates}
        selected_by_venue: dict[str, dict[str, Any]] = {}
        for venue in LIVE_EXECUTION_VENUES:
            bank_open = _open_bank_allocated_trades(account, venue)
            if bank_open:
                selected_by_venue[venue] = bank_open[0]
        for trade in open_answer_trades:
            key = _trade_identity_key(trade)
            venue = str(trade.get("venue") or "")
            trade["bank_allocation_key"] = key
            selected_trade = selected_by_venue.get(venue)
            selected_key = _trade_identity_key(selected_trade) if selected_trade else ""
            trade_quality = trade.get("oracle_winner_bank_entry_quality") if isinstance(trade.get("oracle_winner_bank_entry_quality"), dict) else {}
            trade_quality_eligible = bool(trade_quality.get("bank_quality_eligible", False))
            trade_shadow_reason = _bank_entry_shadow_reason_for_trade(trade)
            if selected_key and key == selected_key and trade_quality_eligible and not trade_shadow_reason:
                venue_bank_usd = _venue_bank_equity_for(account, settings, venue)
                _stamp_bank_allocated_trade(
                    trade,
                    bank_usd=venue_bank_usd,
                    venue_starting_bank_usd=_venue_starting_bank(settings, venue),
                    score_row=candidate_by_key.get(key),
                )
            else:
                _stamp_oracle_shadow_trade(trade)
                if trade_shadow_reason:
                    trade["bank_allocation_reason"] = trade_shadow_reason
                elif not trade_quality_eligible:
                    trade["bank_allocation_reason"] = "demoted_oracle_winner_quality_ineligible"
                elif not (selected_key and key == selected_key):
                    trade["bank_allocation_reason"] = "venue_bank_slot_occupied_or_empty_shadow_only"
        holdings = []
        venue_summaries: dict[str, Any] = {}
        account_bank_equity = 0.0
        account_bank_realized = 0.0
        for venue in LIVE_EXECUTION_VENUES:
            venue_start = _venue_starting_bank(settings, venue)
            venue_realized = _venue_bank_realized_pnl(account, venue)
            venue_equity = _venue_bank_equity_for(account, settings, venue)
            account_bank_equity += venue_equity
            account_bank_realized += venue_realized
            selected_trade = selected_by_venue.get(venue)
            venue_holdings = []
            venue_candidates = [row for row in candidates if str((row.get("trade") or {}).get("venue") or "") == venue]
            if selected_trade:
                selected_key = _trade_identity_key(selected_trade)
                row = candidate_by_key.get(selected_key) or {"trade": selected_trade, "key": selected_key}
                net_bps = float(row.get("net_unrealized_bps") or selected_trade.get("bank_allocation_net_unrealized_bps") or 0.0)
                allocated_notional = float(selected_trade.get("bank_allocated_notional_usd") or 0.0)
                holding = {
                    "rank": 1,
                    "key": selected_key,
                    "asset": str(selected_trade.get("asset") or ""),
                    "venue": str(selected_trade.get("venue") or ""),
                    "side": str(selected_trade.get("side") or ""),
                    "strategy_id": str(selected_trade.get("trade_strategy_id") or ""),
                    "weight_pct": 100.0,
                    "allocated_notional_usd": round(allocated_notional, 8),
                    "current_position_score": round(float(row.get("current_score") or selected_trade.get("bank_allocation_score") or 0.0), 6),
                    "net_unrealized_bps_after_fees": round(net_bps, 6),
                    "estimated_net_pnl_usd": round(allocated_notional * net_bps / 10000.0, 8),
                }
                holdings.append(holding)
                venue_holdings.append(holding)
            venue_summaries[venue] = {
                "starting_bank_usd": round(venue_start, 8),
                "bank_realized_pnl_usd": round(venue_realized, 8),
                "bank_equity_usd": round(venue_equity, 8),
                "open_answer_backed_candidates": len(venue_candidates),
                "allocated_slots": len(venue_holdings),
                "allocated_notional_usd": round(sum(float(row.get("allocated_notional_usd") or 0.0) for row in venue_holdings), 8),
                "holdings": venue_holdings,
            }
        account_summary = {
            "starting_bank_usd": round(starting_bank_usd, 8),
            "bank_realized_pnl_usd": round(account_bank_realized, 8),
            "bank_equity_usd": round(account_bank_equity, 8),
            "venue_banks": venue_summaries,
            "open_answer_backed_candidates": len(candidates),
            "open_answer_backed_without_quote": max(0, len(open_answer_trades) - len(candidates)),
            "allocated_slots": len(holdings),
            "allocated_weight_sum": float(len(holdings)),
            "allocated_notional_usd": round(sum(float(row.get("allocated_notional_usd") or 0.0) for row in holdings), 8),
            "holdings": holdings,
        }
        summary["accounts"][account_id] = account_summary
        total_candidates += len(candidates)
        total_allocated += len(holdings)
        total_allocated_notional += float(account_summary["allocated_notional_usd"])
    summary["open_answer_backed_candidates"] = total_candidates
    summary["allocated_positions"] = total_allocated
    summary["allocated_notional_usd"] = round(total_allocated_notional, 8)
    return summary


def _maybe_log_and_open(
    *,
    account: dict[str, Any],
    scenario: dict[str, Any],
    status: Any,
    settings: dict[str, Any],
    quote: tuple[float, float, float, float],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    inputs: dict[str, Any],
) -> bool:
    inputs = dict(inputs)
    inputs["decision_wall_utc"] = float(inputs.get("decision_wall_utc") or time.time())
    side = status.trade_option_side or status.pressure_watch_direction
    bid, ask, mid, _ts = quote
    fill = float((ask if side == "buy" else bid) if side in ("buy", "sell") else 0.0) or float(mid)
    planned = float(settings.get("initial_bank_usd") or 10000.0) * float(scenario.get("notional_pct_bank") or 0.0)
    if side not in {"buy", "sell"}:
        _append_opportunity(_opportunity_row(
            decision="skipped", reason="no_trade_side", status=status, scenario=scenario,
            settings=settings, inputs=inputs, fill_price=fill,
        ))
        return False
    if bool(scenario.get("oracle_winner_admission_required")):
        oracle_match = oracle_winner_trade_memory.match_oracle_winner(
            _opportunity_row(
                decision="candidate",
                reason="oracle_winner_admission_check",
                status=status,
                scenario=scenario,
                settings=settings,
                inputs=inputs,
                planned_notional=planned,
                fill_price=fill,
            ),
            scenario,
        )
        if not oracle_match:
            _append_opportunity(_opportunity_row(
                decision="skipped", reason="oracle_winner_list_no_match", status=status, scenario=scenario,
                settings=settings, inputs=inputs, planned_notional=planned, fill_price=fill,
            ))
            return False
        inputs["oracle_winner_match"] = oracle_match
        inputs["oracle_winner_bank_entry_quality"] = _oracle_winner_quality_from_match(oracle_match, scenario)
        bank_shadow_reason = _bank_entry_shadow_reason_for_status(status, scenario)
        if bank_shadow_reason:
            inputs["bank_entry_shadow_reason"] = bank_shadow_reason
            inputs["oracle_bank_shadow_reason"] = bank_shadow_reason
    blocker = scenario_blocker(scenario, status)
    if not blocker:
        blocker = account_daily_limit_blocker(account, status, scenario)
    if blocker:
        _append_opportunity(_opportunity_row(
            decision="blocked", reason=blocker, status=status, scenario=scenario,
            settings=settings, inputs=inputs, planned_notional=planned, fill_price=fill,
        ))
        return False
    rotation, position_components = _maybe_rotate_to_best_position(
        account,
        scenario,
        status,
        settings,
        inputs,
        quotes,
        side,
    )
    if rotation:
        _append_opportunity(_opportunity_row(
            decision="rotated",
            reason=ROTATION_CLOSE_REASON,
            status=status,
            scenario=scenario,
            settings=settings,
            inputs=inputs,
            planned_notional=planned,
            fill_price=fill,
            position_rotation=rotation,
        ))
    execution_venue = str(status.venue or "")
    venue_bank_usd = _venue_bank_equity_for(account, settings, execution_venue)
    bank_slot_available = venue_bank_usd > 0.0 and not _open_bank_allocated_trades(account, execution_venue)
    quality = inputs.get("oracle_winner_bank_entry_quality") if isinstance(inputs.get("oracle_winner_bank_entry_quality"), dict) else {}
    bank_quality_eligible = bool(quality.get("bank_quality_eligible", False))
    bank_shadow_reason = str(inputs.get("bank_entry_shadow_reason") or inputs.get("oracle_bank_shadow_reason") or "")
    before = len(account["trades"])
    inputs["opened_wall_utc"] = float(inputs.get("opened_wall_utc") or inputs["decision_wall_utc"])
    maybe_open(account, scenario, status, settings, quote, quotes, inputs)
    opened = account["trades"][before:]
    if opened:
        trade = opened[-1]
        trade["source"] = "live_replay_mock_scenario"
        trade["cell_id"] = trade.get("cell_id") or f"live_replay_{scenario.get('id')}_{status.asset}_{status.venue}_{_live_cell_suffix(inputs)}"
        trade["position_manager_version"] = POSITION_MANAGER_VERSION
        trade["best_position_score"] = float(position_components["score"])
        trade["best_position_score_components"] = dict(position_components)
        _stamp_oracle_winner_quality(trade, quality)
        if bank_shadow_reason:
            trade["bank_entry_shadow_reason"] = bank_shadow_reason
            trade["oracle_bank_shadow_reason"] = bank_shadow_reason
        if bank_slot_available and bank_quality_eligible and not bank_shadow_reason:
            _stamp_bank_allocated_trade(
                trade,
                bank_usd=venue_bank_usd,
                venue_starting_bank_usd=_venue_starting_bank(settings, execution_venue),
                score_row={
                    "current_score": float(position_components["score"]),
                    "net_unrealized_bps": 0.0,
                },
            )
            trade["bank_allocation_reason"] = "venue_bank_slot_available_at_open"
        else:
            _stamp_oracle_shadow_trade(trade)
            if bank_shadow_reason:
                trade["bank_allocation_reason"] = bank_shadow_reason
            elif not bank_quality_eligible:
                trade["bank_allocation_reason"] = "oracle_winner_expected_net_bps_per_min_below_bank_min_shadow_only"
            else:
                trade["bank_allocation_reason"] = "venue_bank_slot_occupied_or_empty_shadow_only"
        if rotation:
            trade["opened_after_position_rotation"] = True
            trade["position_rotation"] = dict(rotation)
        _append_opportunity(_opportunity_row(
            decision="opened", reason="opened", status=status, scenario=scenario,
            settings=settings, inputs=inputs, trade=trade, planned_notional=planned, fill_price=fill,
        ))
        return True
    _append_opportunity(_opportunity_row(
        decision="blocked", reason="open_rejected_by_replay_engine", status=status, scenario=scenario,
        settings=settings, inputs=inputs, planned_notional=planned, fill_price=fill,
    ))
    return False


def _prepare_settings(exit_params: Path) -> dict[str, Any]:
    settings = _load_mock_trade_settings(load_exit_params=False)
    settings["enabled"] = True
    settings["backend_controller_enabled"] = False
    settings["initial_bank_usd"] = 10000.0
    settings["min_trade_notional_usd"] = 1.0
    settings["exit_params_path"] = str(exit_params)
    exit_params_map = trade_exit_strategy.load_exit_params(exit_params)
    settings["exit_params_loaded"] = bool(exit_params_map)
    settings["exit_params_map"] = exit_params_map
    source_scenarios = settings.get("scenarios") or [{}]
    base = dict(source_scenarios[0])
    base.update({
        "base_scenario_id": "route_evidence",
        "min_present_score": 0,
        "max_present_score": 100,
        "notional_pct_bank": 1.0,
        "fixed_mock_notional_usd": 10000.0,
        "cooldown_minutes": 0.0,
        "hold_minutes": 10.0,
        "rotation_enabled": False,
        "exit_params_path": str(exit_params),
        "exit_params_loaded": bool(exit_params_map),
        "allow_promoted_context_rerun": False,
    })
    allowed_pressure = list(base.get("allowed_pressure_states") or [])
    if "transition_risk" not in allowed_pressure:
        allowed_pressure.append("transition_risk")
    base["allowed_pressure_states"] = allowed_pressure
    if exit_params_map:
        base["exit_params_map"] = exit_params_map

    historic = dict(base)
    historic.update({
        "id": "historic_parity_live",
        "label": "Historic Parity Live",
        "requested_strategy_families": list(HISTORIC_PARITY_FAMILIES),
        "allow_context_probes": False,
        "allow_promoted_context_rerun": False,
        "disable_oracle_distilled_context": True,
        "exact_context_routing_only": True,
        "ignore_daily_news_blockers": False,
        "enforce_bucket_health": True,
        "enforce_daily_limits": True,
        "best_position_rotation_enabled": False,
        "historic_parity_exit_selector_enabled": True,
        "counterfactual_exit_selector_enabled": True,
        "counterfactual_exit_selector_min_count": 3,
        "counterfactual_exit_selector_allowed_horizons_minutes": [10, 30, 60, 120, 240, 360],
        "counterfactual_exit_selector_defer_hard_exits": True,
        "counterfactual_exit_selector_blocks_rotation": True,
        "counterfactual_exit_selector_policy_epoch_only": True,
        "counterfactual_exit_selector_allow_policy_source_fallback": True,
        "counterfactual_exit_selector_min_net_usd_at_target_notional": 0.0,
        "counterfactual_exit_selector_min_win_rate": 0.45,
        "counterfactual_exit_selector_min_close_net_bps": 0.0,
        "oracle_parity_executable_ledger_enabled": True,
        "oracle_parity_executable_horizons_minutes": [10, 30, 60, 120, 240, 360],
        "oracle_winner_admission_required": True,
        "oracle_winner_source_of_truth_enabled": True,
        "oracle_winner_exact_entry_required": True,
        "oracle_winner_proven_entries_only": True,
        "oracle_winner_min_count": 1,
        "oracle_winner_min_avg_net_bps": 0.0,
        "oracle_winner_min_bank_entry_net_bps_per_min": ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS_PER_MIN,
        "oracle_winner_below_min_quality_shadow_only": True,
        "oracle_bank_no_side_context_shadow_only": True,
        "oracle_bank_require_live_trade_shape": True,
        "oracle_bank_progress_exit_enabled": True,
        "oracle_bank_fee_cover_cut_minutes": 15.0,
        "oracle_bank_min_net_bps_per_min_after_minutes": 15.0,
        "oracle_bank_min_net_bps_per_min": 0.10,
        "oracle_bank_profit_confirm_bps": 20.0,
        "oracle_bank_profit_confirm_minutes": 30.0,
        "oracle_bank_peak_exit_enabled": True,
        "oracle_bank_peak_exit_min_net_bps": 20.0,
        "oracle_bank_peak_exit_giveback_bps": 12.0,
        "oracle_bank_peak_exit_giveback_fraction": 0.25,
        "oracle_winner_match_levels": ["entry"],
        "disable_family_exit_pairing": True,
        "fixed_mock_notional_usd": 10000.0,
        "notional_pct_bank": 1.0,
    })

    evolve = dict(base)
    evolve.update({
        "id": "evolve_live",
        "label": "Evolve / Oracle Live",
        "requested_strategy_families": list(EVOLVE_LIVE_FAMILIES),
        "allow_context_probes": False,
        "allow_promoted_context_rerun": False,
        "disable_oracle_distilled_context": False,
        "exact_context_routing_only": False,
        "ignore_daily_news_blockers": True,
        "enforce_bucket_health": False,
        "enforce_daily_limits": False,
        "best_position_rotation_enabled": False,
        "best_position_min_score_advantage": 15.0,
        "best_position_max_replaced_net_bps": 0.0,
        "historic_parity_exit_selector_enabled": False,
        "counterfactual_exit_selector_enabled": True,
        "counterfactual_exit_selector_min_count": 3,
        "counterfactual_exit_selector_allowed_horizons_minutes": [10, 30, 60, 120, 240, 360],
        "counterfactual_exit_selector_defer_hard_exits": True,
        "counterfactual_exit_selector_blocks_rotation": True,
        "counterfactual_exit_selector_policy_epoch_only": True,
        "counterfactual_exit_selector_allow_policy_source_fallback": True,
        "counterfactual_exit_selector_min_net_usd_at_target_notional": 0.0,
        "counterfactual_exit_selector_min_win_rate": 0.45,
        "counterfactual_exit_selector_min_close_net_bps": 0.0,
        "oracle_parity_executable_ledger_enabled": True,
        "oracle_parity_executable_horizons_minutes": [10, 30, 60, 120, 240, 360],
        "oracle_winner_admission_required": True,
        "oracle_winner_source_of_truth_enabled": True,
        "oracle_winner_exact_entry_required": True,
        "oracle_winner_proven_entries_only": True,
        "oracle_winner_min_count": 1,
        "oracle_winner_min_avg_net_bps": 0.0,
        "oracle_winner_min_bank_entry_net_bps_per_min": ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS_PER_MIN,
        "oracle_winner_below_min_quality_shadow_only": True,
        "oracle_bank_no_side_context_shadow_only": True,
        "oracle_bank_require_live_trade_shape": True,
        "oracle_bank_progress_exit_enabled": True,
        "oracle_bank_fee_cover_cut_minutes": 15.0,
        "oracle_bank_min_net_bps_per_min_after_minutes": 15.0,
        "oracle_bank_min_net_bps_per_min": 0.10,
        "oracle_bank_profit_confirm_bps": 20.0,
        "oracle_bank_profit_confirm_minutes": 30.0,
        "oracle_bank_peak_exit_enabled": True,
        "oracle_bank_peak_exit_min_net_bps": 20.0,
        "oracle_bank_peak_exit_giveback_bps": 12.0,
        "oracle_bank_peak_exit_giveback_fraction": 0.25,
        "oracle_winner_match_levels": ["entry"],
        "fixed_mock_notional_usd": 10000.0,
        "notional_pct_bank": 1.0,
    })
    settings["scenarios"] = [historic, evolve]
    for scenario in settings["scenarios"]:
        scenario["exit_params_path"] = str(exit_params)
        scenario["exit_params_loaded"] = bool(exit_params_map)
        if exit_params_map:
            scenario["exit_params_map"] = exit_params_map
    settings["strategy_attempt_run_dir"] = str(DEFAULT_OUT)
    settings["live_mock_context_probes_enabled"] = False
    return settings


def run(args: argparse.Namespace) -> None:
    reset_strategy_debug()
    OPEN_DEBUG.clear()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "live_replay_state.json"
    settings = _prepare_settings(Path(args.exit_params))
    state_existed = state_path.exists()
    state = _load_state(state_path, settings["scenarios"])
    epoch = _start_policy_epoch(settings, state)
    accounts = state["accounts"]
    active_ids = {str(scenario.get("id") or "") for scenario in settings["scenarios"] if str(scenario.get("id") or "")}
    retired = state.setdefault("retired_accounts", {})
    for account_id in list(accounts.keys()):
        if account_id not in active_ids:
            retired[account_id] = accounts.pop(account_id)
    for scenario in settings["scenarios"]:
        sid = str(scenario.get("id") or "")
        if not sid:
            continue
        account = accounts.setdefault(sid, {"scenario": scenario, "trades": []})
        account["scenario"] = scenario
        active_epoch_id = str(epoch.get("policy_epoch_id") or "")
        prior_epoch_trades: list[dict[str, Any]] = []
        retained_trades: list[dict[str, Any]] = []
        for trade in account.get("trades") or []:
            if (
                active_epoch_id
                and str(trade.get("policy_epoch_id") or "") != active_epoch_id
                and bool(scenario.get("counterfactual_exit_selector_enabled"))
                and bool(scenario.get("counterfactual_exit_selector_blocks_rotation"))
            ):
                prior_epoch_trades.append(trade)
                continue
            retained_trades.append(trade)
        if prior_epoch_trades:
            retired_id = f"{sid}__closed_before_{active_epoch_id}"
            retired[retired_id] = {
                "scenario": dict(account.get("scenario") or {}, id=retired_id),
                "trades": prior_epoch_trades,
                "retired_reason": "preexisting_trade_before_active_counterfactual_epoch",
                "retired_wall_utc": time.time(),
            }
            account["trades"] = retained_trades
        if bool(scenario.get("counterfactual_exit_selector_enabled")):
            for trade in account.get("trades") or []:
                if trade.get("status") != "open":
                    continue
                stamp_runtime_counterfactual_exit_selection(trade, scenario)
    retired_closed = _retire_prior_epoch_closed_trades(accounts=accounts, state=state, policy_epoch_id=epoch["policy_epoch_id"])
    if retired_closed:
        print(f"[live-replay] retired_prior_epoch_closed_trades={retired_closed}", flush=True)
    state["accounts"] = accounts
    state["live_pnl_guard"] = _apply_live_pnl_guards(
        accounts,
        settings["scenarios"],
        str(settings.get("policy_epoch_id") or ""),
    )
    account_ids = [str(s.get("id") or "") for s in settings["scenarios"] if str(s.get("id") or "")]
    trackers = _load_account_trackers(state, account_ids)
    quotes = _quotes_to_tuple_keys(state.get("quotes") or {})
    state["bank_allocation"] = _apply_bank_allocation(accounts, quotes, settings)
    _save_state(state_path, state)
    seen_chunks = set(state.get("seen_chunks") or [])
    status_count = int(state.get("status_count") or 0)
    last_report = float(state.get("last_report_wall_utc") or 0.0)
    if not state_existed and bool(args.skip_existing_on_start):
        startup_seen, startup_global_start = _latest_chunk_dedupes(
            data_dir,
            synthetic_spread_bps=float(args.synthetic_spread_bps),
            global_start=float(state.get("global_start") or 0.0),
        )
        seen_chunks.update(startup_seen)
        state["seen_chunks"] = sorted(seen_chunks)[-200000:]
        if startup_global_start:
            state["global_start"] = startup_global_start
        state["live_data_only"] = True
        state["skipped_existing_on_start"] = True
        state["startup_skipped_chunks"] = len(startup_seen)
        _save_state(state_path, state)
    print("[live-replay] started historical replay engine on live_data; live-only tail mode", flush=True)
    print(f"[live-replay] policy_epoch={epoch['policy_epoch_id']}", flush=True)
    print(f"[live-replay] trades snapshot: {TRADE_SNAPSHOT}", flush=True)
    while True:
        raw_bars = _load_visible_bars(data_dir)
        all_ts = [float(b.ts) for bars in raw_bars.values() for b in bars]
        if not all_ts:
            time.sleep(float(args.poll_seconds))
            continue
        state["live_pnl_guard"] = _apply_live_pnl_guards(
            accounts,
            settings["scenarios"],
            str(settings.get("policy_epoch_id") or ""),
        )
        global_start = float(state.get("global_start") or 0.0) or min(all_ts)
        state["global_start"] = global_start
        processed = 0
        changed = False
        for (asset, venue), bars in raw_bars.items():
            visible_bars = _recent_tail_bars(bars)
            if not visible_bars:
                continue
            scenario_statuses: list[tuple[str, dict[str, Any], Any, dict[str, Any], tuple[float, float, float, float]]] = []
            bucket_session = session_from_offset_hours((float(bars[-1].ts) - global_start) / 3600.0)
            for scenario in settings["scenarios"]:
                account_id = str(scenario.get("id") or "")
                if not account_id or account_id not in accounts:
                    continue
                tracker = trackers.setdefault(account_id, {})
                status, inputs = current_status_from_visible(
                    asset,
                    venue,
                    visible_bars,
                    tracker,
                    float(args.synthetic_spread_bps),
                    bucket_session,
                    list(scenario.get("requested_strategy_families") or []),
                    bool(scenario.get("allow_context_probes")),
                    bool(scenario.get("allow_promoted_context_rerun")),
                    _strategy_runtime_flags(scenario),
                )
                if status is None:
                    continue
                inputs["bucket_session"] = session_from_offset_hours((float(status.last_update_utc) - global_start) / 3600.0)
                bid = float(status.current_bid or status.current_price or 0.0)
                ask = float(status.current_ask or status.current_price or 0.0)
                mid = float(status.current_price or ((bid + ask) / 2.0) or 0.0)
                quote = (bid, ask, mid, float(status.last_update_utc))
                scenario_statuses.append((account_id, scenario, status, inputs, quote))
            if not scenario_statuses:
                continue
            first_status = scenario_statuses[0][2]
            first_inputs = scenario_statuses[0][3]
            dedupe = _chunk_dedupe_key(asset, venue, first_inputs)
            if not dedupe or dedupe in seen_chunks:
                continue
            seen_chunks.add(dedupe)
            status_count += 1
            processed += 1
            quote = scenario_statuses[0][4]
            quotes[(asset, venue)] = quote
            settings["current_replay_offset_hours"] = (float(first_status.last_update_utc) - global_start) / 3600.0
            for account_id, scenario, status, inputs, quote in scenario_statuses:
                account = accounts[account_id]
                before = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                close_open_for_status(account, scenario, status, quote)
                opened = _maybe_log_and_open(
                    account=account,
                    scenario=scenario,
                    status=status,
                    settings=settings,
                    quote=quote,
                    quotes=quotes,
                    inputs=inputs,
                )
                after = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                changed = changed or opened or before != after
        if processed or changed:
            retired_closed = _retire_prior_epoch_closed_trades(
                accounts=accounts,
                state=state,
                policy_epoch_id=str(settings.get("policy_epoch_id") or ""),
            )
            if retired_closed:
                print(f"[live-replay] retired_prior_epoch_closed_trades={retired_closed}", flush=True)
            state["accounts"] = accounts
            state["trackers"] = _dump_account_trackers(trackers)
            if account_ids:
                state["tracker"] = _tracker_to_string_keys(trackers.get(account_ids[0], {}))
            state["quotes"] = _quotes_to_string_keys(quotes)
            state["seen_chunks"] = sorted(seen_chunks)[-200000:]
            state["status_count"] = status_count
            state["bank_allocation"] = _apply_bank_allocation(accounts, quotes, settings)
            _save_state(state_path, state)
            _rewrite_trade_snapshot(accounts)
            print(f"[live-replay] processed={processed} status_count={status_count}", flush=True)
        now = time.time()
        if now - last_report >= float(args.report_seconds):
            completed_hours = max(0.0, (now - float(state.get("started_wall_utc") or now)) / 3600.0)
            write_replay_outputs(
                output_dir,
                settings,
                _accounts_view_for_policy_epoch(accounts, str(settings.get("policy_epoch_id") or "")),
                requested_hours=completed_hours,
                completed_hours=completed_hours,
                stride_minutes=int(args.stride_minutes),
                status_count=status_count,
                file_stem="live_mock_replay",
                checkpoint=True,
            )
            state["last_report_wall_utc"] = now
            state["bank_allocation"] = _apply_bank_allocation(accounts, quotes, settings)
            last_report = now
            _save_state(state_path, state)
        time.sleep(float(args.poll_seconds))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "live_data"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--exit-params", default=str(DEFAULT_EXIT_PARAMS))
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--report-seconds", type=float, default=3600.0)
    parser.add_argument("--stride-minutes", type=int, default=15)
    parser.add_argument("--synthetic-spread-bps", type=float, default=2.0)
    parser.add_argument("--skip-existing-on-start", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    _run_startup_preflight("live_mock_trade_replay")
    run(args)


if __name__ == "__main__":
    main()
