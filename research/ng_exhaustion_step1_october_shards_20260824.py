#!/usr/bin/env python3
"""October-only sharding around the frozen Step-1 full-MBO/full-V4 engine.

This module changes orchestration and provenance only.  A shard boundary is
usable only after a continued-versus-fresh replay reaches identical complete
future-output-bearing adapter state.  Warmup output is then assigned to the
preceding shard and removed from the following shard.  The merged result stays
unaccepted until exact canonical-row equivalence with monolithic October.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Production orchestration points this additive wrapper at the frozen candidate
# worktree.  The wrapper remains on the October branch while every scientific
# import comes from the exact frozen engine.
FROZEN_CANDIDATE_COMMIT = "0d318335825b4a0e19a5a2881522f3da0374788e"
_engine_root = os.environ.get("NG_EXHAUSTION_FROZEN_ENGINE_ROOT")
if _engine_root:
    sys.path.insert(0, str(Path(_engine_root).resolve() / "research"))

import ng_exhaustion_mbo_5y_step1_census_20260822 as census
from ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    ACTIVITY_WINDOWS_S,
    F_LAST,
    F_SNAPSHOT,
    V4MboAdapter,
    _int,
    _resolve_symbol,
)


OCTOBER_SEGMENT = "20211001_20211101"
OCTOBER_START_EPOCH_SECOND = 1_633_046_400
NOVEMBER_START_EPOCH_SECOND = 1_635_724_800
BOUNDARY_DATES = ("20211010", "20211017", "20211024")
BOUNDARY_PREDECESSORS = ("20211001", "20211010", "20211017")
WARMUP_SECONDS = max(ACTIVITY_WINDOWS_S)
REORDER_TOLERANCE_SECONDS = 60
BOUNDARY_METHOD = "CONTINUED_VERSUS_FRESH_COMPLETE_V4_STATE_AFTER_300S_WARMUP"
PLAN_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_FOUR_CPU_PLAN_V2_20260824"
PROOF_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_BOUNDARY_PROOF_V2_20260824"
GATE_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_BOUNDARY_GATE_V2_20260824"
SHARD_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_SHARD_RECEIPT_V2_20260824"
MERGE_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_MERGE_RECEIPT_V2_20260824"
EQUIVALENCE_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_EQUIVALENCE_V2_20260824"
ACCEPTANCE_SCHEMA = "NG_EXHAUSTION_STEP1_OCTOBER_ACCEPTANCE_RECEIPT_V1_20260824"


class OctoberShardError(RuntimeError):
    pass


def _date(obj: Mapping[str, Any]) -> str:
    return census._dbn_object_date(dict(obj))


def _bound_object(obj: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "date": _date(obj),
        "key": str(obj["key"]),
        "bytes": int(obj["bytes"]),
        "sha256": str(obj["sha256"]),
        "native_segment_job_id": str(obj["native_segment_job_id"]),
    }


def _self_hashed(value: Mapping[str, Any], field: str = "receipt_sha256") -> dict[str, Any]:
    body = dict(value)
    body[field] = census.sha256_json(body)
    return body


def _verify_self_hash(value: Mapping[str, Any], field: str = "receipt_sha256") -> None:
    body = dict(value)
    claimed = body.pop(field, None)
    if not isinstance(claimed, str) or claimed != census.sha256_json(body):
        raise OctoberShardError(f"receipt self-hash drift: {field}")


def october_shard_plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    objects = [dict(x) for x in manifest["canonical_dbn_objects"] if x["segment"] == OCTOBER_SEGMENT]
    objects.sort(key=_date)
    dates = [_date(x) for x in objects]
    expected_dates = [
        "20211001", "20211003", "20211004", "20211005", "20211006", "20211007", "20211008",
        "20211010", "20211011", "20211012", "20211013", "20211014", "20211015", "20211017",
        "20211018", "20211019", "20211020", "20211021", "20211022", "20211024", "20211025",
        "20211026", "20211027", "20211028", "20211029", "20211031",
    ]
    if dates != expected_dates or len(objects) != 26:
        raise OctoberShardError("exact 26-object October canonical roster drift")
    by_date = {_date(x): x for x in objects}
    edges: tuple[tuple[str | None, str | None], ...] = (
        (None, "20211010"),
        ("20211010", "20211017"),
        ("20211017", "20211024"),
        ("20211024", None),
    )
    shards: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(edges, 1):
        selected = [x for x in objects if (start is None or _date(x) >= start) and (end is None or _date(x) <= end)]
        shards.append({
            "shard_id": f"october-cpu-{index}",
            "cpu_slot": index - 1,
            "start_boundary_date": start,
            "end_boundary_date": end,
            "source_objects": [_bound_object(x) for x in selected],
            "source_total_bytes": sum(int(x["bytes"]) for x in selected),
        })
    transitions = []
    for predecessor, boundary in zip(BOUNDARY_PREDECESSORS, BOUNDARY_DATES):
        selected = [x for x in objects if predecessor <= _date(x) <= boundary]
        transitions.append({
            "predecessor_date": predecessor,
            "boundary_date": boundary,
            "boundary_object_sha256": str(by_date[boundary]["sha256"]),
            "source_objects": [_bound_object(x) for x in selected],
        })
    body = {
        "schema": PLAN_SCHEMA,
        "segment": OCTOBER_SEGMENT,
        "target_interval": "2021-10-01T00:00:00Z/2021-11-01T00:00:00Z",
        "target_start_epoch_second": OCTOBER_START_EPOCH_SECOND,
        "target_end_epoch_second": NOVEMBER_START_EPOCH_SECOND,
        "source_manifest_sha256": str(manifest["manifest_sha256"]),
        "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "source_object_count": len(objects),
        "shard_count": len(shards),
        "shards": shards,
        "boundary_transitions": transitions,
        "boundary_method": BOUNDARY_METHOD,
        "warmup_seconds": WARMUP_SECONDS,
        "reorder_tolerance_seconds": REORDER_TOLERANCE_SECONDS,
        "scientific_engine_changed": False,
        "acceptance_requires_monolithic_equivalence": True,
    }
    body["plan_sha256"] = census.sha256_json(body)
    return body


def _counter(value: Any) -> dict[str, int]:
    return {str(k): int(v) for k, v in sorted(dict(value).items()) if int(v) != 0}


def _book_state(book: Any, now_ns: int) -> dict[str, Any]:
    # rolling_activity performs the same time expiry used for a future event at
    # the equality clock; direct rows and window internals are retained below.
    activity_snapshots = book.rolling_activity(now_ns)
    orders = [asdict(book.orders[oid]) for oid in sorted(book.orders)]
    levels = {
        side: {str(price): list(ids) for price, ids in sorted(book.levels[side].items())}
        for side in ("A", "B")
    }
    windows = {}
    for seconds in ACTIVITY_WINDOWS_S:
        window = book._activity_windows[seconds]
        windows[str(seconds)] = {
            "rows": list(window.rows),
            "action_count": _counter(window.action_count),
            "action_side_count": _counter(window.action_side_count),
            "action_qty": _counter(window.action_qty),
            "action_side_qty": _counter(window.action_side_qty),
            "top_qty": _counter(window.top_qty),
            "priority_lost": int(window.priority_lost),
            "missing_refs": int(window.missing_refs),
            "ordered": bool(window.ordered),
        }
    return {
        "instrument_id": int(book.instrument_id),
        "orders": orders,
        "levels": levels,
        "activity_rows": list(book.activity),
        "activity_windows": windows,
        "activity_snapshots": activity_snapshots,
        "activity_last_now_ns": book._activity_last_now_ns,
        "event_group": [x.public_dict() for x in book.event_group],
        "legacy_group_rows": list(book._legacy_group_rows),
        "legacy_group_book_before": book._legacy_group_book_before,
        "legacy_group_visible_add": bool(book._legacy_group_visible_add),
        "top10_cache": {side: book._top10_cache[side] for side in ("A", "B")},
        "integrity": _counter(book.integrity),
        "last_sequence": book.last_sequence,
        "last_recv_ns": book.last_recv_ns,
        "last_event_ns": book.last_event_ns,
        "raw_symbol": book.raw_symbol,
        "side_depth": {side: int(book._side_depth[side]) for side in ("A", "B")},
        "side_order_count": {side: int(book._side_order_count[side]) for side in ("A", "B")},
    }


def adapter_state_payload(adapter: V4MboAdapter, now_ns: int) -> dict[str, Any]:
    return {
        "schema": "NG_EXHAUSTION_STEP1_COMPLETE_FUTURE_OUTPUT_BEARING_V4_STATE_V1_20260824",
        "now_ns": int(now_ns),
        "instrument_ids": sorted(adapter.books),
        "books": [_book_state(adapter.books[iid], now_ns) for iid in sorted(adapter.books)],
        # Global counters do not feed scientific rows; book state above does.
        "adapter_record_count_excluded_as_non_scientific_execution_count": True,
        "adapter_completed_group_count_excluded_as_non_scientific_execution_count": True,
    }


def _apply(adapter: V4MboAdapter, record: Any, raw_symbol: str | None = None) -> tuple[Any, dict[str, Any] | None]:
    msg = adapter.normalize(record, raw_symbol=raw_symbol)
    frame, _legacy = adapter.apply(record, raw_symbol=raw_symbol)
    return msg, frame


def prove_transition_records(
    predecessor_records: Iterable[Any],
    boundary_records: Iterable[Any],
    *,
    warmup_seconds: int = WARMUP_SECONDS,
) -> dict[str, Any]:
    continued = V4MboAdapter()
    fresh = V4MboAdapter()
    predecessor_count = 0
    for record in predecessor_records:
        _apply(continued, record)
        predecessor_count += 1
    first_live_recv_ns: int | None = None
    last_recv_ns: int | None = None
    max_event_second: int | None = None
    boundary_count = 0
    for record in boundary_records:
        msg, _ = _apply(continued, record)
        _apply(fresh, record)
        boundary_count += 1
        last_recv_ns = msg.ts_recv_ns if last_recv_ns is None else max(last_recv_ns, msg.ts_recv_ns)
        event_second = msg.ts_event_ns // 1_000_000_000
        max_event_second = event_second if max_event_second is None else max(max_event_second, event_second)
        if not msg.is_snapshot and first_live_recv_ns is None:
            first_live_recv_ns = msg.ts_recv_ns
    reasons: list[str] = []
    if boundary_count == 0:
        reasons.append("empty_boundary")
    if first_live_recv_ns is None:
        reasons.append("no_live_activity")
    try:
        continued.assert_groups_closed()
        fresh.assert_groups_closed()
    except RuntimeError:
        reasons.append("open_event_groups")
    equality_now_ns = max(last_recv_ns or 0, (first_live_recv_ns or 0) + int(warmup_seconds) * 1_000_000_000)
    left = adapter_state_payload(continued, equality_now_ns)
    right = adapter_state_payload(fresh, equality_now_ns)
    left_hash = census.sha256_json(left)
    right_hash = census.sha256_json(right)
    if left_hash != right_hash:
        reasons.append("state_mismatch")
    cut = None if max_event_second is None else int(max_event_second + REORDER_TOLERANCE_SECONDS + 1)
    if cut is None:
        reasons.append("cut_unavailable")
    return {
        "schema": PROOF_SCHEMA,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "method": BOUNDARY_METHOD,
        "warmup_seconds": int(warmup_seconds),
        "reorder_tolerance_seconds": REORDER_TOLERANCE_SECONDS,
        "predecessor_record_count": predecessor_count,
        "boundary_record_count": boundary_count,
        "continued_instrument_ids": sorted(continued.books),
        "fresh_instrument_ids": sorted(fresh.books),
        "equality_clock_recv_ns": equality_now_ns,
        "cut_epoch_second": cut,
        "continued_state_sha256": left_hash,
        "fresh_state_sha256": right_hash,
        "compared_state_components": [
            "instrument_roster", "full_orders", "fifo_levels", "rolling_activity_rows_and_windows",
            "integrity", "sequence_and_clock_watermarks", "raw_symbol", "event_group_buffers",
            "cached_top10", "side_depth_and_order_counts",
        ],
        "reasons": reasons,
        "scientific_engine_changed": False,
    }


def _dbn_records(path: Path) -> Iterable[tuple[Any, str | None]]:
    try:
        import databento as db
    except ImportError as exc:
        raise OctoberShardError("databento==0.81.0 is required") from exc
    store = db.DBNStore.from_file(str(path))
    instrument_map = None
    try:
        instrument_map = db.common.symbology.InstrumentMap()
        instrument_map.insert_metadata(store.metadata)
    except Exception:
        instrument_map = None
    for record in store:
        if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
            continue
        yield record, _resolve_symbol(instrument_map, _int(record, "instrument_id"), _int(record, "ts_recv"))


def _verified_object_path(stage_dir: Path, manifest: Mapping[str, Any], obj: Mapping[str, Any]) -> Path:
    path = census._local_object_path(stage_dir, dict(manifest), dict(obj))
    if not path.is_file() or path.stat().st_size != int(obj["bytes"]) or census.sha256_file(path) != obj["sha256"]:
        raise OctoberShardError(f"source identity drift: {obj['key']}")
    return path


def prove_transition(
    manifest_path: str | Path,
    stage_dir: str | Path,
    predecessor_date: str,
    boundary_date: str,
    output_path: str | Path,
) -> dict[str, Any]:
    manifest = census.load_manifest(manifest_path)
    plan = october_shard_plan(manifest)
    transition = next((x for x in plan["boundary_transitions"] if x["predecessor_date"] == predecessor_date and x["boundary_date"] == boundary_date), None)
    if transition is None:
        raise OctoberShardError("transition is outside the exact October induction chain")
    by_key = {x["key"]: x for x in manifest["canonical_dbn_objects"]}
    objects = [by_key[x["key"]] for x in transition["source_objects"]]
    paths = [_verified_object_path(Path(stage_dir), manifest, x) for x in objects]
    continued = V4MboAdapter()
    predecessor_count = 0
    for path in paths[:-1]:
        for record, symbol in _dbn_records(path):
            _apply(continued, record, symbol)
            predecessor_count += 1
        continued.assert_groups_closed()
    boundary_rows = list(_dbn_records(paths[-1]))
    fresh = V4MboAdapter()
    first_live_recv_ns = None
    max_event_second = None
    equality_now_ns = 0
    compared = False
    left: dict[str, Any] = {}
    right: dict[str, Any] = {}
    for record, symbol in boundary_rows:
        msg, _ = _apply(continued, record, symbol)
        _apply(fresh, record, symbol)
        if not msg.is_snapshot and first_live_recv_ns is None:
            first_live_recv_ns = msg.ts_recv_ns
        max_event_second = max(max_event_second or msg.ts_event_ns // 1_000_000_000, msg.ts_event_ns // 1_000_000_000)
        threshold = None if first_live_recv_ns is None else first_live_recv_ns + WARMUP_SECONDS * 1_000_000_000
        if threshold is not None and msg.ts_recv_ns >= threshold and all(not x.event_group for x in continued.books.values()):
            equality_now_ns = msg.ts_recv_ns
            left = adapter_state_payload(continued, equality_now_ns)
            right = adapter_state_payload(fresh, equality_now_ns)
            compared = True
            break
    reasons = []
    if first_live_recv_ns is None:
        reasons.append("no_live_activity")
    if not compared:
        reasons.append("boundary_source_does_not_cover_full_warmup")
    left_hash = census.sha256_json(left)
    right_hash = census.sha256_json(right)
    if compared and left_hash != right_hash:
        reasons.append("state_mismatch")
    cut = None if not compared or max_event_second is None else max_event_second + REORDER_TOLERANCE_SECONDS + 1
    proof = {
        "schema": PROOF_SCHEMA,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "method": BOUNDARY_METHOD,
        "plan_sha256": plan["plan_sha256"],
        "source_manifest_sha256": manifest["manifest_sha256"],
        "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "engine_hashes": census.material_hashes(),
        "ruleset_sha256": census.ruleset_sha256(),
        "predecessor_date": predecessor_date,
        "boundary_date": boundary_date,
        "boundary_object_sha256": transition["boundary_object_sha256"],
        "source_objects": transition["source_objects"],
        "predecessor_record_count": predecessor_count,
        "boundary_record_count_read": len(boundary_rows),
        "warmup_seconds": WARMUP_SECONDS,
        "reorder_tolerance_seconds": REORDER_TOLERANCE_SECONDS,
        "equality_clock_recv_ns": equality_now_ns,
        "cut_epoch_second": cut,
        "continued_instrument_ids": sorted(continued.books),
        "fresh_instrument_ids": sorted(fresh.books),
        "continued_state_sha256": left_hash,
        "fresh_state_sha256": right_hash,
        "reasons": reasons,
        "scientific_engine_changed": False,
    }
    proof = _self_hashed(proof)
    census.atomic_json(Path(output_path), proof)
    return proof


def validate_boundary_gate(gate_or_path: Mapping[str, Any] | str | Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    gate = dict(gate_or_path) if isinstance(gate_or_path, Mapping) else json.loads(Path(gate_or_path).read_text())
    if "receipt_sha256" in gate:
        _verify_self_hash(gate)
    proofs = gate.get("boundary_proofs")
    if not isinstance(proofs, list):
        raise OctoberShardError("October boundary gate proof list is absent")
    for proof in proofs:
        _verify_self_hash(proof)
    expected = [(x["predecessor_date"], x["boundary_date"], x["boundary_object_sha256"]) for x in plan["boundary_transitions"]]
    actual = [(x.get("predecessor_date"), x.get("boundary_date"), x.get("boundary_object_sha256")) for x in proofs]
    cuts = [x.get("cut_epoch_second") for x in proofs]
    valid_cuts = len(cuts) == 3 and all(isinstance(x, int) and not isinstance(x, bool) for x in cuts) and all(cuts[i] < cuts[i + 1] for i in range(2)) and OCTOBER_START_EPOCH_SECOND < cuts[0] and cuts[-1] < NOVEMBER_START_EPOCH_SECOND
    if (
        gate.get("schema") != GATE_SCHEMA
        or gate.get("status") != "PASS"
        or gate.get("plan_sha256") != plan["plan_sha256"]
        or gate.get("source_manifest_sha256") != plan["source_manifest_sha256"]
        or gate.get("frozen_candidate_commit") != FROZEN_CANDIDATE_COMMIT
        or not isinstance(gate.get("engine_hashes"), dict)
        or not gate.get("engine_hashes")
        or not isinstance(gate.get("ruleset_sha256"), str)
        or gate.get("engine_hashes") != census.material_hashes()
        or gate.get("ruleset_sha256") != census.ruleset_sha256()
        or gate.get("scientific_engine_changed") is not False
        or actual != expected
        or not valid_cuts
        or any(
            x.get("status") != "PASS"
            or x.get("schema") != PROOF_SCHEMA
            or x.get("method") != BOUNDARY_METHOD
            or x.get("continued_state_sha256") != x.get("fresh_state_sha256")
            or x.get("plan_sha256") != plan["plan_sha256"]
            or x.get("source_manifest_sha256") != plan["source_manifest_sha256"]
            or x.get("frozen_candidate_commit") != FROZEN_CANDIDATE_COMMIT
            or x.get("engine_hashes") != gate.get("engine_hashes")
            or x.get("ruleset_sha256") != gate.get("ruleset_sha256")
            or x.get("source_objects") != plan["boundary_transitions"][index]["source_objects"]
            or x.get("warmup_seconds") != WARMUP_SECONDS
            or x.get("reorder_tolerance_seconds") != REORDER_TOLERANCE_SECONDS
            or x.get("reasons") != []
            or x.get("scientific_engine_changed") is not False
            for index, x in enumerate(proofs)
        )
    ):
        raise OctoberShardError("October boundary gate is not an exact induction-chain pass")
    return gate


def assemble_boundary_gate(plan: Mapping[str, Any], proofs: Sequence[Mapping[str, Any]], output_path: str | Path) -> dict[str, Any]:
    if len(proofs) != 3:
        raise OctoberShardError("exactly three October boundary proofs are required")
    for proof in proofs:
        _verify_self_hash(proof)
    gate = {
        "schema": GATE_SCHEMA,
        "status": "PASS" if all(x.get("status") == "PASS" for x in proofs) else "FAIL_CLOSED",
        "plan_sha256": plan["plan_sha256"],
        "source_manifest_sha256": plan["source_manifest_sha256"],
        "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "engine_hashes": dict(proofs[0].get("engine_hashes") or {}),
        "ruleset_sha256": proofs[0].get("ruleset_sha256"),
        "boundary_proofs": [dict(x) for x in proofs],
        "scientific_engine_changed": False,
    }
    gate = _self_hashed(gate)
    if gate["status"] == "PASS":
        validate_boundary_gate(gate, plan)
    census.atomic_json(Path(output_path), gate)
    return gate


def _object_index(objects: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for obj in objects:
        key = str(obj["key"])
        if key in index:
            raise OctoberShardError(f"duplicate bound source key: {key}")
        index[key] = obj
    return index


def canonical_science_row(row: Mapping[str, Any], objects: Sequence[Mapping[str, Any]], bucket: str) -> dict[str, Any]:
    value = dict(row)
    key = value.get("source_dbn_key")
    sha = value.get("source_dbn_sha256")
    obj = _object_index(objects).get(str(key))
    if obj is None or sha != obj["sha256"]:
        raise OctoberShardError("seconds row source key/SHA is not in the exact bound roster")
    expected_uri = f"s3://{bucket}/{key}"
    source = value.get("source_dbn_object")
    if source != expected_uri:
        native_marker = "native/"
        native_index = str(key).find(native_marker)
        expected_local_suffix = str(key)[native_index:] if native_index >= 0 else str(key)
        normalized_source = None if not isinstance(source, str) else Path(source).as_posix()
        if normalized_source is None or not normalized_source.endswith("/" + expected_local_suffix):
            raise OctoberShardError("seconds row local source path does not resolve to the bound object")
    value["source_dbn_object"] = expected_uri
    return value


def _iter_rows(path: Path) -> Iterable[tuple[bytes, dict[str, Any]]]:
    with gzip.open(path, "rb") as handle:
        for raw in handle:
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise OctoberShardError(f"non-object seconds row: {path}")
            yield raw, row


def trim_seconds(
    input_path: str | Path,
    output_path: str | Path,
    start_epoch_second: int,
    end_epoch_second: int,
    source_objects: Sequence[Mapping[str, Any]],
    bucket: str,
) -> dict[str, Any]:
    if start_epoch_second >= end_epoch_second:
        raise OctoberShardError("empty or inverted shard target interval")
    writer = census.DeterministicGzipJsonlWriter(Path(output_path))
    previous = None
    try:
        for _raw, row in _iter_rows(Path(input_path)):
            second = row.get("epoch_second")
            if not isinstance(second, int) or isinstance(second, bool) or (previous is not None and second <= previous):
                raise OctoberShardError("child seconds are not strictly time ordered")
            previous = second
            if start_epoch_second <= second < end_epoch_second:
                writer.write(canonical_science_row(row, source_objects, bucket))
        output = writer.close()
    except Exception:
        writer.abort()
        raise
    if output["rows"] <= 0:
        raise OctoberShardError("trimmed target shard is empty")
    return output


def _validate_child_receipt(
    receipt: Mapping[str, Any],
    output_path: Path,
    manifest: Mapping[str, Any],
    source_objects: Sequence[Mapping[str, Any]],
) -> None:
    _verify_self_hash(receipt)
    expected_sources = [{k: x[k] for k in ("key", "bytes", "sha256", "native_segment_job_id")} for x in source_objects]
    output = receipt.get("seconds_output") or {}
    if (
        receipt.get("schema") != "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1"
        or receipt.get("status") != "SEGMENT_COMPLETE"
        or receipt.get("segment") != OCTOBER_SEGMENT
        or receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]
        or receipt.get("source_objects") != expected_sources
        or receipt.get("source_object_count") != len(expected_sources)
        or output.get("gzip_sha256") != census.sha256_file(output_path)
        or not isinstance(receipt.get("engine_hashes"), dict)
        or not receipt.get("engine_hashes")
        or not isinstance(receipt.get("ruleset_sha256"), str)
        or receipt.get("release_or_virgin_holdout_consumed") is not False
        or receipt.get("predictive_or_trading_experiment_run") is not False
    ):
        raise OctoberShardError("frozen child receipt/output/source binding failed")


def _target_intervals(plan: Mapping[str, Any], gate: Mapping[str, Any]) -> list[tuple[int, int]]:
    cuts = [int(x["cut_epoch_second"]) for x in gate["boundary_proofs"]]
    edges = [OCTOBER_START_EPOCH_SECOND, *cuts, NOVEMBER_START_EPOCH_SECOND]
    return list(zip(edges, edges[1:]))


def run_shard(
    manifest_path: str | Path,
    shard_id: str,
    work_dir: str | Path,
    boundary_gate_path: str | Path,
    progress_s3_prefix: str | None = None,
) -> dict[str, Any]:
    from kalshi import creds

    manifest = census.load_manifest(manifest_path)
    plan = october_shard_plan(manifest)
    gate = validate_boundary_gate(boundary_gate_path, plan)
    shard_index = next((i for i, x in enumerate(plan["shards"]) if x["shard_id"] == shard_id), None)
    if shard_index is None:
        raise OctoberShardError(f"unknown October shard: {shard_id}")
    shard = plan["shards"][shard_index]
    start, end = _target_intervals(plan, gate)[shard_index]
    root = Path(work_dir)
    stage, child_out, artifact = root / "stage", root / "child", root / "artifact"
    for path in (stage, child_out, artifact):
        path.mkdir(parents=True, exist_ok=True)
    source_dates = {x["date"] for x in shard["source_objects"]}
    s3 = creds.aws_client("s3", manifest.get("region", "us-east-2"))
    staged: list[str] = []
    def upload_progress(path: Path) -> None:
        if progress_s3_prefix:
            key = f"{progress_s3_prefix.rstrip('/')}/{shard_id}/{path.name}"
            s3.upload_file(str(path), manifest["bucket"], key)
    try:
        staged = census.stage_segment(manifest, OCTOBER_SEGMENT, stage, s3, source_dates)
        census.process_segment(
            manifest_path,
            OCTOBER_SEGMENT,
            stage,
            child_out,
            object_dates=source_dates,
            heartbeat_on_write=upload_progress,
        )
        child_receipt_path = child_out / f"{OCTOBER_SEGMENT}.receipt.json"
        child_seconds_path = child_out / f"{OCTOBER_SEGMENT}.seconds.jsonl.gz"
        child = json.loads(child_receipt_path.read_text())
        _validate_child_receipt(child, child_seconds_path, manifest, shard["source_objects"])
        upload_progress(child_receipt_path)
        if child["engine_hashes"] != gate["engine_hashes"] or child["ruleset_sha256"] != gate["ruleset_sha256"]:
            raise OctoberShardError("boundary proof and shard child engine/ruleset identities differ")
        trimmed_path = artifact / f"{shard_id}.seconds.jsonl.gz"
        trimmed = trim_seconds(child_seconds_path, trimmed_path, start, end, shard["source_objects"], manifest["bucket"])
    finally:
        for path in staged:
            Path(path).unlink(missing_ok=True)
    wrapper = {
        "schema": SHARD_SCHEMA,
        "status": "SHARD_COMPLETE_UNACCEPTED_PENDING_MONOLITHIC_EQUIVALENCE",
        "shard_id": shard_id,
        "plan_sha256": plan["plan_sha256"],
        "boundary_gate_receipt_sha256": gate["receipt_sha256"],
        "source_objects": shard["source_objects"],
        "source_partition_mode": "OCTOBER_CANONICAL_SHARD_WRAPPER_AUTHORITATIVE_CHILD_SCOPE_INTERNAL_ONLY",
        "target_start_epoch_second": start,
        "target_end_epoch_second": end,
        "child_receipt_sha256": child["receipt_sha256"],
        "child_engine_hashes": child["engine_hashes"],
        "child_ruleset_sha256": child["ruleset_sha256"],
        "trimmed_seconds_output": trimmed,
        "scientific_engine_changed": False,
        "permanent_frankie_mutated": False,
        "release_or_virgin_holdout_consumed": False,
    }
    wrapper = _self_hashed(wrapper)
    census.atomic_json(artifact / f"{shard_id}.receipt.json", wrapper)
    return wrapper


def merge_shard_bundles(
    plan: Mapping[str, Any],
    bundles: Sequence[tuple[Mapping[str, Any], str | Path, Mapping[str, Any]]],
    output_path: str | Path,
) -> dict[str, Any]:
    if len(bundles) != 4:
        raise OctoberShardError("exactly four shard bundles are required")
    expected_ids = [x["shard_id"] for x in plan["shards"]]
    receipts = [dict(x[0]) for x in bundles]
    if [x.get("shard_id") for x in receipts] != expected_ids:
        raise OctoberShardError("shard bundle order/identity drift")
    gate_hashes: set[str] = set()
    engine_hashes: list[Mapping[str, Any]] = []
    ruleset_hashes: set[str] = set()
    for plan_shard, receipt, (_wrapper, raw_path, child) in zip(plan["shards"], receipts, bundles):
        _verify_self_hash(receipt)
        _verify_self_hash(child)
        path = Path(raw_path)
        output = receipt.get("trimmed_seconds_output") or {}
        expected_child_sources = [{k: x[k] for k in ("key", "bytes", "sha256", "native_segment_job_id")} for x in plan_shard["source_objects"]]
        if (
            receipt.get("schema") != SHARD_SCHEMA
            or receipt.get("status") != "SHARD_COMPLETE_UNACCEPTED_PENDING_MONOLITHIC_EQUIVALENCE"
            or receipt.get("plan_sha256") != plan["plan_sha256"]
            or receipt.get("source_objects") != plan_shard["source_objects"]
            or output.get("gzip_sha256") != census.sha256_file(path)
            or child.get("schema") != "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1"
            or child.get("status") != "SEGMENT_COMPLETE"
            or child.get("source_objects") != expected_child_sources
            or child.get("source_object_count") != len(expected_child_sources)
            or receipt.get("child_receipt_sha256") != child.get("receipt_sha256")
            or receipt.get("child_engine_hashes") != child.get("engine_hashes")
            or receipt.get("child_ruleset_sha256") != child.get("ruleset_sha256")
        ):
            raise OctoberShardError("shard wrapper/output binding failed")
        gate_hashes.add(str(receipt.get("boundary_gate_receipt_sha256")))
        engine_hashes.append(receipt["child_engine_hashes"])
        ruleset_hashes.add(str(receipt["child_ruleset_sha256"]))
    if len(gate_hashes) != 1 or "None" in gate_hashes or len(ruleset_hashes) != 1 or any(x != engine_hashes[0] for x in engine_hashes[1:]):
        raise OctoberShardError("shards do not share one gate/engine/ruleset identity")
    intervals = [(int(x["target_start_epoch_second"]), int(x["target_end_epoch_second"])) for x in receipts]
    if intervals[0][0] != OCTOBER_START_EPOCH_SECOND or intervals[-1][1] != NOVEMBER_START_EPOCH_SECOND or any(intervals[i][1] != intervals[i + 1][0] for i in range(3)):
        raise OctoberShardError("shard target intervals have a gap or overlap")
    writer = census.DeterministicGzipJsonlWriter(Path(output_path))
    previous = None
    total = 0
    try:
        for receipt, (_wrapper, raw_path, _child) in zip(receipts, bundles):
            start, end = int(receipt["target_start_epoch_second"]), int(receipt["target_end_epoch_second"])
            rows = 0
            for _raw, row in _iter_rows(Path(raw_path)):
                second = row.get("epoch_second")
                if not isinstance(second, int) or isinstance(second, bool) or not start <= second < end or (previous is not None and second <= previous):
                    raise OctoberShardError("merged row violates unique canonical target coverage")
                writer.write(row)
                previous = second
                rows += 1
                total += 1
            if rows != receipt["trimmed_seconds_output"]["rows"] or rows == 0:
                raise OctoberShardError("shard row count/emptiness drift")
        merged = writer.close()
    except Exception:
        writer.abort()
        raise
    return {
        "schema": MERGE_SCHEMA,
        "status": "CANDIDATE_MERGE_COMPLETE_UNACCEPTED_PENDING_MONOLITHIC_EQUIVALENCE",
        "plan_sha256": plan["plan_sha256"],
        "source_manifest_sha256": plan["source_manifest_sha256"],
        "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "target_start_epoch_second": OCTOBER_START_EPOCH_SECOND,
        "target_end_epoch_second": NOVEMBER_START_EPOCH_SECOND,
        "row_count": total,
        "ordered_shard_receipt_sha256": [x["receipt_sha256"] for x in receipts],
        "boundary_gate_receipt_sha256": next(iter(gate_hashes)),
        "child_engine_hashes": dict(engine_hashes[0]),
        "child_ruleset_sha256": next(iter(ruleset_hashes)),
        "merged_seconds_output": merged,
        "scientific_engine_changed": False,
        "permanent_frankie_mutated": False,
    }


def verify_monolithic_equivalence(
    reference_path: str | Path,
    candidate_path: str | Path,
    source_objects: Sequence[Mapping[str, Any]],
    bucket: str,
) -> dict[str, Any]:
    left = iter(_iter_rows(Path(reference_path)))
    right = iter(_iter_rows(Path(candidate_path)))
    digest = hashlib.sha256()
    count = 0
    while True:
        try:
            left_item = next(left)
        except StopIteration:
            left_item = None
        try:
            right_item = next(right)
        except StopIteration:
            right_item = None
        if left_item is None and right_item is None:
            break
        if left_item is None or right_item is None:
            raise OctoberShardError(f"monolithic equivalence row-count mismatch at row {count}")
        left_row = canonical_science_row(left_item[1], source_objects, bucket)
        right_row = canonical_science_row(right_item[1], source_objects, bucket)
        left_bytes = census.canonical_bytes(left_row) + b"\n"
        right_bytes = census.canonical_bytes(right_row) + b"\n"
        if left_bytes != right_bytes:
            raise OctoberShardError(f"monolithic scientific equivalence failed at row {count}")
        digest.update(left_bytes)
        count += 1
    return {
        "schema": EQUIVALENCE_SCHEMA,
        "status": "PASS",
        "comparison": "EXACT_CANONICAL_JSONL_AFTER_ALLOWLISTED_SOURCE_PATH_CANONICALIZATION",
        "allowlisted_normalization": ["source_dbn_object: validated local path -> bound canonical S3 URI"],
        "row_count": count,
        "canonical_jsonl_sha256": digest.hexdigest(),
        "scientific_engine_changed": False,
        "permanent_frankie_mutated": False,
    }


def validate_merge_receipt(receipt: Mapping[str, Any], candidate_path: Path, plan: Mapping[str, Any]) -> None:
    _verify_self_hash(receipt)
    output = receipt.get("merged_seconds_output") or {}
    gate_hash = receipt.get("boundary_gate_receipt_sha256")
    if (
        receipt.get("schema") != MERGE_SCHEMA
        or receipt.get("status") != "CANDIDATE_MERGE_COMPLETE_UNACCEPTED_PENDING_MONOLITHIC_EQUIVALENCE"
        or receipt.get("plan_sha256") != plan["plan_sha256"]
        or receipt.get("source_manifest_sha256") != plan["source_manifest_sha256"]
        or receipt.get("frozen_candidate_commit") != FROZEN_CANDIDATE_COMMIT
        or receipt.get("target_start_epoch_second") != OCTOBER_START_EPOCH_SECOND
        or receipt.get("target_end_epoch_second") != NOVEMBER_START_EPOCH_SECOND
        or not isinstance(receipt.get("row_count"), int)
        or receipt.get("row_count", 0) <= 0
        or output.get("rows") != receipt.get("row_count")
        or output.get("gzip_sha256") != census.sha256_file(candidate_path)
        or not isinstance(gate_hash, str)
        or len(gate_hash) != 64
        or len(receipt.get("ordered_shard_receipt_sha256") or []) != 4
        or receipt.get("scientific_engine_changed") is not False
        or receipt.get("permanent_frankie_mutated") is not False
        or not isinstance(receipt.get("child_engine_hashes"), dict)
        or not isinstance(receipt.get("child_ruleset_sha256"), str)
    ):
        raise OctoberShardError("candidate merge receipt is not an exact unaccepted October merge")


def _load_receipts(paths: Sequence[str]) -> list[dict[str, Any]]:
    return [json.loads(Path(path).read_text()) for path in paths]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan_cmd = sub.add_parser("plan")
    plan_cmd.add_argument("--manifest", required=True)
    plan_cmd.add_argument("--output", required=True)
    prove = sub.add_parser("prove-transition")
    prove.add_argument("--manifest", required=True)
    prove.add_argument("--stage-dir", required=True)
    prove.add_argument("--predecessor-date", required=True)
    prove.add_argument("--boundary-date", required=True)
    prove.add_argument("--output", required=True)
    gate = sub.add_parser("assemble-gate")
    gate.add_argument("--manifest", required=True)
    gate.add_argument("--proofs", nargs=3, required=True)
    gate.add_argument("--output", required=True)
    run = sub.add_parser("run-shard")
    run.add_argument("--manifest", required=True)
    run.add_argument("--shard-id", required=True)
    run.add_argument("--work-dir", required=True)
    run.add_argument("--boundary-gate", required=True)
    run.add_argument("--progress-s3-prefix")
    merge = sub.add_parser("merge")
    merge.add_argument("--manifest", required=True)
    merge.add_argument("--boundary-gate", required=True)
    merge.add_argument("--receipts", nargs=4, required=True)
    merge.add_argument("--child-receipts", nargs=4, required=True)
    merge.add_argument("--inputs", nargs=4, required=True)
    merge.add_argument("--output", required=True)
    merge.add_argument("--receipt", required=True)
    equivalent = sub.add_parser("equivalence")
    equivalent.add_argument("--manifest", required=True)
    equivalent.add_argument("--reference", required=True)
    equivalent.add_argument("--reference-receipt", required=True)
    equivalent.add_argument("--candidate", required=True)
    equivalent.add_argument("--merge-receipt", required=True)
    equivalent.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        result = october_shard_plan(census.load_manifest(args.manifest))
        census.atomic_json(Path(args.output), result)
    elif args.command == "prove-transition":
        result = prove_transition(args.manifest, args.stage_dir, args.predecessor_date, args.boundary_date, args.output)
        if result["status"] != "PASS":
            raise SystemExit(2)
    elif args.command == "assemble-gate":
        plan = october_shard_plan(census.load_manifest(args.manifest))
        result = assemble_boundary_gate(plan, _load_receipts(args.proofs), args.output)
        if result["status"] != "PASS":
            raise SystemExit(2)
    elif args.command == "run-shard":
        result = run_shard(args.manifest, args.shard_id, args.work_dir, args.boundary_gate, args.progress_s3_prefix)
    elif args.command == "merge":
        manifest = census.load_manifest(args.manifest)
        plan = october_shard_plan(manifest)
        gate = validate_boundary_gate(args.boundary_gate, plan)
        receipts = _load_receipts(args.receipts)
        children = _load_receipts(args.child_receipts)
        result = merge_shard_bundles(plan, list(zip(receipts, args.inputs, children)), args.output)
        if result["boundary_gate_receipt_sha256"] != gate["receipt_sha256"]:
            raise OctoberShardError("merge shard receipts do not bind the supplied proven boundary gate")
        result = _self_hashed(result)
        census.atomic_json(Path(args.receipt), result)
    else:
        manifest = census.load_manifest(args.manifest)
        plan = october_shard_plan(manifest)
        merge_receipt = json.loads(Path(args.merge_receipt).read_text())
        validate_merge_receipt(merge_receipt, Path(args.candidate), plan)
        objects = [_bound_object(x) for x in manifest["canonical_dbn_objects"] if x["segment"] == OCTOBER_SEGMENT]
        reference_receipt = json.loads(Path(args.reference_receipt).read_text())
        _validate_child_receipt(reference_receipt, Path(args.reference), manifest, objects)
        if reference_receipt.get("engine_hashes") != merge_receipt.get("child_engine_hashes") or reference_receipt.get("ruleset_sha256") != merge_receipt.get("child_ruleset_sha256"):
            raise OctoberShardError("monolithic and sharded engine/ruleset identities differ")
        result = verify_monolithic_equivalence(args.reference, args.candidate, objects, manifest["bucket"])
        result.update({
            "schema": ACCEPTANCE_SCHEMA,
            "status": "ACCEPTED_EXACT_MONOLITHIC_EQUIVALENCE",
            "source_manifest_sha256": manifest["manifest_sha256"],
            "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
            "plan_sha256": merge_receipt["plan_sha256"],
            "boundary_gate_receipt_sha256": merge_receipt["boundary_gate_receipt_sha256"],
            "engine_hashes": merge_receipt["child_engine_hashes"],
            "ruleset_sha256": merge_receipt["child_ruleset_sha256"],
            "merge_receipt_sha256": merge_receipt["receipt_sha256"],
            "reference_receipt_sha256": reference_receipt["receipt_sha256"],
            "reference_gzip_sha256": census.sha256_file(Path(args.reference)),
            "candidate_gzip_sha256": census.sha256_file(Path(args.candidate)),
            "accepted_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        result["normalization_policy_sha256"] = census.sha256_json({
            "comparison": result["comparison"],
            "allowlisted_normalization": result["allowlisted_normalization"],
        })
        result = _self_hashed(result)
        census.atomic_json(Path(args.output), result)
    print(json.dumps({"status": result.get("status", "PLAN_WRITTEN"), "receipt_sha256": result.get("receipt_sha256"), "plan_sha256": result.get("plan_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
