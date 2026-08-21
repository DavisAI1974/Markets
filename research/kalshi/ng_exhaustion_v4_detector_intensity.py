#!/usr/bin/env python3
"""Detector-intensity semantic boundary for NG Exhaustion V4.

A field may be called detector-native intensity only when a frozen causal stream
is proven with source/revision identities and lawful availability. Otherwise V4
must use an explicitly non-native proxy namespace. Retrospective endpoint facts
may never be used to reconstruct a fake native continuous stream.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "NG_EXHAUSTION_V4_DETECTOR_INTENSITY_V1"
NATIVE_NAMES = frozenset({"detector_native_intensity", "native_exhaustion_intensity", "detector_intensity"})


class DetectorIntensityError(ValueError):
    pass


def _sha(v: Any, field: str) -> str:
    text = str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise DetectorIntensityError(f"{field} must be lowercase SHA-256")
    return text


def _finite(v: Any, field: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DetectorIntensityError(f"{field} must be finite") from exc
    if not math.isfinite(x):
        raise DetectorIntensityError(f"{field} must be finite")
    return x


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class NativeIntensitySample:
    event_id: str
    sample_at: float
    available_at: float
    value: float

    def validate(self) -> "NativeIntensitySample":
        if not str(self.event_id or "").strip():
            raise DetectorIntensityError("event_id required")
        sample = _finite(self.sample_at, "sample_at")
        available = _finite(self.available_at, "available_at")
        _finite(self.value, "value")
        if available < sample:
            raise DetectorIntensityError("native sample cannot be available before it exists")
        return self


@dataclass(frozen=True)
class NativeIntensityStreamManifest:
    namespace: str
    source_sha256: str
    detector_revision_sha256: str
    stream_content_sha256: str
    samples: tuple[NativeIntensitySample, ...]
    frozen: bool
    derived_from_retrospective_endpoints: bool

    def validate(self) -> "NativeIntensityStreamManifest":
        if self.namespace not in NATIVE_NAMES:
            raise DetectorIntensityError("proven native stream must use an explicit native namespace")
        for field in ("source_sha256", "detector_revision_sha256", "stream_content_sha256"):
            _sha(getattr(self, field), field)
        if not self.frozen:
            raise DetectorIntensityError("native stream must be frozen")
        if self.derived_from_retrospective_endpoints:
            raise DetectorIntensityError("retrospective endpoint reconstruction cannot prove native intensity")
        if not self.samples:
            raise DetectorIntensityError("native proof requires samples")
        last = float("-inf")
        for sample in self.samples:
            sample.validate()
            if sample.sample_at <= last:
                raise DetectorIntensityError("native samples must be strictly chronological")
            last = sample.sample_at
        return self

    @property
    def manifest_hash(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["samples"] = [asdict(x) for x in self.samples]
        return _hash({"schema": SCHEMA, "native": payload})


@dataclass(frozen=True)
class ExplicitProxyManifest:
    namespace: str
    transform_sha256: str
    source_sha256: str
    causal_inputs_only: bool
    uses_future_endpoint_information: bool
    description: str

    def validate(self) -> "ExplicitProxyManifest":
        ns = str(self.namespace or "").strip()
        if not ns or ns in NATIVE_NAMES or "native" in ns.lower():
            raise DetectorIntensityError("proxy namespace must be visibly non-native")
        if not ns.startswith("v4_proxy."):
            raise DetectorIntensityError("proxy namespace must use v4_proxy.*")
        _sha(self.transform_sha256, "transform_sha256")
        _sha(self.source_sha256, "source_sha256")
        if self.causal_inputs_only is not True:
            raise DetectorIntensityError("proxy requires causal inputs only")
        if self.uses_future_endpoint_information:
            raise DetectorIntensityError("proxy may not use future endpoint information")
        if not str(self.description or "").strip():
            raise DetectorIntensityError("proxy description required")
        return self

    @property
    def manifest_hash(self) -> str:
        self.validate()
        return _hash({"schema": SCHEMA, "proxy": asdict(self)})


def resolve_detector_intensity(
    *,
    native: NativeIntensityStreamManifest | None = None,
    proxy: ExplicitProxyManifest | None = None,
) -> dict[str, Any]:
    if native is not None and proxy is not None:
        raise DetectorIntensityError("choose exactly one native proof or explicit proxy")
    if native is not None:
        native.validate()
        return {
            "schema": SCHEMA,
            "mode": "PROVEN_NATIVE",
            "namespace": native.namespace,
            "resolution_hash": native.manifest_hash,
            "fake_native_reconstruction": False,
        }
    if proxy is not None:
        proxy.validate()
        return {
            "schema": SCHEMA,
            "mode": "EXPLICIT_PROXY",
            "namespace": proxy.namespace,
            "resolution_hash": proxy.manifest_hash,
            "fake_native_reconstruction": False,
        }
    return {
        "schema": SCHEMA,
        "mode": "OMITTED",
        "namespace": None,
        "resolution_hash": _hash({"schema": SCHEMA, "mode": "OMITTED"}),
        "fake_native_reconstruction": False,
    }


def default_v4_proxy(*, transform_sha256: str, source_sha256: str) -> ExplicitProxyManifest:
    """Conservative V4 choice until a real detector-native stream is independently proven."""
    return ExplicitProxyManifest(
        namespace="v4_proxy.polarity_oriented_roll20_trajectory",
        transform_sha256=transform_sha256,
        source_sha256=source_sha256,
        causal_inputs_only=True,
        uses_future_endpoint_information=False,
        description="Causal polarity-oriented roll-20 trajectory proxy; explicitly not detector-native intensity.",
    ).validate()
