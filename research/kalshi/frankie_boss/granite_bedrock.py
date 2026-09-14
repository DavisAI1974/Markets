"""Opt-in Bedrock Converse service for the Granite shadow critic role."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
import json
import math
import threading

from .granite_shadow import GraniteIdentity, ShadowReceipt, ShadowResponse, serve_shadow, serve_native_shadow


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class BedrockConfig:
    region: str
    model_id: str
    converse_text_supported: bool
    connect_timeout: float
    read_timeout: float
    request_timeout: float

    def __post_init__(self):
        for field in ('region', 'model_id'):
            value = getattr(self, field)
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ValueError(f'explicit {field} required')
        if ':prompt/' in self.model_id or 'prompt-router/' in self.model_id:
            raise ValueError('managed prompts and prompt routers unsupported')
        if self.converse_text_supported is not True:
            raise ValueError('deployed model Converse text compatibility must be confirmed')
        for field in ('connect_timeout', 'read_timeout', 'request_timeout'):
            value = getattr(self, field)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{field} must be finite and positive')

    @property
    def config_hash(self):
        return _hash({'schema': 'GRANITE_BEDROCK_CONVERSE_V1', **asdict(self),
                      'boto3': version('boto3'), 'botocore': version('botocore'),
                      'total_max_attempts': 1, 'prompt_mode': 'exact_user_text'})


def _client(config):
    import boto3
    from botocore.config import Config
    return boto3.client('bedrock-runtime', region_name=config.region,
                        config=Config(connect_timeout=config.connect_timeout,
                                      read_timeout=config.read_timeout,
                                      retries={'total_max_attempts': 1, 'mode': 'standard'}))


@dataclass(frozen=True)
class BedrockReceipt:
    shadow: ShadowReceipt
    config_hash: str
    call_hash: str
    provider_json: str | None
    error_type: str | None


class BedrockShadowService:
    """Controller entry point. One underlying call at a time, including timeouts.

    Injected client factories are trusted and must honor supplied SDK settings.
    Echoes below are locally constructed; AWS does not attest the caller's pins.
    """

    def __init__(self, enabled, config, identity, client_factory):
        if type(enabled) is not bool:
            raise ValueError('enabled must be boolean')
        self._enabled = enabled
        self._config = config
        self._identity = identity
        self._client_factory = client_factory
        self._busy = threading.Lock()
        self._sdk_client = None
        if enabled:
            if type(config) is not BedrockConfig or type(identity) is not GraniteIdentity:
                raise ValueError('enabled service requires explicit config and identity')
            config.__post_init__()
            identity.__post_init__()
            if identity.thinking:
                raise ValueError('thinking mode unsupported by text-only Converse adapter')
            self._config_hash = config.config_hash

    @property
    def enabled(self):
        return self._enabled

    @property
    def identity(self):
        return self._identity

    @property
    def request_timeout(self):
        return self._config.request_timeout if self._enabled else None

    @property
    def config_hash(self):
        if not self._enabled:
            return None
        if self._config.config_hash != self._config_hash:
            raise ValueError('SDK/config identity changed; construct a new service')
        return self._config_hash

    async def critique(self, snapshot, *, request_id):
        return await self._critique(snapshot, request_id=request_id, serve=serve_shadow)

    async def critique_native(self, snapshot, *, request_id):
        return await self._critique(snapshot, request_id=request_id, serve=serve_native_shadow)

    async def critique_compact(self, snapshot, *, request_id, max_prompt_bytes=None):
        from .granite_context_route import serve_compact_shadow
        return await self._critique(snapshot, request_id=request_id, serve=serve_compact_shadow,
                                    max_prompt_bytes=max_prompt_bytes)

    async def _critique(self, snapshot, *, request_id, serve, **kwargs):
        if not self._enabled:
            return None
        config, identity = self._config, self._identity
        if config.config_hash != self._config_hash:
            raise ValueError('SDK/config identity changed; construct a new service')
        evidence = {'provider_json': None, 'error_type': None}

        async def transport(request):
            if request.identity != identity or request.timeout_seconds != config.request_timeout:
                raise ValueError('foreign request configuration')
            if not self._busy.acquire(blocking=False):
                evidence['error_type'] = 'Busy'
                raise RuntimeError('underlying Bedrock request still in flight')
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
                    raw = self._sdk_client.converse(
                        modelId=config.model_id,
                        messages=[{'role': 'user', 'content': [{'text': request.prompt_text}]}],
                        inferenceConfig={'temperature': identity.temperature, 'maxTokens': identity.max_tokens},
                        requestMetadata={'shadow_request_hash': request.request_hash,
                                         'transport_config_hash': self._config_hash})
                    evidence['provider_json'] = _json(raw)
                    message = raw.get('output', {}).get('message', {})
                    content = message.get('content')
                    if (raw.get('stopReason') != 'end_turn' or message.get('role') != 'assistant'
                            or type(content) is not list or len(content) != 1
                            or type(content[0]) is not dict or set(content[0]) != {'text'}
                            or type(content[0]['text']) is not str):
                        raise ValueError('unsupported or incomplete Converse output')
                    result = ShadowResponse(request.request_hash, identity.identity_hash, content[0]['text'])
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
                        pass  # Caller loop closed after timeout; never publish late output.

            try:
                threading.Thread(target=work, daemon=True, name='granite-bedrock').start()
            except Exception:
                self._busy.release()
                raise
            return await future

        shadow = await serve(snapshot, identity, request_id=request_id,
                                    timeout_seconds=config.request_timeout, transport=transport, **kwargs)
        return BedrockReceipt(shadow, self._config_hash,
                              _hash({'config_hash': self._config_hash,
                                     'request_hash': shadow.request.request_hash}),
                              evidence['provider_json'], evidence['error_type'])


def build_bedrock_service(*, enabled=False, config=None, identity=None, client_factory=None):
    """Lazy factory: constructing a service never constructs an SDK client."""
    return BedrockShadowService(enabled, config, identity, client_factory or _client)


def main(argv=None):
    """Explicit live integration harness, with caller-owned config and state files.

    Credentials use boto3's normal provider chain; no secrets belong in config.
    This entry point makes one real SDK call and writes evidence, never trades.
    """
    import argparse
    from pathlib import Path
    from .state_serialization import SerializedState, SCHEMA_VERSION as STATE_SCHEMA
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--config', required=True, help='JSON object: config and identity')
    parser.add_argument('--snapshot', required=True, help='canonical synthetic state JSON')
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--receipt', required=True, help='new output file; never overwritten')
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.config).read_text(encoding='utf-8'))
    if type(payload) is not dict or set(payload) != {'config', 'identity'}:
        raise ValueError('live file must contain exactly config and identity')
    service = build_bedrock_service(enabled=True, config=BedrockConfig(**payload['config']),
                                    identity=GraniteIdentity(**payload['identity']))
    state = SerializedState(STATE_SCHEMA, Path(args.snapshot).read_bytes().decode('utf-8'))
    # Validate all local pins and input before SDK credential discovery or invocation.
    from .granite_prompt import build_prompt
    build_prompt(state)
    with Path(args.receipt).open('x', encoding='utf-8', newline='\n') as output:
        receipt = asyncio.run(service.critique(state, request_id=args.request_id))
        output.write(_json(asdict(receipt)) + '\n')
    return 0 if receipt.shadow.status == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())
