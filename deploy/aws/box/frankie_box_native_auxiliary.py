"""Independent native census and read-only price-level calculations."""
from contextlib import contextmanager
import copy
import io
import multiprocessing
import pickle
import os
import time
import traceback
import weakref
from types import SimpleNamespace

import cloudpickle

# What the native values computed here depend on (the auxiliary transport policy's helper_code,
# frankie_box_parallel_evidence.RuntimeSections.start): the worker's level and census computation, the census
# batching, the per-level result view and the snapshot partition coverage/assembly. The worker processes and their
# CPUs (_worker, NativeWorker), the book worker set (ParallelBook.__init__, widen, handover, lost workers), the level
# placement (ParallelBook._slot: which worker computes a level) and close may change without refusing a saved
# checkpoint: a level's result reads only its own level and orders (InstrumentBook._level), so it does not depend on
# which or how many workers compute it.
NATIVE_VALUE_CODE = ('_serve', 'ParallelCensus', '_BookView', '_exact_copy', 'ParallelBook._wrap',
                     'ParallelBook._reseed', 'ParallelBook.snapshot', 'ParallelBook._snapshot',
                     'ParallelBook.materialized')


def native_code_identity():
    from frankie_box_bedrock import code_identity
    return code_identity(__file__, NATIVE_VALUE_CODE)


def _worker(connection, producers, cpu, kind, state):
    """One auxiliary worker process: pinned to its CPU, then the computation (_serve).
    SIGTERM (session 5, 2026-10-08; the shard-hang rule): the default action first, before any task. The workers are
    spawned (exec resets a caught handler, so a spawned worker never had the ROOT's save handler); this keeps it so if
    the start method ever changes to fork. Not part of NATIVE_VALUE_CODE."""
    try:
        import signal
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    except (ValueError, OSError):
        pass
    try:
        from frankie_box_parallel_evidence import pin_threads
        pin_threads(os.getpid(), cpu)
        _serve(connection, producers, cpu, kind, state)
    except BaseException:
        try:
            connection.send_bytes(cloudpickle.dumps(('error', traceback.format_exc()), protocol=5))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


def _serve(connection, producers, cpu, kind, state):
    from frankie_box_bedrock import load_producers
    load_producers(producers)
    from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook
    census = cloudpickle.loads(state) if state is not None else None
    books = {}
    connection.send_bytes(cloudpickle.dumps(('ok', dict(pid=os.getpid(), cpu=cpu))))
    while True:
        command, payload = cloudpickle.loads(connection.recv_bytes())
        if command == 'stop':
            break
        started = time.perf_counter()
        if kind == 'book' and command == 'levels':
            token, generation, reset, changes, items, now_ns, include_ids, dropped = payload
            for old_token in dropped:
                books.pop(old_token, None)
            previous = books.get(token)
            if previous is None:
                if not reset or generation != 1:
                    raise ValueError('book worker requires an initial complete partition')
                view, last_generation = SimpleNamespace(levels={'B':{},'A':{}}, orders={}), 0
            else:
                view, last_generation = previous
            if generation != last_generation + 1:
                raise ValueError('book worker snapshot generation differs')
            if reset:
                view = SimpleNamespace(levels={'B':{},'A':{}}, orders={})
            # Remove all old affected levels first: a moved order may be in
            # another changed level in this same partition.
            for side, price, ids, orders in changes:
                for oid in view.levels[side].pop(price, ()):
                    view.orders.pop(oid, None)
            for side, price, ids, orders in changes:
                if ids:
                    view.levels[side][price] = ids
                    view.orders.update(orders)
            books[token] = view, generation
            actual = {(side,price) for side in ('B','A')
                      for price,ids in view.levels[side].items() if ids}
            if actual != set(items):
                raise ValueError('persistent book partition coverage differs')
            levels = [(side,price,InstrumentBook._level(view, side, price, now_ns, include_ids))
                      for side,price in items]
            result = token, generation, levels
        elif kind == 'census' and command == 'observe_batch':
            stream = io.BytesIO(payload)
            observed = 0
            while stream.tell() < len(payload):
                census.observe(cloudpickle.load(stream))
                observed += 1
            result = observed
        elif kind == 'census' and command == 'state':
            result = census
        else:
            raise ValueError('unsupported native auxiliary command')
        connection.send_bytes(cloudpickle.dumps(
            ('ok', (result, time.perf_counter()-started)), protocol=5))


