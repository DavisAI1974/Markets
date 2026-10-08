"""Canary: the search's on-disk frame columns, option A (DIGEST_V10 tables) vs option B (typed segments), measured on
slices of a real frames spool and extrapolated to a full day (Greg, 2026-10-07 night: "measurements are 1-2 minute
canaries, then extrapolate"; R5 GO: build both and measure, do not pick by taste).

What it does (read-only on the spool; writes only under --out, removed at the end unless --keep):
  1. picks --windows byte windows spread over the spool (each cut at line starts, inside the first 90% of the file so a
     spool still being appended is never read at its tail), each split into --workers ranges;
  2. for each option, runs frankie_box_experiment_search._disk_chunk on the lane's pinned workers
     (frankie_box_lane_pin.ordered_map) exactly as the search does, timing the wall and summing the chunk bytes and the
     workers' peak RSS;
  3. reads every channel of the written chunks back on ONE process (the search's reader, FrameColumnStore.column),
     timing it, and compares every value (type and float bits) with columns() of the same ranges (the in-memory
     reference): exact or not, per option;
  4. extrapolates to --full-bytes (default: the spool's size; e.g. 430e9 for a2's projection): bytes on disk, write
     wall at this worker count, read time per worker for every channel.
It never changes a search, an export or a pin. Run on the box only on Greg's go (see the record
research/kalshi/frankie_boss/STACKS_PASS_20261007_DATA_SEARCH.md for the command).
"""
import argparse
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sys
import time


def _windows(path, size, count, window_bytes):
    """[(start, end)] line-aligned windows spread over the first 90% of the file."""
    usable = int(size * 0.9)
    out = []
    with open(path, 'rb') as handle:
        for k in range(count):
            nominal = (usable - window_bytes) * k // max(1, count - 1) if count > 1 else 0
            handle.seek(max(0, nominal - 1))
            if nominal:
                handle.readline()
            start = handle.tell()
            handle.seek(max(start, min(usable, start + window_bytes) - 1))
            handle.readline()
            end = handle.tell()                    # just after a newline (a whole row), never past the 90% mark by more
            if end > start and end <= size and (not out or start >= out[-1][1]):
                out.append((start, end))
    return out


