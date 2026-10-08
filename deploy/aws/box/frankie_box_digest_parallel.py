"""Parallel DIGEST_V6 table writer: the same bytes as frankie_box_digest_stream.write_table, built on many cores.

The serial writer runs its passes over a table on one core. Here each pass is split into contiguous row ranges
("parts") on pinned helper processes. What crosses a part boundary is small and exact: the planner's and the
verifier's row-to-row state (previous row, last value / integer / list head per column), and the table-wide facts
(column order, derived and constant columns, scales, dictionary counts and first-occurrence numbering, separator). The
coordinator folds those in part order, so every cell, the header and the dictionary are what the serial writer
produces. frankie_box_digest_stream and frankie_box_digest_render are not modified.

Lean on disk (2026-09-28: two side builds filled the 2 TB disk with per-row intermediates). Passes: snapshot (columns
and seeds, nothing written), plan (cells planned and dictionary candidates counted in one read; no plan is stored;
counts are keyed by the sha256 of the candidate's text, so a part's counts are a few dozen bytes per distinct key),
merge (table-wide counts and first-occurrence numbering, on digests), final (each part planned again from its seed and
written as row text, plus the text of the dictionary entries it numbers first), copy (the parts appended to the table,
each part deleted as soon as it is appended), inverse proof (streamed per part). Every helper stops cleanly before the
scratch filesystem's free space falls under DISK_RESERVE. Each pass is a save point keyed by the code it depends on.

Row sources are described, not passed: ('members', database, group keys) or ('rows', database, query, parameters,
excluded, start, count), so each helper reads its own range of a finished sources.sqlite read-only.
"""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import contextlib
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import pickle
import re
import shutil
import sqlite3
import sys
import time
import zlib

BOX = Path(__file__).resolve().parent
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))
import frankie_box_digest_render as DG  # noqa: E402
import frankie_box_digest_stream as TS  # noqa: E402


# ---- helpers ------------------------------------------------------------------------------------------------------

POOL_PIN_WAIT_SECONDS = 5.0      # a helper's wait for its CPU before it takes the pool's whole CPU set instead


def _init(box, cpus, fallback=()):
    """Each helper takes one CPU of the pool's hand-out (in the order given: one thread per physical core first) and is
    pinned to it. A helper that finds the hand-out empty never blocks there: it is pinned to the pool's whole CPU set."""
    if box not in sys.path:
        sys.path.insert(0, box)
    import queue as queue_module
    try:
        cpu = {cpus.get(timeout=POOL_PIN_WAIT_SECONDS)}
    except queue_module.Empty:
        cpu = set(fallback) or set(os.sched_getaffinity(0))
    os.sched_setaffinity(0, cpu)


POOL_CLOSE_GRACE_SECONDS = 60.0  # _bounded_executor_stop: a graceful shutdown (idle helpers exit at once) may take this
POOL_STOP_SECONDS = 10.0         # then terminate()+join, then kill()+join, each bounded


STOP_FILE_ENV = 'FRANKIE_DIGEST_STOP_FILE'   # session 8: the render's LAWFUL stop point (the CPU watchdog's resize, or an operator)
STOPPED_EXIT = 75                            # the same code every saved Frankie job exits with (frankie_box_cores.SAVED_EXIT)


class DigestStopped(SystemExit):
    """The render stopped at a pass boundary on FRANKIE_DIGEST_STOP_FILE: every finished pass is in scratch/passes.pkl,
    the pass that would have started next was not started; the same command again resumes there (exit 75)."""

    def __init__(self, table, label, path):
        super().__init__(STOPPED_EXIT)
        self.table, self.label, self.path = table, label, path


def stop_requested(environ=None):
    """The stop file's path when FRANKIE_DIGEST_STOP_FILE names an existing file, else None. Checked ONLY between passes
    (frankie_box_digest_parallel.step and before the copy): a pass in flight always finishes and saves first, so
    nothing is redone on the resume; the wait for the stop is at most one pass. Orchestration only: not in _pass_code."""
    path = (os.environ if environ is None else environ).get(STOP_FILE_ENV)
    return path if path and Path(path).is_file() else None


def _stage_phase(phase, units_done=None, units_total=None, unit=None, every=None):
    """The stage heartbeat's phase file (frankie_box_stage_progress.report_phase: a no-op outside a Run.child stage;
    session 6: the digest, ROOT process 4, showed its stage name and no units). Never changes a table: an import or
    write failure is swallowed as report_phase swallows its own. Orchestration only: not in _code_identity."""
    try:
        import frankie_box_stage_progress as _SP
        _SP.report_phase(phase, units_done=units_done, units_total=units_total, unit=unit, every=every)
    except Exception:  # noqa: BLE001
        pass


