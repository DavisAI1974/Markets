"""Read-only online C15 prefix copies for actual request capacity preparation.

This is not a C15Builder checkpoint, a completed source receipt or training
permission. Original journal envelopes/hashes are copied byte-for-byte.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from .c15_journal import EvidenceJournal, unpack
from .context_session import journal_prefix


@dataclass(frozen=True)
class PrefixCursor:
    next_cursor: int
    prefix_hash: str


@dataclass(frozen=True)
class OnlinePrefix:
    scope: object
    journal: object
    chain: PrefixCursor
    _failed: bool = False
    evidence_class: str = 'READ_ONLY_COMPLETED_ONLINE_PREFIX'


def snapshot_closed_prefix(source_path, destination_path, scope, *, group_index):
    """Copy through a selected zero-based F_LAST group, if fully applied already.

    The source connection is read-only. An unfinished INPUT tail stays in the
    original journal; no record is erased or represented as completed.
    """
    if type(group_index) is not int or group_index < 0:
        raise ValueError('explicit zero-based closed group required')
    source = Path(source_path).resolve()
    destination = Path(destination_path).resolve()
    if source == destination or destination.exists():
        raise ValueError('fresh distinct prefix snapshot path required')
    selected, group, final = [], -1, None
    connection = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
    try:
        # Append-only ordinals permit short paged reads without a long read
        # transaction blocking the live rollback-journal writer's FULL commit.
        # Finish fetching each tiny page before decoding any expensive body.
        after = -1
        while final is None:
            cursor = connection.execute('SELECT ordinal,kind,body,digest FROM entries '
                'WHERE ordinal>? ORDER BY ordinal LIMIT 8', (after,))
            page = cursor.fetchall()
            cursor.close()
            if not page:
                break
            for row in page:
                selected.append(row)
                after = row[0]
                if row[1] == 'APPLIED':
                    payload = unpack(json.loads(row[2]))['payload']
                    if payload['raw_record']['flags'] & 128:
                        group += 1
                        if group == group_index:
                            final = payload
                            break
    finally:
        connection.close()
    if final is None:
        raise ValueError(f'selected closed group not yet applied: available={group+1}, required={group_index+1}')
    created = EvidenceJournal(destination, create=True)
    try:
        with created.connection:
            created.connection.executemany('INSERT INTO entries VALUES (?,?,?,?)', selected)
    finally:
        created.close()
    journal = EvidenceJournal(destination)
    journal.connection.execute('PRAGMA query_only=ON')
    view = OnlinePrefix(scope, journal, PrefixCursor(final['cursor']+1, final['terminal_prefix_hash']))
    maximum_event = maximum_receive = 0
    for entry in journal_prefix(view, final['cursor']):
        maximum_event = max(maximum_event, entry['normalized']['ts_event_ns'])
        maximum_receive = max(maximum_receive, entry['normalized']['ts_recv_ns'])
    receipt = dict(schema='BOSS_ONLINE_PREFIX_SNAPSHOT_V1', evidence_class=view.evidence_class,
        original_journal=str(source), snapshot_journal=str(destination),
        group_index=group_index, groups_in_prefix=group_index+1,
        records_in_prefix=view.chain.next_cursor,
        source_records_expected=sum(member.mbo_records for member in scope.members),
        source_scope_hash=scope.genesis_hash(), source_prefix_hash=view.chain.prefix_hash,
        journal_count=journal.count, journal_head_hash=journal.head_hash,
        as_of=maximum_receive, source_as_of=maximum_event,
        full_source_complete=False, model_forward_performed=False)
    return view, receipt
