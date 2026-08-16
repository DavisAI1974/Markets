#!/usr/bin/env python3
"""S132 event-driven curve contract for Frankie.

S131 exposed a harness defect: the historical canary adapter constrained every day to a fixed clock
and encoded ABSTAIN as an all-zero path.  That is not Frankie's forecasting contract.  Frankie must
forecast the *shape implied by the market state* -- acceleration windows, catalyst times, turns,
recoveries and quiet stretches -- and choose the curve nodes needed to express that forecast.

This module is deliberately additive and isolated:
- it does NOT edit S120/S131 history;
- it does NOT edit spawn.py, the brain, or specialist role doctrine;
- it removes any allowed-clock list and any fixed point count;
- it makes ``curve_nodes`` the authoritative event-driven curve description;
- legacy ``path_p50_curve`` remains only as a direct projection for downstream compatibility;
- ABSTAIN means "no trading-direction authority", NOT "the market will be flat".

Each curve node is chosen by Frankie and carries its own market-condition rationale plus a P25/P50/P75
cumulative-from-open envelope.  Decimal ET hours are legal (10.5 == 10:30 ET).  The validator checks
only chronology, distribution ordering, endpoint continuity and projection identity; it never supplies
or requires plot times.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import frankie_s118_redo as s120

ForecastStop = s120.ForecastStop

CANONICAL_BLD1_DAY_FIELDS = tuple(s120.CANONICAL_BLD1_DAY_FIELDS)
S132_REQUIRED_FIELDS = CANONICAL_BLD1_DAY_FIELDS + ("disposition", "curve_nodes")
_ALLOWED_CONFIDENCE = {"low", "med", "high"}
_ALLOWED_DISPOSITIONS = {"CALL", "ABSTAIN"}

S132_OUTPUT_ADDENDUM = r"""
S132 EVENT-DRIVEN CURVE CONTRACT:

Frankie forecasts a FULL CURVE from the market conditions he expects.  DO NOT use a fixed cadence,
fixed grid, evenly spaced filler points, or a memorized list of plot times.  Choose a curve node ONLY
when it is needed to express an expected market-state transition: reopen/gap resolution, liquidity
regime change, scheduled catalyst, acceleration/deceleration, expected turn or absorption window,
recovery, or terminal/settlement state.  Decimal ET hours are allowed and encouraged when the market
clock is specific (for example 10.5 for a 10:30 ET EIA release).

Add one top-level field ``curve_nodes``.  Each item must be an object with:
  - et_hour: numeric ET wall-clock hour in [0,24), decimals allowed;
  - p25_cum_usd: cumulative-from-session-open P25;
  - p50_cum_usd: cumulative-from-session-open P50;
  - p75_cum_usd: cumulative-from-session-open P75;
  - market_condition: non-empty explanation of WHY that node exists and what condition it represents.

Node count is determined by the forecast.  There is NO canonical point count and NO canonical clock.
Nodes must be chronological across at most one midnight wrap and must not duplicate a time.
P25 <= P50 <= P75 at every node.  The first node's cumulative values are 0 because it is the curve's
session-open reference.  The final node's P50 must equal ``guessed_net_usd - overnight_gap_usd``.

``path_p50_curve`` remains required only for compatibility with existing render/coordinator code.  It
must be the exact projection of ``curve_nodes`` as ``[[et_hour, p50_cum_usd], ...]`` -- do not author a
second curve.

