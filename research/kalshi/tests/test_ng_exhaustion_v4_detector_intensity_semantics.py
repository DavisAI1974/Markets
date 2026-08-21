import pytest

from research.kalshi.ng_exhaustion_v4_detector_intensity_semantics import (
    DetectorIntensityError,
    NativeIntensityRow,
    explicit_proxy,
    prove_native_stream,
)

H="a"*64
T="b"*64


def row(second=1.0, **overrides):
    base=dict(
        second=second,ts_event=second,ts_recv=second+.01,available_at=second+.02,
        intensity=.4,source_object_id="native",source_revision="detector-v1",source_sha256=H,
        derived_from_future_endpoint=False,
    )
    base.update(overrides)
    return NativeIntensityRow(**base)


def test_proven_native_requires_causal_ordered_frozen_stream():
    out=prove_native_stream([row(1),row(2)],frozen_detector_sha256=T)
    assert out["status"]=="PROVEN_CAUSAL_NATIVE_INTENSITY"
    assert out["resolution"]["mode"]=="PROVEN_NATIVE"
    assert out["future_endpoint_reconstruction_used"] is False


def test_future_endpoint_reconstruction_is_never_native():
    with pytest.raises(DetectorIntensityError):
        prove_native_stream([row(1,derived_from_future_endpoint=True)],frozen_detector_sha256=T)


def test_native_stream_cannot_mix_revisions():
    with pytest.raises(DetectorIntensityError):
        prove_native_stream([row(1),row(2,source_revision="detector-v2")],frozen_detector_sha256=T)


def test_native_stream_cannot_backdate_availability():
    with pytest.raises(DetectorIntensityError):
        prove_native_stream([row(1,available_at=.5)],frozen_detector_sha256=T)


def test_proxy_is_explicitly_non_native():
    out=explicit_proxy(proxy_namespace="v4_proxy.polarity_roll20",proxy_source_sha256=H,transform_sha256=T)
    assert out["status"]=="EXPLICIT_NON_NATIVE_PROXY"
    assert out["resolution"]["mode"]=="EXPLICIT_PROXY"
    assert out["native_intensity_claimed"] is False


def test_proxy_cannot_masquerade_as_native():
    with pytest.raises(DetectorIntensityError):
        explicit_proxy(proxy_namespace="v4_proxy.native_exhaustion",proxy_source_sha256=H,transform_sha256=T)
    with pytest.raises(DetectorIntensityError):
        explicit_proxy(proxy_namespace="detector_intensity",proxy_source_sha256=H,transform_sha256=T)
