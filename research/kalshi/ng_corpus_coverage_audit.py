#!/usr/bin/env python3
"""Audit the broad NG historical corpus and exact G15/G16 replay intersections.

The audit has two separate responsibilities and never conflates them:

1. Verify the declared layout of the one-year L1/dense-trades corpus and the
   spring/summer MBO corpus. A broad corpus is ``VERIFIED_COMPLETE`` only when
   an inspected inventory supplies an explicit expected-day list, every expected
   day is represented by at least one valid PRESENT object, object counts agree,
   and the declared date window is exact.
2. Build the exact daily L1+MBO intersection required by G15 and G16, keyed by
   dataset, publisher, instrument, raw symbol, definition period, and event time.

UNKNOWN remote state remains UNKNOWN. A path pattern, bucket name, or upstream
claim is never treated as evidence that an object exists. This module is
metadata-only, outcome-blind, SHADOW-only, and cannot mutate the blind forecast,
``knowledge/ng_brain.json``, or execution state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "ng_corpus_coverage_audit.v1"
CATALOG_SCHEMA = "ng_corpus_catalog.v1"
DATASET = "GLBX.MDP3"
LANES = ("l1_trades", "mbo")
STATUSES = {"PRESENT", "MISSING", "CORRUPT", "UNKNOWN"}

L1_CORPUS_ID = "l1_dense_one_year"
MBO_CORPUS_ID = "mbo_spring_summer"
EXPECTED_WINDOWS = {
    L1_CORPUS_ID: {
        "start": "2025-07-01",
        "end_exclusive": "2026-07-01",
        "lane": "l1_trades",
    },
    MBO_CORPUS_ID: {
        "start": "2026-03-01",
        "end_exclusive": "2026-07-01",
        "lane": "mbo",
    },
}

G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
G16_DATES = (
    "20260329", "20260330", "20260331", "20260401", "20260402",
    "20260405", "20260406", "20260407", "20260408", "20260409", "20260410",
)
G15_CONTRACT_MAP = {
    day: {
        "raw_symbol": "NGJ26" if day <= "20260319" else "NGK26",
        "instrument_id": 1008 if day <= "20260319" else 996,
    }
    for day in G15_DATES
}
G16_CONTRACT_MAP = {
    day: {"raw_symbol": "NGK26", "instrument_id": 996}
    for day in G16_DATES
}
TARGETS = {15: (G15_DATES, G15_CONTRACT_MAP), 16: (G16_DATES, G16_CONTRACT_MAP)}


class CorpusCoverageError(ValueError):
    """Raised for malformed, contradictory, or tampered corpus metadata."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def _day(value: Any) -> str:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        return ""
    try:
        date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return ""
    return text


def _verify_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusCoverageError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def expected_catalog_template(*, publisher_id: int | None = None) -> dict[str, Any]:
    """Return a truthful UNKNOWN template; it asserts no remote object presence."""
    corpora = []
    for corpus_id, expected in EXPECTED_WINDOWS.items():
        corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "declared_window": {
                    "start": expected["start"],
                    "end_exclusive": expected["end_exclusive"],
                },
                "publisher_id": publisher_id,
                "remote_inventory_verified": False,
                "inventory_complete": False,
                "expected_object_count": None,
                "observed_object_count": None,
                "expected_days": [],
                "inventory_observed_at": None,
                "entries": [],
                "note": "UNKNOWN until concrete local/AWS/S3 objects are inspected.",
            }
        )
    value = {
        "schema": CATALOG_SCHEMA,
        "market": "NG",
        "dataset": DATASET,
        "corpora": corpora,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
    }
    value["catalog_fingerprint"] = _fp(value)
    return value


