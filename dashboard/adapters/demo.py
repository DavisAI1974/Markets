"""Curated Kalshi Demo feed joined to real as-of DavisAI signals.

This module is deliberately not an executor. It selects a small number of high-information
setups from SIGNALS_IN_USE.json, attaches real decision-state futures/options context, and
publishes research packages for the existing dashboard. Every row remains demonstration-only
until an independent market mapper, firing policy, risk coordinator, and Kalshi executor exist.
"""
from __future__ import annotations

import os
from typing import Any

from . import signals

DEMO_REST_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
DEMO_WS_BASE = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

CURATED_SIGNAL_PATHS = [
    "weather.regime",
    "weather_forecast.forecast_run_delta_cdd",
    "weather_forecast.forecast_run_delta",
    "weather_forecast_cycle.weekday_open.gw_cdd_d0",
    "model_disagreement.summary.max_abs_spread_gw_hdd",
    "storage.phase",
    "storage.vs_5yr",
    "storage_consensus.next_print.house_disagreement_bcf",
    "storage_consensus.last_print.surprise_vs_consensus_bcf",
    "squeeze_watch.active",
    "squeeze_watch.calendar_limb_satisfied_live",
    "contract_structure.curve_regime",
    "contract_structure.front_next_spread",
    "grid_stack.bas.US48.est_gas_burn_bcfd",
    "grid_stack.bas.US48.gas_share",
    "grid_stack.bas.US48.wind_mwh",
    "grid_stack.bas.US48.solar_mwh",
    "tape_conditions.session_signed_flow",
    "tape_conditions.session_b_share",
    "tape_conditions.big_print_b_share",
    "cot.managed_money_net_pctile_1y",
    "flow_calendar.days_to_next_eia_release",
    "flow_calendar.days_to_futures_expiry",
    "flow_calendar.days_to_opex",
    "vol_regime.n0_net_sigma_10",
]

