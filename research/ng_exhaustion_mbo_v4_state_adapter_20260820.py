#!/usr/bin/env python3
"""V4-native Databento MBO state adapter for the NG Step-1 structural census.

This is additive research code. It does not modify the frozen 2026-08-17 detector,
canonical rows, Phase-1/Phase-2 findings, runway clock, or permanent Frankie.

Two surfaces are emitted from the same native MBO stream:

1. V4_NATIVE_FULL
   - normalized raw MBO event-group semantics;
   - causal full-depth resting-order state;
   - reconstructed FIFO queue state;
   - rolling add/cancel/modify/trade/fill activity;
   - source/contract/clock provenance.

2. LEGACY_CONTROL
   - an MBP/trade-shaped top-10 projection intended only for overlap/equivalence
     testing against the frozen Step-1 canonical detector surface.

Native DBN remains canonical. This adapter never rewrites it.

Databento/CME MBO normalization used here:
A add; C cancel/reduce by reported quantity; M replace order state; R clear;
T aggressing trade (no resting-book mutation); F resting fill detail (no direct
resting-book mutation); N no mutation. Price changes or size increases on M lose
FIFO priority, while same-price non-increasing modifications retain priority.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PRICE_SCALE = 1_000_000_000
UNDEF_PRICE = 9_000_000_000_000_000_000
F_LAST = 1 << 7
F_TOB = 1 << 6
F_SNAPSHOT = 1 << 5
F_BAD_TS_RECV = 1 << 3
VALID_ACTIONS = frozenset("ACMRTFN")
VALID_SIDES = frozenset("ABN")
ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)
ADAPTER_REVISION = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V1_20260820"


def _enum_text(value: Any) -> str:
    if value is None:
        return "N"
    value = getattr(value, "value", value)
    value = getattr(value, "name", value)
    text = str(value)
    if len(text) == 1:
        return text
    names = {
        "Add": "A", "Cancel": "C", "Modify": "M", "Clear": "R",
        "Trade": "T", "Fill": "F", "None": "N", "Ask": "A", "Bid": "B",
    }
    return names.get(text, text[:1].upper())


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        if name in record:
            return record[name]
        hd = record.get("hd") or {}
        return hd.get(name, default) if isinstance(hd, dict) else default
    if hasattr(record, name):
        return getattr(record, name)
    hd = getattr(record, "hd", None)
    return getattr(hd, name, default) if hd is not None else default


def _int(record: Any, name: str, default: int = 0) -> int:
    value = _get(record, name, default)
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)


def decimal_price(raw: int | None) -> float | None:
    if raw is None or abs(int(raw)) >= UNDEF_PRICE:
        return None
    return int(raw) / PRICE_SCALE


def _ratio(num: float, den: float) -> float | None:
    return None if abs(float(den)) < 1e-15 else float(num) / float(den)


def _safe_mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return None if not vals else float(sum(vals) / len(vals))


def _quantile(values: Iterable[float], q: float) -> float | None:
    vals = sorted(float(x) for x in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    z = q * (len(vals) - 1)
    i = int(math.floor(z))
    j = min(i + 1, len(vals) - 1)
    w = z - i
    return vals[i] * (1.0 - w) + vals[j] * w


@dataclass(frozen=True)
class NormalizedMbo:
    instrument_id: int
    publisher_id: int
    channel_id: int
    order_id: int
    action: str
    side: str
    price_raw: int
    size: int
    flags: int
    sequence: int
    ts_event_ns: int
    ts_recv_ns: int
    ts_in_delta_ns: int
    raw_symbol: str | None = None
    source_dbn_object: str | None = None
    source_dbn_sha256: str | None = None

    @property
    def is_snapshot(self) -> bool:
        return bool(self.flags & F_SNAPSHOT)

    @property
    def is_last(self) -> bool:
        return bool(self.flags & F_LAST)

    @property
    def price(self) -> float | None:
        return decimal_price(self.price_raw)

    def public_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["price"] = self.price
        out["is_snapshot"] = self.is_snapshot
        out["is_last"] = self.is_last
        return out


@dataclass
class RestingOrder:
    instrument_id: int
    order_id: int
    side: str
    price_raw: int
    size: int
    priority_recv_ns: int
    last_update_recv_ns: int
    priority_sequence: int


@dataclass(frozen=True)
class ApplyEffect:
    action: str
    side: str
    price_raw: int
    reported_size: int
    old_size: int | None
    new_size: int | None
    size_delta: int | None
    priority_lost: bool
    removed: bool
    missing_reference: bool
    touched_or_improved_top_before: bool
    top_before_price_raw: int | None


class InstrumentBook:
    """Full resting-order book for one instrument, preserving FIFO list order."""

    def __init__(self, instrument_id: int) -> None:
        self.instrument_id = int(instrument_id)
        self.orders: dict[int, RestingOrder] = {}
        self.levels: dict[str, dict[int, list[int]]] = {"B": defaultdict(list), "A": defaultdict(list)}
        self.activity: deque[dict[str, Any]] = deque()
        self.event_group: list[NormalizedMbo] = []
        self.integrity: Counter[str] = Counter()
        self.last_sequence: int | None = None
        self.last_recv_ns: int | None = None
        self.last_event_ns: int | None = None
        self.raw_symbol: str | None = None

    def _prices(self, side: str) -> list[int]:
        prices = [p for p, ids in self.levels[side].items() if ids]
        return sorted(prices, reverse=(side == "B"))

    def best_price_raw(self, side: str) -> int | None:
        prices = self._prices(side)
        return None if not prices else prices[0]

    def _remove_from_level(self, order: RestingOrder) -> None:
        ids = self.levels[order.side].get(order.price_raw)
        if not ids:
            self.integrity["missing_level_on_remove"] += 1
            return
        try:
            ids.remove(order.order_id)
        except ValueError:
            self.integrity["missing_order_id_in_level_on_remove"] += 1
        if not ids:
            self.levels[order.side].pop(order.price_raw, None)

    def _add_order(self, msg: NormalizedMbo) -> RestingOrder:
        if msg.order_id in self.orders:
            self.integrity["duplicate_add_order_id"] += 1
            self._remove_from_level(self.orders[msg.order_id])
        order = RestingOrder(
            instrument_id=msg.instrument_id,
            order_id=msg.order_id,
            side=msg.side,
            price_raw=msg.price_raw,
            size=max(0, msg.size),
            priority_recv_ns=msg.ts_recv_ns,
            last_update_recv_ns=msg.ts_recv_ns,
            priority_sequence=msg.sequence,
        )
        self.orders[msg.order_id] = order
        self.levels[msg.side][msg.price_raw].append(msg.order_id)
        return order

    def _cancel(self, msg: NormalizedMbo) -> ApplyEffect:
        old = self.orders.get(msg.order_id)
        top = self.best_price_raw(msg.side) if msg.side in ("A", "B") else None
        touched = top is not None and msg.price_raw == top
        if old is None:
            self.integrity["cancel_missing_order"] += 1
            return ApplyEffect("C", msg.side, msg.price_raw, msg.size, None, None, None, False, False, True, touched, top)
        old_size = old.size
        removed_qty = max(0, msg.size)
        new_size = max(0, old_size - removed_qty)
        old.size = new_size
        old.last_update_recv_ns = msg.ts_recv_ns
        removed = new_size == 0
        if removed:
            self._remove_from_level(old)
            self.orders.pop(old.order_id, None)
        return ApplyEffect("C", old.side, old.price_raw, msg.size, old_size, new_size, -min(old_size, removed_qty), False, removed, False, touched, top)

    def _modify(self, msg: NormalizedMbo) -> ApplyEffect:
        old = self.orders.get(msg.order_id)
        top = self.best_price_raw(msg.side) if msg.side in ("A", "B") else None
        touched = top is not None and (msg.price_raw == top or (msg.side == "B" and msg.price_raw > top) or (msg.side == "A" and msg.price_raw < top))
        if old is None:
            # Databento's reference LOB implementation treats a missing modify as an add.
            # Preserve the anomaly explicitly so it cannot be mistaken for clean lineage.
            self.integrity["modify_missing_treated_as_add"] += 1
            new = self._add_order(msg)
            return ApplyEffect("M", msg.side, msg.price_raw, msg.size, None, new.size, None, True, False, True, touched, top)

        old_size = old.size
        old_price = old.price_raw
        old_side = old.side
        if old_side != msg.side:
            self.integrity["modify_side_change"] += 1
            self._remove_from_level(old)
            self.orders.pop(old.order_id, None)
            new = self._add_order(msg)
            return ApplyEffect("M", msg.side, msg.price_raw, msg.size, old_size, new.size, new.size - old_size, True, False, False, touched, top)

        priority_lost = old_price != msg.price_raw or msg.size > old_size
        if priority_lost:
            self._remove_from_level(old)
            old.price_raw = msg.price_raw
            old.size = max(0, msg.size)
            old.priority_recv_ns = msg.ts_recv_ns
            old.priority_sequence = msg.sequence
            old.last_update_recv_ns = msg.ts_recv_ns
            self.levels[old.side][old.price_raw].append(old.order_id)
        else:
            old.size = max(0, msg.size)
            old.last_update_recv_ns = msg.ts_recv_ns
        if old.size == 0:
            self._remove_from_level(old)
            self.orders.pop(old.order_id, None)
        return ApplyEffect(
            "M", old_side, msg.price_raw, msg.size, old_size, old.size,
            old.size - old_size, priority_lost, old.size == 0, False, touched, top,
        )

    def _book_effect(self, msg: NormalizedMbo) -> ApplyEffect:
        top = self.best_price_raw(msg.side) if msg.side in ("A", "B") else None
        touched = False
        if msg.side == "B":
            touched = top is None or msg.price_raw >= top
        elif msg.side == "A":
            touched = top is None or msg.price_raw <= top

        if msg.action == "R":
            self.orders.clear()
            self.levels = {"B": defaultdict(list), "A": defaultdict(list)}
            return ApplyEffect("R", "N", msg.price_raw, msg.size, None, None, None, False, True, False, False, None)
        if msg.action == "A":
            if msg.side not in ("A", "B"):
                self.integrity["add_invalid_side"] += 1
                return ApplyEffect("A", msg.side, msg.price_raw, msg.size, None, None, None, False, False, True, touched, top)
            if abs(msg.price_raw) >= UNDEF_PRICE and msg.flags & F_TOB:
                # Generic normalized top-of-book handling. GLBX.MDP3 true MBO should not
                # normally need this, but keeping it makes the adapter fail-safe across DBN.
                for oid in list(self.orders):
                    order = self.orders[oid]
                    if order.side == msg.side:
                        self._remove_from_level(order)
                        self.orders.pop(oid, None)
                return ApplyEffect("A", msg.side, msg.price_raw, msg.size, None, None, None, False, True, False, touched, top)
            order = self._add_order(msg)
            return ApplyEffect("A", msg.side, msg.price_raw, msg.size, None, order.size, order.size, False, False, False, touched, top)
        if msg.action == "C":
            return self._cancel(msg)
        if msg.action == "M":
            return self._modify(msg)
        if msg.action in ("T", "F", "N"):
            return ApplyEffect(msg.action, msg.side, msg.price_raw, msg.size, None, None, None, False, False, False, touched, top)
        raise ValueError(f"unsupported MBO action {msg.action!r}")

    def _append_activity(self, msg: NormalizedMbo, effect: ApplyEffect) -> None:
        if msg.is_snapshot:
            return
        self.activity.append({
            "ts_recv_ns": msg.ts_recv_ns,
            "action": msg.action,
            "side": msg.side,
            "price_raw": msg.price_raw,
            "size": msg.size,
            "size_delta": effect.size_delta,
            "priority_lost": effect.priority_lost,
            "missing_reference": effect.missing_reference,
            "top_touch": effect.touched_or_improved_top_before,
        })
        cutoff = msg.ts_recv_ns - max(ACTIVITY_WINDOWS_S) * 1_000_000_000
        while self.activity and self.activity[0]["ts_recv_ns"] < cutoff:
            self.activity.popleft()

    def apply(self, msg: NormalizedMbo) -> tuple[ApplyEffect, dict[str, Any] | None]:
        if msg.instrument_id != self.instrument_id:
            raise ValueError("instrument mismatch")
        if msg.action not in VALID_ACTIONS:
            raise ValueError(f"invalid action {msg.action!r}")
        if msg.side not in VALID_SIDES:
            raise ValueError(f"invalid side {msg.side!r}")

        if self.last_sequence is not None and msg.sequence < self.last_sequence and not msg.is_snapshot:
            self.integrity["sequence_regression"] += 1
        if self.last_recv_ns is not None and msg.ts_recv_ns < self.last_recv_ns and not msg.is_snapshot:
            self.integrity["receive_time_regression"] += 1
        self.last_sequence = max(self.last_sequence or msg.sequence, msg.sequence)
        self.last_recv_ns = max(self.last_recv_ns or msg.ts_recv_ns, msg.ts_recv_ns)
        self.last_event_ns = max(self.last_event_ns or msg.ts_event_ns, msg.ts_event_ns)
        self.raw_symbol = msg.raw_symbol or self.raw_symbol

        effect = self._book_effect(msg)
        self._append_activity(msg, effect)
        self.event_group.append(msg)
        if not msg.is_last:
            return effect, None
        frame = self.event_frame(msg.ts_recv_ns)
        self.event_group = []
        return effect, frame

    def _level(self, side: str, price_raw: int, now_ns: int, include_order_ids: bool) -> dict[str, Any]:
        ids = list(self.levels[side].get(price_raw, ()))
        orders = [self.orders[oid] for oid in ids if oid in self.orders]
        total = sum(o.size for o in orders)
        ages = [max(0.0, (now_ns - o.priority_recv_ns) / 1e9) for o in orders]
        out: dict[str, Any] = {
            "side": side,
            "price": decimal_price(price_raw),
            "price_raw": price_raw,
            "size": total,
            "order_count": len(orders),
            "front_order_size": None if not orders else orders[0].size,
            "front_order_age_s": None if not orders else ages[0],
            "queue_age_median_s": _quantile(ages, 0.5),
            "queue_age_p90_s": _quantile(ages, 0.9),
            "largest_order_share": _ratio(max((o.size for o in orders), default=0), total),
        }
        if include_order_ids:
            ahead = 0
            queue = []
            for order in orders:
                queue.append({
                    "order_id": order.order_id,
                    "size": order.size,
                    "volume_ahead": ahead,
                    "priority_recv_ns": order.priority_recv_ns,
                    "priority_sequence": order.priority_sequence,
                    "priority_age_s": max(0.0, (now_ns - order.priority_recv_ns) / 1e9),
                })
                ahead += order.size
            out["fifo_queue"] = queue
        return out

    def book_snapshot(self, now_ns: int, depth_levels: int = 10, include_full_depth: bool = False, include_order_ids: bool = False) -> dict[str, Any]:
        bids = self._prices("B")
        asks = self._prices("A")
        bid_levels = [self._level("B", p, now_ns, include_order_ids) for p in bids[:depth_levels]]
        ask_levels = [self._level("A", p, now_ns, include_order_ids) for p in asks[:depth_levels]]
        bid_size_full = sum(o.size for o in self.orders.values() if o.side == "B")
        ask_size_full = sum(o.size for o in self.orders.values() if o.side == "A")
        bid_size_n = sum(x["size"] for x in bid_levels)
        ask_size_n = sum(x["size"] for x in ask_levels)
        best_bid = None if not bid_levels else bid_levels[0]["price"]
        best_ask = None if not ask_levels else ask_levels[0]["price"]
        spread = None if best_bid is None or best_ask is None else best_ask - best_bid
        mid = None if best_bid is None or best_ask is None else 0.5 * (best_bid + best_ask)
        out: dict[str, Any] = {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "mid": mid,
            "top_n": depth_levels,
            "bid_levels": bid_levels,
            "ask_levels": ask_levels,
            "bid_depth_n": bid_size_n,
            "ask_depth_n": ask_size_n,
            "depth_imbalance_n": _ratio(bid_size_n - ask_size_n, bid_size_n + ask_size_n),
            "bid_depth_full": bid_size_full,
            "ask_depth_full": ask_size_full,
            "depth_imbalance_full": _ratio(bid_size_full - ask_size_full, bid_size_full + ask_size_full),
            "bid_price_level_count_full": len(bids),
            "ask_price_level_count_full": len(asks),
            "bid_order_count_full": sum(1 for o in self.orders.values() if o.side == "B"),
            "ask_order_count_full": sum(1 for o in self.orders.values() if o.side == "A"),
        }
        if include_full_depth:
            out["bid_levels_full"] = [self._level("B", p, now_ns, include_order_ids) for p in bids]
            out["ask_levels_full"] = [self._level("A", p, now_ns, include_order_ids) for p in asks]
        return out

    def rolling_activity(self, now_ns: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for seconds in ACTIVITY_WINDOWS_S:
            cutoff = now_ns - seconds * 1_000_000_000
            rows = [r for r in self.activity if r["ts_recv_ns"] >= cutoff]
            counts = Counter(r["action"] for r in rows)
            qty = Counter()
            side_qty = Counter()
            top_qty = Counter()
            priority_lost = 0
            missing_refs = 0
            for r in rows:
                qty[r["action"]] += max(0, int(r["size"]))
                side_qty[f"{r['action']}_{r['side']}"] += max(0, int(r["size"]))
                if r["top_touch"]:
                    top_qty[r["action"]] += max(0, int(r["size"]))
                priority_lost += int(bool(r["priority_lost"]))
                missing_refs += int(bool(r["missing_reference"]))
            trade_buy = side_qty.get("T_B", 0)
            trade_sell = side_qty.get("T_A", 0)
            add_qty = qty.get("A", 0)
            cancel_qty = qty.get("C", 0)
            out[str(seconds)] = {
                "event_count": len(rows),
                "action_count": dict(counts),
                "action_qty": dict(qty),
                "action_side_qty": dict(side_qty),
                "trade_buy_aggressor_qty": trade_buy,
                "trade_sell_aggressor_qty": trade_sell,
                "trade_aggressor_imbalance": _ratio(trade_buy - trade_sell, trade_buy + trade_sell),
                "add_cancel_churn": _ratio(cancel_qty, add_qty + cancel_qty),
                "top_level_add_qty_derived": top_qty.get("A", 0),
                "top_level_cancel_qty_derived": top_qty.get("C", 0),
                "priority_lost_modify_count": priority_lost,
                "missing_reference_count": missing_refs,
            }
        return out

    def event_frame(self, now_ns: int) -> dict[str, Any]:
        group = list(self.event_group)
        if not group:
            raise RuntimeError("empty event group")
        last = group[-1]
        return {
            "schema": "NG_MBO_V4_NATIVE_EVENT_FRAME_V1",
            "adapter_revision": ADAPTER_REVISION,
            "census_view": "V4_NATIVE_FULL",
            "instrument_id": self.instrument_id,
            "raw_symbol": self.raw_symbol,
            "publisher_id": last.publisher_id,
            "channel_id": last.channel_id,
            "sequence": last.sequence,
            "ts_event_ns": last.ts_event_ns,
            "ts_recv_ns": last.ts_recv_ns,
            "ts_in_delta_ns": last.ts_in_delta_ns,
            "causal_availability_clock": "ts_recv_ns",
            "event_group_complete_f_last": True,
            "snapshot_bootstrap_only": all(x.is_snapshot for x in group),
            "raw_actions": [x.public_dict() for x in group],
            "book": self.book_snapshot(now_ns, depth_levels=10, include_full_depth=False, include_order_ids=False),
            "activity": self.rolling_activity(now_ns),
            "integrity": dict(self.integrity),
            "native_priority_id_exposed": False,
            "fifo_priority_reconstructed": True,
        }

    def checkpoint_state(self, now_ns: int, include_full_depth: bool = True, include_order_ids: bool = True) -> dict[str, Any]:
        """Rich state intended for selected V4 causal checkpoints, not every tick."""
        return {
            "schema": "NG_MBO_V4_CHECKPOINT_STATE_V1",
            "adapter_revision": ADAPTER_REVISION,
            "instrument_id": self.instrument_id,
            "raw_symbol": self.raw_symbol,
            "ts_recv_ns": now_ns,
            "book": self.book_snapshot(now_ns, depth_levels=20, include_full_depth=include_full_depth, include_order_ids=include_order_ids),
            "activity": self.rolling_activity(now_ns),
            "integrity": dict(self.integrity),
        }

    def legacy_control_rows(self, frame: dict[str, Any]) -> list[dict[str, Any]]:
        """Project one completed MBO event group to the old trade/MBP-10-shaped surface.

        This is a compatibility control, not a claim of byte/row equivalence. It must
        pass an overlap comparison before it can support a five-year control census.
        """
        book = frame["book"]
        bids = book["bid_levels"]
        asks = book["ask_levels"]
        rows = []
        for raw in frame["raw_actions"]:
            # Fill/None are MBO-only execution/transport details.  Keep them on
            # V4_NATIVE_FULL, but do not invent rows that did not exist on the
            # historical MBP/trade-shaped LEGACY_CONTROL surface.
            if raw["action"] in ("F", "N"):
                continue
            rec: dict[str, Any] = {
                "adapter_revision": ADAPTER_REVISION,
                "census_view": "LEGACY_CONTROL",
                "ts_event": raw["ts_event_ns"] / 1e9,
                "ts_recv": raw["ts_recv_ns"] / 1e9,
                "instrument_id": raw["instrument_id"],
                "raw_symbol": raw.get("raw_symbol"),
                "action": raw["action"],
                "side": raw["side"],
                "price": raw["price"],
                "size": raw["size"],
                "sequence": raw["sequence"],
                "channel_id": raw["channel_id"],
                "flags": raw["flags"],
                "projection_at_f_last": True,
            }
            for i in range(10):
                bid = bids[i] if i < len(bids) else None
                ask = asks[i] if i < len(asks) else None
                rec[f"bid_px_{i:02d}"] = 0.0 if bid is None else bid["price"]
                rec[f"bid_sz_{i:02d}"] = 0 if bid is None else bid["size"]
                rec[f"ask_px_{i:02d}"] = 0.0 if ask is None else ask["price"]
                rec[f"ask_sz_{i:02d}"] = 0 if ask is None else ask["size"]
            rows.append(rec)
        return rows


class V4MboAdapter:
    def __init__(self) -> None:
        self.books: dict[int, InstrumentBook] = {}
        self.record_count = 0
        self.completed_event_group_count = 0

    @staticmethod
    def normalize(record: Any, raw_symbol: str | None = None, source_dbn_object: str | None = None, source_dbn_sha256: str | None = None) -> NormalizedMbo:
        action = _enum_text(_get(record, "action", "N"))
        side = _enum_text(_get(record, "side", "N"))
        msg = NormalizedMbo(
            instrument_id=_int(record, "instrument_id"),
            publisher_id=_int(record, "publisher_id"),
            channel_id=_int(record, "channel_id"),
            order_id=_int(record, "order_id"),
            action=action,
            side=side,
            price_raw=_int(record, "price", UNDEF_PRICE),
            size=_int(record, "size"),
            flags=_int(record, "flags"),
            sequence=_int(record, "sequence"),
            ts_event_ns=_int(record, "ts_event"),
            ts_recv_ns=_int(record, "ts_recv"),
            ts_in_delta_ns=_int(record, "ts_in_delta"),
            raw_symbol=raw_symbol,
            source_dbn_object=source_dbn_object,
            source_dbn_sha256=source_dbn_sha256,
        )
        if msg.instrument_id <= 0:
            raise ValueError("MBO record missing positive instrument_id")
        if msg.action not in VALID_ACTIONS:
            raise ValueError(f"unsupported action {msg.action!r}")
        if msg.side not in VALID_SIDES:
            raise ValueError(f"unsupported side {msg.side!r}")
        return msg

    def apply(self, record: Any, raw_symbol: str | None = None, source_dbn_object: str | None = None, source_dbn_sha256: str | None = None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        msg = self.normalize(record, raw_symbol, source_dbn_object, source_dbn_sha256)
        book = self.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))
        _, frame = book.apply(msg)
        self.record_count += 1
        if frame is None:
            return None, []
        self.completed_event_group_count += 1
        return frame, book.legacy_control_rows(frame)

    def assert_groups_closed(self) -> None:
        open_groups = {iid: len(book.event_group) for iid, book in self.books.items() if book.event_group}
        if open_groups:
            raise RuntimeError(f"source ended inside F_LAST event group: {open_groups}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class DeterministicJsonlGzip:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.tmp = Path(tempfile.mkstemp(prefix=path.name, suffix=".jsonl")[1])
        self.handle = self.tmp.open("wb")
        self.raw_hash = hashlib.sha256()
        self.rows = 0

    def write(self, obj: dict[str, Any]) -> None:
        data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.handle.write(data)
        self.raw_hash.update(data)
        self.rows += 1

    def close(self) -> dict[str, Any]:
        self.handle.close()
        with self.tmp.open("rb") as src, self.path.open("wb") as dst:
            with gzip.GzipFile(filename="", mode="wb", fileobj=dst, mtime=0) as gz:
                for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
                    gz.write(chunk)
        self.tmp.unlink(missing_ok=True)
        return {
            "path": str(self.path),
            "rows": self.rows,
            "uncompressed_jsonl_sha256": self.raw_hash.hexdigest(),
            "gzip_sha256": sha256_file(self.path),
        }


def _resolve_symbol(instrument_map: Any, instrument_id: int, ts_recv_ns: int) -> str | None:
    if instrument_map is None:
        return None
    try:
        when = datetime.fromtimestamp(ts_recv_ns / 1e9, tz=timezone.utc).date()
        value = instrument_map.resolve(instrument_id, when)
        return None if value is None else str(value)
    except Exception:
        return None


def process_dbn_files(paths: list[str], out_prefix: str) -> dict[str, Any]:
    try:
        import databento as db
    except ImportError as exc:
        raise SystemExit("databento package is required to process DBN files") from exc

    adapter = V4MboAdapter()
    native_writer = DeterministicJsonlGzip(Path(out_prefix + "_V4_NATIVE_EVENTS.jsonl.gz"))
    legacy_writer = DeterministicJsonlGzip(Path(out_prefix + "_LEGACY_CONTROL_ROWS.jsonl.gz"))
    sources = []
    try:
        for raw_path in paths:
            path = Path(raw_path)
            digest = sha256_file(path)
            store = db.DBNStore.from_file(str(path))
            instrument_map = None
            try:
                instrument_map = db.common.symbology.InstrumentMap()
                instrument_map.insert_metadata(store.metadata)
            except Exception:
                instrument_map = None
            mbo_records = 0
            complete_groups_before = adapter.completed_event_group_count
            for record in store:
                if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                    continue
                ts_recv_ns = _int(record, "ts_recv")
                instrument_id = _int(record, "instrument_id")
                symbol = _resolve_symbol(instrument_map, instrument_id, ts_recv_ns)
                frame, legacy = adapter.apply(
                    record,
                    raw_symbol=symbol,
                    source_dbn_object=str(path),
                    source_dbn_sha256=digest,
                )
                mbo_records += 1
                if frame is not None:
                    native_writer.write(frame)
                    for row in legacy:
                        legacy_writer.write(row)
            adapter.assert_groups_closed()
            sources.append({
                "path": str(path),
                "sha256": digest,
                "mbo_records": mbo_records,
                "completed_event_groups": adapter.completed_event_group_count - complete_groups_before,
            })
    finally:
        native_summary = native_writer.close()
        legacy_summary = legacy_writer.close()

    summary = {
        "status": "NG_MBO_V4_STATE_ADAPTER_COMPLETE",
        "adapter_revision": ADAPTER_REVISION,
        "canonical_source_rewritten": False,
        "census_views": ["LEGACY_CONTROL", "V4_NATIVE_FULL"],
        "native_priority_id_exposed": False,
        "fifo_priority_reconstructed": True,
        "causal_availability_clock": "ts_recv_ns",
        "f_last_state_boundary_required": True,
        "sources": sources,
        "record_count": adapter.record_count,
        "completed_event_group_count": adapter.completed_event_group_count,
        "instrument_count": len(adapter.books),
        "integrity_by_instrument": {str(iid): dict(book.integrity) for iid, book in sorted(adapter.books.items())},
        "v4_native_output": native_summary,
        "legacy_control_output": legacy_summary,
        "legacy_control_equivalence_proven": False,
        "full_five_year_census_authorized": False,
        "protected_mutations": {
            "frozen_detector": False,
            "frozen_canonical_rows": False,
            "phase1_phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "spawn_py": False,
        },
    }
    Path(out_prefix + "_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("dbn", nargs="+")
    args = ap.parse_args()
    summary = process_dbn_files(args.dbn, args.out_prefix)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
