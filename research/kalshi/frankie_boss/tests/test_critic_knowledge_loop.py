"""Causal Frankie lessons reach the exact Granite request and require acknowledgment."""
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import pytest
from research.kalshi.frankie_boss import critic_knowledge as knowledge
from research.kalshi.frankie_boss import granite_context as native
from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.granite_context_route import context_route
from test_feedback_cycle import fixture as cycle_fixture
from test_granite_stacked_route_integration import snapshot
from test_granite_parser import valid_output

def record(request_id='prior', available_ns=1):
    return dict(request_id=request_id, available_ns=available_ns, feedback_hash='a'*64,
        principal_receipt_hash='b'*64, training_checkpoint_hash='c'*64,
        lessons=[dict(text='FRANKIE_PRIOR_LESSON_MUST_REACH_GRANITE')], frozen_memory_sha256='d'*64)

def build(records=None, *, cutoff=2, request_id='current'):
    return knowledge.build_knowledge([record()] if records is None else records,
        cutoff_ns=cutoff, request_id=request_id)

def test_canonical_causal_detached_json_stable():
    ns=1790057801123456789
    a=record('a',ns); b=record('b',ns); future=record('future',ns+1)
    a['lessons']=({'text':'tuple canonicalizes','details':(1,2)},)
    rows=[b,future,a]; frozen=copy.deepcopy(rows)
    value=build(rows,cutoff=ns)
    assert rows==frozen
    assert [e['record']['request_id'] for e in value['entries']]==['a','b']
    assert value['entries'][0]['record']['lessons']==[{'text':'tuple canonicalizes','details':[1,2]}]
    assert all(e['lesson_hash']==evidence_hash(e['record']) for e in value['entries'])
    assert build([a,b,future],cutoff=ns)==value
    assert evidence_hash(json.loads(json.dumps(value)))==evidence_hash(value)
    knowledge.validate_knowledge(value,cutoff_ns=ns,request_id='current')
    a['lessons'][0]['text']='changed'
    assert value['entries'][0]['record']['lessons'][0]['text']=='tuple canonicalizes'

def test_empty_explicit():
    value=build([record('future',3)])
    assert value['entries']==[]
    knowledge.validate_knowledge(value,cutoff_ns=2,request_id='current')

@pytest.mark.parametrize('value',[True,1.5,'10',None])
def test_invalid_availability(value):
    item=record(); item['available_ns']=value
    with pytest.raises(ValueError): build([item])

@pytest.mark.parametrize('field',['feedback_hash','principal_receipt_hash','training_checkpoint_hash','frozen_memory_sha256'])
@pytest.mark.parametrize('value',['f'*63,'z'*64,None])
def test_invalid_provenance_even_future(field,value):
    item=record('future',3); item[field]=value
    with pytest.raises(ValueError): build([item])

@pytest.mark.parametrize('rows',[[record('same'),record('same',2)],[record('current')],
    [record('future',3),record('future',4)],[record('current',3)]])
def test_duplicate_and_current_refuse(rows):
    with pytest.raises(ValueError): build(rows)

def test_closed_fields():
    for field in record():
        item=record(); del item[field]
        with pytest.raises(ValueError): build([item])
    item=record(); item['extra']='unattested'
    with pytest.raises(ValueError): build([item])

def test_inner_hash_order_cutoff_and_request():
    original=build([record('a',1),record('b',2)])
    altered=copy.deepcopy(original); altered['entries'][0]['record']['lessons'][0]['text']='tampered'
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    altered=copy.deepcopy(original); altered['entries'].reverse()
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    altered=copy.deepcopy(original); altered['entries'][0]['record']['available_ns']=3
    altered['entries'][0]['lesson_hash']=evidence_hash(altered['entries'][0]['record'])
    with pytest.raises(ValueError): knowledge.validate_knowledge(altered)
    with pytest.raises(ValueError): knowledge.validate_knowledge(original,cutoff_ns=1)
    with pytest.raises(ValueError): knowledge.validate_knowledge(original,request_id='other')

