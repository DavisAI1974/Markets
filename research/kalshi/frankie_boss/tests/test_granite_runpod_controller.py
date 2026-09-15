"""Real native/controller journals with synthetic source and fake Runpod HTTP."""
import asyncio
import base64
import json

import pytest

from research.kalshi.frankie_boss import granite_runpod_controller as assembly
from research.kalshi.frankie_boss import granite_runpod_service as service
from research.kalshi.frankie_boss.controller_journal import ControllerJournal
from research.kalshi.frankie_boss.frankie_controller import FrankieForecastController, native_model_pin
from research.kalshi.frankie_boss.granite_context import ContextReceipt, map_native_context
from research.kalshi.frankie_boss.granite_context_route import context_route
from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.rolling_forecast import RollingForecastBook
from research.kalshi.frankie_boss.granite_live_controller import prepare_fixture
from test_granite_runpod_service import service_pins, admit, response, KEY


def inputs(tmp_path, encoding='native_v1'):
    fixture = prepare_fixture(tmp_path/'synthetic')
    bridge = fixture.bridge
    journal = ControllerJournal(tmp_path/'controller.sqlite', create=True)
    config, identity, runtime = service_pins(encoding)
    arguments = dict(enabled=True, bridge=bridge, journal=journal,
        config=config, identity=identity, runtime_receipt=runtime, api_key=KEY,
        admit_request=admit, expected_native_hash=native_model_pin(bridge),
        expected_critic_config_hash=config.config_hash,
        expected_critic_identity_hash=identity.identity_hash, context_encoding=encoding)
    request = dict(fixture.request, request_id='training-context/1')
    return arguments, request


def original_context(bridge, encoding):
    runner = bridge.context
    tokens, info, input_hash, _, _ = runner._prepare(2, 0)
    receipt = ContextReceipt(**info, input_hash=input_hash, model_hash=runner._model_hash())
    full = map_native_context(tokens=tokens, receipt=receipt, entity=runner.entity,
        registry=runner.model.trunk.registry, expected_input_hash=input_hash,
        expected_packet_hash=evidence_hash(info), source_as_of=1)
    route = context_route(encoding)
    return full, route.encode(full)


@pytest.mark.parametrize('encoding', ['native_v1', 'compact_v1'])
def test_real_controller_exact_full_context_and_durable_replay(tmp_path, monkeypatch, encoding):
    arguments, request = inputs(tmp_path, encoding)
    bridge, journal = arguments['bridge'], arguments['journal']
    full, snapshot = original_context(bridge, encoding)
    route = context_route(encoding)
    expected_prompt = route.build_prompt(snapshot).text
    calls, forwards, critic_events, controller_events = [], [], [], []
    original = bridge.context.model.forward_decision
    def forward(**kwargs):
        forwards.append(1)
        return original(**kwargs)
    monkeypatch.setattr(bridge.context.model, 'forward_decision', forward)
    raw = response(snapshot)
    def exchange(pod, method, path, body, key, timeout):
        calls.append(body)
        assert (pod, method, path, key) == ('test123', 'POST', '/v1/chat/completions', KEY)
        assert json.loads(body)['messages'] == [{'role': 'user', 'content': expected_prompt}]
        return 200, raw
    arguments.update(exchange=exchange, event=critic_events.append, controller_event=controller_events.append)
    controller = assembly.build_runpod_controller(**arguments)
    assert type(controller) is FrankieForecastController
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'complete' and len(result['records']) == len(forwards) == 3
    assert len(calls) == 1
    receipt = result['critic']['receipt']
    assert receipt['shadow']['request']['snapshot_text'] == snapshot.text
    assert route.native(snapshot).text == full.text
    assert base64.b64decode(json.loads(receipt['provider_json'])['body_base64']) == raw
    assert journal.state(request['request_id'])['result'] == result
    state = journal.state(request['request_id'])
    assert state['native'] is not None and state['critic_intent']['prompt_text'] == expected_prompt
    for record in result['records']:
        assert bridge.book.publication(record['publication_hash']).revision == 1
        assert json.loads(record['record_json'])['payload']['confidence'] is None
    assert asyncio.run(controller.refresh(**request)) == result
    assert len(calls) == 1 and len(forwards) == 3
    checkpoint, native_checkpoint = journal.checkpoint(), bridge.book.checkpoint()
    journal.close()
    bridge.book.close()
    bridge.book = RollingForecastBook(tmp_path/'synthetic'/'forecasts.sqlite', checkpoint=native_checkpoint)
    restored_journal = ControllerJournal(tmp_path/'controller.sqlite', checkpoint=checkpoint)
    arguments['journal'] = restored_journal
    restored = assembly.build_runpod_controller(**arguments)
    assert asyncio.run(restored.refresh(**request)) == result
    assert len(calls) == 1 and len(forwards) == 3
    assert [e['phase'] for e in critic_events] == ['request_admission', 'request_sent', 'response_received']
    assert controller_events
    restored_journal.close()
    bridge.book.close()
    bridge.context.builder.journal.close()


