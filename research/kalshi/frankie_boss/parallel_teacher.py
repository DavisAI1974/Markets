"""The R3 teacher's attachment across the box's CPUs (Greg, 2026-09-28: "Fix the 1 cpu issue").

c15_teacher_r3.JournalTeacherR3.attach (pinned, unchanged) walks the complete prefix once, in order, on one core, and for
EVERY context row (the Monday's context is the whole day) it
  - observes 19 columns on the running NormalizerR3 (two statistics.median over its value window each: ~18 ms/row),
  - builds a DipoleTarget (tensors + canonical hash),
  - takes normalizer.receipt(): two source-file reads and evidence_hash(normalizer.export()) over all 19 windows of up to
    floats and their hex (~0.3-0.4 s/row measured on one core),
then hashes the list of every receipt. Over the whole day that is days of one CPU.

parallel_attach returns the same dictionary, in the same order, with the same checks:
  1. the parent runs the pinned raw streams (c15_teacher_r3._paired_raw: the control and R3 raw teachers, in order,
     sharing nothing with the normalizer) and the exact-row context check, keeping for every row what the normalizer and
     the target need (the combined 19 raw values, receipt present, instrument, time, prefix hash, content hash);
  2. a NormalizerR3 restored exactly as attach restores it replays only update() over those rows (validation + append,
     no statistics) and, at each chunk start, exports its state (export() + state_hash, the pinned checkpoint);
  3. each chunk runs in a spawn worker on NormalizerR3.restore(config, export, state_hash) (the pinned restore, which
     verifies that hash): the pinned observe() per row, the pinned DipoleTargetSpec/DipoleTarget, and the receipt;
  4. the receipt's state_hash is evidence_hash(export()) computed from per-value byte fragments kept in step with the
     windows (pack(float) = ["float64", struct hex], pack(hex string) = ["str", hex]; the canonical JSON of a list is its
     parts in order): the first two receipts of every chunk and every GUARD_EVERY-th are also taken the original way
     (normalizer.receipt()) and must be equal, key order included, or the run stops;
  5. attachment_hash = evidence_hash(receipts) from each receipt's canonical bytes (computed in the worker by the pinned
     pack/canonical_tagged_bytes) joined in order.
Identity normalizers (IdentityNormalizerR3) take the same path with receipt = normalizer.export(), as attach does.

The raw streams (step 1) also run across the CPUs (Greg, 2026-09-28: "build the parallel raw streams"). Per receipt row the
pinned iter_raw loops call three pure functions of a group window: the control's JournalTeacher._dynamics (64 and 1024
groups) and R3's _absorption (which runs _dynamics again) and _cohort (64 and 1024 groups each). During step 1 those three
are swapped for recorders (restored after) that return placeholders and queue the call; everything stateful (the group
histories, pending groups, origins, DChain machines, ordinals, content chain, anchors) still runs in the parent, in
order, on the pinned code. Queued calls go to spawn workers in batches: each batch carries every referenced group once
(a per-batch table; a sliding window is a contiguous range of it) and the worker runs the pinned function on exactly the
same groups. Each row's placeholders are replaced by the results as they arrive. Guard: the first two calls of every batch
and every RAW_GUARD_EVERY-th call are also computed in the parent at call time with the pinned function and must equal
the worker's result, or the run stops.
Shared-path payload encodings (EvidencePrecompute, 2026-10-07 night): the canonical bytes of each yielded payload and the
entity's 7-field row hash, computed on pinned workers and registered for parallel_journal._chain_hash_factory exactly as
the legacy walk's reader workers do (section note below). Finish (steps 3-4): pinned workers (FINISH_WORKER_CPUS), a
dead worker redone with one fewer, the finished prefix of chunks joined in order while later chunks run.
Pinned files unchanged: c15_teacher_r3.py, c15_teacher.py, c15_normalizer.py, c15_normalizer_r3.py, dipole_target.py.
"""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter, deque
import hashlib
import multiprocessing
import os
from pathlib import Path
import struct
import sys
import time

GUARD_EVERY = 50_000
FULL_HASH_CHECK_RECEIPTS = 2_000   # up to this many receipts the attachment hash is also recomputed whole (a check, no cap)
RAW_GUARD_EVERY = 20_000
RAW_BATCH_CALLS = 32_768
RAW_MARK = '\x00parallel-raw:'
DSTATE_SCHEMA = 'FRANKIE_TEACHER_DSTATE_ROWS_V1'


def _modules():
    from . import c15_teacher_r3 as T
    from . import c15_normalizer as N
    from . import c15_normalizer_r3 as R
    from . import dipole_target as D
    from .c15_journal import SCHEMA, pack
    from .verified_journal_reader import DIGEST_PREFIX, canonical_tagged_bytes
    return T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes


def _light():
    from . import c15_normalizer as N
    from . import c15_normalizer_r3 as R
    from .c15_journal import pack
    from .verified_journal_reader import DIGEST_PREFIX, canonical_tagged_bytes
    return N, R, pack, DIGEST_PREFIX, canonical_tagged_bytes


def _canonical(value):
    T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes = _modules()
    return canonical_tagged_bytes(pack(value))


class _FastStateHash:
    """evidence_hash(normalizer.export()) from per-value fragments kept in step with the normalizer's windows.

    NormalizerR3.export() == dict(control.Normalizer.export(self), schema=R3 SCHEMA, candidate=R3 CANDIDATE), the control
    export being {schema, candidate, config: config.payload(), windows: [{instrument_id, column, values: list(window),
    n_present, values_hex: [v.hex()...], mode}...]} over _windows in order. The skeleton below is that export with each
    window's two lists replaced by placeholder strings; its canonical bytes are streamed into sha256 with each
    placeholder's bytes replaced by the list's bytes built from the fragments."""

    def __init__(self, normalizer):
        N, R, pack, self.prefix, self.encode = _light()
        self.N, self.R, self.normalizer, self.pack = N, R, normalizer, pack
        self.frags = {key: deque((self._value(v) for v in window), maxlen=window.maxlen)
                      for key, window in normalizer._windows.items()}
        self.counts = dict(normalizer._counts)

    @staticmethod
    def _value(v):
        # pack(float) == ["float64", struct.pack(">d", v).hex()]; pack(str) == ["str", s]; compact ASCII JSON
        return (b'["float64","' + struct.pack('>d', v).hex().encode() + b'"]',
                b'["str","' + v.hex().encode() + b'"]')

    def _sync(self):
        for key, window in self.normalizer._windows.items():
            added = self.normalizer._counts[key] - self.counts[key]
            if added:
                frags, take = self.frags[key], min(added, len(window))
                for index in range(len(window) - take, len(window)):
                    frags.append(self._value(window[index]))
                self.counts[key] = self.normalizer._counts[key]

    def state_hash(self):
        self._sync()
        n, config = self.normalizer, self.normalizer.config
        windows = [{"instrument_id": i, "column": c, "values": '@@V%d@@' % k, "n_present": n._counts[i, c],
                    "values_hex": '@@H%d@@' % k, "mode": config.mode} for k, (i, c) in enumerate(n._windows)]
        control = {"schema": self.N.SCHEMA, "candidate": self.N.CANDIDATE, "config": config.payload(), "windows": windows}
        skeleton = self.encode(self.pack(dict(control, schema=self.R.SCHEMA, candidate=self.R.CANDIDATE)))
        digest, position = hashlib.sha256(self.prefix), 0
        for k, key in enumerate(n._windows):
            frags = self.frags[key]
            for token, part in ((b'["str","@@V%d@@"]' % k, 0), (b'["str","@@H%d@@"]' % k, 1)):
                at = skeleton.index(token, position)
                digest.update(skeleton[position:at])
                digest.update(b'["list",[' + b','.join(f[part] for f in frags) + b']]')
                position = at + len(token)
        digest.update(skeleton[position:])
        return digest.hexdigest()


