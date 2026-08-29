from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
SOURCE_PACKET = Path("/workspace/scratch/da00127ac123/a-clean-artifact-33161766927")
PACKET = Path("/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2")
MEMORY = REPO / "research/kalshi/frankie_raw_mbo_benchmark/prior_memory/workmode-32851909748-1"
RUN_ID = "frankie-a-memory-rt-c7da7d257fda-1"
LAUNCH_COMMIT = "c7da7d257fda2ce9ddccfaee56020ed3e7de8e50"
# Identity only: staging fields differ per run, so the full manifest hash is not pinnable.
SOURCE_IDENTITY_HASH = "4d02dae63163a43fe0dc093ad0bda9a6d055a455cbc946a59d5b9008dad190ac"
PACKAGE_SHA256 = "0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87"
PROOF_RECEIPT_HASH = "e7d8cbc54f354a4902ab72792e379033a25f5f28102fcf9d4bb82dda1d7e8435"
REPOSITORY_RECEIPT_HASH = "9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b"
REQUIRED_STARTING_TIP = "82e140598b03bb38a7761c19d0ac47017c3908d0"
MEMORY_FILES = (
    "RT_OUTPUT.json", "RT_CONTEXT_MANIFEST.json", "RT_AGENT_RECEIPT.json",
    "RT_FIRST_LOCK.json", "RT_FROZEN_STATE.json", "ONEWAY_HANDOFF.json",
    "RT_FREEZE_COMPLETE.json", "RT_FREEZE_EXTERNAL_ANCHOR.json",
    "FORECASTER_OUTPUT.json", "FORECASTER_CONTEXT_MANIFEST.json",
    "FORECASTER_AGENT_RECEIPT.json", "FORECASTER_FIRST_LOCK.json",
    "EXECUTION_USAGE.json", "ARTIFACT_MANIFEST.json", "COMPLETE.json",
)

