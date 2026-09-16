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
import hashlib
import json
from pathlib import Path

try:
    from .c15_builder import C15Builder
    from .c15_journal import SCHEMA, canonical_bytes, evidence_hash, pack, unpack
    from .c15_registry import implementation_identity
    from .causal_prefix_records import RecordPrefixChain
    from .compact_journal import CompactWriter, FORMAT, decode_block
    from .source_conformance import SourceConformanceDriver
    from .verified_journal_reader import DIGEST_PREFIX, GENESIS_HASH
except ImportError:   # the tests import the package modules flat, as every module here allows
    from c15_builder import C15Builder
    from c15_journal import SCHEMA, canonical_bytes, evidence_hash, pack, unpack
    from c15_registry import implementation_identity
    from causal_prefix_records import RecordPrefixChain
    from compact_journal import CompactWriter, FORMAT, decode_block
    from source_conformance import SourceConformanceDriver
    from verified_journal_reader import DIGEST_PREFIX, GENESIS_HASH
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter   # as c15_builder and source_recovery import it


class CompactBuildJournal:
    """EvidenceJournal's append contract, persisted through CompactWriter."""

    def __init__(self, path, *, block_bytes=4 * 1024 * 1024):
        self.path = Path(path)
        self.writer = CompactWriter(self.path, block_bytes=block_bytes)
        self.appends = 0

    @property
    def count(self):
        return self.writer.count

    @property
    def head_hash(self):
        return self.writer.head_hash

    @property
    def sealed(self):
        return self.writer.sealed

    def append(self, kind, payload):
        if type(kind) is not str or not kind:
            raise ValueError('entry kind required')
        # Byte-for-byte the EvidenceJournal.append envelope, body and digest.
        envelope = dict(schema=SCHEMA, ordinal=self.count, previous_hash=self.head_hash, kind=kind, payload=payload)
        body = canonical_bytes(pack(envelope))
        digest = evidence_hash(envelope)
        self.writer.add((self.count, kind, body, digest))
        self.appends += 1
        return digest

    def flush(self):
        self.writer.flush()

    def seal(self):
        """Seal at the writer's own tail. The seal states what was written; conformance is a separate claim."""
        self.writer.seal(expected_count=self.count, expected_head_hash=self.head_hash)

    def rows(self):
        """Every committed row in order with the block chain re-checked; pending rows are flushed first."""
        if not self.sealed:
            self.flush()
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
        """Verified envelopes in order, the same acceptance as EvidenceJournal.entries()."""
        previous, count = GENESIS_HASH, 0
        for ordinal, kind, body, digest in self.rows():
            envelope = unpack(json.loads(body))
            if (body != canonical_bytes(pack(envelope)) or ordinal != count or envelope['ordinal'] != ordinal
                    or envelope['schema'] != SCHEMA or envelope['kind'] != kind
                    or envelope['previous_hash'] != previous
                    or hashlib.sha256(DIGEST_PREFIX + body).hexdigest() != digest):
                raise ValueError('evidence journal continuity or hash mismatch')
            previous, count = digest, count + 1
            yield envelope
        if (count, previous) != (self.count, self.head_hash):
            raise ValueError('evidence journal changed during iteration')

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
        self.writer.db.close()


def conformance_driver_with_compact_journal(scope, journal_path, *, expected_scope_hash, block_bytes=4 * 1024 * 1024):
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
    builder.journal = CompactBuildJournal(journal_path, block_bytes=block_bytes)
    driver = SourceConformanceDriver.__new__(SourceConformanceDriver)
    driver._builder = builder
    driver._stopped = driver._completed = driver._closed = False
    return driver
