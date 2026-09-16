"""A COMPACT prefix must pass the prepared-context cache and answer journal.verify().

Found 2026-09-16 by the journals review and confirmed in code: CompactReader/FrankieCompactReader
had no verify() although context_session.run() and the learner step call journal.verify(), and the
cache's stored-tail check queried an `entries` table a compact container does not have. Cycle 0 of
the Sunday run used the raw prefix, so nothing fired; cycle 1 is the first compact prefix.
"""
import sqlite3
from types import SimpleNamespace
import pytest
import torch
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.compact_journal import CompactReader, CompactWriter
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.prepared_context_cache import prepare_context_cache


def compact_prefix(tmp_path, rows=3):
    raw = tmp_path / 'source.sqlite'
    writer = EvidenceJournal(raw, create=True)
    for i in range(rows):
        writer.append('synthetic', {'i': i})
    count, head = writer.count, writer.head_hash
    writer.close()
    with sqlite3.connect(raw) as db:
        entries = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
    db.close()
    compact = tmp_path / 'prefix.compact.sqlite'
    with CompactWriter(compact, block_bytes=4096) as out:
        for row in entries:
            out.add(row)
        out.seal(expected_count=count, expected_head_hash=head)
    return compact, count, head


def context_over(reader, head):
    context = SimpleNamespace(builder=SimpleNamespace(journal=reader, _failed=False,
        scope=SimpleNamespace(kind=SimpleNamespace(value='RESULT_BEARING'), scope_id='b' * 64, genesis_hash=lambda: 'c' * 64),
        chain=SimpleNamespace(next_cursor=1)), model=torch.nn.Linear(1, 1), entity=(1, 1), t_ctx=1,
        teacher=None, qsv=None, expected_qsv_hash=None, _model_hash=lambda: 'a' * 64)
    context._prepare = lambda *args: (dict(numeric=torch.tensor([1.])), dict(as_of=10, t_ctx=1, teacher_binding=None,
        source_prefix_hash='d' * 64, journal_prefix_hash=head, journal_entries=1, consumed_rows=1,
        context_cursors=(0,), teacher_hash=None), 'e' * 64, None, [{}])
    return context


@pytest.mark.parametrize('reader_class', [CompactReader, FrankieCompactReader])
def test_compact_prefix_passes_cache_and_verify(tmp_path, reader_class):
    compact, count, head = compact_prefix(tmp_path)
    reader = reader_class(compact, expected_count=count, expected_head_hash=head)
    context = context_over(reader, head)
    try:
        assert reader.stored_tail() == (count, head)
        cache = prepare_context_cache(context, as_of=10, through_cursor=0,
            expected_source_checkpoint=dict(count=count, head_hash=head), expected_model_hash='a' * 64,
            expected_teacher_binding=None, checkpoint_hash='f' * 64, current_checkpoint_hash=lambda: 'f' * 64)
        try:
            assert cache.prepare(10, 0)[2] == 'e' * 64
        finally:
            cache.close()
        reader.verify(count=count, head_hash=head)          # what context_session.run() and the learner call
        with pytest.raises(ValueError):
            reader.verify(count=count, head_hash='0' * 64)
    finally:
        reader.close()


def test_verify_refuses_a_rewritten_block(tmp_path):
    compact, count, head = compact_prefix(tmp_path)
    reader = CompactReader(compact, expected_count=count, expected_head_hash=head)
    try:
        reader.verify(count=count, head_hash=head)
        with sqlite3.connect(compact) as db:
            start, blob = db.execute('SELECT start, body FROM blocks ORDER BY start LIMIT 1').fetchone()
            db.execute('UPDATE blocks SET body=? WHERE start=?', (blob[:-1] + bytes([blob[-1] ^ 1]), start))
        db.close()
        with pytest.raises(ValueError, match='block identity'):
            reader.verify(count=count, head_hash=head)
    finally:
        reader.close()
