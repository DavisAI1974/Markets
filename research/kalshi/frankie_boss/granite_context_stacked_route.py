"""Explicit stacked V1 critic route with an exact native inverse."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from . import granite_context as native
from . import granite_context_compact as compact
from . import granite_context_stacked as codec

SCHEMA = 'BOSS_GRANITE_STACKED_ROUTE_V1'
PROMPT_VERSION = 'BOSS_GRANITE_STACKED_ROUTE_PROMPT_V1'
SYSTEM_TEXT = (codec.GRAMMAR + "\nReconstruct field_paths as JSON Pointers to every record and metadata leaf, plus /graph/parent and available /qsv feature names. References below address those reconstructed fields.\n" + native.SYSTEM_TEXT)


def _expand(body, limits):
    reduced = codec.decode(body['codec'], limits=limits)
    # Reuse the accepted exact field-path/scalar-view reconstruction.
    return compact._expand(dict(native_hash=body['native_hash'], tree=compact._encode(reduced)))


@dataclass(frozen=True)
class StackedContext:
    text: str
    limits: codec.DecodeLimits = codec.DEFAULT_LIMITS

    @property
    def hash(self):
        return hashlib.sha256(self.text.encode()).hexdigest()

    def native(self):
        return _expand(json.loads(self.text), self.limits)

    def reconstruct(self):
        return self.native().reconstruct()

    def payloads(self):
        return self.native().payloads()

    def fields(self, row):
        return self.native().fields(row)


def stacked_native_context(snapshot, *, scope_public=None, prefix_seed=None, limits=codec.DEFAULT_LIMITS):
    checked = native.parse_native_context(snapshot.text, expected_hash=snapshot.hash)
    reduced = json.loads(checked.text)
    for name in ('field_paths', 'scalar_views'):
        del reduced[name]
    for name in ('registry', 'receipt', 'evidence', 'qsv'):
        if reduced[name] is not None:
            reduced[name] = native.unpack(reduced[name])
    envelope = codec.encode(reduced, scope_public=scope_public, prefix_seed=prefix_seed, limits=limits)
    result = StackedContext(native._text(dict(schema=SCHEMA, native_hash=checked.hash, codec=envelope)), limits)
    if result.native().text != checked.text:
        raise ValueError('stacked context failed exact native inverse')
    return result


def parse_stacked_context(text, *, expected_hash, limits=codec.DEFAULT_LIMITS):
    native.sha256_digest(expected_hash, 'stacked snapshot')
    if type(limits) is not codec.DecodeLimits or type(text) is not str:
        raise ValueError('explicit stacked text and admission limits required')
    if len(text.encode()) > limits.max_input_bytes or hashlib.sha256(text.encode()).hexdigest() != expected_hash:
        raise ValueError('stacked context byte admission/hash mismatch')
    body = native.parse_json_object(text)
    if body is None or set(body) != {'schema', 'native_hash', 'codec'} or body['schema'] != SCHEMA:
        raise ValueError('invalid stacked context schema')
    if native._text(body) != text:
        raise ValueError('noncanonical stacked context serialization')
    _expand(body, limits)
    return StackedContext(text, limits)


@dataclass(frozen=True)
class StackedPrompt:
    text: str
    snapshot_hash: str
    version: str = PROMPT_VERSION

    @property
    def system_prompt_hash(self):
        return hashlib.sha256(SYSTEM_TEXT.encode()).hexdigest()


def build_stacked_prompt(snapshot, *, max_prompt_bytes=None):
    if type(snapshot) is not StackedContext:
        raise TypeError('StackedContext required')
    parse_stacked_context(snapshot.text, expected_hash=snapshot.hash, limits=snapshot.limits)
    text = SYSTEM_TEXT + '\nsnapshot_hash: ' + snapshot.hash + '\nstacked_native_context:\n' + snapshot.text
    if max_prompt_bytes is not None:
        if type(max_prompt_bytes) is not int or max_prompt_bytes <= 0 or len(text.encode()) > max_prompt_bytes:
            raise ValueError('stacked prompt exceeds configured byte capacity')
    return StackedPrompt(text, snapshot.hash)


def stacked_parser_code_hash():
    return hashlib.sha256(Path(__file__).read_bytes() + codec.codec_code_hash().encode() +
        codec.grammar_hash().encode() + compact.compact_parser_code_hash().encode()).hexdigest()


def score_stacked(output_text, snapshot):
    if type(snapshot) is not StackedContext:
        raise TypeError('StackedContext required')
    parse_stacked_context(snapshot.text, expected_hash=snapshot.hash, limits=snapshot.limits)
    value = native.parse_json_object(output_text)
    if value is None:
        return 0.0, native.Verdict.L0
    if value.keys() != native.REQUIRED_KEYS:
        return 0.2, native.Verdict.L1
    if not native.validate_schema(value):
        return 0.4, native.Verdict.L2
    if value['snapshot_hash'] != snapshot.hash:
        return 0.6, native.Verdict.L3
    fields = json.loads(snapshot.native().text)['field_paths']
    if any(not 0 <= ref['row'] < len(fields) or ref['field'] not in fields[ref['row']] for ref in native.iter_refs(value)):
        return 0.6, native.Verdict.L3
    return 1.0, native.Verdict.L4
