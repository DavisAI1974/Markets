"""Lane CPU placement for the data, search/discovery and day-file pieces (Greg, 2026-10-07 night: "every process/pool/
thread explicitly pinned to its share of the booked lane", physical-core aware, nothing floating or idle).

One place for what search, the native reader, the data export and the day-file builder used to do each in its own way:
  lane_cpus()      the held lane (FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS intersected with this process's affinity, the
                   affinity alone otherwise), read ONCE per process and cached, so a coordinator that later pins itself
                   to its own CPU still hands its workers the whole lane;
  core_order()     the lane's CPUs one hardware thread per physical core first (cores in the order of their first CPU),
                   then the second threads, from frankie_box_boss_session.cpu_topology / core_groups (imported, never
                   copied); the plain sorted list, with the reason, when the topology cannot be read;
  placement(n)     the coordinator CPU (the first CPU of the order) and n worker CPUs: the other cores' threads first,
                   the coordinator's own sibling last, cycling when n exceeds the lane (never idle, never off-lane);
  pinned_pool()    multiprocessing Pool whose workers pin themselves from a shared counter (a respawned worker takes
                   the next CPU in turn instead of blocking on an emptied hand-out queue), with the lane as the
                   fallback affinity when a CPU cannot be set (L-2: a pin never stops a worker);
  wait_result() / iterate_ordered()  result waits that poll and raise when a pool worker died (multiprocessing.Pool
                   replaces a killed worker silently and the task it held never completes: the fix-after item "a dead
                   pinned worker can hang a pool while the heartbeat says running");
  executor()       concurrent.futures ProcessPoolExecutor / ThreadPoolExecutor with the same pinning (a dead process
                   worker already raises BrokenProcessPool there);
  record()         the CPU map for the piece's receipt (lane, coordinator, workers, basis), projected by
                   frankie_box_workflow_inspection.

Placement changes WHERE work runs, never what it computes: no value, order, hash or identity depends on it.
"""
import os
import threading
import time

_LANE = None
POLL_SECONDS = 30.0


def _session():
    try:
        import frankie_box_boss_session as S
    except ImportError:
        from deploy.aws.box import frankie_box_boss_session as S
    return S


def _parse(text):
    listed = set()
    for part in (text or '').split(','):
        part = part.strip()
        if part:
            low, _, high = part.partition('-')
            listed.update(range(int(low), int(high or low) + 1))
    return listed


def lane_cpus(refresh=False):
    """The held lane's CPUs, sorted; cached on the first call of the process (see the module note)."""
    global _LANE
    if _LANE is None or refresh:
        try:
            affinity = set(os.sched_getaffinity(0))
        except (AttributeError, OSError):
            affinity = set(range(os.cpu_count() or 1))
        lane = None
        for name in ('FRANKIE_LANE_CPUS', 'FRANKIE_BOOKED_CPUS'):
            try:
                listed = _parse(os.environ.get(name))
            except ValueError:
                continue
            if listed & affinity:
                lane = sorted(listed & affinity)
                break
        _LANE = lane or sorted(affinity)
    return list(_LANE)


def core_order(cpus=None):
    """(cpus ordered one thread per physical core first, then the second threads; basis)."""
    cpus = sorted(cpus if cpus is not None else lane_cpus())
    try:
        S = _session()
        topology = S.cpu_topology(cpus)
        groups = S.core_groups(cpus, topology) if topology is not None else None
    except Exception as error:  # noqa: BLE001 - placement is never a reason to stop a piece
        groups = None
        why ='topology helper unavailable (%s); plain list order' % type(error).__name__
    else:
        why = 'topology unreadable; plain list order'
    if not groups:
        return cpus, why
    order = []
    for level in range(max(len(g) for g in groups)):
        order.extend(g[level] for g in groups if len(g) > level)
    return order, 'physical-core spread: one hardware thread per core first, then the siblings (%d cores, %d CPUs)' % (
        len(groups), len(order))


