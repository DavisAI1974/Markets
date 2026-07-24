#!/usr/bin/env python3
"""Verify that broad-corpus sources form exact, non-overlapping daily lane partitions.

The full-window exact-overlap gate proves that L1/dense-trades and MBO share one
exact identity and positive cross-lane event-time overlap on every expected day.
It does not prove that the source inventory itself is free of duplicated bytes,
reused objects, or positive-duration overlap between sources in the same lane.
Those conditions can double count historical events while still satisfying a
cross-lane overlap check.

This gate deterministically verifies source ownership before G15 replay.  Each
source may belong to exactly one day and lane, byte-identical sources may not be
listed twice, and same-lane source intervals may touch but may not overlap for a
positive duration.  It remains metadata-only, historical-first, outcome-blind,
SHADOW-only, and has no forecast, brain, options, or execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_broad_corpus_exact_overlap_gate as overlap
import ng_corpus_coverage_audit as coverage

SCHEMA = "ng_broad_corpus_exact_partition_gate.v1"
READY_STATUS = "BROAD_CORPUS_EXACT_PARTITION_VERIFIED"
BLOCKED_STATUS = "BROAD_CORPUS_EXACT_PARTITION_BLOCKED"


class BroadCorpusExactPartitionError(ValueError):
    """Raised when exact source-partition evidence is malformed or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BroadCorpusExactPartitionError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise BroadCorpusExactPartitionError(f"JSON artifact must be an object: {path}")
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
            raise BroadCorpusExactPartitionError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise BroadCorpusExactPartitionError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise BroadCorpusExactPartitionError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise BroadCorpusExactPartitionError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise BroadCorpusExactPartitionError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise BroadCorpusExactPartitionError(f"{label}: value must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusExactPartitionError(f"{label}: value must be finite") from error
    if not math.isfinite(number):
        raise BroadCorpusExactPartitionError(f"{label}: value must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise BroadCorpusExactPartitionError(f"{label}: value must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusExactPartitionError(f"{label}: value must be a positive integer") from error
    if number <= 0:
        raise BroadCorpusExactPartitionError(f"{label}: value must be a positive integer")
    return number


def _identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset": row.get("dataset"),
        "publisher_id": row.get("publisher_id"),
        "instrument_id": row.get("instrument_id"),
        "raw_symbol": row.get("raw_symbol"),
        "definition_date": row.get("definition_date"),
        "definition_start_s": row.get("definition_start_s"),
        "definition_end_s": row.get("definition_end_s"),
    }


def _hex_sha(value: Any, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise BroadCorpusExactPartitionError(f"{label}: sha256 must be 64 lowercase hex characters")
    return text


def _lane_partition(
    *,
    day: str,
    lane: str,
    expected_source_ids: Sequence[str],
    entries_by_source: Mapping[str, Mapping[str, Any]],
    selected_identity: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    source_ids = [str(value) for value in expected_source_ids]
    if not source_ids or len(source_ids) != len(set(source_ids)):
        blockers.append("DUPLICATE_OR_MISSING_SOURCE_ID")

    rows: list[dict[str, Any]] = []
    for source_id in source_ids:
        source = entries_by_source.get(source_id)
        if source is None:
            blockers.append("SOURCE_ID_NOT_FOUND_IN_INSPECTION_RECEIPT")
            continue
        row = copy.deepcopy(dict(source))
        if row.get("status") != "PRESENT":
            blockers.append("SOURCE_NOT_PRESENT")
        if str(row.get("day") or "") != day:
            blockers.append("SOURCE_DAY_MISMATCH")
        if str(row.get("lane") or "") != lane:
            blockers.append("SOURCE_LANE_MISMATCH")
        if _canonical(_identity(row)) != _canonical(dict(selected_identity)):
            blockers.append("SOURCE_IDENTITY_MISMATCH")
        try:
            start = _finite(row.get("event_start_s"), label=f"{day}:{lane}:{source_id}:event_start_s")
            end = _finite(row.get("event_end_s"), label=f"{day}:{lane}:{source_id}:event_end_s")
            if end < start:
                blockers.append("SOURCE_EVENT_RANGE_BACKWARDS")
            size = _positive_int(row.get("size_bytes"), label=f"{day}:{lane}:{source_id}:size_bytes")
            count = _positive_int(row.get("record_count"), label=f"{day}:{lane}:{source_id}:record_count")
            sha = _hex_sha(row.get("sha256"), label=f"{day}:{lane}:{source_id}")
        except BroadCorpusExactPartitionError as error:
            blockers.append(str(error))
            continue
        location = str(row.get("materialized_path") or row.get("location") or "")
        if not location:
            blockers.append("SOURCE_LOCATION_MISSING")
        rows.append(
            {
                "source_id": source_id,
                "location": location,
                "sha256": sha,
                "size_bytes": size,
                "record_count": count,
                "event_start_s": start,
                "event_end_s": end,
            }
        )

    by_sha: dict[str, list[str]] = {}
    by_location: dict[str, list[str]] = {}
    by_interval: dict[tuple[float, float], list[str]] = {}
    for row in rows:
        by_sha.setdefault(str(row["sha256"]), []).append(str(row["source_id"]))
        by_location.setdefault(str(row["location"]), []).append(str(row["source_id"]))
        by_interval.setdefault(
            (float(row["event_start_s"]), float(row["event_end_s"])), []
        ).append(str(row["source_id"]))
    duplicate_sha_groups = sorted(sorted(values) for values in by_sha.values() if len(values) > 1)
    duplicate_location_groups = sorted(
        sorted(values) for values in by_location.values() if len(values) > 1
    )
    duplicate_interval_groups = sorted(
        sorted(values) for values in by_interval.values() if len(values) > 1
    )
    if duplicate_sha_groups:
        blockers.append("DUPLICATE_SOURCE_BYTES")
    if duplicate_location_groups:
        blockers.append("DUPLICATE_SOURCE_LOCATION")
    if duplicate_interval_groups:
        blockers.append("DUPLICATE_SOURCE_EVENT_RANGE")

    positive_overlaps: list[dict[str, Any]] = []
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row["event_start_s"]),
            float(row["event_end_s"]),
            str(row["source_id"]),
        ),
    )
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            overlap_start = max(float(left["event_start_s"]), float(right["event_start_s"]))
            overlap_end = min(float(left["event_end_s"]), float(right["event_end_s"]))
            if overlap_end > overlap_start:
                positive_overlaps.append(
                    {
                        "left_source_id": left["source_id"],
                        "right_source_id": right["source_id"],
                        "overlap_start_s": overlap_start,
                        "overlap_end_s": overlap_end,
                        "overlap_duration_s": overlap_end - overlap_start,
                    }
                )
    if positive_overlaps:
        blockers.append("SAME_LANE_POSITIVE_EVENT_TIME_OVERLAP")

    blockers = sorted(set(blockers))
    partition = {
        "day": day,
        "lane": lane,
        "status": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "source_count": len(rows),
        "source_ids": sorted(source_ids),
        "ordered_sources": ordered,
        "duplicate_sha256_groups": duplicate_sha_groups,
        "duplicate_location_groups": duplicate_location_groups,
        "duplicate_event_range_groups": duplicate_interval_groups,
        "positive_same_lane_overlaps": positive_overlaps,
        "total_record_count": sum(int(row["record_count"]) for row in rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "same_lane_positive_overlap_forbidden": True,
        "duplicate_bytes_forbidden": True,
        "source_partition_fingerprint": "",
    }
    partition["source_partition_fingerprint"] = _fp(
        {key: value for key, value in partition.items() if key != "source_partition_fingerprint"}
    )
    return partition


def _build_unchecked(exact_overlap_gate: Mapping[str, Any]) -> dict[str, Any]:
    checked_gate = copy.deepcopy(dict(exact_overlap_gate))
    overlap.validate_gate(checked_gate)
    _authority(checked_gate, label="exact-overlap gate")

    blockers: list[str] = []
    if checked_gate.get("status") != overlap.READY_STATUS:
        blockers.append("BROAD_CORPUS_EXACT_OVERLAP_NOT_VERIFIED")

    receipt = copy.deepcopy(
        dict(
            dict(
                dict(checked_gate.get("source_broad_scope_gate") or {}).get(
                    "source_inspection_receipt"
                )
                or {}
            )
        )
    )
    catalog = copy.deepcopy(dict(receipt.get("catalog") or {}))
    corpora = {
        str(row.get("corpus_id") or ""): row for row in catalog.get("corpora") or []
    }
    if set(corpora) != {coverage.L1_CORPUS_ID, coverage.MBO_CORPUS_ID}:
        raise BroadCorpusExactPartitionError(
            "exact-overlap gate must embed both canonical inspected corpora"
        )

    entries_by_source: dict[str, dict[str, Any]] = {}
    sha_owners: dict[tuple[str, str], list[tuple[str, str]]] = {}
    location_owners: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for corpus in corpora.values():
        lane = str(corpus.get("lane") or "")
        for raw in corpus.get("entries") or []:
            row = copy.deepcopy(dict(raw))
            source_id = str(row.get("source_id") or "")
            if not source_id:
                raise BroadCorpusExactPartitionError("inspection receipt contains missing source_id")
            if source_id in entries_by_source:
                raise BroadCorpusExactPartitionError(
                    f"inspection receipt contains duplicate source_id {source_id!r}"
                )
            entries_by_source[source_id] = row
            day = str(row.get("day") or "")
            if row.get("status") == "PRESENT":
                sha = _hex_sha(row.get("sha256"), label=f"{source_id}")
                location = str(row.get("materialized_path") or row.get("location") or "")
                sha_owners.setdefault((lane, sha), []).append((day, source_id))
                if location:
                    location_owners.setdefault((lane, location), []).append((day, source_id))

    reports_by_day = {
        str(row.get("day") or ""): row for row in checked_gate.get("day_reports") or []
    }
    expected_days = [str(value) for value in checked_gate.get("expected_overlap_days") or []]
    day_reports: list[dict[str, Any]] = []
    for day in expected_days:
        source_report = reports_by_day.get(day)
        if source_report is None:
            blockers.append(f"{day}:MISSING_EXACT_OVERLAP_DAY_REPORT")
            continue
        selected_identity = copy.deepcopy(dict(source_report.get("selected_identity") or {}))
        day_blockers: list[str] = []
        if source_report.get("status") != "READY" or not selected_identity:
            day_blockers.append("EXACT_OVERLAP_DAY_NOT_READY")
        l1_partition = _lane_partition(
            day=day,
            lane="l1_trades",
            expected_source_ids=source_report.get("l1_source_ids") or [],
            entries_by_source=entries_by_source,
            selected_identity=selected_identity,
        )
        mbo_partition = _lane_partition(
            day=day,
            lane="mbo",
            expected_source_ids=source_report.get("mbo_source_ids") or [],
            entries_by_source=entries_by_source,
            selected_identity=selected_identity,
        )
        day_blockers.extend(f"L1:{value}" for value in l1_partition["blockers"])
        day_blockers.extend(f"MBO:{value}" for value in mbo_partition["blockers"])
        day_blockers = sorted(set(day_blockers))
        day_reports.append(
            {
                "day": day,
                "status": "READY" if not day_blockers else "BLOCKED",
                "blockers": day_blockers,
                "selected_identity": selected_identity,
                "exact_overlap_day_fingerprint": _fp(source_report),
                "l1_partition": l1_partition,
                "mbo_partition": mbo_partition,
            }
        )
        blockers.extend(f"{day}:{reason}" for reason in day_blockers)

    cross_day_sha_reuse: list[dict[str, Any]] = []
    for (lane, sha), owners in sorted(sha_owners.items()):
        days = sorted({day for day, _ in owners})
        if len(days) > 1:
            cross_day_sha_reuse.append(
                {
                    "lane": lane,
                    "sha256": sha,
                    "days": days,
                    "source_ids": sorted(source_id for _, source_id in owners),
                }
            )
    cross_day_location_reuse: list[dict[str, Any]] = []
    for (lane, location), owners in sorted(location_owners.items()):
        days = sorted({day for day, _ in owners})
        if len(days) > 1:
            cross_day_location_reuse.append(
                {
                    "lane": lane,
                    "location": location,
                    "days": days,
                    "source_ids": sorted(source_id for _, source_id in owners),
                }
            )
    if cross_day_sha_reuse:
        blockers.append("SOURCE_BYTES_REUSED_ACROSS_DAYS")
    if cross_day_location_reuse:
        blockers.append("SOURCE_LOCATION_REUSED_ACROSS_DAYS")

    ready_days = [row["day"] for row in day_reports if row["status"] == "READY"]
    blocked_days = [row["day"] for row in day_reports if row["status"] == "BLOCKED"]
    if ready_days != expected_days:
        blockers.append("NOT_ALL_SHARED_DAYS_HAVE_EXACT_SOURCE_PARTITIONS")
    target_days = set(coverage.G15_DATES + coverage.G16_DATES)
    missing_target_days = sorted(target_days - set(ready_days))
    if missing_target_days:
        blockers.append("G15_G16_TARGET_DAY_SOURCE_PARTITION_NOT_READY")

    blockers = sorted(set(blockers))
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "market": "NG",
        "dataset": coverage.DATASET,
        "exact_overlap_gate_fingerprint": checked_gate.get("fingerprint"),
        "broad_scope_gate_fingerprint": checked_gate.get("broad_scope_gate_fingerprint"),
        "inspection_receipt_fingerprint": checked_gate.get("inspection_receipt_fingerprint"),
        "catalog_fingerprint": checked_gate.get("catalog_fingerprint"),
        "coverage_audit_fingerprint": checked_gate.get("coverage_audit_fingerprint"),
        "source_exact_overlap_gate": checked_gate,
        "expected_days": expected_days,
        "expected_day_count": len(expected_days),
        "ready_days": ready_days,
        "blocked_days": blocked_days,
        "day_reports": day_reports,
        "cross_day_sha256_reuse": cross_day_sha_reuse,
        "cross_day_location_reuse": cross_day_location_reuse,
        "all_shared_days_exactly_partitioned": not blockers and ready_days == expected_days,
        "g15_g16_days_included": not missing_target_days,
        "same_lane_positive_overlap_forbidden": True,
        "duplicate_source_bytes_forbidden": True,
        "source_reuse_across_days_forbidden": True,
        "blockers": blockers,
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
            "CONFIGURE_EXACT_G15_REPLAY"
            if not blockers
            else "REPAIR_BROAD_CORPUS_SOURCE_PARTITIONS"
        ),
    }
    output["fingerprint"] = _fp(output)
    return output