def _ranges(path, start, end, pieces):
    cuts = [start]
    with open(path, 'rb') as handle:
        for k in range(1, pieces):
            nominal = start + (end - start) * k // pieces
            if nominal <= cuts[-1]:
                continue
            handle.seek(nominal - 1)
            handle.readline()
            if cuts[-1] < handle.tell() < end:
                cuts.append(handle.tell())
    cuts.append(end)
    return list(zip(cuts, cuts[1:]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--frames', required=True, help='a real frames.jsonl (ROOT work/derived/.rows/frames.jsonl)')
    p.add_argument('--out', default=None, help='scratch directory (default /opt/frankie-box/work/canary-search-columns/<ts>)')
    p.add_argument('--workers', type=int, default=None, help='default: the held lane size minus 1')
    p.add_argument('--windows', type=int, default=3)
    p.add_argument('--window-bytes', type=int, default=None, help='default: workers x 4 MiB (about 5 rows per range)')
    p.add_argument('--full-bytes', type=float, default=None, help='extrapolation target (default: the spool size)')
    p.add_argument('--codecs', default='typed,digest_v10')
    p.add_argument('--keep', action='store_true')
    a = p.parse_args()
    here = Path(__file__).resolve()
    sys.path[:0] = [str(here.parent), str(here.parents[3])]
    import frankie_box_experiment_search as S
    import frankie_box_lane_pin as LP
    lane = LP.lane_cpus()
    workers = a.workers or max(1, len(lane) - 1)
    frames = Path(a.frames)
    size = frames.stat().st_size
    window_bytes = a.window_bytes or workers * (4 << 20)
    out = Path(a.out or '/opt/frankie-box/work/canary-search-columns/%d' % int(time.time()))
    out.mkdir(parents=True, exist_ok=True)
    windows = _windows(frames, size, a.windows, window_bytes)
    ranges = [r for start, end in windows for r in _ranges(frames, start, end, workers)]
    sampled = sum(b - a_ for a_, b in ranges)
    report = dict(schema='FRANKIE_SEARCH_COLUMNS_CANARY_V1', frames=str(frames), spool_bytes=size, workers=workers,
                  lane=lane, windows=windows, ranges=len(ranges), sampled_bytes=sampled,
                  full_bytes=a.full_bytes or size, options={})
    started_all = time.time()
    reference = None
    for codec in [c for c in a.codecs.split(',') if c]:
        directory = out / codec
        directory.mkdir(parents=True, exist_ok=True)
        jobs = [(str(frames), r0, r1, str(directory / ('chunk-%06d.bin' % k)), codec) for k, (r0, r1) in enumerate(ranges)]
        recovery = dict(worker_deaths=[], redone=[])
        started = time.time()
        results = [result for _, result in LP.ordered_map(S._disk_chunk, jobs, min(workers, len(jobs)),
                                                           context=multiprocessing.get_context('fork'), cpus=lane,
                                                           window=min(workers, len(jobs)) * 2, report=recovery)]
        write_wall = time.time() - started
        order, segments, chunks, rows = dict(n=[], t=[]), {}, [], 0
        known = dict(n=set(), t=set())
        for number, result in enumerate(results):
            for kind, name, offset, length, present, dense, big in result['segments']:
                if name not in known[kind]:
                    known[kind].add(name)
                    order[kind].append(name)
                segments.setdefault((kind, name), []).append((number, offset, length, present, dense, big))
            chunks.append((Path(jobs[number][3]).name, result['rows'], result['bytes'], result['sha256']))
            rows += result['rows']
        store = S.FrameColumnStore(directory, rows, chunks, order, segments, codec)
        S._COLUMN_CACHE.clear()
        started = time.time()
        values = 0
        read = {}
        for kind in ('n', 't'):
            for name in order[kind]:
                column = store.column(kind, name)
                values += sum(v is not None for v in column)
                read[(kind, name)] = column
                S._COLUMN_CACHE.clear()
        read_wall = time.time() - started
        if reference is None:
            numeric, text, count = {}, {}, 0
            for r0, r1 in ranges:                 # the in-memory reference of the same ranges (the merge rule)
                part_n, part_t, part_count = S._spool_range_columns((str(frames), r0, r1))
                for merged, part in ((numeric, part_n), (text, part_t)):
                    for key, column in part.items():
                        merged.setdefault(key, [None] * count).extend(column)
                    for key, column in merged.items():
                        if key not in part:
                            column.extend([None] * part_count)
                count += part_count
            reference = dict(n=numeric, t=text, rows=count)
        exact = (rows == reference['rows'] and list(reference['n']) == order['n'] and list(reference['t']) == order['t']
                 and all([S._typed_key(v) for v in read[(k, name)]] == [S._typed_key(v) for v in reference[k][name]]
                         for k in ('n', 't') for name in order[k]))
        stored = sum(c[2] for c in chunks)
        full = report['full_bytes']
        report['options']['A_digest_v10' if codec == 'digest_v10' else 'B_typed'] = dict(
            codec=codec, exact_parse_back=exact, rows=rows, channels=dict(numeric=len(order['n']), text=len(order['t'])),
            present_values=values, bytes_on_disk=stored, disk_to_spool_ratio=round(stored / sampled, 4) if sampled else None,
            write_seconds=round(write_wall, 3), write_bytes_per_second_all_workers=round(sampled / write_wall) if write_wall else None,
            write_bytes_per_second_per_worker=round(sampled / write_wall / min(workers, len(jobs))) if write_wall else None,
            read_seconds_one_process=round(read_wall, 3),
            read_values_per_second_per_worker=round(values / read_wall) if read_wall else None,
            read_spool_bytes_per_second_per_worker=round(sampled / read_wall) if read_wall else None,
            peak_rss_bytes_per_worker=max((r['max_rss'] or 0) for r in results) if results else None,
            pool_recovery=recovery,
            extrapolated=dict(full_bytes=full, bytes_on_disk=round(stored / sampled * full) if sampled else None,
                              write_wall_seconds=round(full / (sampled / write_wall)) if write_wall else None,
                              read_every_channel_seconds_per_worker=round(full / (sampled / read_wall)) if read_wall else None,
                              basis='linear in spool bytes at this worker count; sampled windows spread over the file'))
        if not a.keep:
            shutil.rmtree(directory, ignore_errors=True)
    report['seconds'] = round(time.time() - started_all, 3)
    report['rule'] = 'measurement only: nothing here changes a search, an export or a pin; option chosen by Greg'
    (out / 'canary.json').write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    if not a.keep:
        shutil.rmtree(out / 'typed', ignore_errors=True)


if __name__ == '__main__':
    main()
