"""Prepare ROOT's exact INPUT rows while the original journal is being written.

This is preparation, not a partial-day scientific source. Only a final descriptor
bound to the independently checked, sealed journal can be opened by ROOT. The
fresh sequential producer owns the observer; existing journals and resumed ingest
keep their established reader. No Session import, journal reread or changed codec.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid


SCHEMA = 'FRANKIE_PREPARED_INGEST_INPUTS_V1'
FIELDS_SCHEMA = 'FRANKIE_ROOT_ALL_INPUT_FIELDS_V1'
OFFSET_EVERY = 4096
TAIL_BYTES = 1 << 16


def find_observation(node, depth=0, max_depth=4):
    """Session's observation selection: dictionaries only, in insertion order."""
    if isinstance(node, dict):
        if 'ts_event' in node and 'action' in node and 'instrument_id' in node:
            return node
        if max_depth is None or depth < max_depth:
            for value in node.values():
                found = find_observation(value, depth + 1, max_depth)
                if found is not None:
                    return found
    return None


def _stat_claim(path):
    info = Path(path).stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('prepared INPUT evidence must be a regular file')
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def _tail_claim(path, size):
    with Path(path).open('rb') as stream:
        stream.seek(max(0, size - TAIL_BYTES))
        data = stream.read(TAIL_BYTES)
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _remember(path, value, expected_claim=None):
    # The box imports this under its flat module name. Production ingestion may
    # import through deploy.aws.box; either name must populate ROOT's same cache.
    try:
        import frankie_box_filehash as filehash
    except ImportError:
        from deploy.aws.box import frankie_box_filehash as filehash
    before = _stat_claim(path)
    if expected_claim is not None and before != expected_claim:
        raise ValueError('prepared INPUT file changed before its witness was recorded')
    if not filehash.remember(path, value) or _stat_claim(path) != before:
        raise ValueError('prepared INPUT file changed before its witness was recorded')


