"""Read-only timing of VerifiedJournalReader on real, closed, witness-pinned prefix snapshots.

Hashes each snapshot before and after against its witness pin, refuses any file with a live
WAL or rollback sidecar, and never opens source.sqlite or any active writer's journal. The
compact (cycle 1..18) snapshot is probed once so the result records whether this reader can
read it at all. Output: a JSON table, one row per (snapshot, worker count).

    python research/kalshi/frankie_boss/operations/benchmark_verified_reader.py --out bench.json
Intra-op PyTorch thread timings are a different benchmark and need the native host; this
script measures only the journal drain that precedes every native step.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[4]))
sys.path.insert(0, str(HERE.parents[1]))
from verified_journal_reader import VerifiedJournalReader  # noqa: E402

RUNTIME = Path('E:/Codex/Frankie-BOSS-20260915')
TARGETS = (
    ('prefix-00 (raw, cycle 0)', RUNTIME / 'source-execution-20260915/actual-first-cutoff-capacity/prefix.sqlite',
     RUNTIME / 'actual-prefixes/prefix-00-witness.json', (1, 2, 4, 8, 16)),
    ('prefix-01 (compact, cycle 1)', RUNTIME / 'actual-prefixes/prefix-01.sqlite',
     RUNTIME / 'actual-prefixes/prefix-01-witness.json', (1,)),
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 22), b''):
            digest.update(chunk)
    return digest.hexdigest()


def stored_tail(path):
    connection = sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if 'entries' not in tables:
            return None, None, tables
        count, = connection.execute('SELECT count(*) FROM entries').fetchone()
        head, = connection.execute('SELECT digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
        return count, head, tables
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    cpus = os.cpu_count()
    out = dict(schema='VERIFIED_READER_BENCHMARK_V1', host_logical_cpus=cpus, results=[])
    for label, path, witness, counts in TARGETS:
        for sidecar in ('-wal', '-journal'):
            side = Path(str(path) + sidecar)
            if side.exists() and side.stat().st_size > 32:
                raise SystemExit('live sidecar present; refusing to read ' + str(path))
        pinned = json.loads(witness.read_bytes())['snapshot']['sha256']
        before = sha256(path)
        if before != pinned:
            raise SystemExit('snapshot differs from its witness pin: ' + label)
        count, head, tables = stored_tail(path)
        record = dict(label=label, bytes=path.stat().st_size, rows=count, tables=tables, runs=[])
        if count is None:
            record['verified_journal_reader'] = 'REFUSES: no entries table (compact block layout)'
        for workers in counts:
            if count is None or workers > (cpus or 1):
                continue
            started = time.perf_counter()
            consumed, error = 0, None
            try:
                with VerifiedJournalReader(path, expected_count=count, expected_head_hash=head, workers=workers) as reader:
                    for _ in reader.entries():
                        consumed += 1
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            record['runs'].append(dict(workers=workers, seconds=round(time.perf_counter() - started, 2),
                                       rows_read=consumed, error=error))
            print(json.dumps(dict(label=label, **record['runs'][-1])), flush=True)
        record['sha256_after_equals_pin'] = sha256(path) == pinned
        out['results'].append(record)
    Path(args.out).write_bytes(json.dumps(out, indent=1).encode())
    return 0


if __name__ == '__main__':
    sys.exit(main())
