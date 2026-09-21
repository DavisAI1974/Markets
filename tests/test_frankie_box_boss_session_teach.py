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


import test_frankie_box_boss_session_derive as D  # noqa: E402  (the real session derive on the journal-shaped fixture stream)
import _producers as P  # noqa: E402


def work_dir(tmp_path, monkeypatch):
    """A work directory the REAL session derive wrote: the pinned driver on the fixture stream, the twenty bedrock layer
    files projected by the pinned crosswalk (the producers' own row shapes, never hand-written here)."""
    s = D.stub(tmp_path, monkeypatch)
    D.session.Session.derive(s)
    return s.work


def ledger_rows(work, section):
    rows = [json.loads(l) for l in (work / 'bedrock' / 'ledgers' / 'exact_lifecycle_rows.jsonl').read_text().splitlines() if l.strip()]
    return [r for r in rows if r.get('emitting_section') == section]


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


def good_answer(prompt):
    """An answer whose every number is taken from the facts in the prompt (the lineage node count and the span)."""
    import re
    nodes = re.search(r'\(4\.13\): (\d+) nodes', prompt).group(1)
    span = re.search(r'rows span ([\d.]+) s', prompt).group(1)
    topic = lambda n: dict(what_it_is=f'{n} is the concept', how_this_cycle_shows_it=f'{nodes} lineage nodes over {span} s of rows',
                           what_this_cycle_cannot_show='the candidate lane needs 900 s; no episode rows', relation_to_dipole_state='the dipole state needs an episode')
    return json.dumps(dict(exhaustion=topic('exhaustion'), d_depth=topic('D'), families=topic('families'), prebirth=topic('pre-birth'), clocks=topic('clocks'),
                           questions=['do the whole day\'s records reach the candidate lane?']))


def stub(tmp_path, monkeypatch, answers):
    work = work_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(session, 'PRODUCERS', P.require_producers())
    monkeypatch.setattr(session, 'BRAIN_DIR', brain_dir(tmp_path))
    monkeypatch.setattr(session, 'ROOT', tmp_path / 'root')
    (tmp_path / 'root' / 'receipts').mkdir(parents=True, exist_ok=True)
    calls = []
    notes = []
    s = types.SimpleNamespace(work=work, out=tmp_path / 'out', cycle='00', day='20211003', _notes=notes, request=dict(request_id='req-1'), _estimate_kind='byte estimate', calls=calls)
    s.out.mkdir(exist_ok=True)
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


