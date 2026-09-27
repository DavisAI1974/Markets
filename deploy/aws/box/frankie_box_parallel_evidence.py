"""Parallel exact-ledger encoding around the unchanged native producers.

Two encoders execute the pinned RowSink.write against an in-memory capture.
ROOT commits the returned bytes and accounting in original order. Rows are frozen
at submission, transported in bounded batches, and drained at every state barrier.
"""
from collections import deque
from contextlib import contextmanager, ExitStack
import hashlib
import io
import multiprocessing
from multiprocessing import shared_memory
import os
from pathlib import Path
import time
import traceback

import cloudpickle
from frankie_box_native_parallel import ParallelSections
from frankie_box_prepare_trading_day import save_new

NAMES = ('member', 'lifecycle', 'legacy')
BATCH_ROWS = 32
BATCH_BYTES = 1 << 20  # Flush threshold, never a row or scientific-output cap.


def bind_transport_policy(driver, attribute, policy, predecessor):
    previous = getattr(driver, attribute, None)
    if previous is not None and previous != policy:
        if (previous != predecessor or not driver.checkpointer.parent_checkpoint
                or getattr(driver, '_frankie_reconstruction_checkpoint', None) is not None):
            raise ValueError('saved transport policy requires its verified full-state predecessor')
        driver.adapter.assert_groups_closed()
        history = getattr(driver, '_frankie_transport_transitions', [])
        history.append(dict(attribute=attribute, previous=previous, current=policy,
            completed_mbo_records=driver.counters.records_seen,
            parent_checkpoint=driver.checkpointer.parent_checkpoint))
        driver._frankie_transport_transitions = history
    setattr(driver, attribute, policy)


def pin_threads(pid, cpu):
    for entry in (Path('/proc') / str(pid) / 'task').iterdir():
        os.sched_setaffinity(int(entry.name), {cpu})
    if any(os.sched_getaffinity(int(entry.name)) != {cpu}
           for entry in (Path('/proc') / str(pid) / 'task').iterdir()):
        raise ValueError('native CPU affinity readback differs')


def core_plan():
    seen, cores = set(), []
    for cpu in sorted(os.sched_getaffinity(0)):
        base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
        key = (int((base / 'physical_package_id').read_text()),
               int((base / 'core_id').read_text()))
        if key not in seen:
            seen.add(key)
            cores.append(dict(cpu=cpu, package=key[0], core=key[1]))
    if len(cores) < 8:
        raise ValueError('six native/evidence cores, a book core and a system core required')
    roles = ['ROOT', 'queue', 'replenishment', 'census', 'encoder-1', 'encoder-2']
    roles += ['book-' + str(index + 1) for index in range(len(cores)-7)]
    return dict(zip(roles, cores[1:]))


class _Capture:
    def __init__(self):
        self.encoded = None

    def write(self, encoded):
        if self.encoded is not None:
            raise ValueError('pinned row sink emitted multiple writes')
        self.encoded = encoded

    def update(self, encoded):
        # ROOT hashes the same bytes when it commits them to the retained ledger.
        pass


