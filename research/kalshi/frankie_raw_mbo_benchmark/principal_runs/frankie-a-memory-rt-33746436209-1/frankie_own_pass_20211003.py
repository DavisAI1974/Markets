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


SEED_ACTION_STRINGS = {
    "TFCN", "TFM", "TFMN", "TFFCCN", "TFTFCCN", "TN", "A", "AN", "C", "CN", "M", "MN", "TFC", "TFFCC",
    "TFFFCCCN", "TFFFFCCCCN", "TFFFFFCCCCCN", "TFFCM", "TFFCMN", "TFTFCMN", "TFACN", "TFCAN",
}
SWAP = {"A": "B", "B": "A", "N": "N"}
HORIZON_OFFSETS = {  # seconds; each derived from a declared substrate/detector parameter, not chosen freely
    "H_ROLL_WINDOW": ROLL_WINDOW, "H_REFRACTORY": REFRACTORY, "H_DETECTION_LAG": REFRACTORY + LOCAL_RADIUS,
    "H_TWO_DETECTION_LAGS": 2 * (REFRACTORY + LOCAL_RADIUS),
}


def walk_census(obj: Any, prefix: str, census: dict[str, dict[str, Any]], row_seen: set[str]) -> None:
    """Field census with list sampling (first element + length); distinct values capped at 8."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk_census(v, f"{prefix}.{k}" if prefix else k, census, row_seen)
    elif isinstance(obj, list):
        p = prefix + "[]"
        e = census.setdefault(p, {"obs": 0, "rows": 0, "nulls": 0, "distinct": {}, "types": Counter(), "list_len_max": 0, "list_len_sum": 0})
        e["obs"] += 1
        e["list_len_max"] = max(e["list_len_max"], len(obj))
        e["list_len_sum"] += len(obj)
        if p not in row_seen:
            row_seen.add(p)
            e["rows"] += 1
        if obj:
            walk_census(obj[0], p, census, row_seen)
    else:
        e = census.setdefault(prefix, {"obs": 0, "rows": 0, "nulls": 0, "distinct": {}, "types": Counter(), "num_min": None, "num_max": None})
        e["obs"] += 1
        if prefix not in row_seen:
            row_seen.add(prefix)
            e["rows"] += 1
        if obj is None:
            e["nulls"] += 1
            e["types"]["null"] += 1
            return
        e["types"][type(obj).__name__] += 1
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            e["num_min"] = obj if e["num_min"] is None else min(e["num_min"], obj)
            e["num_max"] = obj if e["num_max"] is None else max(e["num_max"], obj)
        key = repr(obj)[:60]
        d = e["distinct"]
        if key in d:
            d[key] += 1
        elif len(d) < 8:
            d[key] = 1
        else:
            e["distinct_overflow"] = e.get("distinct_overflow", 0) + 1


class Pass:
    def __init__(self, cutoff_indices: list[int]) -> None:
        self.cutoff_indices = set(cutoff_indices)
        self.groups = 0
        self.records = 0
        self.phase_counts: Counter = Counter()
        self.action_counts: Counter = Counter()
        self.side_counts: Counter = Counter()
        self.node_counts: Counter = Counter()
        self.max_actions = 0
        self.max_actions_group = None
        self.comp_hist: Counter = Counter()
        self.family_counts: Counter = Counter()          # (family, phase)
        self.family_first: dict[str, int] = {}
        self.family_astr: dict[str, str] = {}
        self.family_sstr: dict[str, str] = {}
        self.astr_counts: Counter = Counter()
        self.astr_side_counts: Counter = Counter()      # (astr, sstr)
        self.singleton_hashes = 0
        self.sequence_noncontig = 0
        self.snapshot_adds = 0
        self.resets = 0
        self.group_recs: list[dict[str, Any]] = []
        # 4.2
        self.regime: dict[str, dict[str, Any]] = {}
        self.one_side_empty = 0
        # 4.5
        self.e2r_by_comp: dict[int, list[int]] = defaultdict(list)
        self.e2r_by_family: dict[str, list[int]] = defaultdict(list)
        self.formation_by_family: dict[str, list[int]] = defaultdict(list)
        self.gaps_by_family: dict[str, list[int]] = defaultdict(list)
        self.decision_delays: Counter = Counter()
        self.feature_availability_equal_f_last = 0
        self.e2r_max_exemplars: list[tuple[int, int]] = []
        # 4.9 ladder
        self.prev_levels: dict[str, dict[int, tuple[int, int, list[int]]]] = {"B": {}, "A": {}}
        self.prev_best: dict[str, int | None] = {"B": None, "A": None}
        self.ladder_rows: list[dict[str, Any]] = []
        self.ladder_touch_state: Counter = Counter()
        self.touch_migrations: list[dict[str, Any]] = []
        self.ladder_by_stratum: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self.prev_mid: float | None = None
        self.prev_depth: dict[str, int] = {"B": 0, "A": 0}
        # 4.6 queue
        self.orders: dict[int, dict[str, Any]] = {}
        self.resolved: list[dict[str, Any]] = []
        self.level_removals: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])  # fill-removed orders, cancel-removed
        self.untracked_cancel = 0
        self.untracked_fill = 0
        self.untracked_modify = 0
        self.births_not_in_after_book = 0
        self.modify_reprice = 0
        self.modify_size_only = 0
        self.modify_priority_lost = 0
        # 4.7 replenishment
        self.pending_removals: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        self.episodes: list[dict[str, Any]] = []
        self.episodes_open = 0
        self.touch_watch: dict[str, dict[str, Any] | None] = {"B": None, "A": None}
        self.touch_restorations: list[dict[str, Any]] = []
        self.touch_displacements = 0
        # 4.8 absorption
        self.absorption_rows: list[dict[str, Any]] = []
        self.contact_runway: dict[str, Any] | None = None
        self.contact_runways: list[dict[str, Any]] = []
        # 4.4 mirror
        self.last_seen_key: dict[tuple, dict[str, Any]] = {}
        self.pairs: list[dict[str, Any]] = []
        self.unmatched = 0
        self.mirror_keys_both: set = set()
        # 4.14
        self.family_last_recv: dict[str, int] = {}
        self.family_gaps: dict[str, list[int]] = defaultdict(list)
        self.family_edges: Counter = Counter()
        self.family_out: Counter = Counter()
        self.prev_family: str | None = None
        self.within_edges: Counter = Counter()
        self.within_out: Counter = Counter()
        self.run_lengths: Counter = Counter()  # (node, len)
        self.same_family_run: dict[str, Any] = {"family": None, "len": 0, "start": None}
        self.same_family_runs: Counter = Counter()
        self.order_paths: Counter = Counter()
        # 4.15
        self.leaders: list[tuple[str, list[float], int]] = []
        self.cluster_members: Counter = Counter()
        self.cluster_first: dict[str, int] = {}
        # substrate / detector / candidates
        self.sub = Substrate()
        self.det = OwnDetector(18904)
        self.candidates: list[dict[str, Any]] = []
        self.cand_by_event: dict[int, dict[str, Any]] = {}
        self.delivered_candidates: dict[int, dict[str, Any]] = {}
        self.delivered_flow: dict[int, dict[str, Any]] = {}
        self.flow_reconcile = {"compared": 0, "agree": 0, "disagree": 0, "examples": []}
        self.cand_reconcile = {"delivered": 0, "own": 0, "matched": 0, "own_only": [], "delivered_only": []}
        self.delivered_lifecycle_counts: Counter = Counter()
        self.delivered_mirror_dispositions: Counter = Counter()
        self.delivered_lineage_in_stream = 0
        self.delivered_episode_rows: list[dict[str, Any]] = []
        self.per_second_side: dict[int, dict[str, int]] = defaultdict(lambda: Counter())
        self.imb_in_second: dict[int, float] = {}
        self.mid_in_second: dict[int, float] = {}
        self.depth_in_second: dict[int, tuple[int, int]] = {}
        self.touchq_in_second: dict[int, tuple[int, int]] = {}
        self.last_known = {"imb": None, "mid": None, "depth": (0, 0), "touchq": (0, 0)}
        self.trade_seconds: list[int] = []
        self.last_delivered_group_recv = 0
        self.legacy_rows_seen = 0
        self.legacy_actions: Counter = Counter()
        self.lifecycle_rows_seen = 0
        # census
        self.census: dict[str, dict[str, Any]] = {}
        self.latest_row: dict[str, Any] | None = None
        self.latest_line_sha = ""
        self.first_group_recv: int | None = None
        self.last_cutoff = 0

    # ------------------------------------------------------------------ helpers
    def _levels(self, book_full: dict[str, Any], side: str) -> dict[int, tuple[int, int, list[int]]]:
        key = "bid_levels_full" if side == "B" else "ask_levels_full"
        out = {}
        for lv in book_full.get(key) or []:
            out[int(lv["price_raw"])] = (int(lv["size"]), int(lv["order_count"]), [int(o["order_id"]) for o in lv.get("fifo_queue", [])])
        return out

    # ------------------------------------------------------------------ per group
    def on_group(self, d: Any) -> None:
        row = d.group
        gi = int(row["group_index"])
        cutoff = int(d.first_lawful_availability_ns)
        recv = int(row["ts_recv_ns"])
        phase = row["session_phase"]
        fam = row["family_id"]
        st = row["structure"]
        astr = st["action_string"]
        sstr = st["side_string"]
        comp = int(row["component_count"])
        side_or = row["side_orientation"]
        raw = row["raw_actions"]
        bf = row["book_full"]
        clocks = row["clocks"]
        if self.first_group_recv is None:
            self.first_group_recv = recv
        self.groups += 1
        self.records += comp
        self.phase_counts[phase] += 1
        self.comp_hist[comp] += 1
        if comp > self.max_actions:
            self.max_actions, self.max_actions_group = comp, gi
        self.family_counts[(fam, phase)] += 1
        self.family_first.setdefault(fam, gi)
        self.family_astr.setdefault(fam, astr)
        self.family_sstr.setdefault(fam, sstr)
        self.astr_counts[astr] += 1
        self.astr_side_counts[(astr, sstr)] += 1
        if not row.get("sequence_contiguous", True):
            self.sequence_noncontig += 1
        for a in raw:
            self.action_counts[a["action"]] += 1
            self.side_counts[a["side"]] += 1
            self.node_counts[f"{a['action']}|{a['side']}"] += 1
            if a["action"] == "A" and a.get("is_snapshot"):
                self.snapshot_adds += 1
            if a["action"] == "R":
                self.resets += 1
        # lifecycle sidecar tallies + delivered flow / candidate rows for reconciliation
        for lr in d.lifecycle_rows:
            self.lifecycle_rows_seen += 1
            sec = lr.get("emitting_section")
            self.delivered_lifecycle_counts[sec] += 1
            if sec == "flow_substrate" and lr.get("emitted_on") == "SECOND_COMPLETE":
                self.delivered_flow[int(lr["second"])] = lr
            elif sec == "candidate":
                self.delivered_candidates[int(lr["event_second"])] = lr
            elif sec == "episode":
                self.delivered_episode_rows.append({k: lr.get(k) for k in ("candidate_id", "orientation", "recognition_outcome", "detection_lag_seconds")})
            elif sec == "mirror":
                self.delivered_mirror_dispositions[str(lr.get("disposition"))] += 1
            elif sec == "lineage":
                self.delivered_lineage_in_stream += 1
        # legacy sidecar -> substrate
        for lg in d.legacy_rows:
            self.legacy_rows_seen += 1
            self.legacy_actions[lg.get("action")] += 1
            self.sub.observe_legacy(lg)
        # ---- 4.2 regime
        bids = bf.get("bid_levels_full") or []
        asks = bf.get("ask_levels_full") or []
        best_b = int(bids[0]["price_raw"]) if bids else None
        best_a = int(asks[0]["price_raw"]) if asks else None
        bd, ad = int(bf["bid_depth_full"]), int(bf["ask_depth_full"])
        boc, aoc = int(bf["bid_order_count_full"]), int(bf["ask_order_count_full"])
        blc, alc = int(bf["bid_price_level_count_full"]), int(bf["ask_price_level_count_full"])
        spread = (best_a - best_b) if (best_a is not None and best_b is not None) else None
        mid = 0.5 * (best_a + best_b) if spread is not None else None
        imb = (bd - ad) / (bd + ad) if (bd + ad) > 0 else None
        if spread is None:
            self.one_side_empty += 1
        for name, val in (("spread_raw", spread), ("depth_imbalance_full", imb), ("bid_depth_full", bd), ("ask_depth_full", ad),
                          ("bid_order_count_full", boc), ("ask_order_count_full", aoc), ("bid_level_count_full", blc), ("ask_level_count_full", alc)):
            if val is None:
                continue
            r = self.regime.setdefault(name, {"first": val, "first_group": gi, "last": val, "min": val, "min_group": gi, "max": val, "max_group": gi, "sum": 0.0, "n": 0})
            r["last"] = val
            if val < r["min"]:
                r["min"], r["min_group"] = val, gi
            if val > r["max"]:
                r["max"], r["max_group"] = val, gi
            r["sum"] += val
            r["n"] += 1
        # ---- 4.5 clocks
        e2r = [int(x) for x in row.get("event_to_receive_latency_ns") or []]
        self.e2r_by_comp[comp].extend(e2r)
        self.e2r_by_family[fam].extend(e2r)
        formation = int(row["formation_latency_ns"])
        self.formation_by_family[fam].append(formation)
        gaps = [int(x) for x in row.get("within_group_receive_gaps_ns") or []]
        self.gaps_by_family[fam].extend(gaps)
        dd = int(clocks["decision_ts_recv_ns"]) - int(clocks["f_last_ts_recv_ns"])
        self.decision_delays[dd] += 1
        if int(clocks["first_lawful_availability_ns"]) == int(clocks["f_last_ts_recv_ns"]):
            self.feature_availability_equal_f_last += 1
        if e2r:
            m = max(e2r)
            self.e2r_max_exemplars.append((m, gi))
            if len(self.e2r_max_exemplars) > 400:
                self.e2r_max_exemplars.sort(reverse=True)
                del self.e2r_max_exemplars[200:]
        # ---- 4.9 ladder (full-book set difference against the previous group's after-book)
        cur = {"B": self._levels(bf, "B"), "A": self._levels(bf, "A")}
        best = {"B": best_b, "A": best_a}
        prev_spread = (self.prev_best["A"] - self.prev_best["B"]) if (self.prev_best["A"] is not None and self.prev_best["B"] is not None) else None
        if prev_spread is None or spread is None:
            tstate = "UNDEFINED_ONE_SIDE_EMPTY"
        elif spread < prev_spread:
            tstate = "COMPRESSION"
        elif spread > prev_spread:
            tstate = "EXPANSION"
        else:
            tstate = "UNCHANGED"
        self.ladder_touch_state[tstate] += 1
        lad = {"group_index": gi, "touch_state": tstate, "family": fam, "phase": phase, "side_orientation": side_or, "sides": {}}
        for s in ("B", "A"):
            pv, cv = self.prev_levels[s], cur[s]
            births = [p for p in cv if p not in pv]
            deaths = [p for p in pv if p not in cv]
            prices = sorted(cv)
            gapsl = [abs(prices[i + 1] - prices[i]) // TICK_RAW for i in range(len(prices) - 1)]
            depth = sum(v[0] for v in cv.values())
            touch_size = cv[best[s]][0] if best[s] is not None and best[s] in cv else 0
            conc = (touch_size / depth) if depth > 0 else None
            mig = None
            if self.prev_best[s] is not None and best[s] is not None:
                mig = (best[s] - self.prev_best[s]) // TICK_RAW
            migration_depth = sum(abs(cv.get(p, (0, 0, []))[0] - pv.get(p, (0, 0, []))[0]) for p in set(cv) | set(pv))
            lad["sides"][s] = {"births": len(births), "deaths": len(deaths), "occupied": len(cv), "max_gap_ticks": max(gapsl) if gapsl else None,
                               "gap_count": len(gapsl), "concentration_at_touch": conc, "touch_migration_ticks": mig, "depth_migration": migration_depth}
            key = (fam, s, phase)
            b = self.ladder_by_stratum[key]
            b["births"].append(len(births))
            b["deaths"].append(len(deaths))
            b["occupied"].append(len(cv))
            if gapsl:
                b["max_gap_ticks"].append(max(gapsl))
                b["mean_gap_ticks"].append(sum(gapsl) / len(gapsl))
            if conc is not None:
                b["concentration"].append(conc)
            if mig is not None and mig != 0:
                b["touch_migration_ticks"].append(mig)
                self.touch_migrations.append({"group_index": gi, "side": s, "ticks": int(mig), "family": fam, "touch_state": tstate, "recv_ns": recv})
            b["depth_migration"].append(migration_depth)
        self.ladder_rows.append(lad) if len(self.ladder_rows) < 200 or tstate != "UNCHANGED" else None
        # ---- touch restoration watch (4.7)
        for s in ("B", "A"):
            w = self.touch_watch[s]
            pb, cb = self.prev_best[s], best[s]
            if w is not None and cb is not None and ((s == "B" and cb >= w["price_raw"]) or (s == "A" and cb <= w["price_raw"])):
                self.touch_restorations.append({**w, "restored_recv_ns": recv, "restored_group": gi, "duration_ns": recv - w["displaced_recv_ns"], "resolved": True})
                self.touch_watch[s] = None
                w = None
            if pb is not None and cb is not None and ((s == "B" and cb < pb) or (s == "A" and cb > pb)) and w is None:
                self.touch_displacements += 1
                self.touch_watch[s] = {"side": s, "price_raw": pb, "displaced_recv_ns": recv, "displaced_group": gi, "family": fam, "phase": phase, "ticks_away": abs(cb - pb) // TICK_RAW}
        # ---- 4.6 / 4.7 / 4.8 from the raw actions in order
        hit_side = None
        traded = 0
        fills_by_price: Counter = Counter()
        cancels_hit_side = 0
        adds_hit_side_at_hit_price = 0
        opp_retreat = 0
        for a in raw:
            act, side_a, oid = a["action"], a["side"], int(a["order_id"])
            be = a.get("book_effect") or {}
            p = int(a["price_raw"]) if a.get("price_raw") is not None else None
            size = int(a.get("size") or 0)
            ts = int(a["ts_recv_ns"])
            sec = ts // NS
            if act == "A":
                if a.get("is_snapshot") or p is None or p >= UNDEF_PRICE:
                    continue
                self.per_second_side[sec][f"add_{side_a}"] += size
                if oid in self.orders:
                    self.orders[oid]["rebirth"] = True
                self.orders[oid] = {"oid": oid, "side": side_a, "price_raw": p, "size": size, "birth_recv_ns": ts, "birth_group": gi,
                                    "birth_family": fam, "birth_phase": phase, "own_fills": 0, "own_fill_size": 0, "modify_count": 0,
                                    "priority_loss_count": 0, "reprices": 0, "level_fills_at_birth": self.level_removals[(side_a, p)][0],
                                    "level_cancels_at_birth": self.level_removals[(side_a, p)][1], "initial_orders_ahead": None,
                                    "initial_volume_ahead": None, "path": ["A"]}
                self._refill(side_a, p, size, ts, gi, "NEW_ID_ADD", oid)
                if hit_side == side_a and p in fills_by_price:
                    adds_hit_side_at_hit_price += size
            elif act == "C":
                o = self.orders.get(oid)
                if o is None:
                    self.untracked_cancel += 1
                else:
                    o["path"].append("C")
                    self._exit(o, ts, gi, fam, phase, "CANCELLED")
                    self.level_removals[(o["side"], o["price_raw"])][1] += 1
                if p is not None and p < UNDEF_PRICE:
                    self.per_second_side[sec][f"cancel_{side_a}"] += size
                    self._removal(side_a, p, size, ts, gi, fam, phase, "C", be)
                    if hit_side is not None and side_a == hit_side:
                        cancels_hit_side += size
                    elif hit_side is not None and side_a != hit_side and side_a in ("A", "B"):
                        opp_retreat += size
            elif act == "F":
                o = self.orders.get(oid)
                traded += size
                if side_a in ("A", "B"):
                    hit_side = side_a
                if p is not None and p < UNDEF_PRICE:
                    fills_by_price[p] += size
                    self.per_second_side[sec][f"fill_{side_a}"] += size
                    self._removal(side_a, p, size, ts, gi, fam, phase, "F", be)
                if o is None:
                    self.untracked_fill += 1
                else:
                    o["own_fills"] += 1
                    o["own_fill_size"] += size
                    o["path"].append("F")
                    if be.get("removed"):
                        self._exit(o, ts, gi, fam, phase, "FILLED")
                        self.level_removals[(o["side"], o["price_raw"])][0] += 1
            elif act == "M":
                o = self.orders.get(oid)
                if o is None:
                    self.untracked_modify += 1
                else:
                    o["modify_count"] += 1
                    o["path"].append("M")
                    if be.get("priority_lost"):
                        o["priority_loss_count"] += 1
                        self.modify_priority_lost += 1
                    old_p = o["price_raw"]
                    new_p = int(be.get("price_raw") or p or old_p)
                    old_size = int(be.get("old_size") or o["size"])
                    new_size = int(be.get("new_size") if be.get("new_size") is not None else size)
                    if new_p != old_p:
                        self.modify_reprice += 1
                        o["reprices"] += 1
                        self._removal(o["side"], old_p, old_size, ts, gi, fam, phase, "M_REPRICE_AWAY", be)
                        self._refill(o["side"], new_p, new_size, ts, gi, "RESHAPED_RESIDUAL_REPRICE", oid)
                        o["price_raw"] = new_p
                        o["level_fills_at_birth"] = self.level_removals[(o["side"], new_p)][0]
                        o["level_cancels_at_birth"] = self.level_removals[(o["side"], new_p)][1]
                    else:
                        self.modify_size_only += 1
                        if new_size > old_size:
                            self._refill(o["side"], old_p, new_size - old_size, ts, gi, "RESHAPED_RESIDUAL_SIZE_UP", oid)
                        elif new_size < old_size:
                            self._removal(o["side"], old_p, old_size - new_size, ts, gi, fam, phase, "M_SIZE_DOWN", be)
                    o["size"] = new_size
            elif act == "T":
                self.trade_seconds.append(sec)
            elif act == "R":
                for o in list(self.orders.values()):
                    self._exit(o, ts, gi, fam, phase, "RESET_CLEARED")
        # queue position at birth from the after-book FIFO
        for o in self.orders.values():
            if o["birth_group"] == gi and o["initial_orders_ahead"] is None:
                lv = cur[o["side"]].get(o["price_raw"])
                if lv is None or o["oid"] not in lv[2]:
                    o["initial_orders_ahead"] = -1
                    self.births_not_in_after_book += 1
                else:
                    idx = lv[2].index(o["oid"])
                    o["initial_orders_ahead"] = idx
                    # volume ahead: sizes of the orders in front, from the level's fifo queue
                    key = "bid_levels_full" if o["side"] == "B" else "ask_levels_full"
                    for lvfull in bf.get(key) or []:
                        if int(lvfull["price_raw"]) == o["price_raw"]:
                            q = lvfull.get("fifo_queue", [])
                            o["initial_volume_ahead"] = int(q[idx].get("volume_ahead", sum(int(x["size"]) for x in q[:idx])))
                            break
        # ---- 4.8 absorption, group-scoped runway
        mid_before = self.prev_mid
        if traded > 0 and hit_side in ("A", "B"):
            if mid is None or mid_before is None:
                disp = "INDETERMINATE"
            elif (hit_side == "A" and mid > mid_before) or (hit_side == "B" and mid < mid_before):
                disp = "DELIVERED_THROUGH_PRICE"
            elif cancels_hit_side > 0:
                disp = "ACCOMPANIED_BY_WITHDRAWAL"
            else:
                disp = "ABSORBED_WITHOUT_PRICE_MOVE"
            surviving = sum(cur[hit_side].get(p, (0, 0, []))[0] for p in fills_by_price)
            arow = {"group_index": gi, "family": fam, "phase": phase, "hit_side": hit_side, "traded_quantity": traded,
                    "withdrawn_quantity": cancels_hit_side, "same_side_replacement_quantity": adds_hit_side_at_hit_price,
                    "opposite_side_retreat_quantity": opp_retreat, "surviving_depth_at_hit_prices": surviving,
                    "price_response_ticks": (None if (mid is None or mid_before is None) else (mid - mid_before) / TICK_RAW),
                    "disposition": disp, "recv_ns": recv}
            self.absorption_rows.append(arow)
            # contact runway: close the previous one at this contact
            if self.contact_runway is not None:
                self._close_contact_runway(mid_before, recv, gi, "NEXT_CONTACT")
            self.contact_runway = {"open_group": gi, "family": fam, "phase": phase, "hit_side": hit_side, "traded_quantity": traded,
                                   "mid_at_open": mid_before, "hit_prices": sorted(fills_by_price), "replacement": adds_hit_side_at_hit_price,
                                   "withdrawal": cancels_hit_side, "opposite_retreat": opp_retreat, "groups_spanned": 1, "opened_recv_ns": recv}
        else:
            if traded > 0:
                self.absorption_rows.append({"group_index": gi, "family": fam, "phase": phase, "hit_side": "N", "traded_quantity": traded,
                                             "disposition": "INDETERMINATE", "recv_ns": recv, "reason": "unsided fill"})
            if self.contact_runway is not None:
                cr = self.contact_runway
                cr["groups_spanned"] += 1
                for a in raw:
                    if a["action"] == "A" and not a.get("is_snapshot") and a["side"] == cr["hit_side"] and a.get("price_raw") in cr["hit_prices"]:
                        cr["replacement"] += int(a["size"] or 0)
                    elif a["action"] == "C" and a["side"] == cr["hit_side"]:
                        cr["withdrawal"] += int(a["size"] or 0)
                    elif a["action"] == "C" and a["side"] in ("A", "B"):
                        cr["opposite_retreat"] += int(a["size"] or 0)
        # ---- 4.3 / 4.4 mirror pairing (partner = most recent earlier member with the swapped side string)
        key = (astr, sstr)
        mkey = (astr, "".join(SWAP.get(c, c) for c in sstr))
        rec = {"gi": gi, "recv": recv, "formation": formation, "imb": imb, "mid": mid, "e2r_p50": (sorted(e2r)[len(e2r) // 2] if e2r else None), "side_or": side_or}
        if mkey != key and mkey in self.last_seen_key:
            partner = self.last_seen_key[mkey]
            self.mirror_keys_both.add(tuple(sorted([key, mkey])))
            pair = {"anchor_group": partner["gi"], "member_group": gi, "action_string": astr, "orientation": f"MEMBER_{side_or}_VS_ANCHOR_{partner['side_or']}",
                    "distance_ns": recv - partner["recv"], "formation_diff_ns": formation - partner["formation"],
                    "imbalance_diff": (None if (imb is None or partner["imb"] is None) else imb - partner["imb"]),
                    "e2r_p50_diff_ns": (None if (rec["e2r_p50"] is None or partner["e2r_p50"] is None) else rec["e2r_p50"] - partner["e2r_p50"]), "phase": phase}
            self.pairs.append(pair)
        elif mkey != key:
            self.unmatched += 1
        self.last_seen_key[key] = rec
        # ---- 4.14 recurrence
        last = self.family_last_recv.get(fam)
        if last is not None:
            self.family_gaps[fam].append(recv - last)
        self.family_last_recv[fam] = recv
        if self.prev_family is not None:
            self.family_edges[(self.prev_family, fam)] += 1
            self.family_out[self.prev_family] += 1
        r = self.same_family_run
        if r["family"] == fam:
            r["len"] += 1
        else:
            if r["family"] is not None:
                self.same_family_runs[(r["family"], r["len"])] += 1
            r["family"], r["len"], r["start"] = fam, 1, gi
        self.prev_family = fam
        nodes = [f"{a['action']}|{a['side']}" for a in raw]
        for i in range(len(nodes) - 1):
            self.within_edges[(nodes[i], nodes[i + 1])] += 1
            self.within_out[nodes[i]] += 1
        i = 0
        while i < len(nodes):
            j = i
            while j + 1 < len(nodes) and nodes[j + 1] == nodes[i]:
                j += 1
            self.run_lengths[(nodes[i], j - i + 1)] += 1
            i = j + 1
        # ---- 4.15 leader clustering on hash-bound features
        feats = [math.log1p(x) for x in (comp, st["action_counts"].get("A", 0), st["action_counts"].get("C", 0), st["action_counts"].get("M", 0),
                                        st["action_counts"].get("T", 0), st["action_counts"].get("F", 0), st["side_counts"].get("B", 0),
                                        st["side_counts"].get("A", 0), st.get("distinct_price_count", 0), (st.get("price_raw_span", 0) or 0) // TICK_RAW)]
        assigned = None
        best_d = None
        for cid, centre, _ in self.leaders:
            dist = sum(abs(x - y) for x, y in zip(feats, centre))
            if dist <= CLUSTER_RADIUS and (best_d is None or dist < best_d):
                assigned, best_d = cid, dist
        if assigned is None:
            assigned = f"cl-{sha(canonical_bytes([round(x, 6) for x in feats]))[:12]}"
            self.leaders.append((assigned, feats, gi))
            self.cluster_first[assigned] = gi
            best_d = 0.0
        self.cluster_members[assigned] += 1
        # ---- book state for the per-second consumers
        sec_g = recv // NS
        if imb is not None:
            self.imb_in_second[sec_g] = imb
        if mid is not None:
            self.mid_in_second[sec_g] = mid
        self.depth_in_second[sec_g] = (bd, ad)
        self.touchq_in_second[sec_g] = (cur["B"][best_b][1] if best_b in cur["B"] else 0, cur["A"][best_a][1] if best_a in cur["A"] else 0)
        # ---- complete seconds and run the detector / runways
        for srow in self.sub.complete_through(cutoff):
            self._on_second(srow)
        # ---- census (sampled lists)
        if self.groups <= 2000 or self.groups % 7 == 0:
            walk_census(row, "", self.census, set())
        # ---- compact record
        self.group_recs.append({"gi": gi, "recv": recv, "fam": fam, "astr": astr, "phase": phase, "comp": comp, "side": side_or,
                                "mid": mid, "imb": imb, "cl": assigned, "cld": fnum(best_d), "traded": traded, "spread": spread})
        self.prev_levels = cur
        self.prev_best = best
        self.prev_mid = mid
        self.prev_depth = {"B": bd, "A": ad}
        self.latest_row = row
        self.latest_line_sha = d.group_sha256
        self.last_delivered_group_recv = recv
        self.last_cutoff = cutoff

    # ------------------------------------------------------------------ 4.6 / 4.7 internals
    def _exit(self, o: dict[str, Any], ts: int, gi: int, fam: str, phase: str, status: str) -> None:
        lvl = self.prev_levels[o["side"]].get(o["price_raw"])
        final_ahead = lvl[2].index(o["oid"]) if (lvl and o["oid"] in lvl[2]) else None
        fills_ahead = self.level_removals[(o["side"], o["price_raw"])][0] - o["level_fills_at_birth"]
        init = o["initial_orders_ahead"] if (o["initial_orders_ahead"] is not None and o["initial_orders_ahead"] >= 0) else None
        movement = (init - final_ahead) if (init is not None and final_ahead is not None) else None
        self.resolved.append({"oid": o["oid"], "side": o["side"], "price_raw": o["price_raw"], "birth_recv_ns": o["birth_recv_ns"], "birth_group": o["birth_group"],
                              "birth_family": o["birth_family"], "birth_phase": o["birth_phase"], "exit_recv_ns": ts, "exit_group": gi, "exit_family": fam,
                              "exit_phase": phase, "status": status, "lifetime_ns": ts - o["birth_recv_ns"], "own_fills": o["own_fills"], "own_fill_size": o["own_fill_size"],
                              "modify_count": o["modify_count"], "priority_loss_count": o["priority_loss_count"], "reprices": o["reprices"],
                              "initial_orders_ahead": init, "initial_volume_ahead": o["initial_volume_ahead"], "final_orders_ahead": final_ahead,
                              "queue_movement": movement, "fills_ahead": max(0, fills_ahead), "path": "".join(o["path"])[:24]})
        self.order_paths["".join(o["path"])[:12]] += 1
        self.orders.pop(o["oid"], None)

    def _removal(self, side: str, p: int, qty: int, ts: int, gi: int, fam: str, phase: str, kind: str, be: dict[str, Any]) -> None:
        if qty <= 0:
            return
        top_before = be.get("top_before_price_raw")
        touch = "AT_TOUCH" if (top_before is not None and int(top_before) == p) else "BEHIND_TOUCH"
        ep = {"side": side, "price_raw": p, "removed_quantity": qty, "opened_recv_ns": ts, "group": gi, "family": fam, "phase": phase, "kind": kind,
              "touch_state": touch, "resolved": False}
        self.pending_removals[(side, p)].append(ep)
        self.episodes.append(ep)
        self.episodes_open += 1

    def _refill(self, side: str, p: int, qty: int, ts: int, gi: int, kind: str, oid: int) -> None:
        if qty <= 0:
            return
        for off, rel in ((0, "SAME_PRICE"), (TICK_RAW, "NEIGHBOUR_1_TICK"), (-TICK_RAW, "NEIGHBOUR_1_TICK")):
            key = (side, p + off)
            lst = self.pending_removals.get(key)
            if not lst:
                continue
            keep = []
            for ep in lst:
                if ep["resolved"] or ep["opened_recv_ns"] == ts and ep.get("kind", "").startswith("M_") and kind.startswith("RESHAPED_RESIDUAL_REPRICE"):
                    keep.append(ep) if not ep["resolved"] else None
                    continue
                ep["resolved"] = True
                ep["first_refill_recv_ns"] = ts
                ep["duration_ns"] = ts - ep["opened_recv_ns"]
                ep["arrived_quantity"] = qty
                ep["refill_kind"] = kind
                ep["price_relation"] = rel
                ep["refill_group"] = gi
                self.episodes_open -= 1
            self.pending_removals[key] = keep

    def _close_contact_runway(self, mid_now: float | None, recv: int, gi: int, how: str) -> None:
        cr = self.contact_runway
        if cr is None:
            return
        m0 = cr["mid_at_open"]
        if mid_now is None or m0 is None:
            disp = "INDETERMINATE"
        elif (cr["hit_side"] == "A" and mid_now > m0) or (cr["hit_side"] == "B" and mid_now < m0):
            disp = "DELIVERED_THROUGH_PRICE"
        elif cr["withdrawal"] > 0 and cr["withdrawal"] >= cr["replacement"]:
            disp = "ACCOMPANIED_BY_WITHDRAWAL"
        elif cr["replacement"] > 0 or cr["withdrawal"] == 0:
            disp = "ABSORBED_WITHOUT_PRICE_MOVE"
        else:
            disp = "ACCOMPANIED_BY_WITHDRAWAL"
        cr.update({"closed_recv_ns": recv, "close_group": gi, "closed_by": how, "disposition": disp,
                   "price_response_ticks": (None if (mid_now is None or m0 is None) else (mid_now - m0) / TICK_RAW),
                   "duration_ns": recv - cr["opened_recv_ns"]})
        self.contact_runways.append(cr)
        self.contact_runway = None

    # ------------------------------------------------------------------ seconds
    def _on_second(self, srow: dict[str, Any]) -> None:
        s = srow["second"]
        if s in self.imb_in_second:
            self.last_known["imb"] = self.imb_in_second.pop(s)
        if s in self.mid_in_second:
            self.last_known["mid"] = self.mid_in_second.pop(s)
        if s in self.depth_in_second:
            self.last_known["depth"] = self.depth_in_second.pop(s)
        if s in self.touchq_in_second:
            self.last_known["touchq"] = self.touchq_in_second.pop(s)
        # reconcile against the delivered substrate row for this second, if it rode inside the stream
        dl = self.delivered_flow.pop(s, None)
        if dl is not None:
            self.flow_reconcile["compared"] += 1
            ok = (abs(float(dl.get("buy_volume") or 0) - srow["buy_volume"]) < 1e-9 and abs(float(dl.get("sell_volume") or 0) - srow["sell_volume"]) < 1e-9
                  and dl.get("classification") == srow["classification"] and dl.get("window_direction") == srow["window_direction"]
                  and ((dl.get("roll20_value") is None and math.isnan(srow["roll20"])) or (dl.get("roll20_value") is not None and not math.isnan(srow["roll20"]) and abs(float(dl["roll20_value"]) - srow["roll20"]) < 1e-9)))
            if ok:
                self.flow_reconcile["agree"] += 1
            else:
                self.flow_reconcile["disagree"] += 1
                if len(self.flow_reconcile["examples"]) < 20:
                    self.flow_reconcile["examples"].append({"second": s, "own": {k: srow[k] for k in ("buy_volume", "sell_volume", "classification", "window_direction", "roll20")},
                                                            "delivered": {k: dl.get(k) for k in ("buy_volume", "sell_volume", "classification", "window_direction", "roll20_value")}})
        for c in self.det.observe(s, srow["roll20"]):
            self._promote(c, s)
        # runway stages for open candidates
        pss = self.per_second_side.pop(s, None) or Counter()
        for cand in self.candidates:
            if cand["status"] not in ("OPEN",):
                continue
            self._advance_runway(cand, s, srow, pss)

    def _promote(self, c: dict[str, Any], now_second: int) -> None:
        e = c["event_second"]
        # precursor: first second of the contiguous above-bar run that ends at the event second
        a = e
        while self.det.above_bar.get(a - 1, False):
            a -= 1
        alert_known_second = a + 1
        if alert_known_second < e:
            label, lead_s = "PRIOR", e - alert_known_second
        elif alert_known_second == e:
            label, lead_s = "T0", 0
        else:
            label, lead_s = "H+N", -(c["available_second"] - e)
        pred = self.candidates[-1] if self.candidates else None
        orientation = "NO_PREDECESSOR" if pred is None else ("SAME" if pred["polarity"] == c["polarity"] else "FLIP")
        parent = None
        for cand in reversed(self.candidates):
            if cand["status"] == "OPEN":
                parent = cand
                break
        cand = {**c, "status": "OPEN", "orientation": orientation, "predecessor_id": (pred["candidate_id"] if pred else None),
                "alert_second": a, "alert_known_second": alert_known_second, "precursor_label": label, "precursor_lead_seconds": lead_s,
                "promotion_label": "H+N", "promotion_lag_seconds": c["available_second"] - e,
                "phases": [{"phase": "BIRTH", "entered_second": e, "exited_second": c["available_second"], "seconds": c["available_second"] - e,
                            "depletion": 0, "refill": 0, "flow_sum": 0.0, "n": 0}],
                "current_phase": None, "stages": [], "sign_reversals": 0, "last_sign": c["polarity"], "reversal_seconds": 0, "quiet_run": 0,
                "depth": 0, "parent_id": None, "transition": None, "children": [], "termination": None,
                "base": {"mid": self.last_known["mid"], "flow": None, "depth": self.last_known["depth"], "touchq": self.last_known["touchq"], "imb": self.last_known["imb"]},
                "horizons": {}, "change_points": [], "promoted_at_second": now_second, "family_at_promotion": (self.group_recs[-1]["fam"] if self.group_recs else None),
                "groups_in_event_second": [g["gi"] for g in self.group_recs[-400:] if g["recv"] // NS == e][:20]}
        if parent is not None:
            cand["depth"] = parent["depth"] + 1
            cand["parent_id"] = parent["candidate_id"]
            cand["transition"] = "SAME" if parent["polarity"] == c["polarity"] else "FLIP"
            parent["children"].append(cand["candidate_id"])
            parent["status"] = "EXTENDED_BY_SUCCESSOR" if cand["transition"] == "SAME" else "COMPLETED_BY_OPPOSITE_CANDIDATE"
            parent["termination"] = {"by": cand["candidate_id"], "at_second": e, "transition": cand["transition"]}
            self._close_phase(parent, e)
        self.candidates.append(cand)
        self.cand_by_event[e] = cand
        d = self.delivered_candidates.get(e)
        self.cand_reconcile["own"] += 1
        if d is not None:
            self.cand_reconcile["matched"] += 1
            cand["delivered_match"] = {"candidate_id": d["candidate_id"], "polarity_agrees": int(d["polarity"]) == c["polarity"],
                                       "available_second_agrees": int(d["available_second"]) == c["available_second"],
                                       "magnitude_delta": fnum(float(d["magnitude"]) - c["magnitude"])}
        else:
            cand["delivered_match"] = None
            if len(self.cand_reconcile["own_only"]) < 50:
                self.cand_reconcile["own_only"].append(e)

    def _close_phase(self, cand: dict[str, Any], second: int) -> None:
        ph = cand["current_phase"]
        if ph is not None and ph.get("exited_second") is None:
            ph["exited_second"] = second
            ph["seconds"] = second - ph["entered_second"]

    def _advance_runway(self, cand: dict[str, Any], s: int, srow: dict[str, Any], pss: Counter) -> None:
        if s < cand["available_second"]:
            return
        flow = srow["window_signed_flow"]
        sign = 1 if flow > 0 else (-1 if flow < 0 else 0)
        pol = cand["polarity"]
        if sign == pol:
            phase = "PERSISTENCE"
        elif sign == -pol:
            phase = "REVERSAL"
        else:
            phase = "QUIET_NO_DIRECTION"
        if sign != 0 and sign != cand["last_sign"]:
            cand["sign_reversals"] += 1
            cand["last_sign"] = sign
        cp = cand["current_phase"]
        if cp is None or cp["phase"] != phase:
            if cp is not None:
                self._close_phase(cand, s)
            cp = {"phase": phase, "entered_second": s, "exited_second": None, "seconds": 0, "depletion": 0, "refill": 0, "flow_sum": 0.0, "n": 0, "imb_sum": 0.0, "imb_n": 0}
            cand["current_phase"] = cp
            cand["phases"].append(cp)
        cp["n"] += 1
        cp["flow_sum"] += flow
        consumed = "A" if pol > 0 else "B"
        cp["depletion"] += pss.get(f"fill_{consumed}", 0) + pss.get(f"cancel_{consumed}", 0)
        cp["refill"] += pss.get(f"add_{consumed}", 0)
        imb = self.last_known["imb"]
        if imb is not None:
            cp["imb_sum"] += imb
            cp["imb_n"] += 1
        k = s - cand["available_second"]
        if k < 60 or k in (90, 120, 180, 300, 600):
            cand["stages"].append({"k": k, "flow": flow, "imb": imb, "dir": ("LONG" if sign > 0 else "SHORT" if sign < 0 else "NO_DIRECTION"), "mag": abs(flow)})
        # completion by decay: after a reversal, the window carries no classified volume for LOCAL_RADIUS seconds
        if srow["window_volume"] == 0:
            cand["quiet_run"] += 1
        else:
            cand["quiet_run"] = 0
        had_reversal = any(p["phase"] == "REVERSAL" for p in cand["phases"])
        if had_reversal and cand["quiet_run"] >= LOCAL_RADIUS:
            self._close_phase(cand, s + 1)
            cand["status"] = "COMPLETED_DECAY"
            cand["termination"] = {"by": "DECAY_TO_NO_VOLUME", "at_second": s + 1}
        # 4.16 fixed horizons and event-driven change points
        if cand["base"]["flow"] is None and s == cand["available_second"]:
            cand["base"]["flow"] = flow
        for hname, off in HORIZON_OFFSETS.items():
            if hname not in cand["horizons"] and s >= cand["available_second"] + off:
                cand["horizons"][hname] = self._reading(cand, s, flow)
        if len(cand["change_points"]) < 6 and cand["base"]["mid"] is not None and self.last_known["mid"] is not None and self.last_known["mid"] != cand["base"]["mid"] \
                and (not cand["change_points"] or cand["change_points"][-1]["mid"] != self.last_known["mid"]):
            cand["change_points"].append({"kind": "MID_CHANGED", **self._reading(cand, s, flow)})

    def _reading(self, cand: dict[str, Any], s: int, flow: float) -> dict[str, Any]:
        b = cand["base"]
        mid = self.last_known["mid"]
        dep = self.last_known["depth"]
        tq = self.last_known["touchq"]
        return {"at_second": s, "mid": mid, "price_response_ticks": (None if (mid is None or b["mid"] is None) else (mid - b["mid"]) / TICK_RAW),
                "flow_response": (None if b["flow"] is None else flow - b["flow"]), "full_book_response": (dep[0] + dep[1]) - (b["depth"][0] + b["depth"][1]),
                "bid_depth_response": dep[0] - b["depth"][0], "ask_depth_response": dep[1] - b["depth"][1],
                "queue_response_touch_orders": (tq[0] + tq[1]) - (b["touchq"][0] + b["touchq"][1]),
                "imbalance_response": (None if (self.last_known["imb"] is None or b["imb"] is None) else self.last_known["imb"] - b["imb"])}

    def finish_stream(self, last_cutoff: int) -> None:
        for srow in self.sub.complete_through(last_cutoff):
            self._on_second(srow)
        last_second = self.sub.next_second - 1 if self.sub.next_second is not None else 0
        for c in self.det.finish(last_second):
            self._promote(c, last_second)
        for cand in self.candidates:
            if cand["status"] == "OPEN":
                self._close_phase(cand, last_second + 1)
                cand["status"] = "CENSORED_STREAM_END"
        if self.contact_runway is not None:
            self._close_contact_runway(self.prev_mid, self.last_delivered_group_recv, self.group_recs[-1]["gi"], "STREAM_END")
        r = self.same_family_run
        if r["family"] is not None:
            self.same_family_runs[(r["family"], r["len"])] += 1
        self.cand_reconcile["delivered"] = len(self.delivered_candidates) + self.cand_reconcile["matched"]
        self.cand_reconcile["delivered_only"] = sorted(self.delivered_candidates)[:50]


# ====================================================================== emitters
def _seg() -> int:
    return 18904


def null_result(section: str, description: str, denominator: int, cutoff: int, **extra: Any) -> dict[str, Any]:
    return {"section": section, "result": "NULL_RESULT", "member_group_indices": [],
            "population": {"denominator": int(denominator), "description": description}, "cutoff": rd(cutoff), **extra}


def members_of(recs: list[dict[str, Any]], cap: int = 40) -> list[int]:
    return [int(r["gi"]) for r in recs[:cap]]


def by_stratum_recs(P: Pass, keyf) -> dict[tuple, list[dict[str, Any]]]:
    out: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in P.group_recs:
        out[keyf(r)].append(r)
    return out


def phase_of(P: Pass) -> str:
    return "+".join(sorted(P.phase_counts)) if P.phase_counts else "NONE"


def emit_4_0(P: Pass, cutoff: int) -> dict[str, Any]:
    S = P.sub
    n_done = len(S.completed)
    if n_done == 0:
        return null_result("4.0", "no second has completed on the binning clock yet (no legacy row observed)", 0, cutoff)
    secs = sorted(S.completed)
    last = S.completed[secs[-1]]
    recent = [S.completed[s] for s in secs[-30:]]
    rows_recent = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()} for r in recent]
    body = {
        "section": "4.0", "result": "COMPUTED", "member_group_indices": members_of(P.group_recs[-40:]),
        "binning_clock": "ts_recv (legacy row float seconds, floored); a second is final once the F_LAST cutoff reaches (s+1)*1e9",
        "classification_rule": "mid = 0.5*(bid_px_00+ask_px_00) on legacy rows with action T, price>0, size>0, bid_px_00>0, ask_px_00>=bid_px_00; price>mid buy, price<mid sell, at mid neither; the tape side field is never consulted",
        "window_rule": f"roll20 = (b-s)/(b+s) over the trailing {ROLL_WINDOW} s inclusive of t, NaN when the window carries no classified volume; window_signed_flow = b-s over the same window; LONG/SHORT/NO_DIRECTION by its sign (zero flow is no direction)",
        "first_second": S.first_second, "completed_seconds": n_done, "incomplete_second": S.next_second,
        "incomplete_partial_tallies": {"buy_volume": S.buy.get(S.next_second, 0.0), "sell_volume": S.sell.get(S.next_second, 0.0), "rows": S.rows.get(S.next_second, 0)},
        "legacy_rows_observed": P.legacy_rows_seen, "legacy_rows_by_action": dict(P.legacy_actions),
        "own_second_class_census": dict(S.class_census), "window_direction_census": dict(S.window_census),
        "last_completed_second": {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in last.items()},
        "recent_rows_exact": rows_recent,
        "reconciliation_with_delivered_substrate_rows": {**{k: v for k, v in P.flow_reconcile.items() if k != "examples"}, "examples": P.flow_reconcile["examples"][:10],
                                                          "rule": "delivered flow_substrate rows attached by their own emitted_at_recv_ns are compared second by second on buy/sell volume, own-second class, window direction and roll20; a disagreement is reported as a section defect, never hidden"},
        "status": "REJECTED_BY_RECONCILIATION" if P.flow_reconcile["disagree"] else "RECONCILED",
        "averages": [],
    }
    ph = phase_of(P)
    for cls, n in sorted(S.class_census.items()):
        body["averages"].append(average(n / n_done, numerator=n, formula="completed seconds in class / completed seconds", population="completed seconds on the binning clock",
                                        denominator=n_done, family="PER_SECOND_SUBSTRATE", subfamily=f"own_second_class={cls}", side="N/A", phase=ph, status="RESOLVED", cutoff=cutoff,
                                        missingness="a second with no rows is a member; the open second is outside the denominator", inclusion="every completed second since the first legacy row"))
    for wd, n in sorted(S.window_census.items()):
        body["averages"].append(average(n / n_done, numerator=n, formula="completed seconds with window direction / completed seconds", population="completed seconds", denominator=n_done,
                                        family="PER_SECOND_SUBSTRATE", subfamily=f"window_direction={wd}", side="N/A", phase=ph, status="RESOLVED", cutoff=cutoff,
                                        missingness="zero window flow is NO_DIRECTION, never a default side", inclusion="every completed second"))
    return body


def emit_4_0b(P: Pass, cutoff: int) -> dict[str, Any]:
    D = P.det
    c = D.counters()
    if c["seconds_observed"] == 0:
        return null_result("4.0b", "the detector has observed no completed second", 0, cutoff)
    judged = c["seconds_judged"]
    named = c["seconds_in_warmup"] + c["seconds_without_finite_flow"] + c["rejected_zero_magnitude"] + c["rejected_below_threshold"] + c["rejected_not_local_max"] \
        + c["rejected_in_refractory"] + c["suppressed_by_prominence"] + c["rejected_in_refractory_at_release"] + c["candidates_emitted"] + c["candidates_pending_in_window"]
    searched = judged - c["seconds_in_warmup"]
    considered = searched - c["seconds_without_finite_flow"]

    def ratio(num, den, formula):
        return {"basis": "RATIO_OF_EXACT_COUNTS", "numerator": num, "denominator": den, "formula": formula, "value": (fnum(num / den) if den else None)}
    return {
        "section": "4.0b", "result": "COMPUTED", "member_group_indices": members_of(P.group_recs[-20:]),
        "unit": "DIPOLE_FLOW_EVENT (a locally prominent spike in the per-second roll20 signed aggressor imbalance)",
        "detector_parameters": OwnDetector.parameters(), "detector_counters": c,
        "partition_identity": {"seconds_judged": judged, "named_outcomes_plus_pending": named, "holds": judged == named,
                               "formula": "warmup + no_finite_flow + zero_magnitude + below_threshold + not_local_max + in_refractory + suppressed_by_prominence + in_refractory_at_release + emitted + pending == judged"},
        "searched_seconds": searched, "considered_second_events": considered,
        "searched_share_of_observed": ratio(searched, c["seconds_observed"], "searched / seconds_observed"),
        "promotion_rate": ratio(c["candidates_emitted"], considered, "candidates_emitted / considered"),
        "rejection_share_by_reason": {k: ratio(c[k], considered, f"{k} / considered") for k in ("rejected_zero_magnitude", "rejected_below_threshold", "rejected_not_local_max", "rejected_in_refractory", "rejected_in_refractory_at_release", "suppressed_by_prominence")},
        "threshold_crossing_alerts_emitted": len(D.alerts),
        "trailing_bar_now": (frozen_quantile(D.trailing_sorted, PEAK_QUANTILE) if len(D.trailing_sorted) >= MIN_THRESHOLD_OBS else None),
        "reconciliation_with_delivered_candidate_rows": {"own_candidates": P.cand_reconcile["own"], "matched_on_event_second": P.cand_reconcile["matched"],
                                                          "delivered_rows_seen_in_stream": P.delivered_lifecycle_counts.get("candidate", 0), "own_only_event_seconds": P.cand_reconcile["own_only"][:20],
                                                          "delivered_not_yet_matched": sorted(P.delivered_candidates)[:20]},
        "note": "these are counts and ratios of exact counts, never means; promoted is the population 4.10-4.16 report on",
    }


def emit_4_1(P: Pass, cutoff: int) -> dict[str, Any]:
    dup = P.groups - len({r["gi"] for r in P.group_recs})
    return {
        "section": "4.1", "result": "COMPUTED", "member_group_indices": members_of(P.group_recs[-40:]),
        "groups_delivered": P.groups, "native_records": P.records, "duplicate_group_indices": dup, "phase_counts": dict(P.phase_counts),
        "action_counts": dict(P.action_counts), "side_counts": dict(P.side_counts), "node_counts": dict(P.node_counts),
        "records_reconcile_with_component_counts": P.records == sum(k * v for k, v in P.comp_hist.items()),
        "component_histogram": {str(k): v for k, v in sorted(P.comp_hist.items())}, "max_actions_per_group": P.max_actions, "max_actions_group_index": P.max_actions_group,
        "snapshot_adds_not_born": P.snapshot_adds, "book_resets": P.resets, "sequence_noncontiguous_groups": P.sequence_noncontig,
        "families_seen": len(P.family_first), "singleton_families": sum(1 for f in P.family_first if sum(v for (ff, _), v in P.family_counts.items() if ff == f) == 1),
        "f_last_closed_every_group": True, "receive_clock_monotone": True, "instrument_ids": [111313], "continuity_segments": [_seg()],
        "latest_group_sha256": P.latest_line_sha, "first_group_recv": rd(P.first_group_recv or 0), "latest_cutoff": rd(cutoff),
        "note": "identity and integrity facts are counts and hashes; the stream itself refused nothing (disorder, an unclosed group or a clock mismatch raises)",
    }


def emit_4_2(P: Pass, cutoff: int) -> dict[str, Any]:
    if not P.regime:
        return null_result("4.2", "no full-book snapshot with both sides yet", P.groups, cutoff)
    body = {"section": "4.2", "result": "COMPUTED", "member_group_indices": members_of(P.group_recs[-20:]) + [P.regime["spread_raw"]["min_group"], P.regime["spread_raw"]["max_group"]],
            "denominator": P.groups, "groups_with_one_side_empty": P.one_side_empty, "daily": {}, "action_totals": dict(P.action_counts), "side_totals": dict(P.side_counts),
            "group_count": P.groups, "max_actions_per_group": P.max_actions, "averages": []}
    ph = phase_of(P)
    for name, r in P.regime.items():
        body["daily"][name] = {"first": r["first"], "first_group": r["first_group"], "last": r["last"], "min": r["min"], "min_group": r["min_group"], "max": r["max"], "max_group": r["max_group"], "mean": fnum(r["sum"] / r["n"]), "n": r["n"]}
        body["averages"].append(average(r["sum"] / r["n"], numerator=r["sum"], formula=f"sum of {name} over F_LAST-closed groups / groups with both sides", population="F_LAST-closed groups on this source day",
                                        denominator=r["n"], family="DAILY_REGIME", subfamily=name, side="BOTH_SIDES", phase=ph, status="OPEN", cutoff=cutoff,
                                        missingness="groups with one side empty carry no spread/imbalance and are counted apart", inclusion="every delivered group"))
    return body


def emit_4_3(P: Pass, cutoff: int) -> dict[str, Any]:
    fam_tot: Counter = Counter()
    for (f, ph), n in P.family_counts.items():
        fam_tot[f] += n
    top = fam_tot.most_common(25)
    seeds = Counter()
    for a, n in P.astr_counts.items():
        if a in SEED_ACTION_STRINGS:
            seeds[a] += n
    ow = sum(n for a, n in P.astr_counts.items() if a not in SEED_ACTION_STRINGS)
    body = {"section": "4.3", "result": "COMPUTED", "member_group_indices": [P.family_first[f] for f, _ in top[:30]],
            "descriptor": "family_id is the adapter's content-derived id of the versioned descriptor (action/side sequence, fill disposition, order-id graph, price multiplicity, terminal); the literal action string and side string are read beside it",
            "families": len(fam_tot), "singleton_families": sum(1 for n in fam_tot.values() if n == 1), "top_families": [{"family_id": f, "groups": n, "action_string": P.family_astr[f], "side_string": P.family_sstr[f][:32], "first_group": P.family_first[f]} for f, n in top],
            "seed_crosswalk_by_action_string": dict(seeds), "groups_matching_no_seed_action_string": ow, "open_world_action_strings": len([a for a in P.astr_counts if a not in SEED_ACTION_STRINGS]),
            "lifecycle_shape_AN_TFMN_TFCN": {"AN": P.astr_counts.get("AN", 0), "TFMN": P.astr_counts.get("TFMN", 0), "TFCN": P.astr_counts.get("TFCN", 0)},
            "deepest_action_strings": sorted(((len(a), a, n) for a, n in P.astr_counts.items()), reverse=True)[:8], "averages": []}
    for f, n in top[:12]:
        for ph in sorted(P.phase_counts):
            k = P.family_counts.get((f, ph), 0)
            if k:
                fl = P.formation_by_family.get(f, [])
                body["averages"].append(average(k / P.phase_counts[ph], numerator=k, formula="groups in family and phase / groups in phase", population="F_LAST-closed groups in the phase",
                                                denominator=P.phase_counts[ph], family=f, subfamily=f"action_string={P.family_astr[f]}", side=P.family_sstr[f][:8], phase=ph, status="OPEN", cutoff=cutoff,
                                                missingness="none; every group has a family", inclusion="all delivered groups"))
                if fl:
                    q = qs(fl)
                    body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(formation_latency_ns) / groups in family", population="groups in family (all phases)", denominator=len(fl),
                                                    family=f, subfamily=f"formation_latency_ns quantiles p50={q['p50']} p90={q['p90']} max={q['max']}", side=P.family_sstr[f][:8], phase=ph, status="RESOLVED", cutoff=cutoff,
                                                    missingness="single-component groups carry formation latency 0 by construction", inclusion="all groups in the family"))
    return body


def emit_4_4(P: Pass, cutoff: int) -> dict[str, Any]:
    if not P.pairs:
        return null_result("4.4", f"no member has yet met an earlier member with the swapped side string; unmatched so far {P.unmatched}", P.groups, cutoff,
                           delivered_mirror_rows_attached_so_far=dict(P.delivered_mirror_dispositions),
                           matching_rule="partner = the most recent earlier delivered member whose (action_string, side_string) is the side-swapped key of this member; distance = receive-clock gap; pre-event covariates only")
    by_or: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in P.pairs:
        by_or[(p["action_string"], p["orientation"], p["phase"])].append(p)
    top = sorted(by_or.items(), key=lambda kv: -len(kv[1]))[:12]
    body = {"section": "4.4", "result": "COMPUTED", "member_group_indices": [p["member_group"] for p in P.pairs[-30:]] + [p["anchor_group"] for p in P.pairs[-10:]],
            "matching_rule": "partner = the most recent earlier delivered member whose (action_string, side_string) equals this member's side-swapped key; the pair is formed at this member's F_LAST from lawful pre-event covariates only; matching distance = receive-clock gap; every member without such a partner is unmatched and counted",
            "pairs": len(P.pairs), "unmatched": P.unmatched, "keys_with_both_orientations": len(P.mirror_keys_both),
            "delivered_mirror_rows_attached_so_far": dict(P.delivered_mirror_dispositions),
            "recent_pairs_exact": P.pairs[-8:], "averages": []}
    for (astr, orient, ph), lst in top:
        fd = [p["formation_diff_ns"] for p in lst]
        q = qs(fd)
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(member formation_latency - anchor formation_latency) / pairs", population="matched mirror pairs", denominator=len(lst),
                                        family=f"action_string={astr}", subfamily=f"formation_diff quantiles p50={q['p50']} p90={q['p90']}; distance_ns p50={qs([p['distance_ns'] for p in lst])['p50']}", side=orient, phase=ph, status="RESOLVED", cutoff=cutoff,
                                        missingness="unmatched members are excluded from paired differences and counted separately", inclusion="pairs whose both members are delivered"))
        idl = [p["imbalance_diff"] for p in lst if p["imbalance_diff"] is not None]
        if idl:
            q2 = qs(idl)
            body["averages"].append(average(q2["mean"], numerator=q2["sum"], formula="sum(member depth_imbalance_after - anchor depth_imbalance_after) / pairs with both imbalances", population="matched pairs", denominator=len(idl),
                                            family=f"action_string={astr}", subfamily=f"imbalance_diff quantiles p50={q2['p50']} min={q2['min']} max={q2['max']}", side=orient, phase=ph, status="RESOLVED", cutoff=cutoff,
                                            missingness="pairs with an empty side carry no imbalance", inclusion="pairs with both imbalances"))
    return body


def emit_4_5(P: Pass, cutoff: int) -> dict[str, Any]:
    body = {"section": "4.5", "result": "COMPUTED", "member_group_indices": [gi for _, gi in sorted(P.e2r_max_exemplars, reverse=True)[:20]] + members_of(P.group_recs[-10:]),
            "interpretation_domain": "SERIALIZATION_FEED (an economic reading is a separate claim)", "e2r_by_component_count": {}, "formation_by_family_top": {},
            "decision_delay_census": {str(k): v for k, v in P.decision_delays.items()}, "feature_availability_equals_f_last": P.feature_availability_equal_f_last, "groups": P.groups, "averages": []}
    ph = phase_of(P)
    for comp in sorted(P.e2r_by_comp)[:14]:
        q = qs(P.e2r_by_comp[comp])
        body["e2r_by_component_count"][str(comp)] = q
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(event_to_receive_latency_ns per component) / components", population="components of groups with this component count", denominator=q["n"],
                                        family=f"component_count={comp}", subfamily=f"quantiles p50={q['p50']} p90={q['p90']} p99={q['p99']} max={q['max']}", side="ALL_SIDES_NOT_POOLED_BY_SIDE", phase=ph, status="RESOLVED", cutoff=cutoff,
                                        missingness="none; every component carries both clocks", inclusion="all components"))
    fam_tot = Counter()
    for (f, _), n in P.family_counts.items():
        fam_tot[f] += n
    for f, n in fam_tot.most_common(10):
        q = qs(P.formation_by_family[f])
        g = qs(P.gaps_by_family[f])
        body["formation_by_family_top"][f] = {"formation_latency_ns": q, "within_group_receive_gap_ns": g, "action_string": P.family_astr[f]}
        if q["n"]:
            body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(formation_latency_ns) / groups", population="groups in family", denominator=q["n"], family=f, subfamily=f"action_string={P.family_astr[f]}; p50={q['p50']} max={q['max']}",
                                            side=P.family_sstr[f][:8], phase=ph, status="RESOLVED", cutoff=cutoff, missingness="none", inclusion="all groups in the family"))
    return body


def emit_4_6(P: Pass, cutoff: int) -> dict[str, Any]:
    resolved = P.resolved
    open_orders = list(P.orders.values())
    if not resolved and not open_orders:
        return null_result("4.6", "no participant order born in the window yet", P.groups, cutoff)
    strata: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for o in resolved:
        k = (o["birth_family"], o["side"], o["birth_phase"])
        strata[k]["t"].append(o["lifetime_ns"])
        strata[k]["e"].append(True)
        strata[k]["status"].append(o["status"])
        if o["initial_volume_ahead"] is not None:
            strata[k]["vol_ahead"].append(o["initial_volume_ahead"])
        if o["initial_orders_ahead"] is not None:
            strata[k]["orders_ahead"].append(o["initial_orders_ahead"])
        if o["queue_movement"] is not None:
            strata[k]["movement"].append(o["queue_movement"])
        strata[k]["fills_ahead"].append(o["fills_ahead"])
        strata[k]["lifetime_resolved"].append(o["lifetime_ns"])
    for o in open_orders:
        k = (o["birth_family"], o["side"], o["birth_phase"])
        strata[k]["t"].append(cutoff - o["birth_recv_ns"])
        strata[k]["e"].append(False)
        if o["initial_volume_ahead"] is not None:
            strata[k]["vol_ahead"].append(o["initial_volume_ahead"])
    top = sorted(strata.items(), key=lambda kv: -len(kv[1]["t"]))[:10]
    body = {"section": "4.6", "result": "COMPUTED", "member_group_indices": [o["exit_group"] for o in resolved[-30:]] + [o["birth_group"] for o in resolved[-10:]],
            "lifecycle_rule": "birth = a non-snapshot A with a live reference; exit = C, or an F that removes the order, or the reset; M counts modifies, priority loss (book_effect.priority_lost) and reprices; an order still resting at the cutoff is censored at the cutoff (not at stream end)",
            "queue_position_rule": "orders ahead = index in the after-book fifo_queue at birth; volume ahead = the fifo entry's volume_ahead; fills ahead = fill-removed orders at the level since birth (FIFO consumes the front); queue movement = initial - final orders ahead read from the previous group's after-book",
            "population": {"resolved": len(resolved), "open_at_cutoff": len(open_orders), "status_counts": dict(Counter(o["status"] for o in resolved)),
                           "untracked_cancels": P.untracked_cancel, "untracked_fills": P.untracked_fill, "untracked_modifies": P.untracked_modify, "births_not_found_in_after_book": P.births_not_in_after_book,
                           "modify_reprice": P.modify_reprice, "modify_size_only": P.modify_size_only, "modify_priority_lost": P.modify_priority_lost},
            "strata": [], "same_order_paths_top": [{"path": p, "n": n} for p, n in P.order_paths.most_common(12)], "averages": []}
    for (fam, side, ph), d in top:
        k = km(d["t"], d["e"])
        row = {"birth_family": fam, "action_string": P.family_astr.get(fam), "side": side, "birth_phase": ph, "survival": k, "initial_volume_ahead": qs(d["vol_ahead"]), "initial_orders_ahead": qs(d["orders_ahead"]),
               "queue_movement": qs(d["movement"]), "fills_ahead": qs(d["fills_ahead"]), "resolved_lifetime_ns": qs(d["lifetime_resolved"]), "status_counts": dict(Counter(d["status"]))}
        body["strata"].append(row)
        if d["vol_ahead"]:
            q = qs(d["vol_ahead"])
            body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(initial volume ahead) / orders with an observed birth position", population="orders born in this stratum (resolved and open)", denominator=q["n"],
                                            family=fam, subfamily=f"volume_ahead p50={q['p50']} p90={q['p90']} max={q['max']}", side=side, phase=ph, status="OPEN", cutoff=cutoff,
                                            missingness="orders already gone within their birth group have no after-book position and are counted apart", inclusion="born after the reset, non-snapshot"))
        if d["lifetime_resolved"]:
            q = qs(d["lifetime_resolved"])
            body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(resolved lifetime_ns) / resolved orders", population="RESOLVED orders only (censored kept in the survival estimator, never here)", denominator=q["n"],
                                            family=fam, subfamily=f"KM S0.5 at {k.get('time_ns_at_S0.5')} ns; S0.1 at {k.get('time_ns_at_S0.1')} ns; final S={k.get('final_survival')}", side=side, phase=ph, status="RESOLVED", cutoff=cutoff,
                                            missingness="censored orders excluded from this mean by definition", inclusion="resolved orders"))
    return body


def emit_4_7(P: Pass, cutoff: int) -> dict[str, Any]:
    eps = P.episodes
    if not eps:
        return null_result("4.7", "no removal (cancel, fill, modify-away or size-down) has occurred yet", P.groups, cutoff)
    strata: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for e in eps:
        k = (e["family"], e["side"], e["touch_state"], e["phase"])
        if e["resolved"]:
            strata[k]["t"].append(e["duration_ns"])
            strata[k]["ev"].append(True)
            strata[k]["removed"].append(e["removed_quantity"])
            strata[k]["arrived"].append(e["arrived_quantity"])
            strata[k]["kind"].append(e["refill_kind"])
            strata[k]["rel"].append(e["price_relation"])
        else:
            strata[k]["t"].append(cutoff - e["opened_recv_ns"])
            strata[k]["ev"].append(False)
        strata[k]["removal_kind"].append(e["kind"])
    top = sorted(strata.items(), key=lambda kv: -len(kv[1]["t"]))[:10]
    tr = P.touch_restorations
    body = {"section": "4.7", "result": "COMPUTED", "member_group_indices": [e["group"] for e in eps[-30:]] + [t["restored_group"] for t in tr[-10:]],
            "episode_rule": "an episode opens at every removal of resting quantity (C, removing F, M reprice-away, M size-down) at (side, price); it resolves at the FIRST later arrival at the same price or one tick either side (new-ID add = NEW_ID_ADD, or a same-ID modify = RESHAPED_RESIDUAL_*), one attribution per episode; the modify that moved an order never restores its own episode; an episode still pending at the cutoff is censored at the cutoff",
            "touch_rule": "the touch is displaced when a group leaves a side's best price worse than the previous group's; restored when a later group's best price returns to or improves on it",
            "population": {"episodes": len(eps), "resolved": sum(1 for e in eps if e["resolved"]), "pending_censored_at_cutoff": P.episodes_open, "by_removal_kind": dict(Counter(e["kind"] for e in eps)),
                           "by_refill_kind": dict(Counter(e.get("refill_kind") for e in eps if e["resolved"])), "by_price_relation": dict(Counter(e.get("price_relation") for e in eps if e["resolved"])),
                           "touch_displacements": P.touch_displacements, "touch_restorations": len(tr), "touch_still_displaced": {s: (w is not None) for s, w in P.touch_watch.items()}},
            "touch_restoration_time_ns": qs([t["duration_ns"] for t in tr]), "strata": [], "averages": []}
    for (fam, side, touch, ph), d in top:
        k = km(d["t"], d["ev"])
        rem, arr = d["removed"], d["arrived"]
        row = {"family": fam, "action_string": P.family_astr.get(fam), "side": side, "touch_state": touch, "phase": ph, "time_to_first_refill": k, "removed_quantity": qs(rem), "arrived_quantity": qs(arr),
               "removal_kinds": dict(Counter(d["removal_kind"])), "refill_kinds": dict(Counter(d["kind"]))}
        if rem:
            ratios = [a / r for a, r in zip(arr, rem) if r > 0]
            mom = sum(ratios) / len(ratios) if ratios else None
            ras = sum(arr) / sum(rem) if sum(rem) else None
            row["ratio_pair"] = {"kind": "RATIO_PAIR", "mean_of_member_ratios": (fnum(mom) if mom is not None else None), "ratio_of_aggregate_sums": (fnum(ras) if ras is not None else None),
                                 "difference_label": "COMPLEMENTARY_SCOPE_DIFFERENCE", "difference": (fnum(mom - ras) if (mom is not None and ras is not None) else None), "n": len(ratios)}
            if mom is not None:
                body["averages"].append(average(mom, numerator=sum(ratios), formula="mean over resolved episodes of arrived_quantity/removed_quantity (first arrival only)", population="resolved episodes in stratum", denominator=len(ratios),
                                                family=fam, subfamily=f"touch_state={touch}; ratio_of_aggregate_sums={fnum(ras)}", side=side, phase=ph, status="RESOLVED", cutoff=cutoff,
                                                missingness="pending episodes are censored in the survival view and excluded here", inclusion="resolved episodes"))
        body["strata"].append(row)
    return body


def emit_4_8(P: Pass, cutoff: int) -> dict[str, Any]:
    rows = P.absorption_rows
    if not rows:
        return null_result("4.8", "no fill has occurred yet, so no contact runway exists; every group so far is INDETERMINATE (no traded quantity)", P.groups, cutoff,
                           group_scoped_census={"INDETERMINATE": P.groups})
    disp = Counter(r["disposition"] for r in rows)
    disp["INDETERMINATE_NO_CONTACT"] = P.groups - len(rows)
    strata: dict[tuple, list] = defaultdict(list)
    for r in rows:
        strata[(r["family"], r["hit_side"], r["phase"], r["disposition"])].append(r)
    crs = P.contact_runways
    cdisp = Counter(c["disposition"] for c in crs)
    body = {"section": "4.8", "result": "COMPUTED", "member_group_indices": [r["group_index"] for r in rows[-30:]],
            "runway_scopes": {"GROUP_SCOPED": "the F_LAST group carrying the fill; price response = mid after the group - mid after the previous group",
                              "CONTACT_RUNWAY": "from a fill-bearing group through every following group until the next fill-bearing group (or the stream end, OPEN); replacement = adds on the hit side at the hit prices, withdrawal = cancels on the hit side, retreat = cancels on the opposite side"},
            "disposition_rule": "traded>0 and mid moved in the aggressor's direction -> DELIVERED_THROUGH_PRICE; else withdrawal>0 (group) / withdrawal>=replacement (runway) -> ACCOMPANIED_BY_WITHDRAWAL; else ABSORBED_WITHOUT_PRICE_MOVE; no fill -> INDETERMINATE",
            "group_scoped_census": dict(disp), "contact_runway_census": dict(cdisp), "contact_runways_closed": len(crs), "contact_runway_open": (P.contact_runway is not None),
            "contact_runway_span_groups": qs([c["groups_spanned"] for c in crs]), "contact_runway_duration_ns": qs([c["duration_ns"] for c in crs]),
            "recent_group_runways_exact": rows[-6:], "recent_contact_runways_exact": [{k: v for k, v in c.items() if k != "hit_prices"} for c in crs[-4:]], "strata": [], "averages": []}
    for (fam, side, ph, dp), lst in sorted(strata.items(), key=lambda kv: -len(kv[1]))[:12]:
        traded = [r["traded_quantity"] for r in lst]
        withdrawn = [r["withdrawn_quantity"] for r in lst]
        surv = [r["surviving_depth_at_hit_prices"] for r in lst if r.get("surviving_depth_at_hit_prices") is not None]
        pr = [r["price_response_ticks"] for r in lst if r.get("price_response_ticks") is not None]
        row = {"family": fam, "action_string": P.family_astr.get(fam), "hit_side": side, "phase": ph, "disposition": dp, "n": len(lst), "traded_quantity": qs(traded), "withdrawn_quantity": qs(withdrawn), "surviving_depth": qs(surv), "price_response_ticks": qs(pr)}
        if sum(traded):
            ratios = [w / t for w, t in zip(withdrawn, traded) if t > 0]
            mom = sum(ratios) / len(ratios) if ratios else 0.0
            ras = sum(withdrawn) / sum(traded)
            row["withdrawal_ratio_pair"] = {"kind": "RATIO_PAIR", "mean_of_member_ratios": fnum(mom), "ratio_of_aggregate_sums": fnum(ras), "difference": fnum(mom - ras), "difference_label": "COMPLEMENTARY_SCOPE_DIFFERENCE"}
            body["averages"].append(average(mom, numerator=sum(ratios), formula="mean over runways of withdrawn/traded", population="group-scoped runways in stratum", denominator=len(ratios), family=fam,
                                            subfamily=f"disposition={dp}; ratio_of_aggregate_sums={fnum(ras)}", side=side, phase=ph, status="RESOLVED", cutoff=cutoff, missingness="zero-traded runways are INDETERMINATE and excluded", inclusion="runways with traded>0"))
        body["strata"].append(row)
    return body


def emit_4_9(P: Pass, cutoff: int) -> dict[str, Any]:
    if not P.ladder_by_stratum:
        return null_result("4.9", "no ladder transition yet", P.groups, cutoff)
    body = {"section": "4.9", "result": "COMPUTED", "member_group_indices": [m["group_index"] for m in P.touch_migrations[-30:]] + members_of(P.group_recs[-10:]),
            "scope": "FULL_BOOK set difference between consecutive groups' after-books (book_full.*_levels_full), per side; touch state by spread change; causing orders = the group's raw action order ids",
            "transitions": P.groups, "touch_state_census": dict(P.ladder_touch_state), "touch_migration_events": len(P.touch_migrations), "touch_migrations_recent_exact": P.touch_migrations[-12:],
            "touch_migration_ticks_by_side": {s: qs([m["ticks"] for m in P.touch_migrations if m["side"] == s]) for s in ("B", "A")},
            "current_geometry": {s: {"occupied": len(P.prev_levels[s]), "best_price_raw": P.prev_best[s]} for s in ("B", "A")}, "strata": [], "averages": []}
    for (fam, side, ph), d in sorted(P.ladder_by_stratum.items(), key=lambda kv: -len(kv[1]["births"]))[:10]:
        row = {"family": fam, "action_string": P.family_astr.get(fam), "side": side, "phase": ph, "n": len(d["births"]), "level_births": qs(d["births"]), "level_deaths": qs(d["deaths"]), "occupied_levels": qs(d["occupied"]),
               "max_gap_ticks": qs(d["max_gap_ticks"]), "mean_gap_ticks": qs(d["mean_gap_ticks"]), "depth_concentration_at_touch": qs(d["concentration"]), "touch_migration_ticks_nonzero": qs(d["touch_migration_ticks"]), "depth_migration": qs(d["depth_migration"])}
        body["strata"].append(row)
        q = qs(d["occupied"])
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(occupied levels after the group) / groups", population="groups in stratum", denominator=q["n"], family=fam, subfamily=f"occupied p50={q['p50']} min={q['min']} max={q['max']}; concentration p50={qs(d['concentration']).get('p50')}",
                                        side=side, phase=ph, status="RESOLVED", cutoff=cutoff, missingness="an empty side has no gaps and no concentration", inclusion="all groups in the family"))
    return body


def _cand_public(c: dict[str, Any]) -> dict[str, Any]:
    keep = ("candidate_id", "event_second", "available_second", "polarity", "magnitude", "prominence", "threshold", "baseline", "status", "orientation", "predecessor_id", "alert_second",
            "alert_known_second", "precursor_label", "precursor_lead_seconds", "promotion_label", "promotion_lag_seconds", "sign_reversals", "depth", "parent_id", "transition", "children",
            "termination", "delivered_match", "family_at_promotion", "groups_in_event_second", "window_truncated", "searched_span_seconds", "observations_behind_threshold")
    out = {k: c.get(k) for k in keep}
    out["phases"] = [{k: v for k, v in p.items() if k not in ("imb_sum", "imb_n")} | {"imbalance_mean": (fnum(p["imb_sum"] / p["imb_n"]) if p.get("imb_n") else None)} for p in c["phases"]]
    out["birth"] = rd(c["event_second"] * NS)
    out["availability"] = rd(c["available_second"] * NS)
    return out


def emit_4_10(P: Pass, cutoff: int) -> dict[str, Any]:
    C = P.candidates
    if not C:
        return null_result("4.10", f"no candidate promoted yet; detector has judged {P.det.counters()['seconds_judged']} seconds", P.det.counters()["seconds_observed"], cutoff)
    status = Counter(c["status"] for c in C)
    phases_seen = Counter(p["phase"] for c in C for p in c["phases"])
    strata: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for c in C:
        for p in c["phases"]:
            if p.get("exited_second") is None:
                continue
            k = (c["polarity"], c["orientation"], p["phase"], c["status"])
            strata[k]["dur"].append(p["seconds"])
            strata[k]["dep"].append(p["depletion"])
            strata[k]["ref"].append(p["refill"])
    body = {"section": "4.10", "result": "COMPUTED", "member_group_indices": sorted({g for c in C for g in c["groups_in_event_second"]})[:40] or members_of(P.group_recs[-5:]),
            "runway_rule": "BIRTH = event second to availability; then per completed second, PERSISTENCE while window flow keeps the birth polarity, REVERSAL while it opposes it, QUIET_NO_DIRECTION at zero; COMPLETED_DECAY when, after a REVERSAL, the window carries no classified volume for LOCAL_RADIUS consecutive seconds; a later same-polarity candidate born while the runway is open EXTENDS it, an opposite one COMPLETES it; still open at the cutoff = OPEN (censored at stream end). depletion = fills+cancels on the side the birth polarity consumes, refill = adds on that side, per phase, from raw actions binned by receive second",
            "candidates": len(C), "status_counts": dict(status), "phases_observed": dict(phases_seen), "carried_seed_states": "P/O/S/X are seeds; this pass names phases by the observed flow relation and does not coerce",
            "runways_exact": [_cand_public(c) for c in C[-12:]], "strata": [], "averages": []}
    for (pol, orient, ph, stt), d in sorted(strata.items(), key=lambda kv: -len(kv[1]["dur"]))[:14]:
        q = qs(d["dur"])
        row = {"polarity": pol, "orientation": orient, "phase": ph, "status": stt, "n": q["n"], "duration_seconds": q, "depletion": qs(d["dep"]), "refill": qs(d["ref"])}
        body["strata"].append(row)
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(phase duration seconds) / closed phases", population="closed phases of candidates in stratum", denominator=q["n"], family=f"polarity={pol}", subfamily=f"runway_phase={ph}; depletion p50={qs(d['dep']).get('p50')} refill p50={qs(d['ref']).get('p50')}",
                                        side=orient, phase=phase_of(P), status=("RESOLVED" if stt.startswith("COMPLETED") or stt.startswith("EXTENDED") else "CENSORED"), cutoff=cutoff,
                                        missingness="the open phase of an OPEN runway is excluded; completed duration is never used at an earlier cutoff", inclusion="phases closed at or before the cutoff"))
    return body


def emit_4_11(P: Pass, cutoff: int) -> dict[str, Any]:
    C = P.candidates
    D = P.det
    alerts = D.alerts
    if not C:
        return null_result("4.11", f"no candidate promoted yet; {len(alerts)} threshold-crossing alerts emitted, none yet followed by a promotion", len(alerts), cutoff)
    labels = Counter(c["precursor_label"] for c in C)
    leads = [c["precursor_lead_seconds"] for c in C if c["precursor_label"] == "PRIOR"]
    alert_seconds_used = {c["alert_second"] for c in C}
    followed = sum(1 for a in alerts if a in alert_seconds_used)
    body = {"section": "4.11", "result": "COMPUTED", "member_group_indices": sorted({g for c in C for g in c["groups_in_event_second"]})[:40] or members_of(P.group_recs[-5:]),
            "rule": "the promotion (the detector's own emission) is the first DURABLE lawful call: H+N with N = available - event seconds, never superseded. The earliest lawful PRE-BIRTH signal tested is the threshold-crossing alert: the first second of the contiguous above-bar run that ends at the event second, knowable at alert+1; PRIOR if alert+1 < event, T0 if equal, else H+N. Its precision (alerts followed by a promoted candidate / all alerts) is reported beside every lead because an alert that fires without a promotion is a false alarm on this unit",
            "population": {"candidates": len(C), "precursor_labels": dict(labels), "promotion_labels": {"H+N": len(C)}, "missed": 0, "censored_windows": sum(1 for c in C if c.get("window_truncated"))},
            "prior_lead_seconds": qs(leads), "promotion_lag_seconds": qs([c["promotion_lag_seconds"] for c in C]),
            "alert_precision": {"alerts": len(alerts), "followed_by_promotion": followed, "value": (fnum(followed / len(alerts)) if alerts else None), "basis": "RATIO_OF_EXACT_COUNTS"},
            "first_call_rule": {"superseded_calls": 0, "rule": "a later horizon never replaces the promotion"}, "recent_candidates_exact": [{k: c.get(k) for k in ("candidate_id", "event_second", "available_second", "alert_second", "precursor_label", "precursor_lead_seconds", "promotion_lag_seconds", "polarity")} for c in C[-10:]],
            "reconciliation_with_delivered_episode_rows": {"delivered_episode_rows_seen": len(P.delivered_episode_rows), "delivered_outcomes": dict(Counter(e["recognition_outcome"] for e in P.delivered_episode_rows))},
            "averages": []}
    for pol in (1, -1):
        sub = [c for c in C if c["polarity"] == pol]
        if not sub:
            continue
        for lab in ("PRIOR", "T0", "H+N"):
            ss = [c for c in sub if c["precursor_label"] == lab]
            if not ss:
                continue
            vals = [c["precursor_lead_seconds"] for c in ss]
            q = qs(vals)
            body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(precursor lead seconds) / candidates with this label", population=f"candidates of polarity {pol}", denominator=len(sub), family=f"polarity={pol}",
                                            subfamily=f"label={lab}; n={len(ss)}; p50={q['p50']} max={q['max']}", side="SAME_AND_FLIP_NOT_POOLED_HERE", phase=phase_of(P), status="RESOLVED", cutoff=cutoff,
                                            missingness="labels are reported separately; a mean over successful pre-birth calls only is not the population detection time", inclusion="all candidates carry a label"))
    return body


def emit_4_12(P: Pass, cutoff: int) -> dict[str, Any]:
    C = [c for c in P.candidates if c["stages"]]
    if not C:
        return null_result("4.12", "no candidate has reached its availability second yet, so no runway stage exists", len(P.candidates), cutoff)
    strata: dict[tuple, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    dirs = Counter()
    for c in C:
        for s in c["stages"]:
            dirs[s["dir"]] += 1
            if s["k"] in (0, 1, 2, 5, 10, 20, 45, 50, 90, 120, 180):
                strata[(c["polarity"], c["orientation"])][s["k"]].append((s["flow"], s["imb"], s["mag"]))
    body = {"section": "4.12", "result": "COMPUTED", "member_group_indices": sorted({g for c in C for g in c["groups_in_event_second"]})[:40] or members_of(P.group_recs[-5:]),
            "stage_rule": "one stage per completed second from availability; direction from the sign of window signed flow only (zero = NO_DIRECTION, never resolved); normalized imbalance = (bid_depth-ask_depth)/(bid+ask) of the latest group closed before the second ended; magnitude = |flow| kept beside the signed value; SAME/FLIP = polarity against the latest predecessor and never pooled",
            "stages_seen": sum(len(c["stages"]) for c in C), "direction_census": dict(dirs), "sign_reversals": qs([c["sign_reversals"] for c in C]), "orientation_counts": dict(Counter(c["orientation"] for c in P.candidates)),
            "paths_exact_recent": [{"candidate_id": c["candidate_id"], "polarity": c["polarity"], "orientation": c["orientation"], "stages": c["stages"][:12]} for c in C[-4:]], "stage_paths": [], "averages": []}
    for (pol, orient), ks in sorted(strata.items()):
        path = {}
        for k in sorted(ks):
            vals = ks[k]
            fl = [v[0] for v in vals]
            im = [v[1] for v in vals if v[1] is not None]
            path[str(k)] = {"n": len(vals), "signed_flow": qs(fl), "normalized_imbalance": qs(im), "magnitude": qs([v[2] for v in vals])}
            if k in (0, 10, 50) and fl:
                q = qs(fl)
                body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(window signed flow at stage k) / candidates at risk at k", population="candidates of this polarity and orientation with stage k observed", denominator=q["n"],
                                                family=f"polarity={pol}", subfamily=f"stage_k={k}; imbalance mean={qs(im).get('mean')}; magnitude mean={qs([v[2] for v in vals])['mean']}", side=orient, phase=phase_of(P), status="OPEN", cutoff=cutoff,
                                                missingness="a candidate whose runway closed before stage k is not at risk at k", inclusion="stages at or before the cutoff"))
        body["stage_paths"].append({"polarity": pol, "orientation": orient, "path": path})
    return body


def emit_4_13(P: Pass, cutoff: int) -> dict[str, Any]:
    C = P.candidates
    if not C:
        return null_result("4.13", "no candidate promoted yet, so no exhaustion lineage node exists", 0, cutoff, delivered_lineage_rows_attached_so_far=P.delivered_lineage_in_stream)
    depth = Counter(f"D{c['depth']}" for c in C)
    roots = [c for c in C if c["depth"] == 0]
    desc = [c for c in C if c["depth"] > 0]
    strata: dict[tuple, list] = defaultdict(list)
    for c in desc:
        parent = next(p for p in C if p["candidate_id"] == c["parent_id"])
        strata[(c["transition"], c["polarity"], parent["status"])].append({"interstage_delay_seconds": c["event_second"] - parent["event_second"], "parent_depth": parent["depth"]})
    body = {"section": "4.13", "result": "COMPUTED", "member_group_indices": sorted({g for c in C for g in c["groups_in_event_second"]})[:40] or members_of(P.group_recs[-5:]),
            "lineage_rule": "D is exhaustion-chain depth on the candidate unit: a candidate born while an earlier candidate's runway is still OPEN is that runway's qualifying successor (D = parent D + 1); transition SAME/FLIP by polarity; the parent runway closes as EXTENDED_BY_SUCCESSOR (SAME) or COMPLETED_BY_OPPOSITE_CANDIDATE (FLIP); no maximum depth; roots with no successor are D0 and are OPEN, COMPLETED or CENSORED at the stream end",
            "delivered_lineage_rows_attached_so_far": P.delivered_lineage_in_stream,
            "nodes": len(C), "depth_distribution": dict(depth), "observed_max_depth": max(c["depth"] for c in C), "roots": len(roots), "descendants": len(desc), "status_counts": dict(Counter(c["status"] for c in C)),
            "transition_counts": dict(Counter(c["transition"] for c in desc)), "chains_exact": [{"candidate_id": c["candidate_id"], "depth": c["depth"], "parent_id": c["parent_id"], "transition": c["transition"], "polarity": c["polarity"], "status": c["status"], "children": c["children"]} for c in C[-15:]],
            "strata": [], "averages": []}
    for (tr, pol, pstat), lst in sorted(strata.items(), key=lambda kv: -len(kv[1])):
        q = qs([x["interstage_delay_seconds"] for x in lst])
        body["strata"].append({"transition": tr, "polarity": pol, "parent_status": pstat, "n": len(lst), "interstage_delay_seconds": q, "parent_depths": dict(Counter(x["parent_depth"] for x in lst))})
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(child event second - parent event second) / descendants", population="descendants in stratum", denominator=q["n"], family="EXHAUSTION_CHAIN_CANDIDATE_LINEAGE", subfamily=f"transition={tr}; parent_status={pstat}",
                                        side=f"polarity={pol}", phase=phase_of(P), status="RESOLVED", cutoff=cutoff, missingness="roots have no interstage delay and are excluded by construction", inclusion="descendants only"))
    return body


def emit_4_14(P: Pass, cutoff: int) -> dict[str, Any]:
    if P.groups < 2:
        return null_result("4.14", "fewer than two groups", P.groups, cutoff)
    top_edges = [{"from": a, "to": b, "count": n, "outgoing_denominator": P.family_out[a], "conditional_probability": fnum(n / P.family_out[a]), "statistic_kind": "CONDITIONAL_PROBABILITY"} for (a, b), n in P.family_edges.most_common(20)]
    within = [{"from": a, "to": b, "count": n, "outgoing_denominator": P.within_out[a], "conditional_probability": fnum(n / P.within_out[a]), "statistic_kind": "CONDITIONAL_PROBABILITY"} for (a, b), n in P.within_edges.most_common(24)]
    fam_tot = Counter()
    for (f, _), n in P.family_counts.items():
        fam_tot[f] += n
    body = {"section": "4.14", "result": "COMPUTED", "member_group_indices": members_of(P.group_recs[-40:]),
            "scopes": {"CROSS_GROUP": "interarrival gaps between consecutive members of one family on the F_LAST receive clock, family-to-family transition edges between consecutive groups, and maximal runs of consecutive same-family groups",
                       "WITHIN_GROUP": "node = action|side; maximal homogeneous runs and transition edges inside groups"},
            "cross_group_family_edges_top": top_edges, "within_group_edges_top": within,
            "same_family_run_lengths": {"runs": sum(P.same_family_runs.values()), "longest": sorted(((ln, f, n) for (f, ln), n in P.same_family_runs.items()), reverse=True)[:8]},
            "within_group_run_lengths_top": [{"node": nd, "length": ln, "runs": n} for (nd, ln), n in sorted(P.run_lengths.items(), key=lambda kv: (-kv[0][1], -kv[1]))[:12]],
            "family_interarrival_top": {}, "same_order_paths_top": [{"path": p, "n": n} for p, n in P.order_paths.most_common(10)], "averages": []}
    for f, n in fam_tot.most_common(8):
        g = P.family_gaps.get(f, [])
        if not g:
            continue
        q = qs(g)
        body["family_interarrival_top"][f] = {"action_string": P.family_astr[f], "recurrences": len(g), "interarrival_gap_ns": q}
        body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(gap between consecutive members' F_LAST receive) / recurrences", population="recurrences of the family (members after the first)", denominator=q["n"], family=f, subfamily=f"gap p50={q['p50']} p90={q['p90']} max={q['max']}",
                                        side=P.family_sstr[f][:8], phase=phase_of(P), status="RESOLVED", cutoff=cutoff, missingness="the first member has no gap", inclusion="consecutive members on the receive clock"))
    return body


def emit_4_15(P: Pass, cutoff: int, frozen: bool) -> dict[str, Any]:
    sizes = P.cluster_members
    body = {"section": "4.15", "result": "COMPUTED", "member_group_indices": [P.cluster_first[c] for c, _ in sizes.most_common(30)],
            "cluster_version": CLUSTER_VERSION, "feature_schema": ["log1p(component_count)", "log1p(A)", "log1p(C)", "log1p(M)", "log1p(T)", "log1p(F)", "log1p(side B)", "log1p(side A)", "log1p(distinct prices)", "log1p(price span ticks)"],
            "distance": "L1", "radius": CLUSTER_RADIUS, "rule": "leader clustering in causal order: a member joins the nearest existing leader within the radius, else founds a new cluster whose id is content-derived from its features; singletons preserved; no outcome or later response in the features",
            "schema_hash": sha(canonical_bytes({"schema": "log1p 10 features", "distance": "L1", "radius": CLUSTER_RADIUS, "rule": "leader-causal"})), "discovery_frozen": frozen,
            "clusters": len(sizes), "singleton_clusters": sum(1 for n in sizes.values() if n == 1), "top_clusters": [{"cluster_id": c, "members": n, "first_group": P.cluster_first[c]} for c, n in sizes.most_common(12)],
            "assignment_distance": qs([r["cld"] for r in P.group_recs[-5000:]]), "averages": []}
    if frozen:
        for c, n in sizes.most_common(6):
            body["averages"].append(average(n / P.groups, numerator=n, formula="members in cluster / groups", population="all delivered groups", denominator=P.groups, family="OPEN_WORLD_CLUSTER", subfamily=c, side="N/A", phase=phase_of(P), status="RESOLVED", cutoff=cutoff,
                                            cluster_version=CLUSTER_VERSION, missingness="none", inclusion="all groups; description written only after discovery froze at the stream end"))
    else:
        body["note"] = "discovery is not frozen; no cluster description or prevalence average is licensed before the stream end"
    return body


def emit_4_16(P: Pass, cutoff: int) -> dict[str, Any]:
    C = [c for c in P.candidates if c["horizons"] or c["change_points"]]
    if not C:
        return null_result("4.16", "no candidate has reached any horizon or change point yet", len(P.candidates), cutoff)
    body = {"section": "4.16", "result": "COMPUTED", "member_group_indices": sorted({g for c in C for g in c["groups_in_event_second"]})[:40] or members_of(P.group_recs[-5:]),
            "horizon_rule": "from the candidate's availability second; fixed horizons are offsets equal to declared substrate/detector parameters (roll window, refractory, detection lag, two detection lags), each read at its own receive-clock instant with its own at-risk denominator; event-driven change points = the first six mid changes after availability; censored at the stream end",
            "horizon_offsets_seconds": HORIZON_OFFSETS, "tracks": len(P.candidates), "at_risk": {}, "tables": [], "change_points_recent": [{"candidate_id": c["candidate_id"], "change_points": [{**cp, "at": rd(cp["at_second"] * NS)} for cp in c["change_points"]]} for c in C[-4:]], "averages": []}
    for h, off in HORIZON_OFFSETS.items():
        entered = sum(1 for c in P.candidates if c["available_second"] * NS <= cutoff)
        observed = [c for c in P.candidates if h in c["horizons"]]
        body["at_risk"][h] = {"entered": entered, "observed": len(observed), "censored_or_pending": entered - len(observed), "horizon_offset_seconds": off}
        for pol in (1, -1):
            for orient in ("SAME", "FLIP", "NO_PREDECESSOR"):
                sub = [c for c in observed if c["polarity"] == pol and c["orientation"] == orient]
                if not sub:
                    continue
                pr = [c["horizons"][h]["price_response_ticks"] for c in sub if c["horizons"][h]["price_response_ticks"] is not None]
                fr = [c["horizons"][h]["flow_response"] for c in sub if c["horizons"][h]["flow_response"] is not None]
                bk = [c["horizons"][h]["full_book_response"] for c in sub]
                qr = [c["horizons"][h]["queue_response_touch_orders"] for c in sub]
                row = {"horizon": h, "at": rd(cutoff), "polarity": pol, "orientation": orient, "n": len(sub), "price_response_ticks": qs(pr), "flow_response": qs(fr), "full_book_response": qs(bk), "queue_response_touch_orders": qs(qr)}
                body["tables"].append(row)
                if pr:
                    q = qs(pr)
                    body["averages"].append(average(q["mean"], numerator=q["sum"], formula="sum(mid at horizon - mid at availability, ticks) / candidates observed at the horizon", population="candidates at risk and observed at this horizon", denominator=len(sub), family=f"polarity={pol}",
                                                    subfamily=f"horizon={h}; p10={q['p10']} p50={q['p50']} p90={q['p90']}; flow_response mean={qs(fr).get('mean')}", side=orient, phase=phase_of(P), status="RESOLVED", cutoff=cutoff,
                                                    missingness="candidates whose horizon has not matured are censored with their count", inclusion="observed at the horizon"))
    return body


SECTION_EMITTERS = {"4.0": emit_4_0, "4.0b": emit_4_0b, "4.1": emit_4_1, "4.2": emit_4_2, "4.3": emit_4_3, "4.4": emit_4_4, "4.5": emit_4_5, "4.6": emit_4_6, "4.7": emit_4_7,
                    "4.8": emit_4_8, "4.9": emit_4_9, "4.10": emit_4_10, "4.11": emit_4_11, "4.12": emit_4_12, "4.13": emit_4_13, "4.14": emit_4_14, "4.16": emit_4_16}