def test_facts_are_built_from_the_sessions_own_files_in_the_producers_shapes_and_never_average(tmp_path, monkeypatch):
    work = work_dir(tmp_path, monkeypatch)
    producers = P.require_producers()
    facts = T.facts(work, brain_dir(tmp_path), producers)
    assert facts['schema'] == 'FRANKIE_BOX_TEACH_FACTS_V1'
    derive = json.loads((work / 'derive.json').read_bytes())
    assert facts['layers']['clock_lock_time'] == dict(status='could_not', count=0, reason=derive['layers']['clock_lock_time']['reason'])
    assert facts['traversal']['verdict'] == derive['bedrock']['verdict'] == 'ACCEPTED' and facts['traversal']['failed_gates'] == []
    # the lineage rows as the pinned driver emitted them: statuses from native_lineage's own vocabulary, never CLOSED
    lineage = ledger_rows(work, 'lineage')
    L = facts['lineage']
    assert L['vocabulary']['statuses'] == ['CENSORED_SEGMENT_END', 'CENSORED_STREAM_END', 'OPEN', 'TERMINATED']
    assert L['nodes'] == len(lineage) > 0 and sum(L['depth_histogram'].values()) == L['nodes']
    assert L['depth_histogram'] == {str(d): sum(1 for r in lineage if r['depth'] == d) for d in sorted({r['depth'] for r in lineage})}
    assert L['terminated'] + L['censored'] + L['open'] == L['nodes'] and L['terminated'] == sum(1 for r in lineage if r['status'] == 'TERMINATED')
    assert 'CLOSED' not in json.dumps(L)
    # the recurrence gaps as the driver emitted them: mappings with gap_ns, from_node, to_node, recv_ns; listed per event, the largest named
    recurrence = ledger_rows(work, 'recurrence')
    A = facts['ancestry_gaps']
    assert A['events'] == len(recurrence) and A['count'] == sum(len(r['gaps']) for r in recurrence) > 0
    assert A['per_event'][0]['gaps'][0] == dict(gap_ns=recurrence[0]['gaps'][0]['gap_ns'], from_node=recurrence[0]['gaps'][0]['from_node'],
                                                to_node=recurrence[0]['gaps'][0]['to_node'], recv_ns=recurrence[0]['gaps'][0]['recv_ns'],
                                                continuity_segment=recurrence[0]['gaps'][0]['continuity_segment'])
    assert [g['gap_ns'] for g in A['largest']] == sorted([g['gap_ns'] for r in recurrence for g in r['gaps']], reverse=True)[:T.LARGEST_GAPS]
    assert all('from_node' in g and 'to_node' in g and 'event' in g for g in A['largest'])
    assert A['largest_ns'] == max(g['gap_ns'] for r in recurrence for g in r['gaps'])
    assert 'mean' not in json.dumps(facts) and 'average' not in json.dumps(facts)
    C = facts['clocks']
    assert C['derived_clocks'] == dict(clock_event_known_by=True, clock_feature_availability=True, clock_model_evaluation=True)
    assert C['groups'] == derive['bedrock']['groups'] and C['ordered'] + C['unknown'] + len(C['violations']) == C['groups']
    assert C['ordered'] == C['groups'] and C['violations'] == [] and C['decision_basis'] == {'REPLAY_EARLIEST_LAWFUL_AVAILABILITY': C['groups']}
    F = facts['families']
    geometry = json.loads(Path(derive['layers']['derived_d_family_geometry']['path']).read_bytes())
    ids = [r['structure.candidate_family_id'] for r in geometry['member_rows']]
    assert F['distinct_family_ids'] == len(set(ids)) and sum(F['family_id_counts'].values()) == len(ids)
    assert sum(a['count'] for a in F['action_strings']) == derive['f_last_groups']
    T_ = facts['candidate_lane']
    assert T_['warmup_seconds'] == 900 and T_['min_observations'] == 600 and T_['candidate_unit_events'] == 0 and T_['span_seconds'] == pytest.approx(10.0)
    assert T_['verdict'].startswith('the candidate lane cannot open on this cycle\'s rows: 10.0 s of rows against a 900 s warmup and 600 observations')
    assert [f['layer'] for f in facts['frozen']] == list(FROZEN) and all(f['text'].startswith('# Frozen study') for f in facts['frozen'])
    text = T.facts_text(facts)
    assert str(A['largest_ns']) in text and '# Frozen study 2' in text and 'NO_PRODUCER_FOUND' in text and 'verdict over this slice: ACCEPTED' in text
    assert f"{L['terminated']} terminated, {L['censored']} censored, {L['open']} open" in text
    assert T.facts_text(facts) == text


def test_the_candidate_lane_opened_verdict_and_a_missing_clock_layer_reported_as_unknown(tmp_path, monkeypatch):
    work = work_dir(tmp_path, monkeypatch)
    producers = P.require_producers()
    derive = json.loads((work / 'derive.json').read_bytes())
    derive['bedrock']['sections_fed']['candidate_unit_events'] = 3
    derive['bedrock']['sections_fed']['4.10_4.11_4.12_episode_rows'] = 7
    derive['layers']['clock_event_known_by']['status'] = 'could_not'
    known = Path(derive['layers']['clock_event_known_by']['path'])
    body = json.loads(known.read_bytes()); body['status'] = 'could_not'; body['member_rows'] = []; body['reason'] = 'test: not derived'
    known.write_text(json.dumps(body))
    (work / 'derive.json').write_text(json.dumps(derive))
    facts = T.facts(work, brain_dir(tmp_path), producers)
    assert facts['candidate_lane']['verdict'] == 'the candidate lane opened on this cycle\'s rows: 3 candidate events, 7 episode rows over 10.0 s'
    C = facts['clocks']
    assert C['derived_clocks']['clock_event_known_by'] is False and C['violations'] == [] and C['unknown'] == C['groups'] and C['ordered'] == 0
    assert f"{C['groups']} unknown (a clock layer not derived)" in T.facts_text(facts)


