"""The optimized recovery seam consumes a closed parent exactly once."""
from research.kalshi.frankie_boss import source_recovery as recovery
from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.causal_prefix import SourceScope,SourceMember,ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION


def test_closed_completed_tail_single_verified_pass_then_new_append(tmp_path,monkeypatch):
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'x','b'*64,100,4),),SUPPORTED_ADAPTER_REVISION)
    parent=tmp_path/'parent.sqlite';builder=C15Builder(scope,parent)
    def raw(i):return dict(instrument_id=1,publisher_id=1,channel_id=1,order_id=i+1,action='A',side='A',price=100+i,size=10,flags=128,sequence=i,ts_event=i*100+1,ts_recv=i*100+2,ts_in_delta=1)
    for i in range(3):builder.apply(raw(i),source_member_index=0,session_id='s')
    pin=dict(count=builder.journal.count,head_hash=builder.journal.head_hash)
    builder.journal.close();pin['sha256']=recovery.file_sha256(parent)
    original=recovery.VerifiedJournalReader.entries;seen=[]
    def observe(self):
        for entry in original(self):seen.append(entry['ordinal']);yield entry
    monkeypatch.setattr(recovery.VerifiedJournalReader,'entries',observe)
    def forbidden(*args):raise AssertionError('duplicate legacy journal scan')
    monkeypatch.setattr(EvidenceJournal,'entries',forbidden)
    resumed,receipt=recovery.rehydrate_source(scope,parent,tmp_path/'resumed.sqlite',expected_parent=pin)
    assert seen==list(range(6)) and receipt['pending_input_completed']==0
    resumed.apply(raw(3),source_member_index=0,session_id='s')
    assert resumed.chain.next_cursor==4 and resumed.journal.count==8
    resumed.journal.close()
    assert recovery.file_sha256(parent)==pin['sha256']
