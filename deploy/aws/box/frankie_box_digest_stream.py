"""Disk-backed DIGEST_V5 table grammar primitive; production DIGEST_V6 integration is separate.

Only one row/cell, column metadata, previous-row state and fixed SQLite caches are
held in memory. Caller-owned input/context may themselves be materialized.
The output is a fresh scratch artifact, NOT an atomic production publication.
Failures retain all scratch files; only a fully inverse-verified file returns.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import sqlite3

import frankie_box_digest_render as DG


def _pack(value):
    # Private spool codec: preserve tuple/list identity, insertion order and float
    # spelling. Do not normalize these rows through production layer JSON here.
    if isinstance(value, dict):
        return ['dict', [[k, _pack(v)] for k, v in value.items()]]
    if isinstance(value, (list, tuple)):
        return ['tuple' if isinstance(value, tuple) else 'list', [_pack(v) for v in value]]
    return ['scalar', value]


def _unpack(value):
    kind, payload = value
    if kind == 'dict':
        return {k: _unpack(v) for k, v in payload}
    if kind in ('list', 'tuple'):
        items = [_unpack(v) for v in payload]
        return tuple(items) if kind == 'tuple' else items
    return payload


def _dump(value):
    return json.dumps(_pack(value), separators=(',', ':'))


def _load(value):
    return _unpack(json.loads(value))


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
                                number INTEGER UNIQUE);
    ''')
    columns = {}
    n = 0
    for n, row in enumerate(rows, 1):
        row = dict(row)
        for column in DG._flatten(row):
            if not column or column[0] in '=^' or any(c in column for c in ('\t', '\n', '=', ' ')):
                raise ValueError(f'column name {column!r} cannot be spelled in a table header')
            columns.setdefault(column, None)
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
    return list(columns), n, source, cross_n


def _plan(db, name, columns, n, source, cross_n):
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
        cells = DG._plan_row(flat, columns, prev, values, integers, lists)
        db.execute('INSERT INTO plans VALUES (?, ?)', (i, _dump(cells)))
        src = next(cross_rows, {})
        for j, c in enumerate(columns):
            derived[c] = derived[c] and cells[j][1] == '='
            constant[c] = constant[c] and c in flat and c in first and DG._same(flat[c], first[c])
            if cross[c]:
                sc = DG.CROSS_DERIVED[(name, c)][1]
                cross[c] = c in flat and sc in src and DG._same(flat[c], src[sc])
        prev = flat
    whole = {c: '=' if cross[c] or derived[c] else '^' for c in columns
             if cross[c] or (n and (derived[c] or constant[c]))}
    kept = [j for j, c in enumerate(columns) if c not in whole]
    scale_state = {j: [DG.SCALE_MAX, False] for j in kept}
    for cells in _rows(db, 'plans'):
        for j in kept:
            kind, text = cells[j]
            if kind != 'lit':
                key = json.dumps(text) if kind == 'str' else text
                db.execute('INSERT INTO frequency(key, count) VALUES (?, 1) '
                           'ON CONFLICT(key) DO UPDATE SET count=count+1', (key,))
            elif DG._INT_CELL.fullmatch(text):
                k, _ = scale_state[j]
                value, z = abs(int(text)), 0
                if value:
                    while value % 10 == 0 and z < k:
                        value //= 10
                        z += 1
                    k = min(k, z)
                scale_state[j] = [k, True]
    scales = {columns[j]: 10 ** k for j, (k, seen) in scale_state.items() if seen and k >= DG.SCALE_MIN}
    number, has_space = 0, False
    for i, cells in enumerate(_rows(db, 'plans')):
        out = []
        for j in kept:
            kind, text = cells[j]
            if kind == 'lit':
                scale = scales.get(columns[j])
                out.append(DG._scaled(text, scale) if scale and DG._INT_CELL.fullmatch(text) else text)
                continue
            key = json.dumps(text) if kind == 'str' else text
            count, index = db.execute('SELECT count, number FROM frequency WHERE key=?', (key,)).fetchone()
            if count >= 2:
                if index is None:
                    index, number = number, number + 1
                    db.execute('UPDATE frequency SET number=? WHERE key=?', (index, key))
                out.append('@%d' % index)
            elif kind == 'str':
                out.append('S' + text if '\t' not in text and '\n' not in text else 'J' + key)
            else:
                out.append('J' + text)
        out = DG._collapse(out)
        has_space = has_space or any(' ' in cell for cell in out)
        db.execute('INSERT INTO final VALUES (?, ?)', (i, _dump(out)))
    db.commit()
    return whole, scales, first or {}, '\t' if has_space else ' '


def _emit(handle, db, name, columns, n, whole, scales, first, sep):
    handle.write(f'### table {name}: {n} rows, sep={"space" if sep == " " else "tab"}, columns: ')
    handle.write('\t'.join(whole.get(c, '') + c for c in columns) + '\n')
    constants = [c for c in columns if whole.get(c) == '^']
    if constants:
        handle.write('constants: ')
        for i, c in enumerate(constants):
            value = first[c]
            text = ('U' + json.dumps(list(value), separators=(',', ':'), sort_keys=True)) if isinstance(value, tuple) else json.dumps(value, separators=(',', ':'), sort_keys=True)
            handle.write(('\t' if i else '') + c + '=' + text)
        handle.write('\n')
    if scales:
        handle.write('scales: ' + '\t'.join('%s=%d' % (c, k) for c, k in scales.items()) + '\n')
    found = False
    for number, key in db.execute('SELECT number, key FROM frequency WHERE number IS NOT NULL ORDER BY number'):
        handle.write(('\t' if found else 'dictionary: ') + '@%d=%s' % (number, key))
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


def _expanded(line, sep, kept):
    if not kept:
        if line:
            raise ValueError('constant-only table carries unexpected cells')
        return []
    out = []
    for cell in line.split(sep):
        count = int(cell[1:]) if len(cell) > 1 and cell[0] in DG.RUN_MARKS and cell[1:].isdigit() else 1
        if len(out) + count > len(kept):
            raise ValueError('table row expands beyond declared columns')
        out.extend([cell[0]] * count if count != 1 else [cell])
    if len(out) != len(kept):
        raise ValueError('table row has wrong cell count')
    return out


def _verify(handle, db, expected_name, expected, context):
    tokens = _Tokens(handle)
    header, _ = tokens.take()
    m = re.fullmatch(r'### table (\S+): (\d+) rows, sep=(space|tab), columns: (.*)', header)
    if m is None or m.group(1) != expected_name:
        raise ValueError('table header/name mismatch')
    name, n, sep = m.group(1), int(m.group(2)), ' ' if m.group(3) == 'space' else '\t'
    declared = m.group(4).split('\t') if m.group(4) else []
    columns = [c.lstrip('=^') for c in declared]
    whole = {c.lstrip('=^'): c[0] for c in declared if c[:1] in '=^'}
    kept = [c for c in columns if c not in whole]
    constants, scales = {}, {}
    if tokens.starts('constants: '):
        tokens.skip('constants: ')
        line, _ = tokens.take()
        for item in line.split('\t'):
            k, _, value = item.partition('=')
            constants[k] = tuple(json.loads(value[1:])) if value.startswith('U') else json.loads(value)
    if tokens.starts('scales: '):
        tokens.skip('scales: ')
        line, _ = tokens.take()
        for item in line.split('\t'):
            k, _, value = item.partition('=')
            scales[k] = int(value)
    db.execute('CREATE TABLE dictionary (number INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    if tokens.starts('dictionary: '):
        tokens.skip('dictionary: ')
        number = 0
        while True:
            item, delimiter = tokens.take('\t\n')
            k, equal, value = item.partition('=')
            if not equal or k != '@%d' % number:
                raise ValueError('dictionary numbering mismatch')
            json.loads(value)  # Validate one entry, never retain the whole dictionary.
            db.execute('INSERT INTO dictionary VALUES (?, ?)', (number, value))
            number += 1
            if delimiter == '\n':
                break
    db.commit()
    cross = {c: DG.CROSS_DERIVED[(name, c)] for c, mark in whole.items()
             if mark == '=' and (name, c) in DG.CROSS_DERIVED and (context or {}).get(DG.CROSS_DERIVED[(name, c)][0]) is not None}
    sources = {table: iter(context[table]) for table, _ in cross.values()}
    expected = iter(expected)
    prev_row, prev_values, prev_ints, prev_lists = None, {}, {}, {}
    for i in range(n):
        line, _ = tokens.take()
        cells = _expanded(line, sep, kept)
        row = copy.deepcopy(constants)
        derived_cols = {c for c, mark in whole.items() if mark == '=' and c not in cross}
        positional, paired = {}, {}
        source_rows = {}
        for table, source in sources.items():
            try:
                source_rows[table] = DG._flatten(next(source))
            except StopIteration as error:
                raise ValueError('cross-table context truncated') from error
        for c, (table, column) in cross.items():
            row[c] = copy.deepcopy(source_rows[table][column])
        for c, cell in zip(kept, cells):
            if cell == '?':
                continue
            if cell == DG.NONE:
                v = None
            elif cell == DG.TRUE:
                v = True
            elif cell == DG.FALSE:
                v = False
            elif cell == '=':
                derived_cols.add(c)
                continue
            elif cell == DG.SAME:
                v = copy.deepcopy(prev_values[c])
            elif cell.startswith('@'):
                entry = db.execute('SELECT payload FROM dictionary WHERE number=?', (int(cell[1:]),)).fetchone()
                if entry is None:
                    raise ValueError('unknown dictionary entry')
                v = json.loads(entry[0])
            elif cell.startswith('S'):
                v = cell[1:]
            elif cell.startswith('J'):
                v = json.loads(cell[1:])
            elif cell.startswith('U'):
                v = tuple(json.loads(cell[1:]))
            elif cell.startswith('K'):
                positional[c] = [int(x) for x in cell[1:].split(',')] if cell[1:] else []
                continue
            elif cell.startswith('I'):
                parts = cell[1:].split(',')
                start = prev_lists[c] + int(parts[0]) if parts[0][:1] in '+-' and isinstance(prev_lists.get(c), int) else int(parts[0])
                v = [start]
                for delta in parts[1:]:
                    v.append(v[-1] + int(delta))
            elif cell.startswith('~'):
                paired[c] = int(cell[1:])
                continue
            elif cell == 'nan':
                v = float('nan')
            elif re.fullmatch(r'-?\d+/\d+', cell):
                num, _, den = cell.partition('/')
                v = float(int(num)) / float(int(den))
            elif cell.startswith('+') or (cell.startswith('-') and c.endswith(DG.DELTA_KEYS) and isinstance(prev_ints.get(c), int) and re.fullmatch(r'-\d+', cell)):
                v = prev_ints[c] + int(cell) * scales.get(c, 1)
            elif re.fullmatch(r'-?\d+', cell):
                v = int(cell) * scales.get(c, 1)
            else:
                v = float(cell)
            row[c] = v
        for c, offset in paired.items():
            if DG.PAIRED[c] not in row:
                raise ValueError('paired column absent')
            row[c] = row[DG.PAIRED[c]] + offset
        for c, positions in positional.items():
            row[c] = [row['order_ids'][position] for position in positions]
        for c in DG._derived_order(columns):
            if c in derived_cols:
                value = DG._recompute(row, c, prev_row)
                if c.startswith(('action_counts.', 'side_counts.')) and value == 0:
                    continue
                row[c] = value
        try:
            original = next(expected)
        except StopIteration as error:
            raise ValueError('source rows shorter than table') from error
        if not DG._same(DG._unflatten(row), dict(original)):
            raise ValueError(f'table {name} row {i} does not round-trip')
        for c, v in row.items():
            prev_values[c] = v
            if isinstance(v, int) and not isinstance(v, bool):
                prev_ints[c] = v
            if DG._int_list(v):
                prev_lists[c] = v[0]
        prev_row = row
    sentinel = object()
    if next(expected, sentinel) is not sentinel or any(next(source, sentinel) is not sentinel for source in sources.values()):
        raise ValueError('source rows longer than table')
    if not tokens.ended():
        raise ValueError('table has trailing content')
    return n


def verify_table(path, name, rows, scratch_directory, context=None):
    """Inverse-proof a single complete block; retain the independent dictionary DB."""
    db = _database(scratch_directory)
    try:
        with Path(path).open(encoding='utf-8', newline='') as handle:
            return _verify(handle, db, name, rows, context)
    finally:
        db.close()


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
            columns, n, source, cross_n = _snapshot(db, name, rows, context)
            whole, scales, first, sep = _plan(db, name, columns, n, source, cross_n)
            _emit(handle, db, name, columns, n, whole, scales, first, sep)
            handle.flush()
            os.fsync(handle.fileno())
            verified = verify_table(destination, name, _rows(db, 'source'),
                                    Path(scratch_directory) / 'inverse',
                                    {source: _rows(db, 'cross_source')} if source is not None else None)
            if verified != n:
                raise ValueError('verified table count mismatch')
            return dict(path=str(destination), rows=n, verified=True, scratch_directory=str(scratch_directory))
        finally:
            db.close()
