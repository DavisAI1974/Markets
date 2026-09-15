"""Exact context serving through synthetic HTTP; no provider/model calls."""
import asyncio
import base64
from email.message import Message
from dataclasses import replace
import hashlib
import json
import threading

import pytest

from research.kalshi.frankie_boss import granite_runpod_service as service
from research.kalshi.frankie_boss.granite_context import parse_native_context
from granite_context import map_native_context
from research.kalshi.frankie_boss.granite_context_route import context_route
from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity
from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION
from test_granite_context import case
from test_granite_parser import valid_output

KEY = 'private_test_credential_' + 'x' * 32


@pytest.fixture(scope='module')
def source(tmp_path_factory):
    raw = map_native_context(**case(tmp_path_factory.mktemp('runpod-context')))
    return parse_native_context(raw.text, expected_hash=raw.hash)


def service_pins(encoding='native_v1', timeout=1):
    startup = {'schema': 'GRANITE_STARTUP_RUNTIME_V1',
               'mount': {'manifest_sha256': 'a' * 64},
               'environment': {'GRANITE_MAX_MODEL_LEN': '4096', 'GRANITE_SERVED_MODEL': 'granite42-smoke'},
               'runtime': {'packages': {'transformers': '5.8.0', 'tokenizers': '0.22.2'}}}
    runtime = {'outcome': 'service_ready', 'pod_id': 'test123', 'model': 'granite42-smoke',
               'runtime': {'startup': {'startup': startup}}}
    route = context_route(encoding)
    identity = GraniteIdentity('a' * 64, None, 'b' * 64, 'none', service._json(startup),
        False, 0, 1200, hashlib.sha256(route.system_text.encode()).hexdigest(),
        SCHEMA_VERSION, route.parser_code_hash(), None)
    config = service.RunpodConfig('test123', 'granite42-smoke', timeout,
                                 hashlib.sha256(service._json(runtime).encode()).hexdigest())
    return config, identity, runtime


def admit(body):
    return dict(request_sha256=hashlib.sha256(body).hexdigest(), input_tokens=100,
                output_tokens=json.loads(body)['max_tokens'], context=4096,
                tokenizer_sha256='b' * 64)


