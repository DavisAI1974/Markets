"""Caller-pinned, cooperative async Granite shadow boundary; no model connector.

Pins and transport echoes are caller/transport assertions, not loaded-weight
attestations. Timeout bounds waiting, not external work or blocking Python code.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Awaitable, Callable

from . import granite_parser
from .granite_output_schema import SCHEMA_VERSION
from .granite_prompt import build_prompt
from .state_serialization import SerializedState


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def parser_code_hash() -> str:
    """Digest the local parser and its schema dependency as one versioned bundle."""
    from . import granite_output_schema
    return _hash({module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                  for module in (granite_parser, granite_output_schema)})


@dataclass(frozen=True)
class GraniteIdentity:
    base_checkpoint_sha: str
    weights_sha: str | None
    tokenizer_sha: str
    quantization: str
    runtime_versions: str
    thinking: bool
    temperature: float
    max_tokens: int
    system_prompt_hash: str
    schema_version: str
    parser_code_hash: str
    tune_receipt_hash: str | None

    def __post_init__(self) -> None:
        for name in ('base_checkpoint_sha', 'weights_sha', 'tokenizer_sha',
                     'system_prompt_hash', 'parser_code_hash', 'tune_receipt_hash'):
            value = getattr(self, name)
            if value is None and name in ('weights_sha', 'tune_receipt_hash'):
                continue
            if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
                raise ValueError(f'{name} must be a lowercase SHA256')
        if (self.weights_sha is None) != (self.tune_receipt_hash is None):
            raise ValueError('tuned weights and tune receipt must be supplied together')
        for name in ('quantization', 'runtime_versions', 'schema_version'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f'{name} must be explicit')
        if type(self.thinking) is not bool:
            raise ValueError('thinking must be boolean')
        if type(self.temperature) not in (int, float) or self.temperature != 0:
            raise ValueError('inference temperature must be zero')
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise ValueError('max_tokens must be a positive integer')

    @property
    def identity_hash(self) -> str:
        return _hash({'schema': 'GRANITE_SHADOW_IDENTITY_V1', **asdict(self)})


@dataclass(frozen=True)
class ShadowRequest:
    request_id: str
    identity: GraniteIdentity
    snapshot_text: str
    snapshot_hash: str
    prompt_text: str
    timeout_seconds: float

    @property
    def request_hash(self) -> str:
        return _hash({'schema': 'GRANITE_SHADOW_REQUEST_V1', **asdict(self)})


@dataclass(frozen=True)
class ShadowResponse:
    request_hash: str
    identity_hash: str
    text: str


@dataclass(frozen=True)
class ShadowReceipt:
    request: ShadowRequest
    status: str
    response: ShadowResponse | None = None
    verdict: str | None = None


def _discard(task: asyncio.Task) -> None:
    """Retrieve late exceptions without allowing late output to become accepted."""
    if not task.cancelled():
        task.exception()


async def serve_shadow(
    snapshot: SerializedState, identity: GraniteIdentity, *, request_id: str,
    timeout_seconds: float,
    transport: Callable[[ShadowRequest], Awaitable[ShadowResponse]],
) -> ShadowReceipt:
    """Invoke an explicitly provided async transport and return diagnostic evidence.

    Invalid caller configuration raises before invoking transport. Output failures
    are isolated receipts. External cancellation propagates. No retry is implicit.
    """
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be finite and positive')
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError('request_id must be explicit')
    if not isinstance(identity, GraniteIdentity):
        raise TypeError('identity must be GraniteIdentity')
    identity.__post_init__()
    prompt = build_prompt(snapshot)
    if (identity.system_prompt_hash != prompt.system_prompt_hash
            or identity.schema_version != SCHEMA_VERSION
            or identity.parser_code_hash != parser_code_hash()):
        raise ValueError('identity does not match local prompt/schema/parser')
    request = ShadowRequest(request_id, identity, snapshot.text, snapshot.hash,
                            prompt.text, float(timeout_seconds))
    return await _serve_request(request, snapshot, transport, granite_parser.runtime_score)


async def serve_native_shadow(snapshot, identity: GraniteIdentity, *, request_id: str,
                              timeout_seconds: float, transport, max_prompt_bytes=None) -> ShadowReceipt:
    """Serve exact native evidence with its distinct prompt/parser identity."""
    from .granite_context import build_native_prompt, native_parser_code_hash, score_native
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be finite and positive')
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError('request_id must be explicit')
    if not isinstance(identity, GraniteIdentity):
        raise TypeError('identity must be GraniteIdentity')
    identity.__post_init__()
    prompt = build_native_prompt(snapshot, max_prompt_bytes=max_prompt_bytes)
    if (identity.system_prompt_hash != prompt.system_prompt_hash
            or identity.schema_version != SCHEMA_VERSION
            or identity.parser_code_hash != native_parser_code_hash()):
        raise ValueError('identity does not match native prompt/schema/parser')
    request = ShadowRequest(request_id, identity, snapshot.text, snapshot.hash,
                            prompt.text, float(timeout_seconds))
    return await _serve_request(request, snapshot, transport, score_native)


async def _serve_request(request, snapshot, transport, scorer):
    identity, timeout_seconds = request.identity, request.timeout_seconds

    async def invoke() -> ShadowResponse:
        return await transport(request)

    task = asyncio.create_task(invoke())
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
        if not done:
            task.cancel()
            task.add_done_callback(_discard)
            return ShadowReceipt(request, 'timeout')
        try:
            response = task.result()
        except asyncio.CancelledError:
            return ShadowReceipt(request, 'transport_error')
        except Exception:
            return ShadowReceipt(request, 'transport_error')
    except asyncio.CancelledError:
        task.cancel()
        task.add_done_callback(_discard)
        raise
    if not isinstance(response, ShadowResponse) or any(
            not isinstance(getattr(response, field), str)
            for field in ('request_hash', 'identity_hash', 'text')):
        return ShadowReceipt(request, 'malformed_response')
    if response.request_hash != request.request_hash or response.identity_hash != identity.identity_hash:
        return ShadowReceipt(request, 'binding_mismatch', response)
    _, verdict = scorer(response.text, snapshot)
    return ShadowReceipt(request, 'accepted' if verdict is granite_parser.Verdict.L4 else 'rejected',
                         response, verdict.name)
