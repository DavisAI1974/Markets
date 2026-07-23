#!/usr/bin/env python3
"""Regenerate exact G15/G16 basis inventories from inspected target-day shards.

This module closes the metadata seam between deterministic target-day slicing and the
existing G15/G16 replay builders. Counts, event ranges, hashes, definitions, and
queue/flow availability are rebuilt from the exact inspected shard bytes; cumulative
source-object counts are never copied into daily inventories.

Inputs remain outcome-blind and SHADOW-only. The module cannot alter blind forecasts,
posterior state, ``knowledge/ng_brain.json``, or execution authority. Time-series
records are read chronologically and are never randomly shuffled.
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
from typing import Any, Mapping

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer
import ng_g15_corpus_basis_gate as g15_basis
import ng_g16_corpus_basis_gate as g16_basis

SCHEMA = "ng_corpus_basis_inventory_regeneration.v1"
G16_INVENTORY_SCHEMA = g16_basis.TEMPLATE_SCHEMA
QUEUE_ACTIONS = {"A", "M", "C", "R", "F"}
VALID_MBO_ACTIONS = QUEUE_ACTIONS | {"T", "N"}


class BasisInventoryRegenerationError(ValueError):
    """Raised when inspected daily shards cannot truthfully form basis inventories."""


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _authority() -> dict[str, Any]:
    return {
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


def _validate_authority(value: Mapping[str, Any], *, label: str) -> None:
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
            raise BasisInventoryRegenerationError(f"{label}: {field} must remain false")
    for field in ("one_signal_authority_preserved", "blind_forecasts_immutable"):
        if value.get(field) is not True:
            raise BasisInventoryRegenerationError(f"{label}: {field} must remain true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise BasisInventoryRegenerationError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise BasisInventoryRegenerationError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


def _verify_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(checked):
        raise BasisInventoryRegenerationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _iso_utc(seconds: float) -> str:
    return (
        datetime.fromtimestamp(float(seconds), tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _day_from_seconds(seconds: float) -> str:
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc).strftime("%Y%m%d")


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise BasisInventoryRegenerationError(f"{label} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BasisInventoryRegenerationError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise BasisInventoryRegenerationError(f"{label} must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise BasisInventoryRegenerationError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BasisInventoryRegenerationError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0:
        raise BasisInventoryRegenerationError(f"{label} must be a positive integer")
    return number


def _validate_slice_envelope(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify_fingerprint(
        value, "slice_bundle_fingerprint", label="target-day slice bundle"
    )
    if checked.get("schema") != slicer.SCHEMA:
        raise BasisInventoryRegenerationError("target-day slice bundle schema mismatch")
    if checked.get("target_days") != list(slicer._target_days()):
        raise BasisInventoryRegenerationError("target-day slice list mismatch")
    if checked.get("selection_may_use_record_count_or_filename_alone") is not False:
        raise BasisInventoryRegenerationError(
            "unsafe target-day selection heuristic detected"
        )
    if checked.get("conflicting_candidates_stand_down") is not True:
        raise BasisInventoryRegenerationError(
            "conflicting target-day candidates must stand down"
        )
    if checked.get("broad_corpus_completeness_asserted") is not False:
        raise BasisInventoryRegenerationError(
            "target-day slicing may not assert broad completeness"
        )
    if checked.get("source_bytes_untouched") is not True:
        raise BasisInventoryRegenerationError(
            "target-day source bytes must remain untouched"
        )
    slicer._validate_authority(checked, label="target-day slice bundle")
    if checked.get("random_shuffle_used") is not False:
        raise BasisInventoryRegenerationError(
            "target-day slice records may not be randomly shuffled"
        )

    candidates = [
        copy.deepcopy(dict(row)) for row in checked.get("candidates") or []
    ]
    if checked.get("candidate_count") != len(candidates):
        raise BasisInventoryRegenerationError("target-day candidate count mismatch")
    candidate_ids: set[str] = set()
    for row in candidates:
        payload = copy.deepcopy(row)
        observed = payload.pop("candidate_fingerprint", None)
        if observed != _fp(payload):
            raise BasisInventoryRegenerationError(
                "target-day candidate fingerprint mismatch"
            )
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in candidate_ids:
            raise BasisInventoryRegenerationError(
                "missing or duplicate target-day candidate_id"
            )
        candidate_ids.add(candidate_id)
        day = str(row.get("day") or "")
        lane = str(row.get("lane") or "")
        expected = slicer._target_identity(day)
        if expected is None or lane not in coverage.LANES:
            raise BasisInventoryRegenerationError(
                "target-day candidate is outside canonical targets"
            )
        definition = inspection.validate_definition(row.get("definition") or {})
        if row.get("definition_fingerprint") != definition["definition_fingerprint"]:
            raise BasisInventoryRegenerationError(
                "candidate definition fingerprint mismatch"
            )
        if (
            definition["dataset"] != coverage.DATASET
            or definition["raw_symbol"] != expected["raw_symbol"]
            or int(definition["instrument_id"])
            != int(expected["instrument_id"])
        ):
            raise BasisInventoryRegenerationError(
                "candidate exact contract identity mismatch"
            )
        start = _finite(
            row.get("event_start_s"), label="candidate.event_start_s"
        )
        end = _finite(row.get("event_end_s"), label="candidate.event_end_s")
        if (
            end < start
            or _day_from_seconds(start) != day
            or _day_from_seconds(end) != day
        ):
            raise BasisInventoryRegenerationError(
                "candidate event range is not confined to target UTC day"
            )
        _positive_int(row.get("record_count"), label="candidate.record_count")
        _positive_int(row.get("size_bytes"), label="candidate.size_bytes")

    selections = slicer._selection_rows(candidates)
    pairs = slicer._pair_rows(selections, candidates)
    status, groups = slicer._status(pairs)
    if checked.get("selections") != selections:
        raise BasisInventoryRegenerationError(
            "target-day selections were not reproduced"
        )
    if checked.get("pairs") != pairs:
        raise BasisInventoryRegenerationError("target-day pairs were not reproduced")
    if checked.get("status") != status or checked.get("groups") != groups:
        raise BasisInventoryRegenerationError(
            "target-day group status was not reproduced"
        )
    if status != "ANCHOR_G15_G16_TARGET_SLICES_READY":
        raise BasisInventoryRegenerationError(
            "exact inventory regeneration requires all target slices ready; "
            f"got {status}"
        )

    plan = copy.deepcopy(dict(checked.get("inspection_plan") or {}))
    inspection._validate_plan(plan)
    if checked.get("inspection_plan_fingerprint") != plan.get("plan_fingerprint"):
        raise BasisInventoryRegenerationError(
            "target-day inspection-plan fingerprint mismatch"
        )
    return checked


def _catalog_entries(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for corpus in catalog.get("corpora") or []:
        for raw in corpus.get("entries") or []:
            row = copy.deepcopy(dict(raw))
            source_id = str(row.get("source_id") or "")
            if not source_id or source_id in result:
                raise BasisInventoryRegenerationError(
                    f"invalid or duplicate inspected source_id {source_id!r}"
                )
            if row.get("status") != "PRESENT":
                raise BasisInventoryRegenerationError(
                    f"inspected target source is not PRESENT: {source_id}"
                )
            result[source_id] = row
    return result


def _selected_candidates(
    slice_bundle: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    candidates = {
        str(row["candidate_fingerprint"]): copy.deepcopy(dict(row))
        for row in slice_bundle.get("candidates") or []
    }
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for selection in slice_bundle.get("selections") or []:
        day = str(selection.get("day") or "")
        lane = str(selection.get("lane") or "")
        fingerprint = str(selection.get("selected_candidate_fingerprint") or "")
        if not fingerprint or fingerprint not in candidates:
            raise BasisInventoryRegenerationError(
                f"{day}:{lane}: selected target-day candidate is missing"
            )
        key = (day, lane)
        if key in result:
            raise BasisInventoryRegenerationError(
                f"duplicate target-day selection {day}:{lane}"
            )
        result[key] = candidates[fingerprint]
    expected = {
        (day, lane) for day in slicer._target_days() for lane in coverage.LANES
    }
    if set(result) != expected:
        raise BasisInventoryRegenerationError(
            "selected target-day lanes are incomplete"
        )
    return result


def _validate_entry_against_candidate(
    entry: Mapping[str, Any], candidate: Mapping[str, Any], *, verify_files: bool
) -> None:
    prefix = f"{candidate['day']}:{candidate['lane']}"
    definition = inspection.validate_definition(candidate["definition"])
    comparisons = {
        "source_id": candidate["normalized_source_id"],
        "materialized_path": candidate["materialized_path"],
        "day": candidate["day"],
        "lane": candidate["lane"],
        "dataset": definition["dataset"],
        "publisher_id": int(definition["publisher_id"]),
        "instrument_id": int(definition["instrument_id"]),
        "raw_symbol": definition["raw_symbol"],
        "definition_date": definition["definition_date"],
        "definition_start_s": float(definition["definition_start_s"]),
        "definition_end_s": float(definition["definition_end_s"]),
        "event_start_s": float(candidate["event_start_s"]),
        "event_end_s": float(candidate["event_end_s"]),
        "record_count": int(candidate["record_count"]),
        "size_bytes": int(candidate["size_bytes"]),
        "sha256": candidate["sha256"],
        "definition_fingerprint": definition["definition_fingerprint"],
    }
    for field, expected in comparisons.items():
        observed = entry.get(field)
        if isinstance(expected, float):
            if (
                abs(_finite(observed, label=f"{prefix}.{field}") - expected)
                > 1e-9
            ):
                raise BasisInventoryRegenerationError(
                    f"{prefix}: inspected {field} differs from selected shard"
                )
        elif observed != expected:
            raise BasisInventoryRegenerationError(
                f"{prefix}: inspected {field} differs from selected shard"
            )
    if entry.get("raw_input_untouched") is not True:
        raise BasisInventoryRegenerationError(
            f"{prefix}: inspected shard was not preserved"
        )
    if entry.get("identity_inferred_from_filename") is not False:
        raise BasisInventoryRegenerationError(
            f"{prefix}: identity was inferred from filename"
        )
    if verify_files:
        path = Path(str(entry.get("materialized_path") or "")).expanduser().resolve()
        if not path.is_file():
            raise BasisInventoryRegenerationError(
                f"{prefix}: inspected shard file is missing: {path}"
            )
        if (
            path.stat().st_size != int(entry["size_bytes"])
            or _sha256(path) != entry["sha256"]
        ):
            raise BasisInventoryRegenerationError(
                f"{prefix}: inspected shard bytes changed"
            )


def _read_normalized_metrics(
    entry: Mapping[str, Any], *, verify_files: bool
) -> dict[str, Any]:
    path = Path(str(entry.get("materialized_path") or "")).expanduser().resolve()
    if not path.is_file():
        raise BasisInventoryRegenerationError(
            f"missing normalized target shard: {path}"
        )
    if verify_files and (
        path.stat().st_size != int(entry["size_bytes"])
        or _sha256(path) != entry["sha256"]
    ):
        raise BasisInventoryRegenerationError(
            f"normalized target shard bytes changed: {path}"
        )

    lane = str(entry["lane"])
    day = str(entry["day"])
    expected_event_type = "trade" if lane == "l1_trades" else "mbo"
    count = 0
    trade_count = 0
    queue_action_count = 0
    sequence_gap_count = 0
    duplicate_source_sequence_count = 0
    first: float | None = None
    last: float | None = None
    previous_key: tuple[float, int, int] | None = None
    previous_source_sequence: int | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: invalid JSON"
                ) from error
            if not isinstance(row, Mapping):
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: normalized row is not an object"
                )
            if row.get("schema") != "ng_normalized_event.v1":
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: normalized schema mismatch"
                )
            if row.get("event_type") != expected_event_type:
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: lane event type mismatch"
                )
            identity = (
                row.get("dataset"),
                row.get("publisher_id"),
                row.get("instrument_id"),
                row.get("raw_symbol"),
                row.get("definition_date"),
                row.get("session_day"),
            )
            expected_identity = (
                entry["dataset"],
                entry["publisher_id"],
                entry["instrument_id"],
                entry["raw_symbol"],
                entry["definition_date"],
                day,
            )
            if identity != expected_identity:
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: normalized identity mismatch"
                )
            timestamp = _finite(
                row.get("ts_event_s"),
                label=f"{path}:{line_number}.ts_event_s",
            )
            try:
                source_sequence = int(row.get("source_sequence", 0))
                ingest_sequence = int(row.get("ingest_sequence", line_number))
            except (TypeError, ValueError, OverflowError) as error:
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: invalid sequence"
                ) from error
            key = (timestamp, source_sequence, ingest_sequence)
            if previous_key is not None and key < previous_key:
                raise BasisInventoryRegenerationError(
                    f"{path}:{line_number}: chronology moved backward"
                )
            if previous_source_sequence is not None and source_sequence > 0:
                if source_sequence == previous_source_sequence:
                    duplicate_source_sequence_count += 1
                elif source_sequence > previous_source_sequence + 1:
                    sequence_gap_count += source_sequence - previous_source_sequence - 1
                elif source_sequence < previous_source_sequence:
                    raise BasisInventoryRegenerationError(
                        f"{path}:{line_number}: source sequence moved backward"
                    )
            if source_sequence > 0:
                previous_source_sequence = source_sequence
            previous_key = key
            count += 1
            first = timestamp if first is None else first
            last = timestamp
            if lane == "l1_trades":
                trade_count += 1
            else:
                action = str(row.get("action") or "")
                if action not in VALID_MBO_ACTIONS:
                    raise BasisInventoryRegenerationError(
                        f"{path}:{line_number}: invalid MBO action {action!r}"
                    )
                if action == "T":
                    trade_count += 1
                if action in QUEUE_ACTIONS:
                    queue_action_count += 1

    if count != int(entry["record_count"]):
        raise BasisInventoryRegenerationError(
            f"{day}:{lane}: decoded count {count} != inspected count "
            f"{entry['record_count']}"
        )
    if first is None or last is None:
        raise BasisInventoryRegenerationError(
            f"{day}:{lane}: target shard is empty"
        )
    if (
        abs(first - float(entry["event_start_s"])) > 1e-9
        or abs(last - float(entry["event_end_s"])) > 1e-9
    ):
        raise BasisInventoryRegenerationError(
            f"{day}:{lane}: decoded event range differs from inspection"
        )
    if _day_from_seconds(first) != day or _day_from_seconds(last) != day:
        raise BasisInventoryRegenerationError(
            f"{day}:{lane}: decoded event range crosses UTC day"
        )

    return {
        "record_count": count,
        "trade_count": trade_count,
        "queue_action_count": queue_action_count,
        "sequence_gap_count": sequence_gap_count,
        "duplicate_source_sequence_count": duplicate_source_sequence_count,
        "event_start_s": first,
        "event_end_s": last,
        "chronological_ok": True,
        "flow_usable": trade_count > 0,
        "queue_usable": (
            lane == "mbo"
            and queue_action_count > 0
            and sequence_gap_count == 0
            and duplicate_source_sequence_count == 0
        ),
    }


def _inventory_row(
    *,
    day: str,
    l1: Mapping[str, Any],
    mbo: Mapping[str, Any],
    l1_metrics: Mapping[str, Any],
    mbo_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    expected = slicer._target_identity(day)
    if expected is None:
        raise BasisInventoryRegenerationError(f"unexpected target day {day}")
    identity_fields = (
        "dataset",
        "publisher_id",
        "instrument_id",
        "raw_symbol",
        "definition_date",
        "definition_start_s",
        "definition_end_s",
    )
    if tuple(l1.get(field) for field in identity_fields) != tuple(
        mbo.get(field) for field in identity_fields
    ):
        raise BasisInventoryRegenerationError(
            f"{day}: L1/MBO definition identity mismatch"
        )
    if (
        l1.get("dataset") != coverage.DATASET
        or l1.get("raw_symbol") != expected["raw_symbol"]
        or int(l1.get("instrument_id")) != int(expected["instrument_id"])
    ):
        raise BasisInventoryRegenerationError(
            f"{day}: selected pair has wrong exact contract identity"
        )
    overlap_start = max(
        float(l1["event_start_s"]), float(mbo["event_start_s"])
    )
    overlap_end = min(float(l1["event_end_s"]), float(mbo["event_end_s"]))
    if overlap_end < overlap_start:
        raise BasisInventoryRegenerationError(
            f"{day}: selected L1/MBO event ranges do not overlap"
        )
    observed_at = max(
        str(l1.get("inventory_observed_at") or ""),
        str(mbo.get("inventory_observed_at") or ""),
    )
    if not observed_at:
        raise BasisInventoryRegenerationError(
            f"{day}: inventory observation time is missing"
        )

    l1_start = float(l1_metrics["event_start_s"])
    l1_end = float(l1_metrics["event_end_s"])
    mbo_start = float(mbo_metrics["event_start_s"])
    mbo_end = float(mbo_metrics["event_end_s"])
    return {
        "date": day,
        "status": "PRESENT",
        "dataset": coverage.DATASET,
        "publisher_id": int(l1["publisher_id"]),
        "contract": expected["raw_symbol"],
        "expected_instrument_id": int(expected["instrument_id"]),
        "instrument_id": int(mbo["instrument_id"]),
        "raw_symbol": str(mbo["raw_symbol"]),
        "definition_date": str(mbo["definition_date"]),
        "definition_start_s": float(mbo["definition_start_s"]),
        "definition_end_s": float(mbo["definition_end_s"]),
        "mbo_definition_start_s": float(mbo["definition_start_s"]),
        "mbo_definition_end_s": float(mbo["definition_end_s"]),
        "mbo_present": True,
        "mbo_bytes": int(mbo["size_bytes"]),
        "n_mbo": int(mbo_metrics["record_count"]),
        "n_trades": int(mbo_metrics["trade_count"]),
        "first_event_utc": _iso_utc(mbo_start),
        "last_event_utc": _iso_utc(mbo_end),
        "mbo_first_event_s": mbo_start,
        "mbo_last_event_s": mbo_end,
        "mbo_first_event_utc": _iso_utc(mbo_start),
        "mbo_last_event_utc": _iso_utc(mbo_end),
        "mbo_basis_correct": True,
        "chronological_ok": bool(mbo_metrics["chronological_ok"]),
        "flow_usable": bool(mbo_metrics["flow_usable"]),
        "queue_usable": bool(mbo_metrics["queue_usable"]),
        "mbo_trade_count": int(mbo_metrics["trade_count"]),
        "mbo_queue_action_count": int(mbo_metrics["queue_action_count"]),
        "mbo_sequence_gap_count": int(mbo_metrics["sequence_gap_count"]),
        "mbo_duplicate_source_sequence_count": int(
            mbo_metrics["duplicate_source_sequence_count"]
        ),
        "mbo_source_id": str(mbo["source_id"]),
        "mbo_materialized_path": str(mbo["materialized_path"]),
        "mbo_sha256": str(mbo["sha256"]),
        "mbo_inspection_fingerprint": str(mbo["inspection_fingerprint"]),
        "l1_present": True,
        "l1_readable": True,
        "l1_bytes": int(l1["size_bytes"]),
        "l1_n_rows": int(l1_metrics["record_count"]),
        "l1_n_trades": int(l1_metrics["trade_count"]),
        "l1_instrument_id": [int(l1["instrument_id"])],
        "l1_raw_symbol": str(l1["raw_symbol"]),
        "l1_definition_start_s": float(l1["definition_start_s"]),
        "l1_definition_end_s": float(l1["definition_end_s"]),
        "l1_first_event_s": l1_start,
        "l1_last_event_s": l1_end,
        "l1_first_event_utc": _iso_utc(l1_start),
        "l1_last_event_utc": _iso_utc(l1_end),
        "l1_basis_correct": True,
        "l1_source_id": str(l1["source_id"]),
        "l1_materialized_path": str(l1["materialized_path"]),
        "l1_sha256": str(l1["sha256"]),
        "l1_inspection_fingerprint": str(l1["inspection_fingerprint"]),
        "event_time_overlap_start_s": overlap_start,
        "event_time_overlap_end_s": overlap_end,
        "inventory_observed_at": observed_at,
        "daily_counts_derived_from_inspected_shards": True,
        "cumulative_source_counts_reused": False,
    }


def _g16_inventory(
    rows: list[dict[str, Any]], *, receipt: Mapping[str, Any]
) -> dict[str, Any]:
    inventory = {
        "schema": G16_INVENTORY_SCHEMA,
        "group": 16,
        "coverage": {
            "start": g16_basis.CANONICAL_DATES[0],
            "end": g16_basis.CANONICAL_DATES[-1],
        },
        "dataset": coverage.DATASET,
        "contract": g16_basis.RAW_SYMBOL,
        "instrument_id": g16_basis.INSTRUMENT_ID,
        "remote_inventory_verified": True,
        "target_day_shards_only": True,
        "broad_corpus_completeness_asserted": False,
        "inspection_receipt_fingerprint": receipt["receipt_fingerprint"],
        "rows": rows,
        "note": (
            "Exact G16 target-day inventory regenerated from inspected daily shard "
            "bytes; this does not assert completion of the broad spring/summer corpus."
        ),
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    inventory["fingerprint"] = g16_basis._sha(inventory)
    return inventory


def build_basis_inventories(
    slice_bundle: Mapping[str, Any],
    inspection_receipt: Mapping[str, Any],
    *,
    verify_files: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Return exact G15 inventory, G16 inventory, and a provenance completion bundle."""
    before = copy.deepcopy((slice_bundle, inspection_receipt))
    slices = _validate_slice_envelope(slice_bundle)
    receipt = inspection.validate_receipt(inspection_receipt)
    if receipt.get("plan_fingerprint") != slices.get(
        "inspection_plan_fingerprint"
    ):
        raise BasisInventoryRegenerationError(
            "inspection receipt does not belong to target-day slice plan"
        )
    catalog = copy.deepcopy(dict(receipt.get("catalog") or {}))
    audit = copy.deepcopy(dict(receipt.get("audit") or {}))
    rebuilt = coverage.build_audit(catalog)
    if rebuilt != audit:
        raise BasisInventoryRegenerationError(
            "inspection audit is not the deterministic catalog rebuild"
        )
    coverage.validate_audit(audit)
    for group in ("g15", "g16"):
        report = (audit.get("exact_intersections") or {}).get(group) or {}
        if (
            report.get("status") != "MATCHED_L1_MBO_READY"
            or report.get("can_run_exact_replay") is not True
        ):
            raise BasisInventoryRegenerationError(
                f"{group.upper()} exact inspected intersection is not ready"
            )

    entries = _catalog_entries(catalog)
    selected = _selected_candidates(slices)
    expected_source_ids = {
        candidate["normalized_source_id"] for candidate in selected.values()
    }
    if set(entries) != expected_source_ids:
        missing = sorted(expected_source_ids - set(entries))
        extra = sorted(set(entries) - expected_source_ids)
        raise BasisInventoryRegenerationError(
            f"inspected target source set mismatch; missing={missing} extra={extra}"
        )

    metrics: dict[tuple[str, str], dict[str, Any]] = {}
    selected_entries: dict[tuple[str, str], dict[str, Any]] = {}
    for key, candidate in selected.items():
        entry = entries[str(candidate["normalized_source_id"])]
        _validate_entry_against_candidate(
            entry, candidate, verify_files=verify_files
        )
        selected_entries[key] = entry
        metrics[key] = _read_normalized_metrics(
            entry, verify_files=verify_files
        )

    g15_rows: list[dict[str, Any]] = []
    g16_rows: list[dict[str, Any]] = []
    for day in slicer._target_days():
        row = _inventory_row(
            day=day,
            l1=selected_entries[(day, "l1_trades")],
            mbo=selected_entries[(day, "mbo")],
            l1_metrics=metrics[(day, "l1_trades")],
            mbo_metrics=metrics[(day, "mbo")],
        )
        if day == slicer.ANCHOR_DAY or day in coverage.G15_DATES:
            g15_rows.append(row)
        elif day in coverage.G16_DATES:
            g16_rows.append(row)

    if [row["date"] for row in g15_rows] != list(g15_basis.CANONICAL_DATES):
        raise BasisInventoryRegenerationError(
            "G15 inventory canonical date order mismatch"
        )
    if [row["date"] for row in g16_rows] != list(g16_basis.CANONICAL_DATES):
        raise BasisInventoryRegenerationError(
            "G16 inventory canonical date order mismatch"
        )

    g15_report = g15_basis.evaluate_manifest(copy.deepcopy(g15_rows))
    g15_basis.validate_report(g15_report)
    g16_inventory = _g16_inventory(g16_rows, receipt=receipt)
    g16_report = g16_basis.evaluate_manifest(copy.deepcopy(g16_inventory))
    g16_basis.validate_report(g16_report)

    queue_stand_down_days = sorted(
        set(g15_report.get("queue_stand_down_days") or [])
        | set(g16_report.get("queue_stand_down_days") or [])
    )
    flow_stand_down_days = sorted(
        row["date"]
        for row in g15_rows + g16_rows
        if row.get("flow_usable") is not True
    )
    both_ready = (
        g15_report.get("status") == "MATCHED_L1_MBO_READY"
        and g16_report.get("status") == "MATCHED_L1_MBO_READY"
    )
    if both_ready and queue_stand_down_days:
        status = "G15_G16_BASIS_INVENTORIES_READY_WITH_QUEUE_STAND_DOWNS"
    elif both_ready:
        status = "G15_G16_BASIS_INVENTORIES_READY"
    else:
        status = "BLOCKED"

    bundle = {
        "schema": SCHEMA,
        "status": status,
        "slice_bundle_fingerprint": slices["slice_bundle_fingerprint"],
        "inspection_plan_fingerprint": slices["inspection_plan_fingerprint"],
        "inspection_receipt_fingerprint": receipt["receipt_fingerprint"],
        "coverage_catalog_fingerprint": receipt["catalog_fingerprint"],
        "coverage_audit_fingerprint": receipt["audit_fingerprint"],
        "selected_daily_source_count": len(selected_entries),
        "expected_daily_source_count": 2 * len(slicer._target_days()),
        "g15_inventory_fingerprint": _fp(g15_rows),
        "g16_inventory_fingerprint": _fp(g16_inventory),
        "g15_basis_report": g15_report,
        "g16_basis_report": g16_report,
        "queue_stand_down_days": queue_stand_down_days,
        "flow_stand_down_days": flow_stand_down_days,
        "daily_counts_derived_from_inspected_shards": True,
        "cumulative_source_counts_reused": False,
        "inventory_rows_cannot_relabel_wrong_contract": True,
        "broad_corpus_completeness_asserted": False,
        "next_permitted_stage": (
            "EXACT_REPLAY_CATALOG_EXPORT_AND_DETERMINISTIC_REPLAY"
            if both_ready
            else "REPAIR_VISIBLE_FLOW_OR_BASIS_STAND_DOWNS"
        ),
        **_authority(),
    }
    bundle["fingerprint"] = _fp(bundle)
    validate_regeneration_bundle(
        bundle,
        g15_rows,
        g16_inventory,
        slice_bundle=slice_bundle,
        inspection_receipt=inspection_receipt,
        verify_files=verify_files,
        rebuild=False,
    )
    if (slice_bundle, inspection_receipt) != before:
        raise BasisInventoryRegenerationError(
            "basis inventory regeneration mutated an input"
        )
    return g15_rows, g16_inventory, bundle


