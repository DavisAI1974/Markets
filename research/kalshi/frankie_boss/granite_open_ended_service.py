"""One durable, open-ended critic dispatch per exact attempt; never an auto retry.

Connection establishment stays bounded. Decode/response elapsed time has no cap.
A lost caller can reattach to the same live worker. A lost process with dispatch
but no outcome is ambiguous: this implementation has no provider result lookup.
"""
import asyncio
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import threading
import uuid

from .feedback_cycle import _exclusive
from .granite_context_route import serve_context
from .granite_shadow import PendingTransport,ShadowResponse
from .granite_sagemaker import SageMakerReceipt,_final_text,_hash,_json
from .granite_runpod_service import RunpodShadowService,MAX_REQUEST,MAX_RESPONSE,_admission,_error_type

_WORKERS={}
_WORKERS_LOCK=threading.Lock()


def _save(path,value):
    raw=_json(value).encode()
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('durable critic outcome changed')
        return
    temporary=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    with temporary.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    temporary.rename(path)
    if os.name!='nt':
        descriptor=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def _load(path):
    raw=path.read_bytes();value=json.loads(raw)
    if _json(value).encode()!=raw:raise ValueError('noncanonical critic spool evidence')
    return value


def https_exchange_open_ended(pod_id,method,path,body,key,timeout):
    """A single POST. Finite connect timeout, no total response/decode timeout."""
    if (type(pod_id) is not str or not re.fullmatch('[a-z0-9]{1,64}',pod_id) or
        (method,path)!=('POST','/v1/chat/completions') or type(body) is not bytes or len(body)>MAX_REQUEST or
        type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}',key) or timeout is not None):
        raise ValueError('explicit open-ended exact production request required')
    connection=http.client.HTTPSConnection(pod_id+'-8081.proxy.runpod.net',443,timeout=80,context=ssl.create_default_context())
    try:
        connection.connect()  # Only connection establishment has this finite bound.
        connection.sock.settimeout(None)
        connection.request(method,path,body,{'Authorization':'Bearer '+key,'Content-Type':'application/json',
            'Content-Length':str(len(body)),'Connection':'close'})
        response=connection.getresponse()
        lengths=response.headers.get_all('Content-Length',[])
        if (len(lengths)!=1 or not re.fullmatch('[0-9]{1,10}',lengths[0]) or
            response.headers.get_all('Transfer-Encoding') or response.headers.get_all('Content-Encoding') or
            response.getheader('Content-Type','').split(';')[0].strip().lower()!='application/json'):
            raise ValueError('bounded JSON response required')
        size=int(lengths[0])
        if size>MAX_RESPONSE:raise ValueError('provider response exceeds byte bound')
        raw=response.read(size)
        if len(raw)!=size:raise ValueError('incomplete provider response')
        return response.status,raw
    finally:connection.close()


