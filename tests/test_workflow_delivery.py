"""Exact existing-workflow delivery: no runtime dispatch, no model call."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module():
    spec = importlib.util.spec_from_file_location('workflow_delivery_test',
        ROOT / 'research/kalshi/frankie_boss/operations/workflow_delivery.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture
def case(tmp_path, monkeypatch):
    m = module()
    run = tmp_path / 'run'
    principal = run / 'execution/cycle-00/principal'
    principal.mkdir(parents=True)
    config = dict(run_id='retained-run', run_directory=str(run),
                  host_runtime=dict(boss_commit='a' * 40, repository=str(tmp_path),
                                    pod_credential_ssm=dict(trigger_directory=str(tmp_path/'triggers'))))
    cfg = tmp_path/'config.json'
    cfg.write_bytes(raw(config))
    request = raw(dict(request_id='retained-run-cycle-00', attachment={}))
    (principal/'session-request.json').write_bytes(request)
    critic = run/'execution/cycle-00/actual-critic-request.json'
    critic.write_bytes(b'{"retained":true}')
    wait = dict(schema='FRANKIE_WORKFLOW_WAIT_V1', state='WAIT', kind='readiness',
                run_id=config['run_id'], run_directory=str(run), cycle_index=0,
                request_id='retained-run-cycle-00', configuration_sha256=digest(cfg.read_bytes()),
                artifacts={'execution/cycle-00/actual-critic-request.json':
                           dict(sha256=digest(critic.read_bytes()), bytes=critic.stat().st_size),
                           'execution/cycle-00/principal/session-request.json':
                           dict(sha256=digest(request), bytes=len(request))})
    wait_path = run/'wait.json'
    wait_path.write_bytes(raw(wait))
    context = dict(configuration_path=str(cfg), configuration_sha256=digest(cfg.read_bytes()),
                   wait_receipt_path=str(wait_path), wait_receipt_sha256=digest(wait_path.read_bytes()),
                   tools_root=str(tmp_path), tools_commit='a'*40, python=sys.executable,
                   request_id=wait['request_id'], request_sha256=digest(critic.read_bytes()))
    def reader(path, expected_sha256=None, configuration=None):
        assert expected_sha256 == digest(Path(path).read_bytes())
        assert configuration == config
        return dict(wait)
    monkeypatch.setattr(m, 'read_wait_receipt', reader)
    payload = tmp_path/'payload'
    payload.mkdir()
    for name in m.DELIVERED:
        value = {'test': name}
        if name == 'service-pins.json':
            value = dict(request_sha256=context['request_sha256'],
                         admission=dict(request_sha256=context['request_sha256']))
        if name == 'service-ready.json':
            value = dict(inference_sent=False)
        (payload/name).write_bytes(raw(value))
    return m, context, config, wait, payload, principal


def test_readiness_duplicate_verifies_exact_files_and_reuses_receipt(case):
    m, ctx, config, wait, payload, _ = case
    first = m.publish_readiness(ctx, payload)
    second = m.publish_readiness(ctx, payload)
    assert first == second
    trigger = Path(first['trigger'])
    assert json.loads(trigger.read_bytes())['service_pins_sha256'] == digest((payload/'service-pins.json').read_bytes())
    assert Path(first['receipt_path']).is_file()


@pytest.mark.parametrize('change', ['request', 'configuration', 'wait-kind', 'readiness'])
def test_changed_binding_refuses_before_trigger(case, change):
    m, ctx, config, wait, payload, _ = case
    if change == 'request':
        ctx['request_id'] = 'foreign-cycle-00'
    elif change == 'configuration':
        Path(ctx['configuration_path']).write_bytes(b'{}')
    elif change == 'wait-kind':
        wait['kind'] = 'principal'
    else:
        (payload/'service-pins.json').write_bytes(raw(dict(request_sha256='f'*64, admission={})))
    with pytest.raises(ValueError):
        m.publish_readiness(ctx, payload)
    assert not (Path(config['host_runtime']['pod_credential_ssm']['trigger_directory'])/ctx['request_id']/'FRANKIE_ACTUAL_EXECUTE_V1.json').exists()


def test_readiness_changed_duplicate_preserves_all_original_bytes(case):
    m, ctx, config, wait, payload, _ = case
    receipt = m.publish_readiness(ctx, payload)
    before = {p: p.read_bytes() for p in Path(receipt['readiness_directory']).iterdir() if p.is_file()}
    (payload/'observer.json').write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError):
        m.publish_readiness(ctx, payload)
    assert all(p.read_bytes() == value for p, value in before.items())


def test_readiness_existing_trigger_without_matching_intent_is_not_adopted(case):
    m, ctx, config, wait, payload, _ = case
    trigger = Path(config['host_runtime']['pod_credential_ssm']['trigger_directory'])/ctx['request_id']/'FRANKIE_ACTUAL_EXECUTE_V1.json'
    trigger.parent.mkdir(parents=True)
    trigger.write_bytes(b'{}')
    with pytest.raises(ValueError):
        m.publish_readiness(ctx, payload)
    assert trigger.read_bytes() == b'{}'


def test_readiness_failed_completion_receipt_replays_without_overwrite(case, monkeypatch):
    m, ctx, _, _, payload, _ = case
    original = m.publish_bytes
    failed = [False]
    def fail(path, body):
        if Path(path).name == 'receipt.json' and not failed[0]:
            failed[0] = True
            raise OSError('injected completion crash')
        return original(path, body)
    monkeypatch.setattr(m, 'publish_bytes', fail)
    with pytest.raises(OSError):
        m.publish_readiness(ctx, payload)
    assert m.publish_readiness(ctx, payload)['request_id'] == ctx['request_id']


def test_symlink_readiness_destination_refuses(case, tmp_path):
    m, ctx, config, _, payload, _ = case
    destination = Path(config['run_directory'])/'workflow-deliveries/readiness'/ctx['request_id']
    destination.parent.mkdir(parents=True)
    outside = tmp_path/'outside'
    outside.mkdir()
    destination.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        m.publish_readiness(ctx, payload)
    assert list(outside.iterdir()) == []


def principal_payload(case):
    m, ctx, config, wait, payload, principal = case
    wait['kind'] = 'principal'
    ctx['request_sha256'] = digest((principal/'session-request.json').read_bytes())
    response = dict(request_sha256='2'*64, session_id='retained-session')
    record = raw(dict(host_authority='test', session_id='retained-session'))
    (payload/'response.json').write_bytes(raw(response))
    (payload/'host-session-record.json').write_bytes(record)
    attestation = dict(host_record=dict(path=str(principal/'host-session-record.json'), bytes=len(record), sha256=digest(record)))
    (payload/'host-attestation.json').write_bytes(raw(attestation))
    return response, attestation


def test_principal_duplicate_revalidates_same_envelope_and_changed_duplicate_refuses(case):
    m, ctx, _, _, payload, principal = case
    response, attestation = principal_payload(case)
    calls = []
    def recorder(configuration, response_path, attestation_path, cycle_index, turn):
        calls.append(turn)
        final = principal/'session-response.json'
        body = raw(dict(response=json.loads(response_path.read_bytes()), host_attestation=json.loads(attestation_path.read_bytes())))
        if final.exists():
            assert final.read_bytes() == body
        else:
            final.write_bytes(body)
    first = m.record_principal(ctx, payload, turn='initial', recorder=recorder)
    assert m.record_principal(ctx, payload, turn='initial', recorder=recorder) == first
    assert calls == ['initial', 'initial']
    (payload/'response.json').write_bytes(raw(dict(response, session_id='foreign')))
    with pytest.raises(ValueError):
        m.record_principal(ctx, payload, turn='initial', recorder=recorder)
    assert json.loads((principal/'session-response.json').read_bytes())['response'] == response


def test_principal_existing_unrelated_response_is_not_success(case):
    m, ctx, _, _, payload, principal = case
    principal_payload(case)
    (principal/'session-response.json').write_bytes(b'{"response":{},"host_attestation":{}}')
    with pytest.raises(ValueError):
        m.record_principal(ctx, payload, turn='initial', recorder=lambda *args: pytest.fail('foreign envelope reached admission'))


def test_delivery_workflows_are_explicit_reusable_and_no_old_defaults():
    for name in ('frankie_deliver_readiness.yml', 'frankie_host_record_principal_response.yml'):
        source = (ROOT/'.github/workflows'/name).read_text()
        assert 'workflow_call:' in source and 'context_json:' in source
        assert 'push:' not in source and 'schedule:' not in source
        assert "default: '20211003'" not in source
    readiness = (ROOT/'.github/workflows/frankie_deliver_readiness.yml').read_text()
    assert 'head_sha' in readiness and 'conclusion' in readiness and 'workflow_id' in readiness


def test_delivery_import_and_builder_are_stdlib_only_in_fresh_interpreter(tmp_path):
    import subprocess
    code = """import importlib.util,sys
spec=importlib.util.spec_from_file_location('delivery',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert 'torch' not in sys.modules
"""
    subprocess.run([sys.executable, '-S', '-B', '-c', code,
                    str(ROOT/'research/kalshi/frankie_boss/operations/workflow_delivery.py')], check=True)
    result = subprocess.run([sys.executable, '-S', '-B', str(ROOT/'deploy/aws/host/build_readiness_delivery.py'), '--help'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--context-json' in result.stdout


def test_native_payload_placement_uses_verified_run_not_reread_configuration():
    builder = (ROOT/'deploy/aws/host/build_readiness_delivery.py').read_text()
    script = (ROOT/'deploy/aws/host/frankie_host_record_principal_response.ps1').read_text().split('# Record Root')[0]
    assert '$verified.run_directory' in builder and '$verified.run_directory' in script
    assert 'Get-Content' not in builder
    assert 'Get-Content' not in script
