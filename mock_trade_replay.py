from __future__ import annotations

import argparse
import sys
import json
import math
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

from backend.api_server import (
    CHUNK_MAX_SIZE,
    CHUNK_MIN_SEGMENT,
    RegimeStatus,
    _apply_pressure_fields,
    _apply_trade_option_fields,
    _default_mock_trade_settings,
    _mock_trade_exposure_cap,
    _present_trade_score,
    _pressure_watch_from_features,
    _signed_bps,
    _trade_option_from_status,
    _trade_score_band,
    _trade_stage_from_age,
)
from backend.forward_paper import _PRACTICE_FEE_BPS
from markets_adapter import MarketChunker, MarketChunkEncoder
from phase1_5_evaluator import classify_regime, load_bars
from regime_classifier import apply_herd_persistence, baselines_from_corpus
from high_conviction_ticket import build_high_conviction_ticket
from daily_limits import build_daily_tracker, daily_limit_health, load_daily_limits
from dipole_coupling import build_dipole_coupling
from strategy_bucket_stats import (
    bucket_health,
    bucket_id_for_trade,
    load_thresholds,
    profit_R_for_trade,
    session_from_offset_hours,
    write_bucket_stats,
    write_venue_stats,
)
from strategy_switcher import DISABLED_STRATEGIES, NO_TRADE
from strategy_library import reset_strategy_debug, strategy_debug_snapshot
from strategy_family_evolution import record_trade_attempt_open_json, write_evolved_family_jsons
from strategy_refrag_relay import build_refrag_relay
import trade_exit_strategy
import oracle_winner_trade_memory

OPEN_DEBUG: dict[str, int] = {}


VENUES = {
    "BTC": {
        "Coinbase": "btc_coinbase_bins.json",
        "Kraken": "btc_kraken_bins.json",
        "Bybit": "btc_bybit_perp_bins.json",
    },
    "ETH": {
        "Coinbase": "eth_coinbase_bins.json",
        "Kraken": "eth_kraken_bins.json",
        "Bybit": "eth_bybit_perp_bins.json",
    },
}


def scenario_blocker(scenario: dict[str, Any], status: RegimeStatus) -> str:
    side_filter = str(scenario.get("side_filter") or "both")
    side = status.trade_option_side or status.pressure_watch_direction
    if side_filter in {"buy", "sell"} and side != side_filter:
        return "side_not_allowed"
    if bool(getattr(status, "trade_strategy_forced", False)):
        return ""
    blocked_sides = {str(x).lower() for x in scenario.get("blocked_sides") or []}
    if str(side).lower() in blocked_sides:
        return "side_blocked_by_live_pnl_guard"
    blocked_strategy_sides = {str(x).lower() for x in scenario.get("blocked_strategy_sides") or []}
    strategy_side_key = f"{str(status.trade_strategy_id or '').upper()}:{str(side).lower()}".lower()
    if strategy_side_key in blocked_strategy_sides:
        return "strategy_side_blocked_by_live_pnl_guard"
    if bool(scenario.get("block_kraken_buys")) and status.venue == "Kraken" and side == "buy":
        return "kraken_buys_blocked"
    blocked_venue_sides = {
        str(x).lower()
        for x in scenario.get("blocked_venue_sides") or []
    }
    venue_side_key = f"{str(status.venue).lower()}:{str(side).lower()}"
    if venue_side_key in blocked_venue_sides:
        return "venue_side_blocked"
    score = int(status.trade_present_score or status.trade_option_readiness or 0)
    min_score = int(scenario.get("min_present_score") or 0)
    if side == "buy":
        min_score += int(scenario.get("buy_score_premium") or 0)
    strategy_min_scores = {
        str(k).upper(): int(v)
        for k, v in (scenario.get("strategy_min_scores") or {}).items()
    }
    strategy_id = str(status.trade_strategy_id or NO_TRADE).upper()
    if strategy_id in DISABLED_STRATEGIES:
        return "strategy_disabled_globally"
    if strategy_id == NO_TRADE:
        return "strategy_no_trade"
    if bool(scenario.get("enforce_bucket_health")):
        ticket = status.high_conviction_ticket or {}
        bucket = ((ticket.get("strategy") or {}).get("bucket") or {})
        bucket_state = str(bucket.get("state") or "").lower()
        if bucket_state in {"hard_kill", "kill"}:
            return f"bucket_{bucket_state}"
        if bucket_state == "paper_only":
            return "bucket_paper_only"
    if strategy_id in strategy_min_scores:
        min_score = max(min_score, int(strategy_min_scores[strategy_id]))
    if score < min_score:
        return "score_below_scenario"
    if score > int(scenario.get("max_present_score") or 100):
        return "score_above_scenario"
    if status.trade_stage not in set(scenario.get("allowed_stages") or []):
        return "stage_not_allowed"
    if status.trade_option_state not in set(scenario.get("allowed_trade_states") or []):
        return "state_not_allowed"
    if status.pressure_watch_state not in set(scenario.get("allowed_pressure_states") or []):
        return "pressure_not_allowed"
    allowed_strategies = {str(x).upper() for x in scenario.get("allowed_strategies") or []}
    disabled_strategies = {str(x).upper() for x in scenario.get("disabled_strategies") or []}
    if allowed_strategies and strategy_id not in allowed_strategies:
        return "strategy_not_allowed"
    if strategy_id in disabled_strategies:
        return "strategy_disabled"
    if bool(scenario.get("require_news_alignment")):
        news_ctx = status.daily_news_context or {}
        dipole = float(news_ctx.get("news_dipole") or 0.0)
        min_abs = float(scenario.get("news_alignment_min_abs_dipole") or 0.0)
        if abs(dipole) >= min_abs:
            news_side = "buy" if dipole > 0 else "sell"
            if side != news_side:
                return "news_dipole_not_aligned"
    for blocker in status.trade_option_blockers or []:
        text = str(blocker)
        if text.startswith("Present score below") and int(scenario.get("min_present_score") or 0) < 55:
            continue
        if any(token in text for token in (
            "Daily news",
            "daily news",
            "Security/exploit narrative",
            "requires stronger market confirmation",
            "news bias conflicts",
        )):
            if bool(scenario.get("ignore_daily_news_blockers")) and any(token in text for token in (
                "Daily news",
                "daily news",
                "news bias conflicts",
                "requires stronger market confirmation",
            )):
                continue
            return text
        if any(token in text for token in (
            "No usable bid/ask spread",
            "Spread too wide",
            "No traded volume",
            "late-stage",
            "Very hot onset",
            "no longer advancing",
        )):
            return text
    return ""


def _debug_block(reason: str) -> None:
    key = str(reason or "unknown")
    OPEN_DEBUG[key] = int(OPEN_DEBUG.get(key, 0)) + 1


def _fallback_practice_side(status: RegimeStatus, inputs: dict[str, Any]) -> str:
    """Infer a side for evidence probes when pressure routing is quiet."""
    side = str(status.trade_option_side or status.pressure_watch_direction or "").lower()
    if side in {"buy", "sell"}:
        return side

    probes = [
        float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0) or 0.0),
        float(inputs.get("signed_move_bps") or 0.0),
        float(inputs.get("trade_current_chunk_bps") or 0.0),
        float(inputs.get("trade_recent_2chunk_bps") or 0.0),
        float(getattr(status, "chunk_buy_volume", 0.0) or 0.0) - float(getattr(status, "chunk_sell_volume", 0.0) or 0.0),
    ]
    for value in probes:
        if value > 0:
            return "buy"
        if value < 0:
            return "sell"
    aggressor = str(getattr(status, "last_aggressor", "") or "").lower()
    if aggressor in {"buy", "sell"}:
        return aggressor
    return "buy"


def account_daily_limit_blocker(account: dict[str, Any], status: RegimeStatus, scenario: dict[str, Any]) -> str:
    if not bool(scenario.get("enforce_daily_limits")):
        return ""
    ticket = status.high_conviction_ticket or {}
    strategy = ticket.get("strategy") or {}
    bucket = (strategy.get("bucket") or {}).get("id")
    family = strategy.get("id") or status.trade_strategy_id
    day = (ticket.get("daily_limits") or {}).get("day")
    if not bucket or not family or not day:
        return ""
    audit = daily_limit_health(
        family=str(family),
        bucket=str(bucket),
        day=str(day),
        tracker=build_daily_tracker(account["trades"]),
        limits=load_daily_limits(str(scenario.get("daily_limits_path") or "daily_limits.json")),
    )
    blockers = audit.get("blockers") or []
    return str(blockers[0]) if blockers else ""


def equity_for(account: dict[str, Any], settings: dict[str, Any]) -> float:
    realized = sum(float(t.get("realized_pnl_usd") or 0.0) for t in account["trades"] if t["status"] == "closed")
    return max(0.0, float(settings["initial_bank_usd"]) + realized)


def _pnl_bank_fraction(trade: dict[str, Any]) -> float:
    notional = float(trade.get("notional") or trade.get("hypothetical_notional") or 0.0)
    allocated = float(trade.get("bank_allocated_notional_usd") or trade.get("real_mock_notional_usd") or 0.0)
    if notional <= 0.0 or allocated <= 0.0:
        return 0.0
    return max(0.0, allocated / notional)


def bank_realized_pnl_for_trade(trade: dict[str, Any]) -> float:
    if trade.get("bank_realized_pnl_usd") is not None:
        return float(trade.get("bank_realized_pnl_usd") or 0.0)
    return float(trade.get("realized_pnl_usd") or 0.0) * _pnl_bank_fraction(trade)


def bank_equity_for(account: dict[str, Any], settings: dict[str, Any]) -> float:
    realized = sum(bank_realized_pnl_for_trade(t) for t in account["trades"] if t["status"] == "closed")
    return max(0.0, float(settings["initial_bank_usd"]) + realized)


def open_exposure(account: dict[str, Any]) -> float:
    return sum(float(t["notional"]) for t in account["trades"] if t["status"] == "open")


def _exit_price_for_trade(trade: dict[str, Any], bid: float, ask: float, mid: float) -> float:
    exit_price = bid if trade["side"] == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    return float(exit_price)


