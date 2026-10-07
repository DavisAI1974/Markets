"""CPU placement for the trading-day ingest (Greg, 2026-10-07 night: "Including ingest. Basically anything using a cpu to do
its work": every ingest process and pool pinned to its CPUs, physical-core aware, nothing idle, a dead worker never
stops a stage).

The ingest day process runs under `taskset -c <its booking>` (frankie_box_cores.py run). Inside it:
  lane()           the booked CPUs: FRANKIE_BOOKED_CPUS / FRANKIE_LANE_CPUS intersected with the affinity the process
                   started with (frankie_box_boss_session.lane_cpus, imported), read ONCE and cached, so the parent
                   pinning itself to its own CPU later never shrinks what its workers are handed;
  placement(n)     the parent CPU and up to n worker CPUs. The parent keeps the lowest booked CPU (the booking's parent
                   CPU, and the CPU the conformance reader's worker_budget reserves for its ordered consumer: cpus[0]);
                   the workers take one hardware thread per physical core first (frankie_box_boss_session.cpu_topology
                   / core_groups, imported, never copied), the parent core's sibling last. Never more workers than
                   booked CPUs less the parent, so no worker shares the parent's CPU (the spread sidecar's "allowed").
  pin_parent()     the calling (main) thread onto the parent CPU (Linux sched_setaffinity(0) names the calling thread);
  lane_affinity()  a context in which the main thread holds the whole lane again: the pinned first-run conformance
                   reader (frankie_journal_reader.worker_budget, gold standard, not edited) sizes its workers from the
                   calling thread's affinity at construction, so it is built inside this context and the parent is
                   pinned back after;
  pinned_pool()    a fork pool pinned one worker per CPU that redoes a dead worker's task and continues with one worker
                   fewer (frankie_box_boss_session._PinnedPool, imported); a plain fork pool with the reason when the
                   helper cannot be imported;
  resilient()      a call retried with one worker fewer when its process pool broke (BrokenProcessPool: a worker died);
                   for pure, re-runnable calls only (the conformance drains: the same inputs, the same claim).
  record()         the CPU map for the progress stream (never the receipt: the receipts' fields are unchanged).

Placement changes WHERE work runs, never what it computes: no value, order, byte, hash or identity depends on it.

TEMPLATE (session 5, Greg: every ingest pool goes through the shared pin helper deploy/aws/box/frankie_box_lane_pin.py,
which frankie_box_day_external.py already imports; no private copy): lane(), core_order(), placement(), pin_thread()
and record() are now frankie_box_lane_pin.lane_cpus / core_order / placement / pin_thread / record, with the ingest's
one extra rule kept here: never more workers than booked CPUs less the parent (lane_pin.placement cycles past the lane,
which the ingest refuses, so it is called with at most len(lane) - 1). lane_pin has no submit/get pool that survives a
dead worker (its pinned_pool raises on a death; its ordered_map is a generator over one job list, while pass 2/3 and
CompactBuildJournal(executor=) submit block by block), so pinned_pool() keeps frankie_box_boss_session._PinnedPool (the
same never-stop rule) and the record says so; the cross-owner request is in STACKS_PASS_20261007_INGEST.md.
end_pool() is new: every pool stop is bounded (Greg, a2's shard exit hang: terminate() then an unbounded join()): the
workers are given `grace` seconds to end, then SIGKILLed by pid, and the stop is noted with what was done.
"""
import contextlib
import os
import threading
import time

_LANE = None
_HELPER = None
_HELPER_WHY = None
_LP = None
_LP_WHY = None


def _lane_pin():
    """frankie_box_lane_pin (the shared pin helper), or None with the reason kept for record()."""
    global _LP, _LP_WHY
    if _LP is None and _LP_WHY is None:
        try:
            from deploy.aws.box import frankie_box_lane_pin as LP
        except Exception as error:  # noqa: BLE001 - placement is never a reason to stop an ingest
            try:
                import frankie_box_lane_pin as LP          # flat import (the box's deploy/aws/box on sys.path)
            except Exception:  # noqa: BLE001
                _LP_WHY = 'shared pin helper unavailable (%s: %s); local placement' % (type(error).__name__, error)
                return None
        _LP = LP
    return _LP


