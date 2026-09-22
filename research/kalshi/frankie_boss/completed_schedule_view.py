"""Read-only scheduling view of an independently attested completed source.

This does not restore an adapter or authorize source processing. The existing
schedule builder consumes and validates every INPUT/APPLIED pair once.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from .c15_journal import SCHEMA, unpack, evidence_hash
from .c15_registry import implementation_identity
from .causal_prefix_records import RecordPrefixChain
from .verified_journal_reader import VerifiedJournalReader


class _CompletedJournal:
    def __init__(self, reader, chain):
        self.reader,self.chain=reader,chain
        self.count,self.head_hash=reader.count,reader.head_hash
        self.verified_records=None
        self.verified_terminal_prefix=None

    def entries(self):
        terminal=None
        for entry in self.reader.entries():
            required='INPUT' if entry['ordinal']%2==0 else 'APPLIED'
            if entry['kind']!=required:
                raise ValueError('completed journal INPUT/APPLIED pair mismatch')
            if required=='APPLIED':terminal=entry['payload']
            yield entry
        if (terminal is None or terminal.get('record_count')!=self.chain.next_cursor
                or terminal.get('group_count')!=self.chain.next_global_group_ordinal
                or terminal.get('terminal_prefix_hash')!=self.chain.prefix_hash):
            raise ValueError('completed journal terminal source state mismatch')
        self.verified_records=self.chain.next_cursor
        self.verified_terminal_prefix=self.chain.prefix_hash

    def close(self):self.reader.close()


def open_completed_schedule_view(scope,journal_path,state_path,expected_state_sha256,
                                 expected_state_hash,completion, *, reader_factory=VerifiedJournalReader):
    raw=Path(state_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_state_sha256:
        raise ValueError('completed state bytes differ from independent witness')
    state=unpack(json.loads(raw))
    keys={'schema','scope_genesis_hash','implementation','adapter','prefix','sessions',
          'journal_count','journal_hash','state_hash'}
    if type(state) is not dict or set(state)!=keys:
        raise ValueError('completed state fields mismatch')
    if (state['state_hash']!=expected_state_hash or
            evidence_hash({k:v for k,v in state.items() if k!='state_hash'})!=expected_state_hash):
        raise ValueError('completed state hash mismatch')
    if (state['schema']!=SCHEMA or state['scope_genesis_hash']!=scope.genesis_hash()
            or state['implementation']!=implementation_identity()):
        raise ValueError('completed state source implementation identity mismatch')
    chain=RecordPrefixChain.restore(scope,state['prefix'])
    if chain.next_cursor!=sum(member.mbo_records for member in scope.members):
        raise ValueError('incomplete source cannot provide completed schedule view')
    expected=dict(schema='BOSS_SOURCE_CONFORMANCE_V1',builder_state_hash=expected_state_hash,
        scope_kind=scope.kind.value,scope_hash=scope.genesis_hash(),record_count=chain.next_cursor,
        member_counts=tuple(m.mbo_records for m in scope.members),
        group_count=chain.next_global_group_ordinal,source_prefix_hash=chain.prefix_hash,
        journal_count=state['journal_count'],journal_hash=state['journal_hash'])
    actual=dict(completion)
    actual['member_counts']=tuple(actual.get('member_counts',()))
    if actual!=expected:
        raise ValueError('completion receipt differs from full state')
    if (state['journal_count']!=2*chain.next_cursor or
            state['adapter']['record_count']!=chain.next_cursor or
            state['adapter']['completed_event_group_count']!=chain.next_global_group_ordinal):
        raise ValueError('completed state adapter/pair counts mismatch')
    reader=reader_factory(journal_path,expected_count=state['journal_count'],
                                 expected_head_hash=state['journal_hash'])
    return SimpleNamespace(scope=scope,chain=chain,journal=_CompletedJournal(reader,chain),
        _failed=False,evidence_class='READ_ONLY_COMPLETED_SOURCE_SCHEDULE_VIEW')
