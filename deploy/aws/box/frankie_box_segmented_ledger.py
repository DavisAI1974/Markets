"""Frozen ledger prefixes, fresh append segments, and exact background materialization.

Checkpoint state names every retained segment and its committed byte extent.
Restore hashes the ordered bytes without rewriting old prefixes. Independent I/O
workers assemble the ordinary final JSONL files; no scientific computation runs
in these workers, and no prior file or post-checkpoint tail is modified.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import multiprocessing
import os
from pathlib import Path
import time
import traceback
import weakref

from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import RowSink
from frankie_box_prepare_trading_day import safe_path, sync_directory

CHUNK_BYTES = 8 << 20
PREFETCH = 8
READ_WORKERS = 4
STORAGE_SCHEMA = 'FRANKIE_LEDGER_SEGMENTS_V1'
_PRIVATE = {'_frankie_prefixes', '_frankie_append_path', '_frankie_prefix_bytes'}
_jobs = weakref.WeakKeyDictionary()
# A lost materializer is started again from the same frozen parts and append file; at most this many times per ledger
# beyond the CPUs it can use (each loss leaves its CPU out). Integrity refusals (ValueError) are never redone.
MAX_REDOS = 3

# Recorded, never compared (Greg, 2026-10-09): this identity is written beside a saved checkpoint as
# ledger_storage_code; frankie_box_native_checkpoint accepts a save on NATIVE_STATE_FORMAT, which is bumped only
# when the storage FORMAT below changes.
# What a saved checkpoint's ledger storage depends on (frankie_box_native_checkpoint.runtime_identity): the segment
# schema, the verified extents, the byte assembly and its hash checks, the checkpoint attributes and the materialized
# sink. The read pools (_read_at, ordered_chunks: every byte they return is hashed against the checkpoint), the
# materializer processes, their CPU placement and redo (_materializer, _Materializer, _Placement, _io_cpus,
# restore_prefixes' scheduling) may change without refusing a saved checkpoint.
NATIVE_VALUE_CODE = ('STORAGE_SCHEMA', '_PRIVATE', 'frozen_parts', '_verified_digest', '_assemble', '_resume_sink',
                     'checkpoint_storage', 'checkpoint_attributes', 'materialize', 'materialize_all',
                     'SegmentedRowSink')


def native_code_identity():
    from frankie_box_bedrock import code_identity
    return code_identity(__file__, NATIVE_VALUE_CODE)


def _read_at(fd, offset, size):
    pieces = []
    while size:
        value = os.pread(fd, size, offset)
        if not value:
            raise ValueError('frozen ledger segment is shorter than its checkpoint')
        pieces.append(value)
        offset += len(value)
        size -= len(value)
    return pieces[0] if len(pieces) == 1 else b''.join(pieces)


def ordered_chunks(parts):
    """Bounded parallel reads; the consumer still hashes/writes in byte order."""
    with ThreadPoolExecutor(max_workers=READ_WORKERS, thread_name_prefix='ledger-read') as pool:
        for part in parts:
            path, size = safe_path(part['path']), part['bytes']
            if type(size) is not int or size < 0 or path.stat().st_size < size:
                raise ValueError('frozen ledger extent is invalid')
            fd = os.open(path, os.O_RDONLY)
            pending, offset = deque(), 0
            try:
                while offset < size or pending:
                    while offset < size and len(pending) < PREFETCH:
                        width = min(CHUNK_BYTES, size-offset)
                        pending.append(pool.submit(_read_at, fd, offset, width))
                        offset += width
                    if pending:
                        yield pending.popleft().result()
            finally:
                # Finish readers before closing their shared descriptor.
                failure = None
                try:
                    while pending:
                        try:
                            pending.popleft().result()
                        except BaseException as error:
                            if failure is None:
                                failure = error
                finally:
                    os.close(fd)
                if failure is not None:
                    raise failure


def frozen_parts(entry):
    if 'storage_schema' in entry:
        if entry['storage_schema'] != STORAGE_SCHEMA or type(entry.get('segments')) is not list:
            raise ValueError('unknown ledger segment storage')
        parts = [dict(part) for part in entry['segments']]
    else:
        parts = [dict(path=entry['path'], bytes=entry['attributes']['_bytes'])]
    if any(set(part) != {'path', 'bytes'} or type(part['path']) is not str
           or type(part['bytes']) is not int or part['bytes'] < 0 for part in parts):
        raise ValueError('explicit ordered ledger segment extents required')
    if sum(part['bytes'] for part in parts) != entry['attributes']['_bytes']:
        raise ValueError('frozen ledger extents do not cover its logical bytes')
    return parts


def _verified_digest(entry):
    parts, digest = frozen_parts(entry), hashlib.sha256()
    for chunk in ordered_chunks(parts):
        digest.update(chunk)
    if digest.hexdigest() != entry['sha256']:
        raise ValueError('frozen ledger prefix hash differs')
    return parts, digest


def _materializer(connection, parts, append_path, destination, prefix_sha, placeholder, cpu, pending_path):
    """One ledger I/O worker: pinned to its CPU, then the byte assembly (_assemble). Any failure is reported with its
    kind; an integrity refusal (ValueError) is never redone by the coordinator."""
    try:
        os.sched_setaffinity(0, {cpu})
        if os.sched_getaffinity(0) != {cpu}:
            raise OSError('ledger I/O CPU readback differs')
        _assemble(connection, parts, append_path, destination, prefix_sha, placeholder, cpu, pending_path)
    except BaseException as error:
        try:
            connection.send(('error', dict(kind=type(error).__name__, integrity=isinstance(error, ValueError),
                                           traceback=traceback.format_exc())))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


def _assemble(connection, parts, append_path, destination, prefix_sha, placeholder, cpu, pending_path):
    """The frozen prefix parts then the append segment, in byte order, into pending_path; both hashes checked against
    the coordinator's; published over our empty placeholder only."""
    digest, prefix_bytes, appended = hashlib.sha256(), 0, 0
    with open(pending_path, 'xb') as output:
        connection.send(('ready', dict(pid=os.getpid(), cpu=cpu, pending_path=pending_path)))
        for chunk in ordered_chunks(parts):
            output.write(chunk)
            digest.update(chunk)
            prefix_bytes += len(chunk)
        if digest.hexdigest() != prefix_sha:
            raise ValueError('materialized prefix hash differs')
        final = None
        with open(append_path, 'rb') as source:
            while True:
                if connection.poll():
                    command, value = connection.recv()
                    if command == 'stop':
                        return
                    if command != 'finish' or final is not None:
                        raise ValueError('unexpected ledger materialization command')
                    final = value
                if final is not None:
                    remaining = final['append_bytes'] - appended
                    if remaining < 0:
                        raise ValueError('materializer passed the frozen append extent')
                    if remaining == 0:
                        break
                    width = min(CHUNK_BYTES, remaining)
                else:
                    width = CHUNK_BYTES
                chunk = source.read(width)
                if chunk:
                    output.write(chunk)
                    digest.update(chunk)
                    appended += len(chunk)
                elif final is not None:
                    raise ValueError('frozen append segment is shorter than its receipt')
                else:
                    connection.poll(0.1)
            if os.fstat(source.fileno()).st_size != final['append_bytes']:
                raise ValueError('append segment changed across final materialization')
        if (prefix_bytes + appended != final['bytes']
                or digest.hexdigest() != final['sha256']):
            raise ValueError('whole materialized ledger bytes/hash differ')
        output.flush()
        os.fsync(output.fileno())
    current = os.stat(destination)
    if (current.st_dev, current.st_ino, current.st_size) != tuple(placeholder):
        raise ValueError('refusing to replace anything except our empty ledger placeholder')
    os.replace(pending_path, destination)
    sync_directory(Path(destination).parent)
    connection.send(('complete', dict(schema=STORAGE_SCHEMA, path=destination,
        bytes=prefix_bytes+appended, sha256=digest.hexdigest(), prefix_bytes=prefix_bytes,
        append_bytes=appended, pid=os.getpid(), cpu=cpu,
        phase='materialized_prefix_before_finalizer',
        original_segments_preserved=True, byte_order_verified=True)))


