import hashlib
import pytest

from research.kalshi.frankie_boss import granite_runpod as boot
from research.kalshi.frankie_boss import granite_runpod_proxy as proxy


def test_open_boot_passes_no_deadline_and_uses_its_versioned_proxy(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(boot, 'verify_bundle', lambda *args: {})
    env = boot.startup.launch_environment(max_model_len=131072, served_model='granite42-smoke')
    env.update(RUNPOD_GRANITE_API_KEY='private-test-key-'*3,
               RUNPOD_GRANITE_LIFETIME_SECONDS='none', SUPERVISOR_PROGRAM__APP_COMMAND='verified versioned command')
    env['RUNPOD_SUPERVISOR_COMMAND_SHA256'] = hashlib.sha256(env['SUPERVISOR_PROGRAM__APP_COMMAND'].encode()).hexdigest()
    stages, runs = [], []
    def stage(*args, **kwargs):
        stages.append(kwargs['deadline'])
    def prepare(*args, **kwargs):
        stages.append(kwargs['deadline'])
        return {'argv': ['python3', '--host', '0.0.0.0']}
    result = boot.boot(env, bundle_directory=tmp_path, stage=stage, prepare=prepare,
                       runner=lambda *args, **kwargs: runs.append((args, kwargs)))
    assert stages == [None, None]
    assert result['lifetime_seconds'] is None
    assert runs[0][1]['deadline'] is None
    assert runs[0][0][1] == ['python3', str(tmp_path/'granite_runpod_proxy.py')]
    assert env['RUNPOD_GRANITE_API_KEY'] not in capsys.readouterr().out


def test_open_supervisor_ignores_elapsed_days_but_cleans_up_fatal_child_exit(monkeypatch):
    class Child:
        status = None
        def poll(self):
            return self.status
    children = [Child(), Child()]
    spawned, stopped, sleeps = [], [], []
    def spawn(*args, **kwargs):
        child = children[len(spawned)]
        spawned.append(child)
        return child
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            children[0].status = 1
    monkeypatch.setattr(boot, 'stop_children', lambda values: stopped.extend(values))
    with pytest.raises(RuntimeError, match='subprocess exited'):
        boot.supervise(['backend'], ['proxy'], environment={}, deadline=None,
            clock=lambda: 1000000.*(len(sleeps)+1), popen=spawn, sleep=sleep)
    assert sleeps == [.25, .25, .25]
    assert stopped == children


def test_open_proxy_has_finite_connect_only_and_no_decode_timer(monkeypatch):
    from email.message import Message
    raw = b'{"ok":true}'
    headers = Message()
    headers['Content-Length'] = str(len(raw))
    class Response:
        status = 200
        def read(self, size):
            return raw
        def getheader(self, name, default=None):
            return 'application/json' if name == 'Content-Type' else default
    response = Response()
    response.headers = headers
    timeouts = []
    class Socket:
        def settimeout(self, value):
            timeouts.append(value)
    class Connection:
        sock = Socket()
        def connect(self): pass
        def request(self, *args): pass
        def getresponse(self): return response
        def close(self): pass
    def connect(host, port, timeout):
        timeouts.append(timeout)
        return Connection()
    monkeypatch.setattr(proxy.http.client, 'HTTPConnection', connect)
    monkeypatch.setattr(proxy.threading, 'Timer', lambda *args: pytest.fail('no open decode timer'))
    assert proxy._backend('POST', '/v1/chat/completions', b'{}', None) == raw
    assert timeouts == [10, None]


def test_open_stage_wait_is_unbounded_without_infinite_numeric_timeout(monkeypatch, tmp_path):
    calls, waits = [], []
    class Child:
        def wait(self, timeout):
            waits.append(timeout)
            return 0
    def spawn(argv, **kwargs):
        calls.append(argv)
        return Child()
    monkeypatch.setattr(boot, 'stop_children', lambda *args: None)
    manifest = boot.artifacts.strict_json(boot.artifacts.DEFAULT_MANIFEST.read_bytes())
    boot.stage_process(tmp_path, manifest, deadline=None, popen=spawn)
    assert calls[0][-1] == 'none'
    assert waits == [None]


def test_open_download_command_removes_total_alarm_in_new_directory():
    import ast
    import shlex
    from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
    rows = [{'path': name, 'size': 1, 'sha256': 'a'*64} for name in cloud.package.FILES]
    command = cloud.bootstrap_command(rows, 'b'*64, 'example-bucket',
        directory='/opt/ml/additional-model-data-sources/bootstrap-open-run-v1', open_ended=True)
    tree = ast.parse(shlex.split(command)[2])
    payload = next(node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 100)
    source = bytes.fromhex(payload).decode()
    assert 'signal.alarm(60)' not in source
    assert 'signal.alarm(0)' in source
    assert 'bootstrap-open-run-v1' in source
