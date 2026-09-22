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


def test_the_observation_packs_from_a_cache_of_its_orders_and_levels_byte_identically(tmp_path):
    # Greg, 2026-09-22 ("see if you can get it smaller"): the book changes by one order per record, yet pack() re-walked
    # every field of every resting order on every closed group. The builder now keeps each order's and each level's
    # packed subtree and reuses it while the fields are unchanged; the tree it hands the journal equals pack() of the
    # plain mapping node for node, so the bytes written do not change.
    from c15_journal import PrePacked
    records = _records()
    declared = _scope((len(records),))
    driver = SourceConformanceDriver(declared, tmp_path / 'raw.sqlite', expected_scope_hash=declared.genesis_hash())   # the raw path packs the tree
    previous = {}
    reused = 0
    try:
        for cursor, raw in enumerate(records):
            applied = driver.append(raw, cursor=cursor, source_member_index=0, source_sha256=SHA_A, session_id="s",
                                    raw_symbol="NG", source_dbn_object="synthetic")
            observation = applied.observation
            if observation is None:
                continue
            assert type(observation) is PrePacked and isinstance(observation, dict)
            assert observation.tree == pack(dict(observation))                  # byte identity, node for node
            assert pack(observation) is observation.tree                        # pack() hands the cached tree through
            orders = {repr(node): node for node in observation.tree[1][1][1][1]}   # ['dict', [['instrument_id',..], ['orders', ['list', [...]]], ...]]
            for key, node in orders.items():
                if key in previous.get(observation['instrument_id'], {}):
                    assert previous[observation['instrument_id']][key] is node   # an unchanged order = the SAME subtree object
                    reused += 1
            previous[observation['instrument_id']] = orders
        assert reused > 0
    finally:
        driver.close()


def test_the_writer_cuts_boxes_by_the_declared_row_standard(tmp_path):
    # Greg, 2026-09-17/22: TARGET_BOXES = 1189 is the standard for every day we ingest; the ingest writer cut 4 MiB blocks
    # of its own and never saw it. The writer now takes the rows per box (journal_stack_execution.partition_entries_for on
    # the day's entry count) and the format's byte ceiling; the entries, count and head hash are invariant to the cut.
    payloads = [dict(cursor=i, observation=dict(orders=[dict(id=i % 3, price=100, size=3)])) for i in range(9)]
    by_rows = CompactBuildJournal(tmp_path / 'rows.sqlite', block_rows=4)
    by_bytes = CompactBuildJournal(tmp_path / 'bytes.sqlite', block_bytes=2048)
    for i, payload in enumerate(payloads):
        kind = 'INPUT' if i % 2 == 0 else 'APPLIED'
        assert by_rows.append(kind, payload) == by_bytes.append(kind, payload)
    by_rows.seal(); by_bytes.seal()
    assert (by_rows.count, by_rows.head_hash) == (by_bytes.count, by_bytes.head_hash)
    assert [r[1] for r in by_rows.writer.db.execute('SELECT start,count FROM blocks ORDER BY start')] == [4, 4, 1]
    assert by_rows.block_rows == 4 and by_rows.block_bytes == 16 * 1024 * 1024        # the format's ceiling is the byte bound
    by_rows.close(); by_bytes.close()
    with pytest.raises(ValueError, match='rows per box'):
        CompactBuildJournal(tmp_path / 'bad.sqlite', block_rows=0)
    with pytest.raises(ValueError, match='rows per box'):
        CompactBuildJournal(tmp_path / 'bad2.sqlite', block_rows=257)


