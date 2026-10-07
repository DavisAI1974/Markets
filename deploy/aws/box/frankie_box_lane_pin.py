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
  ordered_map()    the pinned fork pool the data/search pieces use: ordered results, bounded in-flight window, and a
                   dead worker never hangs or stops the stage (its lost task is redone, the window shrinks by one;
                   section note at the end);
  record()         the CPU map for the piece's receipt (lane, coordinator, workers, basis), projected by
                   frankie_box_workflow_inspection.
  end_pool() / end_executor()  (session 5, 2026-10-07) the bounded end of a pool, one shared rule for every caller
                   that holds a pool (ordered_map's cleanup, pinned_pool holders, operations/ingest_cpus.end_pool):
                   terminate (or close), join up to STOP_JOIN_SECONDS, SIGKILL the survivors by pid, join again
                   bounded, every kill listed in the report (report['stop_kills'] = [{pid, cpu, at, exit_code}], the
                   shape of report['worker_deaths']); multiprocessing.Pool.terminate() itself joins each worker without
                   a bound, which is where a worker that swallowed SIGTERM hung the a2 run;
  RedoPool         (session 5) the submit/get shape of ordered_map's dead-worker rule over pinned_pool: apply_async()
                   handles whose get() polls, redoes a task whose worker died (attempts, then the coordinator) and
                   never hangs; end() is end_pool;
  reset_worker_sigterm()  run first by every process initializer here: SIGTERM back to its default action in the worker,
                   so a handler inherited from the parent (the ROOT's save flag) cannot keep a worker alive through
                   terminate() (the a2 shard exit hang, 2026-10-07 22:36Z, E2E_ONE_DAY_20231018.md sessions 4-5);
  exclude_sibling= (keyword on placement / pinned_pool / executor / ordered_map / record, default False: every caller
                   unchanged) leaves the coordinator's hyperthread sibling OUT of the worker set, the whole physical
                   core to a serial consumer as the ROOT does; record() lists the choice (sibling_idle, idle_cpus).

Placement changes WHERE work runs, never what it computes: no value, order, hash or identity depends on it.
"""
import os
import signal
import threading
import time

_LANE = None
POLL_SECONDS = 30.0
STOP_JOIN_SECONDS = 10.0    # end_pool / end_executor / ordered_map's cleanup: the most a join waits after terminate(),
                            # then SIGKILL and one more join of the same bound (frankie_box_boss_session.STOP_JOIN_SECONDS)


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


def _coordinator_siblings(order, coordinator):
    """(the coordinator's sibling hardware threads within `order`, topology known?); never raises."""
    try:
        topology = _session().cpu_topology(order)
    except Exception:  # noqa: BLE001
        return set(), False
    if not topology:
        return set(), False
    return {c for c in order if topology.get(c) == topology.get(coordinator)} - {coordinator}, True


def _place(workers, cpus, exclude_sibling):
    """placement()'s work plus the CPUs it set aside: (coordinator, [worker cpus], basis, [idle cpus])."""
    order, basis = core_order(cpus)
    coordinator = order[0]
    idle = []
    if exclude_sibling:
        sibling, known = _coordinator_siblings(order, coordinator)
        others = [c for c in order[1:] if c not in sibling]
        if sibling and others:
            idle = sorted(sibling)
            rest = others if workers < len(others) + 1 else [coordinator] + others
            basis += "; the coordinator's sibling thread%s %s left idle (whole core for the coordinator)" % (
                's' if len(idle) > 1 else '', ','.join(str(c) for c in idle))
        elif sibling:
            # a single-core lane: nothing but the sibling to work on, so it stays a worker CPU (never idle, noted)
            rest = order[1:] if workers < len(order) else order
            basis += "; sibling exclusion requested but the lane holds no other core: the sibling %s stays a worker CPU" % (
                ','.join(str(c) for c in sorted(sibling)))
        else:
            rest = order[1:] if workers < len(order) else order
            basis += '; sibling exclusion requested: ' + (
                'the coordinator has no sibling in the lane' if known else 'topology unreadable, no CPU set aside')
    elif workers < len(order):
        sibling, _ = _coordinator_siblings(order, coordinator)
        rest = [c for c in order[1:] if c not in sibling] + [c for c in order[1:] if c in sibling]
    else:
        rest = order
    workers = max(1, int(workers))
    return coordinator, [rest[i % len(rest)] for i in range(workers)], basis, idle


def placement(workers, cpus=None, *, exclude_sibling=False):
    """(coordinator cpu, [worker cpus], basis). The coordinator keeps the first CPU of the core order; the workers take
    the other cores' threads first and the coordinator's sibling last; with more workers than CPUs they cycle.
    exclude_sibling=True (session 5, default off: every caller unchanged) leaves the coordinator's sibling thread(s)
    out of the worker set, the whole physical core to a serial coordinator as the ROOT does; the basis says so, and
    record() lists the idle CPUs. A lane with no other core keeps the sibling as a worker CPU (noted, never idle)."""
    coordinator, worker_list, basis, _ = _place(workers, cpus, exclude_sibling)
    return coordinator, worker_list, basis


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


def reset_worker_sigterm():
    """In a forked worker, before any task: SIGTERM back to its default action (the parent's handler is inherited by the
    fork; the ROOT's save handler only sets a flag, so a worker blocked in a pipe write resumed it after terminate()
    and the unbounded join hung: a2, 2026-10-07 22:36Z). Returns what was done: 'reset' (a handler or SIG_IGN was in
    place), 'default' (nothing to do) or 'kept (<why>)' (not the main thread: end_pool's bounded join and SIGKILL still
    end the worker). Never raises; the parent's own handler is untouched (a different process)."""
    try:
        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            return 'default'
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        return 'reset'
    except (ValueError, OSError, TypeError) as error:
        return 'kept (%s)' % type(error).__name__


def _pool_initializer(cpus, counter, fallback):
    reset_worker_sigterm()          # first, before the pin and before any task (session 5)
    with counter.get_lock():
        turn = counter.value
        counter.value += 1
    pin_thread(cpus[turn % len(cpus)], fallback)


def pinned_pool(context, workers, cpus=None, *, exclude_sibling=False):
    """context.Pool(workers), each worker pinned to its own lane CPU (placement); respawn-safe, lane fallback. Each
    worker resets SIGTERM to its default action first (reset_worker_sigterm); end it with end_pool (bounded)."""
    lane = list(cpus) if cpus is not None else lane_cpus()
    _, worker_list, _ = placement(workers, lane, exclude_sibling=exclude_sibling)
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


def executor(kind, workers, cpus=None, mp_context=None, *, exclude_sibling=False):
    """('process' | 'thread') executor of `workers`, each worker pinned to its lane CPU (placement). A process worker
    resets SIGTERM to its default action first (reset_worker_sigterm; a thread shares the process's handler, so the
    thread initializer leaves it); end a process executor with end_executor (bounded: shutdown(wait=True) joins each
    worker without a bound)."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    lane = list(cpus) if cpus is not None else lane_cpus()
    _, worker_list, _ = placement(workers, lane, exclude_sibling=exclude_sibling)
    if kind == 'thread':
        return ThreadPoolExecutor(max_workers=workers, initializer=_thread_initializer,
                                  initargs=(tuple(worker_list), [0], threading.Lock(), tuple(lane)))
    import multiprocessing
    context = mp_context or multiprocessing.get_context('fork')
    return ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_pool_initializer,
                               initargs=(tuple(worker_list), context.Value('l', 0), tuple(lane)))


def _worker_cpu(pid):
    """The CPU a live worker is pinned to (its affinity from /proc/<pid>/status; one CPU as an int, several as a sorted
    list), or None when it cannot be read; read before a kill, the entry vanishes once the worker is reaped."""
    try:
        with open('/proc/%d/status' % pid) as handle:
            for line in handle:
                if line.startswith('Cpus_allowed_list:'):
                    cpus = sorted(_parse(line.split(':', 1)[1]))
                    return cpus[0] if len(cpus) == 1 else cpus
    except (OSError, ValueError):
        pass
    return None


def _kill_survivors(processes, kills, at=None):
    """SIGKILL by pid every process of `processes` still alive; one record per kill appended to `kills` (pid, cpu, at,
    exit_code None until reaped); a pid already gone is skipped; never raises."""
    for process in processes:
        pid = getattr(process, 'pid', None)
        try:
            alive = pid and process.exitcode is None
        except (AttributeError, ValueError, OSError):
            alive = bool(pid)
        if not alive:
            continue
        cpu = _worker_cpu(pid)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except OSError as error:
            kills.append(dict(pid=pid, cpu=cpu, at=round(time.time(), 3), exit_code=None, error=str(error)[:200]))
            continue
        kills.append(dict(pid=pid, cpu=cpu, at=round(time.time(), 3), exit_code=None, process=process))


def _record_kills(kills, report, key='stop_kills'):
    for kill in kills:
        process = kill.pop('process', None)
        if process is not None:
            try:
                kill['exit_code'] = process.exitcode
            except (AttributeError, ValueError, OSError):
                pass
    if report is not None:
        report.setdefault(key, []).extend(kills)
    return kills


def end_pool(pool, grace=None, report=None, *, normal=False, label='pool'):
    """End a multiprocessing Pool with a BOUND (session 5, 2026-10-07; a2's shard exit hang: terminate() swallowed by an
    inherited SIGTERM handler, then an unbounded join). terminate() (or close() when normal=True: the workers end
    after their queued work) runs in a helper thread for at most `grace` seconds (STOP_JOIN_SECONDS by default; Pool
    .terminate() itself joins every worker without a bound); a worker still alive after that is SIGKILLed by pid and
    the helper gets `grace` more seconds; then pool.join() (immediate once the helper ended). Every kill is listed in
    report['stop_kills'] ({pid, cpu, at, exit_code}: the shape of ordered_map's report['worker_deaths']), a helper
    still running after the second bound in report['stop_incomplete'] (left to end on its own, never waited for).
    A pool worker holds no output of its own (every result the caller kept is already in the caller), so a kill loses
    nothing the caller has. Never raises; returns dict(label, how, seconds, kills, joined, errors). One shared rule for
    every caller that holds a pool: ordered_map's cleanup, pinned_pool holders, operations/ingest_cpus.end_pool."""
    bound = STOP_JOIN_SECONDS if grace is None else max(0.0, float(grace))
    if pool is None:
        return dict(label=label, how=None, seconds=0.0, kills=[], joined=True, errors=[], outcome='no pool')
    started = time.monotonic()
    before = list(getattr(pool, '_pool', None) or [])
    how = 'close' if normal else 'terminate'
    errors = []

    def stop():
        try:
            getattr(pool, how)()
        except Exception as error:  # noqa: BLE001 - recorded; the end stays bounded below
            errors.append('%s: %s' % (type(error).__name__, str(error)[:200]))
    helper = threading.Thread(target=stop, name='frankie-end-%s' % label, daemon=True)
    helper.start()
    helper.join(bound)
    kills = []
    if helper.is_alive():
        # workers the pool's own handler forked before terminate() stopped it are in pool._pool now, not in `before`
        current = list(getattr(pool, '_pool', None) or [])
        _kill_survivors(before + [p for p in current if p not in before], kills)
        helper.join(bound)
    joined = not helper.is_alive()
    if joined:
        try:
            pool.join()
        except Exception as error:  # noqa: BLE001
            errors.append('join: %s: %s' % (type(error).__name__, str(error)[:200]))
    _record_kills(kills, report)
    if not joined and report is not None:
        report.setdefault('stop_incomplete', []).append(dict(
            label=label, at=round(time.time(), 3), waited_seconds=round(2 * bound, 3),
            note='%s() still running after the kills; left to end on its own, not waited for' % how))
    return dict(label=label, how=how, seconds=round(time.monotonic() - started, 3), kills=kills, joined=joined,
                errors=errors)


def end_executor(pool_executor, grace=None, report=None, *, label='executor'):
    """End a concurrent.futures ProcessPoolExecutor with a BOUND (session 5): shutdown(wait=False, cancel_futures=True)
    (its wait=True joins the manager thread, which waits for every running task and joins each worker without a
    bound), terminate() every live worker (SIGTERM: the default action after reset_worker_sigterm), join them up to
    `grace` seconds in all (STOP_JOIN_SECONDS by default), SIGKILL the survivors by pid and join again bounded, then
    the manager thread bounded. Kills are listed in report['stop_kills'] ({pid, cpu, at, exit_code}); a running task's
    future ends BrokenProcessPool from the executor itself. A ThreadPoolExecutor (no processes) just gets the
    shutdown. Never raises; returns dict(label, seconds, kills, joined, errors)."""
    bound = STOP_JOIN_SECONDS if grace is None else max(0.0, float(grace))
    started = time.monotonic()
    errors, kills = [], []
    if pool_executor is None:
        return dict(label=label, seconds=0.0, kills=[], joined=True, errors=[], outcome='no executor')
    processes = list((getattr(pool_executor, '_processes', None) or {}).values())
    try:
        pool_executor.shutdown(wait=False, cancel_futures=True)
    except Exception as error:  # noqa: BLE001
        errors.append('shutdown: %s: %s' % (type(error).__name__, str(error)[:200]))
    if processes:
        for process in processes:
            try:
                if process.exitcode is None:
                    process.terminate()
            except (AttributeError, ValueError, OSError) as error:
                errors.append('terminate %s: %s' % (getattr(process, 'pid', None), type(error).__name__))
        deadline = time.monotonic() + bound
        for process in processes:
            try:
                process.join(max(0.0, deadline - time.monotonic()))
            except (AttributeError, ValueError, OSError):
                pass
        _kill_survivors(processes, kills)
        if kills:
            deadline = time.monotonic() + bound
            for process in processes:
                try:
                    process.join(max(0.0, deadline - time.monotonic()))
                except (AttributeError, ValueError, OSError):
                    pass
    manager = getattr(pool_executor, '_executor_manager_thread', None)
    if manager is not None and manager.is_alive():
        manager.join(bound)
    joined = manager is None or not manager.is_alive()
    _record_kills(kills, report)
    if not joined and report is not None:
        report.setdefault('stop_incomplete', []).append(dict(
            label=label, at=round(time.time(), 3), waited_seconds=round(bound, 3),
            note='the executor manager thread still running after the kills; left to end on its own, not waited for'))
    return dict(label=label, seconds=round(time.monotonic() - started, 3), kills=kills, joined=joined, errors=errors)


def record(workers, cpus=None, what=None, *, exclude_sibling=False):
    """The CPU map for a receipt: lane, coordinator, the worker CPUs in hand-out order and the basis; plus (additive,
    session 5) sibling_idle (the exclude_sibling choice) and idle_cpus (the coordinator's sibling threads set aside,
    [] when none)."""
    lane = list(cpus) if cpus is not None else lane_cpus()
    coordinator, worker_list, basis, idle = _place(max(1, workers), lane, exclude_sibling)
    return dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, coordinator=coordinator,
                workers=len(worker_list) if workers else 0, worker_cpus=worker_list if workers else [],
                basis=basis, what=what, at=round(time.time(), 3),
                sibling_idle=bool(exclude_sibling), idle_cpus=idle,
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
# redone tasks are listed in `report` for the piece's receipt. Session 5: the pool's end is bounded (end_pool) and
# every worker it had to SIGKILL is listed in report['stop_kills']; a worker resets SIGTERM to its default action first.

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
                on_retry=None, poll=5.0, attempts=3, report=None, fallback=None, exclude_sibling=False,
                stop_join=None):
    """Yield (job, result) in job order from a pinned fork pool of `workers` (placement), at most `window` tasks in
    flight (default: workers), none submitted once stop() is true (submitted ones drain); on_start(pool) right after
    the workers are forked. See the section note for the dead-worker rule. fallback(job), when given, is the result of
    a task whose workers died `attempts` times (a listed disposition) instead of running it in the coordinator.
    Session 5 (additive): every worker resets SIGTERM to its default action before its first task; the cleanup is
    end_pool (terminate, join up to `stop_join` seconds (STOP_JOIN_SECONDS), SIGKILL the survivors, join again
    bounded), each kill listed in report['stop_kills'] ({pid, cpu, at, exit_code}; [] when none); exclude_sibling
    leaves the coordinator's sibling thread out of the worker CPUs (placement)."""
    import multiprocessing
    from collections import deque
    context = context or multiprocessing.get_context('fork')
    lane = list(cpus) if cpus is not None else lane_cpus()
    workers = max(1, int(workers))
    _, worker_list, _ = placement(workers, lane, exclude_sibling=exclude_sibling)
    report = report if report is not None else {}
    report.setdefault('worker_deaths', [])
    report.setdefault('redone', [])
    report.setdefault('stop_kills', [])
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

    def drain():
        # every loop turn, not only on a poll: a full pipe would make a starting worker wait for the next poll
        while not started.empty():
            token, pid = started.get()
            where[token] = pid
        live = {e[0] for e in pending}
        for token in [t for t in where if t not in live]:
            del where[token]                        # yielded or superseded by a redo: its record is no longer needed

    def recover():
        drain()
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
            drain()
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
        end_pool(pool, stop_join, report, label='ordered_map')


_END = object()


# ---- RedoPool: the submit/get shape of the dead-worker rule (session 5, 2026-10-07, for callers that hold a pool and
# hand it tasks one by one: ingest's segment replay / block encoding). ordered_map is iterator-shaped; this is the same
# rule over pinned_pool's placement: apply_async() returns a handle, handle.get() polls (never an unbounded wait) and a
# task whose worker died is redone (`attempts` pool tries, then once in the coordinator, or fallback(job)). The pool
# replaces a dead worker itself (multiprocessing does; the new one takes the next CPU in turn); in-flight bounding is
# the caller's (ordered_map carries the window). One coordinator thread drives it. end() is end_pool (bounded). -------

class _RedoResult:
    """apply_async's handle: ready() / get(timeout) in the shape of multiprocessing's AsyncResult, polling."""
    def __init__(self, pool, function, job):
        self.pool, self.function, self.job = pool, function, job
        self.token, self.result, self.tries = 0, None, 0

    def ready(self):
        with self.pool._lock:
            self.pool._drain()
        return self.result.ready()

    def get(self, timeout=None):
        """The task's result (its exception re-raised, as a pool result would), polling every `poll` seconds for a dead
        worker; multiprocessing.TimeoutError after `timeout` seconds when given (the task stays outstanding)."""
        import multiprocessing
        deadline = None if timeout is None else time.monotonic() + max(0.0, float(timeout))
        while not self.result.ready():
            wait = self.pool.poll if deadline is None else min(self.pool.poll, max(0.0, deadline - time.monotonic()))
            self.result.wait(wait)
            if self.result.ready():
                break
            with self.pool._lock:
                self.pool._recover()
            if deadline is not None and time.monotonic() >= deadline and not self.result.ready():
                raise multiprocessing.TimeoutError('RedoPool task not done after %.3f s (worker alive; polling)' % timeout)
        with self.pool._lock:
            self.pool._outstanding.pop(self.token, None)
            self.pool._where.pop(self.token, None)
        return self.result.get()


class RedoPool:
    def __init__(self, workers, *, context=None, cpus=None, poll=5.0, attempts=3, report=None, fallback=None,
                 on_retry=None, exclude_sibling=False):
        import multiprocessing
        context = context or multiprocessing.get_context('fork')
        lane = list(cpus) if cpus is not None else lane_cpus()
        workers = max(1, int(workers))
        _, worker_list, _ = placement(workers, lane, exclude_sibling=exclude_sibling)
        self.report = report if report is not None else {}
        for key in ('worker_deaths', 'redone', 'stop_kills'):
            self.report.setdefault(key, [])
        self.poll, self.attempts, self.fallback, self.on_retry = float(poll), int(attempts), fallback, on_retry
        self.workers, self.cpu_map = workers, record(workers, lane, what='RedoPool', exclude_sibling=exclude_sibling)
        self._started = context.SimpleQueue()
        self.pool = context.Pool(workers, initializer=_tracked_initializer,
                                 initargs=(tuple(worker_list), context.Value('l', 0), tuple(lane), self._started))
        self.pool._frankie_pids = _pids(self.pool)
        self._seen, self._dead, self._where, self._suspect = set(_pids(self.pool) or ()), set(), {}, {}
        self._outstanding, self._ticket, self._lock = {}, 0, threading.Lock()

    def apply_async(self, function, job):
        """Submit function(job); the handle's get() polls and redoes the task when its worker died."""
        handle = _RedoResult(self, function, job)
        with self._lock:
            self._submit(handle)
        return handle

    def _submit(self, handle):
        self._ticket += 1
        handle.token = self._ticket
        handle.result = self.pool.apply_async(_tracked_call, ((handle.token, handle.function, handle.job),))
        self._outstanding[handle.token] = handle

    def _drain(self):
        while not self._started.empty():
            token, pid = self._started.get()
            self._where[token] = pid

    def _recover(self):
        """ordered_map's dead-worker rule over the outstanding handles (see its section note)."""
        self._drain()
        now = _pids(self.pool)
        if now is None:
            return
        self._seen.update(now)
        newly = self._seen - now - self._dead
        if newly:
            self._dead.update(newly)
            self.report['worker_deaths'].append(dict(pids=sorted(newly), at=round(time.time(), 3),
                                                     in_flight_after=max(1, self.workers - len(self._dead))))
        if not self._dead:
            return
        latest_started = max((t for t in self._where if t in self._outstanding), default=0)
        for token in sorted(self._outstanding):
            handle = self._outstanding[token]
            if handle.result.ready():
                continue
            pid = self._where.get(token)
            if pid is None and token < latest_started:
                if self._suspect.setdefault(token, time.time()) > time.time() - self.poll:
                    continue
            elif pid not in self._dead:
                continue
            handle.tries += 1
            self.report['redone'].append(dict(job=repr(handle.job)[:300], dead_pid=pid, try_number=handle.tries + 1))
            if self.on_retry is not None:
                self.on_retry(handle.job)
            del self._outstanding[token]
            self._where.pop(token, None)
            self._suspect.pop(token, None)
            if handle.tries >= self.attempts:
                handle.result = _Done(self.fallback or handle.function, handle.job)
            else:
                self._submit(handle)

    def outstanding(self):
        """How many submitted tasks have not been collected by get()."""
        with self._lock:
            return len(self._outstanding)

    def end(self, grace=None, *, normal=False):
        """end_pool on the pool (bounded; kills in report['stop_kills']); returns its outcome."""
        return end_pool(self.pool, grace, self.report, normal=normal, label='RedoPool')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.end()
        return False
