"""New open-ended durability seams; synthetic HTTP only, no model/provider calls."""
import asyncio
from dataclasses import asdict
import hashlib
import json
import threading
from types import SimpleNamespace
import pytest

from research.kalshi.frankie_boss import granite_open_ended_service as durable
from research.kalshi.frankie_boss import granite_runpod_service as finite
from research.kalshi.frankie_boss.granite_context_route import context_route
from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity,ShadowRequest,PendingTransport,_serve_request
from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION
from research.kalshi.frankie_boss.granite_parser import Verdict

KEY='synthetic_private_'+'x'*40


def fixture(tmp_path,exchange):
    startup=dict(schema='GRANITE_STARTUP_RUNTIME_V1',mount=dict(manifest_sha256='a'*64),
        environment=dict(GRANITE_MAX_MODEL_LEN='131072',GRANITE_SERVED_MODEL='granite42-smoke'),
        runtime=dict(packages={'transformers':'5.8.0','tokenizers':'0.22.2'}))
    runtime=dict(outcome='service_ready',pod_id='test123',model='granite42-smoke',runtime=dict(startup=dict(startup=startup)))
    route=context_route('compact_v1')
    identity=GraniteIdentity('a'*64,None,'b'*64,'none',finite._json(startup),False,0,1200,
        hashlib.sha256(route.system_text.encode()).hexdigest(),SCHEMA_VERSION,route.parser_code_hash(),None)
    config=finite.RunpodConfig('test123','granite42-smoke',None,finite._hash(runtime))
    def admit(body):return dict(request_sha256=hashlib.sha256(body).hexdigest(),input_tokens=10,output_tokens=1200,context=131072,tokenizer_sha256='b'*64)
    service=finite.build_runpod_service(enabled=True,config=config,identity=identity,runtime_receipt=runtime,
        api_key=KEY,admit_request=admit,exchange=exchange,spool_directory=tmp_path)
    return service,ShadowRequest('same-attempt',identity,'snapshot','c'*64,'actual synthetic prompt',None)


def raw_response():
    return finite._json(dict(object='chat.completion',model='granite42-smoke',choices=[dict(index=0,finish_reason='stop',
        message=dict(role='assistant',content='retained result'))])).encode()


def test_finite_mode_is_retired_and_the_open_ended_hash_is_stable():
    with pytest.raises(ValueError,match='open-ended'):finite.RunpodConfig('test123','granite42-smoke',80,'a'*64)
    config=finite.RunpodConfig('test123','granite42-smoke',None,'a'*64)
    fields=asdict(config);fields.pop('transport_protocol')
    expected=finite._hash(dict(schema='GRANITE_RUNPOD_OPEN_ENDED_V1',**fields,prompt_mode='exact_user_text',
        enable_thinking=False,stream=False,max_request_bytes=finite.MAX_REQUEST,max_response_bytes=finite.MAX_RESPONSE,total_max_attempts=1))
    assert config.config_hash==expected and config.context==131072
    with pytest.raises(ValueError):finite.RunpodConfig('test123','granite42-smoke',float('inf'),'a'*64)


def test_cancelled_caller_late_response_and_disk_replay_never_dispatch_twice(tmp_path):
    sent=threading.Event();release=threading.Event();calls=[]
    def exchange(*args):
        calls.append(args[3]);assert args[-1] is None
        assert list(tmp_path.glob('*/dispatch.json'))  # durable before actual exchange
        sent.set();release.wait();return 200,raw_response()
    service,request=fixture(tmp_path,exchange)
    async def scenario():
        evidence={}
        first=asyncio.create_task(service._durable_transport(request,evidence))
        while not sent.is_set():await asyncio.sleep(.001)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):await first
        second=asyncio.create_task(service._durable_transport(request,evidence))
        await asyncio.sleep(.02)
        assert not second.done() and len(calls)==1
        release.set()
        response=await second
        assert response.text=='retained result'
        assert list(tmp_path.glob('*/outcome.json'))  # saved before caller completion
        fresh,_=fixture(tmp_path,lambda *args:pytest.fail('saved same attempt must not POST'))
        replay=await fresh._durable_transport(request,{})
        assert replay==response and len(calls)==1
    try:asyncio.run(scenario())
    finally:release.set()
    assert KEY not in ''.join(p.read_text() for p in tmp_path.glob('*/*.json'))


def test_process_loss_ambiguity_propagates_without_terminal_verdict_or_retry(tmp_path):
    calls=[]
    def exchange(*args):calls.append(1);raise ConnectionError('synthetic lost response')
    service,request=fixture(tmp_path,exchange)
    async def scenario():
        async def transport(req):return await service._durable_transport(req,{})
        with pytest.raises(PendingTransport):
            await _serve_request(request,None,transport,lambda *_:(None,Verdict.L4))
        # Simulate process loss after dispatch but before durable result, with no
        # live worker registry. This is a synthetic spool; no real files touched.
        directory=next(tmp_path.glob('*/dispatch.json')).parent
        (directory/'outcome.json').unlink()
        durable._WORKERS.pop(str(directory))
        fresh,_=fixture(tmp_path,lambda *args:pytest.fail('ambiguous dispatch must not POST'))
        with pytest.raises(PendingTransport):await fresh._durable_transport(request,{})
        assert calls==[1]
    asyncio.run(scenario())


def test_recovery_only_needs_no_key_and_cannot_create_dispatch(tmp_path):
    service,request=fixture(tmp_path,lambda *args:(200,raw_response()))
    async def scenario():
        expected=await service._durable_transport(request,{})
        recovery=finite.build_runpod_service(enabled=True,config=service._config,identity=service.identity,
            runtime_receipt=service._runtime_receipt if hasattr(service,'_runtime_receipt') else None,
            api_key=None,admit_request=service._admit,spool_directory=tmp_path,recovery_only=True)
        assert await recovery._durable_transport(request,{})==expected
        from dataclasses import replace
        with pytest.raises(PendingTransport):
            await recovery._durable_transport(replace(request,request_id='not-dispatched'),{})
    # Runtime is independently pinned; preserve the constructor input explicitly.
    startup=json.loads(service.identity.runtime_versions)
    service._runtime_receipt=dict(outcome='service_ready',pod_id='test123',model='granite42-smoke',runtime=dict(startup=dict(startup=startup)))
    asyncio.run(scenario())


def test_controller_readback_requires_durable_binding_for_null_timeout(tmp_path,monkeypatch):
    from research.kalshi.frankie_boss import controller_journal as journal
    service,request=fixture(tmp_path,lambda *args:pytest.fail('readback cannot POST'))
    config=dict(critic_config_hash=service.config_hash,critic_identity_hash=service.identity.identity_hash,
        critic_timeout=None,durable_storage_identity=service.durable_storage_identity)
    state=dict(intent=dict(configuration=config),critic_intent=dict(attempt_id=request.request_id,prompt_text=request.prompt_text))
    monkeypatch.setattr(journal,'_critic_context',lambda *_:(None,SimpleNamespace(text=request.snapshot_text,hash=request.snapshot_hash),
        SimpleNamespace(text=request.prompt_text)))
    receipt=dict(shadow=dict(request=asdict(request),status='transport_error',response=None,verdict=None),
        config_hash=service.config_hash,call_hash=finite._hash(dict(config_hash=service.config_hash,request_hash=request.request_hash)),
        provider_json=None,error_type='RuntimeError')
    payload=dict(intent_hash='a'*64,receipt=receipt)
    journal._critic_links(state,payload)
    config.pop('durable_storage_identity')
    with pytest.raises(ValueError):journal._critic_links(state,payload)
