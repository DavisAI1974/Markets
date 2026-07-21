#!/usr/bin/env python3
"""Manifest contract for historical NG L1/trades and MBO replay.

The manifest is deliberately metadata-only. It never claims an AWS/S3 object exists
unless an inventory process actually observed it. Missing remote visibility therefore
produces ``UNKNOWN`` instead of a guessed success state.

G15 uses the Kalshi-underlying contract basis already committed in the project:
NGJ26 through 2026-03-19 and NGK26 from 2026-03-20. The manifest keys every source by
Databento dataset/publisher/instrument/raw symbol/definition period and event-time
coverage so L1/trades and MBO can be joined without continuous-symbol ambiguity.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "ng_historical_manifest.v1"
DATASET = "GLBX.MDP3"
SOURCE_KINDS = ("l1_trades", "mbo")
OBSERVED_STATUSES = {"PRESENT", "MISSING", "CORRUPT", "UNKNOWN"}
G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
G15_CONTRACT_MAP: dict[str, dict[str, Any]] = {
    day: {
        "raw_symbol": "NGJ26" if day <= "20260319" else "NGK26",
        "instrument_id": 1008 if day <= "20260319" else 996,
    }
    for day in G15_DATES
}


class ManifestError(ValueError):
    """Raised for malformed or contradictory manifest metadata."""


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def expected_g15_manifest(*, publisher_id: int | None = None) -> dict[str, Any]:
    """Return an UNKNOWN template; this does not assert any remote object exists."""
    entries: list[dict[str, Any]] = []
    for day in G15_DATES:
        contract = G15_CONTRACT_MAP[day]
        for source_kind in SOURCE_KINDS:
            entries.append(
                {
                    "day": day,
                    "source_kind": source_kind,
                    "status": "UNKNOWN",
                    "location": None,
                    "dataset": DATASET,
                    "publisher_id": publisher_id,
                    "instrument_id": contract["instrument_id"],
                    "raw_symbol": contract["raw_symbol"],
                    "definition_date": None,
                    "definition_start_s": None,
                    "definition_end_s": None,
                    "event_start_s": None,
                    "event_end_s": None,
                    "record_count": None,
                    "size_bytes": None,
                    "sha256": None,
                    "inventory_observed_at": None,
                }
            )
    return {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "coverage": {"start": G15_DATES[0], "end": G15_DATES[-1]},
        "authority": "HISTORICAL_INPUT_METADATA_ONLY",
        "execution_authority": False,
        "remote_inventory_verified": False,
        "note": "UNKNOWN is intentional until an AWS/S3/local inventory records concrete objects.",
        "corpus_expectations": {
            "l1_trades": {
                "expected_window": {"start": "2025-07-01", "end_exclusive": "2026-07-01"},
                "known_logical_store": "nymex_cont",
                "known_format": "daily JSONL.GZ produced from full MBP-10/trades records",
                "inventory_status": "UNVERIFIED",
            },
            "mbo": {
                "expected_window": {"start": "2026-03-01", "end_exclusive": "2026-07-01"},
                "known_logical_store": "UNKNOWN_UNTIL_INVENTORY",
                "known_format": "DBN or causally normalized JSONL",
                "inventory_status": "UNVERIFIED",
            },
        },
        "entries": entries,
    }


def _entry_key(entry: dict[str, Any]) -> tuple[str, str]:
    return str(entry.get("day") or ""), str(entry.get("source_kind") or "")


def _validate_entry(entry: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    day, source_kind = _entry_key(entry)
    prefix = f"{day or '<missing-day>'}:{source_kind or '<missing-source>'}"
    if day not in G15_CONTRACT_MAP:
        errors.append(f"{prefix}: day is not in canonical G15 sessions")
        return
    if source_kind not in SOURCE_KINDS:
        errors.append(f"{prefix}: unsupported source_kind")
        return
    status = str(entry.get("status") or "UNKNOWN").upper()
    if status not in OBSERVED_STATUSES:
        errors.append(f"{prefix}: invalid status {status}")
    expected = G15_CONTRACT_MAP[day]
    if entry.get("dataset") != DATASET:
        errors.append(f"{prefix}: dataset must be {DATASET}")
    try:
        instrument_id = int(entry.get("instrument_id"))
    except (TypeError, ValueError):
        instrument_id = None
    if instrument_id != expected["instrument_id"]:
        errors.append(
            f"{prefix}: instrument_id {instrument_id!r} != canonical {expected['instrument_id']}"
        )
    if entry.get("raw_symbol") != expected["raw_symbol"]:
        errors.append(
            f"{prefix}: raw_symbol {entry.get('raw_symbol')!r} != canonical {expected['raw_symbol']}"
        )
    start = _finite(entry.get("event_start_s"))
    end = _finite(entry.get("event_end_s"))
    definition_start = _finite(entry.get("definition_start_s"))
    definition_end = _finite(entry.get("definition_end_s"))
    if status == "PRESENT":
        required = (
            "location", "publisher_id", "definition_date", "definition_start_s", "definition_end_s",
            "event_start_s", "event_end_s", "record_count", "size_bytes",
        )
        missing = [name for name in required if entry.get(name) in (None, "")]
        if missing:
            errors.append(f"{prefix}: PRESENT entry missing {', '.join(missing)}")
        if start is not None and end is not None and end < start:
            errors.append(f"{prefix}: event_end_s precedes event_start_s")
        if definition_start is not None and definition_end is not None and definition_end < definition_start:
            errors.append(f"{prefix}: definition_end_s precedes definition_start_s")
        if None not in (start, end, definition_start, definition_end):
            if float(start) < float(definition_start) or float(end) > float(definition_end):
                errors.append(f"{prefix}: event range falls outside definition period")
        if int(entry.get("record_count") or 0) <= 0:
            errors.append(f"{prefix}: PRESENT entry must have positive record_count")
        if int(entry.get("size_bytes") or 0) <= 0:
            errors.append(f"{prefix}: PRESENT entry must have positive size_bytes")
        if not entry.get("inventory_observed_at"):
            warnings.append(f"{prefix}: PRESENT without inventory_observed_at")
    elif status == "UNKNOWN" and entry.get("location"):
        warnings.append(f"{prefix}: UNKNOWN entry carries a location but no observed status")


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate identity, paired-source coverage, and event-time overlap for G15."""
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append(f"unexpected schema: {manifest.get('schema')}")
    if manifest.get("execution_authority") is not False:
        errors.append("historical manifest cannot grant execution authority")
    if int(manifest.get("group") or 0) != 15:
        errors.append("manifest group must be 15")

    entries = [copy.deepcopy(row) for row in manifest.get("entries") or []]
    seen: set[tuple[str, str]] = set()
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        key = _entry_key(entry)
        if key in seen:
            errors.append(f"duplicate entry: {key[0]}:{key[1]}")
            continue
        seen.add(key)
        by_key[key] = entry
        _validate_entry(entry, errors, warnings)

    missing_keys: list[str] = []
    unknown_keys: list[str] = []
    source_gaps: list[dict[str, Any]] = []
    ready_days: list[str] = []
    for day in G15_DATES:
        pair = [by_key.get((day, kind)) for kind in SOURCE_KINDS]
        for kind, entry in zip(SOURCE_KINDS, pair):
            if entry is None:
                missing_keys.append(f"{day}:{kind}")
            elif str(entry.get("status") or "UNKNOWN").upper() == "UNKNOWN":
                unknown_keys.append(f"{day}:{kind}")
        if any(entry is None for entry in pair):
            continue
        statuses = [str(entry.get("status") or "UNKNOWN").upper() for entry in pair]
        if statuses != ["PRESENT", "PRESENT"]:
            continue
        identity_fields = (
            "dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date",
            "definition_start_s", "definition_end_s",
        )
        for field_name in identity_fields:
            if pair[0].get(field_name) != pair[1].get(field_name):
                errors.append(f"{day}: paired L1/trades and MBO disagree on {field_name}")
        l1_start = _finite(pair[0].get("event_start_s"))
        l1_end = _finite(pair[0].get("event_end_s"))
        mbo_start = _finite(pair[1].get("event_start_s"))
        mbo_end = _finite(pair[1].get("event_end_s"))
        if None in (l1_start, l1_end, mbo_start, mbo_end):
            continue
        overlap_start = max(float(l1_start), float(mbo_start))
        overlap_end = min(float(l1_end), float(mbo_end))
        if overlap_end < overlap_start:
            errors.append(f"{day}: L1/trades and MBO event-time ranges do not overlap")
        else:
            source_gaps.append(
                {
                    "day": day,
                    "l1_only_head_s": max(0.0, float(mbo_start) - float(l1_start)),
                    "mbo_only_head_s": max(0.0, float(l1_start) - float(mbo_start)),
                    "l1_only_tail_s": max(0.0, float(l1_end) - float(mbo_end)),
                    "mbo_only_tail_s": max(0.0, float(mbo_end) - float(l1_end)),
                    "overlap_start_s": overlap_start,
                    "overlap_end_s": overlap_end,
                }
            )
            ready_days.append(day)

    if missing_keys:
        errors.append("missing canonical entries: " + ", ".join(missing_keys))
    observed_bad = [
        f"{day}:{kind}"
        for (day, kind), entry in by_key.items()
        if str(entry.get("status") or "UNKNOWN").upper() in {"MISSING", "CORRUPT"}
    ]
    if errors or observed_bad:
        status = "BLOCKED"
    elif unknown_keys:
        status = "UNKNOWN"
    elif len(ready_days) == len(G15_DATES):
        status = "READY"
    else:
        status = "PARTIAL"

    return {
        "schema": "ng_historical_manifest_report.v1",
        "group": 15,
        "status": status,
        "ready_days": ready_days,
        "unknown_entries": unknown_keys,
        "observed_bad_entries": observed_bad,
        "source_coverage": source_gaps,
        "errors": errors,
        "warnings": warnings,
        "can_replay_all_g15": status == "READY",
        "execution_authority": False,
    }


