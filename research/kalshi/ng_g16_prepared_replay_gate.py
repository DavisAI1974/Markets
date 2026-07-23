#!/usr/bin/env python3
"""Harden the exact G16 prepared-corpus to causal-replay provenance seam.

The base G16 historical replay module prepares and replays exact NGK26 data. This
wrapper adds an independent fail-closed check that every normalized file remains
inside the prepared output directory and is fingerprint-linked to the exact raw
manifest entry that produced it. It then verifies replay counts, completed MBO
boundaries, visible sequence-gap stand-downs, and immutable authority controls.

No outcomes are read. Random shuffling is forbidden. The blind prior remains
immutable, CME event contracts remain SHADOW, tastytrade remains the brokerage
contract, and options work remains unstarted.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_g16_historical_replay import (
    CANONICAL_DATES,
    DATASET,
    INSTRUMENT_ID,
    RAW_SYMBOL,
    SOURCE_KINDS,
    G16HistoricalReplayError,
    _event_key,
    _identity,
    _sha,
    _sha256,
    _fixture_catalog,
    _fixture_inventory,
    build_manifest,
    prepare_corpus,
    read_jsonl,
    replay_prepared,
    validate_manifest,
    validate_normalized_event,
    validate_prepared_index,
    validate_replay_output,
)

SCHEMA = "ng_g16_prepared_replay_gate.v1"
STATUS_READY = "EXACT_G16_PREPARED_REPLAY_READY"
STATUS_STAND_DOWNS = "EXACT_G16_PREPARED_REPLAY_READY_WITH_STAND_DOWNS"
EXPECTED_SOURCE_COUNT = 23
SOURCE_EVENT = {"definition": "definition", "l1_trades": "trade", "mbo": "mbo"}


class G16PreparedReplayGateError(ValueError):
    """Raised when prepared G16 replay provenance is incomplete or inconsistent."""


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _manifest_entries(manifest: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest.get("entries") or []:
        entry = copy.deepcopy(dict(raw))
        key = (str(entry.get("day") or ""), str(entry.get("source_kind") or ""))
        if key in entries:
            raise G16PreparedReplayGateError(f"duplicate manifest lane: {key[0]}:{key[1]}")
        entries[key] = entry
    expected = {(day, kind) for day in CANONICAL_DATES for kind in SOURCE_KINDS}
    if set(entries) != expected:
        raise G16PreparedReplayGateError(
            f"manifest lane mismatch; missing={sorted(expected-set(entries))}, extra={sorted(set(entries)-expected)}"
        )
    return entries


def _expected_identity(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(entry.get("dataset") or ""),
        int(entry.get("publisher_id") or 0),
        int(entry.get("instrument_id") or 0),
        str(entry.get("raw_symbol") or ""),
        str(entry.get("definition_date") or ""),
    )


def _scan_prepared_source(
    source: Mapping[str, Any],
    *,
    entry: Mapping[str, Any] | None,
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    day = str(source.get("day") or "")
    source_kind = str(source.get("source_kind") or "")
    expected_event = SOURCE_EVENT.get(source_kind)
    if expected_event is None:
        raise G16PreparedReplayGateError(f"{day}: unexpected source kind {source_kind!r}")
    path = Path(str(source.get("path") or "")).resolve()
    count = 0
    event_start = None
    event_end = None
    last_key = None
    for raw in read_jsonl(path):
        event = validate_normalized_event(copy.deepcopy(raw))
        key = _event_key(event)
        if last_key is not None and key < last_key:
            raise G16PreparedReplayGateError(f"{day}:{source_kind}: normalized source moved backward")
        last_key = key
        if str(event.get("event_type") or "") != expected_event:
            raise G16PreparedReplayGateError(f"{day}:{source_kind}: normalized event type mismatch")
        if str(event.get("session_day") or "") != day:
            raise G16PreparedReplayGateError(f"{day}:{source_kind}: normalized session day mismatch")
        identity = _identity(event)
        if source_kind == "definition":
            expected_identity = (
                DATASET,
                int(definition.get("publisher_id") or 0),
                INSTRUMENT_ID,
                RAW_SYMBOL,
                str(definition.get("definition_date") or ""),
            )
        else:
            if entry is None:
                raise G16PreparedReplayGateError(f"{day}:{source_kind}: missing manifest entry")
            expected_identity = _expected_identity(entry)
        if identity != expected_identity:
            raise G16PreparedReplayGateError(f"{day}:{source_kind}: normalized identity differs from manifest")
        timestamp = float(event["ts_event_s"])
        event_start = timestamp if event_start is None else min(event_start, timestamp)
        event_end = timestamp if event_end is None else max(event_end, timestamp)
        count += 1
    if count <= 0 or event_start is None or event_end is None:
        raise G16PreparedReplayGateError(f"{day}:{source_kind}: normalized source is empty")
    if count != int(source.get("record_count") or 0):
        raise G16PreparedReplayGateError(f"{day}:{source_kind}: prepared record_count differs from file")
    if abs(event_start - float(source.get("event_start_s"))) > 1e-9:
        raise G16PreparedReplayGateError(f"{day}:{source_kind}: prepared event_start differs from file")
    if abs(event_end - float(source.get("event_end_s"))) > 1e-9:
        raise G16PreparedReplayGateError(f"{day}:{source_kind}: prepared event_end differs from file")
    return {
        "day": day,
        "source_kind": source_kind,
        "path": str(path),
        "record_count": count,
        "event_start_s": event_start,
        "event_end_s": event_end,
        "size_bytes": int(source.get("size_bytes") or 0),
        "sha256": str(source.get("sha256") or ""),
    }


def validate_prepared_lineage(
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate all 23 prepared sources against their exact raw manifest lineage."""
    try:
        validate_manifest(manifest)
        validate_prepared_index(prepared_index, verify_files=True)
    except G16HistoricalReplayError as error:
        raise G16PreparedReplayGateError(str(error)) from error
    if prepared_index.get("manifest_fingerprint") != manifest.get("fingerprint"):
        raise G16PreparedReplayGateError("prepared index references a different G16 manifest")
    if int(prepared_index.get("source_count") or 0) != EXPECTED_SOURCE_COUNT:
        raise G16PreparedReplayGateError("prepared G16 corpus must contain exactly 23 sources")
    root_text = str(prepared_index.get("output_dir") or "")
    if not root_text:
        raise G16PreparedReplayGateError("prepared index lacks output_dir")
    root = Path(root_text).resolve()
    if not root.is_dir():
        raise G16PreparedReplayGateError(f"prepared output_dir is unavailable: {root}")

    entries = _manifest_entries(manifest)
    definition = dict(manifest.get("definition") or {})
    expected_keys = {(CANONICAL_DATES[0], "definition")} | {
        (day, kind) for day in CANONICAL_DATES for kind in SOURCE_KINDS
    }
    seen_keys: set[tuple[str, str]] = set()
    seen_paths: set[Path] = set()
    summaries: list[dict[str, Any]] = []
    processed_expected = {"definition": 0, "trade": 0, "mbo": 0}

    for raw in prepared_index.get("sources") or []:
        source = copy.deepcopy(dict(raw))
        day = str(source.get("day") or "")
        source_kind = str(source.get("source_kind") or "")
        key = (day, source_kind)
        if key in seen_keys:
            raise G16PreparedReplayGateError(f"duplicate prepared lane: {day}:{source_kind}")
        seen_keys.add(key)
        path = Path(str(source.get("path") or "")).resolve()
        if not _inside(path, root):
            raise G16PreparedReplayGateError(f"prepared source escapes output_dir: {path}")
        if path in seen_paths:
            raise G16PreparedReplayGateError(f"duplicate prepared path: {path}")
        seen_paths.add(path)

        entry = None if source_kind == "definition" else entries.get((day, source_kind))
        if source_kind == "definition":
            if day != CANONICAL_DATES[0] or int(source.get("record_count") or 0) != 1:
                raise G16PreparedReplayGateError("prepared definition source is not canonical")
        else:
            if entry is None:
                raise G16PreparedReplayGateError(f"{day}:{source_kind}: no matching manifest entry")
            prefix = f"{day}:{source_kind}"
            if source.get("manifest_entry_fingerprint") != _sha(entry):
                raise G16PreparedReplayGateError(f"{prefix}: manifest-entry fingerprint mismatch")
            if source.get("raw_location") != entry.get("location"):
                raise G16PreparedReplayGateError(f"{prefix}: raw location lineage mismatch")
            if int(source.get("raw_size_bytes") or 0) != int(entry.get("size_bytes") or 0):
                raise G16PreparedReplayGateError(f"{prefix}: raw size lineage mismatch")
            if source.get("raw_sha256") != entry.get("sha256"):
                raise G16PreparedReplayGateError(f"{prefix}: raw hash lineage mismatch")
            if int(source.get("record_count") or 0) != int(entry.get("record_count") or 0):
                raise G16PreparedReplayGateError(f"{prefix}: prepared count differs from manifest")
            for field in ("event_start_s", "event_end_s"):
                if abs(float(source.get(field)) - float(entry.get(field))) > 1e-9:
                    raise G16PreparedReplayGateError(f"{prefix}: prepared {field} differs from manifest")
        summary = _scan_prepared_source(source, entry=entry, definition=definition)
        summary["manifest_entry_fingerprint"] = None if entry is None else _sha(entry)
        summary["raw_location"] = None if entry is None else entry.get("location")
        summary["raw_size_bytes"] = None if entry is None else entry.get("size_bytes")
        summary["raw_sha256"] = None if entry is None else entry.get("sha256")
        summary["source_fingerprint"] = _sha(summary)
        summaries.append(summary)
        processed_expected[SOURCE_EVENT[source_kind]] += summary["record_count"]

    if seen_keys != expected_keys:
        raise G16PreparedReplayGateError(
            f"prepared source coverage mismatch; missing={sorted(expected_keys-seen_keys)}, extra={sorted(seen_keys-expected_keys)}"
        )
    summaries.sort(key=lambda row: (row["day"], SOURCE_EVENT[row["source_kind"]], row["path"]))
    return {
        "prepared_manifest_fingerprint": manifest["fingerprint"],
        "prepared_corpus_fingerprint": prepared_index["prepared_corpus_fingerprint"],
        "prepared_source_count": len(summaries),
        "prepared_sources": summaries,
        "prepared_source_fingerprints": [row["source_fingerprint"] for row in summaries],
        "processed_expected": processed_expected,
    }