def build_gate(exact_overlap_gate: Mapping[str, Any]) -> dict[str, Any]:
    result = _build_unchecked(exact_overlap_gate)
    validate_gate(result)
    return result


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise BroadCorpusExactPartitionError("exact-partition gate schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="exact-partition gate")
    source = copy.deepcopy(dict(checked.get("source_exact_overlap_gate") or {}))
    expected = _build_unchecked(source)
    if _canonical(expected) != _canonical(checked):
        raise BroadCorpusExactPartitionError(
            "exact-partition gate differs from deterministic reconstruction"
        )
    if checked.get("status") == READY_STATUS:
        if checked.get("blockers") != []:
            raise BroadCorpusExactPartitionError("ready exact-partition gate may not contain blockers")
        if checked.get("all_shared_days_exactly_partitioned") is not True:
            raise BroadCorpusExactPartitionError("shared broad-corpus days are not exactly partitioned")
        if checked.get("g15_g16_days_included") is not True:
            raise BroadCorpusExactPartitionError("G15/G16 target days are not included")
        if checked.get("ready_days") != checked.get("expected_days"):
            raise BroadCorpusExactPartitionError(
                "ready days must equal the complete expected-day set"
            )
    return copy.deepcopy(dict(value))


def selftest() -> int:
    original = overlap.validate_gate
    try:
        overlap.validate_gate = lambda value: value  # type: ignore[assignment]
        days = list(coverage.G15_DATES + coverage.G16_DATES)
        corpora = [
            {"corpus_id": coverage.L1_CORPUS_ID, "lane": "l1_trades", "entries": []},
            {"corpus_id": coverage.MBO_CORPUS_ID, "lane": "mbo", "entries": []},
        ]
        day_reports = []
        for day in days:
            expected = coverage.G15_CONTRACT_MAP.get(day) or coverage.G16_CONTRACT_MAP[day]
            symbol = expected["raw_symbol"]
            definition_anchor = datetime.strptime(
                "20260301" if symbol == "NGJ26" else "20260320", "%Y%m%d"
            ).replace(tzinfo=timezone.utc)
            identity = {
                "dataset": coverage.DATASET,
                "publisher_id": 1,
                "instrument_id": expected["instrument_id"],
                "raw_symbol": symbol,
                "definition_date": definition_anchor.date().isoformat(),
                "definition_start_s": definition_anchor.timestamp(),
                "definition_end_s": datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp(),
            }
            midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
            source_ids = {}
            for corpus in corpora:
                lane = str(corpus["lane"])
                source_id = f"{lane}:{day}"
                source_ids[lane] = source_id
                corpus["entries"].append(
                    {
                        "day": day,
                        "lane": lane,
                        "source_id": source_id,
                        "status": "PRESENT",
                        "location": f"/fixture/{lane}/{day}.jsonl",
                        **identity,
                        "event_start_s": midnight + (60 if lane == "l1_trades" else 120),
                        "event_end_s": midnight + (3600 if lane == "l1_trades" else 3540),
                        "record_count": 2,
                        "size_bytes": 10,
                        "sha256": hashlib.sha256(source_id.encode("utf-8")).hexdigest(),
                    }
                )
            day_reports.append(
                {
                    "day": day,
                    "status": "READY",
                    "selected_identity": identity,
                    "l1_source_ids": [source_ids["l1_trades"]],
                    "mbo_source_ids": [source_ids["mbo"]],
                }
            )
        source = {
            "schema": overlap.SCHEMA,
            "status": overlap.READY_STATUS,
            "fingerprint": "fixture-overlap",
            "broad_scope_gate_fingerprint": "fixture-broad",
            "inspection_receipt_fingerprint": "fixture-receipt",
            "catalog_fingerprint": "fixture-catalog",
            "coverage_audit_fingerprint": "fixture-audit",
            "expected_overlap_days": days,
            "day_reports": day_reports,
            "source_broad_scope_gate": {
                "source_inspection_receipt": {"catalog": {"corpora": corpora}}
            },
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
        }
        result = build_gate(source)
        assert result["status"] == READY_STATUS, result["blockers"]
        assert result["ready_days"] == days
    finally:
        overlap.validate_gate = original
    print("[ng_broad_corpus_exact_partition_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-overlap-gate", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.exact_overlap_gate is None:
        parser.error("--exact-overlap-gate is required")
    result = build_gate(_load(args.exact_overlap_gate))
    if args.out:
        _write(args.out, result)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
