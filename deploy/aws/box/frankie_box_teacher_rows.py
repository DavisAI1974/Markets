"""The teacher's rows, read ONE ROW AT A TIME, and the teacher's second set beside them.

1. The rows file host-dipole-classroom-source.c15.json is canonical_bytes(pack(snapshot)) (sunday_execution._save): one
   line of compact JSON whose top level is ["dict", [[key, packed value], ...]] in the snapshot's insertion order, the
   rows being the elements of the "rows" pair's ["tuple", [row, ...]]. Its consumers used to json.loads it WHOLE (the
   raw bytes, the packed tree and the unpacked snapshot all at once). RowsStream scans it in fixed chunks (bracket
   depth outside strings, vectorized), parses and unpacks each row element by itself (optionally only the fields the
   consumer uses), unpacks the other top-level fields from their own bytes, and hashes both identities on the same
   stream:
     sha256           the file's bytes (the claim / receipt / export pin value);
     snapshot hash    c15_journal.evidence_hash of the snapshot without source_snapshot_hash: SCHEMA, NUL and the
                      file's bytes with the source_snapshot_hash pair (and its separating comma) left out. pack() keeps
                      key order, so these are exactly the bytes evidence_hash re-packs from the whole-load snapshot.
   load() gives the same snapshot as unpack(json.loads(whole file)) (only unselected row fields left out).

2. The rows SIDECAR host-dipole-classroom-source.c15.rows.jsonl (the teacher's publication, 2026-10-09; written by
   frankie_box_experiment_teacher._write_rows_sidecar, receipt `rows_sidecar`): line 1 a header (schema
   FRANKIE_TEACHER_ROWS_SIDECAR_V1, the second set's FORMAT, row_keys, key_fields, clock_fields, plane_reference,
   clock_lock_time, the stream pins, entries_not_carried), then one snapshot row per line (plain JSON) with the second
   set under the header's row_keys. SidecarStream reads it line by line, hashed on the stream. Every name the readers
   use comes from that header (SIDECAR_FIELDS is only the fallback), so a rename on the writer is one place there.

3. Plane VALUES are references, not copies: planes[entry] is a list of [source, source_ordinal, input_cursor,
   instrument_id, known_at_ns] naming a row of that stream's pinned file (header streams[source].path; line
   source_ordinal; packed rows unpacked), or {carrier, element} for an entry the row itself carries, or [] with the
   reason in planes_absent. PlaneResolver reads a referenced row when a consumer needs its value: one forward pass per
   stream file, the rows held per step (a cache keyed by (source, ordinal)), counted ("resolved n plane rows"); a
   reference that cannot be read is listed with its reason, never dropped and never taken as the value.
"""
import hashlib
import json
from pathlib import Path

ROWS_FILE = 'host-dipole-classroom-source.c15.json'
SIDECAR_FILE = 'host-dipole-classroom-source.c15.rows.jsonl'
SIDECAR_SCHEMA = 'FRANKIE_TEACHER_ROWS_SIDECAR_V1'
CHUNK_BYTES = 8 << 20
LOOKAHEAD = 64                                 # bytes kept back so a pair's key is always whole in the buffer
HASH_KEY = 'source_snapshot_hash'
ROWS_KEY = 'rows'

# The sidecar's names (the fallback when its header does not name them; the header's own lists win):
SIDECAR_FIELDS = dict(
    row_keys=('key', 'clocks', 'clocks_absent', 'planes', 'planes_state', 'planes_absent', 'invalidated', 'coverage',
              'match', 'book_columns'),
    key_fields=('adapter_cursor', 'input_cursor', 'input_journal_ordinal', 'source_input_index', 'source_member_index',
                'session_id', 'instrument_id', 'terminal_prefix_hash'),
    clock_fields=('clock_event_time', 'clock_receive_time', 'clock_event_known_by', 'clock_feature_availability',
                  'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time'),
    plane_reference=('source', 'source_ordinal', 'input_cursor', 'instrument_id', 'known_at_ns'))
# The roles the readers use, each the row key that carries it (row_keys of the header; renamed here only)
ROLE_KEYS = dict(key='key', clocks='clocks', clocks_absent='clocks_absent', planes='planes', planes_state='planes_state',
                 planes_absent='planes_absent', invalidated='invalidated', coverage='coverage', match='match',
                 book_columns='book_columns')
