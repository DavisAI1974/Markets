from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (
    build_checkpoint,
    write_checkpoint_atomic,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import export_adapter_state
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter


RT_ROOT = Path("/workspace/scratch/da00127ac123/a-clean-runtime-33161766927")
SOURCE_PACKET = Path("/workspace/scratch/da00127ac123/a-clean-artifact-33161766927")
PACKET = Path("/workspace/scratch/da00127ac123/a-clean-forecaster-packet-33161766927")
RUNTIME = Path("/workspace/scratch/da00127ac123/a-clean-forecaster-runtime-33161766927")
RUN_ID = "frankie-a-clean-forecaster-33161766927-1"


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def receipt_hash(value: dict[str, object], field: str) -> str:
    return hashlib.sha256(canonical({k: v for k, v in value.items() if k != field})).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.exists():
        if sha256_file(target) != sha256_file(source):
            raise RuntimeError(f"existing packet artifact drift: {target}")
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def main() -> None:
    PACKET.mkdir(mode=0o700, parents=True, exist_ok=True)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    (RUNTIME / "checkpoints").mkdir(mode=0o700, exist_ok=True)
    manifest = json.loads((RT_ROOT / "source_manifest.json").read_text(encoding="utf-8"))
    rt_lock = json.loads((RT_ROOT / "RT_FIRST_LOCK.json").read_text(encoding="utf-8"))
    rt_freeze = json.loads((RT_ROOT / "RT_FREEZE_RECEIPT.json").read_text(encoding="utf-8"))
    evidence_bundle = json.loads((RT_ROOT / "evidence_bundle.json").read_text(encoding="utf-8"))
    if rt_lock["memory_mode"] != "CLEAN" or rt_freeze["memory_package_present"] is not False:
        raise RuntimeError("A-clean Forecaster received a memory-bearing RT state")
    if rt_lock["first_lock_hash"] != rt_freeze["first_lock_hash"]:
        raise RuntimeError("RT lock/freeze hash drift")
    if rt_freeze["forecaster_started"] is not False or rt_lock["forecaster_started"] is not False:
        raise RuntimeError("RT state says Forecaster already started")
    if rt_freeze["locked_checkpoint_id"] != "2e10b3f2534aaf697129831608a8e65fd9c4ac8ca92ec171c2a012fe8593b384":
        raise RuntimeError("unexpected final RT checkpoint")
    if rt_lock["first_lock_hash"] != "ef728adf5ae2064c242f0e72acbf95f1d5b586a3f1845bed9ac9577ea998dd42":
        raise RuntimeError("unexpected RT first lock")
    if rt_freeze["freeze_receipt_hash"] != "bc7e8ed9dbcb08177d46a48f16176afb026f5efe0c6fa49164260877fd172793":
        raise RuntimeError("unexpected RT freeze receipt")
    if evidence_bundle["bundle_hash"] != "94a32deafdcb580868ba24df829b616edf36a80f84f80b7cd828efea24a13b36":
        raise RuntimeError("unexpected native evidence bundle")
    if sha256_file(RT_ROOT / "FINAL_FILE_SHA256SUMS") != "d1994ce1449144fd48e2e87930c59727da32d85cc1c9b2cc770d77781c4c6415":
        raise RuntimeError("unexpected immutable RT checksum manifest")

    frozen = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_RT_FROZEN_STATE_V1",
        "run_id": rt_lock["run_id"],
        "packet_id": rt_lock["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "memory_mode": "CLEAN",
        "memory_package_present": False,
        "authoritative_rt_first_lock": rt_lock,
        "rt_first_lock_hash": rt_lock["first_lock_hash"],
        "rt_freeze_receipt_hash": rt_freeze["freeze_receipt_hash"],
        "rt_locked_checkpoint_id": rt_freeze["locked_checkpoint_id"],
        "native_evidence_bundle_hash": evidence_bundle["bundle_hash"],
        "immutable_rt_file_manifest_sha256": sha256_file(RT_ROOT / "FINAL_FILE_SHA256SUMS"),
        "forecaster_may_modify_rt_state": False,
        "frozen_state_hash": "",
    }
    frozen["frozen_state_hash"] = receipt_hash(frozen, "frozen_state_hash")
    handoff = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_ONEWAY_HANDOFF_V1",
        "from_role": "REAL_TIME_FRANKIE",
        "to_role": "FORECASTER_FRANKIE",
        "rt_frozen_before_forecaster": True,
        "forecaster_may_modify_rt_state": False,
        "forecaster_may_create_competing_rt_lock": False,
        "answer_wall": "SEALED",
        "memory_mode": "CLEAN",
        "prior_reduced_surface_memory_present": False,
        "frozen_rt_state_hash": frozen["frozen_state_hash"],
        "handoff_hash": "",
    }
    handoff["handoff_hash"] = receipt_hash(handoff, "handoff_hash")

    write_json(PACKET / "RT_FROZEN_STATE.json", frozen)
    write_json(PACKET / "ONEWAY_HANDOFF.json", handoff)
    for name in ("source_manifest.json", "evidence_bundle.json", "FINAL_FILE_SHA256SUMS"):
        link_or_copy(RT_ROOT / name, PACKET / name)
    link_or_copy(RT_ROOT / "native-evidence-groups.jsonl.gz", PACKET / "native-evidence-groups.jsonl.gz")
    for source in manifest["sources"]:
        link_or_copy(SOURCE_PACKET / "sources" / source["name"], PACKET / "sources" / source["name"])

    packet = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_FORECASTER_WORK_PACKET_V1",
        "run_id": RUN_ID,
        "arm": "A-clean",
        "role": "FORECASTER_FRANKIE",
        "memory_mode": "CLEAN",
        "prior_reduced_surface_memory_present": False,
        "source_manifest_hash": manifest["manifest_hash"],
        "native_evidence_bundle_hash": evidence_bundle["bundle_hash"],
        "native_evidence_groups_sha256": sha256_file(PACKET / "native-evidence-groups.jsonl.gz"),
        "native_mbo_records_total": manifest["total_mbo_records"],
        "native_event_groups_total": evidence_bundle["completed_event_groups"],
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_reconstruction_required": True,
        "raw_actions_preserved_exactly_once": True,
        "independent_full_native_replay_required": True,
        "authoritative_frozen_rt_state_hash": frozen["frozen_state_hash"],
        "oneway_handoff_hash": handoff["handoff_hash"],
        "rt_first_lock_hash": rt_lock["first_lock_hash"],
        "rt_locked_checkpoint_id": rt_freeze["locked_checkpoint_id"],
        "answer_wall": "SEALED",
        "forbidden_inputs": [
            "reduced_or_seconds_market_data",
            "MBP_or_top10_substitutes",
            "prior_reduced_surface_learned_findings",
            "memory_assisted_arm_outputs",
            "answer_key_or_reveal_material",
            "scores_or_reconciliation",
        ],
        "required_output": "advisory forecast curve with causal clocks, scenarios, uncertainty, and abstention",
        "packet_hash": "",
    }
    packet["packet_hash"] = receipt_hash(packet, "packet_hash")
    packet_id = "aclean-fcpkt-" + packet["packet_hash"][:20]
    packet["packet_id"] = packet_id
    packet["packet_hash"] = receipt_hash(packet, "packet_hash")
    write_json(PACKET / "FORECASTER_WORK_PACKET.json", packet)

    initial_state = export_adapter_state(V4MboAdapter())
    controller = {
        "schema": "FRANKIE_A_CLEAN_FORECASTER_CONTINUATION_V1",
        "packet_id": packet_id,
        "phase": "PRE_NATIVE_REPLAY",
        "completed_native_mbo_records": 0,
        "completed_event_groups": 0,
        "hypotheses": [],
        "uncertainty": ["Native replay has not started."],
        "continuation_hash": "",
    }
    controller["continuation_hash"] = receipt_hash(controller, "continuation_hash")
    checkpoint = build_checkpoint(
        run_id=RUN_ID,
        controller="A_CHATGPT",
        memory_mode="CLEAN",
        sequence=0,
        source_manifest_hash=manifest["manifest_hash"],
        completed_mbo_records=0,
        total_mbo_records=manifest["total_mbo_records"],
        event_group_open=False,
        adapter_state_hash=initial_state["state_hash"],
        controller_state_hash=controller["continuation_hash"],
        previous_checkpoint_hash=None,
        phase="PRE_CALL_FORECASTER_NATIVE",
        locked=False,
    )
    write_json(RUNTIME / "FORECASTER_WORK_PACKET.json", packet)
    write_json(RUNTIME / "RT_FROZEN_STATE.json", frozen)
    write_json(RUNTIME / "ONEWAY_HANDOFF.json", handoff)
    write_json(RUNTIME / "checkpoints" / "adapter-state-000000.json", initial_state)
    write_json(RUNTIME / "checkpoints" / "continuation-000000.json", controller)
    write_checkpoint_atomic(RUNTIME / "checkpoints" / "checkpoint-000000.json", checkpoint)
    launch = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_FORECASTER_LAUNCH_RECEIPT_V1",
        "run_id": RUN_ID,
        "packet_id": packet_id,
        "packet_hash": packet["packet_hash"],
        "pre_call_checkpoint_id": checkpoint["checkpoint_hash"],
        "source_manifest_hash": manifest["manifest_hash"],
        "frozen_rt_state_hash": frozen["frozen_state_hash"],
        "oneway_handoff_hash": handoff["handoff_hash"],
        "memory_mode": "CLEAN",
        "memory_package_present": False,
        "native_mbo_records_completed": 0,
        "native_mbo_records_total": manifest["total_mbo_records"],
        "progress_percent": 0.0,
        "status": "RUNNING_PRE_NATIVE_REPLAY",
        "launch_receipt_hash": "",
    }
    launch["launch_receipt_hash"] = receipt_hash(launch, "launch_receipt_hash")
    write_json(RUNTIME / "FORECASTER_LAUNCH_RECEIPT.json", launch)
    print(json.dumps(launch, indent=2, sort_keys=True))


if __name__ == "__main__":
    os.chdir(REPO)
    main()
