"""Exact external snapshot/restore for the proven V4 native-MBO adapter.

The scientific adapter remains unchanged.  This module serializes only the
continuation state needed to resume after a completed F_LAST event group and
reconstructs derived caches from authoritative orders/FIFO/activity state.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    ACTIVITY_WINDOWS_S,
    ADAPTER_REVISION,
    InstrumentBook,
    RestingOrder,
    V4MboAdapter,
    _RollingActivityWindow,
)

SCHEMA = "NG_MBO_V4_EXACT_RESUME_STATE_V1"
_BOOK_KEYS = frozenset({
    "instrument_id",
    "raw_symbol",
    "last_sequence",
    "last_recv_ns",
    "last_event_ns",
    "activity_last_now_ns",
    "integrity",
    "orders",
    "levels",
    "activity",
})
_STATE_KEYS = frozenset({
    "schema",
    "adapter_revision",
    "record_count",
    "completed_event_group_count",
    "books",
    "state_hash",
})
_ORDER_KEYS = frozenset({
    "instrument_id",
    "order_id",
    "side",
    "price_raw",
    "size",
    "priority_recv_ns",
    "last_update_recv_ns",
    "priority_sequence",
})
_LEVEL_KEYS = frozenset({"price_raw", "order_ids"})
_ACTIVITY_KEYS = frozenset({
    "ts_recv_ns",
    "action",
    "side",
    "price_raw",
    "size",
    "size_delta",
    "priority_lost",
    "missing_reference",
    "top_touch",
})


class ResumeStateError(ValueError):
    """Exact-resume state contract violation."""


def _canonical_payload(state: Mapping[str, Any]) -> bytes:
    body = {key: value for key, value in state.items() if key != "state_hash"}
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def adapter_state_hash(state: Mapping[str, Any]) -> str:
    if not isinstance(state, Mapping):
        raise ResumeStateError("adapter state must be a mapping")
    return hashlib.sha256(_canonical_payload(state)).hexdigest()


def _expect_exact_keys(value: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResumeStateError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise ResumeStateError(
            f"unknown or missing {label} fields: unknown={sorted(actual - expected)}, "
            f"missing={sorted(expected - actual)}"
        )
    return value


def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResumeStateError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ResumeStateError(f"{label} must be >= {minimum}")
    return value


def _book_state(book: InstrumentBook) -> dict[str, Any]:
    if book.event_group:
        raise ResumeStateError("resume checkpoint requires an F_LAST-closed event group")
    if book._legacy_group_rows or book._legacy_group_book_before is not None or book._legacy_group_visible_add:
        raise ResumeStateError("legacy event-group continuation state is not closed")

    orders = [asdict(book.orders[oid]) for oid in sorted(book.orders)]
    levels: dict[str, list[dict[str, Any]]] = {}
    for side in ("B", "A"):
        prices = sorted(book.levels[side], reverse=(side == "B"))
        levels[side] = [
            {"price_raw": int(price), "order_ids": list(book.levels[side][price])}
            for price in prices
            if book.levels[side][price]
        ]
    return {
        "instrument_id": int(book.instrument_id),
        "raw_symbol": book.raw_symbol,
        "last_sequence": book.last_sequence,
        "last_recv_ns": book.last_recv_ns,
        "last_event_ns": book.last_event_ns,
        "activity_last_now_ns": book._activity_last_now_ns,
        "integrity": dict(sorted(book.integrity.items())),
        "orders": orders,
        "levels": levels,
        "activity": [dict(row) for row in book.activity],
    }


def export_adapter_state(adapter: V4MboAdapter) -> dict[str, Any]:
    if not hasattr(adapter, "assert_groups_closed"):
        raise ResumeStateError("object is not a V4 MBO adapter")
    try:
        adapter.assert_groups_closed()
    except RuntimeError as exc:
        raise ResumeStateError("resume checkpoint requires an F_LAST-closed event group") from exc

    state: dict[str, Any] = {
        "schema": SCHEMA,
        "adapter_revision": ADAPTER_REVISION,
        "record_count": int(adapter.record_count),
        "completed_event_group_count": int(adapter.completed_event_group_count),
        "books": [_book_state(adapter.books[iid]) for iid in sorted(adapter.books)],
        "state_hash": "",
    }
    state["state_hash"] = adapter_state_hash(state)
    _validate_state(state)
    return state


def _validate_activity(row: Any) -> dict[str, Any]:
    row = dict(_expect_exact_keys(row, _ACTIVITY_KEYS, "activity row"))
    for key in ("ts_recv_ns", "price_raw", "size"):
        _require_int(row[key], f"activity.{key}")
    if row["size_delta"] is not None:
        _require_int(row["size_delta"], "activity.size_delta")
    if row["action"] not in "ACMRTFN" or row["side"] not in "ABN":
        raise ResumeStateError("activity action/side is invalid")
    for key in ("priority_lost", "missing_reference", "top_touch"):
        if not isinstance(row[key], bool):
            raise ResumeStateError(f"activity.{key} must be boolean")
    return row


def _validate_state(state: Mapping[str, Any]) -> None:
    state = _expect_exact_keys(state, _STATE_KEYS, "adapter state")
    if state["state_hash"] != adapter_state_hash(state):
        raise ResumeStateError("adapter state hash mismatch")
    if state["schema"] != SCHEMA:
        raise ResumeStateError("unsupported adapter state schema")
    if state["adapter_revision"] != ADAPTER_REVISION:
        raise ResumeStateError("adapter revision mismatch")
    _require_int(state["record_count"], "record_count", minimum=0)
    _require_int(state["completed_event_group_count"], "completed_event_group_count", minimum=0)
    if state["completed_event_group_count"] > state["record_count"]:
        raise ResumeStateError("completed event-group count exceeds record count")
    if not isinstance(state["books"], list):
        raise ResumeStateError("books must be a list")

    seen_instruments: set[int] = set()
    for raw_book in state["books"]:
        book = _expect_exact_keys(raw_book, _BOOK_KEYS, "book")
        iid = _require_int(book["instrument_id"], "instrument_id", minimum=1)
        if iid in seen_instruments:
            raise ResumeStateError("duplicate instrument book")
        seen_instruments.add(iid)
        if book["raw_symbol"] is not None and not isinstance(book["raw_symbol"], str):
            raise ResumeStateError("raw_symbol must be string or null")
        for key in ("last_sequence", "last_recv_ns", "last_event_ns", "activity_last_now_ns"):
            if book[key] is not None:
                _require_int(book[key], key)
        if not isinstance(book["integrity"], Mapping):
            raise ResumeStateError("integrity must be an object")
        for key, value in book["integrity"].items():
            if not isinstance(key, str):
                raise ResumeStateError("integrity keys must be strings")
            _require_int(value, f"integrity.{key}", minimum=0)

        if not isinstance(book["orders"], list):
            raise ResumeStateError("orders must be a list")
        orders_by_id: dict[int, Mapping[str, Any]] = {}
        for raw_order in book["orders"]:
            order = _expect_exact_keys(raw_order, _ORDER_KEYS, "order")
            oid = _require_int(order["order_id"], "order_id")
            if oid in orders_by_id:
                raise ResumeStateError("duplicate order id")
            if _require_int(order["instrument_id"], "order.instrument_id") != iid:
                raise ResumeStateError("order instrument does not match book")
            if order["side"] not in {"A", "B"}:
                raise ResumeStateError("resting order side must be A or B")
            for key in ("price_raw", "size", "priority_recv_ns", "last_update_recv_ns", "priority_sequence"):
                _require_int(order[key], f"order.{key}")
            if order["size"] < 0:
                raise ResumeStateError("resting order size cannot be negative")
            orders_by_id[oid] = order

        levels = book["levels"]
        if not isinstance(levels, Mapping) or set(levels) != {"B", "A"}:
            raise ResumeStateError("levels must contain exactly B and A")
        fifo_seen: set[int] = set()
        for side in ("B", "A"):
            side_levels = levels[side]
            if not isinstance(side_levels, list):
                raise ResumeStateError("FIFO side levels must be a list")
            prices_seen: set[int] = set()
            for raw_level in side_levels:
                level = _expect_exact_keys(raw_level, _LEVEL_KEYS, "FIFO level")
                price = _require_int(level["price_raw"], "level.price_raw")
                if price in prices_seen:
                    raise ResumeStateError("duplicate FIFO price level")
                prices_seen.add(price)
                ids = level["order_ids"]
                if not isinstance(ids, list) or not ids:
                    raise ResumeStateError("FIFO level must contain order ids")
                for oid in ids:
                    _require_int(oid, "FIFO order id")
                    if oid in fifo_seen:
                        raise ResumeStateError("duplicate order id in FIFO levels")
                    fifo_seen.add(oid)
                    order = orders_by_id.get(oid)
                    if order is None:
                        raise ResumeStateError("FIFO level references missing order")
                    if order["side"] != side or order["price_raw"] != price:
                        raise ResumeStateError("FIFO level does not match order side/price")
        if fifo_seen != set(orders_by_id):
            raise ResumeStateError("orders and FIFO levels do not reconcile")

        if not isinstance(book["activity"], list):
            raise ResumeStateError("activity must be a list")
        activity = [_validate_activity(row) for row in book["activity"]]
        if any(activity[i]["ts_recv_ns"] > activity[i + 1]["ts_recv_ns"] for i in range(len(activity) - 1)):
            raise ResumeStateError("activity rows are not in causal receive order")
        if activity and book["last_recv_ns"] is not None and activity[-1]["ts_recv_ns"] > book["last_recv_ns"]:
            raise ResumeStateError("activity exceeds book receive watermark")


def restore_adapter_state(state: Mapping[str, Any]) -> V4MboAdapter:
    _validate_state(state)
    adapter = V4MboAdapter()
    adapter.record_count = int(state["record_count"])
    adapter.completed_event_group_count = int(state["completed_event_group_count"])

    for raw_book in state["books"]:
        iid = int(raw_book["instrument_id"])
        book = InstrumentBook(iid)
        book.raw_symbol = raw_book["raw_symbol"]
        book.last_sequence = raw_book["last_sequence"]
        book.last_recv_ns = raw_book["last_recv_ns"]
        book.last_event_ns = raw_book["last_event_ns"]
        book.integrity = Counter({str(k): int(v) for k, v in raw_book["integrity"].items()})
        book.orders = {
            int(row["order_id"]): RestingOrder(**dict(row))
            for row in raw_book["orders"]
        }
        book.levels = {"B": defaultdict(list), "A": defaultdict(list)}
        for side in ("B", "A"):
            for level in raw_book["levels"][side]:
                book.levels[side][int(level["price_raw"])] = [int(oid) for oid in level["order_ids"]]

        book._side_depth = {"B": 0, "A": 0}
        book._side_order_count = {"B": 0, "A": 0}
        for order in book.orders.values():
            book._side_depth[order.side] += int(order.size)
            book._side_order_count[order.side] += 1
        book._top10_cache = {"B": None, "A": None}

        book.activity = deque(dict(row) for row in raw_book["activity"])
        book._activity_windows = {seconds: _RollingActivityWindow() for seconds in ACTIVITY_WINDOWS_S}
        for activity_row in book.activity:
            for window in book._activity_windows.values():
                window.append(activity_row)
        book._activity_last_now_ns = raw_book["activity_last_now_ns"]
        if book._activity_last_now_ns is not None:
            for seconds, window in book._activity_windows.items():
                window.expire_before(int(book._activity_last_now_ns) - seconds * 1_000_000_000)

        book.event_group = []
        book._legacy_group_rows = []
        book._legacy_group_book_before = None
        book._legacy_group_visible_add = False
        adapter.books[iid] = book

    restored = export_adapter_state(adapter)
    if restored != dict(state):
        raise ResumeStateError("restored adapter state does not round-trip exactly")
    return adapter


def write_adapter_state_atomic(path: Path | str, state: Mapping[str, Any]) -> None:
    _validate_state(state)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        dict(state),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def load_adapter_state(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResumeStateError(f"cannot load adapter resume state: {target}") from exc
    if not isinstance(value, dict):
        raise ResumeStateError("adapter state file must contain a JSON object")
    _validate_state(value)
    return value
