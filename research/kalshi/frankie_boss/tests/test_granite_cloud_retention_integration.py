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


def test_controller_launch_is_retired_and_never_reaches_the_provider(monkeypatch, tmp_path):
    # Formerly the provider-failure stop/retain lifecycle through the bounded smoke controller. That launch route is
    # retired with the 4,096-token smoke context; the stop/retain lifecycle stays covered by the control and retained
    # host tests. The controller must refuse before touching the journal, the provider or the bootstrap stage.
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setattr(cloud, 'stage_bootstrap', lambda _: pytest.fail('retired launch must not stage'))
    class Journal:
        def get(self, name): pytest.fail('retired launch must not read the journal')
        def put(self, name, value, **kwargs): pytest.fail('retired launch must not write the journal')
    class API:
        def request(self, *args, **kwargs): pytest.fail('retired launch must not call the provider')
    with pytest.raises(ValueError, match='retired with the 4096 context'):
        cloud.controller(Journal(), API())
    assert not (tmp_path / 'pod-info.json').exists() and not (tmp_path / 'service-ready.json').exists()
