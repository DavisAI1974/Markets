"""Resume the existing A-memory diagnostic replay from its latest closed checkpoint.

This recovery runner deliberately completes only the native evidence replay.  It
does not claim to call Real-Time Frankie, create a scientific first lock, freeze
RT knowledge, or authorize the Forecaster.
"""
from __future__ import annotations

from collections import Counter
import gzip
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterator

import databento as db

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark import a_memory_rt_resume_20260828 as base  # noqa: E402
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
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter  # noqa: E402

PACKET = base.PACKET
OUT = base.OUT
INTERVAL = base.INTERVAL
REPLAY_COMMAND = f"cd {REPO} && python {Path(__file__).resolve()}"


def iter_mbo(path: Path) -> Iterator[Any]:
    for record in db.DBNStore.from_file(str(path)):
        if type(record).__name__ in {"MboMsg", "MBOMsg"}:
            yield record


def source_position(
    manifest: dict[str, Any], completed: int
) -> tuple[int, int, bool]:
    """Return source index, local cursor, and whether cursor is a file boundary."""
    cumulative = 0
    sources = manifest["sources"]
    for index, source in enumerate(sources):
        count = int(source["mbo_records"])
        boundary = cumulative + count
        if completed < boundary:
            return index, completed - cumulative, False
        if completed == boundary:
            return index, count, True
        cumulative = boundary
    if completed == int(manifest["total_mbo_records"]):
        return len(sources) - 1, int(sources[-1]["mbo_records"]), True
    raise RuntimeError("completed cursor is outside source manifest")


def checkpoint_source(
    manifest: dict[str, Any], completed: int
) -> tuple[dict[str, Any], int]:
    index, local, _ = source_position(manifest, completed)
    return manifest["sources"][index], local


def load_runtime_chain() -> tuple[
    list[dict[str, Any]], dict[int, dict[str, Any]], dict[int, dict[str, Any]]
]:
    paths = sorted((OUT / "checkpoints").glob("checkpoint-*.json"))
    checkpoints = [load_checkpoint(path) for path in paths]
    verify_chain(checkpoints)
    if checkpoints[0]["sequence"] != 0:
        raise RuntimeError("runtime checkpoint chain does not start at zero")

    states: dict[int, dict[str, Any]] = {}
    controllers: dict[int, dict[str, Any]] = {}
    for checkpoint in checkpoints[1:]:
        sequence = int(checkpoint["sequence"])
        state = base.load_gzip_json(
            OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz"
        )
        if state["state_hash"] != checkpoint["adapter_state_hash"]:
            raise RuntimeError(f"adapter-state hash mismatch at sequence {sequence}")
        controller = json.loads(
            (OUT / "checkpoints" / f"controller-state-{sequence:06d}.json").read_text(
                encoding="utf-8"
            )
        )
        if base.canonical_hash(controller) != checkpoint["controller_state_hash"]:
            raise RuntimeError(f"controller-state hash mismatch at sequence {sequence}")
        states[sequence] = state
        controllers[sequence] = controller
    return checkpoints, states, controllers


