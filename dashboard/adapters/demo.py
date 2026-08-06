"""Versioned demo opportunity feed for dashboard rehearsal.

This is deliberately not an executor. It binds each demonstration row to a named signal from
SIGNALS_IN_USE.json and, when available, its real as-of value. Economics, clocks, and actions are
illustrative and carry no order authority. The contract is designed so a future canonical emit
feed can replace this module without rewriting the frontend.
"""
from __future__ import annotations

import os
from typing import Any

from . import signals

DEMO_REST_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
DEMO_WS_BASE = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

_DEMO_ROWS = [
    {
        "id": "demo-weather-revision",
        "title": "NG weather revision follow-through",
        "route": "DEMO Kalshi follower - market mapping pending",
        "clock_s": 12.0,
        "demo_edge_usd": 1850,
        "demo_size_usd": 6000,
        "play": "weather revision",
        "mode": "DEMO",
        "urgency": "high",
        "direction": "YES",
        "status": "DEMO SIGNAL",
        "subtitle": "Forecast revision is consumed by the brain; no firing mechanism attached.",
        "signal_path": "weather_forecast.forecast_run_delta_cdd",
    },
    {
        "id": "demo-storage-disagreement",
        "title": "Storage consensus disagreement",
        "route": "DEMO Kalshi storage event - ticker unresolved",
        "clock_s": 48.0,
        "demo_edge_usd": 920,
        "demo_size_usd": 3500,
        "play": "storage consensus",
        "mode": "DEMO",
        "urgency": "medium",
        "direction": "SIGNAL",
        "status": "DEMO SIGNAL",
        "subtitle": "House-versus-consensus disagreement displayed as evidence only.",
        "signal_path": "storage_consensus.next_print.house_disagreement_bcf",
    },
    {
        "id": "demo-squeeze",
        "title": "Front-limb squeeze state",
        "route": "DEMO Kalshi NG event - exact contract mapping pending",
        "clock_s": 21.0,
        "demo_edge_usd": 770,
        "demo_size_usd": 2800,
        "play": "squeeze watch",
        "mode": "DEMO",
        "urgency": "medium",
        "direction": "MONITOR",
        "status": "DEMO MONITOR",
        "subtitle": "Squeeze state is real as-of evidence; action is illustrative.",
        "signal_path": "squeeze_watch.active",
    },
    {
        "id": "demo-gas-burn",
        "title": "US48 estimated gas burn",
        "route": "DEMO Kalshi NG daily event - ticker unresolved",
        "clock_s": 75.0,
        "demo_edge_usd": 640,
        "demo_size_usd": 2400,
        "play": "grid stack",
        "mode": "DEMO",
        "urgency": "low",
        "direction": "SIGNAL",
        "status": "DEMO SIGNAL",
        "subtitle": "Real decision-state value joined to a demonstration route.",
        "signal_path": "grid_stack.bas.US48.est_gas_burn_bcfd",
    },
    {
        "id": "demo-cot-crowding",
        "title": "Managed-money crowding context",
        "route": "DEMO Kalshi NG tail event - ticker unresolved",
        "clock_s": 120.0,
        "demo_edge_usd": 430,
        "demo_size_usd": 1800,
        "play": "positioning context",
        "mode": "DEMO",
        "urgency": "low",
        "direction": "SHADOW",
        "status": "DEMO SHADOW",
        "subtitle": "Positioning is context and gain conditioning, not a standalone sign call.",
        "signal_path": "cot.managed_money_net_pctile_1y",
    },
    {
        "id": "demo-eia-clock",
        "title": "EIA release clock",
        "route": "DEMO event-timing guard",
        "clock_s": 180.0,
        "demo_edge_usd": 0,
        "demo_size_usd": 0,
        "play": "flow calendar",
        "mode": "DEMO",
        "urgency": "low",
        "direction": "NO CALL",
        "status": "DEMO GUARD",
        "subtitle": "Calendar proximity is a guard, not an executable signal.",
        "signal_path": "flow_calendar.days_to_next_eia_release",
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
        lookup.setdefault(definition.get("example_path"),
                          next((v.get("value") for v in definition.get("values", [])
                                if v.get("value") is not None), None))
    return lookup


def snapshot(day: str, decision_state: dict, signal_snapshot: dict | None = None) -> dict:
    sigs = signal_snapshot or signals.snapshot(day, decision_state)
    lookup = _signal_lookup(sigs)
    rows = []
    for template in _DEMO_ROWS:
        row = dict(template)
        value = lookup.get(row["signal_path"])
        row["signal_value"] = value
        row["signal_available"] = value is not None
        row["market_ticker"] = None
        row["execution_authority"] = "NONE"
        row["source"] = "dashboard_demo.v1"
        row["provenance"] = "demo economics + real consumed-signal definition/value when available"
        rows.append(row)
    return {
        "schema": "dashboard_demo_feed.v1",
        "environment": "KALSHI_DEMO",
        "day": day,
        "available": True,
        "execution_enabled": False,
        "credential_status": credential_status(),
        "opportunities": rows,
        "note": "Demonstration feed only. No row can create, amend, cancel, or route an order.",
    }
