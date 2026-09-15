"""Bounded verified prefix snapshots: exact bytes, incremental copying, refusals, retained partials.

Sources are temporary C15Builder journals closed before snapshotting; no retained database is read.
"""
import hashlib
import sqlite3

import pytest

from research.kalshi.frankie_boss import journal_prefix_snapshot as module
from research.kalshi.frankie_boss.c15_builder import C15Builder, ADAPTER_REVISION
from research.kalshi.frankie_boss.causal_prefix import SourceScope, SourceMember, ScopeKind
from research.kalshi.frankie_boss.journal_prefix_snapshot import snapshot_journal_prefix
from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader


def record(order_id, flags, ts):
    return dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=order_id, action='A', side='A',
                price=100 + order_id, size=1, flags=flags, sequence=order_id, ts_event=ts, ts_recv=ts + 1, ts_in_delta=1)


def closed_source(tmp_path, flags=(128, 0, 128, 0, 0, 128), name='source.sqlite'):
    """Records 0..5 where cursors 0, 2 and 5 close F_LAST groups; the builder is closed afterwards."""
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a' * 64, (SourceMember(0, 'synthetic', 'b' * 64, 112, len(flags)),),
                        ADAPTER_REVISION)
    builder = C15Builder(scope, tmp_path / name)
    for index, flag in enumerate(flags):
        builder.apply(record(index + 1, flag, 10 * (index + 1)), source_member_index=0, session_id='synthetic')
    rows = list(builder.journal.connection.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal'))
    parent = dict(parent_count=builder.journal.count, parent_head_hash=builder.journal.head_hash)
    builder.journal.close()
    return builder.journal.path, rows, parent


def rows_of(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return list(connection.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal'))
    finally:
        connection.close()


def partials(destination):
    return sorted(destination.parent.glob(destination.name + '.partial-*'))


def test_snapshot_retains_exact_original_rows_and_leaves_source_untouched(tmp_path):
    source, rows, parent = closed_source(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / 'prefix.sqlite'
    receipt = snapshot_journal_prefix(source, destination, through_cursor=2, parent_sha256=before, **parent)
    assert rows_of(destination) == rows[:6]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert rows_of(source) == rows
    assert receipt['journal_count'] == 6 and receipt['journal_head_hash'] == rows[5][3]
    assert receipt['records_in_prefix'] == 3 and receipt['through_cursor'] == 2 and receipt['groups_in_prefix'] == 2
    assert receipt['as_of'] == 31 and receipt['source_as_of'] == 30
    assert receipt['source_prefix_hash'] and len(receipt['source_prefix_hash']) == 64
    assert receipt['snapshot_sha256'] == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert receipt['parent'] == dict(count=parent['parent_count'], head_hash=parent['parent_head_hash'], sha256=before)
    assert receipt['full_source_complete'] is False and receipt['model_forward_performed'] is False
    assert receipt['provenance']['verified_by'] == 'verified_journal_reader.VerifiedJournalReader'
    assert not partials(destination)
    reader = VerifiedJournalReader(destination, expected_count=receipt['journal_count'],
                                   expected_head_hash=receipt['journal_head_hash'])
    assert [e['payload']['cursor'] for e in reader.entries() if e['kind'] == 'APPLIED'] == [0, 1, 2]
    reader.close()
    full = snapshot_journal_prefix(source, tmp_path / 'full.sqlite', through_cursor=5, **parent)
    assert rows_of(tmp_path / 'full.sqlite') == rows and full['groups_in_prefix'] == 3
    assert full['full_source_complete'] is False


def test_copy_is_paged_and_durable_before_the_next_page_is_read(tmp_path, monkeypatch):
    source, rows, parent = closed_source(tmp_path)
    destination = tmp_path / 'prefix.sqlite'
    seen, pages = [], module._pages
    def observed(connection, last_ordinal, page_rows):
        for page in pages(connection, last_ordinal, page_rows):
            assert len(page) <= page_rows
            if seen:
                staging = partials(destination)
                assert len(staging) == 1 and rows_of(staging[0]) == seen  # earlier pages already written
            seen.extend(page)
            yield page
    monkeypatch.setattr(module, '_pages', observed)
    receipt = snapshot_journal_prefix(source, destination, through_cursor=5, page_rows=2, **parent)
    assert len(seen) == 12 and seen == rows and receipt['provenance']['page_rows'] == 2
    assert rows_of(destination) == rows and not partials(destination)


@pytest.mark.parametrize('through_cursor,message', [(1, 'F_LAST'), (3, 'F_LAST'), (6, 'beyond the trusted parent')])
def test_non_f_last_or_out_of_range_cutoff_is_refused_and_partial_retained(tmp_path, through_cursor, message):
    source, rows, parent = closed_source(tmp_path)
    destination = tmp_path / 'prefix.sqlite'
    with pytest.raises(ValueError, match=message) as refused:
        snapshot_journal_prefix(source, destination, through_cursor=through_cursor, **parent)
    assert not destination.exists()
    retained = partials(destination)
    if message == 'F_LAST':
        assert len(retained) == 1 and rows_of(retained[0]) == rows[:2 * through_cursor + 2]
        assert str(retained[0]) in ''.join(refused.value.__notes__)
    else:
        assert not retained
    assert rows_of(source) == rows


def test_failed_row_in_prefix_is_refused(tmp_path):
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a' * 64, (SourceMember(0, 'synthetic', 'b' * 64, 112, 2),), ADAPTER_REVISION)
    builder = C15Builder(scope, tmp_path / 'failed.sqlite')
    builder.apply(record(1, 128, 10), source_member_index=0, session_id='synthetic')
    with pytest.raises(ValueError):
        builder.apply(record(2, 128, 20), source_member_index=0, session_id='')
    parent = dict(parent_count=builder.journal.count, parent_head_hash=builder.journal.head_hash)
    builder.journal.close()
    assert parent['parent_count'] == 4  # INPUT, APPLIED, INPUT, FAILED
    with pytest.raises(ValueError, match='unbroken INPUT/APPLIED'):
        snapshot_journal_prefix(builder.journal.path, tmp_path / 'prefix.sqlite', through_cursor=1, **parent)
    assert snapshot_journal_prefix(builder.journal.path, tmp_path / 'ok.sqlite', through_cursor=0, **parent)['journal_count'] == 2


@pytest.mark.parametrize('damage', [
    "UPDATE entries SET digest='0000000000000000000000000000000000000000000000000000000000000000' WHERE ordinal=1",
    "UPDATE entries SET body=CAST('[\"null\"]' AS BLOB) WHERE ordinal=2",
    "UPDATE entries SET kind='APPLIED' WHERE ordinal=2",
])
def test_corrupt_prefix_is_rejected_and_partial_retained(tmp_path, damage):
    source, rows, parent = closed_source(tmp_path)
    raw = sqlite3.connect(source)
    for operation in ('update', 'delete'):
        raw.execute('DROP TRIGGER forbid_' + operation)
    raw.execute(damage); raw.commit(); raw.close()
    destination = tmp_path / 'prefix.sqlite'
    with pytest.raises(ValueError):
        snapshot_journal_prefix(source, destination, through_cursor=2, **parent)
    assert not destination.exists()
    assert len(partials(destination)) <= 1


def test_existing_destination_is_preserved_and_never_overwritten(tmp_path):
    source, rows, parent = closed_source(tmp_path)
    destination = tmp_path / 'prefix.sqlite'
    destination.write_bytes(b'prior evidence')
    with pytest.raises(ValueError, match='fresh distinct'):
        snapshot_journal_prefix(source, destination, through_cursor=2, **parent)
    assert destination.read_bytes() == b'prior evidence' and not partials(destination)
    with pytest.raises(ValueError, match='fresh distinct'):
        snapshot_journal_prefix(source, source, through_cursor=2, **parent)
    late = tmp_path / 'late.sqlite'
    pages = module._pages
    def plant(connection, last_ordinal, page_rows):
        yield from pages(connection, last_ordinal, page_rows)
        late.write_bytes(b'appeared during the copy')
    module._pages = plant
    try:
        with pytest.raises(FileExistsError):
            snapshot_journal_prefix(source, late, through_cursor=2, **parent)
    finally:
        module._pages = pages
    assert late.read_bytes() == b'appeared during the copy' and len(partials(late)) == 1


def test_wrong_parent_and_unclosed_source_are_refused(tmp_path):
    source, rows, parent = closed_source(tmp_path)
    destination = tmp_path / 'prefix.sqlite'
    with pytest.raises(ValueError, match='differs from checkpoint'):
        snapshot_journal_prefix(source, destination, through_cursor=2, parent_count=parent['parent_count'] - 2,
                                parent_head_hash=parent['parent_head_hash'])
    with pytest.raises(ValueError, match='physical bytes differ'):
        snapshot_journal_prefix(source, destination, through_cursor=2, parent_sha256='0' * 64, **parent)
    sidecar = source.with_name(source.name + '-journal')
    sidecar.write_bytes(b'')
    with pytest.raises(ValueError, match='not closed'):
        snapshot_journal_prefix(source, destination, through_cursor=2, **parent)
    sidecar.unlink()
    assert not destination.exists() and not partials(destination)


def test_retained_wal_snapshot_is_an_acceptable_source(tmp_path):
    source, rows, parent = closed_source(tmp_path)
    retained = tmp_path / 'retained.sqlite'
    with retained.open('xb'):
        pass
    origin, copy = sqlite3.connect(source), sqlite3.connect(retained)
    origin.backup(copy)
    assert copy.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    copy.close(); origin.close()
    assert not module._sidecars(retained)
    receipt = snapshot_journal_prefix(retained, tmp_path / 'prefix.sqlite', through_cursor=2, **parent)
    assert rows_of(tmp_path / 'prefix.sqlite') == rows[:6] and receipt['original_journal'] == str(retained.resolve())