def _append_exit_leg(
    trade: dict[str, Any],
    *,
    leg_type: str,
    reason: str,
    qty: float,
    price: float,
    ts: float,
    gross: float,
    entry_fee_alloc: float,
    exit_fee: float,
    realized: float,
) -> None:
    trade.setdefault("exit_legs", []).append({
        "leg_type": leg_type,
        "reason": reason,
        "qty": round(float(qty), 12),
        "price": round(float(price), 8),
        "ts_utc": float(ts),
        "gross_pnl_usd": round(float(gross), 8),
        "entry_fee_alloc_usd": round(float(entry_fee_alloc), 8),
        "exit_fee_usd": round(float(exit_fee), 8),
        "leg_pnl_usd": round(float(realized), 8),
    })


def _realize_exit_leg(
    trade: dict[str, Any],
    bid: float,
    ask: float,
    mid: float,
    ts: float,
    reason: str,
    leg_type: str,
    qty: float,
) -> bool:
    exit_price = _exit_price_for_trade(trade, bid, ask, mid)
    if exit_price <= 0:
        return False
    fill = float(trade["fill_price"])
    qty = max(0.0, float(qty))
    qty_initial = max(float(trade.get("qty_initial") or trade.get("qty") or 0.0), 1e-12)
    if qty <= 0:
        return False
    signed = 1 if trade["side"] == "buy" else -1
    gross = signed * (exit_price - fill) * qty
    fee_bps = float(trade.get("fee_bps") or _PRACTICE_FEE_BPS)
    exit_fee = exit_price * qty * (fee_bps / 10000.0)
    entry_fee_total = float(trade.get("entry_fees_usd") or 0.0)
    if entry_fee_total <= 0:
        entry_fee_total = float(trade.get("notional") or 0.0) * (fee_bps / 10000.0)
    entry_fee_alloc = entry_fee_total * (qty / qty_initial)
    realized = gross - entry_fee_alloc - exit_fee
    trade["gross_pnl_usd"] = float(trade.get("gross_pnl_usd") or 0.0) + float(gross)
    trade["realized_pnl_usd"] = float(trade.get("realized_pnl_usd") or 0.0) + float(realized)
    trade["fees_usd"] = float(trade["fees_usd"]) + float(exit_fee)
    bank_fraction = _pnl_bank_fraction(trade)
    bank_gross = gross * bank_fraction
    bank_entry_fee_alloc = entry_fee_alloc * bank_fraction
    bank_exit_fee = exit_fee * bank_fraction
    bank_realized = realized * bank_fraction
    trade["bank_gross_pnl_usd"] = float(trade.get("bank_gross_pnl_usd") or 0.0) + float(bank_gross)
    trade["bank_realized_pnl_usd"] = float(trade.get("bank_realized_pnl_usd") or 0.0) + float(bank_realized)
    if trade.get("bank_entry_fees_usd") is None:
        trade["bank_entry_fees_usd"] = float(entry_fee_total) * float(bank_fraction)
    if trade.get("bank_exit_fees_usd") is None:
        trade["bank_exit_fees_usd"] = 0.0
    existing_bank_fees = float(trade.get("bank_fees_usd") or 0.0)
    bank_entry_fees = float(trade.get("bank_entry_fees_usd") or 0.0)
    if existing_bank_fees < bank_entry_fees:
        existing_bank_fees = bank_entry_fees
    trade["bank_exit_fees_usd"] = float(trade.get("bank_exit_fees_usd") or 0.0) + float(bank_exit_fee)
    trade["bank_fees_usd"] = existing_bank_fees + float(bank_exit_fee)
    _append_exit_leg(
        trade,
        leg_type=leg_type,
        reason=reason,
        qty=qty,
        price=exit_price,
        ts=ts,
        gross=gross,
        entry_fee_alloc=entry_fee_alloc,
        exit_fee=exit_fee,
        realized=realized,
    )
    if trade.get("exit_legs"):
        trade["exit_legs"][-1].update({
            "bank_pnl_fraction": round(float(bank_fraction), 8),
            "bank_gross_pnl_usd": round(float(bank_gross), 8),
            "bank_entry_fee_alloc_usd": round(float(bank_entry_fee_alloc), 8),
            "bank_exit_fee_usd": round(float(bank_exit_fee), 8),
            "bank_leg_pnl_usd": round(float(bank_realized), 8),
        })
    return True


def _refresh_scaleout_summary(trade: dict[str, Any]) -> None:
    qty_initial = max(float(trade.get("qty_initial") or trade.get("qty") or 0.0), 1e-12)
    legs = trade.get("exit_legs") or []
    scale_legs = [leg for leg in legs if leg.get("leg_type") == "scale_out"]
    scale_qty = sum(float(leg.get("qty") or 0.0) for leg in scale_legs)
    trade["scale_out_count"] = len(scale_legs)
    trade["scale_out_fraction_realized"] = round(max(0.0, min(1.0, scale_qty / qty_initial)), 6)
    if scale_legs and not trade.get("scale_out_tp1_bps"):
        decision = trade.get("exit_decision") or trade.get("last_exit_decision") or {}
        trade["scale_out_tp1_bps"] = float(decision.get("net_unrealized_bps") or 0.0)


def scale_out_trade(
    trade: dict[str, Any],
    bid: float,
    ask: float,
    mid: float,
    ts: float,
    reason: str,
    fraction: float,
) -> bool:
    if trade["status"] != "open":
        return False
    qty_open = float(trade.get("qty_open") or trade.get("qty") or 0.0)
    leg_qty = qty_open * max(0.0, min(1.0, float(fraction)))
    if leg_qty <= 0 or leg_qty >= qty_open:
        return False
    if not _realize_exit_leg(trade, bid, ask, mid, ts, reason, "scale_out", leg_qty):
        return False
    trade["qty_open"] = max(0.0, qty_open - leg_qty)
    _refresh_scaleout_summary(trade)
    return True


def apply_exit_decision_metadata(trade: dict[str, Any], decision: trade_exit_strategy.ExitDecision) -> None:
    metadata = decision.metadata or {}
    cfg = metadata.get("exit_config") or {}
    if cfg:
        trade["exit_config_level"] = str(cfg.get("config_level") or "")
        trade["exit_config_key"] = str(cfg.get("config_key") or "")
        if cfg.get("hold_minutes") is not None:
            trade["hold_minutes"] = float(cfg.get("hold_minutes") or trade.get("hold_minutes") or 0.0)
        trade["exit_tp1_bps"] = float(cfg.get("tp1_bps") or trade.get("exit_tp1_bps") or 0.0)
        trade["exit_scale_out_fraction"] = float(
            cfg.get("scale_out_fraction") or trade.get("exit_scale_out_fraction") or 0.0
        )
        trade["exit_runner_trail_bps"] = float(cfg.get("trail_bps") or trade.get("exit_runner_trail_bps") or 0.0)
        trade["exit_max_hold_minutes"] = float(cfg.get("max_hold_minutes") or trade.get("exit_max_hold_minutes") or 0.0)
        trade["score_exit_min_profit_bps"] = float(
            cfg.get("min_profit_bps_for_score_exit") or trade.get("score_exit_min_profit_bps") or 0.0
        )
        trade["score_exit_min_hold_minutes"] = float(
            cfg.get("min_hold_minutes") or trade.get("score_exit_min_hold_minutes") or 0.0
        )
    if metadata.get("next_exit_stage"):
        trade["exit_stage"] = str(metadata["next_exit_stage"])
    if metadata.get("mark_under_gate_trim_done"):
        trade["exit_under_gate_trim_done"] = True
    if metadata.get("runner_anchor_net_bps") is not None:
        trade["exit_runner_anchor_net_bps"] = float(metadata["runner_anchor_net_bps"])
    if metadata.get("runner_stop_net_bps") is not None:
        trade["exit_runner_stop_net_bps"] = float(metadata["runner_stop_net_bps"])
    if metadata.get("trail_bps") is not None:
        trade["exit_active_trail_bps"] = float(metadata["trail_bps"])
    if metadata.get("tighten_runner_stop"):
        trade.setdefault("exit_stop_tighten_events", []).append({
            "reason": str(metadata.get("tighten_reason") or decision.reason or ""),
            "elapsed_min": decision.elapsed_min,
            "net_unrealized_bps": decision.net_unrealized_bps,
            "runner_stop_net_bps": float(metadata.get("runner_stop_net_bps") or 0.0),
            "trail_bps": float(metadata.get("trail_bps") or 0.0),
            "aggressive": bool(metadata.get("aggressive")),
        })


def stamp_resolved_exit_profile(trade: dict[str, Any], scenario: dict[str, Any]) -> None:
    profile, cfg = trade_exit_strategy.exit_profile_for_trade(trade, scenario)
    trade["exit_strategy_id"] = profile.profile_id
    trade["exit_strategy_label"] = profile.label
    trade["exit_tp1_bps"] = float(profile.tp1_bps)
    trade["exit_scale_out_fraction"] = float(profile.scale_out_fraction)
    trade["exit_runner_trail_bps"] = float(profile.runner_trail_bps)
    trade["exit_max_hold_minutes"] = float(profile.max_hold_minutes)
    trade["score_exit_min_profit_bps"] = float(profile.score_exit_min_profit_bps)
    trade["score_exit_min_hold_minutes"] = float(profile.score_exit_min_hold_minutes)
    if cfg:
        trade["exit_config_level"] = str(cfg.get("config_level") or "")
        trade["exit_config_key"] = str(cfg.get("config_key") or "")
        if cfg.get("hold_minutes") is not None:
            trade["hold_minutes"] = float(cfg.get("hold_minutes") or trade.get("hold_minutes") or 0.0)


