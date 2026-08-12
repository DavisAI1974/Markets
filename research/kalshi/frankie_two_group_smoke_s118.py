#!/usr/bin/env python3
"""S118 matched-artifact smoke check for G15/G16.

Purpose:
- validate Frankie against two preserved pre-Frankie decision-state / outcome pairs;
- prove the canonical brain is inherited as an input, not replaced;
- keep outcome tape outside the blind-input seal;
- avoid rebuilding historical contract bases merely for the first smoke check.

This is not A-67 evidence and does not run a forecast. It is a structural gate before
spending a real blind/Frankie or paper-trading run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RENDER_ROOT = HERE / "renders" / "ng_refine_s95"
BRAIN = HERE / "knowledge" / "ng_brain.json"

GROUPS = {
    "g15": {
        "state": RENDER_ROOT / "grp15_state.json",
        "actual": RENDER_ROOT / "g15_rt.json",
        "expected_days": 12,
        "expected_anchor_date": "20260313",
        "expected_roll_date": "20260320",
        "basis_tokens": ("NGJ26", "NGK26"),
    },
    "g16": {
        "state": RENDER_ROOT / "grp16_state.json",
        "actual": RENDER_ROOT / "g16_rt.json",
        "expected_days": 11,
        "expected_anchor_date": "20260327",
        "expected_roll_date": None,
        "basis_tokens": (),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing required artifact: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return raw


def _state_days(state: dict[str, Any]) -> list[str]:
    return sorted(k for k in state if len(k) == 8 and k.isdigit())


def _actual_days(actual: dict[str, Any]) -> list[str]:
    rows = actual.get("days")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("actual artifact has no days")
    days = []
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("date", "")).isdigit():
            raise RuntimeError("actual artifact contains malformed day row")
        days.append(str(row["date"]))
    return days


def validate_group(gid: str, cfg: dict[str, Any]) -> dict[str, Any]:
    state_path = Path(cfg["state"])
    actual_path = Path(cfg["actual"])
    state = _load(state_path)
    actual = _load(actual_path)

    if str(actual.get("tag")) != gid:
        raise RuntimeError(f"{gid}: actual tag mismatch: {actual.get('tag')!r}")

    state_days = _state_days(state)
    actual_days = _actual_days(actual)
    if state_days != actual_days:
        only_state = sorted(set(state_days) - set(actual_days))
        only_actual = sorted(set(actual_days) - set(state_days))
        raise RuntimeError(
            f"{gid}: state/actual day mismatch; only_state={only_state}, only_actual={only_actual}"
        )

    expected_days = int(cfg["expected_days"])
    if len(actual_days) != expected_days or int(actual.get("n_days", -1)) != expected_days:
        raise RuntimeError(
            f"{gid}: expected {expected_days} matched days, got state={len(state_days)} "
            f"actual={len(actual_days)} n_days={actual.get('n_days')}"
        )

    anchor = actual.get("anchor")
    if not isinstance(anchor, dict) or str(anchor.get("date")) != cfg["expected_anchor_date"]:
        raise RuntimeError(f"{gid}: anchor mismatch: {anchor!r}")

    expected_roll = cfg["expected_roll_date"]
    rolls = actual.get("rolls") or []
    roll_dates = [str(x.get("date")) for x in rolls if isinstance(x, dict)]
    if expected_roll is None:
        if roll_dates:
            raise RuntimeError(f"{gid}: expected no roll, found {roll_dates}")
    elif expected_roll not in roll_dates:
        raise RuntimeError(f"{gid}: expected roll {expected_roll}, found {roll_dates}")

    basis = str(actual.get("price_basis") or actual.get("note") or "")
    for token in cfg["basis_tokens"]:
        if token not in basis:
            raise RuntimeError(f"{gid}: preserved basis does not name {token}")

    return {
        "group": gid,
        "matched_days": len(actual_days),
        "first_day": actual_days[0],
        "last_day": actual_days[-1],
        "anchor_date": str(anchor["date"]),
        "roll_dates": roll_dates,
        "state_sha256": _sha256(state_path),
        "outcome_sha256": _sha256(actual_path),
        "blind_input_contains_outcome": False,
    }


def build_report() -> dict[str, Any]:
    brain = _load(BRAIN)
    results = [validate_group(gid, cfg) for gid, cfg in GROUPS.items()]
    if not brain:
        raise RuntimeError("canonical brain is empty")
    return {
        "schema_version": "1.0",
        "gate": "S118_TWO_GROUP_MATCHED_ARTIFACT_SMOKE",
        "verdict": "PASS",
        "purpose": "structural preflight only; not A-67 evidence and not a forecast run",
        "brain_inherited": True,
        "brain_path": str(BRAIN),
        "brain_sha256": _sha256(BRAIN),
        "brain_mutated": False,
        "spawn_touched": False,
        "blind_seal": {
            "includes": ["canonical brain", "matched decision-state"],
            "excludes": ["realized RT outcome tape"],
        },
        "groups": results,
        "matched_days_total": sum(x["matched_days"] for x in results),
        "next": "run a real causal Frankie forecast on these two groups, then pivot to paper trading",
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