KEY_CURSOR = 'adapter_cursor'                  # the key field that equals the row's cursor
LOCK_CLOCK = 'clock_lock_time'                 # stamped once at publication: the teacher's as_of (header clock_lock_time)
FIRST_SET_ROW_KEYS = ('cursor', 'target_hash', 'source_manifest_hash', 'source_prefix_hash', 'as_of_ts_recv_ns',
                      'ts_recv_ns', 'components', 'step_receipt_hash', 'dstate', 'raw_components')
SECOND_SET_LEDGER_SCHEMA = 'FRANKIE_CLASSROOM_SECOND_SET_V1'


def _codec():
    from research.kalshi.frankie_boss.c15_journal import SCHEMA, unpack
    return SCHEMA, unpack


def sidecar_of(rows_path):
    """The sidecar beside a rows file (or the rows directory)."""
    path = Path(rows_path)
    return (path if path.is_dir() else path.parent) / SIDECAR_FILE


def _unpack_row(tree, select, unpack, exclude=None):
    """One packed row element ["dict", [[k, v], ...]] unpacked: all fields, only `select`, or all but `exclude`."""
    if select is None and not exclude:
        return unpack(tree)
    if not (isinstance(tree, list) and tree and tree[0] == 'dict'):
        raise ValueError('teacher row is not a packed mapping')
    if select is not None:
        return {k: unpack(v) for k, v in tree[1] if k in select}
    return {k: unpack(v) for k, v in tree[1] if k not in exclude}


