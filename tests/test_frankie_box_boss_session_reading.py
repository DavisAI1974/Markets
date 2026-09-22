"""The session's guarded part reader (frankie_box_boss_session._read_part_guarded) over a fake reading lane: a usable
note is taken as is; a refusal is retried once; two unusable answers split the part in two halves; every attempt is
kept. Structural text only, no market data. (Chat 6: cycle 0's part 4 note was a refusal and the merge dropped it.)"""
import importlib.util
import types
from pathlib import Path

SESSION = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_boss_session.py'
spec = importlib.util.spec_from_file_location('frankie_box_boss_session_reading_under_test', SESSION)
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)

HEADER = 'part {i}/{n} bytes {s}-{e} cycle {cycle} req {req}\n'
GOOD = '## observed\n\n' + ('- fact line with a number 12345 and a hash ' + 'c' * 64 + '\n') * 6
DATA = b''.join(b'row %04d ' % k + b'x' * 40 + b'\n' for k in range(200))


def make(tmp_path, answers):
    """answers: list of (text, incomplete, error) returned by the fake lane in call order; the names asked are recorded."""
    calls = []
    notes = []

    def reader(name, text):
        calls.append((name, text))
        t, inc, err = answers[len(calls) - 1]
        return dict(text=t, incomplete=inc, error=err, job_id=f'job-{len(calls)}')
    s = types.SimpleNamespace(cycle='01', request=dict(request_id='req-x'), serverless=None, reader=reader, note=notes.append,
                              _calls=calls, _notes=notes)
    notes_dir = tmp_path / 'notes'
    notes_dir.mkdir()
    return s, notes_dir


def test_a_usable_note_is_taken_first_time(tmp_path):
    s, notes_dir = make(tmp_path, [(GOOD, False, None)])
    r = session.Session._read_part_guarded(s, 3, 0, len(DATA), 4, DATA, HEADER, notes_dir)
    assert r['attempts'] == 1 and r['halves'] is False and r['unusable'] == [] and r['job_id'] == 'job-1'
    note = (notes_dir / 'note-0003.md').read_text()
    assert note.startswith('## Notes on part 4/4 (bytes 0-%d)\n' % len(DATA)) and 'UNUSABLE' not in note and GOOD in note
    assert [n for n, _ in s._calls] == ['read-0003'] and s._notes == []
    assert sorted(p.name for p in notes_dir.iterdir()) == ['attempt-0003-first.md', 'note-0003.md']


def test_a_refusal_is_retried_once_and_the_retry_is_used(tmp_path):
    s, notes_dir = make(tmp_path, [('I cannot complete this request as written because...', False, None), (GOOD, False, None)])
    r = session.Session._read_part_guarded(s, 3, 0, len(DATA), 4, DATA, HEADER, notes_dir)
    assert r['attempts'] == 2 and r['unusable'] == [] and r['job_id'] == 'job-2'
    assert [n for n, _ in s._calls] == ['read-0003', 'read-0003-retry']
    assert GOOD in (notes_dir / 'note-0003.md').read_text() and 'I cannot' not in (notes_dir / 'note-0003.md').read_text()
    assert 'I cannot complete' in (notes_dir / 'attempt-0003-first.md').read_text()
    assert s._notes == ['read-0003: note unusable (refusal); retrying once']


def test_two_unusable_answers_split_the_part_in_halves_read_separately(tmp_path):
    long_runaway = 'x ' * 500
    s, notes_dir = make(tmp_path, [(long_runaway, True, None), ('', False, 'lane error'), (GOOD + 'A', False, None), (GOOD + 'B', False, None)])
    r = session.Session._read_part_guarded(s, 3, 0, len(DATA), 4, DATA, HEADER, notes_dir)
    names = [n for n, _ in s._calls]
    assert names == ['read-0003', 'read-0003-retry', 'read-0003-a', 'read-0003-b'] and r['halves'] is True and r['unusable'] == []
    a_text, b_text = s._calls[2][1], s._calls[3][1]
    assert 'half a' in a_text and 'half b' in b_text
    a_body = a_text.split('\n', 2)[2].rsplit('\n----- PART ENDS', 1)[0]
    b_body = b_text.split('\n', 2)[2].rsplit('\n----- PART ENDS', 1)[0]
    assert (a_body + b_body).encode() == DATA and a_body.endswith('\n')     # the halves are the whole part, cut on a line boundary
    note = (notes_dir / 'note-0003.md').read_text()
    assert 'read in two halves' in note and '### Half a' in note and '### Half b' in note and GOOD + 'A' in note and GOOD + 'B' in note
    assert s._notes[:2] == ['read-0003: note unusable (incomplete); retrying once', 'read-0003: retry unusable (error); reading the part in two halves']
    assert sorted(p.name for p in notes_dir.iterdir()) == ['attempt-0003-a.md', 'attempt-0003-b.md', 'attempt-0003-first.md', 'attempt-0003-retry.md', 'note-0003.md']


