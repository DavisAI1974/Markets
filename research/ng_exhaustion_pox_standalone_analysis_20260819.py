#!/usr/bin/env python3
"""Standalone, contamination-safe analysis for the fixed 3,429 NG POX cases.

This runner never constructs or filters the POX population.  It validates the
fixed ledger, joins each identity to the frozen causal input records, measures
branch observational knowability, and performs expanding-window chronological
OOT FLIP/SAME prediction at dense causal checkpoints.

Raw-tape execution economics are intentionally not approximated here.  They
remain fail-closed until the authoritative NG raw trade/quote tape is supplied.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


EXPECTED_TOTAL = 3429
EXPECTED_FLIP = 1546
EXPECTED_SAME = 1883
SERIES_FIELDS = (
    "dipole_roll20_oriented_t_minus60_to_plus60",
    "dipole_roll60_raw_t_minus60_to_plus60",
    "book_10level_imbalance_t_minus60_to_plus60",
    "aggressor_buy_volume_t_minus60_to_plus60",
    "aggressor_sell_volume_t_minus60_to_plus60",
)
WINDOWS_S = (5, 10, 20, 60)
RAW_ACTIONS = ("A", "C", "M", "T", "R")
TICK = 0.001
V3_PRICE_LAGS_S = (1, 2, 3, 5, 10, 20, 30, 60, 120)
V3_RANGE_WINDOWS_S = (5, 20, 60)
V3_FLOW_WINDOWS_S = (1, 3, 5, 10, 20, 30, 60)
V3_BOOK_LAGS_S = (0, 1, 2, 3, 5, 10, 20, 30, 60)
V3_DENSE_PATH_S = 60
V3_DENSE_BOOK_S = 20
LIVE_STATE_LAGS_S = (0, 1, 2, 3, 5, 10, 20, 30, 60)
LIVE_SUMMARY_WINDOWS_S = (5, 20, 60)
V3_LIVE_MARKET_POLICY = (
    "OBSERVED_UNORIENTED_PRICE_DIRECTION_VELOCITY_RANGE_DENSE_PRICE_PATH_"
    "SIGNED_FLOW_DENSE_ROLL20_DIPOLE_BOOK_LAGS_CHANGES_DENSE_BOOK_PATH_AND_"
    "CAUSAL_CLOCK_THROUGH_COMPLETED_CHECKPOINT_WITHOUT_TARGET_POLARITY_OR_CONFIRMATION"
)
FEATURE_LAYER_POLICY = (
    "RETAIN_EXISTING_CAUSAL_RAW_AND_V3_LIVE_FEATURES; APPEND_V4_AS_A_DISTINCT_ADDITIVE_LAYER; "
    "V4_MUST_NOT_REPLACE_RENAME_OR_SHADOW_V3"
)
MBO_FIELDS = (
    "add_events", "add_size", "add_bid_size", "add_ask_size",
    "cancel_events", "cancel_size", "cancel_bid_size", "cancel_ask_size",
    "modify_events", "modify_size",
    "trade_events", "trade_size", "trade_bid_size", "trade_ask_size",
    "fill_events", "fill_size",
)
POLICY = "FIXED_3429_DO_NOT_REOPEN"
FAIL_POLICY = "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL"
PRIMARY_SELECTIVE_CONFIDENCE = 0.75
SELECTIVE_CONFIDENCE_THRESHOLDS = (PRIMARY_SELECTIVE_CONFIDENCE,)


def h_checkpoint_grid(maximum_h: int) -> list[int]:
    """User-authorized cadence with a data-derived end, never a fixed H cap."""
    if maximum_h < 0:
        return []
    checkpoints = list(range(0, min(5, maximum_h) + 1))
    if maximum_h >= 10:
        checkpoints.extend(range(10, maximum_h + 1, 5))
    return checkpoints


def prior_checkpoint_grid(prior_start_offsets: Iterable[int | None]) -> list[int]:
    """Mirror the H cadence from each causal predecessor boundary toward t0."""
    starts = sorted({int(value) for value in prior_start_offsets if value is not None and int(value) < 0})
    if not starts:
        return []
    earliest = starts[0]
    checkpoints = set(starts)
    checkpoints.update(range(max(-5, earliest), 0))
    first_multiple = int(math.ceil(earliest / 5.0) * 5)
    checkpoints.update(range(first_multiple, -5, 5))
    return sorted(value for value in checkpoints if earliest <= value < 0)


def on_prior_checkpoint_grid(prior_start_offset_s: int | None, checkpoint_s: int) -> bool:
    if prior_start_offset_s is None or checkpoint_s < int(prior_start_offset_s) or checkpoint_s >= 0:
        return False
    return checkpoint_s == int(prior_start_offset_s) or checkpoint_s >= -5 or checkpoint_s % 5 == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--roster", required=True, type=Path)
    parser.add_argument("--reveal-records", required=True, type=Path)
    parser.add_argument("--blind-records", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open_text(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_json(path: Path) -> Any:
    with open_text(path) as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def event_key(day: Any, second: Any, polarity: Any) -> tuple[str, int, int]:
    return str(day), int(second), int(polarity)


def percentile_summary(values: Iterable[float | int | None]) -> dict[str, Any]:
    array = np.asarray([float(value) for value in values if value is not None and math.isfinite(float(value))])
    if not len(array):
        return {"n": 0, "min": None, "p10": None, "p25": None, "median": None, "p75": None, "p90": None, "max": None, "mean": None}
    return {
        "n": int(len(array)),
        "min": float(np.min(array)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "max": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def utc_at(epoch_s: int, offset_s: int | None) -> str | None:
    if offset_s is None:
        return None
    return (datetime.fromtimestamp(epoch_s, tz=timezone.utc) + timedelta(seconds=int(offset_s))).isoformat()


def finite_float(value: Any) -> float:
    if value is None:
        return float("nan")
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return result if math.isfinite(result) else float("nan")


def normalized_seconds(raw: Any) -> float | None:
    value = finite_float(raw)
    if not math.isfinite(value) or value <= 0:
        return None
    if value > 1e17:
        value /= 1e9
    elif value > 1e14:
        value /= 1e6
    elif value > 1e11:
        value /= 1e3
    return value % 86400.0


class RawCausalDay:
    """End-of-second causal market state built only from raw rows seen so far."""

    def __init__(self, path: Path):
        match = re.search(r"(20\d{6})", path.name)
        if not match:
            raise RuntimeError(f"cannot parse raw day from {path}")
        self.day = match.group(1)
        n = 86400
        self.bid = np.full(n, np.nan)
        self.ask = np.full(n, np.nan)
        self.mid = np.full(n, np.nan)
        self.spread_ticks = np.full(n, np.nan)
        self.book_imbalance = np.full(n, np.nan)
        self.book_imbalance_sum = np.zeros(n)
        self.book_imbalance_count = np.zeros(n)
        self.bid_depth10 = np.full(n, np.nan)
        self.ask_depth10 = np.full(n, np.nan)
        self.last_trade = np.full(n, np.nan)
        self.trade_volume = np.zeros(n)
        self.buy_volume = np.zeros(n)
        self.sell_volume = np.zeros(n)
        self.trade_count = np.zeros(n)
        self.raw_row_count = np.zeros(n)
        self.mid_sum = np.zeros(n)
        self.mid_count = np.zeros(n)
        self.mid_high = np.full(n, np.nan)
        self.mid_low = np.full(n, np.nan)
        self.spread_sum = np.zeros(n)
        self.spread_count = np.zeros(n)
        self.spread_high = np.full(n, np.nan)
        self.spread_low = np.full(n, np.nan)
        self.trade_high = np.full(n, np.nan)
        self.trade_low = np.full(n, np.nan)
        self.trade_notional = np.zeros(n)
        self.action_counts = {action: np.zeros(n) for action in RAW_ACTIONS}
        self.level_fields = {
            f"{side}_{kind}_{level:02d}": np.full(n, np.nan)
            for side in ("bid", "ask")
            for kind in ("px", "sz")
            for level in range(10)
        }
        self.raw_rows = 0
        self.first_observed_second: int | None = None
        self.last_observed_second: int | None = None
        self.first_trade_second: int | None = None
        self.week_first_trade_elapsed_s: int | None = None
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                second_f = normalized_seconds(row.get("ts_event", row.get("ts")))
                if second_f is None:
                    continue
                second = int(second_f)
                self.raw_rows += 1
                self.first_observed_second = second if self.first_observed_second is None else min(self.first_observed_second, second)
                self.last_observed_second = second if self.last_observed_second is None else max(self.last_observed_second, second)
                self.raw_row_count[second] += 1
                action = str(row.get("action", ""))
                if action in self.action_counts:
                    self.action_counts[action][second] += 1
                for name, array in self.level_fields.items():
                    value = finite_float(row.get(name))
                    if math.isfinite(value) and value >= 0:
                        array[second] = value
                bid = finite_float(row.get("bid_px_00"))
                ask = finite_float(row.get("ask_px_00"))
                valid_quote = math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask >= bid
                if valid_quote:
                    bid_depth = sum(finite_float(row.get(f"bid_sz_{level:02d}")) for level in range(10))
                    ask_depth = sum(finite_float(row.get(f"ask_sz_{level:02d}")) for level in range(10))
                    if not math.isfinite(bid_depth):
                        bid_depth = 0.0
                    if not math.isfinite(ask_depth):
                        ask_depth = 0.0
                    self.bid[second] = bid
                    self.ask[second] = ask
                    self.mid[second] = 0.5 * (bid + ask)
                    self.spread_ticks[second] = (ask - bid) / 0.001
                    midpoint = self.mid[second]
                    spread = self.spread_ticks[second]
                    self.mid_sum[second] += midpoint
                    self.mid_count[second] += 1
                    self.mid_high[second] = midpoint if not math.isfinite(float(self.mid_high[second])) else max(self.mid_high[second], midpoint)
                    self.mid_low[second] = midpoint if not math.isfinite(float(self.mid_low[second])) else min(self.mid_low[second], midpoint)
                    self.spread_sum[second] += spread
                    self.spread_count[second] += 1
                    self.spread_high[second] = spread if not math.isfinite(float(self.spread_high[second])) else max(self.spread_high[second], spread)
                    self.spread_low[second] = spread if not math.isfinite(float(self.spread_low[second])) else min(self.spread_low[second], spread)
                    self.bid_depth10[second] = bid_depth
                    self.ask_depth10[second] = ask_depth
                    total_depth = bid_depth + ask_depth
                    self.book_imbalance[second] = (bid_depth - ask_depth) / total_depth if total_depth > 0 else np.nan
                    if total_depth > 0:
                        self.book_imbalance_sum[second] += self.book_imbalance[second]
                        self.book_imbalance_count[second] += 1
                if row.get("action") == "T":
                    price = finite_float(row.get("price"))
                    size = finite_float(row.get("size", row.get("qty")))
                    if math.isfinite(price) and price > 0:
                        self.first_trade_second = (
                            second if self.first_trade_second is None else min(self.first_trade_second, second)
                        )
                        self.last_trade[second] = price
                        self.trade_high[second] = price if not math.isfinite(float(self.trade_high[second])) else max(self.trade_high[second], price)
                        self.trade_low[second] = price if not math.isfinite(float(self.trade_low[second])) else min(self.trade_low[second], price)
                        self.trade_count[second] += 1
                        if math.isfinite(size) and size > 0:
                            self.trade_volume[second] += size
                            self.trade_notional[second] += price * size
                            if valid_quote:
                                midpoint = 0.5 * (bid + ask)
                                if price > midpoint:
                                    self.buy_volume[second] += size
                                elif price < midpoint:
                                    self.sell_volume[second] += size
        for field in ("bid", "ask", "mid", "spread_ticks", "book_imbalance", "bid_depth10", "ask_depth10", "last_trade"):
            array = getattr(self, field)
            last = np.nan
            for index in range(n):
                if math.isfinite(float(array[index])):
                    last = array[index]
                elif math.isfinite(float(last)):
                    array[index] = last
        for array in self.level_fields.values():
            last = np.nan
            for index in range(n):
                if math.isfinite(float(array[index])):
                    last = array[index]
                elif math.isfinite(float(last)):
                    array[index] = last
        self.mid_mean = np.divide(self.mid_sum, self.mid_count, out=np.full(n, np.nan), where=self.mid_count > 0)
        self.spread_mean = np.divide(self.spread_sum, self.spread_count, out=np.full(n, np.nan), where=self.spread_count > 0)
        self.trade_vwap = np.divide(self.trade_notional, self.trade_volume, out=np.full(n, np.nan), where=self.trade_volume > 0)
        self.book_imbalance_mean = np.divide(
            self.book_imbalance_sum,
            self.book_imbalance_count,
            out=np.full(n, np.nan),
            where=self.book_imbalance_count > 0,
        )
        self.buy_volume_cumsum = np.concatenate(([0.0], np.cumsum(self.buy_volume, dtype=float)))
        self.sell_volume_cumsum = np.concatenate(([0.0], np.cumsum(self.sell_volume, dtype=float)))


def load_raw_causal_days(raw_dir: Path, required_days: list[str]) -> tuple[dict[str, RawCausalDay], dict[str, Any]]:
    paths = sorted(raw_dir.glob("NG_*.jsonl.gz"))
    days = [RawCausalDay(path) for path in paths]
    by_day = {day.day: day for day in days}
    missing = sorted(set(required_days) - set(by_day))
    if missing:
        raise RuntimeError(f"raw causal day mismatch: required={required_days} supplied={sorted(by_day)} missing={missing}")

    # Match V3's week-continuous last-observation semantics at UTC boundaries.
    # Exact within-second means are never carried; only normally observable last
    # quote/trade/book state is carried into the next consecutive supplied day.
    carry_fields = ("bid", "ask", "mid", "spread_ticks", "book_imbalance", "bid_depth10", "ask_depth10", "last_trade")
    ordered = sorted(by_day)
    for previous_name, current_name in zip(ordered, ordered[1:]):
        previous_date = datetime.strptime(previous_name, "%Y%m%d")
        current_date = datetime.strptime(current_name, "%Y%m%d")
        if (current_date - previous_date).days != 1:
            continue
        previous = by_day[previous_name]
        current = by_day[current_name]
        for field in carry_fields:
            source = getattr(previous, field)
            target = getattr(current, field)
            if not math.isfinite(float(source[-1])):
                continue
            finite = np.flatnonzero(np.isfinite(target))
            stop = int(finite[0]) if len(finite) else len(target)
            target[:stop] = source[-1]
        for field in previous.level_fields:
            source = previous.level_fields[field]
            target = current.level_fields[field]
            if not math.isfinite(float(source[-1])):
                continue
            finite = np.flatnonzero(np.isfinite(target))
            stop = int(finite[0]) if len(finite) else len(target)
            target[:stop] = source[-1]
    by_week: dict[str, list[RawCausalDay]] = defaultdict(list)
    for raw_day in by_day.values():
        date = datetime.strptime(raw_day.day, "%Y%m%d")
        sunday = date - timedelta(days=(date.weekday() + 1) % 7)
        by_week[sunday.strftime("%Y%m%d")].append(raw_day)
    for week_sunday, week_days in by_week.items():
        sunday = datetime.strptime(week_sunday, "%Y%m%d")
        first_trade = min(
            (
                (datetime.strptime(raw_day.day, "%Y%m%d") - sunday).days * 86400
                + int(raw_day.first_trade_second)
                for raw_day in week_days
                if raw_day.first_trade_second is not None
            ),
            default=None,
        )
        for raw_day in week_days:
            raw_day.week_first_trade_elapsed_s = first_trade
    provenance = {
        day.day: {"name": path.name, "sha256": sha256(path), "raw_rows": day.raw_rows}
        for path, day in zip(paths, days)
    }
    return by_day, provenance


def shifted_day_second(day: str, second: int) -> tuple[str, int]:
    base = datetime.strptime(day, "%Y%m%d")
    day_offset, resolved_second = divmod(int(second), 86400)
    return (base + timedelta(days=day_offset)).strftime("%Y%m%d"), resolved_second


def available_observation_end_offset_s(
    case: dict[str, Any], raw_days: dict[str, RawCausalDay]
) -> int:
    """Last causally observable raw second in the consecutive supplied tape."""
    event_day = str(case["clock"]["day"])
    event_second = int(case["clock"]["second_utc"])
    cursor = datetime.strptime(event_day, "%Y%m%d")
    day_offset = 0
    last_offset = -1
    while True:
        day_name = cursor.strftime("%Y%m%d")
        raw_day = raw_days.get(day_name)
        if raw_day is None or raw_day.last_observed_second is None:
            break
        last_offset = day_offset * 86400 + int(raw_day.last_observed_second) - event_second
        cursor += timedelta(days=1)
        day_offset += 1
    return last_offset


def attach_computational_windows(
    joined: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    raw_days: dict[str, RawCausalDay],
) -> None:
    """Attach data-derived prior/H bounds; no fixed lead or H horizon."""
    for candidate in candidates:
        tape_end = available_observation_end_offset_s(candidate, raw_days)
        next_event = candidate.get("next_event_t0_offset_s")
        natural_end = tape_end if next_event is None else min(tape_end, int(next_event) - 1)
        candidate["authoritative_tape_end_offset_s"] = tape_end
        candidate["membership_h_end_offset_s"] = max(-1, natural_end)
    for case in joined:
        tape_end = available_observation_end_offset_s(case, raw_days)
        branch_known = case.get("branch_causally_known_offset_s")
        natural_end = tape_end if branch_known is None else min(tape_end, int(branch_known) - 1)
        case["authoritative_tape_end_offset_s"] = tape_end
        case["branch_h_end_offset_s"] = max(-1, natural_end)


def raw_value(raw_days: dict[str, RawCausalDay], day: str, second: int, field: str) -> float:
    resolved_day, resolved_second = shifted_day_second(day, second)
    source = raw_days.get(resolved_day)
    if source is None:
        return float("nan")
    return finite_float(getattr(source, field)[resolved_second])


def raw_state_value(
    raw_days: dict[str, RawCausalDay], day: str, second: int, field: str, *, level_field: bool = False
) -> float:
    resolved_day, resolved_second = shifted_day_second(day, second)
    source = raw_days.get(resolved_day)
    if source is None:
        return float("nan")
    array = source.level_fields[field] if level_field else getattr(source, field)
    return finite_float(array[resolved_second])


def raw_count_value(
    raw_days: dict[str, RawCausalDay], day: str, second: int, field: str, *, action: str | None = None
) -> float:
    resolved_day, resolved_second = shifted_day_second(day, second)
    source = raw_days.get(resolved_day)
    if source is None:
        return 0.0
    array = source.action_counts[action] if action is not None else getattr(source, field)
    return finite_float(array[resolved_second])


def raw_sum(raw_days: dict[str, RawCausalDay], day: str, start_second: int, end_second: int, field: str) -> float:
    if end_second < start_second:
        return 0.0
    total = 0.0
    cursor = int(start_second)
    while cursor <= end_second:
        resolved_day, resolved_second = shifted_day_second(day, cursor)
        source = raw_days.get(resolved_day)
        segment_n = min(end_second - cursor + 1, 86400 - resolved_second)
        if source is not None:
            cumulative = getattr(source, f"{field}_cumsum")
            total += float(cumulative[resolved_second + segment_n] - cumulative[resolved_second])
        cursor += segment_n
    return total


def live_book_value(raw_days: dict[str, RawCausalDay], day: str, second: int) -> float:
    exact = raw_value(raw_days, day, second, "book_imbalance_mean")
    return exact if math.isfinite(exact) else raw_value(raw_days, day, second, "book_imbalance")


def live_flow_state(raw_days: dict[str, RawCausalDay], day: str, start_second: int, end_second: int) -> tuple[float, float, float, float]:
    buy = raw_sum(raw_days, day, start_second, end_second, "buy_volume")
    sell = raw_sum(raw_days, day, start_second, end_second, "sell_volume")
    signed = buy - sell
    total = buy + sell
    return (float(total > 0), signed, total, signed / total if total > 0 else 0.0)


def live_market_features(case: dict[str, Any], checkpoint_s: int, raw_days: dict[str, RawCausalDay]) -> dict[str, float]:
    """V3-equivalent continuous market state through the completed checkpoint.

    Every feature is target-agnostic and un-oriented.  The helper reads only
    seconds at or before ``t0 + checkpoint_s`` and is shared by membership and
    FLIP/SAME models, including all prebirth checkpoints.
    """
    day = str(case["clock"]["day"])
    cutoff = int(case["clock"]["second_utc"]) + int(checkpoint_s)
    features: dict[str, float] = {"v3_live_contract_present": 1.0}

    for label, field in (("trade", "last_trade"), ("mid", "mid")):
        now = raw_value(raw_days, day, cutoff, field)
        features[f"v3_live_{label}_price_known"] = float(math.isfinite(now))
        features[f"v3_live_{label}_price_log"] = math.log(max(now, 1e-12)) if math.isfinite(now) else float("nan")
        for lag in V3_PRICE_LAGS_S:
            prior = raw_value(raw_days, day, cutoff - lag, field)
            known = math.isfinite(now) and math.isfinite(prior)
            features[f"v3_live_{label}_direction_lag{lag}_known"] = float(known)
            features[f"v3_live_{label}_direction_lag{lag}_asinh_ticks"] = (
                math.asinh((now - prior) / TICK) if known else float("nan")
            )
        for window in V3_RANGE_WINDOWS_S:
            start = cutoff - window + 1
            base = raw_value(raw_days, day, start, field)
            path = [raw_value(raw_days, day, second, field) for second in range(start, cutoff + 1)]
            finite = [value for value in path if math.isfinite(value)]
            known = math.isfinite(now) and math.isfinite(base) and bool(finite)
            prefix = f"v3_live_{label}_range_w{window}"
            features[f"{prefix}_known"] = float(known)
            if known:
                high = max(finite)
                low = min(finite)
                features[f"{prefix}_direction_asinh_ticks"] = math.asinh((now - base) / TICK)
                features[f"{prefix}_high_asinh_ticks"] = math.asinh((high - base) / TICK)
                features[f"{prefix}_low_asinh_ticks"] = math.asinh((low - base) / TICK)
                features[f"{prefix}_width_asinh_ticks"] = math.asinh((high - low) / TICK)
            else:
                for suffix in ("direction_asinh_ticks", "high_asinh_ticks", "low_asinh_ticks", "width_asinh_ticks"):
                    features[f"{prefix}_{suffix}"] = float("nan")
        dense_base = raw_value(raw_days, day, cutoff - V3_DENSE_PATH_S, field)
        for lag in range(V3_DENSE_PATH_S, -1, -1):
            value = raw_value(raw_days, day, cutoff - lag, field)
            known = math.isfinite(dense_base) and math.isfinite(value)
            features[f"v3_live_{label}_dense_path_lag{lag}_known"] = float(known)
            features[f"v3_live_{label}_dense_path_lag{lag}_asinh_ticks"] = (
                math.asinh((value - dense_base) / TICK) if known else float("nan")
            )

    for window in V3_FLOW_WINDOWS_S:
        known, signed, total, ratio = live_flow_state(raw_days, day, cutoff - window + 1, cutoff)
        prefix = f"v3_live_flow_w{window}"
        features[f"{prefix}_known"] = known
        features[f"{prefix}_signed_asinh"] = math.asinh(signed)
        features[f"{prefix}_total_asinh"] = math.asinh(total)
        features[f"{prefix}_dipole_ratio"] = ratio
    _, _, _, current20 = live_flow_state(raw_days, day, cutoff - 19, cutoff)
    _, _, _, previous20 = live_flow_state(raw_days, day, cutoff - 39, cutoff - 20)
    features["v3_live_dipole_roll20_current"] = current20
    features["v3_live_dipole_roll20_previous"] = previous20
    features["v3_live_dipole_roll20_change"] = current20 - previous20
    features["v3_live_dipole_roll20_magnitude"] = abs(current20)
    for lag in range(V3_DENSE_PATH_S, -1, -1):
        end = cutoff - lag
        known, _, _, ratio = live_flow_state(raw_days, day, end - 19, end)
        features[f"v3_live_dipole_roll20_path_lag{lag}_known"] = known
        features[f"v3_live_dipole_roll20_path_lag{lag}"] = ratio

    book_history: dict[int, float] = {}
    for lag in V3_BOOK_LAGS_S:
        value = live_book_value(raw_days, day, cutoff - lag)
        book_history[lag] = value
        features[f"v3_live_book_lag{lag}_known"] = float(math.isfinite(value))
        features[f"v3_live_book_lag{lag}_imbalance"] = value
    current_book = book_history[0]
    for lag in (5, 20, 60):
        prior = book_history[lag]
        known = math.isfinite(current_book) and math.isfinite(prior)
        features[f"v3_live_book_change_lag{lag}_known"] = float(known)
        features[f"v3_live_book_change_lag{lag}"] = current_book - prior if known else float("nan")
    for lag in range(V3_DENSE_BOOK_S, -1, -1):
        value = live_book_value(raw_days, day, cutoff - lag)
        features[f"v3_live_book_dense_path_lag{lag}_known"] = float(math.isfinite(value))
        features[f"v3_live_book_dense_path_lag{lag}_imbalance"] = value

    decision_second = cutoff % 86400
    angle = 2.0 * math.pi * decision_second / 86400.0
    features["v3_live_clock_utc_sin"] = math.sin(angle)
    features["v3_live_clock_utc_cos"] = math.cos(angle)
    source = case.get("source_roster_identity") or {}
    week_sunday = source.get("week_sunday")
    if week_sunday:
        elapsed = (datetime.strptime(day, "%Y%m%d") - datetime.strptime(str(week_sunday), "%Y%m%d")).days * 86400 + cutoff
        source_day = raw_days.get(day)
        first_trade = None if source_day is None else getattr(source_day, "week_first_trade_elapsed_s", None)
        features["v3_live_hours_since_week_first_trade_asinh"] = (
            math.asinh(max(0.0, float(elapsed) - float(first_trade)) / 3600.0)
            if first_trade is not None
            else float("nan")
        )
        features["v3_live_week_elapsed_fraction"] = max(0.0, min(1.0, elapsed / (6.0 * 86400.0)))
    else:
        features["v3_live_hours_since_week_first_trade_asinh"] = float("nan")
        features["v3_live_week_elapsed_fraction"] = float("nan")
    return features


def predecessor_features(case: dict[str, Any], checkpoint_s: int) -> dict[str, float]:
    """Expose only a predecessor state already confirmed by the checkpoint."""
    context = case.get("predecessor_causal_context")
    known = bool(context is not None and int(context["confirmation_offset_s"]) <= checkpoint_s)
    features = {
        "predecessor_confirmed_by_checkpoint": float(known),
        "predecessor_seconds_since_confirmation": (
            float(checkpoint_s - int(context["confirmation_offset_s"])) if known else float("nan")
        ),
        "predecessor_polarity": float(context["polarity"]) if known else float("nan"),
    }
    for family in ("A", "B", "C"):
        features[f"predecessor_family_{family}"] = float(context.get("family") == family) if known else float("nan")
    return features


def series_stats(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    finite = np.isfinite(array)
    if not np.any(finite):
        return {name: float("nan") for name in ("mean", "std", "min", "max", "delta", "slope", "last")}
    clean = array[finite]
    positions = np.arange(len(array), dtype=float)[finite]
    slope = 0.0
    if len(clean) >= 2 and float(np.var(positions)) > 0:
        slope = float(np.polyfit(positions, clean, 1)[0])
    first = float(clean[0])
    last = float(clean[-1])
    return {
        "mean": float(np.mean(clean)),
        "std": float(np.std(clean)),
        "min": float(np.min(clean)),
        "max": float(np.max(clean)),
        "delta": last - first,
        "slope": slope,
        "last": last,
    }


def raw_market_features(
    case: dict[str, Any], checkpoint_s: int, raw_days: dict[str, RawCausalDay]
) -> dict[str, float]:
    """Fixed-size, maximally rich causal market state; execute at H+1.

    V3-style rolling paths retain evolving information without making feature
    width grow with H.  Full MBP-10 levels remain visible at causal lags, while
    price/flow/book dynamics are summarized over fixed recent windows.
    """
    day = str(case["clock"]["day"])
    raw_day = raw_days[day]
    t0 = int(case["clock"]["second_utc"])
    cutoff = t0 + checkpoint_s
    features: dict[str, float] = {}
    state_fields = [
        ("raw_mid", "mid", False),
        ("raw_spread_ticks", "spread_ticks", False),
        ("raw_book_imbalance", "book_imbalance", False),
        ("raw_book_imbalance_mean_within_second", "book_imbalance_mean", False),
        ("raw_bid_depth10", "bid_depth10", False),
        ("raw_ask_depth10", "ask_depth10", False),
        ("raw_last_trade", "last_trade", False),
        ("raw_mid_mean_within_second", "mid_mean", False),
        ("raw_mid_high_within_second", "mid_high", False),
        ("raw_mid_low_within_second", "mid_low", False),
        ("raw_spread_mean_within_second", "spread_mean", False),
        ("raw_spread_high_within_second", "spread_high", False),
        ("raw_spread_low_within_second", "spread_low", False),
        ("raw_trade_vwap_within_second", "trade_vwap", False),
        ("raw_trade_high_within_second", "trade_high", False),
        ("raw_trade_low_within_second", "trade_low", False),
        *[(f"raw_{name}", name, True) for name in raw_day.level_fields],
    ]
    core_summary_fields = {
        "mid", "spread_ticks", "book_imbalance", "book_imbalance_mean",
        "bid_depth10", "ask_depth10", "last_trade", "mid_mean", "mid_high",
        "mid_low", "spread_mean", "spread_high", "spread_low", "trade_vwap",
        "trade_high", "trade_low",
    }
    reference_second = t0 if checkpoint_s >= 0 else cutoff
    anchor_mid = raw_state_value(raw_days, day, reference_second, "mid")
    polarity = int(case["polarity"])
    confirmation = case.get("origin_confirmation_offset_s")
    if "origin_confirmation_offset_s" not in case:
        endpoint = case.get("endpoint_posthoc") or {}
        confirmation = None if endpoint.get("censored") else endpoint.get("causal_confirmation_offset_s")
    origin_confirmed = confirmation is not None and int(confirmation) <= checkpoint_s
    for name, field, level_field in state_fields:
        for lag in LIVE_STATE_LAGS_S:
            features[f"{name}__checkpoint_lag{lag}"] = raw_state_value(
                raw_days, day, cutoff - lag, field, level_field=level_field
            )
        if not level_field and field in core_summary_fields:
            for window in LIVE_SUMMARY_WINDOWS_S:
                values = [
                    raw_state_value(raw_days, day, second, field)
                    for second in range(cutoff - window + 1, cutoff + 1)
                ]
                for stat, value in series_stats(values).items():
                    features[f"{name}__checkpoint_w{window}_{stat}"] = value
    current_mid = raw_state_value(raw_days, day, cutoff, "mid")
    features["raw_mid_ticks_from_causal_reference__checkpoint"] = (
        (current_mid - anchor_mid) / TICK
        if math.isfinite(current_mid) and math.isfinite(anchor_mid)
        else float("nan")
    )
    features["raw_mid_oriented_ticks_from_t0__checkpoint"] = (
        polarity * (current_mid - anchor_mid) / TICK
        if origin_confirmed and math.isfinite(current_mid) and math.isfinite(anchor_mid)
        else float("nan")
    )
    count_fields = [
        ("raw_trade_volume", "trade_volume", None),
        ("raw_buy_volume", "buy_volume", None),
        ("raw_sell_volume", "sell_volume", None),
        ("raw_trade_count", "trade_count", None),
        ("raw_row_count", "raw_row_count", None),
        *[(f"raw_action_{action}_count", "", action) for action in RAW_ACTIONS],
    ]
    for name, field, action in count_fields:
        features[f"{name}__checkpoint"] = raw_count_value(raw_days, day, cutoff, field, action=action)
        for window in V3_FLOW_WINDOWS_S:
            values = [
                raw_count_value(raw_days, day, second, field, action=action)
                for second in range(cutoff - window + 1, cutoff + 1)
            ]
            features[f"{name}__checkpoint_w{window}_sum"] = float(np.sum(values))
    phase_start_offset = case.get("prior_start_offset_s") if checkpoint_s < 0 else 0
    features["causal_phase_elapsed_s"] = (
        float(checkpoint_s - int(phase_start_offset))
        if phase_start_offset is not None and int(phase_start_offset) <= checkpoint_s
        else float("nan")
    )
    features.update(live_market_features(case, checkpoint_s, raw_days))
    return features


def causal_features(case: dict[str, Any], checkpoint_s: int, raw_days: dict[str, RawCausalDay]) -> dict[str, float]:
    record = case["causal_record"]
    features: dict[str, float] = {}
    second = (int(case["clock"]["second_utc"]) + int(checkpoint_s)) % 86400
    market_clock = str(case["clock"].get("market_clock", "00:00:00"))
    hour, minute, sec = (int(part) for part in market_clock.split(":"))
    market_second = (hour * 3600 + minute * 60 + sec + int(checkpoint_s)) % 86400
    for prefix, cyc_second in (("utc", second), ("market", market_second)):
        angle = 2.0 * math.pi * cyc_second / 86400.0
        features[f"clock_{prefix}_sin"] = math.sin(angle)
        features[f"clock_{prefix}_cos"] = math.cos(angle)
    features.update(predecessor_features(case, checkpoint_s))
    origin_is_confirmed = (
        case["origin_confirmation_offset_s"] is not None and case["origin_confirmation_offset_s"] <= checkpoint_s
    )
    features["origin_polarity"] = float(case["polarity"]) if origin_is_confirmed else float("nan")
    features["origin_confirmation_offset_s"] = float(case["origin_confirmation_offset_s"]) if origin_is_confirmed else float("nan")
    origin_endpoint = case["roster_causal_fields"]["endpoint_posthoc"]
    features["origin_structural_onset_offset_s"] = finite_float(origin_endpoint.get("structural_onset_offset_s")) if origin_is_confirmed else float("nan")
    for family in ("A", "B", "C"):
        features[f"causal_pre_t0_family_{family}"] = (
            float(case.get("frozen_target_family") == family) if origin_is_confirmed else float("nan")
        )

    artifact_checkpoint_s = min(checkpoint_s, 60)
    artifact_available = artifact_checkpoint_s >= -60
    end_index = 60 + artifact_checkpoint_s if artifact_available else -1
    features["causal_artifact_available_by_checkpoint"] = float(artifact_available)
    features["causal_artifact_age_after_plus60_s"] = float(max(0, checkpoint_s - 60))
    for field in SERIES_FIELDS:
        raw = record.get(field)
        if not isinstance(raw, list) or len(raw) != 121:
            values = [float("nan")] * 121
        else:
            values = [finite_float(value) for value in raw]
        short = field.replace("_t_minus60_to_plus60", "")
        oriented_withheld = (
            not origin_is_confirmed
            and field == "dipole_roll20_oriented_t_minus60_to_plus60"
        )
        for lag in LIVE_STATE_LAGS_S:
            offset = artifact_checkpoint_s - lag
            features[f"{short}__checkpoint_lag{lag}"] = (
                values[offset + 60]
                if artifact_available and not oriented_withheld and offset >= -60
                else float("nan")
            )
        for window_s in LIVE_SUMMARY_WINDOWS_S:
            start_offset = max(-60, artifact_checkpoint_s - window_s + 1)
            window = (
                values[start_offset + 60 : end_index + 1]
                if artifact_available and not oriented_withheld
                else []
            )
            for stat, value in series_stats(window).items():
                features[f"{short}__checkpoint_w{window_s}_{stat}"] = value
        prefix_values = values[: end_index + 1] if artifact_available and not oriented_withheld else []
        for stat, value in series_stats(prefix_values).items():
            features[f"{short}__known_history_{stat}"] = value

    buy = record.get("aggressor_buy_volume_t_minus60_to_plus60")
    sell = record.get("aggressor_sell_volume_t_minus60_to_plus60")
    if artifact_available and isinstance(buy, list) and isinstance(sell, list) and len(buy) == len(sell) == 121:
        net_all = [finite_float(b) - finite_float(s) for b, s in zip(buy, sell)]
    else:
        net_all = [float("nan")] * 121
    for lag in LIVE_STATE_LAGS_S:
        offset = artifact_checkpoint_s - lag
        features[f"aggressor_net__checkpoint_lag{lag}"] = (
            net_all[offset + 60] if artifact_available and offset >= -60 else float("nan")
        )
    for window_s in LIVE_SUMMARY_WINDOWS_S:
        start_offset = max(-60, artifact_checkpoint_s - window_s + 1)
        window = net_all[start_offset + 60 : end_index + 1] if artifact_available else []
        for stat, value in series_stats(window).items():
            features[f"aggressor_net__checkpoint_w{window_s}_{stat}"] = value
    for stat, value in series_stats(net_all[: end_index + 1] if artifact_available else []).items():
        features[f"aggressor_net__known_history_{stat}"] = value

    mbo = record.get("mbo_t_minus60_to_plus60") or record.get("mbo_orderflow_t_minus60_to_plus60")
    features["mbo_available"] = float(isinstance(mbo, dict))
    for mbo_field in MBO_FIELDS:
        raw_values = mbo.get(mbo_field) if isinstance(mbo, dict) else None
        values = (
            [finite_float(value) for value in raw_values]
            if isinstance(raw_values, list) and len(raw_values) == 121
            else [float("nan")] * 121
        )
        for lag in LIVE_STATE_LAGS_S:
            offset = artifact_checkpoint_s - lag
            features[f"mbo_{mbo_field}__checkpoint_lag{lag}"] = (
                values[offset + 60] if artifact_available and offset >= -60 else float("nan")
            )
        for window_s in LIVE_SUMMARY_WINDOWS_S:
            start_offset = max(-60, artifact_checkpoint_s - window_s + 1)
            window = values[start_offset + 60 : end_index + 1] if artifact_available else []
            for stat, value in series_stats(window).items():
                features[f"mbo_{mbo_field}__checkpoint_w{window_s}_{stat}"] = value
        for stat, value in series_stats(values[: end_index + 1] if artifact_available else []).items():
            features[f"mbo_{mbo_field}__known_history_{stat}"] = value

    milestones = record.get("post_exhaustion") or record.get("post_exhaustion_dipole_only") or {}
    for name in ("t50_s", "t25_s", "t10_s", "zero_s"):
        observed_time = milestones.get(name) if isinstance(milestones, dict) else None
        observed_by_h = (
            origin_is_confirmed
            and observed_time is not None
            and int(observed_time) <= checkpoint_s
        )
        features[f"causal_milestone_{name}_observed_by_h"] = float(observed_by_h)
        features[f"causal_milestone_{name}_time_if_observed"] = float(observed_time) if observed_by_h else float("nan")
    features.update(raw_market_features(case, checkpoint_s, raw_days))
    return features


def matrix(
    cases: list[dict[str, Any]], checkpoint_s: int, raw_days: dict[str, RawCausalDay], feature_names: list[str] | None = None
) -> tuple[np.ndarray, list[str]]:
    if not cases:
        return np.empty((0, len(feature_names or [])), dtype=float), feature_names or []
    first = causal_features(cases[0], checkpoint_s, raw_days)
    if feature_names is None:
        feature_names = sorted(first)
    result = np.empty((len(cases), len(feature_names)), dtype=np.float32)
    result[0] = [first.get(name, float("nan")) for name in feature_names]
    for index, case in enumerate(cases[1:], start=1):
        row = causal_features(case, checkpoint_s, raw_days)
        result[index] = [row.get(name, float("nan")) for name in feature_names]
    return result, feature_names


def membership_features(candidate: dict[str, Any], checkpoint_s: int, raw_days: dict[str, RawCausalDay]) -> dict[str, float]:
    features = raw_market_features(candidate, checkpoint_s, raw_days)
    features.update(predecessor_features(candidate, checkpoint_s))
    decision_second = (int(candidate["clock"]["second_utc"]) + checkpoint_s) % 86400
    angle = 2.0 * math.pi * decision_second / 86400.0
    features["decision_clock_utc_sin"] = math.sin(angle)
    features["decision_clock_utc_cos"] = math.cos(angle)
    endpoint = candidate.get("endpoint_posthoc") or {}
    confirmation = None if endpoint.get("censored") else endpoint.get("causal_confirmation_offset_s")
    confirmed = confirmation is not None and int(confirmation) <= checkpoint_s
    features["origin_polarity"] = float(candidate["polarity"]) if confirmed else float("nan")
    for family in ("A", "B", "C"):
        features[f"causal_pre_t0_family_{family}"] = (
            float(candidate.get("causal_family") == family) if confirmed else float("nan")
        )
    features["origin_confirmation_offset_s"] = float(confirmation) if confirmed else float("nan")
    features["origin_structural_onset_offset_s"] = (
        finite_float(endpoint.get("structural_onset_offset_s")) if confirmed else float("nan")
    )
    pre = candidate.get("pre_roll20_oriented_t_minus60_to_t0")
    values = (
        [finite_float(value) for value in pre]
        if confirmed and isinstance(pre, list) and len(pre) == 61
        else [float("nan")] * 61
    )
    for offset, value in zip(range(-60, 1), values):
        features[f"candidate_pre_roll20_oriented__at_{offset:+d}"] = value
    return features


def membership_matrix(
    candidates: list[dict[str, Any]], checkpoint_s: int, raw_days: dict[str, RawCausalDay], feature_names: list[str] | None = None
) -> tuple[np.ndarray, list[str]]:
    if not candidates:
        return np.empty((0, len(feature_names or [])), dtype=np.float32), feature_names or []
    first = membership_features(candidates[0], checkpoint_s, raw_days)
    if feature_names is None:
        feature_names = sorted(first)
    result = np.empty((len(candidates), len(feature_names)), dtype=np.float32)
    result[0] = [first.get(name, float("nan")) for name in feature_names]
    for index, candidate in enumerate(candidates[1:], start=1):
        row = membership_features(candidate, checkpoint_s, raw_days)
        result[index] = [row.get(name, float("nan")) for name in feature_names]
    return result, feature_names


def model_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True, add_indicator=True)),
            ("scaler", StandardScaler()),
            ("logistic", LogisticRegression(C=0.01, solver="liblinear", max_iter=3000, random_state=1974)),
        ]
    )


def membership_prediction_pass(
    candidates: list[dict[str, Any]],
    raw_days: dict[str, RawCausalDay],
    checkpoints_to_run: Iterable[int],
    evaluation_candidate_ids: set[str] | None = None,
    residual_training_candidate_ids: set[str] | None = None,
    pass_name: str = "TARGET_A_MEMBERSHIP",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    days = sorted({row["clock"]["day"] for row in candidates})
    first_day = days[0]
    oot_ids = {row["candidate_id"] for row in candidates if row["clock"]["day"] != first_day}
    active_evaluation_ids = set(evaluation_candidate_ids) if evaluation_candidate_ids is not None else set(oot_ids)
    active_training_ids = (
        set(residual_training_candidate_ids)
        if residual_training_candidate_ids is not None
        else {row["candidate_id"] for row in candidates}
    )
    checkpoints_requested = tuple(checkpoints_to_run)
    by_candidate_id = {row["candidate_id"]: row for row in candidates}
    terminal_unresolved_ids: set[str] = set()
    checkpoint_results = []
    predictions: list[dict[str, Any]] = []
    for h in checkpoints_requested:
        if h >= 0:
            expired = {
                candidate_id
                for candidate_id in active_evaluation_ids
                if int(by_candidate_id[candidate_id].get("membership_h_end_offset_s", -1)) < h
            }
            active_evaluation_ids.difference_update(expired)
            active_training_ids.difference_update(expired)
            terminal_unresolved_ids.update(expired)
        if not active_evaluation_ids:
            break
        active_before = len(active_evaluation_ids)
        folds = []
        checkpoint_predictions = []

        def eligible_at_checkpoint(row: dict[str, Any]) -> bool:
            return (
                on_prior_checkpoint_grid(row.get("prior_start_offset_s"), h)
                if h < 0
                else 0 <= h <= int(row.get("membership_h_end_offset_s", -1))
            )

        feature_rows = [
            row
            for row in candidates
            if eligible_at_checkpoint(row)
            and (
                row["clock"]["day"] == first_day
                or row["candidate_id"] in active_training_ids
                or row["candidate_id"] in active_evaluation_ids
            )
        ]
        checkpoint_x, names = membership_matrix(feature_rows, h, raw_days)
        feature_index = {row["candidate_id"]: index for index, row in enumerate(feature_rows)}
        for test_day in days[1:]:
            train = [
                row
                for row in candidates
                if row["clock"]["day"] < test_day
                and eligible_at_checkpoint(row)
                and (
                    row["clock"]["day"] == first_day or row["candidate_id"] in active_training_ids
                )
            ]
            test = [
                row
                for row in candidates
                if row["clock"]["day"] == test_day
                and row["candidate_id"] in active_evaluation_ids
                and eligible_at_checkpoint(row)
            ]
            train_y = np.asarray([int(row["is_fixed_pox"]) for row in train], dtype=int)
            test_y = np.asarray([int(row["is_fixed_pox"]) for row in test], dtype=int)
            if not train or not test or len(np.unique(train_y)) < 2:
                folds.append(
                    {
                        "test_day": test_day,
                        "train_n": len(train),
                        "test_n": len(test),
                        "status": "INSUFFICIENT_TRAINING_CLASS_SUPPORT_OR_EMPTY_TEST",
                    }
                )
                continue
            train_x = checkpoint_x[[feature_index[row["candidate_id"]] for row in train]]
            test_x = checkpoint_x[[feature_index[row["candidate_id"]] for row in test]]
            pipeline = model_pipeline()
            pipeline.fit(train_x, train_y)
            probability = pipeline.predict_proba(test_x)[:, 1]
            train_base = float(np.mean(train_y))
            base = np.full(len(test_y), train_base, dtype=float)
            metrics = binary_metrics(test_y, probability, base)
            fold_positive = bool(
                metrics["n"] >= 50
                and metrics["auc"] is not None
                and metrics["auc"] > 0.5
                and metrics["brier_gain_vs_chronological_base"] > 0
                and metrics["log_loss_gain_vs_chronological_base"] > 0
            )
            folds.append(
                {
                    "test_day": test_day,
                    "train_days": sorted({row["clock"]["day"] for row in train}),
                    "train_n": len(train),
                    "test_n": len(test),
                    "feature_count": len(names),
                    "status": "SCORED",
                    "metrics": metrics,
                    "fold_positive_value": fold_positive,
                }
            )
            for row, actual, predicted in zip(test, test_y, probability):
                prediction = {
                    "candidate_id": row["candidate_id"],
                    "day": test_day,
                    "checkpoint_s": h,
                    "actual_is_fixed_pox": bool(actual),
                    "predicted_pox_probability": float(predicted),
                    "chronological_train_pox_rate": train_base,
                }
                checkpoint_predictions.append(prediction)
                predictions.append(prediction)
        confident_ids = {
            row["candidate_id"]
            for row in checkpoint_predictions
            if float(row["predicted_pox_probability"]) >= PRIMARY_SELECTIVE_CONFIDENCE
            or float(row["predicted_pox_probability"]) <= 1.0 - PRIMARY_SELECTIVE_CONFIDENCE
        }
        active_evaluation_ids.difference_update(confident_ids)
        active_training_ids.difference_update(confident_ids)
        scored = [fold for fold in folds if fold.get("status") == "SCORED"]
        if checkpoint_predictions:
            y = np.asarray([int(row["actual_is_fixed_pox"]) for row in checkpoint_predictions])
            p = np.asarray([row["predicted_pox_probability"] for row in checkpoint_predictions])
            base = np.asarray([row["chronological_train_pox_rate"] for row in checkpoint_predictions])
            metrics = binary_metrics(y, p, base)
            calibration = calibration_buckets(y, p)
            lift = confidence_lift(y, p)
        else:
            metrics, calibration, lift = {"n": 0}, [], {}
        stable = bool(
            len(scored) == len(days) - 1
            and all(fold["fold_positive_value"] for fold in scored)
            and metrics.get("auc") is not None
            and metrics["auc"] >= 0.55
        )
        checkpoint_results.append(
            {
                "checkpoint_s": h,
                "active_residual_before_checkpoint_n": active_before,
                "confident_first_calls_emitted_n": len(confident_ids),
                "active_residual_after_checkpoint_n": len(active_evaluation_ids),
                "evaluation_candidate_n": sum(fold.get("test_n", 0) for fold in folds),
                "chronological_folds": folds,
                "pooled_oot_metrics": metrics,
                "calibration_deciles": calibration,
                "top_confidence_lift": lift,
                "stable_chronological_oot_value": stable,
            }
        )
    stable_h = [row["checkpoint_s"] for row in checkpoint_results if row["stable_chronological_oot_value"]]
    return (
        {
            "status": f"{pass_name}_COMPLETE_NO_PROMOTION",
            "target": "fixed POX membership within the full frozen exhaustion-candidate roster",
            "candidate_universe_rows": len(candidates),
            "positive_rows": sum(row["is_fixed_pox"] for row in candidates),
            "control_rows": sum(not row["is_fixed_pox"] for row in candidates),
            "positive_identity_contract": "exact match to the fixed 3,429 ledger; controls never redefine positives",
            "information_policy": "maximally rich raw MBP-10 causal prefix from prior through H; target-specific origin attributes withheld until causal confirmation",
            "feature_layer_policy": FEATURE_LAYER_POLICY,
            "checkpoint_policy": "data-derived predecessor-to-birth prior window; H=0..5 then every 5 seconds until next event or authoritative tape end; confident calls are removed before the next checkpoint",
            "evaluation_population": "all OOT candidates" if evaluation_candidate_ids is None else "prebirth no-call residual candidates only",
            "checkpoints": checkpoint_results,
            "earliest_stable_checkpoint_s": min(stable_h) if stable_h else None,
            "unresolved_candidate_ids": sorted(active_evaluation_ids | terminal_unresolved_ids),
            "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
            "failure_policy": FAIL_POLICY,
        },
        predictions,
    )


def membership_cascade(
    candidates: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_id_h = {(row["candidate_id"], int(row["checkpoint_s"])): row for row in predictions}
    days = sorted({row["clock"]["day"] for row in candidates})
    oot = [row for row in candidates if row["clock"]["day"] in days[1:]]
    active = {row["candidate_id"] for row in oot}
    calls = []
    checkpoint_values = sorted({int(row["checkpoint_s"]) for row in predictions})
    for stage, checkpoints in (
        ("PREBIRTH", [h for h in checkpoint_values if h < 0]),
        ("H_FALLBACK", [h for h in checkpoint_values if h >= 0]),
    ):
        for h in checkpoints:
            for candidate in oot:
                candidate_id = candidate["candidate_id"]
                if candidate_id not in active:
                    continue
                prediction = by_id_h.get((candidate_id, h))
                if prediction is None:
                    continue
                probability = float(prediction["predicted_pox_probability"])
                if probability >= PRIMARY_SELECTIVE_CONFIDENCE:
                    predicted = True
                elif probability <= 1.0 - PRIMARY_SELECTIVE_CONFIDENCE:
                    predicted = False
                else:
                    continue
                calls.append(
                    {
                        "candidate_id": candidate_id,
                        "day": candidate["clock"]["day"],
                        "actual_is_fixed_pox": candidate["is_fixed_pox"],
                        "predicted_is_fixed_pox": predicted,
                        "predicted_pox_probability": probability,
                        "correct": predicted == candidate["is_fixed_pox"],
                        "first_call_stage": stage,
                        "first_call_checkpoint_s": h,
                    }
                )
                active.remove(candidate_id)
    calls_by_id = {row["candidate_id"]: row for row in calls}
    case_rows = []
    for candidate in candidates:
        base = {
            "candidate_id": candidate["candidate_id"],
            "day": candidate["clock"]["day"],
            "actual_is_fixed_pox": candidate["is_fixed_pox"],
        }
        if candidate["clock"]["day"] == days[0]:
            case_rows.append({**base, "cascade_status": "NO_PRIOR_CHRONOLOGICAL_TRAIN_BLOCK"})
        elif candidate["candidate_id"] in calls_by_id:
            case_rows.append({**base, "cascade_status": "FIRST_CALL_EMITTED", **calls_by_id[candidate["candidate_id"]]})
        else:
            case_rows.append(
                {
                    **base,
                    "cascade_status": "NO_CONFIDENT_CALL_BEFORE_NATURAL_TERMINAL",
                    "prior_start_offset_s": candidate.get("prior_start_offset_s"),
                    "membership_h_end_offset_s": candidate.get("membership_h_end_offset_s"),
                    "terminal_reason": "NEXT_EVENT_BIRTH_OR_AUTHORITATIVE_TAPE_END",
                }
            )

    def summarize(stage: str) -> dict[str, Any]:
        selected = [row for row in calls if row["first_call_stage"] == stage]
        positives = [row for row in selected if row["actual_is_fixed_pox"]]
        negative_controls = [row for row in selected if not row["actual_is_fixed_pox"]]
        return {
            "all_candidate_calls_n": len(selected),
            "accuracy": float(np.mean([row["correct"] for row in selected])) if selected else None,
            "fixed_pox_instances_called_n": len(positives),
            "fixed_pox_instances_correctly_called_positive_n": sum(row["predicted_is_fixed_pox"] for row in positives),
            "fixed_pox_instances_incorrectly_called_negative_n": sum(not row["predicted_is_fixed_pox"] for row in positives),
            "control_false_positive_n": sum(row["predicted_is_fixed_pox"] for row in negative_controls),
            "by_first_call_checkpoint": dict(sorted(Counter(row["first_call_checkpoint_s"] for row in selected).items())),
        }

    oot_positives = [row for row in oot if row["is_fixed_pox"]]
    called_positive_ids = {row["candidate_id"] for row in calls if row["actual_is_fixed_pox"]}
    return (
        {
            "status": "TARGET_A_PREBIRTH_FIRST_RESIDUAL_H_CASCADE_COMPLETE_NO_PROMOTION",
            "confidence_threshold": PRIMARY_SELECTIVE_CONFIDENCE,
            "oot_candidate_n": len(oot),
            "oot_fixed_pox_n": len(oot_positives),
            "prebirth": summarize("PREBIRTH"),
            "h_fallback_residual_only": summarize("H_FALLBACK"),
            "fixed_pox_unresolved_before_natural_terminal_n": sum(row["candidate_id"] not in called_positive_ids for row in oot_positives),
            "prebirth_calls_removed_before_h_regardless_of_correctness": True,
            "h_receives_full_oot_candidate_population_only_if_prebirth_calls_n_is_zero": True,
            "candidate_scope_limitation": "event-centered frozen exhaustion-candidate universe; not an every-second live alert claim",
            "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
            "failure_policy": FAIL_POLICY,
        },
        case_rows,
    )


def binary_metrics(y: np.ndarray, p: np.ndarray, base_p: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {"n": int(len(y)), "flip_rate": float(np.mean(y))}
    if not len(y):
        return result
    result.update(
        {
            "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            "brier": float(brier_score_loss(y, p)),
            "baseline_brier": float(brier_score_loss(y, base_p)),
            "brier_gain_vs_chronological_base": float(brier_score_loss(y, base_p) - brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "baseline_log_loss": float(log_loss(y, base_p, labels=[0, 1])),
            "log_loss_gain_vs_chronological_base": float(log_loss(y, base_p, labels=[0, 1]) - log_loss(y, p, labels=[0, 1])),
        }
    )
    predicted = p >= 0.5
    result["flip_error_rate"] = float(np.mean(~predicted[y == 1])) if np.any(y == 1) else None
    result["same_error_rate"] = float(np.mean(predicted[y == 0])) if np.any(y == 0) else None
    result["accuracy"] = float(np.mean(predicted == y))
    return result


def calibration_buckets(y: np.ndarray, p: np.ndarray) -> list[dict[str, Any]]:
    if not len(y):
        return []
    order = np.argsort(p)
    buckets = []
    for index, positions in enumerate(np.array_split(order, min(10, len(order))), start=1):
        if not len(positions):
            continue
        buckets.append(
            {
                "bucket_low_to_high": index,
                "n": int(len(positions)),
                "predicted_flip_mean": float(np.mean(p[positions])),
                "actual_flip_rate": float(np.mean(y[positions])),
                "min_probability": float(np.min(p[positions])),
                "max_probability": float(np.max(p[positions])),
            }
        )
    return buckets


def confidence_lift(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    if not len(y):
        return {}
    take = max(1, int(math.ceil(len(y) * 0.10)))
    order = np.argsort(p)
    low = order[:take]
    high = order[-take:]
    flip_base = float(np.mean(y))
    same_base = 1.0 - flip_base
    return {
        "fraction_each_tail": 0.10,
        "n_each_tail": take,
        "high_flip_actual_flip_rate": float(np.mean(y[high])),
        "high_flip_lift_vs_pooled_flip_base": float(np.mean(y[high]) - flip_base),
        "high_same_actual_same_rate": float(np.mean(1 - y[low])),
        "high_same_lift_vs_pooled_same_base": float(np.mean(1 - y[low]) - same_base),
    }


def load_and_join(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    ledger = read_jsonl(args.ledger)
    labels = Counter(row.get("branch_label") for row in ledger)
    ids = [row.get("case_id") for row in ledger]
    if len(ledger) != EXPECTED_TOTAL or len(set(ids)) != EXPECTED_TOTAL:
        raise RuntimeError(f"fixed-ledger population mismatch: rows={len(ledger)} unique={len(set(ids))}")
    if labels != Counter({"FLIP": EXPECTED_FLIP, "SAME": EXPECTED_SAME}):
        raise RuntimeError(f"fixed-ledger label mismatch: {dict(labels)}")
    if any(row.get("population_policy") != POLICY for row in ledger):
        raise RuntimeError("fixed-ledger population policy mismatch")

    reveal = read_json(args.reveal_records)
    blind = read_json(args.blind_records)
    reveal_by_key = {event_key(row["day"], row["t0_second_utc"], row["dipole_polarity"]): row for row in reveal}
    blind_by_key = {event_key(row["day"], row["t0_second_utc"], row["dipole_polarity"]): row for row in blind}
    if len(reveal_by_key) != len(reveal) or len(blind_by_key) != len(blind):
        raise RuntimeError("duplicate causal-source identity")
    if set(reveal_by_key) & set(blind_by_key):
        raise RuntimeError("reveal/blind causal-source overlap")

    roster_by_identity: dict[tuple[str, int], dict[str, Any]] = {}
    with open_text(args.roster) as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            roster_by_identity[(str(row["week_sunday"]), int(row["week_index"]))] = row
    fixed_ids = set(ids)
    roster_marked_ids = {
        f"{row['clock']['day']}-{int(row['clock']['second_utc']):05d}-{int(row['polarity']):+d}"
        for row in roster_by_identity.values()
        if row.get("frozen_target_match") is True
    }
    if roster_marked_ids != fixed_ids:
        raise RuntimeError(
            f"full roster positive identity mismatch: marked={len(roster_marked_ids)} fixed={len(fixed_ids)} "
            f"missing={len(fixed_ids-roster_marked_ids)} extra={len(roster_marked_ids-fixed_ids)}"
        )
    def causal_predecessor(row: dict[str, Any]) -> dict[str, Any] | None:
        week = str(row["week_sunday"])
        current_epoch = int(row["clock"]["epoch_utc"])
        for prior_index in range(int(row["week_index"]) - 1, -1, -1):
            prior = roster_by_identity.get((week, prior_index))
            if prior is None:
                continue
            endpoint = prior.get("endpoint_posthoc") or {}
            confirmation = None if endpoint.get("censored") else endpoint.get("causal_confirmation_offset_s")
            if confirmation is None:
                continue
            prior_t0_offset = int(prior["clock"]["epoch_utc"]) - current_epoch
            confirmation_offset = prior_t0_offset + int(confirmation)
            if confirmation_offset >= 0:
                continue
            return {
                "week_index": int(prior_index),
                "t0_offset_s": prior_t0_offset,
                "confirmation_offset_s": confirmation_offset,
                "polarity": int(prior["polarity"]),
                "family": prior.get("descriptors_posthoc", {}).get("family"),
                "structural_onset_offset_from_predecessor_t0_s": endpoint.get("structural_onset_offset_s"),
            }
        return None

    def next_event_offset(row: dict[str, Any]) -> int | None:
        successor = roster_by_identity.get((str(row["week_sunday"]), int(row["week_index"]) + 1))
        if successor is None:
            return None
        offset = int(successor["clock"]["epoch_utc"]) - int(row["clock"]["epoch_utc"])
        return offset if offset > 0 else None

    roster_candidates = []
    for row in sorted(
        roster_by_identity.values(),
        key=lambda item: (item["clock"]["day"], item["clock"]["second_utc"], item["polarity"]),
    ):
        predecessor = causal_predecessor(row)
        successor_offset = next_event_offset(row)
        roster_candidates.append(
            {
                "candidate_id": f"{row['clock']['day']}-{int(row['clock']['second_utc']):05d}-{int(row['polarity']):+d}",
                "clock": row["clock"],
                "polarity": int(row["polarity"]),
                "is_fixed_pox": bool(row.get("frozen_target_match") is True),
                "causal_family": row.get("descriptors_posthoc", {}).get("family"),
                "endpoint_posthoc": row.get("endpoint_posthoc", {}),
                "pre_roll20_oriented_t_minus60_to_t0": row.get("chain_membership_state", {}).get("pre_roll20_oriented_t_minus60_to_t0"),
                "source_roster_identity": {"week_sunday": row["week_sunday"], "week_index": row["week_index"]},
                "predecessor_causal_context": predecessor,
                "prior_start_offset_s": None if predecessor is None else int(predecessor["confirmation_offset_s"]),
                "next_event_t0_offset_s": successor_offset,
            }
        )
    candidate_context_by_id = {row["candidate_id"]: row for row in roster_candidates}

    joined: list[dict[str, Any]] = []
    counts = Counter()
    for ledger_row in ledger:
        key = event_key(ledger_row["clock"]["day"], ledger_row["clock"]["second_utc"], ledger_row["polarity"])
        if key in reveal_by_key:
            causal_record = reveal_by_key[key]
            causal_source = "reveal"
            source_id = causal_record["event_id"]
        elif key in blind_by_key:
            causal_record = blind_by_key[key]
            causal_source = "blind"
            source_id = causal_record["blind_id"]
        else:
            raise RuntimeError(f"missing causal source for {ledger_row['case_id']}")
        counts[causal_source] += 1

        src = ledger_row["source_roster_identity"]
        successor_key = (str(src["week_sunday"]), int(ledger_row["next_event_target"]["next_index"]))
        successor = roster_by_identity.get(successor_key)
        if successor is None:
            raise RuntimeError(f"missing successor roster row for {ledger_row['case_id']}")
        expected_same = int(successor["polarity"]) == int(ledger_row["polarity"])
        if expected_same != bool(ledger_row["next_event_target"]["same_polarity"]):
            raise RuntimeError(f"successor polarity mismatch for {ledger_row['case_id']}")

        origin_endpoint = ledger_row["roster_causal_fields"]["endpoint_posthoc"]
        successor_endpoint = successor["endpoint_posthoc"]
        origin_confirm = None if origin_endpoint.get("censored") else origin_endpoint.get("causal_confirmation_offset_s")
        successor_t0 = int(ledger_row["next_event_target"]["dt_s_posthoc"])
        successor_confirm = None if successor_endpoint.get("censored") else successor_endpoint.get("causal_confirmation_offset_s")
        branch_known = None if successor_confirm is None else successor_t0 + int(successor_confirm)

        array_state = {}
        for field in SERIES_FIELDS:
            values = causal_record.get(field)
            array_state[field] = {
                "length": len(values) if isinstance(values, list) else None,
                "finite_count": int(sum(math.isfinite(finite_float(value)) for value in values)) if isinstance(values, list) else 0,
            }
        joined.append(
            {
                **ledger_row,
                "causal_record": causal_record,
                "causal_source": causal_source,
                "causal_source_record_id": source_id,
                "causal_array_state": array_state,
                "origin_confirmation_offset_s": None if origin_confirm is None else int(origin_confirm),
                "successor_t0_offset_s": successor_t0,
                "successor_confirmation_offset_from_successor_t0_s": None if successor_confirm is None else int(successor_confirm),
                "branch_causally_known_offset_s": branch_known,
                "successor_polarity": int(successor["polarity"]),
                "successor_roster_identity": {"week_sunday": successor["week_sunday"], "week_index": successor["week_index"]},
                "predecessor_causal_context": candidate_context_by_id[ledger_row["case_id"]]["predecessor_causal_context"],
                "prior_start_offset_s": candidate_context_by_id[ledger_row["case_id"]]["prior_start_offset_s"],
            }
        )
    if len(joined) != EXPECTED_TOTAL or counts != Counter({"reveal": 1718, "blind": 1711}):
        raise RuntimeError(f"causal join mismatch: rows={len(joined)} counts={dict(counts)}")

    provenance = {
        "status": "FIXED_LEDGER_CAUSAL_JOIN_VALIDATED",
        "population_policy": POLICY,
        "rows": len(joined),
        "label_counts": dict(labels),
        "causal_source_counts": dict(counts),
        "inputs": {
            "fixed_ledger": {"name": args.ledger.name, "sha256": sha256(args.ledger)},
            "frozen_chain_state_roster": {"name": args.roster.name, "sha256": sha256(args.roster), "github_artifact_id": 9279235031},
            "reveal_records": {"name": args.reveal_records.name, "sha256": sha256(args.reveal_records), "github_artifact_id": 9273273233},
            "blind_records": {"name": args.blind_records.name, "sha256": sha256(args.blind_records), "github_artifact_id": 9274443976},
        },
        "join_key": ["day", "t0_second_utc", "dipole_polarity"],
        "membership_or_label_changes": 0,
        "prebirth_candidate_universe": {
            "definition": "all frozen exhaustion candidates in the full chain-state roster; membership target is frozen_target_match",
            "rows": len(roster_candidates),
            "positive_rows": sum(row["is_fixed_pox"] for row in roster_candidates),
            "control_rows": sum(not row["is_fixed_pox"] for row in roster_candidates),
            "fixed_positive_identity_match": True,
        },
    }
    return joined, roster_candidates, provenance


def public_enriched_row(case: dict[str, Any]) -> dict[str, Any]:
    epoch = int(case["clock"]["epoch_utc"])
    origin_confirm = case["origin_confirmation_offset_s"]
    successor_t0 = case["successor_t0_offset_s"]
    branch_known = case["branch_causally_known_offset_s"]
    return {
        "case_id": case["case_id"],
        "branch_label": case["branch_label"],
        "population_policy": POLICY,
        "frozen_target_split": case["frozen_target_split"],
        "frozen_target_family": case["frozen_target_family"],
        "polarity": case["polarity"],
        "clock": case["clock"],
        "source_roster_identity": case["source_roster_identity"],
        "successor_roster_identity": case["successor_roster_identity"],
        "causal_source": case["causal_source"],
        "causal_source_record_id": case["causal_source_record_id"],
        "causal_array_state": case["causal_array_state"],
        "origin_confirmation_offset_s": origin_confirm,
        "origin_confirmation_timestamp_utc": utc_at(epoch, origin_confirm),
        "origin_first_actionable_offset_s": None if origin_confirm is None else origin_confirm + 1,
        "origin_first_actionable_timestamp_utc": utc_at(epoch, None if origin_confirm is None else origin_confirm + 1),
        "successor_t0_offset_s": successor_t0,
        "successor_t0_timestamp_utc": utc_at(epoch, successor_t0),
        "successor_confirmation_offset_from_successor_t0_s": case["successor_confirmation_offset_from_successor_t0_s"],
        "branch_causally_known_offset_s": branch_known,
        "branch_causally_known_timestamp_utc": utc_at(epoch, branch_known),
        "branch_first_actionable_offset_s": None if branch_known is None else branch_known + 1,
        "branch_first_actionable_timestamp_utc": utc_at(epoch, None if branch_known is None else branch_known + 1),
        "successor_polarity": case["successor_polarity"],
        "computational_prediction_window": {
            "prior_start_offset_s": case.get("prior_start_offset_s"),
            "h_start_rule": "H0_GRID; RAW_LIVE_STATE_AVAILABLE_AT_BIRTH; TARGET_SPECIFIC_FIELDS_REQUIRE_CAUSAL_CONFIRMATION",
            "h_end_offset_s": case.get("branch_h_end_offset_s"),
            "terminal_rule": "SECOND_BEFORE_BRANCH_CAUSALLY_KNOWN_OR_AUTHORITATIVE_TAPE_END",
        },
        "raw_tape_execution_status": "PENDING_DEDICATED_EXACT_EXECUTION_STAGE; AUTHORITATIVE_RAW_CAUSAL_TAPE_JOINED",
    }


def knowability(joined: list[dict[str, Any]]) -> dict[str, Any]:
    def group_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n": len(rows),
            "origin_confirmation_offset_s": percentile_summary(row["origin_confirmation_offset_s"] for row in rows),
            "successor_t0_offset_s": percentile_summary(row["successor_t0_offset_s"] for row in rows),
            "branch_causally_known_offset_s": percentile_summary(row["branch_causally_known_offset_s"] for row in rows),
            "branch_known_minus_parent_plus60_s": percentile_summary(
                None if row["branch_causally_known_offset_s"] is None else row["branch_causally_known_offset_s"] - 60 for row in rows
            ),
            "branch_known_by_parent_plus60_count": sum(
                row["branch_causally_known_offset_s"] is not None and row["branch_causally_known_offset_s"] + 1 <= 60 for row in rows
            ),
        }

    by_label = {label: group_payload([row for row in joined if row["branch_label"] == label]) for label in ("FLIP", "SAME")}
    by_day = {day: group_payload([row for row in joined if row["clock"]["day"] == day]) for day in sorted({row["clock"]["day"] for row in joined})}
    return {
        "status": "OBSERVATIONAL_BRANCH_KNOWABILITY_MEASURED",
        "population_policy": POLICY,
        "definition": "observation bin is origin t0 plus successor_t0_offset_s plus successor causal_confirmation_offset_s; first actionable timestamp is the next second boundary",
        "anti_backdating": "successor structural onset and retrospectively identified successor t0 are not treated as branch knowledge",
        "overall": group_payload(joined),
        "by_branch_label": by_label,
        "by_day": by_day,
        "computational_window_policy": {
            "prior_start": "last predecessor causal confirmation before birth",
            "h_start": 0,
            "h_cadence": "0,1,2,3,4,5 then every 5 seconds",
            "h_end": "second before branch causal confirmation or authoritative tape end",
            "fixed_horizon_used": False,
        },
    }


def stage2(
    joined: list[dict[str, Any]],
    raw_days: dict[str, RawCausalDay],
    checkpoints_to_run: Iterable[int],
    evaluation_case_ids: set[str] | None = None,
    residual_training_case_ids: set[str] | None = None,
    pass_name: str = "STAGE2",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    days = sorted({row["clock"]["day"] for row in joined})
    all_predictions: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    warnings.filterwarnings("ignore", category=ConvergenceWarning)

    checkpoints_requested = tuple(checkpoints_to_run)
    first_day = days[0]
    oot_ids = {row["case_id"] for row in joined if row["clock"]["day"] != first_day}
    active_evaluation_ids = set(evaluation_case_ids) if evaluation_case_ids is not None else set(oot_ids)
    active_training_ids = (
        set(residual_training_case_ids)
        if residual_training_case_ids is not None
        else {row["case_id"] for row in joined}
    )
    by_case_id = {row["case_id"]: row for row in joined}
    terminal_unresolved_ids: set[str] = set()
    for h in checkpoints_requested:
        if h >= 0:
            expired = {
                case_id
                for case_id in active_evaluation_ids
                if int(by_case_id[case_id].get("branch_h_end_offset_s", -1)) < h
            }
            active_evaluation_ids.difference_update(expired)
            active_training_ids.difference_update(expired)
            terminal_unresolved_ids.update(expired)
        if not active_evaluation_ids:
            break
        active_before = len(active_evaluation_ids)
        eligible = [
            row
            for row in joined
            if (
                on_prior_checkpoint_grid(row.get("prior_start_offset_s"), h)
                if h < 0
                else h <= int(row.get("branch_h_end_offset_s", -1))
            )
        ]
        feature_rows = [
            row
            for row in eligible
            if (
                row["clock"]["day"] == first_day
                or row["case_id"] in active_training_ids
                or row["case_id"] in active_evaluation_ids
            )
        ]
        eligible_active_oot_before = sum(
            row["case_id"] in active_evaluation_ids for row in eligible
        )
        checkpoint_x, names = matrix(feature_rows, h, raw_days)
        feature_index = {row["case_id"]: index for index, row in enumerate(feature_rows)}
        fold_results = []
        checkpoint_predictions = []
        for test_day in days[1:]:
            train = [
                row
                for row in eligible
                if row["clock"]["day"] < test_day
                and (
                    row["clock"]["day"] == first_day or row["case_id"] in active_training_ids
                )
            ]
            test = [
                row
                for row in eligible
                if row["clock"]["day"] == test_day
                and row["case_id"] in active_evaluation_ids
            ]
            train_y = np.asarray([1 if row["branch_label"] == "FLIP" else 0 for row in train], dtype=int)
            test_y = np.asarray([1 if row["branch_label"] == "FLIP" else 0 for row in test], dtype=int)
            if not train or not test or len(np.unique(train_y)) < 2:
                fold_results.append(
                    {
                        "test_day": test_day,
                        "train_days": sorted({row["clock"]["day"] for row in train}),
                        "train_n": len(train),
                        "test_n": len(test),
                        "status": "INSUFFICIENT_TRAINING_CLASS_SUPPORT_OR_EMPTY_TEST",
                    }
                )
                continue
            train_x = checkpoint_x[[feature_index[row["case_id"]] for row in train]]
            test_x = checkpoint_x[[feature_index[row["case_id"]] for row in test]]
            pipeline = model_pipeline()
            pipeline.fit(train_x, train_y)
            probability = pipeline.predict_proba(test_x)[:, 1]
            train_base = float(np.mean(train_y))
            base = np.full(len(test_y), train_base, dtype=float)
            metrics = binary_metrics(test_y, probability, base)
            fold_stable = bool(
                metrics["n"] >= 50
                and metrics["auc"] is not None
                and metrics["auc"] > 0.5
                and metrics["brier_gain_vs_chronological_base"] > 0
                and metrics["log_loss_gain_vs_chronological_base"] > 0
            )
            fold_results.append(
                {
                    "test_day": test_day,
                    "train_days": sorted({row["clock"]["day"] for row in train}),
                    "train_n": len(train),
                    "train_flip_rate_chronological_base": train_base,
                    "test_n": len(test),
                    "feature_count": len(names),
                    "status": "SCORED",
                    "metrics": metrics,
                    "fold_positive_value": fold_stable,
                }
            )
            for row, actual, predicted in zip(test, test_y, probability):
                pred_row = {
                    "case_id": row["case_id"],
                    "day": test_day,
                    "checkpoint_s": h,
                    "actual_branch_label": "FLIP" if actual == 1 else "SAME",
                    "predicted_flip_probability": float(predicted),
                    "chronological_train_flip_rate": train_base,
                    "origin_confirmation_offset_s": row["origin_confirmation_offset_s"],
                    "branch_causally_known_offset_s": row["branch_causally_known_offset_s"],
                    "prediction_state": "PREBIRTH_CONDITIONAL_WINDOW" if h < 0 else "PREDICTION_WINDOW",
                }
                checkpoint_predictions.append(pred_row)
                all_predictions.append(pred_row)

        confident_ids = {
            row["case_id"]
            for row in checkpoint_predictions
            if float(row["predicted_flip_probability"]) >= PRIMARY_SELECTIVE_CONFIDENCE
            or float(row["predicted_flip_probability"]) <= 1.0 - PRIMARY_SELECTIVE_CONFIDENCE
        }
        active_evaluation_ids.difference_update(confident_ids)
        active_training_ids.difference_update(confident_ids)

        scored_folds = [fold for fold in fold_results if fold.get("status") == "SCORED"]
        if checkpoint_predictions:
            pooled_y = np.asarray([1 if row["actual_branch_label"] == "FLIP" else 0 for row in checkpoint_predictions], dtype=int)
            pooled_p = np.asarray([row["predicted_flip_probability"] for row in checkpoint_predictions], dtype=float)
            pooled_base = np.asarray([row["chronological_train_flip_rate"] for row in checkpoint_predictions], dtype=float)
            pooled_metrics = binary_metrics(pooled_y, pooled_p, pooled_base)
            calibration = calibration_buckets(pooled_y, pooled_p)
            lift = confidence_lift(pooled_y, pooled_p)
        else:
            pooled_metrics, calibration, lift = {"n": 0}, [], {}
        stable = bool(
            len(scored_folds) == len(days) - 1
            and all(fold["fold_positive_value"] for fold in scored_folds)
            and pooled_metrics.get("auc") is not None
            and pooled_metrics["auc"] >= 0.55
        )
        strong_for_management = bool(
            stable
            and pooled_metrics["auc"] >= 0.60
            and lift.get("high_flip_lift_vs_pooled_flip_base", -1) >= 0.05
            and lift.get("high_same_lift_vs_pooled_same_base", -1) >= 0.05
        )
        checkpoints.append(
            {
                "checkpoint_s": h,
                "active_residual_before_checkpoint_n": active_before,
                "confident_first_calls_emitted_n": len(confident_ids),
                "active_residual_after_checkpoint_n": len(active_evaluation_ids),
                "eligible_prediction_window_n": len(eligible),
                "eligible_active_oot_residual_before_checkpoint_n": eligible_active_oot_before,
                "eligible_flip": sum(row["branch_label"] == "FLIP" for row in eligible),
                "eligible_same": sum(row["branch_label"] == "SAME" for row in eligible),
                "eligible_flip_rate": float(np.mean([row["branch_label"] == "FLIP" for row in eligible])) if eligible else None,
                "chronological_folds": fold_results,
                "pooled_oot_metrics": pooled_metrics,
                "calibration_deciles": calibration,
                "top_confidence_lift": lift,
                "stable_chronological_oot_value": stable,
                "strong_enough_to_alter_management_research_gate": strong_for_management,
            }
        )

    stable_checkpoints = [row["checkpoint_s"] for row in checkpoints if row["stable_chronological_oot_value"]]
    stable_prebirth = [h for h in stable_checkpoints if h < 0]
    management_checkpoints = [row["checkpoint_s"] for row in checkpoints if row["strong_enough_to_alter_management_research_gate"]]
    result = {
        "status": f"{pass_name}_COMPLETE_STANDALONE_NO_PROMOTION",
        "population_policy": POLICY,
        "target": "authoritative future FLIP vs SAME label",
        "feature_policy": {
            "layering": FEATURE_LAYER_POLICY,
            "allowed": "V3-equivalent continuous target-agnostic live price direction/velocity/range, dense price and roll20 dipole paths, signed-flow windows, book lags/changes/path and clock; known predecessor state; causal detector/book/flow/MBO history through its supplied +60 span; complete MBP-10 level-0..9 state, trades and volume through the completed checkpoint",
            "excluded": [
                "branch_label",
                "next_event_target",
                "frozen_target_split",
                "reveal price path",
                "posthoc family/state assignments",
                "successor identity/polarity/timing",
                "D0-D5 results",
            ],
            "eligibility": "prior begins at each case's last causally confirmed predecessor; H begins at birth H0 and ends immediately before successor confirmation or authoritative tape end",
            "raw_price_cutoff": "raw events in seconds <= t0+H only; first executable quote is at or after t0+H+1",
            "target_specific_anti_leakage": "origin polarity, family, confirmation timing, structural onset, and polarity-oriented series are withheld until origin causal confirmation; at H0 and later, raw unoriented live market state is available immediately",
        },
        "validation": {
            "method": "expanding-window chronological OOT by day",
            "days": days,
            "folds": [f"train days before {day}; test {day}" for day in days[1:]],
            "model": "fixed strongly regularized L2 logistic regression, C=0.01, median imputation and standardization fit within each fold",
            "no_model_or_threshold_selection_on_test_days": True,
            "stable_value_gate_predeclared_here": "all three day folds scored with n>=50, AUC>0.5, positive Brier gain, positive log-loss gain; pooled AUC>=0.55",
            "management_gate_predeclared_here": "stable-value gate plus pooled AUC>=0.60 and >=0.05 lift in each 10% confidence tail",
            "limitations": "only four historical days; research diagnostics, never a promotion gate",
            "evaluation_population": "all chronological OOT fixed cases" if evaluation_case_ids is None else "no-call residual cases only",
            "training_population": "all earlier fixed cases" if residual_training_case_ids is None else "first historical day plus earlier chronological prebirth no-call residual cases",
        },
        "checkpoints": checkpoints,
        "earliest_stable_chronological_oot_checkpoint_s": min(stable_checkpoints) if stable_checkpoints else None,
        "earliest_stable_prebirth_checkpoint_s": min(stable_prebirth) if stable_prebirth else None,
        "earliest_management_gate_checkpoint_s": min(management_checkpoints) if management_checkpoints else None,
        "unresolved_case_ids": sorted(active_evaluation_ids | terminal_unresolved_ids),
        "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
        "failure_policy": FAIL_POLICY,
    }
    return result, all_predictions


def selective_cascade(
    joined: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply each OOT prediction once, prebirth first and H only to no-call residuals."""
    by_case_h = {(row["case_id"], int(row["checkpoint_s"])): row for row in predictions}
    days = sorted({row["clock"]["day"] for row in joined})
    oot_cases = [row for row in joined if row["clock"]["day"] in days[1:]]
    checkpoint_values = sorted({int(row["checkpoint_s"]) for row in predictions})
    prebirth_h = [h for h in checkpoint_values if h < 0]
    fallback_h = [h for h in checkpoint_values if h >= 0]
    sensitivity = []
    primary_rows: list[dict[str, Any]] = []

    for confidence in SELECTIVE_CONFIDENCE_THRESHOLDS:
        active = {row["case_id"] for row in oot_cases}
        calls: list[dict[str, Any]] = []
        for stage, checkpoints in (("PREBIRTH", prebirth_h), ("H_FALLBACK", fallback_h)):
            for h in checkpoints:
                for case in oot_cases:
                    case_id = case["case_id"]
                    if case_id not in active:
                        continue
                    prediction = by_case_h.get((case_id, h))
                    if prediction is None:
                        continue
                    probability = float(prediction["predicted_flip_probability"])
                    if probability >= confidence:
                        predicted = "FLIP"
                    elif probability <= 1.0 - confidence:
                        predicted = "SAME"
                    else:
                        continue
                    call = {
                        "case_id": case_id,
                        "day": case["clock"]["day"],
                        "actual_branch_label": case["branch_label"],
                        "predicted_branch_label": predicted,
                        "predicted_flip_probability": probability,
                        "correct": predicted == case["branch_label"],
                        "first_call_stage": stage,
                        "first_call_checkpoint_s": h,
                        "confidence_threshold": confidence,
                        "origin_confirmation_offset_s": case["origin_confirmation_offset_s"],
                        "branch_causally_known_offset_s": case["branch_causally_known_offset_s"],
                    }
                    calls.append(call)
                    active.remove(case_id)

        called_ids = {row["case_id"] for row in calls}
        prebirth_calls = [row for row in calls if row["first_call_stage"] == "PREBIRTH"]
        fallback_calls = [row for row in calls if row["first_call_stage"] == "H_FALLBACK"]
        unresolved = [row for row in oot_cases if row["case_id"] not in called_ids]

        def call_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
            by_h = {}
            for h in checkpoint_values:
                selected = [row for row in rows if row["first_call_checkpoint_s"] == h]
                if not selected:
                    continue
                by_h[str(h)] = {
                    "n": len(selected),
                    "accuracy": float(np.mean([row["correct"] for row in selected])),
                    "flip_error_n": sum(
                        row["actual_branch_label"] == "FLIP" and row["predicted_branch_label"] != "FLIP" for row in selected
                    ),
                    "same_error_n": sum(
                        row["actual_branch_label"] == "SAME" and row["predicted_branch_label"] != "SAME" for row in selected
                    ),
                }
            return {
                "n": len(rows),
                "coverage_of_oot_cases": len(rows) / len(oot_cases) if oot_cases else None,
                "accuracy": float(np.mean([row["correct"] for row in rows])) if rows else None,
                "correct_n": sum(row["correct"] for row in rows),
                "incorrect_n": sum(not row["correct"] for row in rows),
                "by_first_call_checkpoint": by_h,
            }

        result = {
            "confidence_threshold": confidence,
            "probability_call_rule": f"FLIP if p>={confidence:.2f}; SAME if p<={1.0-confidence:.2f}; otherwise no call",
            "oot_cases": len(oot_cases),
            "prebirth": call_summary(prebirth_calls),
            "h_fallback_residual_only": call_summary(fallback_calls),
            "all_calls": call_summary(calls),
            "unresolved_n": len(unresolved),
            "unresolved_fraction": len(unresolved) / len(oot_cases) if oot_cases else None,
            "prebirth_calls_removed_before_h_regardless_of_correctness": True,
        }
        sensitivity.append(result)
        if abs(confidence - PRIMARY_SELECTIVE_CONFIDENCE) < 1e-12:
            primary_by_id = {row["case_id"]: row for row in calls}
            for case in joined:
                base = {
                    "case_id": case["case_id"],
                    "day": case["clock"]["day"],
                    "actual_branch_label": case["branch_label"],
                    "primary_confidence_threshold": PRIMARY_SELECTIVE_CONFIDENCE,
                }
                if case["clock"]["day"] == days[0]:
                    primary_rows.append({**base, "cascade_status": "NO_PRIOR_CHRONOLOGICAL_TRAIN_BLOCK"})
                elif case["case_id"] in primary_by_id:
                    primary_rows.append({**base, "cascade_status": "FIRST_CALL_EMITTED", **primary_by_id[case["case_id"]]})
                else:
                    known = case["branch_causally_known_offset_s"]
                    primary_rows.append(
                        {
                            **base,
                            "cascade_status": "NO_CONFIDENT_CALL_BEFORE_NATURAL_TERMINAL",
                            "prior_start_offset_s": case.get("prior_start_offset_s"),
                            "branch_h_end_offset_s": case.get("branch_h_end_offset_s"),
                            "branch_causally_known_offset_s": known,
                            "terminal_reason": (
                                "BRANCH_CAUSALLY_KNOWN" if known is not None else "AUTHORITATIVE_TAPE_END"
                            ),
                        }
                    )
    primary = next(row for row in sensitivity if abs(row["confidence_threshold"] - PRIMARY_SELECTIVE_CONFIDENCE) < 1e-12)
    return (
        {
            "status": "PREBIRTH_FIRST_RESIDUAL_H_CASCADE_COMPLETE_NO_PROMOTION",
            "population_policy": POLICY,
            "objective": "call every fixed case before birth when confidence permits; run H only on cases receiving no prebirth call",
            "checkpoint_order": {
                "prebirth": prebirth_h,
                "h_fallback": fallback_h,
                "policy": "prior starts at each predecessor confirmation; H=0..5 then every 5 seconds until each case's causal terminal",
            },
            "anti_retry_rule": "all emitted prebirth calls, including errors, are removed from H; outcomes never decide eligibility for a retry",
            "probability_source": "chronological OOT predictions only",
            "primary_confidence_threshold": PRIMARY_SELECTIVE_CONFIDENCE,
            "primary_result": primary,
            "confidence_sensitivity": sensitivity,
            "first_day_without_prior_training_n": sum(row["clock"]["day"] == days[0] for row in joined),
            "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
            "failure_policy": FAIL_POLICY,
        },
        primary_rows,
    )


