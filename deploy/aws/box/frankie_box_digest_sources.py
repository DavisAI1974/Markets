"""Replayable exact calculation-layer tables from independently pinned JSON files.

This module reads the project's calculation layers; it uses no cloud model API.
Python memory is bounded by a row/group, layer/column metadata and SQLite caches.
Snapshots and databases remain in scratch on success and failure.
"""
from __future__ import annotations

import hashlib
import gzip
import zlib
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


def _payload(value):
    text = _dump(value)
    return zlib.compress(text.encode(),1) if len(text) >= 256 else text


def _decoded(value):
    return json.loads(zlib.decompress(value) if isinstance(value,bytes) else value)


def _member_row(row):
    # Apply the existing digest leaf-count reducer before private SQLite storage.
    # Exact projected arrays remain in the independently pinned gzip JSON layer.
    reduced = {}
    for column,value in row.items():
        if '[]' in column and not column.endswith('#count'):
            column,value = column+'#count',DG._leaf_count(value)
        if column in reduced and not DG._same(reduced[column],value):
            raise ValueError('conflicting reduced member columns')
        reduced[column] = value
    return reduced


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
            row = _decoded(payload)
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
                flat[column] = DG._spell(_decoded(payload))
            yield DG._nest(flat)

    def __len__(self):
        return self.db.execute('SELECT count(*) FROM groups').fetchone()[0]


def _prepare_layer(job):
    index,pin,root = job
    obj = BedrockSources.__new__(BedrockSources)
    obj.root = Path(root)/('prepare-%06d' % index)
    obj.root.mkdir()
    obj._references = {}
    database = obj.root/'rows.sqlite'
    obj.db = sqlite3.connect(database)
    obj.db.execute('PRAGMA cache_size=-2048')
    obj.db.execute('PRAGMA temp_store=FILE')
    obj.db.execute('CREATE TABLE rows (layer INTEGER, field TEXT, ordinal INTEGER, section TEXT, payload TEXT, PRIMARY KEY(layer,field,ordinal))')
    try:
        path = obj._snapshot(index,pin)
        meta,counts = obj._read(index,path)
        obj.db.commit()
        return dict(path=str(database),meta=meta,counts=counts)
    finally:
        obj.db.close()


PREPARED_SCHEMA = 'FRANKIE_PREPARED_CALCULATION_LAYER_V2'
FRAGMENTS_PER_JOB = 4
SHARDS = 14


def _member_read(handle, offset):
    """Decompress exactly one gzip member at offset: (bytes, compressed length)."""
    handle.seek(offset)
    decoder, out, consumed = zlib.decompressobj(31), [], 0
    while not decoder.eof:
        chunk = handle.read(1 << 16)
        if not chunk:
            raise ValueError('truncated projected layer member')
        out.append(decoder.decompress(chunk))
        consumed += len(chunk)
    return b''.join(out), consumed - len(decoder.unused_data)


def _range_receipts(projection_root):
    """The retained plan's completed range receipts, in range order, per ledger kind."""
    with (projection_root / 'plan.json').open('rb') as stream:
        plan = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipts = {}
    for kind in ('member', 'lifecycle'):
        values, position = [], 0
        for path in sorted((projection_root / kind).glob('range-[0-9][0-9][0-9][0-9][0-9][0-9].json')):
            value = json.loads(path.read_bytes())
            binding = value.get('binding') or {}
            if (binding.get('plan') != plan or binding.get('kind') != kind or binding.get('index') != len(values)
                    or value.get('actual_start') != position or value.get('readback_verified') is not True):
                raise ValueError('retained projection range receipts differ from the ordered plan')
            position = value['actual_end']
            values.append(value)
        receipts[kind] = values
    return receipts


