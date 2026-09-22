"""New attested-source/runtime seam; no model, market labels, or source ingestion."""
import json
import pytest
from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
from research.kalshi.frankie_boss.frankie_principal_adapter import canonical,digest


def fixture(tmp_path):
    convention={'usd_per_price_unit':1.0,'actual_ng_contract_multiplier':None,'usd_basis':'explicit development numeraire'}
    calendar={'rule':'source-only'};timing={'turn_delta_ticks':1};query={'seed':'fixed'}
    cycles=[]
    for i in range(19):
        as_of=100+i
        cycles.append({'cycle_index':i,'historical_group_index':i,
            'source_prefix':{'source_cursor':i,'receive_cutoff_ns':as_of,'event_cutoff_ns':as_of},
            'learning_cutoff_ns':as_of+1,'learning_through_source_cursor':i+1,'path_query_offsets_ns':[150],
            'forecast_session':{'instrument':'source','session_id':'own-day','open_ns':10,'close_ns':200,
                'event_cutoff_ns':as_of,'receive_cutoff_ns':as_of,'usd_per_price_unit':1.0,'tick_size':0.001,
                'convention_hash':digest(convention),'calendar_hash':digest(calendar),'source_hash':None,
                'knot_policy':{'quantum_ns':1,'max_interior':100},
                'prior_close':{'event_ns':1,'receive_ns':2,'price':5.628,'evidence_hash':'a'*64},
                'opening':{'event_ns':10,'receive_ns':11,'price':5.634,'evidence_hash':'b'*64},'known_marks':[]}})
    body={'schema':'FRANKIE_OWN_SOURCE_CONTRACT_V1','convention':convention,'calendar':calendar,
        'timing_policy':timing,'query_policy':query,'cycles':cycles}
    for name in ('convention','calendar','timing_policy','query_policy'):body[name+'_hash']=digest(body[name])
    path=tmp_path/'contract.json';path.write_bytes(canonical(body))
    return path,digest(body),{'through_cursor':0,'as_of':100,'source_as_of':100,'source_hash':'c'*64}


def test_bind_preserves_actual_session_and_policy_with_verified_runtime_hash(tmp_path):
    path,expected,prefix=fixture(tmp_path)
    result=bind_cycle(path,expected,0,prefix)
    target,session=result['sessions'][0]
    assert target.target_ns==200 and session.source_hash=='c'*64
    assert session.prior_close.price==5.628 and session.usd_per_price_unit==1.0
    assert result['learning_cutoff_ns']==101 and result['split']['cycles'][0]['through_cursor']==0
    assert json.loads(path.read_bytes())['cycles'][0]['forecast_session']['source_hash'] is None


def test_bind_rejects_changed_source_clocks_and_contract(tmp_path):
    path,expected,prefix=fixture(tmp_path)
    with pytest.raises(ValueError,match='causal clocks'):
        bind_cycle(path,expected,0,dict(prefix,as_of=101))
    with pytest.raises(ValueError,match='independent pin'):
        bind_cycle(path,'f'*64,0,prefix)
    body=json.loads(path.read_bytes());body['cycles'][0]['forecast_session']['opening']['receive_ns']=101
    path.write_bytes(canonical(body))
    with pytest.raises(ValueError,match='causally available'):
        bind_cycle(path,digest(body),0,prefix)


def test_metadata_is_explicit_abstention_with_host_reported_defects(tmp_path):
    from research.kalshi.frankie_boss.source_contract_runtime import metadata_for_binding
    path,expected,prefix=fixture(tmp_path)
    bound=bind_cycle(path,expected,0,prefix)
    metadata=metadata_for_binding(bound,state_defects_and_gaps_reported=['explicit missing source'])
    assert metadata[0][0]==bound['sessions'][0][0].digest
    assert metadata[0][1]['disposition']=='ABSTAIN'
    assert metadata[0][1]['state_defects_and_gaps_reported']==['explicit missing source']
    assert metadata[0][1]['plays_fired']==[]


def test_trading_day_binding_carries_exact_authored_bytes_and_dynamic_roster(tmp_path):
    path, _, prefix = fixture(tmp_path)
    body = json.loads(path.read_bytes())
    body.update(schema='FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1', trading_day='20211004',
                source_manifest_hash='a'*64, cycle_count=2, cycles=body['cycles'][:2])
    raw = json.dumps(body, indent=2).encode()
    path.write_bytes(raw)
    import hashlib
    bound = bind_cycle(path, hashlib.sha256(raw).hexdigest(), 0, prefix)
    assert bound['cycle_count'] == 2 and bound['trading_day'] == '20211004'
    assert bound['authored_contract_json'].encode() == raw
    with pytest.raises(ValueError, match='chronological cycle'):
        bind_cycle(path, hashlib.sha256(raw).hexdigest(), 2, prefix)
