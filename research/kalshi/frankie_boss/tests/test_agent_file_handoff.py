"""Delivery uses durable evidence and does no new forecast or critic work."""
import asyncio
import hashlib
import json
import subprocess

import pytest

from test_frankie_controller import build_controller
from c15_journal import canonical_bytes, pack, unpack
from agent_file_handoff import export_handoff, _verify_sources as verify_sources


@pytest.fixture(autouse=True)
def isolated_source_edits(monkeypatch):
    # Unit tests run before the change is committed. Real checkout verification
    # has its own temporary-Git test and is exercised after the commit too.
    monkeypatch.setattr('agent_file_handoff._verify_sources', lambda repository: None)


def completed(tmp_path, **options):
    controller, bridge, critic, request = build_controller(tmp_path, **options)
    result = asyncio.run(controller.refresh(**request))
    args = dict(controller_path=tmp_path/'controller.sqlite',
                native_path=tmp_path/'forecasts.sqlite', request_id=request['request_id'],
                controller_checkpoint=controller.journal.checkpoint(),
                native_checkpoint=bridge.book.checkpoint(),
                boss_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                agent_commit='9'*40)
    return controller, bridge, critic, result, args


def test_exact_all_records_and_deterministic_export_without_calls(tmp_path, monkeypatch):
    controller, bridge, critic, result, args = completed(tmp_path)
    def forbidden(*a, **kw):
        raise AssertionError('export must not compute')
    monkeypatch.setattr(bridge, 'update', forbidden)
    monkeypatch.setattr(critic, 'critique_native', forbidden)
    manifest = export_handoff(tmp_path/'one', **args)
    assert manifest['status'] == 'complete'
    assert len(manifest['targets']) == len(result['records']) == 3
    assert manifest == export_handoff(tmp_path/'two', **args)
    for member in manifest['files']:
        data = (tmp_path/'one'/member['path']).read_bytes()
        assert data == (tmp_path/'two'/member['path']).read_bytes()
        assert member['bytes'] == len(data)
        assert member['sha256'] == hashlib.sha256(data).hexdigest()
    for target, record in zip(manifest['targets'], result['records']):
        assert (tmp_path/'one'/target['record_path']).read_bytes() == record['record_json'].encode()
        publication = bridge.book.publication(record['publication_hash'])
        assert (tmp_path/'one'/target['artifact_path']).read_bytes() == publication.selected.forecast_artifact
    state_bytes = (tmp_path/'one'/'state.c15.json').read_bytes()
    assert state_bytes == canonical_bytes(pack(controller.journal.state(args['request_id'])))
    assert unpack(json.loads(state_bytes))['result'] == result
    for name, journal in [('controller', controller.journal.journal), ('native', bridge.book.journal)]:
        assert (tmp_path/'one'/f'{name}.c15.jsonl').read_bytes() == b''.join(
            canonical_bytes(pack(entry)) + b'\n' for entry in journal.entries())
    assert critic.calls == 1


@pytest.mark.parametrize('field,value', [
    ('request_id','missing'), ('boss_commit','0'*40), ('agent_commit','bad'),
    ('controller_checkpoint',{'schema':'bad','count':0,'head_hash':'0'*64}),
    ('native_checkpoint',{'schema':'bad','count':0,'head_hash':'0'*64}),
])
def test_wrong_pins_refused_before_output(tmp_path, field, value):
    *_, args = completed(tmp_path)
    with pytest.raises(ValueError):
        export_handoff(tmp_path/'out', **{**args,field:value})
    assert not (tmp_path/'out').exists()


def test_existing_export_never_overwritten(tmp_path):
    *_, args = completed(tmp_path)
    export_handoff(tmp_path/'out', **args)
    original = (tmp_path/'out'/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        export_handoff(tmp_path/'out', **args)
    assert (tmp_path/'out'/'manifest.json').read_bytes() == original


def test_rejected_critic_stays_incomplete(tmp_path):
    *_, result, args = completed(tmp_path, verdict='INVALID')
    assert result['status'] == 'incomplete'
    assert export_handoff(tmp_path/'out', **args)['status'] == 'incomplete'


def test_physical_journal_tamper_rejected(tmp_path):
    import sqlite3
    *_, args = completed(tmp_path)
    with sqlite3.connect(args['controller_path']) as db:
        triggers = db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        for (name,) in triggers:
            db.execute('DROP TRIGGER "' + name.replace('"','""') + '"')
        db.execute("UPDATE entries SET body=? WHERE ordinal=0", (b'[]',))
    with pytest.raises(ValueError):
        export_handoff(tmp_path/'out', **args)
    assert not (tmp_path/'out').exists()


def test_later_controller_history_cannot_leak_into_earlier_export(tmp_path):
    controller, _, _, _, args = completed(tmp_path)
    state = controller.journal.state(args['request_id'])
    controller.journal.begin('later', state['intent'])
    args['controller_checkpoint'] = controller.journal.checkpoint()
    with pytest.raises(ValueError, match='end the controller checkpoint'):
        export_handoff(tmp_path/'out', **args)
    assert not (tmp_path/'out').exists()


def test_actual_git_source_identity_rejects_dirty_and_untracked(tmp_path):
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    module = tmp_path/'research'/'kalshi'/'frankie_boss'/'agent_file_handoff.py'
    module.parent.mkdir(parents=True)
    module.write_bytes(b'# committed\n')
    git('init')
    git('add', '.')
    git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
    verify_sources(tmp_path)
    module.write_bytes(b'# changed\n')
    with pytest.raises(ValueError, match='differs from committed'):
        verify_sources(tmp_path)
    module.write_bytes(b'# committed\n')
    (module.parent/'untracked.py').write_bytes(b'# untracked runtime\n')
    with pytest.raises(ValueError, match='differs from committed'):
        verify_sources(tmp_path)


def test_opaque_unselected_historical_artifact_cannot_be_exposed(tmp_path):
    from dataclasses import replace
    from rolling_forecast import ForecastTarget
    controller, bridge, _, request = build_controller(tmp_path)
    result = asyncio.run(controller.refresh(**request))
    selected = bridge.book.publication(result['records'][0]['publication_hash']).selected
    invalid = replace(selected, candidate_id='f'*64, target=ForecastTarget('OTHER','opaque',99999),
                      forecast_artifact=b'UNVALIDATED HISTORICAL ARTIFACT WITH LATER OBSERVATIONS')
    bridge.book.publish((invalid,))
    request['request_id'] = 'refresh/2'
    assert asyncio.run(controller.refresh(**request))['status'] == 'complete'
    with pytest.raises(ValueError):
        export_handoff(tmp_path/'out', controller_path=tmp_path/'controller.sqlite',
            native_path=tmp_path/'forecasts.sqlite', request_id='refresh/2',
            controller_checkpoint=controller.journal.checkpoint(), native_checkpoint=bridge.book.checkpoint(),
            boss_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), agent_commit='9'*40)
    assert not (tmp_path/'out').exists()