def placement(workers, cpus=None):
    """(coordinator cpu, [worker cpus], basis). The coordinator keeps the first CPU of the core order; the workers take
    the other cores' threads first and the coordinator's sibling last; with more workers than CPUs they cycle."""
    order, basis = core_order(cpus)
    coordinator = order[0]
    if workers < len(order):
        try:
            topology = _session().cpu_topology(order)
            sibling = {c for c in order if topology and topology.get(c) == topology.get(coordinator)} - {coordinator}
        except Exception:  # noqa: BLE001
            sibling = set()
        rest = [c for c in order[1:] if c not in sibling] + [c for c in order[1:] if c in sibling]
    else:
        rest = order
    workers = max(1, int(workers))
    return coordinator, [rest[i % len(rest)] for i in range(workers)], basis


def pin_thread(cpu, fallback=None):
    """Pin the calling thread to one CPU; on refusal the fallback set (the lane), else leave it as it is. The CPU it
    ended on (or None)."""
    for target in ({cpu} if cpu is not None else None, set(fallback) if fallback else None):
        if not target:
            continue
        try:
            os.sched_setaffinity(0, target)
            return cpu if target == {cpu} else None
        except (OSError, ValueError):
            continue
    return None


def pin_native_thread(cpu, fallback=None):
    """The same for a non-main thread (threading.get_native_id: sched_setaffinity(0) names the calling thread on Linux,
    so this is pin_thread under its own name for the thread pools' initializers)."""
    return pin_thread(cpu, fallback)


def _pool_initializer(cpus, counter, fallback):
    with counter.get_lock():
        turn = counter.value
        counter.value += 1
    pin_thread(cpus[turn % len(cpus)], fallback)


def pinned_pool(context, workers, cpus=None):
    """context.Pool(workers), each worker pinned to its own lane CPU (placement); respawn-safe, lane fallback."""
    lane = list(cpus) if cpus is not None else lane_cpus()
    _, worker_list, _ = placement(workers, lane)
    pool = context.Pool(workers, initializer=_pool_initializer,
                        initargs=(tuple(worker_list), context.Value('l', 0), tuple(lane)))
    pool._frankie_pids = _pids(pool)
    return pool


def _pids(pool):
    try:
        return {p.pid for p in getattr(pool, '_pool', [])}
    except Exception:  # noqa: BLE001
        return None


def check_alive(pool):
    """Raise when a worker of the pool died since it started (a replaced worker has a new pid)."""
    started, now = getattr(pool, '_frankie_pids', None), _pids(pool)
    if started and now is not None and not now <= started:
        raise RuntimeError('a pinned pool worker died (pids %s replaced); the task it held never completes, so the '
                           'piece stops here instead of waiting forever; saved operations resume'
                           % sorted(started - now))


def wait_result(pool, result, poll=POLL_SECONDS):
    """result.get(), polling every `poll` seconds and raising when a worker died."""
    while not result.ready():
        result.wait(poll)
        if not result.ready():
            check_alive(pool)
    return result.get()


def iterate_ordered(pool, iterator, poll=POLL_SECONDS):
    """Yield an ordered pool.imap iterator's items, polling and raising when a worker died."""
    import multiprocessing
    while True:
        try:
            item = iterator.next(poll)
        except StopIteration:
            return
        except multiprocessing.TimeoutError:
            check_alive(pool)
            continue
        yield item


def _thread_initializer(cpus, counter, lock, fallback):
    with lock:
        turn = counter[0]
        counter[0] += 1
    pin_native_thread(cpus[turn % len(cpus)], fallback)


