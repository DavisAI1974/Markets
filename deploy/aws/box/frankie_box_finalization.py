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
HELPERS = 14                       # ledger readers at most (the Sept-29 policy: 14 readers on 14 distinct cores)
_CACHE = weakref.WeakKeyDictionary()

# Function-level identity (stacks pass, 2026-10-07 night; the eac32a0 pattern of frankie_box_native_checkpoint): what a
# saved native full state depends on in THIS file is how a closed ledger is identified on disk, how its blocks are
# counted, how a closed sink is rebuilt from the saved descriptor and how a sealed verification is reused or receipted.
# scan() (the independent disk read: every byte hashed in file order, rows/bytes/sha256 checked against the evidence,
# refusal on any difference) computes no value a saved state carries, and its CPU placement and pool size may change
# without refusing a saved checkpoint; CHUNK_BYTES / PREFETCH / HELPERS are its read policy only.
NATIVE_VALUE_CODE = ('file_identity', '_block', 'restore_closed', 'reconcile_all', 'execution_receipt')
# Earlier whole-file bindings (finalization_sha256 = sha256 of the whole file, frankie_box_native_checkpoint V2 runtime)
# and the native code identity those exact bytes had: a saved runtime naming one of these is accepted while the named
# definitions are unchanged now (accepts_whole_file). 15164b45 = the file at 002cf94..c9bf631..2f39ddc (a2's ROOT).
WHOLE_FILE_PREDECESSORS = {
    '15164b4521f1bacbdf678354780fe24ca75f0aab4030b00b6b7815411054dc34': '3ee8150e940c023f87568d72577308630b84158e18adc0626b8d990fab53ecd7',
}


def native_code_identity():
    """The native code identity of this file's NATIVE_VALUE_CODE (frankie_box_bedrock.code_identity: each definition
    as its syntax tree without positions; a comment, blank line or move is accepted, a changed definition refuses)."""
    from frankie_box_bedrock import code_identity
    return code_identity(__file__, NATIVE_VALUE_CODE)


def accepts_whole_file(saved_sha256):
    """Why a saved whole-file finalization_sha256 is accepted, or None (refused). 'whole_file_unchanged': this file's
    bytes are exactly those; 'whole_file_<sha8>_code_unchanged': a known earlier version whose NATIVE_VALUE_CODE equals
    the current definitions (WHOLE_FILE_PREDECESSORS). Anything else refuses."""
    if not isinstance(saved_sha256, str):
        return None
    if hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest() == saved_sha256:
        return 'whole_file_unchanged'
    expected = WHOLE_FILE_PREDECESSORS.get(saved_sha256)
    if expected and native_code_identity()['sha256'] == expected:
        return 'whole_file_%s_code_unchanged' % saved_sha256[:8]
    return None


def _lane():
    """The booked lane (FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS as listed; the calling thread may already be pinned to
    one CPU, so its own affinity is not the lane), else the earlier fixed policy CPUs 0-15."""
    for name in ('FRANKIE_LANE_CPUS', 'FRANKIE_BOOKED_CPUS'):
        listed = set()
        try:
            for part in (os.environ.get(name) or '').split(','):
                part = part.strip()
                if part:
                    low, _, high = part.partition('-')
                    listed.update(range(int(low), int(high or low) + 1))
        except ValueError:
            continue
        if listed:
            return sorted(listed), name
    return list(range(16)), 'no booked lane in the environment: the earlier fixed policy CPUs 0-15'


def placement():
    """(reserved cpu, coordinator cpu, [helper cpus], basis). The lane in physical-core order (frankie_box_lane_pin.
    core_order: one thread per core first, then siblings); reserved = the first, coordinator = the second, helpers =
    the next HELPERS. On a lane 0-31 or 0-15 of the 16-core box this is the earlier policy exactly (0, 1, 2-15)."""
    lane, source = _lane()
    try:
        try:
            import frankie_box_lane_pin as LP
        except ImportError:
            from deploy.aws.box import frankie_box_lane_pin as LP
        order, basis = LP.core_order(lane)
    except Exception as error:  # noqa: BLE001 - placement never stops the verification
        order, basis = lane, 'lane order (pin helper unavailable: %s)' % type(error).__name__
    if len(order) < 2:
        order = list(order) * 2 if order else [0, 0]
    helpers = list(order[2:2 + HELPERS]) or [order[1]]
    return order[0], order[1], helpers, '%s; %s' % (source, basis)


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
    # Box policy from the booked lane (stacks pass; was the fixed CPUs 0-15 whatever the booking): the first CPU of the
    # lane's physical-core order reserved, the second joins the ordered bytes, up to HELPERS more read (placement()).
    reserved, coordinator, helper_cpus, basis = placement()
    assignments, helpers, lock = deque(helper_cpus), [], threading.Lock()
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
    os.sched_setaffinity(owner, {coordinator})
    try:
        if os.sched_getaffinity(owner) != {coordinator}:
            raise ValueError('ledger coordinator affinity readback differs')
        fd = os.open(safe_path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size,
                opened.st_mtime_ns, opened.st_ctime_ns) != before:
            raise ValueError('ledger changed while opening')
        width_helpers = len(helper_cpus)
        with ThreadPoolExecutor(max_workers=width_helpers, initializer=initialize,
                                thread_name_prefix='ledger-read') as pool:
            barrier = threading.Barrier(width_helpers, timeout=30)
            starts = [pool.submit(barrier.wait) for _ in range(width_helpers)]
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
    policy = dict(schema='FRANKIE_LEDGER_VERIFICATION_V1', coordinator_cpu=coordinator,
                  reserved_cpu=reserved, helpers=sorted(helpers,key=lambda x:x['cpu']), placement_basis=basis,
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
