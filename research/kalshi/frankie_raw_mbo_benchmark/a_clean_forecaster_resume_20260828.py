from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time

import databento as db

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (  # noqa: E402
    load_checkpoint,
    verify_chain,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (  # noqa: E402
    export_adapter_state,
    restore_adapter_state,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter  # noqa: E402

BASE = Path(__file__).with_name("a_clean_forecaster_replay_20260828.py")
SPEC = importlib.util.spec_from_file_location("a_clean_forecaster_base", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load original A-clean Forecaster replay")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

PACKET = base.PACKET
OUT = base.OUT
INTERVAL = base.INTERVAL
RESUME_SEQUENCE = 2


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def read_gzip_json(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"expected gzip JSON object: {path}")
    return value


def iter_mbo(source_path: Path):
    for record in db.DBNStore.from_file(str(source_path)):
        if type(record).__name__ in {"MboMsg", "MBOMsg"}:
            yield record


def apply_record(
    adapter: V4MboAdapter,
    record: object,
    source: dict[str, object],
    metrics: dict[str, object],
) -> tuple[int, int] | None:
    frame, _ = adapter.apply(
        record,
        raw_symbol=None,
        source_dbn_object=source["name"],
        source_dbn_sha256=source["sha256"],
    )
    if frame is None:
        return None
    if frame["event_group_complete_f_last"] is not True:
        raise RuntimeError("reconstructed event group did not close on F_LAST")
    group = {
        "raw_actions": frame["raw_actions"],
        "compact_event_frame": {"ts_event_ns": frame["ts_event_ns"]},
        "ts_recv_ns": frame["ts_recv_ns"],
    }
    base.update_metrics(metrics, group, frame)
    return int(frame["ts_event_ns"]), int(frame["ts_recv_ns"])


def reconstruct_controller_prefix(
    manifest: dict[str, object], cursor: int
) -> tuple[list[dict[str, object]], dict[str, object], V4MboAdapter, int, int, int]:
    """Rebuild only controller accumulators; the benchmark resumes from the frozen adapter snapshot."""
    audit_adapter = V4MboAdapter()
    completed_sources: list[dict[str, object]] = []
    groups = 0
    last_event_ns = 0
    last_recv_ns = 0
    remaining = cursor
    current: dict[str, object] | None = None

    for source in manifest["sources"]:
        current = base.new_metrics(source)
        source_consumed = 0
        for record in iter_mbo(PACKET / "sources" / source["name"]):
            if remaining == 0:
                break
            closed = apply_record(audit_adapter, record, source, current)
            source_consumed += 1
            remaining -= 1
            if closed is not None:
                groups += 1
                last_event_ns, last_recv_ns = closed
        if source_consumed == int(source["mbo_records"]):
            completed_sources.append(current)
            current = None
        if remaining == 0:
            break

    if remaining != 0 or current is None:
        raise RuntimeError("resume cursor is not inside an active source")
    if int(audit_adapter.record_count) != cursor:
        raise RuntimeError("controller prefix reconstruction cursor mismatch")
    return completed_sources, current, audit_adapter, groups, last_event_ns, last_recv_ns


def main() -> None:
    started = time.monotonic()
    packet = read_json(OUT / "FORECASTER_WORK_PACKET.json")
    manifest = read_json(PACKET / "source_manifest.json")
    if packet["memory_mode"] != "CLEAN" or packet["prior_reduced_surface_memory_present"] is not False:
        raise RuntimeError("A-clean Forecaster packet contains memory")
    if packet["native_mbo_records_total"] != manifest["total_mbo_records"]:
        raise RuntimeError("packet source total drift")

    checkpoints = [
        load_checkpoint(OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json")
        for sequence in range(RESUME_SEQUENCE + 1)
    ]
    verify_chain(checkpoints)
    previous = checkpoints[-1]
    if previous["checkpoint_hash"] != "bdb5cdaa1a06868232346fb6fe48e8e22ac10aad68af21fd64be755fc0292212":
        raise RuntimeError("unexpected A-clean Forecaster resume checkpoint")
    if previous["event_group_open"] or previous["locked"]:
        raise RuntimeError("resume checkpoint is not an unlocked F_LAST boundary")

    continuation = read_json(OUT / "checkpoints" / f"continuation-{RESUME_SEQUENCE:06d}.json")
    if base.value_hash(continuation, "continuation_hash") != continuation["continuation_hash"]:
        raise RuntimeError("controller continuation hash mismatch")
    if continuation["continuation_hash"] != previous["controller_state_hash"]:
        raise RuntimeError("controller continuation is not bound to checkpoint")
    cursor = int(previous["completed_mbo_records"])
    if int(continuation["completed_native_mbo_records"]) != cursor:
        raise RuntimeError("controller continuation cursor mismatch")

    snapshot = read_gzip_json(
        OUT / "checkpoints" / f"adapter-state-{RESUME_SEQUENCE:06d}.json.gz"
    )
    if snapshot["state_hash"] != previous["adapter_state_hash"]:
        raise RuntimeError("adapter snapshot is not bound to checkpoint")
    adapter = restore_adapter_state(snapshot)
    if int(adapter.record_count) != cursor:
        raise RuntimeError("restored adapter cursor mismatch")

    source_metrics, current_metrics, audit_adapter, expected_group, last_event_ns, last_recv_ns = (
        reconstruct_controller_prefix(manifest, cursor)
    )
    if export_adapter_state(audit_adapter)["state_hash"] != snapshot["state_hash"]:
        raise RuntimeError("resume snapshot differs from deterministic prefix replay")
    if expected_group != int(continuation["completed_event_groups"]):
        raise RuntimeError("controller event-group cursor mismatch")
    if [base.compact_metrics(row) for row in source_metrics] != continuation["completed_source_metrics"]:
        raise RuntimeError("completed-source controller state mismatch")
    if base.compact_metrics(current_metrics) != continuation["current_source_metrics"]:
        raise RuntimeError("active-source controller state mismatch")
    if last_event_ns != int(continuation["last_ts_event_ns"]) or last_recv_ns != int(continuation["last_ts_recv_ns"]):
        raise RuntimeError("controller causal watermark mismatch")

    # The audit adapter is deliberately discarded. Continuation proceeds from the exact
    # hash-bound snapshot, while the rebuilt prefix supplies the exact controller sums.
    del audit_adapter
    sequence = RESUME_SEQUENCE
    completed = cursor
    next_interval = ((completed // INTERVAL) + 1) * INTERVAL

    cumulative_before = 0
    source_index = 0
    for index, source in enumerate(manifest["sources"]):
        cumulative_after = cumulative_before + int(source["mbo_records"])
        if completed < cumulative_after:
            source_index = index
            source_local_cursor = completed - cumulative_before
            break
        cumulative_before = cumulative_after
    else:
        raise RuntimeError("resume checkpoint is already at final source boundary")
    if current_metrics["source_name"] != manifest["sources"][source_index]["name"]:
        raise RuntimeError("active source identity mismatch")

    print(json.dumps({
        "status": "RESUME_VERIFIED",
        "checkpoint": previous["checkpoint_hash"],
        "completed": completed,
        "groups": expected_group,
        "source_index": source_index,
        "source_local_cursor": source_local_cursor,
    }, sort_keys=True), flush=True)

    for index in range(source_index, len(manifest["sources"])):
        source = manifest["sources"][index]
        if index != source_index:
            current_metrics = base.new_metrics(source)
            source_local_cursor = 0
        source_seen = 0
        for record in iter_mbo(PACKET / "sources" / source["name"]):
            if source_seen < source_local_cursor:
                source_seen += 1
                continue
            closed = apply_record(adapter, record, source, current_metrics)
            source_seen += 1
            if closed is None:
                continue
            completed = int(adapter.record_count)
            expected_group += 1
            last_event_ns, last_recv_ns = closed
            if completed >= next_interval:
                sequence += 1
                previous = base.save_checkpoint(
                    sequence=sequence,
                    previous=previous,
                    adapter=adapter,
                    packet_id=packet["packet_id"],
                    manifest=manifest,
                    completed=completed,
                    groups=expected_group,
                    source_metrics=source_metrics,
                    current_metrics=current_metrics,
                    phase="FORECASTER_NATIVE_REPLAY",
                    last_event_ns=last_event_ns,
                    last_recv_ns=last_recv_ns,
                )
                while next_interval <= completed:
                    next_interval += INTERVAL

        expected_source_total = sum(
            int(row["mbo_records"]) for row in manifest["sources"][: index + 1]
        )
        if int(adapter.record_count) != expected_source_total:
            raise RuntimeError("native source record total drift")
        completed = int(adapter.record_count)
        sequence += 1
        previous = base.save_checkpoint(
            sequence=sequence,
            previous=previous,
            adapter=adapter,
            packet_id=packet["packet_id"],
            manifest=manifest,
            completed=completed,
            groups=expected_group,
            source_metrics=source_metrics,
            current_metrics=current_metrics,
            phase="FORECASTER_RAW_FILE_BOUNDARY",
            last_event_ns=last_event_ns,
            last_recv_ns=last_recv_ns,
        )
        source_metrics.append(current_metrics)

    if completed != int(manifest["total_mbo_records"]):
        raise RuntimeError("Forecaster native replay did not cover full source roster")
    if expected_group != int(packet["native_event_groups_total"]):
        raise RuntimeError("Forecaster native event-group total drift")
    final_state = export_adapter_state(adapter)
    rt_final = load_checkpoint(
        Path("/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/checkpoints/checkpoint-000017.json")
    )
    if final_state["state_hash"] != rt_final["adapter_state_hash"]:
        raise RuntimeError("Forecaster replay does not match frozen RT state")

    sequence += 1
    previous = base.save_checkpoint(
        sequence=sequence,
        previous=previous,
        adapter=adapter,
        packet_id=packet["packet_id"],
        manifest=manifest,
        completed=completed,
        groups=expected_group,
        source_metrics=source_metrics,
        current_metrics=None,
        phase="PRE_CALL_FORECASTER_MODEL",
        last_event_ns=last_event_ns,
        last_recv_ns=last_recv_ns,
    )
    observations = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_FORECASTER_OBSERVATIONS_V1",
        "run_id": base.RUN_ID,
        "packet_id": packet["packet_id"],
        "source_manifest_hash": manifest["manifest_hash"],
        "frozen_rt_state_hash": packet["authoritative_frozen_rt_state_hash"],
        "native_mbo_records_consumed": completed,
        "native_mbo_records_total": manifest["total_mbo_records"],
        "completed_event_groups": expected_group,
        "causal_clock": "ts_recv_ns",
        "full_depth_fifo_state_reconstructed": True,
        "raw_actions_preserved_exactly_once": True,
        "independent_replay_final_adapter_state_hash": final_state["state_hash"],
        "matches_frozen_rt_adapter_state": True,
        "memory_mode": "CLEAN",
        "memory_package_present": False,
        "source_metrics": [base.compact_metrics(row) for row in source_metrics],
        "last_ts_event_ns": last_event_ns,
        "last_ts_recv_ns": last_recv_ns,
        "pre_model_checkpoint_id": previous["checkpoint_hash"],
        "elapsed_seconds": time.monotonic() - started,
        "observations_hash": "",
    }
    observations["observations_hash"] = base.value_hash(observations, "observations_hash")
    base.write_json(OUT / "FORECASTER_NATIVE_OBSERVATIONS.json", observations)
    print(json.dumps({
        "status": "FORECASTER_MODEL_READY",
        "pre_model_checkpoint": previous["checkpoint_hash"],
        "observations_hash": observations["observations_hash"],
        "completed": completed,
        "total": manifest["total_mbo_records"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
