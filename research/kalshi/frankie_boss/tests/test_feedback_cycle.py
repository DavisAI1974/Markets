"""New coordinator interruption seams, no remote calls or historical smoke tests."""
import asyncio
from pathlib import Path

import pytest
import torch

from research.kalshi.frankie_boss import feedback_cycle as cycle
from research.kalshi.frankie_boss.boss_training_checkpoint import BossTrainingCheckpoint
from research.kalshi.frankie_boss.native_forecast_learning import FrankieFeedback


def fixture(tmp_path, monkeypatch):
    memory = tmp_path/'memory-a'
    memory.write_bytes(b'frozen')
    store = cycle.CycleCoordinator(tmp_path/'cycle.sqlite', lessons_path=tmp_path/'lessons.sqlite',
        frozen_memory_path=memory, frozen_memory_sha256=cycle.file_hash(memory), create=True)
    native, decoder = torch.nn.Linear(1, 1), torch.nn.Linear(1, 1)
    optimizer = torch.optim.SGD(list(native.parameters())+list(decoder.parameters()), lr=.1)
    checkpoint = BossTrainingCheckpoint(tmp_path/'training.sqlite',
        models={'native': native, 'decoder': decoder}, optimizer=optimizer,
        identities=dict(training_config_hash='a'*64, code_hash='b'*64, source_hash='c'*64, model_hash='d'*64), create=True)
    calls = dict(controller=0, principal=0, learner=0, recover=0)
    result = dict(request_id='sun', request_hash='e'*64, status='complete', records=())
    class Controller:
        async def refresh(self, **kwargs):
            calls['controller'] += 1
            return result
    feedback = FrankieFeedback('sun', 'f'*64, 'c'*64, 20, 'a'*64, ())
    envelope = dict(lessons=[dict(text='principal lesson')])
    class Principal:
        def prepare(self, directory): return dict(attachment='verified')
        def execute(self, request_id, attachment):
            calls['principal'] += 1
            return envelope
        def recover(self, request_id, attachment):
            calls['recover'] += 1
            return None
        def verify(self, envelope, **kwargs): return feedback
    class Learner:
        def step(self, **kwargs):
            calls['learner'] += 1
            optimizer.zero_grad()
            native(torch.ones(1, 1)).sum().backward()
            optimizer.step()
            return dict(updated=True, feedback_hash=feedback.digest)
    monkeypatch.setattr(cycle, '_export_verified', lambda *args, **kwargs: dict(
        request_hash='e'*64, status='complete', source=dict(prefix_hash='c'*64, through_cursor=2)))
    args = dict(request_id='sun', controller_factory=Controller, controller_kwargs={}, export_kwargs={},
        principal=Principal(), checkpoint=checkpoint, learner_factory=Learner,
        learning_kwargs=dict(as_of=10, through_cursor=2, source_hash='c'*64, input_hash='f'*64,
            sessions=(), expected_sessions_hash='1'*64, learning_cutoff_ns=20))
    return store, checkpoint, args, calls