def _receipt(normalizer, fast, constants):
    """normalizer.receipt() with the constant fields computed once and state_hash from the fragments; same key order."""
    schema, candidate, normalizer_sha, control_sha, config_hash = constants
    state_hash = fast.state_hash()
    normalizer_id = (f'{schema}:FROZEN:{state_hash}' if normalizer.config.mode == 'FROZEN' else f'{schema}:UPDATING')
    return dict(schema=schema, candidate=candidate, normalizer_code_sha=normalizer_sha, control_code_sha=control_sha,
                config_hash=config_hash, state_hash=state_hash, normalizer_id=normalizer_id)


def _chunk(job):
    """One chunk: the pinned observe, target and receipt per row, from the restored chunk-start state."""
    import torch
    T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes = _modules()
    (identity, instrument_ids, config, payload, state_hash, rows, spec, source_manifest_hash) = job
    normalizer = (R.IdentityNormalizerR3(instrument_ids) if identity else R.NormalizerR3.restore(config, payload, state_hash))
    fast = constants = None
    if not identity:
        fast = _FastStateHash(normalizer)
        constants = (R.SCHEMA, R.CANDIDATE, hashlib.sha256(Path(R.__file__).read_bytes()).hexdigest(),
                     hashlib.sha256(Path(N.__file__).read_bytes()).hexdigest(), normalizer.config.config_hash)
    out, taken = [], 0
    for row in rows:
        wanted, has_receipt, iid, combined, now, prefix, cursor, content = row[:8]
        normalized = ([normalizer.observe(iid, c, v['value'], N.State(v['state'])) for c, v in zip(T.CONTROL_COLUMNS, combined)]
                      if has_receipt else [N.NormalizedValue(v['value'], N.State(v['state'])) for v in combined])
        if not wanted:
            continue
        target = D.DipoleTarget(D.DipoleTargetSpec(normalizer_id=normalizer.normalizer_id, **spec), source_manifest_hash,
                                prefix, now,
                                torch.tensor([[[v.value for v in normalized]]], dtype=torch.float32),
                                torch.tensor([[[int(v.state) for v in normalized]]], dtype=torch.int8),
                                torch.tensor([[now]], dtype=torch.int64))
        if identity:
            receipt_normalizer = normalizer.export()
        else:
            receipt_normalizer = _receipt(normalizer, fast, constants)
            if taken < 2 or taken % GUARD_EVERY == 0:
                original = normalizer.receipt()
                if original != receipt_normalizer or list(original) != list(receipt_normalizer):
                    raise ValueError('parallel teacher receipt differs from normalizer.receipt(); run stopped')
        taken += 1
        receipt = dict(cursor=cursor, source_prefix_hash=prefix, evidence_content_hash=content,
                       target_hash=target.target_hash, normalizer=receipt_normalizer)
        out.append((target, receipt, canonical_tagged_bytes(pack(receipt))))
    # the plain pickler copies tensors by value; the pool's ForkingPickler would pass each tensor's storage through a
    # shared-memory file descriptor once torch is imported (millions of targets: descriptor exhaustion)
    import pickle
    return pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)


_WORKER_CHANGED = [False]

# The raw-batch workers' CPUs (Greg, 2026-10-07 night: every pool pinned to its share of the booked lane). A caller that
# pins the parent's raw loop sets this to the CPUs the workers take, in hand-out order (one worker each), and resets it
# to None after the walk (frankie_box_experiment_teacher). None = unchanged: _cpus() workers on the parent's mask.
# Placement only: every batch result is the pinned functions' value, resolved by token; no value depends on it.
RAW_WORKER_CPUS = None
# What the last raw pool did (workers, CPUs, rebuilds after a dead worker); receipt-only, never an input to a row.
RAW_POOL_RECORD = {}
RAW_POOL_MAX_CONSECUTIVE_BREAKS = 3


# ---- one pool rule for every teacher pool (stacks pass, 2026-10-07 night session 5; Greg: "use the lane_pin
# primitives, do not write your own pool"). Every spawn pool of this module is built by _spawn_pool: the shared
# frankie_box_lane_pin.executor('process', ...) (one worker per CPU of the plan in its physical-core order, a refused pin
# falls back to the lane, never off it, a respawned worker takes the next CPU instead of blocking), spawn because the
# parent already runs reader threads. Without the box module (another host layout) the previous private pinning is
# used, listed in the pool record. Every stop is bounded (_bounded_shutdown): cancel what has not started, give the
# running workers STOP_GRACE_SECONDS, then terminate and kill what is still alive; a wedged worker can never hang the
# stage the way the a2 legacy shards did (spawn workers do not inherit the parent's SIGTERM handler either).
# Placement and teardown only: no value, order, hash or identity depends on them.
STOP_GRACE_SECONDS = 60.0


def _lane_pin():
    """frankie_box_lane_pin (the box module), or None when it is not importable here."""
    import importlib
    for name in ('frankie_box_lane_pin', 'deploy.aws.box.frankie_box_lane_pin'):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def _spawn_pool(workers, planned, record=None):
    """A spawn ProcessPoolExecutor of `workers`, pinned over `planned` (the CPUs of the plan) through the shared lane_pin
    executor; unpinned on the parent's mask when there is no plan. `record` (a dict) gets the placement used."""
    context = multiprocessing.get_context('spawn')
    workers = max(1, int(workers))
    LP = _lane_pin() if planned else None
    if LP is not None:
        if record is not None:
            record['placement'] = LP.record(workers, list(planned), what='teacher spawn pool')
        return LP.executor('process', workers, cpus=list(planned), mp_context=context)
    if planned:
        if record is not None:
            record['placement'] = dict(basis='frankie_box_lane_pin not importable: private pinning, one CPU of the plan '
                                             'per worker in plan order', worker_cpus=list(planned[:workers]))
        return ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_pin_raw_worker,
                                   initargs=(tuple(planned), context.Value('l', 0)))
    return ProcessPoolExecutor(max_workers=workers, mp_context=context)


def _bounded_shutdown(pool, record=None, grace=None):
    """Stop `pool` without an unbounded wait: queued work cancelled, running workers given `grace` seconds to finish,
    then terminated (and killed after 5 s more). What had to be terminated is listed in record['stops']."""
    grace = STOP_GRACE_SECONDS if grace is None else grace
    processes = list((getattr(pool, '_processes', None) or {}).values())
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except Exception as error:  # noqa: BLE001 - listed; the processes are still stopped below
        if record is not None:
            record.setdefault('stops', []).append(dict(shutdown_error='%s: %s' % (type(error).__name__, error)))
    began = time.monotonic()
    deadline = began + grace

    def alive(process):
        try:
            return process.is_alive()
        except Exception:  # noqa: BLE001 - not a child we can poll (never started): nothing to stop
            return False
    # poll every 50 ms until every worker has exited or the grace is over (a worker that is exiting is never counted
    # as running: only one still alive at the deadline is terminated)
    while any(alive(process) for process in processes) and time.monotonic() < deadline:
        time.sleep(0.05)
    stopped = []
    for process in processes:
        if not alive(process):
            continue
        try:
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
        except Exception:  # noqa: BLE001 - listed below; nothing else can be done for it here
            pass
        stopped.append(getattr(process, 'pid', None))
    if stopped and record is not None:
        record.setdefault('stops', []).append(dict(terminated_pids=stopped, grace_seconds=grace,
                                                   waited_seconds=round(time.monotonic() - began, 3),
                                                   reason='still alive when the %.0f s stop grace ended' % grace))
    return stopped


def _submit(pool, function, argument):
    """pool.submit, or a Future already holding BrokenProcessPool when the pool broke at submit (the caller's redo
    handles it like a result that broke)."""
    try:
        return pool.submit(function, argument)
    except Exception as error:  # noqa: BLE001
        from concurrent.futures import Future
        from concurrent.futures.process import BrokenProcessPool
        future = Future()
        future.set_exception(error if isinstance(error, BrokenProcessPool) else BrokenProcessPool(str(error)))
        return future


