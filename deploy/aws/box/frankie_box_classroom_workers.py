"""Session-lived classroom CPU preparation and immutable source witnesses.

No model calls or scientific calculators run here. Threads share immutable bytes;
only independent preparation is dispatched, and results are joined in input order.
"""
from collections import deque
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import threading


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _record(item):
    key, raw = item
    if not isinstance(key, str) or not key or not isinstance(raw, bytes):
        raise ValueError('source inventory requires named immutable bytes')
    meta = dict(source_id=key, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return key, raw, _canonical(meta) + b'\n'


class SourceInventory(Mapping):
    """Ordered byte references with reusable per-source hashes and index bytes."""
    def __init__(self, sources, prepare_map=None):
        if isinstance(sources, SourceInventory):
            sources.index()
            self._records = sources._records.copy()
            self._index = sources._index
            self._index_hash = sources._index_hash.copy() if sources._index_hash is not None else None
        else:
            items = list(sources.items())
            rows = prepare_map(items, _record) if prepare_map is not None else map(_record, items)
            self._records = {key:(raw, line) for key,raw,line in rows}
            self._index = self._index_hash = None

    def __getitem__(self, key):
        return self._records[key][0]

    def __iter__(self):
        return iter(self._records)

    def __len__(self):
        return len(self._records)

    def __setitem__(self, key, raw):
        key, raw, line = _record((key, raw))
        replacing = key in self._records
        self._records[key] = (raw, line)
        if replacing:
            self._index = self._index_hash = None
        elif self._index is not None:
            self._index += line
            self._index_hash.update(line)

    def fork(self):
        return SourceInventory(self)

    def index(self):
        if self._index is None:
            self._index = b''.join(line for raw,line in self._records.values())
            self._index_hash = hashlib.sha256(self._index)
        return self._index, dict(source_id='source-index', bytes=len(self._index),
                                  sha256=self._index_hash.hexdigest())

    def source_records(self):
        return [dict(source_id=key, content=raw) for key,(raw,line) in self._records.items()]


class PreparationWorkers:
    """Coordinator plus fourteen pinned helpers, used only for CPU/I/O preparation."""
    def __init__(self):
        self.owner = threading.get_native_id()
        self.original_affinity = os.sched_getaffinity(self.owner)
        seen, cores = set(), []
        for cpu in sorted(self.original_affinity):
            base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
            key = (int((base/'physical_package_id').read_text()),
                   int((base/'core_id').read_text()))
            if key not in seen:
                seen.add(key)
                cores.append(dict(cpu=cpu, package=key[0], core=key[1]))
        if len(cores) < 16:
            raise ValueError('classroom requires a reserved physical core plus fifteen compute cores')
        self.reserved, self.coordinator = cores[0], cores[1]
        self.assignments = deque(cores[2:16])
        self.workers = []
        self.lock = threading.Lock()
        self.pool = None
        self.closed = False
        self.batches = self.items = 0
        os.sched_setaffinity(self.owner, {self.coordinator['cpu']})
        try:
            if os.sched_getaffinity(self.owner) != {self.coordinator['cpu']}:
                raise ValueError('classroom coordinator affinity differs')
            self.pool = ThreadPoolExecutor(max_workers=14, thread_name_prefix='classroom-prepare',
                                           initializer=self._initialize)
            # Initialization barrier starts all designated helpers, not calculations.
            barrier = threading.Barrier(14, timeout=30)
            starts = [self.pool.submit(barrier.wait) for _ in range(14)]
            for future in starts:
                future.result()
            if len(self.workers) != 14:
                raise ValueError('all designated classroom preparation helpers must start')
            # The coordinator is pinned only while it prepares (ordered()); between batches the owning thread keeps
            # its original CPUs, so pools the session creates later do not inherit a one-CPU mask (Greg, 2026-09-28).
            os.sched_setaffinity(self.owner, self.original_affinity)
        except BaseException:
            self.close()
            raise

    def _initialize(self):
        with self.lock:
            assignment = self.assignments.popleft()
        tid = threading.get_native_id()
        os.sched_setaffinity(tid, {assignment['cpu']})
        if os.sched_getaffinity(tid) != {assignment['cpu']}:
            raise ValueError('classroom helper affinity differs')
        with self.lock:
            self.workers.append(dict(thread_id=tid, **assignment))

    def receipt(self):
        return dict(schema='FRANKIE_CLASSROOM_PREPARATION_WORKERS_V1', pid=os.getpid(),
            coordinator=dict(thread_id=self.owner, **self.coordinator), reserved_io=self.reserved,
            helpers=sorted(self.workers, key=lambda x:x['cpu']), helpers_started=len(self.workers),
            transport='shared immutable bytes in one process; no process pickle',
            maximum_pending_tasks=28, prepared_batches=self.batches, prepared_items=self.items,
            affinity_readback_verified=True, model_concurrency_changed=False)

    def ordered(self, items, work):
        if self.closed or threading.get_native_id() != self.owner:
            raise ValueError('preparation is submitted only by the owning classroom coordinator')
        source, pending, result = iter(items), deque(), []
        exhausted = False
        os.sched_setaffinity(self.owner, {self.coordinator['cpu']})
        try:
            while not exhausted or pending:
                while not exhausted and len(pending) < 28:
                    try:
                        item = next(source)
                    except StopIteration:
                        exhausted = True
                    else:
                        pending.append(self.pool.submit(work, item))
                if pending:
                    result.append(pending.popleft().result())
        except BaseException:
            for future in pending:
                future.cancel()
            for future in pending:
                try:
                    future.result()
                except BaseException:
                    pass
            raise
        finally:
            os.sched_setaffinity(self.owner, self.original_affinity)
        self.batches += 1
        self.items += len(result)
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.pool is not None:
                self.pool.shutdown(wait=True, cancel_futures=True)
        finally:
            os.sched_setaffinity(self.owner, self.original_affinity)


def inventory(session, sources):
    if isinstance(sources, SourceInventory):
        return sources.fork()
    prepare = getattr(session, '_prepare_sources', None)
    return SourceInventory(sources, prepare_map=prepare)
