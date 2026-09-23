"""Scientific review is separate from deterministic mastery and provider attestation."""
import copy
import hashlib
import json
import unittest
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
        self.request = build_request(initial_response=self.initial,
            original_request_sha256='a'*64, fact_review={'findings':[]},
            shared_knowledge={'snapshot_hash':'b'*64}, learning_history={'all':'including failures'})
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
