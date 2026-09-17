"""New jobs-v1 seams; all exchanges synthetic, no inference or cloud calls."""
import asyncio
from dataclasses import replace
import hashlib
import http.client
import json
import pytest
from research.kalshi.frankie_boss import granite_durable_job_client as jobs
from research.kalshi.frankie_boss import granite_runpod_service as service
from research.kalshi.frankie_boss.tests.test_granite_open_ended_service import fixture, raw_response, KEY
from research.kalshi.frankie_boss.granite_shadow import PendingTransport


def configured(tmp_path, exchange, *, key=KEY, recovery=False):
    old, request = fixture(tmp_path, exchange)
    startup=json.loads(old.identity.runtime_versions)
    startup['environment']['GRANITE_TRANSPORT_PROTOCOL']='jobs_v1'
    identity=replace(old.identity,runtime_versions=service._json(startup))
    runtime=dict(outcome='service_ready',pod_id='test123',model='granite42-smoke',runtime=dict(startup=dict(startup=startup)))
    config=replace(old._config,runtime_sha256=service._hash(runtime),transport_protocol='jobs_v1')
    client=service.build_runpod_service(enabled=True,config=config,identity=identity,runtime_receipt=runtime,
        api_key=key,admit_request=old._admit,exchange=exchange,spool_directory=tmp_path,recovery_only=recovery)
    return client,replace(request,identity=identity)


class Remote:
    def __init__(self): self.body=None;self.calls=[];self.state='running';self.lost_accept=False
    def __call__(self,pod,method,path,body,key,timeout):
        self.calls.append((method,path,body));assert timeout==80 and key==KEY
        job=path.split('/')[3]
        if path.endswith('/result'):return 200,raw_response()
        if method=='POST':
            assert self.body is None or self.body==body
            self.body=body
            if self.lost_accept:self.lost_accept=False;raise http.client.RemoteDisconnected('lost acceptance')
        if self.body is None:return 404,b'{}'
        control=dict(schema=jobs.SCHEMA,job_id=job,request_sha256=hashlib.sha256(self.body).hexdigest(),state=self.state)
        if self.state=='completed':control.update(result_sha256=hashlib.sha256(raw_response()).hexdigest(),result_bytes=len(raw_response()),result_status=200)
        return (202 if method=='POST' else 200),service._json(control).encode()


def test_lost_acceptance_queries_same_job_and_replays_without_key(tmp_path,monkeypatch):
    remote=Remote();remote.lost_accept=True;remote.state='completed'
    monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    client,request=configured(tmp_path,remote)
    expected=asyncio.run(client._durable_transport(request,{}))
    assert expected.text=='retained result'
    assert [m for m,_,_ in remote.calls]==['GET','POST','GET','GET']
    assert len({p.removesuffix('/result') for _,p,_ in remote.calls})==1
    replay,_=configured(tmp_path,lambda *a:pytest.fail('disk replay performed HTTP'),key=None,recovery=True)
    assert asyncio.run(replay._durable_transport(request,{}))==expected
    assert KEY not in ''.join(p.read_text() for p in tmp_path.glob('*/*.json'))


def test_same_attempt_changed_body_is_refused_before_http(tmp_path):
    remote=Remote();remote.state='completed';client,request=configured(tmp_path,remote)
    asyncio.run(client._durable_transport(request,{}));calls=len(remote.calls)
    with pytest.raises(ValueError):asyncio.run(client._durable_transport(replace(request,prompt_text='changed'),{}))
    assert len(remote.calls)==calls


def test_ambiguous_backend_never_posts_again_and_pending_resume_uses_fresh_key(tmp_path):
    remote=Remote();remote.state='ambiguous';client,request=configured(tmp_path,remote)
    with pytest.raises(PendingTransport):asyncio.run(client._durable_transport(request,{}))
    remote.calls.clear()
    recovery,_=configured(tmp_path,remote,key=None,recovery=True)
    with pytest.raises(PendingTransport):asyncio.run(recovery._durable_transport(request,{}))
    assert remote.calls==[]
    recovery,_=configured(tmp_path,remote,recovery=True)
    with pytest.raises(PendingTransport):asyncio.run(recovery._durable_transport(request,{}))
    assert [m for m,_,_ in remote.calls]==['GET']
    remote.state='completed'
    assert asyncio.run(recovery._durable_transport(request,{})).text=='retained result'


def test_exact_result_witness_mismatch_stays_pending_without_outcome(tmp_path):
    remote=Remote();remote.state='completed'
    def exchange(*args):
        status,raw=remote(*args)
        return (status,b'x'*len(raw_response())) if args[2].endswith('/result') else (status,raw)
    client,request=configured(tmp_path,exchange)
    with pytest.raises(PendingTransport):asyncio.run(client._durable_transport(request,{}))
    assert not list(tmp_path.glob('*/outcome.json'))


