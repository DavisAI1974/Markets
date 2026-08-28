from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
import math
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
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (  # noqa: E402
    export_adapter_state,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter  # noqa: E402


PACKET = Path("/workspace/scratch/da00127ac123/a-clean-forecaster-packet-33161766927")
OUT = Path("/workspace/scratch/da00127ac123/a-clean-forecaster-runtime-33161766927")
RUN_ID = "frankie-a-clean-forecaster-33161766927-1"
INTERVAL = 500_000


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def value_hash(value: dict[str, object], field: str) -> str:
    return hashlib.sha256(canonical({k: v for k, v in value.items() if k != field})).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_gzip_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(temporary, path)


def new_stat() -> dict[str, object]:
    return {"count": 0, "sum": 0.0, "sum_sq": 0.0, "first": None, "last": None, "min": None, "max": None}


def add_stat(stat: dict[str, object], value: float | None) -> None:
    if value is None or not math.isfinite(float(value)):
        return
    x = float(value)
    if int(stat["count"]) == 0:
        stat["first"] = x
        stat["min"] = x
        stat["max"] = x
    stat["count"] = int(stat["count"]) + 1
    stat["sum"] = float(stat["sum"]) + x
    stat["sum_sq"] = float(stat["sum_sq"]) + x * x
    stat["last"] = x
    stat["min"] = min(float(stat["min"]), x)
    stat["max"] = max(float(stat["max"]), x)


def summarize_stat(stat: dict[str, object]) -> dict[str, object]:
    count = int(stat["count"])
    if count == 0:
        return {"count": 0, "first": None, "last": None, "min": None, "max": None, "mean": None, "stddev": None}
    mean = float(stat["sum"]) / count
    variance = max(0.0, float(stat["sum_sq"]) / count - mean * mean)
    return {
        "count": count,
        "first": stat["first"],
        "last": stat["last"],
        "min": stat["min"],
        "max": stat["max"],
        "mean": mean,
        "stddev": math.sqrt(variance),
    }


def new_metrics(source: dict[str, object]) -> dict[str, object]:
    return {
        "source_name": source["name"],
        "source_role": source["role"],
        "event_groups": 0,
        "native_records": 0,
        "actions": {},
        "action_qty": {},
        "action_side_qty": {},
        "trade_price": new_stat(),
        "mid": new_stat(),
        "spread": new_stat(),
        "depth_imbalance_full": new_stat(),
        "bid_depth_full": new_stat(),
        "ask_depth_full": new_stat(),
        "bid_order_count_full": new_stat(),
        "ask_order_count_full": new_stat(),
        "mid_up_moves": 0,
        "mid_down_moves": 0,
        "mid_unchanged": 0,
        "previous_mid": None,
        "first_ts_event_ns": None,
        "last_ts_event_ns": None,
        "first_ts_recv_ns": None,
        "last_ts_recv_ns": None,
    }


def bump(mapping: dict[str, object], key: str, amount: int) -> None:
    mapping[key] = int(mapping.get(key, 0)) + amount


def update_metrics(metrics: dict[str, object], group: dict[str, object], frame: dict[str, object]) -> None:
    actions = group["raw_actions"]
    metrics["event_groups"] = int(metrics["event_groups"]) + 1
    metrics["native_records"] = int(metrics["native_records"]) + len(actions)
    action_counts = metrics["actions"]
    action_qty = metrics["action_qty"]
    action_side_qty = metrics["action_side_qty"]
    assert isinstance(action_counts, dict) and isinstance(action_qty, dict) and isinstance(action_side_qty, dict)
    for action in actions:
        label = str(action["action"])
        side = str(action["side"])
        size = max(0, int(action["size"]))
        bump(action_counts, label, 1)
        bump(action_qty, label, size)
        bump(action_side_qty, f"{label}_{side}", size)
        if label == "T" and action.get("price") is not None:
            add_stat(metrics["trade_price"], float(action["price"]))
    book = frame["book"]
    mid = book.get("mid")
    add_stat(metrics["mid"], mid)
    add_stat(metrics["spread"], book.get("spread"))
    add_stat(metrics["depth_imbalance_full"], book.get("depth_imbalance_full"))
    add_stat(metrics["bid_depth_full"], book.get("bid_depth_full"))
    add_stat(metrics["ask_depth_full"], book.get("ask_depth_full"))
    add_stat(metrics["bid_order_count_full"], book.get("bid_order_count_full"))
    add_stat(metrics["ask_order_count_full"], book.get("ask_order_count_full"))
    if mid is not None and metrics["previous_mid"] is not None:
        if mid > metrics["previous_mid"]:
            metrics["mid_up_moves"] = int(metrics["mid_up_moves"]) + 1
        elif mid < metrics["previous_mid"]:
            metrics["mid_down_moves"] = int(metrics["mid_down_moves"]) + 1
        else:
            metrics["mid_unchanged"] = int(metrics["mid_unchanged"]) + 1
    if mid is not None:
        metrics["previous_mid"] = mid
    event_ns = int(group["compact_event_frame"]["ts_event_ns"])
    recv_ns = int(group["ts_recv_ns"])
    if metrics["first_ts_event_ns"] is None:
        metrics["first_ts_event_ns"] = event_ns
        metrics["first_ts_recv_ns"] = recv_ns
    metrics["last_ts_event_ns"] = event_ns
    metrics["last_ts_recv_ns"] = recv_ns


def compact_metrics(metrics: dict[str, object]) -> dict[str, object]:
    out = {k: v for k, v in metrics.items() if k not in {
        "trade_price", "mid", "spread", "depth_imbalance_full", "bid_depth_full",
        "ask_depth_full", "bid_order_count_full", "ask_order_count_full", "previous_mid",
    }}
    for key in (
        "trade_price", "mid", "spread", "depth_imbalance_full", "bid_depth_full",
        "ask_depth_full", "bid_order_count_full", "ask_order_count_full",
    ):
        out[key] = summarize_stat(metrics[key])
    trade_buy = int(metrics["action_side_qty"].get("T_B", 0))
    trade_sell = int(metrics["action_side_qty"].get("T_A", 0))
    out["trade_aggressor_imbalance"] = None if trade_buy + trade_sell == 0 else (trade_buy - trade_sell) / (trade_buy + trade_sell)
    add_qty = int(metrics["action_qty"].get("A", 0))
    cancel_qty = int(metrics["action_qty"].get("C", 0))
    out["cancel_to_add_qty"] = None if add_qty == 0 else cancel_qty / add_qty
    return out


def continuation(
    *, packet_id: str, completed: int, groups: int, source_metrics: list[dict[str, object]],
    current_metrics: dict[str, object] | None, phase: str, last_event_ns: int | None,
    last_recv_ns: int | None,
) -> dict[str, object]:
    completed_sources = [compact_metrics(row) for row in source_metrics]
    current = None if current_metrics is None else compact_metrics(current_metrics)
    value = {
        "schema": "FRANKIE_A_CLEAN_FORECASTER_CONTINUATION_V1",
        "packet_id": packet_id,
        "phase": phase,
        "completed_native_mbo_records": completed,
        "completed_event_groups": groups,
        "last_ts_event_ns": last_event_ns,
        "last_ts_recv_ns": last_recv_ns,
        "completed_source_metrics": completed_sources,
        "current_source_metrics": current,
        "hypotheses": [
            "Condition directional paths on full-depth imbalance and aggressive-flow agreement.",
            "Widen or abstain when spread, flow, and depth state conflict.",
            "Treat file/session transitions as regime boundaries rather than continuous evidence.",
        ],
        "uncertainty": [
            "No future outcome or answer-bearing surface is available.",
            "Forecast horizon extends beyond the final held-out receive watermark.",
        ],
        "continuation_hash": "",
    }
    value["continuation_hash"] = value_hash(value, "continuation_hash")
    return value


def save_checkpoint(
    *, sequence: int, previous: dict[str, object], adapter: V4MboAdapter,
    packet_id: str, manifest: dict[str, object], completed: int, groups: int,
    source_metrics: list[dict[str, object]], current_metrics: dict[str, object] | None,
    phase: str, last_event_ns: int | None, last_recv_ns: int | None,
) -> dict[str, object]:
    state = export_adapter_state(adapter)
    cont = continuation(
        packet_id=packet_id,
        completed=completed,
        groups=groups,
        source_metrics=source_metrics,
        current_metrics=current_metrics,
        phase=phase,
        last_event_ns=last_event_ns,
        last_recv_ns=last_recv_ns,
    )
    checkpoint = build_checkpoint(
        run_id=RUN_ID,
        controller="A_CHATGPT",
        memory_mode="CLEAN",
        sequence=sequence,
        source_manifest_hash=manifest["manifest_hash"],
        completed_mbo_records=completed,
        total_mbo_records=manifest["total_mbo_records"],
        event_group_open=False,
        adapter_state_hash=state["state_hash"],
        controller_state_hash=cont["continuation_hash"],
        previous_checkpoint_hash=previous["checkpoint_hash"],
        phase=phase,
        locked=False,
    )
    write_gzip_json(OUT / "checkpoints" / f"adapter-state-{sequence:06d}.json.gz", state)
    write_json(OUT / "checkpoints" / f"continuation-{sequence:06d}.json", cont)
    write_checkpoint_atomic(OUT / "checkpoints" / f"checkpoint-{sequence:06d}.json", checkpoint)
    progress = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_FORECASTER_PROGRESS_V1",
        "run_id": RUN_ID,
        "packet_id": packet_id,
        "checkpoint_sequence": sequence,
        "checkpoint_id": checkpoint["checkpoint_hash"],
        "completed_native_mbo_records": completed,
        "total_native_mbo_records": manifest["total_mbo_records"],
        "progress_percent": checkpoint["progress_percent"],
        "completed_event_groups": groups,
        "last_ts_event_ns": last_event_ns,
        "last_ts_recv_ns": last_recv_ns,
        "phase": phase,
        "memory_mode": "CLEAN",
        "memory_package_present": False,
        "answer_wall": "SEALED",
    }
    write_json(OUT / "progress.json", progress)
    print(json.dumps({"checkpoint": checkpoint["checkpoint_hash"], "sequence": sequence, "completed": completed, "percent": checkpoint["progress_percent"], "phase": phase}, sort_keys=True), flush=True)
    return checkpoint


