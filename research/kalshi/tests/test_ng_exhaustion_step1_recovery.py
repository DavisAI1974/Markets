import datetime as dt
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ng_exhaustion_mbo_5y_step1_census_20260822 import (
    DeterministicGzipJsonlWriter,
    _segment_source_scope,
    material_hashes,
    ruleset_sha256,
    sha256_json,
)
from research.kalshi.ng_exhaustion_step1_completion_gate import PROMOTION_CANARY_IDENTITY
from research.kalshi.ng_exhaustion_step1_recovery import (
    RecoveryError,
    build_finalization_recovery_contract,
    completed_controller_heartbeat,
)


CANDIDATE = "0d318335825b4a0e19a5a2881522f3da0374788e"
PRODUCER_ENGINE = {"research/old.py": "6" * 64}


def recovery_fixture(tmp_path: Path):
    start = dt.date(2021, 1, 1)
    objects = []
    segments = []
    for i in range(65):
        left = start + dt.timedelta(days=i)
        right = left + dt.timedelta(days=1)
        segment = f"{left:%Y%m%d}_{right:%Y%m%d}"
        segments.append(segment)
        objects.append({
            "segment": segment,
            "key": f"exact/glbx-mdp3-{left:%Y%m%d}.mbo.dbn.zst",
            "bytes": i + 1,
        })
    manifest = {
        "canonical_dbn_objects": objects,
        "canonical_object_count": 65,
        "canonical_total_bytes": sum(row["bytes"] for row in objects),
        "deterministic_native_segment_count": 65,
        "selected_interval_count": 61,
        "status": "CANONICAL_NATIVE_MBO_OBJECT_MANIFEST_FROZEN_AND_S3_VALIDATED",
        "prefix_wide_enumeration_used": False,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    manifest_sha = manifest["manifest_sha256"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir()
    for i, segment in enumerate(segments):
        seconds = segment_dir / f"{segment}.seconds.jsonl.gz"
        writer = DeterministicGzipJsonlWriter(seconds)
        writer.write({"epoch_second": i + 1})
        output = writer.close()
        receipt = {
            "status": "SEGMENT_COMPLETE",
            "segment": segment,
            "source_manifest_sha256": manifest_sha,
            "ruleset_sha256": ruleset_sha256(),
            "engine_hashes": PRODUCER_ENGINE,
            "source_scope": _segment_source_scope(manifest, segment, None),
            "seconds_output": output,
        }
        receipt["receipt_sha256"] = sha256_json(receipt)
        (segment_dir / f"{segment}.receipt.json").write_text(json.dumps(receipt))
    launch = {
        "launch_method": "USER_AUTHORIZED_ONE_DAY_CANARY_PROMOTION_V1_20260823",
        "candidate_commit": CANDIDATE,
        "candidate_lock": {
            "source_manifest_sha256": manifest_sha,
            "source_object_count": len(objects),
            "source_total_bytes": sum(row["bytes"] for row in objects),
            "ruleset_sha256": ruleset_sha256(),
            "engine_hashes": PRODUCER_ENGINE,
        },
        "canary_evidence": {
            **PROMOTION_CANARY_IDENTITY,
            "user_authorized_as_launch_canary": True,
            "lineage_equivalence_asserted": False,
            "multiweek_equivalence_asserted": False,
            "source_prefix_wide_enumeration_used": False,
            "release_or_virgin_holdout_consumed": False,
            "predictive_or_trading_experiment_run": False,
        },
        "legacy_overlap_equivalence": {
            "status": "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED",
            "retained_mismatch_count": 1,
            "lineage_equivalence_asserted": False,
            "multiweek_equivalence_asserted": False,
        },
    }
    launch_path = tmp_path / "launch.json"
    launch_path.write_text(json.dumps(launch))
    lock = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZER_LOCK_V1_20260823",
        "parent_candidate_commit": CANDIDATE,
        "recovery_scope": "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY",
        "finalizer_engine_hashes": material_hashes(),
        "recovery_script_sha256": "7" * 64,
        "recovery_workflow_sha256": "8" * 64,
    }
    lock["finalizer_lock_sha256"] = sha256_json(lock)
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(lock))
    return manifest_path, segment_dir, launch_path, lock_path, segments


def test_builds_exact_65_child_no_raw_replay_contract(tmp_path):
    manifest, segments, launch, lock, names = recovery_fixture(tmp_path)
    contract = build_finalization_recovery_contract(
        manifest, segments, launch, lock, candidate_commit=CANDIDATE
    )
    assert contract["recovery_scope"] == "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY"
    assert contract["raw_mbo_replayed"] is False
    assert sorted(contract["children"]) == names
    assert len(contract["children"]) == 65
    assert contract["producer_engine_hashes"] == PRODUCER_ENGINE
    assert contract["finalizer_engine_hashes"] == material_hashes()


def test_recovery_contract_fails_if_any_child_is_missing(tmp_path):
    manifest, segments, launch, lock, names = recovery_fixture(tmp_path)
    (segments / f"{names[-1]}.receipt.json").unlink()
    with pytest.raises(RecoveryError, match="child"):
        build_finalization_recovery_contract(
            manifest, segments, launch, lock, candidate_commit=CANDIDATE
        )


def test_recovery_contract_rejects_manifest_payload_drift(tmp_path):
    manifest, segments, launch, lock, _ = recovery_fixture(tmp_path)
    body = json.loads(manifest.read_text())
    body["canonical_total_bytes"] += 1
    manifest.write_text(json.dumps(body))
    with pytest.raises(RecoveryError, match="manifest hash"):
        build_finalization_recovery_contract(
            manifest, segments, launch, lock, candidate_commit=CANDIDATE
        )


def test_completed_heartbeat_binds_exact_final_receipt(tmp_path):
    manifest, _, _, _, _ = recovery_fixture(tmp_path)
    heartbeat = completed_controller_heartbeat(
        manifest,
        receipt_sha256="9" * 64,
    )
    assert heartbeat["phase"] == "COMPLETE"
    assert heartbeat["receipt_sha256"] == "9" * 64
    assert heartbeat["completed_segments"] == 65
    assert heartbeat["source_scope"]["mode"] == "FULL_CANONICAL_MANIFEST"


def test_completed_heartbeat_rejects_malformed_receipt_hash(tmp_path):
    manifest, _, _, _, _ = recovery_fixture(tmp_path)
    with pytest.raises(RecoveryError, match="SHA-256"):
        completed_controller_heartbeat(manifest, receipt_sha256="not-a-hash")