def _validate_entry(
    entry: Mapping[str, Any], *, lane: str, corpus_id: str, index: int
) -> tuple[dict[str, Any], list[str]]:
    row = copy.deepcopy(dict(entry))
    prefix = f"{corpus_id}:{lane}:entry[{index}]"
    errors: list[str] = []
    status = str(row.get("status") or "UNKNOWN").upper()
    if status not in STATUSES:
        errors.append(f"{prefix}: invalid status {status!r}")
    row["status"] = status

    row_day = _day(row.get("day") or row.get("date") or row.get("session_day"))
    if not row_day:
        errors.append(f"{prefix}: invalid or missing day")
    row["day"] = row_day

    source_id = str(row.get("source_id") or row.get("location") or "").strip()
    if not source_id:
        errors.append(f"{prefix}: source_id or location is required")
    row["source_id"] = source_id

    row_lane = str(row.get("lane") or row.get("source_kind") or lane)
    if row_lane != lane:
        errors.append(f"{prefix}: lane {row_lane!r} differs from corpus lane {lane!r}")
    row["lane"] = lane

    if status == "PRESENT":
        required = (
            "location", "dataset", "publisher_id", "instrument_id", "raw_symbol",
            "definition_date", "definition_start_s", "definition_end_s",
            "event_start_s", "event_end_s", "record_count", "size_bytes",
            "sha256", "inventory_observed_at",
        )
        missing = [field for field in required if row.get(field) in (None, "")]
        if missing:
            errors.append(f"{prefix}: PRESENT entry missing {', '.join(missing)}")
        if row.get("dataset") != DATASET:
            errors.append(f"{prefix}: dataset must be {DATASET}")
        try:
            row["publisher_id"] = int(row.get("publisher_id"))
            row["instrument_id"] = int(row.get("instrument_id"))
        except (TypeError, ValueError, OverflowError):
            errors.append(f"{prefix}: publisher_id and instrument_id must be integers")

        definition_start = _finite(row.get("definition_start_s"))
        definition_end = _finite(row.get("definition_end_s"))
        event_start = _finite(row.get("event_start_s"))
        event_end = _finite(row.get("event_end_s"))
        if None in (definition_start, definition_end, event_start, event_end):
            errors.append(f"{prefix}: definition and event ranges must be finite")
        else:
            row["definition_start_s"] = definition_start
            row["definition_end_s"] = definition_end
            row["event_start_s"] = event_start
            row["event_end_s"] = event_end
            if definition_end < definition_start:
                errors.append(f"{prefix}: definition period is backwards")
            if event_end < event_start:
                errors.append(f"{prefix}: event range is backwards")
            if event_start < definition_start or event_end > definition_end:
                errors.append(f"{prefix}: event range falls outside definition period")
        if _positive_int(row.get("record_count")) is None:
            errors.append(f"{prefix}: record_count must be positive")
        if _positive_int(row.get("size_bytes")) is None:
            errors.append(f"{prefix}: size_bytes must be positive")
        sha = str(row.get("sha256") or "")
        if len(sha) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in sha
        ):
            errors.append(f"{prefix}: sha256 must contain 64 hexadecimal characters")
    elif status == "UNKNOWN":
        row.setdefault("observation_error", "remote or local object not inspected")

    return row, errors


def _identity_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("dataset"),
        row.get("publisher_id"),
        row.get("instrument_id"),
        row.get("raw_symbol"),
        row.get("definition_date"),
        row.get("definition_start_s"),
        row.get("definition_end_s"),
    )