# Unit progress (FRANKIE_WORK_PROBE_V1 / the stage heartbeat; Greg: "never report running without a probe reading"): a
# caller sets PROGRESS to a function(stage, completed, total) and the row pass / finish call it at most every
# PROGRESS_EVERY_SECONDS (the row pass checks the clock every 1,024 rows). Report-only: an error in it is swallowed and
# counted in PROGRESS_ERRORS, never changes a row; None = no reporting (the previous behaviour).
PROGRESS = None
PROGRESS_EVERY_SECONDS = 15.0
PROGRESS_ERRORS = [0]


def _progress(stage, completed, total=None, force=False, _last={}):
    if PROGRESS is None:
        return
    now = time.monotonic()
    if not force and now - _last.get(stage, 0.0) < PROGRESS_EVERY_SECONDS:
        return
    _last[stage] = now
    try:
        PROGRESS(stage, completed, total)
    except Exception:  # noqa: BLE001 - a probe is never the stage's outcome
        PROGRESS_ERRORS[0] += 1


# ---- save identity like ROOT's (Greg, 2026-10-07 night: "every workflow piece needs their restore save code updated to
# match ROOT's"). (5) Function-level code identity: a raw-pass or attachment save binds frankie_box_bedrock.code_identity
# of the declared definitions below (a comment or an unrelated edit of this file no longer refuses a save; any change to
# the named code does); a save written with the old whole-file parallel_teacher_sha256 is accepted while this file is
# byte-identical. (4) Identity is content, not location: any other difference is offered to
# frankie_box_experiment_root.content_rebinds; checkout-prefix moves with equal bytes and sha256 are accepted and recorded
# (<recovery>.checkout-rebinds/<n>.json), anything else refuses as before. Nothing saved is rewritten.
ROW_PASS_CODE = ('RAW_MARK', 'DSTATE_SCHEMA', '_changes_applied', '_raw_batch', '_RawStreams', '_dstate_row', 'row_pass')
FINISH_CODE = ('GUARD_EVERY', '_FastStateHash', '_receipt', '_chunk', '_canonical', '_candidate', 'finish')


def _box(name):
    import importlib
    for qualified in (name, 'deploy.aws.box.' + name):
        try:
            return importlib.import_module(qualified)
        except Exception:  # noqa: BLE001 - not importable here: the caller takes its listed fallback
            continue
    return None


def _code_witness(names):
    """{'parallel_teacher_code': code_identity(this file, names)}; the whole-file sha256 when bedrock is not here."""
    bedrock = _box('frankie_box_bedrock')
    if bedrock is not None and hasattr(bedrock, 'code_identity'):
        return dict(parallel_teacher_code=bedrock.code_identity(__file__, names))
    return dict(parallel_teacher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def _identity_accepted(saved, built, recovery_path, record=None):
    """True when a saved identity may be resumed under the identity this process builds (ROOT's rule, see above)."""
    if saved == built:
        return True
    whole = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if (isinstance(saved, dict) and isinstance(built, dict) and 'parallel_teacher_sha256' in saved
            and 'parallel_teacher_code' in built):
        if saved['parallel_teacher_sha256'] != whole:
            return False
        rest_saved = {k: v for k, v in saved.items() if k != 'parallel_teacher_sha256'}
        rest_built = {k: v for k, v in built.items() if k != 'parallel_teacher_code'}
        if record is not None:
            record.setdefault('identity_notes', []).append('an old whole-file save, accepted: this file is byte-identical')
        if rest_saved == rest_built:
            return True
        saved, built = rest_saved, rest_built
    root = _box('frankie_box_experiment_root')
    moves = root.content_rebinds(saved, built) if root is not None and hasattr(root, 'content_rebinds') else None
    if not moves:
        return False
    import json
    where = Path(str(recovery_path) + '.checkout-rebinds')
    where.mkdir(parents=True, exist_ok=True)
    note = where / ('%d.json' % time.time_ns())
    note.write_text(json.dumps(dict(schema='FRANKIE_TEACHER_CHECKOUT_REBINDS_V1', save=str(recovery_path), moves=moves,
                                    rule='checkout-prefix moves with equal bytes and sha256 only; nothing saved is '
                                         'rewritten'), indent=1, sort_keys=True, default=str))
    if record is not None:
        record.setdefault('checkout_rebinds', []).append(dict(file=str(note), moves=len(moves)))
    return True


def _pin_raw_worker(cpus, counter):
    """Spawn-worker initializer: the next CPU of the plan (a shared counter, so a respawned worker never blocks on an
    emptied hand-out); a refused pin keeps the inherited mask."""
    with counter.get_lock():
        turn = counter.value
        counter.value += 1
    try:
        os.sched_setaffinity(0, {cpus[turn % len(cpus)]})
    except (OSError, AttributeError):
        pass


def _changes_applied():
    import sys
    module = sys.modules.get(__package__ + '.teacher_changes')
    return bool(module is not None and module._SAVED)


def _raw_batch(blob):
    """One batch of the raw streams' window functions, the pinned functions on the same groups, in order."""
    import pickle
    from . import c15_teacher_r3 as T
    tables, calls, changed = pickle.loads(blob)
    if changed and not _WORKER_CHANGED[0]:
        from . import teacher_changes
        teacher_changes.apply()                       # the same changed functions the parent recorded
        _WORKER_CHANGED[0] = True
    out = []
    for token, kind, family, window, side, start in calls:
        table = tables[family]
        groups = (table[window[0]:window[0] + window[1]] if type(window) is tuple else [table[i] for i in window])
        if kind == 'dynamics':
            value = T.JournalTeacher._dynamics(groups, side)
        elif kind == 'absorption':
            value = T._absorption(groups, side)
        else:
            value = T._cohort(start, groups, side)
        out.append((token, value))
    return pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)