_SETUP_ROWS = [
    {
        "id": "demo-futures-kalshi-lag",
        "display_rank": 1,
        "classification": "DIRECT_SIGNAL",
        "title": "NYMEX flow to Kalshi follower lag",
        "route": "NYMEX futures leader -> Kalshi NG event",
        "clock_s": 11.0,
        "demo_edge_usd": 2600,
        "demo_size_usd": 8000,
        "play": "flow nowcast",
        "urgency": "high",
        "direction": "FOLLOW LEADER",
        "status": "DEMO SIGNAL",
        "subtitle": "Use real signed futures flow as the leader; exact Kalshi ticker and firing gate remain unresolved.",
        "signal_path": "tape_conditions.session_signed_flow",
        "futures_paths": [
            ("Signed flow", "tape_conditions.session_signed_flow"),
            ("Session buy share", "tape_conditions.session_b_share"),
            ("Big-print buy share", "tape_conditions.big_print_b_share"),
            ("Front spread", "contract_structure.front_next_spread"),
            ("Curve regime", "contract_structure.curve_regime"),
        ],
        "options_paths": [
            ("Front option month", "options_surface.months[0].month"),
            ("Days to option expiry", "options_surface.months[0].days_to_opex"),
            ("OI-weighted strike", "options_surface.months[0].oi_weighted_strike"),
            ("Put/call OI", "options_surface.months[0].put_call_oi_ratio"),
        ],
        "mapping_status": "KALSHI MARKET MAPPING PENDING",
        "arb_status": "TRADE CANDIDATE - NOT ARBITRAGE",
    },
    {
        "id": "demo-weather-acceptance",
        "display_rank": 2,
        "classification": "DIRECT_SIGNAL",
        "title": "Weather revision acceptance",
        "route": "Forecast revision -> NG futures/options -> Kalshi bracket",
        "clock_s": 24.0,
        "demo_edge_usd": 1850,
        "demo_size_usd": 6000,
        "play": "weather revision",
        "urgency": "high",
        "direction": "DIRECTIONAL",
        "status": "DEMO SIGNAL",
        "subtitle": "Revision size is shown with model disagreement and the futures/options absorption state.",
        "signal_path": "weather_forecast.forecast_run_delta_cdd",
        "futures_paths": [
            ("Forecast CDD revision", "weather_forecast.forecast_run_delta_cdd"),
            ("Current CDD", "weather_forecast.forecast_gw_cdd"),
            ("Model spread", "model_disagreement.summary.max_abs_spread_gw_hdd"),
            ("US48 gas burn", "grid_stack.bas.US48.est_gas_burn_bcfd"),
            ("Futures sigma", "vol_regime.n0_net_sigma_10"),
        ],
        "options_paths": [
            ("Front option month", "options_surface.months[0].month"),
            ("OI-weighted strike", "options_surface.months[0].oi_weighted_strike"),
            ("Front call OI", "options_surface.months[0].total_call_oi"),
            ("Front put OI", "options_surface.months[0].total_put_oi"),
        ],
        "mapping_status": "KALSHI BRACKET MAPPING PENDING",
        "arb_status": "DIRECTIONAL RELATIVE VALUE",
    },
    {
        "id": "demo-storage-curve",
        "display_rank": 3,
        "classification": "RELATIVE_VALUE",
        "title": "Storage expectation versus curve response",
        "route": "Storage consensus -> NYMEX curve/options -> Kalshi storage event",
        "clock_s": 54.0,
        "demo_edge_usd": 1050,
        "demo_size_usd": 4200,
        "play": "storage consensus",
        "urgency": "medium",
        "direction": "RELATIVE VALUE",
        "status": "DEMO RESEARCH",
        "subtitle": "Compare the desk-consensus gap with the futures curve and options concentration.",
        "signal_path": "storage_consensus.next_print.house_disagreement_bcf",
        "futures_paths": [
            ("House disagreement", "storage_consensus.next_print.house_disagreement_bcf"),
            ("Storage phase", "storage.phase"),
            ("Storage vs 5yr", "storage.vs_5yr"),
            ("Front spread", "contract_structure.front_next_spread"),
            ("3d spread change", "contract_structure.front_next_spread_chg_3d"),
        ],
        "options_paths": [
            ("Put/call OI", "options_surface.months[0].put_call_oi_ratio"),
            ("OI-weighted strike", "options_surface.months[0].oi_weighted_strike"),
            ("Top OI strike", "options_surface.months[0].top5_oi_strikes[0].strike"),
            ("Top strike OI share", "options_surface.months[0].top5_oi_strikes[0].share_of_month_oi"),
        ],
        "mapping_status": "EXACT SETTLEMENT MATCH REQUIRED",
        "arb_status": "RELATIVE VALUE - NOT ARBITRAGE",
    },
    {
        "id": "demo-squeeze-tail",
        "display_rank": 4,
        "classification": "RELATIVE_VALUE",
        "title": "Squeeze state versus Kalshi upper tail",
        "route": "NYMEX calendar squeeze -> options OI -> Kalshi upper bracket",
        "clock_s": 35.0,
        "demo_edge_usd": 880,
        "demo_size_usd": 3200,
        "play": "squeeze watch",
        "urgency": "medium",
        "direction": "UPPER TAIL",
        "status": "DEMO MONITOR",
        "subtitle": "A tail package only; positioning and squeeze state do not independently determine direction.",
        "signal_path": "squeeze_watch.active",
        "futures_paths": [
            ("Squeeze active", "squeeze_watch.active"),
            ("Calendar limb live", "squeeze_watch.calendar_limb_satisfied_live"),
            ("Days to expiry", "squeeze_watch.days_to_calendar_front_expiry_live"),
            ("Unwind watch", "squeeze_watch.unwind_watch"),
        ],
        "options_paths": [
            ("OI-weighted strike", "options_surface.months[0].oi_weighted_strike"),
            ("Put/call OI", "options_surface.months[0].put_call_oi_ratio"),
            ("Top OI strike", "options_surface.months[0].top5_oi_strikes[0].strike"),
            ("Second OI strike", "options_surface.months[0].top5_oi_strikes[1].strike"),
        ],
        "mapping_status": "KALSHI TAIL BRACKET PENDING",
        "arb_status": "TAIL TRADE CANDIDATE",
    },
    {
        "id": "demo-residual-stack",
        "display_rank": 5,
        "classification": "DIRECT_SIGNAL",
        "title": "Residual power-stack gas burn",
        "route": "EIA-930 residual stack -> NG futures -> Kalshi NG event",
        "clock_s": 90.0,
        "demo_edge_usd": 690,
        "demo_size_usd": 2600,
        "play": "grid stack",
        "urgency": "low",
        "direction": "PHYSICAL",
        "status": "DEMO SIGNAL",
        "subtitle": "Shows gas burn with wind, solar, coal and nuclear rather than treating load as gas demand.",
        "signal_path": "grid_stack.bas.US48.est_gas_burn_bcfd",
        "futures_paths": [
            ("Estimated gas burn", "grid_stack.bas.US48.est_gas_burn_bcfd"),
            ("Gas share", "grid_stack.bas.US48.gas_share"),
            ("Wind MWh", "grid_stack.bas.US48.wind_mwh"),
            ("Solar MWh", "grid_stack.bas.US48.solar_mwh"),
            ("Coal MWh", "grid_stack.bas.US48.coal_mwh"),
            ("Nuclear MWh", "grid_stack.bas.US48.nuclear_mwh"),
        ],
        "options_paths": [
            ("Front option month", "options_surface.months[0].month"),
            ("Days to option expiry", "options_surface.months[0].days_to_opex"),
            ("Front call OI", "options_surface.months[0].total_call_oi"),
            ("Front put OI", "options_surface.months[0].total_put_oi"),
        ],
        "mapping_status": "DAILY KALSHI EVENT PENDING",
        "arb_status": "PHYSICAL DIRECTION CANDIDATE",
    },
    {
        "id": "demo-event-clock-guard",
        "display_rank": 6,
        "classification": "GUARD",
        "title": "EIA, futures expiry and options expiry guard",
        "route": "Calendar guard across Kalshi, NYMEX futures and options",
        "clock_s": 180.0,
        "demo_edge_usd": 0,
        "demo_size_usd": 0,
        "play": "flow calendar",
        "urgency": "low",
        "direction": "NO CALL",
        "status": "DEMO GUARD",
        "subtitle": "Calendar proximity changes interpretation and execution; it is not a standalone directional call.",
        "signal_path": "flow_calendar.days_to_next_eia_release",
        "futures_paths": [
            ("Days to EIA", "flow_calendar.days_to_next_eia_release"),
            ("Days to futures expiry", "flow_calendar.days_to_futures_expiry"),
            ("In GSCI roll", "flow_calendar.in_gsci_roll"),
            ("In BCOM roll", "flow_calendar.in_bcom_roll"),
        ],
        "options_paths": [
            ("Days to options expiry", "flow_calendar.days_to_opex"),
            ("Options expiry day", "flow_calendar.is_opex_day"),
            ("Front option days", "options_surface.months[0].days_to_opex"),
            ("Options as-of", "options_surface.asof_session"),
        ],
        "mapping_status": "GUARD ONLY",
        "arb_status": "NO TRADE",
    },
]

