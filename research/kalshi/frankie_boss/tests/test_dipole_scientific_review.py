"""Scientific review is separate from deterministic mastery and provider attestation."""
import copy
import hashlib
import json
import unittest
from deploy.aws.box import frankie_box_staged_reading as staged
from research.kalshi.frankie_boss import dipole_shared_knowledge as knowledge
from research.kalshi.frankie_boss import dipole_scientific_review as science
from research.kalshi.frankie_boss.dipole_scientific_review import (
    build_request, parse_review, review_prompt, validate_exchange, exchange,
    request_items, reply_prompt, parse_reply, attach_reply,
)

def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

class ScientificReviewTest(unittest.TestCase):
    def setUp(self):
        self.initial = {'session_id':'s', 'model_identity_as_reported_by_session':'existing-engine',
            'dipole_novel_findings':[{'finding_id':'flow', 'premise':'scoped mechanism'}],
            'everything_else':{'negative_results':['failed idea'], 'observed_ns':1633298400000000001}}
        self.research = b'Historical negative results and later corrected mathematics.'
        catalog=dict(schema=knowledge.CATALOG_SCHEMA, version='fixture',
            sources=[dict(id='research',path='research/evidence.md',revision='a'*40,
                sha256=hashlib.sha256(self.research).hexdigest(),bytes=len(self.research),
                status='RESEARCH',explanation='Not automatically a valid signal.',required=True,
                access='SHARED_RESEARCH',provenance={'fixture':True},supersedes=[])])
        self.descriptor=knowledge._descriptor(catalog,knowledge._hash(knowledge._body(catalog)))
        self.request = build_request(initial_response=self.initial,
            original_request_sha256='a'*64, fact_review={'findings':[]},
            shared_knowledge=self.descriptor, learning_history={'all':'including failures'})
    def review(self, item):
        return {'item_id':item['item_id'], 'disposition':'SUPPORTED_SCOPED',
            'scope':'mathematical relation under explicit assumptions',
            'reasoning_steps':['derive the relation from its definitions'],
            'evidence_checks':[{'source_id':'initial-response','claim':'mechanism','check':'checked algebra','result':'supports'}],
            'contradictions':[], 'assumptions':['fixed event convention'], 'uncertainty':['execution untested'],
            'next_tests':['untouched causal windows'], 'build_forward':['derive a testable feature'],
            'replication_status':'NO_SECOND_OCCURRENCE',
            'predictive_status':'UNESTABLISHED','economic_status':'UNESTABLISHED'}
    def test_all_initial_information_is_retained_exactly(self):
        self.assertEqual(self.request['initial_response'], self.initial)
        self.assertEqual(self.request['learning_history'], {'all':'including failures'})
        self.assertEqual([x['item_id'] for x in request_items(self.request)], ['whole_run','finding:flow'])
    def test_scoped_agreement_without_second_occurrence(self):
        item=request_items(self.request)[1]
        answer=parse_review(json.dumps(self.review(item)),self.request,item)
        self.assertEqual(answer['disposition'],'SUPPORTED_SCOPED')
        self.assertIn('second occurrence is not required',review_prompt(self.request,item,{}).lower())
    def test_agreement_requires_reasoning_and_evidence(self):
        item=request_items(self.request)[0]
        for field in ('reasoning_steps','evidence_checks','scope'):
            answer=self.review(item);answer[field]=[] if field!='scope' else ''
            with self.assertRaises(ValueError):parse_review(json.dumps(answer),self.request,item)
    def test_review_cannot_certify_profit_or_future_outcomes(self):
        item=request_items(self.request)[0]
        answer=self.review(item);answer['economic_status']='PROVEN'
        with self.assertRaises(ValueError):parse_review(json.dumps(answer),self.request,item)
    def test_wrong_item_and_duplicate_findings_refused(self):
        item=request_items(self.request)[0];answer=self.review(item);answer['item_id']='wrong'
        with self.assertRaises(ValueError):parse_review(json.dumps(answer),self.request,item)
        initial=copy.deepcopy(self.initial);initial['dipole_novel_findings']*=2
        with self.assertRaises(ValueError):build_request(initial_response=initial,original_request_sha256='a'*64,
            fact_review={},shared_knowledge={'snapshot_hash':'b'*64},learning_history=None)
    def test_scientific_disagreement_is_preserved_separately(self):
        item=request_items(self.request)[0]
        answer={'item_id':item['item_id'],'position':'DISAGREE','reasoning':'a stated counterexample',
            'learned':['scientific correction'], 'next_steps':['check dimensions']}
        parsed=parse_reply(json.dumps(answer),item)
        self.assertEqual(parsed['position'],'DISAGREE')
    def test_task_identity_depends_on_all_prior_knowledge(self):
        other=build_request(initial_response=self.initial,original_request_sha256='a'*64,fact_review={'findings':[]},
            shared_knowledge={'snapshot_hash':'c'*64},learning_history={'all':'including failures'})
        self.assertNotEqual(other['scientific_request_hash'], self.request['scientific_request_hash'])
    def test_forged_or_incomplete_exchange_refused(self):
        with self.assertRaises(ValueError):validate_exchange(self.request,{})
        with self.assertRaises(ValueError):exchange(self.request,reading={},reviews=[])

    def reading(self):
        sources=[dict(source_id='research',content=self.research)]
        for key,body in (('initial-response',self.request['initial_response']),
                         ('fact-review',self.request['fact_review']),
                         ('learning-history',self.request['learning_history'])):
            sources.append(dict(source_id=key,content=science.canonical(body)))
        binding=dict(role='scientific_teacher',phase='full-run-scientific-review',
            request_hash=self.request['scientific_request_hash'],snapshot_hash=self.descriptor['snapshot_hash'],
            model_identity='fixture')
        plan,prompts=staged.plan_sources(sources,lambda meta:'Read every byte.',len,10000,binding=binding)
        receipts=[]
        for i,part in enumerate(plan['parts']):
            ack={k:part[k] for k in staged.ACK_FIELDS}
            response=json.dumps(dict(ack=ack,assessment='Preserve failed findings and their scope.'))
            prompt=prompts[part['part_id']]
            receipts.append(dict(part_id=part['part_id'],plan_hash=plan['plan_hash'],binding=binding,
                source_offset=part['source_offset'],ack=ack,
                prompt=dict(staged.witness(prompt),content=prompt),
                response=dict(staged.witness(response),content=response),
                provider_job=dict(id='reading-'+str(i),status='completed',role=binding['role'],
                    request_hash=binding['request_hash'],prompt_sha256=staged.witness(prompt)['sha256'],
                    response_sha256=staged.witness(response)['sha256'],incomplete=False)))
        return staged.assemble_parts(plan,receipts)
    def call(self, prompt, response, role):
        return dict(role=role,request_hash=self.request['scientific_request_hash'],
            prompt=prompt,response_text=response,transport=dict(job_id='role-job-'+role,
                status='COMPLETED',incomplete=False,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                response_sha256=hashlib.sha256(response.encode()).hexdigest()))
    def complete(self):
        reviews=[]; replies=[]
        for item in request_items(self.request):
            review=self.review(item)
            reviews.append(dict(review=review,teacher_call=self.call(
                review_prompt(self.request,item,{}),json.dumps(review),'scientific_teacher')))
            reply=dict(item_id=item['item_id'],position='DISAGREE',reasoning='retained scientific uncertainty',
                learned=['derive a candidate with explicit assumptions'],next_steps=['test the claimed mechanism'])
            replies.append(dict(parsed=reply,call=self.call(reply_prompt(self.request,item,review,{}),
                json.dumps(reply),'principal')))
        result=exchange(self.request,reading=self.reading(),reviews=reviews)
        return attach_reply(self.request,result,replies)
    def test_complete_two_role_exchange_keeps_disagreement(self):
        result=self.complete()
        self.assertEqual(validate_exchange(self.request,result),result)
        self.assertEqual(result['reviews'][0]['frankie_reply']['position'],'DISAGREE')
    def test_altered_raw_source_or_teacher_call_cannot_complete(self):
        for alter in ('source','teacher','role','reply'):
            value=self.complete()
            if alter=='source':value['reading']['parts'][0]['prompt']['content']+='changed'
            if alter=='teacher':value['reviews'][0]['teacher_call']['response_text']='{}'
            if alter=='role':value['reviews'][0]['teacher_call']['role']='principal'
            if alter=='reply':value['reviews'][0]['frankie_reply']['position']='AGREE'
            value['exchange_hash']=science.digest({k:v for k,v in value.items() if k!='exchange_hash'})
            with self.assertRaises(ValueError):validate_exchange(self.request,value)
    def test_missing_previous_learning_is_not_coverage(self):
        value=self.complete()
        # A fully valid delivery receipt for a different full run must not pass the expected roster.
        self.request['learning_history']={'changed':'new full learning'}
        self.request['scientific_request_hash']=science.digest({k:v for k,v in self.request.items() if k!='scientific_request_hash'})
        value['scientific_request_hash']=self.request['scientific_request_hash']
        value['exchange_hash']=science.digest({k:v for k,v in value.items() if k!='exchange_hash'})
        with self.assertRaises(ValueError):validate_exchange(self.request,value)

    def test_scientific_evidence_must_name_a_delivered_source(self):
        item=request_items(self.request)[0]
        answer=self.review(item)
        answer['evidence_checks'][0]['source_id']='unavailable-or-invented-source'
        with self.assertRaisesRegex(ValueError,'source'):
            parse_review(json.dumps(answer),self.request,item)
        answer['evidence_checks'][0]['source_id']='research'
        self.assertEqual(parse_review(json.dumps(answer),self.request,item),answer)
