"""Owner-approved nullable-confidence transport; synthetic fixtures only."""
from dataclasses import replace
import json
import pytest
from frankie_category_free import CategoryFreeRecord, validate_category_free, category_free_abstain
from frankie_contract import validate_bld1, ContractError
from test_forecast_bridge import artifact, metadata
from forecast_bridge import prepare_frankie_forecast, route_frankie_forecast


def payload():
    f = artifact()
    return prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata()).payload


def test_approved_route_returns_distinct_versioned_record_and_preserves_forecast():
    f = artifact(); prepared = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    record = route_frankie_forecast(enabled=True, legacy=lambda: pytest.fail('legacy invoked'), load_native=lambda: prepared)
    assert isinstance(record, CategoryFreeRecord)
    assert record.payload == prepared.payload and record.artifact_digest == f.digest
    envelope = json.loads(record.to_json())
    assert envelope['stamp']['contract_id'] == 'BOSS_FRANKIE_CATEGORY_FREE_V1'
    assert envelope['payload']['confidence'] is None and len(envelope['payload']) == 12
    with pytest.raises(ContractError): validate_bld1(record.payload)
    changed = record.payload; changed['path_p50_curve'][0][1] = 99
    assert record.payload['path_p50_curve'][0][1] == 0


@pytest.mark.parametrize('confidence', ['low', 'med', 'medium', 'high', 0, .9, False, 'null'])
def test_only_null_confidence_is_accepted(confidence):
    with pytest.raises(ValueError): validate_category_free({**payload(), 'confidence': confidence})


@pytest.mark.parametrize('change', [dict(probability=.7), dict(reasoning=''),
    dict(guessed_net_usd=float('nan')), dict(path_p50_curve=[[20., 1.], [24., 2.]]),
    dict(path_p50_curve=[[20., 0.], [24., 999.]]), dict(state_defects_and_gaps_reported=['fatal'])])
def test_closed_fields_and_forecast_accounting_are_validated(change):
    with pytest.raises(ValueError): validate_category_free({**payload(), **change})


def test_missing_confidence_is_not_silently_filled():
    p = payload(); del p['confidence']
    with pytest.raises(ValueError): validate_category_free(p)


def test_safety_abstain_is_complete_and_category_free():
    record = category_free_abstain(metadata(), ('native_unavailable: synthetic timeout',))
    p = record.payload
    assert len(p) == 12 and p['confidence'] is None and p['disposition'] == 'ABSTAIN'
    assert p['guessed_net_usd'] == p['overnight_gap_usd'] == 0
    assert p['path_p50_curve'] == [[20., 0.], [24., 0.]]
    assert p['plays_fired'] == p['plays_stood_down'] == []
    assert p['state_defects_and_gaps_reported'] == ['native_unavailable: synthetic timeout']
    assert record.artifact_digest is None


def test_forged_preparation_is_revalidated_at_enabled_boundary():
    f = artifact(); prepared = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    forged = replace(prepared, payload_json=json.dumps({**prepared.payload, 'confidence': 'high'}))
    with pytest.raises(ValueError): route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: forged)


def test_accounting_valid_forgery_cannot_reuse_native_artifact_identity():
    f = artifact(); prepared = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    altered = prepared.payload
    altered['guessed_net_usd'] += 100; altered['overnight_gap_usd'] += 100
    forged = replace(prepared, payload_json=json.dumps(altered))
    with pytest.raises(ValueError, match='native artifact'):
        route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: forged)