def stamp_runtime_counterfactual_exit_selection(trade: dict[str, Any], scenario: dict[str, Any]) -> None:
    if not bool(scenario.get("counterfactual_exit_selector_enabled")):
        return
    if bool(scenario.get("oracle_winner_source_of_truth_enabled")) and isinstance(trade.get("oracle_winner_match"), dict):
        selection = oracle_winner_trade_memory.exit_selection_from_match(trade.get("oracle_winner_match") or {}, scenario)
        selected_id = str(selection.get("selected_counterfactual_id") or "") if isinstance(selection, dict) else ""
        if selection and selected_id:
            trade["runtime_counterfactual_exit_selection"] = selection
            trade.pop("runtime_counterfactual_exit_selection_status", None)
            ledger = trade.get("rt_executable_exit_ledger")
            if isinstance(ledger, dict):
                ledger["memory_selected_counterfactual_id"] = selected_id
                ledger["memory_selection"] = dict(selection)
                candidate = (ledger.get("candidates") or {}).get(selected_id)
                if isinstance(candidate, dict):
                    candidate["memory_selected"] = True
            return
        trade.pop("runtime_counterfactual_exit_selection", None)
        trade["runtime_counterfactual_exit_selection_status"] = "oracle_winner_match_without_runtime_exit"
        return
    current = trade.get("runtime_counterfactual_exit_selection")
    previous_id = str((current or {}).get("selected_counterfactual_id") or "") if isinstance(current, dict) else ""
    selection = trade_exit_strategy.runtime_counterfactual_exit_selection_for_trade(trade, scenario)
    selected_id = str(selection.get("selected_counterfactual_id") or "") if isinstance(selection, dict) else ""
    if not selection:
        trade.pop("runtime_counterfactual_exit_selection", None)
        trade["runtime_counterfactual_exit_selection_status"] = "no_profitable_policy_candidate"
        selected_id = ""
    else:
        trade["runtime_counterfactual_exit_selection"] = selection
        trade.pop("runtime_counterfactual_exit_selection_status", None)
    ledger = trade.get("rt_executable_exit_ledger")
    if isinstance(ledger, dict):
        ledger["memory_selected_counterfactual_id"] = selected_id
        ledger["memory_selection"] = dict(selection or {}) if isinstance(selection, dict) else {}
        candidates = ledger.get("candidates")
        if isinstance(candidates, dict):
            for candidate in candidates.values():
                if isinstance(candidate, dict):
                    candidate.pop("memory_selected", None)
                    candidate.pop("memory_selection", None)
            if selected_id in candidates and isinstance(candidates.get(selected_id), dict):
                candidates[selected_id]["memory_selected"] = True
                candidates[selected_id]["memory_selection"] = dict(selection)
    if previous_id != selected_id:
        for key in (
            "runtime_counterfactual_first_exit_signal_elapsed_min",
            "runtime_counterfactual_first_exit_signal_reason",
            "runtime_counterfactual_first_exit_signal_profile_id",
            "runtime_counterfactual_fixed_hold_due_elapsed_min",
        ):
            trade.pop(key, None)


def close_trade(trade: dict[str, Any], bid: float, ask: float, mid: float, ts: float, reason: str) -> bool:
    if trade["status"] != "open":
        return False
    exit_price = _exit_price_for_trade(trade, bid, ask, mid)
    if exit_price <= 0:
        return False
    qty_open = float(trade.get("qty_open") or trade.get("qty") or 0.0)
    if not _realize_exit_leg(trade, bid, ask, mid, ts, reason, "final_exit", qty_open):
        return False
    trade["status"] = "closed"
    trade["exit_price"] = float(exit_price)
    trade["exit_ts_utc"] = float(ts)
    trade["qty_open"] = 0.0
    trade["close_reason"] = reason
    trade["runner_exit_reason"] = reason
    trade["bucket_id"] = bucket_id_for_trade(trade)
    trade["profit_R"] = profit_R_for_trade(trade)
    _refresh_scaleout_summary(trade)
    return True


def counterfactual_exit_audit(trade: dict[str, Any], bars: list[Any], horizons_min: tuple[int, ...] = (10, 30, 60)) -> dict[str, Any]:
    if trade.get("status") != "closed":
        return {}
    entry = float(trade.get("fill_price") or 0.0)
    qty = float(trade.get("qty") or 0.0)
    if entry <= 0 or qty <= 0:
        return {}
    side = str(trade.get("side") or "")
    signed = 1 if side == "buy" else -1
    entry_fee = float(trade.get("notional") or 0.0) * (float(trade.get("fee_bps") or _PRACTICE_FEE_BPS) / 10000.0)
    fee_bps = float(trade.get("fee_bps") or _PRACTICE_FEE_BPS)
    exit_ts = float(trade.get("exit_ts_utc") or 0.0)
    actual_net = float(trade.get("realized_pnl_usd") or 0.0)

    def exit_price(bar: Any) -> float:
        px = float((bar.bid if side == "buy" else bar.ask) or 0.0)
        return px if px > 0 else float(bar.close or 0.0)

    def net_at(px: float) -> float:
        gross = signed * (px - entry) * qty
        exit_fee = px * qty * (fee_bps / 10000.0)
        return gross - entry_fee - exit_fee

    out: dict[str, Any] = {
        "actual_net_pnl_usd": round(actual_net, 6),
        "actual_exit_offset_min": 0.0,
        "horizons": {},
    }
    after_exit = [bar for bar in bars if float(bar.ts) > exit_ts]
    for horizon in horizons_min:
        horizon_ts = exit_ts + float(horizon) * 60.0
        window = [bar for bar in after_exit if float(bar.ts) <= horizon_ts]
        if not window:
            continue
        scored = [(net_at(exit_price(bar)), exit_price(bar), float(bar.ts)) for bar in window if exit_price(bar) > 0]
        if not scored:
            continue
        best_net, best_px, best_ts = max(scored, key=lambda row: row[0])
        end_net, end_px, end_ts = scored[-1]
        out["horizons"][f"{horizon}m"] = {
            "best_net_pnl_usd": round(float(best_net), 6),
            "best_incremental_vs_actual_usd": round(float(best_net - actual_net), 6),
            "best_exit_price": round(float(best_px), 8),
            "best_after_actual_exit_min": round((float(best_ts) - exit_ts) / 60.0, 3),
            "horizon_end_net_pnl_usd": round(float(end_net), 6),
            "horizon_end_incremental_vs_actual_usd": round(float(end_net - actual_net), 6),
            "horizon_end_exit_price": round(float(end_px), 8),
            "horizon_end_after_actual_exit_min": round((float(end_ts) - exit_ts) / 60.0, 3),
        }
    return out


def annotate_counterfactual_exits(accounts: dict[str, dict[str, Any]], venue_bars: dict[tuple[str, str], list[Any]]) -> None:
    for account in accounts.values():
        for trade in account["trades"]:
            key = (str(trade.get("asset") or ""), str(trade.get("venue") or ""))
            audit = counterfactual_exit_audit(trade, venue_bars.get(key) or [])
            if audit:
                trade["counterfactual_exit_audit"] = audit


def unrealized_bps(trade: dict[str, Any], bid: float, ask: float, mid: float) -> float:
    return trade_exit_strategy.unrealized_bps(trade, bid, ask, mid)


def net_unrealized_bps(trade: dict[str, Any], unreal_bps: float) -> float:
    return trade_exit_strategy.net_unrealized_bps(trade, unreal_bps)


def _rt_exec_horizons(scenario: dict[str, Any]) -> list[int]:
    raw = scenario.get("oracle_parity_executable_horizons_minutes")
    if raw is None:
        raw = scenario.get("counterfactual_exit_selector_allowed_horizons_minutes")
    values: list[int] = []
    for item in raw or [10, 30, 60]:
        try:
            horizon = int(float(item))
        except (TypeError, ValueError):
            continue
        if horizon > 0 and horizon not in values:
            values.append(horizon)
    return values or [10, 30, 60]


def _rt_exec_exit_price(trade: dict[str, Any], bid: float, ask: float, mid: float) -> float:
    price = bid if str(trade.get("side") or "") == "buy" else ask
    return float(price or 0.0) if float(price or 0.0) > 0 else float(mid or 0.0)


def _rt_exec_candidate_result(
    trade: dict[str, Any],
    *,
    candidate_id: str,
    candidate_class: str,
    horizon_minutes: int,
    start_label: str,
    start_ts: float,
    exit_ts: float,
    bid: float,
    ask: float,
    mid: float,
    target_notional_usd: float,
) -> dict[str, Any]:
    exit_price = _rt_exec_exit_price(trade, bid, ask, mid)
    gross_bps = unrealized_bps(trade, bid, ask, mid)
    net_bps = net_unrealized_bps(trade, gross_bps)
    return {
        "candidate_id": candidate_id,
        "candidate_class": candidate_class,
        "status": "closed",
        "complete": True,
        "horizon_minutes": int(horizon_minutes),
        "start_label": start_label,
        "start_ts_utc": float(start_ts),
        "exit_ts_utc": float(exit_ts),
        "entry_price": float(trade.get("fill_price") or 0.0),
        "exit_price": float(exit_price),
        "gross_bps": round(float(gross_bps), 8),
        "net_bps": round(float(net_bps), 8),
        "net_pnl_usd_at_target_notional": round(float(target_notional_usd) * float(net_bps) / 10000.0, 6),
    }


def initialize_rt_executable_exit_ledger(trade: dict[str, Any], scenario: dict[str, Any]) -> None:
    if not bool(scenario.get("oracle_parity_executable_ledger_enabled")):
        return
    if isinstance(trade.get("rt_executable_exit_ledger"), dict):
        return
    entry_ts = float(trade.get("ts_utc") or trade.get("market_entry_ts_utc") or 0.0)
    target_notional = float(scenario.get("fixed_mock_notional_usd") or trade.get("notional") or 10000.0)
    candidates: dict[str, dict[str, Any]] = {
        "actual_exit::runtime_raw": {
            "candidate_id": "actual_exit::runtime_raw",
            "candidate_class": "actual_exit",
            "status": "open",
            "complete": False,
            "horizon_minutes": 0,
            "start_label": "entry",
            "start_ts_utc": entry_ts,
        }
    }
    for horizon in _rt_exec_horizons(scenario):
        candidate_id = f"fixed_hold_{horizon}m_after_entry"
        candidates[candidate_id] = {
            "candidate_id": candidate_id,
            "candidate_class": "fixed_hold",
            "status": "open",
            "complete": False,
            "horizon_minutes": horizon,
            "start_label": "after_entry",
            "start_ts_utc": entry_ts,
            "due_ts_utc": entry_ts + (float(horizon) * 60.0),
        }
        runtime_id = f"fixed_hold_{horizon}m_after_runtime_exit"
        candidates[runtime_id] = {
            "candidate_id": runtime_id,
            "candidate_class": "fixed_hold",
            "status": "waiting_for_runtime_exit_signal",
            "complete": False,
            "horizon_minutes": horizon,
            "start_label": "after_runtime_exit",
            "start_ts_utc": 0.0,
            "due_ts_utc": 0.0,
        }
    selected = trade.get("runtime_counterfactual_exit_selection")
    selected_id = str((selected or {}).get("selected_counterfactual_id") or "") if isinstance(selected, dict) else ""
    if selected_id and selected_id in candidates:
        candidates[selected_id]["memory_selected"] = True
        candidates[selected_id]["memory_selection"] = dict(selected or {})
    trade["rt_executable_exit_ledger"] = {
        "schema": "rt_oracle_parity_executable_exit_ledger_v1",
        "target_notional_usd": target_notional,
        "horizons_minutes": _rt_exec_horizons(scenario),
        "memory_selected_counterfactual_id": selected_id,
        "memory_selection": dict(selected or {}) if isinstance(selected, dict) else {},
        "candidates": candidates,
        "best_closed_executable": {},
    }


