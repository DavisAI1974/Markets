"""Explicit rehydration of an interrupted source journal into a retained fork.

No model or principal calls. Existing adapter transitions are recomputed solely
to restore memory and are checked against every exact retained envelope. Their
journal records are copied, never appended again. A final pending INPUT can be
completed once; FAILED or otherwise nonalternating evidence is refused intact.
"""
import hashlib
from pathlib import Path
import sqlite3

from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter
from .c15_builder import C15Builder
from .verified_journal_reader import VerifiedJournalReader
from .causal_prefix_records import RecordPrefixChain
from .c15_registry import implementation_identity
from .c15_journal import EvidenceJournal, SCHEMA, evidence_hash, canonical_bytes, pack


def file_sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


class _ReplayJournal:
    def __init__(self, parent, destination):
        self.parent, self.destination = parent, destination
        self.iterator = iter(parent.entries())
        self.raw_connection = sqlite3.connect(parent.path.resolve().as_uri()+'?mode=ro', uri=True)
        self.raw_iterator = iter(self.raw_connection.execute('SELECT body,digest FROM entries ORDER BY ordinal'))
        self.pending = None
        self.count = 0
        self.head_hash = evidence_hash(dict(schema=SCHEMA))

    def peek_input(self):
        if self.pending is not None:
            raise ValueError('unconsumed pending replay envelope')
        self.pending = next(self.iterator)
        if self.pending['kind'] != 'INPUT':
            raise ValueError('FAILED or nonalternating original evidence requires explicit separate reconciliation')
        return self.pending['payload']

    def append(self, kind, payload):
        if self.count < self.parent.count:
            expected = self.pending if self.pending is not None else next(self.iterator)
            self.pending = None
            body, digest = next(self.raw_iterator)
            generated = dict(schema=SCHEMA,ordinal=self.count,previous_hash=self.head_hash,kind=kind,payload=payload)
            if canonical_bytes(pack(generated)) != body:
                raise ValueError('rehydrated adapter output differs from retained exact envelope')
            if expected['kind'] != kind:
                raise ValueError('FAILED or nonalternating original evidence')
            self.head_hash = digest
            self.count += 1
            return self.head_hash
        # Only the missing APPLIED of an already retained pending INPUT may be
        # appended during rehydration. A failed replay cannot invent FAILED rows.
        if self.parent.count % 2 != 1 or self.count != self.parent.count or kind != 'APPLIED':
            raise ValueError('unexpected extension during source rehydration')
        if next(self.iterator,None) is not None:
            raise ValueError('parent iterator exceeds its independent count')
        result = self.destination.append(kind,payload)
        self.count, self.head_hash = self.destination.count, self.destination.head_hash
        return result


def rehydrate_source(scope, parent_path, destination_path, *, expected_parent, event=None):
    """Return recovered C15Builder and receipt; parent is independently pinned.

    Caller must stop the failed writer first. The original DB and failure receipt
    remain untouched. Destination WAL + FULL permits readers without interrupting
    future append commits; its WAL belongs to the live database until closed.
    """
    parent_path, destination_path = Path(parent_path), Path(destination_path)
    if parent_path.resolve()==destination_path.resolve():
        raise ValueError('recovery must preserve original parent journal')
    if file_sha256(parent_path)!=expected_parent['sha256']:
        raise ValueError('original parent physical bytes changed')
    parent=VerifiedJournalReader(parent_path,expected_count=expected_parent['count'],expected_head_hash=expected_parent['head_hash'])
    destination=None
    replay=None
    try:
        if (parent.count,parent.head_hash)!=(expected_parent['count'],expected_parent['head_hash']):
            raise ValueError('original parent journal checkpoint changed')
        with destination_path.open('xb'): pass
        connection=sqlite3.connect(destination_path)
        try:
            backup_source=sqlite3.connect(parent_path.resolve().as_uri()+'?mode=ro',uri=True)
            try: backup_source.backup(connection)
            finally: backup_source.close()
            if connection.execute('PRAGMA journal_mode=WAL').fetchone()[0]!='wal':
                raise ValueError('WAL recovery journal unavailable')
            connection.execute('PRAGMA synchronous=FULL')
        finally:
            connection.close()
        destination=EvidenceJournal(destination_path)
        if (destination.count,destination.head_hash)!=(parent.count,parent.head_hash):
            raise ValueError('backup differs from verified original parent')
        builder=C15Builder.__new__(C15Builder)
        builder.scope, builder.chain = scope, RecordPrefixChain(scope)
        builder.adapter, builder.identity = V4MboAdapter(), implementation_identity()
        builder._sessions, builder._failed = {}, False
        replay=_ReplayJournal(parent,destination)
        builder.journal=replay
        total=(parent.count+1)//2
        for _ in range(total):
            submitted=replay.peek_input()
            if submitted['cursor']!=builder.chain.next_cursor or submitted['scope_genesis_hash']!=scope.genesis_hash():
                raise ValueError('original input source scope or cursor differs')
            builder.apply(submitted['record'],source_member_index=submitted['source_member_index'],
                session_id=submitted['session_id'],raw_symbol=submitted['raw_symbol'],
                source_dbn_object=submitted['source_dbn_object'])
            if event is not None and (builder.chain.next_cursor%100==0 or builder.chain.next_cursor==total):
                event(dict(phase='source_rehydration',records=builder.chain.next_cursor,total_records=total))
        if replay.count!=destination.count or replay.head_hash!=destination.head_hash:
            raise ValueError('rehydrated journal head differs')
        if next(replay.iterator,None) is not None:
            raise ValueError('unconsumed parent evidence')
        if file_sha256(parent_path)!=expected_parent['sha256']:
            raise ValueError('parent changed during explicit recovery')
        replay.raw_connection.close()
        builder.journal=destination
        receipt=dict(schema='C15_EXPLICIT_SOURCE_RECOVERY_V1',parent_path=str(parent_path),parent=dict(expected_parent),
            recovered_path=str(destination_path),existing_entries_rewritten=0,
            replayed_complete_records=parent.count//2,pending_input_completed=parent.count%2,
            next_cursor=builder.chain.next_cursor,journal_count=destination.count,journal_hash=destination.head_hash,
            recovery_method='EXACT_ENVELOPE_VERIFIED_IN_MEMORY_REHYDRATION',journal_mode='wal',synchronous='FULL',
            verification_reader='VerifiedJournalReader',parent_verification_passes=1,
            recovery_code_sha256=file_sha256(Path(__file__)),
            reader_code_sha256=file_sha256(Path(__file__).with_name('verified_journal_reader.py')))
        return builder,receipt
    except BaseException:
        if destination is not None: destination.close()
        raise
    finally:
        if replay is not None: replay.raw_connection.close()
        parent.close()
