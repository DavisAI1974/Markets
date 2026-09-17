import contextlib
import http.client
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from research.kalshi.frankie_boss import granite_runpod_proxy as proxy

KEY = 'test-only-' + 'a' * 40
BODY = b'{"model":"granite","messages":[{"role":"user","content":"hello"}],"stream":false,"max_tokens":1200,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}'


@contextlib.contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


@pytest.fixture
def service(monkeypatch):
    calls = []
    response = {'status': 200, 'body': b'{"choices":[]}'}

    class Backend(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.do_POST()

        def do_POST(self):
            calls.append((self.command, self.path, dict(self.headers),
                          self.rfile.read(int(self.headers.get('Content-Length', 0)))))
            time.sleep(response.get('delay', 0))
            self.send_response(response['status'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(response.get('length', len(response['body']))))
            self.send_header('X-Backend-Secret', KEY)
            self.end_headers()
            try:
                if response.get('body_delay'):
                    for byte in response['body']:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(response['body_delay'])
                else:
                    self.wfile.write(response['body'])
            except OSError:
                pass

    with running(HTTPServer(('127.0.0.1', 0), Backend)) as backend:
        monkeypatch.setattr(proxy, 'BACKEND_PORT', backend.server_port)
        with running(proxy.make_server(KEY, ('127.0.0.1', 0), model='granite')) as front:
            def request(path='/v1/chat/completions', body=BODY, method='POST', auth=KEY, headers=None):
                conn = http.client.HTTPConnection('127.0.0.1', front.server_port, timeout=3)
                hs = {'Content-Type': 'application/json'}
                if auth is not None:
                    hs['Authorization'] = 'Bearer ' + auth
                hs.update(headers or {})
                conn.request(method, path, body, hs)
                received = conn.getresponse()
                result = received.status, dict(received.getheaders()), received.read()
                conn.close()
                return result
            yield request, calls, response, front


@pytest.mark.parametrize('path,auth,body,status', [
    ('/v1/chat/completions', None, BODY, 401),
    ('/v1/chat/completions', 'wrong', BODY, 401),
    ('/metrics', KEY, BODY, 404),
    ('/v1/chat/completions?x=1', KEY, BODY, 404),
    ('/v1/chat/completions', KEY, b'{"stream":true}', 400),
    ('/v1/chat/completions', KEY, b'{"messages":[{"content":[{"image_url":"https://invalid"}]}]}', 400),
    ('/v1/chat/completions', KEY, b'{"model":"a","model":"b"}', 400),
], ids=['missing-auth', 'wrong-auth', 'metrics', 'query', 'stream', 'media', 'duplicate-json'])
def test_refused_without_backend(service, path, auth, body, status):
    request, calls, _, _ = service
    assert request(path, auth=auth, body=body)[0] == status
    assert calls == []


def test_oversized_declared_body_refused_before_body_send(service):
    request, calls, _, _ = service
    # Sending an entire rejected body races the server's close and can yield a
    # platform-specific TCP reset. Admission is decided from headers alone.
    assert request(body=None, headers={'Content-Length': str(proxy.MAX_REQUEST + 1)})[0] == 413
    assert not calls


def test_forward_only_body_and_minimal_health(service):
    request, calls, _, _ = service
    status, headers, body = request(headers={'X-Forwarded-Host': 'evil', 'Forwarded': 'secret'})
    assert status == 200 and body == b'{"choices":[]}'
    assert 'X-Backend-Secret' not in headers
    assert calls[0][0:2] == ('POST', '/v1/chat/completions') and calls[0][3] == BODY
    assert not any(k.lower() in ('authorization', 'forwarded', 'x-forwarded-host') for k in calls[0][2])
    assert request('/health', method='GET', body=None)[2] == b'{"status":"ok"}'


@pytest.mark.parametrize('status,body,length', [(500, b'secret', 6), (302, b'', 0),
                                               (200, b'not json', 8), (200, b'{}', 8),
                                               (200, b'{}', 4 * 1024 * 1024 + 1)])
def test_sanitized_backend_failure(service, status, body, length):
    request, _, response, _ = service
    response.update(status=status, body=body, length=length)
    result = request()
    assert result[0] == 502 and result[2] == b'{"error":"upstream unavailable"}'


@pytest.mark.parametrize('key', ['', 'short', 'a' * 257, 'a' * 40 + '\n'])
def test_invalid_key_never_listens(key):
    with pytest.raises(ValueError, match='secret'):
        proxy.make_server(key, ('127.0.0.1', 0), model='granite')


@pytest.mark.parametrize('change', [
    {'model': 'other'}, {'max_tokens': 131073}, {'max_tokens': True},
    {'temperature': 0.1}, {'stream': True}, {'stream': 0},
    {'chat_template_kwargs': {'enable_thinking': 0}}, {'tools': []},
    {'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': 'https://example.com'}]}]},
])
def test_chat_contract(service, change):
    request, calls, _, _ = service
    payload = json.loads(BODY)
    payload.update(change)
    assert request(body=json.dumps(payload).encode())[0] == 400
    assert not calls