def test_still_unusable_after_the_split_is_kept_as_returned_and_marked(tmp_path):
    s, notes_dir = make(tmp_path, [('', False, None), ('', False, None), ("I'm unable to help with that.", False, None), (GOOD, False, None)])
    r = session.Session._read_part_guarded(s, 3, 0, len(DATA), 4, DATA, HEADER, notes_dir)
    assert r['unusable'] == ['refusal']
    note = (notes_dir / 'note-0003.md').read_text()
    assert '### Half a' in note and '[UNUSABLE: refusal; kept as returned]' in note and GOOD in note
    assert s._notes[-1] == 'read-0003: still unusable after retry and split (refusal); kept as returned, marked'


def test_note_verdicts_and_split_range():
    docs = session.docs_module()
    assert docs.note_verdict('', dict()) == 'empty'
    assert docs.note_verdict('short', dict()) == 'empty'
    assert docs.note_verdict(GOOD, dict(error='boom')) == 'error'
    assert docs.note_verdict("  I can't help with this. " + GOOD, dict()) == 'refusal'
    assert docs.note_verdict('Sorry, but I cannot ' + GOOD, dict()) == 'refusal'
    assert docs.note_verdict(GOOD, dict(incomplete=True)) == 'incomplete'
    assert docs.note_verdict(GOOD, dict(incomplete=False)) is None
    assert docs.note_verdict('## Notes\n\nI cannot stress enough that ' + GOOD, dict()) is None   # a refusal is judged at the start only
    first, second = docs.split_range(b'ab\ncd\nef\n', 0, 9)
    assert first == (0, 6) and second == (6, 9)
    assert docs.split_range(b'a', 0, 1) == (None, None)


def test_a_runaway_note_is_detected_and_deloops_when_kept(tmp_path):
    docs = session.docs_module()
    runaway = GOOD + '\n' + '\n'.join(['- `^4 -3 -3 I+1 ^3`', '- `I+1`'] * 200)
    assert docs.note_verdict(runaway, dict(incomplete=True)) == 'runaway'
    assert docs.note_verdict(GOOD + '\n' + '\n'.join(f'- line {k}' for k in range(300)), dict()) is None
    d = docs.deloop(runaway)
    assert d.startswith(GOOD.rstrip('\n')) and 'RUNAWAY TAIL REMOVED' in d and 'lines drawn from 2 distinct lines' in d and d.count('I+1') == 0
    # four unusable answers: the final note is de-looped for the merge, the attempt files keep the full runaway text
    s, notes_dir = make(tmp_path, [(runaway, True, None)] * 4)
    r = session.Session._read_part_guarded(s, 3, 0, len(DATA), 4, DATA, HEADER, notes_dir)
    assert r['unusable'] == ['runaway', 'runaway'] and r['halves'] is True
    note = (notes_dir / 'note-0003.md').read_text()
    assert note.count('RUNAWAY TAIL REMOVED') == 2 and note.count('I+1') == 0 and GOOD.rstrip('\n') in note
    assert (notes_dir / 'attempt-0003-first.md').read_text().count('I+1') == 400


import json
import pytest

def integrated_reader(tmp_path, monkeypatch, answers):
    fake, unused = make(tmp_path, answers)
    s = session.Session.__new__(session.Session)
    s.__dict__.update(fake.__dict__)
    s.work = tmp_path / 'work'
    s.work.mkdir()
    s.day, s.pod_id, s.request_sha256 = '20211004', 'unused', 'a'*64
    corpus = s.work / 'corpus.md'
    corpus.write_bytes(DATA)
    s.reading_corpus = lambda: corpus
    s._chunks = lambda data: [(0, len(data))]
    s._fan_out = lambda label, items, fn: [fn(item) for item in items]
    s._merge_calls = []
    s._merge = lambda notes, level: s._merge_calls.append(notes) or '\n'.join(notes)
    s.docs = lambda: None
    s.refuse = lambda reason: (_ for _ in ()).throw(RuntimeError(reason))
    monkeypatch.setattr(session, 'READING_LEDGER', tmp_path / 'ledger.json')
    return s

def test_unusable_reading_cannot_merge_or_become_current_on_restart(tmp_path, monkeypatch):
    s = integrated_reader(tmp_path, monkeypatch, [('', False, None)] * 4 + [(GOOD, False, None)])
    with pytest.raises(RuntimeError, match='unusable'):
        s.reading()
    assert s._merge_calls == [] and not s._corpus_current()
    first = json.loads((s.work / 'reading.json').read_text())
    assert first['status'] == 'incomplete' and first['outcomes'][0]['unusable']
    s.reading()
    assert len(s._calls) == 5 and s._corpus_current()
    assert len(s._merge_calls) == 1
    assert any(p.read_text() == json.dumps(first, indent=2, sort_keys=True) + '\n'
               or json.loads(p.read_text()) == first for p in s.work.glob('superseded-reading-*/reading.json'))
    receipt = json.loads((s.work / 'reading.json').read_text())
    assert receipt['status'] == 'complete' and receipt['outcomes'][0]['unusable'] == []
    assert '20211004 trading-day run' in s._calls[-1][1]
    assert s._calls[-1][0] != s._calls[0][0]
    note = Path(receipt['notes_dir']) / 'note-0000.md'
    note.write_text('tampered')
    assert not s._corpus_current()
    assert list(s.work.glob('superseded-reading-*/move-receipt.json'))