class _Placement:
    """The CPUs the three ledger materializers use, shared: taken in turn (three distinct CPUs when there are three),
    and a CPU whose worker was lost leaves the set (one fewer; the last CPU is kept)."""

    def __init__(self, cpus, basis):
        self.cpus, self.basis, self.turn = list(cpus), basis, 0

    def take(self):
        cpu = self.cpus[self.turn % len(self.cpus)]
        self.turn += 1
        return cpu

    def lose(self, cpu):
        if cpu in self.cpus and len(self.cpus) > 1:
            self.cpus.remove(cpu)


def _io_cpus():
    """CPUs of the native half for the ledger materializers (Greg, 2026-10-07: not all three on the one system CPU,
    never the native ROOT role's whole core): the booked CPUs the native core plan assigns no role (the system CPU)
    first, then the full-book worker CPUs from the last book role back (their results do not depend on the worker
    count). The queue, replenishment, census and encoder CPUs and both hardware threads of the ROOT core are never
    used. Without a native core plan (no readable topology) the first CPU of the affinity, as before. Placement only:
    the bytes are the same frozen parts and append file, hashed against the checkpoint either way."""
    affinity = sorted(os.sched_getaffinity(0))
    try:
        from frankie_box_parallel_evidence import _booked_cpus, core_plan
        plan = core_plan()
        booked = _booked_cpus()

        def core_of(cpu):
            base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
            return int((base / 'physical_package_id').read_text()), int((base / 'core_id').read_text())
        root_core = (plan['ROOT']['package'], plan['ROOT']['core'])
        roles = {place['cpu']: role for role, place in plan.items()}
        usable = [cpu for cpu in booked if core_of(cpu) != root_core]
        free = [cpu for cpu in usable if cpu not in roles]
        books = sorted((cpu for cpu in usable if roles.get(cpu, '').startswith('book-')),
                       key=lambda cpu: -int(roles[cpu].split('-', 1)[1]))
        cpus = free + books
        if cpus:
            return _Placement(cpus, 'native core plan: unassigned booked CPUs, then book CPUs from the last; '
                                    'ROOT core %s excluded' % (root_core,))
        why = 'no CPU outside the ROOT core'
    except Exception as error:  # noqa: BLE001 - placement only; the first CPU, as before
        why = '%s: %s' % (type(error).__name__, error)
    return _Placement([affinity[0]], 'first CPU of the affinity (no native core plan: %s)' % why)


