"""Lossless native-MBO evidence ledger for the Chat-controlled Frankie arms.

Raw MBO actions are retained exactly once in F_LAST-closed group records. Exact
adapter continuation state is checkpointed separately, so full depth/FIFO state
can be reconstructed without serializing the entire book into every group row.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .mbo_resume_state import ResumeStateError, export_adapter_state
from .raw_mbo_source_manifest import ManifestError, progress_snapshot

SCHEMA = "FRANKIE_CHAT_NATIVE_MBO_EVIDENCE_BUNDLE_V1"
GROUP_SCHEMA = "FRANKIE_CHAT_NATIVE_MBO_EVIDENCE_GROUP_V1"
CHECKPOINT_SCHEMA = "FRANKIE_CHAT_NATIVE_MBO_EVIDENCE_CHECKPOINT_V1"
_ALLOWED_CHECKPOINT_REASONS = frozenset(
    {"INTERVAL", "RAW_FILE_BOUNDARY", "PRE_EXPENSIVE_CALL", "POST_EXPENSIVE_CALL"}
)


class NativeEvidenceBundleError(ValueError):
    """Fail-closed native evidence bundle contract violation."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash(value: Mapping[str, Any], field: str) -> str:
    body = {key: item for key, item in value.items() if key != field}
    return hashlib.sha256(_canonical(body)).hexdigest()


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NativeEvidenceBundleError(f"{label} must be a nonnegative integer")
    return value


