"""Review fixes for the Dipole classroom (ccode, 2026-09-16, after the ChatGPT hardening commits).

Proved functionally, not by source inspection:
1. Pearson is reported at the declared floor and suppressed below it, on a key built by the real builder.
2. The pre-message carries only the prior-correction SUMMARY and the renderer prints it (the
   intermediate hardened adapter used to crash here on every cycle after the first).
3. A narrative HYPOTHESIS on a pair the ledger classifies factually, with no developing structure
   recorded, is a representation item; with one recorded it is an additional hypothesis.
4. The transcript prints the data fields Frankie actually received, not only the message text.
5. End to end through the final adapter in SOCRATIC mode: no file in the model-facing principal
   directory carries a retained observation value; the source snapshot, the teacher key and the
   full post-grade sit in the host-owned audit directory; receipt and completion carry the
   learning measurement.
6. The classroom wrapper no longer hard-codes the cycle count in its request search.
"""
import inspect
import json

import pytest
import torch

from research.kalshi.frankie_boss import frankie_principal_adapter as base_adapter
from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import (
    ACK_SCHEMA, COMPLETION_SCHEMA, GRADE_SCHEMA, MIN_PEARSON_PRESENT_OVERLAP, PAIR_COUNT,
    PRIOR_CORRECTION_SCHEMA, TEACHBACK_SCHEMA, ClassroomMode, build_pre_message, prepare_cycle)
from research.kalshi.frankie_boss.dipole_classroom_final_review import (
    FinalDipoleClassroomPrincipalAdapter, _render_dipole_review, apply_relationship_view_crosscheck,
    build_final_correction_request, prepare_final_cycle)
from research.kalshi.frankie_boss.dipole_classroom_hardening import prepare_hardened_cycle
from research.kalshi.frankie_boss.dipole_classroom_render import render_pre_message
from research.kalshi.frankie_boss.dipole_classroom_session import grade_initial_response
from research.kalshi.frankie_boss.dipole_target import DipoleTarget, DipoleTargetSpec, TargetState

HEX_A='a'*64;HEX_B='b'*64;HEX_C='c'*64
CYCLE_COUNT=19          # the Sunday schedule length; the host reads it from the schedule steps
BASE=1234.5             # distinctive retained values, exact in float32, so a text search over retained files means something


def _target(cursor,values,states):
    spec=DipoleTargetSpec(registry_id='boss/teacher/test',target_names=tuple(COLUMNS),
        target_units=('z_score',)*len(COLUMNS),normalizer_id='test-normalizer',builder_code_sha='1'*40)
    encoded=[float(v) if s==int(TargetState.PRESENT) else 0.0 for v,s in zip(values,states)]
    now=1_000_000+cursor
    return DipoleTarget(spec,HEX_A,f'{cursor+1:064x}',now,
        torch.tensor([[encoded]],dtype=torch.float32),torch.tensor([[states]],dtype=torch.int8),
        torch.tensor([[now]],dtype=torch.int64))


def _teacher(rows=3):
    cursors=tuple(2*(i+1) for i in range(rows));targets=[];raw=[]
    for row,cursor in enumerate(cursors):
        states=[int(TargetState.PRESENT)]*len(COLUMNS)
        values=[BASE+index*10+row*1.25+(row%3)*0.5*index for index in range(len(COLUMNS))]
        targets.append(_target(cursor,values,states))
        raw.append(tuple({'value':values[i],'state':states[i],'reason':''} for i in range(len(COLUMNS))))
    receipts=tuple({'cursor':c,'source_prefix_hash':t.source_prefix_hash,'target_hash':t.target_hash,
        'normalizer':{'normalizer_id':'test-normalizer'}} for c,t in zip(cursors,targets))
    return {'targets':tuple(targets),'raw':tuple(raw),'processed_records':cursors[-1]+1,'context_cursors':cursors,
        'step_receipts':receipts,'attachment_hash':evidence_hash(receipts),'candidate_digest':HEX_C}


