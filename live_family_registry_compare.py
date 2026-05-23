from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path
from typing import Any

import trade_exit_strategy
from backend.api_server import _load_mock_trade_settings
from live_mock_trade_replay import (
    _json_default,
    _load_visible_bars,
    _quotes_to_string_keys,
    _quotes_to_tuple_keys,
    _save_state,
    _tracker_to_string_keys,
    _tracker_to_tuple_keys,
)
from mock_trade_replay import (
    VENUES,
    account_daily_limit_blocker,
    close_open_for_status,
    current_status_from_visible,
    maybe_open,
    net_unrealized_bps,
    scenario_blocker,
    session_from_offset_hours,
    unrealized_bps,
    write_replay_outputs,
)


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_EXIT_PARAMS = REPO_ROOT / "research" / "strategy_evolution" / "exit_params_h0_h168_v2_promoted_min5.json"
DEFAULT_OUT_ROOT = REPO_ROOT / "research" / "strategy_evolution" / "live_family_registry_compare"
ORACLE_POLICY_EPOCH_VERSION = "oracle_sidecar_answer_backed_v5"
FAMILIES = [
    "SMALL_MOVE_FADE",
    "BUY_UP_CONTINUATION",
    "BUY_FADE",
    "SELL_DOWN_CONTINUATION",
    "MEAN_REVERSION_CHOP",
    "NEWS_BREAKOUT",
    "LIQUIDITY_SQUEEZE",
    "VOL_BREAKOUT",
    "BASIS_DISLOCATION",
    "RELATIVE_STRENGTH",
]
HYBRID_ENTRIES: list[tuple[str, str, list[str]]] = [
    (
        "hybrid_small_move_fade",
        "Hybrid Small Move Fade",
        ["SMALL_MOVE_FADE", "BUY_FADE", "VOL_BREAKOUT", "BASIS_DISLOCATION"],
    ),
    (
        "hybrid_audit_continuation",
        "Hybrid Audit Continuation",
        ["BUY_UP_CONTINUATION", "SELL_DOWN_CONTINUATION", "VOL_BREAKOUT", "RELATIVE_STRENGTH"],
    ),
    (
        "hybrid_reversal_liquidity",
        "Hybrid Reversal/Liquidity",
        ["BUY_FADE", "MEAN_REVERSION_CHOP", "LIQUIDITY_SQUEEZE"],
    ),
    (
        "hybrid_momentum_breakout",
        "Hybrid Momentum/Breakout",
        ["BUY_UP_CONTINUATION", "SELL_DOWN_CONTINUATION", "VOL_BREAKOUT", "NEWS_BREAKOUT", "RELATIVE_STRENGTH"],
    ),
    (
        "hybrid_basis_relative_value",
        "Hybrid Basis/Relative Value",
        ["BASIS_DISLOCATION", "RELATIVE_STRENGTH"],
    ),
    (
        "hybrid_vol_liquidity",
        "Hybrid Volatility/Liquidity",
        ["VOL_BREAKOUT", "LIQUIDITY_SQUEEZE"],
    ),
    (
        "hybrid_dislocation_squeeze",
        "Hybrid Dislocation/Squeeze",
        ["BASIS_DISLOCATION", "LIQUIDITY_SQUEEZE", "MEAN_REVERSION_CHOP"],
    ),
    (
        "hybrid_directional_pressure",
        "Hybrid Directional Pressure",
        ["VOL_BREAKOUT", "RELATIVE_STRENGTH", "BASIS_DISLOCATION"],
    ),
]
EXIT_VARIANTS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "default_gated",
        "Default gated exits",
        {"exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS},
    ),
    (
        "basis_runner",
        "Basis runner exits",
        {"exit_profile_id": trade_exit_strategy.BASIS_DISLOCATION_RUNNER_EXITS},
    ),
    (
        "liquidity_runner",
        "Liquidity loose runner exits",
        {"exit_profile_id": trade_exit_strategy.LIQUIDITY_SQUEEZE_RUNNER_EXITS},
    ),
    (
        "meanrev_tight",
        "Mean reversion tight exits",
        {"exit_profile_id": trade_exit_strategy.MEAN_REVERSION_CHOP_TIGHT_EXITS},
    ),
    (
        "fast_scalp",
        "Fast scalp exits",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "hold_minutes": 5,
            "stop_loss_bps": 6.0,
            "take_profit_bps": 10.0,
            "score_exit_min_hold_minutes": 5.0,
            "score_exit_min_profit_bps": 6.0,
            "tp1_bps": 8.0,
            "scale_out_fraction": 0.5,
            "runner_trail_bps": 6.0,
            "max_hold_minutes": 30.0,
        },
    ),
    (
        "wide_runner",
        "Wide runner exits",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "hold_minutes": 20,
            "stop_loss_bps": 12.0,
            "take_profit_bps": 30.0,
            "score_exit_min_hold_minutes": 10.0,
            "score_exit_min_profit_bps": 12.0,
            "tp1_bps": 16.0,
            "scale_out_fraction": 0.33,
            "runner_trail_bps": 14.0,
            "max_hold_minutes": 120.0,
        },
    ),
    (
        "pressure_hold_gated",
        "Pressure-flip tolerant gated exits",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "defer_unprofitable_pressure_exits": True,
            "hold_minutes": 20,
            "stop_loss_bps": 12.0,
            "take_profit_bps": 24.0,
            "score_exit_min_hold_minutes": 15.0,
            "score_exit_min_profit_bps": 12.0,
            "max_hold_minutes": 90.0,
        },
    ),
    (
        "pressure_hold_runner",
        "Pressure-flip tolerant runner exits",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "defer_unprofitable_pressure_exits": True,
            "hold_minutes": 20,
            "stop_loss_bps": 12.0,
            "take_profit_bps": 30.0,
            "score_exit_min_hold_minutes": 15.0,
            "score_exit_min_profit_bps": 12.0,
            "tp1_bps": 16.0,
            "scale_out_fraction": 0.33,
            "runner_trail_bps": 12.0,
            "max_hold_minutes": 120.0,
        },
    ),
    (
        "hard_tp_sl",
        "Hard TP/SL quick exits",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "hold_minutes": 8,
            "stop_loss_bps": 8.0,
            "take_profit_bps": 14.0,
            "score_exit_min_hold_minutes": 999.0,
            "score_exit_min_profit_bps": 999.0,
            "tp1_bps": 0.0,
            "scale_out_fraction": 0.0,
            "runner_trail_bps": 0.0,
            "max_hold_minutes": 45.0,
        },
    ),
    (
        "buy_up_fast_fail_runner",
        "Buy-up fast-fail partial runner",
        {
            "exit_profile_id": trade_exit_strategy.BUY_UP_CONTINUATION_FAST_FAIL_EXITS,
            "hold_minutes": 6,
            "stop_loss_bps": 5.0,
            "take_profit_bps": 14.0,
            "early_loss_bps": 3.0,
            "early_loss_after_minutes": 4.0,
            "score_exit_min_hold_minutes": 6.0,
            "score_exit_min_profit_bps": 8.0,
            "profitable_hold_extension_minutes": 24.0,
            "tp1_bps": 9.0,
            "scale_out_fraction": 0.5,
            "runner_trail_bps": 5.0,
            "max_hold_minutes": 35.0,
            "news_can_full_flat_profitable": True,
        },
    ),
    (
        "oracle_p25_60m",
        "Oracle-distilled p25 target, 60m max hold",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "defer_unprofitable_pressure_exits": True,
            "hold_minutes": 60,
            "stop_loss_bps": 12.0,
            "take_profit_bps": 32.0,
            "score_exit_min_hold_minutes": 45.0,
            "score_exit_min_profit_bps": 24.0,
            "tp1_bps": 0.0,
            "scale_out_fraction": 0.0,
            "runner_trail_bps": 0.0,
            "max_hold_minutes": 60.0,
        },
    ),
    (
        "oracle_median_120m",
        "Oracle-distilled median target, 120m max hold",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "defer_unprofitable_pressure_exits": True,
            "hold_minutes": 120,
            "stop_loss_bps": 12.0,
            "take_profit_bps": 56.0,
            "score_exit_min_hold_minutes": 90.0,
            "score_exit_min_profit_bps": 42.0,
            "tp1_bps": 0.0,
            "scale_out_fraction": 0.0,
            "runner_trail_bps": 0.0,
            "max_hold_minutes": 120.0,
        },
    ),
    (
        "oracle_p75_240m_runner",
        "Oracle-distilled p75 target, 240m runner",
        {
            "exit_profile_id": trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "defer_unprofitable_pressure_exits": True,
            "hold_minutes": 240,
            "stop_loss_bps": 14.0,
            "take_profit_bps": 86.0,
            "score_exit_min_hold_minutes": 120.0,
            "score_exit_min_profit_bps": 55.0,
            "tp1_bps": 56.0,
            "scale_out_fraction": 0.5,
            "runner_trail_bps": 18.0,
            "max_hold_minutes": 240.0,
        },
    ),
]


