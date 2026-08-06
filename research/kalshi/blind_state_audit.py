#!/usr/bin/env python3
"""Strict blind-wall audit for NG forecaster decision-state artifacts.

This module does not create a new signal. It validates and sanitizes the existing
forecast_harness.decision_state output before a blind agent can consume it.

The raw historical stores remain untouched. All gates are applied on the forecast
read path, consistent with the platform rule that ingestion stays raw.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

# These fields describe when a datum became knowable. Future target dates, forecast
# horizons, scheduled print dates, and contract expiries are intentionally excluded.
_TIMESTAMP_KEY = re.compile(
    r"(^|_)(asof|as_of|publication|published|snapshot|knowable_from|available_at|"
    r"release_ts|runtime_utc|max_cycle_runtime|capture_utc|generated_at)(_|$)",
    re.IGNORECASE,
)

# Same-day realized observations are not valid inputs to a forecast issued before
# the session. They can remain in research/refine artifacts, but not in blind state.
_FORBIDDEN_BLIND_PATHS = {
    "weather": "same-day realized weather proxy is not blind evidence",
}

# Source labels that explicitly disclose a post-event/final-vintage value.
_POST_EVENT_SOURCE_WORDS = (
    "final_frozen",
    "post_print",
    "post-print",
    "first post-print",
    "current_vintage_only",
)


def _parse_time(value: Any) -> dt.datetime | None:
    if value is None or isinstance(value, (bool, int, float)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{14}", text):
        try:
            return dt.datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return dt.datetime.strptime(text, "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def issue_cutoff(day8: str, issue_time_et: str = "08:00") -> dt.datetime:
    """Return the default blind issue cutoff for a session date.

    Sunday session dates use the 18:00 ET reopen. Weekdays default to 08:00 ET,
    before the liquid US session. The caller may pass another explicit issue time.
    """
    day = dt.date(int(day8[:4]), int(day8[4:6]), int(day8[6:8]))
    if day.weekday() == 6 and issue_time_et == "08:00":
        hh, mm = 18, 0
    else:
        hh, mm = (int(x) for x in issue_time_et.split(":"))
    local = dt.datetime.combine(day, dt.time(hh, mm), tzinfo=ET)
    return local.astimezone(UTC)


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            child_path = path + (str(idx),)
            yield child_path, child
            yield from _walk(child, child_path)


def _violation(day: str, path: tuple[str, ...], rule: str, value: Any) -> dict[str, Any]:
    return {
        "day": day,
        "path": ".".join(path),
        "rule": rule,
        "value": value,
    }


def audit_day(day8: str, state: dict[str, Any], issue_time_et: str = "08:00") -> dict[str, Any]:
    cutoff = issue_cutoff(day8, issue_time_et)
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for top_key, reason in _FORBIDDEN_BLIND_PATHS.items():
        if state.get(top_key) is not None:
            violations.append(_violation(day8, (top_key,), reason, "present"))

    for path, value in _walk(state):
        key = path[-1]
        if _TIMESTAMP_KEY.search(key):
            parsed = _parse_time(value)
            if parsed is not None and parsed > cutoff:
                violations.append(
                    _violation(
                        day8,
                        path,
                        f"datum timestamp {parsed.isoformat()} is after blind cutoff {cutoff.isoformat()}",
                        value,
                    )
                )

        if key == "final_capture_is_post_print" and value is True:
            violations.append(
                _violation(day8, path, "post-print final capture is not decision-time evidence", value)
            )
        if key == "pre_print" and value is False and "storage_consensus" in path:
            violations.append(
                _violation(day8, path, "post-print consensus observation is not blind evidence", value)
            )
        if key in {"source", "how", "note"} and isinstance(value, str):
            low = value.lower()
            if "storage_consensus" in path and any(word in low for word in _POST_EVENT_SOURCE_WORDS):
                violations.append(
                    _violation(day8, path, "source text discloses a post-event/final vintage", value)
                )

    # Missing data is valid but must remain visible. NaN and infinities are not valid
    # JSON evidence and are called out separately.
    for path, value in _walk(state):
        if isinstance(value, float) and not math.isfinite(value):
            violations.append(_violation(day8, path, "non-finite numeric state", value))
        if path[-1] in {"as_of", "asof", "asof_utc", "publication_ts"} and value is None:
            warnings.append(_violation(day8, path, "missing provenance timestamp", value))

    return {
        "day": day8,
        "issue_cutoff_utc": cutoff.isoformat(),
        "passed": not violations,
        "violations": violations,
        "warnings": warnings,
    }


def audit_state(payload: dict[str, Any], issue_time_et: str = "08:00") -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    for key, state in payload.items():
        if re.fullmatch(r"\d{8}", str(key)) and isinstance(state, dict):
            days.append(audit_day(str(key), state, issue_time_et))
    violations = [v for day in days for v in day["violations"]]
    warnings = [v for day in days for v in day["warnings"]]
    return {
        "schema": "blind_state_audit.v1",
        "passed": not violations,
        "n_days": len(days),
        "n_violations": len(violations),
        "n_warnings": len(warnings),
        "days": days,
        "violations": violations,
        "warnings": warnings,
    }


def _set_path(root: Any, path: list[str], value: Any) -> None:
    node = root
    for part in path[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = path[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def sanitize_state(payload: dict[str, Any], issue_time_et: str = "08:00") -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copy with violating leaves nulled and a visible audit block.

    The raw source file is never modified. A sanitized artifact is written only when
    explicitly requested by the caller.
    """
    clean = copy.deepcopy(payload)
    report = audit_state(clean, issue_time_et)
    for item in report["violations"]:
        day = item["day"]
        path = item["path"].split(".")
        if day not in clean:
            continue
        try:
            _set_path(clean[day], path, None)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    clean["_blind_audit"] = {
        "schema": report["schema"],
        "passed": report["passed"],
        "n_violations_removed": report["n_violations"],
        "n_warnings": report["n_warnings"],
        "violations": report["violations"],
        "note": "violating leaves are null in this sanitized blind artifact; raw stores are unchanged",
    }
    return clean, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an NG decision-state file for blind-wall leakage")
    parser.add_argument("--state", required=True, help="decision-state JSON path")
    parser.add_argument("--issue-time-et", default="08:00")
    parser.add_argument("--report-out")
    parser.add_argument("--sanitize-out")
    parser.add_argument("--strict", action="store_true", help="exit nonzero when violations exist")
    args = parser.parse_args()

    payload = json.loads(Path(args.state).read_text(encoding="utf-8"))
    clean, report = sanitize_state(payload, args.issue_time_et)
    if args.report_out:
        Path(args.report_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.sanitize_out:
        Path(args.sanitize_out).write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
