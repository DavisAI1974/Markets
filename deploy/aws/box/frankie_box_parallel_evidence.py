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

# Recorded, never compared (Greg, 2026-10-09): helper_code is a record in the policy (bind_transport_policy compares
# policy_meaning).
# What the exact evidence bytes and accounting depend on (the evidence transport policy's helper_code): the pinned
# RowSink.write capture and encoding, the ordered commit/hash, the sink proxies, the member freeze bridge and the
# checkpoint barriers. The processes and their CPUs (_encoder, _Encoder, pin_threads, core_plan, _booked_cpus),
# batching dispatch, RuntimeSections.start/close and the policy binding itself may change without refusing a saved
# checkpoint (a commit checks every row's ledger, ordinal and byte extent).
NATIVE_VALUE_CODE = ('_Capture', '_encode_serve', '_Sink', 'ParallelEvidence.install', 'ParallelEvidence.originals_only',
                     'ParallelEvidence.write', 'ParallelEvidence.commit_one', 'ParallelEvidence.drain',
                     'ParallelEvidence.materialized', 'ParallelEvidence.finish', 'FrozenMemberBridge',
                     'RuntimeSections.materialized', 'RuntimeSections.finish')


def native_code_identity():
    from frankie_box_bedrock import code_identity
    return code_identity(__file__, NATIVE_VALUE_CODE)


# Greg, 2026-10-09 (standing): the code version is RECORDED, NEVER COMPARED. helper_code / helper_sha256 stay in every
# policy as a record; a saved policy is compared on its meaning (the policy without them).
RECORDED_CODE = ('helper_code', 'helper_sha256')


def policy_meaning(policy):
    """A transport policy without its recorded-only code fields (a non-dict is returned as it is)."""
    if not isinstance(policy, dict):
        return policy
    return {k: v for k, v in policy.items() if k not in RECORDED_CODE}


def bind_transport_policy(driver, attribute, policy, predecessors):
    """Bind the current transport policy. A saved policy with the same meaning (it differs at most in its recorded
    helper code) is the same policy: bound, the code change recorded. A saved policy of another meaning is accepted
    only when its meaning is one of the named predecessors', on a verified full-state resume, and the transition is
    recorded."""
    previous = getattr(driver, attribute, None)
    if previous is not None and previous != policy:
        same_meaning = policy_meaning(previous) == policy_meaning(policy)
        if not same_meaning and (policy_meaning(previous) not in [policy_meaning(p) for p in predecessors]
                                 or not driver.checkpointer.parent_checkpoint
                                 or getattr(driver, '_frankie_reconstruction_checkpoint', None) is not None):
            raise ValueError('saved transport policy requires its verified full-state predecessor')
        driver.adapter.assert_groups_closed()
        history = getattr(driver, '_frankie_transport_transitions', [])
        history.append(dict(attribute=attribute, previous=previous, current=policy,
            code_recorded_only=same_meaning, completed_mbo_records=driver.counters.records_seen,
            parent_checkpoint=getattr(driver.checkpointer, 'parent_checkpoint', None)))
        driver._frankie_transport_transitions = history
    setattr(driver, attribute, policy)


def pin_threads(pid, cpu):
    for entry in (Path('/proc') / str(pid) / 'task').iterdir():
        os.sched_setaffinity(int(entry.name), {cpu})
    if any(os.sched_getaffinity(int(entry.name)) != {cpu}
           for entry in (Path('/proc') / str(pid) / 'task').iterdir()):
        raise ValueError('native CPU affinity readback differs')


def _booked_cpus():
    """The booked CPUs (16 or 32, Greg 2026-10-07: each ROOT pass gets the whole booking while it runs), never the host
    count: FRANKIE_LANE_CPUS or FRANKIE_BOOKED_CPUS (frankie_box_cores cpu_list) intersected with this process's
    affinity; the affinity alone when neither names a CPU of it."""
    affinity = set(os.sched_getaffinity(0))
    for name in ('FRANKIE_LANE_CPUS', 'FRANKIE_BOOKED_CPUS'):
        listed = set()
        try:
            for part in (os.environ.get(name) or '').split(','):
                if part.strip():
                    low, _, high = part.strip().partition('-')
                    listed.update(range(int(low), int(high or low) + 1))
        except ValueError:
            continue
        if listed & affinity:
            return sorted(listed & affinity)
    return sorted(affinity)


