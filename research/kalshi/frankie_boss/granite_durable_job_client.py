"""Bounded HTTP operations around a durable, open-ended remote inference job."""
import asyncio
import base64
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import ssl
import threading
import time
import uuid
from .feedback_cycle import _exclusive
from .granite_open_ended_service import OpenEndedRunpodService, _save, _load
from .granite_runpod_service import MAX_REQUEST, MAX_RESPONSE, _admission
from .granite_sagemaker import _json, _final_text
from .granite_shadow import PendingTransport, ShadowResponse, IncompleteModelOutput

SCHEMA='GRANITE_DURABLE_JOB_V1'
HTTP_TIMEOUT=80
POLL_SECONDS=2


class RequestNotDispatched(ConnectionError):
    """Local validation or connection failed; request() was never entered."""
    def __init__(self,message,*,local_validation=False):
        self.local_validation=local_validation
        super().__init__(message)


class JobAttention(PendingTransport):
    """An actionable same-job condition, with durable secret-free evidence."""
    def __init__(self,code,job_id,artifact_path,*,details=None):
        self.code,self.job_id,self.artifact_path=code,job_id,artifact_path
        self.details=dict(details or {})
        super().__init__(code)


def https_exchange_jobs(pod_id,method,path,body,key,timeout):
    if (type(pod_id) is not str or not re.fullmatch('[a-z0-9]{1,64}',pod_id) or
        method not in ('GET','POST') or type(path) is not str or not re.fullmatch(r'/v1/jobs/[0-9a-f]{64}(?:/result)?',path) or
        (method=='POST' and path.endswith('/result')) or type(body) is not bytes or len(body)>MAX_REQUEST or
        (method=='GET' and body) or type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}',key) or
        type(timeout) not in (int,float) or not 0<timeout<=80):
        raise RequestNotDispatched('local request validation failed before network',local_validation=True)
    started=time.monotonic()
    connection=timer=None
    try:
        try:
            connection=http.client.HTTPSConnection(pod_id+'-8081.proxy.runpod.net',443,timeout=timeout,context=ssl.create_default_context())
        except Exception:
            raise RequestNotDispatched('local TLS/client setup failed before request',local_validation=True) from None
        try:connection.connect()
        except Exception:raise RequestNotDispatched('connection establishment failed before request') from None
        remaining=timeout-(time.monotonic()-started)
        if remaining<=0:raise RequestNotDispatched('connection completed after HTTP deadline before request')
        def abort():
            try:connection.sock.shutdown(2)
            except Exception:pass
        try:
            timer=threading.Timer(remaining,abort);timer.daemon=True;timer.start()
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Content-Length':str(len(body)),'Connection':'close'}
            if method=='POST':headers['X-Granite-Request-SHA256']=hashlib.sha256(body).hexdigest()
        except Exception:
            raise RequestNotDispatched('local request setup failed before request',local_validation=True) from None
        # Any error from this boundary onward is acceptance-ambiguous.
        connection.request(method,path,body,headers)
        response=connection.getresponse()
        lengths=response.headers.get_all('Content-Length') or []
        if (response.headers.get('Transfer-Encoding') is not None or response.headers.get('Content-Encoding') is not None or
            len(lengths)!=1 or not re.fullmatch('[0-9]{1,10}',lengths[0])):
            raise ValueError('bounded job response required')
        size=int(lengths[0])
        if size>MAX_RESPONSE:raise ValueError('job response exceeds byte bound')
        raw=response.read(size)
        if len(raw)!=size:raise http.client.IncompleteRead(raw,size-len(raw))
        return response.status,raw
    finally:
        try:
            if timer is not None:timer.cancel()
        except Exception:pass
        try:
            if connection is not None:connection.close()
        except Exception:pass


