"""Full-evidence compact reads for Frankie, with bounded ordered CPU workers.

Unlike the conformance projection, every original envelope field is returned.
Physical storage changes neither the logical journal nor native context inputs.
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

try:
    from .compact_journal import CompactReader, decode_block, verified_partition
    from .verified_journal_reader import GENESIS_HASH
except ImportError:
    from compact_journal import CompactReader, decode_block, verified_partition
    from verified_journal_reader import GENESIS_HASH


def available_cpus():
    if hasattr(os, 'sched_getaffinity'):
        return sorted(os.sched_getaffinity(0))
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        process, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(),
                                            ctypes.byref(process), ctypes.byref(system)):
            raise OSError(ctypes.get_last_error(), 'CPU inventory failed')
        return [i for i in range(64) if process.value & (1 << i)]
    raise RuntimeError('explicit CPU affinity support required')


def worker_budget(requested):
    if type(requested) is not int or not 1 <= requested <= 64:
        raise ValueError('worker budget must be between 1 and 64')
    cpus = available_cpus()
    # Reserve a logical CPU for the ordered consumer and host when possible.
    return tuple((cpus[1:] or cpus)[:requested])


def _assign_cpu(assignments):
    cpu = assignments.get()
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 1 << cpu):
            raise OSError(ctypes.get_last_error(), 'CPU dedication failed')
    else:
        os.sched_setaffinity(0, {cpu})


def _read_block(path, index):
    start, length, previous, head = index
    started = time.process_time()
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        row = db.execute('SELECT count,body,sha256,previous,head FROM blocks WHERE start=?',
                         (start,)).fetchone()
    finally:
        db.close()
    if (row is None or (row[0], row[3], row[4]) != (length, previous, head)
            or hashlib.sha256(row[1]).hexdigest() != row[2]):
        raise ValueError('compact block identity differs')
    rows = decode_block(row[1])
    if len(rows) != length or rows[-1][3] != head:
        raise ValueError('compact block coverage differs')
    entries = list(verified_partition(rows, start, previous))
    return entries, time.process_time()-started


class FrankieCompactReader(CompactReader):
    def __init__(self, path, *, expected_count, expected_head_hash, workers=1, emit=None):
        self.worker_cpus = worker_budget(workers)
        self.emit = emit
        self.worker_cpu_seconds = 0.0
        super().__init__(path, expected_count=expected_count, expected_head_hash=expected_head_hash)

    def entries(self):
        context = multiprocessing.get_context('spawn')
        assignments = context.Queue()
        for cpu in self.worker_cpus:
            assignments.put(cpu)
        index = iter(self.db.execute('SELECT start,count,previous,head FROM blocks ORDER BY start'))
        count, head = 0, GENESIS_HASH
        started, last_emit = time.perf_counter(), 0.0
        try:
            with ProcessPoolExecutor(max_workers=len(self.worker_cpus), mp_context=context,
                    initializer=_assign_cpu, initargs=(assignments,)) as pool:
                pending = deque()
                def submit():
                    row = next(index, None)
                    if row is None:
                        return False
                    pending.append((row, time.perf_counter(),
                                    pool.submit(_read_block, str(self.path), row)))
                    return True
                # At most two bounded blocks per worker; no full-day materialization.
                for _ in range(2*len(self.worker_cpus)):
                    if not submit():
                        break
                while pending:
                    row, queued, future = pending.popleft()
                    start, length, previous, terminal = row
                    entries, cpu = future.result()
                    if (start != count or previous != head or len(entries) != length
                            or count+length > self.count):
                        raise ValueError('ordered compact seam differs')
                    yield from entries
                    count, head = count+length, terminal
                    self.worker_cpu_seconds += cpu
                    now = time.perf_counter()
                    if self.emit is not None and (now-last_emit >= 10 or count == self.count):
                        try:
                            self.emit(dict(phase='frankie_compact_read', entries=count,
                                total=self.count, percent=round(100*count/max(1,self.count),4),
                                records_per_second=count/2/max(now-started,1e-9),
                                worker_cpus=self.worker_cpus, worker_cpu_seconds=self.worker_cpu_seconds,
                                queued_blocks=len(pending),
                                oldest_queue_age_seconds=now-pending[0][1] if pending else 0))
                        except OSError:
                            pass  # Diagnostic I/O cannot change journal authority.
                        last_emit = now
                    submit()
            if (count, head) != (self.count, self.head_hash):
                raise ValueError('compact terminal identity differs')
            self._check_seal()
        finally:
            assignments.close()
            assignments.join_thread()
