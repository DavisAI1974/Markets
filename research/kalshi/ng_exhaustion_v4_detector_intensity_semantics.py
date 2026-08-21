#!/usr/bin/env python3
"""Fail-closed detector-intensity semantic resolver for NG Exhaustion V4.

A field may be called detector/native intensity only when it is backed by a frozen
causal stream with explicit source/revision/availability identity. Otherwise V4 must
use an explicitly non-native proxy namespace. Future endpoint reconstruction is forbidden.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from research.kalshi.ng_exhaustion_v4_gate_verifier import DetectorIntensityResolution

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "NG_EXHAUSTION_V4_DETECTOR_INTENSITY_SEMANTICS_V1"


class DetectorIntensityError(ValueError):
    pass


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise DetectorIntensityError(f"{field} must be lowercase SHA-256")
    return text


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DetectorIntensityError(f"{field} must be non-empty")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise DetectorIntensityError(f"{field} must be finite")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DetectorIntensityError(f"{field} must be finite") from exc
    if not math.isfinite(out):
        raise DetectorIntensityError(f"{field} must be finite")
    return out


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class NativeIntensityRow:
    second: float
    ts_event: float
    ts_recv: float
    available_at: float
    intensity: float
    source_object_id: str
    source_revision: str
    source_sha256: str
    derived_from_future_endpoint: bool = False

    def validate(self) -> "NativeIntensityRow":
        second = _finite(self.second, "second")
        event = _finite(self.ts_event, "ts_event")
        recv = _finite(self.ts_recv, "ts_recv")
        avail = _finite(self.available_at, "available_at")
        _finite(self.intensity, "intensity")
        _id(self.source_object_id, "source_object_id")
        _id(self.source_revision, "source_revision")
        _sha(self.source_sha256, "source_sha256")
        if event > avail or recv > avail or second > avail:
            raise DetectorIntensityError("native intensity row is backdated before lawful availability")
        if self.derived_from_future_endpoint:
            raise DetectorIntensityError("future endpoint reconstruction cannot be detector-native intensity")
        return self


def prove_native_stream(rows: Sequence[NativeIntensityRow], *, frozen_detector_sha256: str) -> dict[str, Any]:
    _sha(frozen_detector_sha256, "frozen_detector_sha256")
    if not rows:
        raise DetectorIntensityError("native stream proof requires at least one row")
    prior_second = -math.inf
    revisions = set()
    sources = set()
    payload = []
    for row in rows:
        row.validate()
        if row.second <= prior_second:
            raise DetectorIntensityError("native intensity seconds must be strictly increasing")
        prior_second = row.second
        revisions.add(row.source_revision)
        sources.add(row.source_sha256)
        payload.append(asdict(row))
    if len(revisions) != 1:
        raise DetectorIntensityError("native intensity proof cannot silently mix detector revisions")
    stream_hash = _hash(
        {
            "schema": SCHEMA,
            "frozen_detector_sha256": frozen_detector_sha256,
            "rows": payload,
        }
    )
    resolution = DetectorIntensityResolution(mode="PROVEN_NATIVE", source_sha256=stream_hash)
    resolution.validate()
    return {
        "schema": SCHEMA,
        "status": "PROVEN_CAUSAL_NATIVE_INTENSITY",
        "resolution": asdict(resolution),
        "stream_sha256": stream_hash,
        "row_count": len(rows),
        "source_revision": next(iter(revisions)),
        "source_sha256s": sorted(sources),
        "future_endpoint_reconstruction_used": False,
    }


def explicit_proxy(*, proxy_namespace: str, proxy_source_sha256: str, transform_sha256: str) -> dict[str, Any]:
    namespace = _id(proxy_namespace, "proxy_namespace")
    lower = namespace.lower()
    if not namespace.startswith("v4_proxy."):
        raise DetectorIntensityError("proxy namespace must begin with v4_proxy.")
    if "native" in lower or "detector_intensity" in lower or "native_exhaustion" in lower:
        raise DetectorIntensityError("proxy namespace may not masquerade as native detector intensity")
    _sha(proxy_source_sha256, "proxy_source_sha256")
    _sha(transform_sha256, "transform_sha256")
    resolution = DetectorIntensityResolution(mode="EXPLICIT_PROXY", proxy_namespace=namespace)
    resolution.validate()
    core = {
        "schema": SCHEMA,
        "status": "EXPLICIT_NON_NATIVE_PROXY",
        "resolution": asdict(resolution),
        "proxy_source_sha256": proxy_source_sha256,
        "transform_sha256": transform_sha256,
        "future_endpoint_reconstruction_used": False,
        "native_intensity_claimed": False,
    }
    return {**core, "proxy_receipt_sha256": _hash(core)}
