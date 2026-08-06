"""At-least-once delivery protection for Frankie evidence.

SQS may redeliver a message. The first completed decision for an immutable event hash wins;
subsequent deliveries return the existing evidence without recalling a model or rewriting it.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from frankie_core import (
    FrankieConfig,
    FrankieDecision,
    FrankieEvent,
    GateStop,
    canonical_json,
    load_json,
    sha256_json,
)


def _index_path(config: FrankieConfig, event_hash: str) -> Path:
    return config.evidence_root.parent / "index" / f"{event_hash}.json"


def _write_once(path: Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return True


def lookup_existing(
    *,
    config: FrankieConfig,
    event: FrankieEvent,
) -> tuple[FrankieDecision, dict[str, Any]] | None:
    event_hash = sha256_json(event.as_dict())
    index_path = _index_path(config, event_hash)
    if not index_path.is_file():
        return None
    index = load_json(index_path)
    if not isinstance(index, dict) or index.get("event_hash") != event_hash:
        raise GateStop(f"invalid Frankie event index: {index_path}")
    evidence_path = Path(str(index.get("local_path") or ""))
    if not evidence_path.is_file():
        raise GateStop(f"Frankie index points to missing evidence: {evidence_path}")
    envelope = load_json(evidence_path)
    if not isinstance(envelope, dict):
        raise GateStop(f"invalid evidence envelope: {evidence_path}")
    expected_envelope_hash = sha256_json(
        {"decision": envelope.get("decision"), "event": envelope.get("event")}
    )
    if envelope.get("envelope_hash") != expected_envelope_hash:
        raise GateStop(f"evidence hash mismatch: {evidence_path}")
    if sha256_json(envelope.get("event")) != event_hash:
        raise GateStop(f"indexed evidence carries a different event: {evidence_path}")
    decision_raw = envelope.get("decision")
    if not isinstance(decision_raw, dict):
        raise GateStop(f"indexed evidence missing decision: {evidence_path}")
    decision = FrankieDecision(**decision_raw)
    return decision, {
        "local_path": str(evidence_path),
        "envelope_hash": envelope["envelope_hash"],
        "s3_uri": index.get("s3_uri"),
        "deduplicated": True,
        "index_path": str(index_path),
    }


def record_first(
    *,
    config: FrankieConfig,
    event: FrankieEvent,
    decision: FrankieDecision,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    event_hash = sha256_json(event.as_dict())
    index_path = _index_path(config, event_hash)
    payload = {
        "schema_version": "1.0",
        "event_hash": event_hash,
        "decision_hash": decision.decision_hash,
        "local_path": evidence["local_path"],
        "envelope_hash": evidence["envelope_hash"],
        "s3_uri": evidence.get("s3_uri"),
        "execution_enabled": False,
        "index_id": str(uuid.uuid4()),
    }
    created = _write_once(index_path, payload)
    if not created:
        existing = lookup_existing(config=config, event=event)
        if existing is None:
            raise GateStop(f"event index race could not be resolved: {index_path}")
        existing_decision, existing_evidence = existing
        if existing_decision.decision_hash != decision.decision_hash:
            # Keep first-writer truth. The new envelope remains on disk as diagnostic evidence,
            # but the event index never changes beneath an already processed event.
            return {
                "created": False,
                "first_writer_decision_hash": existing_decision.decision_hash,
                "discarded_decision_hash": decision.decision_hash,
                "index_path": str(index_path),
                "existing_evidence": existing_evidence,
            }
    return {"created": created, "index_path": str(index_path), **payload}
