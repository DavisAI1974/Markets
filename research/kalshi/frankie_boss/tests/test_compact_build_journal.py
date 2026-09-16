"""The direct-to-compact journal is byte-identical to raw-then-convert, on the same builder inputs."""
import sqlite3

import pytest

from test_causal_prefix_records import member, scope, SHA_A, SHA_B
from test_c15_full_evidence import row
from causal_prefix import ScopeKind
from c15_journal import EvidenceJournal, pack
from compact_build_journal import CompactBuildJournal, conformance_driver_with_compact_journal
from compact_journal import CompactReader, CompactWriter
from source_conformance import SourceConformanceDriver


def _scope(counts=(7,)):
    return scope(kind=ScopeKind.PROBE_ONLY, members=tuple(member(i, (SHA_A, SHA_B)[i], n) for i, n in enumerate(counts)))


def _records():
    return [row(0, flags=0), row(1, iid=2), row(2, action="M", size=9), row(3, action="F", size=2),
            row(4, action="C", size=2), row(5, action="C", oid=999), row(6, action="R", side="N", oid=0)]


def _feed(driver, records):
    for cursor, raw in enumerate(records):
        driver.append(raw, cursor=cursor, source_member_index=0, source_sha256=SHA_A, session_id="s",
                      raw_symbol="NG", source_dbn_object="synthetic")


def test_journal_append_matches_evidence_journal_byte_for_byte(tmp_path):
    raw = EvidenceJournal(tmp_path / 'raw.sqlite', create=True)
    compact = CompactBuildJournal(tmp_path / 'compact.sqlite', block_bytes=2048)   # several blocks
    payloads = [dict(cursor=i, bytes=b'\x00\xff', signed_zero=-0.0, nested=[1, None, (True, 2**63)],
                     observation=dict(orders=[dict(id=9 + i % 2, price=100, size=3)])) for i in range(9)]
    for i, payload in enumerate(payloads):
        assert raw.append('INPUT' if i % 2 == 0 else 'APPLIED', payload) == compact.append('INPUT' if i % 2 == 0 else 'APPLIED', payload)
    assert (raw.count, raw.head_hash) == (compact.count, compact.head_hash)
    assert compact.stored_tail() == (compact.count, compact.head_hash)       # unsealed: the writer's tail
    assert pack(list(compact.entries())) == pack(list(raw.entries()))       # pre-seal drain, same acceptance
    compact.verify(count=raw.count, head_hash=raw.head_hash)
    compact.seal()
    assert compact.stored_tail() == (raw.count, raw.head_hash)
    with pytest.raises(ValueError, match='sealed'):
        compact.append('INPUT', {})
    compact.close(); raw.close()
    with sqlite3.connect(tmp_path / 'raw.sqlite') as db:
        raw_rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
    with CompactReader(tmp_path / 'compact.sqlite', expected_count=len(payloads), expected_head_hash=raw_rows[-1][3]) as reader:
        assert [tuple(r) for r in reader.rows()] == [tuple(r) for r in raw_rows]


def test_builder_through_compact_journal_equals_raw_build_then_convert(tmp_path):
    records = _records()
    declared = _scope((len(records),))
    raw_driver = SourceConformanceDriver(declared, tmp_path / 'raw.sqlite', expected_scope_hash=declared.genesis_hash())
    compact_driver = conformance_driver_with_compact_journal(declared, tmp_path / 'compact.sqlite',
                                                             expected_scope_hash=declared.genesis_hash(), block_bytes=4096)
    try:
        _feed(raw_driver, records); _feed(compact_driver, records)
        raw_completion, compact_completion = raw_driver.complete(), compact_driver.complete()
        assert raw_completion == compact_completion
        assert raw_driver.checkpoint()['state_hash'] == compact_driver._builder.export_state()['state_hash']
        compact_driver._builder.journal.seal()
    finally:
        raw_driver.close(); compact_driver.close()
    # raw-then-convert, the Sunday route, yields the same container rows
    with sqlite3.connect(tmp_path / 'raw.sqlite') as db:
        raw_rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
    with CompactWriter(tmp_path / 'converted.sqlite', block_bytes=4096) as writer:
        for r in raw_rows:
            writer.add(tuple(r))
        writer.seal(expected_count=raw_completion.journal_count, expected_head_hash=raw_completion.journal_hash)
    for path in ('compact.sqlite', 'converted.sqlite'):
        with CompactReader(tmp_path / path, expected_count=raw_completion.journal_count,
                           expected_head_hash=raw_completion.journal_hash) as reader:
            assert [tuple(r) for r in reader.rows()] == [tuple(r) for r in raw_rows]


def test_compact_journal_refuses_a_rewritten_block_on_drain(tmp_path):
    compact = CompactBuildJournal(tmp_path / 'compact.sqlite', block_bytes=1024)
    for i in range(6):
        compact.append('INPUT', dict(i=i, payload='x' * 300))
    compact.flush()
    compact.writer.db.execute('UPDATE blocks SET body=? WHERE start=0', (b'\x1f\x8b' + b'\x00' * 40,))
    compact.writer.db.commit()
    with pytest.raises(ValueError, match='block identity'):
        list(compact.entries())