class _RawStreams:
    """Swaps JournalTeacher._dynamics, _absorption and _cohort (pure functions of a group window) for recorders during
    the parent's pinned raw loop; the recorded calls run in spawn workers, batch by batch, while the loop goes on."""

    def __init__(self, T, cpus):
        self.T, self.cpus = T, cpus
        self.calls, self.resolved, self.expected, self.pending = 0, 0, {}, deque()
        self.where, self.early, self.rows = {}, {}, None
        self._new_batch()

    def _new_batch(self):
        self.tables, self.index, self.batch = {'control': [], 'r3': []}, {'control': {}, 'r3': {}}, []

    def __enter__(self):
        T = self.T
        self.original = (T.JournalTeacher.__dict__['_dynamics'], T._absorption, T._cohort)
        dynamics, absorption, cohort = self.original[0].__func__, self.original[1], self.original[2]

        def exact(kind, groups, side, start):
            if kind == 'dynamics':
                return dynamics(groups, side)
            if kind == 'cohort':
                return cohort(start, groups, side)
            T.JournalTeacher._dynamics = self.original[0]      # _absorption runs the pinned _dynamics inside
            try:
                return absorption(groups, side)
            finally:
                T.JournalTeacher._dynamics = staticmethod(record_dynamics)

        def record(kind, family, groups, side, start, width):
            token = self.calls
            self.calls += 1
            if len(self.batch) < 2 or token % RAW_GUARD_EVERY == 0:
                self.expected[token] = exact(kind, groups, side, start)
            table, index = self.tables[family], self.index[family]
            places = []
            for group in groups:
                at = index.get(id(group))
                if at is None:
                    at = index[id(group)] = len(table)
                    table.append(group)
                places.append(at)
            contiguous = all(b == a + 1 for a, b in zip(places, places[1:]))
            window = (places[0] if places else 0, len(places)) if contiguous else places
            self.batch.append((token, kind, family, window, side, start))
            if len(self.batch) >= RAW_BATCH_CALLS:
                self._submit()
            state = int(self.T.State.MISSING)
            marks = [dict(value=0., state=state, mask=0, reason='%s%d.%s' % (RAW_MARK, token, slot))
                     for slot in (('0', '1') if width == 2 else ('-',))]
            return tuple(marks) if width == 2 else marks[0]

        def record_dynamics(groups, side):
            return record('dynamics', 'control', groups, side, None, 2)

        def record_absorption(groups, side):
            return record('absorption', 'r3', groups, side, None, 1)

        def record_cohort(start, groups, side):
            return record('cohort', 'r3', groups, side, start, 2)

        self.planned = tuple(RAW_WORKER_CPUS or ())
        if self.planned:
            self.cpus = len(self.planned)
        RAW_POOL_RECORD.clear()
        RAW_POOL_RECORD.update(workers=self.cpus, cpus=list(self.planned) or None, rebuilds=[],
                               basis=('each spawn worker pinned to one CPU of the plan' if self.planned else
                                      'unpinned spawn workers on the parent\'s mask (no plan given)'))
        self.breaks = 0
        self.pool = self._new_pool(self.cpus)
        T.JournalTeacher._dynamics = staticmethod(record_dynamics)
        T._absorption, T._cohort = record_absorption, record_cohort
        return self

    def _new_pool(self, workers):
        return _spawn_pool(workers, self.planned, RAW_POOL_RECORD)

    def _submit(self):
        import pickle
        if not self.batch:
            return
        blob = pickle.dumps((self.tables, self.batch, _changes_applied()), protocol=pickle.HIGHEST_PROTOCOL)
        try:
            future = self.pool.submit(_raw_batch, blob)
        except Exception as error:  # noqa: BLE001 - a pool that broke between results: redone in _result, one fewer
            from concurrent.futures import Future
            from concurrent.futures.process import BrokenProcessPool
            future = Future()
            future.set_exception(error if isinstance(error, BrokenProcessPool) else BrokenProcessPool(str(error)))
        self.pending.append((blob, future))
        self._new_batch()
        while len(self.pending) > 2 * self.cpus:          # bounded: never the whole day's windows in flight
            self._collect(*self.pending.popleft())

    def _result(self, blob, future):
        """The batch's result. A dead worker never stops or hangs the walk (Greg, 2026-10-07): on BrokenProcessPool a new
        pool with one worker fewer (at least one) takes this batch and every unfinished pending batch again, in order;
        the pure functions give the same values. Only the same batch breaking the pool repeatedly is raised."""
        from concurrent.futures.process import BrokenProcessPool
        while True:
            try:
                result = future.result()
                self.breaks = 0
                return result
            except BrokenProcessPool as error:
                self.breaks += 1
                if self.breaks > RAW_POOL_MAX_CONSECUTIVE_BREAKS:
                    raise
                _bounded_shutdown(self.pool, RAW_POOL_RECORD)
                self.cpus = max(1, self.cpus - 1)
                self.pool = self._new_pool(self.cpus)
                again = 0
                for index, (other, other_future) in enumerate(self.pending):
                    if not (other_future.done() and not other_future.cancelled() and other_future.exception() is None):
                        self.pending[index] = (other, _submit(self.pool, _raw_batch, other))
                        again += 1
                future = _submit(self.pool, _raw_batch, blob)
                RAW_POOL_RECORD['rebuilds'].append(dict(workers=self.cpus, batches_again=again + 1,
                                                        error='%s: %s' % (type(error).__name__, error)))

    def _collect(self, blob, future):
        import pickle
        for token, value in pickle.loads(self._result(blob, future)):
            if token in self.expected:
                expected = self.expected.pop(token)
                if expected != value or (type(value) is dict and list(expected) != list(value)) or (
                        type(value) is tuple and [list(v) for v in expected] != [list(v) for v in value]):
                    raise ValueError('parallel teacher raw stream differs from the pinned function; run stopped')
            if token in self.where:
                self._resolve(token, value)
            else:
                self.early[token] = value

    def place(self, rows, index):
        """Record where row index's placeholders sit; results arriving later go straight into the row."""
        self.rows = rows
        for column, v in enumerate(rows[index][3]):
            if type(v['reason']) is str and v['reason'].startswith(RAW_MARK):
                token, slot = v['reason'][len(RAW_MARK):].split('.')
                self.where.setdefault(int(token), []).append((index, column, slot))
        for token in [t for t in self.early if t in self.where]:
            self._resolve(token, self.early.pop(token))

    def _resolve(self, token, value):
        # the row's value is replaced exactly as attach builds it: control columns dict(v), R3 columns value/state/reason
        for index, column, slot in self.where.pop(token):
            v = value if slot == '-' else value[int(slot)]
            carried = self.rows[index][3][column]
            resolved = dict(v)
            # teacher_changes wraps the deferred result with current-book flags
            # and unknown-side counts in the parent. Replacing the placeholder
            # wholesale loses those inputs. Reapply the same wrappers after the
            # worker result, preserving its value/state/reason and original math.
            if carried.get('incomplete'):
                incomplete = Counter(resolved.get('incomplete', {})) + Counter(carried['incomplete'])
                resolved['incomplete'] = dict(sorted(incomplete.items()))
            resolved.update({k: x for k, x in carried.items()
                             if k not in ('value', 'state', 'mask', 'reason', 'incomplete')})
            # every carried key kept (incomplete lists, unknown-side counts); R3's model-side mask left out as attach does
            self.rows[index][3][column] = ({k: x for k, x in resolved.items() if k != 'mask'}
                                          if 7 <= column < 13 else resolved)
        self.resolved += 1

    def finish(self):
        self._submit()
        while self.pending:
            self._collect(*self.pending.popleft())
        if self.expected or self.where or self.early or self.resolved != self.calls:
            raise ValueError('parallel teacher raw call unresolved; run stopped')

    def __exit__(self, *exc):
        T = self.T
        T.JournalTeacher._dynamics = self.original[0]
        T._absorption, T._cohort = self.original[1], self.original[2]
        for _, future in self.pending:
            future.cancel()
        _bounded_shutdown(self.pool, RAW_POOL_RECORD)
        return False


# ---- the shared path's per-row canonical bytes across the CPUs (Greg, 2026-10-07 night: "stack every optimizer we
# already have that applies to the teacher's data path"; mimic how ROOT and the legacy walk process data) ---------------
# The pinned R3 raw loop chains content = evidence_hash(dict(previous=content, evidence=e)) over EVERY row and the row
# pass hashes the entity's 7-field row: two pure-Python canonical encodings of the full APPLIED payload (every book level)
# per row, on the serial consumer. The legacy walk (parallel_journal) already computes both in its reader workers and the
# consumer only runs the sha256 (parallel_journal._CANONICAL / _SUBSETS, consumed by _chain_hash_factory, the first 64 of
# each also checked the original way there). The shared timeline yields the same payloads without those bytes, so on the
# shared path they were computed serially again. EvidencePrecompute is that legacy fast path for the shared path: the
# consumer reads ahead, ships each present payload (pickled: exact for the journal's plain types) in ordered batches to
# spawn workers pinned one per CPU of the plan, which return canonical_bytes(pack(e)) and, for an entity row, the
# 7-field evidence_hash; the consumer registers them right before it yields that very object. Guard: the first item of
# every batch is also encoded the original way in the consumer and must be equal, or the run stops. A dead worker never
# stops the walk: the pool is rebuilt with one worker fewer and every unfinished batch is submitted again, in order; a
# batch that cannot be pickled, keeps breaking the pool or raises in the worker is simply not registered, and the
# consumer computes those rows the original way at the original place (the same value, or the same error there).
EVIDENCE_BATCH = 256
PRECOMPUTE_RECORD = {}