def _published_layout(path, name, receipts):
    """Walk one published gzip-json layer (projection._publish layout) without inflating its row arrays: the small
    metadata members are decompressed; each row array is located fragment by fragment from the range receipts.
    Returns (metadata object with each fragment array as [], {key: [(offset, bytes, sha256, rows), ...]})."""
    separator = len(gzip.compress(b',\n', compresslevel=1, mtime=0))
    size, parts, arrays = path.stat().st_size, [], {}
    with path.open('rb') as handle:
        text, offset = _member_read(handle, 0)
        if text != b'{':
            raise ValueError('projected layer does not open an object')
        parts.append(text)
        while True:
            text, width = _member_read(handle, offset)
            offset += width
            parts.append(text)
            if text == b'}\n':
                break
            key = json.loads(text[1:-1] if text.startswith(b',') else text[:-1])
            value, width = _member_read(handle, offset)
            offset += width
            if value != b'[':
                parts.append(value)
                continue
            kind = {'member_rows': 'member', 'lifecycle_rows': 'lifecycle'}.get(key)
            if kind is None:
                raise ValueError('unexpected projected row array ' + str(key))
            fragment = name if any(name in r['fragments'] for r in receipts[kind]) else '__section_mirror'
            located = []
            for r in receipts[kind]:
                item = r['fragments'].get(fragment)
                if item is None:
                    continue
                if located:
                    handle.seek(offset)
                    if zlib.decompress(handle.read(separator), 31) != b',\n':
                        raise ValueError('projected layer fragment separator differs')
                    offset += separator
                located.append((offset, item['bytes'], item['sha256'], item['rows']))
                offset += item['bytes']
            close, width = _member_read(handle, offset)
            if close != b']':
                raise ValueError('projected layer fragments do not match the range receipts')
            offset += width
            parts.append(b'[]')
            arrays[key] = located
    if offset != size:
        raise ValueError('projected layer length differs from its located members')
    return json.loads(b''.join(parts)), arrays


def _prepare_fragments(job):
    """Rows of consecutive fragments of one published layer, in order: (section, payload, group key)."""
    path, field, fragments = job
    out = []
    with open(path, 'rb') as handle:
        for offset, width, digest, rows in fragments:
            handle.seek(offset)
            raw = handle.read(width)
            if len(raw) != width or hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('published layer fragment differs from its range receipt')
            decoder = zlib.decompressobj(31)
            text = decoder.decompress(raw) + decoder.flush()
            if not decoder.eof or decoder.unused_data:
                raise ValueError('published layer fragment is not one gzip member')
            lines = text.split(b'\n') if text else []
            if len(lines) != rows:
                raise ValueError('published layer fragment row count differs from its range receipt')
            for i, line in enumerate(lines):
                if i + 1 < len(lines):
                    if not line.endswith(b','):
                        raise ValueError('published layer fragment row separator differs')
                    line = line[:-1]
                row = json.loads(line)
                section = _dump(row.get('emitting_section')) if isinstance(row, dict) else None
                if field == 'member_rows':
                    reduced = _member_row(row)
                    key = _group_key(reduced['group_index']) if 'group_index' in reduced else None
                    out.append((section, _payload(reduced), key))
                else:
                    out.append((section, _payload(row), None))
    return out


