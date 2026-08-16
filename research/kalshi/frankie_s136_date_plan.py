#!/usr/bin/env python3
"""Resolve date intent to one exact, already-declared Frankie historical window.

This module intentionally contains no contract-month arithmetic and no roll heuristic. A run is
admissible only when the requested inclusive date range exactly matches one window already declared
in group_config.py. Contract legs, seam, EIA days, holidays, and anchor are copied from that record.
Anything missing or ambiguous fails before the S135 stager can touch S3.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

import group_config as gc

PLAN_VERSION = "S136_DATE_PLAN_V1"


def _ymd(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            parsed = dt.datetime.strptime(text, fmt).date()
            return parsed.strftime("%Y%m%d")
        except ValueError:
            pass
    raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD or YYYYMMDD")


def _iso(ymd: str) -> str:
    return dt.datetime.strptime(ymd, "%Y%m%d").date().isoformat()


def _fail(message: str) -> RuntimeError:
    return RuntimeError(f"S136 date-plan refused: {message}")


def _validated_declared_window(gid: str, raw: dict[str, Any]) -> dict[str, Any]:
    days = [_ymd(x) for x in raw.get("days", [])]
    if not days:
        raise _fail(f"{gid} has no declared days")
    if days != sorted(days) or len(days) != len(set(days)):
        raise _fail(f"{gid} days are not unique and chronological")

    anchor_date = _ymd(raw.get("anchor_date"))
    if anchor_date >= days[0]:
        raise _fail(f"{gid} anchor_date {anchor_date} is not strictly prior to the window")
    mask_after = _ymd(raw.get("mask_after", anchor_date))
    if mask_after != anchor_date:
        raise _fail(
            f"{gid} mask_after {mask_after} differs from anchor_date {anchor_date}; "
            "date transport cannot prove the same historical boundary"
        )

    anchor = raw.get("anchor")
    if anchor is None:
        raise _fail(f"{gid} has no resolved anchor")
    try:
        anchor = float(anchor)
    except (TypeError, ValueError) as exc:
        raise _fail(f"{gid} anchor is not numeric: {anchor!r}") from exc
    if not math.isfinite(anchor):
        raise _fail(f"{gid} anchor is not finite")

    seam_raw = raw.get("seam")
    seam = _ymd(seam_raw) if seam_raw else None
    legs = raw.get("legs")
    if not isinstance(legs, dict):
        raise _fail(f"{gid} has no declared leg map")
    if seam:
        if seam not in days:
            raise _fail(f"{gid} seam {seam} is outside its declared days")
        if not legs.get("pre") or not legs.get("post"):
            raise _fail(f"{gid} seam exists but pre/post legs are incomplete")
        pre_leg = str(legs["pre"]).lower()
        post_leg = str(legs["post"]).lower()
        declared_stores = {f"ng_mbo_{pre_leg}", f"ng_mbo_{post_leg}"}
    else:
        if not legs.get("all"):
            raise _fail(f"{gid} has no single declared leg")
        pre_leg = str(legs["all"]).lower()
        post_leg = ""
        declared_stores = {f"ng_mbo_{pre_leg}"}

    leg_by_day: dict[str, str] = {}
    for day in days:
        store = gc.leg_for(gid, day)
        if store not in declared_stores:
            raise _fail(
                f"{gid} leg_for({day}) returned {store!r}, outside declared stores "
                f"{sorted(declared_stores)}"
            )
        leg_by_day[day] = store

    eia = [_ymd(x) for x in raw.get("eia_thursdays", [])]
    holidays = [_ymd(x) for x in raw.get("holidays", [])]
    for label, values in (("EIA", eia), ("holiday", holidays)):
        outside = sorted(set(values) - set(days))
        if outside:
            raise _fail(f"{gid} {label} days fall outside the declared window: {outside}")

    return {
        "group": gid,
        "days": days,
        "anchor_date": anchor_date,
        "anchor": anchor,
        "anchor_lasthr_dir": int(raw.get("anchor_lasthr_dir") or 0),
        "mask_after": mask_after,
        "seam": seam,
        "pre_leg": pre_leg,
        "post_leg": post_leg,
        "leg_by_day": leg_by_day,
        "eia": eia,
        "holidays": holidays,
        "basis": str(raw.get("basis") or ""),
    }


def resolve_date_plan(start_date: Any, end_date: Any) -> dict[str, Any]:
    """Resolve an exact configured window or fail closed without inferring a roll."""
    start = _ymd(start_date)
    end = _ymd(end_date)
    if start > end:
        raise _fail(f"start date {start} is after end date {end}")

    matches: list[tuple[str, dict[str, Any]]] = []
    for gid, raw in gc.GROUPS.items():
        declared_days = raw.get("days") if isinstance(raw, dict) else None
        if not declared_days:
            continue
        first = _ymd(declared_days[0])
        last = _ymd(declared_days[-1])
        if first == start and last == end:
            matches.append((str(gid), raw))

    if not matches:
        raise _fail(
            f"{_iso(start)}..{_iso(end)} does not exactly match any declared group_config window; "
            "refusing to infer contract months, roll dates, seams, anchors, or missing sessions"
        )
    if len(matches) != 1:
        gids = [gid for gid, _ in matches]
        raise _fail(
            f"{_iso(start)}..{_iso(end)} matches multiple declared windows {gids}; "
            "refusing an ambiguous contract plan"
        )

    resolved = _validated_declared_window(*matches[0])
    slug = f"{start}_{end}"
    return {
        "plan_version": PLAN_VERSION,
        "start_date": _iso(start),
        "end_date": _iso(end),
        "start_ymd": start,
        "end_ymd": end,
        "resolved_group": resolved["group"],
        "proof": {
            "source": "research/kalshi/group_config.py",
            "mode": "EXACT_DECLARED_WINDOW",
            "contract_roll_inference": "NONE",
        },
        "days": resolved["days"],
        "anchor_date": resolved["anchor_date"],
        "anchor": resolved["anchor"],
        "anchor_lasthr_dir": resolved["anchor_lasthr_dir"],
        "mask_after": resolved["mask_after"],
        "seam": resolved["seam"],
        "pre_leg": resolved["pre_leg"],
        "post_leg": resolved["post_leg"],
        "leg_by_day": resolved["leg_by_day"],
        "eia": resolved["eia"],
        "holidays": resolved["holidays"],
        "basis": resolved["basis"],
        "namespace": f"frankie_s135_date_{slug}",
        "outputs": f"research/kalshi/date_run_outputs/{slug}",
        "render_slug": slug,
    }
