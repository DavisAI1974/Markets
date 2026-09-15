"""Bounded-memory, verified prefix snapshots of closed C15 evidence journals.

Original ordinal/kind/body/digest bytes are copied page by page into a staging file, each
page committed before the next is read, then the whole copy is verified with
VerifiedJournalReader and renamed into the fresh destination. A failed attempt leaves its
staging file beside the never-created destination for diagnosis; nothing is overwritten
and the source is never opened for writing.

This is not a C15Builder checkpoint, a completed source receipt or training permission.
It is not wired into any runtime path and online_source_prefix.py is unchanged.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import uuid

try:
    from .c15_journal import EvidenceJournal, pack
    from .verified_journal_reader import VerifiedJournalReader
except ImportError:
    from c15_journal import EvidenceJournal, pack
    from verified_journal_reader import VerifiedJournalReader

SCHEMA = 'C15_JOURNAL_PREFIX_SNAPSHOT_V1'
EVIDENCE_CLASS = 'READ_ONLY_VERIFIED_JOURNAL_PREFIX'
F_LAST = 128
_HEX = frozenset('0123456789abcdef')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


WAL_HEADER_BYTES = 32


def _sidecars(path):
    """Sidecars that mean the journal is not closed.

    A hot rollback journal (-journal) or a WAL file carrying frames beyond its 32-byte
    header means a writer's work is not in the main file. A read-only open of a WAL-mode
    database creates zero-length -wal/-shm files it cannot remove; those are not content.
    """
    hot = path.with_name(path.name + '-journal')
    wal = path.with_name(path.name + '-wal')
    found = []
    if hot.exists():
        found.append(hot)
    if wal.exists() and wal.stat().st_size > WAL_HEADER_BYTES:
        found.append(wal)
    return found


def _pages(connection, last_ordinal, page_rows):
    """Short paged reads: at most page_rows rows are ever held before they are written."""
    after = -1
    while after < last_ordinal:
        cursor = connection.execute(
            'SELECT ordinal,kind,body,digest FROM entries WHERE ordinal>? AND ordinal<=? ORDER BY ordinal LIMIT ?',
            (after, last_ordinal, page_rows))
        page = cursor.fetchall()
        cursor.close()
        if not page:
            return
        after = page[-1][0]
        yield page


def _verify_pairs(entries, through_cursor):
    """Stream the verified copy once; check every INPUT/APPLIED pair and the F_LAST close."""
    applied, pending, last_applied = 0, None, None
    groups, maximum_event, maximum_receive = 0, 0, 0
    for entry in entries:
        payload = entry['payload']
        if entry['kind'] == 'INPUT':
            if pending is not None or payload['cursor'] != applied:
                raise ValueError('journal input cursor gap or unprocessed submission')
            pending = payload
        elif entry['kind'] == 'APPLIED':
            if (pending is None or payload['cursor'] != pending['cursor']
                    or pack(payload['raw_record']) != pack(pending['record'])
                    or any(payload[k] != pending[k] for k in ('source_member_index', 'session_id'))):
                raise ValueError('journal applied record differs from submitted evidence')
            flags = payload['raw_record']['flags']
            if type(flags) is not int:
                raise ValueError('applied record carries no integer flags')
            if flags & F_LAST:
                groups += 1
            maximum_event = max(maximum_event, payload['normalized']['ts_event_ns'])
            maximum_receive = max(maximum_receive, payload['normalized']['ts_recv_ns'])
            applied, pending, last_applied = applied + 1, None, payload
        else:
            raise ValueError('failed or unknown journal entry cannot be snapshotted as complete')
    if pending is not None or applied != through_cursor + 1 or last_applied['cursor'] != through_cursor:
        raise ValueError('copied prefix does not account for every record through the selected cursor')
    if not last_applied['raw_record']['flags'] & F_LAST:
        raise ValueError('selected cursor does not close an F_LAST group')
    return dict(groups_in_prefix=groups, source_prefix_hash=last_applied['terminal_prefix_hash'],
                as_of=maximum_receive, source_as_of=maximum_event,
                record_count=last_applied['record_count'], group_count=last_applied['group_count'])


def snapshot_journal_prefix(source_path, destination_path, *, parent_count, parent_head_hash, through_cursor,
                            parent_sha256=None, page_rows=64):
    """Copy ordinals 0..2*through_cursor+1 of a closed journal into a fresh verified snapshot.

    parent_count/parent_head_hash are the independently trusted tail of the source; the stored
    tail must match them before a byte is copied. through_cursor selects the final APPLIED
    record, which must close an F_LAST group. Returns the receipt; open the snapshot with
    VerifiedJournalReader(receipt['snapshot_journal'], expected_count=receipt['journal_count'],
    expected_head_hash=receipt['journal_head_hash']).
    """
    if type(parent_count) is not int or parent_count < 0:
        raise ValueError('independently trusted parent count required')
    if type(parent_head_hash) is not str or len(parent_head_hash) != 64 or not _HEX.issuperset(parent_head_hash):
        raise ValueError('independently trusted parent head hash required')
    if type(through_cursor) is not int or through_cursor < 0:
        raise ValueError('explicit zero-based selected cursor required')
    if type(page_rows) is not int or page_rows < 1:
        raise ValueError('positive page size required')
    source, destination = Path(source_path).resolve(), Path(destination_path).resolve()
    if source == destination or destination.exists() or destination.is_symlink():
        raise ValueError('fresh distinct prefix snapshot path required')
    if source.is_symlink() or not source.is_file():
        raise ValueError('closed source journal file required')
    if _sidecars(source):
        raise ValueError('source journal is not closed: sidecar files present')
    if parent_sha256 is not None and file_sha256(source) != parent_sha256:
        raise ValueError('source journal physical bytes differ from trusted parent')
    before = os.stat(source)
    parent = VerifiedJournalReader(source, expected_count=parent_count, expected_head_hash=parent_head_hash)
    parent.close()
    last_ordinal = 2 * through_cursor + 1
    if last_ordinal >= parent_count:
        raise ValueError('selected cursor lies beyond the trusted parent count')
    staging = destination.with_name(destination.name + '.partial-' + uuid.uuid4().hex)
    try:
        copied, last_digest = 0, None
        created = EvidenceJournal(staging, create=True)
        try:
            connection = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
            try:
                connection.execute('PRAGMA query_only=1')
                for page in _pages(connection, last_ordinal, page_rows):
                    for ordinal, kind, body, digest in page:
                        if (ordinal != copied or kind != ('INPUT' if ordinal % 2 == 0 else 'APPLIED')
                                or type(body) is not bytes or type(digest) is not str):
                            raise ValueError('source prefix is not an unbroken INPUT/APPLIED sequence')
                        copied += 1
                    with created.connection:  # each page is durable before the next is read
                        created.connection.executemany('INSERT INTO entries VALUES (?,?,?,?)', page)
                    last_digest = page[-1][3]
            finally:
                connection.close()
        finally:
            created.close()
        if copied != last_ordinal + 1:
            raise ValueError('source journal ends before the selected cursor')
        reader = VerifiedJournalReader(staging, expected_count=copied, expected_head_hash=last_digest)
        try:
            summary = _verify_pairs(reader.entries(), through_cursor)
        finally:
            reader.close()
        after = os.stat(source)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or _sidecars(source):
            raise ValueError('source journal changed while it was being copied')
        if parent_sha256 is not None and file_sha256(source) != parent_sha256:
            raise ValueError('source journal physical bytes changed during copy')
    except BaseException as exc:
        exc.add_note(f'partial prefix snapshot retained for diagnosis: {staging}')
        raise
    os.rename(staging, destination)  # fails if the destination appeared meanwhile; never overwrites
    return dict(schema=SCHEMA, evidence_class=EVIDENCE_CLASS,
                original_journal=str(source), snapshot_journal=str(destination),
                parent=dict(count=parent_count, head_hash=parent_head_hash, sha256=parent_sha256),
                through_cursor=through_cursor, records_in_prefix=through_cursor + 1,
                journal_count=copied, journal_head_hash=last_digest, snapshot_sha256=file_sha256(destination),
                **summary,
                provenance=dict(method='INCREMENTAL_ORIGINAL_BYTE_COPY', page_rows=page_rows,
                                verified_by='verified_journal_reader.VerifiedJournalReader',
                                source_size_bytes=before.st_size, source_mtime_ns=before.st_mtime_ns,
                                staging_path=str(staging)),
                full_source_complete=False, model_forward_performed=False)
