"""Claude R2/R5 and O2/O3/O4/O6 reproductions; no empirical runs."""
from dataclasses import replace
import json
import pytest
from forecast_bridge import prepare_frankie_forecast, route_frankie_forecast
from frankie_category_free import CategoryFreeRecord
from test_forecast_bridge import artifact, metadata, H


def test_route_requires_independent_publication_identity():
    f = artifact(); draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    with pytest.raises(ValueError, match='trusted|publication'):
        route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft)


def test_self_consistent_replacement_cannot_choose_its_own_trusted_root():
    f = artifact(); other = replace(f, input_hash='b'*64)
    draft = prepare_frankie_forecast(other, expected_digest=other.digest, metadata=metadata())
    with pytest.raises(ValueError, match='trusted|artifact'):
        route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
            expected_digest=f.digest, publication_hash=H, metadata=metadata())


def test_draft_cannot_replace_caller_metadata():
    f = artifact()
    forged = {**metadata(), 'disposition': 'CALL', 'plays_fired': ['FORGED_PLAY']}
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=forged)
    with pytest.raises(ValueError, match='metadata|projection'):
        route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
            expected_digest=f.digest, publication_hash=H, metadata=metadata())


def test_loader_cannot_mutate_trusted_caller_metadata():
    f = artifact(); meta = metadata()
    def loader():
        meta['disposition'] = 'CALL'
        meta['plays_fired'].append('FORGED_PLAY')
        return prepare_frankie_forecast(f, expected_digest=f.digest, metadata=meta)
    with pytest.raises(ValueError, match='metadata|projection'):
        route_frankie_forecast(enabled=True, legacy=None, load_native=loader,
            expected_digest=f.digest, publication_hash=H, metadata=meta)


def test_caller_metadata_is_explicitly_unverified_in_transport():
    f = artifact(); meta = metadata()
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=meta)
    record = route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
        expected_digest=f.digest, publication_hash=H, metadata=meta)
    stamp = json.loads(record.to_json())['stamp']
    assert stamp['metadata_verification'] == 'caller_supplied_unverified'
    assert stamp['publication_hash'] == H
    assert len(stamp['metadata_hash']) == 64


def test_standalone_record_has_no_one_dollar_accounting_slack():
    f = artifact(); draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    p = draft.payload; p['guessed_net_usd'] += .5
    with pytest.raises(ValueError, match='terminal|net'):
        CategoryFreeRecord(json.dumps(p), f.digest)
