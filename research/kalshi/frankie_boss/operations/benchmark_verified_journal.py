"""Benchmark lossless verified-journal worker counts on an immutable snapshot.

This is diagnostic only. It performs no model forward, training, cloud action or write to
the journal. Never point it at an active source-recovery journal. The caller must supply
the snapshot file SHA-256 plus its independently trusted journal count/head hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

from research.kalshi.frankie_boss.cpu_runtime import cpu_model
from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader, _worker_context


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_workers(value):
    result = tuple(int(item) for item in value.split(","))
    if not result or any(worker < 1 or worker > 256 for worker in result) or len(set(result)) != len(result):
        raise argparse.ArgumentTypeError("workers must be unique positive integers <=256")
    return result


def benchmark(path, expected_count, expected_head_hash, snapshot_sha256, workers, repeats):
    path = Path(path)
    before = file_sha256(path)
    if before != snapshot_sha256:
        raise ValueError("immutable snapshot differs from independently supplied file SHA-256")
    rows = []
    for worker_count in workers:
        samples = []
        for repeat in range(repeats):
            reader = VerifiedJournalReader(path, expected_count=expected_count,
                expected_head_hash=expected_head_hash, workers=worker_count)
            started = time.perf_counter()
            observed = 0
            try:
                for _ in reader.entries():
                    observed += 1
            finally:
                reader.close()
            elapsed = time.perf_counter() - started
            if observed != expected_count:
                raise ValueError("benchmark reader count differs from trusted checkpoint")
            samples.append(elapsed)
        median = statistics.median(samples)
        rows.append(dict(workers=worker_count, repeats=repeats,
            elapsed_seconds=samples, median_seconds=median,
            rows_per_second=(expected_count / median if median else None)))
    after = file_sha256(path)
    if after != before:
        raise ValueError("immutable snapshot bytes changed during benchmark")
    return dict(schema="FRANKIE_VERIFIED_JOURNAL_BENCHMARK_V1",
        journal=str(path.resolve()), snapshot_sha256=before,
        expected_count=expected_count, expected_head_hash=expected_head_hash,
        cpu_model=cpu_model(), start_method=_worker_context().get_start_method(),
        results=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--expected-head-hash", required=True)
    parser.add_argument("--workers", type=parse_workers, default=parse_workers("1,4,8,16"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 20:
        raise SystemExit("repeats must be between 1 and 20")
    result = benchmark(args.journal, args.expected_count, args.expected_head_hash,
        args.snapshot_sha256, args.workers, args.repeats)
    raw = json.dumps(result, sort_keys=True, indent=2) + "\n"
    Path(args.output).write_text(raw, encoding="utf-8")
    print(raw, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
