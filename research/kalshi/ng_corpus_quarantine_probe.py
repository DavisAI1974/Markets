#!/usr/bin/env python3
"""Quarantine, probe, review, and promote NG corpus objects without inferring identity.

Unreviewed remote objects may enter only a byte-limited quarantine. Decoded source
evidence is matched to separately observed instrument definitions and emitted as a
REVIEW_REQUIRED binding proposal. Promotion reuses verified quarantine bytes only
after explicit operator approval. Outcomes, blind forecasts, posterior state,
``ng_brain.json``, execution, and the options lane remain untouched.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_materialization as materialization
from ng_corpus_quarantine_storage import (
    QUARANTINE_SCHEMA,
    CorpusQuarantineError,
    _fp,
    promote_quarantine,
    quarantine_download,
    validate_quarantine,
)
from ng_corpus_identity_probe import (
    PROBE_SCHEMA,
    PROBE_STATUSES,
    probe_quarantine,
    validate_probe,
)


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _client(endpoint: str | None = None) -> Any:
    try:
        import boto3  # type: ignore
    except ImportError as error:
        raise CorpusQuarantineError("S3 quarantine download requires boto3") from error
    return boto3.client("s3", endpoint_url=endpoint)


def _selftest() -> None:
    class _Lister:
        def __init__(self, key: str, size: int) -> None:
            self.key = key
            self.size = size

        def list_objects_v2(self, **_: Any) -> dict[str, Any]:
            return {
                "Contents": [{"Key": self.key, "Size": self.size, "ETag": "selftest"}],
                "IsTruncated": False,
            }

    class _Downloader:
        def __init__(self, bucket: str, key: str, payload: bytes) -> None:
            self.bucket = bucket
            self.key = key
            self.payload = payload

        def download_file(self, bucket: str, key: str, target: str) -> None:
            assert (bucket, key) == (self.bucket, self.key)
            Path(target).write_bytes(self.payload)

    rows = [
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": coverage.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "ts_event_s": 1773579600.0,
            "sequence": 1,
        },
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": coverage.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "ts_event_s": 1773579700.0,
            "sequence": 2,
        },
    ]
    payload = ("\n".join(json.dumps(row) for row in rows) + "\n").encode("utf-8")
    bucket = "selftest"
    key = "opaque/object.jsonl"
    snapshot = materialization.snapshot_s3(
        _Lister(key, len(payload)),
        bucket=bucket,
        prefixes=["opaque/"],
        observed_at="2026-07-22T00:00:00Z",
    )
    object_id = snapshot["objects"][0]["object_id"]
    definition = inspection.definition_observation(
        dataset=coverage.DATASET,
        publisher_id=1,
        instrument_id=1008,
        raw_symbol="NGJ26",
        definition_date="20260313",
        definition_start_s=1773500000.0,
        definition_end_s=1773700000.0,
        observed_from="selftest-definition",
        observed_at="2026-07-22T00:00:00Z",
        source_sha256=hashlib.sha256(payload).hexdigest(),
        source_size_bytes=len(payload),
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        quarantined = quarantine_download(
            _Downloader(bucket, key, payload),
            snapshot=snapshot,
            object_ids=[object_id],
            output_root=root / "quarantine",
            confirm_download=True,
            max_total_bytes=len(payload),
        )
        result, bindings = probe_quarantine(
            snapshot=snapshot,
            quarantine=quarantined,
            definitions=[definition],
        )
        assert result["objects"][0]["status"] == "UNIQUE_DEFINITION_MATCH"
        approved = copy.deepcopy(bindings)
        binding = approved["bindings"][0]
        binding.update(
            review_status="APPROVED",
            source_id="selftest-g15-l1",
            corpus_id=coverage.L1_CORPUS_ID,
            lane="l1_trades",
            day="20260315",
            definition=definition,
            skip_nonmatching=False,
        )
        binding.pop("binding_fingerprint", None)
        binding["binding_fingerprint"] = _fp(binding)
        approved.pop("binding_manifest_fingerprint", None)
        approved["binding_manifest_fingerprint"] = _fp(approved)
        promoted = promote_quarantine(
            snapshot=snapshot,
            bindings=approved,
            quarantine=quarantined,
            output_root=root / "promoted",
            confirm_promote=True,
        )
        assert promoted["approved_object_count"] == 1


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")

    quarantine_parser = sub.add_parser("quarantine")
    quarantine_parser.add_argument("--snapshot", type=Path, required=True)
    quarantine_parser.add_argument("--object-id", action="append", required=True)
    quarantine_parser.add_argument("--output-root", type=Path, required=True)
    quarantine_parser.add_argument("--max-total-bytes", type=int, required=True)
    quarantine_parser.add_argument("--confirm-quarantine-download", action="store_true")
    quarantine_parser.add_argument("--endpoint")
    quarantine_parser.add_argument("--out", type=Path, required=True)

    probe_parser = sub.add_parser("probe")
    probe_parser.add_argument("--snapshot", type=Path, required=True)
    probe_parser.add_argument("--quarantine", type=Path, required=True)
    probe_parser.add_argument("--definitions", type=Path, required=True)
    probe_parser.add_argument("--probe-out", type=Path, required=True)
    probe_parser.add_argument("--bindings-out", type=Path, required=True)

    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--snapshot", type=Path, required=True)
    promote_parser.add_argument("--bindings", type=Path, required=True)
    promote_parser.add_argument("--quarantine", type=Path, required=True)
    promote_parser.add_argument("--output-root", type=Path, required=True)
    promote_parser.add_argument("--confirm-promote", action="store_true")
    promote_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print("ng_corpus_quarantine_probe selftest: PASS")
        return 0
    if not args.command:
        parser.error("a command or --selftest is required")
    if args.command == "quarantine":
        snapshot = _load(args.snapshot)
        result = quarantine_download(
            _client(args.endpoint),
            snapshot=snapshot,
            object_ids=args.object_id,
            output_root=args.output_root,
            confirm_download=args.confirm_quarantine_download,
            max_total_bytes=args.max_total_bytes,
        )
        _write(args.out, result)
    elif args.command == "probe":
        snapshot = _load(args.snapshot)
        quarantined = _load(args.quarantine)
        result, bindings = probe_quarantine(
            snapshot=snapshot,
            quarantine=quarantined,
            definitions=_load(args.definitions),
        )
        _write(args.probe_out, result)
        _write(args.bindings_out, bindings)
    elif args.command == "promote":
        result = promote_quarantine(
            snapshot=_load(args.snapshot),
            bindings=_load(args.bindings),
            quarantine=_load(args.quarantine),
            output_root=args.output_root,
            confirm_promote=args.confirm_promote,
        )
        _write(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
