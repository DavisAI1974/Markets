"""Actual journal conversion and semantic conformance in one ordered traversal.

Dedicated, affinity-bound CPU processes verify full original canonical envelopes,
share exact order objects and compress bounded blocks. Parent runs every original
source-conformance predicate and commits blocks. No complete seal on failure.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import ctypes
import hashlib
import multiprocessing
import os
from pathlib import Path
import sqlite3
import time

from compact_journal import CompactWriter, encode_block, decode_block, verified_partition, MAX_BYTES
from compact_conformance_reader import project_entries
from verified_journal_reader import GENESIS_HASH


def pin_cpu(cpu):
    if type(cpu) is not int or cpu < 0:
        raise ValueError('explicit logical CPU required')
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 1 << cpu):
            raise OSError(ctypes.get_last_error(), 'CPU affinity assignment failed')
    else:
        os.sched_setaffinity(0, {cpu})


def _assign_cpu(queue):
    pin_cpu(queue.get())


def _convert_partition(path, start, length):
    cpu, wall = time.process_time(), time.perf_counter()
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        previous = GENESIS_HASH if start == 0 else db.execute(
            'SELECT digest FROM entries WHERE ordinal=?', (start-1,)).fetchone()[0]
        size = db.execute('SELECT sum(length(body)) FROM entries WHERE ordinal>=? AND ordinal<?',
                          (start,start+length)).fetchone()[0]
        if size is None or size > MAX_BYTES:
            raise ValueError('partition exceeds bounded byte budget')
        rows = db.execute('SELECT ordinal,kind,body,digest FROM entries WHERE ordinal>=? AND ordinal<? ORDER BY ordinal',
                          (start,start+length)).fetchall()
    finally:
        db.close()
    if len(rows) != length:
        raise ValueError('partition coverage differs')
    projected = project_entries(verified_partition(rows, start, previous))
    blob = encode_block(rows)
    if decode_block(blob) != rows:
        raise ValueError('exact storage reconstruction differs')
    return dict(start=start, count=length, previous=previous, head=rows[-1][3],
        blob=blob, entries=projected, raw_bytes=size,
        cpu_seconds=time.process_time()-cpu, wall_seconds=time.perf_counter()-wall)


class MigratingConformanceReader:
    def __init__(self, source, *, expected_count, expected_head_hash, output, worker_cpus, emit):
        if not worker_cpus or len(set(worker_cpus)) != len(worker_cpus):
            raise ValueError('distinct dedicated worker CPUs required')
        self.source, self.output = Path(source), Path(output)
        self.count, self.head_hash = expected_count, expected_head_hash
        self.worker_cpus, self.emit = tuple(worker_cpus), emit
        self.writer = CompactWriter(output)
        self.worker_cpu_seconds, self.raw_bytes, self.compact_bytes = 0.0, 0, 0
        self.finished = False

    def entries(self):
        context = multiprocessing.get_context('spawn')
        assignments = context.Queue()
        for cpu in self.worker_cpus:
            assignments.put(cpu)
        starts = iter(range(0,self.count,16))
        completed, previous = 0, GENESIS_HASH
        started, last_emit = time.perf_counter(), 0.0
        try:
            with ProcessPoolExecutor(max_workers=len(self.worker_cpus), mp_context=context,
                    initializer=_assign_cpu, initargs=(assignments,)) as pool:
                pending = deque()
                def submit():
                    start = next(starts,None)
                    if start is None:
                        return False
                    pending.append((time.perf_counter(),pool.submit(_convert_partition,
                        str(self.source),start,min(16,self.count-start))))
                    return True
                for _ in range(2*len(self.worker_cpus)):
                    if not submit():
                        break
                while pending:
                    queued, future = pending.popleft()
                    part = future.result()
                    if part['start'] != completed or part['previous'] != previous:
                        raise ValueError('ordered partition boundary differs')
                    blob = part['blob']
                    digest = hashlib.sha256(blob).hexdigest()
                    flushed = time.perf_counter()
                    with self.writer.db:
                        self.writer.db.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)',
                            (part['start'],part['count'],blob,digest,part['previous'],part['head']))
                    persisted = self.writer.db.execute('SELECT body FROM blocks WHERE start=?',
                                                       (part['start'],)).fetchone()[0]
                    if persisted != blob:
                        raise ValueError('persisted block readback differs')
                    flush_seconds = time.perf_counter()-flushed
                    yield from part['entries']
                    completed, previous = completed+part['count'],part['head']
                    self.writer.count,self.writer.head_hash = completed,previous
                    self.worker_cpu_seconds += part['cpu_seconds']
                    self.raw_bytes += part['raw_bytes']
                    self.compact_bytes += len(blob)
                    now = time.perf_counter()
                    if now-last_emit >= 10 or completed == self.count:
                        self.emit(dict(phase='verify_compress_conformance', entries=completed,
                            total=self.count, records=completed//2,
                            logical_entries_verified=completed,
                            compressed_blocks_completed=(completed+15)//16,
                            compressed_blocks_total=(self.count+15)//16,
                            percent=round(100*((completed+15)//16)/((self.count+15)//16),4),
                            bytes_saved=self.raw_bytes-self.compact_bytes,
                            records_per_second=(completed/2)/(now-started),
                            queued_blocks=len(pending), oldest_queue_age_seconds=now-pending[0][0] if pending else 0,
                            flush_seconds=flush_seconds, worker_cpu_seconds=self.worker_cpu_seconds,
                            raw_body_bytes=self.raw_bytes, compressed_block_bytes=self.compact_bytes,
                            worker_cpus=self.worker_cpus, backpressure='bounded_ordered_queue'))
                        last_emit=now
                    submit()
            if (completed,previous)!=(self.count,self.head_hash):
                raise ValueError('terminal journal identity differs')
            self.finished=True
        finally:
            assignments.close()
            assignments.join_thread()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None and self.finished:
                self.writer.seal(expected_count=self.count,expected_head_hash=self.head_hash)
        finally:
            self.writer.db.close()
