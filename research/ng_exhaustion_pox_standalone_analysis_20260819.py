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
CHECKPOINTS_S = (-60, -45, -30, -20, -15, -10, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 10, 15, 20, 30, 45, 60)
SERIES_FIELDS = (
    "dipole_roll20_oriented_t_minus60_to_plus60",
    "dipole_roll60_raw_t_minus60_to_plus60",
    "book_10level_imbalance_t_minus60_to_plus60",
    "aggressor_buy_volume_t_minus60_to_plus60",
    "aggressor_sell_volume_t_minus60_to_plus60",
)
POINT_OFFSETS_S = (-60, -45, -30, -20, -15, -10, -5, 0, 1, 2, 3, 4, 5, 10, 15, 20, 30, 45, 60)
WINDOWS_S = (5, 10, 20, 60)
RAW_ACTIONS = ("A", "C", "M", "T", "R")
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
                if row.get("action") == "T":
                    price = finite_float(row.get("price"))
                    size = finite_float(row.get("size", row.get("qty")))
                    if math.isfinite(price) and price > 0:
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


def load_raw_causal_days(raw_dir: Path, required_days: list[str]) -> tuple[dict[str, RawCausalDay], dict[str, Any]]:
    paths = sorted(raw_dir.glob("NG_*.jsonl.gz"))
    days = [RawCausalDay(path) for path in paths]
    by_day = {day.day: day for day in days}
    if sorted(by_day) != required_days:
        raise RuntimeError(f"raw causal day mismatch: required={required_days} supplied={sorted(by_day)}")
    provenance = {
        day.day: {"name": path.name, "sha256": sha256(path), "raw_rows": day.raw_rows}
        for path, day in zip(paths, days)
    }
    return by_day, provenance


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


def raw_market_features(case: dict[str, Any], checkpoint_s: int, raw_day: RawCausalDay) -> dict[str, float]:
    """Use data through the completed H second; execution starts at H+1."""
    t0 = int(case["clock"]["second_utc"])
    end = min(86399, t0 + checkpoint_s)
    start = max(0, t0 - 60)
    features: dict[str, float] = {}
    state_fields = {
        "raw_mid": raw_day.mid,
        "raw_spread_ticks": raw_day.spread_ticks,
        "raw_book_imbalance": raw_day.book_imbalance,
        "raw_bid_depth10": raw_day.bid_depth10,
        "raw_ask_depth10": raw_day.ask_depth10,
        "raw_last_trade": raw_day.last_trade,
        "raw_mid_mean_within_second": raw_day.mid_mean,
        "raw_mid_high_within_second": raw_day.mid_high,
        "raw_mid_low_within_second": raw_day.mid_low,
        "raw_spread_mean_within_second": raw_day.spread_mean,
        "raw_spread_high_within_second": raw_day.spread_high,
        "raw_spread_low_within_second": raw_day.spread_low,
        "raw_trade_vwap_within_second": raw_day.trade_vwap,
        "raw_trade_high_within_second": raw_day.trade_high,
        "raw_trade_low_within_second": raw_day.trade_low,
        **{f"raw_{name}": array for name, array in raw_day.level_fields.items()},
    }
    dense_offsets = list(range(-60, checkpoint_s + 1))
    reference_index = min(86399, max(0, t0 if checkpoint_s >= 0 else end))
    anchor_mid = raw_day.mid[reference_index]
    polarity = int(case["polarity"])
    for name, array in state_fields.items():
        prefix = [finite_float(value) for value in array[start : end + 1]]
        for stat, value in series_stats(prefix).items():
            features[f"{name}__full_{stat}"] = value
        for offset in dense_offsets:
            index = min(86399, max(0, t0 + offset))
            features[f"{name}__at_{offset:+d}"] = finite_float(array[index])
    for offset in dense_offsets:
        index = min(86399, max(0, t0 + offset))
        mid = finite_float(raw_day.mid[index])
        features[f"raw_mid_ticks_from_causal_reference__at_{offset:+d}"] = (
            (mid - anchor_mid) / 0.001 if math.isfinite(mid) and math.isfinite(anchor_mid) else float("nan")
        )
        features[f"raw_mid_oriented_ticks_from_causal_reference__at_{offset:+d}"] = (
            polarity * (mid - anchor_mid) / 0.001
            if checkpoint_s >= 0 and math.isfinite(mid) and math.isfinite(anchor_mid)
            else float("nan")
        )
    for name, array in {
        "raw_trade_volume": raw_day.trade_volume,
        "raw_buy_volume": raw_day.buy_volume,
        "raw_sell_volume": raw_day.sell_volume,
        "raw_trade_count": raw_day.trade_count,
        "raw_row_count": raw_day.raw_row_count,
        **{f"raw_action_{action}_count": raw_day.action_counts[action] for action in RAW_ACTIONS},
    }.items():
        prefix = np.asarray(array[start : end + 1], dtype=float)
        features[f"{name}__sum"] = float(np.sum(prefix))
        features[f"{name}__last"] = float(prefix[-1]) if len(prefix) else float("nan")
        for window_s in WINDOWS_S:
            window = prefix[max(0, len(prefix) - window_s) :]
            features[f"{name}__w{window_s}_sum"] = float(np.sum(window))
        for offset in dense_offsets:
            index = min(86399, max(0, t0 + offset))
            features[f"{name}__at_{offset:+d}"] = finite_float(array[index])
    return features


