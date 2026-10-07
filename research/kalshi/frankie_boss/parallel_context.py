"""Parallel context encoding for the pinned _prepare (Greg, 2026-09-28: "I told you to fix that. Fix it now").

Launch r6 (2026-09-28) finished the parallel journal walk, then sat on ONE core in context_session._prepare after it:
the Monday's declared context is the whole day (model_context_rows = the record count), so the per-row work after the
walk runs over every context row in the parent:
  - line 171 encode(): registry.validate + pack, identity keys, canonical_bytes(pack(dict(record, metadata))) per row,
    then torch.tensor over a Python list of every byte;
  - line 173 pack(reconstruct_payloads(tokens)) != pack(expected): bytes(values.tolist()) over every byte, then per
    row json.loads/unpack/validate/canonical check, then pack of both full lists;
  - line 177 packets: evidence_hash(dict(schema=PACKET_SCHEMA, source_prefix, record, metadata, as_of)) per row.

For the duration of one _prepare call (parallel_journal.parallel_walk) the context_session module globals encode,
reconstruct_payloads, pack and evidence_hash are replaced by the functions below; context_session.py and
native_mbo_encoder.py are unchanged (both are inside the pinned native model hash).

  - encode: the per-row work runs in pinned worker processes (one per worker CPU, the journal reader's budget); each
    worker also runs the reconstruction check on its own rows: unpack(json.loads(blob)), the {'record','metadata'}
    envelope, registry.validate, canonical_bytes(pack(row)) == blob, and pack(row) == pack(dict(record, metadata)) of
    the rows it encoded. Only the order-dependent parent/age columns and the receive-order seams run in the parent.
    The tensors have the same dtypes, shapes and values as native_mbo_encoder.encode's.
  - reconstruct_payloads, for exactly the tokens this encode returned (same tensor objects, dtypes and the offsets
    partition), returns a verified marker; any other tokens go to the original.
  - pack: the marker, and the caller's expected list when every element is dict(record=rows[i], metadata=metadata[i])
    over the very row and metadata objects this encode verified, pack to the same value; everything else goes to the
    original pack.
  - evidence_hash: a PACKET_SCHEMA dict over a verified row and metadata object is hashed from the canonical bytes the
    workers computed (sha256 over the assembled compact JSON; only the hash runs in the parent). The first 64 are also
    computed the original way and must match, or the run stops. Everything else goes to the original.
"""
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import hashlib
import json
import multiprocessing

import torch

from .c15_journal import SCHEMA as JOURNAL_SCHEMA, evidence_hash, pack, unpack
from .causal_packet import canonical_bytes
from .frankie_journal_reader import _assign_cpu
from .native_mbo_encoder import ACTION_VOCAB, SIDE_VOCAB, _parts, _value

CHUNK = 8192
_HEAD, _MID, _TAIL = b'["dict",[["record",', b'],["metadata",', b']]]'


