#!/usr/bin/env python3
"""Prepare an exact no-raw-replay finalization contract for Step-1."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


RESEARCH_DIR = Path(__file__).resolve().parents[1]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ng_exhaustion_mbo_5y_step1_census_20260822 as census

from kalshi.ng_exhaustion_step1_completion_gate import (
    EXPECTED_FULL_SEGMENTS,
    FINALIZATION_RECOVERY_SCHEMA,
    FINALIZATION_RECOVERY_SCOPE,
    FINALIZER_LOCK_SCHEMA,
    PROMOTION_CANDIDATE,
)


class RecoveryError(ValueError):
    pass


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _load_lock(path: Path, candidate_commit: str) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    claimed = lock.get("finalizer_lock_sha256")
    body = dict(lock)
    body.pop("finalizer_lock_sha256", None)
    if claimed != _canonical_hash(body):
        raise RecoveryError("finalizer lock canonical hash drift")
    if (
        lock.get("schema") != FINALIZER_LOCK_SCHEMA
        or lock.get("parent_candidate_commit") != candidate_commit
        or lock.get("recovery_scope") != FINALIZATION_RECOVERY_SCOPE
        or lock.get("finalizer_engine_hashes") != census.material_hashes()
    ):
        raise RecoveryError("finalizer lock identity or engine drift")
    return lock


def build_finalization_recovery_contract(
    manifest_path: str | Path,
    segment_dir: str | Path,
    launch_receipt_path: str | Path,
    finalizer_lock_path: str | Path,
    *,
    candidate_commit: str,
) -> dict[str, Any]:
    """Validate and pin all 65 completed children without reading raw MBO."""
    if candidate_commit != PROMOTION_CANDIDATE:
        raise RecoveryError("recovery candidate identity drift")
    manifest_path = Path(manifest_path)
    segment_dir = Path(segment_dir)
    launch_receipt_path = Path(launch_receipt_path)
    lock = _load_lock(Path(finalizer_lock_path), candidate_commit)
    try:
        manifest = census.load_manifest(manifest_path)
    except census.CensusError as exc:
        raise RecoveryError(f"canonical manifest validation failed: {exc}") from exc
    launch = json.loads(launch_receipt_path.read_text(encoding="utf-8"))
    launch_lock = launch.get("candidate_lock")
    if not isinstance(launch_lock, dict):
        raise RecoveryError("launch candidate lock is absent")
    objects = manifest.get("canonical_dbn_objects", [])
    object_count = len(objects)
    total_bytes = sum(int(row.get("bytes", 0)) for row in objects)
    if (
        launch.get("candidate_commit") != candidate_commit
        or launch_lock.get("source_manifest_sha256") != manifest.get("manifest_sha256")
        or launch_lock.get("source_object_count") != object_count
        or launch_lock.get("source_total_bytes") != total_bytes
        or manifest.get("canonical_object_count") != object_count
        or manifest.get("canonical_total_bytes") != total_bytes
        or launch_lock.get("ruleset_sha256") != census.ruleset_sha256()
    ):
        raise RecoveryError("launch/manifest/accounting/ruleset recovery binding drift")
    try:
        accepted, _ = census.accepted_one_day_canary_overlap(
            launch_receipt_path,
            source_manifest_sha256=manifest["manifest_sha256"],
        )
    except census.CensusError as exc:
        raise RecoveryError(f"accepted canary recovery binding failed: {exc}") from exc
    segments = sorted({row["segment"] for row in manifest.get("canonical_dbn_objects", [])})
    if (
        len(segments) != EXPECTED_FULL_SEGMENTS
        or manifest.get("deterministic_native_segment_count") != EXPECTED_FULL_SEGMENTS
    ):
        raise RecoveryError("recovery requires the exact 65-segment manifest")
    producer_engine = launch_lock.get("engine_hashes")
    if not isinstance(producer_engine, dict) or not producer_engine:
        raise RecoveryError("producer engine hashes are absent")
    scopes = {
        segment: census._segment_source_scope(manifest, segment, None)
        for segment in segments
    }
    try:
        census._verified_child_outputs(
            manifest,
            segment_dir,
            segments,
            expected_engine_hashes=producer_engine,
            expected_source_scopes=scopes,
        )
    except census.CensusError as exc:
        raise RecoveryError(f"exact child validation failed: {exc}") from exc
    children = {}
    for segment in segments:
        receipt = json.loads(
            (segment_dir / f"{segment}.receipt.json").read_text(encoding="utf-8")
        )
        children[segment] = {
            "receipt_sha256": receipt["receipt_sha256"],
            "seconds_gzip_sha256": receipt["seconds_output"]["gzip_sha256"],
            "seconds_rows": receipt["seconds_output"]["rows"],
        }
    return {
        "schema": FINALIZATION_RECOVERY_SCHEMA,
        "parent_candidate_commit": candidate_commit,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "ruleset_sha256": census.ruleset_sha256(),
        "recovery_scope": FINALIZATION_RECOVERY_SCOPE,
        "raw_mbo_replayed": False,
        "producer_engine_hashes": producer_engine,
        "finalizer_engine_hashes": census.material_hashes(),
        "accepted_launch_receipt_file_sha256": accepted[
            "accepted_launch_receipt_file_sha256"
        ],
        "finalizer_lock_sha256": lock["finalizer_lock_sha256"],
        "children": children,
    }


def completed_controller_heartbeat(
    manifest_path: str | Path,
    *,
    receipt_sha256: str,
) -> dict[str, Any]:
    try:
        manifest = census.load_manifest(manifest_path)
    except census.CensusError as exc:
        raise RecoveryError(f"canonical manifest validation failed: {exc}") from exc
    if (
        not isinstance(receipt_sha256, str)
        or len(receipt_sha256) != 64
        or any(char not in "0123456789abcdef" for char in receipt_sha256)
    ):
        raise RecoveryError("completion heartbeat receipt SHA-256 is malformed")
    objects = manifest.get("canonical_dbn_objects", [])
    segments = {row["segment"] for row in objects}
    object_count = len(objects)
    total_bytes = sum(int(row.get("bytes", 0)) for row in objects)
    if (
        len(segments) != EXPECTED_FULL_SEGMENTS
        or manifest.get("canonical_object_count") != object_count
        or manifest.get("canonical_total_bytes") != total_bytes
    ):
        raise RecoveryError("completion heartbeat requires 65 canonical segments")
    return {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_CONTROLLER_HEARTBEAT_V1",
        "revision": census.REVISION,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_scope": {
            "mode": "FULL_CANONICAL_MANIFEST",
            "requested_object_dates": None,
            "selected_object_count": object_count,
            "selected_total_bytes": total_bytes,
        },
        "overlap_only": False,
        "phase": "COMPLETE",
        "completed_segments": EXPECTED_FULL_SEGMENTS,
        "receipt_sha256": receipt_sha256,
        "recovery_finalizer_used": True,
        "raw_mbo_replayed_by_finalizer": False,
        "heartbeat_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scientific_outcome_mutated_by_heartbeat": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-contract")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--segment-dir", required=True)
    prepare.add_argument("--launch-receipt", required=True)
    prepare.add_argument("--finalizer-lock", required=True)
    prepare.add_argument("--candidate-commit", required=True)
    prepare.add_argument("--output", required=True)
    heartbeat = sub.add_parser("complete-heartbeat")
    heartbeat.add_argument("--manifest", required=True)
    heartbeat.add_argument("--receipt-sha256", required=True)
    heartbeat.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "prepare-contract":
        result = build_finalization_recovery_contract(
            args.manifest,
            args.segment_dir,
            args.launch_receipt,
            args.finalizer_lock,
            candidate_commit=args.candidate_commit,
        )
    else:
        result = completed_controller_heartbeat(
            args.manifest,
            receipt_sha256=args.receipt_sha256,
        )
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": args.command, "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
