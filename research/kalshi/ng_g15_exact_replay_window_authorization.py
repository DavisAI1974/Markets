#!/usr/bin/env python3
"""Bind exact broad-corpus event-time windows to the completed G15 causal replay.

The broad exact-overlap gate proves that L1/dense-trades and MBO share an exact
identity and positive event-time overlap for every expected day.  The G15 replay
completion proves that all canonical G15 states were emitted causally.  This gate
joins those contracts and requires every day's complete replay state span to fit
inside one deterministic contiguous common L1/MBO window before G15 refinement.

It is historical-first and outcome-blind.  It cannot mutate blind forecasts or
posteriors, update ``knowledge/ng_brain.json``, grant execution authority, make CME
event contracts live, substitute IBKR for tastytrade, or start the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_broad_corpus_exact_overlap_gate as overlap
import ng_g15_exact_replay_completion as replay_completion
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES

SCHEMA = "ng_g15_exact_replay_window_authorization.v1"
READY_STATUS = "EXACT_G15_REPLAY_WINDOWS_AUTHORIZED"
READY_WITH_STAND_DOWNS = "EXACT_G15_REPLAY_WINDOWS_AUTHORIZED_WITH_STAND_DOWNS"
BLOCKED_STATUS = "EXACT_G15_REPLAY_WINDOWS_BLOCKED"


class G15ReplayWindowAuthorizationError(ValueError):
    """Raised when exact replay-window evidence is malformed or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G15ReplayWindowAuthorizationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise G15ReplayWindowAuthorizationError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise G15ReplayWindowAuthorizationError(f"{label} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G15ReplayWindowAuthorizationError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise G15ReplayWindowAuthorizationError(f"{label} must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise G15ReplayWindowAuthorizationError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G15ReplayWindowAuthorizationError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise G15ReplayWindowAuthorizationError(f"{label} must be a positive integer")
    return number


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise G15ReplayWindowAuthorizationError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise G15ReplayWindowAuthorizationError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise G15ReplayWindowAuthorizationError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G15ReplayWindowAuthorizationError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G15ReplayWindowAuthorizationError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _source_completion_controls(value: Mapping[str, Any]) -> None:
    for field in (
        "execution_authority",
        "actual_outcomes_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "g16_authorized",
    ):
        if value.get(field) is not False:
            raise G15ReplayWindowAuthorizationError(
                f"exact replay completion must keep {field}=false"
            )
    if value.get("g15_shadow_refinement_authorized") is not True:
        raise G15ReplayWindowAuthorizationError(
            "exact replay completion must authorize G15 SHADOW refinement only"
        )


def _single_interval(day_report: Mapping[str, Any], *, day: str) -> tuple[float, float, list[str]]:
    blockers: list[str] = []
    if day_report.get("status") != "READY":
        blockers.append("BROAD_OVERLAP_DAY_NOT_READY")
    intervals = list(day_report.get("merged_overlap_intervals") or [])
    parsed: list[tuple[float, float]] = []
    for index, raw in enumerate(intervals):
        row = dict(raw)
        start = _finite(row.get("start_s"), label=f"{day}:interval:{index}:start_s")
        end = _finite(row.get("end_s"), label=f"{day}:interval:{index}:end_s")
        if end <= start:
            blockers.append("NON_POSITIVE_COMMON_EVENT_WINDOW")
            continue
        parsed.append((start, end))
    if len(parsed) != 1:
        blockers.append("COMMON_EVENT_WINDOW_NOT_SINGLE_CONTIGUOUS_INTERVAL")
    if not parsed:
        return 0.0, 0.0, sorted(set(blockers))
    return parsed[0][0], parsed[0][1], sorted(set(blockers))


def _day_authorization(
    *,
    day: str,
    overlap_day: Mapping[str, Any] | None,
    completion_day: Mapping[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if overlap_day is None:
        blockers.append("MISSING_BROAD_OVERLAP_DAY")
        overlap_day = {}
    if completion_day is None:
        blockers.append("MISSING_G15_REPLAY_COMPLETION_DAY")
        completion_day = {}

    start, end, interval_blockers = _single_interval(overlap_day, day=day)
    blockers.extend(interval_blockers)
    selected_identity = copy.deepcopy(dict(overlap_day.get("selected_identity") or {}))
    expected = G15_CONTRACT_MAP[day]
    observed_identity = (
        int(selected_identity.get("instrument_id") or 0),
        str(selected_identity.get("raw_symbol") or ""),
    )
    expected_identity = (int(expected["instrument_id"]), str(expected["raw_symbol"]))
    if observed_identity != expected_identity:
        blockers.append("BROAD_OVERLAP_CONTRACT_IDENTITY_MISMATCH")

    completion_identity = (
        int(completion_day.get("instrument_id") or 0),
        str(completion_day.get("raw_symbol") or ""),
    )
    if completion_identity != expected_identity:
        blockers.append("REPLAY_COMPLETION_CONTRACT_IDENTITY_MISMATCH")

    state_count = 0
    first_event = 0.0
    last_event = 0.0
    state_fingerprints: list[str] = []
    try:
        state_count = _positive_int(
            completion_day.get("completed_states"), label=f"{day}:completed_states"
        )
        first_event = _finite(completion_day.get("first_event_s"), label=f"{day}:first_event_s")
        last_event = _finite(completion_day.get("last_event_s"), label=f"{day}:last_event_s")
        if last_event < first_event:
            blockers.append("REPLAY_STATE_RANGE_BACKWARDS")
        state_fingerprints = [str(value or "") for value in completion_day.get("state_fingerprints") or []]
        if len(state_fingerprints) != state_count or any(not value for value in state_fingerprints):
            blockers.append("REPLAY_STATE_FINGERPRINT_COUNT_MISMATCH")
        if start or end:
            if first_event < start or last_event > end:
                blockers.append("REPLAY_STATE_SPAN_OUTSIDE_EXACT_COMMON_WINDOW")
    except G15ReplayWindowAuthorizationError as error:
        blockers.append(str(error))

    stand_down_reasons = {
        str(key): int(value)
        for key, value in dict(completion_day.get("stand_down_reasons") or {}).items()
        if int(value) > 0
    }
    blockers = sorted(set(blockers))
    return {
        "date": day,
        "status": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "selected_identity": selected_identity,
        "common_event_window": {
            "start_s": start,
            "end_s": end,
            "duration_s": max(0.0, end - start),
        },
        "completed_states": state_count,
        "first_state_event_s": first_event,
        "last_state_event_s": last_event,
        "state_fingerprints": state_fingerprints,
        "state_span_inside_common_window": not blockers,
        "start_margin_s": first_event - start if start and first_event else None,
        "end_margin_s": end - last_event if end and last_event else None,
        "stand_down_reasons": dict(sorted(stand_down_reasons.items())),
    }


def _build_unchecked(
    exact_overlap_gate: Mapping[str, Any],
    exact_replay_completion: Mapping[str, Any],
) -> dict[str, Any]:
    overlap_value = copy.deepcopy(dict(exact_overlap_gate))
    completion_value = copy.deepcopy(dict(exact_replay_completion))
    overlap.validate_gate(overlap_value)
    replay_completion.validate_completion(completion_value)
    _authority(overlap_value, label="broad exact-overlap gate")
    _source_completion_controls(completion_value)

    blockers: list[str] = []
    if overlap_value.get("status") != overlap.READY_STATUS:
        blockers.append("BROAD_CORPUS_EXACT_OVERLAP_NOT_VERIFIED")
    if completion_value.get("status") not in {
        replay_completion.READY,
        replay_completion.READY_WITH_STAND_DOWNS,
    }:
        blockers.append("G15_EXACT_REPLAY_NOT_COMPLETE")

    overlap_days = {
        str(row.get("day")): copy.deepcopy(dict(row))
        for row in overlap_value.get("day_reports") or []
    }
    completion_days = {
        str(row.get("date")): copy.deepcopy(dict(row))
        for row in completion_value.get("days") or []
    }
    day_rows = [
        _day_authorization(
            day=day,
            overlap_day=overlap_days.get(day),
            completion_day=completion_days.get(day),
        )
        for day in G15_DATES
    ]
    blocked_days = [row["date"] for row in day_rows if row["status"] == "BLOCKED"]
    stand_down_days = [
        row["date"] for row in day_rows if row.get("stand_down_reasons")
    ]
    for row in day_rows:
        blockers.extend(f"{row['date']}:{reason}" for reason in row.get("blockers") or [])
    blockers = sorted(set(blockers))

    if blockers:
        status = BLOCKED_STATUS
    elif stand_down_days:
        status = READY_WITH_STAND_DOWNS
    else:
        status = READY_STATUS

    window_contract = [
        {
            "date": row["date"],
            "selected_identity": row["selected_identity"],
            "common_event_window": row["common_event_window"],
            "state_fingerprints": row["state_fingerprints"],
        }
        for row in day_rows
    ]
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "market": "NG",
        "group": 15,
        "broad_exact_overlap_fingerprint": overlap_value.get("fingerprint"),
        "exact_replay_completion_fingerprint": completion_value.get("completion_fingerprint"),
        "replay_fingerprint": completion_value.get("replay_fingerprint"),
        "manifest_fingerprint": completion_value.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": completion_value.get("prepared_corpus_fingerprint"),
        "window_contract_fingerprint": _fp(window_contract),
        "canonical_g15_days": list(G15_DATES),
        "day_authorizations": day_rows,
        "blocked_days": blocked_days,
        "stand_down_days": stand_down_days,
        "all_replay_state_spans_inside_exact_common_windows": not blockers,
        "single_contiguous_common_window_required_per_day": True,
        "source_exact_overlap_gate": overlap_value,
        "source_exact_replay_completion": completion_value,
        "blockers": blockers,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": (
            "G15_EXACT_REFINEMENT_FROM_WINDOW_AUTHORIZED_REPLAY"
            if not blockers
            else "REPAIR_G15_REPLAY_EVENT_TIME_WINDOW_ALIGNMENT"
        ),
    }
    result["fingerprint"] = _fp(result)
    return result


def build_authorization(
    exact_overlap_gate: Mapping[str, Any],
    exact_replay_completion: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_unchecked(exact_overlap_gate, exact_replay_completion)
    validate_authorization(result)
    return result


def validate_authorization(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise G15ReplayWindowAuthorizationError(
            "G15 replay-window authorization schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="G15 replay-window authorization")
    expected = _build_unchecked(
        dict(checked.get("source_exact_overlap_gate") or {}),
        dict(checked.get("source_exact_replay_completion") or {}),
    )
    if _canonical(expected) != _canonical(checked):
        raise G15ReplayWindowAuthorizationError(
            "G15 replay-window authorization differs from deterministic reconstruction"
        )
    if checked.get("status") in {READY_STATUS, READY_WITH_STAND_DOWNS}:
        if checked.get("blockers") != [] or checked.get("blocked_days") != []:
            raise G15ReplayWindowAuthorizationError(
                "ready replay-window authorization may not contain blockers"
            )
        if checked.get("all_replay_state_spans_inside_exact_common_windows") is not True:
            raise G15ReplayWindowAuthorizationError(
                "ready replay-window authorization lost exact event-time containment"
            )
        if [row.get("date") for row in checked.get("day_authorizations") or []] != list(G15_DATES):
            raise G15ReplayWindowAuthorizationError(
                "ready replay-window authorization lost canonical G15 day order"
            )
    return copy.deepcopy(dict(value))


def _fixture_sources() -> tuple[dict[str, Any], dict[str, Any]]:
    overlap_days = []
    completion_days = []
    for index, day in enumerate(G15_DATES):
        expected = G15_CONTRACT_MAP[day]
        start = 1000.0 + index * 1000.0
        end = start + 900.0
        overlap_days.append(
            {
                "day": day,
                "status": "READY",
                "selected_identity": {
                    "dataset": "GLBX.MDP3",
                    "publisher_id": 1,
                    "instrument_id": expected["instrument_id"],
                    "raw_symbol": expected["raw_symbol"],
                    "definition_date": "2026-03-01",
                    "definition_start_s": 1.0,
                    "definition_end_s": 9999999999.0,
                },
                "merged_overlap_intervals": [
                    {"start_s": start, "end_s": end, "duration_s": end - start}
                ],
            }
        )
        completion_days.append(
            {
                "date": day,
                "raw_symbol": expected["raw_symbol"],
                "instrument_id": expected["instrument_id"],
                "completed_states": 2,
                "first_event_s": start + 100.0,
                "last_event_s": end - 100.0,
                "stand_down_reasons": {},
                "state_fingerprints": [f"{day}:a", f"{day}:b"],
            }
        )
    overlap_gate = {
        "schema": overlap.SCHEMA,
        "status": overlap.READY_STATUS,
        "fingerprint": "fixture-overlap",
        "day_reports": overlap_days,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    completion = {
        "schema": replay_completion.SCHEMA,
        "status": replay_completion.READY,
        "completion_fingerprint": "fixture-completion",
        "replay_fingerprint": "fixture-replay",
        "manifest_fingerprint": "fixture-manifest",
        "prepared_corpus_fingerprint": "fixture-prepared",
        "days": completion_days,
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "g15_shadow_refinement_authorized": True,
        "g16_authorized": False,
    }
    return overlap_gate, completion


def selftest() -> int:
    original_overlap = overlap.validate_gate
    original_completion = replay_completion.validate_completion
    try:
        overlap.validate_gate = lambda value: value  # type: ignore[assignment]
        replay_completion.validate_completion = lambda value, **kwargs: None  # type: ignore[assignment]
        overlap_gate, completion = _fixture_sources()
        result = build_authorization(overlap_gate, completion)
        assert result["status"] == READY_STATUS
        assert result["all_replay_state_spans_inside_exact_common_windows"] is True
        broken = copy.deepcopy(completion)
        broken["days"][0]["first_event_s"] = 0.0
        blocked = build_authorization(overlap_gate, broken)
        assert blocked["status"] == BLOCKED_STATUS
        assert G15_DATES[0] in blocked["blocked_days"]
    finally:
        overlap.validate_gate = original_overlap
        replay_completion.validate_completion = original_completion
    print("[ng_g15_exact_replay_window_authorization] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-overlap-gate", type=Path)
    parser.add_argument("--exact-replay-completion", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.exact_overlap_gate or not args.exact_replay_completion or not args.out:
        parser.error("--exact-overlap-gate, --exact-replay-completion, and --out are required")
    result = build_authorization(
        _load(args.exact_overlap_gate),
        _load(args.exact_replay_completion),
    )
    _write(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "blocked_days": result["blocked_days"],
                "stand_down_days": result["stand_down_days"],
                "fingerprint": result["fingerprint"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] in {READY_STATUS, READY_WITH_STAND_DOWNS} else 2


if __name__ == "__main__":
    raise SystemExit(main())
