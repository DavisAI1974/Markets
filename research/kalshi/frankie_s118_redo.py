#!/usr/bin/env python3
"""S118/S120 clean-redo guards for the Frankie validation canary boundary.

This module deliberately leaves the canonical brain, specialist doctrine, and spawn.py untouched.
It repairs only measured harness defects:

A-80/S120: preserve the complete canonical play map and use play_index only as consultation advice.
A-82: permit prior-dated realized evidence while failing closed on own/future/undated outcome data.
A-86/S120: validate the canonical BLD-1 day object and make explicit zero-net abstention representable
while continuing to reject decorative non-zero straight-line paths.
S126: keep Frankie as coordinator while giving specialists A-E the complete causal slice, full brain,
and current Frankie shared runtime/toolbox contract without rewriting any specialist role file.

The canonical BLD-1 store currently defines eleven required day fields. The S120 canary boundary adds
one explicit adapter field, ``disposition``, so abstention is structured rather than inferred from
reasoning prose. Do not invent a separate fourteen-field schema here; if a newer canonical contract is
registered, this adapter must be changed to consume that authority directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_forecaster_s115 as current_frankie  # noqa: E402
import frankie_group_forecast_s118 as base  # noqa: E402

ForecastStop = base.ForecastStop

_DATE8 = re.compile(r"20\d{6}")
_LEAK_FIELDS = ("actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd")
_LEAK_CONTEXT = 500
_SPECIALISTS = frozenset("ABCDE")

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

_SPECIALIST_SHARED_ADDENDUM = """
CURRENT FRANKIE SPECIALIST SHARED CONTRACT — A THROUGH E.
Frankie remains the coordinator. The coordinator selects the canonical owner for the day and does
not average, scale, preselect, summarize-away, or substitute that specialist's forecast.

Your existing A/B/C/D/E lens and canonical role text are unchanged. The lens defines your ownership
and emphasis; it is NOT a data-access filter. The supplied `causal_slice` is the complete served
Frankie decision-state universe that is legal at this day's cutoff, and `brain_view_served` retains
every canonical play body. You may consult any supplied causal field that is relevant to your owned
day. `play_index` is consultation guidance only and never removes availability.