def _evidence_batch(blob):
    """One ordered batch: (canonical_bytes(pack(e)), the 7-field evidence_hash or None) per payload."""
    import pickle
    from . import c15_journal as J
    fields, items = pickle.loads(blob)
    out = []
    for e, subset in items:
        out.append((J.canonical_bytes(J.pack(e)), J.evidence_hash({k: e[k] for k in fields}) if subset else None))
    return pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)


class _EvidenceBatch:
    __slots__ = ('blob', 'future', 'values', 'resolved')

    def __init__(self, blob):
        self.blob, self.future, self.values, self.resolved = blob, None, None, False


class EvidencePrecompute:
    """Ordered batches of payloads -> their canonical bytes (and entity 7-field hashes) on pinned spawn workers. One
    owner thread; values(batch) blocks for that batch only. Placement and speed only: a registered value is exactly the
    value the consumer would compute, a missing one is computed there the original way."""

    def __init__(self, cpus, fields, workers=None):
        self.planned = tuple(cpus or ())
        self.workers = max(1, int(workers or len(self.planned) or _cpus()))
        self.fields = tuple(fields)
        self.breaks, self.open = 0, []
        PRECOMPUTE_RECORD.clear()
        PRECOMPUTE_RECORD.update(workers=self.workers, cpus=list(self.planned) or None, batch=EVIDENCE_BATCH, batches=0,
                                 rows=0, not_registered_batches=[], rebuilds=[], guard_checked=0,
                                 basis=('each spawn worker pinned to one CPU of the plan' if self.planned else
                                        'unpinned spawn workers on the parent\'s mask (no plan given)'),
                                 rule='placement and speed only: the consumer computes any row not registered here the '
                                      'original way; the first row of every batch is also checked the original way')
        self.pool = self._new_pool(self.workers)

    def _new_pool(self, workers):
        return _spawn_pool(workers, self.planned, PRECOMPUTE_RECORD)

    def submit(self, items):
        """Queue one ordered batch [(payload, entity_row)...]; returns its handle."""
        import pickle
        PRECOMPUTE_RECORD['batches'] += 1
        PRECOMPUTE_RECORD['rows'] += len(items)
        try:
            batch = _EvidenceBatch(pickle.dumps((self.fields, items), protocol=pickle.HIGHEST_PROTOCOL))
        except Exception as error:  # noqa: BLE001 - not registered; the consumer computes these rows itself
            batch = _EvidenceBatch(None)
            self._skip(batch, 'not picklable (%s)' % type(error).__name__)
            return batch
        self._send(batch)
        self.open.append(batch)
        return batch

    def _send(self, batch):
        try:
            batch.future = self.pool.submit(_evidence_batch, batch.blob)
        except Exception as error:  # noqa: BLE001 - a broken pool at submit: rebuilt on the next wait
            batch.future = None
            batch.values = error

    def _skip(self, batch, why):
        batch.values, batch.resolved, batch.blob = None, True, None
        if len(PRECOMPUTE_RECORD['not_registered_batches']) < 100:
            PRECOMPUTE_RECORD['not_registered_batches'].append(why)

    def values(self, batch):
        """The batch's [(bytes, hash or None)...], or None (not registered: compute those rows the original way)."""
        import pickle
        from concurrent.futures.process import BrokenProcessPool
        while not batch.resolved:
            try:
                if batch.future is None:
                    raise BrokenProcessPool(str(batch.values))
                result = batch.future.result()
            except BrokenProcessPool as error:
                self.breaks += 1
                if self.breaks > RAW_POOL_MAX_CONSECUTIVE_BREAKS:
                    self._skip(batch, 'the pool broke %d times on this batch: %s' % (self.breaks, error))
                    self.breaks = 0
                    break
                # a dead worker: one fewer, every unfinished batch again in order (the pure encoding gives the same)
                _bounded_shutdown(self.pool, PRECOMPUTE_RECORD)
                self.workers = max(1, self.workers - 1)
                self.pool = self._new_pool(self.workers)
                again = 0
                for other in self.open:
                    if other.resolved or (other.future is not None and other.future.done()
                                          and not other.future.cancelled() and other.future.exception() is None):
                        continue
                    self._send(other)
                    again += 1
                PRECOMPUTE_RECORD['rebuilds'].append(dict(workers=self.workers, batches_again=again,
                                                          error='%s: %s' % (type(error).__name__, error)))
                continue
            except Exception as error:  # noqa: BLE001 - the worker raised: the original place raises it again
                self._skip(batch, 'worker error %s' % type(error).__name__)
                break
            self.breaks = 0
            batch.values, batch.resolved, batch.blob, batch.future = pickle.loads(result), True, None, None
        while self.open and self.open[0].resolved:
            self.open.pop(0)
        if batch in self.open:
            self.open.remove(batch)
        return batch.values

    def close(self):
        for batch in self.open:
            if batch.future is not None:
                batch.future.cancel()
        self.open = []
        _bounded_shutdown(self.pool, PRECOMPUTE_RECORD)


# The attachment pool's CPUs (finish, steps 3-4): set by the caller like RAW_WORKER_CPUS (one spawn worker per CPU, in
# hand-out order) and reset to None after; None = unchanged (_cpus() unpinned workers). FINISH_POOL_RECORD: receipt-only.
FINISH_WORKER_CPUS = None
FINISH_POOL_RECORD = {}
FINISH_CHUNKS_PER_WORKER = 4


def _cpus():
    try:
        return max(1, len(os.sched_getaffinity(0)) - 1)
    except (AttributeError, OSError):
        return max(1, (os.cpu_count() or 2) - 1)


SESSION_FIELDS = frozenset({'cursor', 'raw_record', 'normalized', 'source_member_index',
                            'session_id', 'integrity', 'terminal_prefix_hash'})


def _candidate(self, T):
    candidate = self.candidate_digest
    if _changes_applied():
        from . import teacher_changes
        candidate = T.evidence_hash(dict(r3=candidate, changes=teacher_changes.CHANGES_SHA256))
    return candidate


class TeacherSaved(SystemExit):
    """The caller requested a save; no next source row has been consumed."""

    def __init__(self, message):
        print(message, flush=True)
        super().__init__(75)


class _HashingWriter:
    """A write-through target for pickle.dump that hashes every byte as it is written (session 6, 2026-10-08: the
    saved state's digest comes from the write stream; before, the pending file was read back whole for it)."""

    def __init__(self, handle):
        self._handle, self._digest = handle, hashlib.sha256()

    def write(self, data):
        self._digest.update(data)
        return self._handle.write(data)

    def hexdigest(self):
        return self._digest.hexdigest()


def _save_raw_state(path, body):
    # Same local, hash-bound pickle convention as the existing journal walk cache: 64 hex digits of the sha256 of the
    # bytes after them, then the pickle. The bytes written are the same as before; the digest is taken on the write
    # stream (one pass, no read-back), the durability order (body fsync, digest write, fsync, replace, dir fsync) kept.
    import pickle
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('wb') as handle:
        handle.write(b'0' * 64)
        hashing = _HashingWriter(handle)
        pickle.dump(body, hashing, protocol=pickle.HIGHEST_PROTOCOL)
        handle.flush()
        os.fsync(handle.fileno())
    digest = hashing.hexdigest().encode()
    with temporary.open('r+b') as handle:
        handle.write(digest)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _load_raw_state(path):
    # The file is mapped and read ONCE: the hash pass brings its pages in, the unpickle consumes the same mapped bytes
    # (before: one read for the hash, a second for the unpickle). The order is unchanged on purpose: the hash is
    # verified in full BEFORE any byte is unpickled, so a tampered or truncated file is refused without executing it.
    import mmap
    import pickle
    with Path(path).open('rb') as handle:
        size = os.fstat(handle.fileno()).st_size
        if size < 64:
            raise ValueError('saved teacher state hash differs; retained, not discarded')
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            view = memoryview(mapped)
            try:
                expected, body = view[:64], view[64:]
                try:
                    digest = hashlib.sha256()
                    for start in range(0, len(body), 1 << 24):
                        digest.update(body[start:start + (1 << 24)])
                    if digest.hexdigest().encode() != bytes(expected):
                        raise ValueError('saved teacher state hash differs; retained, not discarded')
                    return pickle.loads(body)
                finally:
                    expected.release()
                    body.release()
            finally:
                view.release()