_PACKAGE_TEMPLATES = [
    {
        "id": "kalshi-ladder-monotonicity",
        "status": "AWAITING DEMO BOOKS",
        "status_class": "warning-bg",
        "title": "Kalshi threshold-ladder monotonicity",
        "subtitle": "Strict arbitrage candidate inside one definition-matched event ladder.",
        "strict_arb": True,
        "economics": [
            ["Arb test", "higher-threshold YES cannot exceed lower-threshold YES"],
            ["Prices", "two-sided books required"],
            ["Fees", "must clear all fees and slippage"],
        ],
        "legs": [
            ["Buy lower-threshold YES", "Only on executable ask", "AWAITING"],
            ["Sell higher-threshold YES", "Only on executable bid", "AWAITING"],
        ],
        "risks": ["exact settlement definition", "book depth", "partial-fill recovery"],
        "action": "Inspect definition and books",
    },
    {
        "id": "kalshi-complete-set",
        "status": "AWAITING EVENT SET",
        "status_class": "warning-bg",
        "title": "Kalshi mutually exclusive complete-set",
        "subtitle": "Strict arbitrage candidate only when the outcomes are exhaustive and definition-identical.",
        "strict_arb": True,
        "economics": [
            ["Buy-all test", "sum executable asks + fees < $1"],
            ["Sell-all test", "sum executable bids - fees > $1"],
            ["Coverage", "all outcomes required"],
        ],
        "legs": [
            ["Enumerate all event outcomes", "No missing or overlapping bucket", "AWAITING"],
            ["Price every leg", "Use executable depth, not midpoint", "AWAITING"],
        ],
        "risks": ["outcome completeness", "resolution source", "legging"],
        "action": "Run complete-set check",
    },
    {
        "id": "kalshi-nymex-options-relative-value",
        "status": "RESEARCH CANDIDATE",
        "status_class": "",
        "title": "Kalshi probability versus NYMEX options",
        "subtitle": "Interesting relative value, not strict arbitrage: physical event probability and risk-neutral option pricing differ.",
        "strict_arb": False,
        "economics": [
            ["Kalshi input", "executable bracket probability"],
            ["Options input", "same-date strike distribution"],
            ["Classification", "relative value only"],
        ],
        "legs": [
            ["Kalshi event leg", "Exact threshold and settlement date", "DEMO"],
            ["NYMEX options structure", "Matched strike/date hedge or comparison", "CONTEXT"],
        ],
        "risks": ["risk-neutral vs physical probability", "date mismatch", "settlement basis"],
        "action": "Compare matched definitions",
    },
    {
        "id": "kalshi-nymex-futures-hedge",
        "status": "DEMO PACKAGE",
        "status_class": "",
        "title": "Kalshi event with NYMEX futures hedge",
        "subtitle": "Directional package for rehearsal; not arbitrage and not executable in this build.",
        "strict_arb": False,
        "economics": [
            ["Signal", "curated setup selected"],
            ["Hedge", "NYMEX future or option"],
            ["Authority", "none"],
        ],
        "legs": [
            ["Kalshi event position", "Market mapper pending", "DEMO"],
            ["NYMEX hedge", "Size and trigger policy pending", "DEMO"],
        ],
        "risks": ["basis mismatch", "nonlinear event payoff", "firing policy absent"],
        "action": "Open evidence stack",
    },
]


