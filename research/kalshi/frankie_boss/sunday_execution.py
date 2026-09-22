"""Operational Sunday cycle composition; host supplies all runtime and critic pins.

This file starts no cloud resource. Calling run_cycle may perform the actual
native/critic request and hand off to Frankie, so production callers must first
complete actual admission and the bounded retained-Pod startup guard.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Callable

from .c15_journal import EvidenceJournal, SCHEMA as JOURNAL_SCHEMA, evidence_hash, canonical_bytes, pack, unpack
from .controller_journal import ControllerJournal, SCHEMA as CONTROLLER_SCHEMA
from .rolling_forecast import RollingForecastBook, SCHEMA as BOOK_SCHEMA
from .feedback_cycle import _exclusive
from .frankie_controller import FrankieForecastController, native_model_pin
from .frankie_principal_adapter import file_witness, digest
from .frankie_dipole_classroom_adapter import DipoleClassroomPrincipalAdapter
from .native_forecast_learning import NativeForecastLearner
from .native_forecast_refresh import NativeForecastRefresh
from .source_contract_runtime import bind_cycle, metadata_for_binding, make_principal_adapter
from .sunday_native_runtime import assemble_request, learning_config


def _plain(value):
    if is_dataclass(value):return _plain(asdict(value))
    if isinstance(value,dict):return {k:_plain(v) for k,v in value.items()}
    if isinstance(value,tuple):return tuple(_plain(v) for v in value)
    if isinstance(value,list):return [_plain(v) for v in value]
    return value


def _adapter_identity(adapter_class):
    if type(adapter_class) is not type or not issubclass(adapter_class, DipoleClassroomPrincipalAdapter):
        raise ValueError('explicit Dipole classroom principal adapter class required')
    return f'{adapter_class.__module__}:{adapter_class.__qualname__}'


def _save(path,body):
    raw=canonical_bytes(pack(body))
    if Path(path).exists():
        if Path(path).read_bytes()!=raw:raise ValueError('retained Sunday execution evidence changed')
        return
    path=Path(path)
    temporary=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    with temporary.open('xb') as handle:
        handle.write(raw);handle.flush();os.fsync(handle.fileno())
    # The driver holds its process-lifetime single-writer lock. A partial file
    # remains diagnostic evidence; only fully fsynced bytes become the record.
    temporary.rename(path)


def _load(path):
    raw=Path(path).read_bytes();body=unpack(json.loads(raw))
    if canonical_bytes(pack(body))!=raw:raise ValueError('noncanonical Sunday execution evidence')
    return body


class JournalWitness:
    """Pin each exact next append BEFORE the actual SQLite commit.

    Restart accepts only the independently recorded before/after head for the
    last attempted append. It cannot adopt an arbitrary self-consistent journal
    or repeat a remote call hidden behind a retained CRITIC_INTENT.
    """
    def __init__(self,path,directory,schema):
        self.path=Path(path);self.directory=Path(directory);self.schema=schema
        self.directory.mkdir(parents=True,exist_ok=True)

    def checkpoint(self):
        initial={'schema':self.schema,'count':0,'head_hash':evidence_hash(dict(schema=JOURNAL_SCHEMA))}
        genesis=self.directory/'genesis.c15.json'
        _save(genesis,initial)
        if not self.path.exists():
            if any(self.directory.glob('append-*.c15.json')):
                raise ValueError('pinned journal disappeared')
            return None
        records=sorted(self.directory.glob('append-*.c15.json'))
        expected=initial
        previous_digest=evidence_hash(initial)
        allowed=[initial]
        for ordinal,path in enumerate(records):
            item=_load(path)
            if (item['before']!=expected or item['previous_expectation_hash']!=previous_digest
                    or item['after']['count']!=expected['count']+1
                    or path.name!=f'append-{ordinal:08d}.c15.json'):
                raise ValueError('append witness chain changed')
            allowed=[item['before'],item['after']]
            expected=item['after'];previous_digest=evidence_hash(item)
        journal=EvidenceJournal(self.path)
        try:
            actual={'schema':self.schema,'count':journal.count,'head_hash':journal.head_hash}
            if actual not in allowed:raise ValueError('journal does not match its precommitted append witness')
            journal.verify(count=actual['count'],head_hash=actual['head_hash'])
            return actual
        finally:journal.close()

    def attach(self,owner):
        journal=owner.journal;original=journal.append
        def append(kind,payload):
            before={'schema':self.schema,'count':journal.count,'head_hash':journal.head_hash}
            envelope=dict(schema=JOURNAL_SCHEMA,ordinal=journal.count,previous_hash=journal.head_hash,kind=kind,payload=payload)
            after={'schema':self.schema,'count':journal.count+1,'head_hash':evidence_hash(envelope)}
            previous_path=self.directory/f'append-{journal.count-1:08d}.c15.json'
            previous=evidence_hash(_load(previous_path)) if journal.count else evidence_hash(_load(self.directory/'genesis.c15.json'))
            witness=dict(before=before,after=after,previous_expectation_hash=previous,
                         kind=kind,payload_hash=evidence_hash(payload))
            _save(self.directory/f'append-{journal.count:08d}.c15.json',witness)
            observed=original(kind,payload)
            if observed!=after['head_hash'] or journal.count!=after['count']:
                raise ValueError('actual append differs from independently recorded intent')
            return observed
        journal.append=append
        return owner

    def open(self,factory):
        checkpoint=self.checkpoint()
        owner=factory(self.path,create=checkpoint is None,checkpoint=checkpoint)
        return self.attach(owner)


@dataclass
class SundayRuntime:
    """Explicitly initialized/restored resources supplied by the authorized host.

    critic_factory is called only inside the coordinator's controller factory.
    It receives no implicit model/key defaults and must construct the real critic
    with its accepted tokenizer/startup guard. input_hash comes from the actual
    prepared/admitted full request. Do not substitute a sampled fixture.
    """
    context: object
    decoder: object
    optimizer: object
    checkpoint: object
    expected_checkpoint_hash: str
    development_identity: dict
    refresh_policy: object
    input_hash: str
    expected_native_hash: str
    expected_critic_config_hash: str
    expected_critic_identity_hash: str
    critic_factory: Callable
    source_journal_path: str
    source_journal_checkpoint: dict
    # Construction stays compatible with pre-classroom callers (harnesses, tests); execution
    # does not: run_cycle refuses a runtime whose package/adapter are not bound to its request.
    classroom_package: dict | None = None
    principal_adapter_class: type | None = None
    context_encoding: str = 'compact_v1'
    context_encoding_options: dict | None = None
    critic_knowledge: dict | None = None
    controller_event: Callable | None = None
    learning_event: Callable | None = None
    release: Callable | None = None


class _LazyPrincipal:
    def __init__(self,configuration,binding,directory,runtime):
        self.configuration=configuration;self.binding=binding;self.directory=directory
        self.runtime=runtime;self.adapter=None;self.handoff=None

    def _get(self):
        if self.adapter is None:
            if self.handoff is None:
                manifest_record=_load(self.directory/'principal-export.c15.json')
                self.handoff=Path(manifest_record['directory'])
            else:manifest_record=_load(self.directory/'principal-export.c15.json')
            self.adapter=make_principal_adapter(binding=self.binding,handoff_directory=self.handoff,
                expected_manifest_sha256=manifest_record['manifest_sha256'],
                boss_journal_path=self.runtime.source_journal_path,
                source_journal_checkpoint=self.runtime.source_journal_checkpoint,
                classroom_package=self.runtime.classroom_package,
                adapter_class=self.runtime.principal_adapter_class,
                directory=self.directory/'principal',**self.configuration)
        return self.adapter

    def prepare(self,handoff_directory):
        self.handoff=Path(handoff_directory)
        _save(self.directory/'principal-export.c15.json',{'directory':str(self.handoff.resolve()),
            'manifest_sha256':file_witness(self.handoff/'manifest.json')['sha256']})
        return self._get().prepare(self.handoff)

    def execute(self,request_id,attachment):return self._get().execute(request_id,attachment)
    def recover(self,request_id,attachment):return self._get().recover(request_id,attachment)
    def verify(self,envelope,**kwargs):return self._get().verify(envelope,**kwargs)


class SundayExecution:
    def __init__(self,*,directory,run_id,coordinator,contract_path,expected_contract_sha256,
                 schedule_path,expected_schedule_sha256,runtime_factory,principal_configuration,
                 boss_commit,agent_commit,state_defects_and_gaps_reported):
        self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)
        self.run_id=run_id;self.coordinator=coordinator;self.contract_path=Path(contract_path)
        self.contract_hash=expected_contract_sha256;self.runtime_factory=runtime_factory
        self.principal_configuration=dict(principal_configuration)
        self.boss_commit=boss_commit;self.agent_commit=agent_commit
        self.defects=tuple(state_defects_and_gaps_reported)
        raw=Path(schedule_path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_schedule_sha256:
            raise ValueError('runtime schedule differs from trusted source receipt')
        schedule=json.loads(raw)
        self.steps=schedule['steps'] if isinstance(schedule,dict) else schedule
        declared_count = schedule.get('step_count', 19) if isinstance(schedule, dict) else 19
        if type(declared_count) is not int or declared_count < 1 or len(self.steps)!=declared_count or any(a['as_of']>=b['as_of'] or a['through_cursor']>=b['through_cursor']
                for a,b in zip(self.steps,self.steps[1:])):
            raise ValueError('complete increasing declared runtime schedule required')
        if isinstance(schedule, dict) and schedule.get('schema') == 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1':
            from .trading_day_schedule import verify
            from .source_contract_runtime import load_contract
            verify(schedule, expected_digest=schedule['schedule_sha256'])
            contract = load_contract(self.contract_path, self.contract_hash)
            if any(contract.get(k) != schedule[k] for k in ('trading_day', 'source_manifest_hash')) or contract.get('cycle_count') != len(self.steps):
                raise ValueError('source contract differs from the trading-day schedule')
            for index, step in enumerate(self.steps):
                bound = bind_cycle(self.contract_path, self.contract_hash, index, step)
                feedback = step['feedback_available_through']
                if (bound['learning_cutoff_ns'] != feedback['as_of'] or
                        bound['learning_through_source_cursor'] != feedback['through_cursor']):
                    raise ValueError('source contract learning boundary differs from the schedule')
        if self.principal_configuration.get('receiver_commit')!=agent_commit:
            raise ValueError('principal receiver differs from pinned exporter lineage')
        _save(self.directory/'execution-identity.c15.json',dict(run_id=run_id,
            contract_sha256=expected_contract_sha256,schedule_sha256=expected_schedule_sha256,
            boss_commit=boss_commit,agent_commit=agent_commit,state_defects=self.defects))
        self._lock=asyncio.Lock()

    def request_id(self,index):return f'{self.run_id}-cycle-{index:02d}'

    async def run_cycle(self,index):
        if type(index) is not int or not 0<=index<len(self.steps):raise ValueError('valid Sunday cycle index required')
        request_id=self.request_id(index)
        async with self._lock:
            with _exclusive(self.directory/'execution.lock'):
                # Deliberately before binding, model loading, teacher work or any factory.
                completed=self.coordinator._load(request_id,'complete')
                if completed is not None:return completed
                if index and self.coordinator._load(self.request_id(index-1),'complete') is None:
                    raise ValueError('complete the preceding Sunday cycle before advancing')
                binding=bind_cycle(self.contract_path,self.contract_hash,index,self.steps[index])
                directory=self.directory/f'cycle-{index:02d}';directory.mkdir(exist_ok=True)
                plan_path=directory/'request-plan.c15.json'
                plan=_load(plan_path) if plan_path.exists() else None
                runtime=self.runtime_factory(binding,directory,plan)
                if not isinstance(runtime,SundayRuntime):raise ValueError('explicit SundayRuntime factory result required')
                if type(runtime.classroom_package) is not dict or runtime.classroom_package.get('binding',{}).get('request_id')!=request_id:
                    raise ValueError('runtime Dipole classroom must be bound to this exact cycle request')
                classroom_binding_hash=runtime.classroom_package['binding'].get('classroom_binding_hash')
                if type(classroom_binding_hash) is not str or len(classroom_binding_hash)!=64:
                    raise ValueError('runtime Dipole classroom binding hash required')
                principal_adapter_identity=_adapter_identity(runtime.principal_adapter_class)
                if runtime.checkpoint.checkpoint_hash!=runtime.expected_checkpoint_hash:
                    raise ValueError('runtime training state differs from trusted checkpoint')
                controller_journal=book=None
                try:
                    controller_journal=JournalWitness(directory/'controller.sqlite',directory/'controller-witnesses',CONTROLLER_SCHEMA).open(ControllerJournal)
                    book=JournalWitness(directory/'native.sqlite',directory/'native-witnesses',BOOK_SCHEMA).open(RollingForecastBook)
                    if plan is None:
                        metadata=metadata_for_binding(binding,state_defects_and_gaps_reported=self.defects)
                        bridge,controller_kwargs=assemble_request(runtime.context,runtime.decoder,book,
                            sessions=binding['sessions'],expected_sessions_hash=binding['expected_sessions_hash'],
                            refresh_policy=runtime.refresh_policy,metadata=metadata,request_id=request_id,
                            as_of=binding['as_of'],source_as_of=binding['source_as_of'],
                            through_cursor=binding['through_cursor'],source_hash=binding['source_hash'],
                            development_identity=runtime.development_identity,optimizer=runtime.optimizer,
                            checkpoint=runtime.checkpoint,expected_checkpoint_hash=runtime.expected_checkpoint_hash)
                        controller_kwargs.pop('request_id')
                        if runtime.critic_knowledge is not None:
                            controller_kwargs['critic_knowledge']=unpack(pack(runtime.critic_knowledge))
                        if native_model_pin(bridge)!=runtime.expected_native_hash:
                            raise ValueError('native controller identity differs from host pin')
                        learner_kwargs={k:binding[k] for k in ('as_of','through_cursor','source_hash','sessions',
                            'expected_sessions_hash','learning_cutoff_ns')}
                        learner_kwargs['input_hash']=runtime.input_hash
                        config=learning_config(runtime.optimizer,binding['sessions'],
                            **{k:binding[k] for k in ('timing_policy_hash','query_policy_hash','split_hash')})
                        plan_controller=_plain(controller_kwargs)
                        if runtime.critic_knowledge is not None:
                            plan_controller['critic_knowledge']=unpack(pack(runtime.critic_knowledge))
                        plan=dict(schema='FRANKIE_SUNDAY_REQUEST_PLAN_V1',request_id=request_id,
                            contract_sha256=self.contract_hash,controller_kwargs=plan_controller,
                            learning_kwargs=_plain(learner_kwargs),learning_config_hash=config.digest,
                            initial_checkpoint_hash=runtime.expected_checkpoint_hash,
                            expected_native_hash=runtime.expected_native_hash,
                            expected_critic_config_hash=runtime.expected_critic_config_hash,
                            expected_critic_identity_hash=runtime.expected_critic_identity_hash,
                            classroom_binding_hash=classroom_binding_hash,
                            principal_adapter_identity=principal_adapter_identity,
                            context_encoding=runtime.context_encoding,input_hash=runtime.input_hash,
                            **({'context_encoding_options':_plain(runtime.context_encoding_options)} if runtime.context_encoding_options is not None else {}),
                            source_journal_checkpoint=runtime.source_journal_checkpoint,
                            source_journal_path=str(Path(runtime.source_journal_path).resolve()))
                        _save(plan_path,plan)
                    else:
                        if plan['request_id']!=request_id or plan['contract_sha256']!=self.contract_hash:
                            raise ValueError('retained request plan identity differs')
                        if (plan['source_journal_checkpoint']!=runtime.source_journal_checkpoint or
                                plan['source_journal_path']!=str(Path(runtime.source_journal_path).resolve()) or
                                plan['input_hash']!=runtime.input_hash or plan['context_encoding']!=runtime.context_encoding or
                                plan.get('context_encoding_options')!=_plain(runtime.context_encoding_options) or
                                pack(plan['controller_kwargs'].get('critic_knowledge'))!=pack(runtime.critic_knowledge) or
                                plan.get('classroom_binding_hash')!=classroom_binding_hash or
                                plan.get('principal_adapter_identity')!=principal_adapter_identity):
                            raise ValueError('retained source/admission/classroom identity differs')
                        if plan['controller_kwargs']['sessions']!=_plain(binding['sessions']):
                            raise ValueError('retained request plan has different authored sessions')
                        controller_kwargs=dict(plan['controller_kwargs'],sessions=binding['sessions'])
                        learner_kwargs=dict(plan['learning_kwargs'],sessions=binding['sessions'])
                        config=learning_config(runtime.optimizer,binding['sessions'],
                            **{k:binding[k] for k in ('timing_policy_hash','query_policy_hash','split_hash')})
                        if config.digest!=plan['learning_config_hash']:
                            raise ValueError('retained learning objective differs')
                        bridge=NativeForecastRefresh(runtime.context,runtime.decoder,book,
                            tuple(target for target,_ in binding['sessions']),runtime.refresh_policy)
                    principal=_LazyPrincipal(self.principal_configuration,binding,directory,runtime)
                    def controller_factory():
                        if runtime.checkpoint.checkpoint_hash!=plan['initial_checkpoint_hash']:
                            raise ValueError('unfinished controller cannot change native training state')
                        critic=runtime.critic_factory()
                        return FrankieForecastController(enabled=True,bridge=bridge,journal=controller_journal,
                            critic=critic,expected_native_hash=plan['expected_native_hash'],
                            expected_critic_config_hash=plan['expected_critic_config_hash'],
                            expected_critic_identity_hash=plan['expected_critic_identity_hash'],
                            context_encoding=plan['context_encoding'],context_encoding_options=plan.get('context_encoding_options'),event=runtime.controller_event)
                    def export_kwargs(result):
                        controller_pin=controller_journal.checkpoint();native_pin=book.checkpoint()
                        _save(directory/'completed-journal-pins.c15.json',dict(controller=controller_pin,
                            native=native_pin,controller_result_hash=evidence_hash(result)))
                        if native_pin!=result['native_checkpoint']:
                            raise ValueError('actual native checkpoint differs from completed controller')
                        return dict(controller_path=directory/'controller.sqlite',native_path=directory/'native.sqlite',
                            controller_checkpoint=controller_pin,native_checkpoint=native_pin,
                            boss_commit=self.boss_commit,agent_commit=self.agent_commit)
                    result=await self.coordinator.run(request_id=request_id,controller_factory=controller_factory,
                        controller_kwargs=controller_kwargs,export_kwargs=export_kwargs,principal=principal,
                        checkpoint=runtime.checkpoint,
                        learner_factory=lambda:NativeForecastLearner(runtime.context,runtime.decoder,runtime.optimizer,config,
                            event=runtime.learning_event),
                        learning_kwargs=learner_kwargs)
                    _save(directory/'completion.c15.json',result)
                    return result
                finally:
                    if book is not None:book.close()
                    if controller_journal is not None:controller_journal.close()
                    if runtime.release is not None:runtime.release()

    async def run_remaining(self, *, cycles=None):
        """Run in order until complete or an actual host principal handoff is pending."""
        if cycles is None: cycles = len(self.steps)
        if type(cycles) is not int or not 1 <= cycles <= len(self.steps):
            raise ValueError('cycles must be an integer from 1 through 19')
        results=[]
        for index in range(cycles):results.append(await self.run_cycle(index))
        return tuple(results)
