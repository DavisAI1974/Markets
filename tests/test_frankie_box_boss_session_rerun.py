"""The rerun wiring (Greg, 2026-09-21: "make the changes that Frankie asked for and add the calcs he wants to cyc 0 and
rerun"): the comparison and session-receipts packets enter the writing base, the accounting and receipt-ledger prompts
point at them, reading runs again when the corpus the session would read now differs from the one it read, and writing
runs again when any of its inputs moved. Stub session, real packet modules."""
import importlib.util
import pytest
import json
import types
from pathlib import Path

SESSION = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_boss_session.py'
spec = importlib.util.spec_from_file_location('frankie_box_boss_session_rerun_under_test', SESSION)
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


def stub(tmp_path, monkeypatch):
    notes = []
    s = types.SimpleNamespace(work=tmp_path / 'work', out=tmp_path / 'out', cycle='00', _notes=notes)
    s.work.mkdir(); s.out.mkdir()
    s.note = notes.append
    s._packets_text = lambda: session.Session._packets_text(s)
    s._writing_inputs = lambda: session.Session._writing_inputs(s)
    s._corpus_current = lambda: session.Session._corpus_current(s)
    monkeypatch.setattr(session, 'BRAIN_DIR', tmp_path / 'brain')
    monkeypatch.setattr(session, 'READING_LEDGER', tmp_path / 'reading-ledger.json')
    return s


