"""BR-6 (SPEC_CYCLE0_BEDROCK_20260921.md box-teach-exhaustion): one BOSS teach-back on exhaustion and D from the session's
own bedrock facts and the frozen learned-structure files, transcription-checked by code (every number the BOSS cites
must be in the facts), filed under work/teach/, never in response.json. Stub session and stub BOSS over the real
modules; no model, box or host call."""
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
BOX = TESTS.parent / 'deploy' / 'aws' / 'box'


def load(name, alias=None):
    spec = importlib.util.spec_from_file_location(alias or name, BOX / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


session = load('frankie_box_boss_session', 'frankie_box_boss_session_teach_under_test')
T = load('frankie_box_teach')
NS = 1_000_000_000
BASE = 1633298400 * NS + 300_150_000
FROZEN = ('learned_d_structures_and_families', 'learned_dipoles_and_geometry', 'learned_chains_extensions_reappearances_ancestry',
          'predecessor_ancestry_unresolved_chain_state')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def work_dir(tmp_path):
    work = tmp_path / 'work'
    derived = work / 'derived'
    derived.mkdir(parents=True)
    lineage = [dict(emitting_section='lineage', node_id=700 + i, parent_id=None if i in (0, 3) else 700, depth=[0, 1, 2, 0, 1][i],
                    status=['CLOSED', 'CLOSED', 'OPEN', 'CLOSED', 'CENSORED_STREAM_END'][i], side_orientation='B') for i in range(5)]
    recurrence = [dict(emitting_section='recurrence', gap_count=3, gaps=[1_500_000_000, 250_000_000, 4_750_000_000], run_count=1, runs=[]),
                  dict(emitting_section='recurrence', gap_count=1, gaps=[900_000_000], run_count=1, runs=[])]
    members = []
    for g in range(4):
        recv = BASE + g * 3 * NS
        members.append({'group_index': g, 'ts_recv_ns': recv, 'f_last_ts_recv_ns': recv, 'clocks.first_lawful_availability_ns': recv,
                        'clocks.decision_ts_recv_ns': recv if g != 3 else recv - 1, 'decision_basis': 'REPLAY_EARLIEST_LAWFUL_AVAILABILITY',
                        'structure.candidate_family_id': 'ow-%d' % (g % 2), 'structure.side_string': 'BA'})
    files = {
        'derived_ancestry_gaps': dict(status='derived', reason=None, count=7, lifecycle_sections=['lineage', 'recurrence'], member_rows=[],
                                      lifecycle_rows=lineage + recurrence, section_counts=dict(lineage=5, recurrence=2), producer='native_replay_driver.LineageGraph', partial=[]),
        'derived_d_family_geometry': dict(status='derived', reason=None, count=9, lifecycle_sections=['lineage'], member_paths=['structure.candidate_family_id', 'structure.side_string'],
                                          member_rows=members, lifecycle_rows=lineage, section_counts=dict(lineage=5), producer='a_memory_member_first_recalculation_20260828.describe_structure', partial=[]),
        'clock_event_known_by': dict(status='derived', reason=None, count=4, lifecycle_sections=[], member_paths=['clocks.first_lawful_availability_ns'], member_rows=members, lifecycle_rows=[], section_counts={}, producer='native_clocks.member_clock_row', partial=[]),
        'clock_feature_availability': dict(status='derived', reason=None, count=4, lifecycle_sections=[], member_paths=['clocks.first_lawful_availability_ns'], member_rows=members, lifecycle_rows=[], section_counts={}, producer='native_clocks.member_clock_row', partial=[]),
        'clock_model_evaluation': dict(status='derived', reason=None, count=4, lifecycle_sections=[], member_paths=['clocks.decision_ts_recv_ns', 'decision_basis'], member_rows=members, lifecycle_rows=[], section_counts={}, producer='native_clocks.member_clock_row', partial=[]),
        'prebirth_predecessor_at_risk_state': dict(status='could_not', reason='the candidate lane needs 900 s of warmup and 600 observations before any candidate can be detected; this cycle\'s rows span 13.0 s',
                                                   count=0, lifecycle_sections=['episode', 'candidate'], member_rows=[], lifecycle_rows=[], section_counts=dict(episode=0, candidate=0), producer='native_replay_driver._open_candidate', partial=[]),
        'clock_lock_time': dict(status='could_not', reason='NO_PRODUCER_FOUND: lock time is Frankie\'s OUTPUT', count=0, lifecycle_sections=[], member_rows=[], lifecycle_rows=[], section_counts={}, producer=None, partial=[]),
    }
    layers = {}
    for name, body in files.items():
        p = derived / f'{name}.json'
        p.write_text(json.dumps(body, sort_keys=True))
        layers[name] = dict(status=body['status'], reason=body['reason'], producer=body['producer'], count=body['count'], sha256=sha(p.read_bytes()), bytes=p.stat().st_size, path=str(p), bedrock=True)
    (derived / 'legacy_structure_observables.json').write_text(json.dumps(dict(status='derived', groups=[dict(action_string=s) for s in ('ACA', 'ACA', 'T', 'ACAM', 'ACA', 'T')])))
    layers['legacy_structure_observables'] = dict(status='derived', reason=None, producer='describe_structure', sha256='a' * 64, bytes=1, path=str(derived / 'legacy_structure_observables.json'))
    (work / 'derive.json').write_text(json.dumps(dict(
        layers=layers, pin_group='legacy_observable_crosswalk',
        bedrock=dict(layers=list(files), derived=5, could_not=2, span_seconds=13.04, groups=2282, records=3262,
                     candidate_warmup_seconds=900, candidate_min_observations=600,
                     sections_fed={'candidate_unit_events': 0, '4.10_4.11_4.12_episode_rows': 0, '4.13_lineage_nodes_added': 5, '4.0_flow_seconds_completed': 12}))))
    return work


def brain_dir(tmp_path):
    frozen = tmp_path / 'brain' / 'frozen-learned-structure'
    frozen.mkdir(parents=True)
    entries = []
    for i, layer in enumerate(FROZEN):
        name = f'research__STUDY_{i}.md'
        data = f'# Frozen study {i} for {layer}\n\nD-depth families were defined on 2026-08-17 with 3 depths.\n'.encode()
        (frozen / name).write_bytes(data)
        entries.append(dict(name=name, source=f'research/STUDY_{i}.md', layers=[layer], include=True, bytes=len(data), sha256=sha(data)))
    other = b'# unrelated frozen file\n'
    (frozen / 'research__OTHER.md').write_bytes(other)
    entries.append(dict(name='research__OTHER.md', source='research/OTHER.md', layers=['historical_timing_lifespan_context'], include=True, bytes=len(other), sha256=sha(other)))
    excluded = b'# excluded\n'
    (frozen / 'research__EXCLUDED.md').write_bytes(excluded)
    entries.append(dict(name='research__EXCLUDED.md', source='research/EXCLUDED.md', layers=[FROZEN[0]], include=False, reason='bytes differ', bytes=len(excluded), sha256=sha(excluded)))
    (frozen / 'MANIFEST.json').write_text(json.dumps(dict(entries=entries, at=1, layers=list(FROZEN))))
    return tmp_path / 'brain'


def good_answer(facts_text):
    """An answer whose every number is in the facts."""
    topic = lambda n: dict(what_it_is=f'{n} is the concept', how_this_cycle_shows_it='3 depths on 5 lineage nodes; 2 open lineages; the largest gap 4750000000 ns',
                           what_this_cycle_cannot_show='the candidate lane needs 900 s; the rows span 13.0 s', relation_to_dipole_state='the dipole state needs an episode; 0 episode rows')
    return json.dumps(dict(exhaustion=topic('exhaustion'), d_depth=topic('D'), families=topic('families'), prebirth=topic('pre-birth'), clocks=topic('clocks'),
                           questions=['do the whole day\'s records, beyond these 3262, reach the candidate lane?']))


def stub(tmp_path, monkeypatch, answers):
    work = work_dir(tmp_path)
    monkeypatch.setattr(session, 'BRAIN_DIR', brain_dir(tmp_path))
    monkeypatch.setattr(session, 'ROOT', tmp_path / 'root')
    (tmp_path / 'root' / 'receipts').mkdir(parents=True)
    calls = []
    notes = []
    s = types.SimpleNamespace(work=work, out=tmp_path / 'out', cycle='00', day='20211003', _notes=notes, request=dict(request_id='req-1'), _estimate_kind='byte estimate', calls=calls)
    s.out.mkdir()
    s.note = notes.append
    s._input_tokens = lambda text: session.Session._input_tokens(s, text)
    s._tokenizer = lambda: None
    s._classroom_call = lambda *a, **k: session.Session._classroom_call(s, *a, **k)
    s.teach = lambda: session.Session.teach(s)

    def refuse(why):
        raise RuntimeError('REFUSED: ' + why)
    s.refuse = refuse

    def boss(name, text):
        calls.append(name)
        body = answers.pop(0) if answers else '{}'
        return dict(text=body if not callable(body) else body(text), incomplete=False, job_id='job-%d' % len(calls), usage=dict(prompt_tokens=1))
    s.boss = boss
    return s


def test_facts_are_built_from_the_sessions_own_files_and_never_average(tmp_path):
    facts = T.facts(work_dir(tmp_path), brain_dir(tmp_path))
    assert facts['schema'] == 'FRANKIE_BOX_TEACH_FACTS_V1'
    assert facts['layers']['clock_lock_time'] == dict(status='could_not', count=0, reason='NO_PRODUCER_FOUND: lock time is Frankie\'s OUTPUT')
    assert facts['lineage']['depth_histogram'] == {'0': 2, '1': 2, '2': 1} and facts['lineage']['nodes'] == 5
    assert facts['lineage']['status_counts'] == dict(CLOSED=3, OPEN=1, CENSORED_STREAM_END=1) and facts['lineage']['open'] == 2 and facts['lineage']['closed'] == 3
    gaps = facts['ancestry_gaps']
    assert gaps['count'] == 4 and gaps['largest'][0] == dict(gap_ns=4_750_000_000, event=0) and [g['gap_ns'] for g in gaps['largest']] == [4_750_000_000, 1_500_000_000, 900_000_000, 250_000_000]
    assert gaps['per_event'] == [dict(event=0, gap_count=3, gaps_ns=[1_500_000_000, 250_000_000, 4_750_000_000]), dict(event=1, gap_count=1, gaps_ns=[900_000_000])]
    assert 'mean' not in json.dumps(facts) and 'average' not in json.dumps(facts)
    assert facts['clocks'] == dict(groups=4, ordered=3, violations=[dict(group_index=3, known_by_ns=BASE + 9 * NS, availability_ns=BASE + 9 * NS, evaluation_ns=BASE + 9 * NS - 1)],
                                   rule='event_known_by <= feature_availability <= model_evaluation', decision_basis={'REPLAY_EARLIEST_LAWFUL_AVAILABILITY': 4})
    assert facts['families'] == dict(distinct_family_ids=2, family_id_counts={'ow-0': 2, 'ow-1': 2}, side_strings={'BA': 4}, action_strings=[dict(action_string='ACA', count=3), dict(action_string='T', count=2), dict(action_string='ACAM', count=1)])
    assert facts['candidate_lane'] == dict(span_seconds=13.04, warmup_seconds=900, min_observations=600, candidate_unit_events=0, episode_rows=0,
                                           verdict='the candidate lane cannot open on this cycle\'s rows: 13.0 s of rows against a 900 s warmup and 600 observations; the dipole state and the pre-birth cases have no rows here')
    assert [f['layer'] for f in facts['frozen']] == list(FROZEN) and all(f['text'].startswith('# Frozen study') for f in facts['frozen'])
    assert facts['frozen'][0]['name'] == 'research__STUDY_0.md' and facts['frozen'][0]['sha256'] == sha((tmp_path / 'brain' / 'frozen-learned-structure' / 'research__STUDY_0.md').read_bytes())
    text = T.facts_text(facts)
    assert '4750000000' in text and '13.04' in text and '# Frozen study 2' in text and 'NO_PRODUCER_FOUND' in text
    assert T.facts_text(facts) == text


def test_facts_refuse_without_a_bedrock_or_a_frozen_file(tmp_path):
    work = work_dir(tmp_path)
    brain = brain_dir(tmp_path)
    derive = json.loads((work / 'derive.json').read_bytes()); derive['bedrock'] = None
    (work / 'derive.json').write_text(json.dumps(derive))
    with pytest.raises(ValueError, match='derive.json carries no bedrock'):
        T.facts(work, brain)
    work = work_dir(tmp_path / 'b')
    manifest = json.loads((brain / 'frozen-learned-structure' / 'MANIFEST.json').read_bytes())
    manifest['entries'] = [e for e in manifest['entries'] if FROZEN[1] not in e['layers']]
    (brain / 'frozen-learned-structure' / 'MANIFEST.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='no included frozen learned-structure file for learned_dipoles_and_geometry'):
        T.facts(work, brain)


def test_numbers_in_an_answer_are_checked_against_the_facts():
    facts = 'rows span 13.04 s; 2282 groups; the largest gap 4750000000 ns; defined on 2026-08-17'
    assert T.numbers_in('2,282 groups and 13.04 s and 4750000000 and 2026-08-17') <= T.numbers_in(facts)
    assert T.missing_numbers('there were 2282 groups over 13.04 s', facts) == []
    assert T.missing_numbers('there were 2283 groups, a 42.7 percent rise', facts) == ['2283', '42.7']
    assert T.missing_numbers('D0 and D1 and 4.13 lineage', facts + ' D0 D1 4.13') == []


def test_a_stub_boss_answer_with_every_topic_is_filed_once_and_a_restart_makes_no_model_call(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch, [lambda prompt: good_answer(prompt)])
    record = s.teach()
    assert record['schema'] == 'FRANKIE_BOX_TEACHBACK_V1' and set(record['answer']) == {'exhaustion', 'd_depth', 'families', 'prebirth', 'clocks', 'questions'}
    assert record['call']['attempt'] == 'teach-exhaustion' and record['call']['lane'] == 'boss' and record['facts_sha256']
    assert record['frozen'] == [dict(layer=f['layer'], name=f['name'], source=f['source'], bytes=f['bytes'], sha256=f['sha256']) for f in T.facts(s.work, session.BRAIN_DIR)['frozen']]
    assert (s.work / 'teach' / 'exhaustion-teachback.json').is_file()
    md = (s.work / 'teach' / 'exhaustion-teachback.md').read_text()
    assert md.startswith('# The exhaustion and D teach-back') and '## exhaustion' in md and '## clocks' in md and '## questions' in md and '4750000000' in md
    assert s.calls == ['teach-exhaustion']
    again = s.teach()
    assert again == record and s.calls == ['teach-exhaustion']
    prompt_text = (s.work / 'teach' / 'prompt.txt').read_text()
    assert 'exhaustion' in prompt_text and '# Frozen study 3' in prompt_text and 'every number you cite must appear in the facts' in prompt_text


def test_a_number_not_in_the_facts_is_asked_once_more_then_refused_with_a_receipt(tmp_path, monkeypatch):
    bad = lambda prompt: good_answer(prompt).replace('3 depths', '3 depths and a 42.7 percent rise')
    s = stub(tmp_path, monkeypatch, [bad, bad])
    with pytest.raises(RuntimeError, match='REFUSED: teach-exhaustion: the BOSS\'s classroom answer was unusable twice') as info:
        s.teach()
    assert '42.7' in str(info.value) and s.calls == ['teach-exhaustion', 'teach-exhaustion-retry']
    assert not (s.work / 'teach' / 'exhaustion-teachback.json').exists()


def test_a_missing_topic_or_field_is_refused(tmp_path, monkeypatch):
    def missing(prompt):
        answer = json.loads(good_answer(prompt)); del answer['clocks']; return json.dumps(answer)
    def blank(prompt):
        answer = json.loads(good_answer(prompt)); answer['families']['why'] = ''; answer['families']['what_it_is'] = ''; return json.dumps(answer)
    s = stub(tmp_path, monkeypatch, [missing, blank])
    with pytest.raises(RuntimeError, match='unusable twice'):
        s.teach()
    assert any('clocks' in n and 'missing' in n for n in s._notes) and any('families.what_it_is' in n for n in s._notes)


def test_a_facts_text_over_the_part_budget_refuses_with_the_sizes(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch, [lambda prompt: good_answer(prompt)])
    monkeypatch.setattr(session, 'PART_INPUT_TOKENS', 100)
    with pytest.raises(RuntimeError, match='over the 100-token part budget') as info:
        s.teach()
    assert 'tokens (byte estimate)' in str(info.value) and s.calls == []


def test_teach_runs_after_the_classroom_and_before_writing_and_never_enters_the_response():
    text = (BOX / 'frankie_box_boss_session.py').read_text()
    assert "STAGES = ('verify', 'labels', 'engine', 'derive', 'reading', 'classroom', 'teach', 'writing', 'push', 'correction')" in text
    run = text.split('    def _run(self, stage):')[1]
    assert run.index("self.phase('classroom')") < run.index("self.phase('teach')") < run.index("self.phase('writing')")
    assert "if not (self.work / 'teach' / 'exhaustion-teachback.json').exists():" in run
    writing = text.split('    def writing(self):')[1].split('    def push(')[0]
    assert 'teach' not in writing.split('response = dict(')[1].split('classroom = self.classroom_ledgers()')[0]
