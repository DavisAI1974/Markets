"""The rerun wiring (Greg, 2026-09-21: "make the changes that Frankie asked for and add the calcs he wants to cyc 0 and
rerun"): the comparison and session-receipts packets enter the writing base, the accounting and receipt-ledger prompts
point at them, reading runs again when the corpus the session would read now differs from the one it read, and writing
runs again when any of its inputs moved. Stub session, real packet modules."""
import importlib.util
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


def test_reading_runs_again_only_when_the_corpus_differs(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    corpus = s.work / 'reading-corpus-full.md'
    corpus.write_text('corpus v1')
    s.reading_corpus = lambda: corpus
    assert s._corpus_current() is False                                         # never read
    (s.work / 'merged-notes.md').write_text('notes')
    (s.work / 'reading.json').write_text(json.dumps(dict(corpus_sha256=session.sha256_bytes(b'corpus v1'))))
    assert s._corpus_current() is True                                          # read this exact corpus
    corpus.write_text('corpus v2: the brain now carries the frozen learned structure')
    assert s._corpus_current() is False                                         # the corpus moved: read again


def test_writing_prompts_name_the_comparison_step_and_the_receipt_ledgers():
    text = SESSION.read_text()
    assert 'THE COMPARISON STEP' in text and 'file status "compared" with what differed' in text
    assert "RECEIPT_LEDGERS = ('output_provider_invocation_response_receipts', 'output_knowledge_retrieval_receipts', 'output_answer_wall_access_receipts')" in text
    assert 'THE SESSION RECEIPTS PACKET above is observed fact for this ledger' in text
    assert "written.get('inputs') != self._writing_inputs()" in text and 'if not self._corpus_current():' in text
    assert 'self.compare()' in text and 'self.receipts()' in text