class OpenEndedRunpodService(RunpodShadowService):
    durable_same_attempt_recovery=True

    def __init__(self,*args,spool_directory,recovery_only=False):
        if type(recovery_only) is not bool:raise ValueError('explicit recovery mode required')
        self._recovery_only=recovery_only
        super().__init__(*args)
        if self._config.request_timeout is not None or spool_directory is None:
            raise ValueError('explicit open-ended mode and durable spool required')
        self.directory=Path(spool_directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)

    @property
    def durable_storage_identity(self):
        return hashlib.sha256(str(self.directory).encode()).hexdigest()

    async def _durable_transport(self,request,evidence):
        if request.identity!=self.identity or request.timeout_seconds is not None:
            raise ValueError('foreign durable critic request')
        body=_json(dict(model=self._config.served_model_name,messages=[dict(role='user',content=request.prompt_text)],
            temperature=self.identity.temperature,max_tokens=self.identity.max_tokens,stream=False,
            chat_template_kwargs=dict(enable_thinking=False))).encode()
        if len(body)>MAX_REQUEST:raise ValueError('exact request exceeds proxy byte capacity')
        key=hashlib.sha256(request.request_id.encode()).hexdigest()
        directory=self.directory/key;directory.mkdir(exist_ok=True)
        intent_path=directory/'dispatch.json';outcome_path=directory/'outcome.json'
        binding=dict(schema='GRANITE_OPEN_ENDED_DISPATCH_V1',attempt_id=request.request_id,
            request_hash=request.request_hash,identity_hash=self.identity.identity_hash,config_hash=self.config_hash,
            body_sha256=hashlib.sha256(body).hexdigest(),body_bytes=len(body))
        worker_key=str(directory)
        with _WORKERS_LOCK:
            with _exclusive(directory/'writer.lock'):
                if intent_path.exists():
                    intent=_load(intent_path)
                    if intent['binding']!=binding:raise ValueError('same critic attempt has different exact request')
                    admitted=_admission(intent['admission'],body,self._config,self.identity)
                else:
                    if self._recovery_only:
                        raise PendingTransport('no retained dispatch to recover; recovery cannot POST')
                    admitted=_admission(self._admit(body),body,self._config,self.identity)
                    intent=dict(binding=binding,admission=admitted)
                    _save(directory/'request.json',json.loads(body))
                    _save(intent_path,intent)  # fsynced BEFORE thread creation or POST
                    event=threading.Event()
                    _WORKERS[worker_key]=event
                    def work():
                        def observe(phase):
                            if self._event is not None:
                                try:self._event(dict(phase=phase,request_hash=request.request_hash,body_sha256=binding['body_sha256']))
                                except Exception:pass
                        try:
                            observe('request_sent')
                            status,raw=self._exchange(self._config.pod_id,'POST','/v1/chat/completions',body,self._key,None)
                            if type(status) is not int or not 100<=status<=599 or type(raw) is not bytes or len(raw)>MAX_RESPONSE:
                                raise ValueError('invalid or oversized provider response')
                            decoded=raw.decode('utf-8',errors='replace')
                            unescaped=re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),decoded)
                            if self._key in unescaped:
                                result=dict(binding=binding,status='fatal',error_type='CredentialEchoRejected')
                            else:
                                result=dict(binding=binding,status='response',http_status=status,
                                    body_base64=base64.b64encode(raw).decode('ascii'),body_sha256=hashlib.sha256(raw).hexdigest())
                            _save(outcome_path,result)  # raw outcome durable BEFORE notifying any caller
                            observe('response_persisted')
                        except BaseException as error:
                            # A network loss cannot establish whether inference ran.
                            # Preserve ambiguity, never turn it into permission to POST again.
                            try:_save(outcome_path,dict(binding=binding,status='ambiguous',error_type=_error_type(error)))
                            except BaseException:pass
                            observe('dispatch_ambiguous')
                        finally:event.set()
                    try:threading.Thread(target=work,daemon=False,name='granite-durable-critic').start()
                    except BaseException:
                        event.set()
                        raise PendingTransport('dispatch intent exists; worker start outcome unknown') from None
                event=_WORKERS.get(worker_key)
        if not outcome_path.exists() and event is None:
            raise PendingTransport('previous process dispatched this attempt; outcome unavailable; no redispatch')
        while not outcome_path.exists():
            if event.is_set():raise PendingTransport('worker ended without recoverable outcome; no redispatch')
            await asyncio.sleep(.1)  # reattachable waiting only; cancellation does not stop the worker
        outcome=_load(outcome_path)
        if outcome['binding']!=binding:raise ValueError('persisted response binding differs')
        if outcome['status']=='ambiguous':raise PendingTransport('dispatch outcome ambiguous; no redispatch')
        if outcome['status']=='fatal':raise RuntimeError('durable provider response rejected')
        raw=base64.b64decode(outcome['body_base64'],validate=True)
        if len(raw)>MAX_RESPONSE or hashlib.sha256(raw).hexdigest()!=outcome['body_sha256']:
            raise ValueError('persisted response bytes changed')
        evidence['provider_json']=_json(dict(response={'HTTPStatusCode':outcome['http_status']},
            body_base64=outcome['body_base64'],admission=admitted))
        if outcome['http_status']!=200:raise RuntimeError('durable provider HTTP failure')
        return ShadowResponse(request.request_hash,self.identity.identity_hash,_final_text(raw,self._config.served_model_name))

    async def _critique(self,snapshot,request_id,encoding,max_prompt_bytes):
        if not self.enabled:return None
        evidence={'provider_json':None}
        async def transport(request):return await self._durable_transport(request,evidence)
        shadow=await serve_context(snapshot,self.identity,context_encoding=encoding,request_id=request_id,
            timeout_seconds=None,transport=transport,max_prompt_bytes=max_prompt_bytes)
        return SageMakerReceipt(shadow,self.config_hash,_hash(dict(config_hash=self.config_hash,
            request_hash=shadow.request.request_hash)),evidence['provider_json'],
            'RuntimeError' if shadow.status=='transport_error' else None)
