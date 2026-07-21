#!/usr/bin/env python3
"""Build a strict pre-cutoff G16 decision-state artifact.

The historical G16 state contains rich provenance, including some calendar fields
captured after a scheduled release. This module makes the blind wall enforceable
by construction: each session receives an explicit decision cutoff, future
snapshots and not-yet-knowable blocks are removed, and upcoming storage releases
retain only genuinely pre-print consensus evidence. The source state is never
mutated. The output cannot change the G16 blind forecast, update ng_brain.json,
or grant execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

SCHEMA = "ng_g16_blind_safe_state.v1"
AUTHORITY = "G16_PRE_CUTOFF_STATE_ONLY"
G16_DATES = (
    "20260329", "20260330", "20260331", "20260401", "20260402",
    "20260405", "20260406", "20260407", "20260408", "20260409", "20260410",
)
ET = ZoneInfo("America/New_York")
DROP = object()

FUTURE_RELEASE_FIELDS = {
    "actual_current_vintage_bcf",
    "actual_as_printed_bcf",
    "actual_on_page_bcf",
    "surprise_vs_consensus_bcf",
    "surprise_as_printed_vs_consensus_bcf",
    "vintage_diff_bcf",
    "final_capture_is_post_print",
}
PROVENANCE_FIELDS = (
    "knowable_from",
    "snapshot_utc",
    "as_of_utc",
    "collected_at",
    "effective_at",
    "issue_datetime_utc",
)


class BlindWallError(ValueError):
    """Raised when the source or sanitized state violates the G16 blind wall."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_datetime(value: Any, *, date_at_end: bool = True) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.max if date_at_end else time.min, tzinfo=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = None
        formats = (
            "%Y%m%d%H%M%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y%m%d",
        )
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            for fmt in formats:
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None
        if len(text) in {8, 10} and ("T" not in text and ":" not in text):
            parsed = datetime.combine(parsed.date(), time.max if date_at_end else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def session_decision_cutoff_utc(day: str) -> datetime:
    """Return the instant immediately before the labeled session becomes tradeable.

    Sunday sessions reopen at 18:00 ET on the labeled Sunday. Weekday sessions
    begin at 18:00 ET on the preceding calendar day. The cutoff is one second
    earlier so target-session tape can never enter the state.
    """
    if day not in G16_DATES:
        raise BlindWallError(f"unsupported G16 day: {day}")
    session_date = datetime.strptime(day, "%Y%m%d").date()
    open_date = session_date if session_date.weekday() == 6 else session_date - timedelta(days=1)
    cutoff_et = datetime.combine(open_date, time(17, 59, 59), tzinfo=ET)
    return cutoff_et.astimezone(timezone.utc)


def _record(removals: list[dict[str, Any]], path: str, reason: str, value: Any = None) -> None:
    row: dict[str, Any] = {"path": path, "reason": reason}
    if value not in (None, ""):
        row["observed"] = value
    removals.append(row)


def _future_provenance(mapping: Mapping[str, Any], cutoff: datetime) -> tuple[str, str] | None:
    for field in PROVENANCE_FIELDS:
        if field not in mapping:
            continue
        parsed = _parse_datetime(mapping.get(field))
        if parsed is not None and parsed > cutoff:
            return field, parsed.isoformat()
    as_of = mapping.get("as_of")
    if as_of not in (None, ""):
        parsed = _parse_datetime(as_of)
        if parsed is not None and parsed > cutoff:
            return "as_of", parsed.isoformat()
    issue_date = mapping.get("issue_date")
    if issue_date not in (None, ""):
        parsed = _parse_datetime(issue_date)
        if parsed is not None and parsed > cutoff:
            return "issue_date", parsed.isoformat()
    return None


def _sanitize_estimates(
    estimates: Any,
    *,
    cutoff: datetime,
    path: str,
    removals: list[dict[str, Any]],
    upcoming_release: bool,
) -> list[Any]:
    result: list[Any] = []
    for index, raw in enumerate(estimates or []):
        item_path = f"{path}[{index}]"
        if not isinstance(raw, Mapping):
            sanitized = _sanitize_value(raw, cutoff=cutoff, path=item_path, removals=removals)
            if sanitized is not DROP:
                result.append(sanitized)
            continue
        snapshot = _parse_datetime(raw.get("snapshot_utc"))
        if snapshot is not None and snapshot > cutoff:
            _record(removals, item_path, "snapshot_after_decision_cutoff", snapshot.isoformat())
            continue
        if upcoming_release and raw.get("pre_print") is not True:
            _record(removals, item_path, "post_print_estimate_for_upcoming_release")
            continue
        sanitized = _sanitize_value(raw, cutoff=cutoff, path=item_path, removals=removals)
        if sanitized is not DROP:
            result.append(sanitized)
    return result


def _sanitize_release(
    release: Mapping[str, Any],
    *,
    cutoff: datetime,
    path: str,
    removals: list[dict[str, Any]],
) -> dict[str, Any] | object:
    print_at = _parse_datetime(release.get("print_datetime_utc"), date_at_end=False)
    upcoming = print_at is not None and print_at > cutoff
    result: dict[str, Any] = {}
    for key, raw in release.items():
        child_path = f"{path}.{key}"
        if key == "estimates":
            result[key] = _sanitize_estimates(
                raw,
                cutoff=cutoff,
                path=child_path,
                removals=removals,
                upcoming_release=upcoming,
            )
            continue
        if upcoming and key in FUTURE_RELEASE_FIELDS:
            _record(removals, child_path, "future_release_outcome_field")
            continue
        if upcoming and key == "consensus_chg_bcf":
            _record(removals, child_path, "final_consensus_not_pre_cutoff_safe")
            continue
        if upcoming and key == "source" and "final" in str(raw).lower():
            _record(removals, child_path, "post_print_source_label_removed")
            continue
        if upcoming and key == "consensus_pre_print_bcf":
            snap = _parse_datetime(release.get("consensus_pre_print_snapshot_utc"))
            if snap is None or snap > cutoff:
                _record(removals, child_path, "pre_print_consensus_snapshot_not_available")
                continue
        if upcoming and key == "consensus_pre_print_snapshot_utc":
            snap = _parse_datetime(raw)
            if snap is None or snap > cutoff:
                _record(removals, child_path, "pre_print_snapshot_after_decision_cutoff", raw)
                continue
        sanitized = _sanitize_value(raw, cutoff=cutoff, path=child_path, removals=removals)
        if sanitized is not DROP:
            result[key] = sanitized
    if upcoming:
        result["blind_wall_release_status"] = "UPCOMING_AT_DECISION_CUTOFF"
    else:
        result["blind_wall_release_status"] = "ALREADY_PUBLIC_AT_DECISION_CUTOFF"
    return result


def _sanitize_storage_consensus(
    block: Mapping[str, Any],
    *,
    cutoff: datetime,
    path: str,
    removals: list[dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, raw in block.items():
        child_path = f"{path}.{key}"
        if key in {"next_print", "last_print"} and isinstance(raw, Mapping):
            sanitized = _sanitize_release(raw, cutoff=cutoff, path=child_path, removals=removals)
        else:
            sanitized = _sanitize_value(raw, cutoff=cutoff, path=child_path, removals=removals)
        if sanitized is not DROP:
            result[key] = sanitized
    return result


def _sanitize_value(
    value: Any,
    *,
    cutoff: datetime,
    path: str,
    removals: list[dict[str, Any]],
) -> Any:
    if isinstance(value, Mapping):
        future = _future_provenance(value, cutoff)
        if future is not None:
            field, observed = future
            _record(removals, path, f"{field}_after_decision_cutoff", observed)
            return DROP
        result: dict[str, Any] = {}
        for key, raw in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == "storage_consensus" and isinstance(raw, Mapping):
                sanitized = _sanitize_storage_consensus(
                    raw, cutoff=cutoff, path=child_path, removals=removals
                )
            else:
                sanitized = _sanitize_value(
                    raw, cutoff=cutoff, path=child_path, removals=removals
                )
            if sanitized is not DROP:
                result[str(key)] = sanitized
        return result
    if isinstance(value, list):
        result = []
        for index, raw in enumerate(value):
            sanitized = _sanitize_value(
                raw, cutoff=cutoff, path=f"{path}[{index}]", removals=removals
            )
            if sanitized is not DROP:
                result.append(sanitized)
        return result
    return copy.deepcopy(value)


def _scan_future_provenance(value: Any, *, cutoff: datetime, path: str = "state") -> None:
    if isinstance(value, Mapping):
        future = _future_provenance(value, cutoff)
        if future is not None:
            field, observed = future
            raise BlindWallError(f"{path}: surviving {field} exceeds cutoff ({observed})")
        print_at = _parse_datetime(value.get("print_datetime_utc"), date_at_end=False)
        if print_at is not None and print_at > cutoff:
            forbidden = FUTURE_RELEASE_FIELDS.intersection(value)
            if forbidden:
                raise BlindWallError(
                    f"{path}: upcoming release retains outcome fields {sorted(forbidden)}"
                )
            if "consensus_chg_bcf" in value:
                raise BlindWallError(f"{path}: upcoming release retains final consensus")
        for key, raw in value.items():
            _scan_future_provenance(raw, cutoff=cutoff, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, raw in enumerate(value):
            _scan_future_provenance(raw, cutoff=cutoff, path=f"{path}[{index}]")


def build_blind_safe_state(source: Mapping[str, Any]) -> dict[str, Any]:
    source_before = copy.deepcopy(dict(source))
    dates = sorted(key for key in source if not str(key).startswith("_"))
    if dates != sorted(G16_DATES):
        missing = sorted(set(G16_DATES) - set(dates))
        extra = sorted(set(dates) - set(G16_DATES))
        raise BlindWallError(f"canonical G16 dates required; missing={missing}, extra={extra}")

    days: dict[str, Any] = {}
    total_removals = 0
    for day in G16_DATES:
        raw_day = source.get(day)
        if not isinstance(raw_day, Mapping):
            raise BlindWallError(f"{day}: state must be an object")
        cutoff = session_decision_cutoff_utc(day)
        removals: list[dict[str, Any]] = []
        sanitized = _sanitize_value(
            raw_day,
            cutoff=cutoff,
            path=f"days.{day}.state",
            removals=removals,
        )
        if sanitized is DROP or not isinstance(sanitized, Mapping):
            raise BlindWallError(f"{day}: state was entirely unavailable at cutoff")
        _scan_future_provenance(sanitized, cutoff=cutoff, path=f"days.{day}.state")
        day_row = {
            "date": day,
            "decision_cutoff_utc": cutoff.isoformat(),
            "decision_cutoff_rule": (
                "17:59:59 ET on labeled Sunday; otherwise 17:59:59 ET on prior calendar day"
            ),
            "target_session_tape_used": False,
            "actual_g16_outcomes_used": False,
            "state": sanitized,
            "removal_count": len(removals),
            "removals": removals,
        }
        day_row["day_fingerprint"] = _fingerprint(day_row)
        days[day] = day_row
        total_removals += len(removals)

    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "target_session_tape_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "source_state_fingerprint": _fingerprint(source_before),
        "information_clock": copy.deepcopy(source.get("_information_clock")),
        "n_days": len(days),
        "total_removals": total_removals,
        "days": days,
        "gate": {
            "g16_blind_state_ready": True,
            "g16_outcome_access_authorized": False,
            "g16_refinement_authority": "PRE_CUTOFF_SHADOW_ONLY",
        },
        "note": (
            "Blind-safe decision state only. The immutable grp16 forecast is not modified; "
            "G16 outcomes and target-session tape remain inaccessible."
        ),
    }
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_blind_safe_state(result)
    if dict(source) != source_before:
        raise BlindWallError("source state mutated during sanitization")
    return result


def validate_blind_safe_state(result: Mapping[str, Any]) -> None:
    if result.get("schema") != SCHEMA:
        raise BlindWallError("schema mismatch")
    if result.get("authority") != AUTHORITY:
        raise BlindWallError("authority mismatch")
    for field in (
        "execution_authority",
        "actual_g16_outcomes_used",
        "target_session_tape_used",
        "may_update_ng_brain",
        "may_change_g16_blind_prior",
    ):
        if result.get(field) is not False:
            raise BlindWallError(f"{field} must remain false")
    if int(result.get("n_days") or 0) != len(G16_DATES):
        raise BlindWallError("canonical G16 day count required")
    day_map = result.get("days") or {}
    if list(day_map) != list(G16_DATES):
        raise BlindWallError("G16 days are incomplete or out of order")
    for day in G16_DATES:
        row = day_map[day]
        payload = copy.deepcopy(dict(row))
        observed = payload.pop("day_fingerprint", None)
        if observed != _fingerprint(payload):
            raise BlindWallError(f"{day}: day fingerprint mismatch")
        cutoff = _parse_datetime(row.get("decision_cutoff_utc"), date_at_end=False)
        if cutoff is None or cutoff != session_decision_cutoff_utc(day):
            raise BlindWallError(f"{day}: decision cutoff mismatch")
        if row.get("target_session_tape_used") is not False:
            raise BlindWallError(f"{day}: target tape must remain unused")
        _scan_future_provenance(row.get("state"), cutoff=cutoff, path=f"days.{day}.state")
    payload = copy.deepcopy(dict(result))
    observed = payload.pop("artifact_fingerprint", None)
    if observed != _fingerprint(payload):
        raise BlindWallError("artifact fingerprint mismatch")


def _fixture() -> dict[str, Any]:
    source: dict[str, Any] = {"_information_clock": {"globex_reopen_et": "Sun 18:00"}}
    for day in G16_DATES:
        source[day] = {
            "dow": datetime.strptime(day, "%Y%m%d").strftime("%a"),
            "known_driver": {"as_of": "2026-03-01", "value": 1},
            "future_driver": {"knowable_from": "2027-01-01", "value": 99},
            "storage_consensus": {
                "next_print": {
                    "print_datetime_utc": "2026-12-31T15:30:00Z",
                    "consensus_chg_bcf": 34,
                    "consensus_pre_print_bcf": 38,
                    "consensus_pre_print_snapshot_utc": "2026-03-20T06:00:00Z",
                    "final_capture_is_post_print": True,
                    "actual_as_printed_bcf": 25,
                    "source": "tradingeconomics_final_frozen",
                    "estimates": [
                        {"pre_print": True, "value_bcf": 38, "snapshot_utc": "2026-03-20T06:00:00Z"},
                        {"pre_print": False, "value_bcf": 34, "snapshot_utc": "2026-04-20T06:00:00Z"},
                    ],
                }
            },
        }
    return source


def selftest() -> int:
    source = _fixture()
    result = build_blind_safe_state(source)
    validate_blind_safe_state(result)
    first = result["days"][G16_DATES[0]]["state"]
    next_print = first["storage_consensus"]["next_print"]
    assert next_print["consensus_pre_print_bcf"] == 38
    assert "consensus_chg_bcf" not in next_print
    assert "actual_as_printed_bcf" not in next_print
    assert "future_driver" not in first
    assert len(next_print["estimates"]) == 1
    print("[ng_g16_blind_wall] selftest PASS")
    return 0


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a strict pre-cutoff G16 state artifact")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.input is None or args.out is None:
        parser.error("--input and --out are required unless --selftest is used")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = build_blind_safe_state(source)
    _atomic_json(args.out, result)
    print(json.dumps({
        "status": "ok",
        "out": str(args.out),
        "n_days": result["n_days"],
        "total_removals": result["total_removals"],
        "artifact_fingerprint": result["artifact_fingerprint"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
