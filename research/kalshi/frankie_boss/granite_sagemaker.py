"""Opt-in pinned SageMaker vLLM chat transport for Granite shadow critique."""
from __future__ import annotations

import asyncio
import base64
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
import json
import math
import re
import threading

from .granite_shadow import (GraniteIdentity, ShadowReceipt, ShadowResponse,
                             serve_shadow, serve_native_shadow)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class SageMakerConfig:
    region: str
    endpoint_name: str
    served_model_name: str
    openai_chat_supported: bool
    connect_timeout: float
    read_timeout: float
    request_timeout: float

    def __post_init__(self):
        for field in ('region', 'endpoint_name', 'served_model_name'):
            value = getattr(self, field)
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ValueError(f'explicit {field} required')
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', self.endpoint_name):
            raise ValueError('valid SageMaker endpoint name required')
        if self.openai_chat_supported is not True:
            raise ValueError('endpoint vLLM chat compatibility must be confirmed')
        for field in ('connect_timeout', 'read_timeout', 'request_timeout'):
            value = getattr(self, field)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{field} must be finite and positive')

    @property
    def config_hash(self):
        return _hash(dict(schema='GRANITE_SAGEMAKER_CHAT_V1', **asdict(self),
            boto3=version('boto3'), botocore=version('botocore'), total_max_attempts=1,
            prompt_mode='exact_user_text', enable_thinking=False, stream=False))


def _client(config):
    import boto3
    from botocore.config import Config
    return boto3.client('sagemaker-runtime', region_name=config.region,
        config=Config(connect_timeout=config.connect_timeout, read_timeout=config.read_timeout,
                      retries={'total_max_attempts': 1, 'mode': 'standard'}))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate provider JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite provider JSON constant')


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('nonfinite provider JSON number')
    return number


def _final_text(body, model):
    raw = json.loads(body.decode('utf-8'), object_pairs_hook=_pairs,
                     parse_constant=_constant, parse_float=_float)
    if (type(raw) is not dict or raw.get('object') != 'chat.completion'
            or raw.get('model') != model or type(raw.get('choices')) is not list
            or len(raw['choices']) != 1):
        raise ValueError('unsupported or foreign chat completion')
    choice = raw['choices'][0]
    if (type(choice) is not dict or type(choice.get('index')) is not int
            or choice['index'] != 0 or choice.get('finish_reason') != 'stop'):
        raise ValueError('incomplete or ambiguous chat completion')
    message = choice.get('message')
    optional = {'reasoning', 'reasoning_content', 'tool_calls', 'function_call',
                'refusal', 'audio', 'annotations'}
    if (type(message) is not dict or message.get('role') != 'assistant'
            or type(message.get('content')) is not str
            or set(message) - {'role', 'content'} - optional
            or any(message.get(key) not in (None, '', []) for key in optional)):
        raise ValueError('unsupported reasoning, tools or nontext output')
    return message['content']


@dataclass(frozen=True)
class SageMakerReceipt:
    shadow: ShadowReceipt
    config_hash: str
    call_hash: str
    provider_json: str | None
    error_type: str | None