def _coverage_status(
    corpus: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    corpus_id = str(corpus.get("corpus_id") or "")
    expected = EXPECTED_WINDOWS[corpus_id]
    expected_days_raw = list(corpus.get("expected_days") or [])
    expected_days: list[str] = []
    for raw in expected_days_raw:
        value = _day(raw)
        if not value:
            errors.append(f"{corpus_id}: invalid expected day {raw!r}")
        else:
            expected_days.append(value)
    if len(expected_days) != len(set(expected_days)):
        errors.append(f"{corpus_id}: expected_days contains duplicates")
    expected_days = sorted(set(expected_days))

    by_day: dict[str, list[Mapping[str, Any]]] = {}
    for row in entries:
        by_day.setdefault(str(row.get("day") or ""), []).append(row)
    present_days = sorted(
        day
        for day, rows in by_day.items()
        if any(str(row.get("status")) == "PRESENT" for row in rows)
    )
    missing_expected_days = [day for day in expected_days if day not in present_days]
    unexpected_days = [
        day for day in present_days if expected_days and day not in expected_days
    ]

    expected_count = _positive_int(corpus.get("expected_object_count"))
    observed_count = _positive_int(corpus.get("observed_object_count"))
    present_count = sum(1 for row in entries if row.get("status") == "PRESENT")
    non_present = [
        row["source_id"] for row in entries if row.get("status") != "PRESENT"
    ]
    complete_claim = corpus.get("inventory_complete") is True
    remote_verified = corpus.get("remote_inventory_verified") is True
    counts_match = (
        expected_count is not None
        and observed_count is not None
        and expected_count == observed_count == len(entries)
    )
    exact_days_declared = bool(expected_days)
    complete = bool(
        complete_claim
        and remote_verified
        and counts_match
        and exact_days_declared
        and not missing_expected_days
        and not unexpected_days
        and not non_present
        and present_count == len(entries)
        and not errors
    )

    identity_groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in entries:
        if row.get("status") == "PRESENT":
            identity_groups.setdefault(_identity_key(row), []).append(row)
    identity_partitions = []
    for key, rows in sorted(
        identity_groups.items(),
        key=lambda item: tuple(str(value) for value in item[0]),
    ):
        (
            dataset,
            publisher_id,
            instrument_id,
            raw_symbol,
            definition_date,
            definition_start_s,
            definition_end_s,
        ) = key
        days = sorted({str(row.get("day") or "") for row in rows})
        identity_partitions.append(
            {
                "dataset": dataset,
                "publisher_id": publisher_id,
                "instrument_id": instrument_id,
                "raw_symbol": raw_symbol,
                "definition_date": definition_date,
                "definition_start_s": definition_start_s,
                "definition_end_s": definition_end_s,
                "object_count": len(rows),
                "first_day": days[0] if days else None,
                "last_day": days[-1] if days else None,
            }
        )
    non_exact_raw_symbols = sorted(
        {
            str(row.get("raw_symbol") or "")
            for row in entries
            if row.get("status") == "PRESENT"
            and not re.fullmatch(
                r"NG[A-Z][0-9]{2}", str(row.get("raw_symbol") or "")
            )
        }
    )

    if complete:
        status = "VERIFIED_COMPLETE"
    elif complete_claim and (
        not remote_verified
        or not counts_match
        or not exact_days_declared
        or missing_expected_days
        or non_present
    ):
        status = "CONTRADICTORY_COMPLETE_CLAIM"
    elif any(row.get("status") == "CORRUPT" for row in entries):
        status = "CORRUPT"
    elif any(row.get("status") == "MISSING" for row in entries):
        status = "INCOMPLETE"
    elif any(row.get("status") == "UNKNOWN" for row in entries) or not entries:
        status = "UNKNOWN"
    else:
        status = "PARTIAL"

    return {
        "corpus_id": corpus_id,
        "lane": expected["lane"],
        "declared_window": copy.deepcopy(dict(corpus.get("declared_window") or {})),
        "status": status,
        "remote_inventory_verified": remote_verified,
        "inventory_complete_claimed": complete_claim,
        "expected_object_count": expected_count,
        "observed_object_count": observed_count,
        "catalog_entry_count": len(entries),
        "present_object_count": present_count,
        "expected_day_count": len(expected_days),
        "present_day_count": len(present_days),
        "missing_expected_days": missing_expected_days,
        "unexpected_present_days": unexpected_days,
        "non_present_source_ids": non_present,
        "first_present_day": present_days[0] if present_days else None,
        "last_present_day": present_days[-1] if present_days else None,
        "inventory_observed_at": corpus.get("inventory_observed_at"),
        "completeness_basis": "EXPLICIT_EXPECTED_DAY_LIST_AND_OBJECT_COUNTS",
        "identity_partitions": identity_partitions,
        "non_exact_raw_symbols": non_exact_raw_symbols,
    }


def _candidate_reason(
    rows: Sequence[Mapping[str, Any]], expected: Mapping[str, Any]
) -> str:
    statuses = {str(row.get("status") or "UNKNOWN") for row in rows}
    if "CORRUPT" in statuses:
        return "CORRUPT_SOURCE"
    present = [row for row in rows if row.get("status") == "PRESENT"]
    if present:
        exact = [
            row
            for row in present
            if row.get("dataset") == DATASET
            and row.get("raw_symbol") == expected["raw_symbol"]
            and row.get("instrument_id") == expected["instrument_id"]
        ]
        return "EXACT_PRESENT" if exact else "WRONG_BASIS_PRESENT"
    if "UNKNOWN" in statuses or not rows:
        return "UNKNOWN"
    if "MISSING" in statuses:
        return "MISSING"
    return "UNAVAILABLE"


def _select_pair(
    day: str,
    expected: Mapping[str, Any],
    by_lane_day: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    lanes: dict[str, Any] = {}
    exact_candidates: dict[str, list[Mapping[str, Any]]] = {}
    for lane in LANES:
        rows = list(by_lane_day.get((lane, day), ()))
        reason = _candidate_reason(rows, expected)
        exact = [
            row
            for row in rows
            if row.get("status") == "PRESENT"
            and row.get("dataset") == DATASET
            and row.get("raw_symbol") == expected["raw_symbol"]
            and row.get("instrument_id") == expected["instrument_id"]
        ]
        exact_candidates[lane] = exact
        lanes[lane] = {
            "reason": reason,
            "candidate_source_ids": sorted(
                str(row.get("source_id")) for row in rows
            ),
            "exact_source_ids": sorted(
                str(row.get("source_id")) for row in exact
            ),
        }

    l1_rows = exact_candidates["l1_trades"]
    mbo_rows = exact_candidates["mbo"]
    compatible: list[
        tuple[float, str, str, Mapping[str, Any], Mapping[str, Any]]
    ] = []
    rejected: list[dict[str, Any]] = []
    for l1 in l1_rows:
        for mbo in mbo_rows:
            if _identity_key(l1) != _identity_key(mbo):
                rejected.append(
                    {
                        "l1_source_id": l1["source_id"],
                        "mbo_source_id": mbo["source_id"],
                        "reason": "definition_or_publisher_mismatch",
                    }
                )
                continue
            overlap_start = max(
                float(l1["event_start_s"]), float(mbo["event_start_s"])
            )
            overlap_end = min(
                float(l1["event_end_s"]), float(mbo["event_end_s"])
            )
            if overlap_end < overlap_start:
                rejected.append(
                    {
                        "l1_source_id": l1["source_id"],
                        "mbo_source_id": mbo["source_id"],
                        "reason": "event_time_no_overlap",
                    }
                )
                continue
            duration = overlap_end - overlap_start
            compatible.append(
                (
                    duration,
                    str(l1["source_id"]),
                    str(mbo["source_id"]),
                    l1,
                    mbo,
                )
            )

    compatible.sort(key=lambda item: (-item[0], item[1], item[2]))
    if compatible:
        duration, _, _, l1, mbo = compatible[0]
        overlap_start = max(
            float(l1["event_start_s"]), float(mbo["event_start_s"])
        )
        overlap_end = min(
            float(l1["event_end_s"]), float(mbo["event_end_s"])
        )
        status = "READY"
        blocker = None
        selected = {
            "l1_source_id": l1["source_id"],
            "mbo_source_id": mbo["source_id"],
            "dataset": l1["dataset"],
            "publisher_id": l1["publisher_id"],
            "instrument_id": l1["instrument_id"],
            "raw_symbol": l1["raw_symbol"],
            "definition_date": l1["definition_date"],
            "definition_start_s": l1["definition_start_s"],
            "definition_end_s": l1["definition_end_s"],
            "overlap_start_s": overlap_start,
            "overlap_end_s": overlap_end,
            "overlap_duration_s": duration,
        }
    else:
        selected = None
        reasons = {lane: lanes[lane]["reason"] for lane in LANES}
        if any(reason == "CORRUPT_SOURCE" for reason in reasons.values()):
            status, blocker = "BLOCKED", "CORRUPT_SOURCE"
        elif any(reason == "WRONG_BASIS_PRESENT" for reason in reasons.values()):
            status, blocker = "BLOCKED", "WRONG_BASIS_PRESENT"
        elif l1_rows and mbo_rows:
            status, blocker = "BLOCKED", "IDENTITY_OR_EVENT_TIME_MISMATCH"
        elif any(reason == "MISSING" for reason in reasons.values()):
            status, blocker = "BLOCKED", "MISSING_SOURCE"
        else:
            status, blocker = "UNKNOWN", "UNINSPECTED_SOURCE"

    return {
        "day": day,
        "expected_dataset": DATASET,
        "expected_raw_symbol": expected["raw_symbol"],
        "expected_instrument_id": expected["instrument_id"],
        "status": status,
        "blocker": blocker,
        "lanes": lanes,
        "selected_pair": selected,
        "rejected_pairings": rejected,
        "multiple_compatible_pairs": max(0, len(compatible) - 1),
    }


def build_audit(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Validate broad inventories and compute exact G15/G16 intersections."""
    source = copy.deepcopy(dict(catalog))
    _verify_fingerprint(source, "catalog_fingerprint", label="corpus catalog")
    if source.get("schema") != CATALOG_SCHEMA:
        raise CorpusCoverageError(f"catalog schema must be {CATALOG_SCHEMA}")
    if source.get("dataset") != DATASET:
        raise CorpusCoverageError(f"catalog dataset must be {DATASET}")
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "execution_authority",
    ):
        if source.get(field) is not False:
            raise CorpusCoverageError(f"catalog {field} must remain false")
    if source.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusCoverageError(
            "catalog CME event-contract mode must remain SHADOW"
        )

    by_corpus: dict[str, dict[str, Any]] = {}
    structural_errors: list[str] = []
    all_entries: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for raw in list(source.get("corpora") or []):
        if not isinstance(raw, Mapping):
            structural_errors.append("catalog contains a non-object corpus")
            continue
        corpus = copy.deepcopy(dict(raw))
        corpus_id = str(corpus.get("corpus_id") or "")
        if corpus_id not in EXPECTED_WINDOWS:
            structural_errors.append(f"unexpected corpus_id {corpus_id!r}")
            continue
        if corpus_id in by_corpus:
            structural_errors.append(f"duplicate corpus_id {corpus_id}")
            continue
        expected = EXPECTED_WINDOWS[corpus_id]
        if corpus.get("lane") != expected["lane"]:
            structural_errors.append(
                f"{corpus_id}: lane must be {expected['lane']}"
            )
        window = dict(corpus.get("declared_window") or {})
        canonical_window = {
            "start": expected["start"],
            "end_exclusive": expected["end_exclusive"],
        }
        if window != canonical_window:
            structural_errors.append(
                f"{corpus_id}: declared window differs from canonical layout"
            )

        entries: list[dict[str, Any]] = []
        corpus_errors: list[str] = []
        for index, raw_entry in enumerate(corpus.get("entries") or []):
            if not isinstance(raw_entry, Mapping):
                corpus_errors.append(f"{corpus_id}: entry[{index}] is not an object")
                continue
            entry, entry_errors = _validate_entry(
                raw_entry,
                lane=expected["lane"],
                corpus_id=corpus_id,
                index=index,
            )
            corpus_errors.extend(entry_errors)
            source_id = str(entry.get("source_id") or "")
            if source_id in source_ids:
                corpus_errors.append(
                    f"duplicate source_id across catalog: {source_id}"
                )
            else:
                source_ids.add(source_id)
            entries.append(entry)
            all_entries.append(entry)
        corpus["entries"] = entries
        corpus["validation_errors"] = corpus_errors
        by_corpus[corpus_id] = corpus

    missing_corpora = [
        corpus_id for corpus_id in EXPECTED_WINDOWS if corpus_id not in by_corpus
    ]
    if missing_corpora:
        structural_errors.append(
            "missing required corpora: " + ", ".join(missing_corpora)
        )

    coverage_reports: list[dict[str, Any]] = []
    for corpus_id in EXPECTED_WINDOWS:
        corpus = by_corpus.get(corpus_id)
        if corpus is None:
            continue
        local_errors = list(corpus.get("validation_errors") or [])
        report = _coverage_status(
            corpus, list(corpus.get("entries") or []), local_errors
        )
        report["validation_errors"] = local_errors
        coverage_reports.append(report)

    by_lane_day: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_entries:
        if row.get("day"):
            by_lane_day.setdefault(
                (str(row["lane"]), str(row["day"])), []
            ).append(row)

    group_reports: dict[str, Any] = {}
    for group, (dates, contract_map) in TARGETS.items():
        days = [
            _select_pair(day, contract_map[day], by_lane_day) for day in dates
        ]
        ready_days = [row["day"] for row in days if row["status"] == "READY"]
        unknown_days = [
            row["day"] for row in days if row["status"] == "UNKNOWN"
        ]
        blocked_days = [
            row["day"] for row in days if row["status"] == "BLOCKED"
        ]
        if len(ready_days) == len(dates):
            status = "MATCHED_L1_MBO_READY"
        elif blocked_days:
            status = "BLOCKED"
        elif unknown_days:
            status = "UNKNOWN"
        else:
            status = "PARTIAL"
        group_reports[f"g{group}"] = {
            "group": group,
            "status": status,
            "ready_days": ready_days,
            "unknown_days": unknown_days,
            "blocked_days": blocked_days,
            "day_reports": days,
            "can_run_exact_replay": status == "MATCHED_L1_MBO_READY",
        }

    corpus_statuses = {
        row["corpus_id"]: row["status"] for row in coverage_reports
    }
    target_statuses = {
        name: value["status"] for name, value in group_reports.items()
    }
    if structural_errors or any(
        row.get("validation_errors") for row in coverage_reports
    ):
        overall = "BLOCKED"
    elif all(
        status == "VERIFIED_COMPLETE" for status in corpus_statuses.values()
    ) and all(
        status == "MATCHED_L1_MBO_READY"
        for status in target_statuses.values()
    ):
        overall = "FULL_CORPUS_AND_G15_G16_EXACT_READY"
    elif all(
        status == "MATCHED_L1_MBO_READY"
        for status in target_statuses.values()
    ):
        overall = "G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED"
    elif any(status == "BLOCKED" for status in target_statuses.values()):
        overall = "BLOCKED"
    else:
        overall = "UNKNOWN"

    output = {
        "schema": SCHEMA,
        "status": overall,
        "market": "NG",
        "dataset": DATASET,
        "catalog_fingerprint": source["catalog_fingerprint"],
        "corpus_layout": coverage_reports,
        "exact_intersections": group_reports,
        "structural_errors": structural_errors,
        "unknown_is_not_present": True,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "options_lane_started": False,
        "next_permitted_stage": (
            "G15_AND_G16_EXACT_HISTORICAL_REPLAY"
            if all(
                value["can_run_exact_replay"]
                for value in group_reports.values()
            )
            else "OBSERVE_OR_REPAIR_EXACT_CORPUS_METADATA"
        ),
    }
    output["fingerprint"] = _fp(output)
    return output


def validate_audit(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify_fingerprint(
        value, "fingerprint", label="corpus coverage audit"
    )
    if checked.get("schema") != SCHEMA:
        raise CorpusCoverageError("audit schema mismatch")
    if checked.get("dataset") != DATASET:
        raise CorpusCoverageError("audit dataset mismatch")
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "execution_authority",
        "options_lane_started",
    ):
        if checked.get(field) is not False:
            raise CorpusCoverageError(f"audit {field} must remain false")
    if checked.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusCoverageError(
            "audit CME event-contract mode must remain SHADOW"
        )

    intersections = dict(checked.get("exact_intersections") or {})
    if set(intersections) != {"g15", "g16"}:
        raise CorpusCoverageError(
            "audit must contain G15 and G16 intersections"
        )
    for name, dates in (("g15", G15_DATES), ("g16", G16_DATES)):
        report = dict(intersections[name])
        rows = list(report.get("day_reports") or [])
        if [row.get("day") for row in rows] != list(dates):
            raise CorpusCoverageError(f"{name}: canonical day order mismatch")
        recomputed_ready = [
            row["day"] for row in rows if row.get("status") == "READY"
        ]
        if recomputed_ready != list(report.get("ready_days") or []):
            raise CorpusCoverageError(f"{name}: ready-day summary mismatch")
        if len(recomputed_ready) == len(dates):
            expected_status = "MATCHED_L1_MBO_READY"
        elif any(row.get("status") == "BLOCKED" for row in rows):
            expected_status = "BLOCKED"
        elif any(row.get("status") == "UNKNOWN" for row in rows):
            expected_status = "UNKNOWN"
        else:
            expected_status = "PARTIAL"
        if report.get("status") != expected_status:
            raise CorpusCoverageError(f"{name}: status mismatch")
        expected_authority = expected_status == "MATCHED_L1_MBO_READY"
        if report.get("can_run_exact_replay") is not expected_authority:
            raise CorpusCoverageError(f"{name}: replay authority mismatch")
    return checked


def _present_entry(
    *,
    lane: str,
    day: str,
    symbol: str,
    instrument_id: int,
    publisher_id: int = 1,
) -> dict[str, Any]:
    start = float(int(day) * 1000)
    return {
        "day": day,
        "lane": lane,
        "source_id": f"{lane}:{day}:{symbol}",
        "status": "PRESENT",
        "location": f"s3://observed/{lane}/{day}-{symbol}.jsonl.gz",
        "dataset": DATASET,
        "publisher_id": publisher_id,
        "instrument_id": instrument_id,
        "raw_symbol": symbol,
        "definition_date": (
            "2026-03-01" if symbol == "NGJ26" else "2026-03-20"
        ),
        "definition_start_s": start - 100.0,
        "definition_end_s": start + 1000.0,
        "event_start_s": start,
        "event_end_s": start + 500.0,
        "record_count": 10,
        "size_bytes": 100,
        "sha256": "a" * 64,
        "inventory_observed_at": "2026-07-22T00:00:00Z",
    }


def _fixture(*, complete: bool = True) -> dict[str, Any]:
    catalog = expected_catalog_template(publisher_id=1)
    target_days = list(G15_DATES + G16_DATES)
    for corpus in catalog["corpora"]:
        lane = corpus["lane"]
        entries = []
        for day in target_days:
            expected = G15_CONTRACT_MAP.get(day) or G16_CONTRACT_MAP[day]
            entries.append(
                _present_entry(
                    lane=lane,
                    day=day,
                    symbol=expected["raw_symbol"],
                    instrument_id=expected["instrument_id"],
                )
            )
        corpus["entries"] = entries
        corpus["expected_days"] = target_days
        corpus["expected_object_count"] = len(entries)
        corpus["observed_object_count"] = len(entries)
        corpus["remote_inventory_verified"] = complete
        corpus["inventory_complete"] = complete
        corpus["inventory_observed_at"] = "2026-07-22T00:00:00Z"
    catalog.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = _fp(catalog)
    return catalog


def selftest() -> int:
    unknown = build_audit(expected_catalog_template(publisher_id=1))
    assert unknown["status"] == "UNKNOWN"
    assert unknown["exact_intersections"]["g15"]["status"] == "UNKNOWN"

    ready = build_audit(_fixture())
    assert ready["status"] == "FULL_CORPUS_AND_G15_G16_EXACT_READY", ready
    assert ready["exact_intersections"]["g15"]["can_run_exact_replay"] is True
    validate_audit(ready)
    print("[ng_corpus_coverage_audit] selftest PASS")
    return 0


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CorpusCoverageError(f"{path}: expected a JSON object")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit broad NG corpus coverage and exact G15/G16 intersections"
        )
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="write a truthful UNKNOWN corpus catalog template",
    )
    parser.add_argument("--publisher-id", type=int)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.out is None:
        parser.error("--out is required unless --selftest is used")
    if args.init:
        if args.catalog is not None:
            parser.error("--init and --catalog are mutually exclusive")
        _write(args.out, expected_catalog_template(publisher_id=args.publisher_id))
        return 0
    if args.catalog is None:
        parser.error("--catalog is required")
    result = build_audit(_load(args.catalog))
    validate_audit(result)
    _write(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
