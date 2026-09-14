"""Synthetic secrets and injected HTTP only; never connects to a provider."""
from dataclasses import replace
import base64
import json
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from test_execution_adapters import venue_fixture
from research.kalshi.frankie_boss.execution_adapters import translate
from research.kalshi.frankie_boss.execution_auth import (
    CredentialReference, KalshiSecrets, TastytradeSecrets, kalshi_signature,
)
from research.kalshi.frankie_boss.execution_transport import (
    TransportCapability, HTTPResponse, TransportError, prepare_transport,
)

H = 'a'*64
SECOND = 1_000_000_000


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return HTTPResponse(item[0], item[1], kwargs['url'])


def fixture(venue='tastytrade', environment='live'):
    args, instrument, pin = venue_fixture(venue)
    account = replace(pin.account, environment=environment)
    pin = replace(pin, account=account)
    intent = replace(args['intent'], account=account, adapter_hash=pin.digest)
    wire = translate(intent, instrument, pin)
    ref = CredentialReference(account, 'synthetic-vault-reference', 'version-1')
    origin = ({'live': 'https://api.tastyworks.com', 'sandbox': 'https://api.cert.tastyworks.com'}
              if venue == 'tastytrade' else
              {'live': 'https://external-api.kalshi.com', 'sandbox': 'https://external-api.demo.kalshi.co'})[environment]
    cap = TransportCapability(account, pin.digest, ref, origin, H, 'frankie-test/1', 5000, 30*SECOND, 5*SECOND)
    return pin, wire, cap


def token(body=None):
    return (200, json.dumps(body or {'access_token': 'synthetic-access-secret'}).encode())


def ready(http, clock=lambda: 10*SECOND, venue='tastytrade'):
    pin, wire, cap = fixture(venue)
    secrets = TastytradeSecrets('synthetic-refresh-secret', 'synthetic-client-secret')
    result = prepare_transport(wire=wire, pin=pin, capability=cap, expected_capability_hash=cap.digest,
        resolve_secret=lambda ref: secrets, http=http, expected_http_hash=H, now=clock)
    return result, wire, cap


def test_missing_optional_token_fields_and_one_exact_submit():
    http = FakeHTTP([token(), (503, b'provider unavailable')])
    transport, wire, cap = ready(http)
    assert len(http.calls) == 1  # refresh is complete before controller dispatch
    response = transport(wire)
    assert response.body == b'provider unavailable' and response.http_status == 503
    assert response.wire_hash == wire.digest and response.account == cap.account
    assert http.calls[1]['body'] == wire.body
    assert http.calls[1]['retries'] == 0 and http.calls[1]['follow_redirects'] is False
    with pytest.raises(TransportError):
        transport(wire)
    assert len(http.calls) == 2


@pytest.mark.parametrize('status', [401, 429, 500])
def test_order_errors_never_refresh_or_resend(status):
    http = FakeHTTP([token(), (status, b'error')])
    transport, wire, _ = ready(http)
    assert transport(wire).http_status == status
    with pytest.raises(TransportError):
        transport(wire)
    assert len(http.calls) == 2


def test_uncertain_response_sanitized_and_not_retried():
    http = FakeHTTP([token(), TimeoutError('synthetic-access-secret')])
    transport, wire, _ = ready(http)
    with pytest.raises(TransportError) as err:
        transport(wire)
    assert 'synthetic-access-secret' not in str(err.value)
    assert err.value.__suppress_context__
    with pytest.raises(TransportError):
        transport(wire)
    assert len(http.calls) == 2


@pytest.mark.parametrize('body', [b'bad json', b'{"access_token":"x","expires_in":true}',
    b'{"access_token":"x","expires_in":0}', b'{"access_token":"x","token_type":"Basic"}',
    b'{"access_token":"x","scope":"read"}', b'{"access_token":"x","access_token":"y"}'])
def test_bad_refresh_never_creates_ready_transport(body):
    with pytest.raises(TransportError):
        ready(FakeHTTP([(200, body)]))