def audit_and_rebuild_prefix(
    manifest: dict[str, Any],
    selected: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    states: dict[int, dict[str, Any]],
    controllers: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int, int]:
    """Replay the entire prefix and prove every saved adapter/controller snapshot."""
    target = int(selected["completed_mbo_records"])
    by_cursor = {
        int(checkpoint["completed_mbo_records"]): checkpoint
        for checkpoint in checkpoints[1:]
        if int(checkpoint["completed_mbo_records"]) <= target
    }
    audit = V4MboAdapter()
    completed_metrics: list[dict[str, Any]] = []
    current_metrics: dict[str, Any] | None = None
    verified_sequences: set[int] = set()
    last_event_ns = 0
    last_recv_ns = 0

    for source in manifest["sources"]:
        metrics = base.new_metrics()
        consumed = 0
        for record in iter_mbo(PACKET / "sources" / source["name"]):
            if int(audit.record_count) == target:
                break
            frame, _ = audit.apply(
                record,
                raw_symbol=None,
                source_dbn_object=source["name"],
                source_dbn_sha256=source["sha256"],
            )
            consumed += 1
            if frame is not None:
                base.update_metrics(metrics, frame)
                last_event_ns = int(frame["ts_event_ns"])
                last_recv_ns = int(frame["ts_recv_ns"])

            cursor = int(audit.record_count)
            checkpoint = by_cursor.get(cursor)
            if checkpoint is not None:
                sequence = int(checkpoint["sequence"])
                observed = export_adapter_state(audit)
                if observed != states[sequence]:
                    raise RuntimeError(
                        f"independent adapter-prefix audit failed at sequence {sequence}"
                    )
                expected_controller = base.compact_metrics(
                    metrics, str(source["name"]), str(source["role"])
                )
                if expected_controller != controllers[sequence]:
                    raise RuntimeError(
                        f"independent controller-prefix audit failed at sequence {sequence}"
                    )
                verified_sequences.add(sequence)

        if int(audit.record_count) == target:
            if consumed == int(source["mbo_records"]):
                completed_metrics.append(metrics)
                current_metrics = None
            else:
                current_metrics = metrics
            break
        if consumed != int(source["mbo_records"]):
            raise RuntimeError("prefix audit stopped before a declared source boundary")
        completed_metrics.append(metrics)

    expected_sequences = {int(row["sequence"]) for row in checkpoints[1:]}
    if verified_sequences != expected_sequences:
        raise RuntimeError(
            "not every checkpoint passed prefix audit: "
            f"verified={sorted(verified_sequences)} expected={sorted(expected_sequences)}"
        )
    if export_adapter_state(audit) != states[int(selected["sequence"])]:
        raise RuntimeError("selected adapter snapshot differs from deterministic prefix")
    _, _, at_boundary = source_position(manifest, target)
    if at_boundary and current_metrics is not None:
        raise RuntimeError("boundary prefix unexpectedly retained active-source metrics")
    if not at_boundary and current_metrics is None:
        raise RuntimeError("mid-source prefix lacks active-source metrics")
    return completed_metrics, current_metrics, last_event_ns, last_recv_ns