def _run_startup_preflight(source: str) -> None:
    if os.environ.get("MARKETS_SKIP_ORACLE_PREFLIGHT", "").lower() in {"1", "true", "yes"}:
        print(f"[oracle-preflight] {source}: skipped by MARKETS_SKIP_ORACLE_PREFLIGHT", flush=True)
        return
    from oracle_runtime_preflight import run_startup_preflight

    run_startup_preflight(source)


def _prepare_settings(exit_params: Path) -> dict[str, Any]:
    settings = _load_mock_trade_settings(load_exit_params=False)
    settings["enabled"] = True
    settings["backend_controller_enabled"] = False
    settings["initial_bank_usd"] = 1000.0
    settings["min_trade_notional_usd"] = 1.0
    settings["exit_params_path"] = str(exit_params)
    exit_params_map = trade_exit_strategy.load_exit_params(exit_params)
    settings["exit_params_loaded"] = bool(exit_params_map)
    settings["exit_params_map"] = exit_params_map
    settings["strategy_attempt_run_dir"] = str(DEFAULT_OUT_ROOT)
    return settings


def _base_scenario(settings: dict[str, Any]) -> dict[str, Any]:
    for scenario in settings.get("scenarios") or []:
        if str(scenario.get("id") or "") == "route_evidence":
            base = copy.deepcopy(scenario)
            break
    else:
        base = copy.deepcopy((settings.get("scenarios") or [{}])[0])
    base["allow_context_probes"] = True
    base["allow_promoted_context_rerun"] = False
    base["enforce_bucket_health"] = True
    base["enforce_daily_limits"] = False
    base["notional_pct_bank"] = 1.0
    base["fixed_mock_notional_usd"] = 1000.0
    base["exit_params_path"] = str(settings.get("exit_params_path") or "")
    base["exit_params_loaded"] = bool(settings.get("exit_params_loaded"))
    if settings.get("exit_params_map"):
        base["exit_params_map"] = settings["exit_params_map"]
    return base