def test_a_lineage_status_outside_the_pinned_vocabulary_is_refused(tmp_path, monkeypatch):
    work = work_dir(tmp_path, monkeypatch)
    derive = json.loads((work / 'derive.json').read_bytes())
    for name in derive['bedrock']['layers']:                       # every file carrying lineage rows (the facts read the first)
        path = Path(derive['layers'][name]['path'])
        body = json.loads(path.read_bytes())
        if any(r.get('emitting_section') == 'lineage' for r in body.get('lifecycle_rows', [])):
            for row in body['lifecycle_rows']:
                if row['emitting_section'] == 'lineage':
                    row['status'] = 'CLOSED'
            path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="outside the pinned vocabulary"):
        T.facts(work, brain_dir(tmp_path), P.require_producers())


def test_facts_refuse_without_a_bedrock_or_a_frozen_file(tmp_path, monkeypatch):
    producers = P.require_producers()
    work = work_dir(tmp_path, monkeypatch)
    brain = brain_dir(tmp_path)
    derive = json.loads((work / 'derive.json').read_bytes()); saved = derive['bedrock']; derive['bedrock'] = None
    (work / 'derive.json').write_text(json.dumps(derive))
    with pytest.raises(ValueError, match='derive.json carries no bedrock'):
        T.facts(work, brain, producers)
    derive['bedrock'] = saved
    (work / 'derive.json').write_text(json.dumps(derive))
    manifest = json.loads((brain / 'frozen-learned-structure' / 'MANIFEST.json').read_bytes())
    manifest['entries'] = [e for e in manifest['entries'] if FROZEN[1] not in e['layers']]
    (brain / 'frozen-learned-structure' / 'MANIFEST.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='no included frozen learned-structure file for learned_dipoles_and_geometry'):
        T.facts(work, brain, producers)


def test_numbers_in_an_answer_are_checked_against_the_facts_as_values():
    facts = 'rows span 13.04 s; 2282 groups; the largest gap 4750000000 ns; defined on 2026-08-17; 13.0 s'
    assert T.numbers_in('2,282 groups and 13.04 s and 4750000000 and 2026-08-17') <= T.numbers_in(facts)
    assert T.missing_numbers('there were 2282 groups over 13.04 s', facts) == []
    assert T.missing_numbers('there were 2283 groups, a 42.7 percent rise', facts) == ['2283', '42.7']
    assert T.missing_numbers('D0 and D1 and 4.13 lineage', facts + ' D0 D1 4.13') == []
    assert T.missing_numbers('13 s and 13.00 s and 2282.0 groups', facts) == []       # values, not spellings
    assert T.missing_numbers('a -5 delta', 'the 5 groups') == ['-5']                      # the sign is part of the number
    assert T.missing_numbers('a delta of -2282', facts) == ['-2282']


def test_digit_runs_inside_a_sha256_in_the_facts_never_license_a_number(tmp_path, monkeypatch):
    facts = T.facts(work_dir(tmp_path, monkeypatch), brain_dir(tmp_path), P.require_producers())
    text = T.facts_text(facts)
    sha = facts['frozen'][0]['sha256']
    import re
    runs = [m for m in re.findall(r'\d{3,}', sha)]
    assert runs, 'the fixture digest carries digit runs'
    foreign = next(r for r in runs if r not in T._HEX.sub(' ', text))
    assert T.missing_numbers(f'a {foreign} percent rise', text) == [foreign]
    assert T.missing_numbers('sha256 ' + sha, text) == []                                  # citing the digest itself is not a number


def test_parse_answer_edge_shapes(tmp_path, monkeypatch):
    facts = 'the 5 groups'
    prose = 'Here is my answer:\n' + json.dumps({t: {f: 'x 5' for f in T.FIELDS} for t in T.TOPICS} | dict(questions=['q'])) + '\nDone.'
    assert T.parse_answer(prose, facts)['questions'] == ['q']
    bad = {t: {f: 'x' for f in T.FIELDS} for t in T.TOPICS}
    with pytest.raises(ValueError, match='questions must be a list'):
        T.parse_answer(json.dumps(bad | dict(questions='no')), facts)
    with pytest.raises(ValueError, match='at most 20 questions'):
        T.parse_answer(json.dumps(bad | dict(questions=['q'] * 21)), facts)
    with pytest.raises(ValueError, match='not a JSON object'):
        T.parse_answer('no braces here', facts)
    record = dict(cycle='00', facts_sha256='f' * 64, call=dict(attempt='a', lane='boss'), frozen=[], facts_text='# FACTS',
                  answer={t: {f: 'line one\n## forged heading\n- forged item' for f in T.FIELDS} for t in T.TOPICS} | dict(questions=['a\n# b']))
    md = T.markdown(record)
    assert '\n## forged heading' not in md and '\n- forged item' not in md and '**what_it_is**: line one ## forged heading - forged item' in md
    assert '- a # b' in md


def test_a_stub_boss_answer_with_every_topic_is_filed_once_and_a_restart_makes_no_model_call(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch, [lambda prompt: good_answer(prompt)])
    record = s.teach()
    assert record['schema'] == 'FRANKIE_BOX_TEACHBACK_V1' and set(record['answer']) == {'exhaustion', 'd_depth', 'families', 'prebirth', 'clocks', 'questions'}
    assert record['call']['attempt'] == 'teach-exhaustion' and record['call']['lane'] == 'boss' and record['facts_sha256']
    assert record['frozen'] == [dict(layer=f['layer'], name=f['name'], source=f['source'], bytes=f['bytes'], sha256=f['sha256']) for f in T.facts(s.work, session.BRAIN_DIR, session.PRODUCERS)['frozen']]
    assert (s.work / 'teach' / 'exhaustion-teachback.json').is_file()
    md = (s.work / 'teach' / 'exhaustion-teachback.md').read_text()
    assert md.startswith('# The exhaustion and D teach-back') and '## exhaustion' in md and '## clocks' in md and '## questions' in md
    assert str(record['facts']['ancestry_gaps']['largest_ns']) in md and 'verdict over this slice: ACCEPTED' in md
    assert s.calls == ['teach-exhaustion']
    again = s.teach()
    assert again == record and s.calls == ['teach-exhaustion']
    prompt_text = (s.work / 'teach' / 'prompt.txt').read_text()
    assert 'exhaustion' in prompt_text and '# Frozen study 3' in prompt_text and 'every number you cite must appear in the facts' in prompt_text


def test_a_number_not_in_the_facts_is_asked_once_more_then_refused_with_a_receipt(tmp_path, monkeypatch):
    bad = lambda prompt: good_answer(prompt).replace('is the concept', 'is the concept, a 42.7 percent rise')
    s = stub(tmp_path, monkeypatch, [bad, bad])
    with pytest.raises(RuntimeError, match='REFUSED: teach-exhaustion: the BOSS\'s classroom answer was unusable twice') as info:
        s.teach()
    assert '42.7' in str(info.value) and s.calls == ['teach-exhaustion', 'teach-exhaustion-retry']
    assert not (s.work / 'teach' / 'exhaustion-teachback.json').exists()


def test_a_facts_failure_is_a_receipted_refusal_not_a_traceback(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch, [lambda prompt: good_answer(prompt)])
    monkeypatch.setattr(session._box_module('frankie_box_teach'), 'facts', lambda *a, **k: (_ for _ in ()).throw(TypeError("int() argument must be 'str', not 'dict'")))
    with pytest.raises(RuntimeError, match="REFUSED: teach: the facts could not be computed from this session's files \\(TypeError"):
        s.teach()
    assert s.calls == []


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
