from __future__ import annotations

import dataclasses
import pytest

from research.kalshi.ng_exhaustion_v4_detector_intensity_semantics import (
    IntensitySemanticsError,
    NativeIntensityStream,
    ProxyIntensity,
    resolve_intensity,
)

H = "1" * 64


def native() -> NativeIntensityStream:
    return NativeIntensityStream(
        namespace="detector_native_intensity",
        source_manifest_sha256=H,
        detector_revision_sha256="2" * 64,
        transform_sha256="3" * 64,
        first_available_at=100.0,
        causal_samples=((100.0, 0.1), (101.0, 0.2), (102.0, 0.4)),
        frozen=True,
        endpoint_reconstructed=False,
        future_information_used=False,
    )


def proxy() -> ProxyIntensity:
    return ProxyIntensity(
        namespace="v4_proxy_exhaustion_pressure",
        source_manifest_sha256=H,
        transform_sha256="4" * 64,
        available_at=100.0,
        causal_inputs_only=True,
        endpoint_reconstructed=False,
        claims_native_semantics=False,
    )


def test_proven_native_stream_is_explicit_and_bound():
    out = resolve_intensity(native=native())
    assert out["mode"] == "PROVEN_NATIVE"
    assert out["native_semantics_claimed"] is True
    assert out["v4_empirical_launch_authorized"] is False


def test_native_stream_rejects_future_or_endpoint_reconstruction():
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(native=dataclasses.replace(native(), future_information_used=True))
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(native=dataclasses.replace(native(), endpoint_reconstructed=True))


def test_native_stream_rejects_nonmonotone_or_preeffective_samples():
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(native=dataclasses.replace(native(), causal_samples=((99.0, 0.1), (100.0, 0.2))))
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(native=dataclasses.replace(native(), causal_samples=((100.0, 0.1), (100.0, 0.2))))


def test_proxy_is_explicitly_non_native():
    out = resolve_intensity(proxy=proxy())
    assert out["mode"] == "EXPLICIT_PROXY"
    assert out["native_semantics_claimed"] is False


def test_proxy_cannot_borrow_native_name_or_claim_native_semantics():
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(proxy=dataclasses.replace(proxy(), namespace="detector_intensity"))
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(proxy=dataclasses.replace(proxy(), claims_native_semantics=True))


def test_proxy_rejects_retrospective_endpoint_reconstruction():
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(proxy=dataclasses.replace(proxy(), endpoint_reconstructed=True))


def test_omission_is_legal_and_safer_than_unproven_native_label():
    out = resolve_intensity(omitted=True)
    assert out["mode"] == "OMITTED"
    assert out["namespace"] is None


def test_exactly_one_intensity_mode_is_required():
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity()
    with pytest.raises(IntensitySemanticsError):
        resolve_intensity(native=native(), proxy=proxy())
