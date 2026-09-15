import hashlib
import json

import pytest

from research.kalshi.frankie_boss import granite_retained_lifecycle as life
from research.kalshi.frankie_boss import granite_retained_host as host
from research.kalshi.frankie_boss.tests.test_granite_active_run import ActiveRunStore, S3, Journal
from research.kalshi.frankie_boss.tests.test_granite_startup_pins import candidate


def test_start_claim_precedes_action_and_failure_never_authorizes_repeat(monkeypatch):
    body = b'{}'
    digest = hashlib.sha256(body).hexdigest()
    info = dict(pod_id=life.POD_ID, intent={})
    now = 1789430400.
    startup = life.make_startup(info, start=now, request_sha256=digest,
        local_ready=dict(request_sha256=digest, host_instance_id='local-ready-instance', admitted_at=now-1))
    startup_hash = life.check_startup(startup, info)
    config = candidate()
    journal = Journal()
    store = ActiveRunStore(S3(), 'bucket', life.POD_ID)
    identity = dict(run_id='1', job_id='2', job_deadline=now+1000)
    journal.rows['retained-observer.json'] = dict(startup_sha256=startup_hash, at=now, watchdog_identity=identity)
    class Admission:
        evidence_class = 'LOCAL_TOKENIZER_ADMISSION'
        def __call__(self, raw):
            return dict(request_sha256=digest, context=131072, input_tokens=92000, output_tokens=1200)
    monkeypatch.setattr(life, 'LocalTokenizerAdmission', Admission)
    monkeypatch.setattr(life, 'validate_resume', lambda *args: None)
    calls = []
    class Api:
        def request(self, method, path, body=None):
            if method == 'GET':
                return dict(env={'RP_BOOTSTRAP_URLS': json.dumps({name:
                    'https://bucket.s3.amazonaws.com/'+name+'?X-Amz-Date=20260915T000000Z&X-Amz-Expires=900'
                    for name in ('example.py', 'runpod_bundle.json')})})
            calls.append(path)
            assert store.read()[0]['startup_sha256'] == startup_hash
            assert journal.get('retained-start-intent.json')
            raise OSError('response lost')
    kwargs = dict(now=now, request_body=body, tokenizer_admission=Admission(),
        expected_watchdog_identity=identity, active_runs=store, runtime_configuration=config)
    with pytest.raises(OSError):
        life.start_once(Api(), journal, info, {}, startup, **kwargs)
    assert journal.get('retained-start-failure.json')['status'] == 'start_outcome_unknown'
    assert life.start_once(Api(), journal, info, {}, startup, **kwargs)['status'] == 'observe_existing_start'
    assert len(calls) == 1


def test_bad_telemetry_is_counted_and_does_not_poison_valid_frame(monkeypatch):
    monkeypatch.setattr(host.time, 'time', lambda: 2000.)
    records = {}
    for frame in (None, {'source': 'container', 'ts': 'bad'},
                  {'source': 'container', 'ts': '1970-01-01T00:16:41Z', 'line': 'GRANITE_PROGRESS {oops'}):
        host.keep_startup_frame(records, frame, {'start': 1000.})
    host.keep_startup_frame(records, dict(source='container', ts='1970-01-01T00:16:41Z',
        line='GRANITE_RUNPOD_STARTUP {"startup":{}}'), {'start': 1000.})
    assert records['malformed_frames'] == 3
    assert records['startup'] == {'startup': {}}


def test_runtime_verifier_uses_explicit_long_context_pin():
    cloud = host.cloud
    startup = dict(image_digest=cloud.control.granite_runpod.startup.IMAGE_DIGEST,
        mount=dict(manifest_sha256='a'*64),
        runtime=dict(packages=cloud.admission.TOKENIZER_VERSIONS, gpu_count=1,
            gpu='NVIDIA L40S', gpu_total_memory=47665709056),
        environment=dict(GRANITE_MAX_MODEL_LEN='131072', GRANITE_SERVED_MODEL='granite42-smoke'))
    records = dict(startup=dict(startup=startup), disk=dict(free_bytes=30000000000))
    cloud.validate_runtime(records, dict(model_manifest_sha256='a'*64, context=131072))
    with pytest.raises(ValueError):
        cloud.validate_runtime(records, dict(model_manifest_sha256='a'*64))
