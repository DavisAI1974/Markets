"""Remaining-context output reservation and truncated-result refusal; synthetic only."""
import asyncio
from dataclasses import replace
import hashlib,json
import pytest
from research.kalshi.frankie_boss import granite_runpod_proxy as proxy
from research.kalshi.frankie_boss import granite_runpod_tokenizer as tokenizer
from research.kalshi.frankie_boss import granite_runpod_service as service
from research.kalshi.frankie_boss import sunday_native_runtime as native
from research.kalshi.frankie_boss.tests.test_granite_runpod_tokenizer import synthetic,request
from research.kalshi.frankie_boss.tests.test_granite_durable_job_client import configured,Remote


def test_explicit_long_context_reserves8192_and_keeps_legacy_limit(tmp_path):
    body=request('unchanged',max_tokens=8192)
    proxy._chat(body,'granite42-smoke',service_context=131072)
    with pytest.raises(ValueError):proxy._chat(body,'granite42-smoke')
    proxy._chat(request(max_tokens=8193),'granite42-smoke',service_context=131072)
    ids=[1]*(131072-8192)
    options,_,_=synthetic(tmp_path,ids)
    admit=tokenizer.LocalTokenizerAdmission(tmp_path,context=131072,**options)
    assert admit(body)['output_tokens']==8192
    ids.append(1)
    with pytest.raises(ValueError):admit(body)
    with pytest.raises(ValueError):tokenizer.LocalTokenizerAdmission(tmp_path,**options)(body)


def test_stacked_output8192_reaches_existing_preparation_without_altering_it():
    class Reached(Exception):pass
    class Context:
        def _prepare(self,*args):raise Reached()
    with pytest.raises(Reached):native.prepare_critic_request(Context(),as_of=2,through_cursor=0,source_as_of=1,context_encoding='stacked_v1',service_context=131072,output_tokens=8192)
    with pytest.raises(ValueError):native.prepare_critic_request(Context(),as_of=2,through_cursor=0,source_as_of=1,output_tokens=8192)


def test_capacity_alert_retains_usage_and_propagates_without_redispatch(tmp_path,monkeypatch):
    from research.kalshi.frankie_boss import granite_durable_job_client as jobs
    from research.kalshi.frankie_boss.granite_shadow import IncompleteModelOutput, _serve_request
    class Truncated(Remote):
        def __call__(self,pod,method,path,body,key,timeout):
            self.calls.append((method,path,body))
            job=path.split('/')[3]
            if method=='POST':self.body=body
            if self.body is None:return 404,b'{}'
            result=service._json(dict(object='chat.completion',model='granite42-smoke',usage=dict(prompt_tokens=92427,completion_tokens=38645,total_tokens=131072),choices=[dict(index=0,finish_reason='length',message=dict(role='assistant',content='{"partial":'))])).encode()
            if path.endswith('/result'):return 200,result
            state=dict(schema=jobs.SCHEMA,job_id=job,request_sha256=hashlib.sha256(self.body).hexdigest(),state='completed',result_sha256=hashlib.sha256(result).hexdigest(),result_bytes=len(result),result_status=200)
            return (202 if method=='POST' else 200),service._json(state).encode()
    remote=Truncated();old,req=configured(tmp_path,remote)
    startup=json.loads(old.identity.runtime_versions);startup['environment']['GRANITE_MAX_MODEL_LEN']='131072'
    identity=replace(old.identity,max_tokens=38645,runtime_versions=service._json(startup))
    runtime=dict(outcome='service_ready',pod_id='test123',model='granite42-smoke',runtime=dict(startup=dict(startup=startup)))
    config=replace(old._config,context=131072,runtime_sha256=service._hash(runtime))
    def admit(body):return dict(request_sha256=hashlib.sha256(body).hexdigest(),input_tokens=92427,output_tokens=38645,context=131072,tokenizer_sha256=identity.tokenizer_sha)
    client=service.build_runpod_service(enabled=True,config=config,identity=identity,runtime_receipt=runtime,api_key=old._key,admit_request=admit,exchange=remote,spool_directory=tmp_path)
    req=replace(req,identity=identity)
    with pytest.raises(IncompleteModelOutput) as failure:asyncio.run(_serve_request(req,None,lambda request:client._durable_transport(request,{}),lambda *a:pytest.fail('scorer must not receive partial output')))
    calls=list(remote.calls)
    with pytest.raises(IncompleteModelOutput) as failure:asyncio.run(_serve_request(req,None,lambda request:client._durable_transport(request,{}),lambda *a:pytest.fail('scorer must not receive partial output')))
    assert remote.calls==calls and len([x for x in calls if x[0]=='POST'])==1
    assert json.loads(remote.body)['max_tokens']==38645
    assert failure.value.details['usage_counts']['completion_tokens']==38645
    assert failure.value.details['requested_output_tokens']==38645
    assert failure.value.artifact_path.endswith('output-incomplete.json')
    assert str(failure.value)=='INCOMPLETE RESPONSE — context capacity exhausted'
    assert len(list(tmp_path.glob('*/outcome.json')))==1