def test_default_direct_hash_omits_the_protocol_field_and_carries_the_only_context():
    config=service.RunpodConfig('test123','granite42-smoke',None,'a'*64)
    expected=service._hash(dict(schema='GRANITE_RUNPOD_OPEN_ENDED_V1',pod_id='test123',served_model_name='granite42-smoke',
        request_timeout=None,runtime_sha256='a'*64,context=131072,prompt_mode='exact_user_text',enable_thinking=False,stream=False,
        max_request_bytes=service.MAX_REQUEST,max_response_bytes=service.MAX_RESPONSE,total_max_attempts=1))
    assert config.config_hash==expected
    with pytest.raises(ValueError,match='open-ended'):service.RunpodConfig('test123','granite42-smoke',80,'a'*64)


def test_predispatch_connect_failure_queries_before_create_and_transient_get_recovers(tmp_path,monkeypatch):
    remote=Remote();remote.state='completed';failures=[jobs.RequestNotDispatched('before request'),(524,b'gateway timeout')]
    monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        if failures:
            item=failures.pop(0)
            if isinstance(item,Exception):raise item
            return item
        return remote(*args)
    client,request=configured(tmp_path,exchange)
    assert asyncio.run(client._durable_transport(request,{})).text=='retained result'
    assert [m for m,_,_ in remote.calls]==['GET','POST','GET']


def test_http_protocol_loss_after_acceptance_gets_same_job(tmp_path,monkeypatch):
    remote=Remote();remote.state='completed';first=True
    monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        nonlocal first
        result=remote(*args)
        if args[1]=='POST' and first:
            first=False;raise http.client.IncompleteRead(b'partial',20)
        return result
    client,request=configured(tmp_path,exchange)
    assert asyncio.run(client._durable_transport(request,{})).text=='retained result'
    assert [m for m,_,_ in remote.calls]==['GET','POST','GET','GET']


def test_https_connect_failure_never_enters_request(monkeypatch):
    calls=[]
    class Connection:
        def connect(self):raise OSError('synthetic connection failure')
        def request(self,*args):calls.append(args)
        def close(self):pass
    monkeypatch.setattr(jobs.http.client,'HTTPSConnection',lambda *a,**k:Connection())
    with pytest.raises(jobs.RequestNotDispatched):jobs.https_exchange_jobs('test123','POST','/v1/jobs/'+'a'*64,b'{}',KEY,80)
    assert calls==[]


def test_cancelled_polling_reattaches_to_late_remote_result_without_post(tmp_path,monkeypatch):
    remote=Remote();monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    client,request=configured(tmp_path,remote)
    async def scenario():
        task=asyncio.create_task(client._durable_transport(request,{}))
        while remote.body is None:await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        posts=sum(method=='POST' for method,_,_ in remote.calls)
        remote.state='completed'
        fresh,_=configured(tmp_path,remote,recovery=True)
        assert (await fresh._durable_transport(request,{})).text=='retained result'
        assert sum(method=='POST' for method,_,_ in remote.calls)==posts==1
    asyncio.run(scenario())


def test_server_known_not_dispatched_allows_only_same_job_post(tmp_path,monkeypatch):
    remote=Remote();remote.state='not_dispatched';monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        if args[1]=='POST' and remote.body is not None:remote.state='completed'
        return remote(*args)
    client,request=configured(tmp_path,exchange)
    assert asyncio.run(client._durable_transport(request,{})).text=='retained result'
    posts=[(path,body) for method,path,body in remote.calls if method=='POST']
    assert len(posts)==2 and posts[0]==posts[1]


def test_observed_remote_job_then_404_never_recreates_prior_dispatch(tmp_path,monkeypatch):
    remote=Remote();monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    client,request=configured(tmp_path,remote)
    async def scenario():
        task=asyncio.create_task(client._durable_transport(request,{}))
        while not list(tmp_path.glob('*/observation-*.json')) or remote.body is None:await asyncio.sleep(.001)
        # Wait until a valid running control is durably observed before cancelling.
        while not any('job_running' in p.read_text() for p in tmp_path.glob('*/observation-*.json')):await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        calls=[]
        def lost_store(*args):
            calls.append(args[1])
            if args[1]=='POST':pytest.fail('known accepted job must not be recreated')
            return 404,b'{}'
        fresh,_=configured(tmp_path,lost_store,recovery=True)
        with pytest.raises(PendingTransport):await fresh._durable_transport(request,{})
        assert calls==['GET']
    asyncio.run(scenario())


