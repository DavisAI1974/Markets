"""New transport seams with synthetic backend bytes; no model execution."""
import hashlib
import http.client
import json
import threading
import time

import pytest
from research.kalshi.frankie_boss import granite_runpod_jobs as jobs
from research.kalshi.frankie_boss import granite_runpod_proxy as proxy
from research.kalshi.frankie_boss import granite_runpod as runpod
from research.kalshi.frankie_boss import granite_runpod_package as package

KEY = 'synthetic-private-' + 'a' * 40
BODY = b'{"model":"granite","messages":[{"role":"user","content":"hello"}],"max_tokens":1200,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}'
JOB = 'c' * 64


def test_job_http_accept_health_poll_result_and_no_direct_fallback(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    class Connection:
        def close(self): pass
    def execute(connection, body):
        calls.append(body); entered.set(); release.wait(5)
        return 200, b'{"choices":[]}'
    monkeypatch.setattr(proxy, 'JobStore', lambda directory, **kw:
                        jobs.JobStore(directory, connect=Connection, execute=execute, **kw))
    monkeypatch.setattr(proxy, '_backend', lambda *args: b'{"status":"ok"}')
    server = proxy.make_server(KEY, ('127.0.0.1', 0), model='granite',
                               transport_protocol='jobs_v1', spool=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    def request(method, path, body=b'', auth=KEY, digest=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        headers = {'Authorization': 'Bearer ' + auth, 'Content-Type': 'application/json'}
        if method == 'POST': headers['X-Granite-Request-SHA256'] = digest or hashlib.sha256(body).hexdigest()
        try:
            connection.request(method, path, body, headers)
            result = connection.getresponse()
            return result.status, result.read()
        finally: connection.close()
    try:
        path = '/v1/jobs/' + JOB
        assert request('GET', path)[0] == 404
        assert request('POST', path, BODY, auth='wrong')[0] == 401
        assert request('POST', path, BODY, digest='0' * 64)[0] == 400
        assert request('POST', path, BODY)[0] == 202
        assert entered.wait(2)
        assert request('GET', '/health') == (200, b'{"status":"ok"}')
        assert json.loads(request('GET', path)[1])['state'] == 'running'
        assert request('GET', path + '/result')[0] == 202
        assert request('POST', path, BODY)[0] == 202
        assert request('POST', path, BODY.replace(b'hello', b'changed'))[0] == 409
        assert request('POST', '/v1/chat/completions', BODY)[0] == 404
        release.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            code, raw = request('GET', path + '/result')
            if code == 200: break
            time.sleep(.01)
        assert (code, raw) == (200, b'{"choices":[]}')
        assert calls == [BODY]
    finally:
        release.set(); server.shutdown(); server.server_close(); thread.join()


def test_jobs_protocol_survives_child_and_parent_boot_checks(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(runpod.__file__).parent))
    from test_granite_run_artifacts import fixture
    model = tmp_path / 'model'; model.mkdir()
    manifest, _ = fixture(model)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_bytes(runpod.artifacts.canonical(manifest))
    monkeypatch.setattr(runpod.artifacts, 'DEFAULT_MANIFEST', manifest_path)
    monkeypatch.setattr(runpod, 'verify_bundle', lambda *args: {})
    startup = runpod.startup
    direct = startup.launch_environment(max_model_len=131072, served_model='granite')
    env = startup.launch_environment(max_model_len=131072, served_model='granite', transport_protocol='jobs_v1')
    assert env == dict(direct, GRANITE_TRANSPORT_PROTOCOL='jobs_v1')
    facts = dict(packages={'vllm': '0.20.2', 'model-hosting-container-standards': '0.1.15'},
                 gpu_count=1, source_sha256=runpod.artifacts.strict_json(startup.IMAGE_IDENTITY_FILE.read_bytes())['source_sha256'])
    env.update(RUNPOD_GRANITE_API_KEY=KEY, RUNPOD_GRANITE_LIFETIME_SECONDS='none',
               SUPERVISOR_PROGRAM__APP_COMMAND='synthetic-reviewed-command', RUNPOD_BUNDLE_SHA256='d' * 64)
    env['RUNPOD_SUPERVISOR_COMMAND_SHA256'] = hashlib.sha256(env['SUPERVISOR_PROGRAM__APP_COMMAND'].encode()).hexdigest()
    receipts = []
    def prepare(directory, manifest, environment, **kw):
        # Exercise the real parent child-receipt verifier with a synthetic child
        # that performs the same startup validation, without launching processes.
        class Child:
            def wait(self, timeout): return 0
        def popen(argv, **opts):
            receipt = startup.prepare_startup(directory, manifest, opts['env'], runtime_facts=lambda: facts)
            runpod.artifacts.save_receipt(argv[-1], receipt)
            return Child()
        return runpod.prepare_process(directory, manifest, environment, popen=popen, **kw)
    monkeypatch.setattr(runpod, 'stop_children', lambda children: None)
    evidence = runpod.boot(env, directory=model, stage=lambda *args, **kw: None, prepare=prepare,
                          runner=lambda *args, **kw: receipts.append(kw))
    assert evidence['durable_job_protocol'] == 'jobs_v1'
    assert evidence['startup']['environment']['GRANITE_TRANSPORT_PROTOCOL'] == 'jobs_v1'
    assert receipts[0]['environment']['GRANITE_TRANSPORT_PROTOCOL'] == 'jobs_v1'
    assert receipts[0]['deadline'] is None
    assert KEY not in json.dumps(evidence)


def test_new_server_module_is_pinned_in_both_package_verifiers(tmp_path):
    rows = []
    assert 'granite_runpod_jobs.py' in package.FILES
    for name in package.FILES:
        raw = ('synthetic ' + name).encode()
        (tmp_path / name).write_bytes(raw)
        rows.append(dict(path=name, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    raw = json.dumps(dict(schema='GRANITE_RUNPOD_BUNDLE_V1', files=rows)).encode()
    (tmp_path / 'runpod_bundle.json').write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert runpod.verify_bundle(tmp_path, digest)['files'] == rows
    assert 'granite_runpod_jobs.py' in package.preexec_code(rows, digest)
    (tmp_path / 'granite_runpod_jobs.py').write_bytes(b'changed')
    with pytest.raises(ValueError): runpod.verify_bundle(tmp_path, digest)


def test_actual_client_and_store_recover_lost_accept_once_then_replay_offline(tmp_path, monkeypatch):
    import asyncio
    from research.kalshi.frankie_boss import granite_durable_job_client as client_module
    from research.kalshi.frankie_boss.tests.test_granite_durable_job_client import configured, raw_response
    calls, backend_calls = [], []
    class Connection:
        def close(self): pass
    def execute(connection, body):
        backend_calls.append(body)
        return 200, raw_response()
    monkeypatch.setattr(client_module, 'POLL_SECONDS', .001)
    with jobs.JobStore(tmp_path / 'server', connect=Connection, execute=execute) as store:
        def exchange(pod, method, path, body, key, timeout):
            assert timeout == 80
            calls.append((method, path))
            job_id = path.split('/')[3]
            if method == 'POST':
                store.submit(job_id, hashlib.sha256(body).hexdigest(), body)
                raise http.client.RemoteDisconnected('synthetic lost accepted response')
            value = store.status(job_id)
            if value is None: return 404, b'{}'
            if path.endswith('/result'):
                raw = store.result(job_id)
                if raw is not None: return 200, raw
                return 202, json.dumps(value).encode()
            return 200, json.dumps(value).encode()
        client, request = configured(tmp_path / 'client', exchange)
        response = asyncio.run(client._durable_transport(request, {}))
        assert response.text == 'retained result'
        assert len(backend_calls) == sum(method == 'POST' for method, _ in calls) == 1
        assert len({path.removesuffix('/result') for _, path in calls}) == 1
        replay, _ = configured(tmp_path / 'client', lambda *args: pytest.fail('offline replay performed HTTP'),
                               key=None, recovery=True)
        assert asyncio.run(replay._durable_transport(request, {})) == response
