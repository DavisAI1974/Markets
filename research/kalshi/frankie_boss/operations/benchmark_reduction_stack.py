"""One bounded comparison of the new stack; never scans retained full journals.

Run with explicit output on the evidence drive. The original fixed sample is
read once and checked against its retained sample digest. Timed repetitions are
measurements of changed implementations, not repeats of old passing test suites.
"""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE/'tests'), str(HERE.parents[2])]
from c15_builder import C15Builder
from c15_journal import canonical_bytes, pack, unpack, evidence_hash
from source_conformance import SourceConformanceDriver
from verified_journal_reader import canonical_tagged_bytes, decode_tagged, DIGEST_PREFIX
from compact_journal import encode_block, decode_block, CompactWriter
from single_pass_finalization import finalize_snapshot, physical_hash
from test_single_pass_finalization import fixture


def measure(call):
    wall, cpu = time.perf_counter(), time.process_time()
    result = call()
    return result, dict(wall_seconds=time.perf_counter()-wall, parent_cpu_seconds=time.process_time()-cpu)


def baseline(path, scope, state, physical):
    if physical_hash(path) != physical:
        raise ValueError('physical identity differs')
    builder = C15Builder.restore(scope, path, state, expected_hash=state['state_hash'])
    driver = SourceConformanceDriver.__new__(SourceConformanceDriver)
    driver._builder = builder
    driver._stopped = driver._completed = driver._closed = False
    try:
        result = driver.complete()
    finally:
        driver.close()
    if physical_hash(path) != physical:
        raise ValueError('physical identity changed')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    sample = json.loads((args.evidence_root/'github-parallel/optimization/sample-results.json').read_bytes())
    db_path = args.evidence_root/'github-parallel/bundle/source.sqlite'
    before = db_path.stat()
    db = sqlite3.connect(db_path.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        rows = [db.execute('SELECT ordinal,kind,body,digest FROM entries WHERE ordinal=?',
                          (ordinal,)).fetchone() for ordinal in sample['sample_ordinals']]
    finally:
        db.close()
    raw = b'\n'.join(row[2] for row in rows)
    if hashlib.sha256(raw).hexdigest() != sample['sample_input_sha256']:
        raise ValueError('fixed sample identity differs')
    blob, encode_time = measure(lambda: encode_block(rows))
    if decode_block(blob) != rows:
        raise ValueError('exact sample roundtrip differs')

    def check(mode):
        selected = decode_block(blob) if mode == 'compact_fast' else rows
        for ordinal, kind, body, digest in selected:
            if mode == 'legacy':
                envelope = unpack(json.loads(body))
                valid = canonical_bytes(pack(envelope)) == body and evidence_hash(envelope) == digest
            else:
                tree = json.loads(body)
                envelope = decode_tagged(tree)
                valid = canonical_tagged_bytes(tree) == body and hashlib.sha256(DIGEST_PREFIX+body).hexdigest() == digest
            if not valid or envelope['ordinal'] != ordinal or envelope['kind'] != kind:
                raise ValueError('sample validation differs')
    timings = {name: [] for name in ('legacy', 'fast', 'compact_fast')}
    for order in (('legacy','fast','compact_fast'), ('compact_fast','legacy','fast'), ('fast','compact_fast','legacy')):
        for name in order:
            _, timing = measure(lambda: check(name))
            timings[name].append(timing)
            print(json.dumps(dict(phase='sample_benchmark', mode=name, **timing)), flush=True)

    synthetic = args.output/'synthetic'
    synthetic.mkdir()
    source, scope, state, expected, physical = fixture(synthetic, 128)
    compact = args.output/'synthetic-compact.sqlite'
    db = sqlite3.connect(source)
    write_started = time.perf_counter()
    try:
        with CompactWriter(compact, block_bytes=512*1024) as writer:
            for row in db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal'):
                writer.add(row)
            writer.seal(expected_count=state['journal_count'], expected_head_hash=state['journal_hash'])
            flush_seconds = writer.flush_seconds
    finally:
        db.close()
    write_seconds = time.perf_counter()-write_started
    compact_hash = physical_hash(compact)
    pipeline = {}
    operations = {
        'legacy_two_pass': lambda: baseline(source, scope, state, physical),
        'fast_single_pass': lambda: finalize_snapshot(source, scope, state,
            expected_scope_hash=scope.genesis_hash(), expected_state_hash=state['state_hash'],
            expected_physical_sha256=physical),
        'compact_single_pass_two_workers': lambda: finalize_snapshot(compact, scope, state,
            expected_scope_hash=scope.genesis_hash(), expected_state_hash=state['state_hash'],
            expected_physical_sha256=compact_hash, storage='compact', workers=2)}
    for name, operation in operations.items():
        result, timing = measure(operation)
        if name == 'legacy_two_pass':
            completion = result
        else:
            completion = result.completion
            if result.checkpoint != state:
                raise ValueError('combined checkpoint differs')
            timing['worker_cpu_seconds'] = result.worker_cpu_seconds
        if completion != expected:
            raise ValueError('combined completion differs')
        pipeline[name] = timing
        print(json.dumps(dict(phase='pipeline_benchmark', mode=name, **timing)), flush=True)
    after = db_path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('independent sample source changed')
    report = dict(schema='FRANKIE_REDUCTION_STACK_BENCHMARK_V1',
        sample=dict(rows=len(rows), canonical_bytes=len(raw), input_sha256=sample['sample_input_sha256'],
            gzip6_bytes=len(gzip.compress(raw, compresslevel=6, mtime=0)),
            compact_bytes=len(blob), compact_ratio=len(raw)/len(blob), encode=encode_time,
            timings=timings),
        synthetic=dict(records=128, entries=state['journal_count'], source_bytes=source.stat().st_size,
            compact_bytes=compact.stat().st_size, write_seconds=write_seconds, flush_seconds=flush_seconds,
            timings=pipeline, completion=asdict(expected)),
        dedicated_workers=2, max_inflight_blocks=4,
        limitations=['Fixed sample storage/decoder results are not a full-journal claim.',
            'Synthetic full-conformance timings are not Sunday or sustained real-time acceptance.',
            'Worker CPU excludes process startup; parent CPU is reported separately.',
            'Concurrent original schedule and GitHub work preserved; no affinity claim.',
            'Free Colab/Kaggle GPU tutorial does not establish a provisioned Frankie resource.'])
    (args.output/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps(dict(result=str(args.output/'result.json'), storage_ratio=report['sample']['compact_ratio'])),flush=True)

if __name__ == '__main__':
    main()
