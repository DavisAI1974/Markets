#!/usr/bin/env python3
"""Exact MBP-10 quote-side execution for the fixed NG POX population.

Membership and labels are loaded only from the already-enriched fixed ledger.
The raw files supply executable prices; they can never add, remove, or relabel a
case.  Long entries lift ask and liquidate at bid; short entries hit bid and
liquidate at ask.  Additional 0.5/1.0/2.0 tick round-trip stresses are then
subtracted from those quote-side results.
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


EXPECTED_TOTAL = 3429
EXPECTED_FLIP = 1546
EXPECTED_SAME = 1883
POLICY = "FIXED_3429_DO_NOT_REOPEN"
FAIL_POLICY = "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL"
TICK = 0.001
CHECKPOINTS_S = (0, 1, 2, 3, 4, 5, 10, 15, 20, 30, 45, 60)
HOLDS_S = (5, 10, 20, 30, 60)
STRESSES_TICKS = (0.5, 1.0, 2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enriched-ledger", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix.lower() == ".gz" else path.open("r", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open_text(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl_gz(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
            for row in rows:
                zipped.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def day_from_name(path: Path) -> str:
    match = re.search(r"(20\d{6})", path.name)
    if not match:
        raise RuntimeError(f"cannot parse trading day from {path}")
    return match.group(1)


def normalized_seconds(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    # Existing corpus loaders establish seconds as the source unit.  These
    # guards retain compatibility if a raw shard carries ns/us/ms epochs.
    if value > 1e17:
        value /= 1e9
    elif value > 1e14:
        value /= 1e6
    elif value > 1e11:
        value /= 1e3
    return value % 86400.0


class QuoteTape:
    def __init__(self, day: str, rows: list[tuple[float, float, float, str, int]], raw_rows: int):
        self.day = day
        self.rows = rows
        self.times = [row[0] for row in rows]
        self.raw_rows = raw_rows

    def first_at_or_after(self, requested_second: float) -> tuple[int, tuple[float, float, float, str, int]] | None:
        index = bisect.bisect_left(self.times, float(requested_second))
        return None if index >= len(self.rows) else (index, self.rows[index])


def load_quote_tape(path: Path) -> QuoteTape:
    day = day_from_name(path)
    quotes: list[tuple[float, float, float, str, int]] = []
    raw_rows = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for source_index, line in enumerate(handle):
            if not line.strip():
                continue
            raw_rows += 1
            row = json.loads(line)
            second = normalized_seconds(row.get("ts_event", row.get("ts")))
            bid = float(row.get("bid_px_00", 0.0) or 0.0)
            ask = float(row.get("ask_px_00", 0.0) or 0.0)
            if second is None or bid <= 0 or ask <= 0 or ask < bid:
                continue
            quotes.append((second, bid, ask, str(row.get("action", "")), source_index))
    quotes.sort(key=lambda item: (item[0], item[4]))
    if not quotes:
        raise RuntimeError(f"no valid MBP-10 quote rows in {path}")
    return QuoteTape(day, quotes, raw_rows)


def validate_ledger(rows: list[dict[str, Any]]) -> None:
    labels = Counter(row.get("branch_label") for row in rows)
    ids = [row.get("case_id") for row in rows]
    if len(rows) != EXPECTED_TOTAL or len(set(ids)) != EXPECTED_TOTAL:
        raise RuntimeError(f"fixed ledger mismatch: rows={len(rows)} unique={len(set(ids))}")
    if labels != Counter({"FLIP": EXPECTED_FLIP, "SAME": EXPECTED_SAME}):
        raise RuntimeError(f"label split mismatch: {dict(labels)}")
    if any(row.get("population_policy") != POLICY for row in rows):
        raise RuntimeError("population policy mismatch")


def quote_snapshot(row: tuple[float, float, float, str, int]) -> dict[str, Any]:
    second, bid, ask, action, source_index = row
    return {
        "second_utc": second,
        "bid": bid,
        "ask": ask,
        "mid": 0.5 * (bid + ask),
        "spread_ticks": (ask - bid) / TICK,
        "raw_action": action,
        "raw_source_index": source_index,
    }


def execution_path(tape: QuoteTape, requested_entry_s: float, requested_exit_s: float, direction: int) -> dict[str, Any]:
    if requested_exit_s <= requested_entry_s:
        return {"status": "INVALID_NONPOSITIVE_HORIZON"}
    entry = tape.first_at_or_after(requested_entry_s)
    exit_ = tape.first_at_or_after(requested_exit_s)
    if entry is None or exit_ is None:
        return {"status": "NON_EXECUTABLE_NO_QUOTE_AT_OR_AFTER_REQUEST"}
    entry_index, entry_row = entry
    exit_index, exit_row = exit_
    if exit_index < entry_index:
        return {"status": "NON_EXECUTABLE_ORDERING"}
    entry_second, entry_bid, entry_ask, _, _ = entry_row
    exit_second, exit_bid, exit_ask, _, _ = exit_row
    entry_price = entry_ask if direction > 0 else entry_bid
    exit_price = exit_bid if direction > 0 else exit_ask
    gross_ticks = direction * (exit_price - entry_price) / TICK
    mid_gross_ticks = direction * ((0.5 * (exit_bid + exit_ask)) - (0.5 * (entry_bid + entry_ask))) / TICK
    interval = tape.rows[entry_index : exit_index + 1]
    liquidation = np.asarray([row[1] if direction > 0 else row[2] for row in interval], dtype=float)
    path_ticks = direction * (liquidation - entry_price) / TICK
    return {
        "status": "EXECUTED_EXACT_MBP10_QUOTE_SIDE",
        "direction": direction,
        "requested_entry_second_utc": requested_entry_s,
        "requested_exit_second_utc": requested_exit_s,
        "entry": quote_snapshot(entry_row),
        "exit": quote_snapshot(exit_row),
        "entry_fill_price": entry_price,
        "exit_fill_price": exit_price,
        "entry_latency_s": entry_second - requested_entry_s,
        "exit_latency_s": exit_second - requested_exit_s,
        "quote_points": len(interval),
        "gross_executable_ticks": gross_ticks,
        "gross_mid_to_mid_ticks": mid_gross_ticks,
        "net_ticks_rt_0_5": gross_ticks - 0.5,
        "net_ticks_rt_1_0": gross_ticks - 1.0,
        "net_ticks_rt_2_0": gross_ticks - 2.0,
        "mfe_executable_ticks": float(np.max(path_ticks)),
        "mae_executable_ticks": float(np.min(path_ticks)),
    }


def metric_summary(values: list[float]) -> dict[str, Any]:
    array = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if not len(array):
        return {"n": 0, "mean": None, "median": None, "p10": None, "p25": None, "p75": None, "p90": None, "positive_fraction": None}
    return {
        "n": len(array),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "positive_fraction": float(np.mean(array > 0)),
    }


def aggregate_execution(rows: list[dict[str, Any]], expected_available: int) -> dict[str, Any]:
    executed = [row for row in rows if row["execution"]["status"] == "EXECUTED_EXACT_MBP10_QUOTE_SIDE"]
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executed:
        by_day[row["day"]].append(row)
        by_week[row["week_sunday"]].append(row)

    def pnl(source: list[dict[str, Any]], field: str) -> list[float]:
        return [float(row["execution"][field]) for row in source]

    gross = pnl(executed, "gross_executable_ticks")
    day_net1 = {day: float(np.mean(pnl(group, "net_ticks_rt_1_0"))) for day, group in sorted(by_day.items())}
    week_net1 = {week: float(np.mean(pnl(group, "net_ticks_rt_1_0"))) for week, group in sorted(by_week.items())}
    coverage = len(executed) / expected_available if expected_available else None
    research_gate = bool(
        expected_available >= 50
        and coverage is not None
        and coverage >= 0.99
        and gross
        and float(np.mean(pnl(executed, "net_ticks_rt_2_0"))) > 0
        and float(np.mean(np.asarray(gross) > 0)) > 0.5
        and day_net1
        and all(value > 0 for value in day_net1.values())
        and week_net1
        and all(value > 0 for value in week_net1.values())
    )
    return {
        "expected_available_n": expected_available,
        "executed_n": len(executed),
        "non_executable_n": expected_available - len(executed),
        "execution_coverage": coverage,
        "gross_executable_ticks": metric_summary(gross),
        "gross_mid_to_mid_ticks": metric_summary(pnl(executed, "gross_mid_to_mid_ticks")),
        "net_ticks_rt_0_5": metric_summary(pnl(executed, "net_ticks_rt_0_5")),
        "net_ticks_rt_1_0": metric_summary(pnl(executed, "net_ticks_rt_1_0")),
        "net_ticks_rt_2_0": metric_summary(pnl(executed, "net_ticks_rt_2_0")),
        "mfe_executable_ticks": metric_summary(pnl(executed, "mfe_executable_ticks")),
        "mae_executable_ticks": metric_summary(pnl(executed, "mae_executable_ticks")),
        "losing_n": sum(value < 0 for value in gross),
        "zero_n": sum(abs(value) < 1e-12 for value in gross),
        "choppy_n": sum(
            row["execution"]["mfe_executable_ticks"] > 0 and row["execution"]["mae_executable_ticks"] < 0 for row in executed
        ),
        "by_day_net_1_tick_mean": day_net1,
        "by_week_net_1_tick_mean": week_net1,
        "positive_week_fraction_net_1_tick": float(np.mean([value > 0 for value in week_net1.values()])) if week_net1 else None,
        "predeclared_research_gate": research_gate,
    }


def base_row(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "day": case["clock"]["day"],
        "week_sunday": case["source_roster_identity"]["week_sunday"],
        "branch_label": case["branch_label"],
        "origin_polarity": int(case["polarity"]),
        "successor_polarity": int(case["successor_polarity"]),
        "t0_second_utc": int(case["clock"]["second_utc"]),
        "origin_confirmation_offset_s": case["origin_confirmation_offset_s"],
        "branch_causally_known_offset_s": case["branch_causally_known_offset_s"],
        "population_policy": POLICY,
    }


def stage1(cases: list[dict[str, Any]], tapes: dict[str, QuoteTape]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    cells = []
    for h in CHECKPOINTS_S:
        eligible = [case for case in cases if case["origin_confirmation_offset_s"] is not None and case["origin_confirmation_offset_s"] <= h]
        for hold in HOLDS_S:
            cell_rows = []
            for case in cases:
                row = {**base_row(case), "checkpoint_s": h, "fixed_hold_s": hold}
                if case["origin_confirmation_offset_s"] is None or case["origin_confirmation_offset_s"] > h:
                    row["checkpoint_status"] = "ORIGIN_NOT_CONFIRMED"
                    row["execution"] = {"status": "NOT_REQUESTED_ORIGIN_NOT_CONFIRMED"}
                else:
                    known = case["branch_causally_known_offset_s"]
                    row["checkpoint_status"] = "BRANCH_ALREADY_KNOWN" if known is not None and known <= h else "PREDICTION_WINDOW"
                    # The H bin is fully observed by its end.  Execute from the
                    # next second boundary so no within-bin future information
                    # can influence a same-bin fill.
                    requested_entry = int(case["clock"]["second_utc"]) + h + 1
                    row["execution"] = execution_path(tapes[row["day"]], requested_entry, requested_entry + hold, int(case["polarity"]))
                    cell_rows.append(row)
                rows.append(row)
            aggregate = aggregate_execution(cell_rows, len(eligible))
            cells.append({"checkpoint_s": h, "fixed_hold_s": hold, **aggregate})
    gate_cells = [cell for cell in cells if cell["fixed_hold_s"] == 60 and cell["predeclared_research_gate"]]
    earliest = min((cell["checkpoint_s"] for cell in gate_cells), default=None)
    return (
        {
            "status": "STAGE1_EXACT_RAW_TAPE_COMPLETE_NO_PROMOTION",
            "population_policy": POLICY,
            "direction": "origin dipole polarity / initial continuation",
            "execution_semantics": "features observe the completed H second; long ask-to-bid or short bid-to-ask execution begins at t0+H+1 using the first valid raw MBP-10 quote at or after that boundary",
            "cost_semantics": "reported gross is already quote-side/spread-inclusive; 0.5/1.0/2.0 additional round-trip tick stresses are subtracted",
            "research_gate": "at 60-second hold: >=99% coverage, positive overall mean after 2 ticks, >50% gross-positive trades, and positive mean after 1 tick in every day and week",
            "cells": cells,
            "earliest_checkpoint_passing_60s_hold_research_gate_s": earliest,
            "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
            "failure_policy": FAIL_POLICY,
        },
        rows,
    )


def stage3(cases: list[dict[str, Any]], tapes: dict[str, QuoteTape], stage1_checkpoint: int | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    action_directions = {
        "CONTINUE_ORIGIN": lambda case: int(case["polarity"]),
        "REVERSE_ORIGIN": lambda case: -int(case["polarity"]),
        "FOLLOW_CONFIRMED_SUCCESSOR_NEW_STATE": lambda case: int(case["successor_polarity"]),
    }
    rows: list[dict[str, Any]] = []
    cells = []
    available = [case for case in cases if case["branch_causally_known_offset_s"] is not None]
    for action, direction_fn in action_directions.items():
        for hold in HOLDS_S:
            cell_rows = []
            for case in cases:
                row = {**base_row(case), "action": action, "fixed_hold_from_branch_confirmation_s": hold}
                known = case["branch_causally_known_offset_s"]
                if known is None:
                    row["execution"] = {"status": "NOT_REQUESTED_BRANCH_CONFIRMATION_UNAVAILABLE"}
                else:
                    signal = int(case["clock"]["second_utc"]) + int(known) + 1
                    row["execution"] = execution_path(tapes[row["day"]], signal, signal + hold, direction_fn(case))
                    cell_rows.append(row)
                rows.append(row)
            cells.append({"action": action, "fixed_hold_from_branch_confirmation_s": hold, **aggregate_execution(cell_rows, len(available))})

    parent_exit_comparison: dict[str, Any]
    if stage1_checkpoint is None:
        parent_exit_comparison = {
            "status": "NOT_RUN_NO_STAGE1_ENTRY_CHECKPOINT_PASSED_RESEARCH_GATE",
            "universal_successor_confirmation_exit_promoted": False,
        }
    else:
        comparison_rows = []
        for case in cases:
            known = case["branch_causally_known_offset_s"]
            if known is None or known + 1 >= 60 or case["origin_confirmation_offset_s"] is None or case["origin_confirmation_offset_s"] > stage1_checkpoint:
                continue
            start = int(case["clock"]["second_utc"]) + stage1_checkpoint + 1
            branch_exit = execution_path(tapes[case["clock"]["day"]], start, int(case["clock"]["second_utc"]) + int(known) + 1, int(case["polarity"]))
            parent60_exit = execution_path(tapes[case["clock"]["day"]], start, int(case["clock"]["second_utc"]) + 60, int(case["polarity"]))
            if branch_exit["status"].startswith("EXECUTED") and parent60_exit["status"].startswith("EXECUTED"):
                comparison_rows.append(
                    {
                        "branch_confirmation_exit_ticks": branch_exit["gross_executable_ticks"],
                        "parent_plus60_exit_ticks": parent60_exit["gross_executable_ticks"],
                        "incremental_ticks": branch_exit["gross_executable_ticks"] - parent60_exit["gross_executable_ticks"],
                    }
                )
        incremental = [row["incremental_ticks"] for row in comparison_rows]
        parent_exit_comparison = {
            "status": "MEASURED_CASES_WITH_BRANCH_KNOWN_BEFORE_PARENT_PLUS60",
            "stage1_entry_checkpoint_s": stage1_checkpoint,
            "n": len(comparison_rows),
            "incremental_branch_exit_minus_parent_plus60_ticks": metric_summary(incremental),
            "universal_successor_confirmation_exit_promoted": False,
        }
    return (
        {
            "status": "STAGE3_EXACT_ACTION_ECONOMICS_COMPLETE_NO_PROMOTION",
            "population_policy": POLICY,
            "signal_semantics": "successor frozen-detector causal confirmation; never retrospective successor onset or t0",
            "later_successor_semantics": "fresh/new-state origin; old ancestry is not inherited",
            "stand_down_reset_ticks": 0.0,
            "cells": cells,
            "parent_exit_comparison": parent_exit_comparison,
            "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
            "failure_policy": FAIL_POLICY,
        },
        rows,
    )


def stage4(cases: list[dict[str, Any]], stage3_rows: list[dict[str, Any]], stage1_checkpoint: int | None, tapes: dict[str, QuoteTape]) -> dict[str, Any]:
    delayed_ids = {
        case["case_id"]
        for case in cases
        if case["branch_label"] == "SAME"
        and case["branch_causally_known_offset_s"] is not None
        and case["branch_causally_known_offset_s"] > 60
    }
    cells = []
    for hold in HOLDS_S:
        selected = [
            row
            for row in stage3_rows
            if row["case_id"] in delayed_ids
            and row["action"] == "FOLLOW_CONFIRMED_SUCCESSOR_NEW_STATE"
            and row["fixed_hold_from_branch_confirmation_s"] == hold
        ]
        cells.append({"fixed_hold_from_later_same_successor_confirmation_s": hold, **aggregate_execution(selected, len(delayed_ids))})

    parent_preservation: dict[str, Any]
    if stage1_checkpoint is None:
        parent_preservation = {"status": "NO_STAGE1_ENTRY_CHECKPOINT_PASSED_RESEARCH_GATE", "original_parent_loss_rewritten": False}
    else:
        parent_rows = []
        by_id = {case["case_id"]: case for case in cases}
        for case_id in delayed_ids:
            case = by_id[case_id]
            if case["origin_confirmation_offset_s"] is None or case["origin_confirmation_offset_s"] > stage1_checkpoint:
                continue
            t0 = int(case["clock"]["second_utc"])
            execution = execution_path(tapes[case["clock"]["day"]], t0 + stage1_checkpoint + 1, t0 + 60, int(case["polarity"]))
            if execution["status"].startswith("EXECUTED"):
                parent_rows.append(float(execution["gross_executable_ticks"]))
        parent_preservation = {
            "status": "ORIGINAL_PARENT_PLUS60_OUTCOME_PRESERVED",
            "stage1_entry_checkpoint_s": stage1_checkpoint,
            "original_parent_gross_executable_ticks": metric_summary(parent_rows),
            "original_parent_loss_rewritten": False,
        }
    return {
        "status": "STAGE4_DELAYED_SAME_SEPARATE_WATCH_COMPLETE_NO_AUTOMATIC_REENTRY",
        "population_policy": POLICY,
        "definition": "SAME cases whose successor causal confirmation occurs after the parent +60 boundary",
        "delayed_same_n": len(delayed_ids),
        "later_setup": "separately confirmed same-polarity successor treated as a fresh/new-state origin",
        "cells": cells,
        "parent_outcome_preservation": parent_preservation,
        "automatic_reentry_authorized": False,
        "promotion_status": "PROPOSAL_ONLY_FRESH_PROSPECTIVE_OOT_REQUIRED",
        "failure_policy": FAIL_POLICY,
    }


def summary_md(stage1_result: dict[str, Any], stage3_result: dict[str, Any], stage4_result: dict[str, Any], provenance: dict[str, Any]) -> str:
    earliest = stage1_result["earliest_checkpoint_passing_60s_hold_research_gate_s"]
    passing_stage3 = [
        cell for cell in stage3_result["cells"] if cell["predeclared_research_gate"]
    ]
    passing_stage4 = [cell for cell in stage4_result["cells"] if cell["predeclared_research_gate"]]
    return f"""# NG exhaustion focused POX exact raw-tape results — 2026-08-19

