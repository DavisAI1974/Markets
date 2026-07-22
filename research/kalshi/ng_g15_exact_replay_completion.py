#!/usr/bin/env python3
"""Fail-closed completion contract for exact-basis G15 causal replay.

The gate joins the exact-basis source bridge, prepared corpus, prepared-index replay,
Friday anchor, and locked blind prior. It authorizes G15 SHADOW refinement only.
It does not read outcomes, alter the blind forecast/prior, update ng_brain.json, or
grant execution authority.
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
from ng_historical_prepare import validate_prepared_index
from ng_rt_feature_state import validate_chronological, validate_feature_state

SCHEMA = "ng_g15_exact_replay_completion.v1"
REPLAY_SCHEMA = "ng_historical_replay.v1"
PREPARED_REPLAY_SCHEMA = "ng_historical_prepared_replay.v1"
READY = "EXACT_CAUSAL_REPLAY_READY"
READY_WITH_STAND_DOWNS = "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS"
DIRECTIONS = ("up", "flat", "down")


class ExactReplayCompletionError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _replay_prior_fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(result):
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}")
    return result


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactReplayCompletionError(f"invalid {name}: {value!r}") from error
    if result <= 0:
        raise ExactReplayCompletionError(f"{name} must be positive")
    return result


def _normalize_prior(value: Mapping[str, Any]) -> dict[str, float]:
    result = {key: max(0.0, _finite(value.get(key), f"blind_prior.{key}")) for key in DIRECTIONS}
    total = sum(result.values())
    if total <= 0:
        raise ExactReplayCompletionError("blind prior has no positive probability mass")
    return {key: result[key] / total for key in DIRECTIONS}


def _dependency_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        raise ExactReplayCompletionError(str(error)) from error


def _check_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(replay))
    if value.get("schema") != REPLAY_SCHEMA:
        raise ExactReplayCompletionError(f"unexpected replay schema: {value.get('schema')}")
    if value.get("prepared_replay_schema") != PREPARED_REPLAY_SCHEMA:
        raise ExactReplayCompletionError("replay did not use the prepared-index adapter")
    if value.get("authority") != "HISTORICAL_REFINE_REPLAY_ONLY":
        raise ExactReplayCompletionError("replay authority is invalid")
    if value.get("execution_authority") is not False:
        raise ExactReplayCompletionError("replay cannot grant execution authority")
    if value.get("market") != "NG" or int(value.get("group") or 0) != 15:
        raise ExactReplayCompletionError("replay must describe G15 NG")
    for field in ("sequence_gaps", "duplicate_records", "streams"):
        if not isinstance(value.get(field), list):
            raise ExactReplayCompletionError(f"replay {field} must be visible")
    return value


def _state_summary(
    replay: Mapping[str, Any],
    *,
    anchor: dict[str, Any],
    prior: dict[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    states: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stream_ids: set[tuple[int, str, str]] = set()

    for raw_stream in replay.get("streams") or []:
        stream = dict(raw_stream)
        instrument = dict(stream.get("instrument") or {})
        stream_id = (
            int(instrument.get("instrument_id") or 0),
            str(instrument.get("raw_symbol") or ""),
            str(instrument.get("definition_date") or ""),
        )
        if stream_id in stream_ids:
            raise ExactReplayCompletionError(f"duplicate replay instrument stream: {stream_id}")
        stream_ids.add(stream_id)
        stream_states = [copy.deepcopy(dict(row)) for row in stream.get("states") or []]
        if int(stream.get("n_states") or 0) != len(stream_states):
            raise ExactReplayCompletionError(f"replay n_states mismatch for {stream_id}")
        _dependency_call(validate_chronological, stream_states)
        for state in stream_states:
            _dependency_call(validate_feature_state, state)
            if state.get("source_mode") != "historical_replay":
                raise ExactReplayCompletionError("completion accepts historical-replay states only")
            if state.get("completed_mbo_event_boundary") is not True:
                raise ExactReplayCompletionError("state was not emitted on a completed MBO boundary")
            day = str(state.get("session_day") or "")
            expected = G15_CONTRACT_MAP.get(day)
            if expected is None:
                raise ExactReplayCompletionError(f"state is outside canonical G15: {day!r}")
            identity = dict(state.get("instrument") or {})
            observed = (int(identity.get("instrument_id") or 0), str(identity.get("raw_symbol") or ""))
            if observed != (expected["instrument_id"], expected["raw_symbol"]):
                raise ExactReplayCompletionError(f"{day}: feature-state contract identity mismatch")
            if dict(state.get("blind_prior") or {}) != prior:
                raise ExactReplayCompletionError(f"{day}: feature-state blind prior differs from locked prior")
            _dependency_call(assert_anchor_precedes_state, anchor, state)
            by_day[day].append(state)
            states.append(state)

    missing = [day for day in G15_DATES if not by_day.get(day)]
    if missing:
        raise ExactReplayCompletionError("replay emitted no completed state for: " + ", ".join(missing))

    days = []
    for day in G15_DATES:
        ordered = sorted(by_day[day], key=lambda row: (float(row["as_of_event_s"]), int(row["sequence"])))
        reasons = Counter(
            str(reason)
            for state in ordered
            for reason in (state.get("availability") or {}).get("stand_down_reasons") or []
        )
        days.append(
            {
                "date": day,
                "raw_symbol": G15_CONTRACT_MAP[day]["raw_symbol"],
                "instrument_id": G15_CONTRACT_MAP[day]["instrument_id"],
                "completed_states": len(ordered),
                "first_event_s": ordered[0]["as_of_event_s"],
                "last_event_s": ordered[-1]["as_of_event_s"],
                "flow_allowed_states": sum(
                    bool((state.get("availability") or {}).get("flow_update_allowed")) for state in ordered
                ),
                "queue_allowed_states": sum(
                    bool((state.get("availability") or {}).get("queue_update_allowed")) for state in ordered
                ),
                "stand_down_reasons": dict(sorted(reasons.items())),
                "state_fingerprints": [state.get("feature_fingerprint") for state in ordered],
            }
        )
    return states, days


def build_completion(
    *,
    bridge: dict[str, Any],
    prepared_index: dict[str, Any],
    replay: dict[str, Any],
    anchor: dict[str, Any],
    blind_prior: dict[str, Any],
    verify_prepared_files: bool = True,
) -> dict[str, Any]:
    originals = copy.deepcopy((bridge, prepared_index, replay, anchor, blind_prior))
    _dependency_call(validate_bridge_output, bridge)
    _dependency_call(validate_anchor, anchor)
    _dependency_call(validate_prepared_index, prepared_index, verify_files=verify_prepared_files)

    manifest = dict(bridge.get("manifest") or {})
    manifest_report = validate_manifest(manifest)
    if manifest_report.get("status") != "READY" or manifest_report.get("can_replay_all_g15") is not True:
        raise ExactReplayCompletionError("bridge manifest is no longer READY")
    if manifest.get("basis_status") != "MATCHED_L1_MBO_READY":
        raise ExactReplayCompletionError("bridge manifest is not exact matched L1+MBO basis")

    manifest_fp = _fingerprint(manifest)
    if prepared_index.get("manifest_fingerprint") != manifest_fp:
        raise ExactReplayCompletionError("prepared corpus belongs to a different manifest")
    if int(prepared_index.get("source_count") or 0) != 26 or len(prepared_index.get("sources") or []) != 26:
        raise ExactReplayCompletionError("prepared corpus must contain exactly 26 canonical sources")

    replay_value = _check_replay(replay)
    if replay_value.get("prepared_corpus_fingerprint") != prepared_index.get("prepared_corpus_fingerprint"):
        raise ExactReplayCompletionError("replay references a different prepared corpus")
    if replay_value.get("prepared_manifest_fingerprint") != manifest_fp:
        raise ExactReplayCompletionError("replay references a different exact-basis manifest")
    if int(replay_value.get("prepared_source_count") or 0) != 26:
        raise ExactReplayCompletionError("replay did not consume all 26 prepared sources")
    if replay_value.get("manifest_report") != manifest_report:
        raise ExactReplayCompletionError("replay manifest report differs from the bridge")

    prior_fp = _replay_prior_fingerprint(blind_prior)
    if replay_value.get("blind_prior_fingerprint") != prior_fp:
        raise ExactReplayCompletionError("replay blind-prior fingerprint mismatch")
    prior = _normalize_prior(blind_prior)
    processed = dict(replay_value.get("processed_records") or {})
    for name in ("definition", "trade", "mbo"):
        _positive_int(processed.get(name), f"processed_records.{name}")
    boundaries = _positive_int(replay_value.get("completed_mbo_event_boundaries"), "completed boundaries")

    if replay_value.get("duplicate_records"):
        raise ExactReplayCompletionError("duplicate historical records block completion")
    states, days = _state_summary(replay_value, anchor=anchor, prior=prior)
    if boundaries != len(states):
        raise ExactReplayCompletionError("completed MBO boundary count differs from emitted states")

    gaps = list(replay_value.get("sequence_gaps") or [])
    visible_gap_stop = any("collector_skipped_records" in row["stand_down_reasons"] for row in days)
    if gaps and not visible_gap_stop:
        raise ExactReplayCompletionError("sequence gaps exist without a visible collector stand-down")
    stand_down_count = sum(sum(int(value) for value in row["stand_down_reasons"].values()) for row in days)

    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_WITH_STAND_DOWNS if gaps or stand_down_count else READY,
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
        "manifest_fingerprint": manifest_fp,
        "prepared_corpus_fingerprint": prepared_index.get("prepared_corpus_fingerprint"),
        "replay_fingerprint": _fingerprint(replay_value),
        "anchor_fingerprint": anchor.get("anchor_fingerprint"),
        "blind_prior_fingerprint": prior_fp,
        "prepared_source_count": 26,
        "processed_records": processed,
        "completed_mbo_event_boundaries": boundaries,
        "emitted_feature_states": len(states),
        "sequence_gaps": gaps,
        "duplicate_records": [],
        "stand_down_event_count": stand_down_count,
        "days": days,
        "next_required_stage": "ng_g15_pipeline.run_pipeline",
        "note": "Exact matched L1+MBO replay is complete; only G15 SHADOW refinement is authorized.",
    }
    result["completion_fingerprint"] = _fingerprint(result)
    if (bridge, prepared_index, replay, anchor, blind_prior) != originals:
        raise ExactReplayCompletionError("completion validation mutated source artifacts")
    return result


def validate_completion(
    completion: dict[str, Any],
    *,
    bridge: dict[str, Any] | None = None,
    prepared_index: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
    blind_prior: dict[str, Any] | None = None,
) -> None:
    value = copy.deepcopy(completion)
    observed = value.pop("completion_fingerprint", None)
    if value.get("schema") != SCHEMA or value.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise ExactReplayCompletionError("unexpected or non-ready completion artifact")
    if observed != _fingerprint(value):
        raise ExactReplayCompletionError("completion fingerprint mismatch")
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
            raise ExactReplayCompletionError(f"completion must keep {field}=false")
    if value.get("g15_shadow_refinement_authorized") is not True:
        raise ExactReplayCompletionError("completion must authorize G15 SHADOW refinement")
    if [row.get("date") for row in value.get("days") or []] != list(G15_DATES):
        raise ExactReplayCompletionError("completion lost canonical G15 order")
    checks = (
        (bridge, "bridge_fingerprint", lambda x: x.get("fingerprint")),
        (prepared_index, "prepared_corpus_fingerprint", lambda x: x.get("prepared_corpus_fingerprint")),
        (replay, "replay_fingerprint", _fingerprint),
        (anchor, "anchor_fingerprint", lambda x: x.get("anchor_fingerprint")),
        (blind_prior, "blind_prior_fingerprint", _replay_prior_fingerprint),
    )
    for source, field, expected in checks:
        if source is not None and value.get(field) != expected(source):
            raise ExactReplayCompletionError(f"completion references a different {field}")


def _fixture():
    from ng_g15_anchor import anchor_fingerprint
    from ng_g15_replay_manifest_bridge import _fixture_catalog, _fixture_inventory, build_replay_manifest
    from ng_rt_feature_state import build_feature_state

    inventory = _fixture_inventory()
    bridge = build_replay_manifest(inventory, _fixture_catalog(inventory))
    manifest = bridge["manifest"]
    sources = [
        {"day": "20260315", "source_kind": "definition", "path": "/fixture/definition_NGJ26.jsonl"},
        {"day": "20260320", "source_kind": "definition", "path": "/fixture/definition_NGK26.jsonl"},
        *[
            {"day": day, "source_kind": kind, "path": f"/fixture/{day}_{kind}.jsonl"}
            for day in G15_DATES
            for kind in ("l1_trades", "mbo")
        ],
    ]
    prepared = {
        "schema": "ng_historical_prepared_corpus.v1",
        "market": "NG",
        "group": 15,
        "status": "READY",
        "authority": "HISTORICAL_REPLAY_INPUT_ONLY",
        "execution_authority": False,
        "manifest_fingerprint": _fingerprint(manifest),
        "manifest_report": bridge["manifest_report"],
        "output_dir": "/fixture",
        "source_count": 26,
        "sources": sources,
    }
    prepared["prepared_corpus_fingerprint"] = _fingerprint(prepared)
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
        "prices": {"first": 3.1, "last": 3.132, "high": 3.14, "low": 3.09},
        "direction": "up",
        "trade_count": 10,
    }
    anchor["anchor_fingerprint"] = anchor_fingerprint(anchor)
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    by_symbol = {"NGJ26": [], "NGK26": []}
    seq = {"NGJ26": 0, "NGK26": 0}
    for offset, day in enumerate(G15_DATES, 1):
        expected = G15_CONTRACT_MAP[day]
        symbol = expected["raw_symbol"]
        seq[symbol] += 1
        ts = 1000.0 + offset * 100.0
        state = build_feature_state(
            blind_prior=prior,
            operator_snapshot={
                "schema": "ng_live_operator.v1",
                "authority": "MARKET_DATA_ONLY",
                "as_of_event_s": ts,
                "move_onset_pressure": {"value": 0.1, "activity_ratio": 1.0, "price_efficiency": 0.5},
                "signed_flow": {"imbalance": 0.2},
                "divergence_exhaustion": {"state": "none"},
                "mbo_queue": {"book_complete": True, "snapshot_complete": True, "maybe_bad_book": False},
                "data_quality": {
                    "book_complete": True,
                    "trade_events_60s": 6,
                    "trade_events_15m": 20,
                    "complete_mbo_events": 1,
                    "missing_order_events": 0,
                },
            },
            instrument_identity={
                "dataset": "GLBX.MDP3",
                "publisher_id": 1,
                "instrument_id": expected["instrument_id"],
                "raw_symbol": symbol,
                "definition_date": "2026-03-01" if symbol == "NGJ26" else "2026-03-20",
            },
            decision_cutoff_s=ts,
            horizon="close",
            source_mode="historical_replay",
            sequence=seq[symbol],
        )
        state.update(session_day=day, completed_mbo_event_boundary=True)
        by_symbol[symbol].append(state)
    replay = {
        "schema": REPLAY_SCHEMA,
        "prepared_replay_schema": PREPARED_REPLAY_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_REPLAY_ONLY",
        "execution_authority": False,
        "blind_prior_fingerprint": _replay_prior_fingerprint(prior),
        "manifest_report": bridge["manifest_report"],
        "processed_records": {"definition": 2, "trade": 72, "mbo": 12},
        "completed_mbo_event_boundaries": 12,
        "sequence_gaps": [],
        "duplicate_records": [],
        "streams": [
            {
                "instrument": {"instrument_id": 1008 if symbol == "NGJ26" else 996, "raw_symbol": symbol},
                "n_states": len(by_symbol[symbol]),
                "states": by_symbol[symbol],
            }
            for symbol in ("NGJ26", "NGK26")
        ],
        "prepared_corpus_fingerprint": prepared["prepared_corpus_fingerprint"],
        "prepared_manifest_fingerprint": _fingerprint(manifest),
        "prepared_source_count": 26,
        "prepared_sources": [],
    }
    return bridge, prepared, replay, anchor, prior


def selftest() -> int:
    bridge, prepared, replay, anchor, prior = _fixture()
    result = build_completion(
        bridge=bridge,
        prepared_index=prepared,
        replay=replay,
        anchor=anchor,
        blind_prior=prior,
        verify_prepared_files=False,
    )
    assert result["status"] == READY
    validate_completion(
        result,
        bridge=bridge,
        prepared_index=prepared,
        replay=replay,
        anchor=anchor,
        blind_prior=prior,
    )
    print("[ng_g15_exact_replay_completion] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exact-basis G15 causal replay completion")
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
    required = (args.bridge, args.prepared_index, args.replay, args.anchor, args.blind_prior, args.out)
    if any(value is None for value in required):
        parser.error("--bridge, --prepared-index, --replay, --anchor, --blind-prior, and --out are required")
    result = build_completion(
        bridge=json.loads(args.bridge.read_text()),
        prepared_index=json.loads(args.prepared_index.read_text()),
        replay=json.loads(args.replay.read_text()),
        anchor=json.loads(args.anchor.read_text()),
        blind_prior=json.loads(args.blind_prior.read_text()),
        verify_prepared_files=not args.skip_prepared_file_verification,
    )
    validate_completion(result)
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "days": len(result["days"]),
                "states": result["emitted_feature_states"],
                "stand_down_events": result["stand_down_event_count"],
                "fingerprint": result["completion_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
