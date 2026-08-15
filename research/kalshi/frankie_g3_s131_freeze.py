#!/usr/bin/env python3
"""Actual-free S131 blind freeze coordinator for current-Frankie G3 replay.

This is the S131 historical-replay equivalent of the SELECT/assemble half of
``group_coordinate_blind.py``.  It deliberately stops BEFORE that canonical coordinator's outcome
access, score and render phase.

It does exactly four things:
1. validate every isolated S131 BLD-1 posterior with the current S120 output/path contract;
2. select the configured owner for each day verbatim (never average, smooth or rewrite a call);
3. enforce both Friday handoff sign-offs and the two A bridge records;
4. freeze the ten daily calls plus the complete 120-point P50 price curve into one isolated artifact.

It NEVER imports/opens ``g3_actual.json``, ``g3_rt.json``, MBO evidence, a scorecard, or any reveal
artifact.  The frozen artifact is the line: scoring is a separate later phase.

S131 is a CURRENT-FRANKIE improvement replay.  The specialists were allowed the current brain's
later learned evidence; only the tested Sep-08..Sep-19 2025 outcomes were withheld.  No hydration or
synthetic historical feed is used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import frankie_s118_redo as s120

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMESPACE = "frankie_g3_s131_corrected_reblind"
FC = HERE / "forecasts" / NAMESPACE
GID = "g3"
DAYS = [
    "20250908", "20250909", "20250910", "20250911", "20250912",
    "20250915", "20250916", "20250917", "20250918", "20250919",
]
OWNERS = {
    "20250908": "B", "20250909": "C", "20250910": "C", "20250911": "D",
    "20250912": "E", "20250915": "B", "20250916": "C", "20250917": "C",
    "20250918": "D", "20250919": "E",
}
ANCHOR_DATE = "20250905"
ANCHOR_CLOSE = 3.026
MULT = 10000
CLOCK = [20.0, 22.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 17.0]
BRIDGES = {
    "20250908": FC / "grp3_Abridge_20250908.json",
    "20250915": FC / "grp3_Abridge_20250915.json",
}
FRIDAYS = ("20250912", "20250919")
ET = ZoneInfo("America/New_York")

# The successful no-reveal packet export that established the corrected S3/state/causal packet plane.
PACKET_EXPORT_RUN_ID = 31912683640
PACKET_EXPORT_COMMIT = "31e4df35ee533666e14a0f0f667a5a728363d70c"
PACKET_ARTIFACT_SHA256 = "ed05e11512d48e032813763dc7e7ff9905a49aaf6b0a5132f86b8a9d9c1cbab7"
S3_INVENTORY_RUN_ID = 31911949696
S3_INVENTORY_COMMIT = "89c21ce7ad4a1e0c8c423e9e9be26a68710f3ede"


class FreezeStop(RuntimeError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeStop(f"cannot read required S131 record {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise FreezeStop(f"expected JSON object: {path}")
    return obj


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _day_path(day: str, owner: str) -> Path:
    return FC / f"grp3_{owner}_{day}.json"


def _validate_bridge(target_day: str, path: Path) -> dict[str, Any]:
    b = _read(path)
    if b.get("specialist") != "A" or b.get("group") != GID:
        raise FreezeStop(f"bridge identity mismatch: {path}")

    # The replay-opening Sep5->Sep8 bridge is intentionally a different boundary object: there is
    # no E Friday posterior before the test window, so it declares ``target_monday`` directly.
    # The in-block Sep12->Sep15 bridge is the normal BLD-2 object and declares ``bridge_for``.
    declared_target = str(b.get("target_monday") or b.get("bridge_for") or "")
    if target_day not in declared_target:
        raise FreezeStop(
            f"bridge {path.name} does not identify target Monday {target_day}: {declared_target!r}"
        )
    if target_day == "20250908" and str(b.get("decision_day")) != ANCHOR_DATE:
        raise FreezeStop(
            f"starter bridge must be cut at declared anchor {ANCHOR_DATE}, got {b.get('decision_day')!r}"
        )

    forbidden = sorted(
        k for k in ("guessed_net_usd", "expected_magnitude_usd", "path_p50_curve",
                    "actual_day_move_usd", "actual_close", "actual_net_usd")
        if k in b
    )
    if forbidden:
        raise FreezeStop(
            f"A bridge {path.name} illegally owns a day forecast/outcome field: {forbidden}"
        )
    return {
        "target_day": target_day,
        "path": str(path.relative_to(HERE)),
        "sha256": _sha(path),
        "specialist": "A",
        "verdict": "BRIDGE_PRESENT_NO_MONDAY_NUMBER",
    }


def _timestamps(day: str, path: list[list[Any]]) -> list[str]:
    base = dt.datetime(int(day[:4]), int(day[4:6]), int(day[6:]), tzinfo=ET)
    out: list[str] = []
    offset = -1 if float(path[0][0]) >= 18 else 0
    prev: float | None = None
    for raw_h, _ in path:
        h = float(raw_h) % 24.0
        if prev is not None and h < prev and offset < 0:
            offset += 1
        ts = base + dt.timedelta(days=offset, hours=h)
        out.append(ts.isoformat())
        prev = h
    return out


def build_freeze() -> dict[str, Any]:
    if sorted(OWNERS) != sorted(DAYS):
        raise FreezeStop("owner map and day list differ")

    day_rows: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    full_curve: list[dict[str, Any]] = []
    running_usd = 0.0

    for day in DAYS:
        owner = OWNERS[day]
        path = _day_path(day, owner)
        payload = _read(path)
        try:
            s120.validate_day(payload, GID, day, owner)
        except Exception as exc:
            raise FreezeStop(f"current S120 output/path contract failed for {day} {owner}: {exc}") from exc

        if day in FRIDAYS and not isinstance(payload.get("handoff_out"), dict):
            raise FreezeStop(f"{day}: FRIDAY SIGN-OFF FAIL - owner E has no handoff_out")

        guess = float(payload["guessed_net_usd"])
        gap = float(payload["overnight_gap_usd"])
        curve = payload["path_p50_curve"]
        hours = [float(p[0]) % 24.0 for p in curve]
        if hours != CLOCK:
            raise FreezeStop(f"{day}: full canonical S131 clock mismatch: {hours}")

        timestamps = _timestamps(day, curve)
        prior_close_cum = running_usd
        open_cum = prior_close_cum + gap
        for ts, (h, cum_from_open) in zip(timestamps, curve):
            cum_anchor = open_cum + float(cum_from_open)
            full_curve.append({
                "timestamp_et": ts,
                "date": day,
                "owner": owner,
                "et_hour": float(h) % 24.0,
                "cum_from_open_usd": float(cum_from_open),
                "cum_from_anchor_usd": cum_anchor,
                "price_p50": round(ANCHOR_CLOSE + cum_anchor / MULT, 6),
            })

        running_usd += guess
        day_rows.append({
            "date": day,
            "owner": owner,
            "disposition": str(payload["disposition"]).upper(),
            "confidence": str(payload["confidence"]).lower(),
            "guess_day_move_usd": int(guess) if guess.is_integer() else guess,
            "overnight_gap_usd": int(gap) if gap.is_integer() else gap,
            "prior_close_cum_usd": int(prior_close_cum) if prior_close_cum.is_integer() else prior_close_cum,
            "close_cum_from_anchor_usd": int(running_usd) if running_usd.is_integer() else running_usd,
            "path_p50": curve,
            "source_path": str(path.relative_to(HERE)),
            "source_sha256": _sha(path),
        })
        source_records.append({
            "date": day,
            "owner": owner,
            "path": str(path.relative_to(HERE)),
            "sha256": _sha(path),
        })

    if len(day_rows) != 10 or len(full_curve) != 120:
        raise FreezeStop(
            f"freeze cardinality mismatch: {len(day_rows)} day rows, {len(full_curve)} curve points"
        )

    bridge_rows = [_validate_bridge(day, BRIDGES[day]) for day in ("20250908", "20250915")]
    brain = HERE / "knowledge" / "ng_brain.json"
    if not brain.is_file():
        raise FreezeStop("current brain file missing")

    calls = sum(1 for d in day_rows if d["disposition"] == "CALL")
    abstains = sum(1 for d in day_rows if d["disposition"] == "ABSTAIN")
    return {
        "artifact_version": "s131.current-frankie-g3.blind-freeze.1",
        "group": GID,
        "phase": "BLIND_FROZEN_BEFORE_REVEAL",
        "replay_type": "current_frankie_historical_improvement_test",
        "not_pristine_holdout": True,
        "window": "2025-09-08..2025-09-19",
        "anchor": {"date": ANCHOR_DATE, "close": ANCHOR_CLOSE, "last_hour_dir": "down"},
        "scored_leg": "NGV25",
        "current_brain_later_learned_evidence_allowed": True,
        "target_window_outcomes_read": False,
        "actuals_read": False,
        "score_or_reveal_phase_present": False,
        "hydration": "REJECTED_NOT_USED",
        "model_api_invoked": False,
        "coordinator_rule": "select configured owner verbatim per day; never average/smooth/rewrite",
        "curve_rule": "full 12-point daily cum-from-open curves chained from the Sep-05 anchor; gap carried separately",
        "brain": {"path": "knowledge/ng_brain.json", "sha256": _sha(brain)},
        "corrected_packet_plane": {
            "workflow_run_id": PACKET_EXPORT_RUN_ID,
            "commit": PACKET_EXPORT_COMMIT,
            "artifact_sha256": PACKET_ARTIFACT_SHA256,
            "packet_count": 12,
            "actuals_read": False,
        },
        "archive_availability_proof": {
            "workflow_run_id": S3_INVENTORY_RUN_ID,
            "commit": S3_INVENTORY_COMMIT,
            "policy": "verified Sep-2025 archive gaps remain unavailable/null; no synthesis/hydration",
        },
        "summary": {
            "days": 10,
            "calls": calls,
            "abstains": abstains,
            "full_curve_points": len(full_curve),
            "terminal_cum_usd": int(running_usd) if running_usd.is_integer() else running_usd,
            "terminal_price_p50": round(ANCHOR_CLOSE + running_usd / MULT, 6),
        },
        "bridges": bridge_rows,
        "source_records": source_records,
        "days": day_rows,
        "full_curve_p50": full_curve,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        print(f"STOP - freeze target already exists; immutable blind must not be overwritten: {args.out}")
        return 2
    try:
        frozen = build_freeze()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "S131_BLIND_FROZEN",
            "out": str(args.out),
            "days": frozen["summary"]["days"],
            "calls": frozen["summary"]["calls"],
            "abstains": frozen["summary"]["abstains"],
            "curve_points": frozen["summary"]["full_curve_points"],
            "terminal_cum_usd": frozen["summary"]["terminal_cum_usd"],
            "actuals_read": frozen["actuals_read"],
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
