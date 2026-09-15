import hashlib
import threading
import time

import pytest
from research.kalshi.frankie_boss import granite_runpod_jobs as jobs

BODY = b'{"model":"granite"}'
JOB = 'a' * 64
SHA = hashlib.sha256(BODY).hexdigest()


def settled(store, state):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = store.status(JOB)
        if value['state'] == state:
            return value
        time.sleep(.01)
    raise AssertionError(store.status(JOB))


class Connection:
    def close(self):
        pass


def test_atomic_duplicate_accept_exact_result_and_reopen(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def execute(connection, body):
        calls.append(body); entered.set(); release.wait(3)
        return 503, b'{"error":"model refused"}'
    with jobs.JobStore(tmp_path, connect=Connection, execute=execute) as store:
        assert store.submit(JOB, SHA, BODY)['request_sha256'] == SHA
        assert entered.wait(2)
        for _ in range(5):
            assert store.submit(JOB, SHA, BODY)['state'] == 'running'
        with pytest.raises(jobs.JobConflict):
            store.submit(JOB, hashlib.sha256(b'other').hexdigest(), b'other')
        release.set()
        receipt = settled(store, 'completed')
        assert receipt['result_status'] == 503
        assert receipt['result_sha256'] == hashlib.sha256(store.result(JOB)).hexdigest()
    with jobs.JobStore(tmp_path, connect=Connection, execute=execute) as reopened:
        assert reopened.submit(JOB, SHA, BODY) == receipt
        assert len(calls) == 1


def test_preconnect_failure_may_resume_but_dispatch_loss_cannot(tmp_path):
    attempts = []
    def connect():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionRefusedError()
        return Connection()
    def execute(connection, body):
        raise ConnectionResetError()
    with jobs.JobStore(tmp_path, connect=connect, execute=execute) as store:
        store.submit(JOB, SHA, BODY)
        settled(store, 'not_dispatched')
        store.submit(JOB, SHA, BODY)
        settled(store, 'ambiguous')
        store.submit(JOB, SHA, BODY)
        assert len(attempts) == 2
    with jobs.JobStore(tmp_path, connect=connect, execute=execute) as store:
        assert store.submit(JOB, SHA, BODY)['state'] == 'ambiguous'
        assert len(attempts) == 2


def test_thread_start_failure_and_process_owner_exclusion(tmp_path):
    class NoThread:
        def __init__(self, **kwargs): pass
        def start(self): raise RuntimeError('cannot start')
    with jobs.JobStore(tmp_path, thread_factory=NoThread) as store:
        assert store.submit(JOB, SHA, BODY)['state'] == 'not_dispatched'
        with pytest.raises(jobs.JobStoreBusy):
            jobs.JobStore(tmp_path)


def test_restart_classifies_intent_without_redispatch(tmp_path):
    class DeferredThread:
        def __init__(self, **kwargs): pass
        def start(self): pass
        def join(self): pass
    with jobs.JobStore(tmp_path, thread_factory=DeferredThread) as store:
        store.submit(JOB, SHA, BODY)
        store.submit('b' * 64, SHA, BODY)
        with store._db() as db:
            db.execute("UPDATE jobs SET state='running',dispatch_at=1 WHERE job_id=?", (JOB,))
    with jobs.JobStore(tmp_path) as store:
        assert store.status(JOB)['state'] == 'ambiguous'
        assert store.status('b' * 64)['state'] == 'not_dispatched'