@pytest.mark.parametrize('extra,status', [
    (b'Content-Length: 0\r\nContent-Length: 0\r\n', 400),
    (b'Transfer-Encoding: chunked\r\n', 400),
    (b'Content-Encoding: gzip\r\nContent-Length: 0\r\n', 400),
    (b'Content-Length: -1\r\n', 400),
    (b'X-Long: ' + b'a' * 17000 + b'\r\nContent-Length: 0\r\n', 431),
], ids=['duplicate-length', 'chunked', 'gzip', 'negative-length', 'header-limit'])
def test_raw_framing(service, extra, status):
    _, calls, _, front = service
    with socket.create_connection(('127.0.0.1', front.server_port), timeout=2) as sock:
        sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '
                     + KEY.encode() + b'\r\nContent-Type: application/json\r\n' + extra + b'\r\n')
        assert str(status).encode() in sock.recv(65536).split(b'\r\n')[0]
    assert not calls


def test_unknown_method_does_not_echo(service, capsys):
    _, calls, _, front = service
    with socket.create_connection(('127.0.0.1', front.server_port), timeout=2) as sock:
        sock.sendall(b'SECRET_METHOD / HTTP/1.0\r\n\r\n')
        received = b''
        while chunk := sock.recv(65536):
            received += chunk
    assert b'501' in received and b'SECRET_METHOD' not in received
    assert not calls and 'SECRET_METHOD' not in capsys.readouterr().err


def test_backend_deadline_and_health_failure(service, monkeypatch):
    request, calls, response, _ = service
    monkeypatch.setattr(proxy, 'BACKEND_SECONDS', .1)
    response['delay'] = .3
    started = time.monotonic()
    assert request()[0] == 502
    assert time.monotonic() - started < 1
    response['delay'] = 0
    response['status'] = 500
    assert request('/health', method='GET', body=None)[0] == 503


def test_client_whole_deadline(service, monkeypatch):
    _, calls, _, front = service
    monkeypatch.setattr(proxy, 'CLIENT_SECONDS', .1)
    with socket.create_connection(('127.0.0.1', front.server_port), timeout=2) as sock:
        sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\n')
        time.sleep(.2)
        assert sock.recv(65536) == b''
    assert not calls


def test_secret_echo_is_suppressed(service):
    request, _, response, _ = service
    response['body'] = json.dumps({'secret': KEY}).encode()
    assert KEY.encode() not in request()[2]


def test_slow_body_hits_total_deadline(service, monkeypatch):
    request, _, response, _ = service
    monkeypatch.setattr(proxy, 'BACKEND_SECONDS', .15)
    response['body_delay'] = .06
    started = time.monotonic()
    assert request()[0] == 502
    assert time.monotonic() - started < .6


def test_health_requires_auth(service):
    request, calls, _, _ = service
    assert request('/health', method='GET', body=None, auth=None)[0] == 401
    assert not calls


def test_duplicate_authorization_is_refused(service):
    _, calls, _, front = service
    with socket.create_connection(('127.0.0.1', front.server_port), timeout=2) as sock:
        line = b'Authorization: Bearer ' + KEY.encode() + b'\r\n'
        sock.sendall(b'GET /health HTTP/1.0\r\n' + line + line + b'\r\n')
        assert b'401' in sock.recv(65536).split(b'\r\n')[0]
    assert not calls


def test_backend_budget_clamped_to_whole_client_deadline(service, monkeypatch):
    request, calls, response, front = service
    monkeypatch.setattr(proxy, 'CLIENT_SECONDS', .3)
    response['delay'] = .8
    with socket.create_connection(('127.0.0.1', front.server_port), timeout=2) as sock:
        sock.sendall(b'POST /v1/chat/completions HTTP/1.0\r\nAuthorization: Bearer '
                     + KEY.encode() + b'\r\nContent-Type: application/json\r\nContent-Length: '
                     + str(len(BODY)).encode() + b'\r\n\r\n')
        time.sleep(.2)
        started = time.monotonic()
        sock.sendall(BODY)
        assert sock.recv(65536) == b''
        # A new unauthenticated request can be refused promptly: the single
        # proxy worker did not keep its own upstream socket open for another80s.
        assert request(auth=None)[0] == 401
        assert time.monotonic() - started < .4
    assert len(calls) == 1


@pytest.mark.parametrize('model', [None, '', '../model', 'a' * 129, 'x\ny'])
def test_model_required_before_bind(model):
    with pytest.raises(ValueError, match='model'):
        proxy.make_server(KEY, ('127.0.0.1', 0), model=model)


def test_only_the_pinned_service_context_is_accepted_everywhere():
    with pytest.raises(ValueError, match='service context'):
        proxy.make_server(KEY, ('127.0.0.1', 0), model='granite', service_context=8192)
    with pytest.raises(ValueError, match='service context'):
        proxy._chat(BODY, 'granite', service_context=8192)
    server = proxy.make_server(KEY, ('127.0.0.1', 0), model='granite')
    try:
        assert server.service_context == 131072
    finally:
        server.server_close()
    large = json.loads(BODY); large['max_tokens'] = 8193
    proxy._chat(json.dumps(large).encode(), 'granite')  # the old 1,200 ceiling is gone: bounded by the context alone
    assert proxy.environment_service_context({'GRANITE_MAX_MODEL_LEN': '131072'}) == 131072
    for environment in ({}, {'GRANITE_MAX_MODEL_LEN': '8192'}, {'GRANITE_MAX_MODEL_LEN': 'x'}):
        with pytest.raises(ValueError, match='GRANITE_MAX_MODEL_LEN'):
            proxy.environment_service_context(environment)
