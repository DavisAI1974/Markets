"""Independent native census and read-only price-level calculations."""
from contextlib import contextmanager
import copy
import io
import multiprocessing
import os
import time
import traceback
import weakref
from types import SimpleNamespace

import cloudpickle


def _worker(connection, producers, cpu, kind, state):
    try:
        from frankie_box_parallel_evidence import pin_threads
        from frankie_box_bedrock import load_producers
        pin_threads(os.getpid(), cpu)
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
    except BaseException:
        try:
            connection.send_bytes(cloudpickle.dumps(('error', traceback.format_exc()), protocol=5))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


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
        payload = cloudpickle.dumps((command,value),protocol=5)
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
        if self.process.is_alive():
            if not self.pending:
                try:
                    self.send('stop')
                except (EOFError,OSError):
                    pass
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        self.connection.close()


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
            return copy.deepcopy(result)
        self.used.add(key)
        return result


class ParallelBook:
    def __init__(self,producers,cpus,metrics=None):
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
        try:
            for cpu in cpus:
                self.workers.append(NativeWorker(producers,cpu,'book',metrics=metrics.setdefault(str(cpu),{})))
        except BaseException:
            self.close()
            raise
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
        self.wrapper, self.effect_wrapper = snapshot, effect
        InstrumentBook.book_snapshot = snapshot
        InstrumentBook._book_effect = effect
        self.active = True

    def snapshot(self,book,now_ns,depth_levels,include_order_ids):
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
        def partition(side, price):
            return (price + (side == 'A')) % count
        for side, price in items:
            batches[partition(side, price)].append((side, price))
        changed = items if state['reset'] else sorted(state['dirty'])
        for side, price in changed:
            ids = list(book.levels[side].get(price, ()))
            orders = {oid:book.orders[oid] for oid in ids if oid in book.orders}
            changes[partition(side, price)].append((side, price, ids, orders))
        dropped, self.dropped = self.dropped, []
        for worker, delta, batch in zip(self.workers, changes, batches):
            worker.send('levels', (state['token'], generation, state['reset'], delta,
                                  batch, now_ns, include_order_ids, dropped))
        results = {}
        for worker in self.workers:
            token, actual_generation, levels = worker.receive()
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
        for worker in self.workers:
            worker.close()
        self.workers.clear()
        self.states.clear()
        self.references.clear()
