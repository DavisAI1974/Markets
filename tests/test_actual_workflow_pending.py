"""Actual runner pending boundaries; no classroom/model/cloud runtime is opened."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / 'research/kalshi/frankie_boss/operations'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules(monkeypatch):
    wait = load('workflow_wait_test_boundary', OPS / 'workflow_wait.py')
    monkeypatch.setitem(sys.modules, 'research.kalshi.frankie_boss.operations.workflow_wait', wait)
    actual = load('actual_pending_boundary', OPS / 'run_actual_sunday.py')
    return actual, wait


@pytest.fixture
def retained(tmp_path):
    root = tmp_path / 'run'
    cycle = root / 'execution/cycle-00'
    cycle.mkdir(parents=True)
    configuration = dict(run_id='same-run', run_directory=str(root), host_runtime=dict(
        repository=str(tmp_path), boss_commit='a'*40, schedule={'sha256':'b'*64},
        pod_credential_ssm=dict(name='/private/pod', region='us-east-2',
                                trigger_directory=str(tmp_path/'triggers'))))
    for path in (root/'host-identity.c15.json', cycle/'host-preparation.c15.json',
                 cycle/'actual-critic-request.json'):
        path.write_bytes(b'{"ns":1750000000000000123}')
    return configuration, cycle


def host(actual, configuration, cycle):
    h = actual.ActualHost.__new__(actual.ActualHost)
    h.config = configuration
    h.host = configuration['host_runtime']
    h.directory = Path(configuration['run_directory'])
    h._workflow_cycle = cycle
    h._workflow_resuming = []
    h.pending_return = True
    h.resume_wait_sha256 = None
    h.schedule = {'steps':[{}]}
    return h


@pytest.mark.parametrize('schema,kind', [
    ('FRANKIE_ACTUAL_EXECUTE_V1','readiness'),
    ('FRANKIE_ACTUAL_RESUME_JOB_V1','service_resume'),
])
def test_missing_request_bound_trigger_returns_before_credentials_or_polling(modules, retained, monkeypatch, schema, kind):
    actual, wait = modules
    configuration, cycle = retained
    if kind == 'service_resume':(cycle/'host-service.c15.json').write_bytes(b'{"existing":true}')
    h = host(actual, configuration, cycle)
    monkeypatch.setattr(actual.time, 'sleep', lambda *_: pytest.fail('pending return must not poll'))
    with pytest.raises(wait.WorkflowPending) as pending:
        h.read_execution_trigger(schema, ('readiness_directory','service_pins_sha256'), 'same-run-cycle-00')
    assert pending.value.result['wait_receipt']['kind'] == kind
    assert pending.value.result['wait_receipt']['request_id'] == 'same-run-cycle-00'
    assert not hasattr(h, '_ssm_pod_key')
    assert pending.value.exit_code == 3


def test_pending_mode_cannot_fall_back_to_stdin(modules, retained, monkeypatch):
    actual, _ = modules
    configuration, cycle = retained
    h = host(actual, configuration, cycle)
    h.host = {}
    monkeypatch.setattr(actual, 'read_trigger', lambda *_: pytest.fail('no stdin fallback'))
    with pytest.raises(ValueError):
        h.read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1', (), 'same-run-cycle-00')


def test_principal_callback_retains_same_request_without_releasing_host_lock(modules, retained):
    actual, wait = modules
    configuration, cycle = retained
    principal = cycle/'principal'
    principal.mkdir()
    request = {'request_id':'same-run-cycle-00','attachment':{'context':[1,2]}}
    (principal/'session-request.json').write_text(json.dumps(request))
    (cycle/'request-plan.c15.json').write_bytes(b'{"retained":"plan"}')
    h = host(actual, configuration, cycle)
    lock = SimpleNamespace(release=lambda:pytest.fail('do not release lock before durable pending return'))
    with pytest.raises(wait.WorkflowPending) as pending:
        actual.await_recorded_principal(request, h.directory, lock, pending=h.principal_pending)
    receipt = pending.value.result['wait_receipt']
    assert receipt['kind'] == 'principal'
    assert 'execution/cycle-00/principal/session-request.json' in receipt['artifacts']
    assert not (principal/'session-response.json').exists()


def test_recorded_principal_response_keeps_existing_waiter_admission_path(modules, retained):
    actual, _ = modules
    configuration, cycle = retained
    principal = cycle/'principal'
    principal.mkdir()
    request={'request_id':'same-run-cycle-00'}
    response={'response':{'retained':True},'host_attestation':{'retained':True}}
    (principal/'session-request.json').write_text(json.dumps(request))
    (principal/'session-response.json').write_text(json.dumps(response))
    state=[]
    lock=SimpleNamespace(release=lambda:state.append('release'),acquire=lambda **kw:state.append('acquire'))
    assert actual.await_recorded_principal(request, Path(configuration['run_directory']),lock,
        pending=lambda:pytest.fail('already recorded response must use existing validation path')) == response
    assert state == ['release','acquire']


def test_unpinned_main_returns_existing_wait_before_runtime_imports(modules, retained, monkeypatch):
    actual, wait = modules
    configuration, cycle = retained
    first=wait.write_wait_receipt(configuration,cycle,'readiness')
    config_path=cycle/'config.json'
    config_path.write_text(json.dumps(configuration))
    monkeypatch.setattr(sys,'argv',['runner','--configuration',str(config_path)])
    monkeypatch.setattr(actual,'imports',lambda *_:pytest.fail('unapproved reentry must not load runtime'))
    assert actual.main() == 3
    assert wait.read_wait_receipt(first['receipt_path']) == first['wait_receipt']


def test_unmatched_resume_main_refuses_before_runtime_imports(modules, retained, monkeypatch):
    actual, wait = modules
    configuration, cycle = retained
    wait.write_wait_receipt(configuration,cycle,'readiness')
    config_path=cycle/'config.json'
    config_path.write_text(json.dumps(configuration))
    monkeypatch.setattr(sys,'argv',['runner','--configuration',str(config_path),
        '--pending-return','--resume-wait-sha256','f'*64])
    monkeypatch.setattr(actual,'imports',lambda *_:pytest.fail('unknown event must not load runtime'))
    assert actual.main() == 1


def preparation_host(actual, cycle):
    body=b'{"max_tokens":11}'
    request=cycle/'exact-request.json'
    request.write_bytes(body)
    digest=hashlib.sha256(body).hexdigest()
    prepared=dict(request_id='same-run-cycle-00',request_path=str(request),
        initial_checkpoint_hash='checkpoint',native_pin='native',source_checkpoint={'head':'source'},
        admission=dict(request_sha256=digest,tokenizer_sha256='tokenizer',context=32,output_tokens=11),
        receipt=dict(request_sha256=digest,request_bytes=len(body),
                     context=dict(input_hash='input',as_of=123,source_prefix_hash='source')))
    record=cycle/'preparation.json'
    record.write_bytes(b'preserved')
    h=actual.ActualHost.__new__(actual.ActualHost)
    h.api=SimpleNamespace(driver=SimpleNamespace(_load=lambda p:prepared),
                          native_model_pin=lambda model:'native')
    h.context=h.decoder=object()
    h.checkpoint=SimpleNamespace(checkpoint_hash='checkpoint')
    h.source_checkpoint={'head':'source'}
    h.admit=SimpleNamespace(tokenizer_sha256='tokenizer')
    h.host={'service_context':32}
    h.cache=SimpleNamespace(receipt={'input_hash':'input'})
    return h,prepared,record,request,{'as_of':123,'source_hash':'source'}


def test_actual_retained_preparation_reuses_exact_body_and_context(modules, retained):
    actual,_=modules
    _,cycle=retained
    h,prepared,record,request,binding=preparation_host(actual,cycle)
    before=request.read_bytes()
    assert h.prepared_before_restart(binding,'same-run-cycle-00',record) is prepared
    assert request.read_bytes()==before


@pytest.mark.parametrize('change',['request','source','checkpoint','input'])
def test_actual_retained_preparation_refuses_changed_evidence(modules, retained, change):
    actual,_=modules
    _,cycle=retained
    h,prepared,record,request,binding=preparation_host(actual,cycle)
    if change=='request':request.write_bytes(b'{"max_tokens":12}')
    if change=='source':h.source_checkpoint={'head':'foreign'}
    if change=='checkpoint':h.checkpoint.checkpoint_hash='foreign'
    if change=='input':h.cache.receipt['input_hash']='foreign'
    with pytest.raises(ValueError):
        h.prepared_before_restart(binding,'same-run-cycle-00',record)


def test_transport_attention_preserves_dispatch_job_not_spool_directory(modules, retained):
    actual,wait=modules
    configuration,cycle=retained
    h=host(actual,configuration,cycle)
    spool=cycle/'critic-spool'/('c'*64)
    spool.mkdir(parents=True)
    binding={'job_id':'d'*64,'body_sha256':actual.sha(cycle/'actual-critic-request.json')}
    (spool/'dispatch.json').write_text(json.dumps({'binding':binding}))
    with pytest.raises(wait.WorkflowPending) as pending:
        h.transport_pending()
    assert pending.value.result['wait_receipt']['job_id']=='d'*64


def test_initial_execution_scope_preserves_original_authorized_roster_on_resume(modules, retained):
    _,wait=modules
    configuration,cycle=retained
    wait.write_execution_scope(configuration,target_cycles=3,total_cycles=5)
    receipt=wait.write_wait_receipt(configuration,cycle,'readiness')
    assert 'workflow-execution-scope.json' in receipt['wait_receipt']['artifacts']
    assert wait.resume_admission(configuration,receipt['receipt_sha256'])==3


@pytest.mark.parametrize('target,total',[(0,5),(6,5),(True,5),(3,True)])
def test_invalid_execution_scope_refused(modules, retained, target, total):
    _,wait=modules
    configuration,_=retained
    with pytest.raises(ValueError):
        wait.write_execution_scope(configuration,target_cycles=target,total_cycles=total)


def test_execution_scope_cannot_expand_or_replace_after_first_authorization(modules, retained):
    _,wait=modules
    configuration,_=retained
    wait.write_execution_scope(configuration,target_cycles=3,total_cycles=5)
    wait.write_execution_scope(configuration,target_cycles=3,total_cycles=5)
    with pytest.raises(ValueError):
        wait.write_execution_scope(configuration,target_cycles=4,total_cycles=5)


def test_resume_refuses_scope_changed_since_wait(modules, retained):
    _,wait=modules
    configuration,cycle=retained
    wait.write_execution_scope(configuration,target_cycles=3,total_cycles=5)
    receipt=wait.write_wait_receipt(configuration,cycle,'readiness')
    path=Path(configuration['run_directory'])/'workflow-execution-scope.json'
    value=json.loads(path.read_bytes())
    value['target_cycles']=5
    path.write_bytes(wait.canonical(value))
    with pytest.raises(ValueError):
        wait.resume_admission(configuration,receipt['receipt_sha256'])


def test_legacy_wait_without_execution_scope_stays_capped(modules, retained):
    _,wait=modules
    configuration,cycle=retained
    receipt=wait.write_wait_receipt(configuration,cycle,'readiness')
    assert wait.resume_admission(configuration,receipt['receipt_sha256'])==1