def test_refresh_failure_and_secret_repr_are_redacted():
    for http in [FakeHTTP([(401, b'synthetic-refresh-secret')]),
                 FakeHTTP([RuntimeError('synthetic-client-secret')])]:
        with pytest.raises(TransportError) as err:
            ready(http)
        assert 'synthetic-' not in str(err.value)
        assert len(http.calls) == 1
    secret = TastytradeSecrets('synthetic-refresh-secret', 'synthetic-client-secret')
    assert 'synthetic-' not in repr(secret)


def test_expiry_before_send_and_clock_rollback_refuse_without_refresh():
    for later in [9*SECOND, 40*SECOND]:
        clock = [10*SECOND]
        http = FakeHTTP([token()])
        transport, wire, _ = ready(http, lambda: clock[0])
        clock[0] = later
        with pytest.raises(TransportError):
            transport(wire)
        assert len(http.calls) == 1


def test_token_expiry_measured_from_request_start():
    clock = iter([10*SECOND, 17*SECOND])
    http = FakeHTTP([token({'access_token': 'synthetic-access-secret', 'expires_in': 6})])
    with pytest.raises(TransportError):
        ready(http, lambda: next(clock))


@pytest.mark.parametrize('change', [dict(origin='https://evil.invalid'), dict(origin='https://api.tastyworks.com/'),
    dict(origin='https://api.cert.tastyworks.com'), dict(user_agent='x\r\nInjected: y')])
def test_invalid_capability_refuses(change):
    _, _, cap = fixture()
    with pytest.raises(ValueError):
        replace(cap, **change)


@pytest.mark.parametrize('path', ['/accounts/OTHER/orders', '/accounts/abc/orders?x=1', '//evil.invalid/orders',
    '/accounts/../orders', '/oauth/token'])
def test_path_mismatch_before_secret_resolution(path):
    pin, wire, cap = fixture()
    with pytest.raises((ValueError, TransportError)):
        prepare_transport(wire=replace(wire, path=path), pin=pin, capability=cap,
            expected_capability_hash=cap.digest, resolve_secret=lambda _: pytest.fail('secret read'),
            http=lambda **_: pytest.fail('HTTP'), expected_http_hash=H, now=lambda: 10*SECOND)


def test_preflight_uses_distinct_route_and_exact_wire_identity():
    http = FakeHTTP([token(), (201, b'dry-run'), (201, b'order')])
    transport, wire, _ = ready(http)
    receipt = transport.preflight()
    assert receipt.source == 'tastytrade.dry_run' and receipt.wire_hash == wire.digest
    assert http.calls[1]['url'].endswith('/orders/dry-run')
    assert http.calls[1]['body'] == wire.body
    assert transport(wire).source == 'tastytrade.submit_order'


def test_response_echo_and_redirect_do_not_escape_as_receipts():
    for response in [(200, b'synthetic-access-secret'), (200, b'synthetic-refresh-secret')]:
        http = FakeHTTP([token(), response])
        transport, wire, _ = ready(http)
        with pytest.raises(TransportError):
            transport(wire)
        assert len(http.calls) == 2
    http = FakeHTTP([token()])
    transport, wire, _ = ready(http)
    http.responses.append((302, b'redirect refused'))
    assert transport(wire).http_status == 302
    assert len(http.calls) == 2


def test_mismatched_final_response_url_and_http_pin_refuse():
    pin, wire, cap = fixture()
    with pytest.raises(TransportError):
        prepare_transport(wire=wire, pin=pin, capability=cap, expected_capability_hash=cap.digest,
            resolve_secret=lambda _: pytest.fail('secret resolution'), http=lambda **_: None,
            expected_http_hash='b'*64, now=lambda: 10*SECOND)
    with pytest.raises(TransportError):
        ready(lambda **kw: HTTPResponse(200, token()[1], 'https://evil.invalid/oauth/token'))


