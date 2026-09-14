"""Bounded synthetic software timing for Claude O1, never a provider/data run.

Run from the repository with the usual test PYTHONPATH. Output is diagnostic,
not a production-throughput gate. Work directories must be new; none are deleted.
"""
import argparse
from collections import Counter
from dataclasses import replace
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter_ns
from unittest.mock import patch

import torch
from c15_journal import EvidenceJournal
from context_session import journal_prefix
from forecast_artifact import DecoderSnapshot, NativeForecastArtifact, runtime_hash
from forecast_refresh import RefreshPolicy
from test_c15_full_evidence import submit, row
from test_native_forecast_refresh import build_refresh, update
from test_frankie_forecast_consumer import consume_forecast, context


def measure(operation, repeats):
    operation()  # One untimed warmup; no instrumentation during timing.
    elapsed = []
    for _ in range(repeats):
        started = perf_counter_ns()
        operation()
        elapsed.append((perf_counter_ns()-started)/1e6)
    ordered = sorted(elapsed)
    return dict(samples_ms=elapsed, median_ms=statistics.median(elapsed),
                p95_ms=ordered[math.ceil(.95*len(ordered))-1])


def case(root, rows, repeats):
    path = root/str(rows); path.mkdir()
    bridge, original = build_refresh(path)
    try:
        for index in range(1, rows):
            submit(bridge.context.builder, row(index, action='N', side='N', oid=0))
        bridge.context.t_ctx = 8
        source_as_of = (rows-1)*100+1
        receive = source_as_of+1
        source = bridge.context.builder.chain.prefix_hash
        base = tuple((replace(t, target_ns=2_000_000_000+i*2_000_000_000),
            replace(s, open_ns=1_000_000_000+i*2_000_000_000,
                close_ns=2_000_000_000+i*2_000_000_000,
                event_cutoff_ns=source_as_of, receive_cutoff_ns=receive, source_hash=source))
            for i, (t, s) in enumerate(original))
        bridge.targets = tuple(t for t, _ in base)
        bridge.policy = RefreshPolicy(((10_000_000_000, 1),))
        cursor = bridge.context.builder.chain.next_cursor-1
        counter = 0
        latest = None

        def refresh():
            nonlocal counter, latest
            counter += 1
            sessions = tuple((t, replace(s, receive_cutoff_ns=receive+counter)) for t, s in base)
            latest = update(bridge, sessions)[0]

        def scan():
            for entry in journal_prefix(bridge.context.builder, cursor):
                if entry['normalized']['ts_event_ns'] > source_as_of:
                    raise ValueError('synthetic event cutoff mismatch')

        metrics = dict(
            context_prepare=measure(lambda: bridge.context._prepare(receive, cursor), repeats),
            event_cutoff_scan=measure(scan, repeats),
            full_refresh_three_targets=measure(refresh, repeats))
        candidate = latest.selected
        artifact = NativeForecastArtifact.from_payload(candidate.forecast_artifact, expected_digest=candidate.candidate_id)
        metrics['structural_parse'] = measure(lambda: NativeForecastArtifact.from_payload(
            candidate.forecast_artifact, expected_digest=candidate.candidate_id), repeats)
        metrics['reproduction'] = measure(artifact.verify_reproduction, repeats)

        def consume():
            record = consume_forecast(enabled=True, legacy=None, book=bridge.book,
                publication_hash=latest.receipt_hash, metadata=context())
            if record.artifact_digest != latest.selected.candidate_id:
                raise ValueError('benchmark unexpectedly returned safety abstention')
            return record
        metrics['consume_with_ledger_verification'] = measure(consume, repeats)
        timed_ledger_entries = bridge.book.journal.count
        timed_ledger_bytes = bridge.book.journal.path.stat().st_size

        # Separate instrumented pass: measure visited entries and reconstruction
        # counts, never include wrapper overhead in the latency distributions.
        counts = Counter()
        entries = EvidenceJournal.entries
        restore = DecoderSnapshot.restore
        capture = DecoderSnapshot.capture
        def counted_entries(journal):
            for entry in entries(journal):
                key = 'evidence_entries_visited' if journal.path == bridge.context.builder.journal.path else 'forecast_entries_visited'
                counts[key] += 1
                yield entry
        def counted_restore(snapshot):
            counts['decoder_restores'] += 1
            return restore(snapshot)
        def counted_capture(cls, decoder):
            counts['decoder_captures'] += 1
            return capture(decoder)
        with (patch.object(EvidenceJournal, 'entries', counted_entries),
              patch.object(DecoderSnapshot, 'restore', counted_restore),
              patch.object(DecoderSnapshot, 'capture', classmethod(counted_capture))):
            consume()
            consume_counts = dict(counts)
            counts.clear()
            refresh()  # One additional revision beyond the timed workload.
            refresh_counts = dict(counts)
        return dict(rows=rows, t_ctx=8, targets=3, payload_bytes=len(candidate.forecast_artifact),
            evidence_journal_bytes=bridge.context.builder.journal.path.stat().st_size,
            timed_forecast_journal_bytes=timed_ledger_bytes,
            timed_forecast_journal_entries=timed_ledger_entries,
            forecast_entries_after_instrumented_refresh=bridge.book.journal.count,
            metrics=metrics, instrumented_refresh=refresh_counts,
            instrumented_consume=consume_counts, failures=0)
    finally:
        bridge.book.close()
        bridge.context.builder.journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rows', type=int, nargs='+', default=[32, 128, 512])
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if any(n < 1 or n > 2048 for n in args.rows) or not 3 <= args.repeats <= 20:
        parser.error('bounded synthetic workloads require 1..2048 rows and 3..20 repeats')
    args.work_dir.mkdir(parents=True, exist_ok=False)
    results = dict(scope='synthetic software only; no production throughput claim',
        python=sys.version, torch=str(torch.__version__), platform=platform.platform(),
        cpu=torch.backends.cpu.get_cpu_capability(), threads=torch.get_num_threads(),
        interop_threads=torch.get_num_interop_threads(), runtime_hash=runtime_hash(),
        repeats=args.repeats, percentile_method='nearest rank; five samples give an observed maximum at p95',
        cases=[])
    for rows in args.rows:
        result = case(args.work_dir, rows, args.repeats)
        results['cases'].append(result)
        print(json.dumps(dict(rows=rows, refresh_median_ms=result['metrics']['full_refresh_three_targets']['median_ms'],
            consume_median_ms=result['metrics']['consume_with_ledger_verification']['median_ms'])), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