def _encode_chunk(rows, metadata, as_of, registry):
    """native_mbo_encoder.encode's per-row work for one chunk, minus the order-dependent parent/age columns, plus the
    reconstruction check of every blob against the row and metadata it came from."""
    numeric, nmasks, categorical, cmasks, identities, orders, recvs, blobs, splits = ([] for _ in range(9))
    last_recv = -1
    for row, meta in zip(rows, metadata):
        registry.validate(row)
        if type(meta) is not dict or meta.keys() - {'adapter', 'source_context', 'defects'}:
            raise ValueError('unmapped adapter metadata')
        if 'adapter' in meta:
            registry.validate(meta['adapter'])
        recv, event = _value(row, 'ts_recv'), _value(row, 'ts_event')
        if type(recv) is not int or not last_recv <= recv <= as_of:
            raise ValueError('rows must be received by cutoff in receive order')
        last_recv = recv
        n, nm = [], []
        for value in (as_of-recv, as_of-event if type(event) is int else None,
                      _value(row, 'price'), row.get('size'), row.get('sequence'), _value(row, 'ts_in_delta')):
            parts, mask = _parts(value)
            n.extend(parts); nm.extend(mask)
        identities.append(tuple(canonical_bytes(pack(row.get(f))) for f in ('publisher_id', 'instrument_id', 'order_id')))
        orders.append(row.get('order_id') is not None and row.get('order_id') != 0)
        recvs.append(recv)
        numeric.append(n); nmasks.append(nm)
        action, side = row.get('action'), row.get('side')
        c = [ACTION_VOCAB.index(action) if action in ACTION_VOCAB else 0,
             SIDE_VOCAB.index(side) if side in SIDE_VOCAB else 0]
        cm = [action is not None, side is not None]
        pub = row.get('publisher_id')
        pub_ok = type(pub) is int and 0 <= pub <= 65535
        for value in (row.get('rtype'), pub >> 8 if pub_ok else None,
                      pub & 255 if pub_ok else None, row.get('channel_id')):
            ok = type(value) is int and 0 <= value <= 255
            c.append(value+1 if ok else 0); cm.append(value is not None)
        flags = row.get('flags')
        ok = type(flags) is int and 0 <= flags <= 255
        c.extend([(flags >> bit) & 1 if ok else 0 for bit in range(8)]); cm.extend([ok]*8)
        clock = row.get('independent_clocks', meta.get('adapter', {}).get('independent_clocks'))
        c.append(int(clock) if type(clock) is bool else 0); cm.append(type(clock) is bool)
        categorical.append(c); cmasks.append(cm)
        envelope = pack(dict(record=row, metadata=meta))
        blob = canonical_bytes(envelope)
        # reconstruct_payloads' per-row checks, on this row's exact bytes, and _prepare's pack comparison for it
        payload = unpack(json.loads(blob))
        if set(payload) != {'record', 'metadata'}:
            raise ValueError('invalid exact source envelope')
        registry.validate(payload['record'])
        if canonical_bytes(pack(payload)) != blob:
            raise ValueError('noncanonical exact field representation')
        if pack(payload) != envelope:
            raise ValueError('native inverse reconstruction differs from journal evidence')
        # the record's own canonical bytes, for the packet hash (compact JSON of a list is its parts in order)
        record = canonical_bytes(pack(row))
        if not (blob.startswith(_HEAD + record + _MID) and blob.endswith(_TAIL)):
            raise ValueError('exact envelope bytes differ from their parts')
        blobs.append(blob); splits.append(len(record))
    first = recvs[0] if recvs else None
    return dict(numeric=numeric, nmasks=nmasks, categorical=categorical, cmasks=cmasks, identities=identities,
                orders=orders, recvs=recvs, blobs=blobs, splits=splits, first=first, last=last_recv)


class _Verified:
    """reconstruct_payloads' result for tokens this encode verified row by row in the workers."""
    __slots__ = ('state',)

    def __init__(self, state):
        self.state = state


