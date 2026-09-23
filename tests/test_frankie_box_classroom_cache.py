"""Changed teaching and interrupted publication, with real classroom validation."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
import test_frankie_box_classroom as F
from test_frankie_box_boss_session_classroom import Refused, session, stub

def visible(revision):
    package = copy.deepcopy(F.build_package())
    message = package['pre_message']
    message['teacher_opening'] += '\nREVISION_' + revision
    message.pop('teacher_message_hash')
    message['teacher_message_hash'] = F.evidence_hash(message)
    binding = package['binding']
    binding['teacher_message_hash'] = message['teacher_message_hash']
    binding.pop('classroom_binding_hash')
    binding['classroom_binding_hash'] = F.evidence_hash(binding)
    return F.build_visible(package)

def reader(name, prompt):
    revision = 'B' if 'REVISION_B' in prompt else 'A'
    comp = F.C.component(visible(revision), name.split('-', 2)[2].removesuffix('-retry'))
    rights = [p['right'] for p in F.C.pairs_of(visible(revision), comp['name'])]
    answer = json.loads(F.boss_component_answer(comp, rights))
    answer['explanation'] = 'REVISION_' + revision
    return dict(text=json.dumps(answer), incomplete=False, job_id=name)

def boss(name, prompt):
    answer = json.loads(F.boss_summary_answer())
    answer['cycle_summary'] = 'REVISION_B' if 'REVISION_B' in prompt else 'REVISION_A'
    return dict(text=json.dumps(answer), incomplete=False, job_id=name)

class Active(session.Session):
    def __init__(self, directory):
        self.__dict__.update(stub(directory, visible('A'), reader=reader, boss=boss).__dict__)
        for name in ('_classroom_dir', '_classroom_call', 'classroom_ledgers'):
            self.__dict__.pop(name, None)
        self.dir = directory
        self.served_model = 'synthetic-test'
        self.request_sha256 = F.C.adapter_digest(self.request)

def current(active, value, revision):
    F.C.validate(active.request['attachment']['dipole_classroom'], value)
    teach = value['dipole_teachback']
    assert teach['teacher_message_hash'] == active.request['attachment']['dipole_classroom']['pre_message']['teacher_message_hash']
    assert teach['cycle_summary'] == 'REVISION_' + revision
    assert all(c['explanation'] == 'REVISION_' + revision for c in teach['components'])

def contents(root):
    return {hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

@pytest.mark.parametrize('partial', [False, True])
def test_changed_teaching_never_relabels_old_model_narratives(tmp_path, partial):
    active = Active(tmp_path)
    active.classroom()
    if partial:
        saved = active.work / 'retained-fixture'
        saved.mkdir()
        for name in ('ledgers.json', 'classroom.md', 'receipt.json'):
            (active.work / 'classroom' / name).rename(saved / name)
    before = contents(active.work)
    active.request['attachment']['dipole_classroom'] = visible('B')
    active.request_sha256 = F.C.adapter_digest(active.request)
    try:
        result = active.classroom()
    except Refused:
        assert before <= contents(active.work)
        return
    current(active, result, 'B')
    assert before <= contents(active.work)

def test_full_stage_driver_validates_existing_classroom(tmp_path):
    active = Active(tmp_path)
    active.classroom()
    active.request['attachment']['dipole_classroom'] = visible('B')
    active.request_sha256 = F.C.adapter_digest(active.request)
    for name in ('verify', '_pin_matches_request', 'brain_ready', 'labels', 'engine_reach', 'compare',
                 'serverless_reach', 'teach', 'receipts', 'push'):
        setattr(active, name, lambda: None)
    active._derive_needed = lambda: (False, 'test')
    active._corpus_current = lambda: True
    active._writing_inputs = lambda: {}
    published = []
    active.writing = lambda: published.append(active.classroom_ledgers())
    try:
        active._run('run')
    except Refused:
        assert not published
        return
    assert len(published) == 1
    current(active, published[0], 'B')

@pytest.mark.parametrize('boundary', ['ledgers.json', 'receipt.json'])
def test_interrupted_publication_recovers_without_model_calls(tmp_path, monkeypatch, boundary):
    active = Active(tmp_path)
    original = session.write_json
    def interrupt(path, value):
        if Path(path).name == boundary:
            if boundary == 'ledgers.json':
                original(path, value)
            raise RuntimeError('publication interruption')
        return original(path, value)
    with monkeypatch.context() as patch:
        patch.setattr(session, 'write_json', interrupt)
        with pytest.raises(RuntimeError, match='publication interruption'):
            active.classroom()
    calls = list(active._calls)
    result = active.classroom()
    current(active, result, 'A')
    assert active._calls == calls
    directory = active.work / 'classroom'
    assert (directory / 'classroom.md').is_file()
    receipt = json.loads((directory / 'receipt.json').read_bytes())
    assert receipt['ledgers'] == session.witness(directory / 'ledgers.json')
    assert receipt['report']['consistent'] is True
    assert active.classroom_ledgers() == result