def selftest() -> int:
    template = expected_g15_manifest(publisher_id=1)
    report = validate_manifest(template)
    assert report["status"] == "UNKNOWN"
    assert len(report["unknown_entries"]) == len(G15_DATES) * len(SOURCE_KINDS)

    ready = copy.deepcopy(template)
    for i, entry in enumerate(ready["entries"]):
        entry.update(
            status="PRESENT",
            location=f"s3://example/{entry['source_kind']}/{entry['day']}",
            publisher_id=1,
            definition_date="2026-03-01" if entry["raw_symbol"] == "NGJ26" else "2026-03-20",
            definition_start_s=0.0,
            definition_end_s=5000.0,
            event_start_s=1000.0 + i,
            event_end_s=2000.0 + i,
            record_count=100,
            size_bytes=1000,
            inventory_observed_at="2026-07-21T00:00:00Z",
        )
    ready_report = validate_manifest(ready)
    assert ready_report["status"] == "READY", ready_report

    bad = copy.deepcopy(ready)
    bad["entries"][0]["raw_symbol"] = "NGK26"
    assert validate_manifest(bad)["status"] == "BLOCKED"
    print("[ng_historical_manifest] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or validate G15 historical L1/MBO manifest metadata")
    parser.add_argument("--init", action="store_true", help="write an UNKNOWN canonical G15 template")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--publisher-id", type=int)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.init:
        payload = expected_g15_manifest(publisher_id=args.publisher_id)
    elif args.manifest:
        payload = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    else:
        parser.error("choose --init, --manifest, or --selftest")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