class ParallelContext:
    """One _prepare's parallel encode state; installed by parallel_journal.parallel_walk."""

    def __init__(self, worker_cpus, originals):
        self.worker_cpus = tuple(worker_cpus)
        self.encode_original, self.reconstruct_original, self.pack_original, self.hash_original = originals
        self.tokens = self.rows = self.metadata = self.blobs = self.splits = None
        self.by_metadata = {}
        self.checked = 0

    def encode(self, rows, *, as_of, registry, metadata=None):
        if type(as_of) is not int or not 0 <= as_of <= 2**64-1:
            raise ValueError('as_of must be an exact unsigned nanosecond cutoff')
        rows = list(rows)
        if not rows:
            raise ValueError('nonempty context required')
        metadata = [{} for _ in rows] if metadata is None else list(metadata)
        if len(metadata) != len(rows):
            raise ValueError('metadata must account for every event')
        context = multiprocessing.get_context('spawn')
        assignments = context.Queue()
        for cpu in self.worker_cpus:
            assignments.put(cpu)
        numeric, nmasks, categorical, cmasks, parents, blobs, splits = [], [], [], [], [], [], []
        previous, first = {}, {}
        last_recv, i = -1, 0
        try:
            with ProcessPoolExecutor(max_workers=len(self.worker_cpus), mp_context=context,
                                     initializer=_assign_cpu, initargs=(assignments,)) as pool:
                starts = iter(range(0, len(rows), CHUNK))
                pending = deque()

                def submit():
                    start = next(starts, None)
                    if start is not None:
                        pending.append(pool.submit(_encode_chunk, rows[start:start+CHUNK],
                                                   metadata[start:start+CHUNK], as_of, registry))

                try:
                    # Match the journal reader's bounded ordered window. This
                    # limits queued work, never the complete input or output.
                    for _ in range(2 * len(self.worker_cpus)):
                        submit()
                    while pending:
                        future = pending.popleft()
                        part = future.result()
                        if part['first'] is not None and not last_recv <= part['first']:
                            raise ValueError('rows must be received by cutoff in receive order')
                        last_recv = part['last']
                        for n, nm, identity, has_order, recv in zip(part['numeric'], part['nmasks'], part['identities'],
                                                                    part['orders'], part['recvs']):
                            parents.append(previous.get(identity, -1) if has_order else -1)
                            if has_order:
                                first.setdefault(identity, recv)
                                previous[identity] = i
                            age = recv-first[identity] if has_order else 0
                            n.append(float(age) if age <= 2**53 else 0.); nm.append(has_order and age <= 2**53)
                            numeric.append(n); nmasks.append(nm)
                            i += 1
                        categorical.extend(part['categorical']); cmasks.extend(part['cmasks'])
                        blobs.extend(part['blobs']); splits.extend(part['splits'])
                        submit()
                finally:
                    # Cancel work that has not started; the executor's context
                    # exit drains any already running jobs before propagating failure.
                    for future in pending:
                        future.cancel()
        finally:
            assignments.close()
            assignments.join_thread()
        if i != len(rows):
            raise ValueError('parallel encode lost rows')
        offsets = [0]
        for blob in blobs:
            offsets.append(offsets[-1] + len(blob))
        count = len(rows)
        tokens = dict(numeric=torch.tensor([numeric], dtype=torch.float64),
                      numeric_mask=torch.tensor([nmasks], dtype=torch.bool),
                      categorical=torch.tensor([categorical], dtype=torch.long),
                      categorical_mask=torch.tensor([cmasks], dtype=torch.bool),
                      parent=torch.tensor([parents], dtype=torch.long),
                      venue_id=torch.zeros((1, count), dtype=torch.long),
                      instrument_id=torch.zeros((1, count), dtype=torch.long),
                      byte_values=torch.frombuffer(bytearray().join(blobs), dtype=torch.uint8),
                      byte_offsets=torch.tensor(offsets, dtype=torch.long),
                      cutoff=torch.tensor(list(as_of.to_bytes(8, 'big')), dtype=torch.uint8))
        self.tokens = (tokens, tokens['byte_values'], tokens['byte_offsets'])
        self.rows, self.metadata, self.blobs, self.splits = rows, metadata, blobs, splits
        self.by_metadata = {id(m): k for k, m in enumerate(metadata)}
        return tokens

    def reconstruct_payloads(self, tokens, registry):
        if self.tokens is None or tokens is not self.tokens[0]:
            return self.reconstruct_original(tokens, registry)
        values, offsets = tokens['byte_values'], tokens['byte_offsets']
        if values is not self.tokens[1] or offsets is not self.tokens[2]:
            return self.reconstruct_original(tokens, registry)
        if values.dtype != torch.uint8 or offsets.dtype != torch.long or values.ndim != 1 or offsets.ndim != 1:
            raise ValueError('invalid exact-byte tensors')
        bounds = offsets.tolist()
        if (not bounds or bounds[0] != 0 or bounds[-1] != values.numel() or len(bounds) != len(self.blobs)+1
                or any(b <= a for a, b in zip(bounds, bounds[1:]))):
            raise ValueError('byte offsets must partition all exact evidence')
        return _Verified(self)

    def pack(self, value):
        if type(value) is _Verified:
            if value.state is not self:
                raise ValueError('verified reconstruction from another preparation')
            return ('parallel-verified', id(self))
        if (type(value) is list and self.rows is not None and len(value) == len(self.rows)
                and all(type(item) is dict and len(item) == 2 and list(item) == ['record', 'metadata']
                        and item['record'] is row and item['metadata'] is meta
                        for item, row, meta in zip(value, self.rows, self.metadata))):
            return ('parallel-verified', id(self))
        return self.pack_original(value)

    def evidence_hash(self, payload):
        from .context_session import PACKET_SCHEMA
        if (type(payload) is dict and list(payload) == ['schema', 'source_prefix', 'record', 'metadata', 'as_of']
                and payload['schema'] == PACKET_SCHEMA and type(payload['source_prefix']) is str
                and type(payload['as_of']) is int and self.rows is not None):
            k = self.by_metadata.get(id(payload['metadata']))
            if k is not None and payload['metadata'] is self.metadata[k] and payload['record'] is self.rows[k]:
                blob, split = self.blobs[k], self.splits[k]
                head = len(_HEAD)
                record = blob[head:head+split]
                metadata = blob[head+split+len(_MID):len(blob)-len(_TAIL)]
                data = (b'["dict",[["schema",' + canonical_bytes(pack(payload['schema']))
                        + b'],["source_prefix",' + canonical_bytes(pack(payload['source_prefix']))
                        + b'],["record",' + record + b'],["metadata",' + metadata
                        + b'],["as_of",' + canonical_bytes(pack(payload['as_of'])) + b']]]')
                value = hashlib.sha256(JOURNAL_SCHEMA.encode() + b'\0' + data).hexdigest()
                if self.checked < 64:
                    self.checked += 1
                    if value != self.hash_original(payload):
                        raise ValueError('parallel packet hash differs from evidence_hash; run stopped')
                return value
        return self.hash_original(payload)
