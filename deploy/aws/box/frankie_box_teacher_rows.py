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
                 book_columns='book_columns', state_split='state_split')
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


def sidecar_header(rows_dir):
    """(path, header or None, why): line 1 of the sidecar beside a rows directory, read alone (the rows are not read)."""
    side = sidecar_of(rows_dir)
    if not side.is_file():
        return side, None, 'no rows sidecar at %s' % side
    try:
        with side.open('rb') as handle:
            header = json.loads(handle.readline())
    except (OSError, ValueError) as error:
        return side, None, 'the sidecar header is unreadable (%s)' % error
    return side, header, None


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
                      as_of=None, blocks=None):
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
    # blocks: the sealed blocks to read (a partial sidecar bounded by them, each verified; listed on the record)
    stream = SidecarStream(side) if blocks is None else BlockSidecarStream(rows_dir, blocks)
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


def second_set_at_cutoff(rows_dir, through_cursor, *, day_file=None, blocks=None):
    """The second set of the last teacher row at or before the cutoff (through_cursor), its planes resolved by reading
    their references: the teacher's own instant at the cutoff, aligned on its key and clocks. (record, None) or
    (None, why). One pass over the sidecar."""
    side = sidecar_of(rows_dir)
    if not side.is_file():
        return None, 'no rows sidecar beside the teacher rows (a teacher before the second set)'
    stream = SidecarStream(side) if blocks is None else BlockSidecarStream(rows_dir, blocks)
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


def second_set_field(rows_dir, role, leaf, *, entry=None, day_file=None, through_cursor=None):
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
            if through_cursor is not None and (type(cursor) is not int or cursor > through_cursor):
                yield cursor, None, 'after the cutoff'      # not read further, never resolved
                continue
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


# ---- a second-set leaf ledgered over the rows (the exchange's claims; Jev's material up to his cutoff)
SECOND_SET_PREFIX = 'dipole.second_set.'
SECOND_SET_NAME_RE = (r'dipole\.second_set\.(?:(planes)\[([^\]]+)\](?:\.(.+))?|(key|clocks|book_columns|state_split)\.(.+))')


def second_set_leaf_ledger(rows_dir, name, *, through_cursor=None, day_file=None):
    """(ledger, summary) of one second-set leaf (dipole.second_set.<key|clocks|book_columns|state_split>.<leaf> or
    dipole.second_set.planes[<entry>].<leaf>) over every teacher row of the sidecar, or (None, why). through_cursor:
    rows after it are not ledgered (counted in summary.rows_after_cutoff_excluded, never read into the ledger). A row
    without a finite number is MISSING with its reason counted; a plane with several references at one row is not
    reduced to one value (listed with the count)."""
    import math
    import re
    from research.kalshi.frankie_boss import dipole_classroom as DC
    match = re.fullmatch(SECOND_SET_NAME_RE, str(name))
    if match is None:
        return None, ('not a second-set leaf name (dipole.second_set.<key|clocks|book_columns|state_split>.<leaf> or '
                      'planes[<entry>].<leaf>)')
    role, entry, leaf = (('planes', match[2], match[3] or '') if match[1] else (match[4], None, match[5]))
    if not sidecar_of(rows_dir).is_file():
        return None, 'no rows sidecar beside the teacher rows (a teacher before the second set)'
    ledger, reasons, after = [], {}, 0
    for cursor, value, why in second_set_field(rows_dir, role, leaf, entry=entry, day_file=day_file,
                                               through_cursor=through_cursor):
        if through_cursor is not None and (type(cursor) is not int or cursor > through_cursor):
            after += 1
            continue
        if why is None and role == 'planes':
            numeric = [v for v in value if type(v) in (int, float) and math.isfinite(v)]
            if len(value) != 1:
                why = '%d references at this row: not reduced to one value' % len(value)
            elif not numeric:
                why = 'the referenced row carries no finite number at this leaf'
            else:
                value = numeric[0]
        elif why is None and (type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value)):
            why = 'not a finite number (%s)' % type(value).__name__
        if why is not None:
            reasons[why] = reasons.get(why, 0) + 1
        ledger.append(dict(cursor=cursor, value=value if why is None else None, state='PRESENT' if why is None else 'MISSING'))
    available = sum(p['state'] == 'PRESENT' for p in ledger)
    return ledger, dict(series=name, entity=None, leaf=leaf, role=role, entry=entry, rows=len(ledger),
                        available=available, unavailable=reasons, direction=DC._direction(ledger),
                        through_cursor=through_cursor, rows_after_cutoff_excluded=after,
                        representation='the teacher\'s second set (rows sidecar); a plane read by its reference')


