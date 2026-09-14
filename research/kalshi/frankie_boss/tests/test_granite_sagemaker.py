"""Real SDK protocol with synthetic responses; no AWS credentials or network."""
import asyncio
import base64
from dataclasses import replace
import io
import json
import threading

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber, ANY
import pytest

from research.kalshi.frankie_boss.granite_sagemaker import SageMakerConfig, build_sagemaker_service
from research.kalshi.frankie_boss.granite_prompt import build_prompt
from test_granite_shadow import identity
from test_granite_parser import snapshot, valid_output


def config():
    return SageMakerConfig('us-east-1', 'synthetic-granite', 'granite-4.2-8b', True, 1, 1, .2)


def output():
    return dict(id='synthetic', object='chat.completion', model=config().served_model_name,
        choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant',
            content=json.dumps(valid_output(snapshot())), reasoning=None, tool_calls=[]))],
        usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15))


def response(body=None):
    raw = json.dumps(output()).encode() if body is None else body
    return {'Body': StreamingBody(io.BytesIO(raw), len(raw)), 'ContentType': 'application/json',
            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': 'synthetic-id'}}


def test_disabled_service_has_no_client_or_credentials():
    service = build_sagemaker_service(client_factory=lambda cfg: pytest.fail('disabled'))
    assert service.enabled is False
    assert service.identity is None
    assert service.config_hash is None
    assert asyncio.run(service.critique(None, request_id='x')) is None
    assert asyncio.run(service.critique_native(None, request_id='x')) is None


def test_real_sdk_chat_payload_and_raw_evidence():
    client = boto3.client('sagemaker-runtime', region_name='us-east-1',
                          aws_access_key_id='offline', aws_secret_access_key='offline')
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: client)
    body = dict(model=config().served_model_name,
        messages=[dict(role='user', content=build_prompt(snapshot()).text)],
        temperature=0, max_tokens=1200, stream=False,
        chat_template_kwargs=dict(enable_thinking=False))
    with Stubber(client) as stub:
        stub.add_response('invoke_endpoint', response(), dict(
            EndpointName=config().endpoint_name, ContentType='application/json', Accept='application/json',
            Body=json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode(),
            CustomAttributes=ANY, InferenceId=ANY))
        result = asyncio.run(service.critique(snapshot(), request_id='sdk-test'))
        stub.assert_no_pending_responses()
    assert result.shadow.status == 'accepted'
    evidence = json.loads(result.provider_json)
    assert json.loads(base64.b64decode(evidence['body_base64'])) == output()
    assert evidence['response']['ResponseMetadata']['RequestId'] == 'synthetic-id'
    assert service.enabled and service.identity == identity()
    assert service.config_hash == result.config_hash


@pytest.mark.parametrize('kind', ['length', 'thinking', 'tools', 'wrong_model', 'choices', 'role', 'audio'])
def test_unsupported_outputs_reject_and_close_stream(kind):
    data = output()
    choice = data['choices'][0]
    if kind == 'length': choice['finish_reason'] = 'length'
    elif kind == 'thinking': choice['message']['reasoning'] = 'not allowed'
    elif kind == 'tools': choice['message']['tool_calls'] = [{'id': 'tool'}]
    elif kind == 'wrong_model': data['model'] = 'different'
    elif kind == 'choices': data['choices'].append(choice.copy())
    elif kind == 'role': choice['message']['role'] = 'tool'
    else: choice['message']['audio'] = {'data': 'bytes'}
    raw = json.dumps(data).encode(); wrapped = response(raw)
    stream = wrapped['Body']._raw_stream
    class Client:
        def invoke_endpoint(self, **kwargs): return wrapped
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='x'))
    assert result.shadow.status == 'transport_error'
    assert base64.b64decode(json.loads(result.provider_json)['body_base64']) == raw
    assert stream.closed


@pytest.mark.parametrize('raw', [b'{"choices":[],"choices":[]}', b'{"number":NaN}', b'\xff', b'not json'])
def test_bad_json_body_retained_exactly(raw):
    class Client:
        def invoke_endpoint(self, **kwargs): return response(raw)
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='x'))
    assert result.shadow.status == 'transport_error'
    assert base64.b64decode(json.loads(result.provider_json)['body_base64']) == raw


def test_sdk_factory_has_finite_timeouts_and_no_retry(monkeypatch):
    from research.kalshi.frankie_boss.granite_sagemaker import _client
    calls = []
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: calls.append((a, k)))
    _client(config())
    args, kwargs = calls[0]
    assert args == ('sagemaker-runtime',)
    assert kwargs['region_name'] == config().region
    assert kwargs['config'].retries['total_max_attempts'] == 1
    assert kwargs['config'].read_timeout == 1


def test_timeout_does_not_release_capacity_until_body_finishes():
    release, finished = threading.Event(), threading.Event()
    class Client:
        calls = 0
        def invoke_endpoint(self, **kwargs):
            self.calls += 1
            release.wait(2)
            finished.set()
            return response()
    client = Client()
    service = build_sagemaker_service(enabled=True, config=replace(config(), request_timeout=.01),
                                      identity=identity(), client_factory=lambda cfg: client)
    async def scenario():
        first = await service.critique(snapshot(), request_id='first')
        assert first.shadow.status == 'timeout'
        second = await service.critique(snapshot(), request_id='second')
        assert second.shadow.status == 'transport_error'
        assert second.error_type == 'Busy' and client.calls == 1
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        assert finished.wait(1)