def _dstate_row(e, control):
    """Snapshot the already-advanced machine; no replay, new transition or target."""
    from dataclasses import asdict
    from fractions import Fraction
    m = e['normalized']
    key = m['publisher_id'], m['instrument_id']
    row = dict(schema=DSTATE_SCHEMA, cursor=e['cursor'], source_prefix_hash=e['terminal_prefix_hash'],
               ts_recv_ns=m['ts_recv_ns'], publisher_id=key[0], instrument_id=key[1],
               source_member_index=e['source_member_index'], session_id=e['session_id'])
    if e['receipt'] is None:
        return dict(row, status='NOT_F_LAST', state=None)
    machine = control['machines'].get(key)
    if (machine is None or machine._ordinal != control['ordinal'][key] - 1
            or machine._member != e['source_member_index'] or machine._session != e['session_id']):
        raise ValueError('DState machine does not belong to the current teacher group')
    state = {name: (dict(numerator=value.numerator, denominator=value.denominator)
                    if isinstance(value, Fraction) else value)
             for name, value in asdict(machine._state).items()}
    return dict(row, status='GROUP_STATE', group_ordinal=machine._ordinal,
                tick_raw=machine._tick_raw, state=state)


# Periodic exact save of the raw pass (stacks pass, session 5; the Sept-29 item 2 rule: exact state at a group-closed
# point, a resume continues from it; Greg: a crash must not lose the raw pass). With a recovery path, once
# SAVE_EVERY_SECONDS have passed since the last save, the raw pass saves at the next row that closes its group (the row
# carries its F_LAST receipt) and ends a raw batch exactly: the raw streams are drained first (every placeholder resolved, as the stop-save does),
# then the same state the stop-save writes (complete False) and the walk CONTINUES. A resume loads it exactly as it loads
# a stop-save. Env FRANKIE_TEACHER_SAVE_EVERY_S overrides (0 = off). Every save is listed in SAVE_RECORD (receipt only).
# RESUME_SKIP[0]: the rows a loaded save already holds (the caller's evidence generator may skip precomputing them).
SAVE_EVERY_SECONDS = 1800.0
SAVE_RECORD = {}
RESUME_SKIP = [0]
# One pass on a resume (2026-10-09): before this a resume re-read and re-hashed every row of the journal and of every
# layer spool from instant 0 and threw the first `processed` away (islice). The seek protocol between row_pass and the
# evidence producer (the shared market timeline's walk, frankie_box_experiment_teacher.shared_evidence):
#   RESUME_POSITION_SOURCE[0]  set by the producer: a callable returning a picklable reader position for exactly the rows
#                              it has YIELDED so far (not its read-ahead): each stream's byte offset and resumable
#                              sha256 state, the journal block (FrankieCompactReader.resume_point), the report counts,
#                              and the producer's own counters. row_pass calls it at every save (after the raw streams
#                              are drained) and keeps it in the save as `reader_position`.
#   RESUME_POSITION[0]         set by row_pass on a resume, BEFORE the producer starts: the saved position (None: none).
#   RESUME_SEEKED[0]           set by the producer when it started from RESUME_POSITION: the rows its seek skipped (it
#                              then yields row RESUME_SEEKED[0] first). row_pass skips only the rest (processed - seeked)
#                              by reading; a producer that cannot seek leaves 0 and every saved row is read and skipped
#                              as before.
RESUME_POSITION_SOURCE = [None]
RESUME_POSITION = [None]
RESUME_SEEKED = [0]


def _reader_position():
    """The producer's position for the rows yielded so far (RESUME_POSITION_SOURCE), or None; a failure is listed on
    SAVE_RECORD, never the save's outcome (the resume then reads the saved rows and skips them)."""
    source = RESUME_POSITION_SOURCE[0]
    if source is None:
        return None
    try:
        return source()
    except Exception as error:  # noqa: BLE001 - a position is a speed-up only
        SAVE_RECORD.setdefault('position_errors', []).append('%s: %s' % (type(error).__name__, str(error)[:300]))
        return None


def _skip_resumed(evidence, processed):
    """The evidence after the `processed` rows a save holds: the producer is started first (it reads RESUME_POSITION
    and may seek, RESUME_SEEKED), then only the rows its seek did not skip are read and dropped."""
    from itertools import chain, islice
    iterator = iter(evidence)
    marker = object()
    first = next(iterator, marker)
    seeked = RESUME_SEEKED[0]
    if type(seeked) is not int or not 0 <= seeked <= processed:
        raise ValueError('the evidence producer reports %r rows skipped by its seek; the save holds %d' % (seeked, processed))
    resumed = SAVE_RECORD.get('resumed_from')
    if isinstance(resumed, dict):
        resumed.update(seeked=seeked, read_and_skipped=processed - seeked)
    if first is marker:
        return
    yield from islice(chain((first,), iterator), processed - seeked, None)


def _save_every():
    text = os.environ.get('FRANKIE_TEACHER_SAVE_EVERY_S')
    if text is None:
        return SAVE_EVERY_SECONDS, 'default'
    try:
        value = float(text)
    except ValueError:
        return SAVE_EVERY_SECONDS, 'default (FRANKIE_TEACHER_SAVE_EVERY_S=%r is not a number)' % text[:40]
    return (value if value > 0 else None), 'FRANKIE_TEACHER_SAVE_EVERY_S'