class RowsStream:
    """Iterate the rows (dicts) of the c15.json rows file one at a time. After the iteration: header (every other
    top-level field, unpacked, in file order), sha256 / bytes of the file, snapshot_hash (computed), snapshot_ok
    (computed == header source_snapshot_hash), rows (count), rows_tag (tuple/list), rows_position.
    select: None (whole rows) or row keys to unpack; exclude: row keys not to unpack."""

    def __init__(self, path, select=None, exclude=None):
        self.path = Path(path)
        self.select = None if select is None else frozenset(select)
        self.exclude = frozenset(exclude or ())
        self.header, self.sha256, self.bytes, self.snapshot_hash, self.snapshot_ok = None, None, None, None, None
        self.rows, self.rows_tag, self.rows_position = 0, None, None
        self._done = False

    def __iter__(self):
        if self._done:
            raise ValueError('a RowsStream is read once')
        self._done = True
        yield from self._iter_c15()

    def finish(self):
        if not self._done:
            for _ in self:
                pass
        return self

    def record(self):
        return dict(path=str(self.path), bytes=self.bytes, sha256=self.sha256, rows=self.rows,
                    snapshot_hash=self.snapshot_hash, snapshot_ok=self.snapshot_ok,
                    rule='read one row at a time (frankie_box_teacher_rows.RowsStream); the file and snapshot '
                         'identities hashed on the same stream; never loaded whole')

    def _iter_c15(self):
        import numpy as np
        SCHEMA, unpack = _codec()
        raw = hashlib.sha256()
        snap = hashlib.sha256(SCHEMA.encode() + b'\0')
        header = {}
        depth, in_str, bs_run = 0, False, 0
        A = 0                                   # absolute offset of buf[0]
        snap_fed, skipping = 0, False
        pair_index, pair_key, pair_parts, pair_start = -1, None, None, None
        in_rows, row_parts, row_start = False, None, None
        hash_pair_first = False
        leftover = b''
        first = True
        with self.path.open('rb') as handle:
            eof = False
            while not eof or leftover:
                chunk = b'' if eof else handle.read(CHUNK_BYTES)
                if not chunk:
                    eof = True
                buf = leftover + chunk
                if not buf:
                    break
                if not eof and len(buf) <= LOOKAHEAD:
                    leftover = buf
                    continue
                if first:
                    if not buf.startswith(b'["dict",['):
                        raise ValueError('%s is not a packed mapping (c15 canonical bytes)' % self.path)
                    first = False
                c = len(buf) if eof else len(buf) - LOOKAHEAD
                b = np.frombuffer(buf, dtype=np.uint8)
                n = len(b)
                idx = np.arange(n, dtype=np.int64)
                bs = b == 92
                m = np.maximum.accumulate(np.where(bs, -1 - bs_run, idx))
                m_prev = np.empty(n, dtype=np.int64)
                m_prev[0] = -1 - bs_run
                m_prev[1:] = m[:-1]
                escaped = ((idx - 1 - m_prev) & 1).astype(bool)
                quotes = (b == 34) & ~escaped
                qc = np.cumsum(quotes, dtype=np.int64) + (1 if in_str else 0)
                outside = (qc & 1) == 0
                opens = (b == 91) & outside
                closes = (b == 93) & outside
                d = depth + np.cumsum(opens.astype(np.int32) - closes.astype(np.int32), dtype=np.int64)
                wanted = (opens & ((d == 3) | (d == 6))) | (closes & ((d == 2) | (d == 5)))
                events = np.flatnonzero(wanted[:c])
                for i in events.tolist():
                    level = int(d[i])
                    if opens[i] and level == 3:                     # a top-level pair begins
                        pair_index += 1
                        end = buf.find(b'"', i + 2)
                        if buf[i + 1] != 34 or end < 0:
                            raise ValueError('top-level pair without a key in %s' % self.path)
                        pair_key = buf[i + 2:end].decode('ascii')
                        if pair_key == ROWS_KEY:
                            in_rows = True
                            self.rows_position = len(header)
                            tag_end = buf.find(b'"', end + 4)
                            self.rows_tag = buf[end + 4:tag_end].decode('ascii') if tag_end > 0 else None
                        else:
                            pair_parts, pair_start = bytearray(), i
                        if pair_key == HASH_KEY:
                            cut = A + i - 1 if pair_index > 0 else A + i
                            if cut > snap_fed:
                                snap.update(buf[snap_fed - A:cut - A])
                            snap_fed, skipping, hash_pair_first = cut, True, pair_index == 0
                    elif closes[i] and level == 2:                  # a top-level pair ends
                        if pair_key == ROWS_KEY:
                            in_rows = False
                        else:
                            pair_parts += buf[pair_start:i + 1]
                            tree = json.loads(bytes(pair_parts))
                            header[tree[0]] = unpack(tree[1])
                            pair_parts, pair_start = None, None
                        if pair_key == HASH_KEY:
                            snap_fed, skipping = A + i + (2 if hash_pair_first else 1), False
                        pair_key = None
                    elif in_rows and opens[i] and level == 6:      # a row element begins
                        row_parts, row_start = bytearray(), i
                    elif in_rows and closes[i] and level == 5:     # a row element ends
                        row_parts += buf[row_start:i + 1]
                        element = bytes(row_parts)
                        row_parts, row_start = None, None
                        self.rows += 1
                        yield _unpack_row(json.loads(element), self.select, unpack, self.exclude)
                # carry what is open past the commit point, and the state at it
                if pair_parts is not None:
                    pair_parts += buf[pair_start:c]
                    pair_start = 0
                if row_parts is not None:
                    row_parts += buf[row_start:c]
                    row_start = 0
                raw.update(buf[:c])
                if not skipping and snap_fed < A + c:
                    snap.update(buf[max(0, snap_fed - A):c])
                    snap_fed = A + c
                if c > 0:
                    depth = int(d[c - 1])
                    in_str = bool(qc[c - 1] & 1)
                    bs_run = int((c - 1) - m[c - 1])
                A += c
                leftover = buf[c:]
                if eof and not leftover:
                    break
        if depth != 0 or in_str or pair_parts is not None or row_parts is not None:
            raise ValueError('%s ended inside an element (truncated or not canonical)' % self.path)
        self.bytes, self.sha256 = A, raw.hexdigest()
        self.header = header
        self.snapshot_hash = snap.hexdigest()
        self.snapshot_ok = header.get(HASH_KEY) == self.snapshot_hash


def load(path, select=None, exclude=None):
    """(snapshot, stream): the snapshot as unpack(json.loads(whole file)) gives it (every top-level field in file order;
    rows a tuple of the rows, each with only the `select` fields when given / without the `exclude` fields), read one
    row at a time. stream carries sha256, bytes and the snapshot-hash check (stream.snapshot_ok)."""
    stream = RowsStream(path, select=select, exclude=exclude)
    rows = list(stream)
    order = list(stream.header)
    position = stream.rows_position if stream.rows_position is not None else len(order)
    order.insert(position, ROWS_KEY)
    snapshot = {}
    for key in order:
        snapshot[key] = (rows if stream.rows_tag == 'list' else tuple(rows)) if key == ROWS_KEY else stream.header[key]
    return snapshot, stream