def _session():
    """frankie_box_boss_session (stdlib-only at import), or None with the reason kept for record()."""
    global _HELPER, _HELPER_WHY
    if _HELPER is None and _HELPER_WHY is None:
        try:
            from deploy.aws.box import frankie_box_boss_session as S
        except Exception as error:  # noqa: BLE001 - placement is never a reason to stop an ingest
            try:
                import frankie_box_boss_session as S          # flat import (the box's deploy/aws/box on sys.path)
            except Exception:  # noqa: BLE001
                _HELPER_WHY = 'placement helper unavailable (%s: %s); plain sorted order' % (type(error).__name__, error)
                return None
        _HELPER = S
    return _HELPER


def _affinity():
    try:
        return sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return list(range(os.cpu_count() or 1))


def lane():
    """The booked CPUs, sorted; cached on the first call of the process."""
    global _LANE
    if _LANE is None:
        LP, S = _lane_pin(), _session()
        try:
            if LP is not None:
                _LANE = list(LP.lane_cpus())
            else:
                _LANE = list(S.lane_cpus()) if S is not None else _affinity()
        except Exception:  # noqa: BLE001
            _LANE = _affinity()
    return list(_LANE)


def core_order(cpus):
    """(cpus one hardware thread per physical core first, then the siblings; basis)."""
    cpus = sorted(cpus)
    LP = _lane_pin()
    if LP is not None:
        try:
            order, basis = LP.core_order(cpus)
            return list(order), 'frankie_box_lane_pin.core_order: ' + basis
        except Exception:  # noqa: BLE001 - the local order below
            pass
    S = _session()
    if S is None:
        return cpus, _HELPER_WHY
    try:
        topology = S.cpu_topology(cpus)
        groups = S.core_groups(cpus, topology) if topology is not None else None
    except Exception as error:  # noqa: BLE001
        return cpus, 'topology helper failed (%s); plain sorted order' % type(error).__name__
    if not groups:
        return cpus, 'topology unreadable; plain sorted order'
    order = []
    for level in range(max(len(g) for g in groups)):
        order.extend(g[level] for g in groups if len(g) > level)
    return order, 'physical-core first: one thread per core, then the siblings (%d cores, %d CPUs)' % (len(groups), len(order))


def placement(workers=None):
    """dict(parent, workers, lane, basis): the parent on the lowest booked CPU, at most len(lane) - 1 workers."""
    cpus = lane()
    parent = cpus[0]
    LP = _lane_pin()
    limit = len(cpus) - 1 if workers is None else max(0, min(int(workers), len(cpus) - 1))
    if LP is not None and limit > 0:
        try:
            coordinator, chosen, basis = LP.placement(limit, cpus)
            if coordinator == parent and parent not in chosen and len(set(chosen)) == len(chosen) == limit:
                return dict(parent=parent, workers=list(chosen), lane=cpus,
                            basis='frankie_box_lane_pin.placement: ' + basis)
        except Exception:  # noqa: BLE001 - the local placement below (same rule)
            pass
    order, basis = core_order(cpus)
    sibling = set()
    S = _session()
    if S is not None:
        try:
            topology = S.cpu_topology(cpus)
            if topology:
                sibling = {c for c in cpus if topology.get(c) == topology.get(parent)} - {parent}
        except Exception:  # noqa: BLE001
            sibling = set()
    rest = [c for c in order if c != parent and c not in sibling] + [c for c in order if c in sibling]
    if workers is not None:
        rest = rest[:max(0, int(workers))]
    return dict(parent=parent, workers=rest, lane=cpus, basis=basis)