def executor(kind, workers, cpus=None, mp_context=None):
    """('process' | 'thread') executor of `workers`, each worker pinned to its lane CPU (placement)."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    lane = list(cpus) if cpus is not None else lane_cpus()
    _, worker_list, _ = placement(workers, lane)
    if kind == 'thread':
        return ThreadPoolExecutor(max_workers=workers, initializer=_thread_initializer,
                                  initargs=(tuple(worker_list), [0], threading.Lock(), tuple(lane)))
    import multiprocessing
    context = mp_context or multiprocessing.get_context('fork')
    return ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_pool_initializer,
                               initargs=(tuple(worker_list), context.Value('l', 0), tuple(lane)))


def record(workers, cpus=None, what=None):
    """The CPU map for a receipt: lane, coordinator, the worker CPUs in hand-out order and the basis."""
    lane = list(cpus) if cpus is not None else lane_cpus()
    coordinator, worker_list, basis = placement(max(1, workers), lane)
    return dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, coordinator=coordinator,
                workers=len(worker_list) if workers else 0, worker_cpus=worker_list if workers else [],
                basis=basis, what=what, at=round(time.time(), 3),
                rule='placement only: values, order, hashes and identities never depend on it; a refused pin falls '
                     'back to the lane, never off it')


# ---- additions for the classroom and the BOSS teacher stage (2026-10-07 night; merged from the retired
# frankie_box_lane_pinning.py; nothing above changed) ----------------------------------------------------------------
# A serial consumer on a WHOLE core: its own CPU plus that core's sibling threads, so the helper threads it starts after
# it is pinned (a ProcessPoolExecutor's manager and call-queue feeder) land on the sibling instead of on its own CPU.
# Lazily sized CPU lists elsewhere read the CALLING thread's affinity (os.sched_getaffinity(0)), so a caller pins its
# consumer only after every list it depends on was read, and restores the mask before any later pool is sized.

def consumer_core(cpus=None):
    """(consumer cpu, [its sibling threads in the lane], basis): the consumer is the lane's first CPU (the CPU the
    journal reader and the shared timeline's decode leave free: they take lane[1:])."""
    lane = sorted(cpus if cpus is not None else lane_cpus())
    if not lane:
        return None, [], 'no CPU in the lane'
    consumer = lane[0]
    try:
        topology = _session().cpu_topology(lane)
    except Exception as error:  # noqa: BLE001
        return consumer, [], 'topology helper unavailable (%s); siblings unknown' % type(error).__name__
    if topology is None:
        return consumer, [], 'topology unreadable; siblings unknown'
    return consumer, sorted(c for c in lane if c != consumer and topology[c] == topology[consumer]), \
        'frankie_box_boss_session.cpu_topology (physical_package_id, core_id)'