def credential_status() -> dict:
    key_id = os.environ.get("KALSHI_DEMO_API_KEY_ID")
    key_path = os.path.expanduser(os.environ.get("KALSHI_DEMO_PRIVATE_KEY_PATH", ""))
    return {
        "key_id_present": bool(key_id),
        "private_key_path_present": bool(key_path),
        "private_key_file_exists": bool(key_path and os.path.isfile(key_path)),
        "rest_base": DEMO_REST_BASE,
        "websocket_base": DEMO_WS_BASE,
        "ready_for_authenticated_demo_reads": bool(key_id and key_path and os.path.isfile(key_path)),
        "write_enabled": False,
        "note": "credentials are server-side only; this dashboard build contains no order submission route",
    }


def _signal_lookup(signal_snapshot: dict) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for definition in signal_snapshot.get("signals", []):
        for value in definition.get("values", []):
            lookup[value.get("path")] = value.get("value")
        lookup.setdefault(
            definition.get("example_path"),
            next((v.get("value") for v in definition.get("values", []) if v.get("value") is not None), None),
        )
    return lookup


def _evidence(state: dict, specs: list[tuple[str, str]], lane: str) -> list[dict]:
    rows = []
    for label, path in specs:
        value = signals.resolve(state, path)
        rows.append(
            {
                "label": label,
                "path": path,
                "value": value,
                "available": value is not None,
                "lane": lane,
                "provenance": (
                    "selected as-of decision_state; options and other price-derived blocks may be "
                    "anchor-frozen in blind replay"
                    if lane == "options"
                    else "selected as-of decision_state"
                ),
            }
        )
    return rows


def snapshot(day: str, decision_state: dict, signal_snapshot: dict | None = None) -> dict:
    sigs = signal_snapshot or signals.snapshot(day, decision_state)
    state = decision_state.get("state", {}) if isinstance(decision_state, dict) else {}
    lookup = _signal_lookup(sigs)
    rows = []
    for template in _SETUP_ROWS:
        row = {k: v for k, v in template.items() if k not in {"futures_paths", "options_paths"}}
        signal_value = lookup.get(row["signal_path"])
        futures = _evidence(state, template["futures_paths"], "futures")
        options = _evidence(state, template["options_paths"], "options")
        row.update(
            {
                "signal_value": signal_value,
                "signal_available": signal_value is not None,
                "futures_evidence": futures,
                "options_evidence": options,
                "futures_resolved": sum(1 for item in futures if item["available"]),
                "options_resolved": sum(1 for item in options if item["available"]),
                "market_ticker": None,
                "execution_authority": "NONE",
                "source": "dashboard_demo.v2",
                "provenance": "demo economics; real consumed-signal and decision-state context when available",
                "strict_arb": False,
            }
        )
        rows.append(row)
    rows.sort(key=lambda row: (not row["signal_available"], row["display_rank"]))
    return {
        "schema": "dashboard_demo_feed.v2",
        "environment": "KALSHI_DEMO",
        "day": day,
        "available": True,
        "execution_enabled": False,
        "credential_status": credential_status(),
        "display_signal_paths": CURATED_SIGNAL_PATHS,
        "opportunities": rows,
        "packages": _PACKAGE_TEMPLATES,
        "selection_note": (
            "Curated for decision value: direct signal, cross-market relative value, and guards. "
            "Strict arbitrage labels require exact definitions plus executable two-sided prices."
        ),
        "note": "Demonstration feed only. No row can create, amend, cancel, or route an order.",
    }
