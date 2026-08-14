#!/usr/bin/env python3
"""Frankie S121: restore the established kitchen-sink blind curve contract.

This is a Frankie adapter over the historical BLD-1 prompt. It does NOT edit spawn.py or mutate
old blind artifacts. The legacy template remains provenance. For Frankie, this adapter supersedes
only the output-grid mistake: the forecaster chooses its own path timestamps from its predicted
market-state evolution.

Load-bearing doctrine:
- blind gets the kitchen sink; the only deliberate target-period mask is the future/actual price curve;
- all 90 play bodies remain available;
- no coordinator averaging, smoothing, interpolation, signal preselection, or fixed clock grid;
- trade disposition is independent of the market-path forecast. ABSTAIN does not mean flat price.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

import frankie_s118_redo as s120
import frankie_specialist_parity_s126 as s126

ForecastStop = s120.ForecastStop
CANARY_ADAPTER_FIELDS = s120.CANARY_ADAPTER_FIELDS
_ALLOWED_CONFIDENCE = {"low", "med", "high"}
_ALLOWED_DISPOSITIONS = {"CALL", "ABSTAIN"}

S121_OUTPUT_ADDENDUM = """
S121 FRANKIE CURVE ADAPTER — THIS SUPERSEDES ONLY THE LEGACY BLD-1 FIXED 2-HOURLY OUTPUT GRID.
The blind's only deliberate target-period mask is the future/actual PRICE CURVE. Use every causal
market/fundamental input served to you and the complete Frankie brain. YOU decide which evidence
matters and how the expected market evolves.

`path_p50_curve` is your high-resolution blind recreation of the expected FULL trading session.
Choose the number and timestamps of points yourself from the market-state evolution you forecast.
Use many points where needed to represent expected turns, accelerations, fades, event reactions,
liquidity/flow transitions and settlement behavior; quieter stretches may be less dense. There is
NO required cadence and NO canonical clock grid. Do not average signals into artificial points; do
not smooth, interpolate, or manufacture decorative points after deciding a daily net. The path is
the forecast and the daily net is a consequence/check of that path.

Each point is `[et_time, cumulative_usd_from_day_open]`, where `et_time` may be a numeric ET hour
(including fractional hours) or `HH:MM` string. Points must be in chronological session order from
the evening reopen through the close. The first cumulative value is 0. The last cumulative value
must equal `guessed_net_usd - overnight_gap_usd` within the normal rounding tolerance.

A full session may start at 20:00 ET and close at the next day's 20:00 ET. To make that boundary
unambiguous, a terminal repeated `20:00`/`20.0` is interpreted as the NEXT-DAY session close when it
follows later session points. A terminal `24:00`/`24.0` is also accepted as an explicit S121 close
sentinel for that same next-day 20:00 ET boundary. Those close forms are valid only as the final
curve point; ordinary clock values remain in [0,24).

