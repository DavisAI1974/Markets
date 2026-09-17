#!/usr/bin/env python3
"""Event-driven/no-clock POX action gate.

This is the replacement entry point for focused POX timing. It deliberately
contains no checkpoint cadence, entry-delay grid, hold horizon, timeout exit,
or fixed temporal lookback. Decisions arrive as causal events with their exact
timestamps. Raw execution, when attached, must fill at the first eligible raw
quote/trade at or after that event timestamp.

The current research line remains fail-closed until the authoritative
3,429 / 1,444 / 1,985 case ledger is supplied.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

EXPECTED_TOTAL = 3429
EXPECTED_FLIP = 1444
EXPECTED_SAME = 1985
POPULATION_POLICY = "FIXED_3429_DO_NOT_REOPEN"
TIMING_POLICY = "EVENT_DRIVEN_NO_FIXED_INTERVALS"

CASE_ID_KEYS = ("case_id", "pox_case_id", "event_id", "id")
BRANCH_KEYS = ("branch_label", "branch", "later_branch", "successor_branch")
TIMESTAMP_KEYS = ("event_ts_ns", "timestamp_ns", "ts_recv_ns", "event_timestamp_ns")
ALLOWED_ACTIONS = {
    "NO_CALL",
    "SIGNAL",
    "OPEN",
    "CONTINUE",
    "CLOSE",
    "REVERSE",
    "SUCCESSOR",
    "REORIGIN",
    "STAND_DOWN",
}

FORBIDDEN_TIMING_KEY_FRAGMENTS = (
    "checkpoint_s",
    "delay_s",
    "hold_s",
    "horizon_s",
    "timeout_s",
    "window_s",
    "cadence_s",
    "retry_s",
    "sleep_s",
    "elapsed_trigger",
    "time_trigger",
)


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    with _open_text(path) as f:
        is_jsonl = path.name.lower().endswith((".jsonl", ".jsonl.gz", ".ndjson", ".ndjson.gz"))
        first = f.read(1)
        f.seek(0)
        if not is_jsonl and first in ("[", "{"):
            obj = json.load(f)
            if isinstance(obj, list):
                rows = obj
            elif isinstance(obj, dict):
                rows = obj.get("rows") or obj.get("cases") or obj.get("events") or obj.get("ledger")
                if rows is None:
                    raise RuntimeError("JSON object must contain rows/cases/events/ledger")
            else:
                raise RuntimeError("unsupported JSON container")
            for row in rows:
                if not isinstance(row, dict):
                    raise RuntimeError("all rows must be JSON objects")
                yield row
            return

        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"line {lineno} is not a JSON object")
            yield row


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _find_forbidden_timing_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key).lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if any(fragment in name for fragment in FORBIDDEN_TIMING_KEY_FRAGMENTS):
                found.append(path)
            found.extend(_find_forbidden_timing_keys(child, path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found.extend(_find_forbidden_timing_keys(child, f"{prefix}[{i}]"))
    return found


def load_fixed_ledger(path: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for idx, row in enumerate(_iter_rows(path)):
        case_id_raw = _pick(row, CASE_ID_KEYS)
        label_raw = _pick(row, BRANCH_KEYS)
        if case_id_raw is None:
            raise RuntimeError(f"ledger row {idx} missing stable case id")
        if label_raw is None:
            raise RuntimeError(f"ledger row {idx} missing authoritative branch label")
        case_id = str(case_id_raw)
        label = str(label_raw).upper().strip()
        if label not in {"FLIP", "SAME"}:
            raise RuntimeError(f"ledger case {case_id} has invalid branch label {label!r}")
        if case_id in cases:
            raise RuntimeError(f"duplicate ledger case id: {case_id}")
        cases[case_id] = row
        counts[label] += 1

    observed = (len(cases), counts["FLIP"], counts["SAME"])
    expected = (EXPECTED_TOTAL, EXPECTED_FLIP, EXPECTED_SAME)
    if observed != expected:
        raise RuntimeError(
            "authoritative fixed-ledger invariant failed: "
            f"observed total/flip/same={observed}, expected={expected}. "
            "Fail closed; do not reconstruct or relabel the population."
        )
    return cases


def validate_causal_actions(
    path: Path, cases: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    per_case_last_ts: dict[str, int] = {}
    per_case_last_seq: dict[str, int] = {}
    cases_with_events: set[str] = set()
    action_counts: Counter[str] = Counter()

    for idx, row in enumerate(_iter_rows(path)):
        forbidden = _find_forbidden_timing_keys(row)
        if forbidden:
            raise RuntimeError(
                f"decision row {idx} contains forbidden clock-driven key(s): {forbidden}. "
                "Timing must be caused by causal market/state events, not elapsed intervals."
            )

        case_id_raw = _pick(row, CASE_ID_KEYS)
        if case_id_raw is None:
            raise RuntimeError(f"decision row {idx} missing case id")
        case_id = str(case_id_raw)
        if case_id not in cases:
            raise RuntimeError(
                f"decision row {idx} references unknown case {case_id}; "
                "decision events cannot add population members"
            )

        ts_raw = _pick(row, TIMESTAMP_KEYS)
        if ts_raw is None:
            raise RuntimeError(f"decision row {idx} case {case_id} missing exact causal timestamp_ns")
        try:
            ts_ns = int(ts_raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"decision row {idx} case {case_id} invalid timestamp {ts_raw!r}") from exc

        action = str(row.get("action", "")).upper().strip()
        if action not in ALLOWED_ACTIONS:
            raise RuntimeError(
                f"decision row {idx} case {case_id} invalid action {action!r}; "
                f"allowed={sorted(ALLOWED_ACTIONS)}"
            )

        seq_raw = row.get("event_seq")
        if seq_raw is None:
            raise RuntimeError(f"decision row {idx} case {case_id} missing event_seq")
        try:
            seq = int(seq_raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"decision row {idx} case {case_id} invalid event_seq {seq_raw!r}") from exc

        if case_id in per_case_last_ts and ts_ns < per_case_last_ts[case_id]:
            raise RuntimeError(f"case {case_id} causal timestamps moved backward")
        if case_id in per_case_last_seq and seq <= per_case_last_seq[case_id]:
            raise RuntimeError(f"case {case_id} event_seq must be strictly increasing")

        per_case_last_ts[case_id] = ts_ns
        per_case_last_seq[case_id] = seq
        cases_with_events.add(case_id)
        action_counts[action] += 1

        normalized = dict(row)
        normalized["case_id"] = case_id
        normalized["event_ts_ns"] = ts_ns
        normalized["event_seq"] = seq
        normalized["action"] = action
        normalized["timing_policy"] = TIMING_POLICY
        events.append(normalized)

    summary = {
        "timing_policy": TIMING_POLICY,
        "population_policy": POPULATION_POLICY,
        "case_count": len(cases),
        "cases_with_causal_action_events": len(cases_with_events),
        "cases_without_causal_action_events": len(cases) - len(cases_with_events),
        "causal_action_event_count": len(events),
        "action_counts": dict(sorted(action_counts.items())),
        "fixed_checkpoint_grid_used": False,
        "fixed_entry_delay_grid_used": False,
        "fixed_hold_horizons_used": False,
        "fixed_timeout_exit_used": False,
        "fixed_temporal_lookback_gate_used": False,
        "elapsed_time_decision_trigger_used": False,
        "historical_plus60_role": "DIAGNOSTIC_LABEL_CONTEXT_ONLY_NOT_A_DECISION_TIMER",
        "raw_execution_rule": "FIRST_ELIGIBLE_RAW_QUOTE_OR_TRADE_AT_OR_AFTER_EXACT_CAUSAL_ACTION_TIMESTAMP",
    }
    return events, summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate event-driven/no-clock POX causal action events")
    ap.add_argument("--ledger", required=True, help="authoritative fixed 3,429 case ledger")
    ap.add_argument("--decision-events", required=True, help="causal action event JSON/JSONL ledger")
    ap.add_argument("--out", required=True, help="validation output JSON")
    args = ap.parse_args()

    ledger = Path(args.ledger)
    decisions = Path(args.decision_events)
    if not ledger.is_file():
        raise RuntimeError(f"ledger not found: {ledger}")
    if not decisions.is_file():
        raise RuntimeError(f"decision events not found: {decisions}")

    cases = load_fixed_ledger(ledger)
    _, summary = validate_causal_actions(decisions, cases)
    result = {
        "status": "POX_EVENT_DRIVEN_ACTIONS_VALIDATED",
        "summary": summary,
        "execution_status": "RAW_FILL_ATTACHMENT_PENDING; NO_FIXED_INTERVAL_FALLBACK_AUTHORIZED",
        "promotion_performed": False,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
