"""Synthetic shadow serving only; no provider or model execution."""
import asyncio
from dataclasses import replace
import json

import pytest

from research.kalshi.frankie_boss.granite_shadow import (
    GraniteIdentity, ShadowResponse, parser_code_hash, serve_shadow,
)
from research.kalshi.frankie_boss.granite_prompt import build_prompt
from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION
from test_granite_parser import snapshot, valid_output


def identity():
    return GraniteIdentity('a'*64, None, 'b'*64, 'none', 'synthetic-runtime/1',
                           False, 0, 1200, build_prompt(snapshot()).system_prompt_hash,
                           SCHEMA_VERSION, parser_code_hash(), None)


def run(transport, **kwargs):
    return asyncio.run(serve_shadow(snapshot(), identity(), request_id='fixture/1',
                                    timeout_seconds=0.1, transport=transport, **kwargs))


def test_exact_request_and_accepted_shadow():
    state = snapshot()
    async def transport(request):
        assert request.snapshot_text == state.text
        assert request.prompt_text == build_prompt(state).text
        assert request.identity == identity()
        return ShadowResponse(request.request_hash, request.identity.identity_hash,
                              json.dumps(valid_output(state)))
    receipt = run(transport)
    assert receipt.status == 'accepted'
    assert receipt.verdict == 'L4'
    assert receipt.response.text == json.dumps(valid_output(state))
    assert snapshot() == state


@pytest.mark.parametrize('field', ['system_prompt_hash', 'parser_code_hash', 'schema_version'])
def test_bad_local_pin_prevents_transport(field):
    async def transport(request):
        pytest.fail('must not invoke')
    with pytest.raises(ValueError):
        asyncio.run(serve_shadow(snapshot(), replace(identity(), **{field: 'f'*64}),
                                request_id='x', timeout_seconds=1, transport=transport))


@pytest.mark.parametrize('text,verdict', [('broken', 'L0'), ('{}', 'L1'),
                                       (json.dumps({**valid_output(snapshot()), 'snapshot_hash': 'f'*64}), 'L3')])
def test_parser_rejections_retained(text, verdict):
    async def transport(request):
        return ShadowResponse(request.request_hash, request.identity.identity_hash, text)
    result = run(transport)
    assert result.status == 'rejected'
    assert result.verdict == verdict
    assert result.response.text == text


@pytest.mark.parametrize('field', ['request_hash', 'identity_hash'])
def test_foreign_response_isolated(field):
    async def transport(request):
        response = ShadowResponse(request.request_hash, request.identity.identity_hash,
                                  json.dumps(valid_output(snapshot())))
        return replace(response, **{field: 'f'*64})
    assert run(transport).status == 'binding_mismatch'


def test_transport_failure_and_malformed_response():
    async def failure(request):
        raise RuntimeError('synthetic')
    async def malformed(request):
        return {'text': 'bad'}
    assert run(failure).status == 'transport_error'
    assert run(malformed).status == 'malformed_response'


def test_deadline_does_not_wait_for_cancellation_acknowledgement():
    async def scenario():
        release = asyncio.Event()
        stopped = asyncio.Event()
        async def transport(request):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                await release.wait()
            finally:
                stopped.set()
            return ShadowResponse(request.request_hash, request.identity.identity_hash, '{}')
        result = await asyncio.wait_for(serve_shadow(
            snapshot(), identity(), request_id='x', timeout_seconds=0.001,
            transport=transport), timeout=0.5)
        assert result.status == 'timeout'
        release.set()
        await stopped.wait()
    asyncio.run(scenario())


@pytest.mark.parametrize('timeout', [0, -1, True, float('nan'), float('inf')])
def test_explicit_valid_timeout_required(timeout):
    with pytest.raises(ValueError):
        asyncio.run(serve_shadow(snapshot(), identity(), request_id='x',
                                timeout_seconds=timeout, transport=None))


def test_identity_changes_are_material_and_tuned_receipt_required():
    base = identity()
    assert replace(base, max_tokens=10).identity_hash != base.identity_hash
    with pytest.raises(ValueError):
        replace(base, weights_sha='c'*64)


@pytest.mark.parametrize('changes', [
    {'base_checkpoint_sha': 'c'*64}, {'tokenizer_sha': 'c'*64},
    {'quantization': 'int8'}, {'runtime_versions': 'synthetic/2'},
    {'thinking': True}, {'max_tokens': 1}, {'system_prompt_hash': 'c'*64},
    {'schema_version': 'next'}, {'parser_code_hash': 'c'*64},
    {'weights_sha': 'c'*64, 'tune_receipt_hash': 'd'*64},
])
def test_every_supported_identity_change_mints_identity(changes):
    assert replace(identity(), **changes).identity_hash != identity().identity_hash


@pytest.mark.parametrize('changes', [
    {'base_checkpoint_sha': 'branch-name'}, {'tokenizer_sha': None},
    {'quantization': ''}, {'runtime_versions': ''}, {'thinking': 1},
    {'temperature': True}, {'temperature': 0.5}, {'max_tokens': True},
    {'max_tokens': 0}, {'tune_receipt_hash': 'd'*64},
])
def test_invalid_pins_rejected(changes):
    with pytest.raises(ValueError):
        replace(identity(), **changes)


def test_bad_state_prevents_transport():
    async def transport(request):
        pytest.fail('must not invoke')
    with pytest.raises(ValueError):
        asyncio.run(serve_shadow(replace(snapshot(), text='{}'), identity(),
                                request_id='x', timeout_seconds=1, transport=transport))


def test_request_hash_binds_every_request_field():
    async def transport(request):
        for change in ({'request_id': 'other'}, {'timeout_seconds': 2.0},
                       {'snapshot_text': '{}'}, {'snapshot_hash': 'e'*64},
                       {'prompt_text': 'other'}, {'identity': replace(identity(), max_tokens=5)}):
            assert replace(request, **change).request_hash != request.request_hash
        return ShadowResponse(request.request_hash, request.identity.identity_hash, '{}')
    run(transport)


def test_disagreement_is_only_shadow_evidence():
    output = {**valid_output(snapshot()), 'evidence_verdict': 'CONFLICTED'}
    async def transport(request):
        return ShadowResponse(request.request_hash, request.identity.identity_hash, json.dumps(output))
    result = run(transport)
    assert result.status == 'accepted'
    assert json.loads(result.response.text)['evidence_verdict'] == 'CONFLICTED'


def test_caller_cancellation_propagates_and_cancels_transport():
    async def scenario():
        started, stopped = asyncio.Event(), asyncio.Event()
        async def transport(request):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                stopped.set()
        task = asyncio.create_task(serve_shadow(snapshot(), identity(), request_id='x',
                                               timeout_seconds=1, transport=transport))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(stopped.wait(), timeout=0.5)
    asyncio.run(scenario())