def _transport_bytes(message):
    """Transport only (never a value): the standard C pickler, which reduces the book's RestingOrder instances (an
    importable pinned class, registered by load_producers in every worker) without cloudpickle's per-instance Python
    reducer_override call; cloudpickle when the standard pickler refuses. The worker reads both with cloudpickle.loads
    (the same format), into equal objects."""
    try:
        return pickle.dumps(message, protocol=5)
    except (pickle.PicklingError, TypeError, AttributeError):
        return cloudpickle.dumps(message, protocol=5)


class NativeWorker:
    def __init__(self, producers, cpu, kind, state=None, metrics=None):
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker,
            args=(child,str(producers),cpu,kind,
                  None if state is None else cloudpickle.dumps(state,protocol=5)),
            name='frankie-native-'+kind, daemon=True)
        self.pending = False
        self.compute_seconds = 0.0
        self.metrics = metrics if metrics is not None else {}
        for key in ('messages', 'sent_bytes', 'submit_seconds', 'receive_seconds', 'compute_seconds'):
            self.metrics.setdefault(key, 0)
        try:
            self.process.start()
            child.close()
            self.identity = self.receive(ready=True)
        except BaseException:
            child.close()
            self.close()
            raise

    def send(self, command, value=None):
        if self.pending:
            raise RuntimeError('native auxiliary work is already pending')
        started = time.perf_counter()
        payload = _transport_bytes((command,value))
        self.connection.send_bytes(payload)
        self.pending = True
        self.metrics['messages'] += 1
        self.metrics['sent_bytes'] += len(payload)
        self.metrics['submit_seconds'] += time.perf_counter() - started

    def receive(self, ready=False):
        started = time.perf_counter()
        try:
            status,value = cloudpickle.loads(self.connection.recv_bytes())
        except (EOFError,OSError) as error:
            raise RuntimeError('native auxiliary worker disconnected') from error
        self.pending = False
        self.metrics['receive_seconds'] += time.perf_counter() - started
        if status != 'ok':
            raise RuntimeError('native auxiliary worker failed:\n'+value)
        if ready:
            return value
        result,elapsed = value
        self.compute_seconds += elapsed
        self.metrics['compute_seconds'] += elapsed
        return result

    def close(self):
        """The bounded stop of _close_workers for this one worker (the same steps and 5 s bounds as before: 'stop',
        terminate, kill). Returns what had to be terminated or killed (pid, at, how, exit code), else None."""
        stopped = _close_workers([self])
        return stopped[0] if stopped else None


WORKER_STOP_SECONDS = 5.0      # _close_workers: each step's bound (shared by every worker it stops)


