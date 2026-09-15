"""New closed-source schedule view checks; synthetic journals only."""
import hashlib
from dataclasses import asdict

import pytest

from research.kalshi.frankie_boss import completed_schedule_view as views
from research.kalshi.frankie_boss.causal_prefix import SourceScope,SourceMember,ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from research.kalshi.frankie_boss.c15_journal import canonical_bytes,pack,EvidenceJournal,evidence_hash
from research.kalshi.frankie_boss.source_conformance import SourceConformanceDriver
from research.kalshi.frankie_boss.context_session import journal_prefix


def closed_source(tmp_path):
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'synthetic','b'*64,100,2),),SUPPORTED_ADAPTER_REVISION)
    driver=SourceConformanceDriver(scope,tmp_path/'source.sqlite',expected_scope_hash=scope.genesis_hash())
    for i in range(2):
        row=dict(instrument_id=1,publisher_id=1,channel_id=1,order_id=i+1,action='A',side='A',price=100+i,
            size=10,flags=128,sequence=i,ts_event=i*100+1,ts_recv=i*100+2,ts_in_delta=1)
        driver.append(row,cursor=i,source_member_index=0,source_sha256='b'*64,session_id='s')
    completion=asdict(driver.complete());state=driver.checkpoint();driver.close()
    path=tmp_path/'state.c15.json';path.write_bytes(canonical_bytes(pack(state)))
    args=dict(scope=scope,journal_path=tmp_path/'source.sqlite',state_path=path,
        expected_state_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),expected_state_hash=state['state_hash'],completion=completion)
    return args,state


def test_bound_closed_view_consumes_every_pair_once_and_attests_tail(tmp_path):
    args,state=closed_source(tmp_path)
    view=views.open_completed_schedule_view(**args)
    rows=list(journal_prefix(view,1))
    assert len(rows)==2 and view.journal.verified_records==2
    assert view.journal.verified_terminal_prefix==state['prefix']['prefix_hash']
    assert view.evidence_class=='READ_ONLY_COMPLETED_SOURCE_SCHEDULE_VIEW'
    view.journal.close()


@pytest.mark.parametrize('field,value',[('builder_state_hash','f'*64),('source_prefix_hash','e'*64),('record_count',1),('journal_count',2)])
def test_independent_completion_identity_must_match_state(tmp_path,field,value):
    args,state=closed_source(tmp_path)
    args['completion']=dict(args['completion'],**{field:value})
    with pytest.raises(ValueError,match='completion'):
        views.open_completed_schedule_view(**args)


def test_changed_state_bytes_refused_before_reader(tmp_path):
    args,state=closed_source(tmp_path)
    args['state_path'].write_bytes(args['state_path'].read_bytes()+b' ')
    with pytest.raises(ValueError,match='state bytes'):
        views.open_completed_schedule_view(**args)


def test_wrong_terminal_row_refused_even_with_self_consistent_chain(tmp_path):
    args,state=closed_source(tmp_path)
    old=EvidenceJournal(args['journal_path']);newpath=tmp_path/'changed.sqlite';new=EvidenceJournal(newpath,create=True)
    for entry in old.entries():
        payload=entry['payload']
        if entry['ordinal']==3:payload=dict(payload,terminal_prefix_hash='f'*64)
        new.append(entry['kind'],payload)
    state['journal_hash']=new.head_hash
    state['state_hash']=evidence_hash({k:v for k,v in state.items() if k!='state_hash'})
    args['completion']=dict(args['completion'],journal_hash=new.head_hash,builder_state_hash=state['state_hash'])
    new.close();old.close()
    args['state_path'].write_bytes(canonical_bytes(pack(state)))
    args.update(journal_path=newpath,expected_state_hash=state['state_hash'],expected_state_sha256=hashlib.sha256(args['state_path'].read_bytes()).hexdigest())
    view=views.open_completed_schedule_view(**args)
    with pytest.raises(ValueError,match='terminal'):
        list(journal_prefix(view,1))
    view.journal.close()


def test_pair_kind_mismatch_refused_in_verified_stream(tmp_path):
    args,state=closed_source(tmp_path)
    view=views.open_completed_schedule_view(**args)
    original=view.journal.reader.entries
    def wrong_kind():
        for entry in original():
            if entry['ordinal']==1:entry=dict(entry,kind='FAILED')
            yield entry
    view.journal.reader.entries=wrong_kind
    with pytest.raises(ValueError,match='pair mismatch'):
        list(view.journal.entries())
    assert view.journal.verified_records is None
    view.journal.close()


def test_self_consistent_partial_source_cannot_claim_completion(tmp_path):
    from research.kalshi.frankie_boss.c15_builder import C15Builder
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'partial','b'*64,100,3),),SUPPORTED_ADAPTER_REVISION)
    path=tmp_path/'partial.sqlite';builder=C15Builder(scope,path)
    for i in range(2):
        builder.apply(dict(instrument_id=1,publisher_id=1,channel_id=1,order_id=i+1,action='A',side='A',price=100+i,size=10,flags=128,sequence=i,ts_event=i*100+1,ts_recv=i*100+2,ts_in_delta=1),source_member_index=0,session_id='s')
    state=builder.export_state();builder.journal.close()
    state_path=tmp_path/'partial.c15.json';state_path.write_bytes(canonical_bytes(pack(state)))
    completion=dict(schema='BOSS_SOURCE_CONFORMANCE_V1',builder_state_hash=state['state_hash'],scope_kind=scope.kind.value,scope_hash=scope.genesis_hash(),record_count=2,member_counts=(3,),group_count=2,source_prefix_hash=state['prefix']['prefix_hash'],journal_count=4,journal_hash=state['journal_hash'])
    with pytest.raises(ValueError,match='incomplete source'):
        views.open_completed_schedule_view(scope,path,state_path,hashlib.sha256(state_path.read_bytes()).hexdigest(),state['state_hash'],completion)
