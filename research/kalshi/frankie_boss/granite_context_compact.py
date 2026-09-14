"""Lossless readable native context codec; explicit alternative to native V1."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct

try:
    from . import granite_context as native
    from .granite_contract import render_system_text
except ImportError:
    import granite_context as native
    from granite_contract import render_system_text

SCHEMA = 'BOSS_GRANITE_NATIVE_COMPACT_CONTEXT_V1'
PROMPT_VERSION = 'BOSS_GRANITE_NATIVE_COMPACT_PROMPT_V1'


@dataclass(frozen=True)
class DecodeLimits:
    """Resource admission only: oversize inputs reject, never lose evidence.

    Byte accounting conservatively includes every repeated node's encoded bytes.
    These limits establish decoder safety, not model context capacity.
    """
    max_depth: int = 64
    max_expanded_nodes: int = 4_000_000
    max_expanded_bytes: int = 256 * 1024 * 1024
    max_input_bytes: int = 64 * 1024 * 1024

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise ValueError('positive integer compact admission limits required')


DEFAULT_LIMITS = DecodeLimits()


def _float(value):
    bits = struct.pack('>d', value)
    if math.isfinite(value) and struct.pack('>d', float(repr(value))) == bits:
        return repr(value)
    return 'bits:' + bits.hex()


def _unfloat(value):
    if type(value) is not str:
        raise ValueError('float spelling must be text')
    result = struct.unpack('>d', bytes.fromhex(value[5:]))[0] if value.startswith('bits:') else float(value)
    if _float(result) != value:
        raise ValueError('noncanonical float spelling')
    return result


def _encode(value):
    nodes, seen = [], {}

    def intern(node):
        key = native._text(node)
        if key not in seen:
            seen[key] = len(nodes)
            nodes.append(node)
        return seen[key]

    def visit(item):
        kind = type(item)
        if kind is dict:
            keys = intern(['keys', list(item)])
            return intern(['dict', keys, [visit(v) for v in item.values()]])
        if kind in (tuple, list):
            tag = 'tuple' if kind is tuple else 'list'
            if item and all(type(v) is type(item[0]) for v in item) and type(item[0]) in (float, int, bool, str):
                subtype = {float: 'float64', int: 'int', bool: 'bool', str: 'str'}[type(item[0])]
                return intern([tag + ':' + subtype, [_float(v) for v in item] if subtype == 'float64' else list(item)])
            return intern([tag, [visit(v) for v in item]])
        if item is None:
            return intern(['null'])
        if kind is float:
            return intern(['float64', _float(item)])
        if kind is bytes:
            return intern(['bytes', item.hex()])
        if kind in (bool, int, str):
            return intern([{bool: 'bool', int: 'int', str: 'str'}[kind], item])
        raise ValueError('unsupported typed node')

    root = visit(value)
    return dict(nodes=nodes, root=root)


def _decode(tree, *, limits=DEFAULT_LIMITS):
    """Backward references only; canonical re-encoding rejects every alias."""
    if type(tree) is not dict or set(tree) != {'nodes', 'root'} or type(tree['nodes']) is not list:
        raise ValueError('invalid typed node table')
    if type(limits) is not DecodeLimits:
        raise ValueError('explicit compact admission limits required')
    if len(tree['nodes']) > limits.max_expanded_nodes:
        raise ValueError('compact node table exceeds admission limit')
    values = []
    costs = []

    def ref(index):
        if type(index) is not int or not 0 <= index < len(values):
            raise ValueError('invalid or forward node reference')
        return values[index]

    try:
        for node in tree['nodes']:
            if type(node) is not list or not node or type(node[0]) is not str:
                raise ValueError('invalid node')
            tag = node[0]
            if tag == 'dict' and len(node) == 3:
                keys, items = ref(node[1]), node[2]
                if type(keys) is not list or type(items) is not list or len(keys) != len(items):
                    raise ValueError('dictionary shape mismatch')
                value = dict(zip(keys, [ref(i) for i in items]))
            elif tag == 'null' and len(node) == 1:
                value = None
            elif len(node) == 2:
                data = node[1]
                if tag in ('tuple', 'list'):
                    value = [ref(i) for i in data]
                    if tag == 'tuple':
                        value = tuple(value)
                elif ':' in tag:
                    container, subtype = tag.split(':')
                    types = {'int': int, 'bool': bool, 'str': str, 'float64': str}
                    if container not in ('tuple', 'list') or subtype not in types or type(data) is not list or any(type(v) is not types[subtype] for v in data):
                        raise ValueError('invalid homogeneous vector')
                    value = [_unfloat(v) for v in data] if subtype == 'float64' else list(data)
                    if container == 'tuple':
                        value = tuple(value)
                elif tag == 'keys':
                    if type(data) is not list or any(type(k) is not str for k in data) or len(set(data)) != len(data):
                        raise ValueError('invalid ordered keys')
                    value = list(data)
                elif tag == 'float64':
                    value = _unfloat(data)
                elif tag == 'bytes' and type(data) is str:
                    value = bytes.fromhex(data)
                elif tag in ('int', 'bool', 'str') and type(data) is {'int': int, 'bool': bool, 'str': str}[tag]:
                    value = data
                else:
                    raise ValueError('unknown scalar node')
            else:
                raise ValueError('invalid node length')
            # Backward references permit a linear-time expansion bound before
            # canonical re-encoding or native packing recursively walks the DAG.
            refs = ([node[1], *node[2]] if tag == 'dict' else
                    node[1] if tag in ('tuple', 'list') else [])
            children = [costs[index] for index in refs]
            inline = len(node[1]) if tag == 'keys' or ':' in tag else 0
            depth = 1 + max((c[0] for c in children), default=0)
            count = 1 + inline + sum(c[1] for c in children)
            size = len(native._text(node).encode()) + sum(c[2] for c in children)
            if (depth > limits.max_depth or count > limits.max_expanded_nodes
                    or size > limits.max_expanded_bytes):
                raise ValueError('compact expansion exceeds admission limit')
            costs.append((depth, count, size))
            values.append(value)
        result = ref(tree['root'])
        if native._text(_encode(result)) != native._text(tree):
            raise ValueError('noncanonical typed node table')
        return result
    except (TypeError, KeyError, IndexError, OverflowError, struct.error) as exc:
        raise ValueError('malformed typed node table') from exc


def _expand(body, *, limits=DEFAULT_LIMITS):
    reduced = _decode(body['tree'], limits=limits)
    restored = dict(reduced)
    for name in ('registry', 'receipt', 'evidence', 'qsv'):
        restored[name] = native.pack(reduced[name]) if reduced[name] is not None else None
    paths, views = [], []
    for payload in reduced['evidence']:
        row_paths = list(native._paths(payload['record'], '/record')) + list(native._paths(payload['metadata'], '/metadata'))
        row_paths.append('/graph/parent')
        if reduced['qsv'] is not None:
            row_paths.extend('/qsv/' + n.replace('~', '~0').replace('/', '~1') for n in native.QSV_FEATURE_REGISTRY)
        paths.append(sorted(row_paths))
        views.append(list(native._scalar_views(payload['record'], '/record')) + list(native._scalar_views(payload['metadata'], '/metadata')))
    restored.update(field_paths=paths, scalar_views=views)
    return native.parse_native_context(native._text(restored), expected_hash=body['native_hash'])


@dataclass(frozen=True)
class CompactContext:
    text: str
    limits: DecodeLimits = DEFAULT_LIMITS

    @property
    def hash(self):
        return hashlib.sha256(self.text.encode()).hexdigest()

    def native(self):
        return _expand(json.loads(self.text), limits=self.limits)

    def reconstruct(self):
        return self.native().reconstruct()

    def payloads(self):
        return self.native().payloads()

    def fields(self, row):
        return self.native().fields(row)


def compact_native_context(snapshot, *, limits=DEFAULT_LIMITS):
    if type(snapshot) is not native.NativeContext:
        raise TypeError('NativeContext required')
    native.parse_native_context(snapshot.text, expected_hash=snapshot.hash)
    body = json.loads(snapshot.text)
    for name in ('field_paths', 'scalar_views'):
        del body[name]
    for name in ('registry', 'receipt', 'evidence', 'qsv'):
        if body[name] is not None:
            body[name] = native.unpack(body[name])
    tree = _encode(body)
    _decode(tree, limits=limits)
    return CompactContext(native._text(dict(schema=SCHEMA, native_hash=snapshot.hash, tree=tree)), limits)


def parse_compact_context(text, *, expected_hash, limits=DEFAULT_LIMITS):
    native.sha256_digest(expected_hash, 'compact snapshot')
    if type(limits) is not DecodeLimits:
        raise ValueError('explicit compact admission limits required')
    if type(text) is str and len(text.encode()) > limits.max_input_bytes:
        raise ValueError('compact input exceeds admission limit')
    if type(text) is not str or hashlib.sha256(text.encode()).hexdigest() != expected_hash:
        raise ValueError('compact snapshot hash mismatch')
    body = native.parse_json_object(text)
    if body is None or set(body) != {'schema', 'native_hash', 'tree'} or body['schema'] != SCHEMA:
        raise ValueError('invalid compact context schema')
    try:
        rebuilt = compact_native_context(_expand(body, limits=limits), limits=limits)
    except (TypeError, KeyError, IndexError, RuntimeError) as exc:
        raise ValueError('malformed compact native context') from exc
    if rebuilt.text != text:
        raise ValueError('noncanonical compact native context')
    return rebuilt


SYSTEM_TEXT = render_system_text('compact_native_v1')


@dataclass(frozen=True)
class CompactPrompt:
    text: str
    snapshot_hash: str
    version: str = PROMPT_VERSION

    @property
    def system_prompt_hash(self):
        return hashlib.sha256(SYSTEM_TEXT.encode()).hexdigest()


def build_compact_prompt(snapshot, *, max_prompt_bytes=None):
    if type(snapshot) is not CompactContext:
        raise TypeError('CompactContext required')
    parse_compact_context(snapshot.text, expected_hash=snapshot.hash, limits=snapshot.limits)
    text = SYSTEM_TEXT + '\nsnapshot_hash: ' + snapshot.hash + '\ncompact_native_context:\n' + snapshot.text
    if max_prompt_bytes is not None:
        if type(max_prompt_bytes) is not int or max_prompt_bytes <= 0:
            raise ValueError('explicit positive byte capacity required')
        if len(text.encode()) > max_prompt_bytes:
            raise ValueError('compact prompt exceeds configured byte capacity')
    return CompactPrompt(text, snapshot.hash)


def compact_parser_code_hash():
    return hashlib.sha256((Path(__file__).read_bytes() + native.native_parser_code_hash().encode())).hexdigest()


def score_compact(output_text, snapshot):
    if type(snapshot) is not CompactContext:
        raise TypeError('CompactContext required')
    parse_compact_context(snapshot.text, expected_hash=snapshot.hash, limits=snapshot.limits)
    value = native.parse_json_object(output_text)
    if value is None:
        return 0.0, native.Verdict.L0
    if value.keys() != native.REQUIRED_KEYS:
        return 0.2, native.Verdict.L1
    if not native.validate_schema(value):
        return 0.4, native.Verdict.L2
    if value['snapshot_hash'] != snapshot.hash:
        return 0.6, native.Verdict.L3
    original = snapshot.native()
    fields = json.loads(original.text)['field_paths']
    if any(not 0 <= ref['row'] < len(fields) or ref['field'] not in fields[ref['row']] for ref in native.iter_refs(value)):
        return 0.6, native.Verdict.L3
    return 1.0, native.Verdict.L4


training_score = runtime_score = score_compact
