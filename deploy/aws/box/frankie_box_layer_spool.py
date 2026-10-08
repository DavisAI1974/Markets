"""Spool reference layers: a derived layer whose rows are a whole ROOT RowSpool is written as a small REFERENCE to that
spool instead of a second, re-encoded copy of every row (Greg, 2026-10-08: "stream the data to next step instead of
dumping huge data size on next step"; a2's legacy_book_imbalance.json was a ~497 GB re-encoding of the frames spool).

The reference layer (FRANKIE_LAYER_SPOOL_REF_V1) is the layer's own JSON object, written exactly as before
(frankie_box_durable.write_json: indent=1, sort_keys, default=str), except that each top-level key whose value was a
RowSpool holds a spool reference instead of the rows:

  {"#frankie_layer_spool_ref": "FRANKIE_LAYER_SPOOL_REF_V1", "#spools": ["frames"], "count": ..., "fields": [...],
   "frames": {"#frankie_layer_spool_ref": "FRANKIE_LAYER_SPOOL_REF_V1", "path": ".rows/frames.jsonl",
              "attempt_path": "work/derived/.rows/frames.jsonl", "bytes": ..., "sha256": ..., "count": ...,
              "index_every": 4096, "index": [[0, 0], [4096, <byte offset of row 4096>], ..., [count, bytes]],
              "rows": "..."}, "producer": ..., "status": ...}

`path` resolves against the layer file's own directory (the attempt layout keeps both under work/derived), `index` gives
the byte offset where every index_every-th row begins (a consumer seeks to any row or closed group), and bytes/sha256/
count are the spool's own (one read of the spool when the layer is written, reused for the stage's witnesses).

Every reader gets the values and the order the old re-encoded layer gave: an old layer's element was the spool row
decoded by the journal codec (unpack(json.loads(line))), encoded by write_json's encoder and decoded again by json, so
row_value(line) is exactly that round trip (json.dumps with sort_keys=True, default=str: the same encoder settings;
indentation never changes a decoded value). Readers:
  - ReferenceText: a text stream rendering the old layer's JSON value text on the fly (frankie_box_digest_sources._JSON
    wraps every handle it parses with layer_text(), the ONE shared place every streaming layer reader goes through);
  - SpoolRows: an iterable over the rows (len(), seek by the index), for whole-value readers (load());
  - read_reference(): the reference document of a layer file, or None for an old-form layer (which loads unchanged).
A reader verifies the spool's size before reading and its row count (and sha256 on a whole read) at the end.
"""
import hashlib
import json
import os
from pathlib import Path

SCHEMA = 'FRANKIE_LAYER_SPOOL_REF_V1'
MARKER = '#frankie_layer_spool_ref'
SPOOLS_KEY = '#spools'
INDEX_EVERY = 4096
CHUNK = 16 << 20
ROWS_RULE = ('each row = json.loads(json.dumps(unpack(json.loads(line)), sort_keys=True, default=str)): the value the '
             're-encoded layer element decoded to (frankie_box_durable.write_json encoder settings)')


def _unpack():
    from research.kalshi.frankie_boss.c15_journal import unpack
    return unpack


def row_text(line, unpack=None):
    """The JSON text of one spool row as the old layer held it (compact separators; the same decoded value)."""
    return json.dumps((unpack or _unpack())(json.loads(line)), sort_keys=True, default=str)


def row_value(line, unpack=None):
    return json.loads(row_text(line, unpack))


def scan_spool(path, every=INDEX_EVERY, on_bytes=None):
    """One read of a closed spool: bytes, sha256, row count (newlines; the last row must end on one) and the index.
    on_bytes(n), when given, hears every chunk read (a caller's progress probe over a multi-hundred-GB spool); it never
    changes the scan: an exception raised by it is swallowed, the values are the same with or without it."""
    path = Path(path)
    digest, size, count, index, target = hashlib.sha256(), 0, 0, [[0, 0]], every
    last = b'\n'
    with path.open('rb', buffering=0) as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            if on_bytes is not None:
                try:
                    on_bytes(len(chunk))
                except Exception:  # noqa: BLE001 - a probe never changes the scan
                    pass
            found = chunk.count(b'\n')
            position, passed = -1, 0                       # newlines passed inside this chunk
            while count + found >= target:                 # row `target` begins just after newline number `target`
                while passed < target - count:
                    position = chunk.find(b'\n', position + 1)
                    passed += 1
                index.append([target, size + position + 1])
                target += every
            count += found
            size += len(chunk)
            last = chunk[-1:]
    if size and last != b'\n':
        raise ValueError('retained row spool has a partial final record')
    if index[-1] != [count, size]:
        index.append([count, size])
    return dict(bytes=size, sha256=digest.hexdigest(), count=count, index_every=every, index=index)


def _attempt_path(layer_path, spool_path):
    layer_dir = Path(layer_path).resolve().parent
    try:
        return str(Path(spool_path).resolve().relative_to(layer_dir.parent.parent))
    except ValueError:
        return None


def reference_document(layer_path, value, spool_keys, scans):
    """The reference layer document for `value` (a layer dict) whose `spool_keys` hold closed RowSpools; scans[key] is
    scan_spool of that spool. Non-spool keys are kept as they are (written by the same encoder as before)."""
    layer_path = Path(layer_path)
    document = {k: v for k, v in value.items() if k not in spool_keys}
    for key in spool_keys:
        spool = value[key]
        scan = scans[key]
        if scan['count'] != len(spool):
            raise ValueError('retained row spool count changed')
        document[key] = {MARKER: SCHEMA, 'path': os.path.relpath(Path(spool.path).resolve(), layer_path.resolve().parent),
                         'attempt_path': _attempt_path(layer_path, spool.path), 'rows': ROWS_RULE,
                         **{k: scan[k] for k in ('bytes', 'sha256', 'count', 'index_every', 'index')}}
    document[MARKER] = SCHEMA
    document[SPOOLS_KEY] = sorted(spool_keys)
    return document