def causal_features(case: dict[str, Any], checkpoint_s: int, raw_days: dict[str, RawCausalDay]) -> dict[str, float]:
    record = case["causal_record"]
    features: dict[str, float] = {}
    second = int(case["clock"]["second_utc"])
    market_clock = str(case["clock"].get("market_clock", "00:00:00"))
    hour, minute, sec = (int(part) for part in market_clock.split(":"))
    market_second = hour * 3600 + minute * 60 + sec
    for prefix, cyc_second in (("utc", second), ("market", market_second)):
        angle = 2.0 * math.pi * cyc_second / 86400.0
        features[f"clock_{prefix}_sin"] = math.sin(angle)
        features[f"clock_{prefix}_cos"] = math.cos(angle)
    origin_is_born = checkpoint_s >= 0
    origin_is_confirmed = (
        case["origin_confirmation_offset_s"] is not None and case["origin_confirmation_offset_s"] <= checkpoint_s
    )
    features["origin_polarity"] = float(case["polarity"]) if origin_is_born else float("nan")
    features["origin_confirmation_offset_s"] = float(case["origin_confirmation_offset_s"]) if origin_is_confirmed else float("nan")
    origin_endpoint = case["roster_causal_fields"]["endpoint_posthoc"]
    features["origin_structural_onset_offset_s"] = finite_float(origin_endpoint.get("structural_onset_offset_s")) if origin_is_confirmed else float("nan")
    for family in ("A", "B", "C"):
        features[f"causal_pre_t0_family_{family}"] = float(case.get("frozen_target_family") == family) if origin_is_born else float("nan")

    end_index = 60 + checkpoint_s
    for field in SERIES_FIELDS:
        if checkpoint_s < 0 and field == "dipole_roll20_oriented_t_minus60_to_plus60":
            continue
        raw = record.get(field)
        if not isinstance(raw, list) or len(raw) != 121:
            values = [float("nan")] * 121
        else:
            values = [finite_float(value) for value in raw]
        prefix_values = values[: end_index + 1]
        short = field.replace("_t_minus60_to_plus60", "")
        for offset in range(-60, checkpoint_s + 1):
            features[f"{short}__at_{offset:+d}"] = values[offset + 60]
        for window_s in WINDOWS_S:
            start_offset = max(-60, checkpoint_s - window_s + 1)
            window = values[start_offset + 60 : end_index + 1]
            for stat, value in series_stats(window).items():
                features[f"{short}__w{window_s}_{stat}"] = value
        for stat, value in series_stats(prefix_values).items():
            features[f"{short}__full_{stat}"] = value

    buy = record.get("aggressor_buy_volume_t_minus60_to_plus60")
    sell = record.get("aggressor_sell_volume_t_minus60_to_plus60")
    if isinstance(buy, list) and isinstance(sell, list) and len(buy) == len(sell) == 121:
        net = [finite_float(b) - finite_float(s) for b, s in zip(buy[: end_index + 1], sell[: end_index + 1])]
    else:
        net = [float("nan")] * (end_index + 1)
    for stat, value in series_stats(net).items():
        features[f"aggressor_net__full_{stat}"] = value
    for offset, value in zip(range(-60, checkpoint_s + 1), net):
        features[f"aggressor_net__at_{offset:+d}"] = value

    mbo = record.get("mbo_t_minus60_to_plus60") or record.get("mbo_orderflow_t_minus60_to_plus60")
    features["mbo_available"] = float(isinstance(mbo, dict))
    for mbo_field in MBO_FIELDS:
        raw_values = mbo.get(mbo_field) if isinstance(mbo, dict) else None
        values = (
            [finite_float(value) for value in raw_values]
            if isinstance(raw_values, list) and len(raw_values) == 121
            else [float("nan")] * 121
        )
        if values:
            prefix = values[: end_index + 1]
            for offset in range(-60, checkpoint_s + 1):
                features[f"mbo_{mbo_field}__at_{offset:+d}"] = values[offset + 60]
            for stat, value in series_stats(prefix).items():
                features[f"mbo_{mbo_field}__full_{stat}"] = value

    milestones = record.get("post_exhaustion") or record.get("post_exhaustion_dipole_only") or {}
    for name in ("t50_s", "t25_s", "t10_s", "zero_s"):
        observed_time = milestones.get(name) if isinstance(milestones, dict) else None
        observed_by_h = observed_time is not None and int(observed_time) <= checkpoint_s
        features[f"causal_milestone_{name}_observed_by_h"] = float(observed_by_h)
        features[f"causal_milestone_{name}_time_if_observed"] = float(observed_time) if observed_by_h else float("nan")
    features.update(raw_market_features(case, checkpoint_s, raw_days[str(case["clock"]["day"])]))
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
    features = raw_market_features(candidate, checkpoint_s, raw_days[str(candidate["clock"]["day"])])
    decision_second = (int(candidate["clock"]["second_utc"]) + checkpoint_s) % 86400
    angle = 2.0 * math.pi * decision_second / 86400.0
    features["decision_clock_utc_sin"] = math.sin(angle)
    features["decision_clock_utc_cos"] = math.cos(angle)
    born = checkpoint_s >= 0
    endpoint = candidate.get("endpoint_posthoc") or {}
    confirmation = None if endpoint.get("censored") else endpoint.get("causal_confirmation_offset_s")
    confirmed = confirmation is not None and int(confirmation) <= checkpoint_s
    features["origin_polarity"] = float(candidate["polarity"]) if born else float("nan")
    for family in ("A", "B", "C"):
        features[f"causal_pre_t0_family_{family}"] = float(candidate.get("causal_family") == family) if born else float("nan")
    features["origin_confirmation_offset_s"] = float(confirmation) if confirmed else float("nan")
    features["origin_structural_onset_offset_s"] = (
        finite_float(endpoint.get("structural_onset_offset_s")) if confirmed else float("nan")
    )
    pre = candidate.get("pre_roll20_oriented_t_minus60_to_t0")
    values = [finite_float(value) for value in pre] if born and isinstance(pre, list) and len(pre) == 61 else [float("nan")] * 61
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
    checkpoint_results = []
    predictions: list[dict[str, Any]] = []
    for h in checkpoints_to_run:
        folds = []
        checkpoint_predictions = []
        for test_day in days[1:]:
            train = [
                row
                for row in candidates
                if row["clock"]["day"] < test_day
                and (
                    residual_training_candidate_ids is None
                    or row["clock"]["day"] == first_day
                    or row["candidate_id"] in residual_training_candidate_ids
                )
            ]
            test = [
                row
                for row in candidates
                if row["clock"]["day"] == test_day
                and (evaluation_candidate_ids is None or row["candidate_id"] in evaluation_candidate_ids)
            ]
            train_y = np.asarray([int(row["is_fixed_pox"]) for row in train], dtype=int)
            test_y = np.asarray([int(row["is_fixed_pox"]) for row in test], dtype=int)
            if not train or not test or len(np.unique(train_y)) < 2 or len(np.unique(test_y)) < 2:
                folds.append({"test_day": test_day, "train_n": len(train), "test_n": len(test), "status": "INSUFFICIENT_TWO_CLASS_SUPPORT"})
                continue
            train_x, names = membership_matrix(train, h, raw_days)
            test_x, _ = membership_matrix(test, h, raw_days, names)
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
            "information_policy": "maximally rich raw MBP-10 causal prefix; future origin attributes withheld before birth",
            "evaluation_population": "all OOT candidates" if evaluation_candidate_ids is None else "prebirth no-call residual candidates only",
            "checkpoints": checkpoint_results,
            "earliest_stable_checkpoint_s": min(stable_h) if stable_h else None,
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
    for stage, checkpoints in (
        ("PREBIRTH", [h for h in CHECKPOINTS_S if h < 0]),
        ("H_FALLBACK", [h for h in CHECKPOINTS_S if h >= 0]),
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
            case_rows.append({**base, "cascade_status": "NO_CONFIDENT_CALL_THROUGH_H60"})

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
            "fixed_pox_unresolved_through_h60_n": sum(row["candidate_id"] not in called_positive_ids for row in oot_positives),
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
    roster_candidates = [
        {
            "candidate_id": f"{row['clock']['day']}-{int(row['clock']['second_utc']):05d}-{int(row['polarity']):+d}",
            "clock": row["clock"],
            "polarity": int(row["polarity"]),
            "is_fixed_pox": bool(row.get("frozen_target_match") is True),
            "causal_family": row.get("descriptors_posthoc", {}).get("family"),
            "endpoint_posthoc": row.get("endpoint_posthoc", {}),
            "pre_roll20_oriented_t_minus60_to_t0": row.get("chain_membership_state", {}).get("pre_roll20_oriented_t_minus60_to_t0"),
            "source_roster_identity": {"week_sunday": row["week_sunday"], "week_index": row["week_index"]},
        }
        for row in sorted(roster_by_identity.values(), key=lambda item: (item["clock"]["day"], item["clock"]["second_utc"], item["polarity"]))
    ]

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
        "checkpoint_state": {
            str(h): (
                "PREBIRTH_CONDITIONAL_WINDOW"
                if h < 0
                else "ORIGIN_NOT_CONFIRMED"
                if origin_confirm is None or origin_confirm > h
                else "BRANCH_ALREADY_KNOWN"
                if branch_known is not None and branch_known <= h
                else "PREDICTION_WINDOW"
            )
            for h in CHECKPOINTS_S
        },
        "raw_tape_execution_status": "BLOCKED_AUTHORITATIVE_RAW_TAPE_NOT_SUPPLIED",
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

    checkpoint_states = {}
    for h in CHECKPOINTS_S:
        states = Counter()
        for row in joined:
            origin = row["origin_confirmation_offset_s"]
            known = row["branch_causally_known_offset_s"]
            state = (
                "PREBIRTH_CONDITIONAL_WINDOW"
                if h < 0
                else "ORIGIN_NOT_CONFIRMED"
                if origin is None or origin > h
                else "BRANCH_ALREADY_KNOWN"
                if known is not None and known <= h
                else "PREDICTION_WINDOW"
            )
            states[state] += 1
        checkpoint_states[str(h)] = dict(states)
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
        "checkpoint_states": checkpoint_states,
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
    for h in checkpoints_requested:
        eligible = [
            row
            for row in joined
            if (h < 0 or (row["origin_confirmation_offset_s"] is not None and row["origin_confirmation_offset_s"] <= h))
            and (row["branch_causally_known_offset_s"] is None or row["branch_causally_known_offset_s"] > h)
        ]
        fold_results = []
        checkpoint_predictions = []
        for test_day in days[1:]:
            train = [
                row
                for row in eligible
                if row["clock"]["day"] < test_day
                and (
                    residual_training_case_ids is None
                    or row["clock"]["day"] == first_day
                    or row["case_id"] in residual_training_case_ids
                )
            ]
            test = [
                row
                for row in eligible
                if row["clock"]["day"] == test_day
                and (evaluation_case_ids is None or row["case_id"] in evaluation_case_ids)
            ]
            train_y = np.asarray([1 if row["branch_label"] == "FLIP" else 0 for row in train], dtype=int)
            test_y = np.asarray([1 if row["branch_label"] == "FLIP" else 0 for row in test], dtype=int)
            if not train or not test or len(np.unique(train_y)) < 2 or len(np.unique(test_y)) < 2:
                fold_results.append(
                    {
                        "test_day": test_day,
                        "train_days": sorted({row["clock"]["day"] for row in train}),
                        "train_n": len(train),
                        "test_n": len(test),
                        "status": "INSUFFICIENT_TWO_CLASS_SUPPORT",
                    }
                )
                continue
            train_x, names = matrix(train, h, raw_days)
            test_x, _ = matrix(test, h, raw_days, names)
            pipeline = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True, add_indicator=True)),
                    ("scaler", StandardScaler()),
                    ("logistic", LogisticRegression(C=0.01, solver="liblinear", max_iter=3000, random_state=1974)),
                ]
            )
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
                "eligible_prediction_window_n": len(eligible),
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
            "allowed": "full dense -60..H causal detector/book/flow/MBO prefixes; causally observed milestone state; pre-t0 causal family; complete per-second MBP-10 level-0..9 state, price, spread, depth, row/action counts, trades, and volume through the completed H second; current polarity and clock",
            "excluded": [
                "branch_label",
                "next_event_target",
                "frozen_target_split",
                "reveal price path",
                "posthoc family/state assignments",
                "successor identity/polarity/timing",
                "D0-D5 results",
            ],
            "eligibility": "all fixed cases at H<0 for conditional prebirth branch forecasting; at H>=0, origin confirmation <= H and branch confirmation > H",
            "raw_price_cutoff": "raw events in seconds <= t0+H only; first executable quote is at or after t0+H+1",
            "prebirth_anti_leakage": "for H<0, future origin polarity, t0 price, causal family, confirmation timing, structural onset, and polarity-oriented series are withheld",
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
            "evaluation_population": "all chronological OOT fixed cases" if evaluation_case_ids is None else "prebirth no-call residual cases only",
            "training_population": "all earlier fixed cases" if residual_training_case_ids is None else "first historical day plus earlier chronological prebirth no-call residual cases",
        },
        "checkpoints": checkpoints,
        "earliest_stable_chronological_oot_checkpoint_s": min(stable_checkpoints) if stable_checkpoints else None,
        "earliest_stable_prebirth_checkpoint_s": min(stable_prebirth) if stable_prebirth else None,
        "earliest_management_gate_checkpoint_s": min(management_checkpoints) if management_checkpoints else None,
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
    prebirth_h = [h for h in CHECKPOINTS_S if h < 0]
    fallback_h = [h for h in CHECKPOINTS_S if h >= 0]
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
            for h in CHECKPOINTS_S:
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
                            "cascade_status": "NO_CONFIDENT_CALL_THROUGH_H60",
                            "branch_causally_known_offset_s": known,
                            "branch_became_observable_by_h60": known is not None and known <= 60,
                        }
                    )
    primary = next(row for row in sensitivity if abs(row["confidence_threshold"] - PRIMARY_SELECTIVE_CONFIDENCE) < 1e-12)
    return (
        {
            "status": "PREBIRTH_FIRST_RESIDUAL_H_CASCADE_COMPLETE_NO_PROMOTION",
            "population_policy": POLICY,
            "objective": "call every fixed case before birth when confidence permits; run H only on cases receiving no prebirth call",
            "checkpoint_order": {"prebirth": prebirth_h, "h_fallback": fallback_h},
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
- Residual H calls: {cascade['h_fallback_residual_only']['n']:,}; unresolved through H60: {cascade['unresolved_n']:,}.
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
    required_days = sorted({row["clock"]["day"] for row in joined})
    raw_days, raw_provenance = load_raw_causal_days(args.raw_dir, required_days)
    provenance["raw_causal_inputs"] = raw_provenance
    provenance["raw_causal_cutoff"] = "end of completed checkpoint second H; no event from second H+1 or later"
    enriched_rows = [public_enriched_row(row) for row in joined]
    timing = knowability(joined)
    prebirth_checkpoints = [h for h in CHECKPOINTS_S if h < 0]
    fallback_checkpoints = [h for h in CHECKPOINTS_S if h >= 0]
    membership_prebirth, membership_prebirth_predictions = membership_prediction_pass(
        roster_candidates,
        raw_days,
        prebirth_checkpoints,
        pass_name="TARGET_A_PREBIRTH_MEMBERSHIP",
    )
    _, membership_prebirth_rows = membership_cascade(roster_candidates, membership_prebirth_predictions)
    membership_residual_ids = {
        row["candidate_id"]
        for row in membership_prebirth_rows
        if row["cascade_status"] == "NO_CONFIDENT_CALL_THROUGH_H60"
    }
    membership_h, membership_h_predictions = membership_prediction_pass(
        roster_candidates,
        raw_days,
        fallback_checkpoints,
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
        prebirth_checkpoints,
        pass_name="STAGE2_PREBIRTH_BRANCH",
    )
    prebirth_cascade, prebirth_case_rows = selective_cascade(joined, prebirth_predictions)
    residual_case_ids = {
        row["case_id"]
        for row in prebirth_case_rows
        if row["cascade_status"] == "NO_CONFIDENT_CALL_THROUGH_H60"
    }
    h_result, h_predictions = stage2(
        joined,
        raw_days,
        fallback_checkpoints,
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
