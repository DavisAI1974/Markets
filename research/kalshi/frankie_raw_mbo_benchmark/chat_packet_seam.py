"""Native raw-MBO contract boundary for the Chat-controlled Frankie benchmark arms.

This module is additive.  It reuses the proven two-Frankie orchestration outside
of the scientific-input boundary while requiring native Databento MBO plus the
validated V4 reconstructed full-depth/FIFO state inside that boundary.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .raw_mbo_source_manifest import ManifestError, progress_snapshot

SCHEMA = "FRANKIE_CHAT_NATIVE_RAW_MBO_PACKET_SEAM_V1"
#: The wrong-data package of run 32851909748-1. Accepted as an INERT RECORD only (D86: that
#: package is not memory; D60: its removal is a separate discussion). Nothing builds it.
MEMORY_SCHEMA = "FRANKIE_PREEXISTING_UNREVEALED_OCT45_MEMORY_V1"
#: THE SEED (D86, D88): A-memory's day-one memory is every committed output of the past runs,
#: bound by the registry's `a_memory_overlay` group and hashed over the files' bytes here.
SEED_MEMORY_SCHEMA = "FRANKIE_A_MEMORY_SEED_PACKAGE_V1"
SEED_SURFACE_LABEL = "COMMITTED_PAST_RUN_OUTPUTS"
A_MEMORY_OVERLAY_GROUP = "a_memory_overlay"
VALID_ARMS = frozenset({"A-clean", "A-memory"})
PACKET_BUILDER_REFERENCE = (
    "research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py"
)
COORDINATOR_REFERENCE = (
    "research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py"
)
NATIVE_REPLAY_REFERENCE = "research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py"
NATIVE_ADAPTER_REFERENCE = "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py"
CHECKPOINT_REFERENCE = "research/kalshi/frankie_raw_mbo_benchmark/benchmark_checkpoint.py"
RESUME_STATE_REFERENCE = "research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py"


class ChatPacketSeamError(ValueError):
    """Fail-closed violation of the Chat native raw-MBO benchmark boundary."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash_contract(value: Mapping[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "contract_hash"}
    return hashlib.sha256(_canonical(body)).hexdigest()


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in value)
    ):
        raise ChatPacketSeamError(f"{label} must be a 64-character SHA-256")
    return value.lower()


def _files_sha256(files: Any) -> str:
    """The seed package's identity: one hash over its sorted (path, bytes, sha256) rows."""
    if not isinstance(files, list) or not files:
        raise ChatPacketSeamError("seed memory package carries no files")
    rows = []
    for row in files:
        if not isinstance(row, Mapping) or set(row) != {"layer_id", "path", "bytes", "sha256"}:
            raise ChatPacketSeamError("seed memory package file row is malformed")
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise ChatPacketSeamError("seed memory package file row carries no byte count")
        rows.append({
            "layer_id": str(row["layer_id"]), "path": str(row["path"]),
            "bytes": row["bytes"], "sha256": _sha256(row["sha256"], "seed file sha256"),
        })
    rows.sort(key=lambda r: (r["path"], r["layer_id"]))
    return hashlib.sha256(_canonical({"files": rows})).hexdigest()