def test_the_compact_path_composes_the_observation_bytes_incrementally_and_the_raw_path_proves_them(tmp_path):
    # Greg, 2026-09-22 ("we just want time"): on the compact path the builder no longer copies and re-walks the whole book
    # per closed group; it maintains each order's and each level's canonical fragment as the adapter mutates ONE order per
    # message (a reset rebuilds), joins them into the observation's bytes, and splices those bytes into the APPLIED body.
    # The raw path still packs observe_book; the both-writers test above proves the two byte-identical end to end. Here:
    # every observation equals the reference on every record, a drifted fragment is REFUSED at the next check, and the
    # in-memory observation is a sealed object that materializes from its own bytes, never from the live book.
    from c15_journal import SerializedObservation, unpack
    from c15_observer import IncrementalObservation, observe_book
    from verified_journal_reader import canonical_tagged_bytes
    import json
    records = _records()
    declared = _scope((len(records),))
    driver = conformance_driver_with_compact_journal(declared, tmp_path / 'c.sqlite', expected_scope_hash=declared.genesis_hash(), block_bytes=4096)
    builder = driver._builder
    builder.observation_check_every = 1                      # the differential check on every observation, for the test
    seen = 0
    try:
        for cursor, raw in enumerate(records):
            applied = driver.append(raw, cursor=cursor, source_member_index=0, source_sha256=SHA_A, session_id="s",
                                    raw_symbol="NG", source_dbn_object="synthetic")
            for iid, composer in builder._composers.items():
                assert composer.canonical() == canonical_tagged_bytes(pack(observe_book(builder.adapter.books[iid])))
            if applied.observation is not None:
                seen += 1
                assert type(applied.observation) is SerializedObservation and applied.evidence['observation'] is applied.observation
                book = builder.adapter.books[applied.evidence['normalized']['instrument_id']]
                assert applied.observation.materialize() == unpack(json.loads(canonical_tagged_bytes(pack(observe_book(book)))))
                with pytest.raises(TypeError):
                    applied.observation['orders']                # not a mapping: a reader must materialize() and say so
        assert seen >= 3
        rows = list(driver._builder.journal.rows())
        applied_bodies = [r[2] for r in rows if r[1] == 'APPLIED']
        assert all(b'@@C15-OBSERVATION' not in body for body in applied_bodies)      # the sentinel never reaches the journal
    finally:
        driver.close()
    # a drifted fragment is refused at the next check, never written
    from test_c15_full_evidence import row
    driver = conformance_driver_with_compact_journal(_scope((3,)), tmp_path / 'd.sqlite', expected_scope_hash=_scope((3,)).genesis_hash(), block_bytes=4096)
    driver._builder.observation_check_every = 1
    try:
        driver.append(row(0), cursor=0, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
        composer = next(iter(driver._builder._composers.values()))
        oid = composer.sorted_oids[0]
        composer.order_bytes[0] = b'["dict",[]]'          # the joined fragment, not the map: what the body is built from
        with pytest.raises(ValueError, match='incremental observation differs'):
            driver.append(row(1, oid=2), cursor=1, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
    finally:
        driver.close()


def test_the_writer_splices_exactly_one_observation_and_the_inline_encoder_parses_the_composed_body(tmp_path):
    from c15_journal import OBSERVATION_SENTINEL
    journal = CompactBuildJournal(tmp_path / 's.sqlite', block_bytes=4096)
    observation = b'["dict",[["orders",["list",[]]]]]'
    digest = journal.append('APPLIED', dict(cursor=0, observation=OBSERVATION_SENTINEL), spliced=observation)
    assert journal.head_hash == digest
    with pytest.raises(ValueError, match='exactly one'):
        journal.append('APPLIED', dict(cursor=1, observation=None), spliced=observation)
    with pytest.raises(ValueError, match='exactly one'):
        journal.append('APPLIED', dict(cursor=1, observation=OBSERVATION_SENTINEL, other=OBSERVATION_SENTINEL), spliced=observation)
    journal.append('INPUT', dict(cursor=1))
    journal.seal()
    rows = list(journal.rows())
    assert len(rows) == 2 and observation in rows[0][2] and OBSERVATION_SENTINEL.encode() not in rows[0][2]
    from c15_journal import unpack
    import json
    assert unpack(json.loads(rows[0][2]))['payload']['observation'] == dict(orders=[])
    journal.close()


def test_every_adapter_path_composes_byte_identically_at_the_default_cadence_and_on_every_record(tmp_path):
    # the chat-9 ship review on the incremental observation: the fixture stream above exercises add, modify same price,
    # fill, partial cancel, cancel of a missing order and a reset only. This stream (journal-shaped rows, the tests' own)
    # walks every mutation path of the pinned adapter: duplicate add, modify with and without priority loss, modify with
    # side change, modify of a missing order, modify to size 0, full cancel emptying a level, cancel of a missing order,
    # trade/fill/none, an invalid-side add, the F_TOB one-side clear, a reset, a second instrument emptied, a non-F_LAST
    # group. The raw and the compact journals must agree row for row at the DEFAULT cadence, and the composer must equal
    # observe_book after every record when checked on every observation.
    from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import UNDEF_PRICE, F_LAST, F_TOB
    from test_c15_full_evidence import row
    from c15_observer import observe_book
    from verified_journal_reader import canonical_tagged_bytes
    stream = [row(0, oid=1, side='A', price=101, size=10), row(1, oid=2, side='A', price=101, size=5), row(2, oid=3, side='B', price=99, size=7),
              row(3, oid=4, side='B', price=98, size=3, flags=0), row(4, oid=5, side='B', price=98, size=4),
              row(5, oid=1, side='A', price=102, size=10),                                   # duplicate add
              row(6, oid=2, action='M', side='A', price=101, size=3),                        # modify, no priority loss
              row(7, oid=3, action='M', side='B', price=99, size=9),                         # modify, priority lost (size up)
              row(8, oid=4, action='M', side='B', price=97, size=3),                         # modify, priority lost (price)
              row(9, oid=5, action='M', side='A', price=103, size=4),                        # modify with side change
              row(10, oid=77, action='M', side='B', price=96, size=2),                       # modify of a missing order
              row(11, oid=2, action='C', side='A', price=101, size=1), row(12, oid=2, action='C', side='A', price=101, size=2),   # partial then full cancel
              row(13, oid=999, action='C', side='A', price=101, size=1),                     # cancel of a missing order
              row(14, oid=1, action='T', side='A', price=102, size=1), row(15, oid=1, action='F', side='A', price=102, size=1),
              row(16, oid=0, action='N', side='N', price=0, size=0),
              row(17, oid=4, action='M', side='B', price=97, size=0),                        # modify to size 0
              row(18, oid=8, side='N', price=100, size=1),                                   # invalid-side add
              row(19, oid=0, side='A', price=UNDEF_PRICE, size=0, flags=F_LAST | F_TOB),     # the one-side clear
              row(20, oid=9, side='A', price=105, size=1),
              row(21, oid=0, action='R', side='N', price=0, size=0),                         # reset
              row(22, oid=10, side='B', price=90, size=1),
              row(23, oid=11, iid=2, side='B', price=50, size=1), row(24, oid=11, iid=2, action='C', side='B', price=50, size=1),   # a second instrument, emptied
              row(25, oid=10, action='M', side='B', price=90, size=1, flags=0), row(26, oid=12, side='B', price=90, size=2)]
    declared = _scope((len(stream),))
    raw = SourceConformanceDriver(declared, tmp_path / 'raw.sqlite', expected_scope_hash=declared.genesis_hash())
    compact = conformance_driver_with_compact_journal(declared, tmp_path / 'compact.sqlite', expected_scope_hash=declared.genesis_hash(), block_bytes=4096)
    checked = conformance_driver_with_compact_journal(declared, tmp_path / 'checked.sqlite', expected_scope_hash=declared.genesis_hash(), block_bytes=4096)
    checked._builder.observation_check_every = 1
    try:
        for cursor, raw_row in enumerate(stream):
            for driver in (raw, compact, checked):
                driver.append(raw_row, cursor=cursor, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
            for iid, composer in checked._builder._composers.items():
                assert composer.canonical() == canonical_tagged_bytes(pack(observe_book(checked._builder.adapter.books[iid]))), cursor
        completions = [d.complete() for d in (raw, compact, checked)]
        assert completions[0].digest == completions[1].digest == completions[2].digest
        raw_rows = list(raw._builder.journal.entries())
        assert pack(raw_rows) == pack(list(compact._builder.journal.entries())) == pack(list(checked._builder.journal.entries()))
        assert len(raw_rows) == 2 * len(stream)
        integrity = checked._builder.adapter.books[1].integrity
        assert {'duplicate_add_order_id', 'modify_side_change', 'modify_missing_treated_as_add', 'cancel_missing_order', 'add_invalid_side'} <= set(integrity)
    finally:
        raw.close(); compact.close(); checked.close()


def test_the_differential_check_counts_per_instrument_composer(tmp_path):
    # the chat-9 ship review: the cadence counted observations per BUILDER while composers are per INSTRUMENT, so a second
    # instrument's composer could be unchecked at its own first observation. Each composer is checked at ITS first and
    # every OBSERVATION_CHECK_EVERY-th observation.
    from test_c15_full_evidence import row
    import c15_builder
    assert c15_builder.OBSERVATION_CHECK_EVERY == 64
    declared = _scope((4,))
    driver = conformance_driver_with_compact_journal(declared, tmp_path / 'c.sqlite', expected_scope_hash=declared.genesis_hash(), block_bytes=4096)
    driver._builder.observation_check_every = 2
    try:
        driver.append(row(0, oid=1), cursor=0, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
        driver.append(row(1, oid=5, iid=2, flags=0), cursor=1, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
        composer = driver._builder._composers[2]
        assert composer.observations == 0
        oid = composer.sorted_oids[0]
        composer.order_bytes[0] = b'["dict",[]]'          # the joined fragment, not the map: what the body is built from
        with pytest.raises(ValueError, match='incremental observation differs'):     # instrument 2's FIRST observation is checked
            driver.append(row(2, oid=6, iid=2), cursor=2, source_member_index=0, source_sha256=SHA_A, session_id="s", raw_symbol="NG", source_dbn_object="synthetic")
    finally:
        driver.close()