class _Materializer:
    """One ledger's I/O worker, kept alive to the final receipt. A worker that is lost (exited, disconnected, could
    not start, or failed without an integrity refusal) is started again on another CPU of the placement from the same
    frozen parts and append file, into a new pending path (the lost one's partial file is kept); the placeholder must
    still be ours and empty. An integrity refusal (ValueError in the worker) is never redone. Every loss is recorded
    in `redone` and in the final receipt."""

    def __init__(self, parts, append_path, destination, prefix_sha, placement):
        self.parts, self.append_path, self.destination = parts, str(append_path), str(destination)
        self.prefix_sha, self.placement = prefix_sha, placement
        original = os.stat(destination)
        if original.st_size != 0:
            raise ValueError('materialization requires an empty fresh-generation placeholder')
        self.placeholder = (original.st_dev, original.st_ino, 0)
        self.redone, self.attempts = [], 0
        self.process = self.connection = None
        self.cpu, self.identity = None, None
        self._start()

    def _spawn(self, cpu):
        context = multiprocessing.get_context('spawn')
        pending = self.destination + ('.assembling' if self.attempts == 0 else '.assembling-redo-%d' % self.attempts)
        self.attempts += 1
        self.connection, child = context.Pipe()
        self.cpu = cpu
        self.process = context.Process(target=_materializer, args=(child, self.parts, self.append_path,
            self.destination, self.prefix_sha, self.placeholder, cpu, pending),
            name='frankie-ledger-materializer', daemon=True)
        try:
            self.process.start()
            child.close()
            status, self.identity = self.connection.recv()
            if status != 'ready':
                raise RuntimeError('ledger materializer could not start: ' + str(self.identity))
        except BaseException:
            child.close()
            self.close()
            raise

    def _start(self):
        for _ in range(len(self.placement.cpus) + MAX_REDOS):
            cpu = self.placement.take()
            try:
                self._spawn(cpu)
                return
            except (EOFError, OSError, RuntimeError) as error:
                self._lost(cpu, 'could not start: %s: %s' % (type(error).__name__, error))
        raise RuntimeError('no ledger materializer could start: %s' % self.redone[-3:])

    def _lost(self, cpu, why):
        self.redone.append(dict(cpu=cpu, pid=self.process.pid if self.process is not None else None,
                                why=why[-4000:], at=time.time()))
        self.placement.lose(cpu)
        if len(self.redone) > len(self.placement.cpus) + MAX_REDOS:
            raise RuntimeError('ledger materializer lost too often: %s' % self.redone[-3:])

    @staticmethod
    def _refusal(value):
        """A worker message that is an integrity refusal (never redone), as text; None when the worker was lost."""
        if isinstance(value, dict) and value.get('integrity'):
            return value.get('traceback') or str(value)
        return None

    def _redo(self, why):
        lost = self.cpu
        self.close()
        current = os.stat(self.destination)
        if (current.st_dev, current.st_ino, current.st_size) != self.placeholder:
            raise RuntimeError('ledger materializer lost after its placeholder changed: ' + why)
        self._lost(lost, why)
        self._start()

    def healthy(self):
        why = None
        if self.connection.poll():
            try:
                status, value = self.connection.recv()
            except (EOFError, OSError) as error:
                status, value = 'lost', '%s: %s' % (type(error).__name__, error)
            refusal = self._refusal(value)
            if refusal is not None:
                raise RuntimeError('ledger materializer stopped: ' + refusal)
            why = 'stopped (%s): %s' % (status, value.get('traceback') if isinstance(value, dict) else value)
        elif not self.process.is_alive():
            why = 'exited before final receipt (exit code %s)' % self.process.exitcode
        if why is not None:
            self._redo(why)

    def _published(self, value, why):
        """The lost worker published before its receipt arrived: the destination is accepted only when its whole bytes
        equal the expected size and sha256, read back here."""
        digest, size = hashlib.sha256(), 0
        with open(self.destination, 'rb') as stream:
            for chunk in iter(lambda: stream.read(CHUNK_BYTES), b''):
                digest.update(chunk)
                size += len(chunk)
        if size != value['bytes'] or digest.hexdigest() != value['sha256']:
            raise RuntimeError('ledger materializer lost after publishing bytes that differ: ' + why)
        return dict(schema=STORAGE_SCHEMA, path=self.destination, bytes=size, sha256=value['sha256'],
                    prefix_bytes=value['bytes'] - value['append_bytes'], append_bytes=value['append_bytes'],
                    pid=None, cpu=self.cpu, phase='materialized_prefix_before_finalizer',
                    original_segments_preserved=True, byte_order_verified=True,
                    verified_by_coordinator_readback=why)

    def finish(self, value):
        while True:
            self.healthy()
            try:
                self.connection.send(('finish', value))
                status, result = self.connection.recv()
            except (EOFError, OSError) as error:
                status, result = 'lost', '%s: %s' % (type(error).__name__, error)
            if status == 'complete':
                break
            refusal = self._refusal(result)
            if refusal is not None:
                raise RuntimeError('ledger materializer failed: ' + refusal)
            why = 'lost at finish (%s): %s' % (status, result.get('traceback') if isinstance(result, dict) else result)
            current = os.stat(self.destination)
            if (current.st_dev, current.st_ino, current.st_size) != self.placeholder:
                result = self._published(value, why)
                break
            self._redo(why)
        self.process.join(timeout=5)
        clean = not self.process.is_alive() and self.process.exitcode == 0
        self.close()
        result = dict(result, redone=list(self.redone), clean_exit=clean)
        return result

    def close(self):
        if self.process is not None and self.process.is_alive():
            try:
                self.connection.send(('stop', None))
            except (EOFError, OSError):
                pass
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        if self.connection is not None:
            self.connection.close()


