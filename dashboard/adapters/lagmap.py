"""Lag execution map adapter (feed M store: data/kalshi_echo/lag_map.jsonl).

Serves the per-cell expected-window numbers the UI must use instead of any fixed
7-20s constant (KALSHI_ECHO_MAP_S100 consequence 1). Cells = moneyness band x move
class x am/pm, settle-adjacent rows excluded from summaries exactly as the map's own
summarize() does. Per-event rows remain the store; the summary is a descriptor.
All numbers are regime-stamped: this life is the SPRING LOW-VOL regime.
"""
from __future__ import annotations

import json
import os

from . import paths

STORE = os.path.join(paths.DATA, "kalshi_echo", "lag_map.jsonl")
REGIME_NOTE = ("regime: KXNATGASD life Mar 30 - Jul 17 2026 (spring low-vol). Winter numbers "
               "WILL differ; the map re-measures at first cold via the live collector.")

_cache: dict = {}


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * q))
    return sorted_vals[idx]


def _load_rows() -> list[dict] | None:
    if not os.path.exists(STORE):
        return None
    mtime = os.path.getmtime(STORE)
    if _cache.get("mtime") != mtime:
        rows = []
        with open(STORE) as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        _cache["rows"] = rows
        _cache["mtime"] = mtime
    return _cache["rows"]


def available() -> bool:
    return os.path.exists(STORE)


def summary() -> dict:
    rows = _load_rows()
    if rows is None:
        return {"available": False,
                "reason": f"{os.path.relpath(STORE, paths.REPO)} absent - "
                          "platform_sync pull --prefix kalshi_echo/ first"}
    body = [r for r in rows if not r.get("near_bracket_settle")]
    cells: dict[tuple, list[float]] = {}
    band_all: dict[str, int] = {}
    band_resp: dict[str, int] = {}
    days = set()
    for r in body:
        days.add(r["day"])
        band = r.get("band", "?")
        band_all[band] = band_all.get(band, 0) + 1
        if r.get("delay_s") is not None:
            band_resp[band] = band_resp.get(band, 0) + 1
            tod = "am" if r.get("et_hour", 12) < 12 else "pm"
            cells.setdefault((band, r.get("cls", "?"), tod), []).append(r["delay_s"])
    cell_rows = []
    for (band, cls, tod), vals in sorted(cells.items()):
        vals.sort()
        cell_rows.append({
            "band": band, "cls": cls, "tod": tod, "n": len(vals),
            "delay_min_s": round(vals[0], 1),
            "delay_med_s": round(_quantile(vals, 0.5), 1),
            "delay_p90_s": round(_quantile(vals, 0.9), 1),
        })
    return {
        "available": True,
        "n_rows": len(rows),
        "n_rows_summarized": len(body),
        "n_event_days": len(days),
        "day_range": [min(days), max(days)] if days else None,
        "response_rate_by_band": {
            b: {"responded": band_resp.get(b, 0), "total": band_all.get(b, 0),
                "rate": round(band_resp.get(b, 0) / band_all[b], 4) if band_all.get(b) else None}
            for b in sorted(band_all)
        },
        "cells": cell_rows,
        "note": ("per-cell DESCRIPTORS of the per-event store, settle-adjacent excluded; "
                 "never a pooled verdict. " + REGIME_NOTE),
    }


def expected_window(band: str = "ATM", cls: str | None = None, tod: str | None = None) -> dict:
    """The expected-window chip's numbers for one cell (or the band aggregated across
    cls/tod when unspecified) - the replacement for any fixed-seconds constant."""
    rows = _load_rows()
    if rows is None:
        return {"available": False, "reason": "lag map store absent"}
    vals = sorted(
        r["delay_s"] for r in rows
        if not r.get("near_bracket_settle") and r.get("delay_s") is not None
        and r.get("band") == band
        and (cls is None or r.get("cls") == cls)
        and (tod is None or ("am" if r.get("et_hour", 12) < 12 else "pm") == tod)
    )
    if not vals:
        return {"available": True, "band": band, "cls": cls, "tod": tod, "n": 0,
                "note": "no responded rows in this cell"}
    return {
        "available": True, "band": band, "cls": cls, "tod": tod, "n": len(vals),
        "delay_min_s": round(vals[0], 1),
        "delay_med_s": round(_quantile(vals, 0.5), 1),
        "delay_p90_s": round(_quantile(vals, 0.9), 1),
        "note": ("fast tail (min ~0s) = liquid margin; minutes-scale median = thin-bracket "
                 "fill reality - both true, never conflate. " + REGIME_NOTE),
    }


def events_for_day(day_iso: str, limit: int = 200) -> dict:
    """Per-event rows for one event-day - the UI's per-event evidence table."""
    rows = _load_rows()
    if rows is None:
        return {"available": False, "reason": "lag map store absent"}
    day_rows = [r for r in rows if r.get("day") == day_iso][:limit]
    return {"available": True, "day": day_iso, "n": len(day_rows), "rows": day_rows}