def _encoder(connection, producers, cpu):
    shared = None
    try:
        pin_threads(os.getpid(), cpu)
        from frankie_box_bedrock import load_producers
        load_producers(producers)
        from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import RowSink
        connection.send_bytes(cloudpickle.dumps(('ok', dict(pid=os.getpid(), cpu=cpu))))
        while True:
            message = connection.recv_bytes()
            if not message:
                break
            stream, values = io.BytesIO(message), []
            while stream.tell() < len(message):
                item = cloudpickle.load(stream)
                if item[0] == 'frozen-member':
                    _, ledger, ordinal = item
                    row = cloudpickle.load(stream)
                else:
                    tag, ledger, ordinal, row = item
                    if tag != 'row':
                        raise ValueError('unknown exact evidence row envelope')
                capture = _Capture()
                sink = object.__new__(RowSink)
                sink.ledger = ledger
                sink._handle = sink._digest = capture
                sink._closed = False
                sink._rows, sink._bytes = ordinal - 1, 0
                sink._rows_by_section, sink._bytes_by_section = {}, {}
                sink._key_bytes, sink._key_sampled_rows = {}, 0
                started = time.perf_counter()
                # Original formatting and global ledger sample ordinal, per row.
                RowSink.write(sink, row)
                elapsed = time.perf_counter() - started
                if capture.encoded is None or sink._rows != ordinal:
                    raise ValueError('pinned row sink capture differs')
                values.append((ledger, ordinal, capture.encoded, sink._rows_by_section,
                    sink._bytes_by_section, sink._key_bytes, sink._key_sampled_rows, elapsed))
            required = sum(len(value[2]) for value in values)
            if shared is None or shared.size < required:
                if shared is not None:
                    shared.close()
                    shared.unlink()
                capacity = max(1 << 20, 1 << max(0, required-1).bit_length())
                shared = shared_memory.SharedMemory(create=True, size=capacity)
            metadata, offset = [], 0
            for ledger, ordinal, encoded, rows, widths, keys, sampled, elapsed in values:
                width = len(encoded)
                shared.buf[offset:offset+width] = encoded
                metadata.append((ledger, ordinal, offset, width, rows, widths, keys, sampled, elapsed))
                offset += width
            values = None
            # Receiving the next batch acknowledges that ROOT finished these
            # views. This slot is not reused while the current batch is pending.
            connection.send_bytes(cloudpickle.dumps(('ok', dict(
                schema='FRANKIE_ENCODED_BATCH_SHM_V1', name=shared.name,
                bytes=required, values=metadata)), protocol=5))
    except BaseException:
        try:
            connection.send_bytes(cloudpickle.dumps(('error', traceback.format_exc()), protocol=5))
        except (EOFError, OSError):
            pass
    finally:
        if shared is not None:
            shared.close()
            shared.unlink()
        connection.close()


class _Encoder:
    def __init__(self, producers, cpu):
        self.shared = None
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_encoder, args=(child, str(producers), cpu),
                                       name='frankie-evidence-encoder', daemon=True)
        self.pending = False
        try:
            self.process.start()
            child.close()
            self.identity = self.receive()
        except BaseException:
            child.close()
            self.close()
            raise

    def receive(self):
        try:
            status, value = cloudpickle.loads(self.connection.recv_bytes())
        except (EOFError, OSError) as error:
            raise RuntimeError('evidence encoder disconnected') from error
        self.pending = False
        if status != 'ok':
            raise RuntimeError('evidence encoder failed:\n' + value)
        return value

    def encoded_batch(self, value):
        if value.get('schema') != 'FRANKIE_ENCODED_BATCH_SHM_V1':
            raise ValueError('exact shared evidence batch required')
        if self.shared is None or self.shared.name != value['name']:
            if self.shared is not None:
                self.shared.close()
            # The producer owns unlink; attaching must not register another owner.
            self.shared = shared_memory.SharedMemory(name=value['name'], track=False)
        if type(value['bytes']) is not int or not 0 <= value['bytes'] <= self.shared.size:
            raise ValueError('shared evidence extent differs')
        return value['values']

    def close(self):
        if self.process.is_alive():
            if not self.pending:
                try:
                    self.connection.send_bytes(b'')
                except (EOFError, OSError):
                    pass
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        self.connection.close()
        if self.shared is not None:
            self.shared.close()
            self.shared = None


class _Sink:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def write(self, row):
        self.owner.write(self.name, row)

    def __getattr__(self, name):
        # Native consumers that inspect counters/receipts see all submitted rows.
        self.owner.drain()
        return getattr(self.owner.originals[self.name], name)


