"""Generated credentials and fake HTTP; no real cancellations."""
import base64
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from test_execution_transport import fixture, FakeHTTP
from test_execution_providers import connection
from research.kalshi.frankie_boss.execution_auth import KalshiSecrets
from research.kalshi.frankie_boss.execution_cancel_contracts import CancelWire, cancel_path
from research.kalshi.frankie_boss.execution_cancel_transport import (
    CancelTransportCapability, prepare_cancel_transport,
)
from research.kalshi.frankie_boss.execution_transport import HTTPResponse, TransportError, prepare_transport

SECOND = 1000000000


@pytest.fixture
def setup():
    pin, original, cap = fixture('kalshi', 'sandbox')
    cap = CancelTransportCapability(**vars(cap))
    wire = CancelWire(control_hash='b'*64, adapter_hash=pin.digest, account=pin.account,
        provider_order_id='provider-1', client_id=original.client_id, market_ticker=pin.ticker,
        subaccount=pin.subaccount, method='DELETE',
        path=cancel_path('provider-1', pin.subaccount, pin.ticker),
        body=b'', expires_ns=10*SECOND)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    return pin, wire, cap, key, KalshiSecrets('synthetic-cancel-key', pem)


def prepare(setup, http, now=lambda: SECOND, **updates):
    pin, wire, cap, key, secrets = setup
    args = dict(wire=wire, pin=pin, capability=cap, expected_capability_hash=cap.digest,
        expected_http_hash=cap.http_hash, resolve_secret=lambda _: secrets, http=http, now=now)
    args.update(updates)
    return prepare_cancel_transport(**args)


@pytest.mark.parametrize('status', [200, 301, 401, 404, 429, 500])
def test_one_delete_preserves_raw_receipt_and_signature(setup, status):
    http = FakeHTTP([(status, b'{"result":"synthetic"}')])
    clock = [SECOND]
    ready = prepare(setup, http, now=lambda: clock[0])
    clock[0] = 2*SECOND
    receipt = ready(setup[1])
    assert receipt.source == 'kalshi.cancel_order'
    assert receipt.wire_hash == setup[1].digest and receipt.account == setup[1].account
    assert receipt.http_status == status and receipt.body == b'{"result":"synthetic"}'
    call = http.calls[0]
    assert call['method'] == 'DELETE' and call['body'] == b''
    assert call['url'] == setup[2].origin + setup[1].path
    assert call['retries'] == 0 and call['follow_redirects'] is False
    headers = call['headers']
    assert headers['KALSHI-ACCESS-TIMESTAMP'] == '2000'
    setup[3].public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
        ('2000DELETE'+setup[1].path.split('?')[0]).encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    with pytest.raises(TransportError):
        ready(setup[1])
    assert len(http.calls) == 1


@pytest.mark.parametrize('kind', ['capability', 'http', 'adapter', 'account', 'ticker', 'subaccount'])
def test_binding_refusal_before_secrets(setup, kind):
    pin, wire, cap, _, _ = setup
    changes = {}
    if kind == 'capability':
        changes['expected_capability_hash'] = 'c'*64
    elif kind == 'http':
        changes['expected_http_hash'] = 'c'*64
    elif kind == 'adapter':
        changes['wire'] = replace(wire, adapter_hash='c'*64)
    elif kind == 'account':
        changes['wire'] = replace(wire, account=replace(wire.account, account_id='other'))
    elif kind == 'ticker':
        changes['pin'] = replace(pin, ticker='OTHER')
    else:
        changes['pin'] = replace(pin, subaccount=(pin.subaccount+1)%64)
    def forbidden(*args, **kwargs):
        raise AssertionError('must not resolve secrets or call HTTP')
    with pytest.raises(TransportError):
        prepare(setup, forbidden, resolve_secret=forbidden, **changes)


def test_wire_expiry_clamps_timeout(setup):
    http = FakeHTTP([(200, b'{}')])
    clock = [SECOND]
    ready = prepare(setup, http, now=lambda: clock[0])
    clock[0] = setup[1].expires_ns - 2_000_000
    ready(setup[1])
    assert http.calls[0]['timeout_ms'] == 2


def test_expired_wire_refused_before_secret_resolution(setup):
    calls = []
    with pytest.raises(TransportError):
        prepare(setup, FakeHTTP([]), now=lambda: setup[1].expires_ns, resolve_secret=calls.append)
    assert not calls


def test_expiry_during_preparation(setup):
    times = iter([SECOND, setup[1].expires_ns])
    http = FakeHTTP([])
    with pytest.raises(TransportError):
        prepare(setup, http, now=lambda: next(times))
    assert not http.calls


