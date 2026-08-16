#!/usr/bin/env python3
"""S136 target-session brain wall for CURRENT-FRANKIE historical learning runs.

Current Frankie keeps all present-day brain evidence, including evidence learned after the historical
decision date.  Only evidence attributable to the session being forecast is withheld before freeze.
The old S118/S120 wall remains unchanged for every non-brain packet plane.

This module never edits knowledge/ng_brain.json.  It prunes target-attributed evidence from an
in-memory copy, lets brain_view perform its normal target-token/run-finding redaction, and installs a
date-run-only leak wrapper that removes the brain plane before delegating to the original strict
S118/S120 causal leak guard.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

import brain_view
import frankie_s118_redo as s120

_DROP = object()
_DATE8 = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
_ATTR_KEYS = {
    "date", "day", "session_date", "target_date",
    "_window_days", "window_days", "days", "window",
}
_LEAK_KEYS = set(getattr(s120, "_LEAK_FIELDS", (
    "actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd",
)))


def _norm_day(day: str) -> str:
    d = str(day).replace("-", "")
    if len(d) != 8 or not d.isdigit():
        raise s120.ForecastStop(f"S136 invalid target day {day!r}")
    return d


def _dates_in(obj: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            out.update(_dates_in(key))
            out.update(_dates_in(value))
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            out.update(_dates_in(value))
    elif isinstance(obj, str):
        out.update(_DATE8.findall(obj))
        out.update("".join(parts) for parts in _ISO.findall(obj))
    return out


def _attribution_mentions_target(obj: Mapping[str, Any], target: str) -> bool:
    iso = f"{target[:4]}-{target[4:6]}-{target[6:8]}"
    mmdd = target[4:]
    for key in _ATTR_KEYS:
        if key not in obj:
            continue
        value = obj[key]
        text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
        compact = text.replace("-", "")
        if target in compact or iso in text:
            return True
        if re.search(rf"(?<!\d){re.escape(mmdd)}(?!\d)", text):
            return True
    return False


def _group_run_is_target_aggregate(obj: Mapping[str, Any], source_group: str | None) -> bool:
    if not source_group or "group_run" not in obj:
        return False
    text = str(obj.get("group_run") or "")
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(source_group)}(?![A-Za-z0-9])", text, re.I) is not None


def _prune(obj: Any, target: str, source_group: str | None) -> Any:
    if isinstance(obj, Mapping):
        if _attribution_mentions_target(obj, target) or _group_run_is_target_aggregate(obj, source_group):
            return _DROP
        out = {}
        for key, value in obj.items():
            pruned = _prune(value, target, source_group)
            if pruned is not _DROP:
                out[key] = pruned
        return out
    if isinstance(obj, list):
        out = []
        for value in obj:
            pruned = _prune(value, target, source_group)
            if pruned is not _DROP:
                out.append(pruned)
        return out
    if isinstance(obj, tuple):
        vals = []
        for value in obj:
            pruned = _prune(value, target, source_group)
            if pruned is not _DROP:
                vals.append(pruned)
        return vals
    return copy.deepcopy(obj)


def target_safe_brain(raw_brain: Mapping[str, Any], target_day: str, source_group: str | None) -> dict[str, Any]:
    target = _norm_day(target_day)
    pruned = _prune(raw_brain, target, source_group)
    if pruned is _DROP or not isinstance(pruned, dict):
        raise s120.ForecastStop("S136 target brain wall unexpectedly removed the brain root")
    return pruned


def build_role_view(
    raw_brain: Mapping[str, Any],
    *,
    target_day: str,
    source_group: str | None,
    state_day: Mapping[str, Any],
) -> dict[str, Any]:
    target = _norm_day(target_day)
    safe = target_safe_brain(raw_brain, target, source_group)
    view, _served, _withheld = brain_view.build(
        safe, "specialist", phase="working", window_days=[target]
    )
    view = brain_view.annotate_evaluability(view, state_day)
    assert_brain_target_safe(view, target)
    meta = view.setdefault("meta", {})
    meta["s136_current_full_brain_contract"] = {
        "current_full_brain": True,
        "later_learned_evidence": "KEPT",
        "target_session_evidence": "WITHHELD_STRUCTURALLY",
        "historical_cutoff_redaction": False,
        "source_group_aggregate_touching_target": "WITHHELD",
    }
    return view


def assert_brain_target_safe(view: Mapping[str, Any], target_day: str) -> None:
    target = _norm_day(target_day)

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, Mapping):
            # brain_view's own proof marker intentionally names the target date. It is wall
            # metadata, not evidence, so do not mistake the guardrail label for leaked content.
            if path == "brain_view_served.meta.window_redaction":
                return
            if _attribution_mentions_target(obj, target):
                raise s120.ForecastStop(
                    f"S136 target outcome wall: target-attributed brain object survived at {path}"
                )
            leak_keys = _LEAK_KEYS.intersection(str(k) for k in obj.keys())
            if leak_keys:
                dates = _dates_in(obj)
                if not dates:
                    raise s120.ForecastStop(
                        f"S136 target outcome wall: realized brain field(s) {sorted(leak_keys)} "
                        f"lack an attributable date at {path}"
                    )
                if target in dates:
                    raise s120.ForecastStop(
                        f"S136 target outcome wall: realized brain field(s) {sorted(leak_keys)} "
                        f"retain target date {target} at {path}"
                    )
            for key, value in obj.items():
                walk(value, f"{path}.{key}")
        elif isinstance(obj, (list, tuple)):
            for index, value in enumerate(obj):
                walk(value, f"{path}[{index}]")

    walk(view, "brain_view_served")


def install_date_run_leak_guard() -> None:
    """Keep S118/S120 strict everywhere except legal non-target current-brain evidence."""
    original = s120.assert_no_outcome_leak
    if getattr(original, "_s136_target_brain_wrapper", False):
        return

    def guard(text: str, gid: str, day: str) -> None:
        try:
            payload = json.loads(text)
        except Exception:
            return original(text, gid, day)
        if not isinstance(payload, dict) or "brain_view_served" not in payload:
            return original(text, gid, day)

        brain = payload.get("brain_view_served")
        if not isinstance(brain, Mapping):
            raise s120.ForecastStop("S136 packet brain_view_served is missing or malformed")
        assert_brain_target_safe(brain, day)

        causal_payload = dict(payload)
        causal_payload.pop("brain_view_served", None)
        original(json.dumps(causal_payload, sort_keys=True), gid, day)

    guard._s136_target_brain_wrapper = True  # type: ignore[attr-defined]
    guard._s136_original = original  # type: ignore[attr-defined]
    s120.assert_no_outcome_leak = guard
