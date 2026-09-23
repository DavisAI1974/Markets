"""History shares full learning once while every delivery prompt remains reconstructable."""
import copy
import hashlib
import unittest
from research.kalshi.frankie_boss import dipole_scientific_history as H
from research.kalshi.frankie_boss import dipole_scientific_review as S
from research.kalshi.frankie_boss import dipole_shared_knowledge as K
from research.kalshi.frankie_boss.c15_journal import evidence_hash
import test_dipole_teacher_discussion as discussion_fixtures


class ScientificHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=discussion_fixtures.DiscussionTests()
        self.fixture.setUp()
        self.request=self.fixture.request

    def restore(self,view,prior=()):
        fields={k:v for k,v in self.request.items() if k not in ('initial_response','learning_history')}
        return H.restore(view,request_fields=fields,initial_response=self.request['initial_response'],
            prior_exchanges=prior,resolve_source=lambda source_id:self.fixture.fixture.research)

    def test_exact_round_trip_keeps_all_teacher_and_frankie_outputs(self):
        original=self.fixture.complete()
        view=H.project(self.request,original)
        restored=self.restore(view)
        self.assertEqual(restored,original)
        visible=view['exchange_without_repeated_sources']
        self.assertEqual(visible['reviews'],original['reviews'])
        self.assertEqual(visible['teacher_discussion']['entries'],original['teacher_discussion']['entries'])
        for before,after in zip(original['reading']['parts'],visible['reading']['parts']):
            self.assertEqual(before['response'],after['response'])
            self.assertEqual(before['assessment'],after['assessment'])
            self.assertNotIn('content',after['prompt'])
            self.assertIn('source_fragment',after['prompt'])

    def test_large_source_copies_are_references_not_repeated_knowledge(self):
        fx=self.fixture.fixture
        fx.research=('retained research λ with no dropped source\n'*3000).encode()
        catalog=copy.deepcopy(fx.descriptor['catalog'])
        catalog['sources'][0].update(sha256=hashlib.sha256(fx.research).hexdigest(),bytes=len(fx.research))
        fx.descriptor=K._descriptor(catalog,K._hash(K._body(catalog)))
        self.request['shared_knowledge']=fx.descriptor
        self.request['scientific_request_hash']=S.digest({k:v for k,v in self.request.items() if k!='scientific_request_hash'})
        self.fixture.base=fx.complete()
        self.fixture.sources=[dict(source_id='research',content=fx.research)]
        self.fixture.sources += [dict(source_id=key,content=S.canonical(self.request[field])) for key,field in
            [('initial-response','initial_response'),('fact-review','fact_review'),('learning-history','learning_history')]]
        original=self.fixture.complete()
        view=H.project(self.request,original)
        self.assertLess(len(S.canonical(view)),len(S.canonical(original)))
        self.assertEqual(self.restore(view),original)

    def test_earlier_exchanges_are_referenced_in_order_without_losing_learning(self):
        previous=[]
        for i in range(3):
            entry={'learned':'all observations including failed candidate '+str(i),
                   'exact_nanoseconds':1633298400000000001+i}
            entry['exchange_hash']=evidence_hash(entry)
            previous.append(entry)
        history=dict(schema='FRANKIE_CLASSROOM_LEARNING_HISTORY_V1',learning_policy='fixture',
            knowledge={'request':'previous'},exchanges=previous)
        history['history_hash']=evidence_hash(history)
        self.request['learning_history']=history
        self.request['scientific_request_hash']=S.digest({k:v for k,v in self.request.items() if k!='scientific_request_hash'})
        self.fixture.base=self.fixture.fixture.complete()
        self.fixture.sources=[dict(source_id='research',content=self.fixture.fixture.research)]
        self.fixture.sources += [dict(source_id=key,content=S.canonical(self.request[field])) for key,field in
            [('initial-response','initial_response'),('fact-review','fact_review'),('learning-history','learning_history')]]
        original=self.fixture.complete()
        view=H.project(self.request,original)
        self.assertEqual(view['prior_history']['exchange_hashes'],[x['exchange_hash'] for x in previous])
        self.assertNotIn('exchanges',view['prior_history']['header'])
        self.assertEqual(self.restore(view,previous),original)
        with self.assertRaises(ValueError):self.restore(view,previous[:-1])

    def test_changed_reference_wrapper_or_full_source_refuses_restore(self):
        original=self.fixture.complete()
        view=H.project(self.request,original)
        for alter in ('wrapper','chunk'):
            changed=copy.deepcopy(view)
            fragment=changed['exchange_without_repeated_sources']['reading']['parts'][0]['prompt']['source_fragment']
            if alter=='wrapper':fragment['prefix']+='altered'
            else:fragment['start']+=1
            changed['projection_hash']=S.digest({k:v for k,v in changed.items() if k!='projection_hash'})
            with self.assertRaises(ValueError):self.restore(changed)
        fields={k:v for k,v in self.request.items() if k not in ('initial_response','learning_history')}
        with self.assertRaises(ValueError):
            H.restore(view,request_fields=fields,initial_response=self.request['initial_response'],
                prior_exchanges=(),resolve_source=lambda source_id:b'changed source')
