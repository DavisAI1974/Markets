#!/usr/bin/env python3
"""Reproduce the frozen NG Phase-2 SSOS paper-play characterization.

This script is read-only with respect to the canonical Phase-1 event tables. It
implements the same h=60 / D4 causal-availability wall used in Phase 1, then
measures only the predeclared paper-play return from structural endpoint +5s to
+30s. It never uses the current event's +60 state to decide entry.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

INFO_HORIZON_SECONDS = 60
DEPTH = 4
ENTRY_OFFSET_SECONDS = 5
EXIT_OFFSET_SECONDS = 30
HISTORY_HORIZONS = (5, 10, 20, 30, 60)
METRICS = ("signed_displacement_ticks", "mfe_ticks", "mae_ticks")

S = "collapsed_same_flow_reload"
O = "collapsed_opposite_flow_reversal"
P = "persistent_exhaustion"
X = "collapsed_sparse_indeterminate"
PLAY_SEQUENCE = (S, S, O, S)
STATE_CODE = {S: "S", O: "O", P: "P", X: "X"}


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def load_by_week(path: Path) -> dict[str, list[dict[str, Any]]]:
    by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            by_week[str(row["week_sunday"])].append(row)
    for week in by_week:
        by_week[week].sort(key=lambda row: int(row["sequence_index"]))
    return dict(by_week)


def causal_history_complete(row: dict[str, Any]) -> bool:
    """Mirror the Phase-1 h=60 causal input completeness requirement."""
    if row.get("link", {}).get("next_same_polarity") is None:
        return False
    post = row.get("outcome", {}).get("post_endpoint_price")
    if not isinstance(post, dict):
        return False
    horizons = post.get("horizons", {})
    for metric in METRICS:
        for horizon in HISTORY_HORIZONS:
            cell = horizons.get(str(horizon), {})
            if cell.get("censored", False) or not finite(cell.get(metric)):
                return False
    return True


def d4_history_available(predecessors: list[dict[str, Any]], current: dict[str, Any]) -> bool:
    if len(predecessors) != DEPTH:
        return False
    current_t0 = int(current["t0_idx"])
    for row in predecessors:
        if not causal_history_complete(row):
            return False
        confirmation = row.get("dynamic_endpoint", {}).get("causal_confirmation_idx")
        if confirmation is None:
            return False
        if int(confirmation) + INFO_HORIZON_SECONDS > current_t0:
            return False
    return True


def paper_return_ticks(current: dict[str, Any]) -> float | None:
    """Return oriented ticks from structural endpoint +5s to +30s.

    Entry is permitted only if the endpoint is causally confirmed by +5s. A
    successor that begins before confirmation invalidates the trade. The
    return is reconstructed from canonical signed displacement fields; no raw
    price or future state is needed.
    """
    endpoint = current.get("dynamic_endpoint", {})
    onset = endpoint.get("structural_onset_idx")
    confirmation = endpoint.get("causal_confirmation_idx")
    if onset is None or confirmation is None:
        return None
    if int(confirmation) > int(onset) + ENTRY_OFFSET_SECONDS:
        return None
    if current.get("link", {}).get("next_starts_before_endpoint_confirmation"):
        return None

    post = current.get("outcome", {}).get("post_endpoint_price")
    if not isinstance(post, dict):
        return None
    horizons = post.get("horizons", {})
    entry = horizons.get(str(ENTRY_OFFSET_SECONDS), {})
    exit_ = horizons.get(str(EXIT_OFFSET_SECONDS), {})
    if entry.get("censored", False) or exit_.get("censored", False):
        return None
    entry_move = entry.get("signed_displacement_ticks")
    exit_move = exit_.get("signed_displacement_ticks")
    if not finite(entry_move) or not finite(exit_move):
        return None
    return float(exit_move) - float(entry_move)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    z = q * (len(ordered) - 1)
    lo = int(math.floor(z))
    hi = min(lo + 1, len(ordered) - 1)
    frac = z - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None}
    n = len(values)
    return {
        "n": n,
        "mean": sum(values) / n,
        "median": median(values),
        "positive_rate": sum(v > 0 for v in values) / n,
        "negative_rate": sum(v < 0 for v in values) / n,
        "zero_rate": sum(v == 0 for v in values) / n,
        "mean_positive": (
            sum(v for v in values if v > 0) / sum(v > 0 for v in values)
            if any(v > 0 for v in values)
            else None
        ),
        "mean_negative": (
            sum(v for v in values if v < 0) / sum(v < 0 for v in values)
            if any(v < 0 for v in values)
            else None
        ),
    }


def timing_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p25": None, "p75": None, "max": None}
    return {
        "n": len(values),
        "median": median(values),
        "p25": percentile(values, 0.25),
        "p75": percentile(values, 0.75),
        "max": max(values),
    }


def collect(path: Path) -> dict[str, Any]:
    by_week = load_by_week(path)
    universe: list[dict[str, Any]] = []
    play: list[dict[str, Any]] = []

    for week, rows in sorted(by_week.items()):
        for index in range(DEPTH, len(rows)):
            current = rows[index]
            predecessors = rows[index - DEPTH : index]
            if not d4_history_available(predecessors, current):
                continue
            ret = paper_return_ticks(current)
            if ret is None:
                continue
            item = {
                "week": week,
                "return_ticks": ret,
                "event_id": current["event_id"],
                "sequence": tuple(row["seed_state"] for row in predecessors),
                "predecessors": predecessors,
                "current": current,
            }
            universe.append(item)
            if item["sequence"] == PLAY_SEQUENCE:
                play.append(item)

    universe_returns = [item["return_ticks"] for item in universe]
    play_returns = [item["return_ticks"] for item in play]
    universe_mean = sum(universe_returns) / len(universe_returns) if universe_returns else None
    play_mean = sum(play_returns) / len(play_returns) if play_returns else None

    oldest_gap: list[float] = []
    latest_gap: list[float] = []
    onset_offset: list[float] = []
    deeper: dict[str, list[float]] = defaultdict(list)

    by_event_position: dict[str, tuple[str, int]] = {}
    for week, rows in by_week.items():
        for pos, row in enumerate(rows):
            by_event_position[str(row["event_id"])] = (week, pos)

    for item in play:
        current = item["current"]
        predecessors = item["predecessors"]
        current_t0 = int(current["t0_idx"])
        oldest_gap.append(float(current_t0 - int(predecessors[0]["t0_idx"])))
        latest_gap.append(float(current_t0 - int(predecessors[-1]["t0_idx"])))
        endpoint = current["dynamic_endpoint"]
        onset_offset.append(float(int(endpoint["structural_onset_idx"]) - current_t0))

        week, pos = by_event_position[str(current["event_id"])]
        if pos >= DEPTH + 1:
            fifth = by_week[week][pos - DEPTH - 1]
            code = STATE_CODE.get(str(fifth.get("seed_state")), "?")
            deeper[code].append(float(item["return_ticks"]))

    return {
        "weeks": sorted(by_week),
        "universe_count": len(universe),
        "universe_mean_ticks": universe_mean,
        "play_count": len(play),
        "play_frequency": len(play) / len(universe) if universe else None,
        "play_stats": describe(play_returns),
        "play_delta_vs_universe_ticks": (
            play_mean - universe_mean
            if play_mean is not None and universe_mean is not None
            else None
        ),
        "history_timing_seconds": {
            "oldest_to_current_t0": timing_summary(oldest_gap),
            "latest_to_current_t0": timing_summary(latest_gap),
            "current_onset_offset": timing_summary(onset_offset),
        },
        "deeper_fifth_predecessor": {
            code: {"n": len(values), "gross_mean_ticks": sum(values) / len(values)}
            for code, values in sorted(deeper.items())
        },
        "_universe_returns": universe_returns,
        "_play_mask": [item["sequence"] == PLAY_SEQUENCE for item in universe],
    }


def held_exact_circular_shift_p(result: dict[str, Any]) -> dict[str, Any]:
    """Exact same-week circular-shift falsifier for the held week."""
    values = list(result["_universe_returns"])
    mask = list(result["_play_mask"])
    if not values or not any(mask):
        return {"shift_count": 0, "observed_mean_ticks": None, "p_one_sided": None}
    selected = [value for value, flag in zip(values, mask) if flag]
    observed = sum(selected) / len(selected)
    exceed = 0
    n = len(values)
    for shift in range(n):
        shifted = values[-shift:] + values[:-shift] if shift else values
        null_mean = sum(value for value, flag in zip(shifted, mask) if flag) / len(selected)
        if null_mean >= observed:
            exceed += 1
    return {
        "shift_count": n,
        "observed_mean_ticks": observed,
        "null_at_or_above_observed": exceed,
        "p_one_sided": (1 + exceed) / (1 + n),
    }


def strip_private(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base54", required=True, type=Path)
    parser.add_argument("--held", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    base = collect(args.base54)
    held = collect(args.held)
    falsifier = held_exact_circular_shift_p(held)

    expected = {
        "base_universe": 49832,
        "base_play": 1242,
        "held_universe": 826,
        "held_play": 27,
    }
    observed = {
        "base_universe": base["universe_count"],
        "base_play": base["play_count"],
        "held_universe": held["universe_count"],
        "held_play": held["play_count"],
    }
    if observed != expected:
        raise SystemExit(f"Phase-2 frozen-count drift: expected={expected} observed={observed}")

    result = {
        "status": "NG_CHAIN_D4_SSOS_CONTINUATION_V1_REPRODUCED",
        "play_id": "NG_CHAIN_D4_SSOS_CONTINUATION_V1",
        "signal": {
            "information_horizon_seconds": INFO_HORIZON_SECONDS,
            "depth": DEPTH,
            "predecessor_seed_states_oldest_to_newest": list(PLAY_SEQUENCE),
            "entry_offset_from_structural_endpoint_seconds": ENTRY_OFFSET_SECONDS,
            "exit_offset_from_structural_endpoint_seconds": EXIT_OFFSET_SECONDS,
            "holding_period_seconds": EXIT_OFFSET_SECONDS - ENTRY_OFFSET_SECONDS,
            "direction": "with current exhaustion polarity",
        },
        "base54": strip_private(base),
        "held_20260329": strip_private(held),
        "held_exact_circular_shift_falsifier": falsifier,
        "protected_sources_mutated": False,
    }

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
