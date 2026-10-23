"""Export one bounded episode from existing indexed ledgers, byte-preserving.

Run only on the existing saved-source host. Config on stdin contains a temporary
transport URL; it is never saved. No fits, source mutation, full-source hash,
new services or source restoration. All original nested records remain intact.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import tarfile
import time
import urllib.request
import uuid

BASE = Path('/opt/frankie-box/work/family-research-20261022')
START = time.monotonic()
CAP = 3 * 1024**3
CHUNK = 64 * 1024**2
config = json.loads(sys.stdin.readline())
assert config['first_group'] == 3046 and config['last_group'] == 4712
out = BASE / ('trade-gap-transport-' + uuid.uuid4().hex)
out.mkdir()
db = sqlite3.connect('file:' + str(BASE / 'alignment.sqlite') + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row
pins = {r['name']: dict(r) for r in db.execute('SELECT * FROM source_registry')}
groups = [dict(r) for r in db.execute(
    'SELECT * FROM group_event WHERE source_ordinal BETWEEN ? AND ? ORDER BY source_ordinal',
    (config['first_group'], config['last_group']))]
assert len(groups) == 1667
assert {r['instrument_id'] for r in groups} == {150611}
assert [r['source_ordinal'] for r in groups] == list(range(3046, 4713))
bytes_read = 0
readers = {}
writers = {}
counts = {}
files = []
references = {}
receipt_path = out / 'source-read-receipt.json'
registry = gzip.open(out / 'original-record-index.jsonl.gz', 'wt', encoding='utf-8')

def guard(size=0):
    global bytes_read
    bytes_read += size
    assert bytes_read <= CAP, 'bounded source byte cap exceeded'
    assert time.monotonic() - START < 600, 'ten-minute source read cap exceeded'

class Reader:
    def __init__(self, name):
        self.pin = pins[name]
        self.source = open(self.pin['path'], 'rb')
        self.index = open(self.pin['offset_index'], 'rb')
        self.header = json.loads(self.index.readline())
        self.head = self.index.tell()
        assert self.header['byteorder'] == 'little'
        assert os.fstat(self.source.fileno()).st_size == int(self.pin['bytes'])
        assert self.header['identity']['sha256'] == self.pin['sha256']
    def read(self, ordinal):
        self.index.seek(self.head + ordinal * 8)
        pair = self.index.read(16)
        assert len(pair) == 16
        lo, hi = struct.unpack('<QQ', pair)
        assert 0 < hi - lo < 16 * 1024**2
        guard(hi - lo)
        self.source.seek(lo)
        raw = self.source.read(hi - lo)
        assert len(raw) == hi - lo and raw.endswith(b'\n')
        return raw, lo

def keep(name, ordinal, raw, offset, source_path, **clocks):
    writer = writers.get(name)
    if writer is None or writer['bytes'] + len(raw) > CHUNK:
        if writer is not None:
            writer['handle'].close()
            files.append(dict(name=writer['path'].name, uncompressed_bytes=writer['bytes'],
                              rows=writer['rows'], bytes=writer['path'].stat().st_size))
        number = 1 if writer is None else writer['number'] + 1
        path = out / (name + '.chunk%03d.jsonl.gz' % number)
        writer = dict(number=number, path=path, handle=gzip.open(path, 'wb', compresslevel=3),
                      bytes=0, rows=0)
        writers[name] = writer
    writer['handle'].write(raw)
    writer['bytes'] += len(raw)
    writer['rows'] += 1
    counts[name] = counts.get(name, 0) + 1
    registry.write(json.dumps(dict(source=name, source_ordinal=ordinal, source_path=source_path,
        source_offset=offset, source_length=len(raw), original_row_sha256=hashlib.sha256(raw).hexdigest(),
        chunk=writer['path'].name, chunk_line_number=writer['rows'], **clocks),
        separators=(',', ':')) + '\n')

def unpack(value):
    if not isinstance(value, list) or not value:
        return value
    tag = value[0]
    if tag == 'dict':
        return {key: unpack(item) for key, item in value[1]}
    if tag in ('list', 'tuple', 'set', 'frozenset'):
        return [unpack(item) for item in value[1]]
    if tag == 'float64':
        return struct.unpack('>d', bytes.fromhex(value[1]))[0]
    if tag == 'null':
        return None
    if len(value) == 2 and tag in ('str', 'int', 'float', 'bool'):
        return value[1]
    return value

try:
    for name in ['native.member', 'root.frames', 'native.lifecycle']:
        readers[name] = Reader(name)
    second_path = Path('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl')
    life_ordinals = set()
    with second_path.open('rb') as second:
        for group in groups:
            ordinal = group['source_ordinal']
            raw, offset = readers['native.member'].read(ordinal)
            native = json.loads(raw)
            assert native['frankie_emission']['input_cursor'] == group['input_cursor']
            assert native['ts_recv_ns'] == group['recv_ns'] and native['ts_event_ns'] == group['event_ns']
            assert native['instrument_id'] == group['instrument_id']
            clocks = dict(input_cursor=group['input_cursor'], instrument_id=group['instrument_id'],
                          event_ns=group['event_ns'], receive_ns=group['recv_ns'], known_by_ns=group['recv_ns'])
            keep('native.member', ordinal, raw, offset, pins['native.member']['path'], **clocks)
            row = dict(db.execute('SELECT * FROM second_set_clock WHERE input_cursor=?',
                                  (group['input_cursor'],)).fetchone())
            assert row['source_length'] < 4 * 1024**2
            guard(row['source_length'])
            second.seek(row['source_offset'])
            raw = second.read(row['source_length'])
            assert len(raw) == row['source_length'] and raw.endswith(b'\n')
            assert hashlib.sha256(raw).hexdigest() == row['row_sha256']
            payload = json.loads(raw)
            assert payload['key']['input_cursor'] == group['input_cursor']
            assert payload['clocks']['clock_event_known_by'] == group['recv_ns']
            keep('second_set', group['input_cursor'], raw, row['source_offset'], str(second_path), **clocks)
            refs = payload['clocks']['clock_feature_availability']
            root_refs = [ref for ref in refs if ref[0] == 'root.frames']
            assert len(root_refs) == 1 and root_refs[0][1] == ordinal
            references[str(ordinal)] = refs
            raw, offset = readers['root.frames'].read(ordinal)
            root = unpack(json.loads(raw))
            assert root['ts_recv_ns'] == group['recv_ns'] and root['ts_event_ns'] == group['event_ns']
            keep('root.frames', ordinal, raw, offset, pins['root.frames']['path'], **clocks)
            life_ordinals.update(int(ref[1]) for ref in refs if ref[0] == 'native.lifecycle')
    for ordinal in sorted(life_ordinals):
        raw, offset = readers['native.lifecycle'].read(ordinal)
        row = json.loads(raw)
        emission = row['frankie_emission']
        keep('native.lifecycle', ordinal, raw, offset, pins['native.lifecycle']['path'],
             input_cursor=emission['input_cursor'], known_by_ns=emission['ts_recv_ns'],
             instrument_id=emission['instrument_id'])
    registry.close()
    for writer in writers.values():
        writer['handle'].close()
        files.append(dict(name=writer['path'].name, uncompressed_bytes=writer['bytes'],
                          rows=writer['rows'], bytes=writer['path'].stat().st_size))
    (out / 'original-group-metadata.json').write_text(json.dumps(groups) + '\n')
    (out / 'original-source-references.json').write_text(json.dumps(references) + '\n')
    receipt = dict(status='BOUNDED_EPISODE_SOURCES_EXPORTED_BYTE_FOR_BYTE',
                   first_group=3046, last_group=4712, instrument_id=150611,
                   primary_trade_ordinals=[118,149], group_records=len(groups),
                   original_source_pins={name: readers[name].pin for name in readers},
                   original_index_headers={name: readers[name].header for name in readers},
                   second_set_source=str(second_path), original_record_counts=counts,
                   source_bytes_read=bytes_read, source_byte_cap=CAP, chunk_uncompressed_cap=CHUNK,
                   elapsed_seconds=round(time.monotonic()-START,3), chunks=files,
                   source_policy='Read-only exact indexed records; no full ledger/database/archive rehash; new row/transport hashes only',
                   no_averaging=True, no_nested_field_filter=True, no_trades_removed=True,
                   fits=0, semantic_coverage='NOT_PASSED')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    archive = out / 'transport.tar'
    with tarfile.open(archive, 'w') as tar:
        for path in sorted(out.iterdir()):
            if path != archive:
                tar.add(path, arcname=path.name, recursive=False)
    assert archive.stat().st_size < 512 * 1024**2
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    with archive.open('rb') as body:
        request = urllib.request.Request(config['upload_url'], data=body, method='PUT',
                                         headers={'Content-Length': str(archive.stat().st_size)})
        with urllib.request.urlopen(request, timeout=120) as response:
            assert response.status == 200
    print(json.dumps(dict(status='EXPORTED_AND_TRANSPORTED', files=len(files),
          counts=counts, source_bytes_read=bytes_read, archive_bytes=archive.stat().st_size,
          archive_sha256=digest, local_transport_dir=str(out),
          elapsed_seconds=round(time.monotonic()-START,3)), separators=(',',':')), flush=True)
except Exception as error:
    print(json.dumps(dict(status='FAILED', error_type=type(error).__name__,
                          source_bytes_read=bytes_read, local_transport_dir=str(out))), flush=True)
    raise
