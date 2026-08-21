#!/usr/bin/env python3
"""Fail-closed V4 detector-intensity semantics contract.

A field may be called detector/native exhaustion intensity only when it binds a
frozen causal native stream with exact source/revision/availability identity.
Otherwise V4 must omit the field or use an explicitly non-native proxy name.
Retrospective endpoint reconstruction can never be relabeled as native.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "NG_EXHAUSTION_V4_DETECTOR_INTENSITY_SEMANTICS_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NATIVE_RESERVED = {
    "detector_native_intensity",
    "native_exhaustion_intensity",
    "detector_intensity",
    "exhaustion_intensity",
}


class IntensitySemanticsError(ValueError):
    pass


def _sha(v: Any, field: str) -> str:
    x = str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(x):
        raise IntensitySemanticsError(f"{field} must be lowercase SHA-256")
    return x


def _id(v: Any, field: str) -> str:
    x = str(v or "").strip()
    if not x:
        raise IntensitySemanticsError(f"{field} must be non-empty")
    return x


def _hash(v: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class NativeIntensityStream:
    namespace: str
    source_manifest_sha256: str
    detector_revision_sha256: str
    transform_sha256: str
    first_available_at: float
    causal_samples: tuple[tuple[float, float], ...]
    frozen: bool
    endpoint_reconstructed: bool
    future_information_used: bool

    def validate(self) -> "NativeIntensityStream":
        if self.namespace not in NATIVE_RESERVED:
            raise IntensitySemanticsError("proven native stream must use an explicit native namespace")
        for f in ("source_manifest_sha256", "detector_revision_sha256", "transform_sha256"):
            _sha(getattr(self, f), f)
        try:
            avail = float(self.first_available_at)
        except (TypeError, ValueError, OverflowError) as exc:
            raise IntensitySemanticsError("first_available_at must be numeric") from exc
        if self.frozen is not True:
            raise IntensitySemanticsError("native intensity stream must be frozen")
        if self.endpoint_reconstructed or self.future_information_used:
            raise IntensitySemanticsError("retrospective/future-derived intensity cannot be native")
        if not self.causal_samples:
            raise IntensitySemanticsError("native intensity stream requires causal samples")
        last = None
        for ts, value in self.causal_samples:
            ts = float(ts); value = float(value)
            if ts < avail:
                raise IntensitySemanticsError("native sample precedes lawful stream availability")
            if last is not None and ts <= last:
                raise IntensitySemanticsError("native intensity timestamps must increase strictly")
            last = ts
        return self


@dataclass(frozen=True)
class ProxyIntensity:
    namespace: str
    source_manifest_sha256: str
    transform_sha256: str
    available_at: float
    causal_inputs_only: bool
    endpoint_reconstructed: bool
    claims_native_semantics: bool

    def validate(self) -> "ProxyIntensity":
        name = _id(self.namespace, "namespace")
        if name in NATIVE_RESERVED or "native" in name.lower():
            raise IntensitySemanticsError("proxy namespace must be explicitly non-native")
        if not name.startswith("v4_proxy_"):
            raise IntensitySemanticsError("proxy namespace must begin v4_proxy_")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        _sha(self.transform_sha256, "transform_sha256")
        float(self.available_at)
        if self.causal_inputs_only is not True:
            raise IntensitySemanticsError("proxy must use causal inputs only")
        if self.endpoint_reconstructed:
            raise IntensitySemanticsError("endpoint-reconstructed proxy is forbidden in live V4 state")
        if self.claims_native_semantics:
            raise IntensitySemanticsError("proxy may not claim native detector semantics")
        return self


def resolve_intensity(*, native: NativeIntensityStream | None = None,
                      proxy: ProxyIntensity | None = None, omitted: bool = False) -> dict[str, Any]:
    choices = int(native is not None) + int(proxy is not None) + int(bool(omitted))
    if choices != 1:
        raise IntensitySemanticsError("choose exactly one of proven native, explicit proxy, or omitted")
    if native is not None:
        native.validate()
        core = {"schema": SCHEMA, "mode": "PROVEN_NATIVE", "namespace": native.namespace,
                "binding": asdict(native), "native_semantics_claimed": True,
                "future_endpoint_reconstruction_used": False}
    elif proxy is not None:
        proxy.validate()
        core = {"schema": SCHEMA, "mode": "EXPLICIT_PROXY", "namespace": proxy.namespace,
                "binding": asdict(proxy), "native_semantics_claimed": False,
                "future_endpoint_reconstruction_used": False}
    else:
        core = {"schema": SCHEMA, "mode": "OMITTED", "namespace": None, "binding": None,
                "native_semantics_claimed": False, "future_endpoint_reconstruction_used": False}
    return {**core, "resolution_sha256": _hash(core), "v4_empirical_launch_authorized": False}


if __name__ == "__main__":
    print("V4 DETECTOR INTENSITY SEMANTICS CONTRACT READY; NO EMPIRICAL LAUNCH")
