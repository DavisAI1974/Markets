"""New execution/restart seams without a model, cloud call, or Sunday replay."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from research.kalshi.frankie_boss.sunday_execution import JournalWitness, SundayExecution
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.frankie_principal_adapter import canonical, digest


def test_two_cycle_batch_stops_then_full_resume_preserves_order():
    execution = object.__new__(SundayExecution)
    execution.steps = tuple(range(19))  # Explicit fixture schedule, not a runtime default.
    completed = {}
    fresh = []

    async def run_cycle(index):
        if index not in completed:
            fresh.append(index)
            completed[index] = {'cycle_index': index}
        return completed[index]

    execution.run_cycle = run_cycle
    first = asyncio.run(execution.run_remaining(cycles=2))
    assert fresh == [0, 1] and len(first) == 2
    full = asyncio.run(execution.run_remaining())
    assert fresh == list(range(19)) and len(full) == 19
    assert full[:2] == first


@pytest.mark.parametrize('cycles', [0, 20, -1, True, 1.5])
def test_invalid_cycle_batch_refuses_before_runtime(cycles):
    execution = object.__new__(SundayExecution)
    execution.steps = tuple(range(19))  # Explicit fixture schedule, not a runtime default.
    execution.run_cycle = lambda index: pytest.fail('invalid batch reached runtime')
    with pytest.raises(ValueError, match='cycles'):
        asyncio.run(execution.run_remaining(cycles=cycles))


def test_append_witness_recovers_both_not_committed_and_committed_states(tmp_path):
    path=tmp_path/'journal.sqlite';witness=JournalWitness(path,tmp_path/'witnesses','test-owner')
    assert witness.checkpoint() is None
    journal=EvidenceJournal(path,create=True)
    def crash(kind,payload):raise RuntimeError('before journal commit')
    journal.append=crash
    witness.attach(SimpleNamespace(journal=journal))
    with pytest.raises(RuntimeError,match='before journal commit'):
        journal.append('record',{'full':'payload'})
    journal.close()
    checkpoint=witness.checkpoint()
    assert checkpoint['count']==0
    journal=EvidenceJournal(path)
    witness.attach(SimpleNamespace(journal=journal))
    journal.append('record',{'full':'payload'})
    journal.close()
    assert witness.checkpoint()['count']==1


def test_append_witness_rejects_unwitnessed_valid_journal_suffix(tmp_path):
    path=tmp_path/'journal.sqlite';witness=JournalWitness(path,tmp_path/'witnesses','test-owner')
    witness.checkpoint()
    journal=EvidenceJournal(path,create=True)
    journal.append('unwitnessed',{'otherwise':'valid'})
    journal.close()
    with pytest.raises(ValueError,match='precommitted append witness'):
        witness.checkpoint()


def test_completed_cycle_precedes_contract_binding_and_runtime_factory(tmp_path):
    schedule=[{'through_cursor':i,'as_of':i+10} for i in range(19)]
    path=tmp_path/'schedule.json';path.write_bytes(canonical(schedule))
    completed={'saved':'completion'}
    coordinator=SimpleNamespace(_load=lambda request,stage:completed if stage=='complete' else None)
    execution=SundayExecution(directory=tmp_path/'run',run_id='actual',coordinator=coordinator,
        contract_path=tmp_path/'intentionally-not-needed.json',expected_contract_sha256='a'*64,
        schedule_path=path,expected_schedule_sha256=digest(schedule),
        runtime_factory=lambda *args:pytest.fail('completed cycle loaded models'),
        principal_configuration={'receiver_commit':'b'*40},boss_commit='c'*40,agent_commit='b'*40,
        state_defects_and_gaps_reported=[])
    assert asyncio.run(execution.run_cycle(0))==completed
    assert not (tmp_path/'run/cycle-00').exists()


def _composition_fixture(tmp_path,monkeypatch,*,adapter_class):
    from research.kalshi.frankie_boss import sunday_execution as execution_module
    from research.kalshi.frankie_boss.frankie_principal_adapter import PrincipalPending
    from test_source_contract_runtime import fixture
    contract,contract_hash,first=fixture(tmp_path)
    steps=[dict(first,through_cursor=i,as_of=100+i,source_as_of=100+i) for i in range(19)]
    schedule=tmp_path/'schedule.json';schedule.write_bytes(canonical(steps))
    calls=[]
    class Coordinator:
        def _load(self,request,stage):return None
        async def run(self,**kwargs):
            plan=execution_module._load(tmp_path/'run/cycle-00/request-plan.c15.json')
            assert plan['input_hash']==kwargs['learning_kwargs']['input_hash']=='d'*64
            assert plan['expected_native_hash']=='e'*64
            assert plan['controller_kwargs']['source_hash']=='c'*64
            calls.append('coordinator-after-plan')
            raise PrincipalPending('host session pending in composition fixture')
    def assemble(context,decoder,book,**kwargs):
        selected={k:kwargs[k] for k in ('request_id','sessions','expected_sessions_hash','metadata','as_of',
            'source_as_of','source_hash','through_cursor')}
        selected['arm_hash']='a'*64
        return SimpleNamespace(),selected
    monkeypatch.setattr(execution_module,'assemble_request',assemble)
    monkeypatch.setattr(execution_module,'native_model_pin',lambda bridge:'e'*64)
    monkeypatch.setattr(execution_module,'learning_config',lambda *args,**kwargs:SimpleNamespace(digest='f'*64))
    from research.kalshi.frankie_boss.dipole_classroom import prepare_cycle
    from test_dipole_classroom_session import _teacher, HEX_B
    classroom=prepare_cycle(_teacher(),request_id='request-cycle-00',cycle_index=0,cycle_count=19,source_hash=HEX_B,as_of=2_000_000,through_cursor=6)
    runtime=execution_module.SundayRuntime(context=None,decoder=None,optimizer=None,classroom_package=classroom,
        principal_adapter_class=adapter_class,
        checkpoint=SimpleNamespace(checkpoint_hash='1'*64),expected_checkpoint_hash='1'*64,
        development_identity={},refresh_policy=None,input_hash='d'*64,expected_native_hash='e'*64,
        expected_critic_config_hash='2'*64,expected_critic_identity_hash='3'*64,
        critic_factory=lambda:pytest.fail('critic called before coordinator intent'),
        source_journal_path=str(tmp_path/'source.sqlite'),source_journal_checkpoint={'count':0,'head_hash':'4'*64})
    driver=SundayExecution(directory=tmp_path/'run',run_id='request',coordinator=Coordinator(),
        contract_path=contract,expected_contract_sha256=contract_hash,schedule_path=schedule,
        expected_schedule_sha256=digest(steps),runtime_factory=lambda *args:runtime,
        principal_configuration={'receiver_commit':'b'*40},boss_commit='c'*40,agent_commit='b'*40,
        state_defects_and_gaps_reported=[])
    return execution_module,PrincipalPending,driver,calls


def test_full_request_plan_is_saved_before_coordinator_or_critic_call(tmp_path,monkeypatch):
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
    execution_module,PrincipalPending,driver,calls=_composition_fixture(
        tmp_path,monkeypatch,adapter_class=IntegratedDipoleClassroomPrincipalAdapter)
    with pytest.raises(PrincipalPending):asyncio.run(driver.run_cycle(0))
    plan=execution_module._load(tmp_path/'run/cycle-00/request-plan.c15.json')
    assert plan['principal_adapter_identity']==(
        'research.kalshi.frankie_boss.dipole_classroom_integration:'
        'IntegratedDipoleClassroomPrincipalAdapter')
    assert calls==['coordinator-after-plan']


def test_execution_refuses_missing_classroom_adapter_class(tmp_path,monkeypatch):
    _,_,driver,calls=_composition_fixture(tmp_path,monkeypatch,adapter_class=None)
    with pytest.raises(ValueError,match='principal adapter class required'):
        asyncio.run(driver.run_cycle(0))
    assert calls==[]


@pytest.mark.parametrize('adapter_class', [object, str])
def test_execution_refuses_non_classroom_adapter_before_coordinator(tmp_path,monkeypatch,adapter_class):
    _,_,driver,calls=_composition_fixture(tmp_path,monkeypatch,adapter_class=adapter_class)
    with pytest.raises(ValueError,match='classroom principal adapter'):
        asyncio.run(driver.run_cycle(0))
    assert calls==[]


@pytest.mark.parametrize('tamper', [
    'package_missing', 'request_id', 'binding_hash', 'adapter_missing',
    'adapter_module', 'adapter_qualname', 'plan_adapter_missing', 'plan_adapter_changed',
])
def test_restart_refuses_changed_classroom_identity_before_coordinator(tmp_path,monkeypatch,tamper):
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
    from research.kalshi.frankie_boss.c15_journal import canonical_bytes, pack
    execution,Pending,driver,calls=_composition_fixture(
        tmp_path,monkeypatch,adapter_class=IntegratedDipoleClassroomPrincipalAdapter)
    with pytest.raises(Pending):
        asyncio.run(driver.run_cycle(0))
    calls.clear()
    runtime=driver.runtime_factory(None,None,None)
    if tamper=='package_missing':
        runtime.classroom_package=None
    elif tamper=='request_id':
        runtime.classroom_package['binding']['request_id']='request-cycle-01'
    elif tamper=='binding_hash':
        runtime.classroom_package['binding']['classroom_binding_hash']='9'*64
    elif tamper=='adapter_missing':
        runtime.principal_adapter_class=None
    elif tamper in ('adapter_module','adapter_qualname'):
        alternate=type('AlternateAdapter',(IntegratedDipoleClassroomPrincipalAdapter,),{})
        alternate.__module__=IntegratedDipoleClassroomPrincipalAdapter.__module__
        alternate.__qualname__=IntegratedDipoleClassroomPrincipalAdapter.__qualname__
        setattr(alternate,'__module__' if tamper=='adapter_module' else '__qualname__','changed')
        runtime.principal_adapter_class=alternate
    else:
        path=tmp_path/'run/cycle-00/request-plan.c15.json'
        plan=execution._load(path)
        if tamper=='plan_adapter_missing':
            del plan['principal_adapter_identity']
        else:
            plan['principal_adapter_identity']='changed:Adapter'
        path.write_bytes(canonical_bytes(pack(plan)))
    with pytest.raises(ValueError,match='classroom|principal adapter'):
        asyncio.run(driver.run_cycle(0))
    assert calls==[]