def _fsync_directory(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_descriptor(directory, value):
    from research.kalshi.frankie_boss.c15_journal import pack
    data = (json.dumps(pack(value), separators=(',', ':')) + '\n').encode('utf-8')
    # A partial/crashed descriptor is never replaced or selected by directory
    # scanning. Only its returned pin, published after fsync, identifies it.
    path = directory / ('inputs-' + uuid.uuid4().hex + '.c15.json')
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(directory)
    pin = dict(file=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    _remember(path, pin)
    return pin


def _container_identity(container):
    identity = {name: container[name] for name in ('path', 'count', 'head', 'bytes', 'sha256')}
    if type(identity['count']) is not int or identity['count'] < 0:
        raise ValueError('prepared INPUT journal count must be a nonnegative integer')
    if type(identity['bytes']) is not int or identity['bytes'] < 0:
        raise ValueError('prepared INPUT journal byte count must be a nonnegative integer')
    if not isinstance(identity['head'], str) or not isinstance(identity['sha256'], str):
        raise ValueError('prepared INPUT final journal hashes are required')
    identity['path'] = str(Path(identity['path']).resolve())
    for name in ('layout', 'format', 'conformance'):
        if name in container:
            identity[name] = container[name]
    return identity


class PreparedInputs:
    """One fresh journal's append observer and bounded, type-preserving row spool.

    Call observe only after the corresponding append has succeeded. INPUT must
    carry its original materialized payload; APPLIED is counted without walking
    its payload, so its observation-splice sentinel remains valid. The
    producer must drain/commit its journal before publishing a checkpoint pin.
    Existing-source/resume callers do not create this fresh-only preparer.
    """
    def __init__(self, directory, *, record_provenance=None):
        self.record_provenance = record_provenance
        self._member_source = None
        if record_provenance is not None:
            try:
                from frankie_box_native_source import MemberSource
            except ImportError:
                from deploy.aws.box.frankie_box_native_source import MemberSource
            self._member_source = MemberSource(record_provenance)
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / ('root-inputs-' + uuid.uuid4().hex + '.jsonl')
        self._writer = self.path.open('xb')
        self._digest = hashlib.sha256()
        self._bytes = self._count = self._consumed = 0
        self._kinds, self._bytes_fields = {}, {}
        self._missing = []
        self._first_line = self._last_line = None
        self._offsets = {0: 0}
        self._low = self._high = None
        self._span_valid = True
        self._native_clock_projection_unchanged = True
        self._checkpoint_head = None
        self._complete = None

    def observe(self, kind, payload, ordinal):
        if self._writer.closed or self._complete is not None:
            raise ValueError('prepared INPUT observer is already closed')
        if type(ordinal) is not int or ordinal != self._consumed:
            raise ValueError('prepared INPUT observer requires contiguous journal ordinals from zero')
        if type(kind) is not str or not kind:
            raise ValueError('prepared INPUT observer requires a journal kind')
        self._kinds[kind] = self._kinds.get(kind, 0) + 1
        if kind == 'INPUT':
            if self._member_source is not None:
                self._member_source.verify_input(payload, self._count)
            observation = find_observation(payload, max_depth=None)
            if observation is None:
                if self._member_source is not None:
                    raise ValueError('member-bound native INPUT lacks its original observation')
                from research.kalshi.frankie_boss.c15_journal import pack, unpack
                cursor = (payload or {}).get('cursor') if isinstance(payload, dict) else None
                self._missing.append(dict(input_entry=self._kinds[kind] - 1,
                                          cursor=unpack(pack(cursor))))
            else:
                from research.kalshi.frankie_boss.c15_journal import pack
                for name, value in observation.items():
                    if isinstance(value, (bytes, bytearray)):
                        self._bytes_fields[name] = self._bytes_fields.get(name, 0) + 1
                        if name in ('ts_recv', 'ts_recv_ns'):
                            self._native_clock_projection_unchanged = False
                # Exactly B.RowSpool.append's codec and insertion order, including
                # bytes fields; the full-picture ROOT path retains every field.
                line = (json.dumps(pack(dict(observation)), separators=(',', ':')) + '\n').encode('utf-8')
                if self._count % OFFSET_EVERY == 0:
                    self._offsets[self._count] = self._bytes
                self._writer.write(line)
                self._digest.update(line)
                self._bytes += len(line)
                self._count += 1
                if self._first_line is None:
                    self._first_line = line
                self._last_line = line
                value = observation.get('ts_recv')
                if value is None:
                    value = observation.get('ts_recv_ns')
                if value is not None and self._span_valid:
                    try:
                        value = int(value)
                    except (TypeError, ValueError, OverflowError):
                        # Extraction did not historically validate receive clocks.
                        # Leave any such error to the original span calculator.
                        self._span_valid = False
                    else:
                        self._low = value if self._low is None else min(self._low, value)
                        self._high = value if self._high is None else max(self._high, value)
        self._consumed += 1

    def _snapshot(self, journal_count, journal_head, *, complete, container=None):
        from research.kalshi.frankie_boss.c15_journal import unpack
        if type(journal_count) is not int or journal_count != self._consumed:
            raise ValueError('prepared INPUT extent differs from the committed journal count')
        if not isinstance(journal_head, str):
            raise ValueError('prepared INPUT journal head is required')
        if self._writer.closed:
            raise ValueError('prepared INPUT spool was closed before publication')
        self._writer.flush()
        os.fsync(self._writer.fileno())
        before = _stat_claim(self.path)
        if before['bytes'] != self._bytes:
            raise ValueError('prepared INPUT spool extent changed outside its writer')
        tail = _tail_claim(self.path, self._bytes)
        if _stat_claim(self.path) != before:
            raise ValueError('prepared INPUT spool changed while taking its durable claim')
        ends = [] if self._first_line is None else [unpack(json.loads(self._first_line)),
                                                   unpack(json.loads(self._last_line))]
        offsets = dict(self._offsets)
        offsets[self._count] = self._bytes
        spool = dict(path=str(self.path), count=self._count, bytes=self._bytes,
                     sha256=self._digest.hexdigest(), strong_stat_claim=before, tail_claim=tail,
                     ends=ends, row_offsets=list(offsets.items()), receive_clock_bounds=(self._low, self._high),
                     receive_clock_count=self._count, receive_clock_valid=self._span_valid,
                     native_clock_projection_unchanged=self._native_clock_projection_unchanged)
        value = dict(schema=SCHEMA, input_fields_schema=FIELDS_SCHEMA, complete=complete,
                     journal_count=journal_count, journal_head=journal_head, container=container,
                     kinds=dict(self._kinds), inputs_without_observation=list(self._missing),
                     bytes_fields_spooled=dict(self._bytes_fields), bytes_fields_not_spooled={}, spool=spool)
        if self.record_provenance is not None:
            value['record_provenance'] = self.record_provenance
        return value

    def checkpoint(self, journal_count, journal_head):
        """Pin an exact durable prefix; it is never eligible for full ROOT input."""
        if self._complete is not None:
            raise ValueError('prepared INPUT source is already complete')
        value = self._snapshot(journal_count, journal_head, complete=False)
        pin = _write_descriptor(self.directory, value)
        self._checkpoint_head = (journal_count, journal_head)
        return pin

    def complete(self, container):
        """Publish only after the caller verifies the sealed container/file pin."""
        identity = _container_identity(container)
        if self._member_source is not None and self._count != self._member_source.total:
            raise ValueError('prepared native INPUT count differs from the complete DBN source')
        if self._complete is not None:
            if identity != self._complete[0]:
                raise ValueError('prepared INPUT source was completed for a different journal')
            return dict(self._complete[1])
        if self._checkpoint_head is not None:
            count, head = self._checkpoint_head
            if count > identity['count'] or (count == identity['count'] and head != identity['head']):
                raise ValueError('prepared INPUT final head conflicts with its committed checkpoint')
        value = self._snapshot(identity['count'], identity['head'], complete=True, container=identity)
        # Close before the durable final stat claim, so a reopened RowSpool is
        # read-only and never adopts an uncommitted suffix after publication.
        self._writer.close()
        if _stat_claim(self.path) != value['spool']['strong_stat_claim']:
            raise ValueError('prepared INPUT spool changed at final close')
        _fsync_directory(self.directory)
        _remember(self.path, value['spool'], value['spool']['strong_stat_claim'])
        pin = _write_descriptor(self.directory, value)
        self._complete = (identity, pin)
        return dict(pin)

    def close(self):
        """Retain an incomplete spool after cancellation; never publish it."""
        if not self._writer.closed:
            self._writer.close()


def load_prepared(directory, descriptor, expected_container):
    """Return (read-only B.RowSpool, extraction metadata) for a pinned final source.

    expected_container is ROOT's independently checked final container identity.
    Changed stat/tail claims trigger a complete spool SHA/extent check. Extra or
    partial trailing bytes refuse reuse; nothing is truncated, rewritten or
    selected from incomplete checkpoint descriptors.
    """
    from research.kalshi.frankie_boss.c15_journal import unpack
    try:
        import frankie_box_bedrock as bedrock
    except ImportError:
        from deploy.aws.box import frankie_box_bedrock as bedrock
    path = Path(descriptor['file'])
    if not path.is_absolute():
        path = Path(directory) / path
    before = _stat_claim(path)
    raw = path.read_bytes()
    if (_stat_claim(path) != before or len(raw) != descriptor['bytes']
            or hashlib.sha256(raw).hexdigest() != descriptor['sha256']):
        raise ValueError('prepared INPUT descriptor differs from its published pin')
    value = unpack(json.loads(raw))
    if (value.get('schema') != SCHEMA or value.get('input_fields_schema') != FIELDS_SCHEMA
            or value.get('complete') is not True):
        raise ValueError('only a complete full-field prepared INPUT descriptor may feed ROOT')
    expected = _container_identity(expected_container)
    actual = value['container']
    for name in ('path', 'count', 'head', 'bytes', 'sha256'):
        if actual.get(name) != expected[name]:
            raise ValueError('prepared INPUT journal identity differs: ' + name)
    for name in ('layout', 'format'):
        if name in actual and name in expected and actual[name] != expected[name]:
            raise ValueError('prepared INPUT journal identity differs: ' + name)
    if (value['journal_count'], value['journal_head']) != (expected['count'], expected['head']):
        raise ValueError('prepared INPUT committed frontier differs from the final journal')
    spool = value['spool']
    spool_path = Path(spool['path'])
    observed = _stat_claim(spool_path)
    if observed['bytes'] != spool['bytes']:
        raise ValueError('prepared INPUT spool has a missing or uncommitted trailing extent')
    if (observed == spool['strong_stat_claim']
            and _tail_claim(spool_path, spool['bytes']) == spool['tail_claim']):
        basis = 'producer write-stream sha256; unchanged strong stat and tail claim'
    else:
        digest, size, count, last = hashlib.sha256(), 0, 0, b''
        with spool_path.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
                size += len(block)
                count += block.count(b'\n')
                last = block[-1:]
        if (size != spool['bytes'] or digest.hexdigest() != spool['sha256']
                or count != spool['count'] or (size and last != b'\n')):
            raise ValueError('prepared INPUT spool differs from its pinned complete records')
        basis = 'complete spool sha256 and row count; changed durable stat claim'
    if _stat_claim(spool_path) != observed:
        raise ValueError('prepared INPUT spool changed while verifying its claim')
    if sum(value['kinds'].values()) != expected['count']:
        raise ValueError('prepared INPUT kind accounting differs from the journal count')
    if value['kinds'].get('INPUT', 0) != spool['count'] + len(value['inputs_without_observation']):
        raise ValueError('prepared INPUT observation accounting differs from its spool count')
    if len(spool['ends']) != (2 if spool['count'] else 0):
        raise ValueError('prepared INPUT retained endpoints differ from its row count')
    offsets = {}
    last_row = last_offset = -1
    for row, offset in spool['row_offsets']:
        if (type(row) is not int or type(offset) is not int
                or not 0 <= row <= spool['count'] or not 0 <= offset <= spool['bytes']
                or row <= last_row or offset <= last_offset):
            raise ValueError('prepared INPUT seek offsets are not ordered exact row boundaries')
        offsets[row] = offset
        last_row, last_offset = row, offset
    if offsets.get(0) != 0 or offsets.get(spool['count']) != spool['bytes']:
        raise ValueError('prepared INPUT seek boundaries differ from the committed extent')
    records = bedrock.RowSpool.__new__(bedrock.RowSpool)
    records.path = spool_path
    records._count = spool['count']
    records._ends = spool['ends']
    records._row_offsets = offsets
    records._native_clock_projection_unchanged = spool.get('native_clock_projection_unchanged', False)
    with spool_path.open('rb') as stream:
        records._writer = stream
    if spool['receive_clock_valid']:
        records._receive_clock_bounds = spool['receive_clock_bounds']
        records._receive_clock_count = spool['receive_clock_count']
        records._receive_clock_file_identity = bedrock.ledger_file_identity(spool_path)
    records._row_offsets_file_identity = bedrock.ledger_file_identity(spool_path)
    _remember(spool_path, spool, observed)
    _remember(path, descriptor, before)
    metadata = {name: value[name] for name in ('kinds', 'inputs_without_observation',
                                              'bytes_fields_spooled', 'bytes_fields_not_spooled')}
    if 'record_provenance' in value:
        metadata['record_provenance'] = value['record_provenance']
    metadata['record_spool'] = dict(path=str(spool_path), bytes=spool['bytes'], sha256=spool['sha256'],
                                    hash_basis=basis)
    metadata['proof'] = dict(basis='prepared_source_original_append_payloads_final_container_pin',
                             descriptor=dict(descriptor), count=expected['count'], head=expected['head'],
                             container_bytes=expected['bytes'], container_sha256=expected['sha256'])
    if 'conformance' in actual:
        metadata['proof']['conformance'] = actual['conformance']
    return records, metadata
