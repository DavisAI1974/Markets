"""Versioned bounded-block C15 storage with exact order sharing and gzip.

Original canonical bodies and logical hashes remain authoritative. The format
is opt-in and separate from retained V1 journals. A sealed container is required
for complete reads; interrupted writes retain committed blocks without claiming
completion. No scientific value is recomputed by this codec.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib

try:
    from .c15_journal import SCHEMA
    from .verified_journal_reader import (DIGEST_PREFIX, GENESIS_HASH,
        canonical_tagged_bytes, decode_tagged)
except ImportError:
    from c15_journal import SCHEMA
    from verified_journal_reader import (DIGEST_PREFIX, GENESIS_HASH,
        canonical_tagged_bytes, decode_tagged)

FORMAT = 'C15_EXACT_ORDER_BLOCK_GZIP_V1'
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 256


def _field(tree, key):
    if type(tree) is list and len(tree) == 2 and tree[0] == 'dict':
        return next((value for name, value in tree[1] if name == key), None)


def _orders(tree):
    return _field(_field(_field(tree, 'payload'), 'observation'), 'orders')


def encode_block(rows):
    if not rows or len(rows) > MAX_ROWS or sum(len(row[2]) for row in rows) > MAX_BYTES:
        raise ValueError('block exceeds bounded rows or bytes')
    dictionary, lookup, records = [], {}, []
    for ordinal, kind, body, digest in rows:
        tree = json.loads(body)
        if canonical_tagged_bytes(tree) != body:
            raise ValueError('noncanonical journal body')
        orders, indices = _orders(tree), None
        if orders is not None:
            if type(orders) is not list or len(orders) != 2 or orders[0] != 'list':
                raise ValueError('invalid order list')
            indices = []
            for order in orders[1]:
                key = canonical_tagged_bytes(order)
                if key not in lookup:
                    lookup[key] = len(dictionary)
                    dictionary.append(order)
                indices.append(lookup[key])
            orders[1] = []
        records.append([ordinal, kind, tree, indices, digest, len(body)])
    raw = canonical_tagged_bytes([FORMAT, dictionary, records])
    if len(raw) > MAX_BYTES:
        raise ValueError('encoded block exceeds byte bound')
    compressor = zlib.compressobj(6, zlib.DEFLATED, 31)
    return compressor.compress(raw) + compressor.flush()


def decode_block(blob):
    if type(blob) is not bytes or len(blob) > MAX_BYTES:
        raise ValueError('compressed block exceeds byte bound')
    try:
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(blob, MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('truncated, trailing or oversized block')
        version, dictionary, records = json.loads(raw)
        if (version != FORMAT or type(dictionary) is not list or type(records) is not list
                or not 0 < len(records) <= MAX_ROWS):
            raise ValueError('invalid block schema')
        rows, total = [], 0
        for ordinal, kind, tree, indices, digest, size in records:
            if type(size) is not int or not 0 < size <= MAX_BYTES:
                raise ValueError('invalid reconstructed size')
            total += size
            if total > MAX_BYTES:
                raise ValueError('reconstruction exceeds byte bound')
            if indices is not None:
                orders = _orders(tree)
                if (orders != ['list', []] or type(indices) is not list
                        or any(type(i) is not int or not 0 <= i < len(dictionary) for i in indices)):
                    raise ValueError('invalid order references')
                orders[1] = [dictionary[i] for i in indices]
            body = canonical_tagged_bytes(tree)
            if len(body) != size or hashlib.sha256(DIGEST_PREFIX+body).hexdigest() != digest:
                raise ValueError('reconstructed body identity differs')
            rows.append((ordinal, kind, body, digest))
        return rows
    except (zlib.error, TypeError, KeyError, IndexError, StopIteration, RecursionError) as exc:
        raise ValueError('invalid compressed journal block') from exc


def verified_partition(rows, start, previous):
    count = start
    for ordinal, kind, body, digest in rows:
        tree = json.loads(body)
        envelope = decode_tagged(tree)
        if (canonical_tagged_bytes(tree) != body or type(envelope) is not dict
                or ordinal != count or envelope.get('ordinal') != ordinal
                or envelope.get('schema') != SCHEMA or envelope.get('kind') != kind
                or envelope.get('previous_hash') != previous
                or hashlib.sha256(DIGEST_PREFIX+body).hexdigest() != digest):
            raise ValueError('evidence journal continuity or hash mismatch')
        previous, count = digest, count+1
        yield envelope
def verified_rows(rows, expected_count, expected_head_hash):
    count, head = 0, GENESIS_HASH
    def tracked():
        nonlocal count, head
        for row in rows:
            count, head = count+1, row[3]
            yield row
    yield from verified_partition(tracked(), 0, GENESIS_HASH)
    if (count, head) != (expected_count, expected_head_hash):
        raise ValueError('journal differs from checkpoint')


class CompactWriter:
    def __init__(self, path, *, block_bytes=4*1024*1024):
        if type(block_bytes) is not int or not 0 < block_bytes <= MAX_BYTES//2:
            raise ValueError('invalid block byte budget')
        self.path = Path(path)
        with self.path.open('xb'):
            pass
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE blocks (start INTEGER PRIMARY KEY, count INTEGER, body BLOB, sha256 TEXT, previous TEXT, head TEXT)')
        self.db.execute('CREATE TABLE seal (format TEXT, count INTEGER, head TEXT)')
        self.db.commit()
        self.block_bytes, self.pending, self.pending_bytes = block_bytes, [], 0
        self.count, self.head_hash, self.sealed = 0, GENESIS_HASH, False
        self.flush_seconds, self.flushed_bytes = 0.0, 0

    def add(self, row):
        if self.sealed:
            raise ValueError('container already sealed')
        ordinal, kind, body, digest = row
        if ordinal != self.count or type(body) is not bytes or len(body) > MAX_BYTES//2:
            raise ValueError('noncontiguous or oversized row')
        if self.pending and (self.pending_bytes+len(body) > self.block_bytes or len(self.pending) == MAX_ROWS):
            self.flush()
        # Check authority before persisting; no decoded objects leave this call.
        tree = json.loads(body)
        envelope = decode_tagged(tree)
        if (canonical_tagged_bytes(tree) != body or type(envelope) is not dict
                or envelope.get('schema') != SCHEMA or envelope.get('ordinal') != ordinal
                or envelope.get('kind') != kind or envelope.get('previous_hash') != self.head_hash
                or hashlib.sha256(DIGEST_PREFIX+body).hexdigest() != digest):
            raise ValueError('journal input identity differs')
        self.pending.append(row)
        self.pending_bytes += len(body)
        self.count, self.head_hash = self.count+1, digest

    def flush(self):
        if not self.pending:
            return
        started = time.perf_counter()
        blob = encode_block(self.pending)
        with self.db:
            first = decode_tagged(json.loads(self.pending[0][2]))
            self.db.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)', (self.pending[0][0],
                len(self.pending), blob, hashlib.sha256(blob).hexdigest(),
                first['previous_hash'], self.pending[-1][3]))
        self.flushed_bytes += len(blob)
        self.flush_seconds += time.perf_counter()-started
        self.pending, self.pending_bytes = [], 0

    def seal(self, *, expected_count, expected_head_hash):
        if self.sealed or (self.count, self.head_hash) != (expected_count, expected_head_hash):
            raise ValueError('seal differs from independently supplied checkpoint')
        self.flush()
        with self.db:
            self.db.execute('INSERT INTO seal VALUES (?,?,?)', (FORMAT, self.count, self.head_hash))
        self.sealed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()  # Unflushed input stays unacknowledged; no implicit seal.


class CompactReader:
    def __init__(self, path, *, expected_count, expected_head_hash):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError('compact journal missing')
        self.db = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro', uri=True)
        self.count, self.head_hash = expected_count, expected_head_hash
        try:
            self._check_seal()
        except BaseException:
            self.db.close()
            raise

    def _check_seal(self):
        if self.db.execute('SELECT * FROM seal').fetchall() != [(FORMAT, self.count, self.head_hash)]:
            raise ValueError('sealed journal identity required')

    def rows(self):
        count = 0
        for start, length, blob, digest in self.db.execute('SELECT start,count,body,sha256 FROM blocks ORDER BY start'):
            if start != count or hashlib.sha256(blob).hexdigest() != digest:
                raise ValueError('block identity or continuity differs')
            rows = decode_block(blob)
            if len(rows) != length or [r[0] for r in rows] != list(range(start, start+length)):
                raise ValueError('block coverage differs')
            yield from rows
            count += length
        if count != self.count:
            raise ValueError('compact journal truncated')
        self._check_seal()

    def entries(self):
        yield from verified_rows(self.rows(), self.count, self.head_hash)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