def sha256_stream(path):
    """(bytes, sha256) of a file in 64 MB blocks."""
    digest, total = hashlib.sha256(), 0
    with Path(path).open('rb') as handle:
        while block := handle.read(64 << 20):
            digest.update(block)
            total += len(block)
    return total, digest.hexdigest()


# ---- the sidecar
class SidecarStream:
    """The rows sidecar line by line: .header (line 1), then each row (a dict), hashed on the stream (.sha256, .bytes,
    .rows after the iteration). select: row keys to keep (None = all)."""

    def __init__(self, path, select=None):
        self.path = Path(path)
        self.select = None if select is None else frozenset(select)
        self.header, self.sha256, self.bytes, self.rows = None, None, None, 0
        self._handle, self._digest, self._size = None, hashlib.sha256(), 0
        self._open()

    def _open(self):
        self._handle = self.path.open('rb')
        line = self._handle.readline()
        self._digest.update(line)
        self._size += len(line)
        self.header = json.loads(line)
        if self.header.get('schema') != SIDECAR_SCHEMA:
            self._handle.close()
            raise ValueError('%s is not a %s (schema %s)' % (self.path, SIDECAR_SCHEMA, self.header.get('schema')))

    def fields(self, name):
        """A name list of the header (row_keys, key_fields, clock_fields, plane_reference), else the fallback."""
        value = self.header.get(name)
        return tuple(value) if isinstance(value, (list, tuple)) and value else SIDECAR_FIELDS[name]

    def role(self, role):
        """The row key carrying a role: ROLE_KEYS[role] when the header's row_keys list it."""
        key = ROLE_KEYS[role]
        return key if key in self.fields('row_keys') else None

    def __iter__(self):
        try:
            for line in self._handle:
                self._digest.update(line)
                self._size += len(line)
                row = json.loads(line)
                self.rows += 1
                yield row if self.select is None else {k: v for k, v in row.items() if k in self.select}
        finally:
            self.close()

    def close(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            self.sha256, self.bytes = self._digest.hexdigest(), self._size

    def record(self):
        return dict(path=str(self.path), bytes=self.bytes, sha256=self.sha256, rows=self.rows,
                    format=self.header.get('format'), schema=self.header.get('schema'),
                    row_keys=list(self.fields('row_keys')), key_fields=list(self.fields('key_fields')),
                    clock_fields=list(self.fields('clock_fields')))


def sidecar_check(stream, teacher_receipt):
    """The sidecar as read against the teacher receipt's rows_sidecar (sha256, rows): equal or the difference listed."""
    pinned = (teacher_receipt or {}).get('rows_sidecar') or {}
    if not pinned.get('sha256'):
        return dict(status='no_pin', reason='the teacher receipt names no rows_sidecar sha256')
    same = pinned.get('sha256') == stream.sha256 and pinned.get('rows') in (None, stream.rows)
    return dict(status='equal' if same else 'differs', pinned=dict(sha256=pinned.get('sha256'), rows=pinned.get('rows')),
                read=dict(sha256=stream.sha256, rows=stream.rows))


# ---- plane references resolved by reading
class PlaneResolver:
    """Read the stream rows the plane references name. streams: the sidecar header's {name: pin(path, bytes, sha256)};
    day_file: the day file of the external publications ('external.<point>' references: its points[<point>].rows).
    One forward pass per stream file; a reference to an earlier row than the reader's position is served from the
    cache, else the file is read again from its start (counted: re_reads). Never raises for a reference: an unreadable
    one is returned as {'reference': ..., 'unresolved': reason}."""

    def __init__(self, streams, day_file=None):
        self.streams = dict(streams or {})
        self.day_file, self._day = day_file, None
        self._readers, self.cache = {}, {}
        self.counts = dict(resolved=0, from_cache=0, unresolved=0, re_reads=0, lines_read=0)
        self.unresolved = {}

    def _reader(self, source):
        pin = self.streams.get(source)
        if not isinstance(pin, dict) or not pin.get('path'):
            return None, 'no pinned stream file named %r in the sidecar header' % source
        path = Path(pin['path'])
        if not path.is_absolute() or '..' in path.parts:
            return None, 'the pinned stream path %s is not an absolute owner-local path' % path
        state = self._readers.get(source)
        if state is None:
            try:
                state = self._readers[source] = dict(handle=path.open('rb'), next=0)
            except OSError as error:
                return None, 'the pinned stream file %s cannot be opened (%s)' % (path, error)
        return state, None

    def _row(self, source, ordinal):
        if source.startswith('external.'):
            return self._external(source[len('external.'):], ordinal)
        state, why = self._reader(source)
        if state is None:
            return None, why
        if ordinal < state['next']:
            state['handle'].seek(0)
            state['next'] = 0
            self.counts['re_reads'] += 1
        line = None
        while state['next'] <= ordinal:
            line = state['handle'].readline()
            if not line:
                return None, 'the pinned stream %s ends before row %d' % (source, ordinal)
            state['next'] += 1
            self.counts['lines_read'] += 1
        value = json.loads(line)
        if isinstance(value, list) and value and isinstance(value[0], str):
            _, unpack = _codec()
            value = unpack(value)                       # a ROOT spool row (frame, price, structure) is packed
        return value, None

    def _external(self, point, ordinal):
        if self.day_file is None:
            return None, 'external publication %s: no day file given to resolve it' % point
        if self._day is None:
            try:
                self._day = json.loads(Path(self.day_file).read_bytes())
            except (OSError, ValueError) as error:
                return None, 'the day file %s cannot be read (%s)' % (self.day_file, error)
        table = (self._day.get('points') or {}).get(point)
        if not isinstance(table, dict) or not 0 <= ordinal < len(table.get('rows') or ()):
            return None, 'the day file has no row %d of point %s' % (ordinal, point)
        return dict(columns=table['columns'], row=table['rows'][ordinal]), None

    def resolve(self, reference):
        """{'reference': reference, 'value': the row} or {'reference': reference, 'unresolved': reason}."""
        try:
            source, ordinal = reference[0], int(reference[1])
        except (TypeError, ValueError, IndexError):
            self.counts['unresolved'] += 1
            return dict(reference=reference, unresolved='not a [source, source_ordinal, ...] reference')
        key = (source, ordinal)
        if key in self.cache:
            self.counts['from_cache'] += 1
            return dict(reference=reference, value=self.cache[key])
        try:
            value, why = self._row(source, ordinal)
        except (OSError, ValueError) as error:
            value, why = None, '%s: %s' % (type(error).__name__, error)
        if why is not None:
            self.counts['unresolved'] += 1
            self.unresolved[why] = self.unresolved.get(why, 0) + 1
            return dict(reference=reference, unresolved=why)
        self.cache[key] = value
        self.counts['resolved'] += 1
        return dict(reference=reference, value=value)

    def resolve_planes(self, planes):
        """{entry: [resolved...] | the element carrier as given | []} for one row's planes (every entry kept)."""
        out = {}
        for entry, value in (planes or {}).items():
            if isinstance(value, list):
                out[entry] = [self.resolve(ref) for ref in value]
            else:
                out[entry] = value
        return out

    def clear(self):
        """Drop the per-step cache (the readers keep their positions)."""
        self.cache.clear()

    def close(self):
        for state in self._readers.values():
            state['handle'].close()
        self._readers.clear()

    def record(self):
        return dict(counts=dict(self.counts), unresolved_reasons=dict(self.unresolved),
                    note='resolved %d plane rows (%d from the step cache, %d unresolved, %d re-reads from a file start)'
                         % (self.counts['resolved'], self.counts['from_cache'], self.counts['unresolved'],
                            self.counts['re_reads']),
                    rule='each reference read from its pinned stream file by its row; values are read, never copied '
                         'into the teacher rows; an unreadable reference is listed with its reason')


# ---- the second set per row, for the classroom lesson (whole, aligned, every absence listed)
def _ranges(values):
    """Consecutive integers as [first, last] pairs (lossless)."""
    out = []
    for v in values:
        if out and out[-1][1] + 1 == v:
            out[-1][1] = v
        else:
            out.append([v, v])
    return out


def _listing(ordinals, cursors):
    return dict(rows=len(ordinals), ordinal_ranges=_ranges(ordinals), cursors=[cursors[o] for o in ordinals])


def second_set_lesson(rows_dir, out_path, snapshot_rows, *, anchor_cursors=(), teacher_receipt=None, day_file=None,
                      as_of=None):
    """The teacher's second set for the classroom (Greg, 2026-10-09: whatever Frankie sees is pinned together with the
    99 planes on the same clocks). Streams the sidecar beside the rows, writes every row's second set WHOLE to
    `out_path` (JSON lines, one per row: ordinal, cursor, target_hash and every row key the header lists; the plane
    values stay references), aligned on the classroom's own snapshot rows (cursor, target_hash), and returns the
    record: per role the rows that carry it and those that do not (listed by ordinal ranges and cursors), the key
    cursor checks, the match status, per clock and per plane entry the rows carried / absent with the reasons, the
    clock_lock_time (the teacher's as_of: lock time does not exist before Frankie reads), and the anchor rows' planes
    RESOLVED by reading their references (anchor_cursors). An older teacher (no sidecar) is listed: every row absent."""
    import os
    rows_dir = Path(rows_dir)
    side = sidecar_of(rows_dir)
    cursors = [r.get('cursor') for r in snapshot_rows]
    if not side.is_file():
        return dict(schema=SECOND_SET_LEDGER_SCHEMA, status='not_carried', sidecar=str(side),
                    reason='no rows sidecar beside the teacher rows (a teacher before the second set): the second set '
                           'is absent on every row', rows=len(cursors),
                    absent=dict(all=_listing(list(range(len(cursors))), cursors)))
    stream = SidecarStream(side)
    roles = {role: stream.role(role) for role in ROLE_KEYS}
    row_keys = stream.fields('row_keys')
    clock_fields = stream.fields('clock_fields')
    absent = {role: [] for role in ROLE_KEYS}
    match_status, mismatched, key_differs, align = {}, [], [], []
    clocks_carried, clocks_absent_reasons = {c: 0 for c in clock_fields}, {}
    planes = {}
    book_status = {}
    anchors = {}
    wanted = set(anchor_cursors or ())
    digest, size = hashlib.sha256(), 0
    out_path = Path(out_path)
    pending = out_path.with_name(out_path.name + '.pending')
    side_cursors = []
    with pending.open('wb') as handle:
        for ordinal, row in enumerate(stream):
            cursor = row.get('cursor')
            side_cursors.append(cursor)
            mine = snapshot_rows[ordinal] if ordinal < len(snapshot_rows) else None
            if mine is None or (mine.get('cursor'), mine.get('target_hash')) != (cursor, row.get('target_hash')):
                align.append(dict(ordinal=ordinal, classroom=None if mine is None else [mine.get('cursor'), mine.get('target_hash')],
                                  sidecar=[cursor, row.get('target_hash')]))
            record = dict(ordinal=ordinal, cursor=cursor, target_hash=row.get('target_hash'),
                          ts_recv_ns=row.get('ts_recv_ns'))
            for key in row_keys:
                record[key] = row.get(key)
            for role, key in roles.items():
                if key is None or row.get(key) is None:
                    absent[role].append(ordinal)
            key = row.get(roles['key']) if roles['key'] else None
            if isinstance(key, dict) and key.get(KEY_CURSOR) != cursor:
                key_differs.append(dict(ordinal=ordinal, cursor=cursor, key_cursor=key.get(KEY_CURSOR)))
            match = row.get(roles['match']) if roles['match'] else None
            if isinstance(match, dict):
                status = match.get('status')
                match_status[status] = match_status.get(status, 0) + 1
                if status != 'matched':
                    mismatched.append(dict(ordinal=ordinal, cursor=cursor, mismatches=match.get('mismatches')))
            gone = (row.get(roles['clocks_absent']) if roles['clocks_absent'] else None) or {}
            for clock in clock_fields:
                if clock in gone:
                    reasons = clocks_absent_reasons.setdefault(clock, {})
                    reasons[gone[clock]] = reasons.get(gone[clock], 0) + 1
                elif isinstance(row.get(roles['clocks'] or ''), dict) and clock in row[roles['clocks']]:
                    clocks_carried[clock] += 1
            plane_reasons = (row.get(roles['planes_absent']) if roles['planes_absent'] else None) or {}
            for entry, value in ((row.get(roles['planes']) if roles['planes'] else None) or {}).items():
                slot = planes.setdefault(entry, dict(rows_with_references=0, references=0, rows_element=0,
                                                     rows_absent=0, absent_reasons={}))
                if isinstance(value, list) and value:
                    slot['rows_with_references'] += 1
                    slot['references'] += len(value)
                elif isinstance(value, dict):
                    slot['rows_element'] += 1
                else:
                    slot['rows_absent'] += 1
                    reason = plane_reasons.get(entry, 'no reason recorded')
                    slot['absent_reasons'][reason] = slot['absent_reasons'].get(reason, 0) + 1
            book = row.get(roles['book_columns']) if roles['book_columns'] else None
            if isinstance(book, dict):
                status = book.get('status') or ('group' if book.get('group') else 'other')
                book_status[status] = book_status.get(status, 0) + 1
            if cursor in wanted:
                anchors[cursor] = record
            data = (json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
            digest.update(data)
            size += len(data)
            handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, out_path)
    for ordinal in range(len(side_cursors), len(snapshot_rows)):
        align.append(dict(ordinal=ordinal, classroom=[snapshot_rows[ordinal].get('cursor'),
                                                      snapshot_rows[ordinal].get('target_hash')], sidecar=None))
    # the anchor rows' planes, read by their references (resolving is reading, not copying)
    resolver = PlaneResolver(stream.header.get('streams'), day_file=day_file)
    resolved = {}
    try:
        for cursor in sorted(anchors):
            record = anchors[cursor]
            resolved[str(cursor)] = dict(cursor=cursor, key=record.get(roles['key']) if roles['key'] else None,
                                         clocks=record.get(roles['clocks']) if roles['clocks'] else None,
                                         planes=resolver.resolve_planes(record.get(roles['planes']) if roles['planes']
                                                                        else None),
                                         book_columns=record.get(roles['book_columns']) if roles['book_columns'] else None)
    finally:
        resolver.close()
    lock = stream.header.get('clock_lock_time')
    late = []
    if as_of is not None and isinstance(lock, dict) and type(lock.get('value')) is int and lock['value'] > as_of:
        late.append(dict(clock=LOCK_CLOCK, value=lock['value'], as_of=as_of))
    return dict(
        schema=SECOND_SET_LEDGER_SCHEMA, status='carried', sidecar=stream.record(),
        sidecar_check=sidecar_check(stream, teacher_receipt),
        file=dict(path=str(out_path), bytes=size, sha256=digest.hexdigest(), rows=len(side_cursors),
                  rule='one line per row: ordinal, cursor, target_hash, ts_recv_ns and every sidecar row key whole; '
                       'plane values are the references the teacher published'),
        format=stream.header.get('format'), names=dict(row_keys=list(row_keys), roles=roles,
                                                       key_fields=list(stream.fields('key_fields')),
                                                       clock_fields=list(clock_fields),
                                                       plane_reference=list(stream.fields('plane_reference'))),
        rows=len(side_cursors), classroom_rows=len(snapshot_rows),
        alignment=dict(differs=align, matched=len(snapshot_rows) - len([a for a in align if a['classroom']]),
                       rule='row by row on (cursor, target_hash); a difference is listed, never dropped or refused'),
        carried={role: len(side_cursors) - len(ordinals) for role, ordinals in absent.items()},
        absent={role: _listing(ordinals, side_cursors) for role, ordinals in absent.items() if ordinals},
        key_cursor_differs=key_differs, match_status=match_status, mismatched_rows=mismatched,
        clocks=dict(carried_rows=clocks_carried, absent_reasons=clocks_absent_reasons),
        clock_lock_time=dict(lock or {}, meaning='the teacher\'s as_of, stamped once at publication: lock time does not '
                                                 'exist before Frankie reads'),
        clock_after_cutoff=late,
        planes=planes, entries_not_carried=stream.header.get('entries_not_carried'),
        book_columns=dict(status_rows=book_status),
        anchors_resolved=dict(rows=resolved, resolver=resolver.record(),
                              rule='the second set at the classroom\'s anchor rows (each component\'s first / last / '
                                   'minimum / maximum PRESENT cursor), planes read by their references'),
        rule=('the teacher\'s second set per row, aligned on the row cursor and target_hash, every value whole in '
              'file; a row without a part is listed (absent.<role>), never skipped; the names are the sidecar '
              'header\'s'))


def second_set_summary(lesson):
    """The lesson record without the per-row anchors' resolved values (for receipts; the values are in the lesson)."""
    if not isinstance(lesson, dict):
        return lesson
    out = dict(lesson)
    anchors = out.get('anchors_resolved')
    if isinstance(anchors, dict):
        out['anchors_resolved'] = dict(rows=sorted(anchors.get('rows') or {}), resolver=anchors.get('resolver'))
    return out


def second_set_at_cutoff(rows_dir, through_cursor, *, day_file=None):
    """The second set of the last teacher row at or before the cutoff (through_cursor), its planes resolved by reading
    their references: the teacher's own instant at the cutoff, aligned on its key and clocks. (record, None) or
    (None, why). One pass over the sidecar."""
    side = sidecar_of(rows_dir)
    if not side.is_file():
        return None, 'no rows sidecar beside the teacher rows (a teacher before the second set)'
    stream = SidecarStream(side)
    last, after = None, 0
    for row in stream:
        cursor = row.get('cursor')
        if type(cursor) is int and cursor <= through_cursor:
            last = row
        else:
            after += 1
    if last is None:
        return None, 'no teacher row at or before the cutoff cursor %s' % through_cursor
    roles = {role: stream.role(role) for role in ROLE_KEYS}
    resolver = PlaneResolver(stream.header.get('streams'), day_file=day_file)
    try:
        planes = resolver.resolve_planes(last.get(roles['planes']) if roles['planes'] else None)
    finally:
        resolver.close()
    return dict(schema='FRANKIE_TEACHER_SECOND_SET_AT_CUTOFF_V1', cursor=last.get('cursor'),
                through_cursor=through_cursor, rows_after_cutoff=after,
                **{role: last.get(key) for role, key in roles.items() if key is not None and role != 'planes'},
                planes=planes, clock_lock_time=stream.header.get('clock_lock_time'), sidecar=stream.record(),
                resolver=resolver.record(),
                rule='the last teacher row at or before the cutoff: its key, clocks and book columns whole, its planes '
                     'read by their references'), None


def second_set_field(rows_dir, role, leaf, *, entry=None, day_file=None):
    """One second-set leaf per teacher row, streamed (the exchange's claim ledger on a second-set name): yields
    (cursor, value, why) for every row; `leaf` a dotted path inside the role's value (for planes: `entry` names the
    plane entry (entry names carry dots) and `leaf` the dotted path inside each resolved row; the value is the list of
    that leaf over all the entry's references at the row). why is None when a value
    is there, else the reason it is not (listed by the caller, never dropped)."""
    side = sidecar_of(rows_dir)
    stream = SidecarStream(side)
    key = stream.role(role)
    resolver = PlaneResolver(stream.header.get('streams'), day_file=day_file) if role == 'planes' else None
    parts = [p for p in str(leaf).split('.') if p] if leaf else []
    try:
        for row in stream:
            cursor = row.get('cursor')
            value = row.get(key) if key else None
            if value is None:
                yield cursor, None, 'the row carries no %s' % role
                continue
            if role == 'planes':
                rest = parts
                carried = value.get(entry) if isinstance(value, dict) else None
                if not isinstance(carried, list) or not carried:
                    yield cursor, None, ((row.get(stream.role('planes_absent') or '') or {}).get(entry)
                                         or 'entry %s not carried by a plane row here' % entry)
                    continue
                values = []
                for ref in carried:
                    got = resolver.resolve(ref)
                    values.append(_dig(got.get('value'), rest) if 'value' in got else None)
                resolver.clear()
                yield cursor, values, None
                continue
            found = _dig(value, parts)
            yield cursor, found, None if found is not None else 'leaf %s absent in this row\'s %s' % (leaf, role)
    finally:
        if resolver is not None:
            resolver.close()


def _dig(value, parts):
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.lstrip('-').isdigit() and -len(value) <= int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value