# ---- a teacher's own reading of the whole second set (Greg, 2026-10-09: "BOTH teachers are getting the 2nd group")
# Each teacher (the BOSS teacher's knowledge step, the exchange's two teacher seats, the scientific teacher's lessons)
# reads the teacher publication's second set WHOLE beside its own work: every sidecar row streamed (key, clocks, the
# plane references, the book columns, the per-row state split), the day's state split read whole, the account read
# whole from the receipt, and the full lists (clock mismatches, book-event differences) streamed whole. Plane VALUES
# stay references to the ROOT's stream rows (only copies avoided); each stream file named by them is checked on disk.
# Nothing is cut, capped or sampled; an absent part is listed with its reason and the reader goes on (never fatal).
# The pinned key (19 columns, 171 pairs) is never rebuilt from any of this: the second set is read beside it.
READING_SCHEMA = 'FRANKIE_TEACHER_SECOND_SET_READING_V1'
TEACHER_RECEIPT_FILE = 'receipt.json'
SECOND_SET_PKL = 'teacher-second-set.pkl'
STATE_SPLIT_DAY_FILE = 'teacher-state-split.json'
MISMATCHES_LIST = 'teacher-second-set-mismatches.jsonl'
BOOK_DIFFERENCES_LIST = 'teacher-book-event-differences.jsonl'
RECONCILIATION_LIST = 'teacher-reconciliation-differences.jsonl'   # written by the teacher findings (account entry)
READ_ROLES = ('key', 'clocks', 'planes', 'book_columns', 'state_split')
READING_FILES = dict(boss_teacher='teacher-second-set-read.boss.json')
PART_WORDS = dict(rows_sidecar='every row of the rows sidecar (key, clocks, plane references, book columns, per-row '
                               'state split)',
                  second_set_file='the second-set file (the same records, pinned)',
                  state_split_day='the day\'s state split', account='the account',
                  mismatches_list='the full clock-mismatch list',
                  book_event_differences_list='the full book-event difference list',
                  reconciliation_differences_list='the full reconciliation-difference list')


def _file_identity(path):
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return dict(bytes=st.st_size, mtime_ns=st.st_mtime_ns, inode=st.st_ino)


def _stream_lines(path):
    """(bytes, sha256, lines) of a file read whole in fixed chunks."""
    digest, size, lines = hashlib.sha256(), 0, 0
    with Path(path).open('rb') as handle:
        while True:
            chunk = handle.read(CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b'\n')
    return size, digest.hexdigest(), lines


def _pinned_list(rows_dir, pin, name):
    """A full list beside the receipt ({file, count, sha256}) streamed whole and checked against its pin."""
    pin = pin if isinstance(pin, dict) else None
    path = Path(rows_dir) / ((pin or {}).get('file') or name)
    if not path.is_file():
        return dict(status='absent', path=str(path), reason='not on disk' + ('' if pin else ' and no receipt pin names it'))
    size, sha, lines = _stream_lines(path)
    check = ('no_pin' if not (pin or {}).get('sha256') else
             'equal' if pin['sha256'] == sha and pin.get('count') in (None, lines) else 'differs')
    return dict(status='read', path=str(path), bytes=size, sha256=sha, lines=lines, check=check,
                pinned=dict(sha256=pin.get('sha256'), count=pin.get('count')) if pin else None, how='streamed whole')


