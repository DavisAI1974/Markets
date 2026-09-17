import hashlib
import json
import pytest
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss.tests.test_granite_runpod_cloud_control import intent


def test_watchdog_still_cleans_when_s3_fails_after_arming(monkeypatch, tmp_path):
    clock = [1000]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + 240))
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    calls = []
    monkeypatch.setattr(cloud.control, 'cleanup_once', lambda *args:
                        calls.append(clock[0]) or {'status': 'confirmed_absent', 'pod_id': 'abc'})
    class Journal:
        def put(self, name, value):
            if name != 'watchdog-ready.json':
                raise OSError('S3 unavailable')
        def get(self, name):
            if name == 'intent.json':
                return intent()
            raise OSError('S3 unavailable')
    assert cloud.watchdog(Journal(), object())['status'] == 'confirmed_absent'
    assert calls == [1480]


def test_controller_finishes_cleanup_despite_journal_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    calls = []
    monkeypatch.setattr(cloud.control, 'cleanup_once', lambda *args:
                        calls.append(args) or {'status': 'confirmed_absent', 'pod_id': 'abc'})
    class Journal:
        def put(self, *args):
            raise OSError('S3 unavailable')
    assert cloud.finish(Journal(), object(), intent(), True, 'abc')['status'] == 'confirmed_absent'
    assert len(calls) == 1
    assert calls[0][-1] == 'abc'


def test_unknown_controller_id_is_left_to_watchdog(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    monkeypatch.setattr(cloud.control, 'cleanup_once', lambda *args: pytest.fail('must retain watchdog ownership'))
    class Journal:
        def put(self, *args):
            pass
    assert cloud.finish(Journal(), object(), intent(), False, None)['status'] == 'deferred_to_watchdog'


def test_journal_requires_exact_content_readback(monkeypatch):
    monkeypatch.setattr(cloud.control, 'bounded_call', lambda operation: operation())
    class Client:
        def close(self):
            pass
        def put_object(self, **kwargs):
            assert kwargs['IfNoneMatch'] == '*'
            assert kwargs['ServerSideEncryption'] == 'AES256'
    journal = object.__new__(cloud.Journal)
    journal.client, journal.bucket, journal.prefix = Client(), 'bucket', 'prefix/'
    journal.get_bytes = lambda name: b'changed'
    with pytest.raises(ValueError, match='readback'):
        journal.put_bytes('intent.json', b'original', once=True)


def test_bootstrap_urls_stay_out_of_the_command():
    rows = [{'path': name, 'size': 1, 'sha256': 'a' * 64} for name in cloud.package.FILES]
    command = cloud.bootstrap_command(rows, 'b' * 64, 'expected-bucket')
    assert 'X-Amz-Signature' not in command
    # Decode the generated Python and verify syntax without performing I/O.
    import ast
    import shlex
    expression = ast.parse(shlex.split(command)[2])
    encoded = expression.body[0].value.args[0].func.value.args[0].value
    code = bytes.fromhex(encoded).decode()
    ast.parse(code)
    assert "os.environ.pop('RP_BOOTSTRAP_URLS')" in code
    assert "signal.alarm(60)" in code


def test_wrong_runtime_tokenizer_is_refused():
    admitted = {'model_manifest_sha256': 'manifest'}
    startup = {'image_digest': cloud.control.granite_runpod.startup.IMAGE_DIGEST,
               'mount': {'manifest_sha256': 'manifest'},
               'runtime': {'packages': {'transformers': 'wrong', 'tokenizers': '0.22.2'}}}
    with pytest.raises(ValueError):
        cloud.validate_runtime({'startup': {'startup': startup}}, admitted)


@pytest.mark.parametrize('status', ['termination_pending', 'unresolved', 'absent_in_inventory'])
def test_completed_probe_is_not_success_without_exact_cleanup(status):
    with pytest.raises(RuntimeError, match='cleanup unresolved'):
        cloud.completed_outcome({'outcome': 'completed'}, {'status': status})


def test_lost_create_with_empty_inventory_remains_unresolved(monkeypatch, tmp_path):
    clock = [1000]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + 120))
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    monkeypatch.setattr(cloud.control, 'cleanup_once', lambda *args:
                        {'status': 'absent_in_inventory', 'pod_id': None})
    class Journal:
        def put(self, *args):
            pass
        def get(self, name):
            return intent() if name == 'intent.json' else None
    with pytest.raises(RuntimeError, match='cleanup unresolved'):
        cloud.watchdog(Journal(), object())


def test_late_pod_reconciled_and_exact_id_retained(monkeypatch, tmp_path):
    clock = [1000]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + 120))
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    seen = []
    def cleanup(api, item, pod_id, on_discovered):
        seen.append(pod_id)
        if len(seen) == 1:
            return {'status': 'termination_pending', 'pod_id': 'late123'}
        return {'status': 'confirmed_absent', 'pod_id': pod_id}
    monkeypatch.setattr(cloud.control, 'cleanup_once', cleanup)
    class Journal:
        def put(self, *args):
            pass
        def get(self, name):
            return intent() if name == 'intent.json' else None
    assert cloud.watchdog(Journal(), object())['pod_id'] == 'late123'
    assert seen == [None, 'late123']


def test_reconciled_id_survives_delete_readback_failure(monkeypatch, tmp_path):
    from research.kalshi.frankie_boss.tests.test_granite_runpod_cloud_control import pod
    clock = [1000]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + 120))
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    calls = []
    class API:
        def request(self, method, path, body=None):
            calls.append((method, path))
            if len(calls) == 1:
                return {'pods': [pod()]}
            if len(calls) == 2:
                return pod()
            if method == 'DELETE':
                return None
            if len(calls) == 4:
                raise TimeoutError('readback failed')
            assert path == '/v2/pods/abc123'  # Inventory would now be empty.
            raise cloud.control.ProviderError(404)
    class Journal:
        def put(self, *args):
            pass
        def get(self, name):
            return intent() if name == 'intent.json' else None
    assert cloud.watchdog(Journal(), API()) == {'status': 'confirmed_absent', 'pod_id': 'abc123'}
    assert len(calls) == 5