Do not reach outside the packet. Future day blocks and realized target outcomes remain absent in the
blind phase. Do not reconstruct them. Do not alter Frankie settings, schema, inputs, masks, ownership,
role definitions, thresholds, or execution authority. Return only the existing canonical output.
""".strip()


def _count_leaf_values(obj: Any) -> int:
    """Telemetry only: count supplied leaves without filtering or transforming the packet."""
    if isinstance(obj, Mapping):
        return sum(_count_leaf_values(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_leaf_values(v) for v in obj)
    return 1


def _role_hashes(role_files: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("shared", "specialist"):
        text = role_files.get(name)
        if not isinstance(text, str) or not text:
            raise ForecastStop(f"specialist role file {name!r} missing from packet")
        out[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return out


def specialist_shared_context(
    *, spec: str, gid: str, day: str, causal_slice: Mapping[str, Any],
    view: Mapping[str, Any], role_files: Mapping[str, Any],
) -> dict[str, Any]:
    """Additive A-E context over the already-served Frankie packet; no role/data mutation.

    The packet itself is the authority. This function only proves the load-bearing availability and
    causal-wall properties and then exposes the current static Frankie shared runtime contracts.
    It deliberately does not attach lens-book/track-record rows here: historical blind recreations
    may not import later-written memory merely because its event date is earlier.
    """
    if spec not in _SPECIALISTS:
        raise ForecastStop(f"unknown specialist {spec!r}; expected one of {sorted(_SPECIALISTS)}")
    if not isinstance(causal_slice, Mapping) or day not in causal_slice:
        raise ForecastStop(f"{gid} {day}: complete causal slice is missing the decision-day block")

    future_blocks = sorted(
        str(k) for k in causal_slice
        if isinstance(k, str) and _DATE8.fullmatch(k) and k > day
    )
    if future_blocks:
        raise ForecastStop(
            f"{gid} {day}: specialist packet crossed causal wall with future block(s) {future_blocks[:3]}"
        )

    plays = view.get("plays")
    serving = view.get("_frankie_serving")
    if not isinstance(plays, Mapping) or not isinstance(serving, Mapping):
        raise ForecastStop(f"{gid} {day}: full Frankie brain/serving telemetry missing")
    canonical = int(serving.get("canonical_plays_total", -1))
    served = int(serving.get("full_plays_served", -1))
    if canonical != len(plays) or served != len(plays) or canonical <= 0:
        raise ForecastStop(
            f"{gid} {day}: reduced specialist brain refused: canonical={canonical} "
            f"served={served} bodies={len(plays)}"
        )

    day_block = causal_slice.get(day)
    if not isinstance(day_block, Mapping):
        raise ForecastStop(f"{gid} {day}: decision-day state block must be an object")

    return {
        "contract_version": "s126.specialists-current.1",
        "coordinator": "Frankie",
        "coordinator_policy": (
            "select canonical owner per day; never average, scale, preselect, summarize-away, or "
            "substitute the specialist forecast"
        ),
        "specialist": spec,
        "specialist_role_rewritten": False,
        "role_file_sha256": _role_hashes(role_files),
        "complete_served_causal_slice": True,
        "causal_cutoff_day": day,
        "future_day_blocks_present": False,
        "served_day_blocks": sum(
            1 for k in causal_slice if isinstance(k, str) and _DATE8.fullmatch(k)
        ),
        "served_leaf_values": _count_leaf_values(causal_slice),
        "decision_day_top_level_blocks": sorted(str(k) for k in day_block),
        "full_brain_available": True,
        "canonical_play_bodies": canonical,
        "play_index_consultation_only": True,
        "toolbox_catalogue": current_frankie.TOOLBOX,
        "play_policy": current_frankie.PLAY_POLICY,
        "external_state_contract": current_frankie.BPE_CONTRACT,
        "external_state_actions": current_frankie.HARNESS_ACTION_CONTRACT,
        "harness_policy": current_frankie.HARNESS_POLICY,
        "historical_memory_attached": False,
        "historical_memory_rule": (
            "do not backfill later-written lens-book or track-record memory into historical blind calls"
        ),
        "frankie_settings_mutable": False,
        "frankie_schema_mutable": False,
        "frankie_inputs_mutable": False,
        "execution_enabled": False,
    }


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
    """Faithful causal packet: full canonical brain + full state universe + unchanged A-E roles."""
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
        "frankie_specialist_shared_context": specialist_shared_context(
            spec=spec,
            gid=gid,
            day=day,
            causal_slice=causal_slice,
            view=view,
            role_files=role_files,
        ),
        "canary_output_adapter": {
            "canonical_bld1_required_fields": list(CANONICAL_BLD1_DAY_FIELDS),
            "adapter_required_fields": list(CANARY_ADAPTER_FIELDS),
            "extra_field": "disposition",
            "allowed_dispositions": sorted(_ALLOWED_DISPOSITIONS),
            "abstain_rule": "ABSTAIN iff zero net + low confidence + all-zero canonical curve",
        },
        "redo_guards": [
            "A-80/S120-full-brain",
            "A-82",
            "A-86/S120-abstain",
            "S126-A-E-full-current-context",
        ],
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
    """Install current Frankie guards into the legacy S118 orchestrator in-process."""
    base._compact_brain = full_brain
    base._packet = packet
    base._validate_day = validate_day
    if _CANARY_OUTPUT_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + _CANARY_OUTPUT_ADDENDUM
    if _SPECIALIST_SHARED_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + _SPECIALIST_SHARED_ADDENDUM


if __name__ == "__main__":
    install()
    print(json.dumps({
        "status": "READY",
        "guards": [
            "A-80/S120-full-brain",
            "A-82",
            "A-86/S120-abstain",
            "S126-A-E-full-current-context",
        ],
        "specialists": sorted(_SPECIALISTS),
        "coordinator": "Frankie",
        "specialist_roles_rewritten": False,
        "canonical_bld1_required_fields": list(CANONICAL_BLD1_DAY_FIELDS),
        "canary_adapter_required_fields": list(CANARY_ADAPTER_FIELDS),
        "brain_modified": False,
        "spawn_modified": False,
        "a84_a85_policy_changed": False,
    }, indent=2, sort_keys=True))