def test_clock_before_preparation_completion_cannot_send(setup):
    times = iter([SECOND, 2*SECOND, SECOND+500000000])
    http = FakeHTTP([])
    ready = prepare(setup, http, now=lambda: next(times))
    with pytest.raises(TransportError):
        ready(setup[1])
    assert not http.calls


def test_expiry_during_signing_consumes_lease(setup):
    times = iter([SECOND, SECOND, 2*SECOND, setup[1].expires_ns])
    http = FakeHTTP([])
    ready = prepare(setup, http, now=lambda: next(times))
    with pytest.raises(TransportError):
        ready(setup[1])
    with pytest.raises(TransportError):
        ready(setup[1])
    assert not http.calls


@pytest.mark.parametrize('error', [TimeoutError('synthetic-secret'), KeyboardInterrupt('synthetic-secret'), SystemExit('synthetic-secret')])
def test_error_cannot_resend_and_redacts_text(setup, error):
    calls = []
    def http(**kwargs):
        calls.append(kwargs)
        raise error
    ready = prepare(setup, http)
    with pytest.raises(TransportError if isinstance(error, Exception) else type(error)) as caught:
        ready(setup[1])
    assert 'synthetic-secret' not in str(caught.value)
    with pytest.raises(TransportError):
        ready(setup[1])
    assert len(calls) == 1


def test_secret_echo_is_not_a_receipt(setup):
    http = FakeHTTP([(200, b'synthetic-cancel-key')])
    ready = prepare(setup, http)
    with pytest.raises(TransportError) as error:
        ready(setup[1])
    assert 'synthetic-cancel-key' not in str(error.value) + repr(ready)


def test_concurrent_lease_calls_send_once(setup):
    http = FakeHTTP([(200, b'{}')])
    ready = prepare(setup, http)
    def send():
        try:
            return ready(setup[1])
        except TransportError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert sum(r is not None for r in results) == 1 and len(http.calls) == 1


def test_existing_post_preparation_refuses_cancel_scope(setup):
    pin, wire, cap, _, secrets = setup
    with pytest.raises(TransportError):
        prepare_transport(wire=wire, pin=pin, capability=cap,
            expected_capability_hash=cap.digest, expected_http_hash=cap.http_hash,
            resolve_secret=lambda _: secrets, http=FakeHTTP([]), now=lambda: SECOND)


def test_post_wire_refused_by_cancel_preparation_and_capability_refused_by_post(setup):
    pin, original, _ = fixture('kalshi', 'sandbox')
    with pytest.raises(TransportError):
        prepare(setup, FakeHTTP([]), wire=original)
    cap = setup[2]
    with pytest.raises(TransportError):
        prepare_transport(wire=original, pin=pin, capability=cap,
            expected_capability_hash=cap.digest, expected_http_hash=cap.http_hash,
            resolve_secret=lambda _: setup[4], http=FakeHTTP([]), now=lambda: SECOND)


def test_response_url_mismatch_consumes_lease(setup):
    def http(**kwargs):
        return HTTPResponse(200, b'{}', kwargs['url'] + '/different')
    ready = prepare(setup, http)
    with pytest.raises(TransportError):
        ready(setup[1])
    with pytest.raises(TransportError):
        ready(setup[1])


def test_less_than_millisecond_remaining_cannot_send(setup):
    http, clock = FakeHTTP([]), [SECOND]
    ready = prepare(setup, http, now=lambda: clock[0])
    clock[0] = setup[1].expires_ns - 999999
    with pytest.raises(TransportError):
        ready(setup[1])
    assert not http.calls


@pytest.mark.parametrize('expired_connect', [False, True])
def test_concrete_https_delete_and_expired_connect(setup, connection, monkeypatch, expired_connect):
    from research.kalshi.frankie_boss.execution_providers import HTTPSExchange
    clock, monotonic = [SECOND], [0.0]
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.time.monotonic', lambda: monotonic[0])
    if expired_connect:
        def connect(self):
            monotonic[0] += .003
        monkeypatch.setattr('http.client.HTTPSConnection.connect', connect)
    ready = prepare(setup, HTTPSExchange(origin=setup[2].origin), now=lambda: clock[0])
    clock[0] = setup[1].expires_ns - 2_000_000
    if expired_connect:
        with pytest.raises(TransportError):
            ready(setup[1])
        assert not connection[0].sent
    else:
        result = ready(setup[1])
        assert result.http_status == 401
        assert connection[0].sent[0][0] == ('DELETE', setup[1].path)
        assert connection[0].sent[0][1]['body'] == b''
    assert len(connection) == 1 and connection[0].closed
    assert connection[0].kwargs['timeout'] <= .002
    with pytest.raises(TransportError):
        ready(setup[1])
    assert len(connection) == 1