def test_exact_stacked_prompt_and_response_acknowledgment(tmp_path):
    source=snapshot(tmp_path); cutoff=native.unpack(json.loads(source.text)['receipt'])['as_of']
    bundle=build([record('prior',cutoff),record('future',cutoff+1)],cutoff=cutoff)
    route=context_route('stacked_v1'); encoded=route.encode(source,knowledge=bundle)
    assert route.native(encoded).text==source.text
    prompt=route.build_prompt(encoded).text
    assert 'FRANKIE_PRIOR_LESSON_MUST_REACH_GRANITE' in prompt
    assert '"request_id":"future"' not in prompt
    value=valid_output(encoded)
    value['evidence_refs']=[{'row':0,'field':'/record/extension/odd~1key/1'}]
    assert route.score(json.dumps(value),encoded)[1].name!='L4'
    value.update(knowledge_hash=evidence_hash(bundle),knowledge_review=[
        dict(lesson_hash=e['lesson_hash'],assessment='Considered as prior inference, not raw evidence')
        for e in bundle['entries']])
    assert route.score(json.dumps(value),encoded)[1].name=='L4'
    value['knowledge_hash']='f'*64
    assert route.score(json.dumps(value),encoded)[1].name!='L4'
    value['knowledge_hash']=evidence_hash(bundle);value['knowledge_review']=[]
    assert route.score(json.dumps(value),encoded)[1].name!='L4'

def test_outer_hash_cannot_hide_knowledge_tamper(tmp_path):
    source=snapshot(tmp_path); cutoff=native.unpack(json.loads(source.text)['receipt'])['as_of']
    route=context_route('stacked_v1')
    encoded=route.encode(source,knowledge=build(cutoff=cutoff))
    body=json.loads(encoded.text);body['knowledge']['entries'][0]['record']['lessons'][0]['text']='tampered'
    text=native._text(body)
    with pytest.raises(ValueError): route.parse(text,expected_hash=hashlib.sha256(text.encode()).hexdigest())

def test_two_cycles_freeze_prior_lessons(tmp_path,monkeypatch):
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    seen=[]
    class Controller:
        context_encoding='stacked_v1'
        async def refresh(self,*,request_id,critic_knowledge,**kwargs):
            assert store._load(request_id,'critic_knowledge')==critic_knowledge
            knowledge.validate_knowledge(critic_knowledge,request_id=request_id)
            seen.append(copy.deepcopy(critic_knowledge)); calls['controller']+=1
            return dict(request_id=request_id,request_hash='e'*64,status='complete',records=())
    args['controller_factory']=Controller
    original_verify=args['principal'].verify
    def verify(envelope,**kwargs):
        return replace(original_verify(envelope,**kwargs),request_id=kwargs['request_id'],
            available_ns=20 if kwargs['request_id']=='sun' else 30)
    args['principal'].verify=verify
    original_execute=args['principal'].execute
    def execute(request_id,attachment):
        return dict(original_execute(request_id,attachment),lessons=[dict(text='verified lesson from '+request_id)])
    args['principal'].execute=execute
    original_learner=args['learner_factory']
    class Learner(original_learner):
        def step(self,**kwargs):
            return dict(super().step(**kwargs),feedback_hash=kwargs['feedback'].digest)
    args['learner_factory']=Learner
    try:
        first=asyncio.run(store.run(**args))
        assert seen[0]['entries']==[]
        previous=store.lessons_available(20)
        args['request_id']='mon'
        args['learning_kwargs']=dict(args['learning_kwargs'],as_of=20,through_cursor=3,learning_cutoff_ns=30)
        frozen=store.critic_knowledge('mon',cutoff_ns=20)
        assert frozen['entries']==build(previous,cutoff=20,request_id='mon')['entries']
        assert frozen['origins'][0]['source_hash']==args['learning_kwargs']['source_hash']
        assert store.critic_knowledge('mon',cutoff_ns=20)==frozen
        with pytest.raises(ValueError):store.critic_knowledge('mon',cutoff_ns=21)
        args['controller_kwargs']=dict(critic_knowledge=copy.deepcopy(frozen))
        second=asyncio.run(store.run(**args))
        assert seen[1]==frozen
        assert seen[1]['entries'][0]['record']['lessons']==[{'text':'verified lesson from sun'}]
        assert [r['request_id'] for r in store.lessons_available(30)]==['sun','mon']
        assert second['training']['checkpoint_hash']!=first['training']['checkpoint_hash']
        assert (tmp_path/'memory-a').read_bytes()==b'frozen'
    finally: store.close();checkpoint.close()

