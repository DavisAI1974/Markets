"""Exact native evidence through the real AWS SDK contract, no network."""
import asyncio
from dataclasses import replace
import json

import boto3
from botocore.stub import ANY, Stubber
import pytest

from research.kalshi.frankie_boss import granite_context as context
from research.kalshi.frankie_boss.granite_bedrock import build_bedrock_service
from research.kalshi.frankie_boss.granite_shadow import serve_native_shadow, ShadowResponse
from test_granite_context import case, map_native_context
from test_granite_shadow import identity
from test_granite_bedrock import config
from test_granite_parser import valid_output


def native_case(tmp_path):
    original = map_native_context(**case(tmp_path, extra=True, qsv=True))
    state = context.parse_native_context(original.text, expected_hash=original.hash)
    pin = replace(identity(), system_prompt_hash=context.build_native_prompt(state).system_prompt_hash,
                  parser_code_hash=context.native_parser_code_hash())
    output = valid_output(state)
    output['evidence_refs'] = [{'row': 0, 'field': '/record/extension/odd~1key/1'}]
    return state, pin, json.dumps(output)


def test_native_full_prompt_reaches_real_boto3_converse(tmp_path):
    state, pin, output = native_case(tmp_path)
    client = boto3.client('bedrock-runtime', region_name='us-east-1',
                          aws_access_key_id='offline', aws_secret_access_key='offline')
    service = build_bedrock_service(enabled=True, config=config(), identity=pin, client_factory=lambda cfg: client)
    assert service.enabled and service.identity == pin and service.config_hash == config().config_hash
    with Stubber(client) as stub:
        stub.add_response('converse', {
            'output': {'message': {'role': 'assistant', 'content': [{'text': output}]}},
            'stopReason': 'end_turn', 'usage': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2},
            'metrics': {'latencyMs': 1}}, {
            'modelId': config().model_id,
            'messages': [{'role': 'user', 'content': [{'text': context.build_native_prompt(state).text}]}],
            'inferenceConfig': {'temperature': 0, 'maxTokens': pin.max_tokens},
            'requestMetadata': {'shadow_request_hash': ANY, 'transport_config_hash': ANY}})
        receipt = asyncio.run(service.critique_native(state, request_id='native'))
        stub.assert_no_pending_responses()
    assert receipt.shadow.status == 'accepted'
    assert receipt.shadow.request.snapshot_text == state.text


@pytest.mark.parametrize('change', ['parser', 'prompt', 'capacity'])
def test_native_pin_and_capacity_failures_precede_transport(tmp_path, change):
    state, pin, _ = native_case(tmp_path)
    if change == 'parser':
        pin = replace(pin, parser_code_hash=identity().parser_code_hash)
    if change == 'prompt':
        pin = replace(pin, system_prompt_hash=identity().system_prompt_hash)
    async def transport(request):
        pytest.fail('must not invoke')
    with pytest.raises(ValueError):
        asyncio.run(serve_native_shadow(state, pin, request_id='x', timeout_seconds=1,
                                       transport=transport, max_prompt_bytes=1 if change == 'capacity' else None))


def test_native_binding_and_output_failures_are_receipted(tmp_path):
    state, pin, output = native_case(tmp_path)
    for wrong_hash, text, status in [(True, output, 'binding_mismatch'), (False, '{}', 'rejected')]:
        async def transport(request):
            return ShadowResponse('a'*64 if wrong_hash else request.request_hash, pin.identity_hash, text)
        receipt = asyncio.run(serve_native_shadow(state, pin, request_id='x', timeout_seconds=1, transport=transport))
        assert receipt.status == status


def test_native_disabled_service_does_not_resolve_config_or_sdk():
    service = build_bedrock_service(client_factory=lambda cfg: pytest.fail('disabled'))
    assert not service.enabled and service.config_hash is None
    assert asyncio.run(service.critique_native(None, request_id='x')) is None
