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


def test_nonfatal_gaps_are_visible_with_call_without_changing_twelve_fields():
    from frankie_category_free import report_nonfatal_gaps
    f = artifact(); meta = {**metadata(), 'disposition': 'CALL', 'plays_fired': ['VALID_CALLER_PLAY']}
    annotated = report_nonfatal_gaps(meta, ['calibration absent', 'optional QSV context unavailable'])
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=annotated)
    record = route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
        expected_digest=f.digest, publication_hash=H, metadata=annotated)
    assert len(record.payload) == 12 and record.payload['disposition'] == 'CALL'
    assert record.payload['state_defects_and_gaps_reported'] == []
    assert 'calibration absent' in record.payload['reasoning']
    assert 'QSV context unavailable' in record.payload['reasoning']
    assert meta['reasoning'] == metadata()['reasoning']


def test_integrity_abstention_retains_source_play_history_in_reasoning():
    from frankie_category_free import category_free_abstain
    meta = {**metadata(), 'plays_fired': ['FIRST'], 'plays_stood_down': ['SECOND']}
    record = category_free_abstain(meta, ['source integrity failed'])
    p = record.payload
    assert p['plays_fired'] == p['plays_stood_down'] == []
    assert 'FIRST' in p['reasoning'] and 'SECOND' in p['reasoning']
    assert p['disposition'] == 'ABSTAIN' and p['guessed_net_usd'] == 0


def session_artifact(start, end):
    from datetime import datetime
    import torch
    from forecast_artifact import freeze_forecast
    from test_forecast_session import stopped_decoder
    f = artifact()
    opening = int(datetime.fromisoformat(start).timestamp())*10**9
    closing = int(datetime.fromisoformat(end).timestamp())*10**9
    prior = replace(f.session.prior_close, event_ns=opening-2*10**9, receive_ns=opening-2*10**9)
    s = replace(f.session, open_ns=opening, close_ns=closing,
        event_cutoff_ns=opening-10**9, receive_cutoff_ns=opening-10**9, prior_close=prior)
    return freeze_forecast(stopped_decoder(), torch.ones(4, dtype=torch.float64), s,
        native_model_hash=H, input_hash=H, arm_hash=H)


def test_futures_style_session_reports_explicit_twenty_hour_clock_boundary():
    f = session_artifact('2026-11-02T18:00:00-05:00', '2026-11-03T17:00:00-05:00')
    with pytest.raises(ValueError, match='20:00'):
        prepare_frankie_forecast(f, expected_digest=f.digest, metadata={**metadata(), 'date': '2026-11-03'})


def test_immediate_stop_two_point_equity_curve_is_valid_native_output():
    f = session_artifact('2026-11-02T09:30:00-05:00', '2026-11-02T16:00:00-05:00')
    assert len(f.points) == 2
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    record = route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: draft,
        expected_digest=f.digest, publication_hash=H, metadata=metadata())
    assert [p[0] for p in record.payload['path_p50_curve']] == [9.5, 16.]
