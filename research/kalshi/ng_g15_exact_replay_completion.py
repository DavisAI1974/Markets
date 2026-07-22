#!/usr/bin/env python3
"""Fail-closed completion contract for the exact-basis G15 causal replay.

This module joins the already-separated provenance layers without replaying data or
reading outcomes:

* ``ng_g15_replay_manifest_bridge.v1`` proves the 24 observed L1/MBO lanes are on
  the exact NGJ26/NGK26 basis and exposes the canonical READY manifest;
* ``ng_historical_prepared_corpus.v1`` proves those exact objects were
  materialized, hash-checked, and normalized; and
* ``ng_historical_prepared_replay.v1`` proves the prepared corpus traversed the
  same NGLiveOperator -> ng_rt_feature_state path intended for live use.

The result authorizes only the next G15 SHADOW-refinement stage. It never reads
actual outcomes, never changes the blind prior or forecast, never updates
``ng_brain.json``, and never grants execution authority. Sequence gaps are allowed
only when the resulting feature states visibly stand down. Duplicate records,
missing session coverage, hidden gaps, provenance mismatches, or pre-anchor states
block completion.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from ng_g15_anchor import assert_anchor_precedes_state, validate_anchor
from ng_g15_replay_manifest_bridge import validate_bridge_output
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, validate_manifest
from ng_historical_prepare import PrepareError, validate_prepared_index
from ng_rt_feature_state import validate_chronological, validate_feature_state

SCHEMA = "ng_g15_exact_replay_completion.v1"
REPLAY_SCHEMA = "ng_historical_replay.v1"
PREPARED_REPLAY_SCHEMA = "ng_historical_prepared_replay.v1"
READY = "EXACT_CAUSAL_REPLAY_READY"
READY_WITH_STAND_DOWNS = "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS"
DIRECTIONS = ("up", "flat", "down")


class ExactReplayCompletionError(ValueError):
    """Raised when the exact-basis causal replay is not truthfully complete."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(number):
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}")
    return number


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}") from error
    if number <= 0:
        raise ExactReplayCompletionError(f"{name} must be positive")
    return number


def _normalize_prior(value: Mapping[str, Any]) -> dict[str, float]:
    probabilities = {
        name: max(0.0, _finite(value.get(name), f"blind_prior.{name}"))
        for name in DIRECTIONS
    }
    total = sum(probabilities.values())
    if total <= 0:
        raise ExactReplayCompletionError("blind prior has no positive probability mass")
    return {name: probabilities[name] / total for name in DIRECTIONS}


