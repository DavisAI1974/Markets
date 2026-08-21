import pytest

from research.kalshi.ng_exhaustion_v4_detector_intensity import (
    DetectorIntensityError,
    ExplicitProxyManifest,
    NativeIntensitySample,
    NativeIntensityStreamManifest,
    default_v4_proxy,
    resolve_detector_intensity,
)

H = "a" * 64
H2 = "b" * 64


def test_default_proxy_is_explicitly_non_native():
    proxy = default_v4_proxy(transform_sha256=H, source_sha256=H2)
    out = resolve_detector_intensity(proxy=proxy)
    assert out["mode"] == "EXPLICIT_PROXY"
    assert out["namespace"].startswith("v4_proxy.")
    assert out["fake_native_reconstruction"] is False


def test_proxy_rejects_native_name_and_future_endpoint_use():
    with pytest.raises(DetectorIntensityError):
        ExplicitProxyManifest(
            namespace="detector_native_intensity",
            transform_sha256=H,
            source_sha256=H,
            causal_inputs_only=True,
            uses_future_endpoint_information=False,
            description="invalid proxy name",
        ).validate()
    with pytest.raises(DetectorIntensityError):
        ExplicitProxyManifest(
            namespace="v4_proxy.roll20",
            transform_sha256=H,
            source_sha256=H,
            causal_inputs_only=True,
            uses_future_endpoint_information=True,
            description="future endpoint use",
        ).validate()


def test_native_rejects_retrospective_endpoint_reconstruction():
    with pytest.raises(DetectorIntensityError):
        NativeIntensityStreamManifest(
            namespace="detector_native_intensity",
            source_sha256=H,
            detector_revision_sha256=H,
            stream_content_sha256=H,
            samples=(NativeIntensitySample("e1", 10.0, 10.1, 0.4),),
            frozen=True,
            derived_from_retrospective_endpoints=True,
        ).validate()


def test_proven_native_requires_frozen_chronological_samples():
    native = NativeIntensityStreamManifest(
        namespace="detector_native_intensity",
        source_sha256=H,
        detector_revision_sha256=H2,
        stream_content_sha256=H,
        samples=(
            NativeIntensitySample("e1", 10.0, 10.1, 0.4),
            NativeIntensitySample("e1", 11.0, 11.0, 0.3),
        ),
        frozen=True,
        derived_from_retrospective_endpoints=False,
    )
    out = resolve_detector_intensity(native=native)
    assert out["mode"] == "PROVEN_NATIVE"
    assert out["fake_native_reconstruction"] is False


def test_native_and_proxy_are_mutually_exclusive():
    native = NativeIntensityStreamManifest(
        namespace="detector_native_intensity",
        source_sha256=H,
        detector_revision_sha256=H,
        stream_content_sha256=H,
        samples=(NativeIntensitySample("e1", 10.0, 10.0, 0.4),),
        frozen=True,
        derived_from_retrospective_endpoints=False,
    )
    proxy = default_v4_proxy(transform_sha256=H, source_sha256=H)
    with pytest.raises(DetectorIntensityError):
        resolve_detector_intensity(native=native, proxy=proxy)