def _bounded_executor_stop(executor, graceful):
    """End a ProcessPoolExecutor without an unbounded wait (session 6; the rule of frankie_box_boss_session.
    _bounded_pool_stop and lane_pin's dead-worker handling: never hang). graceful = shutdown(wait=True) on a daemon
    thread given POOL_CLOSE_GRACE_SECONDS (idle helpers exit at once; a helper mid-task finishes it); then every live
    helper process is terminated and joined within POOL_STOP_SECONDS, then killed and joined within POOL_STOP_SECONDS.
    Returns None when the executor ended by itself, else what had to be done (pids, at, exit codes). The helpers' only
    output is the executor's result pipe (every pass writes its part files itself and is redone whole on a loss), so a
    kill loses nothing durable. The spawn helpers never inherited the ROOT's SIGTERM flag handler (exec resets it)."""
    import threading
    processes = list((getattr(executor, '_processes', None) or {}).values())

    def alive(process):
        # race-free: the executor's own management thread may reap a helper first, after which
        # multiprocessing.Process.exitcode/is_alive stay None/True for this handle (popen_fork.poll swallows the
        # ChildProcessError); the kernel's answer is the record
        try:
            os.kill(process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return Path('/proc/%d' % process.pid).is_dir() and 'Z' not in (
            (Path('/proc/%d/stat' % process.pid).read_text().rsplit(')', 1)[-1].split() or ['?'])[0])

    def body():
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        except Exception:  # noqa: BLE001 - an executor already broken; the processes are still checked below
            pass
    thread = threading.Thread(target=body, name='digest-pool-stop', daemon=True)
    thread.start()
    thread.join(POOL_CLOSE_GRACE_SECONDS if graceful else POOL_STOP_SECONDS)
    if not thread.is_alive():
        return None
    acted = dict(graceful=graceful, terminated=[], killed=[], at=round(time.time(), 3), stop_thread_still_waiting=True)
    for process in processes:
        if alive(process):
            process.terminate()
            process.join(POOL_STOP_SECONDS)
            acted['terminated'].append(dict(pid=process.pid, exit_code=process.exitcode, alive_after=alive(process)))
    for process in processes:
        if alive(process):
            process.kill()
            process.join(POOL_STOP_SECONDS)
            acted['killed'].append(dict(pid=process.pid, exit_code=process.exitcode, alive_after=alive(process),
                                        exit_code_note=None if process.exitcode is not None else
                                        'reaped by the executor\'s own thread first; alive_after is the kernel\'s answer'))
    thread.join(POOL_STOP_SECONDS)
    acted['stop_thread_still_waiting'] = thread.is_alive()
    return acted


def _pool(cpus):
    context = multiprocessing.get_context('spawn')
    queue = context.Queue()
    for cpu in cpus:
        queue.put(cpu)
    return ProcessPoolExecutor(max_workers=len(cpus), mp_context=context, initializer=_init,
                               initargs=(str(BOX), queue, tuple(cpus)))


class PinnedPool:
    """The helper processes, one pinned per CPU, shared by every table the digest writes at once (Greg, 2026-10-07:
    every booked CPU busy, every process pinned). map() is pool.map: the results in job order, whatever order the
    helpers finish in, so every pass folds its parts exactly as before; several tables' passes may interleave on the
    helpers, which changes only when a part runs, never what it returns.

    A dead helper never stops or hangs a pass (Greg, 2026-10-07: "continue but with just one less worker"): the
    executor reports it as BrokenProcessPool on every task it held; the pool is started again on one CPU fewer (the
    last of the order, a second hardware thread first) and every task of every caller that had not completed is
    submitted again with its own job. The part functions are pure functions of their job (the plan pass starts from an
    empty count file, _plan_fresh; the final pass truncates its outputs), so a task run twice returns the same result.
    With every helper lost the tasks run in the calling thread. A task's own exception still raises from map()."""

    def __init__(self, cpus, label='digest table helpers', note=None):
        import threading
        self.cpus, self.label, self.note = list(cpus), label, note
        self.started_workers = len(self.cpus)
        self.workers_lost = 0
        self.tasks_redone = 0
        self._lock = threading.RLock()
        self._generation = 0
        self.stop_kills = []              # what _bounded_executor_stop had to do (session 6): terminated/killed pids
        self._executor = _pool(self.cpus) if self.cpus else None

    @property
    def workers(self):
        return len(self.cpus)

    def _submit(self, fn, job):
        from concurrent.futures.process import BrokenProcessPool
        while True:
            with self._lock:
                generation, executor = self._generation, self._executor
                if executor is None:
                    return generation, None
                try:
                    return generation, executor.submit(fn, job)
                except BrokenProcessPool:
                    pass
            self._recover(generation)

    def _recover(self, generation):
        with self._lock:
            if generation != self._generation or self._executor is None:
                return                          # another caller already restarted this generation
            broken, before = self._executor, len(self.cpus)
            self._stop_executor(broken, graceful=False)
            self.cpus = self.cpus[:-1]
            self.workers_lost += before - len(self.cpus)
            self._generation += 1
            self._executor = _pool(self.cpus) if self.cpus else None
        if self.note is not None:
            self.note('%s: a helper exited with work in flight; %s (%d of %d lost so far); its tasks are re-done with the '
                      'same jobs, order and bytes unchanged' % (self.label, ('%d pinned helper(s) left' % len(self.cpus))
                      if self.cpus else 'no helper left: the tasks run in the calling thread', self.workers_lost,
                      self.started_workers))

    def map(self, fn, jobs):
        from concurrent.futures.process import BrokenProcessPool
        jobs = list(jobs)
        slots = [self._submit(fn, job) for job in jobs]
        out = []
        for i, job in enumerate(jobs):
            while True:
                generation, future = slots[i]
                if future is None:
                    out.append(fn(job))
                    break
                try:
                    out.append(future.result())
                    break
                except BrokenProcessPool:
                    self._recover(generation)
                    for k in range(i, len(jobs)):
                        held, pending = slots[k]
                        if pending is None or held == self._generation:
                            continue
                        if pending.done() and not pending.cancelled() and pending.exception() is None:
                            continue            # completed before the loss: its result stands
                        slots[k] = self._submit(fn, jobs[k])
                        with self._lock:
                            self.tasks_redone += 1
        return out

    def record(self):
        return dict(started_workers=self.started_workers, workers=len(self.cpus), workers_lost=self.workers_lost,
                    tasks_redone=self.tasks_redone, cpus=list(self.cpus),
                    stop_kills=list(self.stop_kills))   # additive (session 6): empty when every stop ended by itself

    def _stop_executor(self, executor, graceful):
        """shutdown + join, bounded (_bounded_executor_stop); what had to be terminated or killed is recorded and noted."""
        acted = _bounded_executor_stop(executor, graceful)
        if acted and (acted['terminated'] or acted['killed'] or acted['stop_thread_still_waiting']):
            self.stop_kills.append(acted)
            if self.note is not None:
                self.note('%s: the helper pool did not end within its bound; %d helper(s) terminated, %d killed%s; '
                          'helpers write nothing the proof keeps, nothing lost'
                          % (self.label, len(acted['terminated']), len(acted['killed']),
                             '; its stop thread was left waiting' if acted['stop_thread_still_waiting'] else ''))

    def close(self):
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            self._stop_executor(executor, graceful=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _plan_fresh(job):
    """The plan pass of one part from an empty count file: the coordinator removes it before the pass, and a part re-done
    after its helper died starts from nothing again (sqlite would refuse the existing table)."""
    (Path(job[1]) / 'freq.sqlite').unlink(missing_ok=True)
    return _plan(job)


def _readonly(path):
    import frankie_box_digest_sources as S
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA cache_size=-65536')
    db.create_collation('group_order', S._compare_groups)
    return db


# The pinned crosswalk (frankie_box_bedrock.PIN_COMMIT) names the full-depth ask ladder `book_full.ask_levels_full`
# without the list mark its own carrier gives it ("book_full.bid_levels_full[] / ask_levels_full[] (whole book)"), so
# the whole ask ladder, every FIFO queue of every level, rode each group's member row while the bid ladder is carried
# by its leaf count (Greg, 2026-09-28: not intended). The digest carries it as the bid side is carried: the list path's
# `#count` (the same reducer frankie_box_digest_sources applies to `[]` paths). The ladder stays whole in the layer
# file and the ledger.
MEMBER_LIST_PATHS = {'book_full.ask_levels_full': 'book_full.ask_levels_full[]'}


def _source_rows(spec):
    """The rows of one part, in the order of the whole table's reader (_bedrock_table_job, S._Members, S._Rows), with
    the member path correction MEMBER_LIST_PATHS applied to member rows."""
    import frankie_box_digest_sources as S
    if spec['kind'] == 'inline':          # rows given in the spec itself (comparisons against the serial writer)
        yield from spec['rows']
        return
    if spec['kind'] == 'spool':           # a legacy RowSpool file: its line range, decoded as RowSpool.__iter__ decodes
        from research.kalshi.frankie_boss.c15_journal import unpack
        position = spec['start']
        with open(spec['path'], 'rb') as handle:
            handle.seek(position)
            for line in handle:
                if position >= spec['end']:
                    break
                position += len(line)
                yield unpack(json.loads(line.decode('utf-8')))
        return
    db = _readonly(spec['database'])
    try:
        if spec['kind'] == 'members':
            for key in spec['keys']:
                flat = {}
                for column, payload in db.execute(
                        'SELECT column_name,payload FROM members WHERE group_key=? ORDER BY ordinal', (key,)):
                    value = S._decoded(payload)
                    if column in MEMBER_LIST_PATHS:
                        column, value = MEMBER_LIST_PATHS[column] + '#count', DG._leaf_count(value)
                    value = DG._spell(value)
                    if column in flat:            # only a corrected path can meet a column already read
                        if not DG._same(flat[column], value):
                            raise ValueError('conflicting reduced member column %s in group %s' % (column, key))
                        continue
                    flat[column] = value
                yield DG._nest(flat)
            return
        excluded = spec['excluded']
        cursor = db.execute(spec['query'], tuple(spec['parameters']))
        for _ in range(spec['start']):
            if cursor.fetchone() is None:
                raise ValueError('rows part starts beyond the table')
        for _ in range(spec['count']):
            fetched = cursor.fetchone()
            if fetched is None:
                raise ValueError('rows part shorter than planned')
            row = S._decoded(fetched[0])
            yield {c: DG._spell(v) for c, v in row.items() if c not in excluded} if excluded is not None else row
    finally:
        db.close()


def _fold(state, flat):
    DG.fold(state, flat)


# ---- Session 6 (Greg, 2026-10-08, verbatim: "We stream the data in and get 32 CPUs and workers on this job"; "we only
# do 1 pass. Eliminate the 2nd pass"): fewer decodes of the source rows. A spool table decoded every row five times
# (cross context, snapshot, plan, final, verify: the 496.7 GB full-depth frames of a2, ~29 min per decode on 31
# helpers). Three exact reductions, switched together by ONE run setting, FRANKIE_DIGEST_DECODES = 5 | 4 | 3 | 2 (the
# decodes of a table that feeds a cross-table context; default 2, the floor without a second copy of the spool: the
# dictionary grammar is two-pass, the column set depends on the deepest row and the dictionary on every part's counts,
# so no row's final text exists before the whole table has been seen twice):
#   5  none (the writer as before: cross context, snapshot, plan, final, verify)
#   4  + fuse_context    the cross-table context columns are collected inside the snapshot pass (5 -> 4);
#   3  + canonical_verify the inverse proof compares each parsed-back row with a canonical digest of the source row kept
#                        by the last pass that decoded it (32 bytes a row), instead of decoding the source again (-> 3);
#                        taken only while the canonical form is injective over DG._same's domain: a type-tagged,
#                        prefix-free encoding over exactly CANONICAL_TYPES (a subclass is refused), checked at runtime
#                        against DG._same on a probe vector (_canonical_self_check) and refused for any other leaf type
#                        (the table then verifies by DG._same against the source, the reason on the receipt);
#   2  + one_decode      the plan pass writes every row's pre-dictionary cells (DG._plan_row's output) to the part's own
#                        scratch (cells.jsonl.gz: the table's text, never a copy of the spool; bounded by the disk
#                        reserve, deleted after the final pass, its bytes on the receipt) and the final pass numbers
#                        them from there without decoding the source (-> 2: snapshot and plan).
# The three settings below switch each reduction alone (on|off; the canary's per-reduction comparison); given beside
# FRANKIE_DIGEST_DECODES they must agree with it or the writer refuses. The table's bytes do not depend on any of the
# three (the same cells, dictionary and rows in the same order): toys test_decodes_identity.py / test_two_decodes.py.
PASS_SETTINGS = dict(fuse_context='FRANKIE_DIGEST_FUSE_CONTEXT', canonical_verify='FRANKIE_DIGEST_CANONICAL_VERIFY',
                     one_decode='FRANKIE_DIGEST_ONE_DECODE')
DECODES_SETTING = 'FRANKIE_DIGEST_DECODES'
DECODES_DEFAULT = 2
DECODES_LADDER = {5: dict(fuse_context=False, canonical_verify=False, one_decode=False),
                 4: dict(fuse_context=True, canonical_verify=False, one_decode=False),
                 3: dict(fuse_context=True, canonical_verify=True, one_decode=False),
                 2: dict(fuse_context=True, canonical_verify=True, one_decode=True)}


def pass_modes():
    """{fuse_context, canonical_verify, one_decode: bool, decodes: int, basis: str} from the run settings:
    FRANKIE_DIGEST_DECODES (5|4|3|2, default 2) sets the three; a per-reduction setting (on|off) given as well must
    agree with it (else ValueError), and given alone (no FRANKIE_DIGEST_DECODES) it overrides the default ladder."""
    given = os.environ.get(DECODES_SETTING)
    if given is None:
        decodes, basis = DECODES_DEFAULT, '%s unset: default %d' % (DECODES_SETTING, DECODES_DEFAULT)
    else:
        if given.strip() not in ('5', '4', '3', '2'):
            raise ValueError('%s must be 5, 4, 3 or 2, not %r' % (DECODES_SETTING, given))
        decodes = int(given.strip())
        basis = '%s=%d' % (DECODES_SETTING, decodes)
    out = dict(DECODES_LADDER[decodes])
    for key, name in PASS_SETTINGS.items():
        value = os.environ.get(name)
        if value is None:
            continue
        if value not in ('on', 'off'):
            raise ValueError('%s must be on or off, not %r' % (name, value))
        if given is not None and (value == 'on') != out[key]:
            raise ValueError('%s=%s contradicts %s=%d (%s is %s there)'
                             % (name, value, DECODES_SETTING, decodes, key, 'on' if out[key] else 'off'))
        out[key] = value == 'on'
        basis += '; %s=%s' % (name, value)
    out['decodes'] = decodes
    out['basis'] = basis
    return out


CANONICAL_TYPES = (type(None), bool, int, float, str, bytes, list, tuple, dict)


class _NotCanonical(TypeError):
    """A leaf type outside CANONICAL_TYPES (a subclass included): the row is verified by DG._same instead."""


def _canonical(value, out):
    """Append the type-tagged, prefix-free encoding of value to out (a list of bytes). Over exactly CANONICAL_TYPES two
    values have equal encodings exactly when DG._same holds: floats by repr (an exact round trip; -0.0 keeps its sign;
    every NaN one spelling, as _same treats every NaN as equal), ints by their digits, bools apart from ints, lists
    apart from tuples, strings and bytes with their length, dict keys tagged and sorted by their own encoding. A
    subclass (a numpy float64 is a float whose repr differs; DG._same calls it equal to the plain float it parses back
    to) is refused, never mis-spelled: the row then verifies by DG._same."""
    kind = type(value)
    if value is None:
        out.append(b'n')
    elif kind is bool:
        out.append(b'b1' if value else b'b0')
    elif kind is int:
        out.append(b'i%d;' % value)
    elif kind is float:
        out.append(b'fnan;' if value != value else b'f' + repr(value).encode('ascii') + b';')
    elif kind is str:
        raw = value.encode('utf-8', 'surrogatepass')
        out.append(b's%d:' % len(raw))
        out.append(raw)
    elif kind is bytes:
        out.append(b'y%d:' % len(value))
        out.append(value)
    elif kind is list or kind is tuple:
        out.append((b'l' if kind is list else b't') + b'%d[' % len(value))
        for item in value:
            _canonical(item, out)
        out.append(b']')
    elif kind is dict:
        keyed = []
        for key, item in value.items():
            piece = []
            _canonical(key, piece)
            keyed.append((b''.join(piece), item))
        keyed.sort(key=lambda pair: pair[0])
        out.append(b'd%d{' % len(keyed))
        for key_bytes, item in keyed:
            out.append(key_bytes)
            _canonical(item, out)
        out.append(b'}')
    else:
        raise _NotCanonical(type(value).__name__)


def canonical_digest(value):
    """sha256 of the canonical encoding (32 bytes); _NotCanonical for a leaf type outside CANONICAL_TYPES."""
    out = []
    _canonical(value, out)
    return hashlib.sha256(b''.join(out)).digest()


_CANONICAL_CHECK = []


def _canonical_self_check():
    """(ok, reason): once per process, the canonical encoding against DG._same on every pair of a probe vector that
    holds the cases the domain turns on (0.0 and -0.0, 1, 1.0 and True, every-NaN, int/str, list/tuple, nested dicts
    and lists, bytes, None, big ints, unicode). Any disagreement in either direction refuses the canonical verify."""
    if _CANONICAL_CHECK:
        return _CANONICAL_CHECK[0]
    nan = float('nan')
    probes = [None, True, False, 0, 1, -1, 1 << 70, 0.0, -0.0, 1.0, 0.1, 1e300, float('inf'), float('-inf'), nan,
              float.fromhex('0x1.8p+1023') * float('inf'), '', '1', 'a', 'a\x00b', 'é', b'', b'\x00', b'ab',
              [], [1], [1.0], [True], (1,), [[1]], [(1,)], {}, {'a': 1}, {'a': 1.0}, {'a': True}, {'b': 1},
              {'a': {'b': [1, 2.0, 'x', None]}}, {'a': {'b': [1, 2.0, 'x', nan]}}, {'a': [0.0]}, {'a': [-0.0]},
              [1, 2], [2, 1], {'x': 1, 'y': 2}, {'y': 2, 'x': 1}]
    encoded = []
    for probe in probes:
        try:
            encoded.append(canonical_digest(probe))
        except _NotCanonical as error:
            _CANONICAL_CHECK.append((False, 'probe %r not canonical: %s' % (probe, error)))
            return _CANONICAL_CHECK[0]
    for i, a in enumerate(probes):
        for j, b in enumerate(probes):
            if (encoded[i] == encoded[j]) != bool(DG._same(a, b)):
                _CANONICAL_CHECK.append((False, 'canonical encoding disagrees with DG._same on %r vs %r' % (a, b)))
                return _CANONICAL_CHECK[0]
    _CANONICAL_CHECK.append((True, 'injective over %s on the probe vector (%d values, every pair agrees with DG._same)'
                             % (', '.join(t.__name__ for t in CANONICAL_TYPES), len(probes))))
    return _CANONICAL_CHECK[0]


def _cross_of(row, columns, top):
    """One row's cross-table context columns (the values _cross_rows yields), from the decoded row."""
    if top:
        return {c: row[c] for c in columns if c in row and not (isinstance(row[c], dict) and row[c])}
    flat = DG._flatten(dict(row))
    return {c: flat[c] for c in columns if c in flat}


def _part_db(directory, stage):
    # Part databases are scratch (a failed pass is redone from its inputs), so no journal and no fsync per commit; a
    # 1 GiB page cache per helper keeps the per-candidate count upserts off the disk (profile 2026-09-28: the count
    # pass sat at 37% CPU in disk wait with the default 2 MB cache on 28 helpers).
    db = sqlite3.connect(Path(directory) / (stage + '.sqlite'))
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('PRAGMA cache_size=-1048576')
    return db


def _lookup_db(path):
    """Read-only shared dictionary, memory-mapped so every helper reads it through the one page cache."""
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA mmap_size=274877906944')
    db.execute('PRAGMA cache_size=-262144')
    return db


# Free space every helper and the copy keep on the scratch filesystem by default: the SSM agent, journald and the OS need
# it (2026-09-28: a full disk took the box's command runner down with the build). A parameter of write_table_parallel
# (review 2026-09-28): the value travels with each job, so a helper process sees the caller's reserve, not a module global.
DISK_RESERVE = 32 << 30


class DiskReserve(RuntimeError):
    pass


def _room(directory, needed=0, reserve=DISK_RESERVE):
    free = shutil.disk_usage(directory).free
    if free - needed < reserve:
        raise DiskReserve('stopping before the disk fills: %d bytes free, %d more needed, %d kept free (%s)'
                          % (free, needed, reserve, directory))


def _digest(key):
    # candidate texts are JSON spellings (ensure_ascii), so they encode as ASCII
    return hashlib.sha256(key.encode()).digest()


# ---- phase 1: snapshot ---------------------------------------------------------------------------------------------

def _snapshot(job):
    # Nothing is written: the later passes read the rows again from the same read-only source, in the same order. The
    # rows are JSON decoded (sources.sqlite payloads), so the serial writer's type-preservation spool check cannot fail
    # on them and is not repeated here.
    spec, directory = job[0], job[1]
    cross_columns = list(job[2]) if len(job) > 2 and job[2] else None     # fuse_context: the context from this decode
    Path(directory).mkdir(parents=True, exist_ok=True)
    observer, n, first, last = DG.Observer(), 0, None, None
    state = ({}, {}, {})
    cross = [] if cross_columns else None
    top = bool(cross_columns) and all('.' not in c for c in cross_columns)
    for n, row in enumerate(_source_rows(spec), 1):
        if cross is not None:
            cross.append(_cross_of(row, cross_columns, top))
        flat = DG._flatten(dict(row))
        observer.add(flat)
        if first is None:
            first = flat
        last = flat
        _fold(state, flat)
    return dict(observer=observer, n=n, first=first, last=last, state=state, cross=cross)


# ---- phase 2: plan cells, derived and constant flags, dictionary counts and scales, in one read --------------------

def _plan(job):
    """Plans every cell and counts the dictionary candidates in the same read of the part's rows; no plan is stored.

    Which columns the table keeps is known only when every part is planned, so candidates are counted for every column
    except while a column may still be excluded here (derived '=' or constant on every row of this part so far): its
    candidates are held apart and counted as soon as it cannot be (a column that varies in any part is kept), or left in
    the held table for the merge to count only if the column is kept table-wide. Positions run over every candidate in
    row-major order, so the first-occurrence order of the kept candidates is the serial one."""
    spec, directory, facts, seed, first, reserve = job[:6]
    modes = job[6] if len(job) > 6 else {}
    # one_decode: every row's cells to the part's own scratch (cells.jsonl.gz, zlib level 1: the table's text before
    # the dictionary, streamed, bounded by the reserve, deleted after the final pass) and, under canonical_verify, the
    # canonical digest of every source row (digests.bin, 32 bytes a row) for the inverse proof: the final and verify
    # passes then decode no source row
    one_decode, canonical = bool(modes.get('one_decode')), bool(modes.get('canonical'))
    import gzip
    cells_out = gzip.open(Path(directory) / 'cells.jsonl.gz', 'wt', compresslevel=1, encoding='utf-8', newline='\n') \
        if one_decode else None
    digests_out = (Path(directory) / 'digests.bin').open('wb') if (one_decode and canonical) else None
    canonical_reason = None
    columns = facts.columns
    _room(directory, reserve=reserve)
    prev, values, integers, lists = seed[0], dict(seed[1]), dict(seed[2]), dict(seed[3])
    width = len(columns)
    derived, constant = [True] * width, [True] * width
    scale_state = [[DG.SCALE_MAX, False] for _ in range(width)]
    held = [{} for _ in range(width)]
    db = _part_db(directory, 'freq')
    # cost = the estimated tokens of the candidate's inline spelling (a function of its text), for the dictionary cutoff
    db.execute('CREATE TABLE frequency (digest BLOB PRIMARY KEY, count INTEGER NOT NULL, first INTEGER NOT NULL, '
               'cost INTEGER NOT NULL) WITHOUT ROWID')
    db.execute('CREATE TABLE held (j INTEGER NOT NULL, digest BLOB NOT NULL, count INTEGER NOT NULL, '
               'first INTEGER NOT NULL, cost INTEGER NOT NULL, PRIMARY KEY (j, digest)) WITHOUT ROWID')
    batch = {}

    def flush():
        _room(directory, reserve=reserve)
        db.executemany('INSERT INTO frequency(digest, count, first, cost) VALUES (?, ?, ?, ?) ON CONFLICT(digest) DO UPDATE '
                       'SET count=count+excluded.count, first=min(first, excluded.first)',
                       ((k, v[0], v[1], v[2]) for k, v in sorted(batch.items())))
        batch.clear()

    def add(key, count, position, cost):
        entry = batch.get(key)
        if entry is None:
            batch[key] = [count, position, cost]
            if len(batch) >= 2000000:
                flush()
        else:
            entry[0] += count
            entry[1] = min(entry[1], position)

    position = 0
    for i, row in enumerate(_source_rows(spec)):
        flat = DG._flatten(dict(row))
        cells = DG._plan_row(flat, columns, prev, values, integers, lists, facts)
        if cells_out is not None:
            if i % 4096 == 0:
                _room(directory, reserve=reserve)
            cells_out.write(json.dumps(cells, separators=(',', ':')) + '\n')
            if digests_out is not None:
                try:
                    digests_out.write(canonical_digest(dict(row)))
                except _NotCanonical as error:
                    canonical_reason = 'row %d holds a %s leaf: verified by DG._same instead' % (i, error)
                    digests_out.close()
                    (Path(directory) / 'digests.bin').unlink(missing_ok=True)
                    digests_out = None
        for j, c in enumerate(columns):
            kind, text = cells[j]
            if derived[j] and text != '=':
                derived[j] = False
            if constant[j] and not (c in flat and c in first and DG._same(flat[c], first[c])):
                constant[j] = False
            candidate = derived[j] or constant[j]
            if held[j] and not candidate:
                for key, (count, at, cost) in held[j].items():
                    add(key, count, at, cost)
                held[j] = {}
            if kind != 'lit':
                key = _digest(DG.candidate_key(kind, text))
                if candidate:
                    entry = held[j].get(key)
                    if entry is None:
                        held[j][key] = [1, position, DG.inline_cost(kind, text)]
                    else:
                        entry[0] += 1
                elif key in batch:
                    add(key, 1, position, None)
                else:
                    add(key, 1, position, DG.inline_cost(kind, text))
                position += 1
            else:
                DG.scale_step(scale_state[j], text)
        prev = flat
    flush()
    db.executemany('INSERT INTO held VALUES (?, ?, ?, ?, ?)',
                   ((j, key, count, at, cost) for j, h in enumerate(held) for key, (count, at, cost) in sorted(h.items())))
    db.commit()
    db.close()
    cells_bytes = digests_bytes = 0
    for handle, name in ((cells_out, 'cells.jsonl.gz'), (digests_out, 'digests.bin')):
        if handle is not None:
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            size = (Path(directory) / name).stat().st_size
            if name == 'cells.jsonl.gz':
                cells_bytes = size
            else:
                digests_bytes = size
    return dict(derived=derived, constant=constant, scales=scale_state, cells_bytes=cells_bytes,
                digests_bytes=digests_bytes, canonical_reason=canonical_reason)


# ---- phase 3: merge (coordinator, digests only) ---------------------------------------------------------------------

def _merge(parts, dictionary, kept, reserve=DISK_RESERVE):
    """Table-wide counts (the held counts of kept columns only) and numbering in first-occurrence order over the whole
    table, as the serial pass assigns it: a part's newly seen keys are decided in the order of their first position in
    that part (DG.dictionary_pays, once per key, at its first occurrence), the paying ones numbered consecutively.
    Returns the first number of each part's range and the total."""
    dictionary.unlink(missing_ok=True)
    g = sqlite3.connect(dictionary)
    for pragma in ('journal_mode=OFF', 'synchronous=OFF', 'temp_store=MEMORY', 'cache_size=-16777216'):
        g.execute('PRAGMA ' + pragma)
    g.execute('CREATE TABLE frequency (digest BLOB PRIMARY KEY, count INTEGER NOT NULL, cost INTEGER NOT NULL, '
              'number INTEGER, part INTEGER, decided INTEGER NOT NULL DEFAULT 0) WITHOUT ROWID')
    g.execute('CREATE TEMP TABLE kept (j INTEGER PRIMARY KEY)')
    g.executemany('INSERT INTO kept VALUES (?)', ((j,) for j in kept))
    for p in parts:
        _room(dictionary.parent, reserve=reserve)
        g.execute('ATTACH DATABASE ? AS part', (str(p / 'freq.sqlite'),))
        g.execute('INSERT INTO frequency(digest, count, cost) SELECT digest, count, cost FROM part.frequency WHERE true '
                  'ON CONFLICT(digest) DO UPDATE SET count=count+excluded.count')
        g.execute('INSERT INTO frequency(digest, count, cost) SELECT digest, sum(count), min(cost) FROM part.held '
                  'WHERE j IN (SELECT j FROM kept) GROUP BY digest '
                  'ON CONFLICT(digest) DO UPDATE SET count=count+excluded.count')
        g.commit()
        g.execute('DETACH DATABASE part')
    number, starts = 0, []
    for index, p in enumerate(parts):
        starts.append(number)
        g.execute('ATTACH DATABASE ? AS part', (str(p / 'freq.sqlite'),))
        g.execute('CREATE TEMP TABLE seen (digest BLOB PRIMARY KEY, first INTEGER NOT NULL) WITHOUT ROWID')
        g.execute('INSERT INTO seen SELECT digest, first FROM part.frequency WHERE true')
        g.execute('INSERT INTO seen SELECT digest, min(first) FROM part.held WHERE j IN (SELECT j FROM kept) '
                  'GROUP BY digest ON CONFLICT(digest) DO UPDATE SET first=min(first, excluded.first)')
        fresh = g.execute('SELECT s.digest, f.count, f.cost FROM seen s JOIN frequency f ON f.digest=s.digest '
                          'WHERE f.count >= 2 AND f.decided = 0 ORDER BY s.first').fetchall()
        numbered = []
        for digest, count, cost in fresh:
            if DG.dictionary_pays(count, cost, number + len(numbered)):
                numbered.append(digest)
        g.executemany('UPDATE frequency SET number=?, part=? WHERE digest=?',
                      ((number + i, index, digest) for i, digest in enumerate(numbered)))
        g.executemany('UPDATE frequency SET decided=1 WHERE digest=?', ((digest,) for digest, _, _ in fresh))
        number += len(numbered)
        g.execute('DROP TABLE seen')
        g.commit()
        g.execute('DETACH DATABASE part')
    g.close()
    return dict(starts=starts, total=number)


# ---- phase 4: final cells with the global dictionary, written as the part's row text --------------------------------

def _final(job):
    """The part's rows planned again from its seed and written with the dictionary, cells joined by tabs (no cell holds
    a tab or a newline, checked); the copy turns the tabs into spaces when the table's separator is a space. The text of
    every dictionary entry this part numbers (its first occurrence is here) goes to names.txt, in number order."""
    spec, directory, index, facts, seed, kept, scales, dictionary, start, reserve = job[:10]
    modes = job[10] if len(job) > 10 else {}
    one_decode, canonical = bool(modes.get('one_decode')), bool(modes.get('canonical'))
    columns = facts.columns
    prev, values, integers, lists = seed[0], dict(seed[1]), dict(seed[2]), dict(seed[3])
    lookup = _lookup_db(dictionary)
    has_space, named = False, [start]
    directory = Path(directory)
    _room(directory, reserve=reserve)
    import gzip

    def planned_cells():
        # one_decode: the cells the plan pass wrote for this part (no source decode); else the source decoded and
        # planned again from the part's seed, as before (and, under canonical_verify, its canonical digest kept)
        nonlocal prev
        if one_decode:
            with gzip.open(directory / 'cells.jsonl.gz', 'rt', encoding='utf-8', newline='\n') as saved:
                for line in saved:
                    yield json.loads(line), None
            return
        for row in _source_rows(spec):
            flat = DG._flatten(dict(row))
            cells = DG._plan_row(flat, columns, prev, values, integers, lists, facts)
            prev = flat
            yield cells, row
    digests_out = (directory / 'digests.bin').open('wb') if (canonical and not one_decode) else None
    canonical_reason = None
    with (directory / 'rows.txt').open('w', encoding='utf-8', newline='\n') as rows, \
            (directory / 'names.txt').open('w', encoding='utf-8', newline='\n') as names:
        def number(kind, text, key):
            found, entry, part = lookup.execute('SELECT count, number, part FROM frequency WHERE digest=?',
                                                (_digest(key),)).fetchone()
            if entry is None:
                return None
            if part == index and entry >= named[0]:
                if entry != named[0]:
                    raise ValueError('dictionary first occurrences out of order in part %d' % index)
                names.write('@%d=%s\n' % (entry, DG.entry_spelling(key)))
                named[0] += 1
            return entry

        for i, (cells, row) in enumerate(planned_cells()):
            if i % 256 == 0:
                _room(directory, reserve=reserve)
            if row is not None:
                if digests_out is not None:
                    try:
                        digests_out.write(canonical_digest(dict(row)))
                    except _NotCanonical as error:
                        canonical_reason = 'row %d holds a %s leaf: verified by DG._same instead' % (i, error)
                        digests_out.close()
                        (directory / 'digests.bin').unlink(missing_ok=True)
                        digests_out = None
            out = DG.finish_row(cells, kept, columns, scales, number)
            if any('\t' in cell or '\n' in cell for cell in out):
                raise ValueError('a table cell holds a tab or a newline')
            line = '\t'.join(out)          # empty when every column is constant or derived, as the serial writer writes it
            has_space = has_space or ' ' in line
            rows.write(line + '\n')
        for handle in (rows, names):
            handle.flush()
            os.fsync(handle.fileno())
    digests_bytes = 0
    if digests_out is not None:
        digests_out.flush()
        os.fsync(digests_out.fileno())
        digests_out.close()
        digests_bytes = (directory / 'digests.bin').stat().st_size
    lookup.close()
    return dict(has_space=has_space, size=(directory / 'rows.txt').stat().st_size, named=named[0] - start,
                digests_bytes=digests_bytes, canonical_reason=canonical_reason)


# ---- phase 5: inverse verification, per part ------------------------------------------------------------------------

def _segment_lines(path, offset, length):
    """The lines of one part's byte range of the written table, read one at a time (never the whole segment)."""
    with Path(path).open('rb') as handle:
        handle.seek(offset)
        remaining = length
        while remaining:
            raw = handle.readline(remaining)
            if not raw.endswith(b'\n'):
                raise ValueError('table part line count differs')
            remaining -= len(raw)
            yield raw[:-1].decode('utf-8')


def _verify(job):
    (path, offset, length, count, spec, header, dictionary, seed) = job[:8]
    digests = job[8] if len(job) > 8 else None        # canonical_verify: the source rows' digests kept by the last decode
    lookup = _lookup_db(dictionary)

    def entry(number):
        found = lookup.execute('SELECT payload FROM dictionary WHERE number=?', (number,)).fetchone()
        if found is None:
            raise ValueError('unknown dictionary entry')
        return DG.entry_value(found[0])

    decoder = DG.RowDecoder(header, entry, seed)
    if digests is not None:
        # the parsed-back row's canonical digest against the source row's (equal exactly when DG._same holds over
        # CANONICAL_TYPES; a parsed row outside them cannot equal a canonical source row, so it is a mismatch)
        with Path(digests).open('rb') as kept:
            if os.fstat(kept.fileno()).st_size != 32 * count:
                raise ValueError('source row digests do not cover the table part')
            i = -1
            for i, line in enumerate(_segment_lines(path, offset, length)):
                if i >= count:
                    raise ValueError('table part line count differs')
                row = decoder.decode(line)
                try:
                    parsed = canonical_digest(DG._unflatten(row))
                except _NotCanonical:
                    parsed = None
                if parsed != kept.read(32):
                    raise ValueError(f'table {header.name} part row {i} does not round-trip')
        if i + 1 != count:
            raise ValueError('table part line count differs')
        lookup.close()
        return count
    expected = iter(_source_rows(spec))
    i = -1
    for i, line in enumerate(_segment_lines(path, offset, length)):
        if i >= count:
            raise ValueError('table part line count differs')
        row = decoder.decode(line)
        try:
            original = next(expected)
        except StopIteration as error:
            raise ValueError('source rows shorter than table part') from error
        if not DG._same(DG._unflatten(row), dict(original)):
            raise ValueError(f'table {header.name} part row {i} does not round-trip')
    if i + 1 != count:
        raise ValueError('table part line count differs')
    if next(expected, None) is not None:
        raise ValueError('source rows longer than table part')
    lookup.close()
    return count


# ---- coordinator ---------------------------------------------------------------------------------------------------

CHECKPOINT_SCHEMA = 'FRANKIE_PARALLEL_TABLE_PASSES_V3'   # V3: snapshots carry the DG.Observer (V8 facts)


def _pass_code():
    """What each pass's saved result depends on, cumulatively (a pass's result is reused only while its own code and
    the code of every earlier pass are unchanged): V2 keys passes by these sources, not by the whole file's bytes, so a
    fix in a later pass or in the orchestration keeps the passes before it."""
    import inspect
    import frankie_box_digest_sources as S
    base = [hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (TS, DG)]
    passes = (('snapshot', (_readonly, _source_rows, _fold, _snapshot, S._decoded, S._compare_groups, _seeds)),
              ('plan', (_part_db, _digest, _plan, _table_facts, _canonical, canonical_digest)),   # digests.bin under one_decode
              ('merge', (_merge,)),
              ('final', (_lookup_db, _final)),
              ('copy', (_separator, _copy)))
    digest, out = hashlib.sha256(json.dumps([base, sorted(MEMBER_LIST_PATHS.items())]).encode()), {}
    for label, functions in passes:
        for function in functions:
            digest.update(inspect.getsource(function).encode())
        out[label] = digest.copy().hexdigest()
    return out


def _checkpoint_key(name, specs):
    """A pass save point belongs to exactly this table's parts."""
    return dict(schema=CHECKPOINT_SCHEMA, name=name, specs=hashlib.sha256(pickle.dumps(specs, protocol=4)).hexdigest())


def _load_checkpoint(scratch, key, code):
    """The saved passes whose code still matches, in pass order up to the first that does not (None: nothing usable)."""
    try:
        value = pickle.loads((scratch / 'passes.pkl').read_bytes())
    except (OSError, ValueError, EOFError, pickle.UnpicklingError):
        return None
    if not isinstance(value, dict) or value.get('key') != key:
        return None
    passes, saved, codes = {}, value.get('passes') or {}, value.get('code') or {}
    for label in code:
        if label not in saved or codes.get(label) != code[label]:
            break
        passes[label] = saved[label]
    return passes or None


def _save_checkpoint(scratch, key, code, passes):
    tmp = scratch / 'passes.pkl.tmp'
    with tmp.open('wb') as handle:
        pickle.dump(dict(key=key, code={label: code[label] for label in passes}, passes=passes), handle, protocol=4)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, scratch / 'passes.pkl')


def _seeds(snaps):
    """The table's facts (the parts' observers merged in part order: the serial writer's facts), row count and first
    row, and each part's planner seed (the previous row and the last value / integer / list head per column before the
    part), from the snapshots."""
    observer = DG.Observer()
    for s in snaps:
        observer.merge(s['observer'])
    n = sum(s['n'] for s in snaps)
    first = next((s['first'] for s in snaps if s['n']), None) or {}
    seeds, state, prev = [], ({}, {}, {}), None
    for s in snaps:
        seeds.append((prev, dict(state[0]), dict(state[1]), dict(state[2])))
        if s['n']:
            for folded, part in zip(state, s['state']):
                folded.update(part)
            prev = s['last']
    return observer.facts(), n, first, seeds


def _table_facts(columns, n, planned):
    """The derived ('=') and constant ('^') columns, the kept column indexes and the scales, as the serial pass decides
    them over the whole table, from every part's flags and scale states."""
    derived = {c: all(f['derived'][j] for f in planned) for j, c in enumerate(columns)}
    constant = {c: all(f['constant'][j] for f in planned) for j, c in enumerate(columns)}
    whole = DG.whole_marks(columns, n, derived, constant)
    kept = [j for j, c in enumerate(columns) if c not in whole]
    scale_state = {j: [min(f['scales'][j][0] for f in planned), any(f['scales'][j][1] for f in planned)] for j in kept}
    return whole, kept, DG.scales_of(scale_state, columns)


def _separator(finals):
    return '\t' if any(f['has_space'] for f in finals) else ' '


def _copy(destination, name, n, facts, whole, first, scales, sep, parts, sizes, reserve=DISK_RESERVE):
    """The table: header, constants, scales, the dictionary (each part's names in part order, numbers checked
    consecutive), then every part's rows. Each part's row text is deleted as soon as it is appended (the disk holds the
    table plus one part, never the table twice); an interrupted copy therefore reruns the final pass."""
    destination.unlink(missing_ok=True)       # an unsaved partial table from an interrupted copy
    _room(destination.parent, sum((p / 'names.txt').stat().st_size for p in parts), reserve)   # the dictionary text, at most
    with destination.open('x', encoding='utf-8', newline='\n') as handle:
        for line in DG.header_lines(name, n, sep, facts.columns, whole, first, scales, facts):
            handle.write(line + '\n')
        number = 0
        for p in parts:
            with (p / 'names.txt').open(encoding='utf-8', newline='\n') as names:
                for line in names:
                    if not line.startswith('@%d=' % number) or not line.endswith('\n'):
                        raise ValueError('dictionary numbering mismatch in %s' % p)
                    handle.write(('\t' if number else 'dictionary: ') + line[:-1])
                    number += 1
        if number:
            handle.write('\n')
        handle.flush()
        offset = destination.stat().st_size     # header bytes; the part rows follow in order
        offsets = []
        for p, size in zip(parts, sizes):
            _room(destination.parent, size, reserve)
            offsets.append(offset)
            offset += size
            with (p / 'rows.txt').open('rb') as chunk:
                while block := chunk.read(1 << 22):
                    handle.buffer.write(block.replace(b'\t', b' ') if sep == ' ' else block)
            handle.flush()
            (p / 'rows.txt').unlink()
        os.fsync(handle.fileno())
    if destination.stat().st_size != offset:
        raise ValueError('table %s is not its header and parts' % name)
    return dict(offsets=offsets, identity=TS._identity(destination), numbered=number)


def write_table_parallel(destination, name, specs, scratch_directory, cpus, progress=None, reserve=DISK_RESERVE,
                         pool=None, cross_columns=None, on_cross=None):
    """specs: ordered part row sources (see _source_rows). The same bytes and proof as TS.write_table over the same rows
    (no context); note the ROWS differ for `bedrock.members`, where _source_rows applies MEMBER_LIST_PATHS and the serial
    reader does not, so that table is not byte-identical to a serial build of sources.sqlite. reserve = the bytes every
    helper and the copy keep free on the scratch filesystem.

    Save points per pass (Greg, 2026-09-28: stop, fix and restart without losing work): each finished pass records its
    result in scratch/passes.pkl, keyed by the table's parts and the code the pass depends on (_pass_code); a rerun with
    the same scratch directory resumes at the first pass not saved under the current code. A pass's files are deleted
    only once the pass that reads them is saved.

    pool: a PinnedPool shared with other tables written at the same time (the digest's one set of pinned helpers); None
    starts one on cpus for this table alone. Which helper runs a part never changes what the part returns."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(scratch_directory)
    # session 6: the pass modes (see PASS_SETTINGS); cross_columns + on_cross = the cross-table context collected
    # inside the snapshot pass (fuse_context) and handed to on_cross(rows) once that pass is done (saved or run)
    modes = pass_modes()
    fused = bool(cross_columns) and modes['fuse_context']
    if on_cross is not None and not fused:
        raise ValueError('on_cross needs cross_columns and %s=on' % PASS_SETTINGS['fuse_context'])
    one = modes['one_decode']
    canon_ok, canon_why = _canonical_self_check() if modes['canonical_verify'] else (False, PASS_SETTINGS['canonical_verify'] + '=off')
    canon = modes['canonical_verify'] and canon_ok
    key, code = _checkpoint_key(name, specs), _pass_code()
    key = dict(key, modes=dict(fuse_context=fused, one_decode=one, canonical_verify=canon))
    passes = _load_checkpoint(scratch, key, code) if scratch.is_dir() else None
    if passes is None:
        if scratch.exists():
            shutil.rmtree(scratch)            # no usable save point: the scratch (any older layout) starts over
        scratch.mkdir(parents=True)
        passes = {}
    given = progress or (lambda *a: None)
    labels = ('snapshot', 'plan', 'merge', 'final', 'copy', 'verify')

    def note(table, label):
        # the caller's progress as before, plus the stage heartbeat's phase file at every pass boundary (session 6):
        # pass index of the table's six passes, the table named; never per row
        given(table, label)
        head = label.split(' ', 1)[0]
        _stage_phase('root-digest: table %s pass %s (%d parts)' % (table, label, len(specs)),
                     units_done=labels.index(head) + 1 if head in labels else None, units_total=len(labels), unit='passes')
    parts = [scratch / ('part-%04d' % i) for i in range(len(specs))]
    dictionary = scratch / 'dictionary.sqlite'

    def drop(*filenames):
        for p in parts:
            for filename in filenames:
                (p / filename).unlink(missing_ok=True)

    order = list(code)

    def resume_from(label):
        nonlocal passes
        passes = {k: v for k, v in passes.items() if order.index(k) < order.index(label)}

    def present(filename):
        return all((p / filename).is_file() for p in parts)

    # A saved pass is kept only while the files the next unsaved pass reads are still there (an interrupted copy has
    # deleted the parts it appended; freq.sqlite is deleted once the merge is saved), checked from the last pass back.
    if 'final' in passes and 'copy' not in passes and not (present('rows.txt') and present('names.txt')):
        resume_from('final')
    if 'merge' in passes and 'final' not in passes and not dictionary.is_file():
        resume_from('merge')
    if 'plan' in passes and 'final' not in passes and one and not present('cells.jsonl.gz'):
        resume_from('plan')              # one_decode: the final pass reads the plan pass's cells
    if 'plan' in passes and 'merge' not in passes and not present('freq.sqlite'):
        resume_from('plan')

    def step(label, run):
        if label in passes:
            note(name, label + ' (saved)')
            return passes[label]
        stop = stop_requested()
        if stop:                              # session 8: the lawful stop point, between passes, every earlier pass saved
            note(name, label + ' NOT STARTED: stop requested (%s); exit %d, the same command resumes here' % (stop, STOPPED_EXIT))
            raise DigestStopped(name, label, stop)
        note(name, label)
        passes[label] = run()
        _save_checkpoint(scratch, key, code, passes)
        return passes[label]

    shared = pool
    with (contextlib.nullcontext(shared) if shared is not None else PinnedPool(cpus, label='table %s helpers' % name)) \
            as pool:
        _room(scratch, reserve=reserve)
        snaps = step('snapshot', lambda: list(pool.map(_snapshot, [(spec, str(p), list(cross_columns) if fused else None)
                                                                   for spec, p in zip(specs, parts)])))
        if on_cross is not None:
            import itertools
            on_cross(itertools.chain.from_iterable(s.get('cross') or [] for s in snaps))
        facts, n, first, seeds = _seeds(snaps)
        columns = facts.columns

        def plan():
            drop('freq.sqlite', 'cells.jsonl.gz', 'digests.bin')
            return list(pool.map(_plan_fresh, [(spec, str(p), facts, seed, first, reserve, dict(one_decode=one, canonical=canon))
                                               for spec, p, seed in zip(specs, parts, seeds)]))
        planned = step('plan', plan)
        whole, kept, scales = _table_facts(columns, n, planned)
        cells_bytes = sum(f.get('cells_bytes') or 0 for f in planned)
        canonical_reasons = [f['canonical_reason'] for f in planned if f.get('canonical_reason')]

        numbering = step('merge', lambda: _merge(parts, dictionary, kept, reserve))
        drop('freq.sqlite')                   # numbered and saved: the parts' counts are no longer needed

        def final():
            drop('rows.txt', 'names.txt')
            if not one:
                drop('digests.bin')
            return list(pool.map(_final, [(spec, str(p), i, facts, seed, kept, scales, str(dictionary), start, reserve,
                                           dict(one_decode=one, canonical=canon and not one))
                                          for i, (spec, p, seed, start)
                                          in enumerate(zip(specs, parts, seeds, numbering['starts']))]))
        finals = step('final', final)
        if sum(f['named'] for f in finals) != numbering['total']:
            raise ValueError('table %s: the parts named %d dictionary entries, the merge numbered %d'
                             % (name, sum(f['named'] for f in finals), numbering['total']))
        drop('cells.jsonl.gz')                # the final pass has numbered the cells: the scratch text is not kept
        canonical_reasons += [f['canonical_reason'] for f in finals if f.get('canonical_reason')]
        digests_bytes = sum((f.get('digests_bytes') or 0) for f in (planned if one else finals))
        sep = _separator(finals)
        sizes = [f['size'] for f in finals]

    copied = passes.get('copy')
    if copied is not None:
        note(name, 'copy (saved)')
        if not destination.is_file() or TS._identity(destination) != copied['identity']:
            raise ValueError('table %s changed since its copy save point; remove %s to rebuild it' % (name, scratch))
    else:
        stop = stop_requested()
        if stop:                              # session 8: the copy is a saved pass too; the stop point stands before it
            note(name, 'copy NOT STARTED: stop requested (%s); exit %d, the same command resumes here' % (stop, STOPPED_EXIT))
            raise DigestStopped(name, 'copy', stop)
        note(name, 'copy')
        copied = _copy(destination, name, n, facts, whole, first, scales, sep, parts, sizes, reserve)
        if copied['numbered'] != numbering['total']:
            raise ValueError('table %s: %d dictionary entries copied, %d numbered' % (name, copied['numbered'], numbering['total']))
        passes['copy'] = copied
        _save_checkpoint(scratch, key, code, passes)
    offsets = copied['offsets']
    drop('rows.txt', 'names.txt')
    dictionary.unlink(missing_ok=True)        # the table carries the dictionary now; the proof parses its own
    before = TS._identity(destination)
    # Inverse proof: the header and dictionary are parsed from the written file into their own database, then every
    # part's rows are parsed back from the file at their byte offsets and compared with the part's source rows.
    note(name, 'verify')
    inverse = scratch / 'inverse'
    if inverse.exists():
        shutil.rmtree(inverse)                # an interrupted proof is redone whole
    inverse.mkdir()
    _room(inverse, 2 * (offsets[0] if offsets else destination.stat().st_size), reserve)   # the parsed dictionary, indexed
    vdb = sqlite3.connect(inverse / 'table.sqlite')
    with destination.open(encoding='utf-8', newline='') as reader:
        tokens = TS._Tokens(reader)
        header = DG.Header(tokens)
        if header.name != name or header.n != n:
            raise ValueError('table header/name mismatch')
        vdb.execute('CREATE TABLE dictionary (number INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        DG.read_dictionary(tokens, lambda number, text: vdb.execute('INSERT INTO dictionary VALUES (?, ?)', (number, text)))
        vdb.commit()
    vdb.close()
    if any(mark == '=' and (name, c) in DG.CROSS_DERIVED for c, mark in header.whole.items()):
        raise ValueError('cross-table derived tables are not written in parallel')
    total = destination.stat().st_size
    if offsets and offsets[0] + sum(sizes) != total:
        raise ValueError('table parts do not end the file')
    # canonical_verify: every part's source-row digests must be there (an interrupted scratch may lack them) and no
    # part met a leaf outside CANONICAL_TYPES; otherwise every part verifies by DG._same against the source, as before
    by_digest = canon and not canonical_reasons and present('digests.bin')
    verify_basis = ('the canonical digest of every source row kept by the %s pass (%s)' % ('plan' if one else 'final', canon_why)
                    if by_digest else 'the source rows decoded again and compared by DG._same (%s)'
                    % ('; '.join(canonical_reasons) if canonical_reasons else (canon_why if modes['canonical_verify']
                                                                                 else PASS_SETTINGS['canonical_verify'] + '=off')
                       if not canon or canonical_reasons else 'a part has no digests file'))
    jobs = [(str(destination), off, size, s['n'], spec, header, str(inverse / 'table.sqlite'), seed,
             str(p / 'digests.bin') if by_digest else None)
            for off, size, s, spec, seed, p in zip(offsets, sizes, snaps, specs, seeds, parts)]
    verified = sum(pool_map_verify(jobs, cpus, pool=shared))
    if TS._identity(destination) != before:
        raise ValueError('table changed during inverse proof')
    if verified != n:
        raise ValueError('verified table count mismatch')
    shutil.rmtree(scratch)       # proved: the scratch (inverse, part directories) is no longer needed
    decodes = 1 + (0 if fused or not cross_columns else 1) + (1 if one else 2) + (0 if by_digest else 1)
    return dict(path=str(destination), rows=n, verified=True, verified_identity=before,
                scratch_directory=str(scratch), parts=len(specs),
                passes=dict(schema='FRANKIE_DIGEST_PASSES_V2', fuse_context=fused, one_decode=one,
                            canonical_verify=by_digest, verify_basis=verify_basis, source_decodes=decodes,
                            cells_scratch_bytes=cells_bytes, digests_bytes=digests_bytes,
                            decodes_setting=dict(value=modes['decodes'], basis=modes['basis'],
                                                 feeds_context=bool(cross_columns)),
                            settings={k: 'on' if modes[k] else 'off' for k in PASS_SETTINGS}))


def pool_map_verify(jobs, cpus, pool=None):
    if pool is not None:
        return pool.map(_verify, jobs)
    with PinnedPool(cpus, label='inverse proof helpers') as own:
        return own.map(_verify, jobs)


# ---- splitting a table into parts ----------------------------------------------------------------------------------

def spool_specs(path, parts):
    """Ordered part specs over a closed legacy RowSpool file (frankie_box_bedrock.RowSpool: one packed row per line):
    contiguous line-aligned byte ranges, about size/parts bytes each, read straight from the file by each helper (the
    rows are never held whole). The parts are positions, not a different row set: their rows in order are the spool's
    rows, and the parallel writer's bytes do not depend on where the parts are cut."""
    path = Path(path)
    size = path.stat().st_size
    cuts = [0]
    with path.open('rb') as handle:
        for k in range(1, max(1, parts)):
            nominal = size * k // parts
            if nominal <= cuts[-1]:
                continue
            handle.seek(nominal - 1)
            handle.readline()                  # just after the newline at or after byte nominal - 1: a line start
            cut = handle.tell()
            if cuts[-1] < cut < size:
                cuts.append(cut)
    cuts.append(size)
    return [dict(kind='spool', path=str(path), start=a, end=b) for a, b in zip(cuts, cuts[1:]) if b > a] or \
        [dict(kind='spool', path=str(path), start=0, end=0)]


def _cross_rows(job):
    """The named flat columns of each row of one spool part, in order: the cross-table context a later table reads.

    A column name without a dot is a top-level key of the row in DG._flatten's output: a nested key always carries its
    parent's name and a dot, so flat[c] for such a c is row[c] exactly when row[c] is not a non-empty mapping (which
    flattening dissolves into dotted keys). Those columns are read straight from the row, without flattening the whole
    frame (every price level and order of the full-depth book); any dotted column takes the whole flattening as before."""
    spec, columns = job
    out = []
    top = all('.' not in c for c in columns)
    for row in _source_rows(spec):
        if top:
            out.append({c: row[c] for c in columns if c in row and not (isinstance(row[c], dict) and row[c])})
        else:
            flat = DG._flatten(dict(row))
            out.append({c: flat[c] for c in columns if c in flat})
    return out


def cross_context(specs, columns, cpus, pool=None):
    """Every row's cross-derived source columns (DG.CROSS_DERIVED), in table order, decoded on the pinned helpers: what
    TS.write_table's _snapshot reads of a context table, so a later table's cross check sees the same values. pool: the
    digest's shared PinnedPool (None: one of its own on cpus)."""
    jobs = [(spec, list(columns)) for spec in specs]
    if pool is not None:
        for part in pool.map(_cross_rows, jobs):
            yield from part
        return
    with PinnedPool(cpus, label='cross-context helpers') as own:
        for part in own.map(_cross_rows, jobs):
            yield from part


def split_specs(spec, parts):
    """spec as _bedrock_table_job receives it: {kind: members|rows, database, query, parameters, excluded}."""
    db = _readonly(spec['database'])
    try:
        if spec['kind'] == 'members':
            keys = [k for (k,) in db.execute('SELECT key FROM groups ORDER BY value COLLATE group_order')]
            size = max(1, -(-len(keys) // parts))
            return [dict(kind='members', database=spec['database'], keys=keys[i:i + size])
                    for i in range(0, len(keys), size)] or [dict(kind='members', database=spec['database'], keys=[])]
        query, parameters = spec['query'], list(spec['parameters'])
        total = db.execute('SELECT count(*) FROM (' + query + ')', tuple(parameters)).fetchone()[0]
        prefix, order = 'SELECT payload FROM rows WHERE ', ' ORDER BY ordinal'
        if not (query.startswith(prefix) and query.endswith(order)) or total < 2 * parts:
            return [dict(kind='rows', database=spec['database'], query=query, parameters=parameters,
                         excluded=spec['excluded'], start=0, count=total)]
        # Keyset ranges over the same ordered rows: each part reads only its own ordinals.
        ordinals = [o for (o,) in db.execute(query.replace('SELECT payload', 'SELECT ordinal', 1), tuple(parameters))]
        size = -(-total // parts)
        ranged = query[:-len(order)] + ' AND ordinal BETWEEN ? AND ?' + order
        return [dict(kind='rows', database=spec['database'], query=ranged,
                     parameters=parameters + [ordinals[i], ordinals[min(i + size, total) - 1]],
                     excluded=spec['excluded'], start=0, count=min(size, total - i))
                for i in range(0, total, size)]
    finally:
        db.close()


# ---- reuse of a finished sources.sqlite ---------------------------------------------------------------------------

SOURCES_SAVE_SCHEMA = 'FRANKIE_SOURCES_SAVE_V1'


def sources_code():
    """The code whose change could change sources.sqlite or the rows read from it: the merge (MERGE_CODE, which also
    covers layer preparation), the per-layer copy, the row queries and readers. BedrockSources.__init__ is not keyed
    here: since b35e79b7 it differs only by the save-point identity it passes to _merge_sharded (2026-09-27)."""
    import inspect
    import frankie_box_digest_sources as S
    code = dict(S.merge_shard_key([])['code'])
    for name, function in (('BedrockSources._merge', S.BedrockSources._merge), ('BedrockSources._rows', S.BedrockSources._rows),
                           ('_Rows', S._Rows), ('_Members', S._Members), ('_compare_groups', S._compare_groups),
                           ('_reusable_prepared', S._reusable_prepared)):
        code[name] = hashlib.sha256(inspect.getsource(function).encode()).hexdigest()
    return code


def sources_key(entries):
    identity = [[i, name, pin.get('sha256')] for i, (name, pin) in enumerate(entries.items())]
    return json.loads(json.dumps(dict(schema=SOURCES_SAVE_SCHEMA, layers=identity, code=sources_code())))


def saved_sources(entries, layers_root):
    """A finished sources.sqlite an earlier digest attempt of this calculation root left, receipted with this key and
    unchanged since (bytes and mtime), or None."""
    key = sources_key(entries)
    for receipt in sorted(Path(layers_root).parent.parent.glob('.digest-*/calculation-layers/sources.save.json')):
        try:
            value = json.loads(receipt.read_bytes())
            path = Path(value['path'])
            info = path.stat()
            if (value.get('key') == key and path.parent == receipt.parent and path.name == 'sources.sqlite'
                    and not path.is_symlink() and info.st_size == value['bytes'] and info.st_mtime_ns == value['mtime_ns']
                    and not (path.parent / 'sources.sqlite-journal').exists()):
                return path.parent
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def _file_witness(path):
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as reader:
        while chunk := reader.read(8 << 20):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _published_meta(name, pin, receipts, witness):
    """The metadata fields of a published gzip-json layer, by the walk _prepare_published uses (small metadata members
    decompressed, row arrays located from the range receipts, never inflated); the pin's bytes and sha256 checked."""
    import frankie_box_digest_sources as S
    size, sha = witness.result()
    if size != pin['bytes'] or sha != pin['sha256']:
        raise ValueError('compressed projected layer witness differs')
    path = Path(pin['path'])
    projection = path.resolve().parent.parent
    if projection not in receipts:
        receipts[projection] = S._range_receipts(projection)
    document, _ = S._published_layout(path, name, receipts[projection])
    return {key: document[key] for key in sorted(document) if key in S.META_FIELDS}


def recorded_order(entries, database):
    """The bedrock entries in the order the finished sources.sqlite numbered its layers (layer_index). work/derive.json
    is written with sorted keys, while ROOT numbered the layers in its in-memory order, so a reader of derive.json must
    take the order from here: layer indexes, the sources key and the table ordinals all follow it."""
    db = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = db.execute('SELECT ordinal, payload FROM layer_index ORDER BY ordinal').fetchall()
    finally:
        db.close()
    names = [json.loads(zlib.decompress(p) if isinstance(p, bytes) else p)['layer'] for _, p in rows]
    if [o for o, _ in rows] != list(range(len(rows))) or sorted(names) != sorted(entries):
        raise ValueError('the finished sources layer_index does not number exactly these bedrock layers')
    return {name: entries[name] for name in names}


def _plain_meta(pin):
    """The metadata fields of a plain (not gzip-json) pinned layer, streamed (row arrays skipped), bytes and sha256
    checked against the pin: the same fields BedrockSources._read keeps (last duplicate key wins)."""
    import frankie_box_digest_sources as S
    if pin.get('encoding') is not None:
        raise ValueError('unknown projected layer encoding')
    digest, size = hashlib.sha256(), 0
    with open(pin['path'], 'rb') as reader:
        while chunk := reader.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)
    if size != pin['bytes'] or digest.hexdigest() != pin['sha256']:
        raise ValueError('pinned layer bytes or sha256 differ')
    metadata = {}
    with open(pin['path'], encoding='utf-8') as handle:
        parser = S._JSON(handle)
        parser.expect('{')
        if parser.peek() != '}':
            while True:
                key = parser.value()
                parser.expect(':')
                if key in S.META_FIELDS:
                    metadata[key] = parser.value()
                else:
                    parser.skip()
                if parser.peek() == '}':
                    break
                parser.expect(',')
    return metadata


class ReopenedSources:
    """The table registry of BedrockSources over an existing finished sources.sqlite, read-only: the same table
    names, order, queries and row readers, and the same header facts (derived, layer_count, verdict)."""
    def __init__(self, entries, root):
        import frankie_box_digest_sources as S
        self.root = Path(root)
        self.db = sqlite3.connect((self.root / 'sources.sqlite').resolve().as_uri() + '?mode=ro', uri=True,
                                  check_same_thread=False)
        self.db.execute('PRAGMA cache_size=-65536')
        self.db.create_collation('group_order', S._compare_groups)
        self.tables, self.verdict, self._references = {}, {}, {}
        self.layer_count, self.derived = len(entries), 0
        metadata, first_verdict = [], False
        recorded = {ordinal: json.loads(zlib.decompress(p) if isinstance(p, bytes) else p)
                    for ordinal, p in self.db.execute('SELECT ordinal, payload FROM layer_index')}
        receipts, found = {}, {}
        for index, pin in enumerate(entries.values()):
            if pin.get('encoding') == 'gzip-json':
                found[index] = S._reusable_prepared(index, pin, self.root)
        with ThreadPoolExecutor(8) as pool:     # pin witnesses of the layers without a receipt, hashed in parallel
            hashes = {index: pool.submit(_file_witness, pin['path']) for index, pin in enumerate(entries.values())
                      if index in found and found[index] is None}
        for index, (name, pin) in enumerate(entries.items()):
            if pin.get('encoding') == 'gzip-json':
                # no receipt in reach: the same layout walk ROOT prepared it with (metadata members only)
                meta = found[index]['meta'] if found[index] is not None else _published_meta(name, pin, receipts, hashes[index])
            else:
                # plain layers were prepared in place (no receipt); their metadata is re-read from the pinned file
                meta = _plain_meta(pin)
            row = recorded.get(index) or {}
            mine = dict(layer=name, status=meta.get('status'), reason=meta.get('reason'), producer=meta.get('producer'),
                        member_paths=' '.join(meta.get('member_paths') or []),
                        lifecycle_sections=' '.join(meta.get('lifecycle_sections') or []),
                        section_counts=json.dumps(meta.get('section_counts') or {}, separators=(',', ':'), sort_keys=True),
                        count=meta.get('count'), partial=' '.join(p['section'] for p in (meta.get('partial') or [])))
            if any(row.get(k) != v for k, v in mine.items()):
                raise ValueError('layer %d (%s) metadata differs from the finished sources layer_index' % (index, name))
            metadata.append(meta)
            if isinstance(meta.get('traversal'), dict) and not first_verdict:
                self.verdict = meta['traversal']
                first_verdict = True
            self.derived += meta.get('status') == 'derived'
        if first_verdict:
            self.tables['bedrock.run'] = S._Rows(self.db, 'SELECT payload FROM run')
        self.tables['bedrock.layers'] = S._Rows(self.db, 'SELECT payload FROM layer_index ORDER BY ordinal')
        if self.db.execute('SELECT 1 FROM groups LIMIT 1').fetchone():
            self.tables['bedrock.members'] = S._Members(self.db)
        sections = {}
        for index, meta in enumerate(metadata):
            if meta.get('status') != 'derived':
                continue
            for section in meta.get('lifecycle_sections') or []:
                rows = self._rows(index, 'lifecycle_rows', section)
                if section not in sections and len(rows):
                    sections[section] = rows
        for section in sorted(sections):
            self.tables[f'bedrock.lifecycle.{section}'] = sections[section]
        for index, meta in enumerate(metadata):
            section = meta.get('section')
            if meta.get('status') != 'derived' or not section:
                continue
            for field, prefix in (('companion_rows', 'companions'), ('declarations', 'declarations'),
                                  ('first_last_pairs', 'first_last')):
                rows = self._rows(index, field)
                if len(rows):
                    self.tables[f'bedrock.{prefix}.{section}'] = rows
            if meta.get('matching_rule'):
                self.tables[f'bedrock.matching_rule.{section}'] = self._rows(index, 'matching_rule')

    def _rows(self, index, field, section=None):
        import frankie_box_digest_sources as S
        return S.BedrockSources._rows(self, index, field, section)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
