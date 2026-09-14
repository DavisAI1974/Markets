"""Compact serving keeps exact evidence and SDK contracts without network access."""
import asyncio
from dataclasses import replace
import json

import boto3
from botocore.stub import ANY, Stubber
import pytest

from research.kalshi.frankie_boss import granite_context_compact as compact
from research.kalshi.frankie_boss.granite_bedrock import build_bedrock_service
from research.kalshi.frankie_boss.granite_sagemaker import build_sagemaker_service
from test_granite_native_service import native_case
from test_granite_bedrock import config as bedrock_config
from test_granite_sagemaker import config as sagemaker_config, response
from test_granite_parser import valid_output


def compact_case(tmp_path):
    native, pin, _ = native_case(tmp_path)
    state = compact.compact_native_context(native)
    pin = replace(pin, system_prompt_hash=compact.build_compact_prompt(state).system_prompt_hash,
                  parser_code_hash=compact.compact_parser_code_hash())
    output = valid_output(state)
    output['evidence_refs'] = [{'row': 0, 'field': '/record/extension/odd~1key/1'}]
    return state, pin, json.dumps(output)


@pytest.mark.parametrize('provider', ['bedrock', 'sagemaker'])
def test_compact_exact_prompt_reaches_real_sdk(tmp_path, provider):
    state, pin, output = compact_case(tmp_path)
    prompt = compact.build_compact_prompt(state).text
    client = boto3.client(provider + '-runtime', region_name='us-east-1',
                          aws_access_key_id='offline', aws_secret_access_key='offline')
    if provider == 'bedrock':
        cfg = bedrock_config()
        service = build_bedrock_service(enabled=True, config=cfg, identity=pin, client_factory=lambda cfg: client)
        operation = 'converse'
        returned = {'output': {'message': {'role': 'assistant', 'content': [{'text': output}]}},
            'stopReason': 'end_turn', 'usage': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2},
            'metrics': {'latencyMs': 1}}
        expected = {'modelId': cfg.model_id,
            'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
            'inferenceConfig': {'temperature': 0, 'maxTokens': pin.max_tokens},
            'requestMetadata': {'shadow_request_hash': ANY, 'transport_config_hash': ANY}}
    else:
        cfg = sagemaker_config()
        service = build_sagemaker_service(enabled=True, config=cfg, identity=pin, client_factory=lambda cfg: client)
        operation = 'invoke_endpoint'
        returned = response(json.dumps(dict(object='chat.completion', model=cfg.served_model_name,
            choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant', content=output,
                reasoning=None, tool_calls=[]))])).encode())
        body = dict(model=cfg.served_model_name, messages=[dict(role='user', content=prompt)],
            temperature=0, max_tokens=pin.max_tokens, stream=False, chat_template_kwargs=dict(enable_thinking=False))
        expected = dict(EndpointName=cfg.endpoint_name, ContentType='application/json', Accept='application/json',
            Body=json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode(),
            CustomAttributes=ANY, InferenceId=ANY)
    with Stubber(client) as stub:
        stub.add_response(operation, returned, expected)
        receipt = asyncio.run(service.critique_compact(state, request_id='compact'))
        stub.assert_no_pending_responses()
    assert receipt.shadow.status == 'accepted'
    assert receipt.shadow.request.snapshot_text == state.text
    assert receipt.provider_json is not None


@pytest.mark.parametrize('provider', ['bedrock', 'sagemaker'])
@pytest.mark.parametrize('change', ['parser', 'prompt', 'capacity'])
def test_compact_refuses_wrong_pins_and_size_before_sdk(tmp_path, provider, change):
    state, pin, _ = compact_case(tmp_path)
    if change == 'parser':
        pin = replace(pin, parser_code_hash='f'*64)
    elif change == 'prompt':
        pin = replace(pin, system_prompt_hash='f'*64)
    factory = lambda cfg: pytest.fail('invalid request reached SDK factory')
    service = (build_bedrock_service(enabled=True, config=bedrock_config(), identity=pin, client_factory=factory)
        if provider == 'bedrock' else
        build_sagemaker_service(enabled=True, config=sagemaker_config(), identity=pin, client_factory=factory))
    with pytest.raises(ValueError):
        asyncio.run(service.critique_compact(state, request_id='bad', max_prompt_bytes=1 if change == 'capacity' else None))


def test_compact_route_exact_inverse_and_explicit_encoding(tmp_path):
    from research.kalshi.frankie_boss.granite_context_route import context_route
    native, _, _ = native_case(tmp_path)
    route = context_route('compact_v1')
    snapshot = route.encode(native)
    assert route.native(snapshot).text == native.text
    assert route.parse(snapshot.text, expected_hash=snapshot.hash) == snapshot
    assert context_route('native_v1').encode(native) == native
    for invalid in (None, '', 'auto', 'COMPACT_V1'):
        with pytest.raises(ValueError): context_route(invalid)


def test_route_imports_in_package_and_standalone_modes(tmp_path):
    import importlib
    native, _, _ = native_case(tmp_path)
    for name in ('research.kalshi.frankie_boss.granite_context_route', 'granite_context_route'):
        route = importlib.import_module(name).context_route('compact_v1')
        assert route.native(route.encode(native)).text == native.text


def test_encoding_checks_exact_inverse_before_admission(tmp_path, monkeypatch):
    from research.kalshi.frankie_boss.granite_context_route import context_route
    native, _, _ = native_case(tmp_path)
    foreign_dir = tmp_path/'foreign'; foreign_dir.mkdir()
    foreign, _, _ = native_case(foreign_dir)
    body = json.loads(foreign.text)
    body['source_as_of'] += 1
    from research.kalshi.frankie_boss.granite_context import NativeContext
    foreign = NativeContext(json.dumps(body, sort_keys=True, separators=(',', ':')))
    compact_foreign = compact.compact_native_context(foreign)
    monkeypatch.setattr(compact, 'compact_native_context', lambda snapshot, **kwargs: compact_foreign)
    with pytest.raises(ValueError, match='inverse verification'):
        context_route('compact_v1').encode(native)