def _package(rows=3,**kwargs):
    return prepare_cycle(_teacher(rows),request_id='run-cycle-00',cycle_index=0,cycle_count=CYCLE_COUNT,
        source_hash=HEX_B,as_of=2_000_000,through_cursor=2*rows,**kwargs)


def _response(package,*,narrative_relation=None,developing=None):
    key=package['teacher_key'];pre=package['pre_message'];dims={d['name']:d for d in key['dimensions']}
    components=[]
    for name in COLUMNS:
        d=dims[name];rels=[]
        if name==COLUMNS[0] and narrative_relation is not None:
            rels=[{'with':COLUMNS[1],'relation':narrative_relation,'explanation':'narrative view'}]
        components.append({'name':name,'state_counts':dict(d['state_counts']),'terminal_state':d['terminal_state'],
            'direction':d['first_to_last_present_direction'],'explanation':'e','why':'w','market_behavior':'m',
            'fifo_full_book_order_link':'f','evidence':'v','uncertainty':'u','relationships':rels})
    teachback={'schema':TEACHBACK_SCHEMA,'teacher_message_hash':pre['teacher_message_hash'],'components':components,
        'cycle_summary':'s','correlation_review':'c','relationship_pairs_considered':PAIR_COUNT,
        'unresolved_questions':[],'future_outcome_claimed':False}
    review=[{'name':d['name'],'observations':[{'cursor':p['cursor'],'state':p['state'],'value':p['value'],'explanation':'x'}
        for p in d['observations']]} for d in key['dimensions']]
    first=(COLUMNS[0],COLUMNS[1])
    scan=[{'left':p['left'],'right':p['right'],'direction_relation':p['direction_relation'],'correlation_interpretation':'i',
        'developing_structure':developing if (p['left'],p['right'])==first else None} for p in key['relationship_scan']]
    return {'session_id':'frankie-session','model_identity_as_reported_by_session':'frankie-model',
        'dipole_teachback':teachback,'dipole_observation_review':review,'dipole_relationship_scan':scan,
        'dipole_novel_findings':[]}


def test_pearson_reported_at_the_floor_and_suppressed_below_it():
    n=MIN_PEARSON_PRESENT_OVERLAP
    at=_package(rows=n);corr=at['teacher_key']['relationship_scan'][0]['correlation']
    assert corr['present_overlap']==n and isinstance(corr['pearson'],float) and corr['reason'] is None
    below=_package(rows=n-1);corr=below['teacher_key']['relationship_scan'][0]['correlation']
    assert corr=={'present_overlap':n-1,'pearson':None,'reason':f'FEWER_THAN_{n}_OVERLAPPING_PRESENT_VALUES'}
    assert f'at least {n} overlapping' in at['pre_message']['relationship_instruction']
    final=prepare_final_cycle(_teacher(n),request_id='run-cycle-00',cycle_index=0,cycle_count=CYCLE_COUNT,
        source_hash=HEX_B,as_of=2_000_000,through_cursor=2*n)
    assert isinstance(final['teacher_key']['relationship_scan'][0]['correlation']['pearson'],float)
    assert f'at least {n} overlapping' in final['pre_message']['relationship_instruction']


def test_pre_message_carries_only_the_prior_correction_summary_and_renders():
    key=_package()['teacher_key']
    grade={'schema':GRADE_SCHEMA,'post_grade_hash':'d'*64,'correction_ids':('component:'+COLUMNS[0],),'mastered':False,
        'exhaustive_audit':{'sentinel':987654.321},'component_grades':({'name':COLUMNS[0],'explanation':'SENTINEL-EXPLANATION'},),
        'teacher_closing':'SENTINEL-CLOSING'}
    for builder in (lambda:build_pre_message(key,mode=ClassroomMode.GUIDED.value,prior_grade=grade),
                    lambda:prepare_hardened_cycle(_teacher(),request_id='run-cycle-00',cycle_index=0,cycle_count=CYCLE_COUNT,
                        source_hash=HEX_B,as_of=2_000_000,through_cursor=6,prior_grade=grade)['pre_message'],
                    lambda:prepare_final_cycle(_teacher(),request_id='run-cycle-00',cycle_index=0,cycle_count=CYCLE_COUNT,
                        source_hash=HEX_B,as_of=2_000_000,through_cursor=6,prior_grade=grade)['pre_message']):
        message=builder();prior=message['prior_cycle_correction']
        assert prior['schema']==PRIOR_CORRECTION_SCHEMA and prior['correction_ids']==('component:'+COLUMNS[0],)
        text=json.dumps(message,default=str)
        assert '987654.321' not in text and 'SENTINEL' not in text
        rendered=render_pre_message(message)          # used to KeyError on the summary shape
        assert 'component:'+COLUMNS[0] in rendered and 'SENTINEL' not in rendered
    with pytest.raises(ValueError,match='prior-correction summary'):
        render_pre_message(dict(build_pre_message(key,mode=ClassroomMode.GUIDED.value),prior_cycle_correction=grade))


