#!/usr/bin/env python3
"""Isolated V4 causal discovery-clock contract.

This module does not alter the frozen detector, canonical t0, runway clock, permanent
Frankie, or any launch workflow. It exists to make the V4 event-known boundary
explicit and fail closed when retrospective t0 is substituted for a causal mark.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_VERSION = "NG_EXHAUSTION_V4_CAUSAL_DISCOVERY_V1"

class CausalClockError(ValueError):
    pass


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise CausalClockError(f"{field} must be a finite timestamp")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CausalClockError(f"{field} must be a finite timestamp") from exc
    if not math.isfinite(out):
        raise CausalClockError(f"{field} must be a finite timestamp")
    return out


def _id(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise CausalClockError(f"{field} must be non-empty")
    return out


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(out):
        raise CausalClockError(f"{field} must be lowercase SHA-256")
    return out


def _hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CausalDiscoveryReceipt:
    schema_version: str
    event_id: str
    session_id: str
    detector_revision: str
    detector_source_sha256: str
    source_manifest_sha256: str
    source_object_id: str
    source_range_id: str
    source_ts_event: float
    source_ts_recv: float
    detector_marked_at: float
    event_known_by: float
    canonical_t0: float
    mark_mode: str
    receipt_hash: str

    def core(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("receipt_hash", None)
        return d

    def validate(self) -> "CausalDiscoveryReceipt":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalClockError("schema version mismatch")
        _id(self.event_id, "event_id"); _id(self.session_id, "session_id")
        _id(self.detector_revision, "detector_revision")
        _sha(self.detector_source_sha256, "detector_source_sha256")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        _id(self.source_object_id, "source_object_id"); _id(self.source_range_id, "source_range_id")
        ev = _finite(self.source_ts_event, "source_ts_event")
        recv = _finite(self.source_ts_recv, "source_ts_recv")
        marked = _finite(self.detector_marked_at, "detector_marked_at")
        known = _finite(self.event_known_by, "event_known_by")
        _finite(self.canonical_t0, "canonical_t0")
        if self.mark_mode not in {"PROSPECTIVE", "CAUSAL_REPLAY"}:
            raise CausalClockError("mark_mode must be PROSPECTIVE or CAUSAL_REPLAY")
        if recv < ev:
            # Exchange event time may precede receipt; the reverse is never a reason to backdate.
            pass
        if marked < recv:
            raise CausalClockError("detector_marked_at cannot precede source receive/observation time")
        if known < marked:
            raise CausalClockError("event_known_by cannot precede detector_marked_at")
        if self.receipt_hash != _hash(self.core()):
            raise CausalClockError("receipt hash mismatch")
        return self


def make_receipt(*, event_id: str, session_id: str, detector_revision: str,
                 detector_source_sha256: str, source_manifest_sha256: str,
                 source_object_id: str, source_range_id: str, source_ts_event: Any,
                 source_ts_recv: Any, detector_marked_at: Any, event_known_by: Any,
                 canonical_t0: Any, mark_mode: str) -> CausalDiscoveryReceipt:
    core = {
        "schema_version": SCHEMA_VERSION,
        "event_id": _id(event_id, "event_id"),
        "session_id": _id(session_id, "session_id"),
        "detector_revision": _id(detector_revision, "detector_revision"),
        "detector_source_sha256": _sha(detector_source_sha256, "detector_source_sha256"),
        "source_manifest_sha256": _sha(source_manifest_sha256, "source_manifest_sha256"),
        "source_object_id": _id(source_object_id, "source_object_id"),
        "source_range_id": _id(source_range_id, "source_range_id"),
        "source_ts_event": _finite(source_ts_event, "source_ts_event"),
        "source_ts_recv": _finite(source_ts_recv, "source_ts_recv"),
        "detector_marked_at": _finite(detector_marked_at, "detector_marked_at"),
        "event_known_by": _finite(event_known_by, "event_known_by"),
        "canonical_t0": _finite(canonical_t0, "canonical_t0"),
        "mark_mode": str(mark_mode),
    }
    receipt = CausalDiscoveryReceipt(**core, receipt_hash=_hash(core))
    return receipt.validate()


def validate_availability_chain(receipt: CausalDiscoveryReceipt, *, feature_available_at: Any,
                                model_evaluated_at: Any, decision_available_at: Any) -> dict[str, float]:
    receipt.validate()
    feature = _finite(feature_available_at, "feature_available_at")
    model = _finite(model_evaluated_at, "model_evaluated_at")
    decision = _finite(decision_available_at, "decision_available_at")
    if not receipt.event_known_by <= feature <= model <= decision:
        raise CausalClockError(
            "required order is event_known_by <= feature_available_at <= model_evaluated_at <= decision_available_at"
        )
    return {
        "event_known_by": receipt.event_known_by,
        "feature_available_at": feature,
        "model_evaluated_at": model,
        "decision_available_at": decision,
    }


def first_receive_ordered_mark(rows: Sequence[Mapping[str, Any]], *, qualifying_field: str = "qualifies") -> Mapping[str, Any]:
    """Return the first causally observable qualifying row in receive-time order.

    This helper deliberately does not know the frozen retrospective detector. A separately
    versioned causal replay rule may emit `qualifies`; this function only enforces that the
    chosen mark is the first lawful receive-ordered declaration and never event-time-backdated.
    """
    normalized=[]
    for i,row in enumerate(rows):
        recv=_finite(row.get("ts_recv"), f"rows[{i}].ts_recv")
        event=_finite(row.get("ts_event"), f"rows[{i}].ts_event")
        normalized.append((recv, event, i, row))
    normalized.sort(key=lambda x:(x[0],x[1],x[2]))
    for recv,event,i,row in normalized:
        if bool(row.get(qualifying_field)):
            return {"row_index":i,"ts_event":event,"ts_recv":recv,"detector_marked_at":recv,"event_known_by":recv}
    raise CausalClockError("no causal qualifying mark exists")
