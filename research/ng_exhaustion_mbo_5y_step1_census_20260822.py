#!/usr/bin/env python3
"""Restartable dual-view five-year NG exhaustion Step-1 structural census.

This additive runner binds three already-frozen surfaces rather than rewriting
them:

* the exact native-object manifest;
* the MBO full-state replay bridge;
* the 2026-08-17 detector and inherited-information lineage implementation.

It emits LEGACY_CONTROL and V4_NATIVE_FULL populations plus a deterministic
crosswalk.  It performs no predictive/trading experiment and never reads the
release/virgin holdout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import tempfile
import time
import gc
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import ng_exhaustion_chain_canonical_table_20260817 as frozen_detector
import ng_exhaustion_chain_phase1_discovery_20260817 as frozen_discovery
import ng_exhaustion_chain_phase1_structural_54w_20260817 as frozen_structural
from ng_exhaustion_mbo_5y_canonical_manifest_20260822 import payload_sha256
from ng_exhaustion_mbo_v4_full_state_replay_20260820 import replay_dbn_files
from ng_exhaustion_mbo_v4_state_adapter_20260820 import ADAPTER_REVISION, sha256_file


REVISION = "NG_EXHAUSTION_MBO_5Y_STEP1_DUAL_CENSUS_V1_20260822"
RULESET = "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL"
NATIVE_TAXONOMY = "NG_EXHAUSTION_V4_NATIVE_STRUCTURE_TAXONOMY_V1_20260822"
MAX_DEPTH = 5
INITIAL_TRAIN_WEEKS = 52
TEST_BLOCK_WEEKS = 26
HEARTBEAT_SECONDS = 600
OVERLAP_WEEKS = ("20250713", "20250921", "20250928")
OVERLAP_POLICY = {
    "schema": "NG_EXHAUSTION_LEGACY_CONTROL_OVERLAP_POLICY_V1_20260822",
    "already_revealed_weeks": list(OVERLAP_WEEKS),
    "match_key": "same polarity and nearest t0 within 1 second; one-to-one",
    "minimum_event_recall": 0.95,
    "minimum_event_precision": 0.95,
    "maximum_relative_event_count_delta": 0.05,
    "minimum_family_agreement_on_matches": 0.99,
    "minimum_endpoint_confirmation_agreement_within_1s": 0.95,
    "minimum_lineage_depth_agreement_on_common_origins": 0.95,
    "minimum_lineage_sign_agreement_on_comparable_cells": 0.95,
    "mismatch_policy": RULESET,
    "frozen_detector_mutation_allowed": False,
}


def ruleset_sha256() -> str:
    return sha256_json({
        "revision": REVISION,
        "retention_policy": RULESET,
        "native_taxonomy": NATIVE_TAXONOMY,
        "maximum_depth": MAX_DEPTH,
        "initial_train_weeks": INITIAL_TRAIN_WEEKS,
        "test_block_weeks": TEST_BLOCK_WEEKS,
        "overlap_policy": OVERLAP_POLICY,
    })


class CensusError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_paths(paths: Iterable[str | Path]) -> dict[str, str]:
    return {str(path): sha256_file(Path(path)) for path in paths}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(raw)
    try:
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def deterministic_gzip_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    writer = DeterministicGzipJsonlWriter(path)
    try:
        for row in rows:
            writer.write(row)
        return writer.close()
    except Exception:
        writer.abort()
        raise


class DeterministicGzipJsonlWriter:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.raw_hash = hashlib.sha256()
        self.rows = 0
        self.tmp = path.with_suffix(path.suffix + ".partial")
        self.tmp.unlink(missing_ok=True)
        self.binary_handle = self.tmp.open("wb")
        self.handle = gzip.GzipFile(filename="", mode="wb", fileobj=self.binary_handle, mtime=0)
        self.closed = False

    def write(self, row: dict[str, Any]) -> None:
        line = canonical_bytes(row) + b"\n"
        self.handle.write(line)
        self.raw_hash.update(line)
        self.rows += 1

    def close(self) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("deterministic gzip writer already closed")
        self.handle.close()
        self.binary_handle.close()
        os.replace(self.tmp, self.path)
        self.closed = True
        return {
            "path": str(self.path),
            "rows": self.rows,
            "uncompressed_jsonl_sha256": self.raw_hash.hexdigest(),
            "gzip_sha256": sha256_file(self.path),
        }

    def abort(self) -> None:
        if not self.closed:
            try:
                self.handle.close()
            finally:
                self.binary_handle.close()
                self.tmp.unlink(missing_ok=True)
                self.closed = True


def read_gzip_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt") as handle:
        for line in handle:
            yield json.loads(line)


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text())
    if manifest.get("manifest_sha256") != payload_sha256(manifest):
        raise CensusError("canonical source manifest hash verification failed")
    if manifest.get("status") != "CANONICAL_NATIVE_MBO_OBJECT_MANIFEST_FROZEN_AND_S3_VALIDATED":
        raise CensusError("canonical source manifest is not frozen/S3-validated")
    if manifest.get("selected_interval_count") != 61:
        raise CensusError("canonical source interval count is not 61")
    if manifest.get("prefix_wide_enumeration_used") is not False:
        raise CensusError("canonical source claims prefix-wide enumeration")
    return manifest


def material_hashes() -> dict[str, str]:
    paths = (
        "research/ng_exhaustion_mbo_5y_step1_census_20260822.py",
        "research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py",
        "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py",
        "research/ng_exhaustion_chain_canonical_table_20260817.py",
        "research/ng_exhaustion_chain_phase1_discovery_20260817.py",
        "research/ng_exhaustion_chain_phase1_structural_54w_20260817.py",
        "research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json",
        "research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json",
        "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json",
        "research/ng_exhaustion_mbo_5y_canonical_manifest_20260822.py",
    )
    return sha256_paths(paths)


class Heartbeat:
    def __init__(
        self,
        path: Path,
        base: dict[str, Any],
        interval_s: int = HEARTBEAT_SECONDS,
        on_write: Any | None = None,
    ) -> None:
        self.path = path
        self.base = dict(base)
        self.interval_s = int(interval_s)
        self.started = time.time()
        self.last = 0.0
        self.on_write = on_write

    def write(self, *, force: bool = False, **progress: Any) -> None:
        now = time.time()
        if not force and now - self.last < self.interval_s:
            return
        receipt = {
            **self.base,
            **progress,
            "heartbeat_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "elapsed_seconds": round(now - self.started, 3),
            "scientific_outcome_mutated_by_heartbeat": False,
        }
        atomic_json(self.path, receipt)
        if self.on_write is not None:
            self.on_write(self.path)
        self.last = now


class SecondAggregator:
    """Aggregate native full-state envelopes to deterministic event-time seconds."""

    def __init__(
        self,
        heartbeat: Heartbeat | None = None,
        emit: Any | None = None,
        reorder_tolerance_s: int = 60,
        source_provenance: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.seconds: dict[int, dict[str, Any]] = {}
        self.groups = 0
        self.heartbeat = heartbeat
        self.emit = emit
        self.reorder_tolerance_s = int(reorder_tolerance_s)
        self.max_second: int | None = None
        self.emitted_seconds = 0
        self.source_provenance = source_provenance or {}

    @staticmethod
    def _row(sec: int) -> dict[str, Any]:
        return {
            "epoch_second": sec,
            "legacy_rows": 0,
            "legacy_buy_qty": 0.0,
            "legacy_sell_qty": 0.0,
            "native_buy_qty": 0.0,
            "native_sell_qty": 0.0,
            "trade_count": 0,
            "last_trade_price": None,
            "book_imbalance_sum": 0.0,
            "book_imbalance_n": 0,
            "last_ts_recv_ns": 0,
            "last_raw_symbol": None,
            "last_instrument_id": None,
            "source_dbn_object": None,
            "source_dbn_key": None,
            "source_dbn_sha256": None,
            "source_interval": None,
            "native_segment_job_id": None,
            "canonical_interval_job_id": None,
            "source_requested_symbol": None,
            "raw_contract_resolution": None,
            "source_selection_reason": None,
            "native_state": None,
            "integrity": {},
        }

    def consume(self, envelope: dict[str, Any], legacy: list[dict[str, Any]]) -> None:
        frame = envelope["compact_event_frame"]
        sec = int(int(frame["ts_event_ns"]) // 1_000_000_000)
        if self.max_second is None or sec > self.max_second:
            self.max_second = sec
            self._flush_before(sec - self.reorder_tolerance_s)
        elif sec < self.max_second - self.reorder_tolerance_s:
            raise CensusError(
                f"source event-time order exceeded {self.reorder_tolerance_s}s tolerance: "
                f"second={sec} watermark={self.max_second}"
            )
        row = self.seconds.setdefault(sec, self._row(sec))
        row["last_ts_recv_ns"] = max(row["last_ts_recv_ns"], int(frame["ts_recv_ns"]))
        row["last_raw_symbol"] = frame.get("raw_symbol") or row["last_raw_symbol"]
        row["last_instrument_id"] = frame.get("instrument_id")
        raw_actions = frame.get("raw_actions", [])
        if raw_actions:
            last = raw_actions[-1]
            row["source_dbn_object"] = last.get("source_dbn_object")
            row["source_dbn_sha256"] = last.get("source_dbn_sha256")
            source = self.source_provenance.get(str(last.get("source_dbn_object")), {})
            row["source_dbn_key"] = source.get("key")
            row["source_interval"] = source.get("interval")
            row["native_segment_job_id"] = source.get("native_segment_job_id")
            row["canonical_interval_job_id"] = source.get("canonical_interval_job_id")
            row["source_requested_symbol"] = source.get("requested_symbol")
            row["raw_contract_resolution"] = source.get("raw_contract_resolution")
            row["source_selection_reason"] = source.get("selection_reason")

        for legacy_row in legacy:
            row["legacy_rows"] += 1
            bid_size = sum(float(legacy_row.get(f"bid_sz_{i:02d}", 0) or 0) for i in range(10))
            ask_size = sum(float(legacy_row.get(f"ask_sz_{i:02d}", 0) or 0) for i in range(10))
            total = bid_size + ask_size
            if total > 0:
                row["book_imbalance_sum"] += (bid_size - ask_size) / total
                row["book_imbalance_n"] += 1
            if legacy_row.get("action") != "T":
                continue
            price = float(legacy_row.get("price") or 0)
            size = float(legacy_row.get("size") or 0)
            bid = float(legacy_row.get("bid_px_00") or 0)
            ask = float(legacy_row.get("ask_px_00") or 0)
            if price > 0:
                row["last_trade_price"] = price
                row["trade_count"] += 1
            if price > 0 and size > 0 and bid > 0 and ask >= bid:
                mid = 0.5 * (bid + ask)
                if price > mid:
                    row["legacy_buy_qty"] += size
                elif price < mid:
                    row["legacy_sell_qty"] += size

        for raw in raw_actions:
            if raw.get("action") != "T":
                continue
            size = max(0.0, float(raw.get("size") or 0))
            if raw.get("side") == "B":
                row["native_buy_qty"] += size
            elif raw.get("side") == "A":
                row["native_sell_qty"] += size

        book = frame["book"]
        row["native_state"] = {
            "spread": book.get("spread"),
            "depth_imbalance_full": book.get("depth_imbalance_full"),
            "bid_depth_full": book.get("bid_depth_full"),
            "ask_depth_full": book.get("ask_depth_full"),
            "bid_order_count_full": book.get("bid_order_count_full"),
            "ask_order_count_full": book.get("ask_order_count_full"),
            "bid_price_level_count_full": book.get("bid_price_level_count_full"),
            "ask_price_level_count_full": book.get("ask_price_level_count_full"),
            "activity_20": frame.get("activity", {}).get("20"),
            "fifo_priority_reconstructed": True,
            "full_depth_exposed_in_process": bool(envelope.get("full_depth_exposed")),
        }
        row["integrity"] = dict(frame.get("integrity") or {})
        self.groups += 1
        if self.heartbeat:
            self.heartbeat.write(
                phase="SEGMENT_REPLAY",
                completed_event_groups=self.groups,
                aggregated_seconds=self.emitted_seconds + len(self.seconds),
            )

    def _flush_before(self, exclusive: int) -> None:
        if self.emit is None:
            return
        for sec in sorted(x for x in self.seconds if x < exclusive):
            self.emit(self.seconds.pop(sec))
            self.emitted_seconds += 1

    def finish(self) -> None:
        if self.emit is None:
            return
        for sec in sorted(self.seconds):
            self.emit(self.seconds[sec])
            self.emitted_seconds += 1
        self.seconds.clear()


def _object_dates_for_weeks(weeks: Iterable[str]) -> set[str]:
    dates = set()
    for week in weeks:
        sunday = dt.datetime.strptime(week, "%Y%m%d").date()
        dates.update(frozen_detector.ymds(sunday + dt.timedelta(days=offset)) for offset in range(7))
    return dates


def _dbn_object_date(obj: dict[str, Any]) -> str:
    name = Path(str(obj["key"])).name
    prefix = "glbx-mdp3-"
    value = name[len(prefix):len(prefix) + 8] if name.startswith(prefix) else ""
    if len(value) != 8 or not value.isdigit():
        raise CensusError(f"canonical DBN object lacks exact YYYYMMDD identity: {obj['key']}")
    return value


def _segment_objects(
    manifest: dict[str, Any],
    segment: str,
    object_dates: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows = [x for x in manifest["canonical_dbn_objects"] if x["segment"] == segment]
    if object_dates is not None:
        rows = [x for x in rows if _dbn_object_date(x) in object_dates]
    if not rows:
        raise CensusError(f"segment/object-date selection empty in canonical source manifest: {segment}")
    return rows


def _segment_source_scope(
    manifest: dict[str, Any],
    segment: str,
    object_dates: set[str] | None,
) -> dict[str, Any]:
    objects = _segment_objects(manifest, segment, object_dates)
    return {
        "mode": "FULL_CANONICAL_SEGMENT" if object_dates is None else "REVEALED_OVERLAP_DAILY_OBJECTS",
        "requested_object_dates": None if object_dates is None else sorted(object_dates),
        "selected_object_dates": [_dbn_object_date(obj) for obj in objects],
        "selected_object_count": len(objects),
        "selected_total_bytes": sum(int(obj["bytes"]) for obj in objects),
    }


def _local_object_path(stage_dir: Path, manifest: dict[str, Any], obj: dict[str, Any]) -> Path:
    prefix = manifest["prefix"]
    key = obj["key"]
    if not key.startswith(prefix):
        raise CensusError(f"object outside frozen prefix: {key}")
    return stage_dir.joinpath(*Path(key[len(prefix):]).parts)


def _resumable_segment_receipt(
    manifest: dict[str, Any],
    segment: str,
    out_dir: Path,
    engine: dict[str, str],
    source_scope: dict[str, Any],
) -> dict[str, Any] | None:
    seconds_path = out_dir / f"{segment}.seconds.jsonl.gz"
    receipt_path = out_dir / f"{segment}.receipt.json"
    if not receipt_path.exists() or not seconds_path.exists():
        return None
    prior = json.loads(receipt_path.read_text())
    identity = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1",
        "revision": REVISION,
        "segment": segment,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_scope": source_scope,
        "engine_hashes": engine,
        "ruleset_sha256": ruleset_sha256(),
    }
    body = dict(prior)
    claimed = body.pop("receipt_sha256", None)
    if (
        prior.get("status") == "SEGMENT_COMPLETE"
        and all(prior.get(k) == v for k, v in identity.items())
        and prior.get("seconds_output", {}).get("gzip_sha256") == sha256_file(seconds_path)
        and claimed == sha256_json(body)
    ):
        return prior
    return None


def process_segment(
    manifest_path: str | Path,
    segment: str,
    stage_dir: str | Path,
    out_dir: str | Path,
    *,
    object_dates: set[str] | None = None,
    heartbeat_seconds: int = HEARTBEAT_SECONDS,
    heartbeat_on_write: Any | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    stage = Path(stage_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seconds_path = out / f"{segment}.seconds.jsonl.gz"
    receipt_path = out / f"{segment}.receipt.json"
    engine = material_hashes()
    objects = _segment_objects(manifest, segment, object_dates)
    source_scope = _segment_source_scope(manifest, segment, object_dates)
    identity = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1",
        "revision": REVISION,
        "segment": segment,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_scope": source_scope,
        "engine_hashes": engine,
        "ruleset_sha256": ruleset_sha256(),
    }
    prior = _resumable_segment_receipt(manifest, segment, out, engine, source_scope)
    if prior is not None:
        return {**prior, "resumed_without_recompute": True}

    paths = []
    source_provenance = {}
    for obj in objects:
        path = _local_object_path(stage, manifest, obj)
        if not path.is_file() or path.stat().st_size != int(obj["bytes"]):
            raise CensusError(f"staged source missing/size drift: {path}")
        if sha256_file(path) != obj["sha256"]:
            raise CensusError(f"staged source SHA-256 drift: {path}")
        paths.append(str(path))
        source_provenance[str(path)] = {
            k: obj.get(k) for k in (
                "key", "interval", "native_segment_job_id", "canonical_interval_job_id",
                "requested_symbol", "selection_reason",
                "raw_contract_resolution",
            )
        }

    heartbeat = Heartbeat(
        out / f"{segment}.heartbeat.json",
        {**identity, "status": "RUNNING", "source_object_count": len(objects)},
        heartbeat_seconds,
        heartbeat_on_write,
    )
    heartbeat.write(force=True, phase="SOURCE_HASHES_VERIFIED", verified_objects=len(objects))
    writer = DeterministicGzipJsonlWriter(seconds_path)
    aggregator = SecondAggregator(
        heartbeat,
        emit=writer.write,
        source_provenance=source_provenance,
    )
    try:
        replay = replay_dbn_files(
            paths,
            aggregator.consume,
            materialize_full_state=False,
        )
        aggregator.finish()
        seconds = writer.close()
    except Exception:
        writer.abort()
        raise
    receipt = {
        **identity,
        "status": "SEGMENT_COMPLETE",
        "source_object_count": len(objects),
        "source_objects": [{k: x[k] for k in ("key", "bytes", "sha256", "native_segment_job_id")} for x in objects],
        "replay_summary": replay,
        "seconds_output": seconds,
        "case_retention_policy": RULESET,
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    atomic_json(receipt_path, receipt)
    heartbeat.write(force=True, phase="SEGMENT_COMPLETE", receipt_sha256=receipt["receipt_sha256"])
    return receipt


def week_sunday(epoch_second: int) -> dt.date:
    day = dt.datetime.fromtimestamp(epoch_second, tz=dt.timezone.utc).date()
    return frozen_detector.sunday_of(day)


def _native_label(state: dict[str, Any] | None, polarity: int) -> str:
    state = state or {}
    imbalance = state.get("depth_imbalance_full")
    orders = int(state.get("bid_order_count_full") or 0) + int(state.get("ask_order_count_full") or 0)
    if imbalance is None or not math.isfinite(float(imbalance)):
        depth = "DEPTH_UNKNOWN"
    elif float(imbalance) > 0.20:
        depth = "DEPTH_BID_DOMINANT"
    elif float(imbalance) < -0.20:
        depth = "DEPTH_ASK_DOMINANT"
    else:
        depth = "DEPTH_BALANCED"
    density = "QUEUE_DENSE" if orders >= 100 else "QUEUE_SPARSE"
    flow = "FLOW_POSITIVE" if polarity > 0 else "FLOW_NEGATIVE"
    return f"{NATIVE_TAXONOMY}|{flow}|{depth}|{density}"


def build_week_stream(rows: list[dict[str, Any]], signal: str) -> dict[str, Any]:
    if not rows:
        raise CensusError("cannot build week stream from no seconds")
    sunday = week_sunday(int(rows[0]["epoch_second"]))
    n = 6 * frozen_detector.DAY_SECONDS
    buy = [0.0] * n
    sell = [0.0] * n
    raw_price = [float("nan")] * n
    bsum = [0.0] * n
    bn = [0] * n
    blast = [float("nan")] * n
    actual = []
    seconds_by_idx = {}
    rows_seen = trades = classified = 0
    source_days = set()
    for row in rows:
        sec = int(row["epoch_second"])
        current_sunday = week_sunday(sec)
        if current_sunday != sunday:
            raise CensusError("mixed weeks passed to build_week_stream")
        now = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc)
        day_index = (now.date() - sunday).days
        if not 0 <= day_index < 6:
            continue
        idx = day_index * frozen_detector.DAY_SECONDS + now.hour * 3600 + now.minute * 60 + now.second
        seconds_by_idx[idx] = row
        source_days.add(now.date())
        rows_seen += int(row.get("legacy_rows", 0))
        bsum[idx] += float(row.get("book_imbalance_sum", 0))
        bn[idx] += int(row.get("book_imbalance_n", 0))
        if int(row.get("book_imbalance_n", 0)):
            blast[idx] = float(row["book_imbalance_sum"]) / int(row["book_imbalance_n"])
        price = row.get("last_trade_price")
        if price is not None and float(price) > 0:
            raw_price[idx] = float(price)
            actual.append(idx)
            trades += int(row.get("trade_count", 0))
        if signal == "legacy":
            b = float(row.get("legacy_buy_qty", 0))
            s = float(row.get("legacy_sell_qty", 0))
        elif signal == "native":
            b = float(row.get("native_buy_qty", 0))
            s = float(row.get("native_sell_qty", 0))
        else:
            raise ValueError(signal)
        buy[idx] += b
        sell[idx] += s
        classified += int(b + s > 0)
    if not actual:
        raise CensusError(f"week {sunday} contains no trades")
    first_trade, last_trade = min(actual), max(actual)
    price = [float("nan")] * n
    book = [float("nan")] * n
    last_price = last_book = float("nan")
    for i in range(n):
        if frozen_detector.finite(raw_price[i]):
            last_price = raw_price[i]
        price[i] = last_price
        if frozen_detector.finite(blast[i]):
            last_book = blast[i]
        book[i] = (bsum[i] / bn[i]) if bn[i] else last_book
    cb = [0.0] * (n + 1)
    cs = [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + buy[i]
        cs[i + 1] = cs[i] + sell[i]
    roll20 = [float("nan")] * n
    for i in range(n):
        lo = max(0, i - frozen_detector.ROLL + 1)
        b = cb[i + 1] - cb[lo]
        s = cs[i + 1] - cs[lo]
        if b + s > 0:
            roll20[i] = (b - s) / (b + s)
    required_days = sorted(source_days)
    thresholds = {}
    for day in required_days:
        di = (day - sunday).days
        vals = [
            abs(x) for x in roll20[di * frozen_detector.DAY_SECONDS:(di + 1) * frozen_detector.DAY_SECONDS]
            if frozen_detector.finite(x)
        ]
        thresholds[frozen_detector.ymds(day)] = frozen_detector.quantile(vals, frozen_detector.PEAK_Q)
    return {
        "week_sunday": sunday,
        "first_date": sunday,
        "required_days": [frozen_detector.ymds(x) for x in required_days],
        "buy": buy,
        "sell": sell,
        "price": price,
        "book": book,
        "roll20": roll20,
        "first_trade_idx": first_trade,
        "last_trade_idx": last_trade,
        "day_thresholds": thresholds,
        "rows": rows_seen,
        "trades": trades,
        "classified": classified,
        "midpoint_skipped": None,
        "invalid_trade": None,
        "seconds_by_idx": seconds_by_idx,
        "source_boundary_censored": len(required_days) != 6,
    }


def detect_events_for_week(
    rows: list[dict[str, Any]],
    view: str,
    pre_classifier: Any,
    a_classifier: Any,
) -> list[dict[str, Any]]:
    signal = "legacy" if view == "LEGACY_CONTROL" else "native"
    stream = build_week_stream(rows, signal)
    events, _ = frozen_detector.event_rows_for_week(stream, pre_classifier, a_classifier)
    frozen_detector.attach_links(events)
    for event in events:
        idx = int(event["t0_idx"])
        sec = stream["seconds_by_idx"].get(idx, {})
        event["census_view"] = view
        event["source_boundary_censored"] = stream["source_boundary_censored"]
        event["source_provenance"] = {
            "source_dbn_key": sec.get("source_dbn_key"),
            "staged_source_dbn_object": sec.get("source_dbn_object"),
            "source_dbn_sha256": sec.get("source_dbn_sha256"),
            "source_interval": sec.get("source_interval"),
            "native_segment_job_id": sec.get("native_segment_job_id"),
            "canonical_interval_job_id": sec.get("canonical_interval_job_id"),
            "requested_symbol": sec.get("source_requested_symbol"),
            "raw_contract_resolution": sec.get("raw_contract_resolution"),
            "selection_reason": sec.get("source_selection_reason"),
            "raw_symbol": sec.get("last_raw_symbol"),
            "instrument_id": sec.get("last_instrument_id"),
            "event_known_by_ts_recv_ns": sec.get("last_ts_recv_ns"),
            "contract_resolution_status": (
                "RESOLVED_FROM_DBN_METADATA" if sec.get("last_raw_symbol")
                else "UNRESOLVED_RETAINED"
            ),
        }
        if view == "V4_NATIVE_FULL":
            event["event_id"] = "V4N1|" + event["event_id"]
            event["native_structure"] = {
                "taxonomy": NATIVE_TAXONOMY,
                "label": _native_label(sec.get("native_state"), int(event["polarity"])),
                "state_at_t0": sec.get("native_state"),
                "integrity_at_t0": sec.get("integrity", {}),
            }
    if view == "V4_NATIVE_FULL":
        frozen_detector.attach_links(events)
    return events


def _match_events(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]], tolerance_s: int = 1
) -> tuple[list[tuple[dict[str, Any], dict[str, Any], int]], list[dict[str, Any]], list[dict[str, Any]]]:
    buckets: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for j, row in enumerate(actual):
        buckets[(str(row["week_sunday"]), int(row["polarity"]), int(row["t0_idx"]))].append(j)
    available = set(range(len(actual)))
    matches = []
    missing = []
    for left in expected:
        candidates = []
        week = str(left["week_sunday"])
        polarity = int(left["polarity"])
        t0 = int(left["t0_idx"])
        for candidate_t0 in range(t0 - tolerance_s, t0 + tolerance_s + 1):
            for j in buckets.get((week, polarity, candidate_t0), ()):
                if j in available:
                    candidates.append((abs(t0 - candidate_t0), str(actual[j]["event_id"]), j))
        if not candidates:
            missing.append(left)
            continue
        delta, _, j = min(candidates)
        available.remove(j)
        matches.append((left, actual[j], delta))
    extras = [actual[j] for j in sorted(available)]
    return matches, missing, extras


def compare_lineage(
    frozen_lineage: list[dict[str, Any]], actual_lineage: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frozen = {x["origin_event_id"]: x for x in frozen_lineage}
    actual = {x["origin_event_id"]: x for x in actual_lineage}
    common = sorted(set(frozen) & set(actual))
    depth_agree = 0
    sign_agree = 0
    sign_cells = 0
    mismatches = []
    for event_id in common:
        left = frozen[event_id]
        right = actual[event_id]
        left_depth = int(left.get("consecutive_all_models_positive_depth_candidate", 0))
        right_depth = int(right.get("consecutive_all_models_positive_depth_candidate", 0))
        if left_depth == right_depth:
            depth_agree += 1
        else:
            mismatches.append({
                "kind": "LINEAGE_DEPTH_DISAGREEMENT",
                "origin_event_id": event_id,
                "frozen_depth": left_depth,
                "legacy_control_depth": right_depth,
            })
        for model in ("ridge", "knn", "extra_trees"):
            for depth in ("1", "2", "3"):
                lv = (left.get("incremental_gain", {}).get(model, {}) or {}).get(depth)
                rv = (right.get("incremental_gain", {}).get(model, {}) or {}).get(depth)
                if lv is None or rv is None:
                    continue
                sign_cells += 1
                if (float(lv) > 0) == (float(rv) > 0):
                    sign_agree += 1
                else:
                    mismatches.append({
                        "kind": "LINEAGE_GAIN_SIGN_DISAGREEMENT",
                        "origin_event_id": event_id,
                        "model": model,
                        "depth": int(depth),
                        "frozen_gain": float(lv),
                        "legacy_control_gain": float(rv),
                    })
    depth_rate = depth_agree / len(common) if common else 0.0
    sign_rate = sign_agree / sign_cells if sign_cells else 0.0
    result = {
        "frozen_origin_count": len(frozen),
        "legacy_control_origin_count": len(actual),
        "common_origin_count": len(common),
        "frozen_only_origin_count": len(set(frozen) - set(actual)),
        "legacy_control_only_origin_count": len(set(actual) - set(frozen)),
        "depth_agreement_on_common_origins": depth_rate,
        "sign_agreement_on_comparable_cells": sign_rate,
        "comparable_sign_cell_count": sign_cells,
        "retained_lineage_mismatch_count": len(mismatches),
    }
    return result, mismatches


def derive_pilot_lineage(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    byweek = _byweek_from_events(events)
    if sorted(byweek) != list(OVERLAP_WEEKS):
        raise CensusError(f"revealed overlap week drift: {sorted(byweek)}")
    _, primary_gains = frozen_discovery.analyze_view(byweek, "full")
    rows = []
    models = ("ridge", "knn", "extra_trees")
    for week in sorted(byweek):
        n = len(byweek[week])
        for i, event_row in enumerate(byweek[week]):
            rec = {
                "origin_event_id": event_row["event_id"],
                "week_sunday": week,
                "sequence_index": i,
                "incremental_gain": {},
                "all_models_positive": {},
            }
            for model in models:
                rec["incremental_gain"][model] = {}
                for depth in (1, 2, 3):
                    target = i + depth
                    value = None if target >= n else primary_gains[model][week][depth][target]
                    rec["incremental_gain"][model][str(depth)] = (
                        None if value is None or not frozen_discovery.finite(value) else float(value)
                    )
            for depth in (1, 2, 3):
                values = [rec["incremental_gain"][m][str(depth)] for m in models]
                rec["all_models_positive"][str(depth)] = (
                    None if any(x is None for x in values) else bool(all(x > 0 for x in values))
                )
            candidate = 0
            for depth in (1, 2, 3):
                if rec["all_models_positive"][str(depth)] is True:
                    candidate = depth
                else:
                    break
            rec["consecutive_all_models_positive_depth_candidate"] = candidate
            rows.append(rec)
    return rows


def legacy_overlap_receipt(
    frozen_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    frozen_lineage: list[dict[str, Any]] | None = None,
    actual_lineage: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected = [x for x in frozen_rows if x["week_sunday"] in OVERLAP_WEEKS]
    actual = [x for x in actual_rows if x["week_sunday"] in OVERLAP_WEEKS]
    matches, missing, extras = _match_events(expected, actual)
    family_agree = sum(a.get("family") == b.get("family") for a, b, _ in matches)
    endpoint_comparable = 0
    endpoint_agree = 0
    mismatches = []
    for left, right, delta in matches:
        reasons = []
        if delta:
            reasons.append("T0_WITHIN_TOLERANCE_NOT_EXACT")
        if left.get("family") != right.get("family"):
            reasons.append("FAMILY_DISAGREEMENT")
        lc = (left.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")
        rc = (right.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")
        if lc is not None and rc is not None:
            endpoint_comparable += 1
            if abs(int(lc) - int(rc)) <= 1:
                endpoint_agree += 1
            else:
                reasons.append("ENDPOINT_CONFIRMATION_DISAGREEMENT")
        elif lc != rc:
            reasons.append("ENDPOINT_CENSORSHIP_DISAGREEMENT")
        if reasons:
            mismatches.append({
                "kind": "MATCHED_EVENT_FIELD_MISMATCH",
                "expected_event_id": left["event_id"],
                "actual_event_id": right["event_id"],
                "reasons": reasons,
            })
    mismatches.extend({"kind": "FROZEN_ONLY", "event_id": x["event_id"]} for x in missing)
    mismatches.extend({"kind": "LEGACY_CONTROL_ONLY", "event_id": x["event_id"]} for x in extras)
    n_expected = len(expected)
    n_actual = len(actual)
    recall = len(matches) / n_expected if n_expected else 0.0
    precision = len(matches) / n_actual if n_actual else 0.0
    count_delta = abs(n_actual - n_expected) / n_expected if n_expected else float("inf")
    family_rate = family_agree / len(matches) if matches else 0.0
    endpoint_rate = endpoint_agree / endpoint_comparable if endpoint_comparable else 0.0
    gates = {
        "event_recall": recall >= OVERLAP_POLICY["minimum_event_recall"],
        "event_precision": precision >= OVERLAP_POLICY["minimum_event_precision"],
        "relative_event_count_delta": count_delta <= OVERLAP_POLICY["maximum_relative_event_count_delta"],
        "family_agreement": family_rate >= OVERLAP_POLICY["minimum_family_agreement_on_matches"],
        "endpoint_confirmation_agreement": endpoint_rate >= OVERLAP_POLICY["minimum_endpoint_confirmation_agreement_within_1s"],
    }
    lineage_result = None
    if frozen_lineage is not None or actual_lineage is not None:
        if frozen_lineage is None or actual_lineage is None:
            raise CensusError("both frozen and actual lineage are required for lineage equivalence")
        lineage_result, lineage_mismatches = compare_lineage(frozen_lineage, actual_lineage)
        mismatches.extend(lineage_mismatches)
        gates["lineage_depth_agreement"] = (
            lineage_result["depth_agreement_on_common_origins"]
            >= OVERLAP_POLICY["minimum_lineage_depth_agreement_on_common_origins"]
        )
        gates["lineage_sign_agreement"] = (
            lineage_result["sign_agreement_on_comparable_cells"]
            >= OVERLAP_POLICY["minimum_lineage_sign_agreement_on_comparable_cells"]
        )
    receipt = {
        "schema": "NG_EXHAUSTION_LEGACY_CONTROL_OVERLAP_EQUIVALENCE_V1_20260822",
        "status": "PASS" if all(gates.values()) else "FAIL_CLOSED",
        "policy": OVERLAP_POLICY,
        "frozen_event_count": n_expected,
        "legacy_control_event_count": n_actual,
        "matched_event_count": len(matches),
        "frozen_only_count": len(missing),
        "legacy_control_only_count": len(extras),
        "event_recall": recall,
        "event_precision": precision,
        "relative_event_count_delta": count_delta,
        "family_agreement_on_matches": family_rate,
        "endpoint_confirmation_agreement_within_1s": endpoint_rate,
        "lineage_equivalence": lineage_result,
        "retained_mismatch_count": len(mismatches),
        "gates": gates,
        "frozen_detector_mutated": False,
        "mismatch_policy": RULESET,
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    return receipt, mismatches


def expanding_folds(weeks: list[str]) -> list[tuple[list[str], list[str], str]]:
    if len(weeks) <= INITIAL_TRAIN_WEEKS:
        return []
    folds = []
    start = INITIAL_TRAIN_WEEKS
    ordinal = 1
    while start < len(weeks):
        stop = min(len(weeks), start + TEST_BLOCK_WEEKS)
        folds.append((weeks[:start], weeks[start:stop], f"expanding_{ordinal:02d}"))
        start = stop
        ordinal += 1
    return folds


def _byweek_from_events(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    byweek = defaultdict(list)
    for row in events:
        byweek[row["week_sunday"]].append({
            "event_id": row["event_id"],
            "week_sunday": row["week_sunday"],
            "sequence_index": int(row["sequence_index"]),
            "next_same": row["link"].get("next_same_polarity"),
            "post": row["outcome"].get("post_endpoint_price"),
        })
    for rows in byweek.values():
        rows.sort(key=lambda x: x["sequence_index"])
    return dict(byweek)


def compact_lineage_input(event: dict[str, Any]) -> dict[str, Any]:
    """Keep exact frozen behavior inputs plus registry fields, without full event bulk."""
    behavior = frozen_discovery.behavior_vector(
        {
            "next_same": event["link"].get("next_same_polarity"),
            "post": event["outcome"].get("post_endpoint_price"),
        },
        "full",
    )
    return {
        "event_id": event["event_id"],
        "week_sunday": event["week_sunday"],
        "sequence_index": int(event["sequence_index"]),
        "t0_idx": int(event["t0_idx"]),
        "polarity": int(event["polarity"]),
        "family": event.get("family"),
        "previous_event_id": event["link"].get("previous_event_id"),
        "next_event_id": event["link"].get("next_event_id"),
        "causal_confirmation_idx": (event.get("dynamic_endpoint") or {}).get("causal_confirmation_idx"),
        "behavior_vector_full": behavior,
        "source_boundary_censored": bool(event.get("source_boundary_censored")),
        "source_provenance": event.get("source_provenance"),
        "native_structure": event.get("native_structure"),
    }


def _load_lineage_inputs(
    path: str | Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, np.ndarray], dict[str, np.ndarray]]:
    byweek: dict[str, list[dict[str, Any]]] = defaultdict(list)
    vectors: dict[str, list[list[float]]] = defaultdict(list)
    for row in read_gzip_jsonl(path):
        week = str(row["week_sunday"])
        vectors[week].append(row.pop("behavior_vector_full"))
        byweek[week].append(row)
    arrays = {}
    valid = {}
    for week, rows in byweek.items():
        rows.sort(key=lambda x: int(x["sequence_index"]))
        if [int(x["sequence_index"]) for x in rows] != list(range(len(rows))):
            raise CensusError(f"non-contiguous event sequence in lineage input: {week}")
        array = np.asarray(vectors.pop(week), dtype=float)
        ok = np.all(np.isfinite(array), axis=1)
        transformed = array.copy()
        transformed[:, 1:] = np.arcsinh(transformed[:, 1:])
        arrays[week] = transformed
        valid[week] = ok
    return dict(byweek), arrays, valid


def lineage_population(
    lineage_input_path: str | Path,
    view: str,
    hashes: dict[str, str],
    population_path: str | Path,
    index_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    byweek, arrays, valid = _load_lineage_inputs(lineage_input_path)
    weeks = sorted(byweek)
    models = tuple(frozen_structural.MODELS)
    model_index = {model: i for i, model in enumerate(models)}
    gains = {
        week: np.full((len(byweek[week]), MAX_DEPTH, len(models)), np.nan, dtype=np.float64)
        for week in weeks
    }
    fold_records = []
    for train, test, fold_name in expanding_folds(weeks):
        fold_rec = {"fold": fold_name, "train_week_count": len(train), "test_weeks": test, "depth": {}}
        for depth in range(1, MAX_DEPTH + 1):
            fold_rec["depth"][str(depth)] = {}
            for model in models:
                result = frozen_structural.paired_depth(
                    model, train, test, byweek, arrays, valid, depth
                )
                if result is None:
                    fold_rec["depth"][str(depth)][model] = {"n": 0}
                    continue
                fold_rec["depth"][str(depth)][model] = {
                    k: v for k, v in result.items() if k not in ("meta", "gain")
                }
                for gain, (week, target_index, _event_id) in zip(result["gain"], result["meta"]):
                    gains[week][int(target_index), depth - 1, model_index[model]] = float(gain)
        fold_records.append(fold_rec)

    population_writer = DeterministicGzipJsonlWriter(Path(population_path))
    index_writer = DeterministicGzipJsonlWriter(Path(index_path))
    retained = Counter()
    try:
        for week in weeks:
            rows = byweek[week]
            week_gains = gains[week]
            for origin in rows:
                i = int(origin["sequence_index"])
                evidence = {}
                depth = 0
                unresolved_reasons = []
                for d in range(1, MAX_DEPTH + 1):
                    values = {}
                    for model in models:
                        value = (
                            float(week_gains[i + d, d - 1, model_index[model]])
                            if i + d < len(rows) else float("nan")
                        )
                        values[model] = value if math.isfinite(value) else None
                    evidence[str(d)] = values
                    if all(value is not None and value > 0 for value in values.values()):
                        depth = d
                        continue
                    if all(value is None for value in values.values()):
                        unresolved_reasons.append(f"D{d}_NOT_OOT_SCORED_OR_INVALID")
                    elif any(value is None for value in values.values()):
                        unresolved_reasons.append(f"D{d}_INCOMPLETE_MODEL_EVIDENCE")
                    break
                members = rows[i:min(len(rows), i + depth + 1)]
                if len(members) != depth + 1:
                    unresolved_reasons.append("WEEK_END_DESCENDANT_CENSORED")
                reset = rows[i + depth + 1] if i + depth + 1 < len(rows) else None
                causal_links = []
                for left, right in zip(members, members[1:]):
                    confirm = left.get("causal_confirmation_idx")
                    causal_links.append({
                        "predecessor_event_id": left["event_id"],
                        "successor_event_id": right["event_id"],
                        "predecessor_confirmation_idx": confirm,
                        "successor_t0_idx": right["t0_idx"],
                        "predecessor_information_known_before_successor": (
                            None if confirm is None else int(confirm) < int(right["t0_idx"])
                        ),
                    })
                elapsed = (
                    None if len(members) < 2
                    else int(members[-1]["t0_idx"]) - int(members[0]["t0_idx"])
                )
                chain_seed = f"{view}|{week}|{origin['event_id']}"
                chain_id = hashlib.sha256(chain_seed.encode()).hexdigest()
                integrity_reasons = list(unresolved_reasons)
                provenance = origin.get("source_provenance") or {}
                if not provenance.get("source_dbn_key") or not provenance.get("source_dbn_sha256"):
                    integrity_reasons.append("SOURCE_OBJECT_PROVENANCE_UNRESOLVED")
                if provenance.get("contract_resolution_status") != "RESOLVED_FROM_DBN_METADATA":
                    integrity_reasons.append("RAW_CONTRACT_UNRESOLVED_RETAINED")
                native_integrity = ((origin.get("native_structure") or {}).get("integrity_at_t0") or {})
                if native_integrity:
                    integrity_reasons.append("NATIVE_REPLAY_INTEGRITY_COUNTER_PRESENT")
                overall_unresolved = bool(integrity_reasons)
                row = {
                    "schema": "NG_EXHAUSTION_STEP1_POPULATION_CASE_V1_20260822",
                    "census_view": view,
                    "chain_id": chain_id,
                    "chain_origin_event_id": origin["event_id"],
                    "week_sunday": week,
                    "origin_sequence_index": i,
                    "ordered_member_event_ids": [x["event_id"] for x in members],
                    "ordered_ancestry": [x["event_id"] for x in members[:-1]],
                    "predecessor_event_id": origin.get("previous_event_id"),
                    "successor_event_id": origin.get("next_event_id"),
                    "realized_structural_depth": depth,
                    "legacy_d_label": f"D{depth}" if view == "LEGACY_CONTROL" else None,
                    "native_taxonomy_labels": (
                        [(x.get("native_structure") or {}).get("label") for x in members]
                        if view == "V4_NATIVE_FULL" else None
                    ),
                    "reset_event_id": None if reset is None else reset["event_id"],
                    "reset_boundary_status": "CENSORED_WEEK_END" if reset is None else "REALIZED_NEXT_EVENT",
                    "elapsed_time_seconds": elapsed,
                    "inherited_information_evidence": evidence,
                    "inherited_information_uncertainty": unresolved_reasons,
                    "causal_executable_availability": causal_links,
                    "censored": bool(reset is None or origin.get("source_boundary_censored")),
                    "unresolved": overall_unresolved,
                    "short_long_state": "UNDECLARED_STRUCTURAL_CENSUS_ONLY",
                    "source_provenance": provenance,
                    "adapter_revision": ADAPTER_REVISION,
                    "engine_hashes": hashes,
                    "ruleset_sha256": ruleset_sha256(),
                    "integrity_reasons": integrity_reasons,
                    "retention_policy": RULESET,
                }
                population_writer.write(row)
                index_writer.write({
                    "event_id": origin["event_id"],
                    "week_sunday": week,
                    "t0_idx": int(origin["t0_idx"]),
                    "polarity": int(origin["polarity"]),
                    "family": origin.get("family"),
                    "chain_id": chain_id,
                    "realized_structural_depth": depth,
                    "reset_event_id": None if reset is None else reset["event_id"],
                    "unresolved": overall_unresolved,
                })
                retained["all_cases"] += 1
                retained["unresolved" if overall_unresolved else "resolved"] += 1
                retained["censored" if row["censored"] else "uncensored"] += 1
        population_output = population_writer.close()
        index_output = index_writer.close()
    except Exception:
        population_writer.abort()
        index_writer.abort()
        raise
    event_count = sum(len(rows) for rows in byweek.values())
    if retained["all_cases"] != event_count:
        raise CensusError(f"case-retention invariant failed view={view}")
    summary = {
        "view": view,
        "event_count": event_count,
        "population_count": retained["all_cases"],
        "case_retention_exact": True,
        "depth_histogram": dict(sorted(Counter(
            int(row["realized_structural_depth"])
            for row in read_gzip_jsonl(index_path)
        ).items())),
        "retention_counts": dict(retained),
        "folds": fold_records,
        "frozen_lineage_binding": {
            "discovery_module": "research/ng_exhaustion_chain_phase1_discovery_20260817.py",
            "structural_module": "research/ng_exhaustion_chain_phase1_structural_54w_20260817.py",
            "models": list(frozen_structural.MODELS),
            "maximum_depth": MAX_DEPTH,
        },
    }
    return population_output, summary, index_output


def _group_rows_by_week(path: str | Path) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    current = None
    rows = []
    for row in read_gzip_jsonl(path):
        week = str(row["week_sunday"])
        if current is not None and week != current:
            yield current, rows
            rows = []
        current = week
        rows.append(row)
    if current is not None:
        yield current, rows


def build_crosswalk(
    legacy_index_path: str | Path,
    native_index_path: str | Path,
    output_path: str | Path,
    tolerance_s: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    legacy_iter = iter(_group_rows_by_week(legacy_index_path))
    native_iter = iter(_group_rows_by_week(native_index_path))
    legacy_group = next(legacy_iter, None)
    native_group = next(native_iter, None)
    writer = DeterministicGzipJsonlWriter(Path(output_path))
    counts = Counter()
    try:
        while legacy_group is not None or native_group is not None:
            candidates = [x[0] for x in (legacy_group, native_group) if x is not None]
            week = min(candidates)
            legacy = legacy_group[1] if legacy_group is not None and legacy_group[0] == week else []
            native = native_group[1] if native_group is not None and native_group[0] == week else []
            if legacy_group is not None and legacy_group[0] == week:
                legacy_group = next(legacy_iter, None)
            if native_group is not None and native_group[0] == week:
                native_group = next(native_iter, None)
            primary, _legacy_unmatched_primary, _native_unmatched_primary = _match_events(
                legacy, native, tolerance_s
            )
            counts["primary_matches"] += len(primary)
            primary_ids = {(x["event_id"], y["event_id"]) for x, y, _ in primary}
            native_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
            for j, row in enumerate(native):
                native_buckets[(int(row["polarity"]), int(row["t0_idx"]))].append(j)
            edges = []
            left_degree = Counter()
            right_degree = Counter()
            for i, left in enumerate(legacy):
                for t0 in range(int(left["t0_idx"]) - tolerance_s, int(left["t0_idx"]) + tolerance_s + 1):
                    for j in native_buckets.get((int(left["polarity"]), t0), ()):
                        edges.append((i, j, abs(int(left["t0_idx"]) - t0)))
                        left_degree[i] += 1
                        right_degree[j] += 1
            legacy_only = [row for i, row in enumerate(legacy) if left_degree[i] == 0]
            native_only = [row for j, row in enumerate(native) if right_degree[j] == 0]
            for i, j, delta in edges:
                left = legacy[i]
                right = native[j]
                if left_degree[i] > 1 and right_degree[j] > 1:
                    relationship = "COMPLEX_SPLIT_MERGE"
                elif left_degree[i] > 1:
                    relationship = "SPLIT"
                elif right_degree[j] > 1:
                    relationship = "MERGE"
                else:
                    relationship = "MATCH"
                reset_agreement = left["reset_event_id"] == (
                    None if right["reset_event_id"] is None
                    else str(right["reset_event_id"]).removeprefix("V4N1|")
                )
                depth_agreement = int(left["realized_structural_depth"]) == int(right["realized_structural_depth"])
                writer.write({
                    "status": relationship,
                    "primary_one_to_one_match": (left["event_id"], right["event_id"]) in primary_ids,
                    "legacy_event_id": left["event_id"],
                    "native_event_id": right["event_id"],
                    "t0_delta_seconds": delta,
                    "legacy_chain_id": left["chain_id"],
                    "native_chain_id": right["chain_id"],
                    "depth_agreement": depth_agreement,
                    "legacy_depth": left["realized_structural_depth"],
                    "native_depth": right["realized_structural_depth"],
                    "reset_agreement": reset_agreement,
                    "support_change": {
                        "legacy_unresolved": left["unresolved"],
                        "native_unresolved": right["unresolved"],
                    },
                    "source_provenance_reason": "SAME_CANONICAL_NATIVE_MBO_REPLAY_DIFFERENT_VIEW",
                })
                counts[relationship] += 1
                counts["depth_agreements" if depth_agreement else "depth_disagreements"] += 1
                counts["reset_agreements" if reset_agreement else "reset_disagreements"] += 1
            for row in legacy_only:
                writer.write({
                    "status": "LEGACY_CONTROL_ONLY",
                    "legacy_event_id": row["event_id"],
                    "native_event_id": None,
                    "source_provenance_reason": "VIEW_SPECIFIC_DETECTOR_EVENT",
                })
                counts["LEGACY_CONTROL_ONLY"] += 1
            for row in native_only:
                writer.write({
                    "status": "V4_NATIVE_FULL_ONLY",
                    "legacy_event_id": None,
                    "native_event_id": row["event_id"],
                    "source_provenance_reason": "VIEW_SPECIFIC_DETECTOR_EVENT",
                })
                counts["V4_NATIVE_FULL_ONLY"] += 1
        output = writer.close()
    except Exception:
        writer.abort()
        raise
    summary = {
        "schema": "NG_EXHAUSTION_STEP1_DUAL_CENSUS_CROSSWALK_V1_20260822",
        "primary_matches": counts["primary_matches"],
        "match_edges": counts["MATCH"],
        "split_edges": counts["SPLIT"],
        "merge_edges": counts["MERGE"],
        "complex_split_merge_edges": counts["COMPLEX_SPLIT_MERGE"],
        "legacy_control_only": counts["LEGACY_CONTROL_ONLY"],
        "v4_native_full_only": counts["V4_NATIVE_FULL_ONLY"],
        "depth_agreements": counts["depth_agreements"],
        "depth_disagreements": counts["depth_disagreements"],
        "reset_agreements": counts["reset_agreements"],
        "reset_disagreements": counts["reset_disagreements"],
        "splits_merges_policy": "COMPLETE_EVENT_MATCH_GRAPH_RETAINED; DETERMINISTIC_PRIMARY_EDGE_ANNOTATED; NO_CASE_DROPPED_OR_FORCED_INTO_LEGACY_LABEL",
        "retention_policy": RULESET,
    }
    return output, summary


def _segments_for_weeks(manifest: dict[str, Any], weeks_filter: set[str] | None) -> list[str]:
    if weeks_filter is None:
        return sorted({x["segment"] for x in manifest["canonical_dbn_objects"]})
    selected = set()
    for interval in manifest["selected_intervals"]:
        start = dt.date.fromisoformat(interval["interval"]["start"])
        end = dt.date.fromisoformat(interval["interval"]["end"])
        for week in weeks_filter:
            sunday = dt.datetime.strptime(week, "%Y%m%d").date()
            if start < sunday + dt.timedelta(days=6) and sunday < end:
                selected.update(x["segment"] for x in interval["native_manifests"])
    if not selected:
        raise CensusError(f"no canonical segments cover requested weeks: {sorted(weeks_filter)}")
    return sorted(selected)


def _verified_child_outputs(
    manifest: dict[str, Any],
    segment_dir: Path,
    segments: list[str],
    *,
    expected_engine_hashes: dict[str, str] | None = None,
    expected_source_scopes: dict[str, dict[str, Any]] | None = None,
    pinned_children: dict[str, dict[str, str]] | None = None,
) -> tuple[list[Path], list[str]]:
    paths = []
    receipt_hashes = []
    for segment in segments:
        receipt_path = segment_dir / f"{segment}.receipt.json"
        seconds_path = segment_dir / f"{segment}.seconds.jsonl.gz"
        if not receipt_path.exists() or not seconds_path.exists():
            raise CensusError(f"missing exact child segment output: {segment}")
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("status") != "SEGMENT_COMPLETE":
            raise CensusError(f"child segment not complete: {segment}")
        if receipt.get("segment") != segment:
            raise CensusError(f"child segment identity drift: {segment}")
        if receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]:
            raise CensusError(f"child source-manifest drift: {segment}")
        if receipt.get("ruleset_sha256") != ruleset_sha256():
            raise CensusError(f"child ruleset drift: {segment}")
        if expected_engine_hashes is not None and receipt.get("engine_hashes") != expected_engine_hashes:
            raise CensusError(f"child engine drift: {segment}")
        if expected_source_scopes is not None and receipt.get("source_scope") != expected_source_scopes[segment]:
            raise CensusError(f"child source-scope drift: {segment}")
        if receipt["seconds_output"]["gzip_sha256"] != sha256_file(seconds_path):
            raise CensusError(f"child seconds hash drift: {segment}")
        claimed = receipt.get("receipt_sha256")
        body = dict(receipt)
        body.pop("receipt_sha256", None)
        if claimed != sha256_json(body):
            raise CensusError(f"child receipt hash drift: {segment}")
        if pinned_children is not None:
            pin = pinned_children.get(segment)
            if pin is None:
                raise CensusError(f"child recovery pin missing: {segment}")
            if pin.get("receipt_sha256") != claimed:
                raise CensusError(f"child recovery receipt pin drift: {segment}")
            if pin.get("seconds_gzip_sha256") != receipt["seconds_output"]["gzip_sha256"]:
                raise CensusError(f"child recovery seconds pin drift: {segment}")
            if int(pin.get("seconds_rows", -1)) != int(receipt["seconds_output"].get("rows", -2)):
                raise CensusError(f"child recovery seconds row-count drift: {segment}")
        paths.append(seconds_path)
        receipt_hashes.append(claimed)
    return paths, receipt_hashes


def _segment_epoch_bounds(segment: str) -> tuple[int, int]:
    try:
        start_raw, end_raw = segment.split("_", 1)
        start = dt.datetime.strptime(start_raw, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
        end = dt.datetime.strptime(end_raw, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError) as exc:
        raise CensusError(f"invalid canonical segment identity: {segment}") from exc
    if end <= start:
        raise CensusError(f"non-positive canonical segment interval: {segment}")
    return int(start.timestamp()), int(end.timestamp())


def _iter_seconds_weeks(
    seconds_paths: list[Path],
    weeks_filter: set[str] | None,
    segments: list[str],
    boundary_audit: dict[str, Any],
) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    if len(seconds_paths) != len(segments):
        raise CensusError("child path/segment cardinality drift")
    current_week = None
    rows = []
    last_second = None
    boundary_audit.update({
        "policy": "CLIP_CHILD_SECONDS_TO_CANONICAL_SEGMENT_HALF_OPEN_INTERVAL",
        "segments": {},
        "excluded_out_of_interval_seconds": 0,
        "retention": "RAW_CHILD_OUTPUTS_AND_RECEIPTS_RETAIN_EXCLUDED_WARMUP_ROWS",
    })
    for path, segment in zip(seconds_paths, segments):
        start_second, end_second = _segment_epoch_bounds(segment)
        segment_last_second = None
        segment_audit = {
            "start_epoch_second_inclusive": start_second,
            "end_epoch_second_exclusive": end_second,
            "excluded_before_start": 0,
            "excluded_at_or_after_end": 0,
            "first_excluded_epoch_second": None,
            "last_excluded_epoch_second": None,
        }
        boundary_audit["segments"][segment] = segment_audit
        for row in read_gzip_jsonl(path):
            second = int(row["epoch_second"])
            if segment_last_second is not None and second <= segment_last_second:
                raise CensusError(
                    f"child segment non-increasing/duplicate second: {segment} {second} after {segment_last_second}"
                )
            segment_last_second = second
            if second < start_second or second >= end_second:
                if second < start_second:
                    segment_audit["excluded_before_start"] += 1
                else:
                    segment_audit["excluded_at_or_after_end"] += 1
                if segment_audit["first_excluded_epoch_second"] is None:
                    segment_audit["first_excluded_epoch_second"] = second
                segment_audit["last_excluded_epoch_second"] = second
                boundary_audit["excluded_out_of_interval_seconds"] += 1
                continue
            if last_second is not None and second <= last_second:
                raise CensusError(
                    f"population reconciliation in-bound non-increasing/duplicate second: {second} after {last_second}"
                )
            last_second = second
            week = frozen_detector.ymds(week_sunday(second))
            if weeks_filter is not None and week not in weeks_filter:
                continue
            if current_week is not None and week != current_week:
                yield current_week, rows
                rows = []
            current_week = week
            rows.append(row)
    if current_week is not None:
        yield current_week, rows


def reconcile(
    manifest_path: str | Path,
    segment_dir: str | Path,
    out_dir: str | Path,
    frozen_overlap_table: str | Path,
    frozen_overlap_lineage: str | Path,
    *,
    weeks_filter: set[str] | None = None,
    child_recovery_contract: str | Path | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    segment_dir = Path(segment_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hashes = material_hashes()
    segments = _segments_for_weeks(manifest, weeks_filter)
    object_dates = _object_dates_for_weeks(weeks_filter) if weeks_filter is not None else None
    expected_source_scopes = {
        segment: _segment_source_scope(manifest, segment, object_dates) for segment in segments
    }
    recovery = None
    expected_engine_hashes = hashes
    pinned_children = None
    if child_recovery_contract is not None:
        recovery_path = Path(child_recovery_contract)
        recovery = json.loads(recovery_path.read_text())
        if recovery.get("schema") != "NG_EXHAUSTION_MBO_5Y_STEP1_PREFLIGHT_CHILD_RECOVERY_V1_20260823":
            raise CensusError("unknown child recovery contract schema")
        if recovery.get("source_manifest_sha256") != manifest["manifest_sha256"]:
            raise CensusError("child recovery source-manifest drift")
        if recovery.get("ruleset_sha256") != ruleset_sha256():
            raise CensusError("child recovery ruleset drift")
        if set(recovery.get("children", {})) != set(segments):
            raise CensusError("child recovery segment set drift")
        expected_engine_hashes = recovery.get("producer_engine_hashes")
        if not isinstance(expected_engine_hashes, dict) or not expected_engine_hashes:
            raise CensusError("child recovery producer engine hashes absent")
        pinned_children = recovery["children"]
        recovery = {
            "contract_sha256": sha256_file(recovery_path),
            "parent_candidate_commit": recovery["parent_candidate_commit"],
            "recovery_scope": recovery["recovery_scope"],
            "producer_engine_hashes": expected_engine_hashes,
            "children": pinned_children,
        }
    seconds_paths, child_receipts = _verified_child_outputs(
        manifest,
        segment_dir,
        segments,
        expected_engine_hashes=expected_engine_hashes,
        expected_source_scopes=expected_source_scopes,
        pinned_children=pinned_children,
    )
    child_source_scopes = [
        json.loads((segment_dir / f"{segment}.receipt.json").read_text())["source_scope"]
        for segment in segments
    ]

    pre_classifier = frozen_detector.FrozenPreFamilyClassifier.load(
        "research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json"
    )
    a_classifier = frozen_detector.FrozenAClassifier.load(
        "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"
    )
    event_writers = {
        "legacy": DeterministicGzipJsonlWriter(out / "LEGACY_CONTROL_EVENTS.jsonl.gz"),
        "native": DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_EVENTS.jsonl.gz"),
    }
    lineage_writers = {
        "legacy": DeterministicGzipJsonlWriter(out / "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz"),
        "native": DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz"),
    }
    overlap_events = []
    weeks = []
    population_seconds = 0
    boundary_audit: dict[str, Any] = {}
    try:
        for week, rows in _iter_seconds_weeks(seconds_paths, weeks_filter, segments, boundary_audit):
            weeks.append(week)
            population_seconds += len(rows)
            for key, view in (("legacy", "LEGACY_CONTROL"), ("native", "V4_NATIVE_FULL")):
                events = detect_events_for_week(rows, view, pre_classifier, a_classifier)
                for event in events:
                    event_writers[key].write(event)
                    lineage_writers[key].write(compact_lineage_input(event))
                if key == "legacy" and week in OVERLAP_WEEKS:
                    overlap_events.extend(events)
        event_outputs = {key: writer.close() for key, writer in event_writers.items()}
        lineage_inputs = {key: writer.close() for key, writer in lineage_writers.items()}
    except Exception:
        for writer in [*event_writers.values(), *lineage_writers.values()]:
            writer.abort()
        raise

    frozen_rows = list(read_gzip_jsonl(frozen_overlap_table))
    frozen_lineage = list(read_gzip_jsonl(frozen_overlap_lineage))
    actual_overlap_lineage = derive_pilot_lineage(overlap_events)
    overlap, mismatches = legacy_overlap_receipt(
        frozen_rows, overlap_events, frozen_lineage, actual_overlap_lineage
    )
    atomic_json(out / "LEGACY_CONTROL_OVERLAP_EQUIVALENCE.json", overlap)
    mismatch_output = deterministic_gzip_jsonl(
        out / "LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz", mismatches
    )
    if overlap["status"] != "PASS":
        raise CensusError(
            "LEGACY_CONTROL overlap equivalence failed closed; retained mismatch receipt written"
        )

    legacy_population, legacy_summary, legacy_index = lineage_population(
        out / "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz",
        "LEGACY_CONTROL",
        hashes,
        out / "LEGACY_CONTROL_POPULATION.jsonl.gz",
        out / "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
    )
    gc.collect()
    native_population, native_summary, native_index = lineage_population(
        out / "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz",
        "V4_NATIVE_FULL",
        hashes,
        out / "V4_NATIVE_FULL_POPULATION.jsonl.gz",
        out / "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz",
    )
    gc.collect()
    population_outputs = {"legacy": legacy_population, "native": native_population}
    crosswalk_output, crosswalk_summary = build_crosswalk(
        out / "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
        out / "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz",
        out / "DUAL_CENSUS_CROSSWALK.jsonl.gz",
    )
    summary = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_RECONCILIATION_V1_20260822",
        "status": "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE",
        "revision": REVISION,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_object_count": manifest["canonical_object_count"],
        "source_total_bytes": manifest["canonical_total_bytes"],
        "child_receipt_count": len(child_receipts),
        "child_receipt_hashes": child_receipts,
        "replay_source_scopes": child_source_scopes,
        "replayed_source_object_count": sum(x["selected_object_count"] for x in child_source_scopes),
        "replayed_source_total_bytes": sum(x["selected_total_bytes"] for x in child_source_scopes),
        "segment_boundary_reconciliation": boundary_audit,
        "preflight_child_recovery": recovery,
        "population_seconds": population_seconds,
        "weeks": weeks,
        "weeks_filter": None if weeks_filter is None else sorted(weeks_filter),
        "legacy_overlap_equivalence": overlap,
        "retained_overlap_mismatches": mismatch_output,
        "event_outputs": event_outputs,
        "lineage_input_outputs": lineage_inputs,
        "population_outputs": population_outputs,
        "crosswalk_index_outputs": {"legacy": legacy_index, "native": native_index},
        "legacy_population_summary": legacy_summary,
        "native_population_summary": native_summary,
        "crosswalk_output": crosswalk_output,
        "crosswalk_summary": crosswalk_summary,
        "engine_hashes": hashes,
        "ruleset_sha256": ruleset_sha256(),
        "adapter_revision": ADAPTER_REVISION,
        "native_taxonomy": NATIVE_TAXONOMY,
        "retention_policy": RULESET,
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "permanent_frankie_mutated": False,
        "frozen_detector_mutated": False,
    }
    summary["receipt_sha256"] = sha256_json(summary)
    atomic_json(out / "STEP1_DUAL_CENSUS_RECEIPT.json", summary)
    return summary


def stage_segment(
    manifest: dict[str, Any],
    segment: str,
    stage_dir: Path,
    s3: Any,
    object_dates: set[str] | None = None,
) -> list[Path]:
    paths = []
    for obj in _segment_objects(manifest, segment, object_dates):
        dst = _local_object_path(stage_dir, manifest, obj)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == int(obj["bytes"]) and sha256_file(dst) == obj["sha256"]:
            paths.append(dst)
            continue
        tmp = dst.with_suffix(dst.suffix + ".partial")
        tmp.unlink(missing_ok=True)
        s3.download_file(manifest["bucket"], obj["key"], str(tmp))
        if tmp.stat().st_size != int(obj["bytes"]) or sha256_file(tmp) != obj["sha256"]:
            raise CensusError(f"downloaded source integrity failure: {obj['key']}")
        os.replace(tmp, dst)
        paths.append(dst)
    return paths


def run_controller(
    manifest_path: str | Path,
    work_dir: str | Path,
    frozen_overlap_table: str | Path,
    frozen_overlap_lineage: str | Path,
    *,
    overlap_only: bool = False,
    s3_progress_prefix: str | None = None,
) -> dict[str, Any]:
    try:
        import boto3
    except ImportError as exc:
        raise CensusError("boto3 is required for controller staging") from exc
    manifest = load_manifest(manifest_path)
    work = Path(work_dir)
    stage = work / "stage"
    segments_out = work / "segments"
    results = work / ("overlap_preflight" if overlap_only else "results")
    work.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3", region_name=manifest.get("region", "us-east-2"))
    def upload_progress(path: Path) -> None:
        if not s3_progress_prefix:
            return
        prefix = s3_progress_prefix.strip("/")
        try:
            relative = path.resolve().relative_to(work.resolve()).as_posix()
        except ValueError as exc:
            raise CensusError(f"progress path escaped work directory: {path}") from exc
        s3.upload_file(str(path), manifest["bucket"], f"{prefix}/{relative}")
    weeks_filter = set(OVERLAP_WEEKS) if overlap_only else None
    object_dates = _object_dates_for_weeks(weeks_filter) if weeks_filter is not None else None
    segments = _segments_for_weeks(manifest, weeks_filter)
    controller_objects = [
        obj
        for segment in segments
        for obj in _segment_objects(manifest, segment, object_dates)
    ]
    controller_source_scope = {
        "mode": "FULL_CANONICAL_MANIFEST" if object_dates is None else "REVEALED_OVERLAP_DAILY_OBJECTS",
        "requested_object_dates": None if object_dates is None else sorted(object_dates),
        "selected_object_count": len(controller_objects),
        "selected_total_bytes": sum(int(obj["bytes"]) for obj in controller_objects),
    }
    engine = material_hashes()
    controller_hb = Heartbeat(
        work / "CONTROLLER_HEARTBEAT.json",
        {
            "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_CONTROLLER_HEARTBEAT_V1",
            "revision": REVISION,
            "source_manifest_sha256": manifest["manifest_sha256"],
            "source_scope": controller_source_scope,
            "overlap_only": overlap_only,
        },
        on_write=upload_progress,
    )
    controller_hb.write(force=True, phase="LAUNCHED", segment_count=len(segments), completed_segments=0)
    completed = 0
    for segment in segments:
        source_scope = _segment_source_scope(manifest, segment, object_dates)
        prior = _resumable_segment_receipt(manifest, segment, segments_out, engine, source_scope)
        if prior is not None:
            completed += 1
            controller_hb.write(
                force=True,
                phase="SEGMENT_RESUMED_WITHOUT_RECOMPUTE",
                active_segment=segment,
                completed_segments=completed,
                child_receipt_sha256=prior["receipt_sha256"],
            )
            upload_progress(segments_out / f"{segment}.receipt.json")
            continue
        controller_hb.write(force=True, phase="STAGING_SEGMENT", active_segment=segment, completed_segments=completed)
        staged_paths = stage_segment(manifest, segment, stage, s3, object_dates)
        try:
            child = process_segment(
                manifest_path,
                segment,
                stage,
                segments_out,
                object_dates=object_dates,
                heartbeat_on_write=upload_progress,
            )
        finally:
            for staged_path in staged_paths:
                staged_path.unlink(missing_ok=True)
        completed += 1
        upload_progress(segments_out / f"{segment}.receipt.json")
        controller_hb.write(
            force=True,
            phase="SEGMENT_COMPLETE",
            active_segment=segment,
            completed_segments=completed,
            child_receipt_sha256=child["receipt_sha256"],
        )
    controller_hb.write(force=True, phase="RECONCILING", completed_segments=completed)
    receipt = reconcile(
        manifest_path,
        segments_out,
        results,
        frozen_overlap_table,
        frozen_overlap_lineage,
        weeks_filter=weeks_filter,
    )
    controller_hb.write(force=True, phase="COMPLETE", completed_segments=completed, receipt_sha256=receipt["receipt_sha256"])
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    seg = sub.add_parser("segment")
    seg.add_argument("--manifest", required=True)
    seg.add_argument("--segment", required=True)
    seg.add_argument("--stage-dir", required=True)
    seg.add_argument("--out-dir", required=True)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--manifest", required=True)
    rec.add_argument("--segment-dir", required=True)
    rec.add_argument("--out-dir", required=True)
    rec.add_argument("--frozen-overlap-table", required=True)
    rec.add_argument("--frozen-overlap-lineage", required=True)
    rec.add_argument("--weeks", help="Optional comma-separated revealed overlap weeks")
    rec.add_argument("--child-recovery-contract")
    run = sub.add_parser("run")
    run.add_argument("--manifest", required=True)
    run.add_argument("--work-dir", required=True)
    run.add_argument("--frozen-overlap-table", required=True)
    run.add_argument("--frozen-overlap-lineage", required=True)
    run.add_argument("--overlap-only", action="store_true")
    run.add_argument("--s3-progress-prefix")
    args = ap.parse_args()
    if args.command == "segment":
        result = process_segment(args.manifest, args.segment, args.stage_dir, args.out_dir)
    elif args.command == "reconcile":
        result = reconcile(
            args.manifest,
            args.segment_dir,
            args.out_dir,
            args.frozen_overlap_table,
            args.frozen_overlap_lineage,
            weeks_filter=None if not args.weeks else set(args.weeks.split(",")),
            child_recovery_contract=args.child_recovery_contract,
        )
    else:
        result = run_controller(
            args.manifest,
            args.work_dir,
            args.frozen_overlap_table,
            args.frozen_overlap_lineage,
            overlap_only=args.overlap_only,
            s3_progress_prefix=args.s3_progress_prefix,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
