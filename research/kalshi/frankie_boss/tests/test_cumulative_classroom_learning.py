"""Cumulative learning keeps completion order and truthful market/availability clocks."""
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import pytest
from research.kalshi.frankie_boss import critic_knowledge as knowledge, feedback_cycle as cycle
from research.kalshi.frankie_boss.granite_positive_priming import public_knowledge
from test_feedback_cycle import fixture as cycle_fixture
POLICY = 'cumulative_completed_cycles_v1'

def record(request='prior', available=40):
    return dict(request_id=request, available_ns=available, feedback_hash='a'*64,
        principal_receipt_hash='b'*64, training_checkpoint_hash='c'*64,
        frozen_memory_sha256='d'*64, lessons=[dict(text='Raw learned explanation '+request,
        uncertainty='Unverified hypothesis; preserve its status')])

def nodes(value):
    yield value
    if isinstance(value, dict):
        for child in value.values(): yield from nodes(child)
    elif isinstance(value, (list, tuple)):
        for child in value: yield from nodes(child)

def open_store(directory, policy=None, create=False):
    memory=directory/'memory-a'
    if not memory.exists(): memory.write_bytes(b'frozen')
    return cycle.CycleCoordinator(directory/'cycles.sqlite', lessons_path=directory/'lessons.sqlite',
        frozen_memory_path=memory, frozen_memory_sha256=cycle.file_hash(memory), create=create, learning_policy=policy)

def test_builder_retains_all_prior_learning_in_completion_order():
    ns=1790057801123456789
    rows=[record('z-first',ns+20),record('a-second',ns+10)]
    bundle=knowledge.build_knowledge(rows,cutoff_ns=ns,request_id='next',learning_policy=POLICY)
    assert [e['record'] for e in bundle['entries']]==rows
    assert knowledge.validate_knowledge(bundle)==bundle
    shown=list(nodes(public_knowledge(bundle)))
    assert rows[0]['lessons'][0] in shown and ns+20 in shown
    causal=knowledge.build_knowledge(rows,cutoff_ns=ns,request_id='next')
    assert causal['entries']==[]
    del bundle['learning_policy']
    with pytest.raises(ValueError): knowledge.validate_knowledge(bundle)

def test_rejected_exchange_and_learning_prose_remain_visible_with_status():
    row=record()
    text='Rejected approach remains a lesson, not a success.'
    row['critic_exchange']=dict(schema='FRANKIE_CRITIC_EXCHANGE_V1',status='rejected',verdict='L3',
        request_hash='e'*64,snapshot_hash='f'*64,response_text=text,
        response_hash=hashlib.sha256(text.encode()).hexdigest(),available_ns=40)
    bundle=knowledge.build_knowledge([row],cutoff_ns=1,request_id='next',learning_policy=POLICY)
    shown=list(nodes(public_knowledge(bundle)))
    assert text in shown and 'rejected' in shown and 40 in shown

@pytest.mark.parametrize('bad',[True,'blind',{},1])
def test_unknown_policy_refuses(bad):
    with pytest.raises(ValueError): knowledge.build_knowledge([],cutoff_ns=1,request_id='x',learning_policy=bad)

@pytest.mark.parametrize('first,second',[(POLICY,None),(None,POLICY),(POLICY,'unknown')])
def test_policy_is_owned_durably(tmp_path,first,second):
    store=open_store(tmp_path,first,True); lineage=store._lineage_value();store.close()
    with pytest.raises(ValueError):open_store(tmp_path,second)
    store=open_store(tmp_path,first)
    try:assert store._lineage_value()==lineage
    finally:store.close()

def fixture(tmp_path,monkeypatch):
    ordinary,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch);ordinary.close()
    directory=tmp_path/'cumulative';directory.mkdir()
    store=open_store(directory,POLICY,True);seen=[]
    available={'z-first':40,'a-second':20,'next':30}
    class Controller:
        context_encoding='stacked_v1'
        async def refresh(self,*,request_id,critic_knowledge,**kwargs):
            calls['controller']+=1;seen.append(copy.deepcopy(critic_knowledge))
            return dict(request_id=request_id,request_hash='e'*64,status='complete',records=())
    verify=args['principal'].verify;execute=args['principal'].execute
    args['principal'].verify=lambda envelope,**kw:replace(verify(envelope,**kw),request_id=kw['request_id'],available_ns=available[kw['request_id']])
    args['principal'].execute=lambda request_id,attachment:dict(execute(request_id,attachment),lessons=record(request_id)['lessons'])
    original=args['learner_factory']
    class Learner(original):
        def step(self,**kwargs):return dict(super().step(**kwargs),feedback_hash=kwargs['feedback'].digest)
    args.update(controller_factory=Controller,learner_factory=Learner)
    return store,checkpoint,args,calls,seen

def select(args,name,as_of,cutoff):
    args['request_id']=name
    args['learning_kwargs']=dict(args['learning_kwargs'],as_of=as_of,learning_cutoff_ns=cutoff)

def test_three_completed_cycles_accumulate_despite_reverse_market_clock(tmp_path,monkeypatch):
    store,checkpoint,args,calls,seen=fixture(tmp_path,monkeypatch)
    try:
        for name,as_of,cutoff in [('z-first',10,40),('a-second',5,20)]:
            select(args,name,as_of,cutoff);asyncio.run(store.run(**args))
        frozen=store.critic_knowledge('next',cutoff_ns=1)
        assert [e['record']['request_id'] for e in frozen['entries']]==['z-first','a-second']
        assert [e['record']['available_ns'] for e in frozen['entries']]==[40,20]
        assert [o['as_of'] for o in frozen['origins']]==[10,5]
        assert store.critic_knowledge('next',cutoff_ns=1)==frozen
        select(args,'next',1,30);result=asyncio.run(store.run(**args))
        assert seen[-1]==frozen
        before=dict(calls);state=checkpoint.checkpoint_hash
        assert asyncio.run(store.run(**args))==result
        assert before==calls and state==checkpoint.checkpoint_hash
        with store.db:store.db.execute("DELETE FROM stages WHERE request='z-first' AND stage='complete'")
        with pytest.raises(ValueError):store.critic_knowledge('next',cutoff_ns=1)
    finally:store.close();checkpoint.close()

def test_incomplete_prior_cycle_still_prevents_successor(tmp_path,monkeypatch):
    store,checkpoint,args,calls,seen=fixture(tmp_path,monkeypatch)
    original=store._save
    def crash(request,stage,value):
        if stage=='complete':raise RuntimeError('interrupted completion')
        return original(request,stage,value)
    monkeypatch.setattr(store,'_save',crash)
    try:
        select(args,'z-first',10,40)
        with pytest.raises(RuntimeError):asyncio.run(store.run(**args))
        before=dict(calls);select(args,'a-second',5,20)
        with pytest.raises(ValueError):asyncio.run(store.run(**args))
        assert before==calls
        with pytest.raises(ValueError):store.critic_knowledge('a-second',cutoff_ns=5)
    finally:store.close();checkpoint.close()

def test_policy_change_before_learning_cannot_update_weights(tmp_path,monkeypatch):
    store,checkpoint,args,calls,seen=fixture(tmp_path,monkeypatch)
    original=checkpoint.checkpoint_hash
    def change(phase,**kwargs):
        if phase=='native_learning':store.learning_policy=None
    store.phase_callback=change
    try:
        select(args,'z-first',10,40)
        with pytest.raises(ValueError):asyncio.run(store.run(**args))
        assert calls['learner']==0 and checkpoint.checkpoint_hash==original
    finally:store.close();checkpoint.close()
