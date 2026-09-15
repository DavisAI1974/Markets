"""Only new launch behavior; the passing smoke/control baseline is retained."""
import hashlib
import json
import pytest
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss.tests.test_granite_runpod_cloud_control import intent


def test_thirty_minute_limit_and_no_larger_window():
    item = intent()
    item['deadline'] = item['start'] + cloud.TOTAL_SECONDS
    assert cloud.TOTAL_SECONDS == 1800
    cloud.control.validate_intent(item)
    for duration in (1201, 1801, 3600):
        item['deadline'] = item['start'] + duration
        with pytest.raises(ValueError):
            cloud.control.validate_intent(item)


def test_supervisor_metadata_only_is_removed():
    from types import SimpleNamespace
    environment = {'SUPERVISOR_ENABLED': '1', 'SUPERVISOR_PROCESS_NAME': 'app',
                   'SUPERVISOR_GROUP_NAME': 'app', 'SUPERVISOR_PROGRAM__APP_COMMAND': 'pinned',
                   'SUPERVISOR_UNAPPROVED_OVERRIDE': 'still rejected by bootstrap'}
    exec(cloud.supervisor_metadata_code(), {'os': SimpleNamespace(environ=environment)})
    assert environment == {'SUPERVISOR_PROGRAM__APP_COMMAND': 'pinned',
                           'SUPERVISOR_UNAPPROVED_OVERRIDE': 'still rejected by bootstrap'}


@pytest.mark.parametrize('during_write', [False, True])
def test_service_publication_refuses_cleanup_race(monkeypatch, tmp_path, during_write):
    clock = [2500 if during_write else 2650]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    class Journal:
        def put(self, *args, **kwargs):
            assert during_write
            clock[0] = 2680
    with pytest.raises(TimeoutError):
        cloud.publish_service(Journal(), 'abc123', {'deadline': 2800}, {})
    assert not (tmp_path/'service-ready.json').exists()


@pytest.mark.parametrize('value', [None, 'other'])
def test_unexpected_supervisor_metadata_refused(value):
    from types import SimpleNamespace
    with pytest.raises(SystemExit):
        exec(cloud.supervisor_metadata_code(), {'os': SimpleNamespace(environ={'SUPERVISOR_ENABLED': value})})


@pytest.mark.parametrize('publication_fails', [False, True])
def test_service_launch_keeps_ready_pod_and_cleans_failure(monkeypatch, tmp_path, publication_fails):
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    monkeypatch.setattr(cloud.time, 'time', lambda: 1000)
    monkeypatch.setattr(cloud.secrets, 'token_hex', lambda _: 'a' * 32)
    monkeypatch.setattr(cloud, 'stage_bootstrap', lambda journal: ({'files': []}, {}))
    monkeypatch.setattr(cloud, 'bootstrap_command', lambda *args: 'python3 bootstrap.py')
    monkeypatch.setattr(cloud, 'capture_progress', lambda *args: None)
    records = {'startup': {}, 'disk': {}}
    monkeypatch.setattr(cloud, 'startup_logs', lambda *args: records)
    checked = []
    monkeypatch.setattr(cloud, 'validate_runtime', lambda actual, admitted: checked.append(actual))
    monkeypatch.setattr(cloud.probe, 'run_probe', lambda **kwargs: pytest.fail('standalone smoke must not run'))
    exchanges = []
    def health(pod_id, method, path, *args):
        exchanges.append((method, path))
        assert (method, path) == ('GET', '/health')
        return 200, b'{"status":"ok"}'
    monkeypatch.setattr(cloud.probe, 'https_exchange', health)
    cleanup = []
    monkeypatch.setattr(cloud, 'finish', lambda *args: cleanup.append(args))
    class Journal:
        bucket = 'approved-bucket'
        values = {}
        def get(self, name):
            if name == 'watchdog-ready.json':
                return {'at': 1000}
            if name == 'armed.json':
                return {'at': 1000, 'intent_sha256': hashlib.sha256(cloud.canonical(self.values['intent.json'])).hexdigest()}
            return self.values.get(name)
        def put(self, name, value, *, once=False):
            if name == 'service-ready.json' and publication_fails:
                raise OSError('journal publication unavailable')
            self.values[name] = value
    class API:
        created = None
        def request(self, method, path, body=None):
            if method == 'POST':
                assert self.created is None
                assert body['env']['RUNPOD_GRANITE_LIFETIME_SECONDS'] == '1680'
                self.created = dict(body, id='abc123', cost=1.09)
            else:
                assert (method, path) == ('GET', '/v2/pods/abc123')
            return self.created
    journal = Journal()
    if publication_fails:
        with pytest.raises(OSError):
            cloud.controller(journal, API())
        assert len(cleanup) == 1
    else:
        result = cloud.controller(journal, API())
        assert result['outcome'] == 'service_ready'
        assert result['cleanup_starts_at'] == 2680 and result['deadline'] == 2800
        assert result['inference_sent'] is False
        assert 'api_key' not in json.dumps(result)
        assert cleanup == []
        assert 'controller-finished.json' not in journal.values
    assert checked == [records]
    assert exchanges == [('GET', '/health')]
