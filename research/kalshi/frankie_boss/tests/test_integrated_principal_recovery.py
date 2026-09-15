"""New Claude coordinator / real adapter durable-outbox recovery seam.

Receiver preparation and controller export are isolated by the existing fixture;
execute/recover and the on-disk session request use the actual adapter methods.
No agent, model provider, or receiver calculation is invoked.
"""
import asyncio

import pytest

from research.kalshi.frankie_boss.frankie_principal_adapter import (
    FrankiePrincipalAdapter, PrincipalPending,
)
from test_feedback_cycle import fixture


def test_actual_adapter_recovers_pre_request_gap_then_preserves_pending_outbox(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    principal = FrankiePrincipalAdapter.__new__(FrankiePrincipalAdapter)
    principal.directory = tmp_path / 'actual-adapter-outbox'
    principal.directory.mkdir()
    principal.session_executor = None
    attachment = {'test_prepared_attachment': True}
    principal.prepare = lambda directory: attachment
    principal._request = lambda request_id, value: dict(request_id=request_id, attachment=value)
    execute = principal.execute

    def interrupted_before_request(*unused):
        raise RuntimeError('interrupted before adapter request')

    principal.execute = interrupted_before_request
    args['principal'] = principal
    try:
        with pytest.raises(RuntimeError, match='before adapter request'):
            asyncio.run(store.run(**args))
        assert store._load('sun', 'principal_intent') is not None
        request_path = principal.directory / 'session-request.json'
        assert not request_path.exists()

        # Actual recover raises the actual package's PrincipalNotDispatched;
        # the integrated coordinator dispatches once and the real adapter saves it.
        principal.execute = execute
        with pytest.raises(PrincipalPending, match='consume'):
            asyncio.run(store.run(**args))
        original = request_path.read_bytes()
        stat = request_path.stat()

        principal.execute = lambda *unused: pytest.fail('pending request dispatched twice')
        with pytest.raises(PrincipalPending, match='without a response'):
            asyncio.run(store.run(**args))
        assert request_path.read_bytes() == original
        assert request_path.stat().st_mtime_ns == stat.st_mtime_ns
        assert store._load('sun', 'principal_output') is None
        assert calls['controller'] == 1 and calls['learner'] == 0
        assert checkpoint.training_cursor == -1
    finally:
        store.close()
        checkpoint.close()