def blockers() -> dict[str, Any]:
    return {
        "status": "CAUSAL_PASS_COMPLETE_EXACT_ECONOMICS_DELEGATED_TO_DEDICATED_RUNNER",
        "population_policy": POLICY,
        "target_a_membership_classifier": {
            "status": "BLOCKED_MISSING_CONTROL_UNIVERSE",
            "reason": "the fixed ledger supplies positives only; no honest separately supplied candidate/control universe is available",
            "fabricated_negatives": 0,
        },
        "stage1_initial_continuation_execution": {
            "status": "DELEGATED_TO_NG_EXHAUSTION_POX_RAW_EXECUTION_20260819",
            "reason": "exact quote-side fills and economics are produced by the dedicated raw execution runner after this causal pass",
            "approximate_chart_or_derived_curve_used_as_execution": False,
        },
        "stage3_successor_reset_action_economics": {
            "status": "DELEGATED_TO_NG_EXHAUSTION_POX_RAW_EXECUTION_20260819",
            "timing_analysis_status": "COMPLETED_SEPARATELY",
        },
        "stage4_delayed_same_watch_reentry_economics": {
            "status": "DELEGATED_TO_NG_EXHAUSTION_POX_RAW_EXECUTION_20260819",
            "automatic_reentry_authorized": False,
        },
        "required_raw_tape_contract": {
            "coverage": "all fixed case t0 windows through all required parent/successor/delayed horizons",
            "execution": "first eligible raw trade/quote at or after exact signal timestamp",
            "must_preserve": "non-executable rows, gaps, losses, zero and choppy cases",
        },
    }


