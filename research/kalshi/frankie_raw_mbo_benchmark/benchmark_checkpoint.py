"""Restart-safe, controller-neutral checkpoints for the raw-MBO blind benchmark."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

SCHEMA = "FRANKIE_RAW_MBO_BENCHMARK_CHECKPOINT_V1"
VALID_CONTROLLERS = frozenset({
    "A_CHATGPT",
    "B0_FIXED_DEPTH",
    "B1_RECURRENT",
    "B2_RECURRENT_GRANITE",
})
VALID_MEMORY_MODES = frozenset({"CLEAN", "MEMORY_ASSISTED"})
_ALLOWED_KEYS = frozenset({
    "schema",
    "run_id",
    "controller",
    "memory_mode",
    "sequence",
    "source_manifest_hash",
    "completed_mbo_records",
    "total_mbo_records",
    "progress_percent",
    "event_group_open",
    "adapter_state_hash",
    "controller_state_hash",
    "previous_checkpoint_hash",
    "phase",
    "locked",
    "checkpoint_hash",
})
_FORBIDDEN_TEXT = ("step1", "step-1", "reveal", "outcome", "self_fit", "self-fit", "self_score", "self-score", "answer")


class CheckpointError(ValueError):
    """Checkpoint contract violation."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_sha256(value: str | None, label: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise CheckpointError(f"{label} must be a 64-character SHA-256")


def _reject_answer_text(value: str, label: str) -> None:
    lowered = value.lower()
    if any(token in lowered for token in _FORBIDDEN_TEXT):
        raise CheckpointError(f"{label} contains forbidden answer/reveal terminology")


def progress_percent(completed_mbo_records: int, total_mbo_records: int) -> float:
    if not _is_int(completed_mbo_records) or not _is_int(total_mbo_records):
        raise CheckpointError("MBO record counts must be integers")
    if total_mbo_records <= 0:
        raise CheckpointError("total_mbo_records must be positive")
    if completed_mbo_records < 0 or completed_mbo_records > total_mbo_records:
        raise CheckpointError("completed_mbo_records must be within [0,total_mbo_records]")
    return round((completed_mbo_records * 100.0) / total_mbo_records, 9)


def _canonical_payload(checkpoint: Mapping[str, Any]) -> bytes:
    body = {k: v for k, v in checkpoint.items() if k != "checkpoint_hash"}
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def checkpoint_hash(checkpoint: Mapping[str, Any]) -> str:
    if not isinstance(checkpoint, Mapping):
        raise CheckpointError("checkpoint must be a mapping")
    return hashlib.sha256(_canonical_payload(checkpoint)).hexdigest()


def _validate_checkpoint(checkpoint: Mapping[str, Any]) -> None:
    if not isinstance(checkpoint, Mapping):
        raise CheckpointError("checkpoint must be a mapping")
    actual = set(checkpoint)
    if actual != _ALLOWED_KEYS:
        raise CheckpointError(
            f"unknown or missing checkpoint fields: unknown={sorted(actual - _ALLOWED_KEYS)}, "
            f"missing={sorted(_ALLOWED_KEYS - actual)}"
        )
    observed_hash = checkpoint_hash(checkpoint)
    if checkpoint["checkpoint_hash"] != observed_hash:
        raise CheckpointError("checkpoint hash mismatch")

    if checkpoint["schema"] != SCHEMA:
        raise CheckpointError("unsupported checkpoint schema")

    for label in ("run_id", "controller", "memory_mode", "phase"):
        value = checkpoint[label]
        if not isinstance(value, str) or not value:
            raise CheckpointError(f"{label} must be a non-empty string")
        _reject_answer_text(value, label)

    if checkpoint["controller"] not in VALID_CONTROLLERS:
        raise CheckpointError("unknown benchmark controller")
    if checkpoint["memory_mode"] not in VALID_MEMORY_MODES:
        raise CheckpointError("unknown benchmark memory mode")

    sequence = checkpoint["sequence"]
    if not _is_int(sequence) or sequence < 0:
        raise CheckpointError("sequence must be a nonnegative integer")

    _require_sha256(checkpoint["source_manifest_hash"], "source_manifest_hash")
    _require_sha256(checkpoint["adapter_state_hash"], "adapter_state_hash")
    _require_sha256(checkpoint["controller_state_hash"], "controller_state_hash", optional=True)
    _require_sha256(checkpoint["previous_checkpoint_hash"], "previous_checkpoint_hash", optional=True)

    if not isinstance(checkpoint["event_group_open"], bool):
        raise CheckpointError("event_group_open must be boolean")
    if checkpoint["event_group_open"]:
        raise CheckpointError("checkpoint requires an F_LAST-closed event group")
    if not isinstance(checkpoint["locked"], bool):
        raise CheckpointError("locked must be boolean")

    expected_progress = progress_percent(
        checkpoint["completed_mbo_records"], checkpoint["total_mbo_records"]
    )
    if checkpoint["progress_percent"] != expected_progress:
        raise CheckpointError("progress_percent does not match raw MBO record cursor")
    if checkpoint["locked"] and checkpoint["completed_mbo_records"] != checkpoint["total_mbo_records"]:
        raise CheckpointError("final locked checkpoint requires complete raw MBO replay")


