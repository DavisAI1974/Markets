#!/usr/bin/env python3
"""Locked Friday last-hour anchor for the G15 causal refine replay."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from ng_historical_replay import read_jsonl, validate_normalized_event
from ng_live_operator import NGLiveOperator

SCHEMA = "ng_g15_anchor.v1"
ANCHOR_DAY = "20260313"
ANCHOR_RAW_SYMBOL = "NGJ26"
ANCHOR_INSTRUMENT_ID = 1008
HOUR_S = 3600.0


class AnchorError(ValueError):
    """Raised when a G15 anchor cannot be built without guessing."""


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(event.get("dataset") or ""),
        event.get("publisher_id"),
        int(event.get("instrument_id") or 0),
        str(event.get("raw_symbol") or ""),
        str(event.get("definition_date") or ""),
    )


def _trade_side(value: Any) -> str | None:
    text = str(value or "").upper()
    if text in {"B", "BID", "BUY"}:
        return "BUY"
    if text in {"A", "ASK", "SELL"}:
        return "SELL"
    return None


def anchor_fingerprint(anchor: dict[str, Any]) -> str:
    payload = copy.deepcopy(anchor)
    payload.pop("anchor_fingerprint", None)
    return _fingerprint(payload)


def validate_anchor(anchor: dict[str, Any]) -> None:
    if anchor.get("schema") != SCHEMA:
        raise AnchorError(f"unexpected anchor schema: {anchor.get('schema')}")
    if anchor.get("authority") != "REFINE_ANCHOR_ONLY" or anchor.get("execution_authority") is not False:
        raise AnchorError("anchor authority is invalid")
    if str(anchor.get("date")) != ANCHOR_DAY:
        raise AnchorError(f"G15 anchor date must be {ANCHOR_DAY}")
    instrument = dict(anchor.get("instrument") or {})
    if instrument.get("raw_symbol") != ANCHOR_RAW_SYMBOL:
        raise AnchorError(f"G15 anchor raw symbol must be {ANCHOR_RAW_SYMBOL}")
    if int(instrument.get("instrument_id") or 0) != ANCHOR_INSTRUMENT_ID:
        raise AnchorError(f"G15 anchor instrument_id must be {ANCHOR_INSTRUMENT_ID}")
    start = _finite(anchor.get("hour_start_event_s"))
    end = _finite(anchor.get("hour_end_event_s"))
    cutoff = _finite(anchor.get("cutoff_event_s"))
    if None in (start, end, cutoff) or not float(start) < float(end) <= float(cutoff):
        raise AnchorError("anchor hour/cutoff ordering is invalid")
    if float(end) - float(start) > HOUR_S + 1e-6:
        raise AnchorError("anchor window exceeds one hour")
    prices = dict(anchor.get("prices") or {})
    if any(_finite(prices.get(name)) is None for name in ("first", "last", "high", "low")):
        raise AnchorError("anchor prices must be finite")
    if int(anchor.get("trade_count") or 0) <= 0:
        raise AnchorError("anchor requires at least one trade")
    if anchor_fingerprint(anchor) != anchor.get("anchor_fingerprint"):
        raise AnchorError("anchor fingerprint mismatch")


def build_anchor(
    events: Iterable[dict[str, Any]],
    *,
    cutoff_event_s: float | None = None,
    window_s: float = HOUR_S,
) -> dict[str, Any]:
    """Build the final traded-hour state for Friday 2026-03-13."""
    if not 0 < float(window_s) <= HOUR_S:
        raise AnchorError("window_s must be in (0, 3600]")
    rows = [validate_normalized_event(copy.deepcopy(row)) for row in events]
    if not rows:
        raise AnchorError("anchor input is empty")

    previous: tuple[float, int, int] | None = None
    identities: set[tuple[Any, ...]] = set()
    for row in rows:
        ts = _finite(row.get("ts_event_s"))
        if ts is None:
            raise AnchorError("anchor record lacks finite event time")
        key = (float(ts), int(row.get("source_sequence") or 0), int(row.get("ingest_sequence") or 0))
        if previous is not None and key < previous:
            raise AnchorError("anchor records moved backwards")
        previous = key
        if str(row.get("session_day") or "") != ANCHOR_DAY:
            raise AnchorError(f"anchor record is not from Friday {ANCHOR_DAY}")
        identities.add(_identity(row))
    if len(identities) != 1:
        raise AnchorError("anchor records contain multiple instrument definitions")
    identity = next(iter(identities))
    if (identity[2], identity[3]) != (ANCHOR_INSTRUMENT_ID, ANCHOR_RAW_SYMBOL):
        raise AnchorError("anchor records do not match canonical NGJ26 identity")

    trades = [row for row in rows if row.get("event_type") == "trade"]
    if not trades:
        raise AnchorError("anchor requires trade records")
    last_trade_s = max(float(row["ts_event_s"]) for row in trades)
    cutoff = last_trade_s if cutoff_event_s is None else float(cutoff_event_s)
    if cutoff < last_trade_s:
        raise AnchorError("cutoff_event_s precedes the final supplied trade")
    hour_start = cutoff - float(window_s)
    hour_trades = [row for row in trades if hour_start <= float(row["ts_event_s"]) <= cutoff]
    if not hour_trades:
        raise AnchorError("no trades fall inside the anchor hour")

    operator = NGLiveOperator()
    definition_seen = False
    for row in rows:
        ts = float(row["ts_event_s"])
        if ts > cutoff:
            raise AnchorError("anchor input contains post-cutoff evidence")
        event_type = str(row["event_type"])
        if event_type == "definition":
            definition_seen = True
        elif event_type == "trade":
            operator.on_trade(ts, float(row["price"]), float(row["size"]), row["side"])
        elif event_type == "mbo":
            operator.on_mbo(
                ts,
                row["action"],
                row["side"],
                float(row["size"]),
                int(row["order_id"]),
                None if row.get("price") is None else float(row["price"]),
                int(row["flags"]),
            )

    hour_trades.sort(key=lambda row: (float(row["ts_event_s"]), int(row.get("source_sequence") or 0)))
    prices = [float(row["price"]) for row in hour_trades]
    buy_volume = sell_volume = 0.0
    unmapped = 0
    for row in hour_trades:
        side = _trade_side(row.get("side"))
        if side == "BUY":
            buy_volume += float(row["size"])
        elif side == "SELL":
            sell_volume += float(row["size"])
        else:
            unmapped += 1

    first_price, last_price = prices[0], prices[-1]
    snapshot = operator.snapshot(cutoff)
    anchor = {
        "schema": SCHEMA,
        "date": ANCHOR_DAY,
        "cutoff_event_s": cutoff,
        "hour_start_event_s": max(hour_start, float(hour_trades[0]["ts_event_s"])),
        "hour_end_event_s": float(hour_trades[-1]["ts_event_s"]),
        "authority": "REFINE_ANCHOR_ONLY",
        "execution_authority": False,
        "instrument": {
            "dataset": identity[0],
            "publisher_id": identity[1],
            "instrument_id": identity[2],
            "raw_symbol": identity[3],
            "definition_date": identity[4],
            "continuous_symbol": "NG.v.0",
            "roll_rule": "kalshi_settlement_proximity",
        },
        "prices": {
            "first": first_price,
            "last": last_price,
            "high": max(prices),
            "low": min(prices),
            "net_usd": round((last_price - first_price) * 10000.0),
        },
        "direction": "up" if last_price > first_price else "down" if last_price < first_price else "flat",
        "trade_count": len(hour_trades),
        "buy_volume": round(buy_volume, 6),
        "sell_volume": round(sell_volume, 6),
        "signed_volume": round(buy_volume - sell_volume, 6),
        "unmapped_trade_sides": unmapped,
        "last_hour_operator": {
            "move_onset_pressure": snapshot.get("move_onset_pressure"),
            "signed_flow": snapshot.get("signed_flow"),
            "divergence_exhaustion": snapshot.get("divergence_exhaustion"),
            "mbo_queue": snapshot.get("mbo_queue"),
        },
        "data_quality": {
            **dict(snapshot.get("data_quality") or {}),
            "definition_seen": definition_seen,
            "anchor_window_s": float(window_s),
            "missing_is_visible": True,
        },
        "provenance": {
            "normalized_event_schema": "ng_normalized_event.v1",
            "same_operator_as_live": True,
            "post_anchor_evidence_used": False,
        },
    }
    anchor["anchor_fingerprint"] = anchor_fingerprint(anchor)
    validate_anchor(anchor)
    return anchor


def assert_anchor_precedes_state(anchor: dict[str, Any], state: dict[str, Any]) -> None:
    validate_anchor(anchor)
    state_time = _finite(state.get("as_of_event_s"))
    if state_time is None or float(state_time) <= float(anchor["cutoff_event_s"]):
        raise AnchorError("feature state does not occur after the Friday anchor")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the locked G15 Friday last-hour anchor")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cutoff-event-s", type=float)
    args = parser.parse_args()
    rows = [row for path in args.inputs for row in read_jsonl(path)]
    rows.sort(
        key=lambda row: (
            float(row["ts_event_s"]),
            {"definition": 0, "trade": 1, "mbo": 2}.get(str(row["event_type"]), 99),
            int(row.get("source_sequence") or 0),
        )
    )
    anchor = build_anchor(rows, cutoff_event_s=args.cutoff_event_s)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(anchor, indent=2) + "\n", encoding="utf-8")
    print(f"[ng_g15_anchor] wrote {args.out} fingerprint={anchor['anchor_fingerprint'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
