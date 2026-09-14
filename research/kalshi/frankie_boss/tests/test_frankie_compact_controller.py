"""Encoding changes the critic identity, never native forecasts or retry ownership."""
import asyncio
from dataclasses import replace
import hashlib
import json

import pytest

from controller_journal import ControllerJournal
from frankie_controller import FrankieForecastController, native_model_pin
from test_frankie_controller import Critic, build_controller
from research.kalshi.frankie_boss.granite_context_route import context_route, serve_compact_shadow


class CompactCritic(Critic):
    def __init__(self):
        super().__init__()
        route = context_route('compact_v1')
        self.identity = replace(self.identity,
            system_prompt_hash=hashlib.sha256(route.system_text.encode()).hexdigest(),
            parser_code_hash=route.parser_code_hash())

    async def critique_compact(self, snapshot, *, request_id):
        from research.kalshi.frankie_boss.granite_shadow import ShadowResponse
        from research.kalshi.frankie_boss.granite_bedrock import BedrockReceipt
        from test_granite_parser import valid_output
        self.calls += 1
        async def transport(request):
            value = valid_output(snapshot)
            value['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
            return ShadowResponse(request.request_hash, self.identity.identity_hash, json.dumps(value))
        shadow = await serve_compact_shadow(snapshot, self.identity, request_id=request_id,
            timeout_seconds=self.request_timeout, transport=transport)
        call_hash = hashlib.sha256(json.dumps(dict(config_hash=self.config_hash,
            request_hash=shadow.request.request_hash), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return BedrockReceipt(shadow, self.config_hash, call_hash, None, None)


def with_route(controller, critic, encoding):
    return FrankieForecastController(enabled=True, bridge=controller.bridge, journal=controller.journal,
        critic=critic, context_encoding=encoding, expected_native_hash=native_model_pin(controller.bridge),
        expected_critic_config_hash=critic.config_hash, expected_critic_identity_hash=critic.identity.identity_hash)


def build_compact(tmp_path):
    controller, bridge, _, request = build_controller(tmp_path)
    critic = CompactCritic()
    return with_route(controller, critic, 'compact_v1'), bridge, critic, request


def test_compact_forecasts_match_native_and_restore_without_calls(tmp_path, monkeypatch):
    from rolling_forecast import RollingForecastBook
    left = tmp_path/'native'; left.mkdir()
    right = tmp_path/'compact'; right.mkdir()
    native, _, _, req = build_controller(left)
    expected = asyncio.run(native.refresh(**req))
    controller, bridge, critic, request = build_compact(right)
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'complete'
    assert result['records'] == expected['records']
    state = controller.journal.state(request['request_id'])
    assert state['intent']['configuration']['context_encoding'] == 'compact_v1'
    assert state['critic_intent']['context_encoding'] == 'compact_v1'
    snapshot = context_route('compact_v1').parse(state['critic_intent']['snapshot_text'],
        expected_hash=state['critic_intent']['snapshot_hash'])
    assert snapshot.native().hash == state['critic_intent']['native_snapshot_hash']
    assert asyncio.run(controller.refresh(**request)) == result
    controller_pin, book_pin = controller.journal.checkpoint(), bridge.book.checkpoint()
    controller.journal.close(); bridge.book.close()
    bridge.book = RollingForecastBook(right/'forecasts.sqlite', checkpoint=book_pin)
    controller.journal = ControllerJournal(right/'controller.sqlite', checkpoint=controller_pin)
    restored = with_route(controller, critic, 'compact_v1')
    monkeypatch.setattr(bridge.context.model, 'forward_decision', lambda **kw: pytest.fail('repeated model call'))
    assert asyncio.run(restored.refresh(**request)) == result
    assert critic.calls == 1


@pytest.mark.parametrize('encoding', ['unknown', None, 'compact_v1'])
def test_unknown_encoding_or_native_identity_on_compact_route_rejects(tmp_path, encoding):
    controller, bridge, critic, request = build_controller(tmp_path)
    with pytest.raises(ValueError):
        changed = with_route(controller, critic, encoding)
        asyncio.run(changed.refresh(**request))
    assert critic.calls == 0 and bridge.book.checkpoint()['count'] == 0


def test_completed_request_cannot_switch_encoding(tmp_path):
    controller, bridge, critic, request = build_compact(tmp_path)
    asyncio.run(controller.refresh(**request))
    native = with_route(controller, Critic(), 'native_v1')
    with pytest.raises(ValueError, match='changed'):
        asyncio.run(native.refresh(**request))
    assert critic.calls == 1 and native.critic.calls == 0


@pytest.mark.parametrize('field', ['context_encoding', 'native_snapshot_hash', 'snapshot_text'])
def test_journal_rejects_altered_route_or_snapshot_even_with_new_hash_chain(tmp_path, field):
    from c15_journal import EvidenceJournal, pack, unpack
    import controller_journal
    controller, _, _, request = build_compact(tmp_path)
    asyncio.run(controller.refresh(**request))
    forged = EvidenceJournal(tmp_path/'forged.sqlite', create=True)
    for entry in controller.journal.journal.entries():
        event = unpack(pack(entry['payload']))
        if event['step'] == 'CRITIC_INTENT':
            event['payload'][field] = 'native_v1' if field == 'context_encoding' else 'f'*64
        forged.append(entry['kind'], event)
    checkpoint = dict(schema=controller_journal.SCHEMA, count=forged.count, head_hash=forged.head_hash)
    forged.close()
    with pytest.raises(ValueError): ControllerJournal(tmp_path/'forged.sqlite', checkpoint=checkpoint)


def test_old_journal_without_route_replays_native(tmp_path):
    from c15_journal import EvidenceJournal, pack, unpack, evidence_hash
    import controller_journal
    controller, _, _, request = build_controller(tmp_path)
    asyncio.run(controller.refresh(**request))
    forged = EvidenceJournal(tmp_path/'old-native.sqlite', create=True)
    request_hash = critic_intent_hash = critic_result = None
    for entry in controller.journal.journal.entries():
        event = unpack(pack(entry['payload']))
        payload = event['payload']
        if event['step'] == 'INTENT':
            del payload['configuration']['context_encoding']
            request_hash = evidence_hash(payload)
        event['request_hash'] = request_hash
        if event['step'] == 'CRITIC_INTENT':
            del payload['context_encoding']
            del payload['native_snapshot_hash']
            critic_intent_hash = evidence_hash(payload)
        if event['step'] == 'CRITIC_RESULT':
            payload['intent_hash'] = critic_intent_hash
            critic_result = payload
        if event['step'] == 'RESULT':
            payload['request_hash'] = request_hash
            payload['critic'] = critic_result
            payload['critic_hash'] = evidence_hash(critic_result)
        forged.append(entry['kind'], event)
    checkpoint = dict(schema=controller_journal.SCHEMA, count=forged.count, head_hash=forged.head_hash)
    forged.close()
    restored = ControllerJournal(tmp_path/'old-native.sqlite', checkpoint=checkpoint)
    assert restored.state(request['request_id'])['result']['status'] == 'complete'
    restored.close()


@pytest.mark.parametrize('encoding', ['native_v1', 'compact_v1'])
def test_valid_foreign_snapshot_rejected_at_intent_before_transport(tmp_path, monkeypatch, encoding):
    from test_granite_native_service import native_case
    controller, bridge, critic, request = (build_compact(tmp_path) if encoding == 'compact_v1'
        else build_controller(tmp_path))
    foreign_dir = tmp_path/'foreign'; foreign_dir.mkdir()
    foreign, _, _ = native_case(foreign_dir)
    route = context_route(encoding)
    encoded = route.encode(foreign)
    original = controller._snapshot
    def foreign_snapshot(*args, **kwargs):
        _, _, receipt, packet, _ = original(*args, **kwargs)
        return encoded, route.build_prompt(encoded), receipt, packet, foreign.hash
    monkeypatch.setattr(controller, '_snapshot', foreign_snapshot)
    with pytest.raises(ValueError, match='source intent'):
        asyncio.run(controller.refresh(**request))
    assert critic.calls == 0


def test_context_route_source_change_invalidates_completed_retry(tmp_path, monkeypatch):
    from pathlib import Path
    controller, _, critic, request = build_compact(tmp_path)
    asyncio.run(controller.refresh(**request))
    original = Path.read_bytes
    def changed(path):
        content = original(path)
        return content + b'\n# changed route\n' if path.name == 'granite_context_route.py' else content
    monkeypatch.setattr(Path, 'read_bytes', changed)
    with pytest.raises(ValueError, match='changed'):
        asyncio.run(controller.refresh(**request))
    assert critic.calls == 1


def test_compact_pending_attempt_requires_explicit_recovery(tmp_path, monkeypatch):
    controller, _, critic, request = build_compact(tmp_path)
    original = critic.critique_compact
    async def interrupted(*args, **kwargs): raise RuntimeError('unknown call')
    monkeypatch.setattr(critic, 'critique_compact', interrupted)
    with pytest.raises(RuntimeError): asyncio.run(controller.refresh(**request))
    monkeypatch.setattr(critic, 'critique_compact', original)
    with pytest.raises(ValueError, match='completion unknown'): asyncio.run(controller.refresh(**request))
    result = asyncio.run(controller.refresh(**request, recovery_attempt_id='compact-recovery/1'))
    assert result['status'] == 'complete' and critic.calls == 1
    assert controller.journal.state(request['request_id'])['attempts'][-1] == 'compact-recovery/1'
