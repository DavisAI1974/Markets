import hashlib
import pytest
from research.kalshi.frankie_boss import granite_retained_lifecycle as life


class Journal:
    def __init__(self):
        self.rows = {}
    def get(self, name):
        return self.rows.get(name)
    def put(self, name, value, once=False):
        if once and name in self.rows:
            raise ValueError('duplicate')
        self.rows[name] = value


class Api:
    def __init__(self, journal, fail=False):
        self.calls, self.journal, self.fail = [], journal, fail
    def request(self, method, path, body=None):
        assert method != 'DELETE'
        self.calls.append((method, path, body))
        if method == 'POST':
            assert 'retained-start-intent.json' in self.journal.rows
            if self.fail:
                raise TimeoutError('ambiguous start')
        return {}


def inputs(monkeypatch):
    info = {'pod_id': life.POD_ID, 'intent': {}}
    lease = life.make_lease(info, start=1000.0, duration_seconds=600, request_sha256=hashlib.sha256(b'actual').hexdigest())
    journal = Journal()
    monkeypatch.setattr(life, 'validate_resume', lambda *a: None)
    monkeypatch.setattr(life, 'LocalTokenizerAdmission', Admission)
    admission = dict(request_sha256=hashlib.sha256(b'actual').hexdigest(), input_tokens=100, output_tokens=1200, context=131072)
    return info, lease, journal, admission


def test_retained_start_intent_precedes_action_and_replay_does_not_restart(monkeypatch):
    info, lease, journal, admission = inputs(monkeypatch)
    api = Api(journal)
    arm(api, journal, info, lease, now=1001)
    assert resume(api, journal, info, {}, lease, now=1002,
                            admitted_request=admission)['status'] == 'start_submitted'
    assert resume(api, journal, info, {}, lease, now=1003,
                            admitted_request=admission)['status'] == 'recover_existing_start'
    assert sum(c[0] == 'POST' for c in api.calls) == 1


def test_interrupted_retained_start_is_not_automatically_resubmitted(monkeypatch):
    info, lease, journal, admission = inputs(monkeypatch)
    api = Api(journal, fail=True)
    arm(api, journal, info, lease, now=1001)
    with pytest.raises(TimeoutError):
        resume(api, journal, info, {}, lease, now=1002, admitted_request=admission)
    assert resume(api, journal, info, {}, lease, now=1003,
                            admitted_request=admission)['status'] == 'recover_existing_start'
    assert sum(c[0] == 'POST' for c in api.calls) == 1


def test_retained_start_requires_actual_capacity_and_fresh_independent_arm(monkeypatch):
    info, lease, journal, admission = inputs(monkeypatch)
    api = Api(journal)
    with pytest.raises(ValueError, match='watchdog'):
        resume(api, journal, info, {}, lease, now=1002, admitted_request=admission)
    arm(api, journal, info, lease, now=1001)
    with pytest.raises(ValueError, match='admission'):
        resume(api, journal, info, {}, lease, now=1002,
                         admitted_request=dict(admission, input_tokens=131072))
    with pytest.raises(ValueError, match='admission'):
        resume(api, journal, info, {}, lease, now=1002,
                         admitted_request=dict(admission, context=8192))
    assert not api.calls


def test_deadline_stop_survives_journal_loss(monkeypatch):
    info, lease, journal, admission = inputs(monkeypatch)
    api = Api(journal)
    def unavailable(*args, **kwargs):
        raise OSError('shared journal unavailable')
    journal.get = journal.put = unavailable
    calls = []
    monkeypatch.setattr(life, 'stop_owned_once', lambda *args:
        calls.append(args) or dict(status='confirmed_stopped', data_retained=True))
    assert arm(api, journal, info, lease, now=1480)['data_retained']
    assert len(calls) == 1


IDENTITY = dict(run_id='123', job_id='watchdog', job_deadline=1700)

class Admission:
    evidence_class = 'LOCAL_TOKENIZER_ADMISSION'
    def __init__(self, receipt):
        self.receipt = receipt
    def __call__(self, body):
        assert body == b'actual'
        return self.receipt

def arm(api, journal, info, lease, *, now):
    return life.watchdog_tick(api, journal, info, lease, now=now, watchdog_identity=IDENTITY)

def resume(api, journal, info, manifest, lease, *, now, admitted_request):
    return life.resume_once(api, journal, info, manifest, lease, now=now,
        request_body=b'actual', tokenizer_admission=Admission(admitted_request),
        expected_watchdog_identity=IDENTITY)

def test_review_rejects_fabricated_admission_and_short_watchdog(monkeypatch):
    info, lease, journal, admission = inputs(monkeypatch)
    api = Api(journal)
    with pytest.raises(ValueError, match='actual pinned'):
        life.resume_once(api, journal, info, {}, lease, now=1002,
            request_body=b'actual', tokenizer_admission=lambda body: admission,
            expected_watchdog_identity=IDENTITY)
    with pytest.raises(ValueError, match='job deadline'):
        life.watchdog_tick(api, journal, info, lease, now=1001,
            watchdog_identity=dict(IDENTITY, job_deadline=1600))
    arm(api, journal, info, lease, now=1001)
    result = resume(api, journal, info, {}, lease, now=1002, admitted_request=admission)
    assert result['requires_startup_verification'] is True