def recover_evidence_prefix(
    manifest: dict[str, Any],
    selected: dict[str, Any],
    selected_state: dict[str, Any],
) -> tuple[int, int, list[int]]:
    """Quarantine the interrupted ledger and retain only the selected closed prefix."""
    sequence = int(selected["sequence"])
    target = int(selected["completed_mbo_records"])
    evidence_path = OUT / "native-evidence-groups.jsonl.gz"
    temporary = OUT / f"native-evidence-groups.closed-prefix-{sequence:06d}.tmp.gz"
    quarantine = OUT / (
        f"native-evidence-groups.interrupted-tail-after-checkpoint-{sequence:06d}.jsonl.gz"
    )
    receipt_path = OUT / f"resume-recovery-receipt-{sequence:06d}.json"
    if temporary.exists() or quarantine.exists() or receipt_path.exists():
        raise RuntimeError("sequence-specific evidence recovery targets already exist")

    completed = 0
    groups = 0
    last_recv = -1
    source_group_counts = [0 for _ in manifest["sources"]]
    source_index = 0
    source_local = 0
    reached = False
    with gzip.open(evidence_path, "rt", encoding="utf-8") as source_handle, gzip.open(
        temporary, "wt", encoding="utf-8", compresslevel=1
    ) as destination:
        for line in source_handle:
            row = json.loads(line)
            observed_hash = row.get("group_hash")
            expected_hash = base.canonical_hash(
                {key: value for key, value in row.items() if key != "group_hash"}
            )
            if observed_hash != expected_hash:
                raise RuntimeError("native evidence group hash mismatch")
            if row.get("group_index") != groups:
                raise RuntimeError("native evidence group-index discontinuity")
            if row.get("completed_mbo_records_before") != completed:
                raise RuntimeError("native evidence global cursor discontinuity")
            expected_source = manifest["sources"][source_index]
            if row.get("source_name") != expected_source["name"]:
                raise RuntimeError("native evidence source order drift")
            if row.get("source_record_start") != source_local:
                raise RuntimeError("native evidence source cursor discontinuity")
            after = row.get("completed_mbo_records_after")
            source_end = row.get("source_record_end_exclusive")
            recv = row.get("ts_recv_ns")
            if not isinstance(after, int) or after <= completed or after > target:
                if completed == target:
                    reached = True
                    break
                raise RuntimeError("selected checkpoint is not a closed evidence boundary")
            if not isinstance(source_end, int) or source_end <= source_local:
                raise RuntimeError("native evidence source end cursor is invalid")
            if source_end - source_local != after - completed:
                raise RuntimeError("native evidence local/global cursor delta mismatch")
            if not isinstance(recv, int) or recv < last_recv:
                raise RuntimeError("native evidence receive watermark regressed")
            destination.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            completed = after
            source_local = source_end
            last_recv = recv
            groups += 1
            source_group_counts[source_index] += 1
            if source_local == int(expected_source["mbo_records"]):
                source_index += 1
                source_local = 0
            if completed == target:
                reached = True
                break

    if not reached or completed != target:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("interrupted evidence does not reach selected checkpoint")
    if groups != int(selected_state["completed_event_group_count"]):
        temporary.unlink(missing_ok=True)
        raise RuntimeError("evidence group count differs from selected adapter state")

    os.replace(evidence_path, quarantine)
    os.replace(temporary, evidence_path)
    base.write_json_atomic(
        receipt_path,
        {
            "schema": "FRANKIE_A_MEMORY_RT_RESUME_RECOVERY_V2",
            "selected_checkpoint_id": selected["checkpoint_hash"],
            "selected_checkpoint_sequence": sequence,
            "completed_native_mbo_records": completed,
            "completed_event_groups": groups,
            "last_ts_recv_ns": last_recv,
            "source_group_counts": source_group_counts,
            "quarantined_interrupted_evidence": quarantine.name,
            "closed_prefix_evidence": evidence_path.name,
            "closed_prefix_sha256": base.sha256_file(evidence_path),
            "uncheckpointed_tail_used": False,
        },
    )
    return groups, last_recv, source_group_counts


