#!/usr/bin/env python3
"""Truthful exact-basis readiness gate for the G16 historical L1 + MBO corpus.

G16 is a single NGK26 block.  This module verifies that each canonical G16
session has observed, exact-contract L1/dense-trades and MBO metadata aligned by
Databento dataset, publisher, instrument, raw symbol, definition period, and
overlapping event time.  It never treats a readable continuous-contract file as
an exact leg, never invents AWS/S3 presence, and never grants outcome, brain, or
execution authority.

The expected inventory is metadata-only.  Remote objects that have not actually
been inspected must remain ``UNKNOWN`` or absent; callers may not promote them to
PRESENT merely because a path pattern exists.
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

SCHEMA = "ng_g16_corpus_basis_gate.v1"
TEMPLATE_SCHEMA = "ng_g16_expected_corpus_inventory.v1"
DATASET = "GLBX.MDP3"
RAW_SYMBOL = "NGK26"
INSTRUMENT_ID = 996
CANONICAL_DATES = (
    "20260329", "20260330", "20260331", "20260401", "20260402",
    "20260405", "20260406", "20260407", "20260408", "20260409", "20260410",
)
EXPECTED = {
    day: {"contract": RAW_SYMBOL, "instrument_id": INSTRUMENT_ID}
    for day in CANONICAL_DATES
}
OBSERVED_STATUSES = {"PRESENT", "MISSING", "CORRUPT", "UNKNOWN"}


class G16CorpusBasisError(ValueError):
    """Raised for malformed, contradictory, or tampered G16 corpus metadata."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> bool:
    number = _finite(value)
    return number is not None and number > 0


