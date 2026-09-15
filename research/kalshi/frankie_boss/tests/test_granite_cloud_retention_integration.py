"""Compose controller/watchdog with real retained-disk helpers and fake I/O."""
import copy
import hashlib
import json

import pytest

from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss import granite_cloud_resume as resume
from research.kalshi.frankie_boss.granite_runpod_progress import Progress


def launch_intent():
    nonce = 'a' * 32
    return dict(schema='GRANITE_CLOUD_INTENT_V1', nonce=nonce,
                name='granite-smoke-' + nonce, image=cloud.control.granite_runpod.IMAGE,
                start=1000, deadline=2800, cleanup_mode='stop_retain')


def manifest():
    return cloud.artifacts.strict_json(cloud.artifacts.DEFAULT_MANIFEST.read_bytes())


def owned_pod():
    item = launch_intent()
    return dict(id='retained123', name=item['name'], image=item['image'], status='RUNNING',
                env={'RUNPOD_SMOKE_OWNER': item['nonce'], 'PRIVATE_KEY': 'PRIVATE',
                     'GRANITE_MANIFEST_SHA256': cloud.artifacts.manifest_digest(manifest())},
                gpu={'id': 'NVIDIA L40S', 'count': 1}, dataCenterId='US-MO-1', cost=1.09,
                disk=100, mounts={'persistent': {'path': '/opt/ml', 'size': 50}})


class RetainedAPI:
    def __init__(self, clock):
        self.pod, self.calls, self.clock = owned_pod(), [], clock

    def request(self, method, path, body=None):
        self.calls.append((self.clock[0], method, path, body))
        if method == 'DELETE':
            pytest.fail('retained-disk cleanup must never DELETE')
        if path == '/v2/pods':
            assert method == 'GET'
            return {'pods': [copy.deepcopy(self.pod)]}
        assert path in ('/v2/pods/retained123', '/v2/pods/retained123/action')
        if method == 'POST':
            assert body == {'action': 'stop'}
            self.pod['status'], self.pod['cost'] = 'EXITED', 0
        return copy.deepcopy(self.pod)


def test_thirty_minute_watchdog_stops_even_when_s3_lost_after_arm(monkeypatch, tmp_path):
    clock = [1000]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.time, 'sleep', lambda _: clock.__setitem__(0, clock[0] + 120))
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    item = launch_intent()
    cloud.control.validate_intent(item)
    assert cloud.TOTAL_SECONDS == item['deadline'] - item['start'] == 1800
    class Journal:
        armed = False
        def put(self, name, value):
            if name == 'watchdog-ready.json':
                return
            if name == 'armed.json' and not self.armed:
                self.armed = True
                return
            raise OSError('private S3 failure details')
        def get(self, name):
            if name == 'intent.json':
                return item
            raise OSError('private S3 failure details')
    api = RetainedAPI(clock)
    result = cloud.watchdog(Journal(), api)
    assert result == {'status': 'confirmed_stopped', 'pod_id': 'retained123', 'data_retained': True}
    actions = [call for call in api.calls if call[1] == 'POST']
    assert len(actions) == 1
    assert actions[0][0] == item['deadline'] - 120
    assert clock[0] == item['deadline']
    assert json.loads((tmp_path / 'watchdog-owned-pod.json').read_text()) == {'id': 'retained123'}
    assert json.loads((tmp_path / 'watchdog-cleanup.json').read_text()) == result


def test_finish_uses_real_stop_helper_despite_s3_error(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    class Journal:
        def put(self, *args):
            raise OSError('PRIVATE')
    api = RetainedAPI([1000])
    result = cloud.finish(Journal(), api, launch_intent(), True, 'retained123')
    assert result['status'] == 'confirmed_stopped'
    assert result['data_retained'] is True
    assert api.pod['status'] == 'EXITED'


def test_capture_saves_safe_local_evidence_before_s3_write_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    item, approved = launch_intent(), manifest()
    collector = cloud.telemetry.Collector(item['nonce'], approved)
    progress = Progress(approved, tmp_path, 'stage', item['nonce'], emit=collector.ingest)
    progress.failure(TimeoutError('PRIVATE URL bearer token'))
    class Journal:
        def put(self, name, value):
            assert name == 'pod-info.json'
            assert (tmp_path / name).exists()
            assert 'PRIVATE' not in json.dumps(value)
            raise OSError('PRIVATE')
    with pytest.raises(OSError):
        cloud.capture_progress(Journal(), owned_pod(), item, approved, collector, {})
    info = json.loads((tmp_path / 'pod-info.json').read_text())
    assert info['cleanup_mode'] == 'stop_retain'
    assert info['diagnostics']['diagnostics'][-1]['code'] == 'timeout'
    assert 'PRIVATE' not in (tmp_path / 'pod-info.json').read_text()
    assert 'PRIVATE' not in (tmp_path / 'diagnostics.json').read_text()


def test_controller_provider_failure_stops_retains_and_captures_without_delete(monkeypatch, tmp_path):
    clock = [1000]
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.secrets, 'token_hex', lambda _: 'a' * 32)
    monkeypatch.setattr(cloud.secrets, 'token_urlsafe', lambda _: 'PRIVATE')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    rows = [{'path': name, 'size': 1, 'sha256': '0' * 64} for name in cloud.package.FILES]
    monkeypatch.setattr(cloud, 'stage_bootstrap', lambda _: ({'files': rows}, {'private': 'PRIVATE'}))
    monkeypatch.setattr(cloud, 'startup_logs', lambda *args: pytest.fail('GET failed before log read'))
    class Journal:
        bucket = 'expected-bucket'
        records = {}
        def get(self, name):
            if name == 'watchdog-ready.json':
                return {'at': clock[0]}
            if name == 'armed.json':
                return {'at': clock[0], 'intent_sha256': hashlib.sha256(cloud.canonical(self.records['intent.json'])).hexdigest()}
            return self.records.get(name)
        def put(self, name, value, **kwargs):
            assert 'PRIVATE' not in json.dumps(value)
            self.records[name] = copy.deepcopy(value)
    class API(RetainedAPI):
        failed = False
        def request(self, method, path, body=None):
            if method == 'POST' and path == '/v2/pods':
                self.calls.append((clock[0], method, path, None))
                self.pod['env'] = copy.deepcopy(body['env'])
                return copy.deepcopy(self.pod)
            if method == 'GET' and not self.failed:
                self.failed = True
                self.calls.append((clock[0], method, path, None))
                raise cloud.control.ProviderError(503)
            return super().request(method, path, body)
    api, journal = API(clock), Journal()
    with pytest.raises(cloud.control.ProviderError):
        cloud.controller(journal, api)
    assert journal.records['intent.json']['deadline'] == 2800
    assert journal.records['intent.json']['cleanup_mode'] == 'stop_retain'
    assert api.pod['status'] == 'EXITED'
    assert journal.records['controller-cleanup.json']['status'] == 'confirmed_stopped'
    info = json.loads((tmp_path / 'pod-info.json').read_text())
    assert info['pod']['status'] == 'EXITED'
    assert resume.validate_resume(info, api.pod, manifest()) == info
    assert not (tmp_path / 'service-ready.json').exists()
    assert all('PRIVATE' not in path.read_text() for path in tmp_path.glob('*.json'))


@pytest.mark.parametrize('bad_status', ['confirmed_absent', 'stop_pending', 'absent_in_inventory', 'unresolved'])
def test_terminate_or_pending_receipts_cannot_confirm_retention(bad_status):
    assert not cloud.cleanup_confirmed({'status': bad_status}, launch_intent())
