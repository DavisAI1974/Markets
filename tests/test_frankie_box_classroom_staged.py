"""Observation pages preserve every claim; assembly never repairs teacher values."""
import unittest
from deploy.aws.box.frankie_box_classroom_staged import cursor_pages, collect_observations

class FragmentTests(unittest.TestCase):
    def test_every_cursor_is_paged_once_in_original_order(self):
        roster=list(range(301))
        pages=cursor_pages(roster,128)
        self.assertEqual([x for page in pages for x in page],roster)
        self.assertEqual(list(map(len,pages)),[128,128,45])
    def test_claim_values_are_preserved_without_teacher_repair(self):
        pages=[[dict(cursor=1,state='PRESENT',value=-99.1,explanation='own claim')],
               [dict(cursor=4,state='MISSING',value=None,explanation='absent')]]
        self.assertEqual(collect_observations(pages,[1,4]),pages[0]+pages[1])
    def test_missing_duplicate_or_reordered_claims_refuse(self):
        claim=lambda c:dict(cursor=c,state='PRESENT',value=1,explanation='own claim')
        for pages in ([[claim(1)]],[[claim(1),claim(1)]],[[claim(4),claim(1)]]):
            with self.assertRaises(ValueError):collect_observations(pages,[1,4])
    def test_roster_is_exact_and_nonempty(self):
        for roster in ([],[1,1],[True],[2,1]):
            with self.assertRaises(ValueError):cursor_pages(roster,128)
    def test_nonfinite_or_nonpresent_numeric_claim_refuses(self):
        for point in (dict(cursor=1,state='PRESENT',value=float('nan'),explanation='own claim'),
                      dict(cursor=1,state='MISSING',value=0,explanation='absent')):
            with self.assertRaises(ValueError):collect_observations([[point]],[1])


def test_complete_teach_path_keeps_all_sources_and_uses_original_grader(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from deploy.aws.box import frankie_box_classroom_staged as staged
    from test_frankie_box_classroom import (C, CURSORS, build_package, build_visible,
        boss_component_answer, boss_summary_answer, session_mod, final)
    package=build_package()
    visible=build_visible(package)
    visible['pre_message']['shared_knowledge']={'snapshot_hash':'b'*64}
    visible['pre_message']['observation_cursor_roster']=CURSORS
    visible['pre_message']['learning_history']={'prior_failure':'keep the failed hypothesis'}
    original=json.dumps(package,sort_keys=True)
    monkeypatch.setattr(staged,'ensure_snapshot',lambda descriptor,root:
        [dict(source_id='original-boss-teacher',content=b'Original mathematics and training duties remain.')])
    (tmp_path/'merged-notes.md').write_text('complete current notes')
    (tmp_path/'derivation-digest-full.md').write_text('complete current digest')
    reads=[]
    def consume(session,sources,*args):
        reads.extend(sources)
        return dict(plan_hash='p'*64,parts=[])
    tasks=[]
    def task(session,cache,**kwargs):
        sources=kwargs['sources']
        assert b'keep the failed hypothesis' in sources['learning-history']
        assert sources['original-boss-teacher']==b'Original mathematics and training duties remain.'
        assert sources['derivation-digest-full.md']==b'complete current digest'
        tasks.append(kwargs['task_id'])
        if kwargs['task_id']=='summary':
            assert len([x for x in sources if x.startswith('classroom-answer:component:')])==19
            answer=boss_summary_answer(with_novel=False)
        else:
            name=kwargs['task_id'].split(':',1)[1]
            component=next(x for x in C.components(visible) if x['name']==name)
            rights=[x['right'] for x in C.pairs_of(visible,name)]
            answer=boss_component_answer(component,rights)
        return dict(parsed=kwargs['parse_final'](answer),call={},context_calls=[])
    published=[]
    cache=SimpleNamespace(save=lambda *args:None,publish=lambda *args:published.append(args))
    session=SimpleNamespace(work=tmp_path,cycle='00',request_sha256='a'*64,
        request=dict(request_id='run-cycle-00',attachment=dict(dipole_classroom=visible)))
    ledgers=staged.run(session,C,cache,root=tmp_path,
        staged=SimpleNamespace(consume_sources=consume),dialogue=SimpleNamespace(run_task=task))
    assert len(tasks)==20
    assert len([x for x in reads if x['source_id'].startswith('current-component:')])==19
    assert json.dumps(package,sort_keys=True)==original
    _,grade=session_mod.grade_initial_response(package,ledgers)
    grade=final.apply_relationship_view_crosscheck(grade,ledgers)
    assert grade['mastered'] is True and grade['correction_ids']==()
    assert published[0][2]['report']['observations']==19*len(CURSORS)
    assert published[0][2]['report']['pairs']==171


def test_correction_pages_retain_all_ids_history_and_scientific_disagreement(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from deploy.aws.box import frankie_box_classroom_staged as staged
    from test_frankie_box_classroom import C
    ids=['correction-'+str(i) for i in range(137)]
    correction=dict(request_sha256='a'*64,post_grade_hash='b'*64,correction_ids=ids,
        instruction='Resolve factual errors with evidence.',learning_history={'earlier':'negative finding retained'},
        data_review_items=[dict(correction_id=x,evidence='exact original evidence') for x in ids],
        scientific_review_request={'shared_knowledge':{'snapshot_hash':'c'*64}})
    exchange={'reviews':[{'frankie_reply':{'position':'DISAGREE','reasoning':'unresolved science'}}]}
    monkeypatch.setattr(staged,'ensure_snapshot',lambda descriptor,root:
        [dict(source_id='original-teacher',content=b'governed original duty')])
    sources_seen=[]
    def consume(session,sources,*args):
        sources_seen.extend(sources)
        return dict(plan_hash='d'*64,parts=[])
    tasks=[]
    def task(session,cache,**kwargs):
        tasks.append(kwargs['task_id'])
        assert b'negative finding retained' in kwargs['sources']['learning-history']
        assert b'DISAGREE' in kwargs['sources']['scientific-dialogue']
        instruction=kwargs['task_instruction']({})
        if kwargs['task_id'].startswith('correction-page:'):
            page=json.loads(instruction.split('Correction IDs: ',1)[1].split('\n',1)[0])
            text=json.dumps({'correction_resolutions':[
                dict(correction_id=x,corrected_understanding='My corrected understanding for '+x) for x in page]})
        else:
            assert len([x for x in kwargs['sources'] if x.startswith('resolved-page:')])==3
            text=json.dumps(dict(what_i_will_change='Use the original governed evidence.',
                remaining_disagreements=[]))
        return dict(parsed=kwargs['parse_final'](text),call={},context_calls=[])
    cache=SimpleNamespace(save=lambda *args:None)
    parsed,witness=staged.run_correction(SimpleNamespace(cycle='00'),C,cache,
        correction=correction,ledgers={'full_original_ledgers':'retained'},scientific_exchange=exchange,
        root=tmp_path,staged=SimpleNamespace(consume_sources=consume),dialogue=SimpleNamespace(run_task=task))
    assert [x['correction_id'] for x in parsed['correction_resolutions']]==ids
    assert parsed['remaining_disagreements']==[]
    assert len(tasks)==4
    assert witness['staged_reading_plan_hash']=='d'*64
    assert next(x for x in sources_seen if x['source_id']=='principal-ledgers')['content']==staged.canonical({'full_original_ledgers':'retained'})
