"""Offline Bedrock SDK integration; never uses AWS credentials or network."""
import asyncio
from dataclasses import asdict, replace
import json
import threading

import boto3
from botocore.stub import Stubber
import pytest

from research.kalshi.frankie_boss.granite_bedrock import BedrockConfig, build_bedrock_service
from test_granite_shadow import identity
from test_granite_parser import snapshot, valid_output


def config():
    return BedrockConfig('us-east-1', 'synthetic.granite-v1', True, 1, 1, 0.1)


def response():
    return {'output': {'message': {'role': 'assistant', 'content': [{'text': json.dumps(valid_output(snapshot()))}]}},
            'stopReason': 'end_turn', 'usage': {'inputTokens': 10, 'outputTokens': 5, 'totalTokens': 15},
            'metrics': {'latencyMs': 1}, 'ResponseMetadata': {'RequestId': 'offline-id', 'HTTPStatusCode': 200}}


def test_disabled_factory_never_constructs_client():
    def factory(cfg):
        pytest.fail('disabled route')
    service = build_bedrock_service(enabled=False, config=None, identity=None, client_factory=factory)
    assert asyncio.run(service.critique(None, request_id='x')) is None


def test_real_boto3_converse_path_and_metadata():
    from research.kalshi.frankie_boss.granite_prompt import build_prompt
    client = boto3.client('bedrock-runtime', region_name='us-east-1',
                          aws_access_key_id='offline', aws_secret_access_key='offline')
    service = build_bedrock_service(enabled=True, config=config(), identity=identity(),
                                    client_factory=lambda cfg: client)
    with Stubber(client) as stub:
        from botocore.stub import ANY
        stub.add_response('converse', response(), {
            'modelId': config().model_id,
            'messages': [{'role': 'user', 'content': [{'text': build_prompt(snapshot()).text}]}],
            'inferenceConfig': {'temperature': 0, 'maxTokens': 1200},
            'requestMetadata': {'shadow_request_hash': ANY, 'transport_config_hash': ANY}})
        result = asyncio.run(service.critique(snapshot(), request_id='x'))
        stub.assert_no_pending_responses()
    assert result.shadow.status == 'accepted'
    assert json.loads(result.provider_json)['ResponseMetadata']['RequestId'] == 'offline-id'
    assert result.config_hash == config().config_hash


@pytest.mark.parametrize('field,value', [('converse_text_supported', False), ('read_timeout', 0),
                                       ('region', ''), ('model_id', 'arn:aws:bedrock:us-east-1:123456789012:prompt/ABC:1')])
def test_incompatible_config_rejected(field, value):
    with pytest.raises(ValueError):
        replace(config(), **{field: value})


def test_thinking_mode_rejected_before_client():
    with pytest.raises(ValueError):
        build_bedrock_service(enabled=True, config=config(), identity=replace(identity(), thinking=True))


@pytest.mark.parametrize('kind', ['truncated', 'thinking', 'error'])
def test_provider_failures_are_isolated_with_evidence(kind):
    class Client:
        def converse(self, **kwargs):
            if kind == 'error':
                raise RuntimeError('offline failure')
            value = response()
            if kind == 'truncated':
                value['stopReason'] = 'max_tokens'
            else:
                value['output']['message']['content'] = [{'reasoningContent': {'text': 'unsupported'}}]
            return value
    service = build_bedrock_service(enabled=True, config=config(), identity=identity(), client_factory=lambda cfg: Client())
    result = asyncio.run(service.critique(snapshot(), request_id='x'))
    assert result.shadow.status == 'transport_error'
    assert result.provider_json is not None if kind != 'error' else result.provider_json is None


def test_timeout_retains_worker_capacity_until_network_returns():
    release, entered, finished = threading.Event(), threading.Event(), threading.Event()
    class Client:
        calls = 0
        def converse(self, **kwargs):
            self.calls += 1
            entered.set()
            release.wait(2)
            finished.set()
            return response()
    client = Client()
    service = build_bedrock_service(enabled=True, config=replace(config(), request_timeout=0.01),
                                    identity=identity(), client_factory=lambda cfg: client)
    async def scenario():
        first = await service.critique(snapshot(), request_id='a')
        assert first.shadow.status == 'timeout'
        second = await service.critique(snapshot(), request_id='b')
        assert second.shadow.status == 'transport_error'
        assert client.calls == 1
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        assert finished.wait(1)


def test_default_factory_sets_sdk_region_deadlines_and_single_attempt(monkeypatch):
    from research.kalshi.frankie_boss.granite_bedrock import _client
    calls = []
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: calls.append((args, kwargs)))
    _client(config())
    args, kwargs = calls[0]
    assert args == ('bedrock-runtime',)
    assert kwargs['region_name'] == config().region
    assert kwargs['config'].connect_timeout == config().connect_timeout
    assert kwargs['config'].read_timeout == config().read_timeout
    assert kwargs['config'].retries['total_max_attempts'] == 1


def test_config_endpoint_and_deadline_changes_mint_new_identity():
    for change in ({'region': 'us-west-2'}, {'model_id': 'other.model'},
                   {'connect_timeout': 2}, {'read_timeout': 2}, {'request_timeout': 2}):
        assert replace(config(), **change).config_hash != config().config_hash


def test_bad_local_parser_pin_never_constructs_sdk_client():
    service = build_bedrock_service(enabled=True, config=config(),
                                    identity=replace(identity(), parser_code_hash='f'*64),
                                    client_factory=lambda cfg: pytest.fail('must not construct'))
    with pytest.raises(ValueError):
        asyncio.run(service.critique(snapshot(), request_id='x'))


def test_explicit_live_harness_executes_sdk_path_and_never_overwrites(tmp_path, monkeypatch):
    from research.kalshi.frankie_boss import granite_bedrock as module
    calls = []
    class Client:
        def converse(self, **kwargs):
            calls.append(kwargs)
            return response()
    monkeypatch.setattr(module, '_client', lambda cfg: Client())
    cfg, state, output = tmp_path/'config.json', tmp_path/'state.json', tmp_path/'receipt.json'
    cfg.write_text(json.dumps({'config': asdict(config()), 'identity': asdict(identity())}), encoding='utf-8')
    state.write_bytes(snapshot().text.encode())
    args = ['--live', '--config', str(cfg), '--snapshot', str(state), '--request-id', 'test', '--receipt', str(output)]
    assert module.main(args) == 0
    saved = output.read_bytes()
    assert json.loads(saved)['shadow']['status'] == 'accepted'
    with pytest.raises(FileExistsError):
        module.main(args)
    assert len(calls) == 1
    assert output.read_bytes() == saved
