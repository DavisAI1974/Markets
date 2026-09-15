"""Concrete provider boundaries with synthetic files and fake connections only."""
from dataclasses import replace
import json
import ssl
import pytest
from test_execution_transport import fixture
from research.kalshi.frankie_boss.execution_providers import HTTPSExchange, FileSecretProvider
from research.kalshi.frankie_boss.execution_transport import TransportError, prepare_transport


def request(**updates):
    args = dict(method='POST', url='https://api.cert.tastyworks.com/oauth/token',
                headers={'Authorization': 'Bearer synthetic'}, body=b'{"exact": 1}',
                timeout_ms=1000, follow_redirects=False, retries=0)
    args.update(updates)
    return args


@pytest.fixture
def connection(monkeypatch):
    calls = []
    class Connection:
        def __init__(self, host, **kwargs):
            calls.append(self)
            self.host, self.kwargs = host, kwargs
            self.sent, self.closed = [], False
            self.status, self.payload = 401, b'{"error":"refused"}'
            self.length = len(self.payload)
            self.sock = self
        def connect(self):
            pass
        def settimeout(self, seconds):
            assert 0 < seconds <= self.kwargs['timeout']
        def shutdown(self, how):
            pass
        def set_debuglevel(self, level):
            assert level == 0
        def request(self, *args, **kwargs):
            self.sent.append((args, kwargs))
        def getresponse(self):
            return self
        def read(self, count):
            return self.payload[:count]
        def close(self):
            self.closed = True
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.http.client.HTTPSConnection', Connection)
    return calls


@pytest.mark.parametrize('status', [200, 201, 301, 401, 429, 503])
def test_one_exchange_preserves_status_and_bytes(connection, monkeypatch, status):
    # No response, including redirects, causes another connection/request.
    original = __import__('http.client', fromlist=['HTTPSConnection']).HTTPSConnection.getresponse
    def response(self):
        self.status = status
        return original(self)
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.http.client.HTTPSConnection.getresponse', response)
    result = HTTPSExchange(**{'origin': 'https://api.cert.tastyworks.com'})(**request())
    assert result.status == status and result.body == b'{"error":"refused"}'
    assert len(connection) == 1 and len(connection[0].sent) == 1
    conn = connection[0]
    assert conn.closed and conn.host == 'api.cert.tastyworks.com'
    assert conn.kwargs['context'].check_hostname
    assert conn.kwargs['context'].verify_mode == ssl.CERT_REQUIRED
    assert 0 < conn.kwargs['timeout'] <= 1
    assert conn.sent[0][1]['body'] == request()['body']


@pytest.mark.parametrize('updates', [
    {'url': 'http://api.cert.tastyworks.com/oauth/token'},
    {'url': 'https://api.tastyworks.com/oauth/token'},
    {'url': 'https://user@api.cert.tastyworks.com/oauth/token'},
    {'url': 'https://api.cert.tastyworks.com:443/oauth/token'},
    {'url': 'https://api.cert.tastyworks.com/a/../oauth/token'},
    {'url': 'https://api.cert.tastyworks.com/%2e%2e/oauth/token'},
    {'url': 'https://api.cert.tastyworks.com/oauth/token#fragment'},
    {'url': 'https://api.cert.tastyworks.com/\r\nx'},
    {'headers': {'Host': 'evil.example'}},
    {'headers': {'Content-Length': '1'}},
    {'headers': {'X-Test': 'a\r\nb'}},
    {'follow_redirects': True}, {'retries': 1}, {'timeout_ms': True},
])
def test_refuse_before_connection(connection, updates):
    with pytest.raises(TransportError):
        HTTPSExchange(origin='https://api.cert.tastyworks.com')(**request(**updates))
    assert not connection


def test_timeout_is_sanitized_and_not_retried(connection, monkeypatch):
    def fail(self):
        raise TimeoutError('synthetic-secret')
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.http.client.HTTPSConnection.getresponse', fail)
    with pytest.raises(TransportError) as error:
        HTTPSExchange(origin='https://api.cert.tastyworks.com')(**request())
    assert 'synthetic-secret' not in str(error.value)
    assert len(connection) == 1 and connection[0].closed


def test_response_limit_fails_closed(connection):
    with pytest.raises(TransportError):
        HTTPSExchange(origin='https://api.cert.tastyworks.com', max_response_bytes=4)(**request())
    assert connection[0].closed


def test_truncated_response_fails_closed(connection, monkeypatch):
    def truncated(self):
        self.length = len(self.payload) + 10
        return self
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.http.client.HTTPSConnection.getresponse', truncated)
    with pytest.raises(TransportError):
        HTTPSExchange(origin='https://api.cert.tastyworks.com')(**request())
    assert len(connection) == 1 and connection[0].closed


def test_connect_overrun_never_sends(connection, monkeypatch):
    times = iter([0, 0, 2])
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.time.monotonic', lambda: next(times))
    with pytest.raises(TransportError):
        HTTPSExchange(origin='https://api.cert.tastyworks.com')(**request())
    assert not connection[0].sent and connection[0].closed


