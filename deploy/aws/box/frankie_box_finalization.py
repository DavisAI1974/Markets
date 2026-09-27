"""Bounded disk verification and read-only reuse of finalized native ledgers.

No scientific calculators run here. Every verification reads the original bytes,
counts all lines and hashes in file order. Closed checkpoint ledgers are referenced
in place; original evidence and fresh empty placeholders are both retained.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import stat
import threading
import time
import weakref

from frankie_box_prepare_trading_day import safe_path
from frankie_box_segmented_ledger import _read_at

CHUNK_BYTES = 8 << 20
PREFETCH = 28
_CACHE = weakref.WeakKeyDictionary()


def file_identity(path):
    info = safe_path(path).stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('regular ledger evidence required')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _block(fd, offset, width):
    raw = _read_at(fd, offset, width)
    return raw, raw.count(b'\n')


def scan(path, expected_rows, expected_bytes, expected_sha256, progress=None, name='ledger'):
    before = file_identity(path)
    if before[2] != expected_bytes:
        raise ValueError('sealed ledger size differs')
    owner = threading.get_native_id()
    original = os.sched_getaffinity(owner)
    # Canonical box policy: CPU0 reserved, CPU1 joins ordered bytes, CPUs2-15 read.
    cores = []
    for cpu in range(16):
        topology = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
        cores.append((int((topology/'physical_package_id').read_text()),
                      int((topology/'core_id').read_text())))
    if len(set(cores)) != 16:
        raise ValueError('sixteen distinct designated physical cores required')
    assignments, helpers, lock = deque(range(2,16)), [], threading.Lock()
    def initialize():
        with lock:
            cpu = assignments.popleft()
        tid = threading.get_native_id()
        os.sched_setaffinity(tid, {cpu})
        if os.sched_getaffinity(tid) != {cpu}:
            raise ValueError('ledger helper affinity readback differs')
        with lock:
            helpers.append(dict(thread_id=tid, cpu=cpu))
    digest, rows, size, last = hashlib.sha256(), 0, 0, b''
    fd = None
    started = time.monotonic()
    os.sched_setaffinity(owner, {1})
    try:
        if os.sched_getaffinity(owner) != {1}:
            raise ValueError('ledger coordinator affinity readback differs')
        fd = os.open(safe_path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size,
                opened.st_mtime_ns, opened.st_ctime_ns) != before:
            raise ValueError('ledger changed while opening')
        with ThreadPoolExecutor(max_workers=14, initializer=initialize,
                                thread_name_prefix='ledger-read') as pool:
            barrier = threading.Barrier(14, timeout=30)
            starts = [pool.submit(barrier.wait) for _ in range(14)]
            for future in starts:
                future.result()
            pending, offset = deque(), 0
            while offset < expected_bytes or pending:
                while offset < expected_bytes and len(pending) < PREFETCH:
                    width = min(CHUNK_BYTES, expected_bytes-offset)
                    pending.append(pool.submit(_block, fd, offset, width))
                    offset += width
                raw, count = pending.popleft().result()
                digest.update(raw)
                size += len(raw)
                rows += count
                last = raw[-1:]
                if progress is not None:
                    progress.update('root-ledger-verify-' + name, size, expected_bytes, force=False)
            # Executor joins every reader before the shared descriptor is closed.
        if last and last != b'\n':
            rows += 1
        info = os.fstat(fd)
        if ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != before
                or file_identity(path) != before):
            raise ValueError('ledger changed during independent disk verification')
        if (rows != expected_rows or size != expected_bytes or digest.hexdigest() != expected_sha256):
            raise ValueError('ledger rows/bytes/hash differ from emitted evidence')
    finally:
        if fd is not None:
            os.close(fd)
        os.sched_setaffinity(owner, original)
    policy = dict(schema='FRANKIE_LEDGER_VERIFICATION_V1', coordinator_cpu=1,
                  reserved_cpu=0, helpers=sorted(helpers,key=lambda x:x['cpu']),
                  maximum_pending_chunks=PREFETCH, chunk_bytes=CHUNK_BYTES,
                  bytes_read=size, rows_read=rows, seconds=round(time.monotonic()-started,3),
                  ordered_sha256=True, affinity_readback_verified=True)
    return digest, before, policy


def restore_closed(saved, sinks, progress=None):
    for name in ('member', 'lifecycle', 'legacy'):
        entry, sink = saved[name], getattr(sinks, name)
        attrs = entry['attributes']
        if (attrs.get('_closed') is not True or 'storage_schema' in entry
                or {'path', '_handle', '_digest'} & set(attrs)):
            raise ValueError('finalized restore requires closed materialized ledger state')
        path = safe_path(entry['path'])
        if path.name != sink.path.name:
            raise ValueError('finalized ledger name differs')
        digest, identity, policy = scan(path, attrs['_rows'], attrs['_bytes'], entry['sha256'],
                                        progress, name)
        sink._handle.close()  # Fresh zero-byte placeholder is retained, never published.
        sink.__dict__.update(attrs)
        sink.path, sink._digest = path, digest
        receipt = sink.receipt()
        receipt.update(reconciled_against_counter=attrs['_rows'], rows_read_back_from_disk=attrs['_rows'])
        _CACHE[sink] = (receipt, identity, dict(policy, reused_sealed_path=str(path), ledger_copy_bytes=0))


def reconcile_all(sinks, *, member, lifecycle, legacy, progress=None):
    result = {}
    for name, expected in (('member',member), ('lifecycle',lifecycle), ('legacy',legacy)):
        sink = getattr(sinks, name)
        if sink not in _CACHE:
            receipt = sink.close()
            digest, identity, policy = scan(sink.path, expected, receipt['bytes'], receipt['sha256'],
                                            progress, name)
            if expected != sink.rows_written:
                raise ValueError('independent ledger row count differs from writer count')
            receipt.update(reconciled_against_counter=expected, rows_read_back_from_disk=expected)
            _CACHE[sink] = (receipt, identity, policy)
        receipt, identity, policy = _CACHE[sink]
        if (not sink._closed or not sink._handle.closed or file_identity(sink.path) != identity
                or receipt['path'] != str(sink.path) or receipt['row_count'] != expected
                or receipt['rows_read_back_from_disk'] != expected
                or receipt['reconciled_against_counter'] != expected
                or expected != sink.rows_written or receipt['bytes'] != sink._bytes
                or receipt['sha256'] != sink._digest.hexdigest()):
            raise ValueError('sealed ledger verification cannot be reused')
        result[sink.ledger] = dict(receipt)
    return result


def execution_receipt(sinks):
    return {name:dict(_CACHE[getattr(sinks,name)][2]) for name in ('member','lifecycle','legacy')}