def test_narrative_hypothesis_must_reconcile_with_the_factual_ledger():
    package=_package();pair=f'representation:{COLUMNS[0]}:{COLUMNS[1]}'
    response=_response(package,narrative_relation='HYPOTHESIS')
    _,grade=grade_initial_response(package,response)
    assert grade['mastered'] is True                  # the component grader retains HYPOTHESIS ungraded
    checked=apply_relationship_view_crosscheck(grade,response)
    assert pair in checked['correction_ids'] and checked['mastered'] is False
    response=_response(package,narrative_relation='HYPOTHESIS',developing='a developing structure, labelled HYPOTHESIS')
    _,grade=grade_initial_response(package,response)
    checked=apply_relationship_view_crosscheck(grade,response)
    assert pair not in checked['correction_ids'] and checked['mastered'] is True
    actual=package['teacher_key']['relationship_scan'][0]['direction_relation']
    response=_response(package,narrative_relation=actual)
    _,grade=grade_initial_response(package,response)
    assert pair not in apply_relationship_view_crosscheck(grade,response)['correction_ids']


def test_transcript_prints_the_data_fields_frankie_received():
    package=_package();response=_response(package)
    response['dipole_teachback']['components'][0]['direction']='FALL'   # the retained rows RISE
    for pair in response['dipole_relationship_scan']:                    # and the pairs built on that wrong direction
        if pair['left']==COLUMNS[0]:
            pair['direction_relation']='OPPOSITE_DIRECTION' if pair['direction_relation']=='SAME_DIRECTION' else 'SAME_DIRECTION'
    teachback,grade=grade_initial_response(package,response)
    grade=apply_relationship_view_crosscheck(grade,response)
    novelty={'schema':'DIPOLE_NOVELTY_INVESTIGATION_V1','mode':'TEACH','findings':(),'finding_count':0,
        'scored_for_classroom_mastery':False,'investigation_bundle_hash':'d'*64}
    correction=build_final_correction_request(original_request_sha256='e'*64,response=response,grade=grade,
        key=package['teacher_key'],teachback=teachback,novelty_investigation=novelty)
    rendered=_render_dipole_review(correction)
    assert "'frankie_said': 'FALL'" in rendered and "'data_shows': 'RISE'" in rendered
    root='derived-from:component:'+COLUMNS[0]
    assert root in rendered
    group=next(g for g in correction['root_cause_groups'] if g['root_cause_id']==root)
    assert len(group['member_review_ids'])==len(COLUMNS)-1           # all 18 pair items under the one direction root
    assert len(correction['correction_ids'])==len(COLUMNS)           # while every correction stays individually retained


def _completion(mode):
    return {'schema':COMPLETION_SCHEMA,'mode':mode,'mastered':True,'acknowledged':True,'teacher_complete':True}


from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter


