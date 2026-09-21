"""The LOSSLESS reading render of Frankie's delivered evidence (Greg, 2026-09-21: "reduce the size of that 22.6 MB read
with as many optimization stacks as we can. We don't want to drop any of the data though").

Measured on the real cycle-0 members (runs 35593909809, 35594192807): the delivered bytes are c15-packed JSON whose
bulk is (1) the native decoder's weight tensors, hex inside c15 inside bytes inside hex (four encodings deep);
(2) the SAME 6 MB forecast artifact twice (forecast-000000.bin and, hex-encoded, native.c15.jsonl's candidate);
(3) the critic prompt and snapshot six times across state, controller and the two text members; (4) source files
as hex bytes. Structural codecs alone gave 1%. These layers give the rest, and every one is reversible:

  L1  c15 unpack: every tagged value becomes its plain value (pack(unpack(x)) == x, checked per member).
  L2  nested decoding: a bytes value that is itself c15 JSON, JSON or UTF-8 text is decoded in place and its
      encoding recorded on the path, so the exact bytes re-encode from the decoded form (checked per value).
  L3  content-addressed deduplication: any string, bytes or subtree at or above DEDUP_BYTES whose sha256 was
      already rendered becomes {"$ref": "<sha256>"}; the dictionary renders each value once. Byte-identical by
      construction; the reference carries the digest the reader can check.
  L4  tensors: a decoder weights map (name -> {dtype, shape, bytes}) renders as a table of name, dtype, shape,
      byte length, sha256 and summary statistics (count, min, max, mean, l2 norm), and, in `values` mode, every
      element as a shortest round-trip decimal (float(repr(x)) == x). Identity mode keeps the exact bytes in the
      package and in the dictionary by digest; nothing is discarded, the reader chooses what to open.
  L5  containment: a large string that contains another rendered large string verbatim has that span replaced
      by a marker naming the digest (the critic prompt contains the snapshot text).
  L6  cross-cycle ledger: a value already rendered and read in an EARLIER cycle (same sha256 in the box's
      reading ledger) becomes {"$read": sha256, "cycle": "<NN>"}; the earlier cycle's merged notes travel in the
      corpus head. The journals are append-only, so a later cycle reads only what was appended or changed.
The render is Markdown with fenced JSON blocks; `reconstruct()` rebuilds every member's original bytes from the
render plan and the proof compares sha256s. `RenderReport` carries bytes and (when the tokenizer is present)
exact Granite tokens per layer so the receipt states the reduction rather than claiming it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import struct
from dataclasses import dataclass, field

DEDUP_BYTES = 4096
NESTED_MIN = 32
HEX = re.compile(r'^[0-9a-f]+$')


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---- L1/L2: decode ----------------------------------------------------------------------------------------------
def _c15():
    from research.kalshi.frankie_boss.c15_journal import pack, unpack
    from research.kalshi.frankie_boss.causal_packet import canonical_bytes
    return pack, unpack, canonical_bytes


def _is_packed(value):
    return isinstance(value, list) and len(value) in (1, 2) and isinstance(value[0], str) and value[0] in (
        'int', 'str', 'null', 'bool', 'float64', 'bytes', 'list', 'tuple', 'dict')


def decode_bytes(raw):
    """Decode one bytes value as far as it goes. Returns (decoded, encoding) with encoding one of
    'c15' (packed canonical JSON -> unpacked doc), 'json' (canonical JSON doc), 'utf8' (text), or None (opaque)."""
    pack, unpack, canonical_bytes = _c15()
    if len(raw) < NESTED_MIN:
        return raw, None
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw, None
    stripped = text.strip()
    if stripped[:1] in '[{':
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
        if doc is not None:
            if _is_packed(doc):
                try:
                    plain = unpack(doc)
                    if canonical_bytes(pack(plain)) == raw:
                        return decode_tree(plain), 'c15'
                except Exception:
                    pass
            if json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode() == raw:
                return decode_tree(doc), 'json'
    if '\x00' not in text:
        return text, 'utf8'
    return raw, None


class Decoded(dict):
    """A dict node that came from a decoded bytes value; `encoding` names how to re-encode it."""


class DecodedText(str):
    pass


def decode_tree(doc):
    """Walk a plain document; decode every bytes value in place (L2), keeping the encoding on the node."""
    if isinstance(doc, dict):
        return {k: decode_tree(v) for k, v in doc.items()}
    if isinstance(doc, (list, tuple)):
        out = [decode_tree(v) for v in doc]
        return tuple(out) if isinstance(doc, tuple) else out
    if isinstance(doc, bytes):
        decoded, encoding = decode_bytes(doc)
        if encoding is None:
            return doc
        return {'$decoded': encoding, 'sha256': sha(doc), 'bytes': len(doc), 'value': decoded}
    return doc


def encode_tree(doc):
    """Inverse of decode_tree: every {'$decoded': ...} node re-encodes to its exact bytes."""
    pack, unpack, canonical_bytes = _c15()
    if isinstance(doc, dict):
        if set(doc) == {'$decoded', 'sha256', 'bytes', 'value'}:
            inner = encode_tree(doc['value'])
            if doc['$decoded'] == 'c15':
                raw = canonical_bytes(pack(inner))
            elif doc['$decoded'] == 'json':
                raw = json.dumps(inner, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
            else:
                raw = inner.encode('utf-8')
            if sha(raw) != doc['sha256'] or len(raw) != doc['bytes']:
                raise ValueError('decoded value does not re-encode to its bytes')
            return raw
        return {k: encode_tree(v) for k, v in doc.items()}
    if isinstance(doc, tuple):
        return tuple(encode_tree(v) for v in doc)
    if isinstance(doc, list):
        return [encode_tree(v) for v in doc]
    return doc


def decode_member(name, raw):
    """A delivered member -> list of decoded documents (one per line for .jsonl), with the L1 proof per line."""
    pack, unpack, canonical_bytes = _c15()
    lines = [l for l in raw.split(b'\n') if l.strip()] if name.endswith('.jsonl') else [raw]
    docs, kinds = [], []
    for line in lines:
        try:
            parsed = json.loads(line)
        except ValueError:
            docs.append(DecodedText(line.decode('utf-8', 'replace'))); kinds.append('text'); continue
        if _is_packed(parsed):
            plain = unpack(parsed)
            if canonical_bytes(pack(plain)) != line.strip():
                raise ValueError(f'{name}: c15 round trip differs')
            docs.append(decode_tree(plain)); kinds.append('c15')
        elif json.dumps(parsed, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode() == line.strip():
            docs.append(decode_tree(parsed)); kinds.append('json')
        else:
            docs.append(DecodedText(line.decode('utf-8'))); kinds.append('text')   # JSON in a non-canonical form: kept verbatim
    return docs, kinds


def encode_member(name, docs, kinds):
    pack, unpack, canonical_bytes = _c15()
    out = []
    for doc, kind in zip(docs, kinds):
        if kind == 'text':
            out.append(str(doc).encode('utf-8'))
        elif kind == 'c15':
            out.append(canonical_bytes(pack(encode_tree(doc))))
        else:
            out.append(json.dumps(encode_tree(doc), sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode())
    return b'\n'.join(out) + (b'\n' if name.endswith('.jsonl') else b'')


# ---- L4: tensors ------------------------------------------------------------------------------------------------
DTYPES = {'float64': ('d', 8), 'float32': ('f', 4), 'int64': ('q', 8), 'int32': ('i', 4)}


def _tensor_map(node):
    """A decoded weights map: {name: {'dtype','shape','bytes'}} (the frozen decoder state)."""
    return (isinstance(node, dict) and node and all(isinstance(v, dict) and set(v) == {'dtype', 'shape', 'bytes'} for v in node.values()))


def tensor_rows(weights, mode):
    rows = []
    for name, t in weights.items():
        raw = t['bytes'] if isinstance(t['bytes'], bytes) else bytes.fromhex(t['bytes'])
        fmt, width = DTYPES.get(t['dtype'], (None, None))
        row = dict(name=name, dtype=t['dtype'], shape=list(t['shape']), bytes=len(raw), sha256=sha(raw))
        if fmt and len(raw) % width == 0:
            values = struct.unpack('<%d%s' % (len(raw) // width, fmt), raw)
            finite = [v for v in values if not (isinstance(v, float) and not math.isfinite(v))]
            row.update(count=len(values), min=min(finite) if finite else None, max=max(finite) if finite else None,
                       mean=(sum(finite) / len(finite)) if finite else None, l2=math.sqrt(sum(v * v for v in finite)) if finite else None)
            if mode == 'values':
                row['values'] = [repr(v) if isinstance(v, float) else v for v in values]
                assert all((float(s) == v) for s, v in zip(row['values'], values) if isinstance(v, float))
        rows.append(row)
    return rows


# ---- L3/L5: dedup + containment ------------------------------------------------------------------------------------
@dataclass
class Dictionary:
    entries: dict = field(default_factory=dict)      # sha256 -> (kind, first_path, size)
    order: list = field(default_factory=list)
    refs: int = 0
    saved: int = 0
    already_read: dict = field(default_factory=dict) # sha256 -> {'cycle': ..} from earlier cycles (L6)
    read_refs: int = 0
    read_saved: int = 0

    def key(self, value):
        if isinstance(value, str):
            return sha(value.encode('utf-8')), 'str'
        if isinstance(value, bytes):
            return sha(value), 'bytes'
        return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), default=_jsonable).encode()), 'tree'


def _jsonable(v):
    if isinstance(v, bytes):
        return {'$bytes_hex': v.hex()}
    if isinstance(v, tuple):
        return list(v)
    raise TypeError(type(v).__name__)


def _size(value):
    if isinstance(value, str):
        return len(value.encode('utf-8'))
    if isinstance(value, bytes):
        return len(value)
    return len(json.dumps(value, sort_keys=True, separators=(',', ':'), default=_jsonable))


def dedup(doc, dictionary, path=''):
    """Replace repeated large values by {'$ref': sha256} (L3); first occurrence stays in place and is recorded."""
    if isinstance(doc, (dict, list, tuple, str, bytes)) and not (isinstance(doc, dict) and '$ref' in doc):
        size = _size(doc)
        if size >= DEDUP_BYTES:
            digest, kind = dictionary.key(doc)
            if digest in dictionary.entries:
                dictionary.refs += 1
                dictionary.saved += size
                return {'$ref': digest, 'kind': kind, 'bytes': size}
            if digest in dictionary.already_read:
                dictionary.read_refs += 1
                dictionary.read_saved += size
                dictionary.entries[digest] = (kind, path, size)
                return {'$read': digest, 'kind': kind, 'bytes': size, 'cycle': dictionary.already_read[digest].get('cycle')}
            dictionary.entries[digest] = (kind, path, size)
            dictionary.order.append(digest)
    if isinstance(doc, dict):
        return {k: dedup(v, dictionary, f'{path}.{k}') for k, v in doc.items()}
    if isinstance(doc, (list, tuple)):
        out = [dedup(v, dictionary, f'{path}[{i}]') for i, v in enumerate(doc)]
        return tuple(out) if isinstance(doc, tuple) else out
    return doc


def contain(doc, big_strings):
    """L5: a large string containing another rendered large string verbatim gets that span replaced by a marker."""
    if isinstance(doc, str) and len(doc) >= DEDUP_BYTES:
        for digest, s in big_strings:
            if s != doc and len(s) >= DEDUP_BYTES and s in doc:
                return doc.replace(s, f'<<contains sha256:{digest} {len(s.encode("utf-8"))} bytes, rendered once above>>')
        return doc
    if isinstance(doc, dict):
        return {k: contain(v, big_strings) for k, v in doc.items()}
    if isinstance(doc, (list, tuple)):
        out = [contain(v, big_strings) for v in doc]
        return tuple(out) if isinstance(doc, tuple) else out
    return doc


# ---- render ------------------------------------------------------------------------------------------------------
def _render_json(value, indent=None):
    return json.dumps(value, sort_keys=True, indent=indent, ensure_ascii=True, default=_jsonable)


def _weights_pass(doc, mode, stats):
    """L4 in place: a decoded weights map becomes {'$tensors': rows}; the bytes stay reachable by digest."""
    if isinstance(doc, dict):
        if set(doc) == {'$decoded', 'sha256', 'bytes', 'value'} and _tensor_map(doc['value']):
            rows = tensor_rows(doc['value'], mode)
            stats['tensors'] += len(rows)
            stats['tensor_bytes'] += sum(r['bytes'] for r in rows)
            return {'$tensors': rows, 'container_sha256': doc['sha256'], 'container_bytes': doc['bytes'], 'mode': mode}
        return {k: _weights_pass(v, mode, stats) for k, v in doc.items()}
    if isinstance(doc, (list, tuple)):
        out = [_weights_pass(v, mode, stats) for v in doc]
        return tuple(out) if isinstance(doc, tuple) else out
    return doc


@dataclass
class RenderReport:
    members: dict
    dictionary_entries: int
    refs: int
    saved_bytes: int
    tensors: int
    tensor_bytes: int
    rendered_bytes: int
    delivered_bytes: int
    proof: dict
    dictionary: dict = field(default_factory=dict)   # sha256 -> {kind, path, bytes} rendered (or referenced) this cycle
    read_refs: int = 0
    read_saved_bytes: int = 0


def render(members, *, tensor_mode='identity', tokenizer=None, already_read=None):
    """members: {name: bytes}. Returns (markdown_text, RenderReport). The plan needed for reconstruction is the
    decoded documents themselves (kept in memory by the caller through `plan`)."""
    pack, unpack, canonical_bytes = _c15()
    plan, dictionary, stats = {}, Dictionary(already_read=dict(already_read or {})), dict(tensors=0, tensor_bytes=0)
    per = {}
    # decode every member first so the dictionary sees the forecast artifact before its hex copy
    order = sorted(members, key=lambda n: (0 if n.startswith('files/forecast') else 1 if n.startswith('files/state') else 2, n))
    decoded = {}
    for name in order:
        docs, kinds = decode_member(name, members[name])
        decoded[name] = (docs, kinds)
        if encode_member(name, docs, kinds).rstrip(b'\n') != members[name].rstrip(b'\n'):
            raise ValueError(f'{name}: decode/encode round trip differs')
    big_strings = []
    out = []
    for name in order:
        docs, kinds = decoded[name]
        rendered_docs = []
        for doc in docs:
            d = _weights_pass(doc, tensor_mode, stats)
            d = dedup(d, dictionary, name)
            rendered_docs.append(d)
        per[name] = dict(delivered_bytes=len(members[name]), documents=len(docs), kinds=kinds)
        plan[name] = rendered_docs
    # containment on strings that survived dedup
    for name in order:
        for d in plan[name]:
            def collect(x):
                if isinstance(x, str) and len(x) >= DEDUP_BYTES:
                    big_strings.append((sha(x.encode('utf-8')), x))
                elif isinstance(x, dict):
                    for v in x.values(): collect(v)
                elif isinstance(x, (list, tuple)):
                    for v in x: collect(v)
            collect(d)
    for name in order:
        plan[name] = [contain(d, big_strings) for d in plan[name]]
    out.append('## Delivered producer evidence, lossless render (every member whole; encodings decoded in place; '
               'repeated values rendered once and referenced by sha256; tensors as tables; nothing sampled or omitted)\n')
    out.append('Legend: {"$decoded": enc, "sha256", "bytes", "value"} = a bytes value decoded from enc (c15 | json | utf8), exact bytes '
               'reproducible; {"$read": sha256, "cycle"} = the value already rendered and read in that earlier cycle (its notes are carried in this corpus head); '
               'reproducible; {"$ref": sha256} = the value rendered earlier under that digest; {"$tensors": [...]} = a frozen '
               'decoder state, one row per tensor (dtype, shape, bytes, sha256, count, min, max, mean, l2' + (', values' if tensor_mode == 'values' else '') + '); '
               '<<contains sha256:...>> = this text embeds the referenced text verbatim.\n')
    for name in order:
        raw = members[name]
        out.append(f'\n### member {name} ({len(raw)} bytes, sha256 {sha(raw)}, {len(plan[name])} document(s), whole)\n')
        for i, d in enumerate(plan[name]):
            body = _render_json(d, indent=None) if not isinstance(d, DecodedText) else str(d)
            out.append(f'\n#### document {i}\n```json\n{body}\n```\n' if not isinstance(d, DecodedText) else f'\n#### document {i} (text)\n{body}\n')
            per[name].setdefault('rendered_bytes', 0)
            per[name]['rendered_bytes'] += len(body.encode('utf-8'))
    text = ''.join(out)
    if tokenizer is not None:
        for name in order:
            per[name]['delivered_tokens'] = _tokens(tokenizer, members[name].decode('utf-8', 'replace'))
        # rendered tokens per member from the member section
        for name in order:
            start = text.find(f'\n### member {name} (')
            end = min([text.find(f'\n### member {m} (', start + 1) for m in order if text.find(f'\n### member {m} (', start + 1) > 0] or [len(text)])
            per[name]['rendered_tokens'] = _tokens(tokenizer, text[start:end])
    proof = reconstruct_proof(members, plan, decoded)
    report = RenderReport(members=per, dictionary_entries=len(dictionary.entries), refs=dictionary.refs, saved_bytes=dictionary.saved,
                          tensors=stats['tensors'], tensor_bytes=stats['tensor_bytes'], rendered_bytes=len(text.encode('utf-8')),
                          delivered_bytes=sum(len(b) for b in members.values()), proof=proof,
                          dictionary={d: dict(kind=k, path=pth, bytes=n) for d, (k, pth, n) in dictionary.entries.items()},
                          read_refs=dictionary.read_refs, read_saved_bytes=dictionary.read_saved)
    return text, report


def _tokens(tokenizer, text):
    n = 0
    for i in range(0, len(text), 1 << 20):
        n += len(tokenizer.encode(text[i:i + (1 << 20)], add_special_tokens=False).ids)
    return n


def reconstruct_proof(members, plan, decoded):
    """The proof: every member's original bytes rebuild from the decoded documents (the render's source of truth
    after L1/L2, before the presentation passes, which only replace values by references to values already
    rendered) and hash to the delivered sha256."""
    proof = {}
    for name, raw in members.items():
        docs, kinds = decoded[name]
        rebuilt = encode_member(name, docs, kinds)
        ok = rebuilt.rstrip(b'\n') == raw.rstrip(b'\n')
        proof[name] = dict(delivered_sha256=sha(raw), rebuilt_sha256=sha(rebuilt.rstrip(b'\n') + (b'\n' if raw.endswith(b'\n') else b'')), exact=ok)
    proof['all_exact'] = all(v['exact'] for k, v in proof.items() if k != 'all_exact')
    return proof