class ParallelEvidence:
    def __init__(self, driver, producers, plan):
        self.driver, self.sinks = driver, driver.sinks
        self.originals = {name:getattr(self.sinks, name) for name in NAMES}
        self.proxies = {name:_Sink(self, name) for name in NAMES}
        self.ordinals = {name:sink._rows for name,sink in self.originals.items()}
        self.workers, self.pending = [], deque()
        self.buffer, self.buffer_rows = io.BytesIO(), []
        self.active = False
        self.bridge = None
        predecessor = dict(schema='FRANKIE_PARALLEL_EVIDENCE_V2', encoders=2,
            maximum_pending_batches=2, batch_rows=BATCH_ROWS, batch_flush_bytes=BATCH_BYTES,
            row_freeze='independent protocol-5 pickle at write; no cross-row memo',
            writer='ROOT', serializer='pinned RowSink.write',
            checkpoint_barrier='flush batches then materialize original sinks',
            helper_sha256='98f7450ed0669802bd12643831d44b259bdefd2654ef638496045390990a71ad')
        policy = dict(schema='FRANKIE_PARALLEL_EVIDENCE_V3', encoders=2,
            maximum_pending_batches=2, batch_rows=BATCH_ROWS, batch_flush_bytes=BATCH_BYTES,
            row_freeze='one immutable member pickle inside pinned note_member_row; independent other rows',
            output_transport='producer-owned shared bytes; ROOT ordered write/hash; reuse after commit',
            writer='ROOT', serializer='pinned RowSink.write',
            checkpoint_barrier='flush batches then materialize original sinks',
            helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        bind_transport_policy(driver, '_frankie_evidence_policy', policy, predecessor)
        if not hasattr(driver, '_frankie_evidence_metrics'):
            driver._frankie_evidence_metrics = dict(rows=0, encode_seconds=0.0,
                submit_seconds=0.0, receive_seconds=0.0, commit_seconds=0.0)
        self.metrics = driver._frankie_evidence_metrics
        self.metrics.setdefault('batches', 0)
        self.metrics.setdefault('transport_bytes', 0)
        self.metrics.setdefault('shared_output_bytes', 0)
        self.metrics.setdefault('reused_member_freezes', 0)
        try:
            for role in ('encoder-1', 'encoder-2'):
                self.workers.append(_Encoder(producers, plan[role]['cpu']))
        except BaseException:
            self.close()
            raise
        self.install()
        self.active = True

    def install(self):
        for name, proxy in self.proxies.items():
            setattr(self.sinks, name, proxy)

    def originals_only(self):
        for name, sink in self.originals.items():
            setattr(self.sinks, name, sink)

    def write(self, name, row):
        sink = self.originals[name]
        if sink._closed:
            raise ValueError('closed exact ledger received a row')
        self.ordinals[name] += 1
        ordinal = self.ordinals[name]
        started = time.perf_counter()
        # Freeze now, before any caller mutation. Each row has its own memo.
        frozen = self.bridge.take(row) if name == 'member' and self.bridge is not None else None
        if frozen is None:
            cloudpickle.dump(('row', sink.ledger, ordinal, row), self.buffer, protocol=5)
        else:
            cloudpickle.dump(('frozen-member', sink.ledger, ordinal), self.buffer, protocol=5)
            self.buffer.write(frozen)
            self.metrics['reused_member_freezes'] += 1
        self.buffer_rows.append((name, ordinal))
        self.metrics['submit_seconds'] += time.perf_counter() - started
        if len(self.buffer_rows) >= BATCH_ROWS or self.buffer.tell() >= BATCH_BYTES:
            self.flush_batch()

    def flush_batch(self):
        if not self.buffer_rows:
            return
        if len(self.pending) == len(self.workers):
            self.commit_one()
        worker = next(worker for worker in self.workers if not worker.pending)
        started = time.perf_counter()
        payload = self.buffer.getvalue()
        worker.connection.send_bytes(payload)
        worker.pending = True
        self.pending.append((self.buffer_rows, worker))
        self.metrics['batches'] += 1
        self.metrics['transport_bytes'] += len(payload)
        self.metrics['submit_seconds'] += time.perf_counter() - started
        self.buffer, self.buffer_rows = io.BytesIO(), []

    def commit_one(self):
        offered, worker = self.pending[0]
        started = time.perf_counter()
        batch = worker.receive()
        values = worker.encoded_batch(batch)
        self.metrics['receive_seconds'] += time.perf_counter() - started
        if len(values) != len(offered):
            raise ValueError('encoded evidence batch row count differs')
        cursor = 0
        for (name, ordinal), value in zip(offered, values):
            ledger, actual_ordinal, offset, width, rows, widths, keys, sampled, elapsed = value
            if offset != cursor or type(width) is not int or width < 0 or offset+width > batch['bytes']:
                raise ValueError('shared evidence row extent differs')
            cursor += width
            sink = self.originals[name]
            if (ledger != sink.ledger or actual_ordinal != ordinal or sink._rows + 1 != ordinal
                    or sum(rows.values()) != 1 or sum(widths.values()) != width):
                raise ValueError('encoded evidence order or byte accounting differs')
            started = time.perf_counter()
            encoded = worker.shared.buf[offset:offset+width]
            try:
                sink._handle.write(encoded)
                sink._digest.update(encoded)
            finally:
                encoded.release()
            sink._rows += 1
            sink._bytes += width
            for attr, counts in (('_rows_by_section', rows), ('_bytes_by_section', widths), ('_key_bytes', keys)):
                target = getattr(sink, attr)
                for key, count in counts.items():
                    target[key] = target.get(key, 0) + count
            sink._key_sampled_rows += sampled
            self.metrics['rows'] += 1
            self.metrics['encode_seconds'] += elapsed
            self.metrics['commit_seconds'] += time.perf_counter() - started
        if cursor != batch['bytes']:
            raise ValueError('shared evidence batch has unclaimed bytes')
        self.metrics['shared_output_bytes'] += cursor
        self.pending.popleft()

    def drain(self):
        self.flush_batch()
        while self.pending:
            self.commit_one()

    @contextmanager
    def materialized(self):
        self.drain()
        self.originals_only()
        try:
            yield
        finally:
            if self.active:
                self.install()

    def finish(self):
        self.drain()
        self.active = False
        self.originals_only()
        self.close()

    def close(self):
        for worker in self.workers:
            worker.close()
        self.workers.clear()
        self.active = False
        self.originals_only()


class FrozenMemberBridge:
    """Share one freeze only inside the pinned, mutation-free member call."""
    def __init__(self, run, census, encoding):
        if 'note_member_row' in vars(run) or run.sinks is not encoding.sinks:
            raise ValueError('unwrapped pinned member method and identical sinks required')
        self.run, self.census, self.encoding = run, census, encoding
        self.original, self.context, self.active = run.note_member_row, None, True
        owner = self
        def note_member_row(count=1, *, row=None):
            if owner.context is not None:
                raise RuntimeError('member freeze scope must not nest')
            owner.context = dict(row=row, frozen=None, used=False)
            try:
                result = owner.original(count, row=row)
                if row is not None and not owner.context['used']:
                    raise ValueError('pinned member census/evidence sequence differs')
                return result
            finally:
                owner.context = None
        self.wrapper = note_member_row
        run.note_member_row = self.wrapper
        census.bridge = encoding.bridge = self

    def offer(self, row, frozen):
        if self.context is None:
            return
        if row is not self.context['row'] or self.context['frozen'] is not None:
            raise ValueError('member freeze source differs or was repeated')
        self.context['frozen'] = frozen

    def take(self, row):
        if self.context is None:
            return None
        value = self.context
        if row is not value['row'] or value['frozen'] is None or value['used']:
            raise ValueError('member evidence does not match its scoped census freeze')
        value['used'] = True
        return value['frozen']

    @contextmanager
    def materialized(self):
        if self.context is not None:
            raise RuntimeError('checkpoint cannot bisect a member freeze scope')
        del self.run.note_member_row
        try:
            yield
        finally:
            if self.active:
                self.run.note_member_row = self.wrapper

    def close(self):
        if self.active:
            del self.run.note_member_row
            self.census.bridge = self.encoding.bridge = None
            self.active = False


class RuntimeSections(ParallelSections):
    def __init__(self, driver, producers):
        super().__init__(driver, producers)
        self.plan = core_plan()
        self.encoding = None
        self.census = None
        self.books = None
        self.member_bridge = None

    def start(self):
        super().start()
        try:
            for kind, branch in self.branches.items():
                pin_threads(branch.process.pid, self.plan[kind]['cpu'])
            from frankie_box_native_auxiliary import ParallelCensus, ParallelBook
            import frankie_box_native_auxiliary as auxiliary
            book_roles = [role for role in self.plan if role.startswith('book-')]
            if not book_roles:
                raise ValueError('at least one full-book worker core required')
            predecessor = dict(schema='FRANKIE_NATIVE_AUXILIARY_V2',
                book_workers=len(book_roles), census_workers=1,
                book_rule='persistent fixed partitions; ordered snapshot deltas; pinned math; join before next event',
                census_rule='immutable ordered batches; drain and materialize at checkpoint',
                helper_sha256='5cc07cb1289f0b89facf5a93b7287a6f4fed2be6f785eee79329e0a8e09f1343')
            policy = dict(schema='FRANKIE_NATIVE_AUXILIARY_V3',
                book_workers=len(book_roles), census_workers=1,
                book_rule='persistent fixed partitions; ordered snapshot deltas; pinned math; join before next event',
                census_rule='scoped shared member freeze; ordered batches; drain and materialize at checkpoint',
                helper_sha256=hashlib.sha256(Path(auxiliary.__file__).read_bytes()).hexdigest())
            bind_transport_policy(self.driver, '_frankie_auxiliary_policy', policy, predecessor)
            if not hasattr(self.driver, '_frankie_auxiliary_metrics'):
                self.driver._frankie_auxiliary_metrics = dict(census={}, books={})
            metrics = self.driver._frankie_auxiliary_metrics
            self.census = ParallelCensus(self.driver,self.producers,self.plan['census']['cpu'],metrics['census'])
            self.books = ParallelBook(self.producers,[self.plan[role]['cpu'] for role in book_roles],metrics['books'])
            from frankie_box_segmented_ledger import io_workers
            storage_workers = io_workers(self.driver.sinks)
            self.encoding = ParallelEvidence(self.driver, self.producers, self.plan)
            self.member_bridge = FrozenMemberBridge(self.driver.run, self.census, self.encoding)
            self.driver.checkpointer.encoding = self.encoding
            pin_threads(os.getpid(), self.plan['ROOT']['cpu'])
            workers = {kind:dict(pid=branch.process.pid, **self.plan[kind])
                       for kind,branch in self.branches.items()}
            for role,worker in zip(('encoder-1','encoder-2'), self.encoding.workers):
                workers[role] = dict(pid=worker.process.pid, **self.plan[role])
            workers['census'] = dict(pid=self.census.worker.process.pid, **self.plan['census'])
            for role,worker in zip(book_roles,self.books.workers):
                workers[role] = dict(pid=worker.process.pid, **self.plan[role])
            workers['ROOT'] = dict(pid=os.getpid(), **self.plan['ROOT'])
            receipt = dict(schema='FRANKIE_RUNTIME_WORKERS_V1', at=time.time(), workers=workers,
                base_calculation_processes=3, auxiliary_calculation_processes=1+len(book_roles),
                encoding_processes=2, ledger_io_processes=len(storage_workers),
                total_processes=len(workers)+len(storage_workers), ledger_io_workers=storage_workers,
                auxiliary_policy=policy,
                completed_mbo_records=self.driver.counters.records_seen,
                exact_evidence_policy=self.driver._frankie_evidence_policy,
                transport_transitions=getattr(self.driver, '_frankie_transport_transitions', []),
                numerical_thread_counts_changed=False, cpu_affinity_readback_verified=True)
            save_new(self.driver.checkpointer.checkpoint_dir.parent / 'runtime-workers-receipt.json', receipt)
        except BaseException:
            self.close()
            raise
        return self

    @contextmanager
    def materialized(self):
        with ExitStack() as stack:
            if self.member_bridge is not None:
                stack.enter_context(self.member_bridge.materialized())
            if self.books is not None:
                stack.enter_context(self.books.materialized())
            if self.census is not None:
                stack.enter_context(self.census.materialized())
            stack.enter_context(super().materialized())
            yield

    def finish(self):
        if self.member_bridge is not None:
            self.member_bridge.close()
            self.member_bridge = None
        if self.encoding is not None:
            self.encoding.finish()
            self.driver.checkpointer.encoding = None
        if self.census is not None:
            self.census.finish()
            self.census = None
        if self.books is not None:
            self.books.close()
            self.books = None
        super().finish()

    def close(self):
        if self.member_bridge is not None:
            self.member_bridge.close()
            self.member_bridge = None
        if self.encoding is not None:
            self.encoding.close()
            self.driver.checkpointer.encoding = None
        if self.census is not None:
            self.census.close()
            self.census = None
        if self.books is not None:
            self.books.close()
            self.books = None
        super().close()