def test_lost_unobserved_acceptance_then_404_does_not_post_twice(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        method=args[1];calls.append(method)
        if method=='POST':
            if calls.count('POST')>1:pytest.fail('unknown first acceptance must not permit another POST')
            raise ConnectionError('accepted response lost before any observed control')
        return 404,b'{}'
    client,request=configured(tmp_path,exchange)
    with pytest.raises(PendingTransport):asyncio.run(client._durable_transport(request,{}))
    assert calls==['GET','POST','GET']


def test_proven_post_connect_failure_records_permission_for_same_id_after_404(tmp_path,monkeypatch):
    remote=Remote();remote.state='completed';first=True;monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        nonlocal first
        if args[1]=='POST' and first:
            first=False;raise jobs.RequestNotDispatched('connection failed before request boundary')
        return remote(*args)
    client,request=configured(tmp_path,exchange)
    assert asyncio.run(client._durable_transport(request,{})).text=='retained result'
    assert len(list(tmp_path.glob('*/submit-intent-*.json')))==2
    assert len(list(tmp_path.glob('*/submit-not-dispatched-*.json')))==1
    assert sum(method=='POST' for method,_,_ in remote.calls)==1


def test_short_result_get_retries_same_saved_remote_result(tmp_path,monkeypatch):
    remote=Remote();remote.state='completed';short=True;monkeypatch.setattr(jobs,'POLL_SECONDS',0)
    def exchange(*args):
        nonlocal short
        status,raw=remote(*args)
        if args[2].endswith('/result') and short:short=False;return status,raw[:-1]
        return status,raw
    client,request=configured(tmp_path,exchange)
    assert asyncio.run(client._durable_transport(request,{})).text=='retained result'
    assert sum(method=='POST' for method,_,_ in remote.calls)==1


def test_local_argument_validation_is_proven_before_network(monkeypatch):
    monkeypatch.setattr(jobs.http.client,'HTTPSConnection',lambda *a,**k:pytest.fail('local refusal opened network'))
    with pytest.raises(jobs.RequestNotDispatched) as caught:
        jobs.https_exchange_jobs('test123','POST','/v1/chat/completions',b'{}',KEY,80)
    assert caught.value.local_validation is True


def test_local_post_guard_refusal_keeps_safe_retry_proof_and_attention(tmp_path):
    def exchange(*args):
        if args[1]=='POST':raise jobs.RequestNotDispatched('host admission guard',local_validation=True)
        return 404,b'{}'
    client,request=configured(tmp_path,exchange)
    with pytest.raises(jobs.JobAttention) as caught:asyncio.run(client._durable_transport(request,{}))
    assert caught.value.code=='LOCAL_JOB_REQUEST_REFUSED_NOT_DISPATCHED'
    assert len(list(tmp_path.glob('*/submit-not-dispatched-*.json')))==1


def test_recovery_auth_refusal_identifies_fresh_credential_action(tmp_path):
    client,request=configured(tmp_path,lambda *a:(401,b'{}'))
    with pytest.raises(jobs.JobAttention) as caught:asyncio.run(client._durable_transport(request,{}))
    assert caught.value.code=='REMOTE_JOB_CREDENTIAL_REJECTED'
    assert json.loads(open(caught.value.artifact_path).read())['http_status']==401


def test_repeated_backend_not_dispatched_backs_off_then_requires_attention(tmp_path,monkeypatch):
    remote=Remote();remote.state='not_dispatched';delays=[]
    async def pause(delay):delays.append(delay)
    monkeypatch.setattr(jobs.asyncio,'sleep',pause)
    client,request=configured(tmp_path,remote)
    with pytest.raises(jobs.JobAttention) as caught:asyncio.run(client._durable_transport(request,{}))
    assert caught.value.code=='REMOTE_BACKEND_NOT_DISPATCHED_REQUIRES_ATTENTION'
    assert max(delays)>jobs.POLL_SECONDS and sum(method=='POST' for method,_,_ in remote.calls)==3


def test_incomplete_alert_survives_completion_publication_failure(tmp_path):
    from research.kalshi.frankie_boss.granite_shadow import IncompleteModelOutput
    raw=service._json(dict(object='chat.completion',model='granite42-smoke',choices=[dict(index=0,finish_reason='length',
        message=dict(role='assistant',content='partial'))],usage=dict(prompt_tokens=10,completion_tokens=1200,total_tokens=1210))).encode()
    remote=Remote();remote.state='completed'
    def exchange(*args):
        status,body=remote(*args)
        if args[2].endswith('/result'):return status,raw
        if status!=404:
            value=json.loads(body);value.update(result_bytes=len(raw),result_sha256=hashlib.sha256(raw).hexdigest());body=service._json(value).encode()
        return status,body
    client,request=configured(tmp_path,exchange)
    def publish(outcome):
        assert list(tmp_path.glob('*/output-incomplete.json'))
        raise jobs.JobAttention('RETAINED_COMPLETION_PUBLICATION_PENDING',outcome['job_id'],'retained-publication-intent.json')
    client._outcome_ready=publish
    with pytest.raises(IncompleteModelOutput) as caught:asyncio.run(client._durable_transport(request,{}))
    assert caught.value.details['cleanup_pending']['code']=='RETAINED_COMPLETION_PUBLICATION_PENDING'
    assert list(tmp_path.glob('*/outcome.json')) and list(tmp_path.glob('*/output-incomplete.json'))


def test_terminal_failed_control_publishes_exact_control_then_alerts_without_scoring(tmp_path):
    remote=Remote();remote.state='failed';published=[]
    client,request=configured(tmp_path,remote)
    def publish(value):
        saved=json.loads(open(value['outcome_path']).read())
        assert value['outcome_kind']=='terminal_control' and saved['control']['state']=='failed'
        assert value['outcome_sha256']==hashlib.sha256(service._json(saved['control']).encode()).hexdigest()
        published.append(value)
    client._outcome_ready=publish
    with pytest.raises(jobs.JobAttention) as caught:asyncio.run(client._durable_transport(request,{}))
    assert caught.value.code=='REMOTE_JOB_TERMINAL_FAILURE' and len(published)==1
    assert not any(path.endswith('/result') for _,path,_ in remote.calls)


@pytest.mark.parametrize('phase',['path','tls','connection','timer'])
def test_all_local_setup_failures_are_proven_unsent(phase,monkeypatch):
    calls=[]
    class Connection:
        def connect(self):pass
        def request(self,*args):calls.append(args)
        def close(self):pass
    class Timer:
        def __init__(self,*args):pass
        def start(self):raise RuntimeError('cannot start local timer')
        def cancel(self):pass
    monkeypatch.setattr(jobs.http.client,'HTTPSConnection',lambda *a,**k:Connection())
    if phase=='tls':monkeypatch.setattr(jobs.ssl,'create_default_context',lambda:(_ for _ in ()).throw(RuntimeError('TLS setup')))
    if phase=='connection':monkeypatch.setattr(jobs.http.client,'HTTPSConnection',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('constructor')))
    if phase=='timer':monkeypatch.setattr(jobs.threading,'Timer',Timer)
    with pytest.raises(jobs.RequestNotDispatched) as caught:
        jobs.https_exchange_jobs('test123','POST',None if phase=='path' else '/v1/jobs/'+'a'*64,b'{}',KEY,80)
    assert caught.value.local_validation is True and calls==[]


