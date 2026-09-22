"""Exact recovery from synthetic sealed journals; never production source replay."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from dataclasses import asdict

import pytest
from research.kalshi.frankie_boss import sealed_compact_recovery as recovery
from research.kalshi.frankie_boss.causal_prefix import SourceMember, SourceScope, ScopeKind
from research.kalshi.frankie_boss.c15_journal import pack, unpack, canonical_bytes
from research.kalshi.frankie_boss.c15_registry import implementation_identity
from research.kalshi.frankie_boss.compact_build_journal import conformance_driver_with_compact_journal, CompactBuildJournal
from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook, ADAPTER_REVISION

def declared(counts):
    return SourceScope(kind=ScopeKind.PROBE_ONLY,scope_id='5'*64,
        members=tuple(SourceMember(i,'day-%d.mbo.dbn.zst'%i,chr(97+i)*64,100+i,n) for i,n in enumerate(counts)),
        adapter_revision=ADAPTER_REVISION)

def records():
    cases=[
        (100,'NG',dict(order_id=1,flags=0)),(150,'CL',dict(instrument_id=2,order_id=20)),
        (101,None,dict(order_id=1,action='M',size=9)),(900,None,dict(order_id=2,flags=160)),
        (399,None,dict(action='N',side='N',order_id=0)),(400,None,dict(action='N',side='N',order_id=0)),
        (400.000000001,None,dict(action='R',side='N',order_id=0)),
        (1000,None,dict(instrument_id=2,action='R',side='N',order_id=0,flags=160)),
        (401,'',dict(action='F',order_id=999,size=2)),(402,'NG2',dict(order_id=3,side='B',price=99)),
        (403,None,dict(action='T',side='B',order_id=0)),(1200,None,dict(order_id=4,flags=160)),
        (200,None,dict(instrument_id=2,action='N',side='N',order_id=0)),
    ]
    out=[]
    for i,(seconds,symbol,changes) in enumerate(cases):
        ns=int(seconds*1_000_000_000)
        if i==6:ns=400_000_000_001
        r=dict(instrument_id=1,publisher_id=1,channel_id=1,order_id=1,action='A',side='A',price=101,
            size=10,flags=128,sequence=i,ts_event=ns-1,ts_recv=ns,ts_in_delta=1)
        r.update(changes)
        out.append((r,symbol,0 if i<7 else 1))
    return out

def build(tmp_path, rows=None, counts=(7,6), finish=True):
    rows=records() if rows is None else rows
    scope=declared(counts)
    path=tmp_path/'journal.sqlite'
    driver=conformance_driver_with_compact_journal(scope,path,expected_scope_hash=scope.genesis_hash(),block_rows=3)
    for i,(raw,symbol,member) in enumerate(rows):
        driver.append(raw,cursor=i,source_member_index=member,source_sha256=scope.members[member].sha256,
            session_id='s%d'%member,raw_symbol=symbol,source_dbn_object=scope.members[member].member_key)
    completion=asdict(driver.complete()) if finish else None
    state=driver._builder.export_state() if finish else None
    driver._builder.journal.seal()
    pins=dict(expected_count=driver._builder.journal.count,expected_head_hash=driver._builder.journal.head_hash,
        expected_sha256=recovery.physical_witness(path)['sha256'],expected_bytes=path.stat().st_size,
        code_blobs=implementation_identity()['code_blobs'])
    driver.close()
    return scope,path,pins,state,completion

def forbidden(*args,**kwargs):
    raise AssertionError('recovery attempted source replay or a journal write')

def guards(monkeypatch):
    from research.kalshi.frankie_boss import mbo_source
    monkeypatch.setattr(C15Builder,'apply',forbidden)
    monkeypatch.setattr(InstrumentBook,'apply',forbidden)
    monkeypatch.setattr(CompactBuildJournal,'append',forbidden)
    monkeypatch.setattr(CompactBuildJournal,'seal',forbidden)
    monkeypatch.setattr(mbo_source,'_records',forbidden)
    monkeypatch.setattr(mbo_source,'_decompressed',forbidden)

def test_exact_checkpoint_and_completion_without_replay(tmp_path,monkeypatch):
    scope,path,pins,state,completion=build(tmp_path)
    before=path.read_bytes()
    guards(monkeypatch)
    got=recovery.reconstruct(scope,path,**pins)
    assert canonical_bytes(pack(got['state']))==canonical_bytes(pack(state))
    assert got['completion']==completion
    assert got['source_replays']==got['adapter_apply_calls']==got['parent_writes']==0
    books=got['state']['adapter']['books']
    assert books[0]['raw_symbol']=='NG2' and books[1]['raw_symbol']=='CL'
    assert books[1]['last_recv_ns']==1000_000_000_000 and books[1]['activity_last_now_ns']==200_000_000_000
    assert books[1]['orders']==[]
    assert path.read_bytes()==before

@pytest.mark.parametrize('field,bad', [('expected_count',25),('expected_head_hash','f'*64),
    ('expected_sha256','f'*64),('expected_bytes',1),('code_blobs',{})])
def test_wrong_independent_pin_refuses_without_source_change(tmp_path,field,bad):
    scope,path,pins,_,_=build(tmp_path)
    before=path.read_bytes()
    pins[field]=bad
    with pytest.raises(ValueError):recovery.reconstruct(scope,path,**pins)
    assert path.read_bytes()==before

def test_corrupt_block_refuses_even_with_updated_physical_witness(tmp_path):
    scope,path,pins,_,_=build(tmp_path)
    with sqlite3.connect(path) as db:db.execute("UPDATE blocks SET sha256=? WHERE start=0",('f'*64,))
    before=path.read_bytes()
    pins.update(expected_sha256=hashlib.sha256(before).hexdigest(),expected_bytes=len(before))
    with pytest.raises(ValueError,match='block'):recovery.reconstruct(scope,path,**pins)
    assert path.read_bytes()==before

def test_open_group_and_wrong_session_refuse(tmp_path):
    r,s,m=records()[0]
    scope,path,pins,_,_=build(tmp_path,[(r,s,0)],counts=(1,),finish=False)
    with pytest.raises(ValueError):recovery.reconstruct(scope,path,**pins)
    with pytest.raises(ValueError,match='session'):recovery.reconstruct(scope,path,**pins,expected_session='different')

def test_sidecar_refuses(tmp_path):
    scope,path,pins,_,_=build(tmp_path)
    Path(str(path)+'-wal').write_bytes(b'preserved sidecar')
    with pytest.raises(ValueError,match='sidecar'):recovery.reconstruct(scope,path,**pins)

def test_original_implementation_checkpoint_bytes(tmp_path,monkeypatch):
    root=os.environ.get('RECOVERY_ORIGINAL_ROOT')
    assert root, 'the CI must supply the original pinned checkout'
    source=Path(root).resolve()
    fixture=tmp_path/'fixture.json'
    fixture.write_text(json.dumps(records()))
    script=r'''
import sys,json
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,sys.argv[1])
from research.kalshi.frankie_boss.causal_prefix import SourceMember,SourceScope,ScopeKind
from research.kalshi.frankie_boss.compact_build_journal import conformance_driver_with_compact_journal
from research.kalshi.frankie_boss.c15_journal import canonical_bytes,pack
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import ADAPTER_REVISION
out=Path(sys.argv[2])
scope=SourceScope(kind=ScopeKind.PROBE_ONLY,scope_id='5'*64,
    members=tuple(SourceMember(i,'day-%d.mbo.dbn.zst'%i,chr(97+i)*64,100+i,n) for i,n in enumerate((7,6))),adapter_revision=ADAPTER_REVISION)
d=conformance_driver_with_compact_journal(scope,out/'original.sqlite',expected_scope_hash=scope.genesis_hash(),block_rows=3)
for i,(raw,symbol,member) in enumerate(json.loads((out/'fixture.json').read_bytes())):
 d.append(raw,cursor=i,source_member_index=member,source_sha256=scope.members[member].sha256,session_id='s%d'%member,
          raw_symbol=symbol,source_dbn_object=scope.members[member].member_key)
c=d.complete()
state=d._builder.export_state()
d._builder.journal.seal()
d.close()
(out/'oracle.c15.json').write_bytes(canonical_bytes(pack(state)))
(out/'oracle-completion.json').write_text(json.dumps(asdict(c)))
'''
    subprocess.run([sys.executable,'-c',script,str(source),str(tmp_path)],cwd=source,check=True)
    path=tmp_path/'original.sqlite'
    expected=(tmp_path/'oracle.c15.json').read_bytes()
    state=unpack(json.loads(expected))
    guard=path.read_bytes()
    guards(monkeypatch)
    got=recovery.reconstruct(declared((7,6)),path,expected_sha256=hashlib.sha256(guard).hexdigest(),
        expected_bytes=len(guard),expected_count=26,expected_head_hash=state['journal_hash'],
        code_blobs=recovery.ORIGINAL_CODE_BLOBS)
    assert canonical_bytes(pack(got['state']))==expected
    completion=json.loads((tmp_path/'oracle-completion.json').read_bytes())
    completion['member_counts']=tuple(completion['member_counts'])
    assert got['completion']==completion
    assert path.read_bytes()==guard
