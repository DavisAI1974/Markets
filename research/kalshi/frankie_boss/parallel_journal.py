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
from pathlib import Path
import sys

import hashlib
import json
import re
import sqlite3
import time
import zlib

from .c15_journal import SCHEMA, evidence_hash, pack
from .causal_packet import canonical_bytes
from .frankie_journal_reader import FrankieCompactReader, _assign_cpu, _read_block
from .compact_journal import FORMAT, MAX_BYTES, MAX_ROWS, _field, _orders
from .verified_journal_reader import DIGEST_PREFIX, canonical_tagged_bytes, decode_tagged


# ---- one parse per entry (Greg, 2026-09-28: "Correct the code to send it out again. It's extremely important") -----
# r7's whole-process profile: each block worker spent ~38% in json encoding, ~27% in json decoding, ~17% in the tagged
# decode and partition checks. Per entry the pinned reader (frankie_journal_reader._read_block, unchanged and pinned):
#   decode_block: json.loads of the whole block -> tree; body = canonical_tagged_bytes(tree); sha256(prefix+body)==digest
#   verified_partition: tree2 = json.loads(body); envelope = decode_tagged(tree2); canonical_tagged_bytes(tree2)==body;
#                       sha256(prefix+body)==digest again; ordinal/schema/kind/previous continuity
# and then this module's pairing packed both records (pack) and the teacher pass packed and encoded every payload again.
# For a tree that came from json.loads, json.dumps(json.loads(json.dumps(tree))) == json.dumps(tree) and
# json.loads(json.dumps(tree)) == tree, so the second decode, the second encode and the repeated digest are the same
# computation over the same bytes: _read_block_fast keeps the tree, encodes it once (the body, whose digest it checks),
# decodes the envelope from that tree and runs every other check of the pinned pair. Because pack(decode_tagged(node))
# == node and canonical_tagged_bytes == canonical_bytes on pack output (verified_journal_reader's own docstring),
#   pack(x) == pack(y)                    <=>  node(x) == node(y)                         (the pairing check)
#   canonical_bytes(pack(payload))        ==   canonical_tagged_bytes(payload node)       (the teacher's chain bytes)
#   evidence_hash(entry)                  ==   the entry's digest                          (lead and summary hashes)
#   evidence_hash(7-field context row)    ==   sha256(prefix + canonical_tagged_bytes(['dict', [[k, node_k]...]]))
# Each worker's FIRST block is also read by the pinned _read_block and every one of these values is recomputed the
# original way; any difference stops the run.
def _decode_block_trees(blob):
    """compact_journal.decode_block with the same checks, keeping each record's tagged tree beside its body."""
    if type(blob) is not bytes or len(blob) > MAX_BYTES:
        raise ValueError('compressed block exceeds byte bound')
    try:
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(blob, MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('truncated, trailing or oversized block')
        version, dictionary, records = json.loads(raw)
        if (version != FORMAT or type(dictionary) is not list or type(records) is not list
                or not 0 < len(records) <= MAX_ROWS):
            raise ValueError('invalid block schema')
        rows, total = [], 0
        for ordinal, kind, tree, indices, digest, size in records:
            if type(size) is not int or not 0 < size <= MAX_BYTES:
                raise ValueError('invalid reconstructed size')
            total += size
            if total > MAX_BYTES:
                raise ValueError('reconstruction exceeds byte bound')
            if indices is not None:
                orders = _orders(tree)
                if (orders != ['list', []] or type(indices) is not list
                        or any(type(i) is not int or not 0 <= i < len(dictionary) for i in indices)):
                    raise ValueError('invalid order references')
                orders[1] = [dictionary[i] for i in indices]
            body = canonical_tagged_bytes(tree)
            if len(body) != size or hashlib.sha256(DIGEST_PREFIX+body).hexdigest() != digest:
                raise ValueError('reconstructed body identity differs')
            rows.append((ordinal, kind, tree, body, digest))
        return rows
    except (zlib.error, TypeError, KeyError, IndexError, StopIteration, RecursionError) as exc:
        raise ValueError('invalid compressed journal block') from exc


def _read_block_fast(path, index):
    """frankie_journal_reader._read_block's entries and checks, one parse per entry; also each entry's tree and digest."""
    start, length, previous, head = index
    started = time.process_time()
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        row = db.execute('SELECT count,body,sha256,previous,head FROM blocks WHERE start=?', (start,)).fetchone()
    finally:
        db.close()
    if (row is None or (row[0], row[3], row[4]) != (length, previous, head)
            or hashlib.sha256(row[1]).hexdigest() != row[2]):
        raise ValueError('compact block identity differs')
    rows = _decode_block_trees(row[1])
    if len(rows) != length or rows[-1][4] != head:
        raise ValueError('compact block coverage differs')
    entries, trees, digests, count = [], [], [], start
    for ordinal, kind, tree, body, digest in rows:
        envelope = decode_tagged(tree)
        if (type(envelope) is not dict or ordinal != count or envelope.get('ordinal') != ordinal
                or envelope.get('schema') != SCHEMA or envelope.get('kind') != kind
                or envelope.get('previous_hash') != previous):
            raise ValueError('evidence journal continuity or hash mismatch')
        previous, count = digest, count + 1
        entries.append(envelope); trees.append(tree); digests.append(digest)
    return entries, trees, digests, time.process_time() - started


def _tagged_hash(node):
    return hashlib.sha256(DIGEST_PREFIX + canonical_tagged_bytes(node)).hexdigest()


def _context_node(payload_node):
    return ['dict', [[k, _field(payload_node, k)] for k in CONTEXT_FIELDS]]


_GUARDED = [False]      # per worker process: its first block is checked against the pinned reader


def _guard(path, index, entries, trees, digests):
    """The pinned reader and the original computations on this worker's first block; any difference stops the run."""
    original, _ = _read_block(path, index)
    if original != entries:
        raise ValueError('fast block reader differs from the pinned reader; run stopped')
    for entry, tree, digest in zip(entries, trees, digests):
        payload, node = entry['payload'], _field(tree, 'payload')
        if (evidence_hash(entry) != digest or pack(payload) != node
                or canonical_bytes(pack(payload)) != canonical_tagged_bytes(node)):
            raise ValueError('fast journal hashes differ from the original computation; run stopped')
        if entry['kind'] == 'APPLIED' and (evidence_hash({k: payload[k] for k in CONTEXT_FIELDS})
                                           != _tagged_hash(_context_node(node))):
            raise ValueError('fast context row hash differs from the original computation; run stopped')


def _same_record(applied, pending):
    return (pending is not None and applied['cursor'] == pending['cursor']
            and pack(applied['raw_record']) == pack(pending['record'])
            and all(applied[k] == pending[k] for k in ('source_member_index', 'session_id')))


# The first walk's consumer (the pinned _prepare) reads only these fields of each payload (context_session.py:155-167);
# the order-book fields (observation, effect, orders) are the bulk of a payload and never cross to the parent there.
CONTEXT_FIELDS = ('cursor', 'raw_record', 'normalized', 'source_member_index', 'session_id', 'integrity',
                  'terminal_prefix_hash')


def _prefix_block(path, index, through_cursor, mode='full', entity=None):
    """Decode and verify one block (the reader's task), then pair and select exactly as journal_prefix does.
    mode 'context': ship only CONTEXT_FIELDS; mode 'teacher': ship the full payload and its canonical bytes; both also
    ship the entity's 7-field row hash."""
    entries, trees, digests, cpu = _read_block_fast(path, index)
    if not _GUARDED[0]:
        _GUARDED[0] = True
        _guard(path, index, entries, trees, digests)
    lead, tail, pending, first_input, expected, applied = None, None, None, None, None, 0
    payloads, last, pending_node = [], None, None

    def subset(payload, node):
        m = payload['normalized']
        if entity is None or (m['publisher_id'], m['instrument_id']) != entity:
            return None
        return _tagged_hash(_context_node(node))

    for position, (entry, tree, digest) in enumerate(zip(entries, trees, digests)):
        payload, node = entry['payload'], _field(tree, 'payload')
        if entry['kind'] == 'INPUT':
            if pending is not None or (expected is not None and payload['cursor'] != expected):
                raise ValueError('journal input cursor gap or unprocessed submission')
            if first_input is None:
                first_input = payload['cursor']
            pending, pending_node = payload, node
        elif entry['kind'] == 'APPLIED':
            if pending is None:
                if position != 0:
                    raise ValueError('journal applied record differs from submitted evidence')
                lead = dict(payload=payload, envelope_hash=digest, entries=entry['ordinal'] + 1,
                            canonical=canonical_tagged_bytes(node) if mode == 'teacher' else None,
                            subset=subset(payload, node) if mode != 'full' else None)
                expected = payload['cursor'] + 1
                continue
            # _same_record: pack(raw_record) == pack(record) is the same comparison as their tagged nodes
            applied_record, submitted_record = _field(node, 'raw_record'), _field(pending_node, 'record')
            if applied_record is None or submitted_record is None:
                raise KeyError('raw_record' if applied_record is None else 'record')      # as payload[...] would
            if not (payload['cursor'] == pending['cursor']
                    and applied_record == submitted_record
                    and all(payload[k] == pending[k] for k in ('source_member_index', 'session_id'))):
                raise ValueError('journal applied record differs from submitted evidence')
            applied += 1
            expected = payload['cursor'] + 1
            pending = pending_node = None
            if payload['cursor'] <= through_cursor:
                if mode == 'context':
                    payloads.append(({k: payload[k] for k in CONTEXT_FIELDS}, subset(payload, node)))
                elif mode == 'teacher':
                    payloads.append((payload, canonical_tagged_bytes(node), subset(payload, node)))
                else:
                    payloads.append(payload)
                last = (entry, digest)
        else:
            raise ValueError('failed or unknown journal entry cannot be mapped as complete')
    tail = pending
    summary = None if last is None else (last[1], last[0]['ordinal'] + 1)
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
    entity = _ENTITY[0]
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
                    window.append((row, pool.submit(_prefix_block, str(journal.path), row, through_cursor, mode,
                                                                 entity)))

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
                        yield _emit(lead, part['lead']['canonical'], mode, part['lead']['subset'])
                if part['first_input'] is not None and (pending is not None or part['first_input'] != applied):
                    raise ValueError('journal input cursor gap or unprocessed submission')
                applied += part['applied']
                if part['summary'] is not None and summary is not None:
                    summary.update(journal_prefix_hash=part['summary'][0], journal_entries=part['summary'][1])
                for item in part['payloads']:
                    yield _emit(item[0], item[1] if mode == 'teacher' else None, mode, item[-1])
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
_SUBSETS = {}            # (pass, cursor) -> (7-field row hash, id(raw_record)) for the entity's rows, popped on use
_ENTITY = [None]         # the session's (publisher_id, instrument_id) during parallel_walk


def _emit(payload, canonical, mode, subset=None):
    if mode == 'teacher' and canonical is not None:
        _CANONICAL[id(payload)] = (payload, canonical)
    elif mode == 'context' and list(payload) != list(CONTEXT_FIELDS):   # a seam lead arrives as the full payload
        payload = {k: payload[k] for k in CONTEXT_FIELDS}
    if subset is not None:
        _SUBSETS[(mode, payload['cursor'])] = (subset, id(payload['raw_record']))
    return payload


_CHECKED = [0]
_SUBSET_CHECKED = [0]


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
        if (type(payload) is dict and list(payload) == list(CONTEXT_FIELDS) and type(payload['cursor']) is int):
            # the teacher's exact-row check (c15_teacher_r3.py:349): both dicts are an entity row's 7 fields over the
            # very objects a walk yielded (the context item from the context pass, the subset of the teacher pass's
            # payload); both are alive during the check, so the recorded object id identifies the row
            for side in ('context', 'teacher'):
                entry = _SUBSETS.get((side, payload['cursor']))
                if entry is not None and entry[1] == id(payload['raw_record']):
                    del _SUBSETS[(side, payload['cursor'])]
                    if _SUBSET_CHECKED[0] < 64:
                        _SUBSET_CHECKED[0] += 1
                        if entry[0] != original(payload):
                            raise ValueError('parallel context row hash differs from evidence_hash; run stopped')
                    return entry[0]
        return original(payload)
    return chained


def journal_genesis():
    from .verified_journal_reader import GENESIS_HASH
    return GENESIS_HASH


_SERIAL = None


@contextmanager
def parallel_walk(context):
    """For the duration of one preparation, the pinned _prepare walks the journal in parallel, and its per-row context
    encoding, reconstruction check and packet hashes run in parallel (parallel_context.py)."""
    global _SERIAL
    from .parallel_context import ParallelContext
    module = sys.modules[type(context).__module__]
    original = module.journal_prefix
    _SERIAL = original
    teacher = sys.modules.get(__package__ + '.c15_teacher_r3')
    teacher_hash = getattr(teacher, 'evidence_hash', None)
    names = ('encode', 'reconstruct_payloads', 'pack', 'evidence_hash')
    originals = tuple(getattr(module, name) for name in names)
    journal = context.builder.journal
    encoder = (ParallelContext(journal.worker_cpus, originals) if isinstance(journal, FrankieCompactReader) else None)
    module.journal_prefix = parallel_journal_prefix
    _ENTITY[0] = tuple(context.entity)
    if encoder is not None:
        for name in names:
            setattr(module, name, getattr(encoder, name))
    if teacher is not None:
        teacher.evidence_hash = _chain_hash_factory(teacher_hash)
    try:
        yield
    finally:
        module.journal_prefix = original
        for name, value in zip(names, originals):
            setattr(module, name, value)
        if teacher is not None:
            teacher.evidence_hash = teacher_hash
        _CANONICAL.clear()
        _SUBSETS.clear()
        _ENTITY[0] = None


def prepare_parallel(context, as_of, through_cursor):
    """context._prepare with the journal walked across the box's CPUs; the pinned _prepare body is unchanged."""
    with parallel_walk(context):
        return type(context)._prepare(context, as_of, through_cursor)
