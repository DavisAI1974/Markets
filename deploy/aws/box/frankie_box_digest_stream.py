"""Disk-backed writer of one DIGEST table block (the grammar itself lives in frankie_box_digest_render, DG; this module
only orchestrates its passes on disk).

Only one row/cell, column metadata, previous-row state and fixed SQLite caches are
held in memory. Caller-owned input/context may themselves be materialized.
The output is a fresh scratch artifact, NOT an atomic production publication.
Failures retain all scratch files; only a fully inverse-verified file returns.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import zlib

import frankie_box_digest_render as DG


def _pack(value):
    # Private spool codec: preserve tuple/list identity, insertion order and float
    # spelling. Do not normalize these rows through production layer JSON here.
    if isinstance(value, dict):
        return ['dict', [[k, _pack(v)] for k, v in value.items()]]
    if isinstance(value, (list, tuple)):
        return ['tuple' if isinstance(value, tuple) else 'list', [_pack(v) for v in value]]
    if isinstance(value, (bytes, bytearray)):           # DIGEST_V10: bytes reach the private spool exactly
        return ['bytearray' if isinstance(value, bytearray) else 'bytes', bytes(value).hex()]
    return ['scalar', value]


def _unpack(value):
    kind, payload = value
    if kind == 'dict':
        return {k: _unpack(v) for k, v in payload}
    if kind in ('list', 'tuple'):
        items = [_unpack(v) for v in payload]
        return tuple(items) if kind == 'tuple' else items
    if kind == 'bytes':
        return bytes.fromhex(payload)
    if kind == 'bytearray':
        return bytearray.fromhex(payload)
    return payload


def _dump(value):
    text = json.dumps(_pack(value), separators=(',', ':'))
    if not DG._same(_unpack(json.loads(text)), value):
        raise ValueError('private row spool cannot preserve the input type')
    return zlib.compress(text.encode(),1) if len(text) >= 256 else text


def _load(value):
    return _unpack(json.loads(zlib.decompress(value) if isinstance(value,bytes) else value))


def _database(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect(directory / 'table.sqlite')
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA temp_store=FILE')
    db.execute('PRAGMA mmap_size=0')
    return db


def _rows(db, table):
    # table is an internal literal, never caller SQL.
    for (payload,) in db.execute('SELECT payload FROM ' + table + ' ORDER BY ordinal'):
        yield _load(payload)


def _snapshot(db, name, rows, context):
    db.executescript('''
        CREATE TABLE source (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE cross_source (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE plans (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE final (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE frequency (key TEXT PRIMARY KEY, count INTEGER NOT NULL,
                                number INTEGER UNIQUE, inline INTEGER NOT NULL DEFAULT 0);
    ''')
    observer = DG.Observer()
    n = 0
    for n, row in enumerate(rows, 1):
        row = dict(row)
        observer.add(DG._flatten(row))
        db.execute('INSERT INTO source VALUES (?, ?)', (n - 1, _dump(row)))
    cross_specs = {column: spec for (table, column), spec in DG.CROSS_DERIVED.items() if table == name}
    sources = {spec[0] for spec in cross_specs.values() if (context or {}).get(spec[0]) is not None}
    if len(sources) > 1:
        raise ValueError('this primitive requires one sequential cross-table dependency')
    source = next(iter(sources), None)
    cross_n = 0
    if source is not None:
        wanted = {column for table, column in cross_specs.values() if table == source}
        for cross_n, row in enumerate(context[source], 1):
            flat = DG._flatten(row)
            db.execute('INSERT INTO cross_source VALUES (?, ?)',
                       (cross_n - 1, _dump({c: flat[c] for c in wanted if c in flat})))
    db.commit()
    return observer.facts(), n, source, cross_n


def _plan(db, name, facts, n, source, cross_n):
    columns = facts.columns
    first = None
    derived = {c: True for c in columns}
    constant = {c: True for c in columns}
    cross = {c: source is not None and cross_n == n and (name, c) in DG.CROSS_DERIVED for c in columns}
    prev, values, integers, lists = None, {}, {}, {}
    cross_rows = iter(_rows(db, 'cross_source'))
    for i, row in enumerate(_rows(db, 'source')):
        flat = DG._flatten(row)
        if first is None:
            first = flat
        cells = DG._plan_row(flat, columns, prev, values, integers, lists, facts)
        db.execute('INSERT INTO plans VALUES (?, ?)', (i, _dump(cells)))
        src = next(cross_rows, {})
        for j, c in enumerate(columns):
            derived[c] = derived[c] and cells[j][1] == '='
            constant[c] = constant[c] and c in flat and c in first and DG._same(flat[c], first[c])
            if cross[c]:
                sc = DG.CROSS_DERIVED[(name, c)][1]
                cross[c] = c in flat and sc in src and DG._same(flat[c], src[sc])
        prev = flat
    whole = DG.whole_marks(columns, n, derived, constant, cross)
    kept = [j for j, c in enumerate(columns) if c not in whole]
    scale_state = {j: [DG.SCALE_MAX, False] for j in kept}
    for cells in _rows(db, 'plans'):
        for j in kept:
            kind, text = cells[j]
            if kind != 'lit':
                db.execute('INSERT INTO frequency(key, count) VALUES (?, 1) '
                           'ON CONFLICT(key) DO UPDATE SET count=count+1', (DG.candidate_key(kind, text),))
            else:
                DG.scale_step(scale_state[j], text)
    scales = DG.scales_of(scale_state, columns)
    numbered = [0]

    def number(kind, text, key):
        # the first occurrence decides: the next number when the dictionary pays, else inline on every occurrence
        count, index, inline = db.execute('SELECT count, number, inline FROM frequency WHERE key=?', (key,)).fetchone()
        if index is None and not inline and count >= 2:
            if DG.dictionary_pays(count, DG.inline_cost(kind, text), numbered[0]):
                index = numbered[0]
                numbered[0] += 1
                db.execute('UPDATE frequency SET number=? WHERE key=?', (index, key))
            else:
                db.execute('UPDATE frequency SET inline=1 WHERE key=?', (key,))
        return index

    has_space = False
    for i, cells in enumerate(_rows(db, 'plans')):
        out = DG.finish_row(cells, kept, columns, scales, number)
        has_space = has_space or any(' ' in cell for cell in out)
        db.execute('INSERT INTO final VALUES (?, ?)', (i, _dump(out)))
    db.commit()
    return whole, scales, first or {}, '\t' if has_space else ' '


def _emit(handle, db, name, facts, n, whole, scales, first, sep):
    for line in DG.header_lines(name, n, sep, facts.columns, whole, first, scales, facts):
        handle.write(line + '\n')
    found = False
    for number, key in db.execute('SELECT number, key FROM frequency WHERE number IS NOT NULL ORDER BY number'):
        handle.write(('\t' if found else 'dictionary: ') + '@%d=%s' % (number, DG.entry_spelling(key)))
        found = True
    if found:
        handle.write('\n')
    for cells in _rows(db, 'final'):
        handle.write(sep.join(cells) + '\n')


class _Tokens:
    """Bounded buffered delimiter scanner; never read a complete dictionary line."""
    def __init__(self, handle):
        self.handle, self.buffer, self.pos, self.eof = handle, '', 0, False

    def _ensure(self, count):
        while len(self.buffer) - self.pos < count and not self.eof:
            chunk = self.handle.read(65536)
            self.buffer = self.buffer[self.pos:] + chunk
            self.pos = 0
            self.eof = not chunk

    def starts(self, prefix):
        self._ensure(len(prefix))
        return self.buffer.startswith(prefix, self.pos)

    def skip(self, prefix):
        if not self.starts(prefix):
            raise ValueError('expected ' + prefix)
        self.pos += len(prefix)

    def take(self, delimiters='\n'):
        pieces = []
        while True:
            self._ensure(1)
            ends = [p for c in delimiters if (p := self.buffer.find(c, self.pos)) >= 0]
            if ends:
                end = min(ends)
                pieces.append(self.buffer[self.pos:end])
                delimiter = self.buffer[end]
                self.pos = end + 1
                return ''.join(pieces), delimiter
            pieces.append(self.buffer[self.pos:])
            self.pos = len(self.buffer)
            if self.eof:
                raise ValueError('truncated table (missing delimiter)')

    def ended(self):
        self._ensure(1)
        return self.pos == len(self.buffer) and self.eof


def _verify(handle, db, expected_name, expected, context):
    tokens = _Tokens(handle)
    h = DG.Header(tokens)
    if h.name != expected_name:
        raise ValueError('table header/name mismatch')
    db.execute('CREATE TABLE dictionary (number INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    DG.read_dictionary(tokens, lambda number, text: db.execute('INSERT INTO dictionary VALUES (?, ?)', (number, text)))
    db.commit()

    def entry(number):
        found = db.execute('SELECT payload FROM dictionary WHERE number=?', (number,)).fetchone()
        if found is None:
            raise ValueError('unknown dictionary entry')
        return DG.entry_value(found[0])

    cross = {c: DG.CROSS_DERIVED[(h.name, c)] for c, mark in h.whole.items()
             if mark == '=' and (h.name, c) in DG.CROSS_DERIVED and (context or {}).get(DG.CROSS_DERIVED[(h.name, c)][0]) is not None}
    sources = {table: iter(context[table]) for table, _ in cross.values()}
    expected = iter(expected)
    decoder = DG.RowDecoder(h, entry)
    for i in range(h.n):
        line, _ = tokens.take()
        source_rows = {}
        for table, source in sources.items():
            try:
                source_rows[table] = DG._flatten(next(source))
            except StopIteration as error:
                raise ValueError('cross-table context truncated') from error
        row = decoder.decode(line, {c: source_rows[table][column] for c, (table, column) in cross.items()})
        try:
            original = next(expected)
        except StopIteration as error:
            raise ValueError('source rows shorter than table') from error
        if not DG._same(DG._unflatten(row), dict(original)):
            raise ValueError(f'table {h.name} row {i} does not round-trip')
    sentinel = object()
    if next(expected, sentinel) is not sentinel or any(next(source, sentinel) is not sentinel for source in sources.values()):
        raise ValueError('source rows longer than table')
    if not tokens.ended():
        raise ValueError('table has trailing content')
    return h.n


def verify_table(path, name, rows, scratch_directory, context=None):
    """Inverse-proof a single complete block; retain the independent dictionary DB."""
    db = _database(scratch_directory)
    try:
        with Path(path).open(encoding='utf-8', newline='') as handle:
            return _verify(handle, db, name, rows, context)
    finally:
        db.close()


def _identity(path):
    info = Path(path).stat()
    return [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]


def write_table(destination, name, rows, scratch_directory, context=None):
    """Write and verify a fresh scratch block; never replace existing evidence.

    rows and each applicable context source are consumed once into exact private
    disk spools. No string-returning compatibility renderer/parser is called.
    This API does not publish a production digest or promise bounded caller memory.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation is also the concurrency guard. Failure leaves this path.
    with destination.open('x', encoding='utf-8', newline='\n') as handle:
        db = _database(scratch_directory)
        try:
            facts, n, source, cross_n = _snapshot(db, name, rows, context)
            whole, scales, first, sep = _plan(db, name, facts, n, source, cross_n)
            _emit(handle, db, name, facts, n, whole, scales, first, sep)
            handle.flush()
            os.fsync(handle.fileno())
            before = _identity(destination)
            verified = verify_table(destination, name, _rows(db, 'source'),
                                    Path(scratch_directory) / 'inverse',
                                    {source: _rows(db, 'cross_source')} if source is not None else None)
            if _identity(destination) != before:
                raise ValueError('table changed during inverse proof')
            if verified != n:
                raise ValueError('verified table count mismatch')
            return dict(path=str(destination), rows=n, verified=True, verified_identity=before,
                        scratch_directory=str(scratch_directory))
        finally:
            db.close()