@pytest.mark.parametrize('adapter_class',[FinalDipoleClassroomPrincipalAdapter,IntegratedDipoleClassroomPrincipalAdapter])
def test_final_adapter_keeps_answer_key_material_out_of_the_principal_directory(tmp_path,monkeypatch,adapter_class):
    # The integrated adapter rebinds the final adapter's methods onto the base classroom adapter without the
    # hardened class in its MRO; the same two-turn flow must hold for it (the reviewer's method-rebinding question).
    history=(_completion('TEACH'),_completion('TEACH'),_completion('GUIDED'),_completion('GUIDED'))
    package=prepare_final_cycle(_teacher(),request_id='run-cycle-00',cycle_index=0,cycle_count=CYCLE_COUNT,
        source_hash=HEX_B,as_of=2_000_000,through_cursor=6,history=history)
    assert package['binding']['mode']==ClassroomMode.SOCRATIC.value
    assert package['binding']['independent_discovery_eligible'] is True
    Base=base_adapter.FrankiePrincipalAdapter
    monkeypatch.setattr(Base,'prepare',lambda self,handoff:{'config_hash':'1'*64,'attachment_hash':'2'*64})
    monkeypatch.setattr(Base,'_request',lambda self,rid,attachment:{'schema':'FRANKIE_BOSS_SESSION_REQUEST_V1','request_id':rid,'instruction':'base.'})
    monkeypatch.setattr(Base,'recover',lambda self,rid,attachment:{'feedback':{},'lessons':[],'principal_receipt':{}})
    monkeypatch.setattr(Base,'_files',lambda self:None)
    monkeypatch.setattr(Base,'_attest_host',lambda self,response,attestation,request:attestation)
    adapter=object.__new__(adapter_class)
    adapter.directory=(tmp_path/'cycle-00'/'principal').resolve();adapter.directory.mkdir(parents=True)
    adapter.audit_directory=(tmp_path/'cycle-00'/'classroom-audit').resolve();adapter.audit_directory.mkdir()
    adapter.classroom_package=package
    def executor(request):
        if request['schema']=='FRANKIE_BOSS_SESSION_REQUEST_V1':
            response=_response(package)
        else:
            response={'session_id':'frankie-session','model_identity_as_reported_by_session':'frankie-model',
                'request_sha256':request['request_sha256'],
                'dipole_acknowledgement':{'schema':ACK_SCHEMA,'post_grade_hash':request['post_grade_hash'],'session_id':'frankie-session',
                    'acknowledged':True,'resolved_correction_ids':list(request['correction_ids']),'remaining_disagreements':[],
                    'what_i_will_change':'nothing; no correction was required','correction_resolutions':[]}}
        return {'response':response,'host_attestation':{'schema':'test-attestation'}}
    adapter.session_executor=executor
    attachment=adapter.prepare(tmp_path/'handoff')
    envelope=adapter.execute('run-cycle-00',attachment)
    assert envelope['feedback']=={}
    principal,audit=adapter.directory,adapter.audit_directory
    for name in ('dipole-classroom-source.json','dipole-classroom-teacher-key.audit.json','dipole-classroom-post-grade.json'):
        assert not (principal/name).exists() and (audit/name).exists(),name
    # Frankie's own answers, and the transcript that prints them, legitimately carry the values it
    # claimed; nothing else in the principal directory may carry a retained value.
    own={'session-response.json','classroom-correction-response.json','dipole-classroom-teachback.json','dipole-classroom-transcript.md'}
    sentinel=str(BASE)
    for path in principal.iterdir():
        if path.name not in own:
            assert sentinel not in path.read_text(encoding='utf-8'),path.name
    assert sentinel in (audit/'dipole-classroom-source.json').read_text(encoding='utf-8')
    receipt=json.loads((principal/'dipole-classroom-receipt.json').read_bytes())
    assert receipt['independent_discovery_eligible'] is True and receipt['teacher_complete'] is True
    completion=json.loads((principal/'dipole-classroom-completion.json').read_bytes())
    assert completion['learning_measurement']=='INDEPENDENT_RECOGNITION_ELIGIBLE' and completion['mastered'] is True


def test_wrapper_request_search_is_not_bound_to_nineteen_cycles():
    from research.kalshi.frankie_boss.operations import run_actual_sunday_classroom as wrapper
    source=inspect.getsource(wrapper.await_recorded_principal)
    assert 'range(19)' not in source and 'cycle-*' in source
    assert 'classroom-audit' in inspect.getsource(wrapper.ClassroomActualHost._previous_source_and_grade)