def _close_workers(workers):
    """Stop native auxiliary workers, every wait bounded (session 5; the rule of frankie_box_lane_pin's dead-worker
    handling and boss_session's LegacyFrameShards._stop / _bounded_pool_stop): 'stop' to each idle live worker, one
    shared WORKER_STOP_SECONDS for all to exit; terminate() the rest, one shared bound; kill() what is still alive, one
    shared bound; every connection closed. Per worker this is the earlier NativeWorker.close (stop, join 5, terminate,
    join 5, kill, join 5); several workers now wait in parallel instead of 15 s each in turn. Returns the workers that
    had to be terminated or killed: [dict(pids, at, how, exit_code)]. A worker's only output is its pipe (results
    the caller reads), so ending one loses nothing."""
    live = [w for w in workers if w.process.is_alive()]
    for worker in live:
        if not worker.pending:
            try:
                worker.send('stop')
            except (EOFError, OSError):
                pass

    def wait(group):
        deadline = time.monotonic() + WORKER_STOP_SECONDS
        for worker in group:
            worker.process.join(timeout=max(0.0, deadline - time.monotonic()))
        return [w for w in group if w.process.is_alive()]
    stopped = []
    if live and not all(w.pending for w in live):
        live = wait(live)
    for how in ('terminate', 'kill'):
        if not live:
            break
        for worker in live:
            getattr(worker.process, how)()
        group, live = live, wait(live)
        stopped.extend(dict(pids=[w.process.pid], at=round(time.time(), 3), how=how, exit_code=w.process.exitcode)
                       for w in group if w not in live)
    stopped.extend(dict(pids=[w.process.pid], at=round(time.time(), 3), how='left_alive', exit_code=None) for w in live)
    for worker in workers:
        worker.connection.close()
    return stopped


class ParallelCensus:
    def __init__(self, driver, producers, cpu, metrics=None):
        self.driver = driver
        self.worker = NativeWorker(producers,cpu,'census',driver.run.field_census,metrics)
        self.active = True
        self.bridge = None
        driver.run.field_census = self
        self.buffer, self.buffer_rows, self.pending_rows = io.BytesIO(), 0, 0

    def observe(self,row):
        # Immutable at submission; no mutable row reference crosses calls.
        frozen = cloudpickle.dumps(row, protocol=5)
        self.buffer.write(frozen)
        if self.bridge is not None:
            self.bridge.offer(row, frozen)
        self.buffer_rows += 1
        if self.buffer_rows >= 32 or self.buffer.tell() >= 1 << 20:
            self.flush()

    def receive(self):
        if self.worker.pending:
            if self.worker.receive() != self.pending_rows:
                raise ValueError('census batch observation count differs')
            self.pending_rows = 0

    def flush(self):
        if self.buffer_rows:
            self.receive()
            self.worker.send('observe_batch', self.buffer.getvalue())
            self.pending_rows = self.buffer_rows
            self.buffer, self.buffer_rows = io.BytesIO(), 0

    def state(self):
        self.flush()
        self.receive()
        self.worker.send('state')
        return self.worker.receive()

    @contextmanager
    def materialized(self):
        self.driver.run.field_census = self.state()
        try:
            yield
        finally:
            if self.active:
                self.driver.run.field_census = self

    def finish(self):
        self.driver.run.field_census = self.state()
        self.active = False
        self.worker.close()

    def close(self):
        self.active = False
        self.worker.close()


class _WorkerLost(Exception):
    def __init__(self, workers, why):
        super().__init__(why)
        self.workers, self.why = workers, why


class _BookView:
    def __init__(self, book, results):
        self.book, self.results = book, results
        self.used = set()

    def __getattr__(self,name):
        return getattr(self.book,name)

    def _level(self,side,price,now_ns,include_order_ids):
        key = (side,price)
        result = self.results[key]
        # The original snapshot computes separate objects for top-N and full-depth.
        # Preserve that lack of aliasing when a level occurs in both.
        if key in self.used:
            return _exact_copy(result)
        self.used.add(key)
        return result


def _exact_copy(value):
    """An independent copy equal to copy.deepcopy(value), at C speed (2026-10-07 night: the top-N levels of every
    full-depth snapshot were deep-copied in Python, ~24% of ROOT's toy traversal). A level (InstrumentBook._level) is a
    dict of str/int/float/None/bool with a list of such dicts (fifo_queue); a pickle round trip (protocol 5) rebuilds
    every container fresh, keeps every type and every float bit for bit, and memoizes shared sub-objects exactly as
    deepcopy does. Anything pickle refuses falls back to copy.deepcopy itself."""
    try:
        return pickle.loads(pickle.dumps(value, protocol=5))
    except (pickle.PicklingError, TypeError, AttributeError):
        return copy.deepcopy(value)