def is_reference_document(document):
    return isinstance(document, dict) and document.get(MARKER) == SCHEMA


def spool_refs(document):
    return {key: document[key] for key in document.get(SPOOLS_KEY) or []}


def spool_path(layer_path, ref):
    return Path(layer_path).parent / ref['path']


def _looks_like_reference(head):
    text = head.lstrip()
    return text.startswith('{') and text[1:].lstrip().startswith('"%s"' % MARKER)


def read_reference(layer_path):
    """The reference document of a layer file, or None when the file is an old-form (or any other) layer."""
    layer_path = Path(layer_path)
    with layer_path.open('rb') as handle:
        head = handle.read(4096)
        if not _looks_like_reference(head.decode('utf-8', 'replace')):
            return None
        document = json.loads(head + handle.read())
    if not is_reference_document(document):
        raise ValueError('%s: a spool reference marker without its schema' % layer_path.name)
    return document


class SpoolRows:
    """The rows of one spool reference, in spool order, each as the old layer decoded it. len() is the reference's
    count; rows(start) seeks through the index. A whole read checks bytes, sha256 and count at its end; a partial read
    checks the size before and the count of the rows it read against the reference."""

    def __init__(self, layer_path, ref):
        self.ref, self.path = ref, spool_path(layer_path, ref)
        if self.path.stat().st_size != ref['bytes']:
            raise ValueError('the spool a reference layer names differs from it (bytes); retained for recovery')

    def __len__(self):
        return self.ref['count']

    def __iter__(self):
        return self.rows(0)

    def texts(self, start=0):
        """The row texts (row_text) from row `start`."""
        unpack = _unpack()
        ref = self.ref
        if not 0 <= start <= ref['count']:
            raise IndexError(start)
        base_row, offset = max((entry for entry in ref['index'] if entry[0] <= start), key=lambda entry: entry[0])
        whole = start == 0
        digest, seen = hashlib.sha256(), base_row
        with self.path.open('rb') as handle:
            handle.seek(offset)
            for line in handle:
                if whole:
                    digest.update(line)
                if seen >= start:
                    yield row_text(line, unpack)
                seen += 1
        if seen != ref['count']:
            raise ValueError('retained row spool count changed')
        if whole and digest.hexdigest() != ref['sha256']:
            raise ValueError('the spool a reference layer names differs from it (sha256); retained for recovery')

    def rows(self, start=0):
        for text in self.texts(start):
            yield json.loads(text)


def load(layer_path):
    """A whole layer value: an old-form layer exactly as json.loads gives it; a reference layer with each spool key a
    SpoolRows (iterable, len()) and the marker keys removed."""
    layer_path = Path(layer_path)
    document = read_reference(layer_path)
    if document is None:
        return json.loads(layer_path.read_bytes())
    refs = spool_refs(document)
    return {key: (SpoolRows(layer_path, refs[key]) if key in refs else value)
            for key, value in document.items() if key not in (MARKER, SPOOLS_KEY)}


class ReferenceText:
    """A read()-able text stream of the old layer's JSON value (compact separators; the same decoded values in the same
    order), rendered from a reference document and its spools while it is read."""

    def __init__(self, document, layer_path):
        self.document, self.layer_path = document, Path(layer_path)
        self.refs = spool_refs(document)
        self.rows = {key: SpoolRows(self.layer_path, ref) for key, ref in self.refs.items()}   # sizes checked now
        self._pieces = self._render()
        self._buffer = ''
        self.name = str(layer_path)

    def _render(self):
        keys = sorted(k for k in self.document if k not in (MARKER, SPOOLS_KEY))
        yield '{'
        for i, key in enumerate(keys):
            yield (', ' if i else '') + json.dumps(key) + ': '
            if key in self.rows:
                yield '['
                first = True
                for text in self.rows[key].texts():
                    yield text if first else ', ' + text
                    first = False
                yield ']'
            else:
                yield json.dumps(self.document[key], sort_keys=True, default=str)
        yield '}\n'

    def read(self, size=-1):
        while (size is None or size < 0 or len(self._buffer) < size):
            piece = next(self._pieces, None)
            if piece is None:
                break
            self._buffer += piece
        if size is None or size < 0:
            out, self._buffer = self._buffer, ''
        else:
            out, self._buffer = self._buffer[:size], self._buffer[size:]
        return out

    def close(self):
        self._pieces.close()


class _Prefixed:
    """A text handle with its first chunk read back in front (layer_text's probe of an ordinary layer)."""

    def __init__(self, head, handle):
        self._head, self._handle = head, handle
        self.name = getattr(handle, 'name', None)

    def read(self, size=-1):
        if self._head:
            if size is None or size < 0:
                out, self._head = self._head + self._handle.read(), ''
                return out
            out, self._head = self._head[:size], self._head[size:]
            return out
        return self._handle.read(size)


def layer_text(handle):
    """The handle a streaming layer parser reads: a reference layer's ReferenceText (its old JSON text, rendered), or the
    same text handle unchanged for every other layer (its first chunk read back in front)."""
    head = handle.read(65536)
    if not isinstance(head, str) or not _looks_like_reference(head):
        return _Prefixed(head, handle)
    document = json.loads(head + handle.read())
    if not is_reference_document(document):
        raise ValueError('a spool reference marker without its schema')
    name = getattr(handle, 'name', None)
    if not isinstance(name, str):
        raise ValueError('a spool reference layer is read through its file path')
    return ReferenceText(document, name)