def main() -> None:
    started = time.monotonic()
    packet = json.loads((OUT / "FORECASTER_WORK_PACKET.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACKET / "source_manifest.json").read_text(encoding="utf-8"))
    initial = load_checkpoint(OUT / "checkpoints" / "checkpoint-000000.json")
    if packet["memory_mode"] != "CLEAN" or packet["prior_reduced_surface_memory_present"] is not False:
        raise RuntimeError("A-clean Forecaster packet contains memory")
    if packet["native_mbo_records_total"] != manifest["total_mbo_records"]:
        raise RuntimeError("packet source total drift")
    adapter = V4MboAdapter()
    previous = initial
    sequence = 0
    next_interval = INTERVAL
    expected_group = 0
    completed = 0
    source_index = 0
    source_metrics: list[dict[str, object]] = []
    current_metrics = new_metrics(manifest["sources"][source_index])
    last_event_ns = None
    last_recv_ns = None

    for source_index, source in enumerate(manifest["sources"]):
        if source["name"] != current_metrics["source_name"]:
            raise RuntimeError("native source order drift")
        store = db.DBNStore.from_file(str(PACKET / "sources" / source["name"]))
        for record in store:
            if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                continue
            frame, _ = adapter.apply(
                record,
                raw_symbol=None,
                source_dbn_object=source["name"],
                source_dbn_sha256=source["sha256"],
            )
            if frame is None:
                continue
            if frame["event_group_complete_f_last"] is not True:
                raise RuntimeError("reconstructed event group did not close on F_LAST")
            group = {
                "raw_actions": frame["raw_actions"],
                "compact_event_frame": {"ts_event_ns": frame["ts_event_ns"]},
                "ts_recv_ns": frame["ts_recv_ns"],
            }
            update_metrics(current_metrics, group, frame)
            completed = int(adapter.record_count)
            expected_group += 1
            last_event_ns = int(frame["ts_event_ns"])
            last_recv_ns = int(frame["ts_recv_ns"])

            if completed >= next_interval:
                sequence += 1
                previous = save_checkpoint(
                    sequence=sequence, previous=previous, adapter=adapter, packet_id=packet["packet_id"],
                    manifest=manifest, completed=completed, groups=expected_group,
                    source_metrics=source_metrics, current_metrics=current_metrics,
                    phase="FORECASTER_NATIVE_REPLAY", last_event_ns=last_event_ns, last_recv_ns=last_recv_ns,
                )
                while next_interval <= completed:
                    next_interval += INTERVAL

        expected_source_total = sum(int(row["mbo_records"]) for row in manifest["sources"][: source_index + 1])
        if completed != expected_source_total:
            raise RuntimeError("native source record total drift")
        sequence += 1
        previous = save_checkpoint(
            sequence=sequence, previous=previous, adapter=adapter, packet_id=packet["packet_id"],
            manifest=manifest, completed=completed, groups=expected_group,
            source_metrics=source_metrics, current_metrics=current_metrics,
            phase="FORECASTER_RAW_FILE_BOUNDARY", last_event_ns=last_event_ns, last_recv_ns=last_recv_ns,
        )
        source_metrics.append(current_metrics)
        if source_index + 1 < len(manifest["sources"]):
            current_metrics = new_metrics(manifest["sources"][source_index + 1])

    if completed != manifest["total_mbo_records"]:
        raise RuntimeError("Forecaster native replay did not cover the full source roster")
    if expected_group != packet["native_event_groups_total"]:
        raise RuntimeError("Forecaster native event-group total drift")
    final_state = export_adapter_state(adapter)
    rt_final = load_checkpoint(Path("/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/checkpoints/checkpoint-000017.json"))
    if final_state["state_hash"] != rt_final["adapter_state_hash"]:
        raise RuntimeError("Forecaster independent full-depth/FIFO replay does not match frozen RT state")

    sequence += 1
    previous = save_checkpoint(
        sequence=sequence, previous=previous, adapter=adapter, packet_id=packet["packet_id"],
        manifest=manifest, completed=completed, groups=expected_group,
        source_metrics=source_metrics, current_metrics=None,
        phase="PRE_CALL_FORECASTER_MODEL", last_event_ns=last_event_ns, last_recv_ns=last_recv_ns,
    )
    observations = {
        "schema": "FRANKIE_A_CLEAN_NATIVE_FORECASTER_OBSERVATIONS_V1",
        "run_id": RUN_ID,
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
        "source_metrics": [compact_metrics(row) for row in source_metrics],
        "last_ts_event_ns": last_event_ns,
        "last_ts_recv_ns": last_recv_ns,
        "pre_model_checkpoint_id": previous["checkpoint_hash"],
        "elapsed_seconds": time.monotonic() - started,
        "observations_hash": "",
    }
    observations["observations_hash"] = value_hash(observations, "observations_hash")
    write_json(OUT / "FORECASTER_NATIVE_OBSERVATIONS.json", observations)
    print(json.dumps({"status": "FORECASTER_MODEL_READY", "pre_model_checkpoint": previous["checkpoint_hash"], "observations_hash": observations["observations_hash"], "completed": completed, "total": manifest["total_mbo_records"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
