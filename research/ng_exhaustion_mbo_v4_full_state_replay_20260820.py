#!/usr/bin/env python3
"""Full-state V4 replay bridge for native NG MBO.

The validated base adapter intentionally serializes compact per-F_LAST event frames.
This bridge exposes the *full* reconstructed book and FIFO queue at every completed
event group to downstream chain-family research without altering the base adapter.

Downstream research should consume `full_state_envelope()`/`replay_dbn_files()` so
full MBO state is available in-process. Serializing the entire order book at every
event is optional and is not required to keep the information available.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    V4MboAdapter,
    _int,
    _resolve_symbol,
    sha256_file,
)

REVISION = "NG_EXHAUSTION_MBO_V4_FULL_STATE_REPLAY_V1_20260820"


def full_state_envelope(adapter: V4MboAdapter, frame: dict[str, Any]) -> dict[str, Any]:
    iid = int(frame["instrument_id"])
    book = adapter.books[iid]
    checkpoint = book.checkpoint_state(
        int(frame["ts_recv_ns"]),
        include_full_depth=True,
        include_order_ids=True,
    )
    bid_levels = checkpoint["book"].get("bid_levels_full")
    ask_levels = checkpoint["book"].get("ask_levels_full")
    if bid_levels is None or ask_levels is None:
        raise RuntimeError("full-depth levels missing from V4 full-state checkpoint")
    for level in [*bid_levels, *ask_levels]:
        if "fifo_queue" not in level:
            raise RuntimeError("FIFO queue missing from V4 full-state checkpoint")
    return {
        "schema": "NG_MBO_V4_FULL_STATE_ENVELOPE_V1",
        "revision": REVISION,
        "census_view": "V4_NATIVE_FULL",
        "instrument_id": iid,
        "raw_symbol": frame.get("raw_symbol"),
        "ts_event_ns": frame["ts_event_ns"],
        "ts_recv_ns": frame["ts_recv_ns"],
        "causal_availability_clock": "ts_recv_ns",
        "compact_event_frame": frame,
        "full_state": checkpoint,
        "full_depth_exposed": True,
        "fifo_order_state_exposed": True,
        "native_dbn_replayable": True,
    }


def replay_dbn_files(
    paths: list[str],
    on_group: Callable[[dict[str, Any], list[dict[str, Any]]], None],
) -> dict[str, Any]:
    try:
        import databento as db
    except ImportError as exc:
        raise SystemExit("databento package is required to replay DBN files") from exc

    adapter = V4MboAdapter()
    sources = []
    for raw_path in paths:
        path = Path(raw_path)
        digest = sha256_file(path)
        store = db.DBNStore.from_file(str(path))
        instrument_map = None
        try:
            instrument_map = db.common.symbology.InstrumentMap()
            instrument_map.insert_metadata(store.metadata)
        except Exception:
            instrument_map = None
        records = 0
        groups_before = adapter.completed_event_group_count
        for record in store:
            if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                continue
            symbol = _resolve_symbol(
                instrument_map,
                _int(record, "instrument_id"),
                _int(record, "ts_recv"),
            )
            frame, legacy = adapter.apply(
                record,
                raw_symbol=symbol,
                source_dbn_object=str(path),
                source_dbn_sha256=digest,
            )
            records += 1
            if frame is not None:
                on_group(full_state_envelope(adapter, frame), legacy)
        adapter.assert_groups_closed()
        sources.append(
            {
                "path": str(path),
                "sha256": digest,
                "mbo_records": records,
                "completed_event_groups": adapter.completed_event_group_count - groups_before,
            }
        )
    return {
        "status": "V4_FULL_STATE_REPLAY_COMPLETE",
        "revision": REVISION,
        "sources": sources,
        "record_count": adapter.record_count,
        "completed_event_group_count": adapter.completed_event_group_count,
        "instrument_count": len(adapter.books),
        "full_depth_exposed": True,
        "fifo_order_state_exposed": True,
        "frankie_exposed": False,
        "frankie_mutated": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true", help="Replay and validate full state without serializing every book.")
    ap.add_argument("--summary", default="NG_EXHAUSTION_MBO_V4_FULL_STATE_REPLAY_SUMMARY_20260820.json")
    ap.add_argument("dbn", nargs="+")
    args = ap.parse_args()
    if not args.verify_only:
        raise SystemExit(
            "refusing implicit full-book serialization; use --verify-only or import "
            "replay_dbn_files() from the chain-family research engine"
        )
    groups = 0
    def consume(_envelope: dict[str, Any], _legacy: list[dict[str, Any]]) -> None:
        nonlocal groups
        groups += 1
    summary = replay_dbn_files(args.dbn, consume)
    if groups != summary["completed_event_group_count"]:
        raise RuntimeError("full-state callback/group count mismatch")
    Path(args.summary).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
