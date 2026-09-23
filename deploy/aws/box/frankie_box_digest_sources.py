"""Replayable exact calculation-layer tables from independently pinned JSON files.

This module reads the project's calculation layers; it uses no cloud model API.
Python memory is bounded by a row/group, layer/column metadata and SQLite caches.
Snapshots and databases remain in scratch on success and failure.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat

import frankie_box_digest_render as DG


ROW_FIELDS = ('member_rows', 'lifecycle_rows', 'companion_rows', 'declarations', 'first_last_pairs')
META_FIELDS = frozenset(('status', 'reason', 'producer', 'member_paths', 'lifecycle_sections',
                         'section_counts', 'count', 'partial', 'section', 'matching_rule', 'traversal'))


class _JSON:
    """Decode one array element at a time; never collect a row array."""
    def __init__(self, handle):
        self.handle, self.buffer, self.pos, self.eof = handle, '', 0, False
        self.decoder = json.JSONDecoder()

    def fill(self):
        self.buffer = self.buffer[self.pos:]
        self.pos = 0
        chunk = self.handle.read(65536)
        self.buffer += chunk
        self.eof = not chunk

    def space(self):
        while True:
            while self.pos < len(self.buffer) and self.buffer[self.pos] in ' \t\r\n':
                self.pos += 1
            if self.pos < len(self.buffer) or self.eof:
                return
            self.fill()

    def peek(self):
        self.space()
        return self.buffer[self.pos:self.pos+1]

    def expect(self, character):
        if self.peek() != character:
            raise ValueError('invalid layer JSON: expected ' + character)
        self.pos += 1

    def value(self):
        first = self.peek()
        if not first:
            raise ValueError('truncated layer JSON')
        if first not in '{["':
            # A number may end a read chunk midway through its exponent/digits.
            # Scan its complete token before asking JSONDecoder to interpret it.
            pieces = []
            while True:
                start = self.pos
                while self.pos < len(self.buffer) and self.buffer[self.pos] not in ' \t\r\n,]}':
                    self.pos += 1
                pieces.append(self.buffer[start:self.pos])
                if self.pos < len(self.buffer) or self.eof:
                    return json.loads(''.join(pieces))
                self.fill()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.pos)
            except ValueError:
                if self.eof:
                    raise ValueError('invalid or truncated layer JSON') from None
                self.fill()
            else:
                self.pos = end
                return value

    def array(self):
        self.expect('[')
        if self.peek() == ']':
            self.pos += 1
            return
        while True:
            yield self.value()
            if self.peek() == ']':
                self.pos += 1
                return
            self.expect(',')

    def skip(self):
        """Validate unused structures without materializing their arrays/maps."""
        first = self.peek()
        if first == '[':
            self.expect('[')
            if self.peek() == ']':
                self.pos += 1
                return
            while True:
                self.skip()
                if self.peek() == ']':
                    self.pos += 1
                    return
                self.expect(',')
        elif first == '{':
            self.expect('{')
            if self.peek() == '}':
                self.pos += 1
                return
            while True:
                if not isinstance(self.value(), str):
                    raise ValueError('JSON object key must be a string')
                self.expect(':')
                self.skip()
                if self.peek() == '}':
                    self.pos += 1
                    return
                self.expect(',')
        else:
            self.value()


def _dump(value):
    return json.dumps(value, separators=(',', ':'))


def _group_key(value):
    # Python dict keys merge equal numeric keys (including bool/int/float). The
    # stored group_index cell still receives the legacy typed conflict check.
    if value is None:
        return 'null'
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError('group_index must be finite')
            numerator, denominator = value.as_integer_ratio()
        else:
            numerator, denominator = int(value), 1
        return 'number:%d/%d' % (numerator, denominator)
    if isinstance(value, str):
        return 'string:' + value
    raise ValueError('group_index must be a scalar sortable key')


def _compare_groups(left, right):
    a, b = json.loads(left), json.loads(right)
    a, b = (a is None, a), (b is None, b)
    return (a > b) - (a < b)


class _Rows:
    def __init__(self, db, query, parameters=(), transform=None):
        self.db, self.query, self.parameters, self.transform = db, query, parameters, transform

    def __iter__(self):
        for (payload,) in self.db.execute(self.query, self.parameters):
            row = json.loads(payload)
            yield self.transform(row) if self.transform else row

    def __len__(self):
        return self.db.execute('SELECT count(*) FROM (' + self.query + ')', self.parameters).fetchone()[0]


class _Members:
    def __init__(self, db):
        self.db = db

    def __iter__(self):
        for (key,) in self.db.execute('SELECT key FROM groups ORDER BY value COLLATE group_order'):
            flat = {}
            for column, payload in self.db.execute(
                    'SELECT column_name,payload FROM members WHERE group_key=? ORDER BY ordinal', (key,)):
                flat[column] = DG._spell(json.loads(payload))
            yield DG._nest(flat)

    def __len__(self):
        return self.db.execute('SELECT count(*) FROM groups').fetchone()[0]


class BedrockSources:
    """Pinned layer entries -> ordered replayable table iterables.

    entries is an insertion-ordered mapping of layer names to path/bytes/sha256
    witnesses. A fresh scratch directory is mandatory; it is never removed.
    .verdict is the first dictionary traversal, including an empty dictionary.
    .tables and its iterables are valid until this context is closed.
    """
    def __init__(self, entries, scratch_directory):
        self.root = Path(scratch_directory)
        self.root.mkdir(parents=True, exist_ok=False)
        self.db = sqlite3.connect(self.root/'sources.sqlite')
        self.db.execute('PRAGMA cache_size=-2048')
        self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('PRAGMA mmap_size=0')
        self.db.create_collation('group_order', _compare_groups)
        self.db.executescript('''
            CREATE TABLE rows (layer INTEGER, field TEXT, ordinal INTEGER, section TEXT, payload TEXT,
                               PRIMARY KEY(layer,field,ordinal));
            CREATE INDEX sections ON rows(layer,field,section,ordinal);
            CREATE TABLE groups (key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX group_sort ON groups(value COLLATE group_order);
            CREATE TABLE members (group_key TEXT, column_name TEXT, ordinal INTEGER, payload TEXT,
                                  PRIMARY KEY(group_key,column_name));
            CREATE INDEX member_order ON members(group_key,ordinal);
            CREATE TABLE layer_index (ordinal INTEGER PRIMARY KEY, payload TEXT);
            CREATE TABLE run (payload TEXT);
        ''')
        self.tables, self.verdict = {}, {}
        self.layer_count, self.derived = len(entries), 0
        try:
            metadata = []
            first_verdict = False
            for index, (name, pin) in enumerate(entries.items()):
                snapshot = self._snapshot(index, pin)
                meta, counts = self._read(index, snapshot)
                metadata.append(meta)
                if isinstance(meta.get('traversal'), dict) and not first_verdict:
                    self.verdict = meta['traversal']
                    first_verdict = True
                self.derived += meta.get('status') == 'derived'
                row = dict(layer=name, status=meta.get('status'), reason=meta.get('reason'), producer=meta.get('producer'),
                    member_paths=' '.join(meta.get('member_paths') or []),
                    lifecycle_sections=' '.join(meta.get('lifecycle_sections') or []),
                    section_counts=json.dumps(meta.get('section_counts') or {}, separators=(',', ':'), sort_keys=True),
                    member_count=counts.get('member_rows', 0), lifecycle_count=counts.get('lifecycle_rows', 0),
                    count=meta.get('count'), partial=' '.join(p['section'] for p in (meta.get('partial') or [])))
                self.db.execute('INSERT INTO layer_index VALUES (?,?)', (index, _dump(row)))
                if meta.get('status') == 'derived':
                    self._merge(index, name)
            if first_verdict:
                v = self.verdict
                row = dict(verdict=v.get('verdict'), failed_gates=' '.join(v.get('failed_gates') or []),
                    groups=v.get('groups'), records=v.get('records'), span_seconds=v.get('span_seconds'),
                    candidate_warmup_seconds=v.get('candidate_warmup_seconds'),
                    candidate_min_observations=v.get('candidate_min_observations'))
                self.db.execute('INSERT INTO run VALUES (?)', (_dump(row),))
                self.tables['bedrock.run'] = _Rows(self.db, 'SELECT payload FROM run')
            self.tables['bedrock.layers'] = _Rows(self.db, 'SELECT payload FROM layer_index ORDER BY ordinal')
            if self.db.execute('SELECT 1 FROM groups LIMIT 1').fetchone():
                self.tables['bedrock.members'] = _Members(self.db)
            sections = {}
            for index, meta in enumerate(metadata):
                if meta.get('status') != 'derived':
                    continue
                for section in meta.get('lifecycle_sections') or []:
                    rows = self._rows(index, 'lifecycle_rows', section)
                    if section not in sections and len(rows):
                        sections[section] = rows
            for section in sorted(sections):
                self.tables[f'bedrock.lifecycle.{section}'] = sections[section]
            for index, meta in enumerate(metadata):
                section = meta.get('section')
                if meta.get('status') != 'derived' or not section:
                    continue
                for field, prefix in (('companion_rows', 'companions'), ('declarations', 'declarations'),
                                      ('first_last_pairs', 'first_last')):
                    rows = self._rows(index, field)
                    if len(rows):
                        self.tables[f'bedrock.{prefix}.{section}'] = rows
                if meta.get('matching_rule'):
                    # Small rule metadata is persisted as a one-row source too.
                    self.db.execute('INSERT INTO rows VALUES (?,?,?,?,?)',
                                    (index, 'matching_rule', 0, None, _dump(meta['matching_rule'])))
                    self.tables[f'bedrock.matching_rule.{section}'] = self._rows(index, 'matching_rule')
            self.db.commit()
        except BaseException:
            self.db.commit()
            self.db.close()
            raise

    def _snapshot(self, index, pin):
        if (not isinstance(pin, dict) or type(pin.get('bytes')) is not int
                or pin['bytes'] < 0 or not isinstance(pin.get('sha256'), str)):
            raise ValueError('complete layer path/bytes/sha256 pin required')
        source = Path(pin['path'])
        target = self.root/('layer-%06d.json' % index)
        digest, size = hashlib.sha256(), 0
        with source.open('rb') as reader, target.open('xb') as writer:
            if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                raise ValueError('regular pinned layer file required')
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        if size != pin['bytes'] or digest.hexdigest() != pin['sha256']:
            raise ValueError('pinned layer bytes or sha256 differ')
        return target

    def _read(self, index, path):
        metadata, counts = {}, {}
        with path.open(encoding='utf-8') as handle:
            parser = _JSON(handle)
            parser.expect('{')
            if parser.peek() != '}':
                while True:
                    key = parser.value()
                    if not isinstance(key, str):
                        raise ValueError('JSON object key must be a string')
                    parser.expect(':')
                    if key in ROW_FIELDS:
                        # json.loads keeps the last duplicate key's value.
                        self.db.execute('DELETE FROM rows WHERE layer=? AND field=?', (index, key))
                        count = 0
                        if parser.peek() == '[':
                            for count, row in enumerate(parser.array(), 1):
                                section = _dump(row.get('emitting_section')) if isinstance(row, dict) else None
                                self.db.execute('INSERT INTO rows VALUES (?,?,?,?,?)',
                                                (index, key, count-1, section, _dump(row)))
                        elif parser.value():
                            raise ValueError('layer rows must be an array or null')
                        counts[key] = count
                    elif key in META_FIELDS:
                        metadata[key] = parser.value()
                    else:
                        parser.skip()
                    if parser.peek() == '}':
                        break
                    parser.expect(',')
            parser.expect('}')
            if parser.peek():
                raise ValueError('layer JSON has trailing content')
        return metadata, counts

    def _merge(self, index, name):
        for (payload,) in self.db.execute(
                'SELECT payload FROM rows WHERE layer=? AND field=? ORDER BY ordinal', (index, 'member_rows')):
            row = json.loads(payload)
            if 'group_index' not in row:
                raise ValueError('bedrock member projection of %s carries a row without the group key group_index' % name)
            value = row['group_index']
            key = _group_key(value)
            self.db.execute('INSERT OR IGNORE INTO groups VALUES (?,?)', (key, _dump(value)))
            ordinal = self.db.execute('SELECT count(*) FROM members WHERE group_key=?', (key,)).fetchone()[0]
            for column, value in row.items():
                if '[]' in column and not column.endswith('#count'):
                    column, value = column + '#count', DG._leaf_count(value)
                existing = self.db.execute('SELECT payload FROM members WHERE group_key=? AND column_name=?',
                                           (key, column)).fetchone()
                if existing:
                    if not DG._same(json.loads(existing[0]), value):
                        raise ValueError('bedrock member projection conflict: group %s column %s differs between layers (%s)' %
                                         (row['group_index'], column, name))
                    continue
                self.db.execute('INSERT INTO members VALUES (?,?,?,?)', (key, column, ordinal, _dump(value)))
                ordinal += 1

    def _rows(self, index, field, section=None):
        query = 'SELECT payload FROM rows WHERE layer=? AND field=?'
        parameters = (index, field)
        if field == 'lifecycle_rows':
            query += ' AND section=?'
            parameters += (_dump(section),)
        query += ' ORDER BY ordinal'
        excluded = ('declaration', 'section') if field == 'companion_rows' else ()
        return _Rows(self.db, query, parameters,
                     lambda row: {c: DG._spell(v) for c, v in row.items() if c not in excluded})

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