def test_two_concurrent_order_calls_cannot_double_submit():
    from concurrent.futures import ThreadPoolExecutor
    http = FakeHTTP([token(), (201, b'order')])
    transport, wire, _ = ready(http)
    def attempt():
        try:
            return transport(wire)
        except TransportError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(r is not None for r in results) == 1
    assert len(http.calls) == 2


def test_signature_excludes_query_and_verifies_exact_protocol():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signature = kalshi_signature(key, 1234, 'GET', '/trade-api/v2/portfolio/fills?cursor=a%2Fb')
    key.public_key().verify(base64.b64decode(signature), b'1234GET/trade-api/v2/portfolio/fills',
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    for path in ['https://evil.invalid/a', '//evil.invalid/a', '/a#fragment', '/a\r\n']:
        with pytest.raises(ValueError):
            kalshi_signature(key, 1234, 'GET', path)


@pytest.mark.parametrize('environment', ['live', 'sandbox'])
def test_kalshi_prepares_signature_and_key_before_dispatch(environment):
    pin, wire, cap = fixture('kalshi', environment)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    http = FakeHTTP([(201, b'order')])
    resolutions = []
    def resolve(ref):
        resolutions.append(ref)
        return KalshiSecrets('synthetic-key-id', pem)
    transport = prepare_transport(wire=wire, pin=pin, capability=cap, expected_capability_hash=cap.digest,
        resolve_secret=resolve, http=http, expected_http_hash=H, now=lambda: 10*SECOND)
    assert len(resolutions) == 1 and not http.calls
    assert transport(wire).source == 'kalshi.create_order'
    headers = http.calls[0]['headers']
    key.public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
        ('10000POST'+wire.path).encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())


@pytest.mark.parametrize('expired', [False, True])
def test_controller_final_clock_and_lost_response_survive_reopen(tmp_path, expired):
    from test_execution_controller import setup_controller
    from research.kalshi.frankie_boss.execution_controller import ExecutionController
    from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
    c, ledger, inputs, account, pin = setup_controller(tmp_path, environment='live')
    _, _, cap = fixture('kalshi')
    cap = replace(cap, account=pin.account, adapter_hash=pin.digest,
        credential=replace(cap.credential, account=pin.account))
    authority = replace(c.authority, transport_hash=cap.digest)
    c = ExecutionController(ledger=ledger, store=c.store, authority=authority,
        expected_authority_hash=authority.digest, pin=pin)
    prepared = c.prepare(inputs, account, expected_account_evidence_hash=account.digest)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    http = FakeHTTP([TimeoutError('synthetic-key-id')])
    transport = prepare_transport(wire=prepared.wire, pin=pin, capability=cap,
        expected_capability_hash=cap.digest, resolve_secret=lambda _: KalshiSecrets('synthetic-key-id', pem),
        http=http, expected_http_hash=H, now=lambda: 10)
    with pytest.raises(ValueError):
        c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
            transport=transport, transport_hash=transport.digest, now=lambda: 20 if expired else 10)
    assert len(http.calls) == (0 if expired else 1)
    if expired:
        assert ledger.state(inputs.intent.intent_id)['wire'] is None
        ledger.close()
        return
    assert ledger.killed and ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
    checkpoint = ledger.checkpoint()
    ledger.close()
    assert b'synthetic-key-id' not in (tmp_path/'orders.sqlite').read_bytes()
    reopened = ExecutionLedger(tmp_path/'orders.sqlite', checkpoint=checkpoint)
    try:
        assert reopened.killed and reopened.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
        c = ExecutionController(ledger=reopened, store=c.store, authority=authority,
            expected_authority_hash=authority.digest, pin=pin)
        with pytest.raises(ValueError):
            c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                transport=lambda _: pytest.fail('must not resend'), transport_hash=cap.digest, now=lambda: 10)
    finally:
        reopened.close()


def test_cancellation_messages_are_redacted_and_not_converted_to_retry():
    def http(**kwargs):
        raise KeyboardInterrupt('synthetic-refresh-secret')
    with pytest.raises(KeyboardInterrupt) as err:
        ready(http)
    assert str(err.value) == '' and err.value.__suppress_context__
