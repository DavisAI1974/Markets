#!/usr/bin/env python3
"""Causal NG live onset, divergence, exhaustion, and MBO queue telemetry.

This module enriches the existing live collector and coach path. It is not a
second daily forecaster and has no execution authority. The outputs remain
separate:

- move_onset_pressure: descriptive readiness/transition telemetry;
- signed_flow: nascent-leg likelihood evidence from the dedicated trades feed;
- divergence_exhaustion: continuation versus flip-risk evidence;
- mbo_queue: exact resting-order state plus recent replenishment/removal.

Databento conventions enforced here:

- Trade (T), Fill (F), and None (N) do not change the resting book.
- Cancel (C) carries the actual partial/full size reduction.
- Modify (M) replaces price/size and loses priority on a price change or size
  increase.
- A book-derived value is publishable only after F_LAST for the instrument.
- Snapshot records rebuild state but never count as fresh queue activity.

All state is causal: only records received at or before the snapshot are used.
Thresholds for onset/regime labels remain SHADOW hypotheses pending NG-specific
walk-forward calibration on historical L1/trades and MBO.
"""
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from odcore.info_dipole import divergence, signed_flow_features

WINDOW_S = 300.0
SHORT_S = 60.0
BASELINE_S = 900.0

F_LAST = 1 << 7
F_TOB = 1 << 6
F_SNAPSHOT = 1 << 5
F_BAD_TS_RECV = 1 << 3
F_MAYBE_BAD_BOOK = 1 << 2


def _enum(value: Any) -> str:
    return str(getattr(value, "name", value or "N")).upper()


