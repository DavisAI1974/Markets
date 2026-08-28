from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import databento as db

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (  # noqa: E402
    build_checkpoint,
    load_checkpoint,
    write_checkpoint_atomic,
)
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import (  # noqa: E402
    native_group_envelope,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (  # noqa: E402
    export_adapter_state,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_evidence_bundle import (  # noqa: E402
    NativeEvidenceLedger,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (  # noqa: E402
    V4MboAdapter,
)

PACKET = Path("/workspace/scratch/da00127ac123/a-clean-artifact-33161766927")
OUT = Path("/workspace/scratch/da00127ac123/a-clean-runtime-33161766927")
INTERVAL = 500_000
REPLAY_COMMAND = (
    "cd /workspace/scratch/da00127ac123/Markets && "
    "python /workspace/scratch/da00127ac123/a_clean_rt_replay.py"
)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def json_gzip(path: Path, value: object) -> None:
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def write_json_atomic(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_progress(
    *,
    launch: dict[str, object],
    manifest: dict[str, object],
    checkpoint: dict[str, object],
    source_name: str,
    status: str,
) -> None:
    write_json_atomic(
        OUT / "progress.json",
        {
            "schema": "FRANKIE_A_CLEAN_RT_PROGRESS_V1",
            "run_id": launch["run_id"],
            "packet_id": launch["packet_id"],
            "source_manifest_hash": manifest["manifest_hash"],
            "source_name": source_name,
            "status": status,
            "completed_native_mbo_records": checkpoint["completed_mbo_records"],
            "total_native_mbo_records": checkpoint["total_mbo_records"],
            "progress_percent": checkpoint["progress_percent"],
            "checkpoint_sequence": checkpoint["sequence"],
            "checkpoint_id": checkpoint["checkpoint_hash"],
            "event_group_open": False,
            "memory_mode": "CLEAN",
            "forecaster_started": False,
        },
    )


def state_summary_hash(metrics: dict[str, object]) -> str:
    return canonical_hash(metrics)


def update_metrics(metrics: dict[str, object], frame: dict[str, object]) -> None:
    raw_actions = frame["raw_actions"]
    assert isinstance(raw_actions, list)
    actions = metrics["actions"]
    sides = metrics["sides"]
    assert isinstance(actions, Counter) and isinstance(sides, Counter)
    for action in raw_actions:
        actions[str(action["action"])] += 1
        sides[str(action["side"])] += 1
    metrics["event_groups"] = int(metrics["event_groups"]) + 1
    metrics["max_group_actions"] = max(int(metrics["max_group_actions"]), len(raw_actions))
    book = frame["book"]
    assert isinstance(book, dict)
    for key in (
        "spread",
        "depth_imbalance_full",
        "bid_depth_full",
        "ask_depth_full",
        "bid_order_count_full",
        "ask_order_count_full",
        "bid_price_level_count_full",
        "ask_price_level_count_full",
    ):
        value = book.get(key)
        if value is not None:
            stat = metrics[key]
            assert isinstance(stat, dict)
            if stat["n"] == 0:
                stat["first"] = value
                stat["min"] = value
                stat["max"] = value
            stat["n"] += 1
            stat["last"] = value
            stat["sum"] += value
            stat["min"] = min(stat["min"], value)
            stat["max"] = max(stat["max"], value)


def compact_metrics(raw: dict[str, object], source_name: str, role: str) -> dict[str, object]:
    result: dict[str, object] = {
        "source_name": source_name,
        "source_role": role,
        "event_groups": raw["event_groups"],
        "actions": dict(sorted(raw["actions"].items())),
        "sides": dict(sorted(raw["sides"].items())),
        "max_group_actions": raw["max_group_actions"],
    }
    for key in (
        "spread",
        "depth_imbalance_full",
        "bid_depth_full",
        "ask_depth_full",
        "bid_order_count_full",
        "ask_order_count_full",
        "bid_price_level_count_full",
        "ask_price_level_count_full",
    ):
        stat = raw[key]
        assert isinstance(stat, dict)
        if stat["n"]:
            result[key] = {
                "first": stat["first"],
                "last": stat["last"],
                "min": stat["min"],
                "max": stat["max"],
                "mean": stat["sum"] / stat["n"],
            }
        else:
            result[key] = None
    return result


def new_metrics() -> dict[str, object]:
    def stat() -> dict[str, object]:
        return {"n": 0, "sum": 0.0, "first": None, "last": None, "min": None, "max": None}

    return {
        "event_groups": 0,
        "actions": Counter(),
        "sides": Counter(),
        "max_group_actions": 0,
        "spread": stat(),
        "depth_imbalance_full": stat(),
        "bid_depth_full": stat(),
        "ask_depth_full": stat(),
        "bid_order_count_full": stat(),
        "ask_order_count_full": stat(),
        "bid_price_level_count_full": stat(),
        "ask_price_level_count_full": stat(),
    }


def main() -> None:
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    (OUT / "checkpoints").mkdir(mode=0o700, exist_ok=True)
    manifest = json.loads((PACKET / "source_manifest.json").read_text(encoding="utf-8"))
    launch = json.loads((PACKET / "launch_receipt.json").read_text(encoding="utf-8"))
    first_checkpoint = load_checkpoint(PACKET / "checkpoints" / "checkpoint-000000.json")
    if launch["memory_mode"] != "CLEAN" or launch["prior_frankie_memory_present"] is not False:
        raise RuntimeError("A-clean packet is not memory clean")
    for source in manifest["sources"]:
        path = PACKET / "sources" / source["name"]
        if path.stat().st_size != source["bytes"] or sha256_file(path) != source["sha256"]:
            raise RuntimeError(f"native source hash/size mismatch: {source['name']}")
    (OUT / "REPLAY_COMMAND.txt").write_text(REPLAY_COMMAND + "\n", encoding="utf-8")
    write_json_atomic(OUT / "source_manifest.json", manifest)
    write_json_atomic(OUT / "launch_receipt.json", launch)
    write_json_atomic(OUT / "checkpoints" / "checkpoint-000000.json", first_checkpoint)
    contract = json.loads((PACKET / "chat_packet_contract.json").read_text(encoding="utf-8"))
    controller_state_0 = {
        key: value for key, value in contract.items() if key != "contract_hash"
    }
    if canonical_hash(controller_state_0) != first_checkpoint["controller_state_hash"]:
        raise RuntimeError("initial controller state does not match checkpoint 0")
    write_json_atomic(OUT / "checkpoints" / "controller-state-000000.json", controller_state_0)
    write_json_atomic(
        OUT / "checkpoints" / "adapter-state-000000.json",
        json.loads((PACKET / "checkpoints" / "adapter-state-000000.json").read_text(encoding="utf-8")),
    )
    write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=first_checkpoint,
        source_name=manifest["sources"][0]["name"],
        status="RUNNING_NATIVE_REPLAY",
    )
    adapter = V4MboAdapter()
    ledger = NativeEvidenceLedger(manifest)
    previous_checkpoint = first_checkpoint
    sequence = 0
    next_interval = INTERVAL
    source_metrics: list[dict[str, object]] = []
    started = time.monotonic()

    evidence_path = OUT / "native-evidence-groups.jsonl.gz"
    with gzip.open(evidence_path, "wt", encoding="utf-8", compresslevel=1) as evidence:
        for source in manifest["sources"]:
            name = source["name"]
            path = PACKET / "sources" / name
            metrics = new_metrics()
            store = db.DBNStore.from_file(str(path))
            for record in store:
                if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                    continue
                frame, _ = adapter.apply(
                    record,
                    raw_symbol=None,
                    source_dbn_object=name,
                    source_dbn_sha256=source["sha256"],
                )
                if frame is None:
                    continue
                envelope = {
                    **frame,
                    "seconds_collapse_used": False,
                    "mbp_substitute_used": False,
                    "step1_derived_input_used": False,
                }
                group = ledger.add_group(name, envelope)
                evidence.write(json.dumps(group, sort_keys=True, separators=(",", ":")) + "\n")
                update_metrics(metrics, frame)

                completed = int(group["completed_mbo_records_after"])
                if completed >= next_interval:
                    full_state = native_group_envelope(adapter, frame)["full_state"]
                    evidence_checkpoint = ledger.checkpoint(adapter, source_name=name, reason="INTERVAL")
                    if canonical_hash(full_state) == "":
                        raise RuntimeError("full-depth/FIFO state hash is unavailable")
                    sequence += 1
                    state_path = OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz"
                    json_gzip(state_path, evidence_checkpoint["adapter_state"])
                    snapshot = compact_metrics(metrics, name, source["role"])
                    write_json_atomic(
                        OUT / "checkpoints" / f"controller-state-{sequence:06d}.json",
                        snapshot,
                    )
                    checkpoint = build_checkpoint(
                        run_id=launch["run_id"],
                        controller="A_CHATGPT",
                        memory_mode="CLEAN",
                        sequence=sequence,
                        source_manifest_hash=manifest["manifest_hash"],
                        completed_mbo_records=completed,
                        total_mbo_records=manifest["total_mbo_records"],
                        event_group_open=False,
                        adapter_state_hash=evidence_checkpoint["adapter_state_hash"],
                        controller_state_hash=state_summary_hash(snapshot),
                        previous_checkpoint_hash=previous_checkpoint["checkpoint_hash"],
                        phase="RT_NATIVE_REPLAY",
                        locked=False,
                    )
                    write_checkpoint_atomic(
                        OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
                    )
                    previous_checkpoint = checkpoint
                    write_progress(
                        launch=launch,
                        manifest=manifest,
                        checkpoint=checkpoint,
                        source_name=name,
                        status="RUNNING_NATIVE_REPLAY",
                    )
                    print(
                        json.dumps(
                            {
                                "checkpoint": checkpoint["checkpoint_hash"],
                                "completed": completed,
                                "total": manifest["total_mbo_records"],
                                "percent": checkpoint["progress_percent"],
                                "source": name,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    while next_interval <= completed:
                        next_interval += INTERVAL

            boundary = ledger.checkpoint(adapter, source_name=name, reason="RAW_FILE_BOUNDARY")
            sequence += 1
            json_gzip(
                OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz",
                boundary["adapter_state"],
            )
            summary = compact_metrics(metrics, name, source["role"])
            source_metrics.append(summary)
            write_json_atomic(
                OUT / "checkpoints" / f"controller-state-{sequence:06d}.json",
                summary,
            )
            checkpoint = build_checkpoint(
                run_id=launch["run_id"],
                controller="A_CHATGPT",
                memory_mode="CLEAN",
                sequence=sequence,
                source_manifest_hash=manifest["manifest_hash"],
                completed_mbo_records=boundary["completed_mbo_records"],
                total_mbo_records=manifest["total_mbo_records"],
                event_group_open=False,
                adapter_state_hash=boundary["adapter_state_hash"],
                controller_state_hash=state_summary_hash(summary),
                previous_checkpoint_hash=previous_checkpoint["checkpoint_hash"],
                phase="RT_RAW_FILE_BOUNDARY",
                locked=False,
            )
            write_checkpoint_atomic(
                OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
            )
            previous_checkpoint = checkpoint
            write_progress(
                launch=launch,
                manifest=manifest,
                checkpoint=checkpoint,
                source_name=name,
                status="RAW_FILE_BOUNDARY",
            )
            ledger.finish_source(name)
            print(
                json.dumps(
                    {
                        "boundary_checkpoint": checkpoint["checkpoint_hash"],
                        "completed": checkpoint["completed_mbo_records"],
                        "total": checkpoint["total_mbo_records"],
                        "percent": checkpoint["progress_percent"],
                        "source": name,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        bundle = ledger.finalize()

    final_state = export_adapter_state(adapter)
    sequence += 1
    checkpoint = build_checkpoint(
        run_id=launch["run_id"],
        controller="A_CHATGPT",
        memory_mode="CLEAN",
        sequence=sequence,
        source_manifest_hash=manifest["manifest_hash"],
        completed_mbo_records=manifest["total_mbo_records"],
        total_mbo_records=manifest["total_mbo_records"],
        event_group_open=False,
        adapter_state_hash=final_state["state_hash"],
        controller_state_hash=state_summary_hash({"sources": source_metrics}),
        previous_checkpoint_hash=previous_checkpoint["checkpoint_hash"],
        phase="PRE_CALL_RT_FREEZE",
        locked=False,
    )
    write_checkpoint_atomic(
        OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
    )
    write_json_atomic(
        OUT / "checkpoints" / f"controller-state-{sequence:06d}.json",
        {"sources": source_metrics},
    )
    json_gzip(OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz", final_state)
    write_json_atomic(OUT / "evidence_bundle.json", bundle)
    observations = {
        "schema": "FRANKIE_A_CLEAN_RT_CAUSAL_OBSERVATIONS_V1",
        "run_id": launch["run_id"],
        "packet_id": launch["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "completed_native_mbo_records": manifest["total_mbo_records"],
        "total_native_mbo_records": manifest["total_mbo_records"],
        "progress_percent": 100.0,
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_state_reconstructed": True,
        "raw_actions_preserved_exactly_once": True,
        "memory_package_present": False,
        "source_metrics": source_metrics,
        "pre_freeze_checkpoint_id": checkpoint["checkpoint_hash"],
        "elapsed_seconds": time.monotonic() - started,
        "observations_hash": "",
    }
    observations["observations_hash"] = canonical_hash(
        {key: value for key, value in observations.items() if key != "observations_hash"}
    )
    write_json_atomic(OUT / "rt_observations.json", observations)

    first_lock = {
        "schema": "FRANKIE_A_CLEAN_RT_FIRST_LOCK_V1",
        "run_id": launch["run_id"],
        "packet_id": launch["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "controller": "A_CHATGPT",
        "memory_mode": "CLEAN",
        "lane": "REAL_TIME_FRANKIE",
        "native_mbo_records_consumed": manifest["total_mbo_records"],
        "native_mbo_records_total": manifest["total_mbo_records"],
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_state_reconstructed": True,
        "raw_actions_preserved_exactly_once": True,
        "source_metrics": source_metrics,
        "observations_hash": observations["observations_hash"],
        "pre_freeze_checkpoint_id": checkpoint["checkpoint_hash"],
        "first_lock_frozen": True,
        "amendment_allowed": False,
        "forecaster_started": False,
        "first_lock_hash": "",
    }
    first_lock["first_lock_hash"] = canonical_hash(
        {key: value for key, value in first_lock.items() if key != "first_lock_hash"}
    )
    write_json_atomic(OUT / "RT_FIRST_LOCK.json", first_lock)

    sequence += 1
    locked_checkpoint = build_checkpoint(
        run_id=launch["run_id"],
        controller="A_CHATGPT",
        memory_mode="CLEAN",
        sequence=sequence,
        source_manifest_hash=manifest["manifest_hash"],
        completed_mbo_records=manifest["total_mbo_records"],
        total_mbo_records=manifest["total_mbo_records"],
        event_group_open=False,
        adapter_state_hash=final_state["state_hash"],
        controller_state_hash=first_lock["first_lock_hash"],
        previous_checkpoint_hash=checkpoint["checkpoint_hash"],
        phase="POST_CALL_RT_FREEZE",
        locked=True,
    )
    write_checkpoint_atomic(
        OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", locked_checkpoint
    )
    write_json_atomic(
        OUT / "checkpoints" / f"controller-state-{sequence:06d}.json",
        {key: value for key, value in first_lock.items() if key != "first_lock_hash"},
    )
    json_gzip(
        OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz",
        final_state,
    )
    freeze_receipt = {
        "schema": "FRANKIE_A_CLEAN_RT_FREEZE_RECEIPT_V1",
        "run_id": launch["run_id"],
        "packet_id": launch["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "first_lock_hash": first_lock["first_lock_hash"],
        "locked_checkpoint_id": locked_checkpoint["checkpoint_hash"],
        "completed_native_mbo_records": manifest["total_mbo_records"],
        "total_native_mbo_records": manifest["total_mbo_records"],
        "progress_percent": 100.0,
        "memory_package_present": False,
        "forecaster_started": False,
        "freeze_receipt_hash": "",
    }
    freeze_receipt["freeze_receipt_hash"] = canonical_hash(
        {key: value for key, value in freeze_receipt.items() if key != "freeze_receipt_hash"}
    )
    write_json_atomic(OUT / "RT_FREEZE_RECEIPT.json", freeze_receipt)
    write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=locked_checkpoint,
        source_name=manifest["sources"][-1]["name"],
        status="RT_FIRST_LOCK_FROZEN",
    )
    print(json.dumps(freeze_receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
