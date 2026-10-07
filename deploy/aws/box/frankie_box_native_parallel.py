"""Run independent native sections concurrently inside one ordered ROOT traversal.

The pinned producer modules and their call sites remain unchanged. Only queue and
replenishment own child processes; the causal driver and exact ledgers stay here.
Every group is joined before the next group, and every checkpoint materializes the
complete native object graph (including adapter/calculator aliases).

Pipelined replenishment (2026-10-07 night, V2): the pinned _on_group calls
run.replenishment.advance(recv_ns) immediately after _feed_sections returns, with the
group's own receive time, and nothing between the replenishment observation (inside
_feed_sections) and that call reaches the replenishment calculator or observer (the
queue feed runs in its own process and lineage on ROOT's own graph). So the
replenishment process runs advance(ctx.recv_ns) right after observe_group, in the same
order on the same objects, and ROOT takes that result at the advance call site instead
of paying a second round trip there. A different receive time at the call site refuses;
an error in advance is raised at the advance call site, as before.
"""
from contextlib import contextmanager
import gc
import hashlib
import multiprocessing
from pathlib import Path
import time
import traceback
from types import MethodType

import cloudpickle

KINDS = ('queue', 'replenishment')
POLICY_SCHEMA = 'FRANKIE_NATIVE_PARALLEL_V2'

# What the native values computed or saved through this file depend on (the execution policy's helper_code): which
# process computes which section call and in what order (_worker, _Calculator, _Adapter, _feed_parallel, the
# ParallelSections dispatch, join and materialization), and the reconstruction boundary (which writes a checkpoint and
# moves the save counter). The process lifecycle and transport (_Branch: spawn, pipes, close), the collector settings
# (_CollectorPolicy) and the policy binding itself may change without refusing a saved checkpoint: every result is
# checked against its ordered call site and every checkpoint materializes the ordinary objects.
NATIVE_VALUE_CODE = ('KINDS', '_worker', '_Calculator', '_Adapter', '_feed_parallel',
                     'ParallelSections.start', 'ParallelSections._install_proxies', 'ParallelSections._key',
                     'ParallelSections.submit_group', 'ParallelSections.group_result',
                     'ParallelSections.finish_group', 'ParallelSections.materialized', 'ParallelSections.finish',
                     '_ReconstructionBoundary', 'consume_after_reconstruction')

# The V1 policy as deployed (frankie_box_native_parallel.py of 767346a .. c9bf631, whole-file sha256): e2e a2's
# native checkpoints carry it. Accepted on a verified full-state resume only, recorded (bind_policy).
V1_DEPLOYED = dict(schema='FRANKIE_NATIVE_PARALLEL_V1', start_method='spawn',
                   calculation_processes=3, worker_sections=list(KINDS),
                   groups_in_flight=1, ledger_writer='ROOT',
                   helper_sha256='120e1a8ef9cb44d85d9ae1344dca5a4a060c21fcddec01e757c5ec0ba317b70f')


def native_code_identity():
    from frankie_box_bedrock import code_identity
    return code_identity(__file__, NATIVE_VALUE_CODE)


def execution_policy():
    return dict(schema=POLICY_SCHEMA, start_method='spawn',
                calculation_processes=3, worker_sections=list(KINDS),
                groups_in_flight=1, ledger_writer='ROOT',
                replenishment_advance='computed in the replenishment process right after its group observation, '
                                      'taken at the pinned advance call site (same receive time required)',
                group_payload='one pickle per group, the same bytes to every section process',
                helper_code=native_code_identity()['sha256'])