@pytest.mark.parametrize('result_kind', ['length', 'failed', 'stop'])
def test_untyped_cleanup_io_error_never_masks_persisted_model_outcome(tmp_path,result_kind):
    from research.kalshi.frankie_boss.granite_shadow import IncompleteModelOutput
    remote=Remote();remote.state='failed' if result_kind=='failed' else 'completed'
    raw=service._json(dict(object='chat.completion',model='granite42-smoke',choices=[
        dict(index=0,finish_reason=result_kind,message=dict(role='assistant',content='partial'))])).encode()
    def exchange(*args):
        status,body=remote(*args)
        if result_kind=='length':
            if args[2].endswith('/result'):return status,raw
            if status!=404:
                value=json.loads(body);value.update(result_bytes=len(raw),result_sha256=hashlib.sha256(raw).hexdigest())
                body=service._json(value).encode()
        return status,body
    client,request=configured(tmp_path,exchange)
    def unavailable_directory(value):raise OSError('cleanup directory unavailable')
    client._outcome_ready=unavailable_directory
    expected=IncompleteModelOutput if result_kind=='length' else jobs.JobAttention
    with pytest.raises(expected) as caught:asyncio.run(client._durable_transport(request,{}))
    if result_kind=='failed':assert caught.value.code=='REMOTE_JOB_TERMINAL_FAILURE'
    elif result_kind=='stop':assert caught.value.code=='RETAINED_COMPLETION_PUBLICATION_PENDING'
    if result_kind!='stop':assert caught.value.details['cleanup_pending']['code']=='RETAINED_COMPLETION_PUBLICATION_PENDING'
    assert list(tmp_path.glob('*/outcome.json'))
    if result_kind=='length':assert list(tmp_path.glob('*/output-incomplete.json'))