def current_mask():
    """The calling thread's affinity (a set), or None when it cannot be read."""
    try:
        return set(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return None


def pin_core(cpus):
    """Pin the calling thread to the set `cpus`, read back. Three outcomes, returned, never raised: pinned; fallback (the
    OS refused or the read-back differs: the thread keeps the mask it reads back); unsupported."""
    wanted = set(cpus)
    if not hasattr(os, 'sched_setaffinity'):
        return dict(outcome='unsupported', cpus=sorted(wanted))
    try:
        os.sched_setaffinity(0, wanted)
        got = set(os.sched_getaffinity(0))
    except OSError as error:
        return dict(outcome='fallback', cpus=sorted(wanted), reason='the OS refused (%s); the mask is unchanged' % error)
    if got != wanted:
        return dict(outcome='fallback', cpus=sorted(wanted), read_back=sorted(got))
    return dict(outcome='pinned', cpus=sorted(wanted))


def restore_mask(mask):
    """Give the calling thread back the mask it had; the outcome (restored / fallback / nothing_to_restore)."""
    if mask is None or not hasattr(os, 'sched_setaffinity'):
        return 'nothing_to_restore'
    try:
        os.sched_setaffinity(0, set(mask))
    except OSError:
        return 'fallback'
    return 'restored'


def generators_started(streams):
    """True when every stream's `rows` generator has started (each lazily sized CPU list inside it was read on the
    caller's mask); None when that cannot be told (the caller then does not pin)."""
    import inspect
    try:
        return all(inspect.getgeneratorstate(stream.rows) != inspect.GEN_CREATED for stream in streams)
    except (AttributeError, TypeError):
        return None


# ---- ordered_map: the pinned fork pool that never hangs and never stops on a dead worker (Greg, 2026-10-07 night:
# "a dead pool worker must never stop a stage or hang it; redo the lost task and continue with one less worker") ----
# multiprocessing.Pool replaces a killed worker silently and the task it held never completes. Here every task records
# (token, pid) on a shared queue the moment it starts; every `poll` seconds the coordinator compares the pool's pids
# with every pid it has seen: a pid that vanished is a dead worker, and each unfinished task that started on it (or, by
# the pool's first-in-first-out hand-out, was taken before a later task that did start) is LOST. A lost task is
# submitted again (on_retry(job) first, e.g. to set a half-written output aside), the in-flight window shrinks by one
# per death (one less worker), and after `attempts` pool tries it runs once in the coordinator itself. Results are
# yielded in job order, each exactly once; an exception raised BY a task still propagates as before. The deaths and
# redone tasks are listed in `report` for the piece's receipt.

_STARTED = None


def _tracked_initializer(cpus, counter, fallback, started):
    global _STARTED
    _STARTED = started
    _pool_initializer(cpus, counter, fallback)


def _tracked_call(args):
    token, function, job = args
    if _STARTED is not None:
        _STARTED.put((token, os.getpid()))
    return function(job)


class _Done:
    """A result computed in the coordinator (the last try of a task whose workers kept dying)."""
    def __init__(self, function, job):
        try:
            self.value, self.error = function(job), None
        except Exception as error:  # noqa: BLE001 - re-raised by get(), as a pool result would
            self.value, self.error = None, error

    def ready(self):
        return True

    def wait(self, timeout=None):
        return None

    def get(self, timeout=None):
        if self.error is not None:
            raise self.error
        return self.value


def ordered_map(function, jobs, workers, *, context=None, cpus=None, window=None, stop=None, on_start=None,
                on_retry=None, poll=5.0, attempts=3, report=None, fallback=None):
    """Yield (job, result) in job order from a pinned fork pool of `workers` (placement), at most `window` tasks in
    flight (default: workers), none submitted once stop() is true (submitted ones drain); on_start(pool) right after
    the workers are forked. See the section note for the dead-worker rule. fallback(job), when given, is the result of
    a task whose workers died `attempts` times (a listed disposition) instead of running it in the coordinator."""
    import multiprocessing
    from collections import deque
    context = context or multiprocessing.get_context('fork')
    lane = list(cpus) if cpus is not None else lane_cpus()
    workers = max(1, int(workers))
    _, worker_list, _ = placement(workers, lane)
    report = report if report is not None else {}
    report.setdefault('worker_deaths', [])
    report.setdefault('redone', [])
    started = context.SimpleQueue()
    pool = context.Pool(workers, initializer=_tracked_initializer,
                        initargs=(tuple(worker_list), context.Value('l', 0), tuple(lane), started))
    seen = set(_pids(pool) or ())
    dead, where, ticket, suspect = set(), {}, [0], {}
    pending, source = deque(), iter(jobs)
    window = max(1, int(window or workers))

    def submit(entry):
        ticket[0] += 1
        entry[0] = ticket[0]
        entry[2] = pool.apply_async(_tracked_call, ((entry[0], function, entry[1]),))

    def fill():
        while len(pending) < max(1, window - len(dead)) and not (stop and stop()):
            job = next(source, _END)
            if job is _END:
                return
            entry = [0, job, None, 0]
            submit(entry)
            pending.append(entry)

    def recover():
        while not started.empty():
            token, pid = started.get()
            where[token] = pid
        now = _pids(pool)
        if now is None:
            return
        seen.update(now)
        newly = seen - now - dead
        if newly:
            dead.update(newly)
            report['worker_deaths'].append(dict(pids=sorted(newly), at=round(time.time(), 3),
                                                in_flight_after=max(1, window - len(dead))))
        if not dead:
            return
        tokens = {e[0] for e in pending}
        latest_started = max((t for t in where if t in tokens), default=0)
        for entry in pending:
            if entry[2].ready():
                continue
            pid = where.get(entry[0])
            if pid is None and entry[0] < latest_started:
                # taken from the queue (a later task already started) but never recorded: lost only when it stays so
                # for a whole poll (a live worker records its start within microseconds of taking it)
                if suspect.setdefault(entry[0], time.time()) > time.time() - poll:
                    continue
            elif pid not in dead:
                continue
            entry[3] += 1
            report['redone'].append(dict(job=repr(entry[1])[:300], dead_pid=pid, try_number=entry[3] + 1))
            if on_retry is not None:
                on_retry(entry[1])
            if entry[3] >= attempts:
                entry[2] = _Done(fallback or function, entry[1])
            else:
                submit(entry)

    try:
        if on_start is not None:
            on_start(pool)
        fill()
        while pending:
            entry = pending[0]
            while not entry[2].ready():
                entry[2].wait(poll)
                if not entry[2].ready():
                    recover()
            pending.popleft()
            value = entry[2].get()
            yield entry[1], value
            fill()
    finally:
        pool.terminate()
        pool.join()


_END = object()