def test_compare_and_receipts_stages_write_the_packets_and_the_base_carries_them(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    (s.work / 'derived').mkdir()
    (s.work / 'derive.json').write_text(json.dumps(dict(pin_group='legacy_observable_crosswalk', rows=dict(count=1), input_records=1, f_last_groups=0, failure_count=0,
                                                       layers=dict(legacy_price=dict(status='derived', producer='p', reason=None, sha256='a' * 64, bytes=1, path='x')))))
    (s.work / 'verify.json').write_text(json.dumps(dict(as_of=1, learning_cutoff_ns=2)))
    session.Session.compare(s)
    session.Session.receipts(s)
    assert (s.work / 'comparison.md').is_file() and (s.work / 'session-receipts.md').is_file()
    text = s._packets_text()
    assert text.startswith('----- COMPARISON PACKET -----\n# Comparison packet') and '----- SESSION RECEIPTS PACKET -----\n# Session receipts packet' in text
    assert any(n.startswith('comparison packet: 1 pin layers (1 derived) beside 9 frozen layers') for n in s._notes)
    assert any(n.startswith('session receipts packet: 0 provider invocations') for n in s._notes)
    inputs = s._writing_inputs()
    assert set(inputs) == {'comparison.md', 'session-receipts.md'} and all(len(v) == 64 for v in inputs.values())


def test_legacy_reading_receipt_without_coverage_must_be_read_again(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    corpus = s.work / 'reading-corpus-full.md'
    corpus.write_text('corpus v1')
    s.reading_corpus = lambda: corpus
    assert s._corpus_current() is False                                         # never read
    (s.work / 'merged-notes.md').write_text('notes')
    (s.work / 'reading.json').write_text(json.dumps(dict(corpus_sha256=session.sha256_bytes(b'corpus v1'))))
    assert s._corpus_current() is False                                         # legacy receipt lacks verified coverage
    corpus.write_text('corpus v2: the brain now carries the frozen learned structure')
    assert s._corpus_current() is False                                         # the corpus moved: read again


def test_writing_prompts_name_the_comparison_step_and_the_receipt_ledgers():
    text = SESSION.read_text()
    assert 'THE COMPARISON STEP' in text and 'file status "compared" with what differed' in text
    assert "RECEIPT_LEDGERS = ('output_provider_invocation_response_receipts', 'output_knowledge_retrieval_receipts', 'output_answer_wall_access_receipts')" in text
    assert 'THE SESSION RECEIPTS PACKET above is observed fact for this ledger' in text
    assert "written.get('inputs') != self._writing_inputs()" in text and 'if not self._corpus_current():' in text
    assert 'self.compare()' in text and 'self.receipts()' in text


def test_the_writing_gate_is_stable_once_writing_has_run(tmp_path, monkeypatch):
    """Ship review (Critical): the receipts packet listed the write-* jobs the previous writing pass left behind, so the
    packet, and the gate keyed on it, moved on every restart and all twelve writing calls ran again."""
    s = stub(tmp_path, monkeypatch)
    (s.work / 'derived').mkdir()
    (s.work / 'derive.json').write_text(json.dumps(dict(pin_group='legacy_observable_crosswalk', rows=dict(count=1), input_records=1, f_last_groups=0, failure_count=0, layers={})))
    (s.work / 'verify.json').write_text(json.dumps(dict(as_of=1, learning_cutoff_ns=2)))
    (s.work / 'boss-jobs' / 'abc').mkdir(parents=True)
    (s.work / 'boss-jobs' / 'abc' / 'request.json').write_text(json.dumps(dict(name='read-merge-0', body_sha256='a' * 64)))
    session.Session.compare(s); session.Session.receipts(s)
    before = s._writing_inputs()
    (s.work / 'boss-jobs' / 'def').mkdir()
    (s.work / 'boss-jobs' / 'def' / 'request.json').write_text(json.dumps(dict(name='write-00-accounting', body_sha256='b' * 64)))
    session.Session.receipts(s)
    assert s._writing_inputs() == before
    report = json.loads((s.work / 'session-receipts.json').read_text())
    assert report['excluded_prefixes'] == ['write-'] and [i['name'] for i in report['provider_invocations']] == ['read-merge-0']
    (s.work / 'classroom').mkdir(); (s.work / 'classroom' / 'ledgers.json').write_text('{"a": 1}')
    assert 'classroom/ledgers.json' in s._writing_inputs()      # a re-assembled classroom re-writes the response


def test_refusal_receipts_never_overwrite_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    (tmp_path / 'receipts').mkdir()
    s = types.SimpleNamespace(cycle='00', note=lambda text: None)
    for _ in range(3):
        try:
            session.Session.refuse(s, 'synthetic')
        except SystemExit as stop:
            assert stop.code == 3
    assert len(list((tmp_path / 'receipts').glob('boss-session-refusal-*.json'))) == 3


def test_a_serverless_outcome_is_resumed_only_for_the_prompt_it_answered(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    s.serverless = dict(endpoint_id='e', key='k', execution_timeout_ms=1000, config_hash='c')
    s.served_model = 'm'
    s._input_tokens = lambda text: 10
    d = s.work / 'serverless-jobs' / 'read-part-0001'
    d.mkdir(parents=True)
    (d / 'outcome.json').write_text(json.dumps(dict(text='the old answer')))
    (d / 'prompt.txt').write_text('the old prompt', encoding='utf-8')
    s._supersede_job = lambda directory, name, text: session.Session._supersede_job(s, directory, name, text)
    assert session.Session.serverless_job(s, 'read-part-0001', 'the old prompt') == dict(text='the old answer')
    s._serverless_exchange = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('stop before any network call'))
    with pytest.raises(RuntimeError, match='stop before any network call'):
        session.Session.serverless_job(s, 'read-part-0001', 'a new prompt')
    aside = [p for p in (s.work / 'serverless-jobs').iterdir() if p.name.startswith('read-part-0001.superseded-')]
    assert len(aside) == 1 and (aside[0] / 'outcome.json').exists() and json.loads((aside[0] / 'superseded.json').read_text())['name'] == 'read-part-0001'
    assert not (d / 'outcome.json').exists() and any('moved aside' in n for n in s._notes)


def test_writing_prompts_account_for_the_bedrock_and_the_analysis_carries_the_teachback_section(tmp_path, monkeypatch):
    """BR-7: the accounting prompt says a bedrock layer is accounted for like a pinned one (its own status and reason);
    the analysis prompt names the teach-back section the session appends; _teach_section renders it from the filed
    teach-back and is empty when none was filed."""
    text = SESSION.read_text()
    accounting = text.split("self.boss('write-accounting'")[1].split('accounting_entry = ')[0]
    assert 'THE BEDROCK' in accounting and 'a bedrock layer is accounted for like a pinned one, with its own status and reason' in accounting
    analysis = text.split("self.boss('write-analysis'")[1].split('analysis_md = ')[0]
    assert 'THE EXHAUSTION AND D TEACH-BACK' in analysis
    assert "analysis_md = analysis_md.rstrip('\\n') + self._teach_section()" in text or 'analysis_md += self._teach_section()' in text
    s = stub(tmp_path, monkeypatch)
    s._teach_section = lambda: session.Session._teach_section(s)
    assert s._teach_section() == ''
    (s.work / 'teach').mkdir()
    (s.work / 'teach' / 'exhaustion-teachback.json').write_text(json.dumps(dict(
        cycle='00', facts_sha256='f' * 64, call=dict(attempt='teach-exhaustion', lane='boss'), frozen=[dict(layer='learned_dipoles_and_geometry', source='research/X.md')],
        facts_text='# FACTS\n\n13.0 s\n',
        answer=dict(exhaustion=dict(what_it_is='a', how_this_cycle_shows_it='b', what_this_cycle_cannot_show='c', relation_to_dipole_state='d'),
                    d_depth=dict(what_it_is='e', how_this_cycle_shows_it='f', what_this_cycle_cannot_show='g', relation_to_dipole_state='h'),
                    families=dict(what_it_is='i', how_this_cycle_shows_it='j', what_this_cycle_cannot_show='k', relation_to_dipole_state='l'),
                    prebirth=dict(what_it_is='m', how_this_cycle_shows_it='n', what_this_cycle_cannot_show='o', relation_to_dipole_state='p'),
                    clocks=dict(what_it_is='q', how_this_cycle_shows_it='r', what_this_cycle_cannot_show='s', relation_to_dipole_state='t'),
                    questions=['u?']))))
    section = s._teach_section()
    assert section.startswith('\n\n## THE EXHAUSTION AND D TEACH-BACK')
    assert '**what_it_is**: a' in section and '### clocks' in section and '- u?' in section and 'f' * 64 in section
    assert 'research/X.md' in section and '# FACTS' not in section       # the answer and its witnesses; the facts stay in the teach-back file


def test_every_publication_retries_brain_retention_first(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    s.dir = tmp_path / 'session'
    s.dir.mkdir()
    s.day = '20211004'
    events, attempts = [], []
    def retain():
        attempts.append(1)
        events.append('brain')
        if len(attempts) == 1:
            raise RuntimeError('retention unavailable')
    s.brain_entry = retain
    s.phase = lambda *args: None
    def publish(*args, **kwargs):
        events.append('push')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(session.subprocess, 'run', publish)
    with pytest.raises(RuntimeError, match='retention unavailable'):
        session.Session.push(s)
    assert events == ['brain'] and not (s.dir / 'done').exists()
    assert session.Session.push(s) is True
    assert events == ['brain', 'brain', 'push']


@pytest.mark.parametrize('payload', ['', '## BOSS/Granite producer evidence\n{broken'])
def test_raw_corpus_carries_the_pinned_prior_cycle_zero_documents(tmp_path, monkeypatch, payload):
    s = stub(tmp_path, monkeypatch)
    s.day = '20211004'
    s._head_through_ledger = lambda text: text
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    monkeypatch.setattr(session, 'READING_CONFIG', tmp_path / 'absent.json')
    (tmp_path / 'request').mkdir()
    (tmp_path / 'request' / 'prompt.md').write_text('request instructions\n' + payload)
    (s.work / 'derivation-digest-full.md').write_text('historical digest')
    (s.out / 'analysis.md').write_text('prior cycle zero observed knowledge')
    (s.out / 'response.json').write_text('{"lessons": []}')
    brain = session.brain_module()
    brain.write_entry(s.work, s.out, session.BRAIN_DIR, '00')
    s.knowledge_base = brain.pin_session_base(session.BRAIN_DIR, 'a'*64, s.work / 'base-receipt.json')
    corpus = session.Session.reading_corpus(s)
    assert 'prior cycle zero observed knowledge' in corpus.read_text()
    report = json.loads((s.work / 'reading-corpus.json').read_text())
    assert any(m['name'].endswith('analysis.md') for m in report['members'])