def core_plan():
    """One role per booked CPU after the first (the system/coordinator CPU) and after the ROOT core's second hardware
    thread (left idle: the ROOT role has a whole core). The six native/evidence roles take one CPU on each of six
    distinct physical cores, as before; every other booked CPU, the second hardware thread of a core included, is a
    full-book worker. A 16-CPU lane on 16 cores gives 15 roles (9 book) as before; a 32-CPU booking on 16 cores x 2
    threads gives 30 (24 book); the 16-CPU native half of the side-by-side ROOT (8 cores x 2) gives 14 (8 book). The book
    results do not depend on the worker count: ParallelBook places each level on a worker by a hash of (side, price)
    modulo the count (ParallelBook._slot) and assembles them with the pinned original arithmetic
    (frankie_box_native_auxiliary). In the native child beside the legacy pass, the legacy pass's CPUs are handed to
    the book workers once it ends first (native_cpu_handover)."""
    seen, cores, siblings = set(), [], []
    for cpu in _booked_cpus():
        base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
        key = (int((base / 'physical_package_id').read_text()),
               int((base / 'core_id').read_text()))
        if key not in seen:
            seen.add(key)
            cores.append(dict(cpu=cpu, package=key[0], core=key[1]))
        else:
            siblings.append(dict(cpu=cpu, package=key[0], core=key[1]))
    if len(cores) < 8:
        raise ValueError('six native/evidence cores, a book core and a system core required')
    roles = ['ROOT', 'queue', 'replenishment', 'census', 'encoder-1', 'encoder-2']
    # The ROOT role is the traversal's serial consumer: its core's other hardware thread stays idle so it has a whole
    # physical core (Greg, 2026-10-07); every other sibling remains a book worker. On a lane without siblings nothing
    # changes. The book results do not depend on the worker count (above).
    root_core = (cores[1]['package'], cores[1]['core'])
    places = cores[1:] + [s for s in siblings if (s['package'], s['core']) != root_core]
    roles += ['book-' + str(index + 1) for index in range(len(places) - len(roles))]
    return dict(zip(roles, places))


HANDOVER_ENV = 'FRANKIE_NATIVE_CPU_HANDOVER'
HANDOVER_SCHEMA = 'FRANKIE_NATIVE_CPU_HANDOVER_V1'


def native_cpu_handover():
    """The CPUs the legacy pass handed to this native traversal, [] while none (Greg, 2026-10-07: "give it all the
    CPUs"). The ROOT that forked this native child (frankie_box_boss_session._start_native_overlap) names the file in
    FRANKIE_NATIVE_CPU_HANDOVER and writes it, atomically, once its legacy pass has ended and it only waits for this
    child (_await_native_overlap). The file counts only for the process it names (child_pid == this pid), so a file of
    an earlier attempt never hands CPUs over. Placement only: the book workers' level results do not depend on them."""
    path = os.environ.get(HANDOVER_ENV)
    if not path:
        return []
    try:
        import json
        body = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return []
    if (not isinstance(body, dict) or body.get('schema') != HANDOVER_SCHEMA or body.get('child_pid') != os.getpid()
            or not isinstance(body.get('cpus'), list) or not all(type(c) is int and c >= 0 for c in body['cpus'])):
        return []
    return sorted(set(body['cpus']))


