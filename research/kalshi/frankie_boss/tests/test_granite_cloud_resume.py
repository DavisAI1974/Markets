import copy
import json

import pytest

from research.kalshi.frankie_boss import granite_cloud_resume as resume
from research.kalshi.frankie_boss import granite_run_artifacts as artifacts
from research.kalshi.frankie_boss import granite_runpod_cloud_control as control
from research.kalshi.frankie_boss.granite_cloud_diagnostics import Collector


def intent():
    nonce = 'a' * 32
    return dict(schema='GRANITE_CLOUD_INTENT_V1', nonce=nonce,
                name='granite-smoke-' + nonce, image=control.granite_runpod.IMAGE,
                start=1000, deadline=2200)


def pod(status='RUNNING'):
    owner = intent()
    return dict(id='pod_abc123', name=owner['name'], image=owner['image'],
                env={'RUNPOD_SMOKE_OWNER': owner['nonce'], 'SECRET': 'PRIVATE',
                     'GRANITE_MANIFEST_SHA256': artifacts.manifest_digest(manifest())},
                status=status, dataCenterId='US-TX-4', gpu={'id': 'NVIDIA L40S', 'count': 1},
                disk=100, mounts={'persistent': {'path': '/opt/ml', 'size': 50}}, cost=1.09)


def manifest():
    return artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())


def snapshot():
    return Collector(intent()['nonce'], manifest()).export()


class API:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


def test_stop_readback_preserves_id_before_action():
    api = API([{'pods': [pod()]}, pod(), pod('EXITED'), pod('EXITED')])
    known = []
    def discovered(value):
        assert len(api.calls) == 1
        known.append(value)
    result = resume.stop_owned_once(api, intent(), on_discovered=discovered)
    assert known == ['pod_abc123']
    assert result == {'status': 'confirmed_stopped', 'pod_id': 'pod_abc123', 'data_retained': True}
    assert api.calls[2] == ('POST', '/v2/pods/pod_abc123/action', {'action': 'stop'})
    assert [call[0] for call in api.calls] == ['GET', 'GET', 'POST', 'GET']


def test_updated_stop_response_alone_is_not_readback():
    api = API([pod(), pod(), pod('EXITED'), pod('RUNNING')])
    assert resume.stop_owned_once(api, intent(), 'pod_abc123')['status'] == 'stop_pending'


def test_stop_already_exited_needs_no_mutation():
    api = API([pod('EXITED'), pod('EXITED')])
    assert resume.stop_owned_once(api, intent(), 'pod_abc123')['data_retained'] is True
    assert all(call[0] == 'GET' for call in api.calls)


