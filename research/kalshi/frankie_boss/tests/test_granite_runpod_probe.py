import hashlib
import json
import sqlite3
from email.message import Message

import pytest
from research.kalshi.frankie_boss import granite_runpod_probe as probe

KEY = 'test-only-' + 'a' * 40
REQUEST = b'{"model":"granite","messages":[{"role":"user","content":"Say OK."}],"max_tokens":16}'


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.admission, 'validate_receipt', lambda value, digest: REQUEST)
    kwargs = dict(pod_id='testpod1', expected_pod_id='testpod1',
                  admission_receipt={'input_tokens': 3, 'output_tokens': 16, 'context': 131072},
                  expected_admission_sha256='a' * 64, journal_path=tmp_path/'probe.sqlite', api_key=KEY)
    return kwargs


def success():
    return json.dumps({'object': 'chat.completion', 'model': 'granite', 'choices': [
        {'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'READY'}}],
        'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}}).encode()


@pytest.mark.parametrize('fail', [False, True])
def test_durable_before_io_and_never_resend(setup, fail):
    calls = []
    def exchange(pod_id, method, path, body, key, timeout):
        calls.append(method)
        assert pod_id == 'testpod1' and key == KEY and 0 < timeout <= 80
        if method == 'GET':
            return 200, b'{"status":"ok"}'
        with sqlite3.connect(setup['journal_path']) as other:
            row = other.execute('SELECT request_sha256, outcome FROM attempts WHERE pod_id=?', (pod_id,)).fetchone()
        assert row == (hashlib.sha256(REQUEST).hexdigest(), None)
        assert body == REQUEST
        if fail:
            raise TimeoutError('secret ' + KEY)
        return 200, success()
    receipt = probe.run_probe(**setup, exchange=exchange)
    assert receipt.outcome == ('transport_error' if fail else 'completed')
    with pytest.raises(ValueError, match='attempt'):
        probe.run_probe(**setup, exchange=exchange)
    assert calls == ['GET', 'POST']
    assert KEY not in setup['journal_path'].read_bytes().decode('latin1')


def test_admission_failure_before_health(setup, monkeypatch):
    def refuse(*args):
        raise ValueError('invalid admission')
    monkeypatch.setattr(probe.admission, 'validate_receipt', refuse)
    with pytest.raises(ValueError):
        probe.run_probe(**setup, exchange=lambda *args: pytest.fail('HTTP'))


def test_pod_pin_before_http(setup):
    setup['expected_pod_id'] = 'other'
    with pytest.raises(ValueError):
        probe.run_probe(**setup, exchange=lambda *args: pytest.fail('HTTP'))


def test_bounded_health_no_inference(setup):
    calls = []
    def exchange(*args):
        calls.append(args[1])
        return 503, b'sensitive error'
    receipt = probe.run_probe(**setup, exchange=exchange)
    assert receipt.outcome == 'health_unavailable'
    assert calls == ['GET'] * 3


@pytest.mark.parametrize('raw,status', [(b'x' * 65537, 200), (b'bad', 200),
                                      (KEY.encode(), 200), (success(), 302), (b'secret', 500)],
                         ids=['oversize', 'malformed', 'secret', 'redirect', 'error'])
def test_refused_response_sanitized(setup, raw, status):
    def exchange(pod, method, *args):
        return (200, b'{"status":"ok"}') if method == 'GET' else (status, raw)
    receipt = probe.run_probe(**setup, exchange=exchange)
    assert receipt.outcome == 'response_refused' and receipt.response_base64 is None


def test_cancel_leaves_attempt(setup):
    def exchange(pod, method, *args):
        if method == 'POST':
            raise KeyboardInterrupt()
        return 200, b'{"status":"ok"}'
    with pytest.raises(KeyboardInterrupt):
        probe.run_probe(**setup, exchange=exchange)
    with pytest.raises(ValueError, match='attempt'):
        probe.run_probe(**setup, exchange=lambda *args: pytest.fail('HTTP'))


def test_changed_admission_cannot_renew_attempt(setup):
    def exchange(pod, method, *args):
        return (200, b'{"status":"ok"}') if method == 'GET' else (200, success())
    probe.run_probe(**setup, exchange=exchange)
    setup['expected_admission_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='attempt'):
        probe.run_probe(**setup, exchange=lambda *args: pytest.fail('HTTP'))


@pytest.mark.parametrize('change', [
    {'model': 'other'}, {'usage': {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6}},
    {'usage': {'prompt_tokens': 3, 'completion_tokens': 17, 'total_tokens': 20}},
    {'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 99}},
    {'choices': [{'index': 0, 'finish_reason': 'length', 'message': {'role': 'assistant', 'content': 'READY'}}]},
    {'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'other'}}]},
])
def test_exact_smoke_success_contract(setup, change):
    response = json.loads(success())
    response.update(change)
    def exchange(pod, method, *args):
        return (200, b'{"status":"ok"}') if method == 'GET' else (200, json.dumps(response).encode())
    assert probe.run_probe(**setup, exchange=exchange).outcome == 'response_refused'


def test_whole_budget_clamps_post(setup, monkeypatch):
    clock = [0]
    monkeypatch.setattr(probe.time, 'monotonic', lambda: clock[0])
    def exchange(pod, method, path, body, key, timeout):
        if method == 'GET':
            clock[0] = 89
            return 200, b'{"status":"ok"}'
        assert timeout == 1
        clock[0] = 91
        return 200, success()
    receipt = probe.run_probe(**setup, exchange=exchange)
    assert receipt.attempted and receipt.outcome == 'transport_error'


def test_concrete_https_fixed_origin_and_framing(monkeypatch):
    seen = []
    class Response:
        status = 200
        headers = Message()
        headers['Content-Length'] = '15'
        headers['Content-Type'] = 'application/json'
        def getheader(self, key, default):
            return self.headers.get(key, default)
        def read(self, size):
            assert size == 15
            return b'{"status":"ok"}'
    class Connection:
        sock = object()
        def __init__(self, host, port, **kwargs):
            assert host == 'testpod1-8081.proxy.runpod.net' and port == 443
            assert kwargs['context'].check_hostname
        def connect(self):
            pass
        def request(self, method, path, body, headers):
            seen.append((method, path, body, headers))
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(probe.http.client, 'HTTPSConnection', Connection)
    assert probe.https_exchange('testpod1', 'GET', '/health', b'', KEY, 5) == (200, b'{"status":"ok"}')
    assert seen == [('GET', '/health', b'', {'Authorization': 'Bearer ' + KEY,
        'Content-Type': 'application/json', 'Content-Length': '0', 'Connection': 'close'})]


def test_expired_connect_never_transmits(monkeypatch):
    clock = [0]
    monkeypatch.setattr(probe.time, 'monotonic', lambda: clock[0])
    class Connection:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self):
            clock[0] = 6
        def request(self, *args, **kwargs):
            pytest.fail('transmitted after deadline')
        def close(self):
            pass
    monkeypatch.setattr(probe.http.client, 'HTTPSConnection', Connection)
    with pytest.raises(TimeoutError):
        probe.https_exchange('testpod1', 'GET', '/health', b'', KEY, 5)


def test_admission_composition_frozen_request(tmp_path, monkeypatch):
    from test_granite_runpod_admission import admitted, digest
    directory = tmp_path/'tokenizer'
    directory.mkdir()
    receipt, _ = admitted(directory)
    kwargs = dict(pod_id='testpod1', expected_pod_id='testpod1', admission_receipt=receipt,
                  expected_admission_sha256=digest(receipt), journal_path=tmp_path/'probe.sqlite', api_key=KEY)
    # The production helper refuses synthetic tokenizer evidence before all I/O.
    with pytest.raises(ValueError):
        probe.run_probe(**kwargs, exchange=lambda *args: pytest.fail('HTTP'))
    validate = probe.admission.validate_receipt
    monkeypatch.setattr(probe.admission, 'validate_receipt',
                        lambda value, pin: validate(value, pin, allow_synthetic=True))
    sent = []
    def exchange(pod, method, path, body, key, timeout):
        if method == 'GET':
            return 200, b'{"status":"ok"}'
        sent.append(body)
        response = json.loads(success())
        response['model'] = 'granite42-smoke'
        return 200, json.dumps(response).encode()
    assert probe.run_probe(**kwargs, exchange=exchange).outcome == 'completed'
    assert sent == [probe.admission.request_bytes()]


def test_json_escaped_credential_echo_suppressed(setup):
    response = success()[:-1] + b',"metadata":"' + ''.join('\\u%04x' % ord(c) for c in KEY).encode() + b'"}'
    assert KEY.encode() not in response
    def exchange(pod, method, *args):
        return (200, b'{"status":"ok"}') if method == 'GET' else (200, response)
    assert probe.run_probe(**setup, exchange=exchange).response_base64 is None