def row_pass(self, evidence, *, as_of, source_manifest_hash, recovery_path=None,
             recovery_identity=None, save_requested=None, retain_dstate=False):
    """Step 1 on its own (the teacher reading the journal): the raw streams over every entry, in order, with the window
    functions across the CPUs. Returns (rows, processed, entity row hashes): rows in cursor order, the wanted flag still
    unset (the context is not known yet); the entity row hashes are the 7-field evidence hashes of the session's entity
    rows, for the exact-row check against the context when it arrives."""
    from .parallel_journal import _ENTITY, CONTEXT_FIELDS
    T = _modules()[0]
    if type(as_of) is not int or as_of < 0:
        raise ValueError('nonnegative as_of required')
    entity = _ENTITY[0]
    rows, processed, entity_hashes = [], 0, {}
    RESUME_SKIP[0] = 0
    RESUME_POSITION[0], RESUME_SEEKED[0] = None, 0
    every, every_basis = _save_every() if recovery_path else (None, 'no recovery path')
    SAVE_RECORD.clear()
    SAVE_RECORD.update(every_seconds=every, basis=every_basis, saves=[], resumed_from=None,
                       rule='exact state at a row that closes its group (F_LAST receipt), raw streams drained first; '
                            'the walk continues; a resume loads it as it loads a stop-save')
    continuation = {} if recovery_path or retain_dstate else None
    identity = dict(binding=self.binding, source_manifest_hash=source_manifest_hash,
                    entity=entity, source=recovery_identity,
                    **_code_witness(ROW_PASS_CODE)) if recovery_path else None
    if identity is not None and retain_dstate:
        identity['dstate_schema'] = DSTATE_SCHEMA
    if recovery_path and Path(recovery_path).exists():
        saved = _load_raw_state(recovery_path)
        if not _identity_accepted(saved['identity'], identity, recovery_path, SAVE_RECORD) or saved['as_of'] > as_of:
            raise ValueError('saved teacher source, code or causal bound differs')
        identity = saved['identity']             # the saved document stays the identity (ROOT's rule)
        as_of = saved['as_of']
        rows, processed, entity_hashes = saved['rows'], saved['processed'], saved['entity_hashes']
        continuation = saved['continuation']
        if len(rows) != processed or (processed and (
                continuation['control']['processed'] != processed or continuation['raw']['next_cursor'] != processed)):
            raise ValueError('saved teacher streams and rows do not share one cursor')
        SAVE_RECORD['resumed_from'] = dict(processed=processed, complete=bool(saved['complete']))
        if saved['complete']:
            return rows, processed, entity_hashes
        RESUME_SKIP[0] = processed
        RESUME_POSITION[0] = saved.get('reader_position')
        evidence = _skip_resumed(evidence, processed)
    def save(complete):
        _save_raw_state(recovery_path, dict(identity=identity, as_of=as_of, rows=rows, processed=processed,
            entity_hashes=entity_hashes, continuation=continuation, complete=complete,
            reader_position=None if complete else _reader_position()))
    last_save, due = time.monotonic(), False
    _progress('teacher_raw_rows', processed, None, force=True)
    with _RawStreams(T, _cpus()) as streams:
        for e, old, six in T._paired_raw(self.control, self.raw_teacher, evidence, as_of=as_of,
                                         source_manifest_hash=source_manifest_hash, continuation=continuation):
            processed += 1
            m = e['normalized']
            if entity is None or (m['publisher_id'], m['instrument_id']) == tuple(entity):
                entity_hashes[e['cursor']] = T.evidence_hash({k: e[k] for k in CONTEXT_FIELDS})   # the walk's fast path
            combined = [dict(v) for v in old]
            combined[7:13] = [{k: x for k, x in v.items() if k != 'mask'} for v in six['columns']]   # every carried key kept
            rows.append((False, e['receipt'] is not None, m['instrument_id'], combined, m['ts_recv_ns'],
                         e['terminal_prefix_hash'], e['cursor'], six['evidence_content_hash']))
            if retain_dstate:
                rows[-1] += (_dstate_row(e, continuation['control']),)
            streams.place(rows, len(rows) - 1)
            if recovery_path and save_requested is not None and save_requested():
                streams.finish()
                save(False)
                raise TeacherSaved('teacher saved after cursor %d; resume continues at %d' % (processed - 1, processed))
            if not processed & 1023:
                _progress('teacher_raw_rows', processed)
                if every is not None and not due and time.monotonic() - last_save >= every:
                    due = True                       # saved at the next row that closes its group
            if due and rows[-1][1] and not streams.batch:
                # a row that closes its group AND ends a raw batch exactly (no recorded call waiting for the next
                # submit): draining here moves no batch boundary, so every worker result is unpickled from the very
                # batch it would have been in without the save (the attachment pickle's object sharing, hence its
                # bytes, unchanged; a resume from it starts on the same boundary)
                due, began = False, time.monotonic()
                streams.finish()                     # every placeholder resolved; the pool stays up for the next rows
                save(False)
                last_save = time.monotonic()
                SAVE_RECORD['saves'].append(dict(processed=processed, cursor=e['cursor'],
                                                 seconds=round(last_save - began, 3), at=round(time.time(), 3)))
        streams.finish()
    _progress('teacher_raw_rows', processed, None, force=True)
    if any(type(v['reason']) is str and v['reason'].startswith(RAW_MARK) for row in rows for v in row[3]):
        raise ValueError('parallel teacher raw placeholder left unresolved; run stopped')
    if recovery_path:
        save(True)
    return rows, processed, entity_hashes


def context_spec(context):
    """What the finish needs of the context: each row's cursor, whether it is the 7-field session row, and its hash."""
    T = _modules()[0]
    context = list(context)
    return [(item['cursor'], set(item) == SESSION_FIELDS, T.evidence_hash(item)) for item in context]


