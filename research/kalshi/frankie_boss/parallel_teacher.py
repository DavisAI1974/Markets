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
Pinned files unchanged: c15_teacher_r3.py, c15_teacher.py, c15_normalizer.py, c15_normalizer_r3.py, dipole_target.py.
"""
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import hashlib
import multiprocessing
import os
from pathlib import Path
import struct
import sys

GUARD_EVERY = 50_000
FULL_HASH_CHECK_RECEIPTS = 2_000   # up to this many receipts the attachment hash is also recomputed whole (a check, no cap)
RAW_GUARD_EVERY = 20_000
RAW_BATCH_CALLS = 32_768
RAW_MARK = '\x00parallel-raw:'


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
    for wanted, has_receipt, iid, combined, now, prefix, cursor, content in rows:
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

        import multiprocessing
        self.pool = ProcessPoolExecutor(max_workers=self.cpus, mp_context=multiprocessing.get_context('spawn'))
        T.JournalTeacher._dynamics = staticmethod(record_dynamics)
        T._absorption, T._cohort = record_absorption, record_cohort
        return self

    def _submit(self):
        import pickle
        if not self.batch:
            return
        blob = pickle.dumps((self.tables, self.batch, _changes_applied()), protocol=pickle.HIGHEST_PROTOCOL)
        self.pending.append(self.pool.submit(_raw_batch, blob))
        self._new_batch()
        while len(self.pending) > 2 * self.cpus:          # bounded: never the whole day's windows in flight
            self._collect(self.pending.popleft())

    def _collect(self, future):
        import pickle
        for token, value in pickle.loads(future.result()):
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
            # every carried key kept (incomplete lists, unknown-side counts); R3's model-side mask left out as attach does
            self.rows[index][3][column] = ({k: x for k, x in v.items() if k != 'mask'} if 7 <= column < 13 else dict(v))
        self.resolved += 1

    def finish(self):
        self._submit()
        while self.pending:
            self._collect(self.pending.popleft())
        if self.expected or self.where or self.early or self.resolved != self.calls:
            raise ValueError('parallel teacher raw call unresolved; run stopped')

    def __exit__(self, *exc):
        T = self.T
        T.JournalTeacher._dynamics = self.original[0]
        T._absorption, T._cohort = self.original[1], self.original[2]
        for future in self.pending:
            future.cancel()
        self.pool.shutdown(wait=True, cancel_futures=True)
        return False


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


def row_pass(self, evidence, *, as_of, source_manifest_hash):
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
    with _RawStreams(T, _cpus()) as streams:
        for e, old, six in T._paired_raw(self.control, self.raw_teacher, evidence, as_of=as_of,
                                         source_manifest_hash=source_manifest_hash):
            processed += 1
            m = e['normalized']
            if entity is None or (m['publisher_id'], m['instrument_id']) == tuple(entity):
                entity_hashes[e['cursor']] = T.evidence_hash({k: e[k] for k in CONTEXT_FIELDS})   # the walk's fast path
            combined = [dict(v) for v in old]
            combined[7:13] = [{k: x for k, x in v.items() if k != 'mask'} for v in six['columns']]   # every carried key kept
            rows.append((False, e['receipt'] is not None, m['instrument_id'], combined, m['ts_recv_ns'],
                         e['terminal_prefix_hash'], e['cursor'], six['evidence_content_hash']))
            streams.place(rows, len(rows) - 1)
        streams.finish()
    if any(type(v['reason']) is str and v['reason'].startswith(RAW_MARK) for row in rows for v in row[3]):
        raise ValueError('parallel teacher raw placeholder left unresolved; run stopped')
    return rows, processed, entity_hashes


def context_spec(context):
    """What the finish needs of the context: each row's cursor, whether it is the 7-field session row, and its hash."""
    T = _modules()[0]
    context = list(context)
    return [(item['cursor'], set(item) == SESSION_FIELDS, T.evidence_hash(item)) for item in context]