def failed_conditional(stage2_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "rule_id": "TARGET_A_MEMBERSHIP_CLASSIFIER",
            "status": "COMPLETED_EVENT_CENTERED_FROZEN_EXHAUSTION_CANDIDATE_UNIVERSE_NO_PROMOTION",
            "disposition": FAIL_POLICY,
            "promotion": False,
        },
        {
            "rule_id": "GENERIC_IMMEDIATE_POX_EXECUTION",
            "status": "DELEGATED_TO_DEDICATED_EXACT_RAW_EXECUTION_STAGE",
            "disposition": FAIL_POLICY,
            "promotion": False,
        },
        {
            "rule_id": "UNIVERSAL_SUCCESSOR_CONFIRMATION_EXIT_OR_REVERSAL",
            "status": "DELEGATED_TO_DEDICATED_EXACT_RAW_EXECUTION_STAGE",
            "disposition": FAIL_POLICY,
            "promotion": False,
        },
        {
            "rule_id": "AUTOMATIC_DELAYED_SAME_REENTRY",
            "status": "REJECTED_BY_PROTOCOL_WITHOUT_LATER_TRUSTED_CAUSAL_SETUP",
            "disposition": FAIL_POLICY,
            "promotion": False,
        },
    ]
    for checkpoint in stage2_result["checkpoints"]:
        rows.append(
            {
                "rule_id": f"STAGE2_FLIP_SAME_AT_H{checkpoint['checkpoint_s']}",
                "status": "PASSED_RESEARCH_GATE" if checkpoint["stable_chronological_oot_value"] else "FAILED_OR_UNAVAILABLE_STABLE_OOT_GATE",
                "strong_enough_to_alter_management": checkpoint["strong_enough_to_alter_management_research_gate"],
                "disposition": FAIL_POLICY,
                "promotion": False,
            }
        )
    return rows