class ParallelBook:
    """Full-depth snapshot levels on pinned book workers, the original assembly on their exact per-level results.

    A level's result does not depend on which worker computed it or how many there are (the partition only spreads the
    work; every level joins before the snapshot is assembled), so the worker set may change between snapshots:
    - a worker that disconnects or fails is dropped (never refilled: one less worker), every mirror is re-seeded on the
      survivors and the snapshot is computed again (on no worker left: the original method in this process); `note`
      records it; nothing stops;
    - `handover()` (asked every HANDOVER_CHECK_SECONDS between snapshots until it hands CPUs over, once) adds one pinned
      worker per CPU handed over and re-seeds: in the legacy pass the native child's CPUs once it ended first, in the
      native child (frankie_box_parallel_evidence.RuntimeSections) the legacy pass's CPUs once it ended first.
    Levels are placed on workers by _slot (placement only, outside the native value code)."""

    HANDOVER_CHECK_SECONDS = 5.0

    def __init__(self,producers,cpus,metrics=None,note=None,handover=None):
        from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook
        self.book_class = InstrumentBook
        self.original = InstrumentBook.book_snapshot
        self.original_effect = InstrumentBook._book_effect
        self.states = weakref.WeakKeyDictionary()
        self.next_token, self.dropped, self.references = 0, [], {}
        self.workers = []
        self.active = False
        self.calls, self.levels, self.seconds = 0,0,0.0
        metrics = metrics if metrics is not None else {}
        self.producers, self.metrics, self.note, self.handover = producers, metrics, note, handover
        self.cpus = []
        self.workers_lost, self.snapshots_redone, self.handed_over = 0, 0, []
        self.stop_kills = []          # workers a bounded stop had to terminate or kill (session 5; additive)
        self._handover_next = time.monotonic() + self.HANDOVER_CHECK_SECONDS
        try:
            for cpu in cpus:
                self.workers.append(NativeWorker(producers,cpu,'book',metrics=metrics.setdefault(str(cpu),{})))
                self.cpus.append(cpu)
        except BaseException:
            self.close()
            raise
        self.wrapper, self.effect_wrapper = self._wrap()
        InstrumentBook.book_snapshot = self.wrapper
        InstrumentBook._book_effect = self.effect_wrapper
        self.active = True

    def _wrap(self):
        """The snapshot and book-effect wrappers: full-depth snapshots on the workers, dirty-level tracking for the
        mirrors; every other call the original pinned method."""
        owner = self
        def snapshot(book,now_ns,depth_levels=10,include_full_depth=False,include_order_ids=False):
            if not include_full_depth:
                return owner.original(book,now_ns,depth_levels,include_full_depth,include_order_ids)
            return owner.snapshot(book,now_ns,depth_levels,include_order_ids)
        def effect(book, msg):
            state = owner.states.get(book)
            if state is not None:
                # R and top-of-book side clearing may delete many order IDs.
                # Re-seed on the next full snapshot; ordinary updates touch at
                # most the old and new level, including FIFO priority changes.
                if msg.action == 'R' or (msg.action == 'A' and msg.flags & F_TOB
                                        and abs(msg.price_raw) >= UNDEF_PRICE):
                    state['reset'] = True
                elif msg.action in ('A', 'C', 'M'):
                    old = book.orders.get(msg.order_id)
                    if old is not None:
                        state['dirty'].add((old.side, old.price_raw))
                    if msg.side in ('B', 'A'):
                        state['dirty'].add((msg.side, msg.price_raw))
            result = owner.original_effect(book, msg)
            if state is not None and msg.action in ('A', 'C', 'M'):
                current = book.orders.get(msg.order_id)
                if current is not None:
                    state['dirty'].add((current.side, current.price_raw))
            return result
        from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_TOB, UNDEF_PRICE
        return snapshot, effect

    def _reseed(self):
        """Every mirror starts again: the next snapshot of each book sends its complete partition (generation 1) to the
        current workers; the old tokens are released on the workers that hold them."""
        self.dropped.extend(self.references)
        self.references.clear()
        self.states.clear()

    def widen(self, cpus):
        """One more pinned book worker per CPU in `cpus` (only between snapshots: nothing pending). Returns the CPUs added."""
        if any(worker.pending for worker in self.workers):
            raise RuntimeError('book workers widen only with joined levels')
        added = []
        for cpu in cpus:
            if cpu in self.cpus:
                continue
            self.workers.append(NativeWorker(self.producers,cpu,'book',metrics=self.metrics.setdefault(str(cpu),{})))
            self.cpus.append(cpu)
            added.append(cpu)
        if added:
            self._reseed()
        return added

    def _take_handover(self):
        self._handover_next = time.monotonic() + self.HANDOVER_CHECK_SECONDS
        extra = [cpu for cpu in (self.handover() or []) if cpu not in self.cpus]
        if not extra:
            return
        self.handover = None
        try:
            added = self.widen(extra)
        except Exception as error:  # noqa: BLE001 - a worker that will not start is one CPU not used, never a stop
            added = []
            if self.note is not None:
                self.note('full-depth book workers: handed-over CPUs not taken (%s: %s); %d workers continue'
                          % (type(error).__name__, error, len(self.workers)))
        self.handed_over = added
        if added and self.note is not None:
            self.note('full-depth book workers: CPUs %s handed over; now %d pinned workers; levels unchanged'
                      % (','.join(map(str, added)), len(self.workers)))

    def _lose(self, lost, why):
        """Drop the failed workers (one less each, never refilled), drain the others' results (discarded), re-seed."""
        for worker in self.workers:
            if worker in lost or not worker.pending:
                continue
            try:
                worker.receive()
            except Exception:  # noqa: BLE001 - a second failure in the same snapshot: dropped as well
                lost.append(worker)
        for worker in lost:
            index = self.workers.index(worker)
            self.workers.pop(index)
            self.cpus.pop(index)
            try:
                stopped = worker.close()
                if stopped:
                    self.stop_kills.append(stopped)
            except Exception:  # noqa: BLE001
                pass
        self.workers_lost += len(lost)
        self.snapshots_redone += 1
        self._reseed()
        if self.note is not None:
            self.note('full-depth book workers: %d lost (%s); %d left%s; this snapshot computed again, levels unchanged'
                      % (len(lost), why, len(self.workers), '' if self.workers else ' (snapshots in this process)'))

    # Fibonacci hashing (Knuth): the top 32 bits of a 64-bit golden-ratio product spread consecutive keys evenly.
    SLOT_MULTIPLIER = 0x9E3779B97F4A7C15
    SLOT_MASK = (1 << 64) - 1

    @classmethod
    def _slot(cls, side, price, count):
        """The worker index that computes level (side, price): placement only, never a value (a level's result reads
        only that level). A pure function of (side, price, count), so a persistent mirror keeps every level it owns
        until the worker count changes (widen/lose re-seed). Prices are integer nanodollars on a tick grid
        (InstrumentBook price_raw, PRICE_SCALE 1e9): NG's 0.001 tick is 1,000,000 = 2**6 * 15625, so the earlier
        (price + side) % count put every bid on worker 0 and every ask on worker 1 for any count dividing 64 (e2e a2,
        20231018: 8 workers, CPUs 7 and 16 computed 99% of the levels; ROOT waited 356 s of ~1,260 s on them). The
        golden-ratio product's top bits do not depend on the grid's power-of-two factor."""
        key = 2 * price + (side == 'A')
        return (((key * cls.SLOT_MULTIPLIER) & cls.SLOT_MASK) >> 32) % count

    def snapshot(self,book,now_ns,depth_levels,include_order_ids):
        if self.handover is not None and time.monotonic() >= self._handover_next:
            self._take_handover()
        if not self.workers:
            started = time.perf_counter()
            result = self.original(book,now_ns,depth_levels,True,include_order_ids)
            self.calls += 1
            self.seconds += time.perf_counter()-started
            return result
        try:
            return self._snapshot(book,now_ns,depth_levels,include_order_ids)
        except _WorkerLost as lost:
            self._lose(lost.workers, lost.why)
            return self.snapshot(book,now_ns,depth_levels,include_order_ids)

    def _snapshot(self,book,now_ns,depth_levels,include_order_ids):
        started = time.perf_counter()
        items = [(side,price) for side in ('B','A') for price in book._prices(side)]
        state = self.states.get(book)
        if state is None:
            self.next_token += 1
            token = self.next_token
            state = dict(token=token, generation=0, reset=True, dirty=set())
            # Worker mirrors are released after the native book becomes unreachable.
            def release(ref, token=token):
                self.dropped.append(token)
                self.references.pop(token, None)
            self.references[token] = weakref.ref(book, release)
            self.states[book] = state
        generation = state['generation'] + 1
        count = len(self.workers)
        batches, changes = [[] for _ in range(count)], [[] for _ in range(count)]
        slot = self._slot
        for side, price in items:
            batches[slot(side, price, count)].append((side, price))
        changed = items if state['reset'] else sorted(state['dirty'])
        for side, price in changed:
            ids = list(book.levels[side].get(price, ()))
            orders = {oid:book.orders[oid] for oid in ids if oid in book.orders}
            changes[slot(side, price, count)].append((side, price, ids, orders))
        dropped, self.dropped = self.dropped, []
        lost, why = [], None
        for worker, delta, batch in zip(self.workers, changes, batches):
            try:
                worker.send('levels', (state['token'], generation, state['reset'], delta,
                                      batch, now_ns, include_order_ids, dropped))
            except (EOFError, OSError) as error:
                lost.append(worker)
                why = why or '%s: %s' % (type(error).__name__, error)
        results = {}
        replies = []
        for worker in self.workers:
            if worker in lost:
                continue
            try:
                replies.append(worker.receive())
            except RuntimeError as error:
                lost.append(worker)
                why = why or (str(error).splitlines() or [type(error).__name__])[0]
        if lost:
            raise _WorkerLost(lost, why)
        for token, actual_generation, levels in replies:
            if token != state['token'] or actual_generation != generation:
                raise ValueError('book result belongs to another snapshot')
            for side, price, result in levels:
                if (side, price) in results:
                    raise ValueError('book worker partitions overlap')
                results[(side,price)] = result
        state['generation'], state['reset'] = generation, False
        state['dirty'].clear()
        if set(results) != set(items):
            raise ValueError('parallel full-book level coverage differs')
        # Execute the original pinned assembly and arithmetic using the exact
        # per-level outputs. All levels join before the next market event.
        result = self.original(_BookView(book,results),now_ns,depth_levels,True,include_order_ids)
        self.calls += 1
        self.levels += len(items)
        self.seconds += time.perf_counter()-started
        return result

    @contextmanager
    def materialized(self):
        if any(worker.pending for worker in self.workers):
            raise RuntimeError('book checkpoint requires joined levels')
        self.book_class.book_snapshot = self.original
        self.book_class._book_effect = self.original_effect
        try:
            yield
        finally:
            if self.active:
                self.book_class.book_snapshot = self.wrapper
                self.book_class._book_effect = self.effect_wrapper

    def close(self):
        if self.active:
            self.book_class.book_snapshot = self.original
            self.book_class._book_effect = self.original_effect
            self.active = False
        stopped = _close_workers(self.workers)
        if stopped:
            self.stop_kills.extend(stopped)
            if self.note is not None:
                self.note('full-depth book workers: %d did not stop on request within %.0f s and were ended (%s); '
                          'workers write nothing durable, nothing lost'
                          % (len(stopped), WORKER_STOP_SECONDS, ', '.join(s['how'] for s in stopped)))
        self.workers.clear()
        self.states.clear()
        self.references.clear()