def seed_memory_package(registry: Mapping[str, Any], *, repo_root: Any) -> dict[str, Any]:
    """Build A-memory's memory package FROM the registry's `a_memory_overlay` bindings.

    D86/D88: the memory is the seed - committed past-run outputs, each a repository file the
    overlay group binds - so the package is derived from those bindings and hashed over the
    files' actual bytes; nothing here is typed. A layer still bound to an `external:`
    identity carries no repository bytes and is REFUSED by name: the wrong-data package is
    not memory, and a fallback to it would be exactly the silent substitution D86 ended.
    """
    from pathlib import Path

    groups = [g for g in registry.get("groups", []) if g.get("group_id") == A_MEMORY_OVERLAY_GROUP]
    if len(groups) != 1:
        raise ChatPacketSeamError(
            f"the registry must carry exactly one {A_MEMORY_OVERLAY_GROUP!r} group; found {len(groups)}"
        )
    root = Path(repo_root)
    files: list[dict[str, Any]] = []
    for entry in groups[0].get("entries", []):
        for declared in entry.get("source_paths", []):
            if str(declared).startswith("external:"):
                raise ChatPacketSeamError(
                    f"A-memory overlay layer {entry.get('layer_id')!r} binds {declared}: no "
                    "repository bytes. The wrong-data package is not memory (D86); rebind the "
                    "layer to the seed before sealing a packet."
                )
            path = root / str(declared)
            if not path.is_file():
                raise ChatPacketSeamError(
                    f"A-memory overlay layer {entry.get('layer_id')!r} binds a missing file: {declared}"
                )
            files.append({
                "layer_id": str(entry.get("layer_id")),
                "path": str(declared),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    files.sort(key=lambda r: (r["path"], r["layer_id"]))
    return {
        "schema": SEED_MEMORY_SCHEMA,
        "source_surface_label": SEED_SURFACE_LABEL,
        "package_sha256": _files_sha256(files),
        "files": files,
        "pre_existing_before_current_benchmark": True,
        "step1_or_post_reveal_content": False,
        "current_benchmark_arm_output_content": False,
    }


def _validated_memory_package(memory_package: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(memory_package, Mapping):
        raise ChatPacketSeamError("A-memory requires one hash-bound pre-existing memory package")
    required = {
        "schema",
        "source_surface_label",
        "package_sha256",
        "pre_existing_before_current_benchmark",
        "step1_or_post_reveal_content",
        "current_benchmark_arm_output_content",
    }
    schema = memory_package.get("schema")
    if schema == SEED_MEMORY_SCHEMA:
        required = required | {"files"}
    if set(memory_package) != required:
        raise ChatPacketSeamError("memory package fields are incomplete or contain passthrough data")
    if schema == SEED_MEMORY_SCHEMA:
        if memory_package["source_surface_label"] != SEED_SURFACE_LABEL:
            raise ChatPacketSeamError("seed memory package must be the committed past-run outputs")
        # The hash is RECOMPUTED over the rows, never taken on trust: a package whose stated
        # identity does not equal its files is a package from nowhere.
        if _sha256(memory_package["package_sha256"], "package_sha256") != _files_sha256(memory_package["files"]):
            raise ChatPacketSeamError("seed memory package_sha256 does not equal the hash of its files")
    elif schema != MEMORY_SCHEMA:
        raise ChatPacketSeamError("unsupported memory package schema")
    elif memory_package["source_surface_label"] != "PRIOR_REDUCED_NON_FULL_MBO_SURFACE":
        raise ChatPacketSeamError("memory package must be the allowed pre-existing reduced-surface package")
    if memory_package["pre_existing_before_current_benchmark"] is not True:
        raise ChatPacketSeamError("memory package was not proven pre-existing")
    if memory_package["step1_or_post_reveal_content"] is not False:
        raise ChatPacketSeamError("memory package contains Step-1 or post-reveal content")
    if memory_package["current_benchmark_arm_output_content"] is not False:
        raise ChatPacketSeamError("memory package contains a current benchmark arm output")
    return {
        **dict(memory_package),
        "package_sha256": _sha256(memory_package["package_sha256"], "package_sha256"),
    }


def build_chat_packet_contract(
    *,
    arm: str,
    source_manifest: Mapping[str, Any],
    memory_package: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the controller/scientific-input contract for A-clean or A-memory."""
    if arm not in VALID_ARMS:
        raise ChatPacketSeamError("Chat packet seam only accepts A-clean or A-memory")
    try:
        progress = progress_snapshot(
            source_manifest,
            completed_mbo_records=0,
            phase="PREPARED_NATIVE_RAW_MBO",
        )
    except ManifestError as exc:
        raise ChatPacketSeamError(f"invalid native raw-MBO source manifest: {exc}") from exc

    if arm == "A-clean":
        if memory_package is not None:
            raise ChatPacketSeamError("A-clean cannot receive a memory package")
        memory_mode = "CLEAN"
        bound_memory = None
    else:
        memory_mode = "MEMORY_ASSISTED"
        bound_memory = _validated_memory_package(memory_package)

    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "arm": arm,
        "controller": "A_CHATGPT",
        "memory_mode": memory_mode,
        "memory_package": bound_memory,
        "source_manifest_hash": source_manifest["manifest_hash"],
        "scientific_input": {
            "evidence_surface_label": "NATIVE_RAW_DATABENTO_MBO",
            "source_kind": "NATIVE_DBN_MBO",
            "causal_availability_clock": "ts_recv_ns",
            "canonical_source_rewritten": False,
            "native_dbn_replayable": True,
            "event_by_event_receive_order_required": True,
            "f_last_is_event_group_boundary": True,
            "raw_actions_preserved": True,
            "full_depth_required": True,
            "fifo_order_state_required": True,
            "seconds_collapse_allowed": False,
            "mbp_substitute_allowed": False,
            "step1_derived_input_allowed": False,
            "native_replay_reference": NATIVE_REPLAY_REFERENCE,
            "native_adapter_reference": NATIVE_ADAPTER_REFERENCE,
        },
        "restart_contract": {
            "checkpoint_reference": CHECKPOINT_REFERENCE,
            "resume_state_reference": RESUME_STATE_REFERENCE,
            "checkpoint_only_at_f_last_closed_group": True,
            "progress_denominator": "HASH_BOUND_NATIVE_MBO_RECORD_COUNT",
            "pre_post_expensive_call_checkpoints_required": True,
        },
        "orchestration_reuse": {
            "packet_builder_reference": PACKET_BUILDER_REFERENCE,
            "coordinator_reference": COORDINATOR_REFERENCE,
            "preserve_exact_checkout": True,
            "preserve_keyless_packet_stage": True,
            "preserve_answer_wall": True,
            "preserve_sequential_rt_then_forecaster": True,
            "preserve_first_lock_and_freeze": True,
            "preserve_source_hash_receipts": True,
            "reduced_surface_build_function_reused": False,
        },
        "blind_wall": {
            "step1_exposed": False,
            "reveal_exposed": False,
            "current_other_arm_outputs_exposed": False,
            "answer_release_authorized": False,
        },
        "progress": progress,
        "launch_authorized_by_this_contract": False,
        "contract_hash": "",
    }
    contract["contract_hash"] = _hash_contract(contract)
    return contract


def native_group_envelope(adapter: Any, frame: Mapping[str, Any]) -> dict[str, Any]:
    """Expose one F_LAST-closed native event group with exact full-depth/FIFO state."""
    if not isinstance(frame, Mapping) or frame.get("event_group_complete_f_last") is not True:
        raise ChatPacketSeamError("Chat evidence may cross only at an F_LAST-closed native event group")
    if frame.get("census_view") not in (None, "V4_NATIVE_FULL"):
        raise ChatPacketSeamError("non-native V4 census view cannot enter the Chat seam")
    if frame.get("causal_availability_clock") not in (None, "ts_recv_ns"):
        raise ChatPacketSeamError("Chat evidence must use ts_recv_ns as causal availability")
    raw_actions = frame.get("raw_actions")
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ChatPacketSeamError("native event group must preserve its raw MBO actions")
    instrument_id = frame.get("instrument_id")
    ts_recv_ns = frame.get("ts_recv_ns")
    if isinstance(instrument_id, bool) or not isinstance(instrument_id, int):
        raise ChatPacketSeamError("native event group instrument_id is invalid")
    if isinstance(ts_recv_ns, bool) or not isinstance(ts_recv_ns, int):
        raise ChatPacketSeamError("native event group ts_recv_ns is invalid")
    books = getattr(adapter, "books", None)
    if not isinstance(books, dict) or instrument_id not in books:
        raise ChatPacketSeamError("adapter does not contain the event group's reconstructed book")

    full_state = books[instrument_id].checkpoint_state(
        ts_recv_ns,
        include_full_depth=True,
        include_order_ids=True,
    )
    book = full_state.get("book", {})
    bid_levels = book.get("bid_levels_full")
    ask_levels = book.get("ask_levels_full")
    if not isinstance(bid_levels, list) or not isinstance(ask_levels, list):
        raise ChatPacketSeamError("full reconstructed depth is absent")
    if any("fifo_queue" not in level for level in [*bid_levels, *ask_levels]):
        raise ChatPacketSeamError("full FIFO queue state is absent")

    return {
        "schema": "FRANKIE_CHAT_NATIVE_RAW_MBO_GROUP_V1",
        "census_view": "V4_NATIVE_FULL",
        "instrument_id": instrument_id,
        "raw_symbol": frame.get("raw_symbol"),
        "ts_event_ns": frame.get("ts_event_ns"),
        "ts_recv_ns": ts_recv_ns,
        "causal_availability_clock": "ts_recv_ns",
        "event_group_complete_f_last": True,
        "raw_actions": list(raw_actions),
        "full_state": full_state,
        "full_depth_exposed": True,
        "fifo_order_state_exposed": True,
        "native_dbn_replayable": True,
        "seconds_collapse_used": False,
        "mbp_substitute_used": False,
        "step1_derived_input_used": False,
    }