def _prepared_database(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA temp_store=FILE')
    db.execute('CREATE TABLE rows (layer INTEGER, field TEXT, ordinal INTEGER, section TEXT, payload TEXT, PRIMARY KEY(layer,field,ordinal))')
    db.execute('CREATE TABLE member_keys (ordinal INTEGER PRIMARY KEY, group_key TEXT, shard INTEGER)')
    return db


def _prepare_published(index, name, pin, root, receipts, workers):
    """One gzip-json projected layer, its row fragments spread over the pinned helpers; same rows.sqlite contents
    as _prepare_layer, plus each member row's group key and shard for the sharded merge."""
    import threading
    obj = BedrockSources.__new__(BedrockSources)
    obj.root = Path(root)/('prepare-%06d' % index)
    obj.root.mkdir()
    obj._references = {}
    snapshot, failure = [], []
    def pinned():
        try:
            snapshot.append(obj._snapshot(index, pin))
        except BaseException as error:
            failure.append(error)
    checker = threading.Thread(target=pinned)
    checker.start()
    path = Path(pin['path'])
    from frankie_box_finalization import file_identity
    before = file_identity(path)
    database = obj.root/'rows.sqlite'
    db = _prepared_database(database)
    try:
        document, arrays = _published_layout(path, name, receipts)
        metadata, counts = {}, {}
        for key in sorted(document):
            value = document[key]
            if key in arrays:
                count, expected = 0, sum(f[3] for f in arrays[key])
                jobs = [(str(path), key, arrays[key][i:i + FRAGMENTS_PER_JOB])
                        for i in range(0, len(arrays[key]), FRAGMENTS_PER_JOB)]
                for rows in workers.ordered(_prepare_fragments, jobs):
                    db.executemany('INSERT INTO rows VALUES (?,?,?,?,?)',
                                   [(index, key, count + i, section, payload) for i, (section, payload, _) in enumerate(rows)])
                    if key == 'member_rows':
                        db.executemany('INSERT INTO member_keys VALUES (?,?,?)',
                                       [(count + i, group, zlib.crc32(group.encode()) % SHARDS if group is not None else 0)
                                        for i, (_, _, group) in enumerate(rows)])
                    count += len(rows)
                if count != expected:
                    raise ValueError('published layer rows differ from the range receipts')
                counts[key] = count
            elif key in ROW_FIELDS:
                count = 0
                if isinstance(value, list):
                    for count, row in enumerate(value, 1):
                        section = _dump(row.get('emitting_section')) if isinstance(row, dict) else None
                        reduced = _member_row(row) if key == 'member_rows' else row
                        db.execute('INSERT INTO rows VALUES (?,?,?,?,?)', (index, key, count-1, section, _payload(reduced)))
                        if key == 'member_rows':
                            group = _group_key(reduced['group_index']) if 'group_index' in reduced else None
                            db.execute('INSERT INTO member_keys VALUES (?,?,?)',
                                       (count-1, group, zlib.crc32(group.encode()) % SHARDS if group is not None else 0))
                elif value:
                    raise ValueError('layer rows must be an array or null')
                counts[key] = count
            elif key in META_FIELDS:
                metadata[key] = value
        db.commit()
    finally:
        db.close()
        checker.join()
    if failure:
        raise failure[0]
    if file_identity(path) != before:
        raise ValueError('projected layer changed during consumption')
    receipt = dict(schema=PREPARED_SCHEMA, index=index, pin={k: pin.get(k) for k in ('path', 'bytes', 'sha256', 'encoding')},
                   meta=metadata, counts=counts, database=str(database), database_bytes=database.stat().st_size)
    with (obj.root/'receipt.json').open('x') as output:
        json.dump(receipt, output, sort_keys=True)
        output.flush(); os.fsync(output.fileno())
    return dict(path=str(database), meta=metadata, counts=counts, keyed=True)


def _reusable_prepared(index, pin, root):
    """A prepared layer from an earlier digest attempt of this calculation root with the same layer pin, if its
    receipt and database are intact (save point for reruns)."""
    derived = Path(root).parent.parent
    for receipt in sorted(derived.glob('.digest-*/calculation-layers/prepare-*/receipt.json')):
        try:
            value = json.loads(receipt.read_bytes())
        except (OSError, ValueError):
            continue
        database = Path(value.get('database') or '')
        if (value.get('schema') == PREPARED_SCHEMA and value.get('index') == index
                and value.get('pin') == {k: pin.get(k) for k in ('path', 'bytes', 'sha256', 'encoding')}
                and database.parent == receipt.parent and database.is_file()
                and database.stat().st_size == value.get('database_bytes')):
            return dict(path=str(database), meta=value['meta'], counts=value['counts'], keyed=True, reused=str(receipt))
    return None


def _prepare_layers(entries,root):
    from frankie_box_projection import Workers,save
    workers = Workers()
    try:
        save(Path(root)/'preparation-workers.json',workers.receipt())
        prepared, receipts = [], {}
        for i,(name,pin) in enumerate(entries.items()):
            if pin.get('encoding') != 'gzip-json':
                prepared.append(next(workers.ordered(_prepare_layer,[(i,pin,str(root))])))
                continue
            reused = _reusable_prepared(i, pin, root)
            if reused is not None:
                prepared.append(reused)
                continue
            projection = Path(pin['path']).resolve().parent.parent
            if projection not in receipts:
                receipts[projection] = _range_receipts(projection)
            prepared.append(_prepare_published(i, name, pin, root, receipts[projection], workers))
        return prepared
    finally:
        workers.close()


def _merge_shard(job):
    """One group-key shard of the member merge: every derived layer in order, each row in ordinal order, exactly
    the _merge rules (first group value kept, first column ordinal kept, typed conflict check)."""
    shard, layers, output = job
    db = sqlite3.connect(output)
    db.execute('PRAGMA cache_size=-65536')
    db.execute('PRAGMA temp_store=FILE')
    db.executescript('''
        CREATE TABLE groups (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE members (group_key TEXT, column_name TEXT, ordinal INTEGER, payload TEXT,
                              PRIMARY KEY(group_key,column_name));
    ''')
    try:
        for index, name, database in layers:
            source = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
            try:
                for payload, key in source.execute(
                        'SELECT r.payload, k.group_key FROM rows r JOIN member_keys k ON k.ordinal = r.ordinal '
                        'WHERE r.layer=? AND r.field=? AND k.shard=? ORDER BY r.ordinal', (index, 'member_rows', shard)):
                    row = _decoded(payload)
                    if 'group_index' not in row:
                        raise ValueError('bedrock member projection of %s carries a row without the group key group_index' % name)
                    db.execute('INSERT OR IGNORE INTO groups VALUES (?,?)', (key, _dump(row['group_index'])))
                    retained = {column:(ordinal,_decoded(value)) for column,ordinal,value in db.execute(
                        'SELECT column_name,ordinal,payload FROM members WHERE group_key=? ORDER BY ordinal',(key,))}
                    ordinal, additions = len(retained), []
                    for column,value in row.items():
                        if '[]' in column and not column.endswith('#count'):
                            column,value = column+'#count',DG._leaf_count(value)
                        if column in retained:
                            if not DG._same(retained[column][1],value):
                                raise ValueError('bedrock member projection conflict: group %s column %s differs between layers (%s)' %
                                                 (row['group_index'],column,name))
                            continue
                        retained[column]=(ordinal,value)
                        additions.append((key,column,ordinal,_payload(value)))
                        ordinal += 1
                    db.executemany('INSERT INTO members VALUES (?,?,?,?)',additions)
            finally:
                source.close()
        db.commit()
    finally:
        db.close()
    return output


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
        self._references = {}
        self.layer_count, self.derived = len(entries), 0
        try:
            metadata = []
            prepared = _prepare_layers(entries,self.root)
            # Keyed (projected) layers merge their member rows by group-key shard on the helpers; the member rows
            # themselves are never read from sources.sqlite, only the merged groups/members.
            keyed, sharded = all(p.get('keyed') for p in prepared), []
            first_verdict = False
            for index, (name, pin) in enumerate(entries.items()):
                saved = prepared[index]
                self.db.execute('ATTACH DATABASE ? AS prepared',(saved['path'],))
                if keyed:
                    self.db.execute("INSERT INTO rows SELECT * FROM prepared.rows WHERE field != 'member_rows'")
                else:
                    self.db.execute('INSERT INTO rows SELECT * FROM prepared.rows')
                self.db.commit()
                self.db.execute('DETACH DATABASE prepared')
                meta,counts = saved['meta'],saved['counts']
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
                self.db.execute('INSERT INTO layer_index VALUES (?,?)', (index, _payload(row)))
                if meta.get('status') == 'derived':
                    if keyed:
                        sharded.append((index, name, saved['path']))
                    else:
                        self._merge(index, name)
            if sharded:
                self._merge_sharded(sharded)
            if first_verdict:
                v = self.verdict
                row = dict(verdict=v.get('verdict'), failed_gates=' '.join(v.get('failed_gates') or []),
                    groups=v.get('groups'), records=v.get('records'), span_seconds=v.get('span_seconds'),
                    candidate_warmup_seconds=v.get('candidate_warmup_seconds'),
                    candidate_min_observations=v.get('candidate_min_observations'))
                self.db.execute('INSERT INTO run VALUES (?)', (_payload(row),))
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
                                    (index, 'matching_rule', 0, None, _payload(meta['matching_rule'])))
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
        if pin.get('encoding') == 'gzip-json':
            from frankie_box_finalization import file_identity
            before = file_identity(source)
            with source.open('rb') as stream:
                actual = hashlib.file_digest(stream,'sha256').hexdigest()
            if before[2] != pin['bytes'] or actual != pin['sha256'] or file_identity(source) != before:
                raise ValueError('compressed projected layer witness differs')
            self._references[str(source)] = before
            with (self.root/('layer-%06d.reference.json' % index)).open('x') as output:
                json.dump(dict(pin=pin,identity=before),output,sort_keys=True)
            return source
        if pin.get('encoding') is not None:
            raise ValueError('unknown projected layer encoding')
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
        compressed = str(path) in self._references
        opener = gzip.open if compressed else open
        with opener(path,mode='rt',encoding='utf-8') as handle:
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
                                                (index, key, count-1, section, _payload(_member_row(row) if key == 'member_rows' else row)))
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
        if compressed:
            from frankie_box_finalization import file_identity
            if file_identity(path) != self._references[str(path)]:
                raise ValueError('projected layer changed during consumption')
        return metadata, counts

    def _merge_sharded(self, layers):
        from frankie_box_projection import Workers
        workers = Workers()
        try:
            jobs = [(shard, layers, str(self.root/('merge-%02d.sqlite' % shard))) for shard in range(SHARDS)]
            for output in workers.ordered(_merge_shard, jobs):
                self.db.execute('ATTACH DATABASE ? AS shard', (output,))
                self.db.execute('INSERT INTO groups SELECT * FROM shard.groups')
                self.db.execute('INSERT INTO members SELECT * FROM shard.members')
                self.db.commit()
                self.db.execute('DETACH DATABASE shard')
        finally:
            workers.close()

    def _merge(self, index, name):
        for (payload,) in self.db.execute(
                'SELECT payload FROM rows WHERE layer=? AND field=? ORDER BY ordinal', (index, 'member_rows')):
            row = _decoded(payload)
            if 'group_index' not in row:
                raise ValueError('bedrock member projection of %s carries a row without the group key group_index' % name)
            value = row['group_index']
            key = _group_key(value)
            self.db.execute('INSERT OR IGNORE INTO groups VALUES (?,?)', (key, _dump(value)))
            retained = {column:(ordinal,_decoded(payload)) for column,ordinal,payload in self.db.execute(
                'SELECT column_name,ordinal,payload FROM members WHERE group_key=? ORDER BY ordinal',(key,))}
            ordinal = len(retained)
            additions = []
            for column,value in row.items():
                if '[]' in column and not column.endswith('#count'):
                    column,value = column+'#count',DG._leaf_count(value)
                if column in retained:
                    if not DG._same(retained[column][1],value):
                        raise ValueError('bedrock member projection conflict: group %s column %s differs between layers (%s)' %
                                         (row['group_index'],column,name))
                    continue
                retained[column]=(ordinal,value)
                additions.append((key,column,ordinal,_payload(value)))
                ordinal += 1
            self.db.executemany('INSERT INTO members VALUES (?,?,?,?)',additions)

    def _rows(self, index, field, section=None):
        query = 'SELECT payload FROM rows WHERE layer=? AND field=?'
        parameters = (index, field)
        if field == 'lifecycle_rows':
            query += ' AND section=?'
            parameters += (_dump(section),)
        query += ' ORDER BY ordinal'
        excluded = ('declaration', 'section') if field == 'companion_rows' else ()
        rows = _Rows(self.db, query, parameters,
                     lambda row: {c: DG._spell(v) for c, v in row.items() if c not in excluded})
        rows.excluded = excluded
        return rows

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
