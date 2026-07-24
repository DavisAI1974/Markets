#!/usr/bin/env python3
"""Fail-closed verification of the broad NG historical corpus scope.

The existing coverage audit intentionally allows the exact G15/G16 intersections to be
ready while the wider one-year L1/dense-trades or spring/summer MBO inventory remains
unverified. This gate is the explicit boundary before G15 replay configuration. It
accepts only a byte-inspection receipt, rebuilds and validates the embedded coverage
audit, then proves that both canonical broad windows are genuinely represented by an
explicit, complete daily inventory rather than by the 24 target days alone.

The gate is historical-first and metadata-only. It never opens outcomes, assumes paid
live data, changes blind forecasts or posterior state, writes ``ng_brain.json``, grants
execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection

SCHEMA = "ng_broad_corpus_scope_gate.v1"
READY_STATUS = "BROAD_CORPUS_SCOPE_VERIFIED"
BLOCKED_STATUS = "BROAD_CORPUS_SCOPE_BLOCKED"

MIN_EXPECTED_DAYS = {
    coverage.L1_CORPUS_ID: 250,
    coverage.MBO_CORPUS_ID: 80,
}
EDGE_TOLERANCE_DAYS = 7
MAX_EXPECTED_DAY_GAP = 5
EXACT_NG_SYMBOL = re.compile(r"NG[A-Z][0-9]{2}")


class BroadCorpusScopeError(ValueError):
    """Raised when broad-corpus evidence is malformed, contradictory, or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BroadCorpusScopeError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise BroadCorpusScopeError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise BroadCorpusScopeError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise BroadCorpusScopeError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise BroadCorpusScopeError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise BroadCorpusScopeError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise BroadCorpusScopeError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _parse_day(value: Any, *, label: str) -> date:
    text = str(value or "").replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise BroadCorpusScopeError(f"{label}: invalid day {value!r}")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as error:
        raise BroadCorpusScopeError(f"{label}: invalid day {value!r}") from error


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise BroadCorpusScopeError(f"{label}: value must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusScopeError(f"{label}: value must be finite") from error
    if not math.isfinite(number):
        raise BroadCorpusScopeError(f"{label}: value must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise BroadCorpusScopeError(f"{label}: value must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusScopeError(f"{label}: value must be a positive integer") from error
    if number <= 0:
        raise BroadCorpusScopeError(f"{label}: value must be a positive integer")
    return number


def _max_gap(days: Sequence[date]) -> int:
    if len(days) < 2:
        return 0
    return max((right - left).days for left, right in zip(days, days[1:]))


def _entry_identity(row: Mapping[str, Any], *, corpus_id: str) -> tuple[Any, ...]:
    source_id = str(row.get("source_id") or "")
    prefix = f"{corpus_id}:{source_id or '<missing>'}"
    if row.get("status") != "PRESENT":
        raise BroadCorpusScopeError(f"{prefix}: every broad-corpus object must be PRESENT")
    if row.get("dataset") != coverage.DATASET:
        raise BroadCorpusScopeError(f"{prefix}: dataset must be {coverage.DATASET}")
    publisher_id = _positive_int(row.get("publisher_id"), label=f"{prefix}:publisher_id")
    instrument_id = _positive_int(row.get("instrument_id"), label=f"{prefix}:instrument_id")
    raw_symbol = str(row.get("raw_symbol") or "")
    if not EXACT_NG_SYMBOL.fullmatch(raw_symbol):
        raise BroadCorpusScopeError(f"{prefix}: raw symbol must be an exact NG contract")
    definition_start = _finite(row.get("definition_start_s"), label=f"{prefix}:definition_start_s")
    definition_end = _finite(row.get("definition_end_s"), label=f"{prefix}:definition_end_s")
    event_start = _finite(row.get("event_start_s"), label=f"{prefix}:event_start_s")
    event_end = _finite(row.get("event_end_s"), label=f"{prefix}:event_end_s")
    if definition_end < definition_start or event_end < event_start:
        raise BroadCorpusScopeError(f"{prefix}: backwards definition or event range")
    if event_start < definition_start or event_end > definition_end:
        raise BroadCorpusScopeError(f"{prefix}: event range falls outside definition period")
    _positive_int(row.get("record_count"), label=f"{prefix}:record_count")
    _positive_int(row.get("size_bytes"), label=f"{prefix}:size_bytes")
    sha = str(row.get("sha256") or "").lower()
    if len(sha) != 64 or any(character not in "0123456789abcdef" for character in sha):
        raise BroadCorpusScopeError(f"{prefix}: invalid sha256")
    return (
        coverage.DATASET,
        publisher_id,
        instrument_id,
        raw_symbol,
        str(row.get("definition_date") or ""),
        definition_start,
        definition_end,
    )


def _scope_summary(
    corpus: Mapping[str, Any],
    report: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    corpus_id = str(corpus.get("corpus_id") or "")
    expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
    if expected is None:
        raise BroadCorpusScopeError(f"unexpected corpus id {corpus_id!r}")
    blockers: list[str] = []
    canonical_window = {
        "start": expected["start"],
        "end_exclusive": expected["end_exclusive"],
    }
    if dict(corpus.get("declared_window") or {}) != canonical_window:
        blockers.append("DECLARED_WINDOW_MISMATCH")
    if corpus.get("lane") != expected["lane"]:
        blockers.append("LANE_MISMATCH")
    if corpus.get("remote_inventory_verified") is not True:
        blockers.append("REMOTE_INVENTORY_SCOPE_UNVERIFIED")
    if corpus.get("inventory_complete") is not True:
        blockers.append("INVENTORY_NOT_ASSERTED_COMPLETE")
    if report.get("status") != "VERIFIED_COMPLETE":
        blockers.append("COVERAGE_AUDIT_NOT_VERIFIED_COMPLETE")
    if list(report.get("validation_errors") or []):
        blockers.append("COVERAGE_VALIDATION_ERRORS")

    expected_days_raw = list(corpus.get("expected_days") or [])
    expected_days = sorted({_parse_day(day, label=f"{corpus_id}:expected_day") for day in expected_days_raw})
    if len(expected_days) != len(expected_days_raw):
        blockers.append("DUPLICATE_EXPECTED_DAYS")
    start = date.fromisoformat(expected["start"])
    end_exclusive = date.fromisoformat(expected["end_exclusive"])
    if any(day < start or day >= end_exclusive for day in expected_days):
        blockers.append("EXPECTED_DAY_OUTSIDE_CANONICAL_WINDOW")
    if len(expected_days) < MIN_EXPECTED_DAYS[corpus_id]:
        blockers.append("EXPECTED_DAY_SET_TOO_SMALL_FOR_DECLARED_SCOPE")
    if not expected_days:
        blockers.append("EXPECTED_DAY_SET_EMPTY")
        first_day = last_day = None
        maximum_gap = None
    else:
        first_day = expected_days[0]
        last_day = expected_days[-1]
        maximum_gap = _max_gap(expected_days)
        if first_day > start + timedelta(days=EDGE_TOLERANCE_DAYS):
            blockers.append("WINDOW_START_NOT_COVERED")
        if last_day < end_exclusive - timedelta(days=EDGE_TOLERANCE_DAYS):
            blockers.append("WINDOW_END_NOT_COVERED")
        if maximum_gap > MAX_EXPECTED_DAY_GAP:
            blockers.append("EXPECTED_DAY_GAP_EXCEEDS_LIMIT")

    rows = [copy.deepcopy(dict(row)) for row in corpus.get("entries") or []]
    present_days = sorted({_parse_day(row.get("day"), label=f"{corpus_id}:entry_day") for row in rows})
    if present_days != expected_days:
        blockers.append("PRESENT_DAY_SET_DIFFERS_FROM_EXPECTED_DAY_SET")
    expected_count = corpus.get("expected_object_count")
    observed_count = corpus.get("observed_object_count")
    if expected_count is None or observed_count is None:
        blockers.append("OBJECT_COUNT_UNDECLARED")
    else:
        if int(expected_count) != int(observed_count) or int(observed_count) != len(rows):
            blockers.append("OBJECT_COUNT_MISMATCH")

    identities: set[tuple[Any, ...]] = set()
    publishers: set[int] = set()
    symbols: set[str] = set()
    instruments: set[int] = set()
    source_ids: set[str] = set()
    duplicate_source_ids: set[str] = set()
    for row in rows:
        source_id = str(row.get("source_id") or "")
        if not source_id or source_id in source_ids:
            duplicate_source_ids.add(source_id or "<missing>")
        source_ids.add(source_id)
        identity = _entry_identity(row, corpus_id=corpus_id)
        identities.add(identity)
        publishers.add(int(identity[1]))
        instruments.add(int(identity[2]))
        symbols.add(str(identity[3]))
    if duplicate_source_ids:
        blockers.append("DUPLICATE_OR_MISSING_SOURCE_IDS")
    if len(publishers) != 1:
        blockers.append("CORPUS_PUBLISHER_NOT_UNIQUE")

    summary = {
        "corpus_id": corpus_id,
        "lane": expected["lane"],
        "canonical_window": canonical_window,
        "minimum_expected_day_count": MIN_EXPECTED_DAYS[corpus_id],
        "expected_day_count": len(expected_days),
        "first_expected_day": None if first_day is None else first_day.isoformat(),
        "last_expected_day": None if last_day is None else last_day.isoformat(),
        "maximum_expected_day_gap": maximum_gap,
        "expected_object_count": expected_count,
        "observed_object_count": observed_count,
        "present_object_count": len(rows),
        "publisher_ids": sorted(publishers),
        "instrument_ids": sorted(instruments),
        "raw_symbols": sorted(symbols),
        "identity_partition_count": len(identities),
        "identity_key_fields": [
            "dataset",
            "publisher_id",
            "instrument_id",
            "raw_symbol",
            "definition_date",
            "definition_start_s",
            "definition_end_s",
        ],
        "event_time_verified_inside_definition_period": True,
        "exact_raw_symbols_only": True,
        "all_objects_present_and_hashed": all(row.get("status") == "PRESENT" for row in rows),
        "inventory_observed_at": corpus.get("inventory_observed_at"),
        "blockers": sorted(set(blockers)),
        "status": "VERIFIED" if not blockers else "BLOCKED",
    }
    return summary, sorted(set(blockers))


def _build_unchecked(receipt: Mapping[str, Any]) -> dict[str, Any]:
    checked_receipt = copy.deepcopy(dict(receipt))
    inspection.validate_receipt(checked_receipt)
    catalog = copy.deepcopy(dict(checked_receipt.get("catalog") or {}))
    audit = copy.deepcopy(dict(checked_receipt.get("audit") or {}))
    coverage.validate_audit(audit)
    rebuilt_audit = coverage.build_audit(catalog)
    if _canonical(rebuilt_audit) != _canonical(audit):
        raise BroadCorpusScopeError("inspection receipt audit does not match rebuilt catalog audit")

    corpora = {str(row.get("corpus_id") or ""): row for row in catalog.get("corpora") or []}
    reports = {str(row.get("corpus_id") or ""): row for row in audit.get("corpus_layout") or []}
    if set(corpora) != set(coverage.EXPECTED_WINDOWS) or set(reports) != set(coverage.EXPECTED_WINDOWS):
        raise BroadCorpusScopeError("inspection receipt must contain both canonical broad corpora")

    summaries: list[dict[str, Any]] = []
    blockers: list[str] = []
    for corpus_id in coverage.EXPECTED_WINDOWS:
        summary, local = _scope_summary(corpora[corpus_id], reports[corpus_id])
        summaries.append(summary)
        blockers.extend(f"{corpus_id}:{blocker}" for blocker in local)

    publisher_sets = [set(summary["publisher_ids"]) for summary in summaries]
    common_publishers = set.intersection(*publisher_sets) if publisher_sets else set()
    if len(common_publishers) != 1 or any(values != common_publishers for values in publisher_sets):
        blockers.append("CROSS_CORPUS_PUBLISHER_MISMATCH")

    intersections = dict(audit.get("exact_intersections") or {})
    for group in ("g15", "g16"):
        if dict(intersections.get(group) or {}).get("status") != "MATCHED_L1_MBO_READY":
            blockers.append(f"{group.upper()}_EXACT_INTERSECTION_NOT_READY")
    if audit.get("status") != "FULL_CORPUS_AND_G15_G16_EXACT_READY":
        blockers.append("COVERAGE_AUDIT_FULL_READY_STATUS_MISSING")

    blockers = sorted(set(blockers))
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "market": "NG",
        "dataset": coverage.DATASET,
        "inspection_receipt_fingerprint": checked_receipt.get("receipt_fingerprint"),
        "catalog_fingerprint": catalog.get("catalog_fingerprint"),
        "coverage_audit_fingerprint": audit.get("fingerprint"),
        "source_inspection_receipt": checked_receipt,
        "corpus_scopes": summaries,
        "aligned_publisher_ids": sorted(common_publishers),
        "exact_intersections": {
            group: {
                "status": dict(intersections.get(group) or {}).get("status"),
                "ready_days": list(dict(intersections.get(group) or {}).get("ready_days") or []),
            }
            for group in ("g15", "g16")
        },
        "blockers": blockers,
        "broad_l1_one_year_verified": not blockers and summaries[0]["corpus_id"] == coverage.L1_CORPUS_ID,
        "broad_mbo_spring_summer_verified": not blockers and summaries[1]["corpus_id"] == coverage.MBO_CORPUS_ID,
        "target_day_subset_cannot_satisfy_broad_scope": True,
        "identity_alignment_fields": [
            "dataset",
            "publisher_id",
            "instrument_id",
            "raw_symbol",
            "definition_start_s",
            "definition_end_s",
            "event_time",
        ],
        "remote_presence_inferred": False,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": (
            "CONFIGURE_EXACT_G15_REPLAY" if not blockers else "REPAIR_OR_COMPLETE_BROAD_CORPUS_INVENTORY"
        ),
    }
    output["fingerprint"] = _fp(output)
    return output


def build_gate(inspection_receipt: Mapping[str, Any]) -> dict[str, Any]:
    result = _build_unchecked(inspection_receipt)
    validate_gate(result)
    return result


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise BroadCorpusScopeError("broad-corpus gate schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="broad-corpus gate")
    receipt = copy.deepcopy(dict(checked.get("source_inspection_receipt") or {}))
    expected = _build_unchecked(receipt)
    if _canonical(expected) != _canonical(checked):
        raise BroadCorpusScopeError("broad-corpus gate differs from deterministic reconstruction")
    if checked.get("status") == READY_STATUS:
        if checked.get("blockers") != []:
            raise BroadCorpusScopeError("ready broad-corpus gate may not contain blockers")
        if checked.get("broad_l1_one_year_verified") is not True:
            raise BroadCorpusScopeError("one-year L1/dense-trades scope is not verified")
        if checked.get("broad_mbo_spring_summer_verified") is not True:
            raise BroadCorpusScopeError("spring/summer MBO scope is not verified")
    return copy.deepcopy(dict(value))


def selftest() -> int:
    original_receipt_validator = inspection.validate_receipt
    original_audit_validator = coverage.validate_audit
    original_builder = coverage.build_audit
    try:
        inspection.validate_receipt = lambda value: value  # type: ignore[assignment]
        coverage.validate_audit = lambda value: value  # type: ignore[assignment]
        coverage.build_audit = lambda value: copy.deepcopy(value["_audit"])  # type: ignore[assignment]
        catalog = {
            "corpora": [
                {
                    "corpus_id": corpus_id,
                    "lane": spec["lane"],
                    "declared_window": {"start": spec["start"], "end_exclusive": spec["end_exclusive"]},
                    "remote_inventory_verified": False,
                    "inventory_complete": False,
                    "expected_object_count": None,
                    "observed_object_count": 0,
                    "expected_days": [],
                    "entries": [],
                    "inventory_observed_at": None,
                }
                for corpus_id, spec in coverage.EXPECTED_WINDOWS.items()
            ]
        }
        audit = {
            "status": "UNKNOWN",
            "fingerprint": "fixture-audit",
            "corpus_layout": [
                {"corpus_id": corpus_id, "status": "UNKNOWN", "validation_errors": []}
                for corpus_id in coverage.EXPECTED_WINDOWS
            ],
            "exact_intersections": {"g15": {"status": "UNKNOWN"}, "g16": {"status": "UNKNOWN"}},
        }
        catalog["_audit"] = audit
        receipt = {"receipt_fingerprint": "fixture-receipt", "catalog": catalog, "audit": audit}
        result = build_gate(receipt)
        assert result["status"] == BLOCKED_STATUS
        assert "COVERAGE_AUDIT_FULL_READY_STATUS_MISSING" in result["blockers"]
    finally:
        inspection.validate_receipt = original_receipt_validator
        coverage.validate_audit = original_audit_validator
        coverage.build_audit = original_builder
    print("[ng_broad_corpus_scope_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection-receipt", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.inspection_receipt is None or args.out is None:
        parser.error("--inspection-receipt and --out are required")
    result = build_gate(_load(args.inspection_receipt))
    _write(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