def finish(self, rows, processed, entity_hashes, spec, *, source_manifest_hash):
    """Steps 2-5: the exact-row check of the context against the rows the teacher read, then the normalizer, targets and
    receipts across the CPUs, exactly as before."""
    import torch  # noqa: F401  (attach imports it; the workers use it)
    T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes = _modules()
    if not spec:
        raise ValueError('nonempty complete prefix and context required')
    selected = tuple(cursor for cursor, _, _ in spec)
    if (any(type(cursor) is not int or cursor < 0 for cursor in selected)
            or tuple(sorted(set(selected))) != selected):
        raise ValueError('ordered unique context cursors required')
    for cursor, session_row, item_hash in spec:
        if (not session_row or cursor >= len(rows) or rows[cursor][6] != cursor
                or entity_hashes.get(cursor) != item_hash):
            raise ValueError('context must match exact verified prefix row')
        rows[cursor] = (True,) + rows[cursor][1:]
    identity = isinstance(self.normalizer, R.IdentityNormalizerR3)
    code = Path(T.__file__).read_bytes()
    builder_sha = hashlib.sha1(b'blob ' + str(len(code)).encode() + b'\0' + code).hexdigest()
    units = (('log_seconds', 'log_seconds', 'share', 'log_quantity', 'log_quantity', 'share', 'share',
              'share', 'share', 'share', 'share', 'share', 'share', 'log_groups', 'log_count', 'log_ratio',
              'log_ticks', 'log_groups', 'log_ticks') if identity else ('z_score',) * 19)
    candidate = _candidate(self, T)
    cpus = _cpus()
    # 2. chunk-start states: attach's own restored copy, update() only
    config = self.normalizer.config
    instrument_ids = self.normalizer.config.instrument_ids
    base = (R.IdentityNormalizerR3(instrument_ids) if identity else
            R.NormalizerR3.restore(config, self.normalizer.export(), self.normalizer.state_hash))
    size = max(1, -(-len(rows) // (cpus * 2)))
    target_spec = dict(registry_id=f'boss/teacher/{T.CANDIDATE}:{candidate}', target_names=T.CONTROL_COLUMNS,
                       target_units=units, builder_code_sha=builder_sha)
    jobs = []
    for start in range(0, len(rows), size):
        chunk = rows[start:start + size]
        payload = state = None
        if not identity:
            payload, state = base.export(), base.state_hash
            for _, has_receipt, iid, combined, *_ in chunk:
                if has_receipt:
                    for c, v in zip(T.CONTROL_COLUMNS, combined):
                        base.update(iid, c, v['value'], N.State(v['state']))
        jobs.append((identity, instrument_ids, config, payload, state, chunk, target_spec, source_manifest_hash))
    # 3-4. the chunks across the CPUs, joined in order
    targets, receipts, fragments = [], [], []
    context_mp = multiprocessing.get_context('spawn')
    with ProcessPoolExecutor(max_workers=min(cpus, max(1, len(jobs))), mp_context=context_mp) as pool:
        import pickle
        for blob in pool.map(_chunk, jobs):
            for target, receipt, fragment in pickle.loads(blob):
                targets.append(target)
                receipts.append(receipt)
                fragments.append(fragment)
    raw_rows = [row[3] for row in rows if row[0]]
    if not processed or len(targets) != len(spec):
        raise ValueError('context cursor absent from complete prefix')
    # 5. evidence_hash(receipts) == sha256(prefix + canonical(pack(list))); pack(list) = ["list", [pack(r)...]]
    attachment = hashlib.sha256(DIGEST_PREFIX + b'["list",[' + b','.join(fragments) + b']]').hexdigest()
    if len(receipts) <= FULL_HASH_CHECK_RECEIPTS and attachment != T.evidence_hash(receipts):
        raise ValueError('parallel teacher attachment hash differs; run stopped')
    return dict(targets=tuple(targets), raw=raw_rows, processed_records=processed,
                context_cursors=selected, step_receipts=tuple(receipts),
                attachment_hash=attachment, candidate_digest=candidate)


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
