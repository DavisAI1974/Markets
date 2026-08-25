from __future__ import annotations

import pytest

from markets_adapter import (
    MARKET_FEATURE_SPEC,
    MarketBar,
    MarketChunk,
    MarketChunkEncoder,
    MarketFeatures,
    MarketQuery,
)
from research.kalshi.frankie_boss.trunk import TrunkConfig
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY


def _chunk() -> MarketChunk:
    bars = [
        MarketBar(
            ts=float(index),
            close=100.0 + index,
            open_=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            volume=10.0,
            buy_vol=6.0,
            sell_vol=4.0,
        )
        for index in range(8)
    ]
    return MarketChunk(
        chunk_id="chunk-1",
        source_id="source-1",
        window_start=0,
        window_end=len(bars),
        bars=bars,
    )


def test_qsv_registry_is_the_actual_market_encoder_output_order() -> None:
    encoder = MarketChunkEncoder()
    vector = encoder.encode([_chunk()])[0]

    assert tuple(QSV_FEATURE_REGISTRY) == encoder.feature_registry
    assert QSV_FEATURE_REGISTRY[: len(MARKET_FEATURE_SPEC)] == tuple(
        name for name, _ in MARKET_FEATURE_SPEC
    )
    assert len(vector) == len(QSV_FEATURE_REGISTRY)


def test_registry_names_and_emission_share_one_ordered_spec() -> None:
    class DistinctFeatureEncoder(MarketChunkEncoder):
        def _extract(self, chunk: MarketChunk) -> MarketFeatures:
            return MarketFeatures(
                ret_mean=1.0,
                ret_std=2.0,
                ret_skew=3.0,
                ret_kurt=4.0,
                autocorr_lag1=5.0,
                mean_dipole=6.0,
                mean_ofi=7.0,
                volume_zscore=8.0,
                realized_vol=9.0,
                range_atr=10.0,
                spectral_energy=11.0,
                spectral_entropy=12.0,
                peak_frequency=13.0,
                spectral_centroid=14.0,
                coefficients=[],
            )

    encoder = DistinctFeatureEncoder(d_enc=len(MARKET_FEATURE_SPEC))
    named = dict(zip(encoder.feature_registry, encoder.encode([_chunk()])[0]))

    assert named == {
        name: float(index)
        for index, (name, _) in enumerate(MARKET_FEATURE_SPEC, start=1)
    }


def test_non_default_encoder_registry_is_derived_from_its_configuration() -> None:
    encoder = MarketChunkEncoder(d_enc=len(MARKET_FEATURE_SPEC) + 3)

    assert encoder.feature_registry == tuple(name for name, _ in MARKET_FEATURE_SPEC) + (
        "fft_magnitude_0",
        "fft_magnitude_1",
        "fft_magnitude_2",
    )
    assert len(encoder.encode([_chunk()])[0]) == len(encoder.feature_registry)


def test_summary_only_encoder_and_query_have_no_phantom_coefficient_slot() -> None:
    encoder = MarketChunkEncoder(d_enc=len(MARKET_FEATURE_SPEC))
    target = encoder._extract(_chunk())

    assert len(encoder.encode([_chunk()])[0]) == len(encoder.feature_registry)
    query = MarketQuery(d_enc=len(MARKET_FEATURE_SPEC))
    assert len(query.from_regime_target(target)) == len(encoder.feature_registry)
    assert query.feature_registry == encoder.feature_registry


def test_encoder_rejects_width_below_the_named_market_features() -> None:
    with pytest.raises(ValueError, match="named market features"):
        MarketChunkEncoder(d_enc=len(MARKET_FEATURE_SPEC) - 1)


def test_trunk_qsv_dimension_is_registry_derived_and_drift_fails_closed() -> None:
    assert TrunkConfig().qsv_dim == len(QSV_FEATURE_REGISTRY)

    with pytest.raises(ValueError, match=r"len\(QSV_FEATURE_REGISTRY\)"):
        TrunkConfig(qsv_dim=len(QSV_FEATURE_REGISTRY) - 1)


def test_qsv_is_registered_but_dormant_by_default() -> None:
    cfg = TrunkConfig()

    assert cfg.qsv_dim == len(QSV_FEATURE_REGISTRY)
    assert cfg.use_qsv is False
