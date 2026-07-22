#!/usr/bin/env python3
"""Truthful basis/readiness gate for the committed G15 L1 + MBO inventory.

G15 straddles the Kalshi-underlying NGJ26 -> NGK26 roll.  The year-long NG.n.0
continuation is already NGK26 during the pre-roll part of G15, so a readable L1
file is not automatically a matching L1 file.  This gate separates:

* specific-leg MBO replay readiness; and
* exact-basis, matched L1+MBO readiness.

It never upgrades a wrong-leg L1 source, never invents remote presence, and never
grants execution authority.  A MBO-only causal result may remain useful, but it
must not be labeled a fully matched L1+MBO replay while this gate is blocked.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "ng_g15_corpus_basis_gate.v1"
CANONICAL_DATES = (
    "20260313",  # Friday anchor
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
EXPECTED = {
    day: {
        "contract": "NGJ26" if day <= "20260319" else "NGK26",
        "instrument_id": 1008 if day <= "20260319" else 996,
    }
    for day in CANONICAL_DATES
}


class CorpusBasisError(ValueError):
    """Raised for malformed or tampered basis-gate inputs/outputs."""


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _finite_positive(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _normalize_ids(value: Any) -> list[int]:
    rows = value if isinstance(value, list) else [value]
    result: list[int] = []
    for row in rows:
        try:
            result.append(int(row))
        except (TypeError, ValueError, OverflowError):
            continue
    return sorted(set(result))


def evaluate_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise CorpusBasisError("G15 inventory must be a list")
    by_date: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []
    day_reports: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            errors.append("inventory contains a non-object row")
            continue
        day = str(row.get("date") or "").replace("-", "")
        if day not in EXPECTED:
            errors.append(f"unexpected G15 inventory date: {day!r}")
            continue
        if day in by_date:
            errors.append(f"duplicate G15 inventory date: {day}")
            continue
        by_date[day] = copy.deepcopy(row)

    missing = [day for day in CANONICAL_DATES if day not in by_date]
    if missing:
        errors.append("missing G15 inventory dates: " + ", ".join(missing))

    mbo_blocked_days: list[str] = []
    l1_blocked_days: list[str] = []
    l1_wrong_basis_days: list[str] = []
    queue_stand_down_days: list[str] = []

    for day in CANONICAL_DATES:
        row = by_date.get(day)
        if row is None:
            continue
        expected = EXPECTED[day]
        row_errors: list[str] = []
        row_warnings: list[str] = []

        if row.get("dataset") != "GLBX.MDP3":
            row_errors.append("dataset must be GLBX.MDP3")
        if row.get("publisher_id") in (None, ""):
            row_errors.append("publisher_id is missing")
        if str(row.get("contract") or "") != expected["contract"]:
            row_errors.append(
                f"contract {row.get('contract')!r} != expected {expected['contract']}"
            )
        try:
            expected_id_field = int(row.get("expected_instrument_id"))
        except (TypeError, ValueError, OverflowError):
            expected_id_field = 0
        if expected_id_field != expected["instrument_id"]:
            row_errors.append(
                f"expected_instrument_id {expected_id_field!r} != canonical {expected['instrument_id']}"
            )

        try:
            mbo_id = int(row.get("instrument_id"))
        except (TypeError, ValueError, OverflowError):
            mbo_id = 0
        mbo_checks = {
            "present": row.get("mbo_present") is True,
            "positive_bytes": _finite_positive(row.get("mbo_bytes")),
            "contract_identity": mbo_id == expected["instrument_id"],
            "raw_symbol": str(row.get("raw_symbol") or "") == expected["contract"],
            "basis_flag": row.get("mbo_basis_correct") is True,
            "positive_records": _finite_positive(row.get("n_mbo")),
            "positive_trades": _finite_positive(row.get("n_trades")),
            "chronological": row.get("chronological_ok") is True,
            "flow_usable": row.get("flow_usable") is True,
        }
        mbo_ready = all(mbo_checks.values())
        if not mbo_ready:
            mbo_blocked_days.append(day)
            row_errors.extend(
                f"MBO {name} check failed" for name, passed in mbo_checks.items() if not passed
            )

        first = _parse_time(row.get("first_event_utc"))
        last = _parse_time(row.get("last_event_utc"))
        if first is None or last is None:
            mbo_ready = False
            if day not in mbo_blocked_days:
                mbo_blocked_days.append(day)
            row_errors.append("MBO event-time coverage is missing or invalid")
        elif last < first:
            mbo_ready = False
            if day not in mbo_blocked_days:
                mbo_blocked_days.append(day)
            row_errors.append("MBO event-time coverage moves backward")

        l1_ids = _normalize_ids(row.get("l1_instrument_id"))
        l1_identity_matches = expected["instrument_id"] in l1_ids
        l1_basis_flag = row.get("l1_basis_correct") is True
        l1_checks = {
            "present": row.get("l1_present") is True,
            "readable": row.get("l1_readable") is True,
            "positive_bytes": _finite_positive(row.get("l1_bytes")),
            "positive_rows": _finite_positive(row.get("l1_n_rows")),
            "positive_trades": _finite_positive(row.get("l1_n_trades")),
            "contract_identity": l1_identity_matches,
            "basis_flag": l1_basis_flag,
        }
        l1_ready = all(l1_checks.values())
        if not l1_ready:
            l1_blocked_days.append(day)
            row_errors.extend(
                f"L1 {name} check failed" for name, passed in l1_checks.items() if not passed
            )
        if not l1_identity_matches or not l1_basis_flag:
            l1_wrong_basis_days.append(day)

        queue_usable = row.get("queue_usable") is True
        if not queue_usable:
            queue_stand_down_days.append(day)
            row_warnings.append("queue evidence stood down; trade-flow may remain usable")

        day_reports.append({
            "date": day,
            "expected_contract": expected["contract"],
            "expected_instrument_id": expected["instrument_id"],
            "observed_mbo_instrument_id": mbo_id or None,
            "observed_l1_instrument_ids": l1_ids,
            "mbo_specific_leg_ready": mbo_ready,
            "l1_exact_basis_ready": l1_ready,
            "matched_l1_mbo_ready": mbo_ready and l1_ready,
            "queue_usable": queue_usable,
            "errors": row_errors,
            "warnings": row_warnings,
            "source_row_fingerprint": _sha(row),
        })

    mbo_blocked_days = sorted(set(mbo_blocked_days))
    l1_blocked_days = sorted(set(l1_blocked_days))
    l1_wrong_basis_days = sorted(set(l1_wrong_basis_days))
    queue_stand_down_days = sorted(set(queue_stand_down_days))
    structural_errors = bool(errors)
    mbo_ready_all = not structural_errors and not mbo_blocked_days and len(day_reports) == len(CANONICAL_DATES)
    matched_ready_all = mbo_ready_all and not l1_blocked_days

    if structural_errors or not mbo_ready_all:
        status = "BLOCKED"
    elif matched_ready_all:
        status = "MATCHED_L1_MBO_READY"
    else:
        status = "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"

    report = {
        "schema": SCHEMA,
        "group": 15,
        "status": status,
        "canonical_dates": list(CANONICAL_DATES),
        "contract_map": copy.deepcopy(EXPECTED),
        "mbo_specific_leg_ready": mbo_ready_all,
        "matched_l1_mbo_ready": matched_ready_all,
        "mbo_blocked_days": mbo_blocked_days,
        "l1_blocked_days": l1_blocked_days,
        "l1_wrong_basis_days": l1_wrong_basis_days,
        "queue_stand_down_days": queue_stand_down_days,
        "day_reports": day_reports,
        "errors": errors,
        "warnings": warnings,
        "interpretation": (
            "A specific-leg MBO causal replay may be evaluated, but it must not be described as a "
            "fully matched L1+MBO replay until matched_l1_mbo_ready is true."
        ),
        "actual_outcomes_used": False,
        "may_relabel_wrong_leg_l1": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    report["fingerprint"] = _sha(report)
    return report


def validate_report(report: dict[str, Any]) -> None:
    candidate = copy.deepcopy(report)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA:
        raise CorpusBasisError("unexpected basis-gate report schema")
    if observed != _sha(candidate):
        raise CorpusBasisError("basis-gate report fingerprint mismatch")
    if candidate.get("execution_authority") is not False:
        raise CorpusBasisError("basis gate cannot grant execution authority")
    if candidate.get("may_relabel_wrong_leg_l1") is not False:
        raise CorpusBasisError("basis gate cannot relabel wrong-leg L1")
    if candidate.get("matched_l1_mbo_ready") is True and candidate.get("l1_blocked_days"):
        raise CorpusBasisError("matched readiness contradicts blocked L1 days")


def _fixture_rows(*, wrong_pre_roll_l1: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in CANONICAL_DATES:
        expected = EXPECTED[day]
        l1_id = 996 if wrong_pre_roll_l1 and day <= "20260319" else expected["instrument_id"]
        rows.append({
            "date": day,
            "contract": expected["contract"],
            "expected_instrument_id": expected["instrument_id"],
            "mbo_present": True,
            "mbo_bytes": 100,
            "l1_present": True,
            "l1_bytes": 100,
            "l1_readable": True,
            "l1_instrument_id": [l1_id],
            "l1_n_rows": 10,
            "l1_n_trades": 2,
            "l1_basis_correct": l1_id == expected["instrument_id"],
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": expected["instrument_id"],
            "raw_symbol": expected["contract"],
            "mbo_basis_correct": True,
            "n_mbo": 10,
            "n_trades": 2,
            "first_event_utc": f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00+00:00",
            "last_event_utc": f"{day[:4]}-{day[4:6]}-{day[6:]}T23:00:00+00:00",
            "chronological_ok": True,
            "flow_usable": True,
            "queue_usable": True,
        })
    return rows


def selftest() -> int:
    ready = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=False))
    validate_report(ready)
    assert ready["status"] == "MATCHED_L1_MBO_READY"
    blocked = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=True))
    validate_report(blocked)
    assert blocked["status"] == "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"
    assert blocked["mbo_specific_leg_ready"] is True
    assert blocked["matched_l1_mbo_ready"] is False
    assert blocked["l1_wrong_basis_days"] == [day for day in CANONICAL_DATES if day <= "20260319"]
    print("[ng_g15_corpus_basis_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate exact-basis G15 L1+MBO readiness")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.manifest:
        parser.error("--manifest is required")
    rows = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = evaluate_manifest(rows)
    validate_report(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "mbo_specific_leg_ready": report["mbo_specific_leg_ready"],
        "matched_l1_mbo_ready": report["matched_l1_mbo_ready"],
        "l1_wrong_basis_days": report["l1_wrong_basis_days"],
        "fingerprint": report["fingerprint"],
        "out": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