def _ranges(cpus):
    S = _session()
    if S is not None:
        try:
            return S.cpu_ranges(cpus)
        except Exception:  # noqa: BLE001
            pass
    return ','.join(str(c) for c in sorted(cpus))


def pin_parent():
    """Pin the calling thread to the parent CPU; the CPU it holds after (None: left as it was)."""
    cpu = lane()[0]
    try:
        os.sched_setaffinity(0, {cpu})
        return cpu
    except (AttributeError, OSError, ValueError):
        return None


@contextlib.contextmanager
def lane_affinity():
    """The calling thread on the whole lane inside the block, its previous affinity restored after."""
    try:
        before = os.sched_getaffinity(0)
    except (AttributeError, OSError):
        yield
        return
    try:
        os.sched_setaffinity(0, set(lane()))
    except (OSError, ValueError):
        pass
    try:
        yield
    finally:
        try:
            os.sched_setaffinity(0, before)
        except (OSError, ValueError):
            pass


class _PlainTask:
    __slots__ = ('result',)

    def __init__(self, result):
        self.result = result

    def ready(self):
        return self.result.ready()


class _PlainPool:
    """The fallback when the pinned pool helper cannot be imported: a fork pool on the inherited affinity (the booking),
    the same submit / get / ready interface, no recovery (the reason is noted by the caller)."""

    def __init__(self, cpus, label, note=None):
        import multiprocessing
        self.label, self.workers_lost, self.tasks_redone = label, 0, 0
        self.started_workers = max(1, len(cpus))
        self.pool = multiprocessing.get_context('fork').Pool(self.started_workers)

    @property
    def workers(self):
        return self.started_workers

    def submit(self, fn, args):
        return _PlainTask(self.pool.apply_async(fn, (args,)))

    def get(self, task):
        return task.result.get()

    def close(self):
        self.pool.close()
        self.pool.join()

    def terminate(self):
        self.pool.terminate()
        self.pool.join()


def pinned_pool(cpus, label, note=None):
    """A fork pool pinned one worker per CPU with dead-worker recovery (frankie_box_boss_session._PinnedPool: a lost task
    is submitted again with its own arguments, the pool continues with one worker fewer, the last tasks run in the
    caller). submit(fn, arg) -> task; task.ready(); get(task) -> fn(arg)'s result; close(); workers. When the helper
    cannot be imported, the plain fork pool on the booking (no recovery), with `fallback` set to the reason."""
    S = _session()
    if S is not None and hasattr(S, '_PinnedPool') and cpus:
        pool = S._PinnedPool(list(cpus), label, note=note)
        pool.fallback = None
        return pool
    pool = _PlainPool(list(cpus), label, note=note)
    pool.fallback = _HELPER_WHY or 'no pinned pool helper; plain fork pool on the booking'
    return pool


def pin_thread(cpu):
    """Pin the calling thread to one CPU (placement only; the lane when refused, else left as it was)."""
    LP = _lane_pin()
    if LP is not None:
        try:
            LP.pin_thread(cpu, lane())
            return
        except Exception:  # noqa: BLE001
            pass
    try:
        os.sched_setaffinity(0, {cpu})
    except (AttributeError, OSError, ValueError):
        pass


def resilient(call, workers, note=None, *, label='pool', retries_at_one=2):
    """call(workers) retried with one worker fewer each time its process pool broke (a worker died); at one worker it is
    retried retries_at_one more times, then the error stands. A real exception from the work itself is never caught.
    Only for pure calls whose re-run makes the same claim from the same inputs."""
    from concurrent.futures.process import BrokenProcessPool
    workers, left = max(1, int(workers)), retries_at_one
    while True:
        try:
            return call(workers)
        except BrokenProcessPool as error:
            if workers <= 1:
                if left <= 0:
                    raise
                left -= 1
            nxt = max(1, workers - 1)
            if note is not None:
                note(dict(phase='worker_lost', label=label, workers_before=workers, workers_now=nxt,
                          error='%s: %s' % (type(error).__name__, str(error)[:200]),
                          rule='a dead worker never stops the stage: the call is redone from its own inputs with one '
                               'worker fewer; the bytes and the claim are the same'))
            workers = nxt


