"""The classroom stages as wired in frankie_box_boss_session.Session (classroom, classroom_ledgers, correction, push turn):
fan-out over the 19 components on the reading lane, one summary on the BOSS, durable parsed answers (a re-run makes no
model call), a refusal asked once more then refused with a receipt, the four ledgers in the response, and the three
correction files with the host record path the recorder stages. Lanes are fakes; the classroom module and the
validators are real (tests/test_frankie_box_classroom.py builds the synthetic TEACH package)."""
import importlib.util
import json
import threading
import types
from pathlib import Path

import pytest

from test_frankie_box_classroom import COLUMNS, boss_component_answer, boss_summary_answer, build_visible, C

SESSION = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_boss_session.py'
spec = importlib.util.spec_from_file_location('frankie_box_boss_session_classroom_under_test', SESSION)
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class Refused(SystemExit):
    pass


def stub(tmp_path, visible, *, reader, boss):
    notes, calls = [], []
    s = types.SimpleNamespace(work=tmp_path / 'work', out=tmp_path / 'out', cycle='00', day='20211003', pod_id='podtest', serverless=None,
                              request=dict(request_id='run-cycle-00', attachment=dict(dipole_classroom=visible)), _notes=notes, _calls=calls,
                              _lock=threading.Lock(), _estimate_kind='byte estimate')
    s.work.mkdir(); s.out.mkdir()
    s.note = notes.append
    s.phase = lambda word, note=None: notes.append(f'phase {word}')
    s._input_tokens = lambda text: 1000
    def refuse(why):
        notes.append('REFUSED ' + why)
        raise Refused(why)
    s.refuse = refuse
    s._fan_out = lambda label, items, work: [work(item) for item in items]
    s._classroom_dir = lambda: session.Session._classroom_dir(s)
    s._classroom_call = lambda name, text, parse, lane: session.Session._classroom_call(s, name, text, parse, lane)
    s.classroom_ledgers = lambda: session.Session.classroom_ledgers(s)
    def rd(name, text):
        calls.append(('reader', name)); return reader(name, text)
    def bs(name, text):
        calls.append(('boss', name)); return boss(name, text)
    s.reader, s.boss = rd, bs
    return s


def good_reader(visible):
    by_name = {c['name']: c for c in C.components(visible)}
    def reader(name, text):
        cname = name.split('-', 2)[2].removesuffix('-retry')
        comp = by_name[cname]
        rights = [p['right'] for p in C.pairs_of(visible, cname)]
        return dict(text=boss_component_answer(comp, rights), incomplete=False, job_id='job-' + name)
    return reader


def good_boss(name, text):
    return dict(text=boss_summary_answer(), incomplete=False, job_id='job-' + name)


def test_classroom_stage_fans_out_assembles_and_is_resumable(tmp_path):
    visible = build_visible()
    s = stub(tmp_path, visible, reader=good_reader(visible), boss=good_boss)
    ledgers = session.Session.classroom(s)
    assert set(ledgers) == set(session.CLASSROOM_KEYS) and len(ledgers['dipole_relationship_scan']) == 171
    names = [n for lane, n in s._calls if lane == 'reader']
    assert names == [f'classroom-{i:02d}-{c}' for i, c in enumerate(COLUMNS)] and [n for lane, n in s._calls if lane == 'boss'] == ['classroom-summary']
    d = s.work / 'classroom'
    assert (d / 'ledgers.json').exists() and (d / 'summary.json').exists() and (d / 'classroom.md').exists()
    receipt = json.loads((d / 'receipt.json').read_text())
    assert receipt['report']['components'] == 19 and receipt['report']['consistent'] is True and len(receipt['calls']) == 20 and 'transcribed' in receipt['composition']
    assert sorted(p.name for p in d.glob('component-*.json'))[0] == f'component-00-{COLUMNS[0]}.json'
    before = len(s._calls)
    again = session.Session.classroom(s)
    assert again == ledgers and len(s._calls) == before and s._notes[-1] == 'classroom: ledgers already assembled; nothing to do'
    assert s.classroom_ledgers() == ledgers


def test_a_partial_run_resumes_from_the_durable_answers(tmp_path):
    visible = build_visible()
    reader = good_reader(visible)
    s = stub(tmp_path, visible, reader=reader, boss=good_boss)
    session.Session.classroom(s)
    (s.work / 'classroom' / 'ledgers.json').unlink(); (s.work / 'classroom' / 'summary.json').unlink()
    (s.work / 'classroom' / f'component-04-{COLUMNS[4]}.json').unlink()
    before = len(s._calls)
    session.Session.classroom(s)
    assert [n for lane, n in s._calls[before:]] == [f'classroom-04-{COLUMNS[4]}', 'classroom-summary']


def test_an_unusable_answer_is_asked_once_more_then_refused_with_nothing_filed(tmp_path):
    visible = build_visible()
    reader = good_reader(visible)
    def flaky(name, text):
        if name.startswith(f'classroom-02-{COLUMNS[2]}'):
            return dict(text='I cannot complete this request.', incomplete=False, job_id='j')
        return reader(name, text)
    s = stub(tmp_path, visible, reader=flaky, boss=good_boss)
    with pytest.raises(Refused, match='unusable twice'):
        session.Session.classroom(s)
    names = [n for lane, n in s._calls]
    assert names[2:4] == [f'classroom-02-{COLUMNS[2]}', f'classroom-02-{COLUMNS[2]}-retry']
    assert not (s.work / 'classroom' / 'ledgers.json').exists() and any('asking once more' in n for n in s._notes)


