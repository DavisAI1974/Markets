"""The R3 teacher's attachment across the box's CPUs (Greg, 2026-09-28: "Fix the 1 cpu issue").

c15_teacher_r3.JournalTeacherR3.attach (pinned, unchanged) walks the complete prefix once, in order, on one core, and for
EVERY context row (the Monday's context is the whole day) it
  - observes 19 columns on the running NormalizerR3 (two statistics.median over a 4096-value window each: ~18 ms/row),
  - builds a DipoleTarget (tensors + canonical hash),
  - takes normalizer.receipt(): two source-file reads and evidence_hash(normalizer.export()) over all 19 windows of up to
    4096 floats and their hex (~0.3-0.4 s/row measured on one core),
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


def _cpus():
    try:
        return max(1, len(os.sched_getaffinity(0)) - 1)
    except (AttributeError, OSError):
        return max(1, (os.cpu_count() or 2) - 1)


def parallel_attach(self, evidence, context, *, as_of, source_manifest_hash):
    """JournalTeacherR3.attach, the per-row normalizer, target and receipt work across the box's CPUs."""
    import torch  # noqa: F401  (attach imports it; the workers use it)
    T, N, R, D, SCHEMA, pack, DIGEST_PREFIX, canonical_tagged_bytes = _modules()
    context = list(context)
    if type(as_of) is not int or as_of < 0:
        raise ValueError('nonnegative as_of required')
    if not context:
        raise ValueError('nonempty complete prefix and context required')
    selected = tuple(e['cursor'] for e in context)
    if (any(type(cursor) is not int or cursor < 0 for cursor in selected)
            or tuple(sorted(set(selected))) != selected):
        raise ValueError('ordered unique context cursors required')
    session_fields = {'cursor', 'raw_record', 'normalized', 'source_member_index',
                      'session_id', 'integrity', 'terminal_prefix_hash'}
    selected_rows = {item['cursor']: item for item in context}
    identity = isinstance(self.normalizer, R.IdentityNormalizerR3)
    code = Path(T.__file__).read_bytes()
    builder_sha = hashlib.sha1(b'blob ' + str(len(code)).encode() + b'\0' + code).hexdigest()
    units = (('log_seconds', 'log_seconds', 'share', 'log_quantity', 'log_quantity', 'share', 'share',
              'share', 'share', 'share', 'share', 'share', 'share', 'log_groups', 'log_count', 'log_ratio',
              'log_ticks', 'log_groups', 'log_ticks') if identity else ('z_score',) * 19)
    wanted = set(selected)
    # 1. the pinned raw streams, in order, with the exact-row check (attach's own loop minus the normalizer)
    rows, processed = [], 0
    for e, old, six in T._paired_raw(self.control, self.raw_teacher, evidence, as_of=as_of,
                                     source_manifest_hash=source_manifest_hash):
        processed += 1
        if e['cursor'] in wanted:
            item = selected_rows[e['cursor']]
            if (set(item) not in (session_fields, set(e))
                    or T.evidence_hash(item) != T.evidence_hash({k: e[k] for k in item})):
                raise ValueError('context must match exact verified prefix row')
        combined = [dict(v) for v in old]
        combined[7:13] = [{k: v[k] for k in ('value', 'state', 'reason')} for v in six['columns']]
        rows.append((e['cursor'] in wanted, e['receipt'] is not None, e['normalized']['instrument_id'], combined,
                     e['normalized']['ts_recv_ns'], e['terminal_prefix_hash'], e['cursor'], six['evidence_content_hash']))
    # 2. chunk-start states: attach's own restored copy, update() only
    config = self.normalizer.config
    instrument_ids = self.normalizer.config.instrument_ids
    base = (R.IdentityNormalizerR3(instrument_ids) if identity else
            R.NormalizerR3.restore(config, self.normalizer.export(), self.normalizer.state_hash))
    cpus = _cpus()
    size = max(1, -(-len(rows) // (cpus * 2)))
    spec = dict(registry_id=f'boss/teacher/{T.CANDIDATE}:{self.candidate_digest}', target_names=T.CONTROL_COLUMNS,
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
        jobs.append((identity, instrument_ids, config, payload, state, chunk, spec, source_manifest_hash))
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
    if not processed or len(targets) != len(context):
        raise ValueError('context cursor absent from complete prefix')
    # 5. evidence_hash(receipts) == sha256(prefix + canonical(pack(list))); pack(list) = ["list", [pack(r)...]]
    attachment = hashlib.sha256(DIGEST_PREFIX + b'["list",[' + b','.join(fragments) + b']]').hexdigest()
    if len(receipts) <= 4096 and attachment != T.evidence_hash(receipts):
        raise ValueError('parallel teacher attachment hash differs; run stopped')
    return dict(targets=tuple(targets), raw=raw_rows, processed_records=processed,
                context_cursors=selected, step_receipts=tuple(receipts),
                attachment_hash=attachment, candidate_digest=self.candidate_digest)
