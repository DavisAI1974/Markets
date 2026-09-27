"""Run independent native sections concurrently inside one ordered ROOT traversal.

The pinned producer modules and their call sites remain unchanged. Only queue and
replenishment own child processes; the causal driver and exact ledgers stay here.
Every group is joined before the next group, and every checkpoint materializes the
complete native object graph (including adapter/calculator aliases).
"""
from contextlib import contextmanager
import hashlib
import multiprocessing
from pathlib import Path
import time
import traceback
from types import MethodType

import cloudpickle

KINDS = ('queue', 'replenishment')


def execution_policy():
    return dict(schema='FRANKIE_NATIVE_PARALLEL_V1', start_method='spawn',
                calculation_processes=3, worker_sections=list(KINDS),
                groups_in_flight=1, ledger_writer='ROOT',
                helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def bind_policy(driver):
    policy = execution_policy()
    previous = getattr(driver, '_frankie_parallel_policy', None)
    if previous is not None and previous != policy:
        raise ValueError('checkpoint parallel execution policy differs')
    driver._frankie_parallel_policy = policy
    if not hasattr(driver, '_frankie_parallel_metrics'):
        driver._frankie_parallel_metrics = {
            kind: dict(groups=0, calls=0, compute_seconds=0.0, wait_seconds=0.0)
            for kind in KINDS
        }


def _worker(connection, kind, payload, producers):
    """Own one native branch; receive no source iterator or evidence sink."""
    try:
        # spawn starts a fresh interpreter: register the pinned V4 module before
        # importing any native module or unpickling its state.
        from frankie_box_bedrock import load_producers
        load_producers(producers)
        calculator, adapter, books = cloudpickle.loads(payload)
        connection.send_bytes(cloudpickle.dumps(('ok', None, 0.0), protocol=5))
        while True:
            command, args = cloudpickle.loads(connection.recv_bytes())
            started = time.perf_counter()
            if command == 'stop':
                break
            if command == 'group':
                actions, ctx = args
                if kind == 'queue':
                    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import ReplayBook
                    result = adapter.feed_group(
                        calculator, actions, ctx,
                        book=books.setdefault(ctx.instrument_id, ReplayBook()))
                else:
                    result = adapter.observe_group(actions, ctx, calculator=calculator)
            elif command == 'call':
                target, method, positional, keywords = args
                allowed = (
                    target == 'calculator' and method == 'close_continuity_segment'
                    or target == 'adapter' and method == 'close_continuity_segment'
                    or kind == 'replenishment' and target == 'calculator' and method == 'advance'
                )
                if not allowed:
                    raise ValueError('unsupported native branch call')
                owner = calculator if target == 'calculator' else adapter
                result = getattr(owner, method)(*positional, **keywords)
            elif command == 'state':
                # One pickle keeps the observer's references to pending episodes
                # and the queue adapter's references to its actual books intact.
                result = (calculator, adapter, books)
            else:
                raise ValueError('unknown native branch command')
            elapsed = time.perf_counter() - started
            connection.send_bytes(cloudpickle.dumps(('ok', result, elapsed), protocol=5))
    except BaseException:
        try:
            connection.send_bytes(cloudpickle.dumps(
                ('error', traceback.format_exc(), 0.0), protocol=5))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


class _Branch:
    def __init__(self, kind, state, metrics, producers):
        self.kind = kind
        self.metrics = metrics
        self.pending = None
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe(duplex=True)
        self.process = context.Process(
            target=_worker, args=(child, kind, cloudpickle.dumps(state, protocol=5), producers),
            name='frankie-native-' + kind, daemon=True)
        try:
            self.process.start()
        except BaseException:
            child.close()
            self.connection.close()
            raise
        child.close()
        self.pending = 'ready'
        try:
            self.receive()
        except BaseException:
            self.close()
            raise

    def send(self, command, args=()):
        if self.pending is not None:
            raise RuntimeError('native branch already has an outstanding command')
        self.connection.send_bytes(cloudpickle.dumps((command, args), protocol=5))
        self.pending = command

    def receive(self):
        if self.pending is None:
            raise RuntimeError('native branch has no outstanding command')
        command = self.pending
        started = time.perf_counter()
        try:
            status, result, elapsed = cloudpickle.loads(self.connection.recv_bytes())
        except (EOFError, OSError) as error:
            raise RuntimeError(self.kind + ' native worker disconnected') from error
        finally:
            self.pending = None
        if status != 'ok':
            raise RuntimeError(self.kind + ' native worker failed:\n' + result)
        if command in ('group', 'call'):
            self.metrics['groups' if command == 'group' else 'calls'] += 1
            self.metrics['compute_seconds'] += elapsed
            self.metrics['wait_seconds'] += time.perf_counter() - started
        return result

    def call(self, target, method, *args, **kwargs):
        self.send('call', (target, method, args, kwargs))
        return self.receive()

    def close(self):
        # These are only this traversal's children, never another ROOT or host.
        try:
            if self.process.is_alive() and self.pending is None:
                try:
                    self.send('stop')
                except (BrokenPipeError, EOFError, OSError):
                    pass
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        finally:
            self.connection.close()
            if not self.process.is_alive():
                self.process.close()


class _Calculator:
    def __init__(self, branch):
        self.branch = branch

    def close_continuity_segment(self, **kwargs):
        return self.branch.call('calculator', 'close_continuity_segment', **kwargs)

    def advance(self, recv_ns):
        return self.branch.call('calculator', 'advance', recv_ns)


class _Adapter:
    def __init__(self, branch, coordinator):
        self.branch = branch
        self.coordinator = coordinator

    def observe_group(self, actions, ctx, *, calculator):
        return self.coordinator.group_result(self.branch.kind, ctx)

    def feed_group(self, calculator, actions, ctx, *, book):
        return self.coordinator.group_result(self.branch.kind, ctx)

    def close_continuity_segment(self, **kwargs):
        return self.branch.call('adapter', 'close_continuity_segment', **kwargs)


def _feed_parallel(driver, actions, ctx):
    parallel = driver.checkpointer.parallel
    parallel.submit_group(actions, ctx)
    # Keep the pinned retention/counter/dependency ordering verbatim.
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import NativeReplayDriver
    NativeReplayDriver._feed_sections(driver, actions, ctx)
    parallel.finish_group()


class ParallelSections:
    def __init__(self, driver, producers):
        bind_policy(driver)
        self.producers = str(producers)
        self.driver = driver
        self.branches = {}
        self.group_key = None
        self.results_pending = set()
        self.active = False

    def start(self):
        if self.active or '_feed_sections' in vars(self.driver):
            raise RuntimeError('driver already has a section dispatcher')
        driver = self.driver
        states = {
            'queue': (driver.run.queue, driver.queue_adapter, driver._queue_books),
            'replenishment': (driver.run.replenishment, driver.replenishment_observer, None),
        }
        try:
            for kind in KINDS:
                self.branches[kind] = _Branch(
                    kind, states[kind], driver._frankie_parallel_metrics[kind], self.producers)
        except BaseException:
            self.close()
            raise
        self._install_proxies()
        self.active = True
        return self

    def _install_proxies(self):
        driver = self.driver
        driver.run.queue = _Calculator(self.branches['queue'])
        driver.queue_adapter = _Adapter(self.branches['queue'], self)
        driver.run.replenishment = _Calculator(self.branches['replenishment'])
        driver.replenishment_observer = _Adapter(self.branches['replenishment'], self)
        # The pinned call site supplies an unused placeholder; real books stay
        # paired with the queue calculator and adapter in their owning process.
        driver._queue_books = {}
        driver._feed_sections = MethodType(_feed_parallel, driver)

    @staticmethod
    def _key(ctx):
        return (ctx.group_index, ctx.continuity_segment, ctx.instrument_id, ctx.recv_ns)

    def submit_group(self, actions, ctx):
        if self.group_key is not None or self.results_pending:
            raise RuntimeError('previous native group has not joined')
        self.group_key = self._key(ctx)
        for kind in KINDS:
            self.branches[kind].send('group', (actions, ctx))
            self.results_pending.add(kind)

    def group_result(self, kind, ctx):
        if self.group_key != self._key(ctx) or kind not in self.results_pending:
            raise RuntimeError('native group result does not match its ordered call site')
        result = self.branches[kind].receive()
        self.results_pending.remove(kind)
        return result

    def finish_group(self):
        if self.results_pending:
            raise RuntimeError('native group has unretained section results')
        self.group_key = None

    @contextmanager
    def materialized(self):
        if not self.active or self.group_key is not None or self.results_pending:
            raise RuntimeError('native snapshot requires a completed group')
        for kind in KINDS:
            self.branches[kind].send('state')
        states = {kind: self.branches[kind].receive() for kind in KINDS}
        driver = self.driver
        driver.run.queue, driver.queue_adapter, driver._queue_books = states['queue']
        driver.run.replenishment, driver.replenishment_observer, _ = states['replenishment']
        del driver._feed_sections
        try:
            yield
        finally:
            if self.active:
                self._install_proxies()

    def finish(self):
        # Finalization executes against ordinary native objects in ROOT, with
        # the original producer finalizers and reconciliation gates unchanged.
        with self.materialized():
            self.active = False
        self.close()

    def close(self):
        for branch in self.branches.values():
            branch.close()
        self.branches.clear()