sys.path.insert(0, str(REPO))
from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (  # noqa: E402
    build_checkpoint,
    write_checkpoint_atomic,
)
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import (  # noqa: E402
    build_chat_packet_contract,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (  # noqa: E402
    export_adapter_state,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter  # noqa: E402


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    ).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    if PACKET.exists():
        raise RuntimeError(f"packet path already exists: {PACKET}")
    (PACKET / "sources").mkdir(parents=True, mode=0o700)
    (PACKET / "memory" / "learned-output-chain").mkdir(parents=True, mode=0o700)
    (PACKET / "checkpoints").mkdir(parents=True, mode=0o700)

    manifest = json.loads((SOURCE_PACKET / "source_manifest.json").read_text(encoding="utf-8"))
    if manifest["source_identity_hash"] != SOURCE_IDENTITY_HASH or manifest["total_mbo_records"] != 5_667_689:
        raise RuntimeError("native source manifest identity mismatch")
    write_json(PACKET / "source_manifest.json", manifest)
    for source in manifest["sources"]:
        original = SOURCE_PACKET / "sources" / source["name"]
        if original.stat().st_size != source["bytes"] or file_hash(original) != source["sha256"]:
            raise RuntimeError(f"native source identity mismatch: {source['name']}")
        destination = PACKET / "sources" / source["name"]
        subprocess.run(["cp", "--reflink=auto", str(original), str(destination)], check=True)

    proof = json.loads((MEMORY / "REPOSITORY_FREEZE.json").read_text(encoding="utf-8"))
    if proof["proof_chain_verification"] != "PASS" or proof["source_run_id"] != "workmode-32851909748-1":
        raise RuntimeError("prior memory recovery proof mismatch")
    stage = PACKET / "memory" / "learned-output-chain"
    for name in MEMORY_FILES:
        shutil.copyfile(MEMORY / name, stage / name)
    package = PACKET / "memory" / "prior-learned-package.tgz"
    command = (
        f"tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf - "
        f"-C {stage} . | gzip -n > {package}"
    )
    subprocess.run(["bash", "-lc", command], check=True)
    if file_hash(package) != PACKAGE_SHA256:
        raise RuntimeError("deterministic prior memory package hash mismatch")

    recovery = {
        "schema": "FRANKIE_PRIOR_MEMORY_REPOSITORY_VERIFICATION_V1",
        "source_run_id": proof["source_run_id"],
        "source_surface_label": proof["source_surface_label"],
        "source_launch_commit": proof["source_launch_commit"],
        "recovery_proof_sha256": file_hash(MEMORY / "REPOSITORY_FREEZE.json"),
        "required_artifact_count": len(MEMORY_FILES),
        "rt_output_sha256": file_hash(MEMORY / "RT_OUTPUT.json"),
        "forecaster_output_sha256": file_hash(MEMORY / "FORECASTER_OUTPUT.json"),
        "complete_receipt_hash": json.loads((MEMORY / "COMPLETE.json").read_text())["receipt_hash"],
        "proof_chain_verification": "PASS",
        "step1_or_post_reveal_content": False,
        "current_raw_mbo_arm_output_content": False,
        "old_reduced_market_rows_in_package": False,
    }
    recovery["receipt_hash"] = canonical_hash(recovery)
    if recovery["receipt_hash"] != REPOSITORY_RECEIPT_HASH:
        raise RuntimeError("repository verification receipt hash mismatch")
    write_json(PACKET / "memory" / "prior-memory-repository-verification.json", recovery)

    files = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": file_hash(path)}
        for path in sorted(stage.iterdir())
    ]
    memory_receipt = {
        "schema": "FRANKIE_PREEXISTING_UNREVEALED_OCT45_MEMORY_PROOF_V2",
        "prior_run_id": "workmode-32851909748-1",
        "source_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "package_sha256": PACKAGE_SHA256,
        "repository_recovery_proof_sha256": file_hash(MEMORY / "REPOSITORY_FREEZE.json"),
        "pre_existing_before_current_benchmark": True,
        "proof_chain_verification": "PASS",
        "step1_or_post_reveal_content": False,
        "current_benchmark_arm_output_content": False,
        "old_reduced_rows_in_package": False,
        "files": files,
    }
    memory_receipt["receipt_hash"] = canonical_hash(memory_receipt)
    if memory_receipt["receipt_hash"] != PROOF_RECEIPT_HASH:
        raise RuntimeError("prior memory proof receipt hash mismatch")
    write_json(PACKET / "memory" / "prior-learned-package-receipt.json", memory_receipt)

    contract_memory = {
        "schema": "FRANKIE_PREEXISTING_UNREVEALED_OCT45_MEMORY_V1",
        "source_surface_label": memory_receipt["source_surface_label"],
        "package_sha256": memory_receipt["package_sha256"],
        "pre_existing_before_current_benchmark": True,
        "step1_or_post_reveal_content": False,
        "current_benchmark_arm_output_content": False,
    }
    contract = build_chat_packet_contract(
        arm="A-memory", source_manifest=manifest, memory_package=contract_memory
    )
    write_json(PACKET / "chat_packet_contract.json", contract)
    empty_state = export_adapter_state(V4MboAdapter())
    write_json(PACKET / "checkpoints" / "adapter-state-000000.json", empty_state)
    checkpoint = build_checkpoint(
        run_id=RUN_ID,
        controller="A_CHATGPT",
        memory_mode="MEMORY_ASSISTED",
        sequence=0,
        source_manifest_hash=manifest["manifest_hash"],
        completed_mbo_records=0,
        total_mbo_records=manifest["total_mbo_records"],
        event_group_open=False,
        adapter_state_hash=empty_state["state_hash"],
        controller_state_hash=contract["contract_hash"],
        previous_checkpoint_hash=None,
        phase="PRE_CALL_RT_NATIVE",
        locked=False,
    )
    write_checkpoint_atomic(PACKET / "checkpoints" / "checkpoint-000000.json", checkpoint)
    packet_id = "amemory-rtpkt-" + contract["contract_hash"][:20]
    launch = {
        "schema": "FRANKIE_A_MEMORY_RT_NATIVE_LAUNCH_V1",
        "run_id": RUN_ID,
        "lane": "REAL_TIME_FRANKIE",
        "arm": "A-memory",
        "memory_mode": "MEMORY_ASSISTED",
        "packet_id": packet_id,
        "checkpoint_id": checkpoint["checkpoint_hash"],
        "source_manifest_hash": manifest["manifest_hash"],
        "prior_memory_package_sha256": PACKAGE_SHA256,
        "prior_memory_proof_receipt_hash": PROOF_RECEIPT_HASH,
        "repository_verification_receipt_hash": REPOSITORY_RECEIPT_HASH,
        "required_starting_tip": REQUIRED_STARTING_TIP,
        "launch_commit": LAUNCH_COMMIT,
        "completed_native_mbo_records": 0,
        "total_native_mbo_records": manifest["total_mbo_records"],
        "progress_percent": 0.0,
        "rt_lane_status": "RUNNING_PRE_CALL",
        "forecaster_lane_started": False,
        "first_lock_frozen": False,
        "prior_frankie_memory_present": True,
        "native_raw_mbo_only": True,
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_required": True,
        "receipt_hash": "",
    }
    launch["receipt_hash"] = canonical_hash({k: v for k, v in launch.items() if k != "receipt_hash"})
    write_json(PACKET / "launch_receipt.json", launch)
    print(json.dumps({
        "run_id": RUN_ID,
        "packet_id": packet_id,
        "checkpoint_id": checkpoint["checkpoint_hash"],
        "source_manifest_hash": manifest["manifest_hash"],
        "memory_package_sha256": PACKAGE_SHA256,
        "progress": "0 / 5667689",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
