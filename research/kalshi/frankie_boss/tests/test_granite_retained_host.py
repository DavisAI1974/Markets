import hashlib

from research.kalshi.frankie_boss import granite_retained_host as host


def test_observer_exhaustion_preserves_pod_even_after_storage_outage(monkeypatch, tmp_path):
    info = {'pod_id': host.lifecycle.POD_ID, 'intent': {}}
    startup = host.lifecycle.make_startup(info, start=1000., request_sha256='a'*64,
        local_ready=dict(request_sha256='a'*64, host_instance_id='local-ready-instance', admitted_at=999.))
    class Journal:
        def get(self, name):
            if name == 'retained-startup.json':
                return startup
            raise OSError('storage unavailable')
        def put(self, *args, **kwargs):
            raise OSError('storage unavailable')
    clock = [1000.]
    monkeypatch.setattr(host, 'OUT', tmp_path)
    monkeypatch.setattr(host.time, 'time', lambda: clock[0])
    monkeypatch.setattr(host.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    monkeypatch.setattr(host, 'watchdog_identity', lambda: dict(run_id='1', job_id='2', job_deadline=1700.))
    monkeypatch.setattr(host.retained, 'stop_owned_once', lambda *args: (_ for _ in ()).throw(AssertionError('no elapsed stop')))
    host.watchdog(Journal(), object(), info)
    host.cleanup(object())
    assert (tmp_path/'startup-intent.json').exists()
    assert (tmp_path/'watchdog-attention.json').exists()
    assert (tmp_path/'observer-handoff.json').exists()
    assert not (tmp_path/'confirmed-fatal.json').exists()


def test_cleanup_uses_cached_ownership_without_storage(monkeypatch, tmp_path):
    info = {'pod_id': host.lifecycle.POD_ID, 'intent': {}}
    lease = host.lifecycle.make_lease(info, start=1000., duration_seconds=600,
                                     request_sha256='a'*64)
    monkeypatch.setattr(host, 'OUT', tmp_path)
    monkeypatch.setattr(host, 'INFO_SHA256', hashlib.sha256(host.artifacts.canonical(info)).hexdigest())
    host.save('pod-info.json', info)
    host.save('lease.json', lease)
    host.save('confirmed-fatal.json', {'reason': 'verified_integrity_failure'})
    calls = []
    def stop(api, intent, pod_id):
        calls.append(pod_id)
        return dict(status='confirmed_stopped')
    monkeypatch.setattr(host.retained, 'stop_owned_once', stop)
    monkeypatch.setattr(host.cloud, 'Journal', lambda: (_ for _ in ()).throw(AssertionError('no S3 allowed')))
    host.cleanup(object())
    assert calls == [host.lifecycle.POD_ID]


def test_startup_requires_fresh_provider_container_timestamp(monkeypatch):
    monkeypatch.setattr(host.time, 'time', lambda: 2000.)
    records = {}
    frame = dict(source='container', ts='1970-01-01T00:16:39Z',
                 line='GRANITE_RUNPOD_STARTUP {"startup":{}}')
    host.keep_startup_frame(records, frame, {'start': 1000.})
    assert not records
    host.keep_startup_frame(records, dict(frame, ts='1970-01-01T00:16:41Z'), {'start': 1000.})
    assert records == {'startup': {'startup': {}}, 'startup_event_at': 1001.}


def test_open_run_explicit_completion_still_stops_retained_pod(monkeypatch, tmp_path):
    info = {'pod_id': host.lifecycle.POD_ID, 'intent': {}}
    startup = host.lifecycle.make_startup(info, start=1000., request_sha256='a'*64,
        local_ready=dict(request_sha256='a'*64, host_instance_id='local-ready-instance', admitted_at=999.))
    class Journal:
        def get(self, name):
            return {'retained-startup.json': startup,
                    'retained-finished.json': {'startup_sha256': host.lifecycle.check_startup(startup, info)}}.get(name)
        def put(self, *args, **kwargs):
            pass
    calls = []
    monkeypatch.setattr(host, 'OUT', tmp_path)
    monkeypatch.setattr(host.time, 'time', lambda: 1001.)
    monkeypatch.setattr(host, 'watchdog_identity', lambda: dict(run_id='1', job_id='2', job_deadline=2000.))
    def stop(api, intent, pod_id):
        calls.append(pod_id)
        return {'status': 'confirmed_stopped'}
    monkeypatch.setattr(host.retained, 'stop_owned_once', stop)
    host.watchdog(Journal(), object(), info)
    assert calls == [host.lifecycle.POD_ID]
