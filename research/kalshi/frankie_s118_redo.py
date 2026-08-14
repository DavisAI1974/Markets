#!/usr/bin/env python3
"""S118/S120 clean-redo guards for the Frankie validation canary boundary.

This module deliberately leaves the canonical brain, specialist doctrine, and spawn.py untouched.
It repairs only measured harness defects:

A-80/S120: preserve the complete canonical play map and use play_index only as consultation advice.
A-82: permit prior-dated realized evidence while failing closed on own/future/undated outcome data.
A-86/S120: validate the canonical BLD-1 day object and make explicit zero-net abstention representable
while continuing to reject decorative non-zero straight-line paths.

The canonical BLD-1 store currently defines eleven required day fields. The S120 canary boundary adds
one explicit adapter field, ``disposition``, so abstention is structured rather than inferred from
reasoning prose. Do not invent a separate fourteen-field schema here; if a newer canonical contract is
registered, this adapter must be changed to consume that authority directly.
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

# Authority: canonical BLD-1 OUTPUT object in store/sop_templates.json, mirrored here only for
# validation. Keep this tuple byte-for-byte aligned with that object until a single generated schema
# replaces it. S120 explicitly refuses to promote the unlocated "14 fields" narrative to code truth.
CANONICAL_BLD1_DAY_FIELDS = (
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
CANARY_ADAPTER_FIELDS = CANONICAL_BLD1_DAY_FIELDS + ("disposition",)
_ALLOWED_CONFIDENCE = {"low", "med", "high"}
_ALLOWED_DISPOSITIONS = {"CALL", "ABSTAIN"}
_EXPECTED_CLOCK = {20.0, 22.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 17.0, 18.0}

_CANARY_OUTPUT_ADDENDUM = """
S120 CANARY OUTPUT ADAPTER: In addition to every field required by the canonical BLD-1 OUTPUT
object, return one extra top-level string field named `disposition`, exactly `CALL` or `ABSTAIN`.
`ABSTAIN` is a first-class no-call state: it is valid only with guessed_net_usd=0, confidence=low,
and an all-zero canonical session curve. Do not use ABSTAIN for a non-zero directional forecast.
For `CALL`, the canonical A-86 path-shape requirements still apply; a mechanically straight or flat
non-zero path is invalid. Return only the JSON object.
""".strip()


def _play_map(raw_plays: Any) -> dict[str, Any]:
    plays: dict[str, Any] = {}
    if isinstance(raw_plays, Mapping):
        return {str(k): v for k, v in raw_plays.items()}
    if isinstance(raw_plays, list):
        for row in raw_plays:
            if not isinstance(row, Mapping):
                continue
            pid = str(row.get("id") or row.get("play") or row.get("name") or "")
            if pid:
                plays[pid] = row
    return plays


def _index_items(index: Any) -> list[tuple[str, Any]]:
    if isinstance(index, Mapping) and isinstance(index.get("rows"), list):
        index = index["rows"]
    if isinstance(index, Mapping):
        return [(str(k), v) for k, v in index.items()]
    out: list[tuple[str, Any]] = []
    if isinstance(index, list):
        for row in index:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("play") or row.get("name") or row.get("id") or "")
            if name:
                out.append((name, row))
    return out


def full_brain(view: dict[str, Any]) -> dict[str, Any]:
    """S120: keep every canonical play body available; play_index remains consultation guidance.

    S115's contract is additive availability + selective consultation. The prior S118 canary adapter
    violated that contract by replacing the full ``plays`` map with the index-selected subset. We
    still compute the suggested subset for telemetry, but never remove the other canonical bodies.
    """
    out = dict(view)
    plays = _play_map(view.get("plays"))
    if view.get("plays") is not None and not plays:
        raise ForecastStop("A-80/S120: brain plays are present but cannot be resolved by name")

    selected: set[str] = set()
    for name, row in _index_items(view.get("play_index")):
        status = json.dumps(row, sort_keys=True).upper() if isinstance(row, Mapping) else str(row).upper()
        if any(token in status for token in ("ARMED", "PARTIALLY_EVALUABLE", "EVALUABLE")):
            if name in plays:
                selected.add(name)

    out["plays"] = plays
    out["_frankie_serving"] = {
        "canonical_plays_total": len(plays),
        "full_plays_served": len(plays),
        "index_suggested_plays": sorted(selected),
        "index_suggested_count": len(selected),
        "rule": "full canonical play availability; play_index guides selective consultation only",
        "s120_full_availability": True,
    }
    return out


# Backward-compatible name used by the S118 installation seam. Semantics are intentionally no
# longer compaction: the name survives so older wrappers do not become a second serving path.
compact_brain = full_brain


def assert_no_outcome_leak(text: str, gid: str, day: str) -> None:
    """A-82: prior dated evidence is legal; own/future/undated realized evidence is not."""
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
    """Faithful causal packet: full canonical brain availability + leak wall + output adapter."""
    prompt = base._emit_prompt(
        template, gid, day=day, spec=spec, namespace=namespace,
        allow_bridge_deviation=bridge_deviation,
    )
    view_path = base._build_role_view(gid, day, namespace)
    view = full_brain(base._read_json(view_path))
    causal_slice = base._read_json(base._slice_path(gid, day))
    role_files = {
        "shared": base.ROLE_SHARED.read_text(encoding="utf-8"),
        "specialist": base.ROLE_SPEC[spec].read_text(encoding="utf-8"),
    }
    payload = {
        "packet_version": "s120.canary-boundary.1",
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
        "canary_output_adapter": {
            "canonical_bld1_required_fields": list(CANONICAL_BLD1_DAY_FIELDS),
            "adapter_required_fields": list(CANARY_ADAPTER_FIELDS),
            "extra_field": "disposition",
            "allowed_dispositions": sorted(_ALLOWED_DISPOSITIONS),
            "abstain_rule": "ABSTAIN iff zero net + low confidence + all-zero canonical curve",
        },
        "redo_guards": ["A-80/S120-full-brain", "A-82", "A-86/S120-abstain"],
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


def _max_linear_shape_deviation(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    y0, y1 = pts[0][1], pts[-1][1]
    return max(
        abs(y - (y0 + (y1 - y0) * i / (n - 1)))
        for i, (_, y) in enumerate(pts)
    )


def _all_zero_curve(pts: list[tuple[float, float]]) -> bool:
    return all(abs(y) <= 1e-9 for _, y in pts)


def validate_day(payload: Mapping[str, Any], gid: str, day: str, spec: str) -> None:
    """Single S120 canary output boundary: completeness, abstention, and A-86 path semantics."""
    missing = [k for k in CANARY_ADAPTER_FIELDS if k not in payload]
    if missing:
        raise ForecastStop(f"{gid} {day}: S120 day-output contract missing fields {missing}")
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

    confidence = str(payload.get("confidence", "")).lower()
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ForecastStop(f"{gid} {day}: confidence must be low|med|high")
    disposition = str(payload.get("disposition", "")).upper()
    if disposition not in _ALLOWED_DISPOSITIONS:
        raise ForecastStop(f"{gid} {day}: disposition must be CALL|ABSTAIN")

    pts = _curve_points(payload.get("path_p50_curve"), gid, day)
    if abs(pts[0][1]) > 1e-9:
        raise ForecastStop(f"{gid} {day}: curve must start at 0 cumulative USD from the day's open")
    want_last = float(guess) - float(gap)
    if abs(pts[-1][1] - want_last) > 1.0:
        raise ForecastStop(
            f"{gid} {day}: curve last point {pts[-1][1]} != day net ex-gap {want_last}"
        )

    if disposition == "ABSTAIN":
        if abs(float(guess)) > 1e-9 or abs(float(gap)) > 1e-9:
            raise ForecastStop(f"{gid} {day}: ABSTAIN requires zero guessed net and zero overnight gap")
        if confidence != "low":
            raise ForecastStop(f"{gid} {day}: ABSTAIN requires low confidence")
        if not _all_zero_curve(pts):
            raise ForecastStop(f"{gid} {day}: ABSTAIN requires an all-zero canonical curve")
    else:
        max_dev = _max_linear_shape_deviation(pts)
        threshold = max(10.0, 0.03 * max(1.0, abs(pts[-1][1] - pts[0][1])))
        if max_dev < threshold:
            raise ForecastStop(
                f"{gid} {day}: A-86 decorative straight-line curve rejected "
                f"(max shape deviation {max_dev:.1f})"
            )

    if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
        raise ForecastStop(f"{gid} {day}: forecast attempted to enable execution")


def install() -> None:
    """Install the S120 canary-boundary functions into the legacy S118 orchestrator in-process."""
    base._compact_brain = full_brain
    base._packet = packet
    base._validate_day = validate_day
    if _CANARY_OUTPUT_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + _CANARY_OUTPUT_ADDENDUM


if __name__ == "__main__":
    install()
    print(json.dumps({
        "status": "READY",
        "guards": ["A-80/S120-full-brain", "A-82", "A-86/S120-abstain"],
        "canonical_bld1_required_fields": list(CANONICAL_BLD1_DAY_FIELDS),
        "canary_adapter_required_fields": list(CANARY_ADAPTER_FIELDS),
        "brain_modified": False,
        "spawn_modified": False,
        "a84_a85_policy_changed": False,
    }, indent=2, sort_keys=True))