def record(workers=None):
    """The CPU map of this ingest process for the progress stream."""
    p = placement(workers)
    LP = _lane_pin()
    shared = None
    if LP is not None and p['workers']:
        try:
            shared = LP.record(len(p['workers']), p['lane'], what='trading-day ingest')
        except Exception as error:  # noqa: BLE001
            shared = dict(error='%s: %s' % (type(error).__name__, error))
    return dict(phase='cpu_placement', lane_placement=shared, pin_helper='frankie_box_lane_pin' if LP is not None else _LP_WHY,
                pool_helper='frankie_box_boss_session._PinnedPool' if _session() is not None else _HELPER_WHY, lane=_ranges(p['lane']), lane_cpus=len(p['lane']), parent_cpu=p['parent'],
                worker_cpus=p['workers'], worker_cpu_list=_ranges(p['workers']) if p['workers'] else '', basis=p['basis'],
                booking=os.environ.get('FRANKIE_CPU_BOOKING'),
                rule='the parent keeps the lowest booked CPU (the reader reserves it for its ordered consumer); each pool '
                     'worker is pinned to one CPU of the booking, one thread per physical core first; placement only')


def _workers_of(pool):
    """The worker processes of a pool (ingest_cpus.pinned_pool's, a multiprocessing.Pool, a ProcessPoolExecutor)."""
    inner = getattr(pool, 'pool', pool)
    for name in ('_pool', '_processes'):
        held = getattr(inner, name, None)
        if held is None:
            continue
        try:
            return list(held.values()) if isinstance(held, dict) else list(held)
        except Exception:  # noqa: BLE001
            return []
    return []


def end_pool(pool, *, normal=True, grace=60.0, note=None, label='pool'):
    """Stop a pool with a BOUND (Greg, a2's shard exit hang: terminate() caught by an inherited SIGTERM handler, then an
    unbounded join()). normal=True: close() (the workers end after their queued work), else terminate(); either runs in
    a helper thread for at most `grace` seconds; a worker still alive after it is SIGKILLed by pid (a pool's workers
    hold no output of their own: every result the caller kept is already in the caller), then the helper gets `grace`
    more seconds. Never raises; returns (and notes) what was done."""
    import signal
    if pool is None:
        return dict(label=label, outcome='no pool')
    started = time.monotonic()
    workers = _workers_of(pool)
    how = 'close' if normal else 'terminate'
    errors = []

    def stop():
        try:
            getattr(pool, how)()
        except Exception as error:  # noqa: BLE001 - recorded; the stop is still bounded below
            errors.append('%s: %s' % (type(error).__name__, str(error)[:200]))
    helper = threading.Thread(target=stop, name='end-pool-%s' % label, daemon=True)
    helper.start()
    helper.join(grace)
    killed = []
    if helper.is_alive():
        for process in workers + [w for w in _workers_of(pool) if w not in workers]:
            pid = getattr(process, 'pid', None)
            try:
                if pid and process.exitcode is None:
                    os.kill(pid, signal.SIGKILL)
                    killed.append(pid)
            except (OSError, AttributeError, ValueError):
                pass
        helper.join(grace)
    outcome = dict(phase='pool_stopped', label=label, how=how, seconds=round(time.monotonic() - started, 3),
                   bounded_at_s=grace, killed_pids=killed, helper_ended=not helper.is_alive(), errors=errors,
                   rule='every pool stop is bounded: close/terminate gets the grace, then the workers still alive are '
                        'SIGKILLed by pid; nothing the caller holds is lost')
    if (killed or errors or helper.is_alive()) and note is not None:
        try:
            note(outcome)
        except Exception:  # noqa: BLE001
            pass
    return outcome