`disposition` remains `CALL` or `ABSTAIN`, but it is a TRADE/NO-CALL disposition only. ABSTAIN does
NOT erase the market forecast and does NOT require zero net, zero gap, low confidence, or a flat
curve. Return your best market-path forecast either way.
""".strip()

_TIME_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})$")


def _et_hour(raw: Any, gid: str, day: str, *, allow_close_sentinel: bool = False) -> float:
    """Parse an ET clock value, allowing 24:00 only as the terminal S121 close sentinel."""
    if isinstance(raw, bool):
        raise ForecastStop(f"{gid} {day}: curve ET time must be numeric hour or HH:MM")
    if isinstance(raw, (int, float)):
        h = float(raw)
        if allow_close_sentinel and math.isfinite(h) and abs(h - 24.0) <= 1e-12:
            return 24.0
    elif isinstance(raw, str):
        text = raw.strip()
        if allow_close_sentinel and text == "24:00":
            return 24.0
        m = _TIME_RE.match(text)
        if not m:
            raise ForecastStop(f"{gid} {day}: curve ET time {raw!r} must be numeric hour or HH:MM")
        hh, mm = int(m.group("h")), int(m.group("m"))
        if hh > 23 or mm > 59:
            raise ForecastStop(f"{gid} {day}: invalid ET time {raw!r}")
        h = hh + mm / 60.0
    else:
        raise ForecastStop(f"{gid} {day}: curve ET time must be numeric hour or HH:MM")
    if not math.isfinite(h) or h < 0 or h >= 24:
        raise ForecastStop(f"{gid} {day}: curve ET time {raw!r} outside [0,24)")
    return h


def _session_position(hour: float) -> float:
    """Hours since the 20:00 ET reopen, allowing the session to cross midnight."""
    return hour - 20.0 if hour >= 20.0 else hour + 4.0


def curve_points(curve: Any, gid: str, day: str) -> list[tuple[float, float]]:
    """Validate endogenous timestamps; intentionally imposes no cadence or exact point count."""
    if not isinstance(curve, list) or len(curve) < 2:
        raise ForecastStop(f"{gid} {day}: path_p50_curve must contain a real session path")
    pts: list[tuple[float, float]] = []
    prior_pos: float | None = None
    for index, point in enumerate(curve):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ForecastStop(f"{gid} {day}: every path point must be [et_time, cumulative_usd]")
        terminal = index == len(curve) - 1
        h = _et_hour(point[0], gid, day, allow_close_sentinel=terminal)
        value = point[1]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ForecastStop(f"{gid} {day}: curve cumulative value must be finite numeric")

        # S124 exposed a real S121 contract gap: a full 20:00 -> 20:00 session could not express its
        # close. Preserve 20:00 as position 0 at the reopen, but interpret a repeated terminal 20:00
        # as the next-day close. 24:00/24.0 is an explicit terminal synonym for the same boundary.
        if terminal and h == 24.0:
            pos = 24.0
        else:
            pos = _session_position(h)
            if terminal and prior_pos is not None and abs(h - 20.0) <= 1e-12 and pos <= prior_pos:
                pos = 24.0

        if prior_pos is not None and pos <= prior_pos:
            raise ForecastStop(f"{gid} {day}: curve timestamps must be strictly chronological")
        prior_pos = pos
        pts.append((pos, float(value)))
    return pts


def _mechanically_linear(pts: list[tuple[float, float]]) -> bool:
    """Reject exact endpoint interpolation, independent of timestamp cadence.

    This intentionally catches only a mechanically exact decorative line. It does not require a
    particular shape and does not reject ordinary near-linear market forecasts.
    """
    if len(pts) <= 2:
        return False
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    if abs(x1 - x0) <= 1e-12:
        return False
    for x, y in pts[1:-1]:
        expected = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        if abs(y - expected) > 1e-7:
            return False
    return True


def validate_day(payload: Mapping[str, Any], gid: str, day: str, spec: str) -> None:
    missing = [k for k in CANARY_ADAPTER_FIELDS if k not in payload]
    if missing:
        raise ForecastStop(f"{gid} {day}: S121 day-output contract missing fields {missing}")
    if str(payload.get("specialist")) != spec:
        raise ForecastStop(f"{gid} {day}: specialist mismatch")
    if str(payload.get("group")) != gid:
        raise ForecastStop(f"{gid} {day}: group mismatch")
    if str(payload.get("date", "")).replace("-", "") != day:
        raise ForecastStop(f"{gid} {day}: date mismatch")

    guess, gap = payload.get("guessed_net_usd"), payload.get("overnight_gap_usd")
    for name, value in (("guessed_net_usd", guess), ("overnight_gap_usd", gap)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ForecastStop(f"{gid} {day}: {name} must be finite numeric")
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise ForecastStop(f"{gid} {day}: reasoning must be non-empty")
    for key in ("plays_fired", "plays_stood_down", "state_defects_and_gaps_reported"):
        if not isinstance(payload.get(key), list):
            raise ForecastStop(f"{gid} {day}: {key} must be a list")
    if str(payload.get("confidence", "")).lower() not in _ALLOWED_CONFIDENCE:
        raise ForecastStop(f"{gid} {day}: confidence must be low|med|high")
    if str(payload.get("disposition", "")).upper() not in _ALLOWED_DISPOSITIONS:
        raise ForecastStop(f"{gid} {day}: disposition must be CALL|ABSTAIN")

    pts = curve_points(payload.get("path_p50_curve"), gid, day)
    if abs(pts[0][1]) > 1e-9:
        raise ForecastStop(f"{gid} {day}: curve must start at 0 cumulative USD from day open")
    want_last = float(guess) - float(gap)
    if abs(pts[-1][1] - want_last) > 1.0:
        raise ForecastStop(f"{gid} {day}: curve endpoint does not reconcile with day net ex-gap")
    if abs(pts[-1][1]) > 1e-9 and _mechanically_linear(pts):
        raise ForecastStop(f"{gid} {day}: A-86 decorative exact endpoint interpolation rejected")
    if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
        raise ForecastStop(f"{gid} {day}: forecast attempted to enable execution")


def install() -> None:
    """Install S120, specialist parity, then S121 curve validation on the current runner."""
    s126.install()
    base = s120.base
    base._validate_day = validate_day
    if S121_OUTPUT_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + S121_OUTPUT_ADDENDUM


if __name__ == "__main__":
    install()
    print("S121 READY: endogenous timestamps; full 20:00 close expressible; ABSTAIN independent of market-path forecast")