Status: **EXACT MBP-10 EXECUTION PASS COMPLETE; NO PROMOTION**

- Fixed cases: {provenance['rows']:,} ({provenance['flip']:,} FLIP / {provenance['same']:,} SAME).
- Raw days: {', '.join(provenance['raw_days'])}.
- Pricing: long ask-to-bid and short bid-to-ask, using the first valid raw MBP-10 quote at or after the exact requested timestamp.
- Approximate chart/derived paths used: no.

## Stage 1

- Earliest dense checkpoint passing the predeclared 60-second-hold execution research gate: `{earliest}` seconds.
- Gross results already include displayed spread; 0.5/1.0/2.0-tick fields impose additional round-trip stress.
- Losing, zero, choppy, unavailable, and non-executable cases remain in the row ledger.

## Stage 3

- Branch actions begin only at successor frozen-detector causal confirmation.
- Stage-3 action/hold cells passing the research gate: {len(passing_stage3)}.
- A successor is treated as a fresh state; old ancestry is not inherited and universal exit/reversal is not promoted.

## Stage 4

- Delayed SAME cases after the parent +60 boundary: {stage4_result['delayed_same_n']:,}.
- Later SAME-successor cells passing the research gate: {len(passing_stage4)}.
- The original parent outcome is preserved. Recovery alone never authorizes automatic re-entry.

