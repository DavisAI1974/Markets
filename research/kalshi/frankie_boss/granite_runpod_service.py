"""Exact, per-request-admitted Granite critic transport; no allocation or retries."""
from dataclasses import asdict, dataclass
import hashlib
import http.client
import json
import math
import re
import ssl
import threading
import time

from .granite_runpod_admission import TOKENIZER_VERSIONS
from .granite_runpod_admission import CONTEXT
from .granite_runpod_probe import _remaining, _shutdown
from .granite_sagemaker import _hash, _json
from .granite_shadow import GraniteIdentity, IncompleteModelOutput

MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024
ADMISSION_FIELDS = {'request_sha256', 'input_tokens', 'output_tokens', 'context', 'tokenizer_sha256'}


@dataclass(frozen=True)
class RunpodConfig:
    pod_id: str
    served_model_name: str
    request_timeout: float | None
    runtime_sha256: str
    context: int = CONTEXT
    transport_protocol: str = 'direct_v1'

    def __post_init__(self):
        if self.transport_protocol not in ('direct_v1', 'jobs_v1') or (self.transport_protocol=='jobs_v1' and self.request_timeout is not None):
            raise ValueError('explicit jobs_v1 requires open-ended inference mode')
        if type(self.pod_id) is not str or not re.fullmatch('[a-z0-9]{1,64}', self.pod_id):
            raise ValueError('explicit DNS-compatible approved Pod ID required')
        if type(self.served_model_name) is not str or not re.fullmatch('[A-Za-z0-9_.-]{1,100}', self.served_model_name):
            raise ValueError('explicit served model required')
        if self.request_timeout is not None and (type(self.request_timeout) not in (int, float)
                or not math.isfinite(self.request_timeout) or not 0 < self.request_timeout <= 80):
            raise ValueError('request timeout must be positive and at most 80 seconds')
        if type(self.context) is not int or self.context != CONTEXT:
            raise ValueError('explicit supported 131072 context required')
        if self.request_timeout is not None:
            raise ValueError('long-context candidate requires open-ended transport')
        if type(self.runtime_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', self.runtime_sha256):
            raise ValueError('independently trusted runtime receipt hash required')

    @property
    def config_hash(self):
        schema = 'GRANITE_RUNPOD_SERVICE_V1' if self.request_timeout is not None else 'GRANITE_RUNPOD_OPEN_ENDED_V1'
        fields=asdict(self)
        if self.transport_protocol=='direct_v1':fields.pop('transport_protocol')
        else:schema='GRANITE_RUNPOD_DURABLE_JOBS_V1'
        return _hash(dict(schema=schema, **fields,
            prompt_mode='exact_user_text', enable_thinking=False, stream=False,
            max_request_bytes=MAX_REQUEST, max_response_bytes=MAX_RESPONSE, total_max_attempts=1))


def https_exchange(pod_id, method, path, body, key, timeout):
    """Fixed proxy endpoint, bounded bytes and wall time, no redirect or retry.

    DNS may outlive the caller's timeout; the remaining-time check prevents a late
    POST, and service capacity remains occupied until this function returns.
    """
    if (type(pod_id) is not str or not re.fullmatch('[a-z0-9]{1,64}', pod_id)
            or (method, path) != ('POST', '/v1/chat/completions')
            or type(body) is not bytes or len(body) > MAX_REQUEST
            or type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}', key)
            or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 80):
        raise ValueError('fixed Runpod service transport required')
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPSConnection(pod_id + '-8081.proxy.runpod.net', 443,
        timeout=_remaining(deadline), context=ssl.create_default_context())
    timer = None
    try:
        connection.connect()
        timer = threading.Timer(_remaining(deadline), _shutdown, (connection.sock,))
        timer.daemon = True
        timer.start()
        connection.request(method, path, body, {'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json', 'Content-Length': str(len(body)), 'Connection': 'close'})
        response = connection.getresponse()
        sizes = response.headers.get_all('Content-Length', [])
        if (len(sizes) != 1 or not re.fullmatch('[0-9]{1,10}', sizes[0])
                or response.headers.get_all('Transfer-Encoding')
                or response.headers.get_all('Content-Encoding')
                or response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json'):
            raise ValueError('bounded JSON response required')
        size = int(sizes[0])
        if size > MAX_RESPONSE:
            raise ValueError('provider response exceeds byte bound')
        raw = response.read(size)
        if len(raw) != size:
            raise ValueError('incomplete provider response')
        _remaining(deadline)
        return response.status, raw
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


def _runtime(config, identity, receipt):
    try:
        if type(receipt) is not dict or _hash(receipt) != config.runtime_sha256:
            raise ValueError()
        startup = receipt['runtime']['startup']['startup']
        if (receipt['outcome'] != 'service_ready' or receipt['pod_id'] != config.pod_id
                or receipt['model'] != config.served_model_name
                or startup['schema'] != 'GRANITE_STARTUP_RUNTIME_V1'
                or startup['environment']['GRANITE_MAX_MODEL_LEN'] != str(config.context)
                or startup['environment']['GRANITE_SERVED_MODEL'] != config.served_model_name
                or (config.transport_protocol=='jobs_v1' and startup['environment'].get('GRANITE_TRANSPORT_PROTOCOL')!='jobs_v1')
                or startup['mount']['manifest_sha256'] != identity.base_checkpoint_sha
                or identity.runtime_versions != _json(startup)
                or any(startup['runtime']['packages'].get(k) != v for k, v in TOKENIZER_VERSIONS.items())):
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('trusted runtime differs from configured Pod/model/context/identity') from None


def _admission(value, body, config, identity):
    if (type(value) is not dict or set(value) != ADMISSION_FIELDS
            or value['request_sha256'] != hashlib.sha256(body).hexdigest()
            or value['tokenizer_sha256'] != identity.tokenizer_sha
            or type(value['context']) is not int or value['context'] != config.context
            or type(value['input_tokens']) is not int or not 0 < value['input_tokens'] <= config.context
            or type(value['output_tokens']) is not int or value['output_tokens'] != identity.max_tokens
            or value['input_tokens'] + value['output_tokens'] > config.context):
        raise ValueError('exact untruncated request token admission required')
    return dict(value)


def _error_type(error):
    if isinstance(error, IncompleteModelOutput):
        return 'IncompleteModelOutput'
    for cls in (TimeoutError, ConnectionError, OSError, ValueError, RuntimeError):
        if isinstance(error, cls):
            return cls.__name__
    return 'Exception'


class RunpodShadowService:
    """Critic protocol with one underlying call, retained even after caller timeout.

    admit_request(exact_payload_bytes) must synchronously measure the complete chat
    template using the pinned tokenizer and return ADMISSION_FIELDS. A frozen smoke
    receipt, character estimate or truncated input is not an admission callback.
    event receives only safe phase, request hash, time, counts, status and error type.
    """

    def __init__(self, enabled, config, identity, api_key, runtime_receipt,
                 admit_request, exchange, event):
        if type(enabled) is not bool:
            raise ValueError('enabled must be boolean')
        self._enabled, self._config, self._identity = enabled, config, identity
        self._key, self._admit, self._exchange, self._event = api_key, admit_request, exchange, event
        self._busy = threading.Lock()
        self._config_hash = self._identity_hash = None
        if enabled:
            if type(config) is not RunpodConfig or type(identity) is not GraniteIdentity:
                raise ValueError('enabled service requires pinned config and identity')
            config.__post_init__()
            identity.__post_init__()
            if (identity.thinking or identity.quantization != 'none' or identity.weights_sha is not None
                    or identity.max_tokens > config.context):
                raise ValueError('identity differs from pinned proxy/runtime capabilities')
            if not (getattr(self,'_recovery_only',False) and api_key is None) and (type(api_key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}', api_key)):
                raise ValueError('private proxy credential required')
            if not callable(admit_request) or not callable(exchange) or (event is not None and not callable(event)):
                raise ValueError('per-request admission and transport callbacks required')
            _runtime(config, identity, runtime_receipt)
            self._config_hash, self._identity_hash = config.config_hash, identity.identity_hash

    @property
    def enabled(self):
        return self._enabled

    @property
    def identity(self):
        return self._identity

    @property
    def request_timeout(self):
        return self._config.request_timeout if self.enabled else None

    @property
    def config_hash(self):
        if self.enabled and (self._config.config_hash != self._config_hash
                             or self.identity.identity_hash != self._identity_hash):
            raise ValueError('configured service identity changed')
        return self._config_hash

    async def critique_native(self, snapshot, *, request_id, max_prompt_bytes=None):
        return await self._critique(snapshot, request_id, 'native_v1', max_prompt_bytes)

    async def critique_compact(self, snapshot, *, request_id, max_prompt_bytes=None):
        return await self._critique(snapshot, request_id, 'compact_v1', max_prompt_bytes)

    async def critique_stacked(self, snapshot, *, request_id, max_prompt_bytes=None):
        return await self._critique(snapshot, request_id, 'stacked_v1', max_prompt_bytes)

    async def _critique(self, snapshot, request_id, encoding, max_prompt_bytes):
        if not self.enabled:
            return None
        # The finite direct_v1 critic (one bounded HTTPS exchange under a request timeout) was the retired smoke
        # transport. RunpodConfig no longer admits a finite request_timeout, so an enabled base service cannot be
        # built; the open-ended and durable-jobs subclasses carry the live request paths (Greg, 2026-09-16).
        raise ValueError('finite direct Runpod critic retired with the smoke context; use the open-ended or durable jobs service')


def build_runpod_service(*, enabled=False, config=None, identity=None, api_key=None,
                         runtime_receipt=None, admit_request=None, exchange=None, event=None, spool_directory=None, recovery_only=False,
                         outcome_ready=None):
    if enabled and type(config) is RunpodConfig and config.transport_protocol=='jobs_v1':
        from .granite_durable_job_client import DurableJobRunpodService, https_exchange_jobs
        return DurableJobRunpodService(enabled,config,identity,api_key,runtime_receipt,admit_request,
            exchange or https_exchange_jobs,event,spool_directory=spool_directory,recovery_only=recovery_only,outcome_ready=outcome_ready)
    if outcome_ready is not None:raise ValueError('outcome publication callback requires durable jobs transport')
    if enabled and type(config) is RunpodConfig and config.request_timeout is None:
        from .granite_open_ended_service import OpenEndedRunpodService, https_exchange_open_ended
        return OpenEndedRunpodService(enabled,config,identity,api_key,runtime_receipt,admit_request,
            exchange or https_exchange_open_ended,event,spool_directory=spool_directory,recovery_only=recovery_only)
    if spool_directory is not None or recovery_only:
        raise ValueError('durable spool requires explicit open-ended service mode')
    return RunpodShadowService(enabled, config, identity, api_key, runtime_receipt,
                              admit_request, exchange or https_exchange, event)
