"""WAL regression: a row appended by another connection during iteration must be rejected.

In WAL mode the reader's SELECT holds a snapshot that excludes a concurrent append, so the
rows it iterated can equal the supplied expectations while the stored tail has moved. The
reader must reread the stored tail after the SELECT finishes and reject the change.
"""
import sqlite3

import pytest

from c15_journal import EvidenceJournal
from verified_journal_reader import VerifiedJournalReader


def wal_journal(tmp_path):
    journal = EvidenceJournal(tmp_path / 'wal.sqlite', create=True)
    for value in (1, 2, 3):
        journal.append('KIND', dict(value=value))
    assert journal.connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    return journal


def test_append_by_another_connection_during_iteration_is_rejected_when_exhausted(tmp_path):
    journal = wal_journal(tmp_path)
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count, expected_head_hash=journal.head_hash)
    stream = reader.entries()
    assert next(stream)['payload']['value'] == 1
    writer = EvidenceJournal(journal.path)  # a second connection, as a live writer would hold
    writer.append('LATE', dict(value=4))
    assert next(stream)['payload']['value'] == 2
    assert next(stream)['payload']['value'] == 3
    with pytest.raises(ValueError, match='changed during iteration'):
        next(stream)
    with pytest.raises(ValueError, match='changed during iteration'):
        reader.verify(count=reader.count, head_hash=reader.head_hash)
    reader.close(); writer.close(); journal.close()


def test_tail_reread_uses_the_stored_tail_not_the_iterated_rows(tmp_path):
    journal = wal_journal(tmp_path)
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count, expected_head_hash=journal.head_hash)
    stream = reader.entries()
    next(stream)
    raw = sqlite3.connect(journal.path)
    for operation in ('update', 'delete'):
        raw.execute('DROP TRIGGER forbid_' + operation)
    raw.execute('DELETE FROM entries WHERE ordinal=2')  # external damage to the stored tail, not a journal write
    raw.commit(); raw.close()
    next(stream)
    next(stream)  # the snapshot still serves the deleted row
    with pytest.raises(ValueError, match='changed during iteration'):
        next(stream)
    reader.close(); journal.close()


def test_unchanged_wal_journal_still_verifies(tmp_path):
    journal = wal_journal(tmp_path)
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count, expected_head_hash=journal.head_hash)
    assert [entry['payload']['value'] for entry in reader.entries()] == [1, 2, 3]
    reader.verify(count=journal.count, head_hash=journal.head_hash)
    reader.close(); journal.close()
