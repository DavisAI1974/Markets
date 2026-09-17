"""Runpod service configuration and the config-free HTTPS transport; no provider/model calls.

The finite direct_v1 critic that this file once exercised (one bounded exchange under a request timeout) was the
4,096-token smoke transport and is retired: RunpodConfig admits no finite request_timeout. The live request paths and
their behaviours (exact prompt, admission before HTTP, bounded raw provider receipts, capacity refusal, one dispatch)
are covered by test_granite_open_ended_service.py and test_granite_durable_job_client.py.
"""
import asyncio
from email.message import Message
import hashlib
import json

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


def service_pins(encoding='native_v1'):
    startup = {'schema': 'GRANITE_STARTUP_RUNTIME_V1',
               'mount': {'manifest_sha256': 'a' * 64},
               'environment': {'GRANITE_MAX_MODEL_LEN': '131072', 'GRANITE_SERVED_MODEL': 'granite42-smoke'},
               'runtime': {'packages': {'transformers': '5.8.0', 'tokenizers': '0.22.2'}}}
    runtime = {'outcome': 'service_ready', 'pod_id': 'test123', 'model': 'granite42-smoke',
               'runtime': {'startup': {'startup': startup}}}
    route = context_route(encoding)
    identity = GraniteIdentity('a' * 64, None, 'b' * 64, 'none', service._json(startup),
        False, 0, 1200, hashlib.sha256(route.system_text.encode()).hexdigest(),
        SCHEMA_VERSION, route.parser_code_hash(), None)
    config = service.RunpodConfig('test123', 'granite42-smoke', None,
                                 hashlib.sha256(service._json(runtime).encode()).hexdigest())
    return config, identity, runtime


def response(snapshot):
    content = valid_output(snapshot)
    content['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
    return service._json({'object': 'chat.completion', 'model': 'granite42-smoke',
        'choices': [{'index': 0, 'finish_reason': 'stop',
                     'message': {'role': 'assistant', 'content': json.dumps(content)}}]}).encode()


def admit(body):
    return dict(request_sha256=hashlib.sha256(body).hexdigest(), input_tokens=100,
                output_tokens=json.loads(body)['max_tokens'], context=131072,
                tokenizer_sha256='b' * 64)


@pytest.mark.parametrize('timeout', [0.03, 1, 60, 80])
def test_finite_request_timeout_is_retired_with_the_smoke_context(timeout):
    with pytest.raises(ValueError, match='open-ended'):
        service.RunpodConfig('test123', 'granite42-smoke', timeout, 'a' * 64)
    assert service.RunpodConfig('test123', 'granite42-smoke', None, 'a' * 64).context == 131072
    with pytest.raises(ValueError, match='131072'):
        service.RunpodConfig('test123', 'granite42-smoke', None, 'a' * 64, 4096)


def test_base_critic_refuses_if_ever_reached(source):
    config, identity, runtime = service_pins()
    critic = service.RunpodShadowService(True, config, identity, KEY, runtime, admit, lambda *a: None, None)
    with pytest.raises(ValueError, match='retired'):
        asyncio.run(critic.critique_native(source, request_id='retired'))


def test_runtime_context_and_receipt_binding_required():
    config, identity, runtime = service_pins()
    runtime['runtime']['startup']['startup']['environment']['GRANITE_MAX_MODEL_LEN'] = '8192'
    with pytest.raises(ValueError):
        service._runtime(config, identity, runtime)
    with pytest.raises(ValueError):
        service._runtime(service.RunpodConfig('test123', 'granite42-smoke', None, service._hash(runtime)), identity, runtime)


def test_disabled_and_config_hash_never_depend_on_credentials(tmp_path):
    critic = service.build_runpod_service()
    assert not critic.enabled and critic.identity is None and critic.config_hash is None
    assert asyncio.run(critic.critique_native(None, request_id='disabled')) is None
    config, identity, runtime = service_pins()
    first = service.build_runpod_service(enabled=True, config=config, identity=identity, runtime_receipt=runtime,
        api_key=KEY, admit_request=admit, exchange=lambda *a: None, spool_directory=tmp_path / 'one')
    second = service.build_runpod_service(enabled=True, config=config, identity=identity, runtime_receipt=runtime,
        api_key='z' * 40, admit_request=admit, exchange=lambda *a: None, spool_directory=tmp_path / 'two')
    assert first.config_hash == second.config_hash == config.config_hash
    assert KEY not in service._json(config.__dict__)


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
    payload = b'p' * 10000  # Above the probe helper's MAX_PROBE_BODY_BYTES bound; the service transport has no such bound.
    if damage is None:
        assert service.https_exchange('test123', 'POST', '/v1/chat/completions', payload, KEY, 5) == (200, raw)
    else:
        with pytest.raises(ValueError):
            service.https_exchange('test123', 'POST', '/v1/chat/completions', payload, KEY, 5)
    assert len(sent) == 1 and sent[0][2] == payload and closed == [True]
    assert reads == ([] if damage in ('oversized', 'chunked', 'duplicate_length') else [len(raw)])