def _flags(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _trade_direction(side: Any) -> str | None:
    """Databento trade side: B=buyer aggressor, A=seller aggressor."""
    text = _enum(side)
    if text in {"B", "BID", "BUY"}:
        return "BUY"
    if text in {"A", "ASK", "SELL"}:
        return "SELL"
    return None


def _book_side(side: Any) -> str | None:
    text = _enum(side)
    if text in {"B", "BID", "BUY"}:
        return "BID"
    if text in {"A", "ASK", "SELL"}:
        return "ASK"
    return None


def _action(value: Any) -> str:
    text = _enum(value)
    return {
        "ADD": "A",
        "MODIFY": "M",
        "CANCEL": "C",
        "CLEAR": "R",
        "TRADE": "T",
        "FILL": "F",
        "NONE": "N",
    }.get(text, text[:1] if text else "N")


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(slots=True)
class RestingOrder:
    side: str
    price: float
    size: float
    priority_event_s: float
    priority_seq: int


class NGLiveOperator:
    """Low-allocation rolling state for the live collector callback."""

    def __init__(self) -> None:
        self.second_bins: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        self.trades: deque[tuple[float, float, float, str]] = deque()
        # ts, side, added size, removed size, action
        self.book_deltas: deque[tuple[float, str, float, float, str]] = deque()
        self.orders: dict[int, RestingOrder] = {}
        self.last_price: float | None = None
        self.trade_rate_history: deque[tuple[float, float]] = deque()
        self.mapping_flags: set[str] = set()
        self.missing_order_events = 0
        self.event_seq = 0
        self.complete_events = 0
        self.last_complete_event_s: float | None = None
        self.book_ready = False
        self.snapshot_active = False
        self.snapshot_complete = False
        self.maybe_bad_book = False

    def _purge(self, now_s: float) -> None:
        cutoff = now_s - BASELINE_S
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()
        while self.book_deltas and self.book_deltas[0][0] < cutoff:
            self.book_deltas.popleft()
        for second in list(self.second_bins):
            if second < int(cutoff) - 1:
                del self.second_bins[second]
        while self.trade_rate_history and self.trade_rate_history[0][0] < now_s - 3600.0:
            self.trade_rate_history.popleft()

    def on_trade(self, ts_s: float, price: float, size: float, side: Any) -> None:
        """Consume only the dedicated Databento trades-schema record."""
        direction = _trade_direction(side)
        if direction is None:
            self.mapping_flags.add(f"unmapped_trade_side:{_enum(side)}")
            return
        row = self.second_bins[int(ts_s)]
        row[0 if direction == "BUY" else 1] += float(size)
        row[2] = float(price)
        if self.last_price is not None:
            row[3] += abs(float(price) - self.last_price)
        self.last_price = float(price)
        self.trades.append((ts_s, float(price), float(size), direction))
        self._purge(ts_s)

    def _record_delta(
        self,
        ts_s: float,
        side: str | None,
        added: float,
        removed: float,
        action: str,
        snapshot: bool,
    ) -> None:
        if snapshot or side not in {"BID", "ASK"}:
            return
        if added > 0 or removed > 0:
            self.book_deltas.append((ts_s, side, float(added), float(removed), action))

    def on_mbo(
        self,
        ts_s: float,
        action: Any,
        side: Any,
        size: float,
        order_id: int,
        price: float | None,
        flags: Any,
    ) -> None:
        """Apply one normalized Databento MBO record to the working book."""
        act = _action(action)
        book_side = _book_side(side)
        flag_bits = _flags(flags)
        snapshot = bool(flag_bits & F_SNAPSHOT)
        complete = bool(flag_bits & F_LAST)
        self.event_seq += 1
        self.book_ready = False
        self.snapshot_active = self.snapshot_active or snapshot
        self.maybe_bad_book = self.maybe_bad_book or bool(flag_bits & F_MAYBE_BAD_BOOK)

        if book_side is None and _enum(side) not in {"N", "NONE"}:
            self.mapping_flags.add(f"unmapped_mbo_side:{_enum(side)}")

        # Trade, Fill, and None are informational. The accompanying Cancel/Modify
        # record is the only resting-book change.
        if act in {"T", "F", "N"}:
            pass
        elif act == "R":
            self.orders.clear()
            if snapshot:
                self.snapshot_active = True
                self.snapshot_complete = False
        elif act == "A":
            if book_side is None:
                self.mapping_flags.add("add_without_book_side")
            elif flag_bits & F_TOB:
                # A top-of-book add replaces the prior synthetic order on that side.
                self.orders = {oid: order for oid, order in self.orders.items() if order.side != book_side}
                if price is not None:
                    self.orders[int(order_id)] = RestingOrder(
                        book_side, float(price), float(size), ts_s, self.event_seq
                    )
                    self._record_delta(ts_s, book_side, float(size), 0.0, act, snapshot)
            elif price is not None:
                self.orders[int(order_id)] = RestingOrder(
                    book_side, float(price), float(size), ts_s, self.event_seq
                )
                self._record_delta(ts_s, book_side, float(size), 0.0, act, snapshot)
        elif act == "C":
            existing = self.orders.get(int(order_id))
            if existing is None:
                self.missing_order_events += 1
                self.mapping_flags.add("cancel_missing_order")
            else:
                reduction = min(float(size), existing.size)
                existing.size -= reduction
                self._record_delta(ts_s, existing.side, 0.0, reduction, act, snapshot)
                if existing.size <= 0:
                    self.orders.pop(int(order_id), None)
        elif act == "M":
            existing = self.orders.get(int(order_id))
            if existing is None:
                self.missing_order_events += 1
                if book_side is not None and price is not None:
                    self.orders[int(order_id)] = RestingOrder(
                        book_side, float(price), float(size), ts_s, self.event_seq
                    )
                    self._record_delta(ts_s, book_side, float(size), 0.0, act, snapshot)
            elif book_side is not None and price is not None:
                old_side, old_price, old_size = existing.side, existing.price, existing.size
                new_size = float(size)
                loses_priority = old_price != float(price) or new_size > old_size
                if old_side != book_side or old_price != float(price):
                    self._record_delta(ts_s, old_side, 0.0, old_size, act, snapshot)
                    self._record_delta(ts_s, book_side, new_size, 0.0, act, snapshot)
                elif new_size > old_size:
                    self._record_delta(ts_s, book_side, new_size - old_size, 0.0, act, snapshot)
                elif new_size < old_size:
                    self._record_delta(ts_s, book_side, 0.0, old_size - new_size, act, snapshot)
                existing.side = book_side
                existing.price = float(price)
                existing.size = new_size
                if loses_priority:
                    existing.priority_event_s = ts_s
                    existing.priority_seq = self.event_seq
        else:
            self.mapping_flags.add(f"unknown_mbo_action:{act}")

        if complete:
            self.complete_events += 1
            self.last_complete_event_s = ts_s
            self.book_ready = not self.maybe_bad_book
            if self.snapshot_active:
                self.snapshot_complete = True
                self.snapshot_active = False
        self._purge(ts_s)

    def _series(self, now_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        start, end = int(now_s - WINDOW_S) + 1, int(now_s)
        buy: list[float] = []
        sell: list[float] = []
        prices: list[float] = []
        travel: list[float] = []
        last = self.last_price or 0.0
        for second in range(start, end + 1):
            row = self.second_bins.get(second)
            if row is None:
                buy.append(0.0)
                sell.append(0.0)
                prices.append(last)
                travel.append(0.0)
            else:
                buy.append(row[0])
                sell.append(row[1])
                if row[2] > 0:
                    last = row[2]
                prices.append(last)
                travel.append(row[3])
        return np.asarray(buy), np.asarray(sell), np.asarray(prices), np.asarray(travel)

    def _bbo(self) -> dict[str, Any]:
        bids = [order for order in self.orders.values() if order.side == "BID"]
        asks = [order for order in self.orders.values() if order.side == "ASK"]
        best_bid = max((order.price for order in bids), default=None)
        best_ask = min((order.price for order in asks), default=None)

        def level(side_orders: list[RestingOrder], price_value: float | None) -> dict[str, Any] | None:
            if price_value is None:
                return None
            at_level = [order for order in side_orders if order.price == price_value]
            return {
                "price": price_value,
                "size": round(sum(order.size for order in at_level), 6),
                "order_count": len(at_level),
                # A newly posted order is behind every currently resting lot at the level.
                "hypothetical_new_order_queue_ahead": round(sum(order.size for order in at_level), 6),
            }

        return {
            "best_bid": level(bids, best_bid),
            "best_ask": level(asks, best_ask),
            "spread": None if best_bid is None or best_ask is None else round(best_ask - best_bid, 9),
            "resting_orders": len(self.orders),
        }

    def _queue(self, now_s: float, price_drift: float) -> dict[str, Any]:
        stats = {
            "BID": {"added": 0.0, "removed": 0.0, "events": 0},
            "ASK": {"added": 0.0, "removed": 0.0, "events": 0},
        }
        for ts_s, side, added, removed, _action_name in self.book_deltas:
            if ts_s < now_s - SHORT_S:
                continue
            stats[side]["added"] += added
            stats[side]["removed"] += removed
            stats[side]["events"] += 1

        consumed_side = "ASK" if price_drift > 0 else "BID" if price_drift < 0 else None
        recruitment = None
        if consumed_side:
            values = stats[consumed_side]
            total = values["added"] + values["removed"]
            recruitment = (values["added"] - values["removed"]) / total if total else None
        return {
            "window_s": SHORT_S,
            "book_complete": self.book_ready,
            "snapshot_complete": self.snapshot_complete,
            "maybe_bad_book": self.maybe_bad_book,
            "consumed_side": consumed_side,
            "far_side_recruitment": None if recruitment is None else round(recruitment, 6),
            "recent_book_deltas": {
                side: {
                    "added_size": round(values["added"], 6),
                    "removed_size": round(values["removed"], 6),
                    "events": values["events"],
                }
                for side, values in stats.items()
            },
            "bbo": self._bbo() if self.book_ready else None,
            "interpretation": (
                "positive recruitment means Add/Modify growth exceeds Cancel removal on the side price is consuming; "
                "Trade and Fill are excluded because they do not update the Databento resting book"
            ),
        }

    def snapshot(self, now_s: float) -> dict[str, Any]:
        self._purge(now_s)
        buy, sell, prices, travel = self._series(now_s)
        volume = float(buy.sum() + sell.sum())
        price_drift = float(prices[-1] - prices[0]) if prices.size and prices[0] > 0 else 0.0
        gross_travel = float(travel.sum())
        efficiency = abs(price_drift) / gross_travel if gross_travel > 0 else 0.0

        flow = signed_flow_features(buy, sell) if volume > 0 else None
        div = divergence(buy, sell, price_drift) if volume > 0 and price_drift != 0 else None

        recent_n = sum(1 for row in self.trades if row[0] >= now_s - SHORT_S)
        baseline_n = len(self.trades)
        short_rate = recent_n / SHORT_S
        baseline_rate = baseline_n / BASELINE_S
        self.trade_rate_history.append((now_s, short_rate))
        history = [value for _, value in self.trade_rate_history]
        median_rate = statistics.median(history) if history else 0.0
        activity_ratio = short_rate / median_rate if median_rate > 0 else (
            short_rate / baseline_rate if baseline_rate > 0 else None
        )

        queue = self._queue(now_s, price_drift)
        recruitment = queue.get("far_side_recruitment")
        flow_level = abs(float(flow["imb_level"])) if flow else 0.0
        flow_change = abs(float(flow["imb_flow"])) if flow else 0.0
        activity = _clip(((activity_ratio or 1.0) - 0.75) / 1.75)
        queue_stress = 0.0 if recruitment is None else _clip(max(0.0, -float(recruitment)))
        onset_pressure = _clip(
            0.35 * _clip(flow_level / 0.35)
            + 0.20 * _clip(flow_change / 0.25)
            + 0.25 * activity
            + 0.10 * _clip(efficiency)
            + 0.10 * queue_stress
        )

        if volume <= 0 or recent_n < 6:
            regime = "insufficient_data"
        elif (activity_ratio or 0.0) < 0.55:
            regime = "depleted"
        elif onset_pressure >= 0.78 and efficiency >= 0.55:
            regime = "cascade"
        elif flow_level >= 0.18 and efficiency >= 0.30:
            regime = "channeled"
        elif onset_pressure >= 0.55 or (div and div["expect"] in {"flip_risk", "reversal"}):
            regime = "transition"
        elif efficiency < 0.12 and (activity_ratio or 1.0) >= 1.0:
            regime = "recirculating_watch"
        else:
            regime = "equilibrium"

        return {
            "schema": "ng_live_operator.v2",
            "as_of_event_s": now_s,
            "authority": "SHADOW_TELEMETRY",
            "execution_authority": False,
            "source": "Databento trades + MBO",
            "window_s": WINDOW_S,
            "move_onset_pressure": {
                "value": round(onset_pressure, 5),
                "regime": regime,
                "activity_ratio": None if activity_ratio is None else round(activity_ratio, 4),
                "price_efficiency": round(efficiency, 5),
                "note": "descriptive onset/readiness hypothesis; not direction and not yet NG-calibrated",
            },
            "signed_flow": flow,
            "divergence_exhaustion": div,
            "mbo_queue": queue,
            "data_quality": {
                "trade_events_15m": baseline_n,
                "trade_events_60s": recent_n,
                "complete_mbo_events": self.complete_events,
                "last_complete_event_s": self.last_complete_event_s,
                "missing_order_events": self.missing_order_events,
                "mapping_flags": sorted(self.mapping_flags),
                "book_complete": self.book_ready,
                "snapshot_active": self.snapshot_active,
                "snapshot_complete": self.snapshot_complete,
                "maybe_bad_book": self.maybe_bad_book,
                "missing_is_visible": True,
            },
            "retest_registry": "research/kalshi/knowledge/signal_retest_registry.json",
        }


def selftest() -> int:
    op = NGLiveOperator()
    last = F_LAST
    # Add one bid order. Fill/Trade do not change the resting order.
    op.on_mbo(1.0, "A", "B", 10, 1, 3.000, last)
    assert op.orders[1].size == 10
    op.on_mbo(2.0, "F", "B", 3, 1, 3.000, last)
    op.on_mbo(3.0, "T", "A", 3, 0, 3.000, last)
    assert op.orders[1].size == 10
    # Cancel reduces by the stated amount; modify size increase loses priority.
    op.on_mbo(4.0, "C", "B", 3, 1, 3.000, last)
    assert op.orders[1].size == 7
    old_seq = op.orders[1].priority_seq
    op.on_mbo(5.0, "M", "B", 12, 1, 3.000, last)
    assert op.orders[1].size == 12 and op.orders[1].priority_seq > old_seq
    op.on_mbo(6.0, "A", "A", 8, 2, 3.001, last)
    snap = op.snapshot(6.0)
    assert snap["mbo_queue"]["bbo"]["best_bid"]["size"] == 12
    assert snap["mbo_queue"]["bbo"]["best_ask"]["size"] == 8
    # Snapshot adds rebuild the book but do not pollute recent activity.
    op.on_mbo(10.0, "R", "N", 0, 0, None, F_SNAPSHOT)
    op.on_mbo(10.1, "A", "B", 4, 3, 2.999, F_SNAPSHOT | F_LAST)
    snap2 = op.snapshot(10.1)
    assert snap2["mbo_queue"]["snapshot_complete"] is True
    print("[ng_live_operator] selftest PASS")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    raise SystemExit(selftest() if args.selftest else 0)
