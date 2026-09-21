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
  L7  derivable vectors: a list of consecutive integers renders as {"$range": [first, last]}; a list of packet
      hashes equal to the vector the stacked critic snapshot's packet recipe reconstructs (granite_context_stacked.decode
      on the delivered snapshot) renders as {"$derivable": "packet_hashes", "from": "critic snapshot", "sha256"}; both
      recomputed and compared before the reference is written.
  L6  cross-cycle ledger: a value already rendered and read in an EARLIER cycle (same sha256 in the box's
      reading ledger) becomes {"$read": sha256, "cycle": "<NN>"}; the earlier cycle's merged notes travel in the
      corpus head. The journals are append-only, so a later cycle reads only what was appended or changed.
  L8  known files (Greg 2026-09-21 12:2xZ, stack the stacks; profile 35603160044: seven source files delivered as
      configuration, 23.8k tokens, are byte-identical to files in the box's checkout): a text or bytes value whose
      sha256 equals a file in a checkout the box holds renders as {"$file": path, "checkout", "commit", "sha256",
      "bytes"}; the reader opens the file on the box; equality is by digest.
  L9  the stacked envelope (the critic's context, 91k tokens of JSON syntax around already delta-encoded columns) is
      spelled as a STACKED_TEXT_V1 block (frankie_box_stacked_text: the same tagged tree in prefix notation), parsed
      back and compared to the envelope's canonical JSON before it is used.
  L10 a list of same-keyed dicts (forecast points, known marks, the tensor rows) renders as a DIGEST_V4 table block
      (frankie_box_digest_render: header once, ^ for a repeated cell, deltas, dictionary), parsed back and compared
      before it is used; a list whose table does not round-trip or is not smaller stays JSON.
Blocks (L9, L10) are fenced text after their document; the document keeps a {"$stacked"|"$table", "block", "sha256"}
node where the value was, so nothing is out of order for the reader.
The render is Markdown with fenced JSON blocks; `reconstruct()` rebuilds every member's original bytes from the
render plan and the proof compares sha256s. `RenderReport` carries bytes and (when the tokenizer is present)
exact Granite tokens per layer so the receipt states the reduction rather than claiming it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import struct
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RENDER_VERSION = 'READING_RENDER_L10_V1'   # bumps when a layer changes what the corpus says; the session rebuilds a corpus whose identity differs
DEDUP_BYTES = 4096
NESTED_MIN = 32
FILE_MIN = 1024        # L8: a value at least this large may be a known file
TABLE_MIN = 16         # L10: a list of at least this many same-keyed dicts may be a table block
STACKED_MIN = 512      # L9: a text value at least this large may be the JSON of a stacked envelope
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
DTYPES = {'float64': ('d', 8), 'float32': ('f', 4), 'int64': ('q', 8), 'int32': ('i', 4),
          'torch.float64': ('d', 8), 'torch.float32': ('f', 4), 'torch.int64': ('q', 8), 'torch.int32': ('i', 4)}   # native byte order ('=d', the snapshot contract)


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
            values = struct.unpack('=%d%s' % (len(raw) // width, fmt), raw)
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
    derivable: dict = field(default_factory=dict)    # L7: digest -> info of vectors the package's stacked snapshot reconstructs
    derived: int = 0
    ranges: int = 0
    known_files: dict = field(default_factory=dict)  # L8: sha256 -> {path, checkout, commit} of files in checkouts the box holds
    file_refs: int = 0
    file_saved: int = 0

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


RANGE_MIN = 64


def _monotone(doc):
    return (isinstance(doc, (list, tuple)) and len(doc) >= RANGE_MIN and all(type(v) is int for v in doc)
            and all(b - a == 1 for a, b in zip(doc, doc[1:])))


def derivable_vectors(members, notes=None):
    """L7: vectors reconstructible from a stacked envelope delivered in the package (the critic snapshot): sha256 of the
    canonical list -> description. Decoding is the codec's own (self-verifying); a failure yields nothing, and the
    reason is appended to `notes` (a list) so the corpus receipt states why the layer did not fire."""
    out = {}
    notes = notes if notes is not None else []
    try:
        from research.kalshi.frankie_boss import granite_context_stacked as stacked
    except Exception as err:
        notes.append(f'codec import failed: {type(err).__name__}: {str(err)[:200]}')
        return out
    for name, raw in members.items():
        try:
            doc = json.loads(raw.decode('utf-8'))
        except Exception:
            continue
        envelope = doc.get('codec') if isinstance(doc, dict) else None
        if not (isinstance(envelope, dict) and envelope.get('schema') == getattr(stacked, 'SCHEMA', None)):
            continue
        try:
            root = stacked.decode(envelope)
        except Exception as err:
            notes.append(f'{name}: decode failed: {type(err).__name__}: {str(err)[:200]}')
            continue
        vector = (root.get('receipt') or {}).get('packet_hashes') if isinstance(root, dict) else None
        if isinstance(vector, (list, tuple)) and vector:
            digest = sha(json.dumps(list(vector), separators=(',', ':')).encode())
            out[digest] = dict(kind='packet_hashes', member=name, count=len(vector))
        else:
            notes.append(f'{name}: decoded, no receipt.packet_hashes vector')
    return out


def dedup(doc, dictionary, path=''):
    """Replace repeated large values by {'$ref': sha256} (L3); first occurrence stays in place and is recorded.
    L7: consecutive-integer lists become {'$range': [first, last]}; a hash vector the delivered stacked snapshot
    reconstructs becomes {'$derivable': ...} (checked by digest against the codec's own reconstruction)."""
    if _monotone(doc):
        dictionary.ranges += 1
        return {'$range': [doc[0], doc[-1]], 'count': len(doc)}
    if isinstance(doc, (list, tuple)) and dictionary.derivable and doc and all(isinstance(v, str) for v in doc):
        digest = sha(json.dumps(list(doc), separators=(',', ':')).encode())
        if digest in dictionary.derivable:
            info = dictionary.derivable[digest]
            dictionary.derived += 1
            return {'$derivable': info['kind'], 'from': f"the stacked packet recipe of {info['member']}", 'count': len(doc), 'sha256': digest}
    if dictionary.known_files:
        known = _known_file(doc, dictionary)
        if known is not None:
            return known
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


def _known_file(doc, dictionary):
    """L8: a decoded-bytes node, a string or a bytes value whose sha256 is a file in a checkout the box holds."""
    if isinstance(doc, dict) and set(doc) == {'$decoded', 'sha256', 'bytes', 'value'}:
        digest, size, encoding = doc['sha256'], doc['bytes'], doc['$decoded']
    elif isinstance(doc, str) and len(doc) >= FILE_MIN:
        raw = doc.encode('utf-8'); digest, size, encoding = sha(raw), len(raw), 'utf8'
    elif isinstance(doc, bytes) and len(doc) >= FILE_MIN:
        digest, size, encoding = sha(doc), len(doc), None
    else:
        return None
    info = dictionary.known_files.get(digest)
    if not info or size < FILE_MIN:
        return None
    dictionary.file_refs += 1
    dictionary.file_saved += size
    return {'$file': info['path'], 'checkout': info['checkout'], 'commit': info.get('commit'), 'sha256': digest, 'bytes': size, 'decoded': encoding}


def known_files_index(checkouts, max_bytes=2_000_000):
    """{sha256: {path, checkout, commit}} over every file (<= max_bytes) of the given checkouts {label: directory};
    the commit is the checkout's HEAD when it is a git checkout. Exact bytes only."""
    index = {}
    for label, directory in checkouts.items():
        commit = None
        head = os.path.join(directory, '.git', 'HEAD')
        try:
            ref = open(head).read().strip()
            if ref.startswith('ref: '):
                commit = open(os.path.join(directory, '.git', ref[5:])).read().strip()
            else:
                commit = ref
        except OSError:
            commit = None
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = [d for d in dirnames if d not in ('.git', 'venv', 'node_modules', '__pycache__')]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(path) > max_bytes:
                        continue
                    raw = open(path, 'rb').read()
                except OSError:
                    continue
                index.setdefault(sha(raw), dict(path=os.path.relpath(path, directory), checkout=label, commit=commit))
    return index


def _no_tuples(value):
    if isinstance(value, tuple):
        return False
    if isinstance(value, dict):
        return all(_no_tuples(v) for v in value.values())
    if isinstance(value, list):
        return all(_no_tuples(v) for v in value)
    return True


def _same_keys(items):
    """L10 candidates: a list of >= TABLE_MIN non-empty dicts, no key holding a '.', no tuples. Key sets may differ
    between rows: the DIGEST_V4 grammar writes `?` for a cell the row does not carry, and the parse-back proof
    decides (run 35604644446: the forecast's 101 points and 58 known marks were left as JSON by a same-keys rule)."""
    return (isinstance(items, (list, tuple)) and len(items) >= TABLE_MIN and all(isinstance(v, dict) and v for v in items)
            and not any('.' in k for v in items for k in v))   # the container may be a c15 tuple (run 35605902090: the forecast's points and marks are); a tuple cell is a `U` cell (DIGEST_V4), a tuple nested in one refuses and the value stays JSON


def table_candidates(doc, path=''):
    """Diagnostics: every list of >= TABLE_MIN dicts under doc with why it would or would not be a table block."""
    out = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            out.extend(table_candidates(v, f'{path}.{k}'))
    elif isinstance(doc, (list, tuple)):
        if len(doc) >= TABLE_MIN and all(isinstance(v, dict) for v in doc):
            keysets = {tuple(v) for v in doc}
            why = 'tuple' if isinstance(doc, tuple) else 'dotted key' if any('.' in k for v in doc for k in v) else 'tuples inside' if not _no_tuples(list(doc)) else 'candidate'
            out.append((path, len(doc), len(keysets), why))
        for i, v in enumerate(doc):
            out.extend(table_candidates(v, f'{path}[{i}]'))
    return out


def _is_envelope(node):
    return (isinstance(node, dict) and set(node) == {'schema', 'prompt_version', 'grammar_sha256', 'data'}
            and node.get('schema') == 'BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V1' and isinstance(node.get('data'), list))


def _stacked_text_block(text, path):
    """L9 on a TEXT value that is the JSON of a stacked envelope, or of a dict carrying one at `codec` (the critic's
    snapshot_text: schema, native_hash, codec, spelled by the route's _text without sorted keys, so L2 leaves it text).
    The text must be exactly json.dumps(obj, separators=(',', ':'), ensure_ascii=True) of what it parses to, and the
    block's parse must put that text back byte for byte; else None."""
    if not (isinstance(text, str) and len(text) >= STACKED_MIN and text[:1] == '{'):
        return None
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    holder = obj if _is_envelope(obj) else (obj.get('codec') if _is_envelope(obj.get('codec')) else None)
    if holder is None or json.dumps(obj, separators=(',', ':'), ensure_ascii=True) != text:
        return None
    import frankie_box_stacked_text as ST
    spelled = ST.prove(holder['data'])
    holder['data'] = ST.parse(spelled)
    if json.dumps(obj, separators=(',', ':'), ensure_ascii=True) != text:
        raise ValueError(f'{path}: the STACKED_TEXT_V1 block does not put the snapshot text back')
    digest = sha(text.encode('utf-8'))
    ident = 'stacked-' + digest[:12]
    holder['data'] = {'$stacked': 'STACKED_TEXT_V1', 'block': ident}
    block = dict(id=ident, kind='STACKED_TEXT_V1', text=spelled, sha256=digest, path=path, bytes=len(text.encode('utf-8')))
    return {'$stacked_text': 'STACKED_TEXT_V1', 'block': ident, 'sha256': digest, 'bytes': len(text.encode('utf-8')), 'json': obj}, block


def _blocks_pass(doc, blocks, path=''):
    """L9/L10 in place: a stacked envelope's data becomes a STACKED_TEXT_V1 block; a list of same-keyed dicts becomes
    a DIGEST_V4 table block when the table parses back to the same rows and is smaller. Each block is proven before
    the node is replaced; a failure leaves the value as it was."""
    if isinstance(doc, str):
        found = _stacked_text_block(doc, path)
        if found is not None:
            blocks.append(found[1])
            return found[0]
        return doc
    if isinstance(doc, dict):
        if _is_envelope(doc):
            import frankie_box_stacked_text as ST
            text = ST.prove(doc['data'])
            digest = sha(ST.canonical(doc['data']).encode())
            ident = 'stacked-' + digest[:12]
            blocks.append(dict(id=ident, kind='STACKED_TEXT_V1', text=text, sha256=digest, path=path, bytes=len(ST.canonical(doc['data']).encode())))
            return {k: (v if k != 'data' else {'$stacked': 'STACKED_TEXT_V1', 'block': ident, 'sha256': digest, 'bytes': len(ST.canonical(doc['data']).encode())}) for k, v in doc.items()}
        return {k: _blocks_pass(v, blocks, f'{path}.{k}') for k, v in doc.items()}
    if _same_keys(doc):
        try:
            import frankie_box_digest_render as DG
            rows = [dict(r) for r in doc]
            block = DG.render_table('rows', rows)
            name, parsed = DG.parse_table(block)
            if DG._same(parsed, rows):        # every value, type-strict (the render's JSON sorts keys: key order is not carried by either form)
                spelled = json.dumps(doc, separators=(',', ':'), sort_keys=True, default=_jsonable)
                if len(block.encode('utf-8')) < len(spelled.encode('utf-8')):
                    digest = sha(spelled.encode('utf-8'))
                    ident = 'table-' + digest[:12]
                    blocks.append(dict(id=ident, kind='DIGEST_V4', text=block, sha256=digest, path=path, rows=len(rows), bytes=len(spelled.encode('utf-8'))))
                    node = {'$table': 'DIGEST_V4', 'block': ident, 'rows': len(rows), 'columns': list(doc[0]), 'sha256': digest}
                    if isinstance(doc, tuple):
                        node['container'] = 'tuple'
                    return node
        except Exception:
            pass
    if isinstance(doc, (list, tuple)):
        out = [_blocks_pass(v, blocks, f'{path}[{i}]') for i, v in enumerate(doc)]
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
    # compact separators: 15% fewer tokens than ', ' / ': ' on the same document with the pinned tokenizer (run 35603160044 follow-up)
    return _wrap_json(json.dumps(value, sort_keys=True, indent=indent, separators=(',', ':'), ensure_ascii=True, default=_jsonable))


def _wrap_json(text, max_depth=2):
    """Insert a newline after every comma at nesting depth <= max_depth (outside strings), so a document renders as
    many lines and the part boundaries (line-based) fall between keys, never inside a value. JSON-equivalent."""
    out, depth, in_string, escape = [], 0, False, False
    for ch in text:
        out.append(ch)
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in '[{':
            depth += 1
        elif ch in ']}':
            depth -= 1
        elif ch == ',' and depth <= max_depth:
            out.append('\n')
    return ''.join(out)


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
    derived_vectors: int = 0
    ranges: int = 0
    l7_notes: list = field(default_factory=list)   # why L7 did not fire, per envelope (empty when it did)
    file_refs: int = 0                             # L8
    file_saved_bytes: int = 0
    stacked_blocks: int = 0                        # L9
    table_blocks: int = 0                          # L10
    table_rows: int = 0
    blocks: dict = field(default_factory=dict)     # member -> [{id, kind, sha256, path, rows, bytes}]


def render(members, *, tensor_mode='identity', tokenizer=None, already_read=None, known_files=None):
    """members: {name: bytes}. Returns (markdown_text, RenderReport). The plan needed for reconstruction is the
    decoded documents themselves (kept in memory by the caller through `plan`). known_files: {sha256: {path, checkout,
    commit}} of files in checkouts the box holds (L8), from known_files_index."""
    pack, unpack, canonical_bytes = _c15()
    l7_notes = []
    plan, dictionary, stats = {}, Dictionary(already_read=dict(already_read or {}), derivable=derivable_vectors(members, l7_notes), known_files=dict(known_files or {})), dict(tensors=0, tensor_bytes=0)
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
    blocks = {}
    for name in order:
        blocks[name] = []
        plan[name] = [_blocks_pass(d, blocks[name], name) if not isinstance(d, DecodedText) else d for d in plan[name]]
    out.append('## Delivered producer evidence, lossless render (every member whole; encodings decoded in place; '
               'repeated values rendered once and referenced by sha256; tensors as tables; nothing sampled or omitted)\n')
    out.append('Legend: {"$decoded": enc, "sha256", "bytes", "value"} = a bytes value decoded from enc (c15 | json | utf8), exact bytes '
               'reproducible; {"$read": sha256, "cycle"} = the value already rendered and read in that earlier cycle (its notes are carried in this corpus head); '
               '{"$range": [first, last]} = the consecutive integers first..last; {"$derivable": "packet_hashes", ...} = the hash vector the '
               'delivered stacked snapshot reconstructs by its packet recipe (checked equal by digest); '
               'reproducible; {"$ref": sha256} = the value rendered earlier under that digest; {"$tensors": [...]} = a frozen '
               'decoder state, one row per tensor (dtype, shape, bytes, sha256, count, min, max, mean, l2' + (', values' if tensor_mode == 'values' else '') + '); '
               '<<contains sha256:...>> = this text embeds the referenced text verbatim; {"$file": path, "checkout", "commit", "sha256", "bytes"} = '
               'the value is byte-identical (by sha256) to that file of that checkout on this box, open it there; {"$stacked": "STACKED_TEXT_V1", "block"} (or {"$stacked_text", "block", "sha256", "bytes", "json"} for a text value that is the JSON of one) = '
               'the stacked envelope\'s data spelled as the named block below its document (prefix notation: tag then parts; V atom, F/H/X/G as the codec, '
               'M n keys.. values.., L/T n items.., C L|T n fields.. columns.., S L|T count node, Q L|T n items.. ints, N L|T ints, B L|T count n ints..; ints = '
               'I n v.. | D seed n deltas.. | R n (value count).. | E seed n (delta count)..), parsed back and checked equal to the envelope; '
               '{"$table": "DIGEST_V4", "block", "rows", "columns"} = that list of rows as the named DIGEST_V4 table block below its document '
               '(same grammar as the derivation digest: header once, ^ = the cell above, ^k = k such cells, deltas, @n dictionary, n/d exact fractions, scales), parsed back and checked equal.\n')
    for name in order:
        raw = members[name]
        out.append(f'\n### member {name} ({len(raw)} bytes, sha256 {sha(raw)}, {len(plan[name])} document(s), whole)\n')
        for i, d in enumerate(plan[name]):
            body = _render_json(d, indent=None) if not isinstance(d, DecodedText) else str(d)
            out.append(f'\n#### document {i}\n```json\n{body}\n```\n' if not isinstance(d, DecodedText) else f'\n#### document {i} (text)\n{body}\n')
            per[name].setdefault('rendered_bytes', 0)
            per[name]['rendered_bytes'] += len(body.encode('utf-8'))
        for b in blocks[name]:
            rows = f", {b['rows']} rows" if 'rows' in b else ''
            out.append(f"\n#### block {b['id']} ({b['kind']}{rows}; parsed back and checked equal to the value at {b['path']}; sha256 {b['sha256']}, {b['bytes']} JSON bytes)\n```\n{b['text']}```\n")
            per[name]['rendered_bytes'] += len(b['text'].encode('utf-8'))
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
                          read_refs=dictionary.read_refs, read_saved_bytes=dictionary.read_saved, derived_vectors=dictionary.derived, ranges=dictionary.ranges,
                          l7_notes=l7_notes, file_refs=dictionary.file_refs, file_saved_bytes=dictionary.file_saved,
                          stacked_blocks=sum(1 for bs in blocks.values() for b in bs if b['kind'] == 'STACKED_TEXT_V1'),
                          table_blocks=sum(1 for bs in blocks.values() for b in bs if b['kind'] == 'DIGEST_V4'),
                          table_rows=sum(b.get('rows', 0) for bs in blocks.values() for b in bs),
                          blocks={n: [{k: v for k, v in b.items() if k != 'text'} for b in bs] for n, bs in blocks.items() if bs})
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