def _replay_envelope(replay: Mapping[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(replay))
    if candidate.get("schema") != REPLAY_SCHEMA:
        raise ExactReplayCompletionError(f"unexpected replay schema: {candidate.get('schema')}")
    if candidate.get("prepared_replay_schema") != PREPARED_REPLAY_SCHEMA:
        raise ExactReplayCompletionError("replay did not come from the prepared-index adapter")
    if candidate.get("authority") != "HISTORICAL_REFINE_REPLAY_ONLY":
        raise ExactReplayCompletionError("replay authority is invalid")
    if candidate.get("execution_authority") is not False:
        raise ExactReplayCompletionError("replay cannot grant execution authority")
    if int(candidate.get("group") or 0) != 15 or candidate.get("market") != "NG":
        raise ExactReplayCompletionError("replay must describe G15 NG")
    if not isinstance(candidate.get("sequence_gaps"), list):
        raise ExactReplayCompletionError("replay sequence_gaps must be visible")
    if not isinstance(candidate.get("duplicate_records"), list):
        raise ExactReplayCompletionError("replay duplicate_records must be visible")
    return candidate


def _flatten_and_validate_states(
    replay: Mapping[str, Any],
    *,
    anchor: dict[str, Any],
    normalized_prior: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    states: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observed_streams: set[tuple[int, str, str]] = set()

    streams = replay.get("streams")
    if not isinstance(streams, list) or not streams:
        raise ExactReplayCompletionError("replay contains no instrument streams")

    for raw_stream in streams:
        stream = dict(raw_stream)
        instrument = dict(stream.get("instrument") or {})
        identity = (
            int(instrument.get("instrument_id") or 0),
            str(instrument.get("raw_symbol") or ""),
            str(instrument.get("definition_date") or ""),
        )
        if identity in observed_streams:
            raise ExactReplayCompletionError(f"duplicate replay instrument stream: {identity}")
        observed_streams.add(identity)
        stream_states = [copy.deepcopy(dict(row)) for row in stream.get("states") or []]
        if int(stream.get("n_states") or 0) != len(stream_states):
            raise ExactReplayCompletionError(f"replay n_states mismatch for {identity}")
        validate_chronological(stream_states)

        for state in stream_states:
            validate_feature_state(state)
            if state.get("source_mode") != "historical_replay":
                raise ExactReplayCompletionError("G15 completion accepts historical-replay states only")
            if state.get("completed_mbo_event_boundary") is not True:
                raise ExactReplayCompletionError("feature state was not emitted on a completed MBO boundary")
            day = str(state.get("session_day") or "")
            expected = G15_CONTRACT_MAP.get(day)
            if expected is None:
                raise ExactReplayCompletionError(f"feature state is outside canonical G15: {day!r}")
            state_instrument = dict(state.get("instrument") or {})
            if (
                int(state_instrument.get("instrument_id") or 0),
                str(state_instrument.get("raw_symbol") or ""),
            ) != (expected["instrument_id"], expected["raw_symbol"]):
                raise ExactReplayCompletionError(f"{day}: feature-state contract identity mismatch")
            if dict(state.get("blind_prior") or {}) != normalized_prior:
                raise ExactReplayCompletionError(f"{day}: feature-state blind prior differs from locked prior")
            assert_anchor_precedes_state(anchor, state)
            by_day[day].append(state)
            states.append(state)

    missing = [day for day in G15_DATES if not by_day.get(day)]
    if missing:
        raise ExactReplayCompletionError("replay emitted no completed state for: " + ", ".join(missing))

    day_summary: dict[str, dict[str, Any]] = {}
    for day in G15_DATES:
        ordered = sorted(
            by_day[day],
            key=lambda row: (
                _finite(row.get("as_of_event_s"), "as_of_event_s"),
                int(row.get("sequence") or 0),
            ),
        )
        stand_down = Counter(
            str(reason)
            for state in ordered
            for reason in (state.get("availability") or {}).get("stand_down_reasons") or []
        )
        day_summary[day] = {
            "date": day,
            "raw_symbol": G15_CONTRACT_MAP[day]["raw_symbol"],
            "instrument_id": G15_CONTRACT_MAP[day]["instrument_id"],
            "completed_states": len(ordered),
            "first_event_s": ordered[0]["as_of_event_s"],
            "last_event_s": ordered[-1]["as_of_event_s"],
            "flow_allowed_states": sum(
                bool((state.get("availability") or {}).get("flow_update_allowed"))
                for state in ordered
            ),
            "queue_allowed_states": sum(
                bool((state.get("availability") or {}).get("queue_update_allowed"))
                for state in ordered
            ),
            "stand_down_reasons": dict(sorted(stand_down.items())),
            "state_fingerprints": [state.get("feature_fingerprint") for state in ordered],
        }
    return states, day_summary


def build_completion(
    *,
    bridge: dict[str, Any],
    prepared_index: dict[str, Any],
    replay: dict[str, Any],
    anchor: dict[str, Any],
    blind_prior: dict[str, Any],
    verify_prepared_files: bool = True,
) -> dict[str, Any]:
    """Validate the exact-basis provenance chain and authorize G15 SHADOW refinement."""
    originals = [copy.deepcopy(item) for item in (bridge, prepared_index, replay, anchor, blind_prior)]
    validate_bridge_output(bridge)
    validate_anchor(anchor)
    try:
        validate_prepared_index(prepared_index, verify_files=verify_prepared_files)
    except PrepareError as error:
        raise ExactReplayCompletionError(str(error)) from error

    manifest = dict(bridge.get("manifest") or {})
    manifest_report = validate_manifest(manifest)
    if manifest_report.get("status") != "READY" or manifest_report.get("can_replay_all_g15") is not True:
        raise ExactReplayCompletionError("bridge manifest is no longer READY")
    if manifest.get("basis_status") != "MATCHED_L1_MBO_READY":
        raise ExactReplayCompletionError("bridge manifest is not exact matched L1+MBO basis")

    manifest_fingerprint = _fingerprint(manifest)
    if prepared_index.get("manifest_fingerprint") != manifest_fingerprint:
        raise ExactReplayCompletionError("prepared corpus does not belong to the exact-basis bridge manifest")
    if int(prepared_index.get("source_count") or 0) != 26:
        raise ExactReplayCompletionError("prepared corpus must contain exactly 26 canonical sources")

    replay_checked = _replay_envelope(replay)
    if replay_checked.get("prepared_corpus_fingerprint") != prepared_index.get("prepared_corpus_fingerprint"):
        raise ExactReplayCompletionError("replay references a different prepared corpus")
    if replay_checked.get("prepared_manifest_fingerprint") != manifest_fingerprint:
        raise ExactReplayCompletionError("replay references a different exact-basis manifest")
    if int(replay_checked.get("prepared_source_count") or 0) != 26:
        raise ExactReplayCompletionError("replay did not consume all 26 prepared sources")
    if replay_checked.get("manifest_report") != manifest_report:
        raise ExactReplayCompletionError("replay manifest report differs from the exact-basis bridge")

    expected_prior_fingerprint = _fingerprint(blind_prior)
    if replay_checked.get("blind_prior_fingerprint") != expected_prior_fingerprint:
        raise ExactReplayCompletionError("replay blind-prior fingerprint mismatch")
    normalized_prior = _normalize_prior(blind_prior)

    processed = dict(replay_checked.get("processed_records") or {})
    for name in ("definition", "trade", "mbo"):
        _positive_int(processed.get(name), f"processed_records.{name}")
    completed_boundaries = _positive_int(
        replay_checked.get("completed_mbo_event_boundaries"),
        "completed_mbo_event_boundaries",
    )

    duplicates = list(replay_checked.get("duplicate_records") or [])
    if duplicates:
        raise ExactReplayCompletionError("duplicate historical records block exact replay completion")

    states, day_summary = _flatten_and_validate_states(
        replay_checked,
        anchor=anchor,
        normalized_prior=normalized_prior,
    )
    if completed_boundaries != len(states):
        raise ExactReplayCompletionError(
            "completed_mbo_event_boundaries does not equal the emitted feature-state count"
        )

    sequence_gaps = list(replay_checked.get("sequence_gaps") or [])
    visible_gap_stand_down = any(
        "collector_skipped_records" in summary["stand_down_reasons"]
        for summary in day_summary.values()
    )
    if sequence_gaps and not visible_gap_stand_down:
        raise ExactReplayCompletionError("sequence gaps exist without a visible collector stand-down")

    stand_down_count = sum(
        sum(int(count) for count in summary["stand_down_reasons"].values())
        for summary in day_summary.values()
    )
    status = READY_WITH_STAND_DOWNS if sequence_gaps or stand_down_count else READY
    completion = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": status,
        "authority": "EXACT_HISTORICAL_REPLAY_COMPLETION_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "g15_shadow_refinement_authorized": True,
        "g16_authorized": False,
        "basis_status": manifest["basis_status"],
        "bridge_fingerprint": bridge.get("fingerprint"),
        "manifest_fingerprint": manifest_fingerprint,
        "prepared_corpus_fingerprint": prepared_index.get("prepared_corpus_fingerprint"),
        "replay_fingerprint": _fingerprint(replay_checked),
        "anchor_fingerprint": anchor.get("anchor_fingerprint"),
        "blind_prior_fingerprint": expected_prior_fingerprint,
        "prepared_source_count": int(replay_checked["prepared_source_count"]),
        "processed_records": processed,
        "completed_mbo_event_boundaries": completed_boundaries,
        "emitted_feature_states": len(states),
        "sequence_gaps": sequence_gaps,
        "duplicate_records": [],
        "stand_down_event_count": stand_down_count,
        "days": [day_summary[day] for day in G15_DATES],
        "next_required_stage": "ng_g15_pipeline.run_pipeline",
        "note": (
            "Exact matched L1+MBO provenance, preparation, and deterministic replay are complete. "
            "This artifact authorizes SHADOW refinement only; skill remains unscored and G16 remains blocked."
        ),
    }
    completion["completion_fingerprint"] = _fingerprint(completion)

    if [bridge, prepared_index, replay, anchor, blind_prior] != originals:
        raise ExactReplayCompletionError("completion validation mutated its source artifacts")
    return completion


def validate_completion(
    completion: dict[str, Any],
    *,
    bridge: dict[str, Any] | None = None,
    prepared_index: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
    blind_prior: dict[str, Any] | None = None,
) -> None:
    candidate = copy.deepcopy(completion)
    observed = candidate.pop("completion_fingerprint", None)
    if candidate.get("schema") != SCHEMA or candidate.get("status") not in {
        READY,
        READY_WITH_STAND_DOWNS,
    }:
        raise ExactReplayCompletionError("unexpected or non-ready completion artifact")
    if observed != _fingerprint(candidate):
        raise ExactReplayCompletionError("completion artifact fingerprint mismatch")
    for name in (
        "execution_authority",
        "actual_outcomes_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "g16_authorized",
    ):
        if candidate.get(name) is not False:
            raise ExactReplayCompletionError(f"completion artifact must keep {name}=false")
    if candidate.get("g15_shadow_refinement_authorized") is not True:
        raise ExactReplayCompletionError("completion artifact must authorize only G15 SHADOW refinement")
    if [row.get("date") for row in candidate.get("days") or []] != list(G15_DATES):
        raise ExactReplayCompletionError("completion artifact lost canonical G15 day order")
    if bridge is not None and candidate.get("bridge_fingerprint") != bridge.get("fingerprint"):
        raise ExactReplayCompletionError("completion references a different bridge")
    if prepared_index is not None and candidate.get(
        "prepared_corpus_fingerprint"
    ) != prepared_index.get("prepared_corpus_fingerprint"):
        raise ExactReplayCompletionError("completion references a different prepared corpus")
    if replay is not None and candidate.get("replay_fingerprint") != _fingerprint(replay):
        raise ExactReplayCompletionError("completion references a different replay")
    if anchor is not None and candidate.get("anchor_fingerprint") != anchor.get("anchor_fingerprint"):
        raise ExactReplayCompletionError("completion references a different anchor")
    if blind_prior is not None and candidate.get("blind_prior_fingerprint") != _fingerprint(blind_prior):
        raise ExactReplayCompletionError("completion references a different blind prior")


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    from ng_g15_anchor import anchor_fingerprint
    from ng_g15_replay_manifest_bridge import (
        _fixture_catalog,
        _fixture_inventory,
        build_replay_manifest,
    )
    from ng_rt_feature_state import build_feature_state

    inventory = _fixture_inventory()
    bridge = build_replay_manifest(inventory, _fixture_catalog(inventory))
    manifest = bridge["manifest"]
    prepared_index = {
        "schema": "ng_historical_prepared_corpus.v1",
        "market": "NG",
        "group": 15,
        "status": "READY",
        "authority": "HISTORICAL_REPLAY_INPUT_ONLY",
        "execution_authority": False,
        "manifest_fingerprint": _fingerprint(manifest),
        "manifest_report": bridge["manifest_report"],
        "output_dir": "/fixture/not-materialized",
        "source_count": 26,
        "sources": [],
    }
    prepared_index["prepared_corpus_fingerprint"] = _fingerprint(prepared_index)

    anchor = {
        "schema": "ng_g15_anchor.v1",
        "date": "20260313",
        "cutoff_event_s": 1000.0,
        "hour_start_event_s": 900.0,
        "hour_end_event_s": 999.0,
        "authority": "REFINE_ANCHOR_ONLY",
        "execution_authority": False,
        "instrument": {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
        },
        "prices": {
            "first": 3.1,
            "last": 3.132,
            "high": 3.14,
            "low": 3.09,
            "net_usd": 320,
        },
        "direction": "up",
        "trade_count": 10,
    }
    anchor["anchor_fingerprint"] = anchor_fingerprint(anchor)
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}

    streams: dict[str, list[dict[str, Any]]] = {"NGJ26": [], "NGK26": []}
    sequence_by_symbol = {"NGJ26": 0, "NGK26": 0}
    for offset, day in enumerate(G15_DATES, 1):
        contract = G15_CONTRACT_MAP[day]
        symbol = contract["raw_symbol"]
        sequence_by_symbol[symbol] += 1
        event_time = 1000.0 + offset * 100.0
        operator = {
            "schema": "ng_live_operator.v1",
            "authority": "MARKET_DATA_ONLY",
            "as_of_event_s": event_time,
            "move_onset_pressure": {
                "value": 0.1,
                "regime": "quiet",
                "activity_ratio": 1.0,
                "price_efficiency": 0.5,
            },
            "signed_flow": {"imbalance": 0.2},
            "divergence_exhaustion": {"state": "none"},
            "mbo_queue": {
                "book_complete": True,
                "snapshot_complete": True,
                "maybe_bad_book": False,
                "consumed_side": None,
                "far_side_recruitment": 0.0,
            },
            "data_quality": {
                "book_complete": True,
                "snapshot_active": False,
                "trade_events_60s": 6,
                "trade_events_15m": 20,
                "complete_mbo_events": 1,
                "missing_order_events": 0,
            },
        }
        state = build_feature_state(
            blind_prior=prior,
            operator_snapshot=operator,
            instrument_identity={
                "dataset": "GLBX.MDP3",
                "publisher_id": 1,
                "instrument_id": contract["instrument_id"],
                "raw_symbol": symbol,
                "definition_date": "2026-03-01" if symbol == "NGJ26" else "2026-03-20",
            },
            decision_cutoff_s=event_time,
            horizon="close",
            source_mode="historical_replay",
            sequence=sequence_by_symbol[symbol],
        )
        state["session_day"] = day
        state["completed_mbo_event_boundary"] = True
        streams[symbol].append(state)

    replay = {
        "schema": REPLAY_SCHEMA,
        "prepared_replay_schema": PREPARED_REPLAY_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_REPLAY_ONLY",
        "execution_authority": False,
        "blind_prior_fingerprint": _fingerprint(prior),
        "manifest_report": bridge["manifest_report"],
        "processed_records": {"definition": 2, "trade": 72, "mbo": 12},
        "completed_mbo_event_boundaries": 12,
        "sequence_gaps": [],
        "duplicate_records": [],
        "streams": [
            {
                "instrument": {
                    "dataset": "GLBX.MDP3",
                    "publisher_id": 1,
                    "instrument_id": 1008 if symbol == "NGJ26" else 996,
                    "raw_symbol": symbol,
                    "definition_date": "2026-03-01" if symbol == "NGJ26" else "2026-03-20",
                },
                "n_states": len(streams[symbol]),
                "states": streams[symbol],
            }
            for symbol in ("NGJ26", "NGK26")
        ],
        "prepared_corpus_fingerprint": prepared_index["prepared_corpus_fingerprint"],
        "prepared_manifest_fingerprint": _fingerprint(manifest),
        "prepared_source_count": 26,
        "prepared_sources": [],
    }
    return bridge, prepared_index, replay, anchor, prior


