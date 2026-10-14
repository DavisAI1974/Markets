"""Owner-local teacher products shared by the hub's consumers.

Records use independent hash-bound pickles: each memo dies after one record, and
the index makes a cursor read independent of the size of preceding records. A
manifest is published last. Existing teacher pickles and classroom saves remain
readable and are never rewritten by this module.
"""
from __future__ import annotations

import bisect
import fcntl
import hashlib
import json
import os
import pickle
import struct
import tempfile
import uuid
from pathlib import Path

RECORD_SCHEMA = 'FRANKIE_TEACHER_RECORD_STORE_V1'
JOINED_SCHEMA = 'FRANKIE_TEACHER_JOINED_RECORDS_V1'
KEY_SCHEMA = 'FRANKIE_SHARED_TEACHER_KEY_V1'
JOINED_FILE = 'teacher-second-set.json'
KEY_FILE = 'teacher-key.json'
_OFFSET = struct.Struct('>Q')


def _write_json(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(body, sort_keys=True, separators=(',', ':')) + '\n').encode()
    # A committed manifest never changes underneath a reader, including when a
    # stopped producer returns after installing its payloads. Unique temporary
    # names also keep a concurrent attempt from truncating another write.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.pending', delete=False) as handle:
        pending = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(pending, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError('published teacher manifest is immutable: ' + str(path))
    finally:
        pending.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _read_json(path, pin=None):
    data = Path(path).read_bytes()
    if pin is not None and (len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']):
        raise ValueError('teacher product manifest differs from its pin: ' + str(path))
    return json.loads(data)


def _identity_matches(retained, requested):
    import frankie_box_market_timeline as MT
    return MT.without_recorded_code(retained) == MT.without_recorded_code(requested)


class RecordWriter:
    """One bounded pickle and offset per record, with optional partial continuation.

    A progress save uses the teacher's existing hash-bound atomic state writer.
    It binds output positions and the caller's running calculation state in one
    publication. Unpublished bytes are retained after interruption, never erased
    by close() or by opening a replacement writer.
    """
    def __init__(self, path, identity, *, resume=False):
        self.path, self.identity = Path(path), identity
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError('published teacher record store is immutable: ' + str(self.path))
        self.progress_path = self.path.with_suffix('.progress.pkl')
        self.data_hash, self.index_hash = hashlib.sha256(), hashlib.sha256()
        self.count, self.size, self.closed = 0, 0, False
        self.continuation = None
        self._saved_position = None
        self.data = self.index = None
        if resume and self.progress_path.exists():
            self._resume()
        else:
            if self.progress_path.exists():
                raise ValueError('partial teacher output requires its saved continuation')
            self.data_pending, self.index_pending = self._new_paths()
            self.data, self.index = self.data_pending.open('xb'), self.index_pending.open('xb')

    def _new_paths(self):
        name = self.path.stem + '.' + uuid.uuid4().hex
        return (self.path.with_name(name + '.records.pending'), self.path.with_name(name + '.index.pending'))

    def _resume(self):
        from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
        saved = _load_raw_state(self.progress_path)
        if (saved.get('schema') != RECORD_SCHEMA or saved.get('format') != 1
                or not _identity_matches(saved['identity'], self.identity)):
            raise ValueError('partial teacher output belongs to another source, range or save format')
        self.count, self.size = saved['rows'], saved['data']['bytes']
        if (type(self.count) is not int or self.count < 0 or type(self.size) is not int or self.size < 0
                or saved['index']['bytes'] != self.count * _OFFSET.size):
            raise ValueError('partial teacher output positions differ')
        paths = [Path(saved[name]['path']) for name in ('data', 'index')]
        sizes = [self.size, self.count * _OFFSET.size]
        for path, size in zip(paths, sizes):
            if path.parent.resolve() != self.path.parent.resolve() or path.stat().st_size < size:
                raise ValueError('partial teacher output is missing its saved extent')
        # A process can die between an output write and its state publication.
        # Preserve that entire attempt. Copy only the acknowledged prefix to a
        # new write generation; never truncate the retained file or replay its
        # calculations. A clean cooperative save appends to its original files.
        fork = any(path.stat().st_size != size for path, size in zip(paths, sizes))
        targets = self._new_paths() if fork else paths
        handles = []
        try:
            for name, path, target, size, digest in zip(
                    ('data', 'index'), paths, targets, sizes, (self.data_hash, self.index_hash)):
                output = target.open('xb') if fork else None
                if output is not None:
                    handles.append(output)
                with path.open('rb') as source:
                    remaining = size
                    while remaining:
                        chunk = source.read(min(1 << 20, remaining))
                        if not chunk:
                            raise ValueError('partial teacher output ended before its saved position')
                        digest.update(chunk)
                        if output is not None:
                            output.write(chunk)
                        remaining -= len(chunk)
                if digest.hexdigest() != saved[name]['sha256']:
                    raise ValueError('partial teacher output differs from its saved bytes')
            if not fork:
                handles = [path.open('ab') for path in targets]
            self.data, self.index = handles
            self.data_pending, self.index_pending = targets
            self.continuation = saved['continuation']
            self._saved_position = (self.count, self.size, self.data_hash.hexdigest(), self.index_hash.hexdigest())
            # Publish a copied generation before it accepts another record.
            if fork:
                self.save(self.continuation)
        except BaseException:
            for handle in handles:
                handle.close()
            raise

    def save(self, continuation):
        """Retain a partial output and the exact calculation state that made it."""
        from research.kalshi.frankie_boss.parallel_teacher import _save_raw_state
        if self.closed:
            raise ValueError('teacher output writer is closed')
        for handle in (self.data, self.index):
            handle.flush()
            os.fsync(handle.fileno())
        _save_raw_state(self.progress_path, dict(schema=RECORD_SCHEMA, format=1, identity=self.identity,
            rows=self.count,
            data=dict(path=str(self.data_pending), bytes=self.size, sha256=self.data_hash.hexdigest()),
            index=dict(path=str(self.index_pending), bytes=self.count * _OFFSET.size,
                       sha256=self.index_hash.hexdigest()), continuation=continuation))
        self.continuation = continuation
        self._saved_position = (self.count, self.size, self.data_hash.hexdigest(), self.index_hash.hexdigest())

    def append(self, record):
        raw = pickle.dumps(record, protocol=pickle.HIGHEST_PROTOCOL)
        prefix = _OFFSET.pack(len(raw)) + hashlib.sha256(raw).digest()
        offset = _OFFSET.pack(self.size)
        self.index.write(offset)
        self.index_hash.update(offset)
        self.data.write(prefix)
        self.data.write(raw)
        self.data_hash.update(prefix)
        self.data_hash.update(raw)
        self.size += len(prefix) + len(raw)
        self.count += 1

    def finish(self):
        if self._saved_position is not None and self._saved_position != (
                self.count, self.size, self.data_hash.hexdigest(), self.index_hash.hexdigest()):
            raise ValueError('teacher final output requires its matching calculation continuation')
        for handle in (self.data, self.index):
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
        self.closed = True
        # Immutable data names mean a crash can never replace the payload named
        # by an already published manifest. Only the small manifest is current.
        self.data_path = self.path.with_name(self.path.stem + '.' + self.data_hash.hexdigest() + '.records')
        self.index_path = self.path.with_name(self.path.stem + '.' + self.index_hash.hexdigest() + '.index')
        for pending, target, expected in ((self.data_pending, self.data_path, self.data_hash.hexdigest()),
                                          (self.index_pending, self.index_path, self.index_hash.hexdigest())):
            try:
                os.link(pending, target)
            except FileExistsError:
                # A stopped writer may already have installed these exact bytes.
                digest = hashlib.sha256()
                with target.open('rb') as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b''):
                        digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise ValueError('immutable teacher record file differs from its name')
            # The progress save still refers to this name until the manifest is
            # durable. Retain its hard link, including after final publication.
        from research.kalshi.frankie_boss.operations.ingest_block_sources import file_claim
        data_claim = file_claim(self.data_path, self.size, self.data_hash.hexdigest(), 'teacher product write stream')
        body = dict(schema=RECORD_SCHEMA, identity=self.identity, rows=self.count,
            data=dict(path=str(self.data_path), bytes=self.size, sha256=self.data_hash.hexdigest()),
            index=dict(path=str(self.index_path), bytes=self.count * _OFFSET.size,
                       sha256=self.index_hash.hexdigest()),
            data_claim=data_claim,
            encoding='uint64 big-endian length, sha256 digest, independent pickle; index uint64 byte offsets')
        if self.progress_path.is_file():
            raw = self.progress_path.read_bytes()
            body['continuation'] = dict(path=str(self.progress_path), bytes=len(raw),
                                        sha256=hashlib.sha256(raw).hexdigest())
        return _write_json(self.path, body)

    def close(self):
        if not self.closed:
            self.data.close()
            self.index.close()
            self.closed = True
        # A stopped writer's partial output and its progress state are evidence.
        # The next process continues them; close is not a cleanup instruction.


class RecordStore:
    def __init__(self, path, *, pin=None, identity=None):
        self.path = Path(path)
        self.manifest = _read_json(path, pin)
        if self.manifest.get('schema') != RECORD_SCHEMA:
            raise ValueError('teacher record store schema differs')
        if identity is not None and not _identity_matches(self.manifest['identity'], identity):
            raise ValueError('teacher record store belongs to another source or range')
        self.data_path = Path(self.manifest['data']['path'])
        self.index_path = Path(self.manifest['index']['path'])
        for name, target in (('data', self.data_path), ('index', self.index_path)):
            if target.stat().st_size != self.manifest[name]['bytes']:
                raise ValueError('teacher record store %s size differs' % name)
        from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds
        claim = self.manifest.get('data_claim')
        held = (claim_still_holds(claim, self.data_path) if claim is not None
                and claim.get('sha256') == self.manifest['data']['sha256'] else None)
        if held is None:
            digest = hashlib.sha256()
            with self.data_path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b''):
                    digest.update(chunk)
            if digest.hexdigest() != self.manifest['data']['sha256']:
                raise ValueError('teacher record data differs from its manifest pin')
        # The index is small (eight bytes per adapter row). Check it before seeking;
        # each payload is independently checked before any pickle opcode is read.
        index = self.index_path.read_bytes()
        if hashlib.sha256(index).hexdigest() != self.manifest['index']['sha256']:
            raise ValueError('teacher record index differs')
        self.offsets = index

    def __len__(self):
        return self.manifest['rows']

    def continuation(self):
        """The calculation carry pinned with this completed part, if retained."""
        pin = self.manifest.get('continuation')
        if pin is None:
            return None
        from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
        path = Path(pin['path'])
        raw = path.read_bytes()
        if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('teacher part continuation differs from its manifest pin')
        saved = _load_raw_state(path)
        if (saved.get('schema') != RECORD_SCHEMA or saved.get('format') != 1
                or not _identity_matches(saved['identity'], self.manifest['identity'])
                or saved['rows'] != len(self)
                or any(saved[k][v] != self.manifest[k][v] for k in ('data', 'index')
                       for v in ('bytes', 'sha256'))):
            raise ValueError('teacher part continuation differs from its completed output')
        return saved['continuation']

    @staticmethod
    def _record(handle, total_bytes):
        prefix = handle.read(40)
        if len(prefix) != 40:
            raise ValueError('teacher record prefix is truncated')
        length = _OFFSET.unpack(prefix[:8])[0]
        if length > total_bytes - handle.tell():
            raise ValueError('teacher record length exceeds its pinned file')
        raw = handle.read(length)
        if len(raw) != length or hashlib.sha256(raw).digest() != prefix[8:]:
            raise ValueError('teacher record differs from its hash')
        return pickle.loads(raw)

    def __iter__(self):
        with self.data_path.open('rb') as handle:
            for _ in range(len(self)):
                yield self._record(handle, self.manifest['data']['bytes'])
            if handle.read(1):
                raise ValueError('teacher record store has unindexed trailing bytes')

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        offset = _OFFSET.unpack_from(self.offsets, index * _OFFSET.size)[0]
        with self.data_path.open('rb') as handle:
            handle.seek(offset)
            return self._record(handle, self.manifest['data']['bytes'])