def _replay_checks(
    replay: Mapping[str, Any],
    lineage: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validate_replay_output(replay)
    except G16HistoricalReplayError as error:
        raise G16PreparedReplayGateError(str(error)) from error
    if replay.get("manifest_fingerprint") != lineage.get("prepared_manifest_fingerprint"):
        raise G16PreparedReplayGateError("replay references a different manifest")
    if replay.get("prepared_corpus_fingerprint") != lineage.get("prepared_corpus_fingerprint"):
        raise G16PreparedReplayGateError("replay references a different prepared corpus")
    if int(replay.get("source_count") or 0) != EXPECTED_SOURCE_COUNT:
        raise G16PreparedReplayGateError("replay source_count is not 23")
    if replay.get("blind_prior_fingerprint") != _sha(dict(blind_prior)):
        raise G16PreparedReplayGateError("replay references a different blind prior")
    expected = dict(lineage.get("processed_expected") or {})
    observed = dict(replay.get("processed_records") or {})
    if observed != expected:
        raise G16PreparedReplayGateError(
            f"replay processed-record counts differ from prepared sources: expected={expected}, observed={observed}"
        )
    states = [
        state
        for stream in replay.get("streams") or []
        for state in stream.get("states") or []
    ]
    if int(replay.get("completed_mbo_event_boundaries") or 0) != len(states):
        raise G16PreparedReplayGateError("completed MBO boundary count differs from emitted states")
    if sorted({str(state.get("session_day") or "") for state in states}) != sorted(CANONICAL_DATES):
        raise G16PreparedReplayGateError("replay lacks canonical G16 session coverage")
    if replay.get("sequence_gaps"):
        reasons = {
            str(reason)
            for state in states
            for reason in ((state.get("availability") or {}).get("stand_down_reasons") or [])
        }
        if "collector_skipped_records" not in reasons:
            raise G16PreparedReplayGateError("sequence gaps are not exposed as collector_skipped_records")
        if replay.get("status") != "READY_WITH_STAND_DOWNS":
            raise G16PreparedReplayGateError("sequence gaps require READY_WITH_STAND_DOWNS")
    return {
        "replay_fingerprint": replay.get("fingerprint"),
        "replay_status": replay.get("status"),
        "n_states": len(states),
        "stand_down_days": sorted(str(day) for day in replay.get("stand_down_days") or []),
        "queue_stand_down_days": sorted(str(day) for day in replay.get("queue_stand_down_days") or []),
        "sequence_gap_count": len(replay.get("sequence_gaps") or []),
    }


def run_gate(
    prepared_index: dict[str, Any],
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replay the verified corpus and emit a fingerprinted exact-provenance gate."""
    originals = copy.deepcopy((prepared_index, manifest, blind_prior))
    lineage = validate_prepared_lineage(prepared_index, manifest)
    replay = replay_prepared(
        copy.deepcopy(prepared_index),
        copy.deepcopy(manifest),
        blind_prior,
    )
    replay_summary = _replay_checks(replay, lineage, blind_prior)
    if (prepared_index, manifest, blind_prior) != originals:
        raise G16PreparedReplayGateError("G16 prepared replay mutated an input artifact")
    status = STATUS_STAND_DOWNS if replay_summary["stand_down_days"] else STATUS_READY
    completion = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 16,
        "status": status,
        "authority": "EXACT_G16_HISTORICAL_REPLAY_PROVENANCE_ONLY",
        "manifest_fingerprint": lineage["prepared_manifest_fingerprint"],
        "prepared_corpus_fingerprint": lineage["prepared_corpus_fingerprint"],
        "prepared_source_count": lineage["prepared_source_count"],
        "prepared_source_fingerprints": lineage["prepared_source_fingerprints"],
        "replay_fingerprint": replay_summary["replay_fingerprint"],
        "blind_prior_fingerprint": _sha(dict(blind_prior)),
        "processed_records": copy.deepcopy(replay.get("processed_records") or {}),
        "completed_mbo_event_boundaries": int(replay.get("completed_mbo_event_boundaries") or 0),
        "n_feature_states": replay_summary["n_states"],
        "stand_down_days": replay_summary["stand_down_days"],
        "queue_stand_down_days": replay_summary["queue_stand_down_days"],
        "sequence_gap_count": replay_summary["sequence_gap_count"],
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "G16_PRE_CUTOFF_EXACT_CAUSAL_PIPELINE",
    }
    completion["fingerprint"] = _sha(completion)
    validate_gate_artifact(
        completion,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=replay,
        blind_prior=blind_prior,
    )
    return replay, completion


def validate_gate_artifact(
    completion: Mapping[str, Any],
    *,
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
) -> None:
    candidate = copy.deepcopy(dict(completion))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or candidate.get("status") not in {STATUS_READY, STATUS_STAND_DOWNS}:
        raise G16PreparedReplayGateError("unexpected G16 prepared replay gate artifact")
    if observed != _sha(candidate):
        raise G16PreparedReplayGateError("G16 prepared replay gate fingerprint mismatch")
    lineage = validate_prepared_lineage(prepared_index, manifest)
    replay_summary = _replay_checks(replay, lineage, blind_prior)
    expected_status = STATUS_STAND_DOWNS if replay_summary["stand_down_days"] else STATUS_READY
    expected_links = {
        "status": expected_status,
        "manifest_fingerprint": lineage["prepared_manifest_fingerprint"],
        "prepared_corpus_fingerprint": lineage["prepared_corpus_fingerprint"],
        "prepared_source_count": lineage["prepared_source_count"],
        "prepared_source_fingerprints": lineage["prepared_source_fingerprints"],
        "replay_fingerprint": replay_summary["replay_fingerprint"],
        "blind_prior_fingerprint": _sha(dict(blind_prior)),
        "processed_records": dict(replay.get("processed_records") or {}),
        "completed_mbo_event_boundaries": int(replay.get("completed_mbo_event_boundaries") or 0),
        "n_feature_states": replay_summary["n_states"],
        "stand_down_days": replay_summary["stand_down_days"],
        "queue_stand_down_days": replay_summary["queue_stand_down_days"],
        "sequence_gap_count": replay_summary["sequence_gap_count"],
    }
    for field, value in expected_links.items():
        if candidate.get(field) != value:
            raise G16PreparedReplayGateError(f"completion {field} does not match exact replay provenance")
    false_fields = (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in false_fields:
        if candidate.get(field) is not False:
            raise G16PreparedReplayGateError(f"completion must keep {field}=false")
    if candidate.get("one_signal_authority_preserved") is not True:
        raise G16PreparedReplayGateError("completion must preserve one signal authority")
    if candidate.get("blind_forecast_immutable") is not True:
        raise G16PreparedReplayGateError("completion must keep blind forecast immutable")
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16PreparedReplayGateError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16PreparedReplayGateError("brokerage contract must remain tastytrade_not_ibkr")
    if candidate.get("next_permitted_stage") != "G16_PRE_CUTOFF_EXACT_CAUSAL_PIPELINE":
        raise G16PreparedReplayGateError("unexpected next permitted stage")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G16PreparedReplayGateError(f"expected JSON object: {path}")
    return value


def _selftest() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        inventory, definition = _fixture_inventory(root)
        catalog = _fixture_catalog(inventory, definition)
        manifest = build_manifest(inventory, catalog)
        prepared = prepare_corpus(manifest, root / "prepared")
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        replay, completion = run_gate(prepared, manifest, prior)
        assert completion["status"] == STATUS_READY
        assert completion["prepared_source_count"] == EXPECTED_SOURCE_COUNT
        assert completion["replay_fingerprint"] == replay["fingerprint"]
        assert completion["actual_outcomes_used"] is False
        assert completion["random_shuffle_used"] is False
        assert completion["execution_authority"] is False
        assert completion["options_lane_started"] is False
    print("ng_g16_prepared_replay_gate selftest passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--replay-out", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return
    required = (args.prepared, args.manifest, args.blind_prior, args.replay_out, args.out)
    if any(path is None for path in required):
        parser.error("--prepared --manifest --blind-prior --replay-out and --out are required")
    replay, completion = run_gate(
        _load(args.prepared),
        _load(args.manifest),
        _load(args.blind_prior),
    )
    _atomic(args.replay_out, replay)
    _atomic(args.out, completion)
    print(json.dumps({"status": completion["status"], "fingerprint": completion["fingerprint"]}, sort_keys=True))


if __name__ == "__main__":
    main()
