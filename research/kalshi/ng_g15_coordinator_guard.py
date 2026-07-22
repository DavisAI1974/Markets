#!/usr/bin/env python3
"""Fail-closed ownership guard for the G15 five-specialist coordinator.

The coordinator is a selector, not an ensemble.  Every canonical G15 day must be
claimed exactly once by its pre-assigned day-class specialist, and every emitted
refined day must be byte-for-meaning identical to that selected claim.  Missing
claims, wrong-owner claims, averaging, fallback-to-blind, or post-coordinate
mutation block publication.

This module is deliberately data-light: it validates committed specialist and
refined JSON artifacts without reading outcomes or market data.  It grants no
execution or brain-update authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "ng_g15_coordinator_guard.v1"
DAYS = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)
OWNER = {
    "20260315": "A", "20260322": "A",
    "20260316": "B", "20260323": "B",
    "20260317": "C", "20260318": "C", "20260324": "C", "20260325": "C",
    "20260319": "D", "20260326": "D",
    "20260320": "E", "20260327": "E",
}
LETTERS = tuple("ABCDE")


class CoordinatorGuardError(ValueError):
    """Raised when specialist selection or refined output violates ownership."""


def _date(value: Any) -> str:
    return str(value or "").replace("-", "")


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise CoordinatorGuardError(f"{label}: boolean is not a magnitude")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CoordinatorGuardError(f"{label}: expected finite number") from error
    if not math.isfinite(result):
        raise CoordinatorGuardError(f"{label}: expected finite number")
    return result


def _entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("days"), list):
        rows = payload["days"]
    elif isinstance(payload, dict):
        rows = [value for value in payload.values() if isinstance(value, dict) and value.get("date")]
    else:
        raise CoordinatorGuardError("specialist artifact must be a list or object")
    return [copy.deepcopy(row) for row in rows if isinstance(row, dict) and row.get("date")]


def _unwrap_curve(curve: Any, *, label: str) -> list[list[float]]:
    if not isinstance(curve, list) or len(curve) < 2:
        raise CoordinatorGuardError(f"{label}: path_p50_curve must contain at least two points")
    normalized: list[list[float]] = []
    offset = 0.0
    previous_clock: float | None = None
    previous_unwrapped: float | None = None
    for index, point in enumerate(curve):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise CoordinatorGuardError(f"{label}: curve point {index} is malformed")
        clock = _finite(point[0], f"{label}:curve[{index}].hour")
        cumulative = _finite(point[1], f"{label}:curve[{index}].cumulative")
        if previous_clock is not None and clock < previous_clock:
            offset += 24.0
        unwrapped = clock + offset
        if previous_unwrapped is not None and unwrapped <= previous_unwrapped:
            raise CoordinatorGuardError(f"{label}: curve time is not strictly chronological")
        normalized.append([clock, cumulative])
        previous_clock = clock
        previous_unwrapped = unwrapped
    if abs(normalized[0][1]) > 1e-6:
        raise CoordinatorGuardError(f"{label}: curve must begin at cumulative zero")
    return normalized


def _letter(path: Path) -> str:
    match = re.search(r"_([A-E])\.json$", path.name)
    if not match:
        raise CoordinatorGuardError(f"cannot derive specialist letter from {path.name}")
    return match.group(1)


def inspect_specialists(specialist_dir: Path) -> dict[str, Any]:
    paths = sorted(specialist_dir.glob("grp15_mbo_specialist_*.json"))
    found = [_letter(path) for path in paths]
    if sorted(found) != list(LETTERS):
        raise CoordinatorGuardError(
            f"expected exactly specialist files A-E; observed {found or 'none'}"
        )

    claims: dict[str, dict[str, Any]] = {}
    file_meta: list[dict[str, Any]] = []
    for path, letter in zip(paths, found):
        payload = json.loads(path.read_text(encoding="utf-8"))
        file_meta.append({"specialist": letter, "path": str(path), "sha256": _file_sha(path)})
        seen_in_file: set[str] = set()
        for entry in _entries(payload):
            day = _date(entry.get("date"))
            if day not in OWNER:
                raise CoordinatorGuardError(f"specialist {letter}: non-canonical G15 day {day!r}")
            if day in seen_in_file:
                raise CoordinatorGuardError(f"specialist {letter}: duplicate claim for {day}")
            seen_in_file.add(day)
            expected_owner = OWNER[day]
            if letter != expected_owner:
                raise CoordinatorGuardError(
                    f"{day}: specialist {letter} claimed day owned by {expected_owner}"
                )
            if day in claims:
                raise CoordinatorGuardError(f"{day}: claimed by more than one specialist")
            net = _finite(entry.get("expected_magnitude_usd"), f"{day}:{letter}:expected_magnitude_usd")
            curve = _unwrap_curve(entry.get("path_p50_curve"), label=f"{day}:{letter}")
            if abs(curve[-1][1] - net) > 1.0:
                raise CoordinatorGuardError(
                    f"{day}:{letter}: curve endpoint {curve[-1][1]} != magnitude {net}"
                )
            if not isinstance(entry.get("posterior_direction_by_horizon"), dict):
                raise CoordinatorGuardError(f"{day}:{letter}: missing posterior direction map")
            if not str(entry.get("selection_reason") or "").strip():
                raise CoordinatorGuardError(f"{day}:{letter}: missing selection_reason")
            if entry.get("execution_authority") is True:
                raise CoordinatorGuardError(f"{day}:{letter}: execution authority is forbidden")
            claims[day] = {
                "date": day,
                "owner": letter,
                "net": net,
                "curve": curve,
                "direction": copy.deepcopy(entry["posterior_direction_by_horizon"]),
                "confidence": copy.deepcopy(entry.get("confidence")),
                "selection_reason": str(entry["selection_reason"]),
                "claim_fingerprint": _sha(entry),
                "source_file": str(path),
            }

    missing = [day for day in DAYS if day not in claims]
    if missing:
        raise CoordinatorGuardError("missing owner claims: " + ", ".join(missing))
    if set(claims) != set(DAYS):
        raise CoordinatorGuardError("specialist claim set differs from canonical G15 sessions")

    return {
        "files": file_meta,
        "claims": [claims[day] for day in DAYS],
        "claims_fingerprint": _sha([claims[day] for day in DAYS]),
    }


def validate_refined(refined: dict[str, Any], specialist_report: dict[str, Any]) -> dict[str, Any]:
    if int(refined.get("group") or 0) != 15:
        raise CoordinatorGuardError("refined artifact group must be 15")
    if refined.get("execution_authority") is True:
        raise CoordinatorGuardError("refined artifact cannot grant execution authority")
    method = str(refined.get("method") or "").lower()
    if "select" not in method or "no averaging" not in method:
        raise CoordinatorGuardError("refined method must explicitly state SELECT and NO averaging")

    rows = refined.get("days")
    if not isinstance(rows, list):
        raise CoordinatorGuardError("refined artifact must contain a days list")
    dates = [_date(row.get("date")) for row in rows if isinstance(row, dict)]
    if dates != list(DAYS):
        raise CoordinatorGuardError("refined days must equal canonical G15 order exactly")

    claims = {row["date"]: row for row in specialist_report["claims"]}
    checked: list[dict[str, Any]] = []
    for row, day in zip(rows, DAYS):
        if not isinstance(row, dict):
            raise CoordinatorGuardError(f"{day}: refined row is malformed")
        claim = claims[day]
        owner = str(row.get("owner_specialist") or "")
        if owner != OWNER[day] or owner != claim["owner"]:
            raise CoordinatorGuardError(f"{day}: refined owner {owner!r} is not canonical owner {OWNER[day]}")
        net = _finite(row.get("refined_net_usd"), f"{day}:refined_net_usd")
        if abs(net - float(claim["net"])) > 1e-9:
            raise CoordinatorGuardError(
                f"{day}: refined net {net} was not selected verbatim from owner {owner} ({claim['net']})"
            )
        curve = _unwrap_curve(row.get("refined_path_p50"), label=f"{day}:refined")
        if curve != claim["curve"]:
            raise CoordinatorGuardError(f"{day}: refined path was not selected verbatim from owner {owner}")
        if row.get("posterior_direction_by_horizon") != claim["direction"]:
            raise CoordinatorGuardError(f"{day}: refined direction map differs from owner {owner}")
        if str(row.get("selection_reason") or "") != claim["selection_reason"]:
            raise CoordinatorGuardError(f"{day}: selection reason differs from owner {owner}")
        if row.get("execution_authority") is not False:
            raise CoordinatorGuardError(f"{day}: execution_authority must be false")
        checked.append({
            "date": day,
            "owner": owner,
            "selected_claim_fingerprint": claim["claim_fingerprint"],
            "refined_day_fingerprint": _sha(row),
            "net": net,
        })

    return {
        "checked_days": checked,
        "checked_days_fingerprint": _sha(checked),
        "refined_artifact_fingerprint": _sha(refined),
    }


def build_guard_report(*, specialist_dir: Path, refined_path: Path) -> dict[str, Any]:
    specialist_report = inspect_specialists(specialist_dir)
    refined = json.loads(refined_path.read_text(encoding="utf-8"))
    refined_report = validate_refined(refined, specialist_report)
    report = {
        "schema": SCHEMA,
        "group": 15,
        "status": "PASS",
        "selection_rule": "exactly one canonical owner per day; SELECT verbatim; never average; never fallback",
        "canonical_days": list(DAYS),
        "owner_map": copy.deepcopy(OWNER),
        "specialist_files": specialist_report["files"],
        "claims_fingerprint": specialist_report["claims_fingerprint"],
        **refined_report,
        "actual_outcomes_used": False,
        "may_average_specialists": False,
        "may_fallback_to_blind_when_owner_missing": False,
        "may_change_blind_prior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    report["fingerprint"] = _sha(report)
    return report


def validate_guard_report(report: dict[str, Any]) -> None:
    candidate = copy.deepcopy(report)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or candidate.get("status") != "PASS":
        raise CoordinatorGuardError("invalid coordinator guard report")
    if observed != _sha(candidate):
        raise CoordinatorGuardError("coordinator guard report fingerprint mismatch")
    forbidden = (
        "may_average_specialists", "may_fallback_to_blind_when_owner_missing",
        "may_change_blind_prior", "may_update_ng_brain", "execution_authority",
    )
    if any(candidate.get(field) is not False for field in forbidden):
        raise CoordinatorGuardError("coordinator guard authority gates are not closed")


def _fixture_entry(day: str, owner: str) -> dict[str, Any]:
    net = float((list(DAYS).index(day) + 1) * (10 if owner in {"A", "C", "E"} else -10))
    return {
        "date": day,
        "expected_magnitude_usd": net,
        "path_p50_curve": [[20, 0], [22, net]],
        "posterior_direction_by_horizon": {"close": "up" if net > 0 else "down"},
        "confidence": 0.5,
        "selection_reason": f"specialist {owner} owns {day}",
        "execution_authority": False,
    }


def selftest() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        claims_by_owner = {letter: [] for letter in LETTERS}
        for day in DAYS:
            claims_by_owner[OWNER[day]].append(_fixture_entry(day, OWNER[day]))
        for letter in LETTERS:
            (root / f"grp15_mbo_specialist_{letter}.json").write_text(
                json.dumps({"days": claims_by_owner[letter]}), encoding="utf-8"
            )
        refined_days = []
        for day in DAYS:
            entry = next(row for row in claims_by_owner[OWNER[day]] if _date(row["date"]) == day)
            refined_days.append({
                "date": day,
                "owner_specialist": OWNER[day],
                "refined_net_usd": entry["expected_magnitude_usd"],
                "refined_path_p50": entry["path_p50_curve"],
                "posterior_direction_by_horizon": entry["posterior_direction_by_horizon"],
                "selection_reason": entry["selection_reason"],
                "execution_authority": False,
            })
        refined_path = root / "grp15_mbo_refined.json"
        refined_path.write_text(json.dumps({
            "group": 15,
            "method": "coordinator SELECTS owner per day, NO averaging",
            "days": refined_days,
        }), encoding="utf-8")
        report = build_guard_report(specialist_dir=root, refined_path=refined_path)
        validate_guard_report(report)
        assert len(report["checked_days"]) == len(DAYS)
    print("[ng_g15_coordinator_guard] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate G15 specialist ownership and coordinator output")
    parser.add_argument("--specialist-dir", type=Path)
    parser.add_argument("--refined", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.specialist_dir or not args.refined:
        parser.error("--specialist-dir and --refined are required")
    report = build_guard_report(specialist_dir=args.specialist_dir, refined_path=args.refined)
    validate_guard_report(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checked_days": len(report["checked_days"]),
        "fingerprint": report["fingerprint"],
        "out": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
