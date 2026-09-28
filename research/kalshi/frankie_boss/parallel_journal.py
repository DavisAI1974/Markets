"""Parallel journal prefix (Greg, 2026-09-28: "We have to fix that 1 cpu problem").

The first cycle's context preparation walks the whole C15 journal through context_session.journal_prefix: the
compact reader already decodes blocks on worker CPUs, but the ordered parent then does, per entry, the INPUT/APPLIED
pairing check (pack() of both records) and, for EVERY in-cutoff APPLIED entry, summary.update(journal_prefix_hash=
evidence_hash(entry)) -- a full canonical hash about 2M times for the Monday -- on one core (profile of launch r4,
2026-09-28: pack 28%, typing/abc checks 40%, causal_packet._canon 12%, json 6%, all under context_session.py:155).

This module yields exactly what journal_prefix yields over a FrankieCompactReader, in the same order, with the same
checks and the same final summary, but the per-entry work runs in the block workers: each worker decodes and verifies
its block (frankie_journal_reader._read_block, the reader's own task), pairs the entries inside the block, and hashes
only the block's LAST in-cutoff APPLIED envelope (the summary keeps only the last value). A block's leading APPLIED or
trailing INPUT is paired by the parent across the seam with the same checks. The parent keeps the reader's ordered
seam checks and its terminal count/head/seal check, and journal_prefix's terminal pending/applied check.

context_session.py and c15_journal.py are NOT changed (both are inside the pinned native model hash): prepare_parallel
swaps the module-level journal_prefix only for one _prepare call, so the pinned _prepare body runs unchanged on top.
Any other journal type (VerifiedJournalReader) falls back to the original serial journal_prefix.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import multiprocessing
import sys

import hashlib
import re

from .c15_journal import SCHEMA, evidence_hash, pack
from .causal_packet import canonical_bytes
from .frankie_journal_reader import FrankieCompactReader, _assign_cpu, _read_block


def _same_record(applied, pending):
    return (pending is not None and applied['cursor'] == pending['cursor']
            and pack(applied['raw_record']) == pack(pending['record'])
            and all(applied[k] == pending[k] for k in ('source_member_index', 'session_id')))


# The first walk's consumer (the pinned _prepare) reads only these fields of each payload (context_session.py:155-167);
# the order-book fields (observation, effect, orders) are the bulk of a payload and never cross to the parent there.
CONTEXT_FIELDS = ('cursor', 'raw_record', 'normalized', 'source_member_index', 'session_id', 'integrity',
                  'terminal_prefix_hash')


def _prefix_block(path, index, through_cursor, mode='full'):
    """Decode and verify one block (the reader's task), then pair and select exactly as journal_prefix does.
    mode 'context': ship only CONTEXT_FIELDS; mode 'teacher': ship the full payload and its canonical bytes."""
    entries, cpu = _read_block(path, index)
    lead, tail, pending, first_input, expected, applied = None, None, None, None, None, 0
    payloads, last = [], None
    for position, entry in enumerate(entries):
        payload = entry['payload']
        if entry['kind'] == 'INPUT':
            if pending is not None or (expected is not None and payload['cursor'] != expected):
                raise ValueError('journal input cursor gap or unprocessed submission')
            if first_input is None:
                first_input = payload['cursor']
            pending = payload
        elif entry['kind'] == 'APPLIED':
            if pending is None:
                if position != 0:
                    raise ValueError('journal applied record differs from submitted evidence')
                lead = dict(payload=payload, envelope_hash=evidence_hash(entry), entries=entry['ordinal'] + 1,
                            canonical=canonical_bytes(pack(payload)) if mode == 'teacher' else None)
                expected = payload['cursor'] + 1
                continue
            if not _same_record(payload, pending):
                raise ValueError('journal applied record differs from submitted evidence')
            applied += 1
            expected = payload['cursor'] + 1
            pending = None
            if payload['cursor'] <= through_cursor:
                if mode == 'context':
                    payloads.append({k: payload[k] for k in CONTEXT_FIELDS})
                elif mode == 'teacher':
                    payloads.append((payload, canonical_bytes(pack(payload))))
                else:
                    payloads.append(payload)
                last = entry
        else:
            raise ValueError('failed or unknown journal entry cannot be mapped as complete')
    tail = pending
    summary = None if last is None else (evidence_hash(last), last['ordinal'] + 1)
    return dict(count=len(entries), lead=lead, first_input=first_input, applied=applied, payloads=payloads,
                tail=tail, summary=summary, cpu=cpu)


def parallel_journal_prefix(builder, through_cursor, summary=None):
    """Same contract as context_session.journal_prefix for a FrankieCompactReader journal."""
    journal = builder.journal
    if not isinstance(journal, FrankieCompactReader):
        yield from _SERIAL(builder, through_cursor, summary)
        return
    if builder._failed:
        raise ValueError('unprocessed evidence exists; builder is stopped')
    if type(through_cursor) is not int or not 0 <= through_cursor < builder.chain.next_cursor:
        raise ValueError('cutoff cursor outside applied journal')
    # the pinned _prepare walks twice: its own pass passes a summary, the teacher's pass does not
    mode = 'context' if summary is not None else 'teacher'
    context = multiprocessing.get_context('spawn')
    assignments = context.Queue()
    for cpu in journal.worker_cpus:
        assignments.put(cpu)
    index = iter(journal.db.execute('SELECT start,count,previous,head FROM blocks ORDER BY start').fetchall())
    count, head, applied, pending = 0, journal_genesis(), 0, None
    try:
        with ProcessPoolExecutor(max_workers=len(journal.worker_cpus), mp_context=context,
                                 initializer=_assign_cpu, initargs=(assignments,)) as pool:
            window = deque()

            def submit():
                row = next(index, None)
                if row is not None:
                    window.append((row, pool.submit(_prefix_block, str(journal.path), row, through_cursor, mode)))

            for _ in range(2 * len(journal.worker_cpus)):         # bounded, as the reader: no full-day materialization
                submit()
            while window:
                row, future = window.popleft()
                start, length, previous, terminal = row
                part = future.result()
                if start != count or previous != head or part['count'] != length or count + length > journal.count:
                    raise ValueError('ordered compact seam differs')
                if part['lead'] is not None:                        # an APPLIED whose INPUT closed the previous block
                    lead = part['lead']['payload']
                    if not _same_record(lead, pending):
                        raise ValueError('journal applied record differs from submitted evidence')
                    applied, pending = applied + 1, None
                    if lead['cursor'] <= through_cursor:
                        if summary is not None:
                            summary.update(journal_prefix_hash=part['lead']['envelope_hash'],
                                           journal_entries=part['lead']['entries'])
                        yield _emit(lead, part['lead']['canonical'], mode)
                if part['first_input'] is not None and (pending is not None or part['first_input'] != applied):
                    raise ValueError('journal input cursor gap or unprocessed submission')
                applied += part['applied']
                if part['summary'] is not None and summary is not None:
                    summary.update(journal_prefix_hash=part['summary'][0], journal_entries=part['summary'][1])
                for item in part['payloads']:
                    yield _emit(item[0], item[1], mode) if mode == 'teacher' else item
                if part['tail'] is not None:
                    pending = part['tail']
                count, head = count + length, terminal
                journal.worker_cpu_seconds += part['cpu']
                submit()
        if (count, head) != (journal.count, journal.head_hash):
            raise ValueError('compact terminal identity differs')
        journal._check_seal()
    finally:
        assignments.close()
        assignments.join_thread()
    if pending is not None or applied != builder.chain.next_cursor:
        raise ValueError('journal does not account for every source record')


_CANONICAL = {}          # id(payload) -> (payload, canonical bytes), filled as the teacher's walk yields, popped on use


def _emit(payload, canonical, mode):
    if mode == 'teacher' and canonical is not None:
        _CANONICAL[id(payload)] = (payload, canonical)
    elif mode == 'context':
        payload = {k: payload[k] for k in CONTEXT_FIELDS}
    return payload


_CHECKED = [0]


def _chain_hash_factory(original):
    """The r3 teacher chains content = evidence_hash(dict(previous=content, evidence=e)) over every row. That is
    sha256(SCHEMA \\0 canonical_bytes(pack(...))) and canonical_bytes is compact JSON over the tagged tree, so the bytes
    are exactly  ["dict",[["previous",["str","<64 hex>"]],["evidence",<canonical_bytes(pack(e))>]]] . The workers
    computed canonical_bytes(pack(e)); only the sha256 runs here, in order. The first 64 chained hashes are also
    computed the original way and must match, or the run stops."""
    prefix = SCHEMA.encode() + b'\0["dict",[["previous",["str","'

    def chained(payload):
        if type(payload) is dict and len(payload) == 2 and list(payload) == ['previous', 'evidence']:
            previous, evidence = payload['previous'], payload['evidence']
            entry = _CANONICAL.pop(id(evidence), None)
            if (entry is not None and entry[0] is evidence and type(previous) is str
                    and re.fullmatch('[0-9a-f]{64}', previous)):
                value = hashlib.sha256(prefix + previous.encode() + b'"]],["evidence",' + entry[1] + b']]]').hexdigest()
                if _CHECKED[0] < 64:
                    _CHECKED[0] += 1
                    if value != original(payload):
                        raise ValueError('parallel teacher content hash differs from evidence_hash; run stopped')
                return value
        return original(payload)
    return chained


def journal_genesis():
    from .verified_journal_reader import GENESIS_HASH
    return GENESIS_HASH


_SERIAL = None


@contextmanager
def parallel_walk(context):
    """For the duration of one preparation, the pinned _prepare walks the journal in parallel."""
    global _SERIAL
    module = sys.modules[type(context).__module__]
    original = module.journal_prefix
    _SERIAL = original
    teacher = sys.modules.get(__package__ + '.c15_teacher_r3')
    teacher_hash = getattr(teacher, 'evidence_hash', None)
    module.journal_prefix = parallel_journal_prefix
    if teacher is not None:
        teacher.evidence_hash = _chain_hash_factory(teacher_hash)
    try:
        yield
    finally:
        module.journal_prefix = original
        if teacher is not None:
            teacher.evidence_hash = teacher_hash
        _CANONICAL.clear()


def prepare_parallel(context, as_of, through_cursor):
    """context._prepare with the journal walked across the box's CPUs; the pinned _prepare body is unchanged."""
    with parallel_walk(context):
        return type(context)._prepare(context, as_of, through_cursor)