def response(snapshot):
    content = valid_output(snapshot)
    content['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
    return service._json({'object': 'chat.completion', 'model': 'granite42-smoke',
        'choices': [{'index': 0, 'finish_reason': 'stop',
                     'message': {'role': 'assistant', 'content': json.dumps(content)}}]}).encode()


def build(exchange, *, encoding='native_v1', timeout=1, admission=admit, event=None):
    config, identity, runtime = service_pins(encoding, timeout)
    return service.build_runpod_service(enabled=True, config=config, identity=identity,
        runtime_receipt=runtime, api_key=KEY, admit_request=admission, exchange=exchange, event=event)


@pytest.mark.parametrize('encoding', ['native_v1', 'compact_v1'])
def test_exact_prompt_one_call_and_raw_provider_receipt(source, encoding):
    route = context_route(encoding)
    snapshot = route.encode(source)
    calls, events = [], []
    raw = response(snapshot)
    def exchange(pod_id, method, path, body, key, timeout):
        calls.append(body)
        assert (pod_id, method, path, key) == ('test123', 'POST', '/v1/chat/completions', KEY)
        assert 0 < timeout <= 1
        assert json.loads(body)['messages'] == [{'role': 'user', 'content': route.build_prompt(snapshot).text}]
        return 200, raw
    critic = build(exchange, encoding=encoding, event=events.append)
    result = asyncio.run(getattr(critic, route.method)(snapshot, request_id='exact'))
    assert result.shadow.status == 'accepted' and len(calls) == 1
    assert base64.b64decode(json.loads(result.provider_json)['body_base64']) == raw
    assert result.config_hash == critic.config_hash
    assert result.call_hash == hashlib.sha256(service._json(dict(config_hash=result.config_hash,
        request_hash=result.shadow.request.request_hash)).encode()).hexdigest()
    assert [event['phase'] for event in events] == ['request_admission', 'request_sent', 'response_received']
    assert KEY not in json.dumps(events) and route.build_prompt(snapshot).text not in json.dumps(events)


@pytest.mark.parametrize('mutation', ['hash', 'overflow', 'tokenizer', 'smoke'])
def test_per_request_admission_refuses_before_http(source, mutation):
    def admission(body):
        value = admit(body)
        if mutation == 'hash': value['request_sha256'] = 'f' * 64
        if mutation == 'overflow': value['input_tokens'] = 4096
        if mutation == 'tokenizer': value['tokenizer_sha256'] = 'c' * 64
        if mutation == 'smoke':
            value.update(schema='GRANITE_RUNPOD_TOKEN_ADMISSION_V1', input_tokens=19,
                         request_sha256=hashlib.sha256(b'Reply exactly READY.').hexdigest())
        return value
    critic = build(lambda *a: pytest.fail('unadmitted request'), admission=admission)
    result = asyncio.run(critic.critique_native(source, request_id='bad-admission'))
    assert result.shadow.status == 'transport_error'
    assert result.error_type == 'ValueError'


def test_runtime_context_and_receipt_binding_required():
    config, identity, runtime = service_pins()
    runtime['runtime']['startup']['startup']['environment']['GRANITE_MAX_MODEL_LEN'] = '8192'
    for pinned in [config, replace(config, runtime_sha256=service._hash(runtime))]:
        with pytest.raises(ValueError):
            service.build_runpod_service(enabled=True, config=pinned, identity=identity,
                runtime_receipt=runtime, api_key=KEY, admit_request=admit)


def test_timeout_keeps_capacity_until_underlying_call_ends(source):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def exchange(*args):
        calls.append(args)
        entered.set()
        release.wait(2)
        finished.set()
        return 200, response(source)
    critic = build(exchange, timeout=.03)
    async def scenario():
        first = await critic.critique_native(source, request_id='first')
        assert entered.is_set() and first.shadow.status == 'timeout'
        second = await critic.critique_native(source, request_id='second')
        assert second.shadow.status == 'transport_error' and second.error_type == 'Busy'
        assert len(calls) == 1
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        assert finished.wait(1)


@pytest.mark.parametrize('damage', ['model', 'length', 'oversized', 'status', 'credential'])
def test_provider_failures_preserve_bounded_raw_response_without_secrets(source, damage):
    value = json.loads(response(source))
    status = 503 if damage == 'status' else 200
    if damage == 'model': value['model'] = 'other'
    if damage == 'length': value['choices'][0]['finish_reason'] = 'length'
    if damage == 'credential': value['choices'][0]['message']['content'] = KEY
    raw = b'x' * (service.MAX_RESPONSE + 1) if damage == 'oversized' else service._json(value).encode()
    result = asyncio.run(build(lambda *a: (status, raw)).critique_native(source, request_id='bad-response'))
    assert result.shadow.status == 'transport_error'
    if damage in ('oversized', 'credential'):
        assert result.provider_json is None
    else:
        assert base64.b64decode(json.loads(result.provider_json)['body_base64']) == raw


def test_disabled_and_config_hash_never_depend_on_credentials():
    critic = service.build_runpod_service()
    assert not critic.enabled and critic.identity is None and critic.config_hash is None
    assert asyncio.run(critic.critique_native(None, request_id='disabled')) is None
    first = build(lambda *a: None)
    config, identity, runtime = service_pins()
    second = service.build_runpod_service(enabled=True, config=config, identity=identity,
        runtime_receipt=runtime, api_key='z' * 40, admit_request=admit)
    assert first.config_hash == second.config_hash
    assert KEY not in service._json(config.__dict__)


def test_prompt_capacity_failure_is_explicit_not_truncation(source):
    critic = build(lambda *a: pytest.fail('capacity failure must precede HTTP'))
    with pytest.raises(ValueError, match='capacity'):
        asyncio.run(critic.critique_native(source, request_id='too-large', max_prompt_bytes=1))


def test_slow_admission_never_sends_after_caller_timeout(source):
    release, complete = threading.Event(), threading.Event()
    events = []
    def admission(body):
        release.wait(2)
        return admit(body)
    def event(value):
        events.append(value)
        if value['phase'] == 'request_failed' and value['input_tokens'] is not None:
            complete.set()
    critic = build(lambda *a: pytest.fail('late admission must not send'), timeout=.03,
                   admission=admission, event=event)
    try:
        result = asyncio.run(critic.critique_native(source, request_id='slow-admission'))
        assert result.shadow.status == 'timeout' and result.error_type == 'TimeoutError'
        assert events[-1]['phase'] == 'request_failed'
    finally:
        release.set()
        assert complete.wait(1)
    assert not any(event['phase'] == 'request_sent' for event in events)


@pytest.mark.parametrize('damage', [None, 'oversized', 'chunked', 'duplicate_length', 'short'])
def test_default_https_transport_bounds_reads_and_keeps_large_exact_payload(monkeypatch, damage):
    sent, reads, closed = [], [], []
    headers = Message()
    raw = b'{"ok":true}'
    declared = service.MAX_RESPONSE + 1 if damage == 'oversized' else len(raw)
    headers['Content-Length'] = str(declared)
    headers['Content-Type'] = 'application/json'
    if damage == 'chunked': headers['Transfer-Encoding'] = 'chunked'
    if damage == 'duplicate_length': headers['Content-Length'] = str(declared)
    class Response:
        status = 200
        def __init__(self): self.headers = headers
        def getheader(self, name, default=None): return self.headers.get(name, default)
        def read(self, size):
            reads.append(size)
            return raw[:-1] if damage == 'short' else raw
    class Connection:
        sock = object()
        def __init__(self, host, port, **kwargs):
            assert (host, port) == ('test123-8081.proxy.runpod.net', 443)
        def connect(self): pass
        def request(self, method, path, body, headers): sent.append((method, path, body, headers))
        def getresponse(self): return Response()
        def close(self): closed.append(True)
    monkeypatch.setattr(service.http.client, 'HTTPSConnection', Connection)
    payload = b'p' * 10000  # Above the standalone smoke helper's 4096-byte limit.
    if damage is None:
        assert service.https_exchange('test123', 'POST', '/v1/chat/completions', payload, KEY, 5) == (200, raw)
    else:
        with pytest.raises(ValueError):
            service.https_exchange('test123', 'POST', '/v1/chat/completions', payload, KEY, 5)
    assert len(sent) == 1 and sent[0][2] == payload and closed == [True]
    assert reads == ([] if damage in ('oversized', 'chunked', 'duplicate_length') else [len(raw)])