def test_sql_availability_cannot_hide_future_payload(tmp_path,monkeypatch):
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    try:
        asyncio.run(store.run(**args))
        with store.lessons:
            store.lessons.execute('UPDATE lessons SET available_ns=0')
        with pytest.raises(ValueError,match='availability'):
            store.lessons_available(10)
    finally: store.close();checkpoint.close()

def test_missing_origin_refuses_and_retry_rechecks_origin(tmp_path,monkeypatch):
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    try:
        asyncio.run(store.run(**args))
        store.critic_knowledge('next',20)
        with store.db:
            store.db.execute("DELETE FROM stages WHERE request='sun' AND stage='complete'")
        with pytest.raises(ValueError,match='origin'):
            store.critic_knowledge('next',20)
    finally: store.close();checkpoint.close()

def test_preflight_includes_identical_knowledge_hash(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from research.kalshi.frankie_boss import sunday_native_runtime as runtime
    source=snapshot(tmp_path)
    info=native.unpack(json.loads(source.text)['receipt'])
    cutoff=info['as_of'];info.pop('input_hash');info.pop('model_hash')
    context=SimpleNamespace(_prepare=lambda *a:({},info,'a'*64,None,[]),
        _model_hash=lambda:'d'*64,qsv=None,teacher=None,builder=None,entity=(1,1),
        model=SimpleNamespace(trunk=SimpleNamespace(registry=None)))
    monkeypatch.setattr(runtime,'journal_prefix',lambda *a:[])
    monkeypatch.setattr(runtime,'map_native_context',lambda **kw:source)
    bundle=build(cutoff=cutoff)
    body,receipt=runtime.prepare_critic_request(context,as_of=cutoff,through_cursor=0,
        source_as_of=1,context_encoding='stacked_v1',critic_knowledge=bundle)
    route=context_route('stacked_v1')
    assert json.loads(body)['messages'][0]['content']==route.build_prompt(route.encode(source,knowledge=bundle)).text
    assert receipt['critic_knowledge_hash']==evidence_hash(bundle)

@pytest.mark.parametrize('bad',[[],{},None,True,''])
def test_malformed_acknowledgment_is_rejected(bad):
    bundle=build()
    reply=dict(knowledge_hash=evidence_hash(bundle),knowledge_review=[dict(lesson_hash=bad,assessment='review')])
    assert knowledge.acknowledged(reply,bundle) is False

def test_canonical_full_envelope_hash_survives_sorted_json():
    bundle=build()
    assert evidence_hash(bundle)==evidence_hash(json.loads(json.dumps(bundle,sort_keys=True)))

@pytest.mark.parametrize('tamper',[False,True])
def test_request_plan_preserves_arrays_on_resume(tmp_path,monkeypatch,tamper):
    from test_sunday_execution import _composition_fixture
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
    module,Pending,driver,calls=_composition_fixture(tmp_path,monkeypatch,
        adapter_class=IntegratedDipoleClassroomPrincipalAdapter)
    runtime=driver.runtime_factory(None,None,None)
    runtime.context_encoding='stacked_v1'
    monkeypatch.setattr(module,'NativeForecastRefresh',lambda *a,**kw:object())
    bundle=build([record('prior',99)],cutoff=100,request_id='request-cycle-00')
    runtime.critic_knowledge=copy.deepcopy(bundle)
    with pytest.raises(Pending): asyncio.run(driver.run_cycle(0))
    path=tmp_path/'run/cycle-00/request-plan.c15.json'
    saved=module._load(path)['controller_kwargs']['critic_knowledge']
    assert saved==bundle and evidence_hash(saved)==evidence_hash(bundle)
    assert type(saved['entries']) is list
    calls.clear()
    if tamper:
        runtime.critic_knowledge['entries'][0]['record']['lessons'][0]['text']='changed'
        with pytest.raises(ValueError): asyncio.run(driver.run_cycle(0))
        assert calls==[]
    else:
        with pytest.raises(Pending): asyncio.run(driver.run_cycle(0))
        assert calls==['coordinator-after-plan']

def test_prepared_body_cannot_lie_about_knowledge(tmp_path):
    source=snapshot(tmp_path); cutoff=native.unpack(json.loads(source.text)['receipt'])['as_of']
    route=context_route('stacked_v1');bundle=build(cutoff=cutoff)
    body=json.dumps(dict(messages=[dict(role='user',content=route.build_prompt(route.encode(source,knowledge=bundle)).text)]))
    knowledge.verify_prepared_knowledge(body,bundle)
    altered=build([dict(record(),lessons=[dict(text='other knowledge')])],cutoff=cutoff)
    with pytest.raises(ValueError):
        knowledge.verify_prepared_knowledge(body,altered)

def test_legacy_lesson_retry_does_not_rewrite_history(tmp_path,monkeypatch):
    from research.kalshi.frankie_boss.c15_journal import canonical_bytes,pack
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    original_save=store._save; original_lessons=store._save_lessons
    class Controller:
        async def refresh(self,**kw):
            calls['controller']+=1
            return dict(request_id='sun',request_hash='e'*64,status='complete',records=(),critic={})
    args['controller_factory']=Controller
    def legacy_lessons(request_id,feedback,envelope,training):
        record=dict(request_id=request_id,available_ns=feedback.available_ns,
            feedback_hash=feedback.digest,principal_receipt_hash=feedback.principal_receipt_hash,
            training_checkpoint_hash=training['checkpoint_hash'],lessons=envelope['lessons'],
            frozen_memory_sha256=store.memory_hash)
        digest=evidence_hash(record)
        with store.lessons:
            store.lessons.execute('INSERT INTO lessons VALUES (?,?,?,?)',
                (request_id,feedback.available_ns,canonical_bytes(pack(record)),digest))
        return dict(lessons_hash=digest,available_ns=feedback.available_ns)
    def crash(request_id,stage,value):
        if stage=='complete':raise RuntimeError('crash after lesson commit')
        return original_save(request_id,stage,value)
    monkeypatch.setattr(store,'_save',crash)
    monkeypatch.setattr(store,'_save_lessons',legacy_lessons)
    try:
        with pytest.raises(RuntimeError):asyncio.run(store.run(**args))
        old=store.lessons.execute('SELECT payload,digest FROM lessons').fetchone()
        monkeypatch.setattr(store,'_save',original_save)
        monkeypatch.setattr(store,'_save_lessons',original_lessons)
        monkeypatch.setattr(knowledge,'critic_exchange',lambda *a,**kw:dict(diagnostic='new optional exchange'))
        asyncio.run(store.run(**args))
        assert store.lessons.execute('SELECT payload,digest FROM lessons').fetchone()==old
        assert calls['learner']==calls['principal']==calls['controller']==1
    finally:store.close();checkpoint.close()

class KnowledgeCritic:
    enabled=True
    config_hash='c'*64
    request_timeout=1.0
    def __init__(self,acknowledge):
        from test_frankie_controller import Critic
        route=context_route('stacked_v1')
        self.identity=replace(Critic().identity,
            system_prompt_hash=hashlib.sha256(route.system_text.encode()).hexdigest(),
            parser_code_hash=route.parser_code_hash())
        self.acknowledge=acknowledge;self.calls=0;self.sent=[]
    async def critique_stacked(self,snapshot,*,request_id):
        from research.kalshi.frankie_boss.granite_context_route import serve_context
        from research.kalshi.frankie_boss.granite_shadow import ShadowResponse
        from research.kalshi.frankie_boss.granite_bedrock import BedrockReceipt
        self.calls+=1
        async def transport(request):
            self.sent.append(request)
            value=valid_output(snapshot);value['evidence_refs']=[{'row':0,'field':'/record/price'}]
            bundle=json.loads(snapshot.text)['knowledge']
            if self.acknowledge:
                value.update(knowledge_hash=evidence_hash(bundle),knowledge_review=[
                    dict(lesson_hash=e['lesson_hash'],assessment='Retain prior uncertainty')
                    for e in bundle['entries']])
            return ShadowResponse(request.request_hash,request.identity.identity_hash,json.dumps(value))
        shadow=await serve_context(snapshot,self.identity,context_encoding='stacked_v1',
            request_id=request_id,timeout_seconds=self.request_timeout,transport=transport)
        call_hash=hashlib.sha256(json.dumps(dict(config_hash=self.config_hash,
            request_hash=shadow.request.request_hash),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return BedrockReceipt(shadow,self.config_hash,call_hash,None,None)

@pytest.mark.parametrize('acknowledge',[True,False])
def test_real_controller_exchange_and_exact_replay(tmp_path,monkeypatch,acknowledge):
    from test_frankie_controller import build_controller
    from research.kalshi.frankie_boss.frankie_controller import FrankieForecastController,native_model_pin
    from research.kalshi.frankie_boss.controller_journal import ControllerJournal
    base,bridge,_,request=build_controller(tmp_path);base.journal.close()
    critic=KnowledgeCritic(acknowledge)
    journal=ControllerJournal(tmp_path/'stacked-controller.sqlite',create=True)
    bundle=build([record('prior',1)],cutoff=request['as_of'],request_id=request['request_id'])
    request=dict(request,critic_knowledge=bundle)
    def controller(journal):
        return FrankieForecastController(enabled=True,bridge=bridge,journal=journal,critic=critic,
            context_encoding='stacked_v1',expected_native_hash=native_model_pin(bridge),
            expected_critic_config_hash=critic.config_hash,expected_critic_identity_hash=critic.identity.identity_hash)
    active=controller(journal)
    try:
        result=asyncio.run(active.refresh(**request))
        assert result['status']==('complete' if acknowledge else 'incomplete')
        assert critic.calls==1 and len(result['records'])==3
        sent=critic.sent[0];parsed=json.loads(sent.snapshot_text)['knowledge']
        assert parsed==bundle and evidence_hash(parsed)==evidence_hash(bundle)
        state=journal.state(request['request_id'])
        assert state['intent']['request']['critic_knowledge']==bundle
        assert state['critic_intent']['prompt_text']==sent.prompt_text
        exchange=knowledge.critic_exchange(result,available_ns=3)
        assert exchange['status']==('accepted' if acknowledge else 'rejected')
        assert exchange['response_text']==result['critic']['receipt']['shadow']['response']['text']
        assert exchange['request_hash']==sent.request_hash
        previous=record(request['request_id'],3);previous['critic_exchange']=exchange
        carried=build([previous],cutoff=3,request_id='next')
        assert carried['entries'][0]['record']['critic_exchange']==exchange
        # A foreign response remains in the original receipt, never reusable knowledge.
        foreign=copy.deepcopy(result);shadow=foreign['critic']['receipt']['shadow']
        shadow['status']='binding_mismatch';shadow['response']['request_hash']='f'*64
        mismatch=knowledge.critic_exchange(foreign,available_ns=3)
        assert mismatch['status']=='binding_mismatch' and mismatch['response_text'] is None
        timeout=copy.deepcopy(result);timeout['critic']['receipt']['shadow'].update(status='timeout',response=None,verdict=None)
        assert knowledge.critic_exchange(timeout,available_ns=3)['response_hash'] is None
        witness=journal.checkpoint();journal.close()
        journal=ControllerJournal(tmp_path/'stacked-controller.sqlite',checkpoint=witness);active=controller(journal)
        monkeypatch.setattr(bridge.context.model,'forward_decision',lambda **kw:pytest.fail('second forward'))
        assert asyncio.run(active.refresh(**request))==result and critic.calls==1
        changed=build([dict(record('prior',1),lessons=[dict(text='changed')])],
            cutoff=request['as_of'],request_id=request['request_id'])
        with pytest.raises(ValueError):asyncio.run(active.refresh(**dict(request,critic_knowledge=changed)))
        assert critic.calls==1
    finally:journal.close();bridge.book.close()