def _parse_time(value: Any) -> float | None:
    """Return UTC epoch seconds from numeric or ISO-8601 metadata."""
    number = _finite(value)
    if number is not None:
        return float(number)
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def _first_present(mapping: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        if mapping.get(field) not in (None, ""):
            return mapping.get(field)
    return None


def _event_range(row: Mapping[str, Any], lane: str) -> tuple[float | None, float | None]:
    if lane == "mbo":
        start_fields = ("mbo_first_event_utc", "mbo_event_start_utc", "mbo_event_start_s", "first_event_utc", "event_start_s")
        end_fields = ("mbo_last_event_utc", "mbo_event_end_utc", "mbo_event_end_s", "last_event_utc", "event_end_s")
    elif lane == "l1":
        start_fields = ("l1_first_event_utc", "l1_event_start_utc", "l1_event_start_s")
        end_fields = ("l1_last_event_utc", "l1_event_end_utc", "l1_event_end_s")
    else:
        raise G16CorpusBasisError(f"unsupported lane: {lane}")
    return _parse_time(_first_present(row, start_fields)), _parse_time(_first_present(row, end_fields))


def _definition_range(row: Mapping[str, Any], lane: str) -> tuple[float | None, float | None]:
    prefix = "mbo_" if lane == "mbo" else "l1_"
    start = _first_present(
        row,
        (
            f"{prefix}definition_start_utc",
            f"{prefix}definition_start_s",
            "definition_start_utc",
            "definition_start_s",
        ),
    )
    end = _first_present(
        row,
        (
            f"{prefix}definition_end_utc",
            f"{prefix}definition_end_s",
            "definition_end_utc",
            "definition_end_s",
        ),
    )
    return _parse_time(start), _parse_time(end)


def _normalize_ids(value: Any) -> list[int]:
    values = value if isinstance(value, list) else [value]
    result: list[int] = []
    for item in values:
        try:
            result.append(int(item))
        except (TypeError, ValueError, OverflowError):
            continue
    return sorted(set(result))


def expected_inventory_template(*, publisher_id: int | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for day in CANONICAL_DATES:
        rows.append(
            {
                "date": day,
                "status": "UNKNOWN",
                "dataset": DATASET,
                "publisher_id": publisher_id,
                "contract": RAW_SYMBOL,
                "expected_instrument_id": INSTRUMENT_ID,
                "instrument_id": None,
                "raw_symbol": None,
                "definition_date": None,
                "definition_start_s": None,
                "definition_end_s": None,
                "mbo_present": False,
                "mbo_bytes": None,
                "n_mbo": None,
                "n_trades": None,
                "first_event_utc": None,
                "last_event_utc": None,
                "mbo_basis_correct": False,
                "chronological_ok": False,
                "flow_usable": False,
                "queue_usable": False,
                "l1_present": False,
                "l1_readable": False,
                "l1_bytes": None,
                "l1_n_rows": None,
                "l1_n_trades": None,
                "l1_instrument_id": None,
                "l1_raw_symbol": None,
                "l1_definition_start_s": None,
                "l1_definition_end_s": None,
                "l1_first_event_utc": None,
                "l1_last_event_utc": None,
                "l1_basis_correct": False,
                "inventory_observed_at": None,
            }
        )
    template = {
        "schema": TEMPLATE_SCHEMA,
        "group": 16,
        "coverage": {"start": CANONICAL_DATES[0], "end": CANONICAL_DATES[-1]},
        "dataset": DATASET,
        "contract": RAW_SYMBOL,
        "instrument_id": INSTRUMENT_ID,
        "remote_inventory_verified": False,
        "note": "UNKNOWN is intentional until concrete AWS/S3/local objects are inspected.",
        "rows": rows,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    template["fingerprint"] = _sha(template)
    return template


def _rows_from_inventory(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, Mapping):
        rows = value.get("rows")
        if rows is None:
            rows = value.get("entries")
    else:
        rows = None
    if not isinstance(rows, list):
        raise G16CorpusBasisError("G16 inventory must be a list or an object containing rows/entries")
    return [copy.deepcopy(row) for row in rows]


def evaluate_manifest(inventory: Any) -> dict[str, Any]:
    rows = _rows_from_inventory(inventory)
    by_date: dict[str, dict[str, Any]] = {}
    structural_errors: list[str] = []
    warnings: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            structural_errors.append("inventory contains a non-object row")
            continue
        day = str(row.get("date") or row.get("day") or "").replace("-", "")
        if day not in EXPECTED:
            structural_errors.append(f"unexpected G16 inventory date: {day!r}")
            continue
        if day in by_date:
            structural_errors.append(f"duplicate G16 inventory date: {day}")
            continue
        by_date[day] = row

    missing = [day for day in CANONICAL_DATES if day not in by_date]
    if missing:
        structural_errors.append("missing G16 inventory dates: " + ", ".join(missing))

    day_reports: list[dict[str, Any]] = []
    mbo_blocked_days: list[str] = []
    l1_blocked_days: list[str] = []
    l1_wrong_basis_days: list[str] = []
    event_overlap_blocked_days: list[str] = []
    definition_blocked_days: list[str] = []
    queue_stand_down_days: list[str] = []

    for day in CANONICAL_DATES:
        row = by_date.get(day)
        if row is None:
            continue
        row_errors: list[str] = []
        row_warnings: list[str] = []

        status = str(row.get("status") or ("PRESENT" if row.get("mbo_present") or row.get("l1_present") else "UNKNOWN")).upper()
        if status not in OBSERVED_STATUSES:
            row_errors.append(f"invalid observed status {status}")
        if row.get("dataset") != DATASET:
            row_errors.append(f"dataset must be {DATASET}")
        if row.get("publisher_id") in (None, ""):
            row_errors.append("publisher_id is missing")
        if str(row.get("contract") or "") != RAW_SYMBOL:
            row_errors.append(f"contract {row.get('contract')!r} != expected {RAW_SYMBOL}")
        try:
            expected_id = int(row.get("expected_instrument_id"))
        except (TypeError, ValueError, OverflowError):
            expected_id = 0
        if expected_id != INSTRUMENT_ID:
            row_errors.append(f"expected_instrument_id {expected_id!r} != canonical {INSTRUMENT_ID}")
        common_identity_ok = bool(
            status == "PRESENT"
            and row.get("dataset") == DATASET
            and row.get("publisher_id") not in (None, "")
            and str(row.get("contract") or "") == RAW_SYMBOL
            and expected_id == INSTRUMENT_ID
        )

        try:
            mbo_id = int(row.get("instrument_id"))
        except (TypeError, ValueError, OverflowError):
            mbo_id = 0
        mbo_raw_symbol = str(row.get("raw_symbol") or "")
        mbo_start, mbo_end = _event_range(row, "mbo")
        mbo_def_start, mbo_def_end = _definition_range(row, "mbo")
        mbo_definition_ok = (
            mbo_def_start is not None
            and mbo_def_end is not None
            and mbo_def_start <= mbo_start if mbo_start is not None else False
        )
        mbo_definition_ok = bool(
            mbo_definition_ok
            and mbo_end is not None
            and mbo_end <= mbo_def_end
            and mbo_def_end >= mbo_def_start
        )
        mbo_checks = {
            "observed_present_status": status == "PRESENT",
            "catalog_identity": common_identity_ok,
            "present": row.get("mbo_present") is True,
            "positive_bytes": _positive(row.get("mbo_bytes")),
            "contract_identity": mbo_id == INSTRUMENT_ID,
            "raw_symbol": mbo_raw_symbol == RAW_SYMBOL,
            "basis_flag": row.get("mbo_basis_correct") is True,
            "positive_records": _positive(row.get("n_mbo")),
            "positive_trades": _positive(row.get("n_trades")),
            "chronological": row.get("chronological_ok") is True,
            "flow_usable": row.get("flow_usable") is True,
            "event_range": mbo_start is not None and mbo_end is not None and mbo_end >= mbo_start,
            "definition_period": mbo_definition_ok,
        }
        mbo_ready = all(mbo_checks.values())
        if not mbo_ready:
            mbo_blocked_days.append(day)
            row_errors.extend(f"MBO {name} check failed" for name, passed in mbo_checks.items() if not passed)
        if not mbo_definition_ok:
            definition_blocked_days.append(day)

        l1_ids = _normalize_ids(row.get("l1_instrument_id"))
        l1_raw_symbol = str(row.get("l1_raw_symbol") or row.get("l1_contract") or "")
        l1_start, l1_end = _event_range(row, "l1")
        l1_def_start, l1_def_end = _definition_range(row, "l1")
        l1_definition_ok = bool(
            l1_def_start is not None
            and l1_def_end is not None
            and l1_start is not None
            and l1_end is not None
            and l1_def_end >= l1_def_start
            and l1_start >= l1_def_start
            and l1_end <= l1_def_end
        )
        l1_identity_matches = INSTRUMENT_ID in l1_ids
        l1_symbol_matches = l1_raw_symbol == RAW_SYMBOL
        l1_checks = {
            "observed_present_status": status == "PRESENT",
            "catalog_identity": common_identity_ok,
            "present": row.get("l1_present") is True,
            "readable": row.get("l1_readable") is True,
            "positive_bytes": _positive(row.get("l1_bytes")),
            "positive_rows": _positive(row.get("l1_n_rows")),
            "positive_trades": _positive(row.get("l1_n_trades")),
            "contract_identity": l1_identity_matches,
            "raw_symbol": l1_symbol_matches,
            "basis_flag": row.get("l1_basis_correct") is True,
            "event_range": l1_start is not None and l1_end is not None and l1_end >= l1_start,
            "definition_period": l1_definition_ok,
        }
        l1_ready = all(l1_checks.values())
        if not l1_ready:
            l1_blocked_days.append(day)
            row_errors.extend(f"L1 {name} check failed" for name, passed in l1_checks.items() if not passed)
        if not l1_identity_matches or not l1_symbol_matches or row.get("l1_basis_correct") is not True:
            l1_wrong_basis_days.append(day)
        if not l1_definition_ok:
            definition_blocked_days.append(day)

        overlap_start = None
        overlap_end = None
        overlap_ready = False
        if None not in (mbo_start, mbo_end, l1_start, l1_end):
            overlap_start = max(float(mbo_start), float(l1_start))
            overlap_end = min(float(mbo_end), float(l1_end))
            overlap_ready = overlap_end >= overlap_start
        if not overlap_ready:
            event_overlap_blocked_days.append(day)
            row_errors.append("L1 and MBO event-time ranges do not overlap")

        queue_usable = row.get("queue_usable") is True
        if not queue_usable:
            queue_stand_down_days.append(day)
            row_warnings.append("queue evidence stood down; valid trade-flow evidence may remain usable")

        matched = mbo_ready and l1_ready and overlap_ready
        day_reports.append(
            {
                "date": day,
                "expected_contract": RAW_SYMBOL,
                "expected_instrument_id": INSTRUMENT_ID,
                "observed_mbo_instrument_id": mbo_id or None,
                "observed_mbo_raw_symbol": mbo_raw_symbol or None,
                "observed_l1_instrument_ids": l1_ids,
                "observed_l1_raw_symbol": l1_raw_symbol or None,
                "mbo_specific_leg_ready": mbo_ready,
                "l1_exact_basis_ready": l1_ready,
                "event_time_overlap_ready": overlap_ready,
                "overlap_start_s": overlap_start,
                "overlap_end_s": overlap_end,
                "matched_l1_mbo_ready": matched,
                "queue_usable": queue_usable,
                "errors": row_errors,
                "warnings": row_warnings,
                "source_row_fingerprint": _sha(row),
            }
        )

    mbo_blocked_days = sorted(set(mbo_blocked_days))
    l1_blocked_days = sorted(set(l1_blocked_days))
    l1_wrong_basis_days = sorted(set(l1_wrong_basis_days))
    event_overlap_blocked_days = sorted(set(event_overlap_blocked_days))
    definition_blocked_days = sorted(set(definition_blocked_days))
    queue_stand_down_days = sorted(set(queue_stand_down_days))

    structurally_complete = not structural_errors and len(day_reports) == len(CANONICAL_DATES)
    mbo_ready_all = structurally_complete and not mbo_blocked_days
    matched_ready_all = (
        mbo_ready_all
        and not l1_blocked_days
        and not event_overlap_blocked_days
        and not definition_blocked_days
    )
    if not mbo_ready_all:
        status = "BLOCKED"
    elif matched_ready_all:
        status = "MATCHED_L1_MBO_READY"
    else:
        status = "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"

    report = {
        "schema": SCHEMA,
        "group": 16,
        "status": status,
        "canonical_dates": list(CANONICAL_DATES),
        "contract_map": copy.deepcopy(EXPECTED),
        "dataset": DATASET,
        "publisher_must_match": True,
        "mbo_specific_leg_ready": mbo_ready_all,
        "matched_l1_mbo_ready": matched_ready_all,
        "mbo_blocked_days": mbo_blocked_days,
        "l1_blocked_days": l1_blocked_days,
        "l1_wrong_basis_days": l1_wrong_basis_days,
        "event_overlap_blocked_days": event_overlap_blocked_days,
        "definition_blocked_days": definition_blocked_days,
        "queue_stand_down_days": queue_stand_down_days,
        "day_reports": day_reports,
        "errors": structural_errors,
        "warnings": warnings,
        "interpretation": (
            "G16 causal refinement may be labeled exact matched L1+MBO only when "
            "matched_l1_mbo_ready is true. UNKNOWN remote objects and wrong-leg "
            "continuous-contract data remain blocked."
        ),
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_relabel_wrong_leg_l1": False,
        "may_change_g16_blind_prior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    report["fingerprint"] = _sha(report)
    return report


def validate_report(report: Mapping[str, Any]) -> None:
    candidate = copy.deepcopy(dict(report))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA:
        raise G16CorpusBasisError("unexpected G16 basis-gate report schema")
    if observed != _sha(candidate):
        raise G16CorpusBasisError("G16 basis-gate report fingerprint mismatch")
    if candidate.get("group") != 16:
        raise G16CorpusBasisError("G16 basis-gate report group mismatch")
    if list(candidate.get("canonical_dates") or []) != list(CANONICAL_DATES):
        raise G16CorpusBasisError("G16 canonical date order mismatch")
    if candidate.get("actual_outcomes_used") is not False:
        raise G16CorpusBasisError("basis gate cannot use G16 outcomes")
    for field in (
        "paid_live_data_assumed",
        "may_relabel_wrong_leg_l1",
        "may_change_g16_blind_prior",
        "may_update_ng_brain",
        "execution_authority",
    ):
        if candidate.get(field) is not False:
            raise G16CorpusBasisError(f"basis gate: {field} must remain false")
    if candidate.get("matched_l1_mbo_ready") is True:
        blocked = (
            list(candidate.get("l1_blocked_days") or [])
            + list(candidate.get("mbo_blocked_days") or [])
            + list(candidate.get("event_overlap_blocked_days") or [])
            + list(candidate.get("definition_blocked_days") or [])
        )
        if blocked:
            raise G16CorpusBasisError("matched readiness contradicts blocked days")
        if candidate.get("status") != "MATCHED_L1_MBO_READY":
            raise G16CorpusBasisError("matched readiness contradicts status")


def _fixture_rows(*, wrong_l1_day: str | None = None, no_overlap_day: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, day in enumerate(CANONICAL_DATES):
        start = 1_774_000_000.0 + index * 100_000.0
        end = start + 80_000.0
        l1_id = 1008 if day == wrong_l1_day else INSTRUMENT_ID
        l1_symbol = "NGJ26" if day == wrong_l1_day else RAW_SYMBOL
        l1_start = end + 10.0 if day == no_overlap_day else start + 1.0
        l1_end = end + 20.0 if day == no_overlap_day else end - 1.0
        rows.append(
            {
                "date": day,
                "status": "PRESENT",
                "dataset": DATASET,
                "publisher_id": 1,
                "contract": RAW_SYMBOL,
                "expected_instrument_id": INSTRUMENT_ID,
                "instrument_id": INSTRUMENT_ID,
                "raw_symbol": RAW_SYMBOL,
                "definition_start_s": start - 1000.0,
                "definition_end_s": end + 1000.0,
                "mbo_present": True,
                "mbo_bytes": 1000,
                "n_mbo": 100,
                "n_trades": 20,
                "first_event_utc": start,
                "last_event_utc": end,
                "mbo_basis_correct": True,
                "chronological_ok": True,
                "flow_usable": True,
                "queue_usable": True,
                "l1_present": True,
                "l1_readable": True,
                "l1_bytes": 500,
                "l1_n_rows": 50,
                "l1_n_trades": 20,
                "l1_instrument_id": [l1_id],
                "l1_raw_symbol": l1_symbol,
                "l1_definition_start_s": start - 1000.0,
                "l1_definition_end_s": end + 1000.0,
                "l1_first_event_utc": l1_start,
                "l1_last_event_utc": l1_end,
                "l1_basis_correct": l1_id == INSTRUMENT_ID and l1_symbol == RAW_SYMBOL,
                "inventory_observed_at": "2026-07-22T00:00:00Z",
            }
        )
    return rows


def selftest() -> int:
    template = expected_inventory_template(publisher_id=1)
    assert template["remote_inventory_verified"] is False
    assert all(row["status"] == "UNKNOWN" for row in template["rows"])

    ready = evaluate_manifest(_fixture_rows())
    validate_report(ready)
    assert ready["status"] == "MATCHED_L1_MBO_READY"
    assert ready["matched_l1_mbo_ready"] is True

    wrong = evaluate_manifest(_fixture_rows(wrong_l1_day=CANONICAL_DATES[0]))
    validate_report(wrong)
    assert wrong["status"] == "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"
    assert wrong["l1_wrong_basis_days"] == [CANONICAL_DATES[0]]

    gap = evaluate_manifest(_fixture_rows(no_overlap_day=CANONICAL_DATES[-1]))
    validate_report(gap)
    assert gap["event_overlap_blocked_days"] == [CANONICAL_DATES[-1]]

    print("[ng_g16_corpus_basis_gate] selftest PASS")
    return 0


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exact-basis G16 L1/MBO corpus metadata")
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--init", action="store_true", help="emit an UNKNOWN expected inventory template")
    parser.add_argument("--publisher-id", type=int)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.init:
        value = expected_inventory_template(publisher_id=args.publisher_id)
    else:
        if args.inventory is None:
            parser.error("--inventory is required unless --init or --selftest is used")
        value = evaluate_manifest(json.loads(args.inventory.read_text(encoding="utf-8")))
        validate_report(value)
    if args.out:
        _atomic_write(args.out, value)
    else:
        print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
