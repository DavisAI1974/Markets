"""Historical reads are distinct from runtime-locked reproduction (Claude R1)."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
import torch
from forecast_artifact import NativeForecastArtifact, DecoderSnapshot
from forecast_bridge import prepare_frankie_forecast, route_frankie_forecast
from test_forecast_bridge import artifact, metadata, H


def test_archived_v1_payload_is_readable_without_loading_decoder(monkeypatch):
    saved = json.loads((Path(__file__).parent/'fixtures/native_forecast_bdd7663.json').read_text())
    monkeypatch.setattr(DecoderSnapshot, 'restore', lambda self: pytest.fail('decoder used during historical read'))
    frozen = NativeForecastArtifact.from_payload(saved['payload'].encode(), expected_digest=saved['digest'])
    assert frozen.payload == saved['payload'].encode() and frozen.digest == saved['digest']
    assert frozen.session.prior_close is None  # Preserve old omission, never backfill history.
    draft = prepare_frankie_forecast(frozen, expected_digest=saved['digest'], metadata=metadata())
    record = route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
        expected_digest=saved['digest'], publication_hash=H, metadata=metadata())
    assert record.payload['guessed_net_usd'] == frozen.net_usd
    assert record.reproduction_status == 'unknown'


def test_published_receipt_remains_a_producer_claim_after_runtime_drift(tmp_path, monkeypatch):
    import forecast_artifact
    from test_frankie_forecast_consumer import build_refresh, update, context, consume_forecast
    bridge, sessions = build_refresh(tmp_path); pub = update(bridge, sessions)[0]
    monkeypatch.setattr(forecast_artifact, 'runtime_hash', lambda: 'b'*64)
    record = consume_forecast(enabled=True, legacy=None, book=bridge.book,
        publication_hash=pub.receipt_hash, metadata=context())
    assert record.artifact_digest == pub.selected.candidate_id
    assert record.reproduction_status == 'publisher_verified'
    f = NativeForecastArtifact.from_payload(pub.selected.forecast_artifact, expected_digest=pub.selected.candidate_id)
    with pytest.raises(ValueError, match='runtime'): f.verify_reproduction()


def test_runtime_drift_blocks_queries_and_reproduction_but_not_reads(monkeypatch):
    import forecast_artifact
    f = artifact(); raw = f.payload
    monkeypatch.setattr(forecast_artifact, 'runtime_hash', lambda: 'b'*64)
    restored = NativeForecastArtifact.from_payload(raw, expected_digest=f.digest)
    assert restored.payload == raw
    with pytest.raises(ValueError, match='runtime'): restored.query(f.points[-1].time_ns)
    with pytest.raises(ValueError, match='runtime'): restored.verify_reproduction()


def test_thread_count_drift_preserves_historical_projection():
    f = artifact(); raw = f.payload; original = torch.get_num_threads()
    try:
        torch.set_num_threads(1 if original != 1 else 2)
        restored = NativeForecastArtifact.from_payload(raw, expected_digest=f.digest)
        assert prepare_frankie_forecast(restored, expected_digest=f.digest, metadata=metadata()).payload['guessed_net_usd'] == f.net_usd
        with pytest.raises(ValueError, match='runtime'): restored.verify_reproduction()
    finally:
        torch.set_num_threads(original)


def test_structural_parse_keeps_quantile_and_observation_validation():
    f = artifact()
    for changes in (dict(gap_quantiles=(0., float('nan'), 1.)),
                    dict(gap_quantiles=(1., 0., -1.)), dict(gap_observed=True),
                    dict(points=(replace(f.points[0], quantiles=(-1., 0., 1.)), *f.points[1:]))):
        with pytest.raises(ValueError): replace(f, **changes)


def test_structural_parse_does_not_certify_reproduction():
    f = artifact()
    # Interior values can be structurally sound but not produced by the decoder.
    p = f.points[1]
    changed = replace(f, points=(f.points[0], replace(p, quantiles=tuple(v+.1 for v in p.quantiles)), *f.points[2:]))
    assert NativeForecastArtifact.from_payload(changed.payload, expected_digest=changed.digest) == changed
    with pytest.raises(ValueError, match='query|point'): changed.verify_reproduction()


@pytest.mark.parametrize('dimension', [4.0, True])
def test_snapshot_dimensions_are_exact_positive_integers(dimension):
    from c15_journal import unpack, pack, canonical_bytes
    f = artifact(); weights = unpack(json.loads(f.snapshot.weights))
    value = weights['session_projection.weight']
    value['shape'] = (dimension, value['shape'][1])
    with pytest.raises(ValueError, match='tensor'):
        replace(f.snapshot, weights=canonical_bytes(pack(weights)))
