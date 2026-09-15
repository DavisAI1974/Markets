import io
import json
import threading

import pytest

from research.kalshi.frankie_boss.granite_active_run import ActiveRunStore, completion_cleanup


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class S3:
    def __init__(self):
        self.raw, self.version = None, 0
        self.lock = threading.Lock()

    def get_object(self, **kwargs):
        with self.lock:
            if self.raw is None:
                raise Missing()
            return dict(Body=io.BytesIO(self.raw), ContentLength=len(self.raw), ETag=str(self.version))

    def put_object(self, **kwargs):
        with self.lock:
            if (kwargs.get('IfNoneMatch') == '*' and self.raw is not None
                    or 'IfMatch' in kwargs and kwargs['IfMatch'] != str(self.version)):
                raise ValueError('conditional conflict')
            self.raw = kwargs['Body']
            self.version += 1


class Journal:
    def __init__(self):
        self.rows = {}

    def get(self, name):
        return self.rows.get(name)

    def put(self, name, value, **kwargs):
        if kwargs.get('once') and name in self.rows:
            raise ValueError('exists')
        self.rows[name] = value


def test_old_completion_cannot_stop_new_owner_and_duplicate_observer_cannot_stop_twice():
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    journal = Journal()
    calls = []
    store.claim('a'*64)
    def stop(*args):
        calls.append(1)
        nested = completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64, stop)
        assert nested['status'] == 'cleanup_pending'
        return dict(status='confirmed_stopped', pod_id='pod', data_retained=True)
    completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64, stop)
    store.claim('b'*64)
    completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64, stop)
    assert calls == [1]
    assert store.read()[0]['startup_sha256'] == 'b'*64
    assert completion_cleanup(None, Journal(), store, {'intent': {}}, 'a'*64, stop)['status'] == 'not_active_run'


def test_crash_before_memo_preserves_stopping_even_if_pod_has_exited():
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    store.claim('a'*64)
    def lost(*args):
        raise OSError('stop outcome unknown')
    with pytest.raises(OSError):
        completion_cleanup(None, Journal(), store, {'intent': {}}, 'a'*64, lost)
    assert completion_cleanup(None, Journal(), store, {'intent': {}}, 'a'*64, lost)['status'] == 'cleanup_pending'
    with pytest.raises(ValueError):
        store.claim('b'*64)


def test_completed_memo_recovers_release_but_pending_memo_never_releases():
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    store.claim('a'*64)
    store.begin_stop('a'*64)
    journal = Journal()
    journal.rows['retained-completion-cleanup.json'] = dict(startup_sha256='a'*64, status='stop_pending')
    with pytest.raises(ValueError):
        completion_cleanup(None, journal, store, {}, 'a'*64, None)
    assert store.read()[0]['phase'] == 'stopping'
    journal.rows['retained-completion-cleanup.json'] = dict(startup_sha256='a'*64,
        status='confirmed_stopped', pod_id='pod', data_retained=True)
    completion_cleanup(None, journal, store, {}, 'a'*64, None)
    assert store.read()[0]['phase'] == 'closed'


def test_claim_race_has_only_one_winner():
    client = S3()
    store = ActiveRunStore(client, 'bucket', 'pod')
    barrier = threading.Barrier(2)
    original = store.read
    def read():
        result = original()
        if result[0] is None:
            barrier.wait()
        return result
    store.read = read
    outcomes = []
    def claim(digest):
        try:
            store.claim(digest)
            outcomes.append('won')
        except ValueError:
            outcomes.append('lost')
    workers = [threading.Thread(target=claim, args=(x*64,)) for x in ('a', 'b')]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(3)
    assert sorted(outcomes) == ['lost', 'won']


def test_acknowledged_pending_stop_resumes_read_only_and_releases(monkeypatch):
    from research.kalshi.frankie_boss import granite_active_run as runs
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    store.claim('a'*64)
    journal = Journal()
    calls = []
    class API:
        def request(self, method, path):
            calls.append((method, path))
            return {'status': 'EXITED'}
    monkeypatch.setattr(runs, '_owned', lambda pod, intent, pod_id: pod)
    monkeypatch.setattr(runs, '_stop_result', lambda pod, pod_id: dict(
        status='confirmed_stopped', pod_id=pod_id, data_retained=True))
    def stop(api, intent, pod_id, on_ack=None):
        calls.append(('POST', pod_id))
        on_ack()
        return dict(status='stop_pending', pod_id=pod_id, data_retained=True)
    assert runs.completion_cleanup(API(), journal, store, {'intent': {}}, 'a'*64,
        stop, acknowledged_stop=True)['status'] == 'stop_pending'
    assert store.read()[0]['phase'] == 'stopping'
    result = runs.completion_cleanup(API(), journal, store, {'intent': {}}, 'a'*64,
        stop, acknowledged_stop=True)
    assert result['status'] == 'confirmed_stopped'
    assert calls == [('POST', 'pod'), ('GET', '/v2/pods/pod')]
    assert store.read()[0]['phase'] == 'closed'


def test_unknown_stop_without_ack_never_reads_or_releases():
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    store.claim('a'*64)
    journal = Journal()
    def stop(*args, on_ack=None):
        raise OSError('unknown dispatch outcome')
    with pytest.raises(OSError):
        completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64,
            stop, acknowledged_stop=True)
    assert completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64,
        stop, acknowledged_stop=True)['status'] == 'cleanup_pending'
    assert store.read()[0]['phase'] == 'stopping'


def test_stop_helper_persists_ack_before_readback(monkeypatch):
    from research.kalshi.frankie_boss import granite_cloud_resume as resume
    monkeypatch.setattr(resume.control, 'validate_intent', lambda value: None)
    monkeypatch.setattr(resume, '_owned', lambda pod, intent, pod_id=None: pod)
    monkeypatch.setattr(resume, '_stop_result', lambda pod, pod_id: {'status': 'stop_pending'})
    events = []
    class API:
        def request(self, method, path, *args):
            events.append(method)
            return {}
    resume.stop_owned_once(API(), {}, 'pod', on_ack=lambda: events.append('durable_ack'))
    assert events == ['GET', 'GET', 'POST', 'durable_ack', 'GET']


def test_ack_write_transient_or_lost_readback_recovers_without_second_stop():
    for persisted in (False, True):
        store = ActiveRunStore(S3(), 'bucket', 'pod')
        store.claim('a'*64)
        class FlakyJournal(Journal):
            attempts = 0
            def put(self, name, value, **kwargs):
                if name == 'retained-stop-acknowledged.json':
                    self.attempts += 1
                    if self.attempts == 1:
                        if persisted:
                            super().put(name, value, **kwargs)
                        raise OSError('transient acknowledgement write/readback')
                return super().put(name, value, **kwargs)
        journal = FlakyJournal()
        calls = []
        def stop(api, intent, pod_id, on_ack):
            calls.append('stop')
            on_ack()
            return dict(status='confirmed_stopped', pod_id=pod_id, data_retained=True)
        result = completion_cleanup(None, journal, store, {'intent': {}}, 'a'*64,
                                    stop, acknowledged_stop=True)
        assert result['status'] == 'confirmed_stopped'
        assert calls == ['stop']
        assert store.read()[0]['phase'] == 'closed'