def second_set_reading(rows_dir, reader):
    """The whole second set as read by one teacher (`reader` names it): READING_SCHEMA record. Never raises for a part:
    a part that cannot be read is listed with its reason. Deterministic for the same files (no clock, no timing)."""
    rows_dir = Path(rows_dir)
    out = dict(schema=READING_SCHEMA, reader=reader, rows_dir=str(rows_dir), parts={}, listed=[],
               rule='read whole beside the teacher\'s own work; plane values by reference to the ROOT\'s stream rows '
                    '(only copies avoided); never cut, capped or sampled; an absent part is listed, never fatal; the '
                    'pinned key is never rebuilt from it')
    receipt_path = rows_dir / TEACHER_RECEIPT_FILE
    receipt = {}
    try:
        raw = receipt_path.read_bytes()
        receipt = json.loads(raw)
        out['receipt'] = dict(path=str(receipt_path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    except (OSError, ValueError) as error:
        out['receipt'] = dict(status='absent', path=str(receipt_path), reason='%s: %s' % (type(error).__name__, error))
        out['listed'].append(dict(part='receipt', reason=out['receipt']['reason']))
    if not isinstance(receipt, dict):
        receipt = {}
    second = receipt.get('teacher_second_set') if isinstance(receipt.get('teacher_second_set'), dict) else {}
    parts = out['parts']

    def guarded(name, fn):
        try:
            parts[name] = fn()
        except Exception as error:  # noqa: BLE001 - one part's failure is listed; the others are read
            parts[name] = dict(status='unreadable', reason='%s: %s' % (type(error).__name__, error))
        if parts[name].get('status') != 'read':
            out['listed'].append(dict(part=name, status=parts[name].get('status'), reason=parts[name].get('reason')))

    def sidecar():
        side = sidecar_of(rows_dir)
        if not side.is_file():
            return dict(status='absent', path=str(side), reason='no rows sidecar beside the teacher rows (%s)' % (
                (receipt.get('rows_sidecar') or {}).get('reason') or 'a teacher before the second set'))
        stream = SidecarStream(side)
        roles = {role: stream.role(role) for role in READ_ROLES}
        carrying = {role: 0 for role in READ_ROLES}
        without = {role: [] for role in READ_ROLES}
        entries, references, element_rows, empty_rows, book_status = {}, 0, 0, 0, {}
        for ordinal, row in enumerate(stream):
            for role, key in roles.items():
                if key is not None and row.get(key) is not None:
                    carrying[role] += 1
                else:
                    without[role].append(ordinal)
            planes = row.get(roles['planes']) if roles['planes'] else None
            for entry, value in (planes or {}).items():
                slot = entries.setdefault(entry, dict(rows_with_references=0, references=0, rows_element=0,
                                                      rows_without=0))
                if isinstance(value, list):
                    if value:
                        slot['rows_with_references'] += 1
                        slot['references'] += len(value)
                        references += len(value)
                    else:
                        slot['rows_without'] += 1
                        empty_rows += 1
                else:
                    slot['rows_element'] += 1
                    element_rows += 1
            book = row.get(roles['book_columns']) if roles['book_columns'] else None
            status = book.get('status') if isinstance(book, dict) else None
            book_status[str(status)] = book_status.get(str(status), 0) + 1
        record = stream.record()
        streams = {}
        for name, pin in sorted((stream.header.get('streams') or {}).items()):
            named = pin.get('path') if isinstance(pin, dict) else None
            ident = _file_identity(named) if named else None
            streams[name] = dict(path=named, pinned_bytes=(pin or {}).get('bytes') if isinstance(pin, dict) else None,
                                 sha256=(pin or {}).get('sha256') if isinstance(pin, dict) else None,
                                 on_disk=ident is not None and pin.get('bytes') in (None, ident['bytes']),
                                 reason=None if ident is not None else 'the pinned stream file is not on disk')
        absent_streams = sorted(n for n, s in streams.items() if not s['on_disk'])
        return dict(status='read', how='streamed whole, row by row', path=record['path'], bytes=record['bytes'],
                    sha256=record['sha256'], rows=record['rows'], format=record['format'],
                    check=sidecar_check(stream, receipt), roles=roles, carrying=carrying,
                    without={r: dict(rows=len(o), ordinal_ranges=_ranges(o)) for r, o in without.items()},
                    planes=dict(entries=len(entries), references=references, element_rows=element_rows,
                                rows_without=empty_rows, per_entry=entries),
                    book_columns_status=book_status, streams=streams, streams_not_on_disk=absent_streams,
                    clock_lock_time=stream.header.get('clock_lock_time'),
                    entries_not_carried=stream.header.get('entries_not_carried'),
                    plane_values='by reference: each [source, source_ordinal, ...] names a row of a ROOT stream file '
                                 '(read at use by PlaneResolver); not copied')

    def second_file():
        path = rows_dir / (second.get('file') or SECOND_SET_PKL)
        ident = _file_identity(path)
        if ident is None:
            return dict(status='absent', path=str(path), reason=second.get('reason') or 'not on disk')
        return dict(status='read', path=str(path), bytes=ident['bytes'], sha256=second.get('sha256'),
                    how='pinned by the teacher receipt (teacher_second_set.sha256); the same '
                    'records are read row by row in the rows sidecar, so it is not read a second time')

    def state_split():
        split = second.get('state_split') if isinstance(second.get('state_split'), dict) else {}
        pinned = split.get('day_file_sha256')
        path = rows_dir / (split.get('day_file') or STATE_SPLIT_DAY_FILE)
        if not path.is_file():
            return dict(status='absent', path=str(path), reason='not on disk')
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        doc = json.loads(data)
        sides = doc.get('sides') or {}
        return dict(status='read', how='read whole', path=str(path), bytes=len(data), sha256=sha,
                    check='no_pin' if not pinned else 'equal' if pinned == sha else 'differs', pinned=pinned,
                    schema=doc.get('schema'), summary=doc.get('summary'),
                    sides={side: dict(fields=len((value or {}).get('fields') or {}),
                                      buckets=sum(len((f or {}).get('buckets') or {})
                                                  for f in ((value or {}).get('fields') or {}).values()),
                                      all_sum_back=(value or {}).get('all_sum_back')) for side, value in sides.items()})

    def account():
        value = receipt.get('account')
        if not isinstance(value, dict):
            return dict(status='absent', reason='the teacher receipt carries no account (a teacher before it)')
        canonical = json.dumps(value, sort_keys=True, default=str).encode()
        read_together = value.get('read_together') if isinstance(value.get('read_together'), dict) else {}
        return dict(status='read', how='read whole from the teacher receipt', path=str(receipt_path),
                    sha256=hashlib.sha256(canonical).hexdigest(), sections=sorted(value),
                    format=value.get('format'), planes=len(read_together.get('planes') or {}),
                    book_columns=read_together.get('book_columns'),
                    state_split=(read_together.get('state_split') or {}).get('status'))

    guarded('rows_sidecar', sidecar)
    guarded('second_set_file', second_file)
    guarded('state_split_day', state_split)
    guarded('account', account)
    guarded('mismatches_list', lambda: _pinned_list(rows_dir, second.get('mismatches') or second.get('mismatches_file'),
                                                    MISMATCHES_LIST))
    missing = ((receipt.get('account') or {}).get('missing_or_thin') or {}) if isinstance(receipt.get('account'), dict) else {}
    reconciliation = missing.get('reconciliation') if isinstance(missing.get('reconciliation'), dict) else {}
    guarded('book_event_differences_list', lambda: _pinned_list(rows_dir, reconciliation.get('all'), BOOK_DIFFERENCES_LIST))
    guarded('reconciliation_differences_list', lambda: _pinned_list(rows_dir, None, RECONCILIATION_LIST))
    out['read'] = sorted(name for name, part in parts.items() if part.get('status') == 'read')
    out['absent'] = sorted(name for name, part in parts.items() if part.get('status') != 'read')
    return out


def _identity_of(rows_dir, parts, receipt_sha256):
    """The files a reading read (stats) and the receipt's sha256: equal identity = the same reading (reuse)."""
    ident = {name: _file_identity(Path(part['path'])) for name, part in sorted(parts.items())
             if part.get('path') and name != 'account'}
    ident['receipt'] = receipt_sha256
    return ident


def second_set_reading_file(rows_dir, out_path, reader, *, reuse_on=None):
    """(record, pin {path, bytes, sha256}, how) of one teacher's reading written to out_path (JSON; its bytes depend
    only on what was read, never on file stats or clocks). A reading already written there by the same reader for the
    same files (the stats kept in <out_path>.identity.json and the receipt's sha256 unchanged) is reused, not read
    again; else the second set is read whole and the file written (the same content gives the same bytes). Never
    raises: a failure is (record with status failed, None, reason). reuse_on (names of identity keys, e.g. the rows
    sidecar and the receipt): only those decide a reuse (a reader whose document a restart must reproduce byte for byte
    keeps its first reading while the second set itself is unchanged; a list written later is not taken in then)."""
    import os
    out_path = Path(out_path)
    identity_path = out_path.with_name(out_path.name + '.identity.json')

    def receipt_sha():
        try:
            return hashlib.sha256((Path(rows_dir) / TEACHER_RECEIPT_FILE).read_bytes()).hexdigest()
        except OSError:
            return None

    def write(path, data):
        pending = path.with_name(path.name + '.pending')
        with pending.open('wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, path)
    try:
        if out_path.is_file() and identity_path.is_file():
            data = out_path.read_bytes()
            kept = json.loads(data)
            then = json.loads(identity_path.read_bytes())
            now = _identity_of(rows_dir, kept.get('parts') or {}, receipt_sha())
            if reuse_on is not None:
                then, now = ({k: v.get(k) for k in reuse_on} for v in (then, now))
            if kept.get('schema') == READING_SCHEMA and kept.get('reader') == reader and then == now:
                return kept, dict(path=str(out_path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()), \
                    'reused (the same files: stats and the receipt unchanged)'
        record = second_set_reading(rows_dir, reader)
        data = (json.dumps(record, sort_keys=True, indent=1, default=str) + '\n').encode()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not out_path.is_file() or out_path.read_bytes() != data:
            write(out_path, data)
        identity = _identity_of(rows_dir, record['parts'], (record.get('receipt') or {}).get('sha256'))
        write(identity_path, (json.dumps(identity, sort_keys=True) + '\n').encode())
        return record, dict(path=str(out_path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()), 'read whole'
    except Exception as error:  # noqa: BLE001 - the reading is added knowledge; its failure is listed, never the day's
        return (dict(schema=READING_SCHEMA, reader=reader, rows_dir=str(rows_dir), status='failed',
                     reason='%s: %s' % (type(error).__name__, error), parts={}, read=[], absent=[], listed=[]),
                None, 'failed (%s: %s)' % (type(error).__name__, error))


def reading_reference(record, pin, how):
    """The compact reference a teacher's turn or receipt carries: the reading file's pin and, per part, what was read
    (counts and pins; the whole reading is the file). how=None leaves out the read-or-reused note (a document whose
    bytes a restart must reproduce)."""
    parts = {}
    for name, part in sorted(((record or {}).get('parts') or {}).items()):
        parts[name] = {k: part.get(k) for k in ('status', 'how', 'path', 'bytes', 'sha256', 'rows', 'lines', 'check',
                                                 'carrying', 'sections', 'reason') if part.get(k) is not None}
        if name == 'rows_sidecar' and isinstance(part.get('planes'), dict):
            parts[name]['planes'] = {k: part['planes'].get(k) for k in ('entries', 'references', 'element_rows',
                                                                        'rows_without')}
            parts[name]['streams_not_on_disk'] = part.get('streams_not_on_disk')
    record = record or {}
    out = dict(schema=READING_SCHEMA, reader=record.get('reader'), reading=pin,
               status=record.get('status') or ('read' if record.get('read') else 'nothing read'),
               read=record.get('read'), absent=record.get('absent'), parts=parts, listed=record.get('listed'),
               reason=record.get('reason'))
    if how is not None:            # how differs between a first read and a reuse: kept off a document a restart rewrites
        out['how'] = how
    return out


def reading_sentence(record):
    """One plain sentence of what a teacher read of the second set (the day reports): a reading record or its
    reading_reference."""
    if not isinstance(record, dict):
        return 'no reading recorded'
    if record.get('status') == 'failed':
        return 'the reading failed (%s)' % record.get('reason')
    parts = record.get('parts') or {}
    said = []
    side = parts.get('rows_sidecar') or {}
    if side.get('status') == 'read':
        carrying = side.get('carrying') or {}
        planes = side.get('planes') or {}
        check = side.get('check')
        said.append('%s rows of the rows sidecar streamed whole (sha256 %s; against the teacher receipt: %s): key on %s '
                    'rows, clocks on %s, the planes on %s (%s references over %s plane entries; %s entry-rows '
                    'carried by the row itself; %s entry-rows with no plane row at that instant), book columns on %s, '
                    'the per-row state split on %s' % (
                        side.get('rows'), side.get('sha256'), check.get('status') if isinstance(check, dict) else check,
                        carrying.get('key'), carrying.get('clocks'), carrying.get('planes'), planes.get('references'),
                        planes.get('entries'), planes.get('element_rows'), planes.get('rows_without'),
                        carrying.get('book_columns'), carrying.get('state_split')))
        if side.get('streams_not_on_disk'):
            said.append('stream files named by plane references and not on disk: %s' % ', '.join(side['streams_not_on_disk']))
    for name, noun in (('state_split_day', 'the day\'s state split'), ('account', 'the account'),
                       ('mismatches_list', 'the full clock-mismatch list'),
                       ('book_event_differences_list', 'the full book-event difference list'),
                       ('reconciliation_differences_list', 'the full reconciliation-difference list'),
                       ('second_set_file', 'the second-set file')):
        part = parts.get(name) or {}
        if part.get('status') != 'read':
            continue
        if part.get('lines') is not None:
            said.append('%s streamed whole (%s lines; against its pin: %s)' % (noun, part['lines'], part.get('check')))
        elif name == 'account':
            said.append('%s read whole (sections: %s)' % (noun, ', '.join(part.get('sections') or []) or 'recorded'))
        elif name == 'second_set_file':
            said.append('%s pinned (sha256 %s)' % (noun, part.get('sha256')))
        else:
            said.append('%s read whole (against its pin: %s)' % (noun, part.get('check')))
    absent = ['%s (%s)' % (PART_WORDS.get(x.get('part'), x.get('part')), x.get('reason') or x.get('status'))
              for x in record.get('listed') or []]
    text = '; '.join(said) if said else 'nothing of the second set was read'
    return text + ('. Not read, listed: %s' % '; '.join(absent) if absent else '')


# ---- the sealed blocks (frankie_box_teacher_blocks, 2026-10-09): the sidecar published per block while the teacher walks.
# A block is readable the moment it is sealed, whether or not the day is complete: its bytes are a fixed range of the
# sidecar (append-only), pinned by sha256 in blocks/<n>.json and in teacher-blocks.json.
BLOCKS_MANIFEST = 'teacher-blocks.json'
BLOCKS_SCHEMA = 'FRANKIE_TEACHER_BLOCKS_V1'
BLOCK_SCHEMA = 'FRANKIE_TEACHER_BLOCK_V1'
BLOCK_READ_BYTES = 8 << 20


def blocks(rows_dir):
    """The teacher's blocks manifest beside the rows (schedule, the sealed blocks in order, complete, status), or None
    when the teacher published no blocks there."""
    path = Path(rows_dir) / BLOCKS_MANIFEST
    if not path.is_file():
        return None
    manifest = json.loads(path.read_bytes())
    if manifest.get('schema') != BLOCKS_SCHEMA:
        raise ValueError('%s is not a %s (schema %s)' % (path, BLOCKS_SCHEMA, manifest.get('schema')))
    return manifest


def block_record(rows_dir, n, manifest=None):
    """blocks/<n>.json, checked against the manifest's sha256 of it. Raises when block n is not sealed or differs."""
    manifest = manifest if manifest is not None else blocks(rows_dir)
    sealed = (manifest or {}).get('blocks') or []
    if not 1 <= n <= len(sealed):
        raise ValueError('block %d is not sealed (%d sealed)' % (n, len(sealed)))
    entry = sealed[n - 1]
    data = (Path(rows_dir) / entry['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('block %d record %s differs from its manifest sha256' % (n, entry['file']))
    record = json.loads(data)
    if record.get('schema') != BLOCK_SCHEMA or record.get('index') != n:
        raise ValueError('block %d record %s is not block %d' % (n, entry['file'], n))
    return record


def _block_range(rows_dir, record):
    """(path, start, end) of a block's bytes. The block's sha256 stays pinned on its record; it is NOT re-read and
    compared here (Greg, 2026-10-09: gates that re-check sealed data are off; the reader reads the sealed range once)."""
    side = record['sidecar']
    path = Path(rows_dir) / side['file']
    start, end = side['bytes']
    return path, start, end


def iter_block(rows_dir, n, select=None, manifest=None):
    """Block n's rows (dicts, one per sidecar line, in cursor order) from its sealed byte range, read once (the range's
    sha256 is pinned on the record, not re-checked). select: row keys to keep (None = all)."""
    record = block_record(rows_dir, n, manifest)
    path, start, end = _block_range(rows_dir, record)
    keep = None if select is None else frozenset(select)
    with path.open('rb') as handle:
        handle.seek(start)
        at = start
        while at < end:
            line = handle.readline()
            if not line:
                raise ValueError('the rows sidecar %s ends inside block %d' % (path, n))
            at += len(line)
            row = json.loads(line)
            yield row if keep is None else {k: v for k, v in row.items() if k in keep}
    if at != end:
        raise ValueError('block %d lines end at byte %d, not at its pinned end %d' % (n, at, end))


def sidecar_header_of_blocks(rows_dir, manifest=None):
    """Line 1 of a block-published sidecar, verified against the manifest's header pin."""
    manifest = manifest if manifest is not None else blocks(rows_dir)
    start, end = manifest['header']['bytes']
    with (Path(rows_dir) / manifest['sidecar']).open('rb') as handle:
        handle.seek(start)
        data = handle.read(end - start)
    if hashlib.sha256(data).hexdigest() != manifest['header']['sha256']:
        raise ValueError('the block sidecar header differs from its manifest pin')
    return json.loads(data)


class BlockSidecarStream(SidecarStream):
    """SidecarStream over the header and the given sealed blocks only (a partial sidecar while the teacher walks): the
    header checked against the manifest's pin, each block's bytes checked against its sha256 before any of its rows is
    read. .sha256/.bytes cover the header and those blocks' bytes; record() lists the blocks read."""

    def __init__(self, rows_dir, indices, select=None):
        self.rows_dir = Path(rows_dir)
        self.manifest = blocks(self.rows_dir)
        if self.manifest is None:
            raise ValueError('no %s beside %s' % (BLOCKS_MANIFEST, self.rows_dir))
        self.indices = sorted(set(int(n) for n in indices))
        self.read_blocks = []
        super().__init__(self.rows_dir / self.manifest['sidecar'], select=select)

    def _open(self):
        self.header = sidecar_header_of_blocks(self.rows_dir, self.manifest)
        start, end = self.manifest['header']['bytes']
        with self.path.open('rb') as handle:
            handle.seek(start)
            data = handle.read(end - start)
        self._digest.update(data)
        self._size += len(data)

    def __iter__(self):
        for n in self.indices:
            record = block_record(self.rows_dir, n, self.manifest)
            path, start, end = _block_range(self.rows_dir, record)
            with path.open('rb') as handle:
                handle.seek(start)
                at = start
                while at < end:
                    line = handle.readline()
                    at += len(line)
                    self._digest.update(line)
                    self._size += len(line)
                    row = json.loads(line)
                    self.rows += 1
                    yield row if self.select is None else {k: v for k, v in row.items() if k in self.select}
            self.read_blocks.append(dict(index=n, cursor_range=record['cursor_range'], clock_range=record['clock_range'],
                                         lines=record['sidecar']['lines'], sha256=record['sidecar']['sha256']))
        self.close()

    def close(self):
        self.sha256, self.bytes = self._digest.hexdigest(), self._size

    def record(self):
        out = super().record()
        out.update(blocks=list(self.read_blocks), manifest=BLOCKS_MANIFEST, complete=bool(self.manifest.get('complete')),
                   rule='the sidecar header and the sealed blocks listed, each verified against its sha256; sha256 '
                        'covers exactly those bytes')
        return out


def follow_blocks(rows_dir, on_block, waiter, *, check=None, start=1):
    """Block by block as they seal: on_block(n, manifest) for each sealed block in order from `start`; between blocks
    wait on `waiter` (a frankie_box_wake.Waiter on the rows directory and its blocks directory, built by the caller
    BEFORE this call), no interval and no timeout, until the manifest says complete (every block done) or stopped.
    check(): called before every look (a save request raises there). Returns {status, blocks, waits}."""
    n, waits, done = start, 0, []
    while True:
        if check is not None:
            check()
        manifest = blocks(rows_dir)
        if manifest is None:
            waiter.wait()
            waits += 1
            continue
        sealed = manifest.get('blocks') or []
        if n <= len(sealed):
            done.append(on_block(n, manifest))
            n += 1
            continue
        if manifest.get('complete'):
            return dict(status='complete', blocks=done, waits=waits, manifest_status=manifest.get('status'))
        if manifest.get('status') in ('failed', 'stopped'):
            return dict(status=manifest['status'], reason=manifest.get('reason'), blocks=done, waits=waits)
        waiter.wait()
        waits += 1
