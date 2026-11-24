"""Canonical writer for registry state (arch §3.3).

Arch §3.3 mandates that every registry write goes through a ``registry_writer``
module that performs (a) schema validation against the operator manifest meta-
schema and (b) appends an audit-log entry. Until this module landed, the
control-plane operators (notably ``operator_lineage_tracker``) called
``storage.save_json`` directly — bypassing the audit hook and leaving no
durable record of who wrote what when. That violated Rule 3 ("Registry Writes
Are Restricted ... All through registry_writer") in spirit even though the
allowlist was respected at the caller boundary.

This module is the spec-compliant write seam. It:

1. Resolves the target path the same way ``storage.operator_state_path``
   does, so legacy on-disk paths are unchanged.
2. Validates the payload against an optional caller-supplied schema. The
   meta-schema slot is wired but no schemas are registered yet (tracked in
   ``BUGS_DEFERRED_FOR_DISCUSSION`` item D). Until schemas land,
   ``schema_validated=False`` is recorded in every audit entry so a future
   audit pass can identify the pre-schema writes.
3. Writes atomically via ``storage.save_json`` (tempfile + ``os.replace``).
4. Appends an audit-log JSONL entry to
   ``registry/audit/registry_writer.jsonl`` with the timestamp, kind,
   operator_id, target path, payload SHA-256, schema validation result, and
   the caller's intent string (free-form, useful for tying writes back to
   the originating control-plane operator).

Concurrency: the JSONL append uses a single ``os.write`` syscall after
pre-serializing the line (mirrors the orchestrator's Fix I pattern). For lines
under PIPE_BUF this is atomic on Windows + POSIX; lines exceeding the
threshold log a warning. Audit entries are typically <500 bytes so this is
comfortable.

Idempotency: callers that re-write identical payloads still produce a new
audit entry — the log is an event stream, not a state-mirror. Filter by
payload_hash if you want unique writes only.

Reading the audit log: any JSONL reader works. The schema is intentionally
flat:

    {"ts", "kind", "operator_id", "path", "payload_hash", "schema_validated",
     "schema_id", "intent"}
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from refrag_discovery.paths import REGISTRY_DIR
from refrag_discovery.control_plane.storage import (
    operator_state_path,
    save_json,
)


AUDIT_LOG_PATH = REGISTRY_DIR / "audit" / "registry_writer.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_hex(payload: dict[str, Any]) -> str:
    """Stable hash for audit reproducibility (sort_keys for determinism)."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _append_audit_entry(entry: dict[str, Any]) -> None:
    """Atomic-append one JSONL audit entry. Mirrors orchestrator Fix I."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True) + "\n"
    payload = line.encode("utf-8")
    if len(payload) > 4000:
        # Audit entries should be small; warn if a caller is stuffing huge
        # intent strings or similar so we surface the bloat early.
        print(
            f"warning: registry_writer audit entry {len(payload)} bytes "
            f"exceeds 4 KB atomic-append threshold for "
            f"{entry.get('kind')}/{entry.get('operator_id')}",
            flush=True,
        )
    fd = os.open(
        str(AUDIT_LOG_PATH),
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o644,
    )
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def write_registry(
    *,
    kind: str,
    operator_id: str,
    payload: dict[str, Any],
    artifacts_dir: Path | None = None,
    schema_validator: Callable[[dict[str, Any]], None] | None = None,
    schema_id: str | None = None,
    intent: str = "",
) -> Path:
    """Spec-compliant registry write (arch §3.3).

    Parameters
    ----------
    kind:
        Registry kind ("lineage", "manifests", etc). Routed via
        ``operator_state_path`` so legacy paths are preserved.
    operator_id:
        The operator this state belongs to (becomes the filename stem).
    payload:
        JSON-serializable dict. Will be atomically written via
        ``storage.save_json``.
    artifacts_dir:
        Optional sandbox override. ``None`` routes registry kinds to
        ``REGISTRY_DIR`` per arch §3.1.
    schema_validator:
        Optional callable invoked with ``payload`` before write. Raise to
        block the write; ``None`` means "no schema validated yet" and the
        audit entry records ``schema_validated=False``. Until per-kind
        schemas are defined, all callers will pass ``None`` and the audit
        log identifies pre-schema writes.
    schema_id:
        Identifier for the schema that was validated (or ``None``). Recorded
        in the audit entry for backward-trace.
    intent:
        Free-form short string describing the caller's intent (e.g.
        "lineage_registration", "manifest_synthesis_promotion"). Lets the
        audit log distinguish "lineage_tracker normal write" from
        "manifest_synthesizer promoted a synthesized manifest" without
        scraping callsites.

    Returns
    -------
    Path
        The absolute path the payload was written to.
    """
    if schema_validator is not None:
        schema_validator(payload)
        schema_validated = True
    else:
        schema_validated = False

    path = operator_state_path(kind, operator_id, artifacts_dir)
    save_json(path, payload)

    _append_audit_entry(
        {
            "ts": _utc_now_iso(),
            "kind": kind,
            "operator_id": operator_id,
            "path": str(path),
            "payload_hash": _sha256_hex(payload),
            "schema_validated": schema_validated,
            "schema_id": schema_id,
            "intent": intent,
        }
    )
    return path


__all__ = [
    "AUDIT_LOG_PATH",
    "write_registry",
]