def policy_predecessors():
    """The saved policies a verified full-state resume accepts (recorded): the deployed V1, and V1 in its whole-file
    form while this file is byte-identical to the saving checkout (Greg, 2026-10-07: saves survive unrelated edits,
    never a changed computation)."""
    whole_file = dict(V1_DEPLOYED, helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    return (V1_DEPLOYED, whole_file)


def bind_policy(driver):
    """Bind this checkout's execution policy. A saved driver's earlier policy is accepted only when it is a named
    predecessor, on a verified full-state resume, and the transition is recorded on the driver
    (frankie_box_parallel_evidence.bind_transport_policy, the same rule as the evidence and auxiliary policies)."""
    from frankie_box_parallel_evidence import bind_transport_policy
    bind_transport_policy(driver, '_frankie_parallel_policy', execution_policy(), policy_predecessors())
    if not hasattr(driver, '_frankie_parallel_metrics'):
        driver._frankie_parallel_metrics = {
            kind: dict(groups=0, calls=0, compute_seconds=0.0, wait_seconds=0.0)
            for kind in KINDS
        }


class _CollectorPolicy:
    """Value-neutral collector settings for the traversal (Greg 2026-10-07 session 4, native lever 3): the state built
    or restored before the traversal is frozen (gc.freeze: the collector no longer walks it, and a forked child's
    collector no longer writes the parent's pages) and the youngest generation collects every YOUNG_THRESHOLD
    container allocations instead of the default. Reference counting frees every acyclic object at once either way;
    only when cyclic garbage is reclaimed changes, never a value. Restored at close (thresholds; unfreeze)."""

    YOUNG_THRESHOLD = 100_000

    def __init__(self):
        self.saved = None

    def enter(self):
        if self.saved is not None:
            return
        self.saved = gc.get_threshold()
        gc.collect()
        gc.freeze()
        young, *older = self.saved
        gc.set_threshold(max(young, self.YOUNG_THRESHOLD), *older)

    def exit(self):
        if self.saved is None:
            return
        gc.set_threshold(*self.saved)
        gc.unfreeze()
        self.saved = None


def _worker(connection, kind, payload, producers):
    """Own one native branch; receive no source iterator or evidence sink."""
    def reply(status, result, elapsed):
        connection.send_bytes(cloudpickle.dumps((status, result, elapsed), protocol=5))
    try:
        # spawn starts a fresh interpreter: register the pinned V4 module before
        # importing any native module or unpickling its state.
        from frankie_box_bedrock import load_producers
        load_producers(producers)
        calculator, adapter, books = cloudpickle.loads(payload)
        payload = None
        # This branch's state is long-lived: the collector stops walking it (value-neutral, as in ROOT).
        _CollectorPolicy().enter()
        reply('ok', None, 0.0)
        while True:
            command, args = cloudpickle.loads(connection.recv_bytes())
            started = time.perf_counter()
            if command == 'stop':
                break
            advance_at = None
            if command == 'group':
                actions, ctx = args
                if kind == 'queue':
                    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import ReplayBook
                    result = adapter.feed_group(
                        calculator, actions, ctx,
                        book=books.setdefault(ctx.instrument_id, ReplayBook()))
                else:
                    result = adapter.observe_group(actions, ctx, calculator=calculator)
                    # The pinned _on_group's next replenishment call is advance(recv_ns) at this group's receive
                    # time (module docstring); it is computed now and taken at that call site.
                    advance_at = ctx.recv_ns
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
            reply('ok', result, time.perf_counter() - started)
            if advance_at is not None:
                started = time.perf_counter()
                reply('ok', calculator.advance(advance_at), time.perf_counter() - started)
    except BaseException:
        try:
            reply('error', traceback.format_exc(), 0.0)
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


class _Branch:
    def __init__(self, kind, state, metrics, producers):
        self.kind = kind
        self.metrics = metrics
        self.pending = None
        self.advance_at = None
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
        self.send_payload(command, cloudpickle.dumps((command, args), protocol=5))

    def send_payload(self, command, payload):
        """Send an already pickled (command, args) message: one group pickle serves every section process."""
        if self.pending is not None:
            raise RuntimeError('native branch already has an outstanding command')
        self.connection.send_bytes(payload)
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

    def expect_advance(self, recv_ns):
        """The replenishment process has computed advance(recv_ns) after this group's observation; it is the
        outstanding reply until the pinned call site takes it."""
        self.pending = 'call'
        self.advance_at = recv_ns

    def take_advance(self, recv_ns):
        if self.advance_at is None:
            return self.call('calculator', 'advance', recv_ns)
        expected, self.advance_at = self.advance_at, None
        if recv_ns != expected:
            raise RuntimeError('replenishment advance call differs from its group receive time')
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
        return self.branch.take_advance(recv_ns)


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
        self.collector = _CollectorPolicy()

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
        self.collector.enter()
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
        # One pickle, the same bytes to every section process: each unpickles its own copy of this group.
        payload = cloudpickle.dumps(('group', (actions, ctx)), protocol=5)
        for kind in KINDS:
            self.branches[kind].send_payload('group', payload)
            self.results_pending.add(kind)

    def group_result(self, kind, ctx):
        if self.group_key != self._key(ctx) or kind not in self.results_pending:
            raise RuntimeError('native group result does not match its ordered call site')
        branch = self.branches[kind]
        result = branch.receive()
        self.results_pending.remove(kind)
        if kind == 'replenishment':
            branch.expect_advance(ctx.recv_ns)
        return result

    def finish_group(self):
        if self.results_pending:
            raise RuntimeError('native group has unretained section results')
        self.group_key = None

    @contextmanager
    def materialized(self):
        if (not self.active or self.group_key is not None or self.results_pending
                or any(branch.pending is not None for branch in self.branches.values())):
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
        self.collector.exit()
        for branch in self.branches.values():
            branch.close()
        self.branches.clear()


class _ReconstructionBoundary:
    """Switch only after consume_recovery has verified the retained prefix."""
    def __init__(self, progress, driver, parallel, target):
        self.progress, self.driver, self.parallel, self.target = progress, driver, parallel, target

    def update(self, stage, completed=0, total=None, **kwargs):
        if not self.parallel.active and stage == 'root-native-records':
            driver = self.driver
            if (completed != self.target or driver.counters.records_seen != self.target
                    or getattr(driver, '_frankie_reconstruction_checkpoint', None) is not None):
                raise ValueError('parallel activation requires the exact verified reconstruction boundary')
            from frankie_box_prepare_trading_day import save_new, witness
            checkpointer = driver.checkpointer
            receipt_path = checkpointer.checkpoint_dir.parent / 'reconstruction-receipt.json'
            import json
            receipt = json.loads(receipt_path.read_bytes())
            if (receipt.get('records') != self.target
                    or receipt.get('adapter_and_exact_ledger_prefixes_verified') is not True):
                raise ValueError('verified reconstruction receipt required before parallel calculations')
            driver.adapter.assert_groups_closed()
            driver._frankie_parallel_boundary = dict(
                completed_mbo_records=self.target,
                reconstruction_receipt=witness(receipt_path),
                rule='serial reconstruction verified before any parallel group or new source record')
            # This is an explicit interval save outside NativeReplayDriver.maybe_save:
            # match the continuation counter that FullCheckpointer serializes.
            advances_save_counter = self.target > 0 and checkpointer.sequence >= 0
            checkpoint = checkpointer._write(
                driver.adapter, completed_mbo_records=self.target,
                event_group_open=False, controller_state=None, locked=False)
            if advances_save_counter:
                driver.counters.save_points += 1
            self.parallel.start()
            transition = dict(
                schema='FRANKIE_PARALLEL_BOUNDARY_TRANSITION_V1',
                **driver._frankie_parallel_boundary,
                checkpoint_hash=checkpoint['checkpoint_hash'],
                execution_policy=driver._frankie_parallel_policy,
                workers_started=True, new_records_processed_at_transition=0)
            save_new(checkpointer.checkpoint_dir.parent / 'parallel-transition-receipt.json', transition)
        if self.progress is not None:
            return self.progress.update(stage, completed, total, **kwargs)


def consume_after_reconstruction(consume, driver, records, total, progress, checkpoint, descriptor, parallel):
    reconstruction = getattr(driver, '_frankie_reconstruction_checkpoint', None)
    if reconstruction is None:
        parallel.start()
        consume(driver, records, total, progress, checkpoint, descriptor)
        return
    target = reconstruction['completed_mbo_records']
    boundary = _ReconstructionBoundary(progress, driver, parallel, target)
    consume(driver, records, total, boundary, checkpoint, descriptor)
    if not parallel.active:
        raise ValueError('source ended before the verified parallel activation boundary')