def _rt_exec_refresh_summary(trade: dict[str, Any]) -> None:
    ledger = trade.get("rt_executable_exit_ledger")
    if not isinstance(ledger, dict):
        return
    candidates = ledger.get("candidates")
    if not isinstance(candidates, dict):
        return
    closed = [
        candidate for candidate in candidates.values()
        if isinstance(candidate, dict) and candidate.get("status") == "closed"
    ]
    if not closed:
        ledger["best_closed_executable"] = {}
        ledger["closed_candidate_count"] = 0
        ledger["open_candidate_count"] = sum(
            1 for candidate in candidates.values()
            if isinstance(candidate, dict) and candidate.get("status") != "closed"
        )
        return
    best = max(closed, key=lambda row: float(row.get("net_pnl_usd_at_target_notional") or 0.0))
    ledger["best_closed_executable"] = dict(best)
    ledger["closed_candidate_count"] = len(closed)
    ledger["open_candidate_count"] = sum(
        1 for candidate in candidates.values()
        if isinstance(candidate, dict) and candidate.get("status") != "closed"
    )


def _rt_exec_close_candidate(
    trade: dict[str, Any],
    candidate: dict[str, Any],
    *,
    exit_ts: float,
    bid: float,
    ask: float,
    mid: float,
) -> None:
    ledger = trade.get("rt_executable_exit_ledger") if isinstance(trade.get("rt_executable_exit_ledger"), dict) else {}
    target_notional = float((ledger or {}).get("target_notional_usd") or trade.get("notional") or 10000.0)
    candidate.update(_rt_exec_candidate_result(
        trade,
        candidate_id=str(candidate.get("candidate_id") or ""),
        candidate_class=str(candidate.get("candidate_class") or ""),
        horizon_minutes=int(candidate.get("horizon_minutes") or 0),
        start_label=str(candidate.get("start_label") or ""),
        start_ts=float(candidate.get("start_ts_utc") or 0.0),
        exit_ts=float(exit_ts),
        bid=bid,
        ask=ask,
        mid=mid,
        target_notional_usd=target_notional,
    ))


def update_rt_executable_exit_ledger(
    trade: dict[str, Any],
    scenario: dict[str, Any],
    decision: trade_exit_strategy.ExitDecision | None,
    quote: tuple[float, float, float, float],
) -> None:
    if not bool(scenario.get("oracle_parity_executable_ledger_enabled")):
        return
    initialize_rt_executable_exit_ledger(trade, scenario)
    ledger = trade.get("rt_executable_exit_ledger")
    if not isinstance(ledger, dict):
        return
    candidates = ledger.get("candidates")
    if not isinstance(candidates, dict):
        return
    bid, ask, mid, ts = quote
    ts = float(ts or 0.0)
    raw_action = str(getattr(decision, "action", "") or "")
    raw_reason = str(getattr(decision, "reason", "") or "")
    raw_exit_signal = raw_action in {"close", "scale_out"} and bool(raw_reason)
    if raw_exit_signal and not ledger.get("runtime_exit_signal_ts_utc"):
        ledger["runtime_exit_signal_ts_utc"] = ts
        ledger["runtime_exit_signal_reason"] = raw_reason
        ledger["runtime_exit_signal_action"] = raw_action
        for candidate in candidates.values():
            if not isinstance(candidate, dict) or candidate.get("start_label") != "after_runtime_exit":
                continue
            if candidate.get("status") == "waiting_for_runtime_exit_signal":
                horizon = int(candidate.get("horizon_minutes") or 0)
                candidate["status"] = "open"
                candidate["start_ts_utc"] = ts
                candidate["due_ts_utc"] = ts + (float(horizon) * 60.0)
                candidate["runtime_exit_signal_reason"] = raw_reason
                candidate["runtime_exit_signal_action"] = raw_action
    actual = candidates.get("actual_exit::runtime_raw")
    if raw_action == "close" and raw_reason and isinstance(actual, dict) and actual.get("status") != "closed":
        actual["runtime_exit_signal_reason"] = raw_reason
        _rt_exec_close_candidate(trade, actual, exit_ts=ts, bid=bid, ask=ask, mid=mid)
    for candidate in candidates.values():
        if not isinstance(candidate, dict) or candidate.get("status") != "open":
            continue
        if candidate.get("candidate_class") != "fixed_hold":
            continue
        due_ts = float(candidate.get("due_ts_utc") or 0.0)
        if due_ts > 0 and ts + 1e-9 >= due_ts:
            _rt_exec_close_candidate(trade, candidate, exit_ts=ts, bid=bid, ask=ask, mid=mid)
    for candidate in candidates.values():
        if not isinstance(candidate, dict) or candidate.get("status") == "closed":
            continue
        gross_bps = unrealized_bps(trade, bid, ask, mid)
        net_bps = net_unrealized_bps(trade, gross_bps)
        candidate["mark_ts_utc"] = ts
        candidate["mark_net_bps"] = round(float(net_bps), 8)
        candidate["mark_net_pnl_usd_at_target_notional"] = round(
            float(ledger.get("target_notional_usd") or trade.get("notional") or 10000.0) * float(net_bps) / 10000.0,
            6,
        )
    _rt_exec_refresh_summary(trade)


def profitable_exit_gate_blocks(trade: dict[str, Any], scenario: dict[str, Any], net_bps: float, elapsed_min: float, reason: str) -> bool:
    profile = trade_exit_strategy.exit_profile_from_scenario(scenario)
    signal = trade_exit_strategy.profitable_exit_gate_signal(trade, profile, net_bps, elapsed_min, reason)
    if signal:
        trade.setdefault("deferred_exit_signals", []).append(signal)
        return True
    return False


def invalidation_reason(
    trade: dict[str, Any],
    status: RegimeStatus,
    scenario: dict[str, Any],
    unreal_bps: float,
    elapsed_min: float,
) -> str:
    decision = trade_exit_strategy.decide_trade_exit(
        trade,
        status,
        scenario,
        unreal_bps,
        elapsed_min,
        setup_blocker_reason=scenario_blocker(scenario, status),
    )
    trade["last_exit_decision"] = decision.to_trade_metadata()
    if decision.deferred_signal:
        trade.setdefault("deferred_exit_signals", []).append(decision.deferred_signal)
    return decision.reason if decision.action == "close" else ""


def apply_trade_context(
    tracker: dict[tuple[str, str], dict[str, Any]],
    key: tuple[str, str],
    status: RegimeStatus,
    inputs: dict[str, Any],
) -> None:
    side = status.pressure_watch_direction
    if side not in ("buy", "sell"):
        tracker.pop(key, None)
        return
    chunk_id = str(inputs["chunk_id"])
    start_price = float(inputs.get("chunk_start_price") or 0.0)
    close_price = float(inputs.get("chunk_close_price") or status.current_price or 0.0)
    recent_start = float(inputs.get("recent_2chunk_start_price") or start_price)
    row = tracker.get(key)
    if row is None or row.get("side") != side:
        row = {"side": side, "age_chunks": 0, "onset_price": start_price or close_price, "last_chunk_id": chunk_id}
    elif row.get("last_chunk_id") != chunk_id:
        row["age_chunks"] = int(row.get("age_chunks") or 0) + 1
        row["last_chunk_id"] = chunk_id
    tracker[key] = row
    age = int(row.get("age_chunks") or 0)
    inputs["trade_age_chunks"] = age
    inputs["trade_stage"] = _trade_stage_from_age(age)
    inputs["trade_from_onset_bps"] = _signed_bps(float(row.get("onset_price") or close_price), close_price, side)
    inputs["trade_current_chunk_bps"] = _signed_bps(start_price, close_price, side)
    inputs["trade_recent_2chunk_bps"] = _signed_bps(recent_start, close_price, side)
    inputs["trade_present_score"] = _present_trade_score(status, inputs)
    inputs["trade_score_band"] = _trade_score_band(int(inputs["trade_present_score"]))


