import copy

import pytest
import torch

from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import ACK_SCHEMA, PAIR_COUNT, TEACHBACK_SCHEMA, prepare_cycle
from research.kalshi.frankie_boss.dipole_classroom_session import (
    CORRECTION_REQUEST_SCHEMA,
    correction_request,
    finish,
    grade_initial_response,
    model_visible_classroom,
    validate_correction_response,
)
from research.kalshi.frankie_boss.dipole_target import DipoleTarget, DipoleTargetSpec, TargetState

HEX_A='a'*64;HEX_B='b'*64;HEX_C='c'*64


def _target(cursor, values, states):
    spec=DipoleTargetSpec(registry_id='boss/teacher/test',target_names=tuple(COLUMNS),
        target_units=('z_score',)*len(COLUMNS),normalizer_id='test-normalizer',builder_code_sha='1'*40)
    encoded=[float(v) if s==int(TargetState.PRESENT) else 0.0 for v,s in zip(values,states)]
    now=1_000_000+cursor
    return DipoleTarget(spec,HEX_A,f'{cursor+1:064x}',now,
        torch.tensor([[encoded]],dtype=torch.float32),torch.tensor([[states]],dtype=torch.int8),
        torch.tensor([[now]],dtype=torch.int64))


def _teacher():
    cursors=(2,4,6);targets=[];raw=[]
    for row,cursor in enumerate(cursors):
        states=[int(TargetState.PRESENT)]*len(COLUMNS);reasons=['']*len(COLUMNS)
        if row==0:
            states[1]=int(TargetState.MISSING);reasons[1]='WINDOW_SHORT'
            states[2]=int(TargetState.INVALID);reasons[2]='LEVEL_INTEGRITY'
            states[7]=int(TargetState.ABLATED);reasons[7]='UNBUILT_B2_C1'
        values=[float(i+row) for i in range(len(COLUMNS))]
        targets.append(_target(cursor,values,states))
        raw.append(tuple({'value':values[i],'state':states[i],'reason':reasons[i]} for i in range(len(COLUMNS))))
    receipts=tuple({'cursor':c,'source_prefix_hash':t.source_prefix_hash,'target_hash':t.target_hash,
        'normalizer':{'normalizer_id':'test-normalizer'}} for c,t in zip(cursors,targets))
    return {'targets':tuple(targets),'raw':tuple(raw),'processed_records':7,'context_cursors':cursors,
        'step_receipts':receipts,'attachment_hash':evidence_hash(receipts),'candidate_digest':HEX_C}


def _package():
    return prepare_cycle(_teacher(),request_id='run-cycle-00',cycle_index=0,source_hash=HEX_B,
        as_of=2_000_000,through_cursor=6)


def _teachback(package):
    key=package['teacher_key'];pre=package['pre_message'];dimensions={d['name']:d for d in key['dimensions']}
    components=[]
    for name in COLUMNS:
        d=dimensions[name]
        components.append({'name':name,'state_counts':dict(d['state_counts']),'terminal_state':d['terminal_state'],
            'direction':d['first_to_last_present_direction'],'explanation':'I reviewed the complete retained evidence.',
            'why':'I separated what Dipole measures from my interpretation.','market_behavior':'I described the causal order-book behavior.',
            'fifo_full_book_order_link':'I connected FIFO/full-book/order behavior only where supported.',
            'evidence':'I used all retained cursors and states.','uncertainty':'I did not use later outcomes.','relationships':[]})
    return {'schema':TEACHBACK_SCHEMA,'teacher_message_hash':pre['teacher_message_hash'],'components':components,
        'cycle_summary':'I reviewed all 19 Dipole dimensions.','correlation_review':'I considered all 171 pairs without treating correlation as causation.',
        'relationship_pairs_considered':PAIR_COUNT,'unresolved_questions':[],'future_outcome_claimed':False}


def _observation_review(package):
    result=[]
    for d in package['teacher_key']['dimensions']:
        result.append({'name':d['name'],'observations':[{'cursor':p['cursor'],'state':p['state'],'value':p['value'],
            'explanation':'I explicitly accounted for this retained observation.'} for p in d['observations']]})
    return result


def _relationship_scan(package):
    return [{'left':p['left'],'right':p['right'],'direction_relation':p['direction_relation'],
        'correlation_interpretation':'I reviewed the current-window direction and Pearson evidence without claiming causation.',
        'developing_structure':None} for p in package['teacher_key']['relationship_scan']]


def _response(package):
    return {'session_id':'frankie-session','model_identity_as_reported_by_session':'frankie-model',
        'dipole_teachback':_teachback(package),'dipole_observation_review':_observation_review(package),
        'dipole_relationship_scan':_relationship_scan(package)}


def _ack(grade):
    return {'schema':ACK_SCHEMA,'post_grade_hash':grade['post_grade_hash'],'session_id':'frankie-session',
        'acknowledged':True,'resolved_correction_ids':list(grade['correction_ids']),'remaining_disagreements':[],
        'what_i_will_change':'I will carry every Dipole correction into the next cycle.'}


def test_model_visible_classroom_withholds_audit_key_but_requires_both_exhaustive_ledgers():
    package=_package();visible=model_visible_classroom(package)
    assert 'teacher_key' not in visible
    assert visible['audit_key_withheld'] is True
    assert visible['required_response_ledgers']['dipole_relationship_scan']==PAIR_COUNT
    assert visible['coverage_invariant']=='ALL_19_DIPOLE_DIMENSIONS_EVERY_CYCLE'


