"""Prior learning stays visible across replay cutoffs and bound to the next teaching exchange."""
import copy
import importlib
import json
import pytest
from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.critic_knowledge import build_knowledge, CUMULATIVE
from research.kalshi.frankie_boss.dipole_classroom_integration import prepare_integrated_cycle
from research.kalshi.frankie_boss.dipole_classroom_final_review import final_model_visible_classroom, _render_final_pre
from test_dipole_classroom import _teacher
from test_box_classroom_mode_progression import C

def api():
    return importlib.import_module('research.kalshi.frankie_boss.dipole_classroom_learning')

def learning(request='run-cycle-01', cutoff=2_000_000):
    record = dict(request_id='run-cycle-00',available_ns=1790057801123456789,
        feedback_hash='a'*64,principal_receipt_hash='b'*64,training_checkpoint_hash='c'*64,
        frozen_memory_sha256='d'*64,lessons=[dict(text='PRIOR_FULL_RESEARCH_EXPLANATION',
            status='unverified', unsuccessful_idea='RETAIN_FAILED_APPROACH')])
    knowledge=build_knowledge([record],cutoff_ns=cutoff,request_id=request,learning_policy=CUMULATIVE)
    origin=dict(request_id='run-cycle-00',as_of=2_000_000,through_cursor=6,
        **{k:'e'*64 for k in ('binding_hash','feedback_stage_hash','training_hash','completion_hash','source_hash','input_hash')})
    knowledge['origins']=[origin]
    exchange=dict(origin=origin,frankie_response=dict(observations=['ALL_PRIOR_OBSERVATIONS'],
        uncertainty='UNRESOLVED_PRIOR_QUESTION'),teacher_correction=dict(explanation='FULL_TEACHER_CORRECTION'),
        frankie_correction_response=dict(explanation='FRANKIE_REVISED_REASONING'))
    exchange['exchange_hash']=evidence_hash(exchange)
    value=dict(schema='FRANKIE_CLASSROOM_LEARNING_HISTORY_V1',learning_policy=CUMULATIVE,
        knowledge=knowledge,exchanges=[exchange])
    value['history_hash']=evidence_hash(value)
    return value

def prepared(history):
    previous=prepare_integrated_cycle(_teacher(),request_id='run-cycle-00',cycle_index=0,
        cycle_count=8,source_hash='b'*64,as_of=2_000_000,through_cursor=6)
    return prepare_integrated_cycle(_teacher(offset=1),request_id='run-cycle-01',cycle_index=1,
        cycle_count=8,source_hash='b'*64,as_of=2_000_000,through_cursor=6,previous_snapshot=previous['source'],
        learning_history=history)

def test_entire_prior_exchange_and_failed_ideas_remain_model_visible():
    value=learning()
    package=prepared(value)
    public=json.loads(json.dumps(final_model_visible_classroom(package)))
    assert public['pre_message']['learning_history']==value
    assert public['binding']['learning_history_hash']==value['history_hash']
    assert public['learning_measurement']=='CUMULATIVE_LEARNING_REPLAY'
    assert public['independent_discovery_eligible'] is False
    text=_render_final_pre(package['pre_message'])
    prompt=C.component_prompt(public,C.components(public)[0]['name'],cycle='01',request_id='run-cycle-01')
    for token in ('PRIOR_FULL_RESEARCH_EXPLANATION','RETAIN_FAILED_APPROACH','ALL_PRIOR_OBSERVATIONS',
            'UNRESOLVED_PRIOR_QUESTION','FULL_TEACHER_CORRECTION','FRANKIE_REVISED_REASONING',
            '1790057801123456789'):
        assert token in text and token in prompt
    assert 'teacher_key' not in public

@pytest.mark.parametrize('change',['lesson','exchange','policy','request','missing_origin'])
def test_changed_or_wrong_request_history_refuses(change):
    value=learning()
    if change=='lesson':value['knowledge']['entries'][0]['record']['lessons'][0]['text']='tampered'
    if change=='exchange':value['exchanges'][0]['frankie_response']['uncertainty']='tampered'
    if change=='policy':value['learning_policy']=None
    if change=='request':value=learning(request='wrong-request')
    if change=='missing_origin':value['exchanges']=[]
    with pytest.raises(ValueError):prepared(value)

def test_history_hashes_preserve_integer_timestamps_through_json():
    value=learning()
    assert api().validate_history(json.loads(json.dumps(value)))==value
    assert value['knowledge']['entries'][0]['record']['available_ns']==1790057801123456789
