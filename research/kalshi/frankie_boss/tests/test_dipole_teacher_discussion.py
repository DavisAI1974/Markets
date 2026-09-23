"""Teacher discussion retains distinct roles, original duties and complete evidence."""
import copy
import hashlib
import json
import unittest
from types import SimpleNamespace
from research.kalshi.frankie_boss import dipole_teacher_discussion as D
from research.kalshi.frankie_boss import dipole_scientific_review as S
from deploy.aws.box import frankie_box_staged_reading as staged
import test_dipole_scientific_review as fixtures


def reading(sources,request,role):
    binding=dict(role=role,phase='boss-teacher-shared-research',
        request_hash=request['scientific_request_hash'],
        snapshot_hash=request['shared_knowledge']['snapshot_hash'],model_identity='fixture')
    plan,prompts=staged.plan_sources(sources,lambda meta:'Read all research and prior conversation.',
        len,10000,binding=binding)
    parts=[]
    for index,part in enumerate(plan['parts']):
        ack={key:part[key] for key in staged.ACK_FIELDS}
        response=json.dumps(dict(ack=ack,assessment='Keep the failed finding and its scope.'))
        prompt=prompts[part['part_id']]
        parts.append(dict(part_id=part['part_id'],plan_hash=plan['plan_hash'],binding=binding,
            source_offset=part['source_offset'],ack=ack,
            prompt=dict(staged.witness(prompt),content=prompt),
            response=dict(staged.witness(response),content=response),
            provider_job=dict(id='boss-reading-'+str(index),status='completed',role=role,
                request_hash=binding['request_hash'],prompt_sha256=staged.witness(prompt)['sha256'],
                response_sha256=staged.witness(response)['sha256'],incomplete=False)))
    return staged.assemble_parts(plan,parts)


def teacher_answer(item,prior,position='DISAGREE'):
    return dict(item_id=item['item_id'],responds_to_hash=S.digest(prior),position=position,
        reasoning='The mechanism needs a dimensional check; no recurrence is required for that check.',
        evidence_checks=[dict(source_id='research',claim='mechanism',check='units checked',result='unresolved')],
        build_forward=['retain the candidate and failed assumptions'],
        teaching_implications=['explain dimensional validity before predictive testing'],
        proposed_training_experiments=['a governed comparison after independent validation'],
        uncertainty=['the scientific disagreement remains open'],next_tests=['recompute the candidate'],
        original_duties='PRESERVED',target_changes='NONE',
        predictive_status='UNESTABLISHED',economic_status='UNESTABLISHED')


def frankie_answer(item,prior):
    return dict(item_id=item['item_id'],responds_to_hash=S.digest(prior),position='UNRESOLVED',
        reasoning='Both teachers have different scoped views.',
        learned=['retain both views and the original training role'],
        next_steps=['resolve the dimensional question'])


class DiscussionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ScientificReviewTest()
        self.fixture.setUp()
        self.request=self.fixture.request
        self.base=self.fixture.complete()
        self.sources=[dict(source_id='research',content=self.fixture.research)]
        self.sources += [dict(source_id=key,content=S.canonical(self.request[field])) for key,field in
            [('initial-response','initial_response'),('fact-review','fact_review'),('learning-history','learning_history')]]

    def complete(self):
        sources=self.sources+[dict(source_id='classroom-exchange',content=S.canonical(self.base))]
        delivery=reading(sources,self.request,D.BOSS_ROLE)
        entries=[]
        for item,review in zip(S.request_items(self.request),self.base['reviews']):
            prior=D.initial_turn(review)
            boss=teacher_answer(item,prior)
            boss_call=self.fixture.call(D.teacher_prompt(self.request,item,D.BOSS_ROLE,prior,{}),
                json.dumps(boss),D.BOSS_ROLE)
            classroom=teacher_answer(item,boss,'AGREE')
            classroom_call=self.fixture.call(D.teacher_prompt(self.request,item,D.CLASSROOM_ROLE,boss,{}),
                json.dumps(classroom),D.CLASSROOM_ROLE)
            final_prior=D.final_turn(boss,classroom)
            reply=frankie_answer(item,final_prior)
            reply_call=self.fixture.call(D.frankie_prompt(self.request,item,final_prior,{}),
                json.dumps(reply),'principal')
            entries.append(dict(item_id=item['item_id'],
                boss_teacher=dict(parsed=boss,call=boss_call,context_calls=[]),
                classroom_teacher=dict(parsed=classroom,call=classroom_call,context_calls=[]),
                frankie=dict(parsed=reply,call=reply_call,context_calls=[])))
        return D.attach(self.request,self.base,reading=delivery,entries=entries)

    def rehash(self,value):
        discussion=value['teacher_discussion']
        discussion['discussion_hash']=S.digest({k:v for k,v in discussion.items() if k!='discussion_hash'})
        value['exchange_hash']=S.digest({k:v for k,v in value.items() if k!='exchange_hash'})

    def test_both_teachers_and_frankie_keep_every_item_and_disagreement(self):
        value=self.complete()
        self.assertEqual(D.validate(self.request,value),value)
        entries=value['teacher_discussion']['entries']
        self.assertEqual([x['item_id'] for x in entries],['whole_run','finding:flow'])
        self.assertEqual(entries[0]['boss_teacher']['parsed']['position'],'DISAGREE')
        self.assertEqual(entries[0]['classroom_teacher']['parsed']['position'],'AGREE')
        self.assertEqual(entries[0]['frankie']['parsed']['position'],'UNRESOLVED')

    def test_original_training_role_cannot_be_replaced_by_discussion(self):
        item=S.request_items(self.request)[0]
        prior=D.initial_turn(self.base['reviews'][0])
        for field,bad in [('original_duties','REPLACED'),('target_changes','APPLY_NOW'),
                          ('economic_status','PROVEN')]:
            answer=teacher_answer(item,prior);answer[field]=bad
            with self.assertRaises(ValueError):
                D.parse_teacher(json.dumps(answer),self.request,item,prior)

    def test_invented_source_is_not_scientific_evidence(self):
        item=S.request_items(self.request)[0];prior=D.initial_turn(self.base['reviews'][0])
        answer=teacher_answer(item,prior)
        answer['evidence_checks'][0]['source_id']='invented-paper'
        with self.assertRaises(ValueError):D.parse_teacher(json.dumps(answer),self.request,item,prior)

    def test_missing_peer_reply_or_changed_role_does_not_complete(self):
        for alter in ('missing','role','prior','old-exchange','source'):
            value=self.complete()
            first=value['teacher_discussion']['entries'][0]
            if alter=='missing':del first['classroom_teacher']
            if alter=='role':first['boss_teacher']['call']['role']='principal'
            if alter=='prior':first['frankie']['parsed']['responds_to_hash']='f'*64
            if alter=='old-exchange':value['teacher_discussion']['classroom_exchange_hash']='f'*64
            if alter=='source':
                value['teacher_discussion']['reading']['parts'][0]['prompt']['content']+='changed'
            self.rehash(value)
            with self.assertRaises(ValueError):D.validate(self.request,value)

    def test_no_teacher_discussion_is_not_completion(self):
        with self.assertRaises(ValueError):D.validate(self.request,self.base)

    def test_host_correction_requires_teacher_discussion(self):
        from research.kalshi.frankie_boss.dipole_classroom_session import (
            validate_correction_response,CORRECTION_REQUEST_SCHEMA)
        correction=dict(schema=CORRECTION_REQUEST_SCHEMA,request_sha256='c'*64,
            scientific_review_request=self.request)
        response=dict(session_id=self.request['session_id'],request_sha256='c'*64,
            model_identity_as_reported_by_session='existing-engine',dipole_scientific_exchange=self.base)
        with self.assertRaisesRegex(ValueError,'teacher discussion'):
            validate_correction_response(correction=correction,response=response,
                initial_response=self.fixture.initial,grade={})

    def test_runtime_adapter_delivers_all_sources_and_completes_all_roles(self):
        from deploy.aws.box import frankie_box_teacher_discussion as runtime
        delivered=[]
        def consume(session,sources,role,phase,snapshot_hash,request_hash,cache,instruction):
            delivered.extend(sources)
            return reading(sources,self.request,role)
        def task(session,cache,**kwargs):
            item=next(x for x in S.request_items(self.request) if x['item_id']==kwargs['task_id'])
            key=kwargs['phase']
            if key=='boss-teacher-review':
                original=next(x for x in self.base['reviews'] if x['review']['item_id']==item['item_id'])
                answer=teacher_answer(item,D.initial_turn(original))
            elif key=='classroom-teacher-reply':
                prior=json.loads(kwargs['sources']['boss-teacher:'+item['item_id']])
                answer=teacher_answer(item,prior,'AGREE')
            else:
                prior=D.final_turn(json.loads(kwargs['sources']['boss-teacher:'+item['item_id']]),
                    json.loads(kwargs['sources']['classroom-teacher:'+item['item_id']]))
                answer=frankie_answer(item,prior)
            text=json.dumps(answer)
            prompt=kwargs['task_instruction']({})
            return dict(parsed=kwargs['parse_final'](text),context_calls=[],
                call=self.fixture.call(prompt,text,kwargs['role']))
        value=runtime.run(SimpleNamespace(),self.request,self.base,self.sources,cache=None,
            classroom_module=None,staged_module=SimpleNamespace(consume_sources=consume),run_task=task)
        self.assertEqual(D.validate(self.request,value),value)
        self.assertEqual({x['source_id'] for x in delivered},
            {'research','initial-response','fact-review','learning-history','classroom-exchange'})
        self.assertIn(b'including failures',next(x['content'] for x in delivered if x['source_id']=='learning-history'))
