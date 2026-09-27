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


def _materializer(connection, parts, append_path, destination, prefix_sha, placeholder, cpu):
    pending_path = str(destination) + '.assembling'
    try:
        os.sched_setaffinity(0, {cpu})
        if os.sched_getaffinity(0) != {cpu}:
            raise ValueError('ledger I/O CPU readback differs')
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
    except BaseException:
        try:
            connection.send(('error', traceback.format_exc()))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


class _Materializer:
    def __init__(self, parts, append_path, destination, prefix_sha, cpu):
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        original = os.stat(destination)
        if original.st_size != 0:
            raise ValueError('materialization requires an empty fresh-generation placeholder')
        self.process = context.Process(target=_materializer, args=(child, parts, str(append_path),
            str(destination), prefix_sha, (original.st_dev, original.st_ino, 0), cpu),
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

    def healthy(self):
        if self.connection.poll():
            status, value = self.connection.recv()
            raise RuntimeError('ledger materializer stopped: ' + str(value))
        if not self.process.is_alive():
            raise RuntimeError('ledger materializer exited before final receipt')

    def finish(self, value):
        self.healthy()
        self.connection.send(('finish', value))
        try:
            status, result = self.connection.recv()
        except (EOFError, OSError) as error:
            raise RuntimeError('ledger materializer disconnected') from error
        if status != 'complete':
            raise RuntimeError('ledger materializer failed: ' + str(result))
        self.process.join(timeout=5)
        if self.process.is_alive() or self.process.exitcode != 0:
            raise RuntimeError('ledger materializer did not finish cleanly')
        self.connection.close()
        return result

    def close(self):
        if self.process.is_alive():
            try:
                self.connection.send(('stop', None))
            except (EOFError, OSError):
                pass
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
        self.connection.close()


def restore_prefixes(saved, sinks):
    items = [(name, getattr(sinks, name)) for name in ('member', 'lifecycle', 'legacy')]
    # These are required checkpoint-byte reads, never scientific replay.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix='ledger-verify') as pool:
        verified = {name: pool.submit(_verified_digest, saved[name]) for name, _ in items}
        states = {name: future.result() for name, future in verified.items()}
    cpu = min(os.sched_getaffinity(0))
    try:
        for name, sink in items:
            parts, digest = states[name]
            sink._handle.close()
            append_path = sink.path.with_suffix('.append.jsonl')
            sink.__dict__.update(saved[name]['attributes'])
            sink._handle = append_path.open('xb')
            sink._closed = False
            sink._digest = digest
            sink._frankie_prefixes = parts
            sink._frankie_append_path = str(append_path)
            sink._frankie_prefix_bytes = sink._bytes
            sink.__class__ = SegmentedRowSink
            _jobs[sink] = _Materializer(parts, append_path, sink.path, digest.hexdigest(), cpu)
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