def validate_regeneration_bundle(
    bundle: Mapping[str, Any],
    g15_inventory: list[dict[str, Any]],
    g16_inventory: Mapping[str, Any],
    *,
    slice_bundle: Mapping[str, Any] | None = None,
    inspection_receipt: Mapping[str, Any] | None = None,
    verify_files: bool = True,
    rebuild: bool = True,
) -> dict[str, Any]:
    checked = _verify_fingerprint(
        bundle, "fingerprint", label="basis regeneration bundle"
    )
    if checked.get("schema") != SCHEMA:
        raise BasisInventoryRegenerationError(
            "basis regeneration schema mismatch"
        )
    if checked.get("status") not in {
        "G15_G16_BASIS_INVENTORIES_READY",
        "G15_G16_BASIS_INVENTORIES_READY_WITH_QUEUE_STAND_DOWNS",
        "BLOCKED",
    }:
        raise BasisInventoryRegenerationError(
            "basis regeneration status mismatch"
        )
    _validate_authority(checked, label="basis regeneration bundle")
    if checked.get("daily_counts_derived_from_inspected_shards") is not True:
        raise BasisInventoryRegenerationError(
            "daily counts must derive from inspected shards"
        )
    if checked.get("cumulative_source_counts_reused") is not False:
        raise BasisInventoryRegenerationError(
            "cumulative source counts may not populate daily inventories"
        )
    if checked.get("inventory_rows_cannot_relabel_wrong_contract") is not True:
        raise BasisInventoryRegenerationError(
            "wrong-contract relabel protection is disabled"
        )
    if checked.get("broad_corpus_completeness_asserted") is not False:
        raise BasisInventoryRegenerationError(
            "target inventory may not assert broad corpus completeness"
        )
    if checked.get("g15_inventory_fingerprint") != _fp(g15_inventory):
        raise BasisInventoryRegenerationError(
            "G15 inventory fingerprint mismatch"
        )
    if checked.get("g16_inventory_fingerprint") != _fp(g16_inventory):
        raise BasisInventoryRegenerationError(
            "G16 inventory fingerprint mismatch"
        )

    g15_report = g15_basis.evaluate_manifest(copy.deepcopy(g15_inventory))
    g15_basis.validate_report(g15_report)
    g16_report = g16_basis.evaluate_manifest(copy.deepcopy(g16_inventory))
    g16_basis.validate_report(g16_report)
    if checked.get("g15_basis_report") != g15_report:
        raise BasisInventoryRegenerationError(
            "embedded G15 basis report mismatch"
        )
    if checked.get("g16_basis_report") != g16_report:
        raise BasisInventoryRegenerationError(
            "embedded G16 basis report mismatch"
        )
    expected_queue = sorted(
        set(g15_report.get("queue_stand_down_days") or [])
        | set(g16_report.get("queue_stand_down_days") or [])
    )
    if checked.get("queue_stand_down_days") != expected_queue:
        raise BasisInventoryRegenerationError(
            "queue stand-down summary mismatch"
        )

    if rebuild:
        if slice_bundle is None or inspection_receipt is None:
            raise BasisInventoryRegenerationError(
                "full validation requires slice bundle and inspection receipt"
            )
        rebuilt_g15, rebuilt_g16, rebuilt_bundle = build_basis_inventories(
            slice_bundle,
            inspection_receipt,
            verify_files=verify_files,
        )
        if rebuilt_g15 != g15_inventory or rebuilt_g16 != g16_inventory:
            raise BasisInventoryRegenerationError(
                "inventories are not the deterministic byte-level rebuild"
            )
        if rebuilt_bundle != bundle:
            raise BasisInventoryRegenerationError(
                "bundle is not the deterministic byte-level rebuild"
            )
    return copy.deepcopy(dict(bundle))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def selftest() -> int:
    assert list(g15_basis.CANONICAL_DATES) == [
        slicer.ANCHOR_DAY,
        *coverage.G15_DATES,
    ]
    assert list(g16_basis.CANONICAL_DATES) == list(coverage.G16_DATES)
    assert len(slicer._target_days()) == 24
    assert QUEUE_ACTIONS.isdisjoint({"T", "N"})
    print("[ng_corpus_basis_inventory_regeneration] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate exact G15/G16 basis inventories from inspected "
            "target-day shards"
        )
    )
    parser.add_argument("--slice-bundle", type=Path)
    parser.add_argument("--inspection-receipt", type=Path)
    parser.add_argument("--g15-out", type=Path)
    parser.add_argument("--g16-out", type=Path)
    parser.add_argument("--bundle-out", type=Path)
    parser.add_argument("--no-verify-files", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        "slice_bundle",
        "inspection_receipt",
        "g15_out",
        "g16_out",
        "bundle_out",
    )
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))
    g15_inventory, g16_inventory, bundle = build_basis_inventories(
        _load_json(args.slice_bundle),
        _load_json(args.inspection_receipt),
        verify_files=not args.no_verify_files,
    )
    _write_json(args.g15_out, g15_inventory)
    _write_json(args.g16_out, g16_inventory)
    _write_json(args.bundle_out, bundle)
    print(
        json.dumps(
            {
                "status": bundle["status"],
                "g15_basis_status": bundle["g15_basis_report"]["status"],
                "g16_basis_status": bundle["g16_basis_report"]["status"],
                "queue_stand_down_days": bundle["queue_stand_down_days"],
                "flow_stand_down_days": bundle["flow_stand_down_days"],
                "g15_inventory": str(args.g15_out),
                "g16_inventory": str(args.g16_out),
                "bundle": str(args.bundle_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