def _build_accounts(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base = _base_scenario(settings)
    accounts: dict[str, dict[str, Any]] = {}
    variants: list[tuple[str, str, list[str], dict[str, Any]]] = [
        ("family_registry_dispatch", "Family Registry Dispatch", list(FAMILIES), {}),
        (
            "family_registry_no_bucket_guard",
            "Family Registry Dispatch, No Bucket Guard",
            list(FAMILIES),
            {"enforce_bucket_health": False},
        ),
        (
            "family_registry_ignore_stale_news",
            "Family Registry Dispatch, Ignore Stale News",
            list(FAMILIES),
            {"ignore_daily_news_blockers": True},
        ),
        (
            "family_registry_no_bucket_ignore_stale_news",
            "Family Registry Dispatch, No Bucket Guard, Ignore Stale News",
            list(FAMILIES),
            {"enforce_bucket_health": False, "ignore_daily_news_blockers": True},
        ),
        (
            "family_registry_confirmed_only",
            "Family Registry Dispatch, Confirmed Only",
            list(FAMILIES),
            {
                "allowed_trade_states": ["confirmed"],
                "allowed_pressure_states": ["confirmed", "high_priority"],
            },
        ),
        (
            "family_registry_fast_exit",
            "Family Registry Dispatch, Fast Exit",
            list(FAMILIES),
            {
                "enforce_bucket_health": False,
                "ignore_daily_news_blockers": True,
                "hold_minutes": 5,
                "stop_loss_bps": 6.0,
                "take_profit_bps": 10.0,
                "exit_profile_id": "scalp_tp_trail",
                "tp1_bps": 8.0,
                "scale_out_fraction": 0.5,
                "runner_trail_bps": 6.0,
                "max_hold_minutes": 30.0,
            },
        ),
        (
            "family_registry_runner_exit",
            "Family Registry Dispatch, Runner Exit",
            list(FAMILIES),
            {
                "enforce_bucket_health": False,
                "ignore_daily_news_blockers": True,
                "hold_minutes": 15,
                "stop_loss_bps": 10.0,
                "take_profit_bps": 24.0,
                "exit_profile_id": "runner_tp_trail",
                "tp1_bps": 14.0,
                "scale_out_fraction": 0.35,
                "runner_trail_bps": 10.0,
                "max_hold_minutes": 90.0,
            },
        ),
    ]
    for family in FAMILIES:
        variants.append((f"family_{family.lower()}", f"Family Shadow: {family}", [family], {}))
        variants.append((
            f"family_{family.lower()}_no_bucket_guard",
            f"Family Shadow: {family}, No Bucket Guard",
            [family],
            {"enforce_bucket_health": False},
        ))
        variants.append((
            f"family_{family.lower()}_no_bucket_ignore_stale_news",
            f"Family Shadow: {family}, No Bucket Guard, Ignore Stale News",
            [family],
            {"enforce_bucket_health": False, "ignore_daily_news_blockers": True},
        ))
    matrix_entries: list[tuple[str, str, list[str]]] = [
        ("matrix_registry", "Matrix Registry", list(FAMILIES)),
        *[
            (f"matrix_{family.lower()}", f"Matrix {family}", [family])
            for family in FAMILIES
        ],
        *[
            (f"matrix_{hybrid_id}", f"Matrix {hybrid_label}", families)
            for hybrid_id, hybrid_label, families in HYBRID_ENTRIES
        ],
    ]
    for entry_id, entry_label, requested in matrix_entries:
        for exit_id, exit_label, exit_overrides in EXIT_VARIANTS:
            variants.append((
                f"{entry_id}__exit_{exit_id}",
                f"{entry_label} x {exit_label}",
                requested,
                {
                    "enforce_bucket_health": False,
                    "ignore_daily_news_blockers": True,
                    "exit_variant_id": exit_id,
                    "exit_variant_label": exit_label,
                    **exit_overrides,
                },
            ))
    for scenario_id, label, requested, overrides in variants:
        scenario = copy.deepcopy(base)
        scenario["id"] = scenario_id
        scenario["base_scenario_id"] = "route_evidence"
        scenario["label"] = label
        scenario["requested_strategy_families"] = requested
        scenario.update(overrides)
        accounts[scenario["id"]] = {"scenario": scenario, "trades": []}
        if scenario_id.startswith("matrix_"):
            for side in ("buy", "sell"):
                side_scenario = copy.deepcopy(scenario)
                side_scenario["id"] = f"{scenario_id}__side_{side}"
                side_scenario["label"] = f"{label}, {side.title()} Probe"
                side_scenario["force_probe_side"] = side
                side_scenario["side_filter"] = side
                accounts[side_scenario["id"]] = {"scenario": side_scenario, "trades": []}
    return accounts


def _opportunity_row(
    *,
    decision: str,
    reason: str,
    account_id: str,
    status: Any,
    scenario: dict[str, Any],
    settings: dict[str, Any],
    inputs: dict[str, Any],
    trade: dict[str, Any] | None = None,
    planned_notional: float = 0.0,
    fill_price: float = 0.0,
) -> dict[str, Any]:
    source_action = str(getattr(status, "trade_strategy_source_queue_action", "") or "")
    resolved_family = str(getattr(status, "trade_strategy_id", "") or "")
    row_ts = float(inputs.get("decision_wall_utc") or time.time())
    return {
        "schema": "live_family_registry_opportunity_v1",
        "source": "live_family_registry_compare",
        "ts_utc": row_ts,
        "policy_epoch_id": str(settings.get("policy_epoch_id") or ""),
        "policy_epoch_version": str(settings.get("policy_epoch_version") or ""),
        "policy_epoch_started_wall_utc": float(settings.get("policy_epoch_started_wall_utc") or 0.0),
        "market_ts_utc": float(inputs.get("chunk_end_ts_utc") or getattr(status, "last_update_utc", 0.0) or 0.0),
        "decision": decision,
        "reason": reason,
        "account_id": account_id,
        "asset": status.asset,
        "venue": status.venue,
        "side": status.trade_option_side or status.pressure_watch_direction,
        "chunk_id": str(inputs.get("chunk_id") or ""),
        "chunk_start_ts_utc": float(inputs.get("chunk_start_ts_utc") or 0.0),
        "chunk_end_ts_utc": float(inputs.get("chunk_end_ts_utc") or getattr(status, "last_update_utc", 0.0) or 0.0),
        "chunk_window": list(getattr(status, "chunk_window", ()) or []),
        "bucket_session": str(inputs.get("bucket_session") or ""),
        "scenario_id": str(scenario.get("id") or ""),
        "scenario_label": str(scenario.get("label") or ""),
        "requested_strategy_families": list(scenario.get("requested_strategy_families") or []),
        "exit_variant_id": str(scenario.get("exit_variant_id") or ""),
        "exit_variant_label": str(scenario.get("exit_variant_label") or ""),
        "exit_profile_id": str(scenario.get("exit_profile_id") or scenario.get("exit_management_model") or ""),
        "notional_pct_bank": float(scenario.get("notional_pct_bank") or 0.0),
        "fixed_mock_notional_usd": float(scenario.get("fixed_mock_notional_usd") or 0.0),
        "initial_bank_usd": float(settings.get("initial_bank_usd") or 10000.0),
        "planned_notional_usd": float(planned_notional or 0.0),
        "fill_price": float(fill_price or 0.0),
        "actual_execution": False,
        "actual_notional": 0.0,
        "learning_capital_model": "full_bank_hypothetical_no_exposure_lock",
        "resolver_id": "EXACT_CONTEXT_RESOLVER" if source_action.startswith("context_routing_") else "",
        "resolver_action": source_action,
        "resolved_strategy_family": resolved_family,
        "trade_strategy_id": resolved_family,
        "trade_strategy_label": status.trade_strategy_label,
        "trade_strategy_confidence": status.trade_strategy_confidence,
        "trade_strategy_variant_id": status.trade_strategy_variant_id,
        "trade_strategy_forced": bool(status.trade_strategy_forced),
        "trade_strategy_reasons": list(status.trade_strategy_reasons),
        "trade_strategy_blockers": list(status.trade_strategy_blockers),
        "trade_strategy_risk_tags": list(status.trade_strategy_risk_tags),
        "trade_option_state": status.trade_option_state,
        "trade_option_profile": status.trade_option_profile,
        "trade_option_readiness": status.trade_option_readiness,
        "trade_option_blockers": list(status.trade_option_blockers),
        "trade_stage": status.trade_stage,
        "trade_present_score": status.trade_present_score,
        "trade_from_onset_bps": status.trade_from_onset_bps,
        "trade_current_chunk_bps": status.trade_current_chunk_bps,
        "trade_recent_2chunk_bps": status.trade_recent_2chunk_bps,
        "pressure_watch_state": status.pressure_watch_state,
        "pressure_watch_direction": status.pressure_watch_direction,
        "regime": status.regime,
        "confidence": status.confidence,
        "adjusted_confidence": status.adjusted_confidence,
        "mean_dipole": status.mean_dipole,
        "opened_trade_intent_id": str((trade or {}).get("intent_id") or ""),
    }


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")


def _is_ignored_blocker(reason: str, scenario: dict[str, Any]) -> bool:
    if not bool(scenario.get("ignore_daily_news_blockers")):
        return False
    text = str(reason or "")
    return "Daily news" in text or "daily news" in text


def _status_for_scenario(status: Any, scenario: dict[str, Any]) -> Any:
    force_side = str(scenario.get("force_probe_side") or "").lower()
    needs_copy = bool(scenario.get("ignore_daily_news_blockers")) or force_side in {"buy", "sell"}
    if not needs_copy:
        return status
    adjusted = copy.copy(status)
    blockers = list(status.trade_option_blockers or [])
    if bool(scenario.get("ignore_daily_news_blockers")):
        blockers = [blocker for blocker in blockers if not _is_ignored_blocker(str(blocker), scenario)]
    if force_side in {"buy", "sell"}:
        adjusted.pressure_watch_direction = force_side
        adjusted.pressure_watch_state = adjusted.pressure_watch_state or "internal"
        adjusted.pressure_watch_label = f"Forced {force_side} matrix probe"
        adjusted.trade_option_side = force_side
        adjusted.trade_option_state = adjusted.trade_option_state or "early_probe"
        adjusted.trade_option_profile = adjusted.trade_option_profile or "practice_probe"
        adjusted.trade_option_readiness = max(int(adjusted.trade_option_readiness or 0), 55)
        blockers = [
            blocker for blocker in blockers
            if "No directional side" not in str(blocker)
            and "Pressure is not visible enough" not in str(blocker)
        ]
    adjusted.trade_option_blockers = blockers
    return adjusted


def _mark_trade_pnl(
    trade: dict[str, Any],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
) -> dict[str, Any]:
    row = dict(trade)
    quote = quotes.get((str(row.get("asset") or ""), str(row.get("venue") or "")))
    if row.get("status") == "open" and quote:
        bid, ask, mid, ts = quote
        u_bps = unrealized_bps(row, bid, ask, mid)
        net_bps = net_unrealized_bps(row, u_bps)
        qty_initial = max(float(row.get("qty_initial") or row.get("qty") or 0.0), 1e-12)
        qty_open = max(float(row.get("qty_open") or row.get("qty") or 0.0), 0.0)
        open_fraction = max(0.0, min(1.0, qty_open / qty_initial))
        open_notional = float(row.get("notional") or 0.0) * open_fraction
        unrealized = open_notional * (float(net_bps) / 10000.0)
        row["mark_bid"] = float(bid)
        row["mark_ask"] = float(ask)
        row["mark_mid"] = float(mid)
        row["mark_ts_utc"] = float(ts)
        row["unrealized_bps"] = round(float(u_bps), 6)
        row["net_unrealized_bps"] = round(float(net_bps), 6)
        row["unrealized_pnl_usd"] = round(float(unrealized), 8)
    else:
        row.setdefault("unrealized_bps", 0.0)
        row.setdefault("net_unrealized_bps", 0.0)
        row.setdefault("unrealized_pnl_usd", 0.0)
    row["mark_to_market_pnl_usd"] = round(
        float(row.get("realized_pnl_usd") or 0.0) + float(row.get("unrealized_pnl_usd") or 0.0),
        8,
    )
    return row


def _write_trade_snapshot(
    path: Path,
    accounts: dict[str, dict[str, Any]],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        for account_id, account in accounts.items():
            for trade in account.get("trades") or []:
                row = _mark_trade_pnl(trade, quotes)
                row["compare_account_id"] = account_id
                f.write(json.dumps(row, default=_json_default) + "\n")
    tmp.replace(path)


def _maybe_log_and_open(
    *,
    account_id: str,
    account: dict[str, Any],
    status: Any,
    settings: dict[str, Any],
    quote: tuple[float, float, float, float],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    inputs: dict[str, Any],
    opportunity_log: Path,
) -> bool:
    inputs = dict(inputs)
    inputs["decision_wall_utc"] = float(inputs.get("decision_wall_utc") or time.time())
    scenario = account["scenario"]
    status = _status_for_scenario(status, scenario)
    side = status.trade_option_side or status.pressure_watch_direction
    bid, ask, mid, _ts = quote
    fill = float((ask if side == "buy" else bid) if side in ("buy", "sell") else 0.0) or float(mid)
    planned = float(scenario.get("fixed_mock_notional_usd") or 0.0) or (
        float(settings.get("initial_bank_usd") or 10000.0) * float(scenario.get("notional_pct_bank") or 0.0)
    )
    if side not in {"buy", "sell"}:
        _append_jsonl(opportunity_log, _opportunity_row(
            decision="skipped", reason="no_trade_side", account_id=account_id, status=status,
            scenario=scenario, settings=settings, inputs=inputs, fill_price=fill,
        ))
        return False
    blocker = scenario_blocker(scenario, status)
    if _is_ignored_blocker(blocker, scenario):
        blocker = ""
    if not blocker:
        blocker = account_daily_limit_blocker(account, status, scenario)
    if blocker:
        _append_jsonl(opportunity_log, _opportunity_row(
            decision="blocked", reason=blocker, account_id=account_id, status=status,
            scenario=scenario, settings=settings, inputs=inputs, planned_notional=planned, fill_price=fill,
        ))
        return False
    before = len(account["trades"])
    inputs["opened_wall_utc"] = float(inputs.get("opened_wall_utc") or inputs["decision_wall_utc"])
    maybe_open(account, scenario, status, settings, quote, quotes, inputs)
    opened = account["trades"][before:]
    if opened:
        trade = opened[-1]
        trade["source"] = "live_family_registry_compare"
        trade["compare_account_id"] = account_id
        trade["actual_execution"] = False
        trade["actual_notional"] = 0.0
        _append_jsonl(opportunity_log, _opportunity_row(
            decision="opened", reason="opened", account_id=account_id, status=status,
            scenario=scenario, settings=settings, inputs=inputs, trade=trade,
            planned_notional=planned, fill_price=fill,
        ))
        return True
    _append_jsonl(opportunity_log, _opportunity_row(
        decision="blocked", reason="open_rejected_by_replay_engine", account_id=account_id,
        status=status, scenario=scenario, settings=settings, inputs=inputs,
        planned_notional=planned, fill_price=fill,
    ))
    return False


def _summarize(
    accounts: dict[str, dict[str, Any]],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    quotes = quotes or {}
    out: dict[str, Any] = {}
    for account_id, account in accounts.items():
        trades = [_mark_trade_pnl(t, quotes) for t in list(account.get("trades") or [])]
        closed = [t for t in trades if t.get("status") == "closed"]
        open_trades = [t for t in trades if t.get("status") == "open"]
        pnl = sum(float(t.get("realized_pnl_usd") or 0.0) for t in closed)
        unrealized = sum(float(t.get("unrealized_pnl_usd") or 0.0) for t in open_trades)
        mtm = pnl + unrealized
        wins = sum(1 for t in closed if float(t.get("realized_pnl_usd") or 0.0) > 0.0)
        out[account_id] = {
            "label": account["scenario"].get("label"),
            "opened": len(trades),
            "closed": len(closed),
            "open": len(open_trades),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": (wins / len(closed)) if closed else None,
            "realized_pnl_usd": round(pnl, 6),
            "open_unrealized_pnl_usd": round(unrealized, 6),
            "mark_to_market_pnl_usd": round(mtm, 6),
            "actual_execution": False,
            "actual_notional": 0.0,
        }
    return out


def _write_progress(
    *,
    run_id: str,
    policy_epoch: dict[str, Any],
    start_wall: float,
    duration_seconds: float,
    run_forever: bool,
    status_count: int,
    seen_chunks: set[str],
    trackers: dict[str, dict[tuple[str, str], dict[str, Any]]],
    quotes: dict[tuple[str, str], tuple[float, float, float, float]],
    accounts: dict[str, dict[str, Any]],
    state_path: Path,
    trade_snapshot: Path,
    summary_path: Path,
) -> None:
    summary = _summarize(accounts, quotes)
    state = {
        "run_id": run_id,
        "active_policy_epoch": dict(policy_epoch),
        "started_wall_utc": start_wall,
        "duration_seconds": duration_seconds,
        "run_forever": run_forever,
        "status_count": status_count,
        "seen_chunks": sorted(seen_chunks),
        "trackers": {k: _tracker_to_string_keys(v) for k, v in trackers.items()},
        "quotes": _quotes_to_string_keys(quotes),
        "summary": summary,
    }
    _save_state(state_path, state)
    _write_trade_snapshot(trade_snapshot, accounts, quotes)
    summary_path.write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    run_id = args.run_id or time.strftime("run_%Y%m%d_%H%M%S_utc", time.gmtime())
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"
    opportunity_log = output_dir / "family_registry_opportunities.jsonl"
    trade_snapshot = output_dir / "family_registry_trades.jsonl"
    summary_path = output_dir / "summary.json"
    settings = _prepare_settings(Path(args.exit_params))
    policy_epoch = {
        "policy_epoch_id": f"{ORACLE_POLICY_EPOCH_VERSION}_{run_id}",
        "policy_epoch_version": ORACLE_POLICY_EPOCH_VERSION,
        "policy_epoch_started_wall_utc": time.time(),
        "answer_backed_routes_forced": True,
        "oracle_setup_blockers_defer": True,
        "oracle_long_hold_enforced": True,
    }
    settings.update(policy_epoch)
    accounts = _build_accounts(settings)
    for account in accounts.values():
        account["scenario"].update(policy_epoch)
    trackers = {account_id: {} for account_id in accounts}
    quotes: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    seen_chunks: set[str] = set()
    status_count = 0
    start_wall = time.time()
    duration_seconds = float(args.duration_seconds)
    run_forever = duration_seconds <= 0.0
    end_wall = None if run_forever else start_wall + duration_seconds
    global_start = 0.0
    last_progress_write = 0.0
    print(f"[family-compare] run_id={run_id}", flush=True)
    print(f"[family-compare] policy_epoch={policy_epoch['policy_epoch_id']}", flush=True)
    print(f"[family-compare] output={output_dir}", flush=True)
    while run_forever or time.time() < end_wall:
        raw_bars = _load_visible_bars(Path(args.data_dir))
        all_ts = [float(b.ts) for bars in raw_bars.values() for b in bars]
        if not all_ts:
            time.sleep(float(args.poll_seconds))
            continue
        global_start = global_start or min(all_ts)
        processed = 0
        changed = False
        for (asset, venue), bars in raw_bars.items():
            session = session_from_offset_hours((float(bars[-1].ts) - global_start) / 3600.0)
            chunk_probe_status, chunk_probe_inputs = current_status_from_visible(
                asset,
                venue,
                bars,
                _tracker_to_tuple_keys({}),
                float(args.synthetic_spread_bps),
                session,
                list(FAMILIES),
                True,
                False,
            )
            if chunk_probe_status is None:
                continue
            chunk_id = str(chunk_probe_inputs.get("chunk_id") or "")
            dedupe = f"{asset}|{venue}|{chunk_id}"
            if not chunk_id or dedupe in seen_chunks:
                continue
            seen_chunks.add(dedupe)
            processed += 1
            status_count += 1
            for account_id, account in accounts.items():
                scenario = account["scenario"]
                tracker = trackers[account_id]
                requested = list(scenario.get("requested_strategy_families") or FAMILIES)
                status, inputs = current_status_from_visible(
                    asset,
                    venue,
                    bars,
                    tracker,
                    float(args.synthetic_spread_bps),
                    session,
                    requested,
                    bool(scenario.get("allow_context_probes")),
                    bool(scenario.get("allow_promoted_context_rerun")),
                )
                if status is None:
                    continue
                inputs["bucket_session"] = session_from_offset_hours((float(status.last_update_utc) - global_start) / 3600.0)
                bid = float(status.current_bid or status.current_price or 0.0)
                ask = float(status.current_ask or status.current_price or 0.0)
                mid = float(status.current_price or ((bid + ask) / 2.0) or 0.0)
                quote = (bid, ask, mid, float(status.last_update_utc))
                quotes[(asset, venue)] = quote
                settings["current_replay_offset_hours"] = (float(status.last_update_utc) - global_start) / 3600.0
                before = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                close_open_for_status(account, scenario, status, quote)
                opened = _maybe_log_and_open(
                    account_id=account_id,
                    account=account,
                    status=status,
                    settings=settings,
                    quote=quote,
                    quotes=quotes,
                    inputs=inputs,
                    opportunity_log=opportunity_log,
                )
                after = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                changed = changed or opened or before != after
                if (opened or before != after) and time.time() - last_progress_write >= 10.0:
                    _write_progress(
                        run_id=run_id,
                        policy_epoch=policy_epoch,
                        start_wall=start_wall,
                        duration_seconds=duration_seconds,
                        run_forever=run_forever,
                        status_count=status_count,
                        seen_chunks=seen_chunks,
                        trackers=trackers,
                        quotes=quotes,
                        accounts=accounts,
                        state_path=state_path,
                        trade_snapshot=trade_snapshot,
                        summary_path=summary_path,
                    )
                    last_progress_write = time.time()
        if processed or changed:
            _write_progress(
                run_id=run_id,
                policy_epoch=policy_epoch,
                start_wall=start_wall,
                duration_seconds=duration_seconds,
                run_forever=run_forever,
                status_count=status_count,
                seen_chunks=seen_chunks,
                trackers=trackers,
                quotes=quotes,
                accounts=accounts,
                state_path=state_path,
                trade_snapshot=trade_snapshot,
                summary_path=summary_path,
            )
            last_progress_write = time.time()
            print(f"[family-compare] processed={processed} status_count={status_count}", flush=True)
        time.sleep(float(args.poll_seconds))
    write_replay_outputs(
        output_dir,
        settings,
        accounts,
        requested_hours=max(0.0, duration_seconds) / 3600.0,
        completed_hours=max(0.0, (time.time() - start_wall) / 3600.0),
        stride_minutes=15,
        status_count=status_count,
        file_stem="family_registry_compare",
        checkpoint=True,
    )
    final = {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "duration_seconds": round(time.time() - start_wall, 3),
        "status_count": status_count,
        "summary": _summarize(accounts, quotes),
        "mock_only": {
            "actual_execution": False,
            "actual_notional": 0.0,
        },
    }
    summary_path.write_text(json.dumps(final, indent=2, default=_json_default), encoding="utf-8")
    print(json.dumps(final, indent=2, default=_json_default), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "live_data"))
    parser.add_argument("--output-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--exit-params", default=str(DEFAULT_EXIT_PARAMS))
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=0.0,
        help="Run duration. Use 0 or a negative value to run continuously.",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--synthetic-spread-bps", type=float, default=2.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    _run_startup_preflight("live_family_registry_compare")
    run(args)


if __name__ == "__main__":
    main()
