"""Regression evidence for review fixes H1, M5 and L1 on the cycle coordinator only.

No remote calls, no principal invocation, no training beyond the fixture's Linear(1,1).
H1 coordinates against the adapter exception contract: PrincipalPending (present) means a
durable session request exists without a response; PrincipalNotDispatched (being added by
Codex) means no durable request was ever written. Until that adapter change merges, a
narrow local double is installed under the agreed name and the coordinator resolves it
lazily, so the same tests bind to the real class once it exists.
"""
import asyncio
from dataclasses import dataclass

import pytest

from research.kalshi.frankie_boss import feedback_cycle as cycle
from research.kalshi.frankie_boss import frankie_principal_adapter as adapter
from research.kalshi.frankie_boss.boss_training_checkpoint import encode_state
from research.kalshi.frankie_boss.native_forecast_learning import FrankieFeedback, SessionFeedback
from test_feedback_cycle import fixture


class LocalNotDispatched(RuntimeError):
    """Local stand-in for adapter PrincipalNotDispatched: no durable session request exists."""


def not_dispatched(monkeypatch):
    signal = getattr(adapter, 'PrincipalNotDispatched', None)
    if signal is None:
        monkeypatch.setattr(adapter, 'PrincipalNotDispatched', LocalNotDispatched, raising=False)
        signal = LocalNotDispatched
    return signal


@dataclass(frozen=True)
class RequestedSession:
    session_id: str


def weights(checkpoint):
    return encode_state({role: model.state_dict() for role, model in checkpoint.models.items()})


def test_intent_without_durable_request_dispatches_exactly_once_on_recovery(tmp_path, monkeypatch):
    signal = not_dispatched(monkeypatch)
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    principal, execute = args['principal'], args['principal'].execute
    def crash_before_durable_request(request_id, attachment):
        raise RuntimeError('validation failed before session-request.json was written')
    principal.execute = crash_before_durable_request
    with pytest.raises(RuntimeError, match='before session-request'):
        asyncio.run(store.run(**args))
    assert store._load('sun', 'principal_intent') is not None
    assert calls['principal'] == 0
    def never_dispatched(request_id, attachment):
        calls['recover'] += 1
        raise signal('no durable session request exists')
    principal.recover = never_dispatched
    principal.execute = execute
    result = asyncio.run(store.run(**args))
    assert result['feedback_hash'] and calls == dict(controller=1, principal=1, learner=1, recover=1)
    store.close(); checkpoint.close()


def test_pending_outbox_propagates_without_redispatch(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    principal = args['principal']
    def outbox(request_id, attachment):
        calls['principal'] += 1
        raise adapter.PrincipalPending('authorized host session must consume the outbox')
    principal.execute = outbox
    with pytest.raises(adapter.PrincipalPending):
        asyncio.run(store.run(**args))
    def still_pending(request_id, attachment):
        calls['recover'] += 1
        raise adapter.PrincipalPending('existing principal intent has no completed response')
    principal.recover = still_pending
    principal.execute = lambda *unused: pytest.fail('pending outbox was resubmitted')
    with pytest.raises(adapter.PrincipalPending):
        asyncio.run(store.run(**args))
    assert calls == dict(controller=1, principal=1, learner=0, recover=1)
    assert store._load('sun', 'principal_output') is None
    store.close(); checkpoint.close()


def test_generic_recovery_failure_never_infers_safety_to_dispatch(tmp_path, monkeypatch):
    not_dispatched(monkeypatch)
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    principal = args['principal']
    def lost(*unused):
        calls['principal'] += 1
        raise TimeoutError('lost response after dispatch')
    principal.execute = lost
    with pytest.raises(TimeoutError):
        asyncio.run(store.run(**args))
    def unreadable(*unused):
        calls['recover'] += 1
        raise OSError('retained evidence unreadable')
    principal.recover = unreadable
    principal.execute = lambda *unused: pytest.fail('generic failure treated as not dispatched')
    with pytest.raises(OSError, match='unreadable'):
        asyncio.run(store.run(**args))
    assert calls['principal'] == 1 and calls['recover'] == 1 and calls['learner'] == 0
    store.close(); checkpoint.close()


def test_feedback_roster_mismatch_rejected_before_save_and_training(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    principal = args['principal']
    accepted = principal.verify(None)
    ghost = FrankieFeedback('sun', 'f'*64, 'c'*64, 20, 'a'*64,
        (SessionFeedback(session_id='ghost', timing=(), gap=None, path=()),))
    principal.verify = lambda envelope, **kwargs: ghost
    before = weights(checkpoint)
    with pytest.raises(ValueError, match='roster'):
        asyncio.run(store.run(**args))
    assert store._load('sun', 'principal_output') is not None
    assert store._load('sun', 'feedback') is None
    assert checkpoint.training_cursor == -1 and calls['learner'] == 0
    assert weights(checkpoint) == before and not checkpoint._failed
    principal.verify = lambda envelope, **kwargs: accepted
    principal.execute = lambda *unused: pytest.fail('retained principal output was re-executed')
    result = asyncio.run(store.run(**args))
    assert result['training']['checkpoint_hash'] == checkpoint.checkpoint_hash
    assert calls['learner'] == 1 and calls['principal'] == 1
    store.close(); checkpoint.close()


def test_feedback_roster_order_must_match_requested_sessions(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    args['learning_kwargs']['sessions'] = (('first', RequestedSession('s1')), ('second', RequestedSession('s2')))
    def labelled(*ids):
        return FrankieFeedback('sun', 'f'*64, 'c'*64, 20, 'a'*64,
            tuple(SessionFeedback(session_id=i, timing=(), gap=None, path=()) for i in ids))
    args['principal'].verify = lambda envelope, **kwargs: labelled('s2', 's1')
    with pytest.raises(ValueError, match='roster'):
        asyncio.run(store.run(**args))
    assert store._load('sun', 'feedback') is None and calls['learner'] == 0
    args['principal'].verify = lambda envelope, **kwargs: labelled('s1', 's2')
    assert asyncio.run(store.run(**args))['feedback_hash'] == labelled('s1', 's2').digest
    assert calls['learner'] == 1
    store.close(); checkpoint.close()


def test_conflicting_export_request_id_is_rejected_not_overwritten(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    args['export_kwargs'] = dict(request_id='other')
    with pytest.raises(ValueError, match='export request'):
        asyncio.run(store.run(**args))
    assert store._load('sun', 'export') is None and calls['principal'] == 0
    args['export_kwargs'] = dict(request_id='sun')
    assert asyncio.run(store.run(**args))['request_id'] == 'sun'
    assert calls['principal'] == 1
    store.close(); checkpoint.close()