@pytest.mark.parametrize('slow', [False, True])
def test_local_tls_exchange_and_deadline(tmp_path, monkeypatch, slow):
    """Real stdlib TLS against loopback, generated key, no venue/DNS access."""
    import datetime
    import socket
    import threading
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'api.cert.tastyworks.com')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('api.cert.tastyworks.com')]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .add_extension(x509.KeyUsage(True, False, True, False, False, True, True, False, False), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # This workstation injects pip truststore globally; its client verification
    # wrapper also verifies server-side peers. Use its underlying server context.
    server_context = getattr(server_context, '_ctx', server_context)
    server_context.load_cert_chain(cert_path, key_path)
    original_context, original_connect = ssl.create_default_context, socket.create_connection
    def trusted_context():
        context = original_context()
        context.load_verify_locations(cafile=str(cert_path))
        return context
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(3)
    stop, received, errors = threading.Event(), [], []
    def serve():
        try:
            client, _ = listener.accept()
            with server_context.wrap_socket(client, server_side=True) as stream:
                stream.settimeout(3)
                data = b''
                while b'\r\n\r\n' not in data:
                    data += stream.recv(4096)
                head, body = data.split(b'\r\n\r\n', 1)
                while len(body) < len(request()['body']):
                    body += stream.recv(4096)
                received.append((head, body))
                if slow:
                    stop.wait(2)
                else:
                    stream.sendall(b'HTTP/1.1 302 Found\r\nContent-Length: 2\r\nLocation: https://invalid.example/\r\nConnection: close\r\n\r\n{}')
        except Exception as error:
            errors.append(type(error).__name__)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    def loopback(address, timeout, *args, **kwargs):
        assert address == ('api.cert.tastyworks.com', 443)
        return original_connect(listener.getsockname(), timeout, *args, **kwargs)
    monkeypatch.setattr(ssl, 'create_default_context', trusted_context)
    monkeypatch.setattr(socket, 'create_connection', loopback)
    try:
        exchange = HTTPSExchange(origin='https://api.cert.tastyworks.com')
        if slow:
            with pytest.raises(TransportError):
                exchange(**request(timeout_ms=200))
        else:
            response = exchange(**request())
            assert response.status == 302 and response.body == b'{}'
    finally:
        stop.set()
        thread.join(4)
        listener.close()
    assert not thread.is_alive() and not errors
    assert len(received) == 1 and received[0][1] == request()['body']


def secret_file(tmp_path, venue='tastytrade'):
    _, _, cap = fixture(venue)
    path = tmp_path / 'synthetic.json'
    secrets = (dict(refresh_token='synthetic-refresh', client_secret='synthetic-client')
               if venue == 'tastytrade' else dict(key_id='synthetic-id', private_key_pem='synthetic-pem'))
    path.write_text(json.dumps(dict(credential_hash=cap.credential.digest, secrets=secrets)))
    return cap.credential, path


@pytest.mark.parametrize('venue', ['tastytrade', 'kalshi'])
def test_exact_secret_binding_and_redaction(tmp_path, venue):
    ref, path = secret_file(tmp_path, venue)
    provider = FileSecretProvider(reference=ref, path=path)
    secret = provider(ref)
    assert 'synthetic' not in repr(provider) + repr(secret)
    with pytest.raises(TransportError):
        provider(replace(ref, version='different-version'))


@pytest.mark.parametrize('text', ['{}', '{"credential_hash":"wrong","secrets":{}}',
    '{"secrets":{},"secrets":{}}', 'not json synthetic-refresh'])
def test_bad_secret_file_sanitized(tmp_path, text):
    ref, path = secret_file(tmp_path)
    path.write_text(text)
    with pytest.raises(TransportError) as error:
        FileSecretProvider(reference=ref, path=path)(ref)
    assert 'synthetic-refresh' not in str(error.value)


def test_secret_file_limit(tmp_path):
    ref, path = secret_file(tmp_path)
    path.write_bytes(b'x' * 65537)
    with pytest.raises(TransportError):
        FileSecretProvider(reference=ref, path=path)(ref)


def test_ready_lease_caps_connect_budget_and_cannot_resend(tmp_path, connection, monkeypatch):
    import http.client
    ref, path = secret_file(tmp_path)
    pin, wire, cap = fixture()
    clock, monotonic = [0], [0.0]
    def response(self):
        self.status = 200
        self.payload = b'{"access_token":"synthetic-access","expires_in":900}'
        self.length = len(self.payload)
        return self
    def connect(self):
        if len(connection) == 2:
            monotonic[0] += .002
    monkeypatch.setattr(http.client.HTTPSConnection, 'getresponse', response)
    monkeypatch.setattr(http.client.HTTPSConnection, 'connect', connect)
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.time.monotonic', lambda: monotonic[0])
    ready = prepare_transport(wire=wire, pin=pin, capability=cap,
        expected_capability_hash=cap.digest, expected_http_hash=cap.http_hash,
        resolve_secret=FileSecretProvider(reference=ref, path=path),
        http=HTTPSExchange(origin=cap.origin), now=lambda: clock[0])
    clock[0] = 30_000_000_000 - 1_000_000
    with pytest.raises(TransportError):
        ready(wire)
    assert len(connection) == 2
    assert connection[0].kwargs['timeout'] <= cap.timeout_ms / 1000
    assert connection[1].kwargs['timeout'] <= .001
    assert not connection[1].sent and connection[1].closed
    with pytest.raises(TransportError):
        ready(wire)
    assert len(connection) == 2