def current_status_from_visible(
    asset: str,
    venue: str,
    visible_bars: list,
    tracker: dict[tuple[str, str], dict[str, Any]],
    synthetic_spread_bps: float,
    bucket_session: str = "",
    requested_strategy_families: list[str] | None = None,
    allow_context_probes: bool = False,
    allow_promoted_context_rerun: bool = False,
    strategy_runtime_flags: dict[str, Any] | None = None,
) -> tuple[RegimeStatus | None, dict[str, Any]]:
    chunker = MarketChunker(
        max_window_size=CHUNK_MAX_SIZE,
        stride=CHUNK_MAX_SIZE // 2,
        min_segment=CHUNK_MIN_SEGMENT,
        mode="hybrid",
    )
    chunks = chunker.chunk(f"{venue}-{asset}", visible_bars, multi_signal=True)
    if not chunks:
        return None, {}
    encoder = MarketChunkEncoder(d_enc=64, compute_hawkes=False, compute_hurst=False)
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    results = [classify_regime(f, base) for f in feats]
    apply_herd_persistence(results)
    chunk = chunks[-1]
    feat = feats[-1]
    result = results[-1]
    buy_v = float(sum(b.buy_vol for b in chunk.bars))
    sell_v = float(sum(b.sell_vol for b in chunk.bars))
    last = chunk.bars[-1]
    bid = float(last.bid or 0.0)
    ask = float(last.ask or 0.0)
    if bid <= 0 or ask <= 0:
        half_spread = float(last.close) * (float(synthetic_spread_bps) / 10000.0) / 2.0
        bid = max(0.0, float(last.close) - half_spread)
        ask = float(last.close) + half_spread
    status = RegimeStatus(
        asset=asset,
        venue=venue,
        regime=result.regime.value,
        confidence=float(result.confidence),
        adjusted_confidence=float(result.adjusted_confidence),
        cross_venue_multiplier=float(result.cross_venue_multiplier),
        notes=list(result.notes[:3]),
        mean_dipole=float(feat.mean_dipole),
        realized_vol=float(feat.realized_vol),
        chunk_window=(chunk.window_start, chunk.window_end),
        last_update_utc=float(last.ts),
        current_price=float(last.close),
        current_bid=float(bid),
        current_ask=float(ask),
        last_aggressor=str(last.last_aggressor),
        chunk_buy_volume=buy_v,
        chunk_sell_volume=sell_v,
        chunk_n_trades=int(sum(b.n_trades for b in chunk.bars)),
    )
    prev_feat = feats[-2] if len(feats) >= 2 else None
    inputs = {
        "regime": status.regime,
        "mean_dipole": float(feat.mean_dipole),
        "volume_zscore": float(feat.volume_zscore),
        "dipole_acl1": float(feat.dipole_autocorr_lag1),
        "prev_mean_dipole": float(prev_feat.mean_dipole) if prev_feat is not None else None,
        "chunk_id": chunk.chunk_id,
        "spread_bps": (
            ((status.current_ask - status.current_bid) / max((status.current_ask + status.current_bid) / 2.0, 1e-12) * 10000.0)
            if status.current_ask > 0 and status.current_bid > 0 else 0.0
        ),
        "signed_move_bps": (
            (1 if feat.mean_dipole > 0 else -1)
            * math.log(max(float(chunk.bars[-1].close), 1e-12) / max(float(chunk.bars[0].close), 1e-12))
            * 10000.0
            if feat.mean_dipole != 0 else 0.0
        ),
        "realized_vol_bps": float(feat.realized_vol) * 10000.0,
        "chunk_total_volume": float(feat.chunk_total_volume),
        "chunk_start_ts_utc": float(chunk.bars[0].ts),
        "chunk_end_ts_utc": float(chunk.bars[-1].ts),
        "chunk_start_price": float(chunk.bars[0].close),
        "chunk_close_price": float(chunk.bars[-1].close),
        "recent_2chunk_start_price": float(chunks[-2].bars[0].close) if len(chunks) >= 2 and chunks[-2].bars else float(chunk.bars[0].close),
        "strategy_mode": "practice",
        "bucket_session": str(bucket_session or ""),
        "allow_context_probes": bool(allow_context_probes),
        "allow_promoted_context_rerun": bool(allow_promoted_context_rerun),
        "requested_strategy_families": requested_strategy_families or [
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
        ],
    }
    if strategy_runtime_flags:
        inputs.update(dict(strategy_runtime_flags))
    watch = _pressure_watch_from_features(
        regime=status.regime,
        mean_dipole=float(feat.mean_dipole),
        volume_zscore=float(feat.volume_zscore),
        dipole_acl1=float(feat.dipole_autocorr_lag1),
        prev_mean_dipole=inputs["prev_mean_dipole"],
    )
    _apply_pressure_fields(status, watch)
    apply_trade_context(tracker, (asset, venue), status, inputs)
    if not status.pressure_watch_direction and bool(allow_context_probes):
        status.pressure_watch_direction = _fallback_practice_side(status, inputs)
        status.pressure_watch_state = status.pressure_watch_state or "internal"
        status.pressure_watch_label = status.pressure_watch_label or "Fallback evidence side"
    _apply_trade_option_fields(status, _trade_option_from_status(status, inputs))
    status.high_conviction_ticket = build_high_conviction_ticket(status, inputs, mode="practice")
    return status, inputs


def maybe_rotate(account: dict[str, Any], scenario: dict[str, Any], incoming_status: RegimeStatus,
                 quotes: dict[tuple[str, str], tuple[float, float, float, float]]) -> bool:
    if (
        bool(scenario.get("counterfactual_exit_selector_enabled"))
        and bool(scenario.get("counterfactual_exit_selector_blocks_rotation"))
    ):
        return False
    if not bool(scenario.get("rotation_enabled")):
        return False
    open_trades = [t for t in account["trades"] if t["status"] == "open"]
    if not open_trades:
        return False
    incoming_score = int(incoming_status.trade_present_score or 0)
    rows = []
    for t in open_trades:
        quote = quotes.get((t["asset"], t["venue"]))
        if not quote:
            continue
        bid, ask, mid, ts = quote
        u_bps = unrealized_bps(t, bid, ask, mid)
        rows.append((u_bps, int(t.get("trade_present_score") or 0), t, quote))
    if not rows:
        return False
    rows.sort(key=lambda r: (r[0], r[1]))
    weakest_bps, weakest_score, weakest, quote = rows[0]
    if incoming_score < weakest_score + int(scenario.get("rotation_min_score_advantage") or 10):
        return False
    if weakest_bps > float(scenario.get("rotation_min_underperform_bps", -5.0)):
        return False
    bid, ask, mid, ts = quote
    if close_trade(weakest, bid, ask, mid, ts, "rotation_to_better_performer"):
        weakest["rotation_to_asset"] = incoming_status.asset
        weakest["rotation_to_venue"] = incoming_status.venue
        weakest["rotation_to_score"] = incoming_score
        weakest["rotation_from_unrealized_bps"] = round(float(weakest_bps), 4)
        return True
    return False