class SageMakerShadowService:
    """One underlying SDK call at a time, including calls whose caller timed out."""

    def __init__(self, enabled, config, identity, client_factory):
        if type(enabled) is not bool:
            raise ValueError('enabled must be boolean')
        self._enabled, self._config, self._identity = enabled, config, identity
        self._client_factory = client_factory
        self._sdk_client = None
        self._busy = threading.Lock()
        self._config_hash = None
        if enabled:
            if type(config) is not SageMakerConfig or type(identity) is not GraniteIdentity:
                raise ValueError('enabled service requires explicit config and identity')
            config.__post_init__()
            identity.__post_init__()
            if identity.thinking:
                raise ValueError('thinking mode unsupported by text-only transport')
            self._config_hash = config.config_hash

    @property
    def enabled(self):
        return self._enabled

    @property
    def identity(self):
        return self._identity

    @property
    def config_hash(self):
        if self.enabled and self._config.config_hash != self._config_hash:
            raise ValueError('SDK/config identity changed; construct a new service')
        return self._config_hash

    async def critique(self, snapshot, *, request_id):
        return await self._critique(snapshot, request_id, serve_shadow)

    async def critique_native(self, snapshot, *, request_id, max_prompt_bytes=None):
        return await self._critique(snapshot, request_id, serve_native_shadow,
                                    max_prompt_bytes=max_prompt_bytes)

    async def _critique(self, snapshot, request_id, serve, **kwargs):
        if not self.enabled:
            return None
        config_hash = self.config_hash
        config, identity = self._config, self.identity
        evidence = {'provider_json': None, 'error_type': None}

        async def transport(request):
            if request.identity != identity or request.timeout_seconds != config.request_timeout:
                raise ValueError('foreign shadow request configuration')
            if not self._busy.acquire(blocking=False):
                evidence['error_type'] = 'Busy'
                raise RuntimeError('underlying SageMaker request still in flight')
            loop = asyncio.get_running_loop()
            future = loop.create_future()

            def deliver(result, error):
                if not future.done():
                    if error is None:
                        future.set_result(result)
                    else:
                        future.set_exception(error)

            def work():
                result = error = None
                try:
                    if self._sdk_client is None:
                        self._sdk_client = self._client_factory(config)
                    payload = dict(model=config.served_model_name,
                        messages=[dict(role='user', content=request.prompt_text)],
                        temperature=identity.temperature, max_tokens=identity.max_tokens,
                        stream=False, chat_template_kwargs=dict(enable_thinking=False))
                    raw = self._sdk_client.invoke_endpoint(
                        EndpointName=config.endpoint_name, ContentType='application/json',
                        Accept='application/json', Body=_json(payload).encode(),
                        CustomAttributes=f'shadow_request_hash={request.request_hash};transport_config_hash={config_hash}',
                        InferenceId=_hash(dict(config_hash=config_hash, request_hash=request.request_hash)))
                    metadata = {key: value for key, value in raw.items() if key != 'Body'}
                    evidence['provider_json'] = _json(dict(response=metadata, body_base64=None))
                    stream = raw['Body']
                    try:
                        body = stream.read()
                        if type(body) is bytes:
                            evidence['provider_json'] = _json(dict(response=metadata,
                                body_base64=base64.b64encode(body).decode('ascii')))
                    finally:
                        stream.close()
                    if type(body) is not bytes:
                        raise ValueError('provider body must be bytes')
                    if raw.get('ContentType', '').split(';', 1)[0].strip().lower() != 'application/json':
                        raise ValueError('provider returned non-JSON content type')
                    text = _final_text(body, config.served_model_name)
                    result = ShadowResponse(request.request_hash, identity.identity_hash, text)
                except Exception as exc:
                    evidence['error_type'] = type(exc).__name__
                    if hasattr(exc, 'response'):
                        evidence['provider_json'] = _json(exc.response)
                    error = exc
                finally:
                    self._busy.release()
                    try:
                        loop.call_soon_threadsafe(deliver, result, error)
                    except RuntimeError:
                        pass  # Closed caller loop: late output cannot become accepted.

            try:
                threading.Thread(target=work, daemon=True, name='granite-sagemaker').start()
            except Exception:
                self._busy.release()
                raise
            return await future

        shadow = await serve(snapshot, identity, request_id=request_id,
            timeout_seconds=config.request_timeout, transport=transport, **kwargs)
        return SageMakerReceipt(shadow, config_hash,
            _hash(dict(config_hash=config_hash, request_hash=shadow.request.request_hash)),
            evidence['provider_json'], evidence['error_type'])


def build_sagemaker_service(*, enabled=False, config=None, identity=None, client_factory=None):
    """Lazy factory; the default client uses only the standard AWS credential chain."""
    return SageMakerShadowService(enabled, config, identity, client_factory or _client)
