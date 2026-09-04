#!/usr/bin/env python3
"""REAL_TIME_FRANKIE's own pass over source day 20211003 (run frankie-a-memory-rt-33746436209-1).

Every number this pass writes is computed here, from the raw member rows (raw_actions, book_full,
clocks), the legacy observable rows and the lifecycle rows, all consumed ONLY through
`CausalGroupStream` in ts_recv_ns order. The runner's calculation_result.json is never opened.
Lifecycle rows that ride inside the stream are used for RECONCILIATION against what this pass
computed from the more primitive rows (4.0 second-by-second, the detector's candidates), and
that reconciliation is written down agree/disagree; they are never adopted in place of a
computation.

Written at every staged invocation cutoff (19) and at the stream-end cutoff (the last delivered
group's F_LAST receive), which is where whole-day tallies and drained STREAM_END rows are
lawfully knowable.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_bytes,
    canonical_hash,
    load_registry,
)

RUN_ID = "frankie-a-memory-rt-33746436209-1"
ARM = "A_MEMORY"
ROLE = "REAL_TIME_FRANKIE"
SOURCE_DAY = "20211003"
SOURCE_ROLE = "SCORED_FINDINGS_DAY"
SESSION_ID = "session_014m3YsXKuT773qhNQLuWahu"
MODEL = "claude-fable-5-1"
NS = 1_000_000_000
TICK_RAW = 1_000_000
UNDEF_PRICE = 9223372036854775807

CLK_RECV = "clock_receive_time"
CLK_EVENT = "clock_event_time"
CLK_KNOWN = "clock_event_known_by"
CLK_FEAT = "clock_feature_availability"
CLK_DISC = "clock_prospective_discovery_confirmation"
CLK_MODEL = "clock_model_evaluation"

# Substrate / detector parameters, declared once. These are the frozen program's own constants
# as the delivered candidate rows and the mission's seed vocabulary declare them; they are
# reported on every row they shape (contract 4.0b) so two runs under different values are two
# populations. Nothing else in this pass is a fixed time interval.
ROLL_WINDOW = 20
PEAK_QUANTILE = 0.85
LOCAL_RADIUS = 5
REFRACTORY = 45
BASELINE_START = 30
BASELINE_LAG = 9
WARMUP_SECONDS = 900
MIN_THRESHOLD_OBS = 600
THRESHOLD_OBS_CAP = 86400
ZERO_FLOW_EPS = 1e-12
CLUSTER_VERSION = "FRK_LEADER_L1_LOG1P_R1.0_V1"
CLUSTER_RADIUS = 1.0

MISSION_SHA = "e14f28812bf9be09dfbd74c40a7fda181dfda16effa0a9e39dee45a9bf9b559e"
CONTRACT_PATH = Path("research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md")
KNOWLEDGE_MANIFEST_SHA = "131ae230f99dd26ce1b08804cfcaa309c328c42cb4129e661209b4dd23852f33"
SOURCE_MANIFEST_SHA = "a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba"
KNOWLEDGE_RECEIPT_SHA = "6dc5825b578ac6fd3a6afa5b13c76bcd359a857d738610e64b02efb654891ea4"
DELIVERY_RECEIPT_SHA = "3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b"


def rd(ns: int, clock: str = CLK_RECV) -> dict[str, Any]:
    return {"clock": clock, "observed_ns": int(ns)}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fnum(x: float) -> float:
    return float(round(x, 9))


def qs(values: list[float]) -> dict[str, Any]:
    """Observed quantile set + extremes + mean + sum; never a mean alone."""
    n = len(values)
    if n == 0:
        return {"n": 0}
    s = sorted(values)

    def q(p: float) -> float:
        return s[min(n - 1, int(math.floor(p * (n - 1) + 0.5)))]

    return {
        "n": n, "min": s[0], "p10": q(0.10), "p25": q(0.25), "p50": q(0.50), "p75": q(0.75),
        "p90": q(0.90), "p99": q(0.99), "max": s[-1], "mean": fnum(sum(s) / n), "sum": fnum(sum(s)),
    }


def km(times: list[float], events: list[bool]) -> dict[str, Any]:
    """Kaplan-Meier product-limit with at-risk counts; times at which S first reaches each level."""
    n = len(times)
    out: dict[str, Any] = {"estimator": "KAPLAN_MEIER_PRODUCT_LIMIT", "n": n, "events": int(sum(events)),
                           "censored": int(n - sum(events))}
    if n == 0:
        return out
    order = sorted(range(n), key=lambda i: (times[i], not events[i]))
    s = 1.0
    at_risk = n
    levels = [0.9, 0.75, 0.5, 0.25, 0.1, 0.05]
    reached: dict[float, float] = {}
    i = 0
    while i < n:
        t = times[order[i]]
        d = 0
        c = 0
        j = i
        while j < n and times[order[j]] == t:
            if events[order[j]]:
                d += 1
            else:
                c += 1
            j += 1
        if d > 0 and at_risk > 0:
            s *= 1.0 - d / at_risk
            for lv in levels:
                if lv not in reached and s <= lv:
                    reached[lv] = t
        at_risk -= d + c
        i = j
    for lv in levels:
        out[f"time_ns_at_S{lv}"] = reached.get(lv)
    out["final_survival"] = fnum(s)
    out["final_time_ns"] = max(times)
    return out


def average(value: float, *, numerator: float, formula: str, population: str, denominator: int,
            family: str, subfamily: str, side: str, phase: str, status: str, cutoff: int,
            missingness: str, inclusion: str, segment: int = 18904,
            cluster_version: str = "NO_CLUSTER_STRATUM", clock: str = CLK_RECV) -> dict[str, Any]:
    return {
        "value": fnum(value),
        "strata": {
            "numerator": fnum(numerator), "formula": formula, "population": population,
            "denominator": int(denominator), "source_day": SOURCE_DAY, "source_role": SOURCE_ROLE,
            "family": family, "subfamily": subfamily, "cluster_version": cluster_version,
            "side_or_mirror_orientation": side, "session": "CME_GLOBEX_SUNDAY_REOPEN_20211003",
            "phase": phase, "continuity_segment": segment, "causal_clock": clock,
            "cutoff_recv_ns": int(cutoff), "status": status, "missingness_rule": missingness,
            "inclusion_rule": inclusion,
        },
    }


def frozen_quantile(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[int(pos)]
    return sorted_vals[lo] * (hi - pos) + sorted_vals[hi] * (pos - lo)


def median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return float("nan")
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


class Substrate:
    """4.0: per-second aggressor classification by the midpoint rule, roll20 and window flow."""

    def __init__(self) -> None:
        self.buy: dict[int, float] = defaultdict(float)
        self.sell: dict[int, float] = defaultdict(float)
        self.buy_trades: Counter = Counter()
        self.sell_trades: Counter = Counter()
        self.at_mid: Counter = Counter()
        self.no_quote: Counter = Counter()
        self.unusable: Counter = Counter()
        self.rows: Counter = Counter()
        self.last_quote: dict[int, tuple[float, float]] = {}
        self.first_second: int | None = None
        self.next_second: int | None = None
        self.completed: dict[int, dict[str, Any]] = {}
        self.class_census: Counter = Counter()
        self.window_census: Counter = Counter()

    def observe_legacy(self, row: dict[str, Any]) -> None:
        sec = int(math.floor(float(row["ts_recv"])))
        if self.first_second is None:
            self.first_second = sec
            self.next_second = sec
        self.rows[sec] += 1
        if row.get("action") != "T":
            return
        price = row.get("price")
        size = row.get("size")
        bid = row.get("bid_px_00")
        ask = row.get("ask_px_00")
        try:
            price = float(price)
            size = float(size)
        except (TypeError, ValueError):
            self.unusable[sec] += 1
            return
        if not (math.isfinite(price) and math.isfinite(size)) or price <= 0 or size <= 0:
            self.unusable[sec] += 1
            return
        try:
            bid = float(bid)
            ask = float(ask)
        except (TypeError, ValueError):
            self.no_quote[sec] += 1
            return
        if not (math.isfinite(bid) and math.isfinite(ask)) or bid <= 0 or ask < bid:
            self.no_quote[sec] += 1
            return
        mid = 0.5 * (bid + ask)
        self.last_quote[sec] = (bid, ask)
        if price > mid:
            self.buy[sec] += size
            self.buy_trades[sec] += 1
        elif price < mid:
            self.sell[sec] += size
            self.sell_trades[sec] += 1
        else:
            self.at_mid[sec] += 1

    def complete_through(self, cutoff_ns: int) -> list[dict[str, Any]]:
        """Every second s with (s+1)*NS <= cutoff is final; emit its exact row."""
        out = []
        if self.next_second is None:
            return out
        while (self.next_second + 1) * NS <= cutoff_ns:
            s = self.next_second
            b = self.buy.get(s, 0.0)
            sl = self.sell.get(s, 0.0)
            lo = s - ROLL_WINDOW + 1
            wb = sum(self.buy.get(x, 0.0) for x in range(lo, s + 1))
            ws = sum(self.sell.get(x, 0.0) for x in range(lo, s + 1))
            tot = wb + ws
            roll = (wb - ws) / tot if tot > 0 else float("nan")
            wflow = wb - ws
            trades = self.buy_trades.get(s, 0) + self.sell_trades.get(s, 0) + self.at_mid.get(s, 0) \
                + self.no_quote.get(s, 0) + self.unusable.get(s, 0)
            if b > sl:
                cls = "BUY"
            elif sl > b:
                cls = "SELL"
            elif self.at_mid.get(s, 0) > 0 and trades == self.at_mid.get(s, 0):
                cls = "EXCLUDED_AT_MID"
            elif self.no_quote.get(s, 0) > 0 and (b + sl) == 0 and self.at_mid.get(s, 0) == 0:
                cls = "NO_QUOTE"
            elif self.unusable.get(s, 0) > 0 and (b + sl) == 0:
                cls = "UNUSABLE_PRICE_OR_SIZE"
            else:
                cls = "NO_DIRECTION"
            wdir = "LONG" if wflow > 0 else ("SHORT" if wflow < 0 else "NO_DIRECTION")
            row = {
                "second": s, "buy_volume": b, "sell_volume": sl, "buy_trades": self.buy_trades.get(s, 0),
                "sell_trades": self.sell_trades.get(s, 0), "at_mid_trades": self.at_mid.get(s, 0),
                "no_quote_trades": self.no_quote.get(s, 0), "unusable_trades": self.unusable.get(s, 0),
                "rows": self.rows.get(s, 0), "classification": cls, "roll20": roll,
                "window_signed_flow": wflow, "window_volume": tot, "window_direction": wdir,
                "completed_at_recv_ns": (s + 1) * NS,
            }
            self.completed[s] = row
            self.class_census[cls] += 1
            self.window_census[wdir] += 1
            out.append(row)
            self.next_second += 1
        return out


class OwnDetector:
    """My own causal peak detector under the declared parameters (4.0b).

    Trailing causal quantile bar over finite |flow| observations (sorted list), warm-up on both
    seconds seen and finite observations, zero-flow guard, local maximum over +/- LOCAL_RADIUS,
    prominence against the median of |flow| over t-30..t-10, windowed prominence selection with
    a refractory enforced against what was picked. Every judged second leaves by one named door.
    Also emits threshold-crossing ALERTS (the pre-birth signal 4.11 tests), never used to select.
    """

    def __init__(self, segment: int) -> None:
        self.segment = segment
        self.flow: list[tuple[int, float]] = []  # bounded window of (second, flow)
        self.trailing_sorted: list[float] = []
        self.trailing_count = 0
        self.seconds_seen = 0
        self.prev_second: int | None = None
        self.last_accepted: int | None = None
        self.pending: list[dict[str, Any]] = []
        self.c: Counter = Counter()
        self.emitted: list[dict[str, Any]] = []
        self.thresholds: dict[int, float] = {}
        self.alerts: list[int] = []
        self.above_bar: dict[int, bool] = {}
        self.bar_live_from: int | None = None

    def observe(self, second: int, flow: float) -> list[dict[str, Any]]:
        if self.prev_second is not None and second != self.prev_second + 1:
            raise RuntimeError(f"seconds must be contiguous: {second} after {self.prev_second}")
        self.prev_second = second
        finite = isinstance(flow, float) and math.isfinite(flow)
        self.flow.append((second, flow if finite else float("nan")))
        if finite:
            bisect.insort(self.trailing_sorted, abs(flow))
            self.trailing_count += 1
            if len(self.trailing_sorted) > THRESHOLD_OBS_CAP:
                self.trailing_sorted.pop(0)
        self.seconds_seen += 1
        self.c["seconds_observed"] += 1
        span = 2 * LOCAL_RADIUS + BASELINE_START + 1
        while len(self.flow) > span:
            self.flow.pop(0)
        released: list[dict[str, Any]] = []
        # alert bookkeeping on the just-arrived second (known at second+1)
        if self.seconds_seen > WARMUP_SECONDS and len(self.trailing_sorted) >= MIN_THRESHOLD_OBS and finite:
            thr = frozen_quantile(self.trailing_sorted, PEAK_QUANTILE)
            self.thresholds[second] = thr
            if self.bar_live_from is None:
                self.bar_live_from = second
            above = abs(flow) >= thr and abs(flow) >= ZERO_FLOW_EPS
            self.above_bar[second] = above
            if above and not self.above_bar.get(second - 1, False):
                self.alerts.append(second)
        idx = len(self.flow) - 1 - LOCAL_RADIUS
        if idx >= LOCAL_RADIUS:
            found = self._judge(idx)
            if found is not None:
                released.extend(self._select(found))
        released.extend(self._release(second))
        return released

    def finish(self, last_second: int) -> list[dict[str, Any]]:
        return self._release(last_second) + self._release(last_second, truncating=True)

    def _judge(self, idx: int) -> dict[str, Any] | None:
        second, value = self.flow[idx]
        self.c["seconds_judged"] += 1
        if self.seconds_seen <= WARMUP_SECONDS or len(self.trailing_sorted) < MIN_THRESHOLD_OBS:
            self.c["seconds_in_warmup"] += 1
            return None
        if not math.isfinite(value):
            self.c["seconds_without_finite_flow"] += 1
            return None
        if abs(value) < ZERO_FLOW_EPS:
            self.c["rejected_zero_magnitude"] += 1
            return None
        threshold = frozen_quantile(self.trailing_sorted, PEAK_QUANTILE)
        if not math.isfinite(threshold) or abs(value) < threshold:
            self.c["rejected_below_threshold"] += 1
            return None
        window = [abs(v) for _, v in self.flow[idx - LOCAL_RADIUS: idx + LOCAL_RADIUS + 1] if math.isfinite(v)]
        if not window or abs(value) < max(window) - 1e-12:
            self.c["rejected_not_local_max"] += 1
            return None
        history = [abs(v) for s, v in self.flow if math.isfinite(v) and second - BASELINE_START <= s < second - BASELINE_LAG]
        baseline = median(history) if history else 0.0
        if not math.isfinite(baseline):
            baseline = 0.0
        return {
            "candidate_id": f"frk-dip-{self.segment}-{second}", "event_second": second,
            "available_second": second + LOCAL_RADIUS, "polarity": 1 if value > 0 else -1,
            "magnitude": abs(value), "prominence": abs(value) - baseline, "threshold": threshold,
            "baseline": baseline, "observations_behind_threshold": len(self.trailing_sorted),
            "searched_span_seconds": (second - self.bar_live_from + 1) if self.bar_live_from is not None else 0,
            "window_truncated": False, "continuity_segment": self.segment,
        }

    def _select(self, cand: dict[str, Any]) -> list[dict[str, Any]]:
        if self.last_accepted is not None and cand["event_second"] - self.last_accepted < REFRACTORY:
            self.c["rejected_in_refractory"] += 1
            return []
        self.pending.append(cand)
        return []

    def _release(self, now: int, *, truncating: bool = False) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while self.pending:
            window_open = self.pending[0]["event_second"]
            closes_at = window_open + REFRACTORY + LOCAL_RADIUS
            if not truncating and now < closes_at:
                break
            group = [c for c in self.pending if c["event_second"] < window_open + REFRACTORY]
            winner = max(group, key=lambda c: (c["prominence"], c["magnitude"]))
            survivors = [c for c in self.pending if c["event_second"] >= winner["event_second"] + REFRACTORY]
            self.c["rejected_in_refractory_at_release"] += len(self.pending) - len(group) - len(survivors)
            self.pending = survivors
            self.last_accepted = winner["event_second"]
            self.c["suppressed_by_prominence"] += len(group) - 1
            self.c["candidates_emitted"] += 1
            w = dict(winner)
            w["available_second"] = closes_at
            w["window_truncated"] = truncating
            self.emitted.append(w)
            out.append(w)
        return out

    def counters(self) -> dict[str, int]:
        keys = ["seconds_observed", "seconds_judged", "seconds_in_warmup", "seconds_without_finite_flow",
                "rejected_zero_magnitude", "rejected_below_threshold", "rejected_not_local_max",
                "rejected_in_refractory", "rejected_in_refractory_at_release", "suppressed_by_prominence",
                "candidates_emitted"]
        d = {k: int(self.c.get(k, 0)) for k in keys}
        d["candidates_pending_in_window"] = len(self.pending)
        return d

    @staticmethod
    def parameters() -> dict[str, Any]:
        return {
            "selection_rule": "CAUSAL_WINDOWED_PROMINENCE", "threshold_rule": "TRAILING_CAUSAL_QUANTILE",
            "peak_quantile": PEAK_QUANTILE, "local_radius_seconds": LOCAL_RADIUS, "refractory_seconds": REFRACTORY,
            "threshold_observation_cap": THRESHOLD_OBS_CAP, "min_threshold_observations": MIN_THRESHOLD_OBS,
            "warmup_seconds": WARMUP_SECONDS, "baseline_start_seconds": BASELINE_START,
            "baseline_lag_seconds": BASELINE_LAG, "baseline_points": BASELINE_START - BASELINE_LAG,
            "prominence_rule": "|flow| minus the median of |flow| over t-30..t-10 (21 points), causal",
            "zero_flow_guard": ZERO_FLOW_EPS, "flow_reading": "roll20 = (b-s)/(b+s) over the trailing 20 s inclusive, NaN when the window carries no classified volume",
            "implementation": "REAL_TIME_FRANKIE's own implementation of the declared rules; reconciled against the delivered candidate rows, never substituted by them",
        }