def _resume_sink(sink, entry, parts, digest):
    """The restored sink: the checkpoint attributes, the verified prefix digest and parts, a fresh append segment."""
    sink._handle.close()
    append_path = sink.path.with_suffix('.append.jsonl')
    sink.__dict__.update(entry['attributes'])
    sink._handle = append_path.open('xb')
    sink._closed = False
    sink._digest = digest
    sink._frankie_prefixes = parts
    sink._frankie_append_path = str(append_path)
    sink._frankie_prefix_bytes = sink._bytes
    sink.__class__ = SegmentedRowSink
    return append_path


def restore_prefixes(saved, sinks):
    items = [(name, getattr(sinks, name)) for name in ('member', 'lifecycle', 'legacy')]
    # These are required checkpoint-byte reads, never scientific replay.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix='ledger-verify') as pool:
        verified = {name: pool.submit(_verified_digest, saved[name]) for name, _ in items}
        states = {name: future.result() for name, future in verified.items()}
    placement = _io_cpus()
    try:
        for name, sink in items:
            parts, digest = states[name]
            append_path = _resume_sink(sink, saved[name], parts, digest)
            _jobs[sink] = _Materializer(parts, append_path, sink.path, digest.hexdigest(), placement)
    except BaseException:
        for _, sink in items:
            job = _jobs.pop(sink, None)
            if job is not None:
                job.close()
        raise


