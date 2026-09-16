"""Profile one read-only drain of a C15 journal with the repository's own readers.

Measures what every native cycle pays several times over: decoding and verifying every row of a
prefix journal. Opens the file read-only, decodes nothing it does not verify, writes nothing but
the report. Reports wall seconds, rows, milliseconds per row, and the top cProfile functions, so
the per-row cost is attributed (SQLite fetch, JSON parse, tagged decode, canonical re-encode,
SHA-256, pair repack) rather than guessed.

    python operations/profile_journal_drain.py --journal prefix-01.sqlite --receipt prefix-01-receipt.json
        [--workers N] [--limit-rows R] [--report out.json]

The receipt supplies the independently held (journal_count, journal_head_hash). A compact
container (C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1) is drained single-threaded with CompactReader
and, when --workers > 1, again with FrankieCompactReader. A raw snapshot is drained with
VerifiedJournalReader. --limit-rows profiles only the first R rows; the drain then stops early
and the terminal identity is NOT checked, and the report says so.
"""
import argparse
import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from c15_journal import pack  # noqa: E402
from compact_journal import CompactReader  # noqa: E402
from verified_journal_reader import VerifiedJournalReader  # noqa: E402


def drain(entries, limit_rows=None):
    """Consume entries the way journal_prefix does: pair check via pack() on INPUT/APPLIED."""
    rows = applied = 0
    pending = None
    for entry in entries:
        rows += 1
        payload = entry['payload']
        if entry['kind'] == 'INPUT':
            pending = payload
        elif entry['kind'] == 'APPLIED':
            if pending is None or pack(payload['raw_record']) != pack(pending['record']):
                raise ValueError('journal applied record differs from submitted evidence')
            applied += 1
            pending = None
        if limit_rows is not None and rows >= limit_rows:
            break
    return rows, applied


def timed(label, make_reader, *, limit_rows, top):
    profiler = cProfile.Profile()
    started = time.perf_counter()
    reader = make_reader()
    try:
        profiler.enable()
        rows, applied = drain(reader.entries(), limit_rows)
        profiler.disable()
    finally:
        reader.close()
    wall = time.perf_counter() - started
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats('cumulative')
    stats.print_stats(top)
    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    result = dict(label=label, wall_seconds=round(wall, 3), rows=rows, applied_records=applied,
                  ms_per_row=round(1000 * wall / max(rows, 1), 3), complete=limit_rows is None,
                  profile_top=lines[:top + 8])
    print(json.dumps({k: v for k, v in result.items() if k != 'profile_top'}), flush=True)
    for line in result['profile_top']:
        print('   ', line)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--limit-rows', type=int)
    parser.add_argument('--top', type=int, default=25)
    parser.add_argument('--report')
    args = parser.parse_args()
    receipt = json.loads(Path(args.receipt).read_bytes())
    count, head = receipt['journal_count'], receipt['journal_head_hash']
    journal = Path(args.journal)
    compact = receipt.get('schema') == 'C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1'
    results = dict(schema='FRANKIE_JOURNAL_DRAIN_PROFILE_V1', journal=str(journal), bytes=journal.stat().st_size,
                   compact=compact, journal_count=count, python=sys.version.split()[0], runs=[])
    if compact:
        results['runs'].append(timed('compact_single_thread',
            lambda: CompactReader(journal, expected_count=count, expected_head_hash=head),
            limit_rows=args.limit_rows, top=args.top))
        if args.workers > 1:
            from frankie_journal_reader import FrankieCompactReader
            results['runs'].append(timed(f'compact_{args.workers}_workers',
                lambda: FrankieCompactReader(journal, expected_count=count, expected_head_hash=head, workers=args.workers),
                limit_rows=args.limit_rows, top=args.top))
    else:
        results['runs'].append(timed('raw_verified_reader',
            lambda: VerifiedJournalReader(journal, expected_count=count, expected_head_hash=head),
            limit_rows=args.limit_rows, top=args.top))
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