class JoinedRecords:
    def __init__(self, manifest):
        self.manifest = manifest
        self.parts = manifest['parts']
        self.ends = [part['stop'] for part in self.parts]
        self._stores = {}
        expected = 0
        for part in self.parts:
            if part['start'] != expected or part['stop'] <= expected:
                raise ValueError('joined teacher records have a gap or overlap')
            expected = part['stop']
        if expected != manifest['rows']:
            raise ValueError('joined teacher record count differs')

    def _store(self, index):
        if index not in self._stores:
            part = self.parts[index]
            store = RecordStore(part['pin']['path'], pin=part['pin'])
            if len(store) != part['stop'] - part['start']:
                raise ValueError('joined teacher part count differs')
            self._stores[index] = store
        return self._stores[index]

    def __len__(self):
        return self.manifest['rows']

    def __iter__(self):
        for index in range(len(self.parts)):
            yield from self._store(index)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        part = bisect.bisect_right(self.ends, index)
        return self._store(part)[index - self.parts[part]['start']]


def publish_joined(path, header, parts, *, identity):
    path = Path(path)
    if path.is_file():
        raw = path.read_bytes()
        pin = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        body = json.loads(raw)
        if (body.get('schema') != JOINED_SCHEMA or not _identity_matches(body['identity'], identity)
                or body['parts'] != parts or body['rows'] != header['rows_total']):
            raise ValueError('published joined teacher records belong to another source or range')
        kept_header, records = load_joined(path, pin=pin)
        # These counts describe how the first successful producer assembled the
        # source. A resumed producer has a different walk/save split; it keeps
        # the committed provenance instead of replacing it after a crash.
        def meaning(value):
            value = {k: v for k, v in value.items()
                     if k not in ('joined_in_walk', 'restored_from_save', 'merged_at_publication')}
            value['book_read'] = {k: v for k, v in value['book_read'].items()
                                  if k not in ('groups_read_in_walk', 'groups_read_at_publication',
                                               'rows_read_at_publication')}
            return value
        if meaning(kept_header) != meaning(header):
            raise ValueError('published joined teacher header differs from its exact source reading')
        return pin, records, kept_header
    header_hash = hashlib.sha256(pickle.dumps(header, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()
    header_path = path.parent / 'teacher-second-set-blocks' / ('header-' + header_hash + '.json')
    if header_path.is_file():
        raw = header_path.read_bytes()
        header_pin = dict(path=str(header_path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        RecordStore(header_path, pin=header_pin, identity=identity)
    else:
        writer = RecordWriter(header_path, identity)
        try:
            writer.append(header)
            header_pin = writer.finish()
        finally:
            writer.close()
    body = dict(schema=JOINED_SCHEMA, header_record=header_pin, identity=identity,
                rows=header['rows_total'], parts=parts)
    records = JoinedRecords(body)
    return _write_json(path, body), records, header


def load_joined(path, *, pin=None):
    """(original header, complete adapter-row sequence), including old publications."""
    path = Path(path)
    if path.suffix == '.pkl':
        from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
        body = _load_raw_state(path)
        return {k: v for k, v in body.items() if k != 'records'}, body['records']
    body = _read_json(path, pin)
    if body.get('schema') != JOINED_SCHEMA:
        raise ValueError('joined teacher publication schema differs')
    header = RecordStore(body['header_record']['path'], pin=body['header_record'])[0]
    return header, JoinedRecords(body)


def _source_state(path):
    st = Path(path).stat()
    with Path(path).open('rb') as handle:
        handle.seek(max(0, st.st_size - 65536))
        tail = hashlib.sha256(handle.read()).hexdigest()
    return dict(device=st.st_dev, inode=st.st_ino, bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                ctime_ns=st.st_ctime_ns, tail_sha256=tail)


def _key_identity(snapshot, previous):
    return dict(source_snapshot_hash=snapshot['source_snapshot_hash'],
                teacher_attachment_hash=snapshot['teacher_attachment_hash'],
                request_id=snapshot['request_id'], cycle_index=snapshot['cycle_index'],
                previous_snapshot_hash=None if previous is None else previous['source_snapshot_hash'])


def _load_key(body):
    metadata = RecordStore(body['metadata']['path'], pin=body['metadata'])[0]
    if len(metadata['dimensions']) != len(body['ledgers']):
        raise ValueError('shared teacher key dimension count differs')
    dimensions = []
    for dimension, pin in zip(metadata['dimensions'], body['ledgers']):
        ledger = tuple(point for chunk in RecordStore(pin['path'], pin=pin) for point in chunk)
        nonpresent = tuple(dict(cursor=p['cursor'], state=p['state'], reason=p['raw_reason'])
                           for p in ledger if p['state'] != 'PRESENT')
        dimension = dict(dimension)
        dimension['observations'] = ledger
        dimension['nonpresent_explanations'] = nonpresent
        dimensions.append(dimension)
    return dict(metadata, dimensions=tuple(dimensions))


def _record_product(path, identity, values, count):
    """Resume a completed part; the final key manifest remains the commit point."""
    path = Path(path)
    if path.is_file():
        store = RecordStore(path, identity=identity)
        if len(store) != count:
            raise ValueError('retained teacher key part count differs')
        raw = path.read_bytes()
        return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    writer = RecordWriter(path, identity)
    try:
        for value in values:
            writer.append(value)
        return writer.finish()
    finally:
        writer.close()


def ensure_teacher_key(rows_path, *, snapshot=None, snapshot_hash_verified=None, previous_snapshot=None):
    """Return (exact full key, manifest pin); all consumers share one source-bound key.

    The record store preserves tuples and floats. Only observations are factored
    out; nonpresent_explanations is the existing exact projection of those same
    observations. Mode, teacher prompts and reveal policy are never cached here.
    """
    from research.kalshi.frankie_boss import dipole_classroom as DC, dipole_classroom_integration as I
    import frankie_box_hub_runtime as HR
    rows_path = HR.bound_path(rows_path)
    rows_path = Path(rows_path)
    if snapshot is not None:
        if (snapshot.get('schema') != DC.SOURCE_SCHEMA
                or tuple(snapshot.get('coverage_columns') or ()) != tuple(DC.COLUMNS)):
            raise ValueError('complete teacher snapshot required for a shared key')
        verified = (snapshot_hash_verified if snapshot_hash_verified is not None else
                    DC.evidence_hash({k: v for k, v in snapshot.items() if k != 'source_snapshot_hash'}))
        if verified != snapshot.get('source_snapshot_hash'):
            raise ValueError('shared teacher snapshot differs from its evidence hash')
    default_path = rows_path.parent / KEY_FILE
    with default_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = _source_state(rows_path)
        if default_path.is_file():
            raw = default_path.read_bytes()
            kept = json.loads(raw)
            identity = None if snapshot is None else _key_identity(snapshot, previous_snapshot)
            if (kept.get('schema') == KEY_SCHEMA and kept.get('source_state') == state
                    and (identity is None or kept.get('identity') == identity)
                    and kept['identity']['previous_snapshot_hash'] == (
                        None if previous_snapshot is None else previous_snapshot['source_snapshot_hash'])):
                return _load_key(kept), dict(path=str(default_path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if snapshot is None:
            import frankie_box_teacher_rows as TR
            snapshot, stream = TR.load(rows_path, select=('cursor', 'ts_recv_ns', 'target_hash', 'components'))
            snapshot_hash_verified = stream.snapshot_hash
            if not stream.snapshot_ok:
                raise ValueError('shared teacher snapshot differs from its evidence hash')
        identity = _key_identity(snapshot, previous_snapshot)
        identity_hash = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        directory = rows_path.parent / 'teacher-key' / identity_hash
        path = directory / 'manifest.json'
        if path.is_file():
            raw = path.read_bytes()
            kept = json.loads(raw)
            if kept.get('schema') != KEY_SCHEMA or kept.get('identity') != identity:
                raise ValueError('addressed teacher key differs from its source identity')
            return _load_key(kept), dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        key = I._repin_teacher_key_correlations(DC.build_teacher_key(
            snapshot, previous_snapshot, snapshot_hash_verified=snapshot_hash_verified))
        payload_directory = directory / key['teacher_key_hash']
        payload_identity = dict(identity, teacher_key_hash=key['teacher_key_hash'])
        ledgers, dimensions = [], []
        for index, dimension in enumerate(key['dimensions']):
            ledger = dimension['observations']
            chunks = (ledger[start:start + 512] for start in range(0, len(ledger), 512))
            ledgers.append(_record_product(payload_directory / ('%02d.json' % index), payload_identity,
                                           chunks, (len(ledger) + 511) // 512))
            # Keep insertion positions: c15's mapping codec records key order.
            dimensions.append({k: None if k in ('observations', 'nonpresent_explanations') else v
                               for k, v in dimension.items()})
        metadata = dict(key, dimensions=tuple(dimensions))
        metadata_pin = _record_product(payload_directory / 'metadata.json', payload_identity, (metadata,), 1)
        if _source_state(rows_path) != state:
            raise ValueError('teacher source changed while publishing the shared key')
        body = dict(schema=KEY_SCHEMA, identity=identity, source_state=state,
                    source_path=str(rows_path), metadata=metadata_pin, ledgers=ledgers,
                    teacher_key_hash=key['teacher_key_hash'])
        pin = _write_json(path, body)
        if not default_path.exists():
            pin = _write_json(default_path, body)
        return key, pin
