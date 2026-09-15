"""Explicit interrupted source recovery, never principal or model execution."""
import sqlite3

import pytest

from research.kalshi.frankie_boss import source_recovery as recovery
from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.causal_prefix import SourceScope, SourceMember, ScopeKind


def raw(i):
    return dict(instrument_id=1,publisher_id=1,channel_id=1,order_id=i+1,action='A',side='A',
        price=100+i,size=10,flags=128,sequence=i,ts_event=100*i+1,ts_recv=100*i+2,ts_in_delta=1)


def interrupted_case(tmp_path):
    from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'source','b'*64,100,3),),SUPPORTED_ADAPTER_REVISION)
    parent=tmp_path/'parent.sqlite'
    builder=C15Builder(scope,parent)
    builder.apply(raw(0),source_member_index=0,session_id='s')
    builder.journal.append('INPUT',dict(record=raw(1),cursor=1,source_member_index=0,session_id='s',
        raw_symbol=None,source_dbn_object=None,scope_genesis_hash=scope.genesis_hash()))
    pin=dict(count=builder.journal.count,head_hash=builder.journal.head_hash)
    builder.journal.close()
    pin['sha256']=recovery.file_sha256(parent)
    return scope,parent,pin


def test_pending_input_recovered_once_and_wal_writer_survives_reader(tmp_path):
    scope,parent,pin=interrupted_case(tmp_path)
    builder,receipt=recovery.rehydrate_source(scope,parent,tmp_path/'resumed.sqlite',expected_parent=pin)
    assert builder.chain.next_cursor==2 and builder.journal.count==4
    assert receipt['existing_entries_rewritten']==0 and receipt['pending_input_completed']==1
    assert recovery.file_sha256(parent)==pin['sha256']
    reader=sqlite3.connect(tmp_path/'resumed.sqlite')
    reader.execute('BEGIN')
    cursor=reader.execute('SELECT body FROM entries')
    cursor.fetchone()
    builder.apply(raw(2),source_member_index=0,session_id='s')
    assert builder.journal.count==6
    cursor.close(); reader.rollback(); reader.close()
    builder.journal.close()


def test_failed_tail_is_preserved_and_refused(tmp_path):
    scope,parent,pin=interrupted_case(tmp_path)
    journal=EvidenceJournal(parent)
    journal.append('FAILED',dict(cursor=1,error='retained failure'))
    pin.update(count=journal.count,head_hash=journal.head_hash)
    journal.close(); pin['sha256']=recovery.file_sha256(parent)
    with pytest.raises(ValueError,match='FAILED'):
        recovery.rehydrate_source(scope,parent,tmp_path/'resumed.sqlite',expected_parent=pin)
    assert recovery.file_sha256(parent)==pin['sha256']


def test_changed_parent_pin_refuses_before_replay(tmp_path):
    scope,parent,pin=interrupted_case(tmp_path)
    pin['sha256']='f'*64
    with pytest.raises(ValueError,match='parent'):
        recovery.rehydrate_source(scope,parent,tmp_path/'resumed.sqlite',expected_parent=pin)
    assert not (tmp_path/'resumed.sqlite').exists()


def test_self_consistent_but_wrong_retained_calculation_refuses_rehydration(tmp_path):
    scope,parent,pin=interrupted_case(tmp_path)
    original=EvidenceJournal(parent)
    altered=EvidenceJournal(tmp_path/'altered.sqlite',create=True)
    for entry in original.entries():
        payload=entry['payload']
        if entry['kind']=='APPLIED': payload=dict(payload,rank_after=999)
        altered.append(entry['kind'],payload)
    changed=dict(count=altered.count,head_hash=altered.head_hash)
    altered.close(); original.close()
    changed['sha256']=recovery.file_sha256(tmp_path/'altered.sqlite')
    with pytest.raises(ValueError,match='rehydrated adapter output'):
        recovery.rehydrate_source(scope,tmp_path/'altered.sqlite',tmp_path/'refused.sqlite',expected_parent=changed)
