"""Periodic save points for long native raw-MBO runs.

The checkpoint primitives already exist: `benchmark_checkpoint` builds and verifies a
hash-chained sequence, and `mbo_resume_state` exports and restores exact adapter state.
What was missing is the driver that calls them *during* a run. Before this module the
launch workflows sealed one checkpoint at record 0 and copied results to durable storage
only after the replay finished, so a job that died at any point lost the whole run.

This module saves on a record or wall-clock interval, at F_LAST-closed group boundaries
only, and pushes each save point to durable storage as it is written. Resume reads the
newest save point whose adapter state verifies against its own checkpoint hash.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (
    CheckpointError,
    build_checkpoint,
    load_checkpoint,
    progress_percent,
    verify_chain,
    write_checkpoint_atomic,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (
    ResumeStateError,
    adapter_state_hash,
    export_adapter_state,
    restore_adapter_state,
)

CHECKPOINT_GLOB = "checkpoint-*.json"
DEFAULT_EVERY_RECORDS = 250_000
DEFAULT_EVERY_SECONDS = 600.0


class PeriodicCheckpointError(RuntimeError):
    """A save point could not be written, verified, or resumed."""


def canonical_hash(value: Any) -> str:
    """Hash a value exactly as the existing A-memory resume path does.

    Deliberately no trailing newline: `a_memory_rt_resume_20260828.canonical_hash` is what
    already-written `controller-state-*.json` receipts were hashed with, so a different
    canonical form here would make previously written save points unverifiable.
    """
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_gzip_json_atomic(path: Path | str, value: Mapping[str, Any]) -> None:
    """Write canonical JSON gzipped, atomically, with a deterministic gzip header."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json_bytes(value)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
                handle.write(payload)
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def read_gzip_json(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    try:
        with gzip.open(target, "rb") as handle:
            value = json.loads(handle.read().decode("utf-8"))
    except (OSError, EOFError, json.JSONDecodeError) as exc:
        raise PeriodicCheckpointError(f"cannot read save point: {target}") from exc
    if not isinstance(value, dict):
        raise PeriodicCheckpointError(f"save point is not a JSON object: {target}")
    return value


def adapter_state_path(checkpoint_dir: Path | str, sequence: int) -> Path:
    return Path(checkpoint_dir) / f"adapter-state-{sequence:06d}.json.gz"


def controller_state_path(checkpoint_dir: Path | str, sequence: int) -> Path:
    return Path(checkpoint_dir) / f"controller-state-{sequence:06d}.json"


def checkpoint_path(checkpoint_dir: Path | str, sequence: int) -> Path:
    return Path(checkpoint_dir) / f"checkpoint-{sequence:06d}.json"


class PeriodicCheckpointer:
    """Writes hash-chained save points on a record or wall-clock interval.

    `durable_sync` is called with each written save point's paths immediately after they
    land locally. It is injected rather than importing an S3 client so the interval logic
    is testable without credentials, and so a failed push is reported at the save point
    that failed rather than at the end of the run.
    """

    def __init__(
        self,
        *,
        run_id: str,
        controller: str,
        memory_mode: str,
        source_manifest_hash: str,
        total_mbo_records: int,
        checkpoint_dir: Path | str,
        phase: str,
        every_records: int = DEFAULT_EVERY_RECORDS,
        every_seconds: float = DEFAULT_EVERY_SECONDS,
        durable_sync: Callable[[Sequence[Path]], None] | None = None,
        progress_report: Callable[[Mapping[str, Any]], None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if every_records <= 0:
            raise PeriodicCheckpointError("every_records must be positive")
        if every_seconds <= 0:
            raise PeriodicCheckpointError("every_seconds must be positive")
        self.run_id = run_id
        self.controller = controller
        self.memory_mode = memory_mode
        self.source_manifest_hash = source_manifest_hash
        self.total_mbo_records = total_mbo_records
        self.checkpoint_dir = Path(checkpoint_dir)
        self.phase = phase
        self.every_records = every_records
        self.every_seconds = every_seconds
        self._durable_sync = durable_sync
        self._progress_report = progress_report
        self._monotonic = monotonic
        self._last_reported_percent = -1
        self._sequence = -1
        self._previous_hash: str | None = None
        self._last_saved_records = 0
        self._last_saved_at = monotonic()
        self._saved: list[dict[str, Any]] = []

    @property
    def sequence(self) -> int:
        return self._sequence

    def report_progress(self, completed_mbo_records: int) -> dict[str, Any] | None:
        """Emit a percent-complete meter, at most once per whole percent.

        Reported independently of save points: at a 250k-record save interval a run would
        otherwise go many minutes with no sign of life, which is what makes a stalled job
        indistinguishable from a slow one.
        """
        if self._progress_report is None:
            return None
        percent = progress_percent(completed_mbo_records, self.total_mbo_records)
        whole = int(percent)
        if whole <= self._last_reported_percent:
            return None
        self._last_reported_percent = whole
        row = {
            "run_id": self.run_id,
            "controller": self.controller,
            "phase": self.phase,
            "completed_mbo_records": completed_mbo_records,
            "total_mbo_records": self.total_mbo_records,
            "progress_percent": percent,
            "last_save_point_sequence": self._sequence,
            "records_since_last_save_point": completed_mbo_records - self._last_saved_records,
        }
        self._progress_report(row)
        return row

    @property
    def saved_checkpoints(self) -> list[dict[str, Any]]:
        return list(self._saved)

    def _write(
        self,
        adapter: Any,
        *,
        completed_mbo_records: int,
        event_group_open: bool,
        controller_state: Mapping[str, Any] | None,
        locked: bool,
    ) -> dict[str, Any]:
        sequence = self._sequence + 1
        state = export_adapter_state(adapter)
        state_hash = adapter_state_hash(state)

        controller_hash: str | None = None
        written: list[Path] = []

        state_target = adapter_state_path(self.checkpoint_dir, sequence)
        write_gzip_json_atomic(state_target, state)
        written.append(state_target)

        if controller_state is not None:
            controller_target = controller_state_path(self.checkpoint_dir, sequence)
            payload = _canonical_json_bytes(controller_state)
            controller_target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=controller_target.name + ".", suffix=".tmp", dir=controller_target.parent
            )
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, controller_target)
            finally:
                tmp.unlink(missing_ok=True)
            written.append(controller_target)
            controller_hash = canonical_hash(dict(controller_state))

        checkpoint = build_checkpoint(
            run_id=self.run_id,
            controller=self.controller,
            memory_mode=self.memory_mode,
            sequence=sequence,
            source_manifest_hash=self.source_manifest_hash,
            completed_mbo_records=completed_mbo_records,
            total_mbo_records=self.total_mbo_records,
            event_group_open=event_group_open,
            adapter_state_hash=state_hash,
            controller_state_hash=controller_hash,
            previous_checkpoint_hash=self._previous_hash,
            phase=self.phase,
            locked=locked,
        )
        target = checkpoint_path(self.checkpoint_dir, sequence)
        write_checkpoint_atomic(target, checkpoint)
        written.append(target)

        self._sequence = sequence
        self._previous_hash = checkpoint["checkpoint_hash"]
        self._last_saved_records = completed_mbo_records
        self._last_saved_at = self._monotonic()
        self._saved.append(checkpoint)

        if self._durable_sync is not None:
            self._durable_sync(tuple(written))
        self.report_progress(completed_mbo_records)
        return checkpoint

    def seal_start(
        self,
        adapter: Any,
        *,
        controller_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write sequence 0. Must be called before any interval save."""
        if self._sequence >= 0:
            raise PeriodicCheckpointError("start checkpoint already sealed")
        return self._write(
            adapter,
            completed_mbo_records=0,
            event_group_open=False,
            controller_state=controller_state,
            locked=False,
        )

    def due(self, completed_mbo_records: int) -> bool:
        if self._sequence < 0:
            return False
        if completed_mbo_records - self._last_saved_records >= self.every_records:
            return True
        return (self._monotonic() - self._last_saved_at) >= self.every_seconds

    def maybe_save(
        self,
        adapter: Any,
        *,
        completed_mbo_records: int,
        event_group_open: bool = False,
        controller_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Save if the interval has elapsed and the cursor sits on a closed group.

        Saving mid-group is refused rather than recorded: an F_LAST-closed boundary is the
        only causally lawful resume point, so a save point taken inside an open group would
        resume into a partially observed event.
        """
        if self._sequence < 0:
            raise PeriodicCheckpointError("seal_start must be called before interval saves")
        self.report_progress(completed_mbo_records)
        if event_group_open or not self.due(completed_mbo_records):
            return None
        return self._write(
            adapter,
            completed_mbo_records=completed_mbo_records,
            event_group_open=False,
            controller_state=controller_state,
            locked=False,
        )

    def seal_final(
        self,
        adapter: Any,
        *,
        completed_mbo_records: int,
        controller_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write the terminal, locked save point. No further saves are permitted."""
        if self._sequence < 0:
            raise PeriodicCheckpointError("seal_start must be called before the final seal")
        if completed_mbo_records != self.total_mbo_records:
            raise PeriodicCheckpointError(
                "final seal requires the full record denominator: "
                f"{completed_mbo_records} of {self.total_mbo_records}"
            )
        return self._write(
            adapter,
            completed_mbo_records=completed_mbo_records,
            event_group_open=False,
            controller_state=controller_state,
            locked=True,
        )


def load_chain(checkpoint_dir: Path | str) -> list[dict[str, Any]]:
    """Load and verify the full hash-chained save-point sequence."""
    paths = sorted(Path(checkpoint_dir).glob(CHECKPOINT_GLOB))
    if not paths:
        raise PeriodicCheckpointError(f"no save points under {checkpoint_dir}")
    checkpoints = [load_checkpoint(path) for path in paths]
    try:
        verify_chain(checkpoints)
    except CheckpointError as exc:
        raise PeriodicCheckpointError(f"save-point chain is not valid: {exc}") from exc
    return checkpoints


def resume_from_latest(checkpoint_dir: Path | str) -> tuple[dict[str, Any], Any]:
    """Return the newest verified save point and its restored adapter.

    The adapter state is re-hashed and compared against the checkpoint that claims it, so
    a truncated or partially synced state file is rejected here rather than resuming a run
    on a book that does not match its own receipt.
    """
    checkpoints = load_chain(checkpoint_dir)
    latest = checkpoints[-1]
    if latest["locked"]:
        raise PeriodicCheckpointError("latest save point is the terminal seal; run is complete")
    sequence = int(latest["sequence"])
    state = read_gzip_json(adapter_state_path(checkpoint_dir, sequence))
    if adapter_state_hash(state) != latest["adapter_state_hash"]:
        raise PeriodicCheckpointError(f"adapter state hash mismatch at sequence {sequence}")
    try:
        adapter = restore_adapter_state(state)
    except ResumeStateError as exc:
        raise PeriodicCheckpointError(f"cannot restore adapter at sequence {sequence}: {exc}") from exc
    return latest, adapter
