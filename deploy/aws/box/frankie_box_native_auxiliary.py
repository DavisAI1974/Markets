"""Independent native census and read-only price-level calculations."""
from contextlib import contextmanager
import copy
import multiprocessing
import os
import time
import traceback
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
        connection.send_bytes(cloudpickle.dumps(('ok', dict(pid=os.getpid(), cpu=cpu))))
        while True:
            command, payload = cloudpickle.loads(connection.recv_bytes())
            if command == 'stop':
                break
            started = time.perf_counter()
            if kind == 'book' and command == 'levels':
                levels, orders, items, now_ns, include_ids = payload
                view = SimpleNamespace(levels=levels, orders=orders)
                result = [(side,price,InstrumentBook._level(view, side, price, now_ns, include_ids))
                          for side,price in items]
            elif kind == 'census' and command == 'observe':
                census.observe(payload)
                result = None
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
    def __init__(self, producers, cpu, kind, state=None):
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker,
            args=(child,str(producers),cpu,kind,
                  None if state is None else cloudpickle.dumps(state,protocol=5)),
            name='frankie-native-'+kind, daemon=True)
        self.pending = False
        self.compute_seconds = 0.0
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
        self.connection.send_bytes(cloudpickle.dumps((command,value),protocol=5))
        self.pending = True

    def receive(self, ready=False):
        try:
            status,value = cloudpickle.loads(self.connection.recv_bytes())
        except (EOFError,OSError) as error:
            raise RuntimeError('native auxiliary worker disconnected') from error
        self.pending = False
        if status != 'ok':
            raise RuntimeError('native auxiliary worker failed:\n'+value)
        if ready:
            return value
        result,elapsed = value
        self.compute_seconds += elapsed
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
    def __init__(self, driver, producers, cpu):
        self.driver = driver
        self.worker = NativeWorker(producers,cpu,'census',driver.run.field_census)
        self.active = True
        driver.run.field_census = self

    def observe(self,row):
        # One immutable row in flight; observe order remains the source order.
        if self.worker.pending:
            self.worker.receive()
        self.worker.send('observe',row)

    def state(self):
        if self.worker.pending:
            self.worker.receive()
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
    def __init__(self,producers,cpus):
        from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook
        self.book_class = InstrumentBook
        self.original = InstrumentBook.book_snapshot
        self.workers = []
        self.active = False
        self.calls, self.levels, self.seconds = 0,0,0.0
        try:
            for cpu in cpus:
                self.workers.append(NativeWorker(producers,cpu,'book'))
        except BaseException:
            self.close()
            raise
        owner = self
        def snapshot(book,now_ns,depth_levels=10,include_full_depth=False,include_order_ids=False):
            if not include_full_depth:
                return owner.original(book,now_ns,depth_levels,include_full_depth,include_order_ids)
            return owner.snapshot(book,now_ns,depth_levels,include_order_ids)
        self.wrapper = snapshot
        InstrumentBook.book_snapshot = snapshot
        self.active = True

    def snapshot(self,book,now_ns,depth_levels,include_order_ids):
        started = time.perf_counter()
        items = [(side,price) for side in ('B','A') for price in book._prices(side)]
        if not items:
            return self.original(book,now_ns,depth_levels,True,include_order_ids)
        count = min(len(items),len(self.workers))
        batches = [[] for _ in range(count)]
        for index,item in enumerate(items):
            batches[index % count].append(item)
        submitted = []
        for worker,batch in zip(self.workers,batches):
            levels,orders = {'B':{},'A':{}},{}
            for side,price in batch:
                ids = list(book.levels[side].get(price,()))
                levels[side][price] = ids
                orders.update((oid,book.orders[oid]) for oid in ids if oid in book.orders)
            worker.send('levels',(levels,orders,batch,now_ns,include_order_ids))
            submitted.append(worker)
        results = {}
        for worker in submitted:
            for side,price,result in worker.receive():
                results[(side,price)] = result
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
        try:
            yield
        finally:
            if self.active:
                self.book_class.book_snapshot = self.wrapper

    def close(self):
        if self.active:
            self.book_class.book_snapshot = self.original
            self.active = False
        for worker in self.workers:
            worker.close()
        self.workers.clear()
