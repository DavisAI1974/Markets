"""A COMPACT prefix must pass the prepared-context cache and answer journal.verify().

Found 2026-09-16 by the journals review and confirmed in code: CompactReader/FrankieCompactReader
had no verify() although context_session.run() and the learner step call journal.verify(), and the
cache's stored-tail check ran SQL against an `entries` table a compact container does not have.
Cycle 0 of the Sunday run used the raw prefix, so nothing fired; cycle 1 is the first compact prefix.

Proves: (1) prepare then REUSE through the cache with a compact prefix, and the reuse path decodes
no block; (2) refusal for a changed seal count, a changed seal head, one rewritten block, and a
dropped seal table; (3) the same logical prefix read through the raw reader and the compact reader
yields the same envelope stream and the same stored tail.
"""
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import torch
from research.kalshi.frankie_boss import compact_journal
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal, pack
from research.kalshi.frankie_boss.compact_journal import CompactReader, CompactWriter
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.prepared_context_cache import prepare_context_cache
from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader


def journals(tmp_path, rows=5):
    raw = tmp_path / 'source.sqlite'
    writer = EvidenceJournal(raw, create=True)
    for i in range(rows):
        writer.append('synthetic', {'i': i, 'payload': 'x' * 300})
    count, head = writer.count, writer.head_hash
    writer.close()
    with sqlite3.connect(raw) as db:
        entries = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
    db.close()
    compact = tmp_path / 'prefix.compact.sqlite'
    with CompactWriter(compact, block_bytes=1024) as out:   # several blocks
        for row in entries:
            out.add(row)
        out.seal(expected_count=count, expected_head_hash=head)
    return raw, compact, count, head


def context_over(reader, head):
    context = SimpleNamespace(builder=SimpleNamespace(journal=reader, _failed=False,
        scope=SimpleNamespace(kind=SimpleNamespace(value='RESULT_BEARING'), scope_id='b' * 64, genesis_hash=lambda: 'c' * 64),
        chain=SimpleNamespace(next_cursor=1)), model=torch.nn.Linear(1, 1), entity=(1, 1), t_ctx=1,
        teacher=None, qsv=None, expected_qsv_hash=None, _model_hash=lambda: 'a' * 64)
    context._prepare = lambda *args: (dict(numeric=torch.tensor([1.])), dict(as_of=10, t_ctx=1, teacher_binding=None,
        source_prefix_hash='d' * 64, journal_prefix_hash=head, journal_entries=1, consumed_rows=1,
        context_cursors=(0,), teacher_hash=None), 'e' * 64, None, [{}])
    return context


def cache_for(context, count, head):
    return prepare_context_cache(context, as_of=10, through_cursor=0,
        expected_source_checkpoint=dict(count=count, head_hash=head), expected_model_hash='a' * 64,
        expected_teacher_binding=None, checkpoint_hash='f' * 64, current_checkpoint_hash=lambda: 'f' * 64)


@pytest.mark.parametrize('reader_class', [CompactReader, FrankieCompactReader])
def test_prepare_then_reuse_decodes_no_block_and_verify_agrees(tmp_path, reader_class):
    _, compact, count, head = journals(tmp_path)
    reader = reader_class(compact, expected_count=count, expected_head_hash=head)
    context = context_over(reader, head)
    decoded = []
    original = compact_journal.decode_block
    try:
        assert reader.stored_tail() == (count, head)
        cache = cache_for(context, count, head)
        try:
            with patch.object(compact_journal, 'decode_block', lambda blob: decoded.append(1) or original(blob)):
                for _ in range(3):
                    assert cache.prepare(10, 0)[2] == 'e' * 64        # the reuse path
            assert decoded == [], 'cache reuse must not decode a block'
        finally:
            cache.close()
        reader.verify(count=count, head_hash=head)          # what context_session.run() and the learner call
        with pytest.raises(PermissionError):
            reader.append('synthetic', {})
    finally:
        reader.close()


@pytest.mark.parametrize('tamper', ['seal_count', 'seal_head', 'block_sha', 'drop_seal'])
def test_verify_and_cache_refuse_every_tamper(tmp_path, tamper):
    _, compact, count, head = journals(tmp_path)
    reader = CompactReader(compact, expected_count=count, expected_head_hash=head)
    try:
        reader.verify(count=count, head_hash=head)
        with sqlite3.connect(compact) as db:
            if tamper == 'seal_count':
                db.execute('UPDATE seal SET count=count+1')
            elif tamper == 'seal_head':
                db.execute('UPDATE seal SET head=?', ('0' * 64,))
            elif tamper == 'block_sha':
                start, blob = db.execute('SELECT start, body FROM blocks ORDER BY start LIMIT 1').fetchone()
                db.execute('UPDATE blocks SET body=? WHERE start=?', (blob[:-1] + bytes([blob[-1] ^ 1]), start))
            elif tamper == 'drop_seal':
                db.execute('DROP TABLE seal')
        db.close()
        with pytest.raises((ValueError, sqlite3.OperationalError)):
            reader.verify(count=count, head_hash=head)
        context = context_over(reader, head)
        if tamper == 'block_sha':
            # The cache's tail check is the seal, O(1) and no decode, so a rewritten block is not
            # its job: consumption (entries) and verify() refuse it, as asserted above and here.
            with pytest.raises(ValueError):
                list(reader.entries())
        else:
            with pytest.raises((ValueError, sqlite3.OperationalError)):
                cache_for(context, count, head)      # a seal tamper must refuse at the cache's tail check
    finally:
        reader.close()


def test_raw_and_compact_readers_yield_the_same_stream(tmp_path):
    raw, compact, count, head = journals(tmp_path)
    with VerifiedJournalReader(raw, expected_count=count, expected_head_hash=head) as a, \
            CompactReader(compact, expected_count=count, expected_head_hash=head) as b, \
            FrankieCompactReader(compact, expected_count=count, expected_head_hash=head, workers=1) as c:
        stream_a = [pack(e) for e in a.entries()]
        stream_b = [pack(e) for e in b.entries()]
        stream_c = [pack(e) for e in c.entries()]
        assert stream_a == stream_b == stream_c
        assert a.stored_tail() == b.stored_tail() == c.stored_tail() == (count, head)