def finish(self, rows, processed, entity_hashes, spec, *, source_manifest_hash,
           recovery_path=None, save_requested=None):
    """Steps 2-5: the exact-row check of the context against the rows the teacher read, then the normalizer, targets and
    receipts across the CPUs, exactly as before."""
    import torch  # noqa: F401  (attach imports it; the workers use it)
    T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes = _modules()
    if not spec:
        raise ValueError('nonempty complete prefix and context required')
    selected = tuple(cursor for cursor, _, _ in spec)
    widths = {len(row) for row in rows}
    if widths not in ({8}, {9}):
        raise ValueError('teacher rows mix incompatible DState capture coverage')
    if (any(type(cursor) is not int or cursor < 0 for cursor in selected)
            or tuple(sorted(set(selected))) != selected):
        raise ValueError('ordered unique context cursors required')
    for cursor, session_row, item_hash in spec:
        if (not session_row or cursor >= len(rows) or rows[cursor][6] != cursor
                or entity_hashes.get(cursor) != item_hash):
            raise ValueError('context must match exact verified prefix row')
        rows[cursor] = (True,) + rows[cursor][1:]
    dstate_rows = tuple(rows[cursor][8] for cursor in selected) if widths == {9} else None
    identity = isinstance(self.normalizer, R.IdentityNormalizerR3)
    code = Path(T.__file__).read_bytes()
    builder_sha = hashlib.sha1(b'blob ' + str(len(code)).encode() + b'\0' + code).hexdigest()
    units = (('log_seconds', 'log_seconds', 'share', 'log_quantity', 'log_quantity', 'share', 'share',
              'share', 'share', 'share', 'share', 'share', 'share', 'log_groups', 'log_count', 'log_ratio',
              'log_ticks', 'log_groups', 'log_ticks') if identity else ('z_score',) * 19)
    candidate = _candidate(self, T)
    planned = tuple(FINISH_WORKER_CPUS or ())
    cpus = len(planned) or _cpus()
    # 2. chunk-start states: attach's own restored copy, update() only
    config = self.normalizer.config
    instrument_ids = self.normalizer.config.instrument_ids
    base = (R.IdentityNormalizerR3(instrument_ids) if identity else
            R.NormalizerR3.restore(config, self.normalizer.export(), self.normalizer.state_hash))
    # chunk granularity only (each chunk restores its own exact start state, so no value depends on it): several
    # chunks per worker keep every CPU busy to the end of the pass (sibling threads, a redone chunk)
    size = max(1, -(-len(rows) // (cpus * FINISH_CHUNKS_PER_WORKER)))
    target_spec = dict(registry_id=f'boss/teacher/{T.CANDIDATE}:{candidate}', target_names=T.CONTROL_COLUMNS,
                       target_units=units, builder_code_sha=builder_sha)
    recovery_identity = dict(binding=self.binding, candidate=candidate, source=source_manifest_hash,
                             processed=processed, context=hashlib.sha256(_canonical(spec)).hexdigest(),
                             normalizer=self.normalizer.export(),
                             **_code_witness(FINISH_CODE))
    if dstate_rows is not None:
        recovery_identity['dstate_sha256'] = T.evidence_hash(dstate_rows)
    saved = _load_raw_state(recovery_path) if recovery_path and Path(recovery_path).exists() else None
    identity_notes = {}
    if saved and not _identity_accepted(saved['identity'], recovery_identity, recovery_path, identity_notes):
        raise ValueError('saved teacher attachment source, context or normalizer changed')
    if saved:
        recovery_identity = saved['identity']   # the saved document stays the identity (chunks are bound to it)
    jobs = saved['jobs'] if saved else []
    # Preparation is saved once; each result gets its own immutable, hash-bound file.
    # Rewriting all prior tensors after every chunk would turn recovery into quadratic I/O.
    blobs = dict(enumerate(saved.get('blobs', ()))) if saved else {}
    prepared = saved['prepared'] if saved else 0
    size = saved.get('chunk_size', size) if saved else size
    chunks_dir = Path(str(recovery_path) + '.chunks') if recovery_path else None
    def chunk_path(index):
        return chunks_dir / ('%08d.pkl' % index)
    def keep_chunk(index, blob):
        if recovery_path:
            _save_raw_state(chunk_path(index), dict(identity=recovery_identity, index=index, blob=blob))
        blobs[index] = blob
    if recovery_path:
        for index in range(len(jobs)):
            path = chunk_path(index)
            if path.exists():
                retained = _load_raw_state(path)
                if retained['identity'] != recovery_identity or retained['index'] != index:
                    raise ValueError('saved teacher attachment chunk belongs to another source or position')
                blobs[index] = retained['blob']
            elif index in blobs:       # preserve results saved by the earlier combined-state format
                keep_chunk(index, blobs[index])
    if saved and not identity:
        base = R.NormalizerR3.restore(config, saved['base'], saved['base_hash'])
    def save_finish():
        _save_raw_state(recovery_path, dict(identity=recovery_identity, jobs=jobs, chunk_size=size,
            prepared=prepared, base=None if identity else base.export(),
            base_hash=None if identity else base.state_hash))
    for start in range(prepared, len(rows), size):
        chunk = rows[start:start + size]
        payload = state = None
        if not identity:
            payload, state = base.export(), base.state_hash
            for _, has_receipt, iid, combined, *_ in chunk:
                if has_receipt:
                    for c, v in zip(T.CONTROL_COLUMNS, combined):
                        base.update(iid, c, v['value'], N.State(v['state']))
        jobs.append((identity, instrument_ids, config, payload, state, chunk, target_spec, source_manifest_hash))
        prepared = start + len(chunk)
        if recovery_path and save_requested and save_requested():
            save_finish()
            raise TeacherSaved('teacher saved all prepared attachment chunks and normalizer state')
    if recovery_path and (saved is None or prepared != saved['prepared'] or 'blobs' in saved):
        save_finish()
    # 3-4. the chunks across the CPUs, joined in order. Each worker pinned to one CPU of the plan (physical cores first,
    # set by the caller); a dead worker never stops the pass (Greg, 2026-10-07): the pool is rebuilt with one worker
    # fewer and every chunk in flight goes back to the front of the queue, in order (each chunk is a pure function of
    # its job); only the same chunk breaking the pool repeatedly is raised. The finished prefix of chunks is unpickled
    # and joined in order while later chunks still run (the same lists, the same order as joining at the end).
    import pickle
    from concurrent.futures.process import BrokenProcessPool
    targets, receipts, fragments = [], [], []

    def new_pool(workers):
        return _spawn_pool(workers, planned, FINISH_POOL_RECORD)
    workers = min(cpus, max(1, len(jobs)))
    FINISH_POOL_RECORD.clear()
    FINISH_POOL_RECORD.update(workers=workers, cpus=list(planned) or None, chunks=len(jobs), chunk_rows=size,
                              reused_chunks=len(blobs), rebuilds=[], **identity_notes,
                              basis=('each spawn worker pinned to one CPU of the plan' if planned else
                                     'unpinned spawn workers on the parent\'s mask (no plan given)'))
    joined = [0]

    def join_ready():
        while joined[0] < len(jobs) and joined[0] in blobs:
            for target, receipt, fragment in pickle.loads(blobs.pop(joined[0])):
                targets.append(target)
                receipts.append(receipt)
                fragments.append(fragment)
            joined[0] += 1
    pool = new_pool(workers)
    try:
        pending = deque()
        remaining = deque(index for index in range(len(jobs)) if index not in blobs)
        failure, breaks = None, {}
        def rebuild(lost, error):
            nonlocal pool, workers
            for other, other_future in pending:
                if (other_future.done() and not other_future.cancelled()
                        and other_future.exception() is None):
                    keep_chunk(other, other_future.result())       # finished before the pool broke: kept
                else:
                    lost.append(other)
            pending.clear()
            _bounded_shutdown(pool, FINISH_POOL_RECORD)
            workers = max(1, workers - 1)
            pool = new_pool(workers)
            remaining.extendleft(reversed(sorted(set(lost))))
            FINISH_POOL_RECORD['rebuilds'].append(dict(workers=workers, chunks_again=len(set(lost)),
                                                       error='%s: %s' % (type(error).__name__, error)))
        while remaining or pending:
            stopping = recovery_path and save_requested and save_requested()
            try:
                while not stopping and failure is None and remaining and len(pending) < workers:
                    index = remaining[0]
                    pending.append((index, pool.submit(_chunk, jobs[index])))
                    remaining.popleft()
            except BrokenProcessPool as error:     # the pool broke between results: the same redo, one fewer
                breaks[remaining[0]] = breaks.get(remaining[0], 0) + 1
                if breaks[remaining[0]] > RAW_POOL_MAX_CONSECUTIVE_BREAKS:
                    raise
                rebuild([], error)
                continue
            if pending:
                index, future = pending.popleft()
                try:
                    keep_chunk(index, future.result())
                    _progress('teacher_attachment_chunks', len(jobs) - len(remaining) - len(pending), len(jobs))
                except BrokenProcessPool as error:
                    breaks[index] = breaks.get(index, 0) + 1
                    if breaks[index] > RAW_POOL_MAX_CONSECUTIVE_BREAKS:
                        failure = failure or error
                        continue
                    rebuild([index], error)
                    continue
                except Exception as error:
                    # Drain and retain other work already in flight before propagating the failure.
                    # Resume schedules only missing chunks, including a failed chunk between successes.
                    failure = failure or error
                if failure is None:
                    join_ready()
            elif failure is not None:
                raise failure
            elif stopping:
                raise TeacherSaved('teacher saved every completed attachment chunk; no outstanding workers')
        if failure is not None:
            raise failure
        if recovery_path and save_requested and save_requested():
            raise TeacherSaved('teacher attachment calculations saved before publication')
    finally:
        _bounded_shutdown(pool, FINISH_POOL_RECORD)
    _progress('teacher_attachment_chunks', len(jobs), len(jobs), force=True)
    join_ready()
    if joined[0] != len(jobs):
        raise ValueError('parallel teacher attachment chunk missing at join; run stopped')
    raw_rows = [row[3] for row in rows if row[0]]
    if not processed or len(targets) != len(spec):
        raise ValueError('context cursor absent from complete prefix')
    # 5. evidence_hash(receipts) == sha256(prefix + canonical(pack(list))); pack(list) = ["list", [pack(r)...]]
    attachment = hashlib.sha256(DIGEST_PREFIX + b'["list",[' + b','.join(fragments) + b']]').hexdigest()
    if len(receipts) <= FULL_HASH_CHECK_RECEIPTS and attachment != T.evidence_hash(receipts):
        raise ValueError('parallel teacher attachment hash differs; run stopped')
    return dict(targets=tuple(targets), raw=raw_rows, processed_records=processed,
                context_cursors=selected, step_receipts=tuple(receipts),
                attachment_hash=attachment, candidate_digest=candidate,
                **(dict(dstate_rows=dstate_rows) if dstate_rows is not None else {}))


def parallel_attach(self, evidence, context, *, as_of, source_manifest_hash):
    """JournalTeacherR3.attach across the box's CPUs. When the concurrent teacher (concurrent_teacher.py) has been reading
    the journal since the first walk began, the context is handed to it and its result returned: the journal is NOT
    walked a second time (the evidence generator given here is never started). Otherwise the row pass runs here."""
    from . import concurrent_teacher
    context = list(context)
    running = concurrent_teacher.current(as_of=as_of, source_manifest_hash=source_manifest_hash)
    if running is not None:
        return running.result(context_spec(context))
    rows, processed, entity_hashes = row_pass(self, evidence, as_of=as_of, source_manifest_hash=source_manifest_hash)
    return finish(self, rows, processed, entity_hashes, context_spec(context), source_manifest_hash=source_manifest_hash)
