"""Helpers for fetching public Bybit linear ticker snapshots over WebSocket.

Bybit's REST market endpoints are geoblocked from this US/cloud environment,
but the public linear ticker WebSocket has remained reachable and already
powers the repo's perp collectors. This module gives the monitors and remote
history collectors a shared, low-friction way to fetch current snapshots.
"""

from __future__ import annotations

import json
import ssl
import time
from typing import Iterable

from websocket import WebSocketTimeoutException, create_connection


BYBIT_PUBLIC_LINEAR_WSS = "wss://stream.bybit.com/v5/public/linear"


def fetch_bybit_ticker_snapshots(
    symbols: Iterable[str],
    timeout_s: float = 15.0,
) -> dict[str, dict]:
    """Return the latest ticker payload per requested Bybit linear symbol.

    The returned dict is keyed by symbol and contains the merged ticker fields
    from the latest snapshot/delta messages plus `_ws_ts` from the envelope.
    Partial success is allowed: callers get whichever symbols arrived before
    the timeout.
    """
    wanted: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        sym = str(symbol or "").strip().upper()
        if not sym or sym in seen:
            continue
        wanted.append(sym)
        seen.add(sym)
    if not wanted:
        return {}

    ws = create_connection(
        BYBIT_PUBLIC_LINEAR_WSS,
        timeout=timeout_s,
        sslopt={"cert_reqs": ssl.CERT_NONE},
    )
    ws.settimeout(timeout_s)
    latest: dict[str, dict] = {}
    deadline = time.time() + timeout_s
    try:
        ws.send(json.dumps({
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in wanted],
        }))
        while time.time() < deadline and len(latest) < len(wanted):
            try:
                raw = ws.recv()
            except WebSocketTimeoutException:
                break
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            topic = str(msg.get("topic") or "")
            if not topic.startswith("tickers."):
                continue
            symbol = topic.split(".", 1)[1].upper()
            if symbol not in seen:
                continue
            payload = msg.get("data") or {}
            if not isinstance(payload, dict):
                continue
            merged = dict(latest.get(symbol) or {})
            merged.update(payload)
            merged["symbol"] = symbol
            try:
                merged["_ws_ts"] = float(msg.get("ts", 0.0)) / 1000.0
            except (TypeError, ValueError):
                merged["_ws_ts"] = 0.0
            latest[symbol] = merged
    finally:
        try:
            ws.close()
        except Exception:
            pass

    return {symbol: latest[symbol] for symbol in wanted if symbol in latest}
