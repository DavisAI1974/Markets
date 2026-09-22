"""Write the C15 evidence journal directly into the compact container while the builder runs.

The Sunday build wrote every row into the raw SQLite journal (two fsync'd commits per record,
205 KB per record, 11.7 GB for one Sunday) and converted it to the sealed compact container
afterwards. For a 6.47M-record block that raw journal is about 2 TB and never needs to exist:
CompactWriter.add needs exactly (ordinal, kind, body, digest), and those are the four values
EvidenceJournal.append computes before its INSERT. This class computes the same envelope, the
same canonical body and the same digest as EvidenceJournal.append, so a builder fed through it
produces a container byte-identical to raw-then-convert (tests/test_compact_build_journal.py
proves it on synthetic journals; the Sunday both-ways run proves it on the real day).

It satisfies the builder's journal interface: append, count, head_hash, path, entries, verify,
stored_tail, close. entries() before the seal flushes pending rows and drains the committed
blocks single-threaded, which is what SourceConformanceDriver.complete() needs; after the seal
the parallel FrankieCompactReader is the faster drain and the caller may substitute it.

Identity: FREE. No teacher, normaliser or builder byte changes; the journal bodies are the
builder's, unchanged.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing
from pathlib import Path
import time

try:
    from .c15_builder import C15Builder
    from .c15_journal import OBSERVATION_SENTINEL, SCHEMA, pack
    from .c15_registry import implementation_identity
    from .causal_prefix_records import RecordPrefixChain
    from .compact_journal import CompactWriter, FORMAT, MAX_BYTES, MAX_ROWS, decode_block, encode_block, verified_rows
    from .source_conformance import SourceConformanceDriver
    from .verified_journal_reader import DIGEST_PREFIX, GENESIS_HASH, canonical_tagged_bytes
except ImportError:   # the tests import the package modules flat, as every module here allows
    from c15_builder import C15Builder
    from c15_journal import OBSERVATION_SENTINEL, SCHEMA, pack
    from c15_registry import implementation_identity
    from causal_prefix_records import RecordPrefixChain
    from compact_journal import CompactWriter, FORMAT, MAX_BYTES, MAX_ROWS, decode_block, encode_block, verified_rows
    from source_conformance import SourceConformanceDriver
    from verified_journal_reader import DIGEST_PREFIX, GENESIS_HASH, canonical_tagged_bytes
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter   # as c15_builder and source_recovery import it


class CompactBuildJournal:
    """EvidenceJournal's append contract, persisted through the compact codec.

    Per row it does what EvidenceJournal.append does, once: pack the envelope to its tagged tree,
    serialise the tree canonically, hash the bytes. EvidenceJournal serialises through the generic
    causal_packet canonicaliser twice (body, then evidence_hash re-packs and re-serialises); the
    codec's canonical_tagged_bytes is byte-identical on pack() output (proven differentially in
    tests/test_verified_journal_reader.py) and the digest is sha256(DIGEST_PREFIX + body) by
    definition. Measured on 1,000 real Sunday records: the double generic pass was 96% of 141 ms
    per record. Blocks are cut by CompactWriter.add's rule (block_bytes, MAX_ROWS), encoded from
    the trees already in hand, inserted and read back the way the first run's journal stack did.
    """

    def __init__(self, path, *, block_bytes=MAX_BYTES // 2, workers=0, block_rows=MAX_ROWS):
        """workers > 0 encodes blocks (order dedup, gzip) on that many spawned processes while the
        parent stays on the causal sequence; blocks are inserted in order and read back, as the
        first run's journal stack did. workers == 0 encodes inline. A box is cut at `block_rows`
        rows (the day's standard, box_standard.partition_entries_for; Greg, 2026-09-17:
        TARGET_BOXES = 1189 for every day we ingest) or at `block_bytes` of bodies (the format's
        ceiling by default), whichever comes first; the entries, count and head hash are invariant
        to the cut, the container's bytes are not."""
        if type(block_rows) is not int or not 0 < block_rows <= MAX_ROWS:
            raise ValueError(f'rows per box must be an integer in 1..{MAX_ROWS}')
        self.path = Path(path)
        self.writer = CompactWriter(self.path, block_bytes=block_bytes)
        self.block_bytes, self.block_rows = block_bytes, block_rows
        self.appends = 0
        self._rows, self._trees, self._pending_bytes, self._pending_previous = [], [], 0, GENESIS_HASH
        self.workers = int(workers)
        self._pool = (ProcessPoolExecutor(max_workers=self.workers, mp_context=multiprocessing.get_context('spawn'))
                      if self.workers > 0 else None)
        self._inflight = deque()          # (future, start, count, previous, head) in submission order
        self.worker_cpu_seconds = 0.0

    @property
    def count(self):
        return self.writer.count

    @property
    def head_hash(self):
        return self.writer.head_hash

    @property
    def sealed(self):
        return self.writer.sealed

    accepts_spliced = True     # the builder may hand the observation as canonical bytes (c15_observer.IncrementalObservation)
    _SENTINEL_NODE = None

    def append(self, kind, payload, *, spliced=None):
        """`spliced`: the observation's canonical bytes, replacing the one OBSERVATION_SENTINEL string node of the payload in
        the body (Greg, 2026-09-22): the bytes are what pack() of the mapping would have serialised to, so the body and the
        digest are those of the plain envelope; the parsed tree is then not kept for this row (the inline encoder parses
        the body). Exactly one sentinel is required, else refused."""
        if self.sealed:
            raise ValueError('container already sealed')
        if type(kind) is not str or not kind:
            raise ValueError('entry kind required')
        ordinal, previous = self.count, self.head_hash
        envelope = dict(schema=SCHEMA, ordinal=ordinal, previous_hash=previous, kind=kind, payload=payload)
        tree = pack(envelope)
        body = canonical_tagged_bytes(tree)                                  # == canonical_bytes(tree)
        if spliced is not None:
            if type(spliced) is not bytes or not spliced:
                raise ValueError('spliced observation bytes required')
            if CompactBuildJournal._SENTINEL_NODE is None:
                CompactBuildJournal._SENTINEL_NODE = canonical_tagged_bytes(pack(OBSERVATION_SENTINEL))
            token = CompactBuildJournal._SENTINEL_NODE
            if body.count(token) != 1:
                raise ValueError('the payload must carry exactly one observation sentinel to splice')
            body = body.replace(token, spliced, 1)
            tree = None
        digest = hashlib.sha256(DIGEST_PREFIX + body).hexdigest()            # == evidence_hash(envelope)
        if len(body) > MAX_BYTES // 2:
            raise ValueError('oversized row')
        if self._rows and (self._pending_bytes + len(body) > self.block_bytes or len(self._rows) == self.block_rows):
            self.flush()
        if not self._rows:
            self._pending_previous = previous
        self._rows.append((ordinal, kind, body, digest)); self._trees.append(tree); self._pending_bytes += len(body)
        self.writer.count, self.writer.head_hash = ordinal + 1, digest
        self.appends += 1
        return digest

    def _insert(self, start, count, blob, previous, head):
        started = time.perf_counter()
        digest = hashlib.sha256(blob).hexdigest()
        with self.writer.db:
            self.writer.db.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)', (start, count, blob, digest, previous, head))
        if self.writer.db.execute('SELECT body FROM blocks WHERE start=?', (start,)).fetchone()[0] != blob:
            raise ValueError('persisted block readback differs')
        self.writer.flushed_bytes += len(blob)
        self.writer.flush_seconds += time.perf_counter() - started

    def _collect(self, *, all_of_them):
        """Insert finished worker blocks in submission order; the queue holds at most 2 x workers."""
        limit = 0 if all_of_them else 2 * self.workers
        while self._inflight and (len(self._inflight) > limit or self._inflight[0][0].done()):
            future, start, count, previous, head = self._inflight.popleft()
            blob, cpu = future.result()
            self._insert(start, count, blob, previous, head)
            self.worker_cpu_seconds += cpu

    def flush(self):
        if not self._rows:
            return
        start, count, head = self._rows[0][0], len(self._rows), self._rows[-1][3]
        if self._pool is None:
            trees = self._trees if all(tree is not None for tree in self._trees) else None    # a spliced row: the encoder parses the body
            self._insert(start, count, encode_block(self._rows, trees), self._pending_previous, head)
        else:
            future = self._pool.submit(_encode_rows, self._rows)     # the worker parses the bodies itself
            self._inflight.append((future, start, count, self._pending_previous, head))
            self._collect(all_of_them=False)
        self._rows, self._trees, self._pending_bytes = [], [], 0

    def seal(self):
        """Seal at the writer's own tail. The seal states what was written; conformance is a separate claim."""
        self.flush()
        self._collect(all_of_them=True)
        self.writer.seal(expected_count=self.count, expected_head_hash=self.head_hash)

    def rows(self):
        """Every committed row in order with the block chain re-checked; pending rows are flushed first."""
        self.flush()
        self._collect(all_of_them=True)
        count, previous = 0, GENESIS_HASH
        for start, length, blob, digest, before, head in self.writer.db.execute(
                'SELECT start,count,body,sha256,previous,head FROM blocks ORDER BY start'):
            if start != count or before != previous or hashlib.sha256(blob).hexdigest() != digest:
                raise ValueError('block identity or continuity differs')
            rows = decode_block(blob)
            if len(rows) != length or [r[0] for r in rows] != list(range(start, start + length)) or rows[-1][3] != head:
                raise ValueError('block coverage differs')
            yield from rows
            count, previous = count + length, head
        if (count, previous) != (self.count, self.head_hash):
            raise ValueError('compact journal changed during iteration')

    def entries(self):
        """Verified envelopes in order through the fast reader's path: one parse, one validating
        decode, one canonical serialisation, one hash per row (the 3.37x reader of
        SPEC-verified-journal-reader.md), the same rows accepted and refused as
        EvidenceJournal.entries(). This is the drain SourceConformanceDriver.complete() runs."""
        yield from verified_rows(self.rows(), self.count, self.head_hash)

    def stored_tail(self):
        rows = self.writer.db.execute('SELECT format,count,head FROM seal').fetchall()
        if not rows:
            return self.count, self.head_hash   # unsealed: the writer's tail is the only tail
        if len(rows) != 1 or rows[0][0] != FORMAT:
            raise ValueError('sealed journal identity required')
        return rows[0][1], rows[0][2]

    def verify(self, *, count, head_hash):
        for _ in self.entries():
            pass
        if (self.count, self.head_hash) != (count, head_hash):
            raise ValueError('journal differs from checkpoint; existing evidence was retained')

    def close(self):
        try:
            if self._inflight:
                self._collect(all_of_them=True)
        finally:
            if self._pool is not None:
                self._pool.shutdown(wait=True)
            self.writer.db.close()