def summary_markdown(provenance: dict[str, Any], timing: dict[str, Any], stage2_result: dict[str, Any], blocker_payload: dict[str, Any]) -> str:
    overall = timing["overall"]
    earliest = stage2_result["earliest_stable_chronological_oot_checkpoint_s"]
    management = stage2_result["earliest_management_gate_checkpoint_s"]
    cascade = stage2_result["cascade"]["primary_result"]
    known60 = overall["branch_known_by_parent_plus60_count"]
    return f"""# NG exhaustion focused POX standalone results — 2026-08-19

Status: **STANDALONE CAUSAL JOIN, PREBIRTH-FIRST PREDICTION, AND KNOWABILITY COMPLETE; EXACT ECONOMICS DELEGATED TO THE RAW RUNNER**

## Fixed population

- Population policy: `{POLICY}`
- Cases: {provenance['rows']:,}
- FLIP / SAME: {provenance['label_counts']['FLIP']:,} / {provenance['label_counts']['SAME']:,}
- Fixed-ledger SHA-256: `{provenance['inputs']['fixed_ledger']['sha256']}`
- Causal join: {provenance['causal_source_counts']['reveal']:,} reveal + {provenance['causal_source_counts']['blind']:,} blind; zero missing, overlap, membership changes, or label changes.

## Stage 2 — causal FLIP/SAME prediction

- Primary design: prebirth first; H is run only on the no-call residual cohort.
- Prebirth OOT calls at the fixed 0.75 confidence threshold: {cascade['prebirth']['n']:,} / {cascade['oot_cases']:,}; accuracy {cascade['prebirth']['accuracy']}.
- Cases handed to H after removing every prebirth call, including errors: {stage2_result['h_input_residual_n']:,}.
- Residual H calls: {cascade['h_fallback_residual_only']['n']:,}; unresolved at each case's causal terminal: {cascade['unresolved_n']:,}.
- Earliest checkpoint passing the predeclared stable chronological OOT research gate: `{earliest}` seconds.
- Earliest checkpoint passing the stricter management-alteration research gate: `{management}` seconds.
- These are four-day expanding-window historical diagnostics only. No play is promoted; fresh prospective/OOT validation remains required.

## Stage 3 — observational knowability

- Branch knowledge is dated at successor frozen-detector causal confirmation, never at retrospective onset or successor t0.
- Median successor t0 offset: {overall['successor_t0_offset_s']['median']:.1f} seconds.
- Median branch causal-knowledge offset: {overall['branch_causally_known_offset_s']['median']:.1f} seconds.
- Branch causally known by the parent +60 boundary: {known60:,} / {overall['n']:,} cases.

## Dedicated exact-execution stage

- Target A membership classifier: `{blocker_payload['target_a_membership_classifier']['status']}`.
- Stage 1 exact initial-continuation economics: `{blocker_payload['stage1_initial_continuation_execution']['status']}`.
- Stage 3 action economics and Stage 4 delayed-SAME re-entry economics are produced by the same dedicated exact raw-tape runner.
- No chart reconstruction or derived one-second curve was substituted for exact execution.

## Contamination and promotion boundary

- Independent D0-D5 result artifacts were not used.
- D0-D5 incremental crosswalk remains explicitly deferred until this standalone POX pass is frozen.
- All failed and conditional rules remain under `{FAIL_POLICY}`.
"""


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    joined, roster_candidates, provenance = load_and_join(args)
    fixed_event_days = sorted({row["clock"]["day"] for row in joined})
    required_days = sorted({row["clock"]["day"] for row in roster_candidates})
    raw_days, raw_provenance = load_raw_causal_days(args.raw_dir, required_days)
    attach_computational_windows(joined, roster_candidates, raw_days)
    provenance["raw_causal_inputs"] = raw_provenance
    provenance["fixed_event_days"] = fixed_event_days
    provenance["raw_candidate_days"] = required_days
    provenance["raw_context_days"] = sorted(set(raw_days) - set(required_days))
    provenance["raw_causal_cutoff"] = "end of completed checkpoint second H; no event from second H+1 or later"
    provenance["v3_live_market_policy"] = V3_LIVE_MARKET_POLICY
    provenance["feature_layer_policy"] = FEATURE_LAYER_POLICY
    provenance["fixed_prediction_horizon_used"] = False
    enriched_rows = [public_enriched_row(row) for row in joined]
    timing = knowability(joined)
    membership_prebirth_checkpoints = prior_checkpoint_grid(row.get("prior_start_offset_s") for row in roster_candidates)
    branch_prebirth_checkpoints = prior_checkpoint_grid(row.get("prior_start_offset_s") for row in joined)
    membership_fallback_checkpoints = h_checkpoint_grid(
        max((int(row.get("membership_h_end_offset_s", -1)) for row in roster_candidates), default=-1)
    )
    branch_fallback_checkpoints = h_checkpoint_grid(
        max((int(row.get("branch_h_end_offset_s", -1)) for row in joined), default=-1)
    )
    membership_prebirth, membership_prebirth_predictions = membership_prediction_pass(
        roster_candidates,
        raw_days,
        membership_prebirth_checkpoints,
        pass_name="TARGET_A_PREBIRTH_MEMBERSHIP",
    )
    _, membership_prebirth_rows = membership_cascade(roster_candidates, membership_prebirth_predictions)
    membership_residual_ids = {
        row["candidate_id"]
        for row in membership_prebirth_rows
        if row["cascade_status"] == "NO_CONFIDENT_CALL_BEFORE_NATURAL_TERMINAL"
    }
    membership_h, membership_h_predictions = membership_prediction_pass(
        roster_candidates,
        raw_days,
        membership_fallback_checkpoints,
        evaluation_candidate_ids=membership_residual_ids,
        residual_training_candidate_ids=membership_residual_ids,
        pass_name="TARGET_A_H_FALLBACK_RESIDUAL_ONLY",
    )
    membership_predictions = membership_prebirth_predictions + membership_h_predictions
    membership_cascade_result, membership_case_rows = membership_cascade(roster_candidates, membership_predictions)
    target_a_result = {
        "status": "TARGET_A_PREBIRTH_FIRST_RESIDUAL_H_COMPLETE_NO_PROMOTION",
        "population_policy": POLICY,
        "prebirth_pass": membership_prebirth,
        "h_fallback_residual_only_pass": membership_h,
        "cascade": membership_cascade_result,
        "h_input_residual_candidate_n": len(membership_residual_ids),
        "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
        "failure_policy": FAIL_POLICY,
    }
    prebirth_result, prebirth_predictions = stage2(
        joined,
        raw_days,
        branch_prebirth_checkpoints,
        pass_name="STAGE2_PREBIRTH_BRANCH",
    )
    prebirth_cascade, prebirth_case_rows = selective_cascade(joined, prebirth_predictions)
    residual_case_ids = {
        row["case_id"]
        for row in prebirth_case_rows
        if row["cascade_status"] == "NO_CONFIDENT_CALL_BEFORE_NATURAL_TERMINAL"
    }
    h_result, h_predictions = stage2(
        joined,
        raw_days,
        branch_fallback_checkpoints,
        evaluation_case_ids=residual_case_ids,
        residual_training_case_ids=residual_case_ids,
        pass_name="STAGE2_H_FALLBACK_RESIDUAL_ONLY",
    )
    predictions = prebirth_predictions + h_predictions
    cascade_result, cascade_case_rows = selective_cascade(joined, predictions)
    stage2_result = {
        "status": "STAGE2_PREBIRTH_FIRST_RESIDUAL_H_COMPLETE_NO_PROMOTION",
        "population_policy": POLICY,
        "prebirth_pass": prebirth_result,
        "h_fallback_residual_only_pass": h_result,
        "cascade": cascade_result,
        "prebirth_emitted_n": cascade_result["primary_result"]["prebirth"]["n"],
        "h_input_residual_n": len(residual_case_ids),
        "h_full_population_used": len(residual_case_ids) == sum(row["clock"]["day"] != sorted({x["clock"]["day"] for x in joined})[0] for row in joined),
        "earliest_stable_prebirth_checkpoint_s": prebirth_result["earliest_stable_prebirth_checkpoint_s"],
        "earliest_stable_chronological_oot_checkpoint_s": prebirth_result["earliest_stable_chronological_oot_checkpoint_s"],
        "earliest_management_gate_checkpoint_s": h_result["earliest_management_gate_checkpoint_s"],
        "checkpoints": prebirth_result["checkpoints"] + h_result["checkpoints"],
        "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
        "failure_policy": FAIL_POLICY,
    }
    blocker_payload = blockers()
    blocker_payload["target_a_membership_classifier"] = {
        "status": "COMPLETED_EVENT_CENTERED_FROZEN_EXHAUSTION_CANDIDATE_UNIVERSE",
        "candidate_rows": len(roster_candidates),
        "fixed_positive_rows": EXPECTED_TOTAL,
        "control_rows": len(roster_candidates) - EXPECTED_TOTAL,
        "fixed_positive_identity_match": True,
        "scope_limitation": "not an every-second live alert claim",
    }
    failures = failed_conditional(stage2_result)

    write_json(args.out_dir / "NG_EXHAUSTION_POX_CAUSAL_JOIN_PROVENANCE_20260819.json", provenance)
    write_jsonl(args.out_dir / "NG_EXHAUSTION_POX_CAUSAL_ENRICHED_3429_20260819.jsonl", enriched_rows)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_BRANCH_KNOWABILITY_20260819.json", timing)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_TARGET_A_PREBIRTH_MEMBERSHIP_20260819.json", target_a_result)
    write_jsonl(args.out_dir / "NG_EXHAUSTION_POX_TARGET_A_OOT_PREDICTIONS_20260819.jsonl", membership_predictions)
    write_jsonl(args.out_dir / "NG_EXHAUSTION_POX_TARGET_A_FIRST_CALL_CASCADE_12994_20260819.jsonl", membership_case_rows)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_STAGE2_BRANCH_PREDICTION_20260819.json", stage2_result)
    write_jsonl(args.out_dir / "NG_EXHAUSTION_POX_STAGE2_OOT_PREDICTIONS_20260819.jsonl", predictions)
    write_jsonl(args.out_dir / "NG_EXHAUSTION_POX_STAGE2_FIRST_CALL_CASCADE_3429_20260819.jsonl", cascade_case_rows)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_INPUT_BLOCKERS_20260819.json", blocker_payload)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_FAILED_CONDITIONAL_RULES_20260819.json", failures)
    (args.out_dir / "NG_EXHAUSTION_POX_STANDALONE_RESULTS_20260819.md").write_text(
        summary_markdown(provenance, timing, stage2_result, blocker_payload), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": "POX_STANDALONE_CAUSAL_PASS_COMPLETE",
                "rows": len(joined),
                "earliest_stable_checkpoint_s": stage2_result["earliest_stable_chronological_oot_checkpoint_s"],
                "earliest_management_checkpoint_s": stage2_result["earliest_management_gate_checkpoint_s"],
                "prediction_rows": len(predictions),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