def maybe_open(account: dict[str, Any], scenario: dict[str, Any], status: RegimeStatus,
               settings: dict[str, Any], quote: tuple[float, float, float, float],
               quotes: dict[tuple[str, str], tuple[float, float, float, float]],
               inputs: dict[str, Any] | None = None) -> None:
    if not bool(scenario.get("enabled", True)):
        _debug_block("scenario_disabled")
        return
    blocker = scenario_blocker(scenario, status)
    if blocker:
        _debug_block(blocker)
        return
    daily_blocker = account_daily_limit_blocker(account, status, scenario)
    if daily_blocker:
        _debug_block(daily_blocker)
        return
    bid, ask, mid, ts = quote
    side = status.trade_option_side or status.pressure_watch_direction
    fill_price = ask if side == "buy" else bid
    if fill_price <= 0:
        fill_price = mid
    if fill_price <= 0:
        _debug_block("no_fill_price")
        return
    inputs = inputs or {}
    equity = equity_for(account, settings)
    # Learning evidence is sized from the fixed starting bank. Research PnL must not
    # compound into later hypothetical trade size or suppress evidence logging.
    bank = float(settings["initial_bank_usd"])
    min_notional = float(settings["min_trade_notional_usd"])
    notional = bank * float(scenario["notional_pct_bank"])
    if notional < min_notional:
        _debug_block("below_min_notional")
        return
    qty = notional / fill_price
    fee_bps = float(settings.get("mock_fee_bps") or _PRACTICE_FEE_BPS)
    fee = notional * (fee_bps / 10000.0)
    exit_profile = trade_exit_strategy.exit_profile_from_scenario(scenario)
    trade = {
        "asset": status.asset,
        "venue": status.venue,
        "side": side,
        "status": "open",
        "ts_utc": float(ts),
        "opened_wall_utc": float(inputs.get("opened_wall_utc") or inputs.get("decision_wall_utc") or 0.0),
        "policy_epoch_id": str(settings.get("policy_epoch_id") or scenario.get("policy_epoch_id") or ""),
        "policy_epoch_version": str(settings.get("policy_epoch_version") or scenario.get("policy_epoch_version") or ""),
        "policy_epoch_started_wall_utc": float(
            settings.get("policy_epoch_started_wall_utc") or scenario.get("policy_epoch_started_wall_utc") or 0.0
        ),
        "market_entry_ts_utc": float(inputs.get("chunk_end_ts_utc") or ts),
        "chunk_id": str(inputs.get("chunk_id") or ""),
        "chunk_start_ts_utc": float(inputs.get("chunk_start_ts_utc") or 0.0),
        "chunk_end_ts_utc": float(inputs.get("chunk_end_ts_utc") or ts),
        "replay_offset_hours": float(settings.get("current_replay_offset_hours") or 0.0),
        "bucket_session": session_from_offset_hours(float(settings.get("current_replay_offset_hours") or 0.0)),
        "fill_price": float(fill_price),
        "qty": float(qty),
        "qty_initial": float(qty),
        "qty_open": float(qty),
        "notional": float(notional),
        "hypothetical_notional": float(notional),
        "actual_notional": 0.0,
        "actual_execution": False,
        "actual_side": side,
        "learning_capital_model": "full_bank_hypothetical_no_exposure_lock",
        "pnl_accounting_role": "oracle_shadow",
        "pnl_counted_as_real": False,
        "real_mock_notional_usd": 0.0,
        "bank_allocated_notional_usd": 0.0,
        "bank_pnl_weight": 0.0,
        "bank_gross_pnl_usd": 0.0,
        "bank_realized_pnl_usd": 0.0,
        "bank_entry_fees_usd": 0.0,
        "bank_exit_fees_usd": 0.0,
        "bank_fees_usd": 0.0,
        "exit_management_model": exit_profile.profile_id,
        "exit_strategy_id": exit_profile.profile_id,
        "exit_strategy_label": exit_profile.label,
        "score_exit_min_hold_minutes": exit_profile.score_exit_min_hold_minutes,
        "score_exit_min_profit_bps": exit_profile.score_exit_min_profit_bps,
        "profitable_hold_extension_minutes": exit_profile.profitable_hold_extension_minutes,
        "exit_tp1_bps": exit_profile.tp1_bps,
        "exit_scale_out_fraction": exit_profile.scale_out_fraction,
        "exit_runner_trail_bps": exit_profile.runner_trail_bps,
        "exit_max_hold_minutes": exit_profile.max_hold_minutes,
        "suggested_exit_strategy_id": trade_exit_strategy.suggested_exit_profile_id_for_strategy(status.trade_strategy_id),
        "fees_usd": float(fee),
        "entry_fees_usd": float(fee),
        "fee_bps": fee_bps,
        "exit_price": 0.0,
        "exit_ts_utc": 0.0,
        "gross_pnl_usd": 0.0,
        "realized_pnl_usd": 0.0,
        "exit_stage": "stage1",
        "scale_out_count": 0,
        "scale_out_fraction_realized": 0.0,
        "scale_out_tp1_bps": 0.0,
        "runner_exit_reason": "",
        "exit_legs": [],
        "hold_minutes": float(scenario["hold_minutes"]),
        "mock_scenario_id": scenario["id"],
        "mock_scenario_label": scenario["label"],
        "trade_present_score": int(status.trade_present_score),
        "trade_stage": status.trade_stage,
        "trade_from_onset_bps": float(status.trade_from_onset_bps),
        "trade_current_chunk_bps": float(status.trade_current_chunk_bps),
        "trade_recent_2chunk_bps": float(status.trade_recent_2chunk_bps),
        "mean_dipole": float(inputs.get("mean_dipole") or status.mean_dipole or 0.0),
        "dipole_acl1": float(inputs.get("dipole_acl1") or 0.0),
        "volume_zscore": float(inputs.get("volume_zscore") or 0.0),
        "trade_option_state": status.trade_option_state,
        "pressure_watch_state": status.pressure_watch_state,
        "trade_strategy_id": status.trade_strategy_id,
        "trade_strategy_label": status.trade_strategy_label,
        "trade_strategy_mode": str(inputs.get("strategy_mode") or "practice"),
        "trade_strategy_confidence": status.trade_strategy_confidence,
        "trade_strategy_side_override": getattr(status, "trade_strategy_side_override", ""),
        "trade_strategy_reasons": list(status.trade_strategy_reasons),
        "trade_strategy_blockers": list(status.trade_strategy_blockers),
        "trade_strategy_stop_loss_bps": status.trade_strategy_stop_loss_bps,
        "trade_strategy_take_profit_bps": status.trade_strategy_take_profit_bps,
        "trade_strategy_exit_score_drop": status.trade_strategy_exit_score_drop,
        "trade_strategy_forced": bool(getattr(status, "trade_strategy_forced", False)),
        "trade_strategy_variant_id": str(getattr(status, "trade_strategy_variant_id", "") or ""),
        "trade_strategy_risk_tags": list(getattr(status, "trade_strategy_risk_tags", []) or []),
        "trade_strategy_handoff_hint": str(getattr(status, "trade_strategy_handoff_hint", "") or ""),
        "trade_strategy_source_queue_action": str(getattr(status, "trade_strategy_source_queue_action", "") or ""),
        "high_conviction_ticket": dict(status.high_conviction_ticket),
        "daily_news_context": dict(status.daily_news_context),
        "daily_news_status": dict(status.daily_news_status),
        "dipole_coupling": build_dipole_coupling(
            status=status,
            inputs=inputs,
            news_context=status.daily_news_context,
        ).to_dict(),
    }
    oracle_match = inputs.get("oracle_winner_match")
    if isinstance(oracle_match, dict) and oracle_match:
        trade["oracle_winner_source_of_truth"] = True
        trade["oracle_winner_match"] = dict(oracle_match)
    if bool(scenario.get("historic_parity_exit_selector_enabled")):
        trade["historic_parity_exit_selection"] = trade_exit_strategy.historic_parity_exit_selection_for_trade(trade)
    stamp_runtime_counterfactual_exit_selection(trade, scenario)
    stamp_resolved_exit_profile(trade, scenario)
    initialize_rt_executable_exit_ledger(trade, scenario)
    account["trades"].append(trade)
    record_trade_attempt_open_json(
        trade,
        source="mock_trade_replay_open",
        run_id=str(trade.get("cell_id") or trade.get("mock_scenario_id") or "mock_replay_open"),
        run_dir=settings.get("strategy_attempt_run_dir"),
    )


def close_open_for_status(account: dict[str, Any], scenario: dict[str, Any], status: RegimeStatus,
                          quote: tuple[float, float, float, float]) -> None:
    bid, ask, mid, ts = quote
    for t in account["trades"]:
        if t["status"] != "open" or t["asset"] != status.asset or t["venue"] != status.venue:
            continue
        stamp_runtime_counterfactual_exit_selection(t, scenario)
        stamp_resolved_exit_profile(t, scenario)
        elapsed_min = (float(ts) - float(t["ts_utc"])) / 60.0
        u_bps = unrealized_bps(t, bid, ask, mid)
        decision = trade_exit_strategy.decide_trade_exit(
            t,
            status,
            scenario,
            u_bps,
            elapsed_min,
            setup_blocker_reason=scenario_blocker(scenario, status),
        )
        update_rt_executable_exit_ledger(t, scenario, decision, quote)
        if t.get("runtime_counterfactual_exit_selection"):
            decision = trade_exit_strategy.apply_runtime_counterfactual_exit_selector(t, scenario, decision)
        else:
            decision = trade_exit_strategy.apply_historic_parity_exit_selector(t, scenario, decision)
        update_rt_executable_exit_ledger(t, scenario, decision, quote)
        t["last_exit_decision"] = decision.to_trade_metadata()
        t["exit_strategy_id"] = decision.profile_id
        if decision.deferred_signal:
            t.setdefault("deferred_exit_signals", []).append(decision.deferred_signal)
        if decision.action == "scale_out":
            fraction = float((decision.metadata or {}).get("scale_out_fraction") or 0.0)
            t["exit_decision"] = decision.to_trade_metadata()
            if scale_out_trade(t, bid, ask, mid, ts, decision.reason, fraction):
                apply_exit_decision_metadata(t, decision)
            continue
        apply_exit_decision_metadata(t, decision)
        if decision.action == "close" and decision.reason:
            t["exit_decision"] = decision.to_trade_metadata()
            close_trade(t, bid, ask, mid, ts, decision.reason)