def test_failed_critic_preserves_durable_native_forecasts(tmp_path):
    arguments, request = inputs(tmp_path)
    calls = []
    def exchange(*args):
        calls.append(args)
        return 503, b'{"error":"synthetic unavailable"}'
    controller = assembly.build_runpod_controller(**arguments, exchange=exchange)
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'incomplete' and len(result['records']) == 3
    assert result['critic']['receipt']['shadow']['status'] == 'transport_error'
    assert controller.journal.state(request['request_id'])['result'] == result
    assert all(arguments['bridge'].book.publication(row['publication_hash']).revision == 1
               for row in result['records'])
    assert asyncio.run(controller.refresh(**request)) == result and len(calls) == 1
    controller.journal.close()
    arguments['bridge'].book.close()
    arguments['bridge'].context.builder.journal.close()


@pytest.mark.parametrize('pin', ['expected_native_hash', 'expected_critic_config_hash', 'expected_critic_identity_hash'])
def test_independent_pins_refused_before_native_or_http_work(tmp_path, monkeypatch, pin):
    arguments, _ = inputs(tmp_path)
    arguments[pin] = 'f' * 64
    def forbidden(*args, **kwargs):
        pytest.fail('assembly must not invoke model or HTTP')
    monkeypatch.setattr(arguments['bridge'].context.model, 'forward_decision', forbidden)
    with pytest.raises(ValueError):
        assembly.build_runpod_controller(**arguments, exchange=forbidden)
    assert arguments['journal'].checkpoint()['count'] == 0
    assert arguments['bridge'].book.checkpoint()['count'] == 0
    arguments['journal'].close()
    arguments['bridge'].book.close()
    arguments['bridge'].context.builder.journal.close()


def test_default_disabled_preserves_legacy_without_service_construction(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('disabled assembly must not construct Runpod service')
    monkeypatch.setattr(service, 'build_runpod_service', forbidden)
    sentinel = object()
    controller = assembly.build_runpod_controller(legacy=lambda: sentinel,
        config=object(), runtime_receipt=object(), admit_request=forbidden,
        api_key=object(), exchange=forbidden)
    assert type(controller) is FrankieForecastController and not controller.enabled
    assert asyncio.run(controller.refresh()) is sentinel


def test_enable_flag_is_explicit_boolean():
    with pytest.raises(ValueError):
        assembly.build_runpod_controller(enabled=1)


def test_critic_diagnostic_failure_resumes_without_false_unknown_attempt(tmp_path, monkeypatch):
    arguments, request = inputs(tmp_path)
    bridge, journal = arguments['bridge'], arguments['journal']
    _, snapshot = original_context(bridge, 'native_v1')
    calls, forwards, event_failures = [], [], []
    original = bridge.context.model.forward_decision
    def forward(**kwargs):
        forwards.append(1)
        return original(**kwargs)
    monkeypatch.setattr(bridge.context.model, 'forward_decision', forward)
    def event(value):
        if value['phase'] == 'critic_request' and not event_failures:
            event_failures.append(1)
            raise OSError('synthetic diagnostic write failure')
    def exchange(*args):
        calls.append(args)
        return 200, response(snapshot)
    controller = assembly.build_runpod_controller(**arguments, exchange=exchange, controller_event=event)
    try:
        with pytest.raises(OSError, match='diagnostic write failure'):
            asyncio.run(controller.refresh(**request))
        state = journal.state(request['request_id'])
        assert len(state['native']['publications']) == 3
        assert state['critic_intent'] is None and state['critic_result'] is None
        assert state['result'] is None and not calls and len(forwards) == 3
        result = asyncio.run(controller.refresh(**request))
        assert result['status'] == 'complete' and len(result['records']) == 3
        assert len(calls) == 1 and len(forwards) == 3 and len(event_failures) == 1
    finally:
        journal.close()
        bridge.book.close()
        bridge.context.builder.journal.close()