def test_complete_replay_never_constructs_old_controller_or_learner(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    result = asyncio.run(store.run(**args))
    args['controller_factory'] = lambda: pytest.fail('old controller constructed')
    args['learner_factory'] = lambda: pytest.fail('completed learner constructed')
    assert asyncio.run(store.run(**args)) == result
    assert calls == dict(controller=1, principal=1, learner=1, recover=0)
    assert store.lessons_available(19) == []
    assert len(store.lessons_available(20)) == 1
    store.close(); checkpoint.close()


def test_verified_incomplete_controller_reaches_principal_without_retry(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    incomplete = dict(request_id='sun', request_hash='e'*64, status='incomplete', records=())
    class Controller:
        async def refresh(self, **kwargs):
            calls['controller'] += 1
            return incomplete
    args['controller_factory'] = Controller
    monkeypatch.setattr(cycle, '_export_verified', lambda *args, **kwargs: dict(
        request_hash='e'*64, status='incomplete', source=dict(prefix_hash='c'*64, through_cursor=2)))
    result = asyncio.run(store.run(**args))
    assert result['feedback_hash'] and calls['controller'] == calls['principal'] == calls['learner'] == 1
    store.close(); checkpoint.close()


def test_training_commit_without_cycle_receipt_recovers_without_forward(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    original = store._save
    def crash(request_id, stage, value):
        if stage == 'training': raise RuntimeError('crash after training commit')
        return original(request_id, stage, value)
    monkeypatch.setattr(store, '_save', crash)
    with pytest.raises(RuntimeError, match='crash'):
        asyncio.run(store.run(**args))
    pin, models, optimizer, identities = checkpoint.checkpoint_hash, checkpoint.models, checkpoint.optimizer, checkpoint.identities
    store.close(); checkpoint.close()
    store = cycle.CycleCoordinator(tmp_path/'cycle.sqlite', lessons_path=tmp_path/'lessons.sqlite',
        frozen_memory_path=tmp_path/'memory-a', frozen_memory_sha256=cycle.file_hash(tmp_path/'memory-a'))
    checkpoint = BossTrainingCheckpoint(tmp_path/'training.sqlite', models=models, optimizer=optimizer,
        identities=identities, expected_checkpoint_hash=pin)
    args['checkpoint'] = checkpoint
    args['controller_factory'] = lambda: pytest.fail('old controller constructed')
    args['learner_factory'] = lambda: pytest.fail('second forward')
    result = asyncio.run(store.run(**args))
    assert result['training']['checkpoint_hash'] == checkpoint.checkpoint_hash
    assert calls['learner'] == calls['principal'] == 1
    store.close(); checkpoint.close()


def test_ambiguous_principal_never_resubmits(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    def fail(*args):
        calls['principal'] += 1
        raise TimeoutError('lost response')
    args['principal'].execute = fail
    with pytest.raises(TimeoutError): asyncio.run(store.run(**args))
    with pytest.raises(cycle.AmbiguousPrincipalCall): asyncio.run(store.run(**args))
    assert calls['principal'] == 1 and calls['recover'] == 1 and calls['learner'] == 0
    store.close(); checkpoint.close()


def test_changed_learning_binding_refuses_completed_replay(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    asyncio.run(store.run(**args))
    args['learning_kwargs']['source_hash'] = '9'*64
    with pytest.raises(ValueError, match='identity changed'): asyncio.run(store.run(**args))
    store.close(); checkpoint.close()


def test_ambiguous_call_recovers_saved_output_without_execute(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    output = args['principal'].execute('sun', {})
    def lost(*unused): raise TimeoutError('after principal output persisted')
    args['principal'].execute = lost
    with pytest.raises(TimeoutError): asyncio.run(store.run(**args))
    args['principal'].recover = lambda *unused: output
    result = asyncio.run(store.run(**args))
    assert result['feedback_hash'] and calls['learner'] == 1
    store.close(); checkpoint.close()


def test_unattested_output_is_retained_but_never_trained(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    def reject(*unused, **kwargs): raise ValueError('principal attestation failed')
    args['principal'].verify = reject
    with pytest.raises(ValueError, match='attestation'): asyncio.run(store.run(**args))
    assert store._load('sun', 'principal_output') is not None
    assert store._load('sun', 'feedback') is None
    assert checkpoint.training_cursor == -1 and calls['learner'] == 0
    assert store.lessons_available(100) == []
    store.close(); checkpoint.close()


def test_diagnostic_failure_before_intent_never_claims_remote_call(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    def fail(phase, **kwargs):
        if phase == 'frankie_calculations': raise RuntimeError('diagnostic disk full')
    store.phase_callback = fail
    with pytest.raises(RuntimeError, match='diagnostic'): asyncio.run(store.run(**args))
    assert store._load('sun', 'principal_intent') is None
    assert calls['principal'] == 0
    store.close(); checkpoint.close()


def test_real_export_readback_binds_input_and_refuses_tamper(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(cycle.__file__).parent))
    from test_agent_file_handoff import completed
    from research.kalshi.frankie_boss import agent_file_handoff
    from research.kalshi.frankie_boss.forecast_artifact import NativeForecastArtifact
    monkeypatch.setattr(agent_file_handoff, '_verify_sources', lambda repository: None)
    controller, bridge, critic, result, export_args = completed(tmp_path)
    request = controller.journal.state(export_args['request_id'])['intent']['request']
    publication = bridge.book.publication(result['records'][0]['publication_hash'])
    artifact = NativeForecastArtifact.from_payload(publication.selected.forecast_artifact,
        expected_digest=publication.selected.candidate_id)
    learning = dict(as_of=request['as_of'], through_cursor=request['through_cursor'],
        source_hash=request['source_hash'], input_hash=artifact.input_hash)
    directory = tmp_path/'export'
    manifest = cycle._export_verified(directory, export_args, result, learning)
    assert len(manifest['targets']) == len(result['records'])
    member = directory/manifest['targets'][0]['artifact_path']
    member.write_bytes(member.read_bytes()+b'changed')
    with pytest.raises(ValueError, match='member bytes changed'):
        cycle._export_verified(directory, export_args, result, learning)
    assert critic.calls == 1
    controller.journal.close(); bridge.book.close()