def test_remaining_context_selected_once_and_only_max_tokens_changes(tmp_path):
    ids=[1]*92427
    options,calls,_=synthetic(tmp_path,ids)
    admit=tokenizer.LocalTokenizerAdmission(tmp_path,context=131072,**options)
    original=request('same prompt',max_tokens=1)
    body,receipt=admit.with_remaining_output(original)
    assert len(calls)==1
    expected=json.loads(original);expected['max_tokens']=38645
    assert json.loads(body)==expected
    assert receipt['input_tokens']==92427 and receipt['output_tokens']==38645
    assert receipt['request_sha256']==hashlib.sha256(body).hexdigest()
    assert receipt['input_tokens']+receipt['output_tokens']==receipt['context']==131072
    proxy._chat(body,'granite42-smoke',service_context=131072)
    assert admit(request('same prompt',max_tokens=8193))['output_tokens']==8193
    with pytest.raises(ValueError):admit(request('same prompt',max_tokens=38646))
    ids.extend([1]*38645)
    with pytest.raises(ValueError):admit.with_remaining_output(original)




@pytest.mark.parametrize('encoding',['compact_v1','stacked_v1'])
def test_native_request_gate_depends_on_service_context_not_encoding(encoding):
    class Reached(Exception):pass
    class Context:
        def _prepare(self,*args):raise Reached()
    kwargs=dict(as_of=2,through_cursor=0,source_as_of=1,context_encoding=encoding,output_tokens=8193)
    with pytest.raises(Reached):native.prepare_critic_request(Context(),service_context=131072,**kwargs)
    with pytest.raises(ValueError):native.prepare_critic_request(Context(),service_context=4096,**kwargs)
    with pytest.raises(ValueError):native.prepare_critic_request(Context(),service_context=8192,**kwargs)


def test_finite_worker_preserves_typed_incomplete_error(tmp_path,monkeypatch):
    from research.kalshi.frankie_boss.granite_shadow import IncompleteModelOutput, ShadowRequest, _serve_request
    from research.kalshi.frankie_boss.tests.test_granite_open_ended_service import fixture
    raw=service._json(dict(object='chat.completion',model='granite42-smoke',choices=[dict(index=0,finish_reason='length',message=dict(role='assistant',content='partial'))])).encode()
    async def route(snapshot,identity,*,transport,**kwargs):
        req=ShadowRequest('typed-finite',identity,'{}','c'*64,'unchanged prompt',1)
        return await _serve_request(req,None,transport,lambda *a:pytest.fail('partial scoring forbidden'))
    monkeypatch.setattr(service,'serve_context',route)
    events=[];old,_=fixture(tmp_path,lambda *a:(200,raw))
    startup=json.loads(old.identity.runtime_versions)
    runtime=dict(outcome='service_ready',pod_id='test123',model='granite42-smoke',runtime=dict(startup=dict(startup=startup)))
    critic=service.build_runpod_service(enabled=True,config=replace(old._config,request_timeout=1),
        identity=old.identity,runtime_receipt=runtime,api_key=old._key,admit_request=old._admit,
        exchange=old._exchange,event=events.append)
    with pytest.raises(IncompleteModelOutput) as failure:asyncio.run(critic._critique(None,'typed-finite','native_v1',None))
    assert failure.value.details['usage_counts']=={}
    assert any(row.get('error_type')=='IncompleteModelOutput' for row in events)