def summarize_account(account: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    trades = account["trades"]
    closed = [t for t in trades if t["status"] == "closed"]
    open_ = [t for t in trades if t["status"] == "open"]
    wins = sum(1 for t in closed if float(t["realized_pnl_usd"]) > 0)
    realized = sum(float(t["realized_pnl_usd"]) for t in closed)
    bank_closed = [t for t in closed if _pnl_bank_fraction(t) > 0.0 or float(t.get("bank_realized_pnl_usd") or 0.0) != 0.0]
    bank_wins = sum(1 for t in bank_closed if bank_realized_pnl_for_trade(t) > 0.0)
    bank_realized = sum(bank_realized_pnl_for_trade(t) for t in closed)
    bank_open_allocated = sum(float(t.get("bank_allocated_notional_usd") or 0.0) for t in open_)
    rotations = sum(1 for t in closed if t.get("close_reason") == "rotation_to_better_performer")
    return {
        "scenario_id": account["scenario"]["id"],
        "label": account["scenario"]["label"],
        "rotation_enabled": bool(account["scenario"].get("rotation_enabled")),
        "n_trades": len(trades),
        "n_open": len(open_),
        "n_closed": len(closed),
        "wins": wins,
        "win_rate": round(wins / len(closed), 3) if closed else None,
        "realized_pnl_usd": round(realized, 4),
        "ending_equity_usd": round(equity_for(account, settings), 4),
        "bank_n_open_allocated": sum(1 for t in open_ if float(t.get("bank_allocated_notional_usd") or 0.0) > 0.0),
        "bank_n_closed_counted": len(bank_closed),
        "bank_wins": bank_wins,
        "bank_win_rate": round(bank_wins / len(bank_closed), 3) if bank_closed else None,
        "bank_open_allocated_notional_usd": round(bank_open_allocated, 4),
        "bank_realized_pnl_usd": round(bank_realized, 4),
        "bank_ending_equity_usd": round(bank_equity_for(account, settings), 4),
        "rotations": rotations,
        "avg_trade_pnl_usd": round(mean([float(t["realized_pnl_usd"]) for t in closed]), 4) if closed else 0.0,
        "bank_avg_trade_pnl_usd": round(mean([bank_realized_pnl_for_trade(t) for t in bank_closed]), 4) if bank_closed else 0.0,
    }


def summarize_closed_by_strategy(accounts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for account in accounts.values():
        for trade in account["trades"]:
            if trade.get("status") != "closed":
                continue
            strategy_id = str(trade.get("trade_strategy_id") or NO_TRADE)
            row = rows.setdefault(strategy_id, {
                "strategy_id": strategy_id,
                "label": str(trade.get("trade_strategy_label") or strategy_id),
                "n_closed": 0,
                "wins": 0,
                "realized_pnl_usd": 0.0,
                "bank_realized_pnl_usd": 0.0,
                "bank_counted_closed": 0,
                "forced": 0,
            })
            pnl = float(trade.get("realized_pnl_usd") or 0.0)
            bank_pnl = bank_realized_pnl_for_trade(trade)
            row["n_closed"] += 1
            row["wins"] += 1 if pnl > 0 else 0
            row["realized_pnl_usd"] += pnl
            row["bank_realized_pnl_usd"] += bank_pnl
            row["bank_counted_closed"] += 1 if _pnl_bank_fraction(trade) > 0.0 or bank_pnl != 0.0 else 0
            row["forced"] += 1 if bool(trade.get("trade_strategy_forced")) else 0
    out = []
    for row in rows.values():
        n = int(row["n_closed"])
        row["win_rate"] = round(int(row["wins"]) / n, 3) if n else None
        row["realized_pnl_usd"] = round(float(row["realized_pnl_usd"]), 4)
        row["bank_realized_pnl_usd"] = round(float(row["bank_realized_pnl_usd"]), 4)
        out.append(row)
    out.sort(key=lambda r: (float(r["bank_realized_pnl_usd"]), float(r["realized_pnl_usd"]), int(r["n_closed"])), reverse=True)
    return out


def write_replay_outputs(
    output_dir: Path,
    settings: dict[str, Any],
    accounts: dict[str, dict[str, Any]],
    *,
    requested_hours: float,
    completed_hours: float,
    stride_minutes: int,
    status_count: int,
    file_stem: str = "mock_replay",
    checkpoint: bool = False,
) -> tuple[Path, Path]:
    summaries = [summarize_account(a, settings) for a in accounts.values()]
    strategy_summaries = summarize_closed_by_strategy(accounts)
    strategy_debug = strategy_debug_snapshot()
    open_debug = dict(sorted(OPEN_DEBUG.items(), key=lambda item: int(item[1]), reverse=True))
    all_trades = [t for account in accounts.values() for t in account["trades"]]
    refrag_relay = build_refrag_relay(all_trades, strategy_debug=strategy_debug)
    bucket_stats_path = output_dir / f"{file_stem}_strategy_bucket_stats.json"
    venue_stats_path = output_dir / f"{file_stem}_strategy_venue_stats.json"
    bucket_stats = write_bucket_stats(
        all_trades,
        bucket_stats_path,
        thresholds_path=settings.get("bucket_thresholds_path") or "bucket_thresholds.json",
    )
    venue_stats = write_venue_stats(
        all_trades,
        venue_stats_path,
        venue_prefs_path=settings.get("venue_prefs_path") or "venue_prefs.json",
    )
    summaries.sort(key=lambda r: (r["ending_equity_usd"], r["realized_pnl_usd"]), reverse=True)
    start_hour = float((settings.get("replay_refinements") or {}).get("start_hour") or 0.0)
    payload = {
        "start_hour": start_hour,
        "end_hour": round(start_hour + requested_hours, 4),
        "hours": requested_hours,
        "completed_hours": round(completed_hours, 4),
        "stride_minutes": stride_minutes,
        "status_count": status_count,
        "checkpoint": checkpoint,
        "settings": settings,
        "summaries": summaries,
        "strategy_summaries": strategy_summaries,
        "strategy_debug": strategy_debug,
        "open_debug": open_debug,
        "refrag_relay": refrag_relay,
        "bucket_stats_path": str(bucket_stats_path),
        "bucket_stats": bucket_stats,
        "venue_stats_path": str(venue_stats_path),
        "venue_stats": venue_stats,
        "accounts": {
            sid: {
                "scenario": account["scenario"],
                "trades": account["trades"],
            }
            for sid, account in accounts.items()
        },
    }
    result_path = output_dir / f"{file_stem}_results.json"
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    evolution_write = write_evolved_family_jsons(
        refrag_relay,
        run_dir=output_dir,
        source=str(result_path),
        run_id=file_stem,
    )
    payload["strategy_family_evolution"] = evolution_write
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path = output_dir / f"{file_stem}_report.md"
    title = "Mock Trade Replay Checkpoint" if checkpoint else "Mock Trade Replay Report"
    lines = [
        f"# {title}",
        "",
        f"Window requested: hours {start_hour:g}-{start_hour + requested_hours:g}",
        f"Window completed: hours {start_hour:g}-{start_hour + completed_hours:g}",
        f"Statuses evaluated: {status_count}",
        "",
        "| Scenario | Rotation | Trades | Open | Bank open | Closed | Bank closed | Bank win rate | Bank P&L | Shadow P&L | Bank equity | Rotations |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        bank_win = "n/a" if row["bank_win_rate"] is None else f"{row['bank_win_rate'] * 100:.1f}%"
        lines.append(
            f"| {row['label']} | {row['rotation_enabled']} | {row['n_trades']} | "
            f"{row['n_open']} | {row['bank_n_open_allocated']} | {row['n_closed']} | "
            f"{row['bank_n_closed_counted']} | {bank_win} | ${row['bank_realized_pnl_usd']:.2f} | "
            f"${row['realized_pnl_usd']:.2f} | ${row['bank_ending_equity_usd']:.2f} | {row['rotations']} |"
        )
    if strategy_summaries:
        lines.extend([
            "",
            "## Strategy Summary",
            "",
            "| Strategy | Closed | Bank closed | Forced | Win rate | Bank P&L | Shadow P&L |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in strategy_summaries:
            win = "n/a" if row["win_rate"] is None else f"{row['win_rate'] * 100:.1f}%"
            lines.append(
                f"| {row['label']} | {row['n_closed']} | {row['bank_counted_closed']} | "
                f"{int(row.get('forced') or 0)} | {win} | ${row['bank_realized_pnl_usd']:.2f} | "
                f"${row['realized_pnl_usd']:.2f} |"
            )
    if strategy_debug:
        lines.extend([
            "",
            "## Strategy Debug",
            "",
            "| Strategy | Signals | Top skip reasons |",
            "|---|---:|---|",
        ])
        for strategy_id, counters in sorted(strategy_debug.items()):
            signals = int(counters.get("signals") or 0)
            skips = [
                f"{key}={value}"
                for key, value in sorted(counters.items(), key=lambda item: int(item[1]), reverse=True)
                if key != "signals"
            ][:4]
            lines.append(f"| {strategy_id} | {signals} | {', '.join(skips)} |")
    if open_debug:
        lines.extend([
            "",
            "## Open Debug",
            "",
            "| Reason | Count |",
            "|---|---:|",
        ])
        for reason, count in list(open_debug.items())[:12]:
            lines.append(f"| {reason} | {count} |")
    relay_reports = (refrag_relay.get("family_reports") or {})
    if relay_reports:
        lines.extend([
            "",
            "## Refrag Relay",
            "",
            "| Family | Trades | P&L R | Handoff |",
            "|---|---:|---:|---|",
        ])
        for family, report in sorted(relay_reports.items()):
            lines.append(
                f"| {family} | {int(report.get('trades') or 0)} | "
                f"{float(report.get('pnl_R') or 0.0):.2f} | {str(report.get('handoff_note') or '')} |"
            )
    if payload.get("strategy_family_evolution"):
        evolution = payload["strategy_family_evolution"]
        lines.extend([
            "",
            "## Evolved Family JSON",
            "",
            f"Manifest: `{evolution.get('manifest_path')}`",
        ])
    bucket_rows = list((bucket_stats.get("buckets") or {}).values())
    if bucket_rows:
        bucket_rows.sort(key=lambda r: float(r.get("pnl_usd") or 0.0))
        lines.extend([
            "",
            "## Bucket Health",
            "",
            "| Bucket | State | Trades | Win rate | P&L | P&L R | Reason |",
            "|---|---|---:|---:|---:|---:|---|",
        ])
        for row in bucket_rows[:12]:
            health = row.get("health") or {}
            stats = health.get("stats") or row
            win = stats.get("win_rate")
            win_text = "n/a" if win is None else f"{float(win) * 100:.1f}%"
            reason = "; ".join(health.get("reasons") or [])
            lines.append(
                f"| `{row['bucket_id']}` | {health.get('state', '')} | {int(row.get('trades') or 0)} | "
                f"{win_text} | ${float(row.get('pnl_usd') or 0):.2f} | {float(row.get('pnl_R') or 0):.2f} | {reason} |"
            )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return result_path, report_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=".")
    p.add_argument("--output-dir", default="mock_replay_day1_out")
    p.add_argument("--start-hour", type=float, default=0.0)
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--stride-minutes", type=int, default=15)
    p.add_argument("--disable-pressure-scout", action="store_true")
    p.add_argument("--block-watch", action="store_true")
    p.add_argument("--min-score-floor", type=int, default=0)
    p.add_argument("--side-filter", choices=["both", "buy", "sell"], default="both")
    p.add_argument("--block-kraken-buys", action="store_true")
    p.add_argument("--buy-score-premium", type=int, default=0)
    p.add_argument("--require-news-alignment", action="store_true")
    p.add_argument("--news-alignment-min-abs-dipole", type=float, default=0.25)
    p.add_argument(
        "--allowed-strategies",
        default="",
        help="Comma-separated strategy ids to allow in every scenario.",
    )
    p.add_argument(
        "--disabled-strategies",
        default="",
        help="Comma-separated strategy ids to block in every scenario.",
    )
    p.add_argument(
        "--block-venue-side",
        default="",
        help="Comma-separated venue:side pairs to block, e.g. Coinbase:buy,Bybit:sell.",
    )
    p.add_argument(
        "--strategy-min-score",
        default="",
        help="Comma-separated strategy=min_score overrides, e.g. MEAN_REVERSION_CHOP=45.",
    )
    p.add_argument("--bucket-thresholds", default="bucket_thresholds.json")
    p.add_argument("--venue-prefs", default="venue_prefs.json")
    p.add_argument("--daily-limits", default="daily_limits.json")
    p.add_argument(
        "--enforce-bucket-health",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Block hard-kill/kill/paper-only buckets to simulate product-eligible trades only.",
    )
    p.add_argument(
        "--enforce-daily-limits",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop opening new trades after family or bucket daily R-loss limits are reached.",
    )
    p.add_argument("--early-loss-bps", type=float, default=0.0)
    p.add_argument("--early-loss-after-minutes", type=float, default=3.0)
    p.add_argument(
        "--synthetic-spread-bps",
        type=float,
        default=2.0,
        help="Fallback crossed spread when historical bars lack bid/ask.",
    )
    p.add_argument(
        "--checkpoint-hours",
        type=float,
        default=12.0,
        help="Write checkpoint result/report files every N replay hours. Use 0 to disable.",
    )
    p.add_argument(
        "--disable-news-context",
        action="store_true",
        help="Use no daily news context for historical replay/autoresearch runs.",
    )
    p.add_argument(
        "--exit-params",
        default="exit_params.json",
        help="Bucket/venue/family exit parameter map generated from trade-level counterfactual evidence.",
    )
    p.add_argument(
        "--allow-context-probes",
        action="store_true",
        help="Allow routed practice mode to probe unseen family/context pairs. Leave off for winner-only routed runs.",
    )
    p.add_argument(
        "--allow-promoted-context-rerun",
        action="store_true",
        help="For evidence-mining runs only, allow forced probes to re-sample contexts that already have promoted winners.",
    )
    args = p.parse_args()
    reset_strategy_debug()
    OPEN_DEBUG.clear()

    if args.disable_news_context:
        api_server = sys.modules.get("backend.api_server")
        if api_server is not None:
            api_server._DAILY_NEWS_CONTEXT_PATH = "__mock_replay_news_context_disabled__.json"

    settings = _default_mock_trade_settings()
    exit_params_map = trade_exit_strategy.load_exit_params(args.exit_params)
    refinements = {
        "start_hour": float(args.start_hour),
        "disable_pressure_scout": bool(args.disable_pressure_scout),
        "block_watch": bool(args.block_watch),
        "min_score_floor": int(args.min_score_floor),
        "side_filter": args.side_filter,
        "block_kraken_buys": bool(args.block_kraken_buys),
        "buy_score_premium": int(args.buy_score_premium),
        "require_news_alignment": bool(args.require_news_alignment),
        "news_alignment_min_abs_dipole": float(args.news_alignment_min_abs_dipole),
        "allowed_strategies": [s.strip().upper() for s in args.allowed_strategies.split(",") if s.strip()],
        "disabled_strategies": [s.strip().upper() for s in args.disabled_strategies.split(",") if s.strip()],
        "blocked_venue_sides": [s.strip().lower() for s in args.block_venue_side.split(",") if s.strip()],
        "strategy_min_scores": {
            k.strip().upper(): int(v.strip())
            for item in args.strategy_min_score.split(",")
            if "=" in item
            for k, v in [item.split("=", 1)]
            if k.strip() and v.strip().isdigit()
        },
        "bucket_thresholds_path": args.bucket_thresholds,
        "venue_prefs_path": args.venue_prefs,
        "daily_limits_path": args.daily_limits,
        "enforce_bucket_health": bool(args.enforce_bucket_health),
        "enforce_daily_limits": bool(args.enforce_daily_limits),
        "early_loss_bps": float(args.early_loss_bps),
        "early_loss_after_minutes": float(args.early_loss_after_minutes),
        "exit_params_path": str(args.exit_params),
        "exit_params_loaded": bool(exit_params_map),
        "allow_context_probes": bool(args.allow_context_probes),
    }
    for scenario in settings["scenarios"]:
        base_id = str(scenario.get("base_scenario_id") or scenario.get("id") or "")
        learning_mode = not bool(args.enforce_bucket_health) and not bool(args.enforce_daily_limits)
        if learning_mode:
            scenario["enabled"] = True
            scenario["enforce_bucket_health"] = False
            scenario["enforce_daily_limits"] = False
            scenario["min_present_score"] = 0
            scenario.setdefault("score_exit_min_hold_minutes", 30.0)
            scenario.setdefault("score_exit_min_profit_bps", 20.0)
            scenario.setdefault("profitable_hold_extension_minutes", 60.0)
            scenario["allowed_stages"] = sorted(set(scenario.get("allowed_stages") or []) | {"onset", "early_follow", "mature"})
            scenario["allowed_trade_states"] = sorted(
                set(scenario.get("allowed_trade_states") or []) | {"watch", "early_probe", "confirmed"}
            )
            scenario["allowed_pressure_states"] = sorted(
                set(scenario.get("allowed_pressure_states") or [])
                | {"internal", "forming", "high_priority", "confirmed"}
            )
        if args.disable_pressure_scout and base_id == "pressure_scout":
            scenario["enabled"] = False
        if args.block_watch:
            scenario["allowed_trade_states"] = [
                s for s in (scenario.get("allowed_trade_states") or [])
                if s != "watch"
            ]
        if args.min_score_floor:
            scenario["min_present_score"] = max(
                int(scenario.get("min_present_score") or 0),
                int(args.min_score_floor),
            )
        if args.side_filter != "both":
            scenario["side_filter"] = args.side_filter
        if args.block_kraken_buys:
            scenario["block_kraken_buys"] = True
        if args.buy_score_premium:
            scenario["buy_score_premium"] = int(args.buy_score_premium)
        if args.require_news_alignment:
            scenario["require_news_alignment"] = True
            scenario["news_alignment_min_abs_dipole"] = float(args.news_alignment_min_abs_dipole)
        if refinements["allowed_strategies"]:
            scenario["allowed_strategies"] = list(refinements["allowed_strategies"])
        if refinements["disabled_strategies"]:
            scenario["disabled_strategies"] = list(refinements["disabled_strategies"])
        if refinements["blocked_venue_sides"]:
            scenario["blocked_venue_sides"] = list(refinements["blocked_venue_sides"])
        if refinements["strategy_min_scores"]:
            scenario["strategy_min_scores"] = dict(refinements["strategy_min_scores"])
        if args.enforce_bucket_health:
            scenario["enforce_bucket_health"] = True
        if args.enforce_daily_limits:
            scenario["enforce_daily_limits"] = True
            scenario["daily_limits_path"] = args.daily_limits
        if args.early_loss_bps:
            scenario["early_loss_bps"] = float(args.early_loss_bps)
            scenario["early_loss_after_minutes"] = float(args.early_loss_after_minutes)
        if exit_params_map:
            scenario["exit_params_map"] = exit_params_map
    settings["replay_refinements"] = refinements
    scenarios = settings["scenarios"]
    accounts = {
        s["id"]: {"scenario": s, "trades": []}
        for s in scenarios
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    settings["strategy_attempt_run_dir"] = str(output_dir)
    data_dir = Path(args.data_dir)

    raw_bars: dict[tuple[str, str], list] = {}
    for asset, venues in VENUES.items():
        for venue, filename in venues.items():
            path = data_dir / filename
            if path.exists():
                bars = load_bars(str(path))
                if bars:
                    raw_bars[(asset, venue)] = bars

    all_raw_ts = [b.ts for bars in raw_bars.values() for b in bars]
    if not all_raw_ts:
        raise SystemExit("no bars loaded")
    global_start = min(all_raw_ts)
    start_ts = global_start + float(args.start_hour) * 3600.0
    end_ts = start_ts + float(args.hours) * 3600.0
    venue_bars: dict[tuple[str, str], list] = {
        key: [b for b in bars if start_ts <= b.ts <= end_ts]
        for key, bars in raw_bars.items()
    }
    venue_bars = {key: bars for key, bars in venue_bars.items() if bars}

    tracker: dict[tuple[str, str], dict[str, Any]] = {}
    seen_chunks: set[tuple[str, str, str]] = set()
    quotes: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    step_s = args.stride_minutes * 60.0
    all_ts = [b.ts for bars in venue_bars.values() for b in bars]
    if not all_ts:
        raise SystemExit("no bars loaded")
    t = min(all_ts) + CHUNK_MIN_SEGMENT * 60.0
    start_t = min(all_ts)
    end_t = min(all_ts) + args.hours * 3600.0
    checkpoint_s = max(0.0, float(args.checkpoint_hours) * 3600.0)
    next_checkpoint_t = start_t + checkpoint_s if checkpoint_s > 0 else float("inf")
    status_count = 0
    while t <= end_t:
        settings["current_replay_offset_hours"] = (float(t) - float(global_start)) / 3600.0
        for (asset, venue), bars in venue_bars.items():
            visible = [b for b in bars if b.ts <= t]
            if len(visible) < CHUNK_MIN_SEGMENT:
                continue
            status, inputs = current_status_from_visible(
                asset,
                venue,
                visible,
                tracker,
                args.synthetic_spread_bps,
                session_from_offset_hours((float(t) - float(global_start)) / 3600.0),
                refinements["allowed_strategies"] or None,
                bool(args.allow_context_probes),
                bool(args.allow_promoted_context_rerun),
            )
            if status is None:
                continue
            inputs["bucket_session"] = session_from_offset_hours(
                (float(status.last_update_utc) - float(global_start)) / 3600.0
            )
            status.high_conviction_ticket = build_high_conviction_ticket(status, inputs, mode="practice")
            chunk_id = str(inputs.get("chunk_id") or "")
            dedupe = (asset, venue, chunk_id)
            if dedupe in seen_chunks:
                continue
            seen_chunks.add(dedupe)
            status_count += 1
            bid = status.current_bid or status.current_price
            ask = status.current_ask or status.current_price
            mid = status.current_price or (bid + ask) / 2.0
            quote = (float(bid), float(ask), float(mid), float(status.last_update_utc))
            quotes[(asset, venue)] = quote
            for account in accounts.values():
                scenario = account["scenario"]
                close_open_for_status(account, scenario, status, quote)
                maybe_open(account, scenario, status, settings, quote, quotes, inputs)
        while t >= next_checkpoint_t and next_checkpoint_t < end_t:
            completed_hours = max(0.0, (next_checkpoint_t - start_t) / 3600.0)
            suffix = str(int(round(completed_hours))) if completed_hours.is_integer() else f"{completed_hours:g}"
            result_path, report_path = write_replay_outputs(
                output_dir,
                settings,
                accounts,
                requested_hours=float(args.hours),
                completed_hours=completed_hours,
                stride_minutes=int(args.stride_minutes),
        status_count=status_count,
        file_stem=f"mock_replay_checkpoint_{suffix}h",
        checkpoint=True,
            )
            print(f"wrote checkpoint {result_path}")
            print(f"wrote checkpoint {report_path}")
            next_checkpoint_t += checkpoint_s
        t += step_s

    for (asset, venue), bars in venue_bars.items():
        if not bars:
            continue
        last = bars[-1]
        quote = (
            float(last.bid or last.close),
            float(last.ask or last.close),
            float(last.close),
            float(last.ts),
        )
        for account in accounts.values():
            for trade in account["trades"]:
                if trade["status"] == "open" and trade["asset"] == asset and trade["venue"] == venue:
                    close_trade(trade, *quote, reason="replay_window_end")

    annotate_counterfactual_exits(accounts, venue_bars)

    result_path, report_path = write_replay_outputs(
        output_dir,
        settings,
        accounts,
        requested_hours=float(args.hours),
        completed_hours=float(args.hours),
        stride_minutes=int(args.stride_minutes),
        status_count=status_count,
    )
    print(f"wrote {result_path}")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
