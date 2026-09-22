"""Recover one synthetic retained tuple; no native forward or real source reads."""
import hashlib,json
import pytest
from research.kalshi.frankie_boss import retained_preparation_recovery as recovery
from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.kalshi.frankie_boss.c15_journal import canonical_bytes,pack
from research.kalshi.frankie_boss.causal_prefix import SourceScope,SourceMember,ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from research.kalshi.frankie_boss.sunday_native_runtime import initialize,prepare_critic_request
from research.kalshi.frankie_boss.prepared_context_cache import same_preparation


def test_teacher_only_recovery_matches_entire_retained_tuple(tmp_path,monkeypatch):
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'synthetic','b'*64,100,3),),SUPPORTED_ADAPTER_REVISION)
    builder=C15Builder(scope,tmp_path/'prefix.sqlite')
    for i in range(3):
        builder.apply(dict(instrument_id=111313,publisher_id=1,channel_id=1,order_id=i+1,action='A',side='A',price=1000000000+i*1000000,size=10,flags=128,sequence=i,ts_event=i*100+1,ts_recv=i*100+2,ts_in_delta=1),source_member_index=0,session_id='s')
    context,_,_,initial=initialize(builder,context_rows=8)
    monkeypatch.setattr(context.model,'forward',lambda *a,**k:pytest.fail('native forward forbidden'))
    expected=context._prepare(202,2)
    monkeypatch.setattr(context,'_prepare',lambda *a,**k:expected)
    body,prepared=prepare_critic_request(context,as_of=202,through_cursor=2,source_as_of=201)
    def pin(name,raw):
        p=tmp_path/name;p.write_bytes(raw);return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest())
    witness=dict(schema='RETAINED_FIRST_PREPARATION_RECOVERY_V1',request=pin('request.json',body),prepared=pin('prepared.json',json.dumps(prepared).encode()),initialization=pin('initial.c15.json',canonical_bytes(pack(initial))),prefix=dict(path=str(builder.journal.path),sha256=hashlib.sha256(builder.journal.path.read_bytes()).hexdigest(),count=builder.journal.count,head_hash=builder.journal.head_hash))
    monkeypatch.setattr(context,'_prepare',lambda *a,**k:pytest.fail('full preparation forbidden'))
    seen=[];original=recovery.VerifiedJournalReader.entries
    def entries(reader):
        for entry in original(reader):seen.append(entry['ordinal']);yield entry
    monkeypatch.setattr(recovery.VerifiedJournalReader,'entries',entries)
    actual=recovery.recover_retained_preparation(context,witness,as_of=202,through_cursor=2)
    assert same_preparation(expected,actual)
    assert seen==list(range(6))
    builder.journal.close()


@pytest.mark.parametrize('failed,next_cursor',[(True,3),(False,4)])
def test_incompatible_prefix_view_refused_before_artifact_reads(failed,next_cursor):
    from types import SimpleNamespace
    context=SimpleNamespace(builder=SimpleNamespace(_failed=failed,chain=SimpleNamespace(next_cursor=next_cursor)))
    witness=dict(schema='RETAINED_FIRST_PREPARATION_RECOVERY_V1',request={},prepared={},initialization={},prefix={})
    with pytest.raises(ValueError,match='healthy exact retained prefix'):
        recovery.recover_retained_preparation(context,witness,as_of=202,through_cursor=2)

@pytest.fixture
def retained_guard_case(tmp_path,monkeypatch):
    scope=SourceScope(ScopeKind.RESULT_BEARING,'c'*64,(SourceMember(0,'guard-synthetic','d'*64,100,1),),SUPPORTED_ADAPTER_REVISION)
    builder=C15Builder(scope,tmp_path/'guard-prefix.sqlite')
    builder.apply(dict(instrument_id=111313,publisher_id=1,channel_id=1,order_id=1,action='A',side='A',price=1000000000,size=10,flags=128,sequence=1,ts_event=101,ts_recv=102,ts_in_delta=1),source_member_index=0,session_id='guard')
    context,_,_,initial=initialize(builder,context_rows=8)
    monkeypatch.setattr(context.model,'forward',lambda *a,**k:pytest.fail('native forward forbidden'))
    prepared_tuple=context._prepare(102,0)
    monkeypatch.setattr(context,'_prepare',lambda *a,**k:prepared_tuple)
    body,prepared=prepare_critic_request(context,as_of=102,through_cursor=0,source_as_of=101)
    def pin(name,raw):
        p=tmp_path/name;p.write_bytes(raw);return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest())
    witness=dict(schema='RETAINED_FIRST_PREPARATION_RECOVERY_V1',request=pin('request.json',body),prepared=pin('prepared.json',json.dumps(prepared).encode()),initialization=pin('initial.c15.json',canonical_bytes(pack(initial))),prefix=dict(path=str(builder.journal.path),sha256=hashlib.sha256(builder.journal.path.read_bytes()).hexdigest(),count=builder.journal.count,head_hash=builder.journal.head_hash))
    monkeypatch.setattr(context,'_prepare',lambda *a,**k:pytest.fail('full preparation forbidden'))
    monkeypatch.setattr(recovery,'VerifiedJournalReader',lambda *a,**k:pytest.fail('invalid identity must not open verified teacher reader'))
    yield context,witness
    builder.journal.close()


@pytest.mark.parametrize('defect,message',[
    ('registry','exact complete first-prefix'),
    ('wal','retained prefix must be closed'),
    ('handle','context journal handle differs'),
])
def test_registry_wal_and_handle_fail_before_teacher_scan(retained_guard_case,monkeypatch,defect,message):
    from pathlib import Path
    from types import SimpleNamespace
    context,witness=retained_guard_case
    if defect=='registry':
        monkeypatch.setattr(context,'model',SimpleNamespace(trunk=SimpleNamespace(registry=SimpleNamespace(digest='f'*64))))
        initial=recovery.unpack(json.loads(Path(witness['initialization']['path']).read_bytes()))
        monkeypatch.setattr(context,'_model_hash',lambda:initial['native_hash'])
    elif defect=='wal':
        Path(witness['prefix']['path']+'-wal').write_bytes(b'not-closed')
    else:
        monkeypatch.setattr(context.builder.journal,'head_hash','f'*64)
    with pytest.raises(ValueError,match=message):
        recovery.recover_retained_preparation(context,witness,as_of=102,through_cursor=0)
