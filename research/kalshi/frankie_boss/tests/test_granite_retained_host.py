import hashlib

from research.kalshi.frankie_boss import granite_retained_host as host
from research.kalshi.frankie_boss.tests.test_granite_active_run import ActiveRunStore, S3, Journal as RowJournal


class OwnedJournal(RowJournal):
    # Run-bound cleanup binds the S3 Pod-level ownership record through the journal's client.
    def __init__(self):
        super().__init__()
        self.client, self.bucket = S3(), 'bucket'


def confirmed_stop(calls):
    def stop(api, intent, pod_id, **options):
        calls.append(pod_id)
        if 'on_ack' in options:
            options['on_ack']()
        return dict(status='confirmed_stopped', pod_id=pod_id, data_retained=True)
    return stop


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


def test_cleanup_uses_cached_ownership_and_run_bound_release(monkeypatch, tmp_path):
    # Confirmed-fatal cleanup trusts only the cached ownership receipt (never a
    # journal lookup of the Pod) and releases through the run-bound protocol:
    # fatal journaled under the startup digest, one stop, ownership closed.
    info = {'pod_id': host.lifecycle.POD_ID, 'intent': {}}
    startup = host.lifecycle.make_startup(info, start=1000., request_sha256='a'*64,
        local_ready=dict(request_sha256='a'*64, host_instance_id='local-ready-instance', admitted_at=999.))
    digest = host.lifecycle.check_startup(startup, info)
    monkeypatch.setattr(host, 'OUT', tmp_path)
    monkeypatch.setattr(host, 'INFO_SHA256', hashlib.sha256(host.artifacts.canonical(info)).hexdigest())
    host.save('pod-info.json', info)
    host.save('startup-intent.json', startup)
    host.save('confirmed-fatal.json', {'reason': 'verified_integrity_failure'})
    journal = OwnedJournal()
    store = ActiveRunStore(journal.client, journal.bucket, host.lifecycle.POD_ID)
    store.claim(digest)
    calls = []
    monkeypatch.setattr(host.retained, 'stop_owned_once', confirmed_stop(calls))
    monkeypatch.setattr(host.cloud, 'Journal', lambda: journal)
    monkeypatch.setattr(host, 'info_from_journal', lambda *args: (_ for _ in ()).throw(AssertionError('cached ownership only')))
    host.cleanup(object())
    assert calls == [host.lifecycle.POD_ID]
    assert journal.prefix == 'retained-granite/'+('a'*64)+'/'+host.JOURNAL_GENERATION+'/'
    assert journal.rows['retained-confirmed-fatal.json'] == {'startup_sha256': digest}
    assert journal.rows['retained-completion-cleanup.json']['startup_sha256'] == digest
    assert store.read()[0]['phase'] == 'closed'
    assert host.artifacts.strict_json((tmp_path/'cleanup.json').read_bytes())['status'] == 'confirmed_stopped'


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
    digest = host.lifecycle.check_startup(startup, info)
    journal = OwnedJournal()
    journal.rows.update({'retained-startup.json': startup, 'retained-finished.json': {'startup_sha256': digest}})
    store = ActiveRunStore(journal.client, journal.bucket, host.lifecycle.POD_ID)
    store.claim(digest)
    calls = []
    monkeypatch.setattr(host, 'OUT', tmp_path)
    monkeypatch.setattr(host.time, 'time', lambda: 1001.)
    # The watchdog reconciles a stop until the job deadline; with a frozen clock
    # any swallowed cleanup error would spin forever, so a sleep is a failure.
    monkeypatch.setattr(host.time, 'sleep', lambda seconds: (_ for _ in ()).throw(AssertionError('completion cleanup did not stop the Pod')))
    monkeypatch.setattr(host, 'watchdog_identity', lambda: dict(run_id='1', job_id='2', job_deadline=2000.))
    monkeypatch.setattr(host.retained, 'stop_owned_once', confirmed_stop(calls))
    host.watchdog(journal, object(), info)
    assert calls == [host.lifecycle.POD_ID]
    assert journal.rows['retained-completion-cleanup.json']['startup_sha256'] == digest
    assert store.read()[0]['phase'] == 'closed'
    assert host.artifacts.strict_json((tmp_path/'completion-cleanup.json').read_bytes())['status'] == 'confirmed_stopped'