class DurableJobRunpodService(OpenEndedRunpodService):
    def __init__(self,*args,outcome_ready=None,**kwargs):
        if outcome_ready is not None and not callable(outcome_ready):raise ValueError('outcome callback must be callable')
        self._outcome_ready=outcome_ready
        super().__init__(*args,**kwargs)

    @property
    def durable_storage_identity(self):
        return hashlib.sha256((_json(dict(protocol='jobs_v1',directory=str(self.directory)))+
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest()).encode()).hexdigest()

    async def _publish_saved_outcome(self,value):
        if self._outcome_ready is None:return
        try:
            await asyncio.to_thread(self._outcome_ready,value)
        except JobAttention:
            raise
        except Exception as error:
            # Cleanup failure cannot replace a persisted terminal model outcome.
            # Preserve a safe pointer even when its own directory cannot be made.
            raise JobAttention('RETAINED_COMPLETION_PUBLICATION_PENDING',value['job_id'],
                value['outcome_path'],details=dict(error_type=type(error).__name__)) from None

    async def _durable_transport(self,request,evidence):
        if request.identity!=self.identity or request.timeout_seconds is not None or self._config.transport_protocol!='jobs_v1':
            raise ValueError('foreign durable job request')
        body=_json(dict(model=self._config.served_model_name,messages=[dict(role='user',content=request.prompt_text)],
            temperature=self.identity.temperature,max_tokens=self.identity.max_tokens,stream=False,
            chat_template_kwargs=dict(enable_thinking=False))).encode()
        if len(body)>MAX_REQUEST:raise ValueError('exact job request exceeds byte capacity')
        body_hash=hashlib.sha256(body).hexdigest()
        job_id=hashlib.sha256(_json(dict(attempt=request.request_id,request_hash=request.request_hash,
            config_hash=self.config_hash,body_sha256=body_hash)).encode()).hexdigest()
        # One local slot per controller attempt: changed bytes must be refused,
        # never become a second remote identity after an ambiguous first dispatch.
        directory=self.directory/hashlib.sha256(request.request_id.encode()).hexdigest();directory.mkdir(exist_ok=True)
        binding=dict(schema='GRANITE_DURABLE_CLIENT_JOB_V1',attempt_id=request.request_id,job_id=job_id,
            request_hash=request.request_hash,identity_hash=self.identity.identity_hash,config_hash=self.config_hash,
            body_sha256=body_hash,body_bytes=len(body))
        outcome_path=directory/'outcome.json'
        with _exclusive(directory/'writer.lock'):
            intent_path=directory/'dispatch.json'
            if intent_path.exists():
                intent=_load(intent_path)
                if intent['binding']!=binding:raise ValueError('retained job identity differs')
                admitted=_admission(intent['admission'],body,self._config,self.identity)
            else:
                if self._recovery_only:raise PendingTransport('no retained job exists to recover')
                admitted=_admission(self._admit(body),body,self._config,self.identity)
                _save(directory/'request.json',json.loads(body))
                _save(intent_path,dict(binding=binding,admission=admitted))
        # Every invocation starts with GET, including a lost process/POST response.
        # A 404 permits only this exact idempotent job create, never direct inference.
        last_phase=None
        def observe(phase):
            nonlocal last_phase
            if phase==last_phase:return
            last_phase=phase
            _save(directory/('observation-'+uuid.uuid4().hex+'.json'),dict(binding=binding,phase=phase))
            if self._event is not None:
                try:self._event(dict(phase=phase,request_hash=request.request_hash,body_sha256=body_hash,job_id=job_id))
                except Exception:pass
        def uncertain_submission():
            return any(not p.with_name(p.name.replace('submit-intent-','submit-not-dispatched-')).exists()
                for p in directory.glob('submit-intent-*.json'))
        def attention(code,**details):
            marker=directory/('attention-'+uuid.uuid4().hex+'.json')
            _save(marker,dict(binding=binding,code=code,**details))
            observe(code.lower())
            raise JobAttention(code,job_id,str(marker.resolve()))
        async def exchange(method,path,payload,*,known_not_dispatched=False):
            submission=None
            if method=='POST':
                submission=uuid.uuid4().hex
                with _exclusive(directory/'writer.lock'):
                    if not known_not_dispatched and ((directory/'remote-accepted.json').exists() or uncertain_submission()):
                        raise PendingTransport('earlier acceptance may exist; missing remote state cannot permit POST')
                    _save(directory/('submit-intent-'+submission+'.json'),dict(binding=binding))
            try:
                status,raw=await asyncio.to_thread(self._exchange,self._config.pod_id,method,path,payload,self._key,HTTP_TIMEOUT)
            except RequestNotDispatched as error:
                if submission is not None:
                    with _exclusive(directory/'writer.lock'):
                        _save(directory/('submit-not-dispatched-'+submission+'.json'),dict(binding=binding))
                if error.local_validation:
                    attention('LOCAL_JOB_REQUEST_REFUSED_NOT_DISPATCHED')
                raise
            if type(status) is not int or type(raw) is not bytes or len(raw)>MAX_RESPONSE:
                raise ValueError('invalid bounded HTTP outcome')
            if status in (401,403):attention('REMOTE_JOB_CREDENTIAL_REJECTED',http_status=status)
            if status in (408,429,500,502,503,504,520,521,522,523,524):
                raise ConnectionError('transient proxy response; query same durable job')
            return status,raw
        def save_outcome(value):
            with _exclusive(directory/'writer.lock'):_save(outcome_path,value)
        def control(raw):
            value=json.loads(raw)
            if (type(value) is not dict or value.get('schema')!=SCHEMA or value.get('job_id')!=job_id or
                value.get('request_sha256')!=body_hash or value.get('state') not in
                ('accepted','running','not_dispatched','ambiguous','completed','failed')):
                raise ValueError('remote job control identity differs')
            # Once the durable server acknowledged this identity, a later 404
            # indicates missing state or wrong routing, never a fresh job slot.
            with _exclusive(directory/'writer.lock'):
                _save(directory/'remote-accepted.json',dict(binding=binding))
            return value
        not_dispatched_count=0
        while not outcome_path.exists():
            if self._key is None:raise PendingTransport('same remote job requires an in-memory credential to recover')
            try:
                status,raw=await exchange('GET','/v1/jobs/'+job_id,b'')
                if status==404:
                    if (directory/'remote-accepted.json').exists() or uncertain_submission():
                        raise PendingTransport('previously possible or accepted remote job disappeared; no recreation')
                    observe('job_not_found_same_id_create')
                    status,raw=await exchange('POST','/v1/jobs/'+job_id,body)
                    if status!=202:raise ValueError('idempotent job acceptance failed')
                elif status!=200:raise ValueError('job status request failed')
                state=control(raw);phase=state['state'];observe('job_'+phase)
                if phase=='not_dispatched':
                    not_dispatched_count+=1
                    if not_dispatched_count>=3:
                        attention('REMOTE_BACKEND_NOT_DISPATCHED_REQUIRES_ATTENTION',observations=not_dispatched_count)
                    await asyncio.sleep(min(60,POLL_SECONDS*2**(not_dispatched_count-1)))
                    status,raw=await exchange('POST','/v1/jobs/'+job_id,body,known_not_dispatched=True)
                    if status!=202:raise ValueError('safe undispatched job resume failed')
                    control(raw)
                elif phase=='ambiguous':
                    raise PendingTransport('remote dispatch is ambiguous; same job retained, no redispatch')
                elif phase=='failed':
                    if (set(state)-{'schema','job_id','request_sha256','state','accepted_at','updated_at','dispatch_at'} or
                        any(type(state[k]) not in (int,float) or not math.isfinite(state[k]) for k in
                            ('accepted_at','updated_at','dispatch_at') if k in state)):
                        raise ValueError('terminal control must contain only bounded public state')
                    save_outcome(dict(binding=binding,status='fatal',error_type='RemoteJobFailed',control=state,
                        control_sha256=hashlib.sha256(_json(state).encode()).hexdigest()))
                elif phase=='completed':
                    digest=state.get('result_sha256');size=state.get('result_bytes');code=state.get('result_status')
                    if (type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest) or
                        type(size) is not int or not 0<=size<=MAX_RESPONSE or type(code) is not int or not 100<=code<=599):
                        raise ValueError('completed job lacks exact result witness')
                    result_status,result=await exchange('GET','/v1/jobs/'+job_id+'/result',b'')
                    if result_status==200 and len(result)<size:
                        raise ConnectionError('short durable result transfer; retry same result GET')
                    if result_status!=200 or len(result)!=size or hashlib.sha256(result).hexdigest()!=digest:
                        raise ValueError('remote job result bytes differ')
                    decoded=result.decode('utf-8',errors='replace')
                    unescaped=re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),decoded)
                    if self._key in unescaped:raise ValueError('credential echo rejected')
                    save_outcome(dict(binding=binding,status='response',http_status=code,
                        body_base64=base64.b64encode(result).decode('ascii'),body_sha256=digest))
                    observe('job_result_persisted')
                    continue
                if phase!='not_dispatched':not_dispatched_count=0
            except PendingTransport:raise
            except RequestNotDispatched:
                observe('job_http_not_dispatched')
            except (ConnectionError,OSError,TimeoutError,http.client.HTTPException):
                observe('job_http_outcome_unknown_query_same_id')
            except (ValueError,TypeError,KeyError,json.JSONDecodeError):
                raise PendingTransport('remote job response invalid; retain same job for inspection') from None
            await asyncio.sleep(POLL_SECONDS)
        outcome=_load(outcome_path)
        if outcome['binding']!=binding:raise ValueError('persisted job outcome identity differs')
        if outcome['status']=='fatal':
            control=outcome.get('control');digest=outcome.get('control_sha256')
            if (type(control) is not dict or control.get('schema')!=SCHEMA or control.get('job_id')!=job_id or
                control.get('request_sha256')!=body_hash or control.get('state')!='failed' or
                hashlib.sha256(_json(control).encode()).hexdigest()!=digest):
                raise JobAttention('REMOTE_JOB_TERMINAL_FAILURE_EVIDENCE_INCOMPLETE',job_id,str(outcome_path.resolve()))
            details={}
            if self._outcome_ready is not None:
                try:
                    await self._publish_saved_outcome(dict(protocol='jobs_v1',outcome_kind='terminal_control',
                        job_id=job_id,request_sha256=body_hash,outcome_sha256=digest,http_status=None,
                        outcome_path=str(outcome_path.resolve())))
                except JobAttention as cleanup:
                    details['cleanup_pending']=dict(code=cleanup.code,artifact_path=cleanup.artifact_path)
            raise JobAttention('REMOTE_JOB_TERMINAL_FAILURE',job_id,str(outcome_path.resolve()),details=details)
        raw=base64.b64decode(outcome['body_base64'],validate=True)
        if len(raw)>MAX_RESPONSE or hashlib.sha256(raw).hexdigest()!=outcome['body_sha256']:
            raise ValueError('persisted job result bytes differ')
        evidence['provider_json']=_json(dict(response={'HTTPStatusCode':outcome['http_status']},
            body_base64=outcome['body_base64'],admission=admitted,job_id=job_id))
        async def publish_outcome():
            if self._outcome_ready is not None:
                await self._publish_saved_outcome(dict(protocol='jobs_v1',outcome_kind='model_response',job_id=job_id,
                    request_sha256=body_hash,outcome_sha256=outcome['body_sha256'],http_status=outcome['http_status'],
                    outcome_path=str(outcome_path.resolve())))
        if outcome['http_status']!=200:
            await publish_outcome()
            raise RuntimeError('durable backend HTTP failure')
        try:
            text = _final_text(raw,self._config.served_model_name)
        except IncompleteModelOutput as error:
            details = dict(error.details, requested_output_tokens=admitted['output_tokens'],
                input_tokens=admitted['input_tokens'], context=admitted['context'],
                result_sha256=outcome['body_sha256'])
            marker = directory/'output-incomplete.json'
            with _exclusive(directory/'writer.lock'):
                _save(marker, dict(schema='GRANITE_INCOMPLETE_MODEL_OUTPUT_V1',
                    binding=binding, details=details, raw_outcome_path=str(outcome_path.resolve())))
            try:await publish_outcome()
            except JobAttention as cleanup:
                details=dict(details,cleanup_pending=dict(code=cleanup.code,artifact_path=cleanup.artifact_path))
            raise IncompleteModelOutput(details, str(marker.resolve())) from None
        except ValueError:
            await publish_outcome()
            raise
        await publish_outcome()
        return ShadowResponse(request.request_hash,self.identity.identity_hash,text)
