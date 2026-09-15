"""Explicit lossless critic encodings shared by serving and durable replay."""
from dataclasses import dataclass
import hashlib
import math

from research.kalshi.frankie_boss import granite_context as native
from research.kalshi.frankie_boss import granite_context_compact as compact
from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION
from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity, ShadowRequest, _serve_request


@dataclass(frozen=True)
class ContextRoute:
    encoding: str
    method: str
    parse: object
    build_prompt: object
    score: object
    parser_code_hash: object
    system_text: str

    def validate_identity(self, identity):
        identity.__post_init__()
        if (identity.system_prompt_hash != hashlib.sha256(self.system_text.encode()).hexdigest()
                or identity.parser_code_hash != self.parser_code_hash()
                or identity.schema_version != SCHEMA_VERSION):
            raise ValueError('critic does not pin selected context prompt/parser/schema')

    def native(self, snapshot):
        checked = self.parse(snapshot.text, expected_hash=snapshot.hash)
        return checked.native() if self.encoding in ('compact_v1', 'stacked_v1') else checked

    def encode(self, snapshot, *, scope_public=None, prefix_seed=None):
        checked = native.parse_native_context(snapshot.text, expected_hash=snapshot.hash)
        if self.encoding == 'stacked_v1':
            from .granite_context_stacked_route import stacked_native_context
            encoded = stacked_native_context(checked, scope_public=scope_public, prefix_seed=prefix_seed)
        else:
            if scope_public is not None or prefix_seed is not None:
                raise ValueError('derivation options require explicit stacked_v1 route')
            encoded = compact.compact_native_context(checked) if self.encoding == 'compact_v1' else checked
        restored = self.native(encoded)
        if (restored.hash, restored.text) != (snapshot.hash, snapshot.text):
            raise ValueError('context encoding failed exact native inverse verification')
        return encoded


def context_route(encoding='native_v1'):
    if encoding == 'native_v1':
        return ContextRoute(encoding, 'critique_native', native.parse_native_context,
            native.build_native_prompt, native.score_native, native.native_parser_code_hash, native.SYSTEM_TEXT)
    if encoding == 'compact_v1':
        return ContextRoute(encoding, 'critique_compact', compact.parse_compact_context,
            compact.build_compact_prompt, compact.score_compact, compact.compact_parser_code_hash, compact.SYSTEM_TEXT)
    if encoding == 'stacked_v1':
        from . import granite_context_stacked_route as stacked
        return ContextRoute(encoding, 'critique_stacked', stacked.parse_stacked_context,
            stacked.build_stacked_prompt, stacked.score_stacked, stacked.stacked_parser_code_hash, stacked.SYSTEM_TEXT)
    raise ValueError('unknown context_encoding; expected native_v1, compact_v1 or stacked_v1')


async def serve_context(snapshot, identity, *, context_encoding, request_id,
                        timeout_seconds, transport, max_prompt_bytes=None):
    route = context_route(context_encoding)
    if timeout_seconds is not None and (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError('timeout_seconds must be finite and positive')
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError('request_id must be explicit')
    if not isinstance(identity, GraniteIdentity):
        raise TypeError('identity must be GraniteIdentity')
    route.validate_identity(identity)
    prompt = route.build_prompt(snapshot, max_prompt_bytes=max_prompt_bytes)
    request = ShadowRequest(request_id, identity, snapshot.text, snapshot.hash, prompt.text, None if timeout_seconds is None else float(timeout_seconds))
    return await _serve_request(request, snapshot, transport, route.score)


async def serve_compact_shadow(snapshot, identity, **kwargs):
    return await serve_context(snapshot, identity, context_encoding='compact_v1', **kwargs)
