#!/usr/bin/env python3
"""Causal NG live onset/divergence/exhaustion telemetry.

This enriches the existing live collector and coach path. It is not a second daily
forecaster and has no execution authority. The output separates:
- move_onset_pressure: descriptive readiness/transition telemetry;
- signed_flow: nascent-leg likelihood evidence;
- divergence_exhaustion: continuation versus flip-risk evidence;
- mbo_queue: order-level add/cancel/fill/recruitment diagnostics.

All state is computed from records received at or before the snapshot timestamp.
Thresholds for onset/regime labels are explicit SHADOW hypotheses pending NG-specific
walk-forward calibration on historical L1 and MBO.
"""
from __future__ import annotations

import statistics
from collections import defaultdict, deque
from typing import Any

import numpy as np

from odcore.info_dipole import divergence, signed_flow_features

WINDOW_S = 300.0
SHORT_S = 60.0
BASELINE_S = 900.0


def _enum(value: Any) -> str:
    return str(getattr(value, "name", value or "N")).upper()


def _trade_direction(side: Any) -> str | None:
    # Databento trade side: B = buyer aggressor, A = seller aggressor.
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
        "A": "ADD", "ADD": "ADD",
        "M": "MODIFY", "MODIFY": "MODIFY",
        "C": "CANCEL", "CANCEL": "CANCEL",
        "T": "TRADE", "TRADE": "TRADE",
        "F": "FILL", "FILL": "FILL",
        "R": "CLEAR", "CLEAR": "CLEAR",
    }.get(text, text)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


class NGLiveOperator:
    """Low-allocation rolling feature state for the collector callback."""

    def __init__(self) -> None:
        self.second_bins: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        self.trades: deque[tuple[float, float, float, str]] = deque()
        self.mbo: deque[tuple[float, str, str | None, float]] = deque()
        self.last_price: float | None = None
        self.trade_rate_history: deque[tuple[float, float]] = deque()
        self.mapping_flags: set[str] = set()

    def _purge(self, now_s: float) -> None:
        cutoff = now_s - BASELINE_S
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()
        while self.mbo and self.mbo[0][0] < cutoff:
            self.mbo.popleft()
        for second in list(self.second_bins):
            if second < int(cutoff) - 1:
                del self.second_bins[second]
        while self.trade_rate_history and self.trade_rate_history[0][0] < now_s - 3600.0:
            self.trade_rate_history.popleft()

    def on_trade(self, ts_s: float, price: float, size: float, side: Any) -> None:
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

    def on_mbo(self, ts_s: float, action: Any, side: Any, size: float) -> None:
        normalized_side = _book_side(side)
        if normalized_side is None and _enum(side) != "N":
            self.mapping_flags.add(f"unmapped_mbo_side:{_enum(side)}")
        self.mbo.append((ts_s, _action(action), normalized_side, float(size or 0.0)))
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
                buy.append(0.0); sell.append(0.0); prices.append(last); travel.append(0.0)
            else:
                buy.append(row[0]); sell.append(row[1])
                if row[2] > 0:
                    last = row[2]
                prices.append(last); travel.append(row[3])
        return np.asarray(buy), np.asarray(sell), np.asarray(prices), np.asarray(travel)

    def _queue(self, now_s: float, price_drift: float) -> dict[str, Any]:
        stats = {"BID": defaultdict(float), "ASK": defaultdict(float)}
        for ts_s, action, side, size in self.mbo:
            if ts_s < now_s - SHORT_S or side not in stats:
                continue
            stats[side][f"{action.lower()}_events"] += 1.0
            stats[side][f"{action.lower()}_size"] += size

        consumed_side = "ASK" if price_drift > 0 else "BID" if price_drift < 0 else None
        recruitment = None
        if consumed_side:
            values = stats[consumed_side]
            added = values.get("add_size", 0.0) + values.get("modify_size", 0.0)
            removed = (values.get("cancel_size", 0.0) + values.get("fill_size", 0.0)
                       + values.get("trade_size", 0.0))
            total = added + removed
            recruitment = (added - removed) / total if total else None
        return {
            "window_s": SHORT_S,
            "consumed_side": consumed_side,
            "far_side_recruitment": recruitment,
            "events": {side: dict(values) for side, values in stats.items()},
            "interpretation": (
                "positive recruitment = resting liquidity added faster than removed on the side price is consuming; "
                "negative = removal/consumption dominates"
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
            "schema": "ng_live_operator.v1",
            "as_of_event_s": now_s,
            "authority": "SHADOW_TELEMETRY",
            "execution_authority": false,
            "source": "L1/trades + MBO",
            "window_s": WINDOW_S,
            "move_onset_pressure": {
                "value": round(onset_pressure, 5),
                "regime": regime,
                "activity_ratio": None if activity_ratio is None else round(activity_ratio, 4),
                "price_efficiency": round(efficiency, 5),
                "note": "descriptive onset/readiness hypothesis; not direction and not yet NG-calibrated"
            },
            "signed_flow": flow,
            "divergence_exhaustion": div,
            "mbo_queue": queue,
            "data_quality": {
                "trade_events_15m": baseline_n,
                "trade_events_60s": recent_n,
                "mapping_flags": sorted(self.mapping_flags),
                "missing_is_visible": true
            },
            "retest_registry": "research/kalshi/knowledge/signal_retest_registry.json"
        }
