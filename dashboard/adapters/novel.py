"""Read-only Novel Edge Lab adapter.

The panel is a registry and readiness surface, not an execution service. It reports
which preregistered candidates have local inputs, which are partial, which can be
watched in the next 48 hours, and which balance convention belongs to each structure.
No thresholds, weights, coefficients, orders, credentials, or route authority live here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from . import paths

CONFIG = os.path.join(paths.DASHBOARD, "novel_candidates.json")
ET = ZoneInfo("America/New_York")


def _load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _path_state(rel: str) -> dict:
    absolute = os.path.join(paths.REPO, rel)
    if os.path.isfile(absolute):
        return {"path": rel, "present": True, "kind": "file", "bytes": os.path.getsize(absolute)}
    if os.path.isdir(absolute):
        n_files = sum(len(files) for _, _, files in os.walk(absolute))
        return {"path": rel, "present": n_files > 0, "kind": "directory", "files": n_files}
    return {"path": rel, "present": False, "kind": "missing"}


def _readiness(required: list[str], supporting: list[str]) -> dict:
    req = [_path_state(p) for p in required]
    sup = [_path_state(p) for p in supporting]
    req_present = sum(1 for item in req if item["present"])
    sup_present = sum(1 for item in sup if item["present"])
    if required and req_present == len(required):
        level = "WIRED_INPUTS"
        truth = "real"
    elif req_present or sup_present:
        level = "PARTIAL_INPUTS"
        truth = "partial"
    else:
        level = "AWAITING_DATA"
        truth = "awaiting"
    return {
        "level": level,
        "truth_level": truth,
        "required_present": req_present,
        "required_total": len(req),
        "supporting_present": sup_present,
        "supporting_total": len(sup),
        "required": req,
        "supporting": sup,
    }


def _next_weekday_window(now: dt.datetime, weekday: int, hour: int, minute: int) -> dt.datetime:
    days = (weekday - now.weekday()) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + dt.timedelta(days=days)
    if candidate <= now:
        candidate += dt.timedelta(days=7)
    return candidate


def _immediate_schedule(now: dt.datetime) -> list[dict]:
    windows: list[dict] = []

    # Daily settlement-source watch. This is intentionally a watch window, not a
    # claim that a matching active contract exists; active-rule verification is required.
    for hour, minute, label in ((14, 15, "WTI source/expiry approach"), (16, 45, "5:00 p.m. commodity determination approach")):
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= now:
            when += dt.timedelta(days=1)
        if when.weekday() < 5 and when <= now + dt.timedelta(hours=48):
            windows.append({
                "candidate_id": "COMMODITY_SETTLEMENT_CLOCK_RESIDUAL",
                "label": label,
                "starts_at_et": when.isoformat(timespec="minutes"),
                "authority": "WATCH_ONLY",
                "requires": "Exact active-market rule, source, symbol, and settlement-minute verification",
            })

    # Friday wrapper parity is a natural overlap cell.
    friday = _next_weekday_window(now, 4, 16, 40)
    if friday <= now + dt.timedelta(hours=48):
        windows.append({
            "candidate_id": "KALSHI_DUPLICATE_WRAPPER_PARITY",
            "label": "Daily-versus-weekly rule-hash and executable-book comparison",
            "starts_at_et": friday.isoformat(timespec="minutes"),
            "authority": "WATCH_ONLY",
            "requires": "Full canonical rule hashes and synchronous YES/NO asks",
        })
        windows.append({
            "candidate_id": "KALSHI_COMMODITY_ORACLE_HEALTH",
            "label": "Cross-commodity provider freshness comparison",
            "starts_at_et": friday.isoformat(timespec="minutes"),
            "authority": "WATCH_ONLY",
            "requires": "Provider-grouped active contracts with exact source timestamps",
        })

    # Thursday storage-to-options-to-Kalshi sequence. If the release window has
    # already passed, retain the final settlement comparison when it is still ahead.
    if now.weekday() == 3:
        for hour, minute, label in (
            (10, 29, "EIA storage release: NG options versus Kalshi probability response"),
            (16, 50, "Post-release final NG probability and settlement-source check"),
        ):
            when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now <= when <= now + dt.timedelta(hours=48):
                windows.append({
                    "candidate_id": "CME_KALSHI_DIGITAL_PARITY",
                    "label": label,
                    "starts_at_et": when.isoformat(timespec="minutes"),
                    "authority": "SHADOW",
                    "requires": "Same-month option vertical, executable Kalshi book, fees, and source/clock map",
                })

    windows.sort(key=lambda x: x["starts_at_et"])
    return windows


def snapshot(now: dt.datetime | None = None) -> dict:
    cfg = _load_config()
    now = now.astimezone(ET) if now else dt.datetime.now(ET)
    candidates = []
    for raw in cfg["candidates"]:
        item = dict(raw)
        item["readiness"] = _readiness(raw.get("required_paths", []), raw.get("supporting_paths", []))
        item["execution_enabled"] = False
        item["provenance"] = "PREREGISTERED_CANDIDATE"
        item["status_note"] = (
            "Structural seam: contract or clock logic survives rules scrutiny; profitability remains unproven."
            if "STRUCTURAL" in raw["verdict"] or "CONFIRMED" in raw["verdict"]
            else "Predictive candidate: mechanism is specified, but untouched-forward evidence is not yet present."
        )
        candidates.append(item)

    schedules = _immediate_schedule(now)
    immediate_ids = {w["candidate_id"] for w in schedules}
    for item in candidates:
        item["next_48h_window_active"] = item["id"] in immediate_ids

    wired = sum(1 for c in candidates if c["readiness"]["level"] == "WIRED_INPUTS")
    partial = sum(1 for c in candidates if c["readiness"]["level"] == "PARTIAL_INPUTS")
    awaiting = len(candidates) - wired - partial
    return {
        "schema_version": cfg["schema_version"],
        "generated_at_et": now.isoformat(timespec="seconds"),
        "authority": cfg["authority"],
        "execution_enabled": False,
        "doctrine": cfg["doctrine"],
        "balance_modes": cfg["balance_modes"],
        "summary": {
            "candidates": len(candidates),
            "wired_inputs": wired,
            "partial_inputs": partial,
            "awaiting_data": awaiting,
            "next_48h_watch_windows": len(schedules),
        },
        "immediate_schedule": schedules,
        "candidates": sorted(candidates, key=lambda x: x["rank"]),
        "source_files": [
            "DATA_POINTS.md",
            "research/kalshi/SIGNALS_IN_USE.json",
            "research/kalshi/CHATGPT_S113_A24_HIDDEN_EDGE_CANDIDATES.md",
            "dashboard/novel_candidates.json",
        ],
    }