def test_local_pin_failure_prevents_client_construction():
    service = build_sagemaker_service(enabled=True, config=config(),
        identity=replace(identity(), parser_code_hash='f'*64),
        client_factory=lambda cfg: pytest.fail('invalid pin'))
    with pytest.raises(ValueError):
        asyncio.run(service.critique(snapshot(), request_id='x'))


def test_native_boundary_uses_its_distinct_prompt_and_parser(tmp_path):
    from test_granite_context import case
    from granite_context import map_native_context
    from research.kalshi.frankie_boss.granite_context import (
        parse_native_context, build_native_prompt, native_parser_code_hash)
    raw_snapshot = map_native_context(**case(tmp_path))
    native = parse_native_context(raw_snapshot.text, expected_hash=raw_snapshot.hash)
    native_identity = replace(identity(), system_prompt_hash=build_native_prompt(native).system_prompt_hash,
                               parser_code_hash=native_parser_code_hash())
    class Client:
        def invoke_endpoint(self, **kwargs):
            assert json.loads(kwargs['Body'])['messages'][0]['content'] == build_native_prompt(native).text
            data = output()
            valid = valid_output(native)
            valid['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
            data['choices'][0]['message']['content'] = json.dumps(valid)
            return response(json.dumps(data).encode())
    service = build_sagemaker_service(enabled=True, config=config(), identity=native_identity,
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique_native(native, request_id='native'))
    assert result.shadow.status == 'accepted'


def test_config_drift_and_thinking_reject_before_invocation(monkeypatch):
    from research.kalshi.frankie_boss import granite_sagemaker as module
    with pytest.raises(ValueError):
        build_sagemaker_service(enabled=True, config=config(), identity=replace(identity(), thinking=True))
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity())
    monkeypatch.setattr(module, 'version', lambda name: 'changed')
    with pytest.raises(ValueError, match='changed'):
        _ = service.config_hash


@pytest.mark.parametrize('changes', [dict(endpoint_name='bad/name'), dict(endpoint_name='-bad'),
    dict(served_model_name=''), dict(openai_chat_supported=False),
    dict(connect_timeout=True), dict(read_timeout=float('inf')), dict(request_timeout=0)])
def test_invalid_configuration_rejects(changes):
    with pytest.raises(ValueError):
        replace(config(), **changes)


def test_real_sdk_error_retains_aws_response():
    from botocore.exceptions import ClientError
    provider = {'Error': {'Code': 'ModelError', 'Message': 'synthetic'},
                'ResponseMetadata': {'RequestId': 'failed'}}
    class Client:
        def invoke_endpoint(self, **kwargs):
            raise ClientError(provider, 'InvokeEndpoint')
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='error'))
    assert result.shadow.status == 'transport_error' and result.error_type == 'ClientError'
    assert json.loads(result.provider_json) == provider


def test_call_and_request_hashes_are_sent_without_prompt_metadata_leak():
    seen = []
    class Client:
        def invoke_endpoint(self, **kwargs):
            seen.append(kwargs)
            return response()
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='bindings'))
    assert seen[0]['InferenceId'] == result.call_hash
    assert seen[0]['CustomAttributes'] == (
        f'shadow_request_hash={result.shadow.request.request_hash};transport_config_hash={result.config_hash}')


def test_cancelled_caller_keeps_capacity_during_body_read():
    started, release, closed = threading.Event(), threading.Event(), threading.Event()
    class Body:
        def read(self):
            started.set()
            release.wait(2)
            return json.dumps(output()).encode()
        def close(self): closed.set()
    class Client:
        calls = 0
        def invoke_endpoint(self, **kwargs):
            self.calls += 1
            return {'Body': Body(), 'ContentType': 'application/json'}
    client = Client()
    service = build_sagemaker_service(enabled=True, config=replace(config(), request_timeout=1),
                                      identity=identity(), client_factory=lambda cfg: client)
    async def scenario():
        task = asyncio.create_task(service.critique(snapshot(), request_id='cancel'))
        for _ in range(100):
            if started.is_set(): break
            await asyncio.sleep(.005)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        another = await service.critique(snapshot(), request_id='busy')
        assert another.error_type == 'Busy' and client.calls == 1
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        assert closed.wait(1)


def test_failed_body_read_always_closes_stream():
    class Body:
        closed = False
        def read(self): raise TimeoutError('synthetic read timeout')
        def close(self): self.closed = True
    body = Body()
    class Client:
        def invoke_endpoint(self, **kwargs):
            return {'Body': body, 'ContentType': 'application/json', 'InvokedProductionVariant': 'AllTraffic'}
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='read'))
    assert result.shadow.status == 'transport_error' and body.closed
    assert json.loads(result.provider_json)['body_base64'] is None


def test_close_failure_still_retains_completed_body():
    payload = json.dumps(output()).encode()
    class Body:
        def read(self): return payload
        def close(self): raise OSError('synthetic close failure')
    class Client:
        def invoke_endpoint(self, **kwargs):
            return {'Body': Body(), 'ContentType': 'application/json'}
    service = build_sagemaker_service(enabled=True, config=config(), identity=identity(),
                                      client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='close'))
    assert result.shadow.status == 'transport_error'
    assert base64.b64decode(json.loads(result.provider_json)['body_base64']) == payload