def _encode_rows(rows):
    """Worker: encode one block from its rows (bodies are parsed here, off the causal parent)."""
    started = time.process_time()
    return encode_block(rows), time.process_time() - started


def conformance_driver_with_compact_journal(scope, journal_path, *, expected_scope_hash, block_bytes=MAX_BYTES // 2, workers=0,
                                            block_rows=MAX_ROWS):
    """SourceConformanceDriver whose builder writes the compact container directly.

    Same construction as source_recovery.rehydrate_source: the builder's __init__ hard-wires an
    EvidenceJournal, so the builder is assembled field by field with the compact journal in its
    place. Every other builder field is what __init__ would have set.
    """
    SourceConformanceDriver._check_scope(scope, expected_scope_hash)
    builder = C15Builder.__new__(C15Builder)
    builder.scope, builder.chain = scope, RecordPrefixChain(scope)
    builder.adapter, builder.identity = V4MboAdapter(), implementation_identity()
    builder._sessions, builder._failed = {}, False
    builder.journal = CompactBuildJournal(journal_path, block_bytes=block_bytes, workers=workers, block_rows=block_rows)
    driver = SourceConformanceDriver.__new__(SourceConformanceDriver)
    driver._builder = builder
    driver._stopped = driver._completed = driver._closed = False
    return driver