ABSTAIN semantics change at this S132 boundary: ABSTAIN means Frankie does not grant directional
trading authority.  It does NOT mean zero expected range, zero curve, or even necessarily zero P50 net.
Frankie must still emit his best full event-driven P50 curve and uncertainty envelope from the state.
Return only the JSON object.
""".strip()


def _num(x: Any, label: str, gid: str, day: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ForecastStop(f"{gid} {day}: {label} must be numeric")
    return float(x)


def _unwrap_hours(hours: list[float], gid: str, day: str) -> list[float]:
    """Map ET wall-clock hours to a monotone session axis without imposing a session grid.

    If the first point is in the evening (>=18), it belongs to the prior calendar day; one decrease
    in wall-clock hour is then the midnight wrap.  If Frankie starts after midnight, no wrap is needed.
    A second/non-monotone wrap is invalid.  This is chronology validation, not a plot-time prior.
    """
    if not hours:
        return []
    out: list[float] = []
    day_offset = -24.0 if hours[0] >= 18.0 else 0.0
    wrapped = day_offset == 0.0
    prev_h: float | None = None
    for h in hours:
        if prev_h is not None and h < prev_h:
            if wrapped:
                raise ForecastStop(f"{gid} {day}: curve_nodes are not chronological (second/backward wrap)")
            day_offset += 24.0
            wrapped = True
        x = h + day_offset
        if out and x <= out[-1]:
            raise ForecastStop(f"{gid} {day}: curve_nodes contain duplicate/non-increasing time {h}")
        out.append(x)
        prev_h = h
    return out


def curve_nodes(payload: Mapping[str, Any], gid: str, day: str) -> list[dict[str, Any]]:
    raw = payload.get("curve_nodes")
    if not isinstance(raw, list) or len(raw) < 2:
        raise ForecastStop(f"{gid} {day}: curve_nodes must contain at least open and terminal nodes")

    nodes: list[dict[str, Any]] = []
    hours: list[float] = []
    for i, node in enumerate(raw):
        if not isinstance(node, Mapping):
            raise ForecastStop(f"{gid} {day}: curve_nodes[{i}] must be an object")
        h = _num(node.get("et_hour"), f"curve_nodes[{i}].et_hour", gid, day)
        if not 0.0 <= h < 24.0:
            raise ForecastStop(f"{gid} {day}: curve node ET hour {h} must be in [0,24)")
        p25 = _num(node.get("p25_cum_usd"), f"curve_nodes[{i}].p25_cum_usd", gid, day)
        p50 = _num(node.get("p50_cum_usd"), f"curve_nodes[{i}].p50_cum_usd", gid, day)
        p75 = _num(node.get("p75_cum_usd"), f"curve_nodes[{i}].p75_cum_usd", gid, day)
        if not p25 <= p50 <= p75:
            raise ForecastStop(
                f"{gid} {day}: curve_nodes[{i}] must satisfy P25<=P50<=P75; got {p25},{p50},{p75}"
            )
        why = node.get("market_condition")
        if not isinstance(why, str) or not why.strip():
            raise ForecastStop(f"{gid} {day}: curve_nodes[{i}].market_condition must be non-empty")
        hours.append(h)
        nodes.append({
            "et_hour": h,
            "p25_cum_usd": p25,
            "p50_cum_usd": p50,
            "p75_cum_usd": p75,
            "market_condition": why.strip(),
        })

    _unwrap_hours(hours, gid, day)

    first = nodes[0]
    if any(abs(first[k]) > 1e-9 for k in ("p25_cum_usd", "p50_cum_usd", "p75_cum_usd")):
        raise ForecastStop(f"{gid} {day}: first curve node must anchor cumulative-from-open at 0")

    return nodes


def projected_p50(nodes: list[dict[str, Any]]) -> list[list[float]]:
    return [[float(n["et_hour"]), float(n["p50_cum_usd"])] for n in nodes]


def validate_day(payload: Mapping[str, Any], gid: str, day: str, spec: str) -> None:
    """Validate the S132 day object without imposing plot times or flat-abstain semantics."""
    missing = [k for k in S132_REQUIRED_FIELDS if k not in payload]
    if missing:
        raise ForecastStop(f"{gid} {day}: S132 day-output contract missing fields {missing}")

    if str(payload.get("specialist")) != spec:
        raise ForecastStop(f"{gid} {day}: specialist mismatch: {payload.get('specialist')!r}")
    if str(payload.get("group")) != gid:
        raise ForecastStop(f"{gid} {day}: group mismatch: {payload.get('group')!r}")
    if str(payload.get("date", "")).replace("-", "") != day:
        raise ForecastStop(f"{gid} {day}: date mismatch: {payload.get('date')!r}")

    guess = _num(payload.get("guessed_net_usd"), "guessed_net_usd", gid, day)
    gap = _num(payload.get("overnight_gap_usd"), "overnight_gap_usd", gid, day)

    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise ForecastStop(f"{gid} {day}: reasoning must be non-empty")
    for key in ("plays_fired", "plays_stood_down", "state_defects_and_gaps_reported"):
        if not isinstance(payload.get(key), list):
            raise ForecastStop(f"{gid} {day}: {key} must be a list")

    confidence = str(payload.get("confidence", "")).lower()
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ForecastStop(f"{gid} {day}: confidence must be low|med|high")
    disposition = str(payload.get("disposition", "")).upper()
    if disposition not in _ALLOWED_DISPOSITIONS:
        raise ForecastStop(f"{gid} {day}: disposition must be CALL|ABSTAIN")
    if disposition == "ABSTAIN" and confidence != "low":
        raise ForecastStop(f"{gid} {day}: ABSTAIN keeps low confidence but does not force a flat curve")

    nodes = curve_nodes(payload, gid, day)
    want_last = guess - gap
    if abs(nodes[-1]["p50_cum_usd"] - want_last) > 1.0:
        raise ForecastStop(
            f"{gid} {day}: terminal curve P50 {nodes[-1]['p50_cum_usd']} != day net ex-gap {want_last}"
        )

    legacy = payload.get("path_p50_curve")
    if not isinstance(legacy, list):
        raise ForecastStop(f"{gid} {day}: path_p50_curve compatibility projection missing")
    expected = projected_p50(nodes)
    try:
        got = [[float(p[0]), float(p[1])] for p in legacy]
    except Exception as exc:
        raise ForecastStop(f"{gid} {day}: malformed path_p50_curve compatibility projection") from exc
    if got != expected:
        raise ForecastStop(
            f"{gid} {day}: path_p50_curve must be the exact P50 projection of authoritative curve_nodes"
        )

    if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
        raise ForecastStop(f"{gid} {day}: forecast attempted to enable execution")


def install() -> None:
    """Install S132 boundary over the legacy forecaster in-process only."""
    s120.install()
    s120.base._validate_day = validate_day
    if S132_OUTPUT_ADDENDUM not in s120.base.MODEL_INSTRUCTIONS:
        s120.base.MODEL_INSTRUCTIONS = s120.base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + S132_OUTPUT_ADDENDUM


def _selftest() -> None:
    good = {
        "specialist": "D", "group": "gX", "date": "20250102",
        "guessed_net_usd": -40, "overnight_gap_usd": 0,
        "path_p50_curve": [[19.25, 0], [10.5, -120], [13.75, 35], [16.92, -40]],
        "curve_nodes": [
            {"et_hour": 19.25, "p25_cum_usd": 0, "p50_cum_usd": 0, "p75_cum_usd": 0,
             "market_condition": "reopen reference"},
            {"et_hour": 10.5, "p25_cum_usd": -300, "p50_cum_usd": -120, "p75_cum_usd": 90,
             "market_condition": "scheduled catalyst / widest uncertainty"},
            {"et_hour": 13.75, "p25_cum_usd": -160, "p50_cum_usd": 35, "p75_cum_usd": 220,
             "market_condition": "expected absorption and counter-move"},
            {"et_hour": 16.92, "p25_cum_usd": -190, "p50_cum_usd": -40, "p75_cum_usd": 130,
             "market_condition": "terminal state"},
        ],
        "reasoning": "event-driven test", "plays_fired": [], "plays_stood_down": [],
        "confidence": "low", "state_defects_and_gaps_reported": [], "disposition": "ABSTAIN",
    }
    validate_day(good, "gX", "20250102", "D")
    assert len(good["curve_nodes"]) == 4
    assert [n["et_hour"] for n in good["curve_nodes"]] == [19.25, 10.5, 13.75, 16.92]

    bad = json.loads(json.dumps(good))
    bad["path_p50_curve"][1][0] = 10.0
    try:
        validate_day(bad, "gX", "20250102", "D")
    except ForecastStop:
        pass
    else:
        raise AssertionError("projection mismatch was not rejected")


if __name__ == "__main__":
    _selftest()
    print(json.dumps({
        "status": "READY",
        "contract": "S132_EVENT_DRIVEN_CURVE",
        "fixed_clock": False,
        "fixed_point_count": False,
        "abstain_forces_flat_curve": False,
        "curve_nodes_authoritative": True,
    }, indent=2, sort_keys=True))
