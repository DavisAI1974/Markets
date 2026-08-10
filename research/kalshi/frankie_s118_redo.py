#!/usr/bin/env python3
"""S118 clean-redo guards for the Frankie two-group validation path.

This module deliberately leaves the canonical brain, specialist doctrine, and spawn.py untouched.
It repairs only measured harness defects from the invalid S118 diagnostic run:

A-80: serve the actual indexed play objects instead of silently serving zero plays.
A-82: permit prior-dated realized evidence while failing closed on own/future/undated outcome data.
A-86: refuse one-point-per-day decorative curves and under-specified canonical BLD-1 outputs.

A-84/A-85 are NOT encoded here. They are findings from an invalid/contaminated diagnostic run and
must be earned again by a clean rerun before they can change selection or magnitude policy.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_group_forecast_s118 as base  # noqa: E402

ForecastStop = base.ForecastStop

_DATE8 = re.compile(r"20\d{6}")
_LEAK_FIELDS = ("actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd")
_LEAK_CONTEXT = 500
_REQUIRED_DAY_FIELDS = (
    "specialist",
    "group",
    "date",
    "guessed_net_usd",
    "overnight_gap_usd",
    "path_p50_curve",
    "reasoning",
    "plays_fired",
    "plays_stood_down",
    "confidence",
    "state_defects_and_gaps_reported",
)
_ALLOWED_CONFIDENCE = {"low", "med", "high"}
_EXPECTED_CLOCK = {20.0, 22.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 17.0, 18.0}


def compact_brain(view: dict[str, Any]) -> dict[str, Any]:
    """A-80: preserve the whole index and attach the plays it actually names as usable today."""
    out = {k: v for k, v in view.items() if k != "plays"}
    raw_plays = view.get("plays")
    plays: dict[str, Any] = {}
    if isinstance(raw_plays, Mapping):
        plays = {str(k): v for k, v in raw_plays.items()}
    elif isinstance(raw_plays, list):
        for row in raw_plays:
            if not isinstance(row, Mapping):
                continue
            pid = str(row.get("id") or row.get("play") or row.get("name") or "")
            if pid:
                plays[pid] = row

    index: Any = view.get("play_index")
    if isinstance(index, Mapping) and isinstance(index.get("rows"), list):
        index = index["rows"]

    items: list[tuple[str, Any]] = []
    if isinstance(index, Mapping):
        items = [(str(k), v) for k, v in index.items()]
    elif isinstance(index, list):
        for row in index:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("play") or row.get("name") or row.get("id") or "")
            if name:
                items.append((name, row))

    chosen: set[str] = set()
    for name, row in items:
        status = json.dumps(row, sort_keys=True).upper() if isinstance(row, Mapping) else str(row).upper()
        if any(token in status for token in ("ARMED", "PARTIALLY_EVALUABLE", "EVALUABLE")):
            chosen.add(name)

    selected = {name: plays[name] for name in chosen if name in plays}
    if plays and not selected:
        raise ForecastStop(
            "A-80: brain contains plays but serving selected zero; fail closed instead of running Frankie brainless"
        )

    out["plays"] = selected
    out["_frankie_serving"] = {
        "canonical_plays_total": len(plays),
        "selected_plays": sorted(selected),
        "selected_count": len(selected),
        "rule": "index-selected serving only; canonical brain/view unchanged",
        "a80_zero_play_fail_closed": True,
    }
    return out


def assert_no_outcome_leak(text: str, gid: str, day: str) -> None:
    """A-82: prior dated evidence is legal; own/future/undated realized evidence is not."""
    # The canonical rehearsal banner may NAME a forbidden file in a prohibition. Remove only those
    # explicit 'do not open ...' sentences before checking artifact names; contents remain forbidden.
    scan = re.sub(r"do not open[^\n]+", "", text, flags=re.IGNORECASE)
    for token in (f"{gid}_actual.json", f"{gid}_rt.json"):
        if token in scan:
            raise ForecastStop(f"outcome leak: forbidden artifact {token!r} entered {gid} {day} packet")

    for token in _LEAK_FIELDS:
        start = 0
        while True:
            i = text.find(token, start)
            if i < 0:
                break
            start = i + len(token)
            ctx = text[max(0, i - _LEAK_CONTEXT): i + _LEAK_CONTEXT]
            dates = _DATE8.findall(ctx)
            if not dates:
                raise ForecastStop(
                    f"outcome leak: {token!r} has no attributable historical date in {gid} {day} packet"
                )
            bad = sorted({d for d in dates if d >= day})
            if bad:
                raise ForecastStop(
                    f"outcome leak: {token!r} in {gid} {day} packet is associated with own/future date(s) {bad}"
                )


def packet(template: str, gid: str, day: str, spec: str, namespace: str,
           *, bridge_deviation: bool = False) -> tuple[str, dict[str, Any]]:
    """Same packet as the S118 runner, with repaired brain serving and leak wall."""
    prompt = base._emit_prompt(
        template, gid, day=day, spec=spec, namespace=namespace,
        allow_bridge_deviation=bridge_deviation,
    )
    view_path = base._build_role_view(gid, day, namespace)
    view = compact_brain(base._read_json(view_path))
    causal_slice = base._read_json(base._slice_path(gid, day))
    role_files = {
        "shared": base.ROLE_SHARED.read_text(encoding="utf-8"),
        "specialist": base.ROLE_SPEC[spec].read_text(encoding="utf-8"),
    }
    payload = {
        "packet_version": "s118.redo.1",
        "group": gid,
        "day": day,
        "specialist": spec,
        "template": template,
        "walked_validation_only": True,
        "realized_outcome_in_packet": False,
        "canonical_prompt": prompt,
        "canonical_role_files": role_files,
        "causal_slice": causal_slice,
        "brain_view_served": view,
        "redo_guards": ["A-80", "A-82", "A-86"],
    }
    assert_no_outcome_leak(json.dumps(payload, sort_keys=True), gid, day)
    return prompt, payload


def _curve_points(curve: Any, gid: str, day: str) -> list[tuple[float, float]]:
    if not isinstance(curve, list) or len(curve) < 9:
        raise ForecastStop(f"{gid} {day}: A-86 requires a real intraday curve with >=9 points")
    pts: list[tuple[float, float]] = []
    for p in curve:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ForecastStop(f"{gid} {day}: every path_p50_curve point must be [et_hour, cum_usd]")
        h, v = p
        if isinstance(h, bool) or not isinstance(h, (int, float)):
            raise ForecastStop(f"{gid} {day}: curve ET hour must be numeric")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ForecastStop(f"{gid} {day}: curve cumulative value must be numeric")
        hf = float(h) % 24.0
        if hf not in _EXPECTED_CLOCK:
            raise ForecastStop(f"{gid} {day}: curve hour {h!r} is off the canonical session clock")
        pts.append((hf, float(v)))
    if len({h for h, _ in pts}) < 8:
        raise ForecastStop(f"{gid} {day}: A-86 curve has too few distinct session times")
    return pts


def validate_day(payload: Mapping[str, Any], gid: str, day: str, spec: str) -> None:
    """A-86: canonical completeness + real path shape, not merely list length."""
    missing = [k for k in _REQUIRED_DAY_FIELDS if k not in payload]
    if missing:
        raise ForecastStop(f"{gid} {day}: canonical BLD-1 output missing fields {missing}")
    if str(payload.get("specialist")) != spec:
        raise ForecastStop(f"{gid} {day}: specialist mismatch: {payload.get('specialist')!r}")
    if str(payload.get("group")) != gid:
        raise ForecastStop(f"{gid} {day}: group mismatch: {payload.get('group')!r}")
    if str(payload.get("date", "")).replace("-", "") != day:
        raise ForecastStop(f"{gid} {day}: date mismatch: {payload.get('date')!r}")

    guess = payload.get("guessed_net_usd")
    gap = payload.get("overnight_gap_usd")
    if isinstance(guess, bool) or not isinstance(guess, (int, float)):
        raise ForecastStop(f"{gid} {day}: guessed_net_usd must be numeric")
    if isinstance(gap, bool) or not isinstance(gap, (int, float)):
        raise ForecastStop(f"{gid} {day}: overnight_gap_usd must be numeric")
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise ForecastStop(f"{gid} {day}: reasoning must be non-empty")
    for key in ("plays_fired", "plays_stood_down", "state_defects_and_gaps_reported"):
        if not isinstance(payload.get(key), list):
            raise ForecastStop(f"{gid} {day}: {key} must be a list")
    if str(payload.get("confidence", "")).lower() not in _ALLOWED_CONFIDENCE:
        raise ForecastStop(f"{gid} {day}: confidence must be low|med|high")

    pts = _curve_points(payload.get("path_p50_curve"), gid, day)
    if abs(pts[0][1]) > 1e-9:
        raise ForecastStop(f"{gid} {day}: curve must start at 0 cumulative USD from the day's open")
    want_last = float(guess) - float(gap)
    if abs(pts[-1][1] - want_last) > 1.0:
        raise ForecastStop(
            f"{gid} {day}: curve last point {pts[-1][1]} != day net ex-gap {want_last}"
        )

    # Refuse the exact A-86 failure shape: a straight interpolation of a single daily net.
    n = len(pts)
    y0, y1 = pts[0][1], pts[-1][1]
    max_dev = 0.0
    for i, (_, y) in enumerate(pts):
        linear = y0 + (y1 - y0) * i / (n - 1)
        max_dev = max(max_dev, abs(y - linear))
    if max_dev < max(10.0, 0.03 * max(1.0, abs(y1 - y0))):
        raise ForecastStop(
            f"{gid} {day}: A-86 decorative straight-line curve rejected (max shape deviation {max_dev:.1f})"
        )

    if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
        raise ForecastStop(f"{gid} {day}: forecast attempted to enable execution")


def install() -> None:
    """Install repaired functions into the S118 runner for this process only."""
    base._compact_brain = compact_brain
    base._packet = packet
    base._validate_day = validate_day


if __name__ == "__main__":
    install()
    print(json.dumps({
        "status": "READY",
        "guards": ["A-80", "A-82", "A-86"],
        "brain_modified": False,
        "spawn_modified": False,
        "a84_a85_policy_changed": False,
    }, indent=2, sort_keys=True))