def selftest() -> int:
    bridge, prepared, replay, anchor, prior = _fixture()
    completion = build_completion(
        bridge=bridge,
        prepared_index=prepared,
        replay=replay,
        anchor=anchor,
        blind_prior=prior,
        verify_prepared_files=False,
    )
    assert completion["status"] == READY
    assert completion["g15_shadow_refinement_authorized"] is True
    assert completion["g16_authorized"] is False
    validate_completion(
        completion,
        bridge=bridge,
        prepared_index=prepared,
        replay=replay,
        anchor=anchor,
        blind_prior=prior,
    )
    print("[ng_g15_exact_replay_completion] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate exact-basis G15 causal replay completion"
    )
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--skip-prepared-file-verification", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.bridge,
        args.prepared_index,
        args.replay,
        args.anchor,
        args.blind_prior,
        args.out,
    )
    if any(path is None for path in required):
        parser.error(
            "--bridge, --prepared-index, --replay, --anchor, --blind-prior, and --out are required"
        )
    completion = build_completion(
        bridge=json.loads(args.bridge.read_text(encoding="utf-8")),
        prepared_index=json.loads(args.prepared_index.read_text(encoding="utf-8")),
        replay=json.loads(args.replay.read_text(encoding="utf-8")),
        anchor=json.loads(args.anchor.read_text(encoding="utf-8")),
        blind_prior=json.loads(args.blind_prior.read_text(encoding="utf-8")),
        verify_prepared_files=not args.skip_prepared_file_verification,
    )
    validate_completion(completion)
    _atomic_json(args.out, completion)
    print(
        json.dumps(
            {
                "status": completion["status"],
                "days": len(completion["days"]),
                "states": completion["emitted_feature_states"],
                "stand_down_events": completion["stand_down_event_count"],
                "fingerprint": completion["completion_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