def rebuild_ledger(
    manifest: dict[str, Any],
    selected: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    states: dict[int, dict[str, Any]],
    group_count: int,
    last_recv_ns: int,
    source_group_counts: list[int],
) -> NativeEvidenceLedger:
    target = int(selected["completed_mbo_records"])
    evidence_checkpoints: list[dict[str, Any]] = []
    boundary_by_source: dict[str, dict[str, Any]] = {}
    for checkpoint in checkpoints[1:]:
        source, local_cursor = checkpoint_source(
            manifest, int(checkpoint["completed_mbo_records"])
        )
        reason = (
            "RAW_FILE_BOUNDARY"
            if checkpoint["phase"] == "RT_RAW_FILE_BOUNDARY"
            else "INTERVAL"
        )
        sequence = int(checkpoint["sequence"])
        value = base.make_evidence_checkpoint(
            manifest_hash=manifest["manifest_hash"],
            source_name=source["name"],
            source_record_cursor=local_cursor,
            completed_mbo_records=int(checkpoint["completed_mbo_records"]),
            completed_event_groups=int(states[sequence]["completed_event_group_count"]),
            reason=reason,
            adapter_state=states[sequence],
        )
        evidence_checkpoints.append(value)
        if reason == "RAW_FILE_BOUNDARY":
            boundary_by_source[source["name"]] = value

    active_index, local_cursor, at_boundary = source_position(manifest, target)
    completed_source_count = active_index + 1 if at_boundary else active_index
    summaries: list[dict[str, Any]] = []
    group_start = 0
    for index in range(completed_source_count):
        source = manifest["sources"][index]
        boundary = boundary_by_source.get(source["name"])
        if boundary is None:
            raise RuntimeError("completed source lacks reconstructed boundary checkpoint")
        count = source_group_counts[index]
        summaries.append(
            {
                "name": source["name"],
                "date": source["date"],
                "role": source["role"],
                "sha256": source["sha256"],
                "mbo_records": int(source["mbo_records"]),
                "first_group_index": group_start,
                "group_count": count,
                "boundary_checkpoint_hash": boundary["checkpoint_hash"],
            }
        )
        group_start += count

    ledger = NativeEvidenceLedger(manifest)
    ledger._source_index = completed_source_count
    ledger._source_record_cursor = 0 if at_boundary else local_cursor
    ledger._completed_mbo_records = target
    ledger._group_count = group_count
    ledger._last_raw_ts_recv_ns = last_recv_ns
    ledger._current_source_group_start = group_start
    ledger._source_summaries = summaries
    ledger._checkpoint_descriptors = [
        base.evidence_descriptor(value) for value in evidence_checkpoints
    ]
    ledger._last_checkpoint = None if at_boundary else evidence_checkpoints[-1]
    return ledger


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((PACKET / "source_manifest.json").read_text(encoding="utf-8"))
    launch = json.loads((PACKET / "launch_receipt.json").read_text(encoding="utf-8"))
    if launch["memory_mode"] != "MEMORY_ASSISTED" or launch["prior_frankie_memory_present"] is not True:
        raise RuntimeError("A-memory packet lacks its verified learned-output package")
    proof = json.loads(
        (PACKET / "memory" / "prior-learned-package-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        proof["package_sha256"] != base.MEMORY_PACKAGE_SHA256
        or proof["receipt_hash"] != base.MEMORY_PROOF_RECEIPT_HASH
        or proof["old_reduced_rows_in_package"] is not False
        or proof["step1_or_post_reveal_content"] is not False
        or proof["current_benchmark_arm_output_content"] is not False
    ):
        raise RuntimeError("A-memory learned-output proof drift")
    package = PACKET / "memory" / "prior-learned-package.tgz"
    if base.sha256_file(package) != base.MEMORY_PACKAGE_SHA256:
        raise RuntimeError("A-memory learned-output package bytes drift")
    for source in manifest["sources"]:
        path = PACKET / "sources" / source["name"]
        if path.stat().st_size != source["bytes"] or base.sha256_file(path) != source["sha256"]:
            raise RuntimeError(f"native source hash/size mismatch: {source['name']}")
    return manifest, launch


def main() -> None:
    started = time.monotonic()
    manifest, launch = verify_inputs()
    checkpoints, states, controllers = load_runtime_chain()
    selected = checkpoints[-1]
    if (
        selected["run_id"] != launch["run_id"]
        or selected["source_manifest_hash"] != manifest["manifest_hash"]
        or selected["memory_mode"] != "MEMORY_ASSISTED"
        or selected["event_group_open"] is not False
        or selected["locked"] is not False
        or int(selected["completed_mbo_records"]) >= int(manifest["total_mbo_records"])
    ):
        raise RuntimeError("latest checkpoint is not an eligible closed A-memory resume point")

    completed_metrics, current_metrics, last_event_ns, last_recv_ns = audit_and_rebuild_prefix(
        manifest, selected, checkpoints, states, controllers
    )
    selected_sequence = int(selected["sequence"])
    selected_state = states[selected_sequence]
    adapter = restore_adapter_state(selected_state)
    groups, ledger_last_recv, source_group_counts = recover_evidence_prefix(
        manifest, selected, selected_state
    )
    if ledger_last_recv != last_recv_ns:
        raise RuntimeError("evidence and deterministic replay receive watermarks differ")
    ledger = rebuild_ledger(
        manifest,
        selected,
        checkpoints,
        states,
        groups,
        ledger_last_recv,
        source_group_counts,
    )

    previous = selected
    sequence = selected_sequence
    completed = int(selected["completed_mbo_records"])
    next_interval = ((completed // INTERVAL) + 1) * INTERVAL
    active_index, local_cursor, at_boundary = source_position(manifest, completed)
    start_index = active_index + 1 if at_boundary else active_index
    source_metrics = completed_metrics
    evidence_path = OUT / "native-evidence-groups.jsonl.gz"
    (OUT / "REPLAY_COMMAND.txt").write_text(REPLAY_COMMAND + "\n", encoding="utf-8")
    base.write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=selected,
        source_name=manifest["sources"][start_index]["name"],
        status="RESUME_AUDIT_PASSED",
    )
    print(
        json.dumps(
            {
                "status": "RESUME_AUDIT_PASSED",
                "checkpoint": selected["checkpoint_hash"],
                "sequence": selected_sequence,
                "completed": completed,
                "groups": groups,
                "source_index": start_index,
                "source_local_cursor": 0 if at_boundary else local_cursor,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    with gzip.open(evidence_path, "at", encoding="utf-8", compresslevel=1) as evidence:
        for index in range(start_index, len(manifest["sources"])):
            source = manifest["sources"][index]
            if index == start_index and not at_boundary:
                if current_metrics is None:
                    raise RuntimeError("active source metrics are absent after prefix audit")
                metrics = current_metrics
                skip = local_cursor
            else:
                metrics = base.new_metrics()
                skip = 0

            seen = 0
            for record in iter_mbo(PACKET / "sources" / source["name"]):
                if seen < skip:
                    seen += 1
                    continue
                seen += 1
                frame, _ = adapter.apply(
                    record,
                    raw_symbol=None,
                    source_dbn_object=source["name"],
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
                group = ledger.add_group(source["name"], envelope)
                evidence.write(json.dumps(group, sort_keys=True, separators=(",", ":")) + "\n")
                base.update_metrics(metrics, frame)
                last_event_ns = int(frame["ts_event_ns"])
                last_recv_ns = int(frame["ts_recv_ns"])
                completed = int(group["completed_mbo_records_after"])

                if completed >= next_interval:
                    full_state = native_group_envelope(adapter, frame)["full_state"]
                    evidence_checkpoint = ledger.checkpoint(
                        adapter, source_name=source["name"], reason="INTERVAL"
                    )
                    if not base.canonical_hash(full_state):
                        raise RuntimeError("full-depth/FIFO state hash is unavailable")
                    sequence += 1
                    base.json_gzip(
                        OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz",
                        evidence_checkpoint["adapter_state"],
                    )
                    snapshot = base.compact_metrics(metrics, source["name"], source["role"])
                    base.write_json_atomic(
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
                        controller_state_hash=base.state_summary_hash(snapshot),
                        previous_checkpoint_hash=previous["checkpoint_hash"],
                        phase="RT_NATIVE_REPLAY",
                        locked=False,
                    )
                    write_checkpoint_atomic(
                        OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
                    )
                    previous = checkpoint
                    base.write_progress(
                        launch=launch,
                        manifest=manifest,
                        checkpoint=checkpoint,
                        source_name=source["name"],
                        status="RUNNING_NATIVE_REPLAY",
                    )
                    print(
                        json.dumps(
                            {
                                "checkpoint": checkpoint["checkpoint_hash"],
                                "completed": completed,
                                "total": manifest["total_mbo_records"],
                                "percent": checkpoint["progress_percent"],
                                "source": source["name"],
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    while next_interval <= completed:
                        next_interval += INTERVAL

            if seen != int(source["mbo_records"]):
                raise RuntimeError(f"native source iteration count mismatch: {source['name']}")
            boundary = ledger.checkpoint(
                adapter, source_name=source["name"], reason="RAW_FILE_BOUNDARY"
            )
            sequence += 1
            base.json_gzip(
                OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz",
                boundary["adapter_state"],
            )
            summary = base.compact_metrics(metrics, source["name"], source["role"])
            base.write_json_atomic(
                OUT / "checkpoints" / f"controller-state-{sequence:06d}.json", summary
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
                controller_state_hash=base.state_summary_hash(summary),
                previous_checkpoint_hash=previous["checkpoint_hash"],
                phase="RT_RAW_FILE_BOUNDARY",
                locked=False,
            )
            write_checkpoint_atomic(
                OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
            )
            previous = checkpoint
            ledger.finish_source(source["name"])
            source_metrics.append(metrics)
            base.write_progress(
                launch=launch,
                manifest=manifest,
                checkpoint=checkpoint,
                source_name=source["name"],
                status="RAW_FILE_BOUNDARY",
            )
            print(
                json.dumps(
                    {
                        "boundary_checkpoint": checkpoint["checkpoint_hash"],
                        "completed": checkpoint["completed_mbo_records"],
                        "total": checkpoint["total_mbo_records"],
                        "percent": checkpoint["progress_percent"],
                        "source": source["name"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        bundle = ledger.finalize()

    if completed != int(manifest["total_mbo_records"]):
        raise RuntimeError("replay did not reconcile to source-manifest total")
    final_state = export_adapter_state(adapter)
    sequence += 1
    final_controller = {
        "sources": [
            base.compact_metrics(row, source["name"], source["role"])
            for row, source in zip(source_metrics, manifest["sources"])
        ]
    }
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
        controller_state_hash=base.state_summary_hash(final_controller),
        previous_checkpoint_hash=previous["checkpoint_hash"],
        phase="RT_NATIVE_REPLAY_COMPLETE",
        locked=False,
    )
    base.json_gzip(
        OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz", final_state
    )
    base.write_json_atomic(
        OUT / "checkpoints" / f"controller-state-{sequence:06d}.json", final_controller
    )
    write_checkpoint_atomic(
        OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint
    )
    base.write_json_atomic(OUT / "evidence_bundle.json", bundle)
    observations = {
        "schema": "FRANKIE_A_MEMORY_RT_DIAGNOSTIC_REPLAY_OBSERVATIONS_V2",
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
        "prior_memory_package_sha256": base.MEMORY_PACKAGE_SHA256,
        "source_metrics": final_controller["sources"],
        "diagnostic_replay_checkpoint_id": checkpoint["checkpoint_hash"],
        "scientific_frankie_lock_created": False,
        "scientific_rt_freeze_created": False,
        "forecaster_authorized": False,
        "last_ts_event_ns": last_event_ns,
        "last_ts_recv_ns": last_recv_ns,
        "elapsed_seconds": time.monotonic() - started,
        "observations_hash": "",
    }
    observations["observations_hash"] = base.canonical_hash(
        {key: value for key, value in observations.items() if key != "observations_hash"}
    )
    base.write_json_atomic(OUT / "rt_observations.json", observations)
    base.write_progress(
        launch=launch,
        manifest=manifest,
        checkpoint=checkpoint,
        source_name=manifest["sources"][-1]["name"],
        status="READY_FOR_POSITIVE_DERIVATION",
    )
    print(
        json.dumps(
            {
                "status": "READY_FOR_POSITIVE_DERIVATION",
                "diagnostic_replay_checkpoint": checkpoint["checkpoint_hash"],
                "completed": manifest["total_mbo_records"],
                "total": manifest["total_mbo_records"],
                "scientific_frankie_lock_created": False,
                "scientific_rt_freeze_created": False,
                "forecaster_authorized": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