def test_an_incomplete_answer_whose_json_parses_is_kept_and_noted(tmp_path):
    visible = build_visible()
    reader = good_reader(visible)
    def cut(name, text):
        o = reader(name, text); o['incomplete'] = True; return o
    s = stub(tmp_path, visible, reader=cut, boss=good_boss)
    session.Session.classroom(s)
    assert sum('output incomplete but the JSON parsed whole' in n for n in s._notes) == 19


def test_a_prompt_over_the_part_budget_is_refused_before_any_call(tmp_path):
    visible = build_visible()
    s = stub(tmp_path, visible, reader=good_reader(visible), boss=good_boss)
    s._input_tokens = lambda text: session.PART_INPUT_TOKENS + 1
    with pytest.raises(Refused, match='part budget'):
        session.Session.classroom(s)
    assert s._calls == []


def test_classroom_ledgers_refuses_without_the_stage(tmp_path):
    s = stub(tmp_path, build_visible(), reader=None, boss=None)
    with pytest.raises(Refused, match='classroom stage must complete first'):
        s.classroom_ledgers()


def correction_request(response):
    return dict(schema=session.CORRECTION_REQUEST_SCHEMA, original_request_sha256='9' * 64, session_id=response['session_id'],
                model_identity_as_reported_by_session=response['model_identity_as_reported_by_session'], post_grade_hash='7' * 64,
                correction_ids=['relationship:%s:%s' % (COLUMNS[0], COLUMNS[1])],
                data_review_items=[dict(correction_id='relationship:%s:%s' % (COLUMNS[0], COLUMNS[1]), kind='RELATIONSHIP_DATA_REVIEW', left=COLUMNS[0], right=COLUMNS[1],
                                        frankie_said='SAME_DIRECTION', data_shows='OPPOSITE_DIRECTION', message='the data is showing OPPOSITE_DIRECTION instead')],
                root_cause_groups=[], novelty_investigation=dict(findings=[], finding_count=0), instruction='Resolve every correction_id in your own words.',
                request_sha256='5' * 64)


def test_correction_stage_writes_the_three_files_bound_to_the_request(tmp_path, monkeypatch):
    visible = build_visible()
    s = stub(tmp_path, visible, reader=good_reader(visible), boss=good_boss)
    ledgers = session.Session.classroom(s)
    response = dict(session_id='boss:frankie-box:test:cycle-00', model_identity_as_reported_by_session='granite42-smoke (test)', request_sha256='9' * 64, **ledgers)
    (s.out / 'response.json').write_text(json.dumps(response))
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    (tmp_path / 'request').mkdir()
    correction = correction_request(response)
    (tmp_path / 'request' / 'classroom-correction-request.json').write_text(json.dumps(correction))
    ack_text = json.dumps(dict(what_i_will_change='read the pair as the data shows it', remaining_disagreements=[],
                               correction_resolutions=[dict(correction_id=correction['correction_ids'][0], corrected_understanding='the directions are opposite in this window')]))
    def boss(name, text):
        assert name == 'classroom-correction' and correction['instruction'] in text
        return dict(text=ack_text, incomplete=False, job_id='job-c')
    s.boss = boss
    reply = session.Session.correction(s)
    filed = json.loads((s.out / 'correction-response.json').read_text())
    assert filed == json.loads(json.dumps(reply)) and filed['request_sha256'] == '5' * 64 and filed['session_id'] == response['session_id']
    assert filed['dipole_acknowledgement']['correction_resolutions'][0]['corrected_understanding'] == 'the directions are opposite in this window'
    record = json.loads((s.out / 'host-correction-record.json').read_text())
    attestation = json.loads((s.out / 'host-correction-attestation.json').read_text())
    assert record['request_sha256'] == attestation['request_sha256'] == C.adapter_digest(correction)
    assert record['response_sha256'] == attestation['response_sha256'] == C.adapter_digest(filed) and record['host_authority']
    assert attestation['host_record']['path'] == session.HOST_CORRECTION_RECORD_PATH.format(cycle='00') and attestation['host_record']['path'].endswith('/principal/host-correction-record.json')
    raw = (s.out / 'host-correction-record.json').read_bytes()
    assert attestation['host_record']['bytes'] == len(raw) and attestation['host_record']['sha256'] == session.sha256_bytes(raw)
    receipt = json.loads((s.work / 'classroom' / 'correction-receipt.json').read_text())
    assert receipt['correction_ids'] == 1 and receipt['resolutions'] == 1 and receipt['remaining_disagreements'] == []
    s.boss = lambda name, text: (_ for _ in ()).throw(AssertionError('no second call'))
    assert session.Session.correction(s) == reply


def test_correction_refuses_a_request_for_another_session(tmp_path, monkeypatch):
    visible = build_visible()
    s = stub(tmp_path, visible, reader=good_reader(visible), boss=good_boss)
    ledgers = session.Session.classroom(s)
    response = dict(session_id='boss:frankie-box:test:cycle-00', model_identity_as_reported_by_session='granite42-smoke (test)', **ledgers)
    (s.out / 'response.json').write_text(json.dumps(response))
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    (tmp_path / 'request').mkdir()
    other = correction_request(dict(response, session_id='someone-else'))
    (tmp_path / 'request' / 'classroom-correction-request.json').write_text(json.dumps(other))
    with pytest.raises(Refused, match='different session_id'):
        session.Session.correction(s)
