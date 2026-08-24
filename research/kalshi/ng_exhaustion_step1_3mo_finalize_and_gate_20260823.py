#!/usr/bin/env python3
"""Run the exact bounded Sep-Nov 2021 Step-1 finalizer and gate with producer binding.

The three monthly children were produced by the frozen 0d318... Step-1 engine.
Later completion/recovery hardening intentionally changed finalizer file hashes without
replaying those children. This wrapper binds child verification to the immutable producer
hashes in the accepted launch receipt while binding finalization to the current finalizer
lock. It does not replay raw MBO, alter scientific definitions, launch Frankie, or proceed
downstream.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

RESEARCH_DIR = Path(__file__).resolve().parents[1]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ng_exhaustion_mbo_5y_step1_census_20260822 as census
import ng_exhaustion_mbo_3mo_step1_finalize_20260823 as bounded
from kalshi import ng_exhaustion_step1_3mo_completion_gate as gate

CANDIDATE = "0d318335825b4a0e19a5a2881522f3da0374788e"
LOCK_SCHEMA = "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZER_LOCK_V1_20260823"


class BoundFinalizationError(ValueError):
    pass


def _canonical_hash(body: dict[str, Any]) -> str:
    return census.sha256_json(body)


def _load_bindings(
    parent_manifest: dict[str, Any],
    launch_path: Path,
    lock_path: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    candidate_lock = launch.get("candidate_lock")
    if not isinstance(candidate_lock, dict):
        raise BoundFinalizationError("accepted launch candidate lock is absent")
    if launch.get("candidate_commit") != CANDIDATE or candidate_lock.get("candidate_commit") != CANDIDATE:
        raise BoundFinalizationError("child producer candidate identity drift")
    if candidate_lock.get("source_manifest_sha256") != parent_manifest.get("manifest_sha256"):
        raise BoundFinalizationError("child producer parent-manifest identity drift")
    if candidate_lock.get("ruleset_sha256") != census.ruleset_sha256():
        raise BoundFinalizationError("child producer ruleset identity drift")
    if candidate_lock.get("retention_policy") != census.RULESET:
        raise BoundFinalizationError("child producer retention-policy drift")
    if candidate_lock.get("release_or_virgin_holdout_consumed") is not False:
        raise BoundFinalizationError("launch receipt consumed release/virgin holdout")
    if candidate_lock.get("predictive_or_trading_experiment_authorized") is not False:
        raise BoundFinalizationError("launch receipt authorized predictive/trading work")
    producer = candidate_lock.get("engine_hashes")
    if not isinstance(producer, dict) or not producer:
        raise BoundFinalizationError("child producer engine hashes are absent")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    claimed = lock.get("finalizer_lock_sha256")
    body = dict(lock)
    body.pop("finalizer_lock_sha256", None)
    if claimed != _canonical_hash(body):
        raise BoundFinalizationError("finalizer lock canonical hash drift")
    finalizer = census.material_hashes()
    if lock.get("schema") != LOCK_SCHEMA:
        raise BoundFinalizationError("finalizer lock schema drift")
    if lock.get("parent_candidate_commit") != CANDIDATE:
        raise BoundFinalizationError("finalizer lock parent candidate drift")
    if lock.get("finalizer_engine_hashes") != finalizer:
        raise BoundFinalizationError("current finalizer engine is not the locked finalizer")
    return dict(producer), dict(finalizer), lock


def run_bound_finalization(
    *,
    parent_manifest_path: Path,
    segment_dir: Path,
    out_dir: Path,
    accepted_launch_path: Path,
    finalizer_lock_path: Path,
) -> dict[str, Any]:
    parent_manifest = census.load_manifest(parent_manifest_path)
    producer_hashes, finalizer_hashes, lock = _load_bindings(
        parent_manifest, accepted_launch_path, finalizer_lock_path
    )

    original_verified = census._verified_child_outputs

    def producer_bound_verified(
        manifest: dict[str, Any],
        child_dir: Path,
        segments: list[str],
        *,
        expected_engine_hashes: dict[str, str] | None = None,
        expected_source_scopes: dict[str, dict[str, Any]] | None = None,
        pinned_children: dict[str, dict[str, str]] | None = None,
    ):
        if expected_engine_hashes is not None and expected_engine_hashes != finalizer_hashes:
            raise census.CensusError("bounded caller finalizer-engine identity drift")
        return original_verified(
            manifest,
            child_dir,
            segments,
            expected_engine_hashes=producer_hashes,
            expected_source_scopes=expected_source_scopes,
            pinned_children=pinned_children,
        )

    census._verified_child_outputs = producer_bound_verified
    try:
        receipt = bounded.finalize_bounded_three_months(
            parent_manifest_path,
            segment_dir,
            out_dir,
            accepted_launch_path,
        )
        receipt["child_producer_identity"] = {
            "candidate_commit": CANDIDATE,
            "source_manifest_sha256": parent_manifest["manifest_sha256"],
            "ruleset_sha256": census.ruleset_sha256(),
            "engine_hashes": producer_hashes,
            "finalizer_engine_hashes": finalizer_hashes,
            "finalizer_lock_sha256": lock["finalizer_lock_sha256"],
            "raw_mbo_replayed": False,
            "scientific_definition_changed_by_binding": False,
        }
        receipt.pop("receipt_sha256", None)
        receipt["receipt_sha256"] = census.sha256_json(receipt)
        census.atomic_json(out_dir / "STEP1_DUAL_CENSUS_RECEIPT.json", receipt)

        result = gate.validate_completion(
            parent_manifest_path=parent_manifest_path,
            segment_dir=segment_dir,
            out_dir=out_dir,
            accepted_one_day_launch_receipt=accepted_launch_path,
        )
        observed = json.loads((out_dir / "STEP1_DUAL_CENSUS_RECEIPT.json").read_text(encoding="utf-8"))
        if observed.get("child_producer_identity") != receipt["child_producer_identity"]:
            raise BoundFinalizationError("child producer binding was not retained exactly")
        return {
            **result,
            "status": "STEP1_3MO_BOUND_PRODUCER_COMPLETION_GATE_PASS",
            "child_producer_candidate_commit": CANDIDATE,
            "child_producer_engine_hashes": producer_hashes,
            "finalizer_engine_hashes": finalizer_hashes,
            "finalizer_lock_sha256": lock["finalizer_lock_sha256"],
            "raw_mbo_replayed": False,
            "frankie_launched": False,
            "downstream_v4_launched": False,
        }
    finally:
        census._verified_child_outputs = original_verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-manifest", required=True)
    parser.add_argument("--segment-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--accepted-one-day-launch-receipt", required=True)
    parser.add_argument("--finalizer-lock", required=True)
    args = parser.parse_args()
    result = run_bound_finalization(
        parent_manifest_path=Path(args.parent_manifest),
        segment_dir=Path(args.segment_dir),
        out_dir=Path(args.out_dir),
        accepted_launch_path=Path(args.accepted_one_day_launch_receipt),
        finalizer_lock_path=Path(args.finalizer_lock),
    )
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
