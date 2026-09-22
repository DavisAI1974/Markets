"""Causal Frankie lessons reach the exact Granite request and require acknowledgment."""
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import pytest
from research.kalshi.frankie_boss import critic_knowledge as knowledge
from research.kalshi.frankie_boss import granite_context as native
from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.granite_context_route import context_route
from test_feedback_cycle import fixture as cycle_fixture
from test_granite_stacked_route_integration import snapshot
from test_granite_parser import valid_output

def record(request_id='prior', available_ns=1):
    return dict(request_id=request_id, available_ns=available_ns, feedback_hash='a'*64,
        principal_receipt_hash='b'*64, training_checkpoint_hash='c'*64,
        lessons=[dict(text='FRANKIE_PRIOR_LESSON_MUST_REACH_GRANITE')], frozen_memory_sha256='d'*64)

def build(records=None, *, cutoff=2, request_id='current'):
    return knowledge.build_knowledge([record()] if records is None else records,
        cutoff_ns=cutoff, request_id=request_id)

def test_canonical_causal_detached_json_stable():
    ns=1790057801123456789
    a=record('a',ns); b=record('b',ns); future=record('future',ns+1)
    a['lessons']=({'text':'tuple canonicalizes','details':(1,2)},)
    rows=[b,future,a]; frozen=copy.deepcopy(rows)
    value=build(rows,cutoff=ns)
    assert rows==frozen
    assert [e['record']['request_id'] for e in value['entries']]==['a','b']
    assert value['entries'][0]['record']['lessons']==[{'text':'tuple canonicalizes','details':[1,2]}]
    assert all(e['lesson_hash']==evidence_hash(e['record']) for e in value['entries'])
    assert build([a,b,future],cutoff=ns)==value
    assert evidence_hash(json.loads(json.dumps(value)))==evidence_hash(value)
    knowledge.validate_knowledge(value,cutoff_ns=ns,request_id='current')
    a['lessons'][0]['text']='changed'
    assert value['entries'][0]['record']['lessons'][0]['text']=='tuple canonicalizes'

def test_empty_explicit():
    value=build([record('future',3)])
    assert value['entries']==[]
    knowledge.validate_knowledge(value,cutoff_ns=2,request_id='current')

@pytest.mark.parametrize('value',[True,1.5,'10',None])
def test_invalid_availability(value):
    item=record(); item['available_ns']=value
    with pytest.raises(ValueError): build([item])

@pytest.mark.parametrize('field',['feedback_hash','principal_receipt_hash','training_checkpoint_hash','frozen_memory_sha256'])
@pytest.mark.parametrize('value',['f'*63,'z'*64,None])
def test_invalid_provenance_even_future(field,value):
    item=record('future',3); item[field]=value
    with pytest.raises(ValueError): build([item])

@pytest.mark.parametrize('rows',[[record('same'),record('same',2)],[record('current')],
    [record('future',3),record('future',4)],[record('current',3)]])
def test_duplicate_and_current_refuse(rows):
    with pytest.raises(ValueError): build(rows)

def test_closed_fields():
    for field in record():
        item=record(); del item[field]
        with pytest.raises(ValueError): build([item])
    item=record(); item['extra']='unattested'
    with pytest.raises(ValueError): build([item])

def test_inner_hash_order_cutoff_and_request():
    original=build([record('a',1),record('b',2)])
    altered=copy.deepcopy(original); altered['entries'][0]['record']['lessons'][0]['text']='tampered'
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    altered=copy.deepcopy(original); altered['entries'].reverse()
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    altered=copy.deepcopy(original); altered['entries'][0]['record']['available_ns']=3
    altered['entries'][0]['lesson_hash']=evidence_hash(altered['entries'][0]['record'])
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    with pytest.raises(ValueError): knowledge.validate_knowledge(original,cutoff_ns=1)
    with pytest.raises(ValueError): knowledge.validate_knowledge(original,request_id='other')

def test_exact_stacked_prompt_and_response_acknowledgment(tmp_path):
    source=snapshot(tmp_path); cutoff=native.unpack(json.loads(source.text)['receipt'])['as_of']
    bundle=build([record('prior',cutoff),record('future',cutoff+1)],cutoff=cutoff)
    route=context_route('stacked_v1'); encoded=route.encode(source,knowledge=bundle)
    assert route.native(encoded).text==source.text
    prompt=route.build_prompt(encoded).text
    assert 'FRANKIE_PRIOR_LESSON_MUST_REACH_GRANITE' in prompt
    assert '"request_id":"future"' not in prompt
    value=valid_output(encoded)
    assert route.score(json.dumps(value),encoded)[1].name!='L4'
    value.update(knowledge_hash=evidence_hash(bundle),knowledge_review=[
        dict(lesson_hash=e['lesson_hash'],assessment='Considered as prior inference, not raw evidence')
        for e in bundle['entries']])
    assert route.score(json.dumps(value),encoded)[1].name=='L4'
    value['knowledge_hash']='f'*64
    assert route.score(json.dumps(value),encoded)[1].name!='L4'
    value['knowledge_hash']=evidence_hash(bundle);value['knowledge_review']=[]
    assert route.score(json.dumps(value),encoded)[1].name!='L4'

def test_outer_hash_cannot_hide_knowledge_tamper(tmp_path):
    source=snapshot(tmp_path); cutoff=native.unpack(json.loads(source.text)['receipt'])['as_of']
    route=context_route('stacked_v1')
    encoded=route.encode(source,knowledge=build(cutoff=cutoff))
    body=json.loads(encoded.text);body['knowledge']['entries'][0]['record']['lessons'][0]['text']='tampered'
    text=native._text(body)
    with pytest.raises(ValueError): route.parse(text,expected_hash=hashlib.sha256(text.encode()).hexdigest())