def runtime_note(directory):
    """A note writer for the native child's placement events (handed-over CPUs, lost book workers): one JSON line each
    in <bedrock>/runtime-workers-notes.jsonl, and the ROOT log (stderr). Never raises into the traversal."""
    import json
    import sys
    def note(text):
        line = json.dumps(dict(at=time.time(), pid=os.getpid(), note=text), sort_keys=True)
        try:
            with open(Path(directory) / 'runtime-workers-notes.jsonl', 'a') as stream:
                stream.write(line + '\n')
        except OSError:
            pass
        try:
            print('native runtime: ' + text, file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass
    return note


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
    """One encoder process: pinned to its CPU, then the encoding (_encode_serve)."""
    try:
        pin_threads(os.getpid(), cpu)
        _encode_serve(connection, producers, cpu)
    except BaseException:
        try:
            connection.send_bytes(cloudpickle.dumps(('error', traceback.format_exc()), protocol=5))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


def _encode_serve(connection, producers, cpu):
    shared = None
    try:
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
    finally:
        if shared is not None:
            shared.close()
            shared.unlink()


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
        current = dict(encoders=2,
            maximum_pending_batches=2, batch_rows=BATCH_ROWS, batch_flush_bytes=BATCH_BYTES,
            row_freeze='one immutable member pickle inside pinned note_member_row; independent other rows',
            output_transport='producer-owned shared bytes; ROOT ordered write/hash; reuse after commit',
            writer='ROOT', serializer='pinned RowSink.write',
            checkpoint_barrier='flush batches then materialize original sinks')
        # V4 binds the native code identity of this file's NATIVE_VALUE_CODE, not its whole bytes. Compatibility rule
        # (Greg, 2026-10-07): a saved V3 policy (whole-file helper_sha256) is accepted only while this whole file is
        # byte-identical; the existing V2 predecessor rule is unchanged. The transition is recorded on the driver.
        policy = dict(current, schema='FRANKIE_PARALLEL_EVIDENCE_V4', helper_code=native_code_identity()['sha256'])
        whole_file = dict(current, schema='FRANKIE_PARALLEL_EVIDENCE_V3',
            helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        bind_transport_policy(driver, '_frankie_evidence_policy', policy, (predecessor, whole_file))
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


def auxiliary_policies(book_workers):
    """The auxiliary transport policy this checkout binds, and the saved predecessors it accepts (on a verified
    full-state resume, recorded by bind_transport_policy). book_workers: the core plan's starting count."""
    import frankie_box_native_auxiliary as auxiliary
    predecessor = dict(schema='FRANKIE_NATIVE_AUXILIARY_V2',
        book_workers=book_workers, census_workers=1,
        book_rule='persistent fixed partitions; ordered snapshot deltas; pinned math; join before next event',
        census_rule='immutable ordered batches; drain and materialize at checkpoint',
        helper_sha256='5cc07cb1289f0b89facf5a93b7287a6f4fed2be6f785eee79329e0a8e09f1343')
    rules = dict(census_workers=1,
        book_rule='persistent fixed partitions; ordered snapshot deltas; pinned math; join before next event',
        census_rule='scoped shared member freeze; ordered batches; drain and materialize at checkpoint')
    # V4 binds the native code identity of frankie_box_native_auxiliary's NATIVE_VALUE_CODE and no longer the
    # book worker count (a level's result does not depend on it; ParallelBook already changes its worker set
    # mid-run); the count is recorded in the workers receipt. Compatibility rule (Greg, 2026-10-07): a saved
    # V3 policy is accepted only while frankie_box_native_auxiliary.py is byte-identical and the count is the
    # same; the existing V2 predecessor rule is unchanged. The transition is recorded on the driver.
    # V5 (2026-10-07 night): level placement moved out of ParallelBook._snapshot into ParallelBook._slot (a
    # hash of side and price; the earlier price-modulo placement put every bid on one worker and every ask on
    # another on NG's power-of-two tick grid). Placement never changes a level's value (InstrumentBook._level
    # reads only its own level), so a saved V4 policy of the deployment that had the old placement (helper
    # code 81092be5, commits 275367f/1e0a893) is accepted on a verified full-state resume, recorded.
    # V6 (2026-10-07 night, native levers): the second copy of a level used by both the top-N and the full-depth
    # list is made by an exact pickle round trip instead of copy.deepcopy (frankie_box_native_auxiliary._exact_copy:
    # equal values, types and float bits, no aliasing, as before). The V5 deployment (helper code 7ecfa33a, commits
    # 5493732 .. c9bf631) is accepted on a verified full-state resume, recorded, as V4 already was.
    placement = 'ParallelBook._slot: golden-ratio hash of (side, price) modulo the worker count'
    policy = dict(rules, schema='FRANKIE_NATIVE_AUXILIARY_V6', book_placement=placement,
        level_copy='exact pickle round trip of the second use of a level (equal to copy.deepcopy)',
        helper_code=auxiliary.native_code_identity()['sha256'])
    golden_ratio = dict(rules, schema='FRANKIE_NATIVE_AUXILIARY_V5', book_placement=placement,
        helper_code='7ecfa33a70dd6321afa75ac697b569ba08778b4e56fecb7d2748879a98b3d40a')
    price_modulo = dict(rules, schema='FRANKIE_NATIVE_AUXILIARY_V4',
        helper_code='81092be52fd103e586013440640a923f4a89f832d5e1fe9c48fa9995a0ab4103')
    whole_file = dict(rules, schema='FRANKIE_NATIVE_AUXILIARY_V3', book_workers=book_workers,
        helper_sha256=hashlib.sha256(Path(auxiliary.__file__).read_bytes()).hexdigest())
    return policy, (predecessor, whole_file, price_modulo, golden_ratio)


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
            book_roles = [role for role in self.plan if role.startswith('book-')]
            if not book_roles:
                raise ValueError('at least one full-book worker core required')
            policy, predecessors = auxiliary_policies(len(book_roles))
            bind_transport_policy(self.driver, '_frankie_auxiliary_policy', policy, predecessors)
            if not hasattr(self.driver, '_frankie_auxiliary_metrics'):
                self.driver._frankie_auxiliary_metrics = dict(census={}, books={})
            metrics = self.driver._frankie_auxiliary_metrics
            self.census = ParallelCensus(self.driver,self.producers,self.plan['census']['cpu'],metrics['census'])
            # The legacy pass's CPUs join the book workers once it ends first (placement only; native_cpu_handover).
            directory = self.driver.checkpointer.checkpoint_dir.parent
            self.books = ParallelBook(self.producers,[self.plan[role]['cpu'] for role in book_roles],metrics['books'],
                                      note=runtime_note(directory),
                                      handover=native_cpu_handover if os.environ.get(HANDOVER_ENV) else None)
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
                book_workers=len(book_roles),
                book_cpu_handover=os.environ.get(HANDOVER_ENV),
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