def build_checkpoint(
    *,
    run_id: str,
    controller: str,
    memory_mode: str,
    sequence: int,
    source_manifest_hash: str,
    completed_mbo_records: int,
    total_mbo_records: int,
    event_group_open: bool,
    adapter_state_hash: str,
    controller_state_hash: str | None,
    previous_checkpoint_hash: str | None,
    phase: str,
    locked: bool,
) -> dict[str, Any]:
    if sequence == 0 and previous_checkpoint_hash is not None:
        raise CheckpointError("sequence 0 cannot have a previous checkpoint")
    if sequence > 0 and previous_checkpoint_hash is None:
        raise CheckpointError("nonzero sequence requires previous_checkpoint_hash")
    checkpoint: dict[str, Any] = {
        "schema": SCHEMA,
        "run_id": run_id,
        "controller": controller,
        "memory_mode": memory_mode,
        "sequence": sequence,
        "source_manifest_hash": source_manifest_hash,
        "completed_mbo_records": completed_mbo_records,
        "total_mbo_records": total_mbo_records,
        "progress_percent": progress_percent(completed_mbo_records, total_mbo_records),
        "event_group_open": event_group_open,
        "adapter_state_hash": adapter_state_hash,
        "controller_state_hash": controller_state_hash,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "phase": phase,
        "locked": locked,
        "checkpoint_hash": "",
    }
    checkpoint["checkpoint_hash"] = checkpoint_hash(checkpoint)
    _validate_checkpoint(checkpoint)
    return checkpoint


def verify_chain(checkpoints: Sequence[Mapping[str, Any]]) -> None:
    if not checkpoints:
        raise CheckpointError("checkpoint chain is empty")
    validated = []
    for checkpoint in checkpoints:
        _validate_checkpoint(checkpoint)
        validated.append(checkpoint)

    first = validated[0]
    if first["sequence"] != 0 or first["previous_checkpoint_hash"] is not None:
        raise CheckpointError("checkpoint chain must start at sequence 0")

    stable = ("run_id", "controller", "memory_mode", "source_manifest_hash", "total_mbo_records")
    for previous, current in zip(validated, validated[1:]):
        if previous["locked"]:
            raise CheckpointError("locked checkpoint is terminal")
        if current["sequence"] != previous["sequence"] + 1:
            raise CheckpointError("checkpoint sequence is not contiguous")
        if current["previous_checkpoint_hash"] != previous["checkpoint_hash"]:
            raise CheckpointError("checkpoint hash chain link mismatch")
        if current["completed_mbo_records"] < previous["completed_mbo_records"]:
            raise CheckpointError("raw MBO record cursor regressed")
        for key in stable:
            if current[key] != previous[key]:
                raise CheckpointError(f"checkpoint {key} drift")


def write_checkpoint_atomic(path: Path | str, checkpoint: Mapping[str, Any]) -> None:
    _validate_checkpoint(checkpoint)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        dict(checkpoint),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def load_checkpoint(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"cannot load checkpoint: {target}") from exc
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint file must contain a JSON object")
    _validate_checkpoint(value)
    return value
