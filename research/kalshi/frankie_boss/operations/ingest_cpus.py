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
                   fewer (frankie_box_boss_session._PinnedPool, imported); None when the helper cannot be imported (the
                   caller keeps its plain pool, with the reason noted);
  resilient()      a call retried with one worker fewer when its process pool broke (BrokenProcessPool: a worker died);
                   for pure, re-runnable calls only (the conformance drains: the same inputs, the same claim).
  record()         the CPU map for the progress stream (never the receipt: the receipts' fields are unchanged).

Placement changes WHERE work runs, never what it computes: no value, order, byte, hash or identity depends on it.
"""
import contextlib
import os

_LANE = None
_HELPER = None
_HELPER_WHY = None


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
        S = _session()
        try:
            _LANE = list(S.lane_cpus()) if S is not None else _affinity()
        except Exception:  # noqa: BLE001
            _LANE = _affinity()
    return list(_LANE)


def core_order(cpus):
    """(cpus one hardware thread per physical core first, then the siblings; basis)."""
    cpus = sorted(cpus)
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


def pinned_pool(cpus, label, note=None):
    """A fork pool pinned one worker per CPU with dead-worker recovery (frankie_box_boss_session._PinnedPool: a lost task
    is submitted again with its own arguments, the pool continues with one worker fewer, the last tasks run in the
    caller), or None when the helper is unavailable. submit(fn, arg) -> task; get(task) -> fn(arg)'s result."""
    S = _session()
    if S is None or not hasattr(S, '_PinnedPool') or not cpus:
        return None
    return S._PinnedPool(list(cpus), label, note=note)


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
    return dict(phase='cpu_placement', lane=_ranges(p['lane']), lane_cpus=len(p['lane']), parent_cpu=p['parent'],
                worker_cpus=p['workers'], worker_cpu_list=_ranges(p['workers']) if p['workers'] else '', basis=p['basis'],
                booking=os.environ.get('FRANKIE_CPU_BOOKING'),
                rule='the parent keeps the lowest booked CPU (the reader reserves it for its ordered consumer); each pool '
                     'worker is pinned to one CPU of the booking, one thread per physical core first; placement only')