def checkpoint_storage(sink):
    if not hasattr(sink, '_frankie_prefixes'):
        return {}
    _jobs[sink].healthy()
    return dict(storage_schema=STORAGE_SCHEMA, segments=list(sink._frankie_prefixes) + [
        dict(path=sink._frankie_append_path, bytes=sink._bytes-sink._frankie_prefix_bytes)])


def checkpoint_attributes(sink):
    return {k:v for k,v in vars(sink).items() if k not in _PRIVATE | {'_handle', '_digest', 'path'}}


def materialize(sink):
    if not hasattr(sink, '_frankie_prefixes'):
        return
    closed = sink._closed
    if not sink._handle.closed:
        sink._handle.flush()
        os.fsync(sink._handle.fileno())
        sink._handle.close()
    expected = dict(append_bytes=sink._bytes-sink._frankie_prefix_bytes,
                    bytes=sink._bytes, sha256=sink._digest.hexdigest())
    receipt = _jobs[sink].finish(expected)
    sink._frankie_ledger_transfer = receipt
    del _jobs[sink]
    for name in _PRIVATE:
        delattr(sink, name)
    sink._handle = sink.path.open('ab')
    if closed:
        sink._handle.close()


def materialize_all(sinks):
    for name in ('member', 'lifecycle', 'legacy'):
        materialize(getattr(sinks, name))


def io_workers(sinks):
    return {name:dict(_jobs[sink].identity) for name in ('member', 'lifecycle', 'legacy')
            if (sink := getattr(sinks, name)) in _jobs}


class SegmentedRowSink(RowSink):
    def receipt(self):
        materialize(self)
        return super().receipt()

    def read_back(self):
        materialize(self)
        return super().read_back()
