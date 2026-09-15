"""Pinned local DBN bytes -> exact MBO mappings -> complete C15 evidence.

No provider connection, inferred QSV, source rewriting or operational authority.
The source scope and runtime pin must come from independently trusted callers.
"""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
from pathlib import Path
import tempfile

try:
    from .c15_journal import evidence_hash
    from .forecast_contract import sha256_digest
    from .source_conformance import SourceConformanceDriver, SourceCompletion
except ImportError:
    from c15_journal import evidence_hash
    from forecast_contract import sha256_digest
    from source_conformance import SourceConformanceDriver, SourceCompletion

SOURCE_EXTRA_FIELDS = ('dbn_length', 'ts_out', 'dbn_wire_bytes', 'dbn_extraction_hash')
_INTEGER_FIELDS = ('ts_event', 'ts_recv', 'rtype', 'publisher_id', 'instrument_id',
    'price', 'size', 'channel_id', 'order_id', 'flags', 'ts_in_delta', 'sequence')


def _runtime():
    import databento_dbn as dbn
    import zstandard
    import zstandard.backend_c as zstd_binary
    versions = {'databento-dbn': version('databento-dbn'), 'zstandard': version('zstandard')}
    if versions != {'databento-dbn': '0.62.0', 'zstandard': '0.25.0'}:
        raise ValueError('unsupported pinned DBN/Zstandard runtime versions')
    material = dict(versions=versions,
        extractor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), binaries={
        'databento_dbn': hashlib.sha256(Path(dbn._lib.__file__).read_bytes()).hexdigest(),
        'zstandard': hashlib.sha256(Path(zstd_binary.__file__).read_bytes()).hexdigest()})
    return dbn, zstandard, evidence_hash(material)


def runtime_hash():
    """Inspect installed runtime identity; caller decides whether it is trusted."""
    return _runtime()[2]


@dataclass(frozen=True)
class MboSourcePin:
    dbn_version: int
    runtime_hash: str

    def __post_init__(self):
        if type(self.dbn_version) is not int or self.dbn_version not in (1, 2, 3):
            raise ValueError('explicit supported DBN version required')
        sha256_digest(self.runtime_hash, 'runtime_hash')

    @property
    def digest(self):
        return evidence_hash(dict(schema='BOSS_MBO_EXTRACTION_V1', **asdict(self)))


@dataclass(frozen=True)
class MboIngestion:
    completion: SourceCompletion
    extraction_hash: str
    metadata: tuple[bytes, ...]
    checkpoint: dict


def _check_pin(pin):
    if type(pin) is not MboSourcePin:
        raise ValueError('typed MBO extraction pin required')
    dbn, zstd, current = _runtime()
    if current != pin.runtime_hash:
        raise ValueError('installed runtime differs from trusted pin')
    return dbn, zstd


def _extract(record, pin, dbn):
    if type(record) is not dbn.MBOMsg:
        raise ValueError('every source record must be an exact SDK MBO record')
    wire = bytes(record)
    if len(wire) not in (56, 64) or wire[0] * 4 != len(wire) or wire[1] != 160:
        raise ValueError('unsupported MBO wire layout')
    return {**{field: int(getattr(record, field)) for field in _INTEGER_FIELDS},
            'action': str(record.action), 'side': str(record.side),
            'dbn_length': wire[0], 'ts_out': int(record.ts_out) if len(wire) == 64 else None,
            'dbn_wire_bytes': wire, 'dbn_extraction_hash': pin.digest}


def extract_mbo(record, pin):
    """Extract all exact fields plus original wire bytes from an actual SDK record."""
    dbn, _ = _check_pin(pin)
    return _extract(record, pin, dbn)


def _verified_copy(path, member, stack):
    snapshot = stack.enter_context(tempfile.TemporaryFile())
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(64 * 1024), b''):
            snapshot.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    if size != member.size_bytes or digest.hexdigest() != member.sha256:
        raise ValueError('source bytes or size differ from trusted member')
    snapshot.seek(0)
    return snapshot


def _decompressed(snapshot, zstd, stack):
    magic = snapshot.read(4)
    snapshot.seek(0)
    if magic[:3] == b'DBN':
        return snapshot
    if magic != b'\x28\xb5\x2f\xfd':
        raise ValueError('unsupported source encoding; require DBN or Zstandard')
    output = stack.enter_context(tempfile.TemporaryFile())
    decoder = None
    try:
        for chunk in iter(lambda: snapshot.read(64 * 1024), b''):
            remaining = chunk
            while remaining:
                if decoder is None:
                    decoder = zstd.ZstdDecompressor().decompressobj()
                output.write(decoder.decompress(remaining))
                remaining = decoder.unused_data
                if decoder.eof:
                    decoder = None
                else:
                    break
    except zstd.ZstdError as exc:
        raise ValueError('invalid compressed source') from exc
    if decoder is not None:
        raise ValueError('truncated compressed source frame')
    output.seek(0)
    return output


