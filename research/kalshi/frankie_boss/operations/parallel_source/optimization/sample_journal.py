"""Bounded, standalone sample experiment. Never opens the active source DB."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'bundle/source.sqlite'
REPO = Path('C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie')
sys.path.insert(0, str(REPO))
from research.kalshi.frankie_boss.c15_journal import SCHEMA, canonical_bytes, pack, unpack, evidence_hash
from research.kalshi.frankie_boss.verified_journal_reader import decode_tagged, canonical_tagged_bytes


def encoded(tree):
    return json.dumps(tree, ensure_ascii=True, separators=(',', ':')).encode()


def field(tree, key):
    if tree[0] != 'dict':
        raise ValueError('mapping required')
    return next(value for name, value in tree[1] if name == key)


def gzip_measure(raw):
    result = {}
    for level in (1, 6):
        started = time.process_time()
        compressed = gzip.compress(raw, compresslevel=level, mtime=0)
        cpu = time.process_time() - started
        began = time.process_time()
        restored = gzip.decompress(compressed)
        decode_cpu = time.process_time() - began
        if restored != raw:
            raise ValueError('compression roundtrip differs')
        result[str(level)] = dict(bytes=len(compressed), ratio=len(raw)/len(compressed),
            compression_cpu_seconds=cpu, decompression_cpu_seconds=decode_cpu)
    return result


def main():
    output = Path(__file__).with_name('sample-results.json')
    if output.exists():
        raise ValueError('existing experiment result must not be overwritten or repeated')
    phase = json.loads((ROOT/'snapshot-progress.json').read_bytes())['phase']
    if phase not in ('snapshot_hash', 'compressing_snapshot', 'archive_hash', 'ready'):
        raise ValueError('independent SQLite backup is not yet closed')
    checkpoint = json.loads((ROOT/'bundle/checkpoint-receipt.json').read_bytes())
    if checkpoint['journal_count'] != 114054:
        raise ValueError('unexpected independent checkpoint count')
    # 48 evenly distributed complete pairs + 16 adjacent pairs, at most 128 rows.
    cursors = sorted(set(round(i * 57026 / 47) for i in range(48)) | set(range(28506, 28522)))
    ordinals = [ordinal for cursor in cursors for ordinal in (cursor*2, cursor*2+1)]
    before = DB.stat()
    connection = sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1', uri=True)
    connection.execute('PRAGMA query_only=ON')
    rows, skipped, total = [], [], 0
    try:
        tail = connection.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
        if tail != (checkpoint['journal_count']-1, checkpoint['journal_hash']):
            raise ValueError('snapshot tail differs from checkpoint')
        for ordinal in ordinals:
            size = connection.execute('SELECT length(body) FROM entries WHERE ordinal=?', (ordinal,)).fetchone()[0]
            if total+size > 32*1024*1024:
                skipped.append(ordinal)
                continue
            row = connection.execute('SELECT ordinal,kind,body,digest FROM entries WHERE ordinal=?', (ordinal,)).fetchone()
            rows.append(row)
            total += size
    finally:
        connection.close()
    after = DB.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('independent snapshot changed')
    field_bytes, kind_bytes, observation_samples = {}, {}, []
    for ordinal, kind, body, digest in rows:
        if hashlib.sha256(SCHEMA.encode()+b'\0'+body).hexdigest() != digest:
            raise ValueError('sample body digest mismatch')
        tree = json.loads(body)
        if encoded(tree) != body:
            raise ValueError('sample canonical bytes differ')
        kind_bytes[kind] = kind_bytes.get(kind, 0)+len(body)
        if kind == 'APPLIED':
            payload = field(tree, 'payload')
            for key, value in payload[1]:
                field_bytes[key] = field_bytes.get(key, 0)+len(encoded(value))
            observation = field(payload, 'observation')
            if 28506 <= ordinal//2 < 28522 and observation[0] != 'null':
                observation_samples.append(observation)
    raw = b'\n'.join(row[2] for row in rows)
    compressed = gzip_measure(raw)
    # Limited one-shot CPU comparison; full journal continuity is not claimed.
    timing_rows, timing_bytes = [], 0
    for row in rows:
        if timing_bytes+len(row[2]) <= 2*1024*1024 and len(timing_rows) < 16:
            timing_rows.append(row)
            timing_bytes += len(row[2])
    timing = {}
    timing_plain = b'\n'.join(row[2] for row in timing_rows)
    timing_compressed = {str(level): gzip.compress(timing_plain, compresslevel=level, mtime=0) for level in (1, 6)}
    for name in ('legacy', 'verified_reader', 'verified_gzip_1', 'verified_gzip_6'):
        began = time.process_time()
        selected = timing_rows
        if name.startswith('verified_gzip_'):
            bodies = gzip.decompress(timing_compressed[name[-1]]).split(b'\n')
            if len(bodies) != len(timing_rows):
                raise ValueError('compressed timed sample row count differs')
            selected = [(row[0], row[1], body, row[3]) for row, body in zip(timing_rows, bodies)]
        for ordinal, kind, body, digest in selected:
            if name == 'legacy':
                envelope = unpack(json.loads(body))
                valid = canonical_bytes(pack(envelope)) == body and evidence_hash(envelope) == digest
            else:
                tree = json.loads(body)
                envelope = decode_tagged(tree)
                valid = canonical_tagged_bytes(tree) == body and hashlib.sha256(SCHEMA.encode()+b'\0'+body).hexdigest() == digest
            if not valid or envelope['ordinal'] != ordinal or envelope['kind'] != kind:
                raise ValueError('sample decoder result differs')
        timing[name+'_cpu_seconds'] = time.process_time()-began
    timing['ratio'] = timing['legacy_cpu_seconds']/timing['verified_reader_cpu_seconds']
    timing['rows'] = len(timing_rows)
    timing['bytes'] = timing_bytes
    timing['compressed_bytes'] = {level:len(body) for level,body in timing_compressed.items()}
    # Exact book-order dictionary prototype. Retains all other observation nodes.
    dictionary, lookup, records, original_order_bytes = [], {}, [], 0
    for observation in observation_samples:
        template = copy.deepcopy(observation)
        orders = field(template, 'orders')
        if orders[0] != 'list':
            raise ValueError('observation orders list required')
        ids = []
        for order in orders[1]:
            order_bytes = encoded(order)
            original_order_bytes += len(order_bytes)
            if order_bytes not in lookup:
                lookup[order_bytes] = len(dictionary)
                dictionary.append(order_bytes.decode())
            ids.append(lookup[order_bytes])
        orders[1] = []
        records.append(dict(template=template, order_ids=ids))
    container = dict(schema='EXPERIMENT_EXACT_OBSERVATION_ORDER_DICTIONARY_V1', dictionary=dictionary, records=records)
    for original, record in zip(observation_samples, container['records']):
        restored = copy.deepcopy(record['template'])
        field(restored, 'orders')[1] = [json.loads(container['dictionary'][index]) for index in record['order_ids']]
        if encoded(restored) != encoded(original):
            raise ValueError('observation prototype exact-byte roundtrip failed')
    original = encoded(observation_samples)
    prototype = encoded(container)
    report = dict(scope='FIXED_SAMPLE_ONLY_NOT_FULL_VERIFICATION_OR_PRODUCTION_BENCHMARK',
        snapshot=str(DB), snapshot_phase_at_open=phase, snapshot_bytes=before.st_size,
        checkpoint_state_hash=checkpoint['state_hash'], journal_count=checkpoint['journal_count'],
        sample_rows=len(rows), sample_body_bytes=total, sample_ordinals=[row[0] for row in rows], skipped_ordinals=skipped,
        kind_bytes=kind_bytes, applied_field_value_bytes=field_bytes, gzip_levels=compressed,
        sample_input_sha256=hashlib.sha256(raw).hexdigest(), decoder_one_shot=timing,
        observation_prototype=dict(observations=len(observation_samples), unique_orders=len(dictionary),
            original_order_bytes=original_order_bytes, unique_order_bytes=sum(len(v.encode()) for v in dictionary),
            original_observation_bytes=len(original), prototype_bytes=len(prototype),
            original_gzip=gzip_measure(original), prototype_gzip=gzip_measure(prototype), exact_roundtrip=True),
        limitations=['Sample not statistically weighted; field shares exclude envelope/key overhead.',
            'No full-chain/source-conformance claim; sampled bytes only.',
            'One-shot decoder timing, fixed order, no variance estimate or production speedup guarantee.',
            'Adjacent observation dictionary is a prototype, not a migrated journal format.'])
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('sample_rows','sample_body_bytes','gzip_levels','decoder_one_shot','observation_prototype')}))


if __name__ == '__main__':
    main()
