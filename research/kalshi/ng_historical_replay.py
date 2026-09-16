#!/usr/bin/env python3
"""Deterministic G15 L1/trades + MBO replay through the live operator.

Inputs are normalized Databento records. The adapter preserves event order, applies
trades and MBO to ``NGLiveOperator``, and emits ``ng_rt_feature_state`` only when an
MBO event carries F_LAST. The blind prior is immutable and event contracts stay SHADOW.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from ng_historical_manifest import G15_CONTRACT_MAP, validate_manifest
from ng_live_operator import F_LAST, NGLiveOperator
from ng_rt_feature_state import build_feature_state, validate_chronological

SCHEMA = "ng_historical_replay.v1"
NORMALIZED_SCHEMA = "ng_normalized_event.v1"
EVENT_TYPES = {"trade", "mbo", "definition"}
SOURCE_ORDER = {"definition": 0, "trade": 1, "mbo": 2}


class ReplayError(ValueError):
    pass


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _identity(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(event.get("dataset") or ""),
        event.get("publisher_id"),
        int(event.get("instrument_id") or 0),
        str(event.get("raw_symbol") or ""),
        str(event.get("definition_date") or ""),
    )


def _event_key(event: dict[str, Any]) -> tuple[float, int, int, int]:
    ts = _finite(event.get("ts_event_s"))
    if ts is None:
        raise ReplayError("event missing finite ts_event_s")
    return (
        ts,
        SOURCE_ORDER.get(str(event.get("event_type")), 99),
        int(event.get("source_sequence") or 0),
        int(event.get("ingest_sequence") or 0),
    )


def validate_normalized_event(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("schema") != NORMALIZED_SCHEMA:
        raise ReplayError(f"unexpected event schema: {event.get('schema')}")
    event_type = str(event.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        raise ReplayError(f"unsupported event_type: {event_type}")
    dataset, _publisher, instrument_id, raw_symbol, definition_date = _identity(event)
    missing = []
    if _finite(event.get("ts_event_s")) is None:
        missing.append("ts_event_s")
    if not dataset:
        missing.append("dataset")
    if instrument_id <= 0:
        missing.append("instrument_id")
    if not raw_symbol:
        missing.append("raw_symbol")
    if not definition_date:
        missing.append("definition_date")
    if missing:
        raise ReplayError("event missing: " + ", ".join(missing))
    required = {
        "trade": ("price", "size", "side"),
        "mbo": ("action", "side", "size", "order_id", "flags"),
        "definition": (),
    }[event_type]
    absent = [name for name in required if event.get(name) in (None, "")]
    if absent:
        raise ReplayError(f"{event_type} missing: {', '.join(absent)}")
    return event


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise ReplayError(f"{path}:{line_number}: {error}") from error
            event.setdefault("ingest_sequence", line_number)
            event.setdefault("source_id", str(path))
            yield validate_normalized_event(event)


def merge_sorted_sources(sources: Sequence[Iterable[dict[str, Any]]]) -> Iterator[dict[str, Any]]:
    """Stable k-way merge. Each input source must already be chronological."""
    iterators = [iter(source) for source in sources]
    heap: list[tuple[tuple[float, int, int, int], int, dict[str, Any]]] = []
    prior: dict[int, tuple[float, int, int, int]] = {}
    for index, iterator in enumerate(iterators):
        try:
            event = validate_normalized_event(next(iterator))
        except StopIteration:
            continue
        key = _event_key(event)
        prior[index] = key
        heapq.heappush(heap, (key, index, event))
    while heap:
        _, index, event = heapq.heappop(heap)
        yield event
        try:
            next_event = validate_normalized_event(next(iterators[index]))
        except StopIteration:
            continue
        key = _event_key(next_event)
        if key < prior[index]:
            raise ReplayError(f"source {index} moved backwards")
        prior[index] = key
        heapq.heappush(heap, (key, index, next_event))


@dataclass
class SourceContinuity:
    last_sequence: dict[tuple[Any, ...], int] = field(default_factory=dict)
    sequence_gaps: list[dict[str, Any]] = field(default_factory=list)
    seen: set[tuple[Any, ...]] = field(default_factory=set)
    duplicates: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, event: dict[str, Any]) -> None:
        identity = _identity(event)
        event_type = str(event["event_type"])
        source_id = str(event.get("source_id") or event.get("session_day") or "default")
        source = (event_type, identity, source_id)
        sequence = int(event.get("source_sequence") or 0)
        previous = self.last_sequence.get(source)
        if sequence > 0 and previous is not None:
            if sequence <= previous:
                raise ReplayError(f"non-increasing sequence for {event_type}:{identity[3]}")
            if sequence > previous + 1:
                self.sequence_gaps.append(
                    {
                        "event_type": event_type,
                        "instrument_id": identity[2],
                        "raw_symbol": identity[3],
                        "expected": previous + 1,
                        "observed": sequence,
                        "missing_count": sequence - previous - 1,
                        "as_of_event_s": float(event["ts_event_s"]),
                    }
                )
        if sequence > 0:
            self.last_sequence[source] = sequence
        unique = (event_type, identity, event["ts_event_s"], sequence, event.get("order_id"), event.get("action"))
        if unique in self.seen:
            self.duplicates.append(
                {"event_type": event_type, "raw_symbol": identity[3], "ts_event_s": event["ts_event_s"]}
            )
        self.seen.add(unique)

    def quality(self, identity: tuple[Any, ...]) -> dict[str, Any]:
        gaps = [row for row in self.sequence_gaps if row["instrument_id"] == identity[2]]
        return {
            "skipped_records": sum(int(row["missing_count"]) for row in gaps),
            "sequence_gaps": gaps,
            "duplicates": [row for row in self.duplicates if row["raw_symbol"] == identity[3]],
            "callback_backlog": False,
            "definition_mismatch": False,
        }


def _manifest_identity_by_day(manifest: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    result = {}
    for entry in manifest.get("entries") or []:
        if entry.get("source_kind") != "l1_trades" or str(entry.get("status")).upper() != "PRESENT":
            continue
        result[str(entry["day"])] = (
            str(entry.get("dataset") or ""),
            entry.get("publisher_id"),
            int(entry.get("instrument_id") or 0),
            str(entry.get("raw_symbol") or ""),
            str(entry.get("definition_date") or ""),
        )
    return result


def replay_events(
    events: Iterable[dict[str, Any]],
    *,
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
    horizon: str = "close",
    require_ready_manifest: bool = True,
) -> dict[str, Any]:
    """Replay records and emit one feature state per completed MBO event."""
    manifest_report = validate_manifest(manifest)
    if require_ready_manifest and manifest_report["status"] != "READY":
        raise ReplayError(f"G15 manifest is {manifest_report['status']}; observed paired sources are required")
    manifest_identities = _manifest_identity_by_day(manifest)
    prior_before = copy.deepcopy(blind_prior)
    prior_hash = hashlib.sha256(json.dumps(prior_before, sort_keys=True).encode()).hexdigest()

    operators: dict[tuple[Any, ...], NGLiveOperator] = {}
    stream_states: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    stream_sequences: dict[tuple[Any, ...], int] = {}
    continuity = SourceContinuity()
    definition_seen: set[tuple[Any, ...]] = set()
    processed = {"trade": 0, "mbo": 0, "definition": 0}
    complete_boundaries = 0
    last_key = None

    for raw_event in events:
        event = validate_normalized_event(copy.deepcopy(raw_event))
        key = _event_key(event)
        if last_key is not None and key < last_key:
            raise ReplayError("merged replay moved backwards")
        last_key = key
        continuity.observe(event)
        identity = _identity(event)
        day = str(event.get("session_day") or "")
        expected = G15_CONTRACT_MAP.get(day)
        if expected and (identity[2], identity[3]) != (expected["instrument_id"], expected["raw_symbol"]):
            raise ReplayError(f"{day}: wrong G15 contract identity")
        manifest_identity = manifest_identities.get(day)
        if manifest_identity and identity != manifest_identity:
            raise ReplayError(f"{day}: event identity differs from manifest")

        event_type = str(event["event_type"])
        processed[event_type] += 1
        if event_type == "definition":
            definition_seen.add(identity)
            continue
        operator = operators.setdefault(identity, NGLiveOperator())
        stream_states.setdefault(identity, [])
        if event_type == "trade":
            operator.on_trade(float(event["ts_event_s"]), float(event["price"]), float(event["size"]), event["side"])
            continue

        operator.on_mbo(
            float(event["ts_event_s"]), event["action"], event["side"], float(event["size"]),
            int(event["order_id"]), None if event.get("price") is None else float(event["price"]), int(event["flags"]),
        )
        if not (int(event["flags"]) & int(F_LAST)):
            continue
        complete_boundaries += 1
        stream_sequences[identity] = stream_sequences.get(identity, 0) + 1
        quality = continuity.quality(identity)
        quality["definition_verified_by_stream"] = identity in definition_seen
        quality["definition_verified_by_manifest"] = bool(manifest_identity)
        state = build_feature_state(
            blind_prior=prior_before,
            operator_snapshot=operator.snapshot(float(event["ts_event_s"])),
            instrument_identity={
                "dataset": identity[0], "publisher_id": identity[1], "instrument_id": identity[2],
                "raw_symbol": identity[3], "definition_date": identity[4], "continuous_symbol": "NG.v.0",
                "roll_rule": "kalshi_settlement_proximity",
            },
            decision_cutoff_s=float(event["ts_event_s"]),
            horizon=horizon,
            source_mode="historical_replay",
            sequence=stream_sequences[identity],
            collector_quality=quality,
        )
        state["session_day"] = day or None
        state["completed_mbo_event_boundary"] = True
        stream_states[identity].append(state)

    for states in stream_states.values():
        validate_chronological(states)
    if blind_prior != prior_before:
        raise ReplayError("blind prior was mutated")
    if hashlib.sha256(json.dumps(blind_prior, sort_keys=True).encode()).hexdigest() != prior_hash:
        raise ReplayError("blind prior fingerprint changed")

    streams = [
        {
            "instrument": {
                "dataset": identity[0], "publisher_id": identity[1], "instrument_id": identity[2],
                "raw_symbol": identity[3], "definition_date": identity[4],
            },
            "n_states": len(stream_states[identity]),
            "states": stream_states[identity],
        }
        for identity in sorted(stream_states, key=lambda row: (row[2], row[3], row[4]))
    ]
    return {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_REPLAY_ONLY",
        "execution_authority": False,
        "blind_prior_fingerprint": prior_hash,
        "manifest_report": manifest_report,
        "processed_records": processed,
        "completed_mbo_event_boundaries": complete_boundaries,
        "sequence_gaps": continuity.sequence_gaps,
        "duplicate_records": continuity.duplicates,
        "streams": streams,
        "note": "States emit only on F_LAST; CME event contracts remain SHADOW.",
    }


def selftest() -> int:
    from ng_historical_manifest import expected_g15_manifest

    manifest = expected_g15_manifest(publisher_id=1)
    for entry in manifest["entries"]:
        entry.update(
            status="PRESENT", location=f"file:///{entry['source_kind']}/{entry['day']}", publisher_id=1,
            definition_date="2026-03-01" if entry["raw_symbol"] == "NGJ26" else "2026-03-20",
            definition_start_s=0.0, definition_end_s=1000.0, event_start_s=1.0, event_end_s=20.0,
            record_count=10, size_bytes=100, inventory_observed_at="2026-07-21T00:00:00Z",
        )
    identity = {
        "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008, "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01", "session_day": "20260316",
    }
    events = [{**identity, "schema": NORMALIZED_SCHEMA, "event_type": "definition", "ts_event_s": 1.0, "source_sequence": 1}]
    for sequence in range(1, 7):
        events.append({
            **identity, "schema": NORMALIZED_SCHEMA, "event_type": "trade", "ts_event_s": sequence + 1,
            "source_sequence": sequence, "price": 3.0 + sequence / 1000, "size": 4, "side": "B",
        })
    events.append({
        **identity, "schema": NORMALIZED_SCHEMA, "event_type": "mbo", "ts_event_s": 8.0,
        "source_sequence": 1, "action": "A", "side": "B", "size": 10, "order_id": 1,
        "price": 3.004, "flags": F_LAST,
    })
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    result = replay_events(events, manifest=manifest, blind_prior=prior)
    assert result["completed_mbo_event_boundaries"] == 1
    assert result["streams"][0]["n_states"] == 1
    assert prior == {"up": 0.4, "flat": 0.2, "down": 0.4}
    print("[ng_historical_replay] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay normalized historical G15 L1/trades + MBO")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--allow-unknown-manifest", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.manifest or not args.blind_prior or not args.input or not args.out:
        parser.error("--manifest, --blind-prior, --input, and --out are required")
    result = replay_events(
        merge_sorted_sources([read_jsonl(path) for path in args.input]),
        manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
        blind_prior=json.loads(args.blind_prior.read_text(encoding="utf-8")),
        require_ready_manifest=not args.allow_unknown_manifest,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"processed": result["processed_records"], "boundaries": result["completed_mbo_event_boundaries"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