class NativeEvidenceLedger:
    """Track exact raw-action/group/checkpoint cursors against one source manifest."""

    def __init__(self, source_manifest: Mapping[str, Any]) -> None:
        try:
            progress_snapshot(
                source_manifest,
                completed_mbo_records=0,
                phase="NATIVE_EVIDENCE_BUNDLE_PREPARED",
            )
        except ManifestError as exc:
            raise NativeEvidenceBundleError(f"invalid native source manifest: {exc}") from exc
        self.source_manifest = dict(source_manifest)
        self._sources = [dict(row) for row in source_manifest["sources"]]
        self._source_index = 0
        self._source_record_cursor = 0
        self._completed_mbo_records = 0
        self._group_count = 0
        self._last_raw_ts_recv_ns: int | None = None
        self._current_source_group_start = 0
        self._source_summaries: list[dict[str, Any]] = []
        self._checkpoint_descriptors: list[dict[str, Any]] = []
        self._last_checkpoint: dict[str, Any] | None = None

    def _current_source(self) -> dict[str, Any]:
        if self._source_index >= len(self._sources):
            raise NativeEvidenceBundleError("all hash-bound native sources are already complete")
        return self._sources[self._source_index]

    def _require_current_source(self, source_name: str) -> dict[str, Any]:
        source = self._current_source()
        if source_name != source["name"]:
            raise NativeEvidenceBundleError(
                f"native source order drift: expected {source['name']}, got {source_name}"
            )
        return source

    def add_group(self, source_name: str, envelope: Mapping[str, Any]) -> dict[str, Any]:
        source = self._require_current_source(source_name)
        if not isinstance(envelope, Mapping):
            raise NativeEvidenceBundleError("native event-group envelope must be an object")
        if envelope.get("event_group_complete_f_last") is not True:
            raise NativeEvidenceBundleError("evidence group must be F_LAST closed")
        if envelope.get("census_view") != "V4_NATIVE_FULL":
            raise NativeEvidenceBundleError("evidence group must be V4_NATIVE_FULL")
        if envelope.get("causal_availability_clock") != "ts_recv_ns":
            raise NativeEvidenceBundleError("evidence group causal clock must be ts_recv_ns")
        if envelope.get("seconds_collapse_used") is not False:
            raise NativeEvidenceBundleError("seconds-collapsed evidence cannot enter the native bundle")
        if envelope.get("mbp_substitute_used") is not False:
            raise NativeEvidenceBundleError("MBP substitute cannot enter the native bundle")
        if envelope.get("step1_derived_input_used") is not False:
            raise NativeEvidenceBundleError("Step-1-derived evidence cannot enter the native bundle")

        raw_actions = envelope.get("raw_actions")
        if not isinstance(raw_actions, list) or not raw_actions:
            raise NativeEvidenceBundleError("native event group has no raw MBO actions")
        if raw_actions[-1].get("is_last") is not True:
            raise NativeEvidenceBundleError("native event group does not terminate on F_LAST")
        action_recv: list[int] = []
        for index, action in enumerate(raw_actions):
            if not isinstance(action, Mapping):
                raise NativeEvidenceBundleError(f"raw MBO action {index} is malformed")
            recv = action.get("ts_recv_ns")
            if isinstance(recv, bool) or not isinstance(recv, int):
                raise NativeEvidenceBundleError(f"raw MBO action {index} lacks ts_recv_ns")
            action_recv.append(recv)
        if action_recv != sorted(action_recv):
            raise NativeEvidenceBundleError("raw MBO actions are not in receive-time causal order")
        if self._last_raw_ts_recv_ns is not None and action_recv[0] < self._last_raw_ts_recv_ns:
            raise NativeEvidenceBundleError("raw MBO receive-time cursor regressed across groups")

        group_recv = envelope.get("ts_recv_ns")
        if isinstance(group_recv, bool) or not isinstance(group_recv, int) or group_recv != action_recv[-1]:
            raise NativeEvidenceBundleError("event-group receive watermark does not match final raw action")
        expected = int(source["mbo_records"])
        next_source_cursor = self._source_record_cursor + len(raw_actions)
        if next_source_cursor > expected:
            raise NativeEvidenceBundleError("native source emitted more MBO records than its hash-bound count")

        compact_event_frame = {
            "census_view": "V4_NATIVE_FULL",
            "instrument_id": envelope.get("instrument_id"),
            "raw_symbol": envelope.get("raw_symbol"),
            "ts_event_ns": envelope.get("ts_event_ns"),
            "ts_recv_ns": group_recv,
            "causal_availability_clock": "ts_recv_ns",
            "event_group_complete_f_last": True,
        }
        record = {
            "schema": GROUP_SCHEMA,
            "source_name": source_name,
            "source_role": source["role"],
            "group_index": self._group_count,
            "source_record_start": self._source_record_cursor,
            "source_record_end_exclusive": next_source_cursor,
            "completed_mbo_records_before": self._completed_mbo_records,
            "completed_mbo_records_after": self._completed_mbo_records + len(raw_actions),
            "ts_recv_ns": group_recv,
            "causal_availability_clock": "ts_recv_ns",
            "compact_event_frame": compact_event_frame,
            "raw_actions": [dict(row) for row in raw_actions],
            "raw_actions_stored_exactly_once": True,
            "full_depth_reconstructable_from_checkpoint_and_raw_actions": True,
            "fifo_reconstructable_from_checkpoint_and_raw_actions": True,
            "seconds_collapse_used": False,
            "mbp_substitute_used": False,
            "step1_derived_input_used": False,
        }
        record["group_hash"] = _hash(record, "group_hash")

        self._source_record_cursor = next_source_cursor
        self._completed_mbo_records += len(raw_actions)
        self._group_count += 1
        self._last_raw_ts_recv_ns = action_recv[-1]
        return record

    def checkpoint(self, adapter: Any, *, source_name: str, reason: str) -> dict[str, Any]:
        self._require_current_source(source_name)
        if reason not in _ALLOWED_CHECKPOINT_REASONS:
            raise NativeEvidenceBundleError("unsupported native evidence checkpoint reason")
        try:
            state = export_adapter_state(adapter)
        except ResumeStateError as exc:
            raise NativeEvidenceBundleError(str(exc)) from exc
        adapter_records = _require_nonnegative_int(state.get("record_count"), "adapter record_count")
        if adapter_records != self._completed_mbo_records:
            raise NativeEvidenceBundleError(
                "adapter raw-MBO cursor does not match evidence ledger completed cursor"
            )
        checkpoint = {
            "schema": CHECKPOINT_SCHEMA,
            "source_manifest_hash": self.source_manifest["manifest_hash"],
            "source_name": source_name,
            "source_record_cursor": self._source_record_cursor,
            "completed_mbo_records": self._completed_mbo_records,
            "completed_event_groups": self._group_count,
            "event_group_open": False,
            "reason": reason,
            "adapter_state_hash": state["state_hash"],
            "adapter_state": state,
            "full_depth_fifo_continuation_preserved": True,
            "checkpoint_hash": "",
        }
        checkpoint["checkpoint_hash"] = _hash(checkpoint, "checkpoint_hash")
        self._last_checkpoint = checkpoint
        self._checkpoint_descriptors.append(
            {
                "source_name": source_name,
                "source_record_cursor": self._source_record_cursor,
                "completed_mbo_records": self._completed_mbo_records,
                "reason": reason,
                "adapter_state_hash": state["state_hash"],
                "checkpoint_hash": checkpoint["checkpoint_hash"],
            }
        )
        return checkpoint

    def finish_source(self, source_name: str) -> dict[str, Any]:
        source = self._require_current_source(source_name)
        expected = int(source["mbo_records"])
        if self._source_record_cursor != expected:
            raise NativeEvidenceBundleError(
                f"native source record-count mismatch: expected {expected}, got {self._source_record_cursor}"
            )
        if (
            self._last_checkpoint is None
            or self._last_checkpoint["source_name"] != source_name
            or self._last_checkpoint["source_record_cursor"] != expected
            or self._last_checkpoint["reason"] != "RAW_FILE_BOUNDARY"
        ):
            raise NativeEvidenceBundleError("raw-file boundary checkpoint is mandatory before source close")
        summary = {
            "name": source["name"],
            "date": source["date"],
            "role": source["role"],
            "sha256": source["sha256"],
            "mbo_records": expected,
            "first_group_index": self._current_source_group_start,
            "group_count": self._group_count - self._current_source_group_start,
            "boundary_checkpoint_hash": self._last_checkpoint["checkpoint_hash"],
        }
        self._source_summaries.append(summary)
        self._source_index += 1
        self._source_record_cursor = 0
        self._current_source_group_start = self._group_count
        self._last_checkpoint = None
        return summary

    def finalize(self) -> dict[str, Any]:
        if self._source_index != len(self._sources):
            raise NativeEvidenceBundleError("native evidence bundle cannot finalize with incomplete sources")
        total = int(self.source_manifest["total_mbo_records"])
        if self._completed_mbo_records != total:
            raise NativeEvidenceBundleError("native evidence bundle total does not reconcile to manifest")
        bundle = {
            "schema": SCHEMA,
            "source_manifest_hash": self.source_manifest["manifest_hash"],
            "scientific_input": "NATIVE_DBN_MBO",
            "causal_availability_clock": "ts_recv_ns",
            "completed_mbo_records": self._completed_mbo_records,
            "total_mbo_records": total,
            "percent_complete": round(self._completed_mbo_records * 100.0 / total, 9),
            "completed_event_groups": self._group_count,
            "sources": list(self._source_summaries),
            "checkpoint_descriptors": list(self._checkpoint_descriptors),
            "raw_actions_preserved_exactly_once": True,
            "full_depth_fifo_reconstructable": True,
            "seconds_surface_present": False,
            "mbp_substitute_present": False,
            "step1_derived_input_present": False,
            "progress_denominator": "HASH_BOUND_NATIVE_MBO_RECORD_COUNT",
            "bundle_hash": "",
        }
        bundle["bundle_hash"] = _hash(bundle, "bundle_hash")
        return bundle