def _read_exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise ValueError('truncated DBN source')
    return data


def _metadata(stream, pin, dbn):
    header = _read_exact(stream, 8)
    if header[:3] != b'DBN' or header[3] != pin.dbn_version:
        raise ValueError('source DBN metadata version differs from pin')
    length = int.from_bytes(header[4:], 'little')
    # Validate declared metadata size against remaining bytes before allocating.
    position = stream.tell()
    stream.seek(0, 2)
    available = stream.tell() - position
    stream.seek(position)
    if length > available:
        raise ValueError('truncated DBN metadata')
    raw = header + _read_exact(stream, length)
    try:
        metadata = dbn.Metadata.decode(raw, upgrade_policy=dbn.VersionUpgradePolicy.AS_IS)
    except dbn.DBNError as exc:
        raise ValueError('invalid DBN metadata') from exc
    if metadata.version != pin.dbn_version or metadata.schema != 'mbo':
        raise ValueError('source metadata is not the pinned MBO schema')
    return raw, metadata.ts_out


def _records(stream, pin, ts_out, dbn):
    while first := stream.read(1):
        size = first[0] * 4
        if size < 2:
            raise ValueError('invalid DBN record length')
        wire = first + _read_exact(stream, size - 1)
        if wire[1] != 160:
            raise ValueError('non-MBO record in declared MBO source; no record is skipped')
        if size != (64 if ts_out else 56):
            raise ValueError('MBO record length disagrees with metadata ts_out')
        decoder = dbn.DBNDecoder(has_metadata=False, ts_out=ts_out,
            input_version=pin.dbn_version, upgrade_policy=dbn.VersionUpgradePolicy.AS_IS)
        try:
            records = decoder.write_and_decode(wire)
            remainder = decoder.decode()
        except dbn.DBNError as exc:
            raise ValueError('invalid MBO wire record') from exc
        if (len(records) != 1 or remainder or decoder.buffer()
                or type(records[0]) is not dbn.MBOMsg or bytes(records[0]) != wire):
            raise ValueError('SDK did not reproduce exact source record bytes')
        yield _extract(records[0], pin, dbn)


def ingest_sources(scope, paths, journal_path, pin, *, expected_scope_hash,
                   session_ids, raw_symbol=None, event=None):
    """Ingest verified complete local sources and return a restorable C15 result.

    This creates a new journal. Errors retain that journal; never truncate or
    retry an uncertain prefix. No DBNStore auto-upgrade or non-MBO filter is used.
    """
    SourceConformanceDriver._check_scope(scope, expected_scope_hash)
    dbn, zstd = _check_pin(pin)
    if (type(paths) is not tuple or len(paths) != len(scope.members)
            or type(session_ids) is not tuple or len(session_ids) != len(paths)
            or any(type(s) is not str or not s for s in session_ids)):
        raise ValueError('complete ordered source paths and explicit sessions required')
    with ExitStack() as stack:
        snapshots = [_verified_copy(path, member, stack)
                     for path, member in zip(paths, scope.members)]
        streams = [_decompressed(snapshot, zstd, stack) for snapshot in snapshots]
        metadata = [_metadata(stream, pin, dbn) for stream in streams]
        driver = SourceConformanceDriver(scope, journal_path, expected_scope_hash=expected_scope_hash)
        stack.callback(driver.close)
        cursor = 0
        total = sum(member.mbo_records for member in scope.members)
        if event is not None:
            event(dict(phase='ingestion', records=0, total_records=total))
        for index, (stream, (_, ts_out), session) in enumerate(zip(streams, metadata, session_ids)):
            for raw in _records(stream, pin, ts_out, dbn):
                driver.append(raw, cursor=cursor, source_member_index=index,
                    source_sha256=scope.members[index].sha256, session_id=session,
                    raw_symbol=raw_symbol, source_dbn_object=str(paths[index]))
                cursor += 1
                if event is not None and (cursor % 1000 == 0 or cursor == total):
                    event(dict(phase='ingestion', records=cursor, total_records=total))
        if event is not None:
            event(dict(phase='source_verification', records=cursor, total_records=total))
        completion = driver.complete()
        result = MboIngestion(completion, pin.digest, tuple(raw for raw, _ in metadata),
                              driver.checkpoint())
        if event is not None:
            event(dict(phase='source_saved', records=cursor, total_records=total,
                journal_hash=completion.journal_hash))
        return result