## Boundary

- No permanent brain merge, strategy merge, live play, or promotion was performed.
- Fresh prospective/OOT validation remains required.
- D0-D5 incremental crosswalk remains deferred until the standalone POX outputs are frozen.
"""


def finalize_rule_ledger(out_dir: Path, stage1_result: dict[str, Any], stage3_result: dict[str, Any], stage4_result: dict[str, Any]) -> list[dict[str, Any]]:
    path = out_dir / "NG_EXHAUSTION_POX_FAILED_CONDITIONAL_RULES_20260819.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    replaced = {
        "GENERIC_IMMEDIATE_POX_EXECUTION",
        "UNIVERSAL_SUCCESSOR_CONFIRMATION_EXIT_OR_REVERSAL",
        "AUTOMATIC_DELAYED_SAME_REENTRY",
    }
    rows = [row for row in existing if row.get("rule_id") not in replaced]
    for cell in stage1_result["cells"]:
        rows.append(
            {
                "rule_id": f"STAGE1_H{cell['checkpoint_s']}_HOLD{cell['fixed_hold_s']}",
                "status": "PASSED_RESEARCH_GATE" if cell["predeclared_research_gate"] else "FAILED_EXECUTION_RESEARCH_GATE",
                "executed_n": cell["executed_n"],
                "disposition": FAIL_POLICY,
                "promotion": False,
            }
        )
    for cell in stage3_result["cells"]:
        rows.append(
            {
                "rule_id": f"STAGE3_{cell['action']}_HOLD{cell['fixed_hold_from_branch_confirmation_s']}",
                "status": "PASSED_RESEARCH_GATE" if cell["predeclared_research_gate"] else "FAILED_EXECUTION_RESEARCH_GATE",
                "executed_n": cell["executed_n"],
                "disposition": FAIL_POLICY,
                "promotion": False,
            }
        )
    rows.extend(
        [
            {
                "rule_id": "UNIVERSAL_SUCCESSOR_CONFIRMATION_EXIT_OR_REVERSAL",
                "status": stage3_result["parent_exit_comparison"]["status"],
                "promoted": False,
                "disposition": FAIL_POLICY,
            },
            {
                "rule_id": "AUTOMATIC_DELAYED_SAME_REENTRY",
                "status": "REJECTED_BY_PROTOCOL; LATER_CONFIRMED_SUCCESSOR_TESTED_ONLY_AS_FRESH_STATE",
                "promoted": False,
                "disposition": FAIL_POLICY,
            },
        ]
    )
    for cell in stage4_result["cells"]:
        rows.append(
            {
                "rule_id": f"STAGE4_DELAYED_SAME_FRESH_SUCCESSOR_HOLD{cell['fixed_hold_from_later_same_successor_confirmation_s']}",
                "status": "PASSED_RESEARCH_GATE" if cell["predeclared_research_gate"] else "FAILED_EXECUTION_RESEARCH_GATE",
                "executed_n": cell["executed_n"],
                "disposition": FAIL_POLICY,
                "promotion": False,
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cases = read_jsonl(args.enriched_ledger)
    validate_ledger(cases)
    raw_paths = sorted(args.raw_dir.glob("NG_*.jsonl.gz"))
    tapes = {day_from_name(path): load_quote_tape(path) for path in raw_paths}
    required_days = sorted({case["clock"]["day"] for case in cases})
    if sorted(tapes) != required_days:
        raise RuntimeError(f"raw-day mismatch: required={required_days} supplied={sorted(tapes)}")

    stage1_result, stage1_rows = stage1(cases, tapes)
    checkpoint = stage1_result["earliest_checkpoint_passing_60s_hold_research_gate_s"]
    stage3_result, stage3_rows = stage3(cases, tapes, checkpoint)
    stage4_result = stage4(cases, stage3_rows, checkpoint, tapes)
    provenance = {
        "status": "AUTHORITATIVE_RAW_MBP10_JOIN_VALIDATED",
        "population_policy": POLICY,
        "rows": len(cases),
        "flip": EXPECTED_FLIP,
        "same": EXPECTED_SAME,
        "enriched_ledger": {"name": args.enriched_ledger.name, "sha256": sha256(args.enriched_ledger)},
        "raw_days": required_days,
        "raw_files": {
            day: {
                "name": next(path.name for path in raw_paths if day_from_name(path) == day),
                "sha256": sha256(next(path for path in raw_paths if day_from_name(path) == day)),
                "raw_rows": tapes[day].raw_rows,
                "valid_quote_rows": len(tapes[day].rows),
            }
            for day in required_days
        },
        "membership_changes": 0,
        "label_changes": 0,
        "chart_or_derived_price_substitution": False,
        "tick_size": TICK,
    }
    write_json(args.out_dir / "NG_EXHAUSTION_POX_RAW_EXECUTION_PROVENANCE_20260819.json", provenance)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_STAGE1_INITIAL_CONTINUATION_EXECUTION_20260819.json", stage1_result)
    write_jsonl_gz(args.out_dir / "NG_EXHAUSTION_POX_STAGE1_EXECUTION_ROWS_20260819.jsonl.gz", stage1_rows)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_STAGE3_SUCCESSOR_ACTION_ECONOMICS_20260819.json", stage3_result)
    write_jsonl_gz(args.out_dir / "NG_EXHAUSTION_POX_STAGE3_ACTION_ROWS_20260819.jsonl.gz", stage3_rows)
    write_json(args.out_dir / "NG_EXHAUSTION_POX_STAGE4_DELAYED_SAME_REEXPRESSION_20260819.json", stage4_result)
    write_json(
        args.out_dir / "NG_EXHAUSTION_POX_FAILED_CONDITIONAL_RULES_20260819.json",
        finalize_rule_ledger(args.out_dir, stage1_result, stage3_result, stage4_result),
    )
    (args.out_dir / "NG_EXHAUSTION_POX_RAW_EXECUTION_RESULTS_20260819.md").write_text(
        summary_md(stage1_result, stage3_result, stage4_result, provenance), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": "POX_EXACT_RAW_EXECUTION_PASS_COMPLETE",
                "rows": len(cases),
                "earliest_stage1_checkpoint_s": checkpoint,
                "stage1_rows": len(stage1_rows),
                "stage3_rows": len(stage3_rows),
                "delayed_same_n": stage4_result["delayed_same_n"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
