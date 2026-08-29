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
    verify_chain,
    write_checkpoint_atomic,
)
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import (  # noqa: E402
    native_group_envelope,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (  # noqa: E402
    export_adapter_state,
    restore_adapter_state,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_evidence_bundle import (  # noqa: E402
    NativeEvidenceLedger,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (  # noqa: E402
    V4MboAdapter,
)

PACKET = Path("/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2")
OUT = Path("/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2")
MEMORY_PACKAGE_SHA256 = "b487acfbbea8ac8a82f42ceb555e8334057e4004740af91b9127cd2ba71e1cf8"
MEMORY_PROOF_RECEIPT_HASH = "d54c61915c0d85c8b2630eb79d5e1b8911481c80883c56d75ba815fcfab20c05"
INTERVAL = 500_000
REPLAY_COMMAND = (
    "cd /workspace/scratch/da00127ac123/Markets-c7da7d2 && "
    "python /workspace/scratch/da00127ac123/a_memory_rt_replay.py"
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
            "schema": "FRANKIE_A_MEMORY_RT_PROGRESS_V1",
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
            "memory_mode": "MEMORY_ASSISTED",
            "prior_memory_package_sha256": MEMORY_PACKAGE_SHA256,
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


def load_gzip_json(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return value


def make_evidence_checkpoint(
    *,
    manifest_hash: str,
    source_name: str,
    source_record_cursor: int,
    completed_mbo_records: int,
    completed_event_groups: int,
    reason: str,
    adapter_state: dict[str, object],
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "FRANKIE_CHAT_NATIVE_MBO_EVIDENCE_CHECKPOINT_V1",
        "source_manifest_hash": manifest_hash,
        "source_name": source_name,
        "source_record_cursor": source_record_cursor,
        "completed_mbo_records": completed_mbo_records,
        "completed_event_groups": completed_event_groups,
        "event_group_open": False,
        "reason": reason,
        "adapter_state_hash": adapter_state["state_hash"],
        "adapter_state": adapter_state,
        "full_depth_fifo_continuation_preserved": True,
        "checkpoint_hash": "",
    }
    value["checkpoint_hash"] = canonical_hash(
        {key: item for key, item in value.items() if key != "checkpoint_hash"}
    )
    return value


def evidence_descriptor(value: dict[str, object]) -> dict[str, object]:
    return {
        "source_name": value["source_name"],
        "source_record_cursor": value["source_record_cursor"],
        "completed_mbo_records": value["completed_mbo_records"],
        "reason": value["reason"],
        "adapter_state_hash": value["adapter_state_hash"],
        "checkpoint_hash": value["checkpoint_hash"],
    }


def recover_evidence_prefix(
    evidence_path: Path,
    *,
    checkpoint: dict[str, object],
    adapter_state: dict[str, object],
) -> tuple[int, int]:
    """Keep only the exactly-once group prefix closed by the selected checkpoint."""
    target = int(checkpoint["completed_mbo_records"])
    temporary = evidence_path.with_name(evidence_path.name + ".closed-prefix.tmp")
    quarantine = evidence_path.with_name(
        "native-evidence-groups.interrupted-tail-after-checkpoint-000002.jsonl.gz"
    )
    receipt_path = OUT / "resume_recovery_receipt.json"
    if quarantine.exists() and receipt_path.exists() and not temporary.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("selected_checkpoint_id") != checkpoint["checkpoint_hash"]
            or receipt.get("completed_native_mbo_records") != target
            or receipt.get("uncheckpointed_tail_used") is not False
            or receipt.get("closed_prefix_sha256") != sha256_file(evidence_path)
        ):
            raise RuntimeError("existing resume evidence recovery receipt drift")
        return int(receipt["completed_event_groups"]), int(receipt["last_ts_recv_ns"])
    if quarantine.exists() or temporary.exists() or receipt_path.exists():
        raise RuntimeError("resume evidence recovery targets are only partially present")

    completed = 0
    groups = 0
    last_recv = -1
    with gzip.open(evidence_path, "rt", encoding="utf-8") as source, gzip.open(
        temporary, "wt", encoding="utf-8", compresslevel=1
    ) as destination:
        for line in source:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError("native evidence row is not an object")
            observed_hash = row.get("group_hash")
            expected_hash = canonical_hash(
                {key: item for key, item in row.items() if key != "group_hash"}
            )
            if observed_hash != expected_hash:
                raise RuntimeError("native evidence group hash mismatch before checkpoint")
            if row.get("group_index") != groups:
                raise RuntimeError("native evidence group index discontinuity")
            if row.get("completed_mbo_records_before") != completed:
                raise RuntimeError("native evidence completed cursor discontinuity")
            after = row.get("completed_mbo_records_after")
            if isinstance(after, bool) or not isinstance(after, int) or after <= completed:
                raise RuntimeError("native evidence completed cursor is invalid")
            recv = row.get("ts_recv_ns")
            if isinstance(recv, bool) or not isinstance(recv, int) or recv < last_recv:
                raise RuntimeError("native evidence receive cursor regressed")
            if after > target:
                raise RuntimeError("checkpoint cursor is not an F_LAST-closed evidence boundary")
            destination.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            completed = after
            last_recv = recv
            groups += 1
            if completed == target:
                break

    if completed != target:
        raise RuntimeError("interrupted evidence does not reach the selected checkpoint")
    if groups != int(adapter_state["completed_event_group_count"]):
        raise RuntimeError("evidence group count does not match restored adapter state")
    os.replace(evidence_path, quarantine)
    os.replace(temporary, evidence_path)
    write_json_atomic(
        receipt_path,
        {
            "schema": "FRANKIE_A_MEMORY_RT_RESUME_RECOVERY_V1",
            "selected_checkpoint_id": checkpoint["checkpoint_hash"],
            "selected_checkpoint_sequence": checkpoint["sequence"],
            "completed_native_mbo_records": completed,
            "completed_event_groups": groups,
            "last_ts_recv_ns": last_recv,
            "quarantined_interrupted_evidence": quarantine.name,
            "closed_prefix_evidence": evidence_path.name,
            "closed_prefix_sha256": sha256_file(evidence_path),
            "uncheckpointed_tail_used": False,
        },
    )
    return groups, last_recv


def audit_prefix_and_rebuild_metrics(
    *,
    source: dict[str, object],
    target: int,
    checkpoints: dict[int, dict[str, object]],
) -> dict[str, object]:
    """Independently prove state restoration and rebuild exact summary accumulators."""
    audit = V4MboAdapter()
    metrics = new_metrics()
    path = PACKET / "sources" / str(source["name"])
    store = db.DBNStore.from_file(str(path))
    verified: set[int] = set()
    for record in store:
        if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
            continue
        frame, _ = audit.apply(
            record,
            raw_symbol=None,
            source_dbn_object=str(source["name"]),
            source_dbn_sha256=str(source["sha256"]),
        )
        if frame is not None:
            update_metrics(metrics, frame)
        cursor = int(audit.record_count)
        if cursor in checkpoints:
            expected_state = checkpoints[cursor]
            observed_state = export_adapter_state(audit)
            if observed_state != expected_state:
                raise RuntimeError(f"independent resume-state audit failed at cursor {cursor}")
            sequence = 1 if cursor < target else 2
            expected_summary = json.loads(
                (OUT / "checkpoints" / f"controller-state-{sequence:06d}.json").read_text(
                    encoding="utf-8"
                )
            )
            if compact_metrics(metrics, str(source["name"]), str(source["role"])) != expected_summary:
                raise RuntimeError(f"independent controller-state audit failed at cursor {cursor}")
            verified.add(cursor)
        if cursor == target:
            break
        if cursor > target:
            raise RuntimeError("resume cursor is not a raw-MBO boundary")
    if verified != set(checkpoints):
        raise RuntimeError("not all selected checkpoints passed independent replay audit")
    return metrics


def main() -> None:
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    (OUT / "checkpoints").mkdir(mode=0o700, exist_ok=True)
    manifest = json.loads((PACKET / "source_manifest.json").read_text(encoding="utf-8"))
    launch = json.loads((PACKET / "launch_receipt.json").read_text(encoding="utf-8"))
    first_checkpoint = load_checkpoint(PACKET / "checkpoints" / "checkpoint-000000.json")
    if launch["memory_mode"] != "MEMORY_ASSISTED" or launch["prior_frankie_memory_present"] is not True:
        raise RuntimeError("A-memory packet lacks its verified learned-output package")
    memory_proof = json.loads(
        (PACKET / "memory" / "prior-learned-package-receipt.json").read_text(encoding="utf-8")
    )
    if (
        memory_proof["package_sha256"] != MEMORY_PACKAGE_SHA256
        or memory_proof["receipt_hash"] != MEMORY_PROOF_RECEIPT_HASH
        or memory_proof["old_reduced_rows_in_package"] is not False
        or memory_proof["step1_or_post_reveal_content"] is not False
        or memory_proof["current_benchmark_arm_output_content"] is not False
    ):
        raise RuntimeError("A-memory learned-output proof drift")
    if sha256_file(PACKET / "memory" / "prior-learned-package.tgz") != MEMORY_PACKAGE_SHA256:
        raise RuntimeError("A-memory learned-output package bytes drift")
    for source in manifest["sources"]:
        path = PACKET / "sources" / source["name"]
        if path.stat().st_size != source["bytes"] or sha256_file(path) != source["sha256"]:
            raise RuntimeError(f"native source hash/size mismatch: {source['name']}")
    (OUT / "REPLAY_COMMAND.txt").write_text(REPLAY_COMMAND + "\n", encoding="utf-8")
    write_json_atomic(OUT / "source_manifest.json", manifest)
    write_json_atomic(OUT / "launch_receipt.json", launch)
    checkpoint_paths = sorted((OUT / "checkpoints").glob("checkpoint-*.json"))
    checkpoints = [load_checkpoint(path) for path in checkpoint_paths]
    verify_chain(checkpoints)
    selected = checkpoints[-1]
    if (
        selected["sequence"] != 2
        or selected["checkpoint_hash"]
        != "d03b863917ad250364729e976c6ba042555ffceb7b60c84ab7dfb530aeaf1757"
        or selected["completed_mbo_records"] != 1_000_000
        or selected["event_group_open"] is not False
        or selected["locked"] is not False
    ):
        raise RuntimeError("resume is pinned to the validated closed checkpoint sequence 2")
    state_by_cursor: dict[int, dict[str, object]] = {}
    for checkpoint in checkpoints[1:]:
        sequence_number = int(checkpoint["sequence"])
        state = load_gzip_json(
            OUT / "checkpoints" / f"adapter-state-{sequence_number:06d}.json.gz"
        )
        if state["state_hash"] != checkpoint["adapter_state_hash"]:
            raise RuntimeError("checkpoint adapter-state hash mismatch")
        controller = json.loads(
            (OUT / "checkpoints" / f"controller-state-{sequence_number:06d}.json").read_text(
                encoding="utf-8"
            )
        )
        if canonical_hash(controller) != checkpoint["controller_state_hash"]:
            raise RuntimeError("checkpoint controller-state hash mismatch")
        state_by_cursor[int(checkpoint["completed_mbo_records"])] = state

    adapter_state = state_by_cursor[int(selected["completed_mbo_records"])]
    adapter = restore_adapter_state(adapter_state)
    evidence_path = OUT / "native-evidence-groups.jsonl.gz"
    completed_groups, last_recv_ns = recover_evidence_prefix(
        evidence_path,
        checkpoint=selected,
        adapter_state=adapter_state,
    )
    first_source = manifest["sources"][0]
    metrics_at_resume = audit_prefix_and_rebuild_metrics(
        source=first_source,
        target=int(selected["completed_mbo_records"]),
        checkpoints=state_by_cursor,
    )

    evidence_checkpoints: list[dict[str, object]] = []
    for checkpoint in checkpoints[1:]:
        cursor = int(checkpoint["completed_mbo_records"])
        state = state_by_cursor[cursor]
        completed_event_groups = int(state["completed_event_group_count"])
        value = make_evidence_checkpoint(
            manifest_hash=manifest["manifest_hash"],
            source_name=first_source["name"],
            source_record_cursor=cursor,
            completed_mbo_records=cursor,
            completed_event_groups=completed_event_groups,
            reason="INTERVAL",
            adapter_state=state,
        )
        evidence_checkpoints.append(value)

    ledger = NativeEvidenceLedger(manifest)
    ledger._source_index = 0
    ledger._source_record_cursor = int(selected["completed_mbo_records"])
    ledger._completed_mbo_records = int(selected["completed_mbo_records"])
    ledger._group_count = completed_groups
    ledger._last_raw_ts_recv_ns = last_recv_ns
    ledger._current_source_group_start = 0
    ledger._source_summaries = []
    ledger._checkpoint_descriptors = [
        evidence_descriptor(value) for value in evidence_checkpoints
    ]
    ledger._last_checkpoint = evidence_checkpoints[-1]

    previous_checkpoint = selected
    sequence = int(selected["sequence"])
    next_interval = 1_500_000
    source_metrics: list[dict[str, object]] = []
    started = time.monotonic()

    write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=selected,
        source_name=first_source["name"],
        status="RESUMED_NATIVE_REPLAY",
    )
    with gzip.open(evidence_path, "at", encoding="utf-8", compresslevel=1) as evidence:
        for source_index, source in enumerate(manifest["sources"]):
            name = source["name"]
            path = PACKET / "sources" / name
            metrics = metrics_at_resume if source_index == 0 else new_metrics()
            skip_mbo_records = int(selected["completed_mbo_records"]) if source_index == 0 else 0
            seen_mbo_records = 0
            store = db.DBNStore.from_file(str(path))
            for record in store:
                if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                    continue
                if seen_mbo_records < skip_mbo_records:
                    seen_mbo_records += 1
                    continue
                seen_mbo_records += 1
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
                        memory_mode="MEMORY_ASSISTED",
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

            if seen_mbo_records != int(source["mbo_records"]):
                raise RuntimeError(
                    f"native source iteration count mismatch: {name}: "
                    f"{seen_mbo_records} != {source['mbo_records']}"
                )

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
                memory_mode="MEMORY_ASSISTED",
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
        memory_mode="MEMORY_ASSISTED",
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
        "schema": "FRANKIE_A_MEMORY_RT_CAUSAL_OBSERVATIONS_V1",
        "run_id": launch["run_id"],
        "packet_id": launch["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "completed_native_mbo_records": manifest["total_mbo_records"],
        "total_native_mbo_records": manifest["total_mbo_records"],
        "progress_percent": 100.0,
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_state_reconstructed": True,
        "raw_actions_preserved_exactly_once": True,
        "memory_package_present": True,
        "prior_memory_package_sha256": MEMORY_PACKAGE_SHA256,
        "source_metrics": source_metrics,
        "pre_freeze_checkpoint_id": checkpoint["checkpoint_hash"],
        "elapsed_seconds": time.monotonic() - started,
        "observations_hash": "",
    }
    observations["observations_hash"] = canonical_hash(
        {key: value for key, value in observations.items() if key != "observations_hash"}
    )
    write_json_atomic(OUT / "rt_observations.json", observations)

    write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=checkpoint,
        source_name=manifest["sources"][-1]["name"],
        status="READY_FOR_RT_MEMORY_REASONING",
    )
    print(
        json.dumps(
            {
                "status": "READY_FOR_RT_MEMORY_REASONING",
                "pre_call_checkpoint_id": checkpoint["checkpoint_hash"],
                "completed_native_mbo_records": manifest["total_mbo_records"],
                "total_native_mbo_records": manifest["total_mbo_records"],
                "prior_memory_package_sha256": MEMORY_PACKAGE_SHA256,
                "forecaster_started": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