def test_grade_requires_every_observation_and_every_pair_explicitly():
    package=_package();response=_response(package)
    response['dipole_observation_review'][0]['observations']=response['dipole_observation_review'][0]['observations'][:-1]
    teachback,grade=grade_initial_response(package,response)
    assert grade['mastered'] is False
    assert any(item.startswith('observation:') or item.startswith('observation-set:') for item in grade['correction_ids'])
    assert grade['exhaustive_audit']['coverage_proven'] is True

    response=_response(package);response['dipole_relationship_scan']=response['dipole_relationship_scan'][:-1]
    with pytest.raises(ValueError,match='exactly 171 pairs'):
        grade_initial_response(package,response)


def test_wrong_observation_and_pair_become_point_by_point_corrections():
    package=_package();response=_response(package)
    first=response['dipole_observation_review'][0]['observations'][0]
    first['value']=first['value']+1.0
    pair=response['dipole_relationship_scan'][0]
    pair['direction_relation']='OPPOSITE_DIRECTION' if pair['direction_relation']!='OPPOSITE_DIRECTION' else 'SAME_DIRECTION'
    teachback,grade=grade_initial_response(package,response)
    assert grade['mastered'] is False
    assert f"observation:{COLUMNS[0]}:{first['cursor']}" in grade['correction_ids']
    assert f"relationship:{pair['left']}:{pair['right']}" in grade['correction_ids']
    assert len(grade['exhaustive_audit']['relationship_grades'])==PAIR_COUNT
    assert teachback['exhaustive_audit_hash']==grade['exhaustive_audit']['audit_hash']


def test_correct_exhaustive_first_answer_can_master_and_finish_after_same_session_ack():
    package=_package();initial=_response(package)
    teachback,grade=grade_initial_response(package,initial)
    assert grade['mastered'] is True
    assert grade['correction_ids']==()
    correction=correction_request(original_request_sha256='d'*64,response=initial,grade=grade)
    assert correction['schema']==CORRECTION_REQUEST_SCHEMA
    correction_response={'session_id':'frankie-session','model_identity_as_reported_by_session':'frankie-model',
        'request_sha256':correction['request_sha256'],'dipole_acknowledgement':_ack(grade)}
    ack=validate_correction_response(correction=correction,response=correction_response,initial_response=initial,grade=grade)
    completed=finish(package,teachback=teachback,grade=grade,acknowledgement=ack)
    assert completed['teacher_complete'] is True
    assert completed['observation_claims_reviewed']==sum(len(d['observations']) for d in package['teacher_key']['dimensions'])
    assert completed['relationship_pairs_explicitly_reviewed']==PAIR_COUNT


def test_correction_must_return_from_same_frankie_session():
    package=_package();initial=_response(package);teachback,grade=grade_initial_response(package,initial)
    correction=correction_request(original_request_sha256='d'*64,response=initial,grade=grade)
    wrong={'session_id':'different-session','model_identity_as_reported_by_session':'frankie-model',
        'request_sha256':correction['request_sha256'],'dipole_acknowledgement':_ack(grade)}
    with pytest.raises(ValueError,match='same Frankie session'):
        validate_correction_response(correction=correction,response=wrong,initial_response=initial,grade=grade)


def test_corrected_understanding_is_required_per_correction_and_rendered():
    from research.kalshi.frankie_boss.dipole_classroom_render import render_transcript
    from research.kalshi.frankie_boss.dipole_classroom_resolution import bind_resolution_requirement, validate_correction_resolutions
    package=_package();initial=_response(package)
    first=initial['dipole_observation_review'][0]['observations'][0];first['value']=first['value']+1.0
    teachback,grade=grade_initial_response(package,initial)
    assert grade['correction_ids']
    correction=bind_resolution_requirement(correction_request(original_request_sha256='d'*64,response=initial,grade=grade))
    assert 'correction_resolutions' in correction['instruction']
    raw_ack=_ack(grade)
    correction_response={'session_id':'frankie-session','model_identity_as_reported_by_session':'frankie-model',
        'request_sha256':correction['request_sha256'],'dipole_acknowledgement':raw_ack}
    base=validate_correction_response(correction=correction,response=correction_response,initial_response=initial,grade=grade)
    with pytest.raises(ValueError,match='corrected-understanding record'):
        validate_correction_resolutions(raw_ack,grade,base)  # an ID echo alone is not enough
    raw_ack['correction_resolutions']=[{'correction_id':cid,'corrected_understanding':f'I now read {cid} from the retained value, not my own guess.'}
        for cid in grade['correction_ids']]
    ack=validate_correction_resolutions(raw_ack,grade,base)
    assert [r['correction_id'] for r in ack['correction_resolutions']]==list(grade['correction_ids'])
    transcript=render_transcript(package['pre_message'],teachback,grade,ack)
    assert "Frankie's corrected understanding, per correction" in transcript
    for cid in grade['correction_ids']:
        assert f'`{cid}`: I now read {cid}' in transcript
    completed=finish(package,teachback=teachback,grade=grade,acknowledgement=ack)
    assert completed['teacher_complete'] is True and completed['mastered'] is False