@pytest.mark.parametrize('status', ['ERROR', 'TERMINATED'])
def test_bad_status_never_claims_retained(status):
    api = API([pod(status), pod(status)])
    with pytest.raises(ValueError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')
    assert all(call[0] == 'GET' for call in api.calls)


def test_notfound_is_not_retained_success():
    api = API([control.ProviderError(404)])
    with pytest.raises(control.ProviderError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')


def test_conflict_race_accepts_only_fresh_exited():
    api = API([pod(), pod(), control.ProviderError(409), pod('EXITED')])
    assert resume.stop_owned_once(api, intent(), 'pod_abc123')['status'] == 'confirmed_stopped'
    api = API([pod(), pod(), control.ProviderError(409), pod()])
    with pytest.raises(control.ProviderError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')


def test_changed_owner_before_stop_refused():
    other = pod()
    other['env']['RUNPOD_SMOKE_OWNER'] = 'b' * 32
    api = API([pod(), other])
    with pytest.raises(ValueError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')
    assert len(api.calls) == 2


def test_pod_info_has_safe_actual_config_without_secrets():
    item = pod('EXITED')
    item['untrusted'] = 'PRIVATE'
    runtime = {'startup': {'startup': {'runtime': {
        'packages': {'torch': '2.11.0', 'tokenizers': '0.22.2', 'SECRET': 'PRIVATE'},
        'gpu_count': 1, 'gpu': 'NVIDIA L40S', 'gpu_total_memory': 48000000000,
        'python': '3.12.3', 'cuda': '13.0', 'SECRET': 'PRIVATE'},
        'environment': {'GRANITE_MAX_MODEL_LEN': '4096', 'TOKEN': 'PRIVATE'}}}}
    info = resume.capture_pod_info(item, intent(), manifest(), snapshot(), runtime)
    assert info['pod']['mounts']['persistent'] == {'path': '/opt/ml', 'size': 50}
    assert info['model']['manifest_sha256'] == artifacts.manifest_digest(manifest())
    assert info['retained_directory'] == '/opt/ml/model'
    assert info['cleanup_mode'] == 'stop_retain'
    assert 'PRIVATE' not in json.dumps(info)
    assert 'SECRET' not in json.dumps(info)
    assert resume.validate_resume(info, item, manifest()) == info


@pytest.mark.parametrize('damage', ['manifest', 'owner', 'mount', 'status', 'id', 'intent', 'unknown_field', 'model_env'])
def test_resume_refuses_changed_identity_or_untrusted_info(damage):
    item, approved = pod('EXITED'), manifest()
    info = resume.capture_pod_info(item, intent(), approved, snapshot())
    if damage == 'manifest':
        approved['files'][0]['sha256'] = '0' * 64
    elif damage == 'owner':
        item['env']['RUNPOD_SMOKE_OWNER'] = 'b' * 32
    elif damage == 'mount':
        item['mounts']['persistent']['size'] = 60
    elif damage == 'status':
        item['status'] = 'RUNNING'
    elif damage == 'id':
        item['id'] = 'different'
    elif damage == 'intent':
        info['intent']['nonce'] = 'b' * 32
    elif damage == 'model_env':
        item['env']['GRANITE_MANIFEST_SHA256'] = '0' * 64
    else:
        info['secret'] = 'PRIVATE'
    with pytest.raises(ValueError):
        resume.validate_resume(info, item, approved)


def test_diagnostics_unvalidated_extra_field_refused():
    raw = snapshot()
    raw['SECRET'] = 'PRIVATE'
    with pytest.raises(ValueError):
        resume.capture_pod_info(pod(), intent(), manifest(), raw)


def test_resume_accepts_info_captured_while_running_after_exact_stop():
    info = resume.capture_pod_info(pod(), intent(), manifest(), snapshot())
    stopped = pod('EXITED')
    stopped['cost'] = 0
    assert resume.validate_resume(info, stopped, manifest()) == info


def test_wrong_exact_id_response_and_path_injection_are_refused():
    foreign = pod()
    foreign['id'] = 'other'
    api = API([foreign])
    with pytest.raises(ValueError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')
    assert len(api.calls) == 1
    api = API([])
    with pytest.raises(ValueError):
        resume.stop_owned_once(api, intent(), '../other?secret')
    assert not api.calls


def test_exited_without_persistent_disk_is_not_retained():
    missing = pod('EXITED')
    missing['mounts'] = {}
    api = API([missing, missing])
    with pytest.raises(ValueError):
        resume.stop_owned_once(api, intent(), 'pod_abc123')


def test_telemetry_history_preserved_and_unknown_nested_fields_refused(tmp_path):
    from research.kalshi.frankie_boss.granite_runpod_progress import Progress
    collector = Collector(intent()['nonce'], manifest())
    progress = Progress(manifest(), tmp_path, 'stage', intent()['nonce'], emit=collector.ingest)
    progress.failure(TimeoutError('PRIVATE'))
    diagnostic = collector.export()
    info = resume.capture_pod_info(pod(), intent(), manifest(), diagnostic)
    assert info['diagnostics']['diagnostics'][0]['code'] == 'timeout'
    diagnostic['latest']['stage']['SECRET'] = 'PRIVATE'
    with pytest.raises(ValueError):
        resume.capture_pod_info(pod(), intent(), manifest(), diagnostic)
