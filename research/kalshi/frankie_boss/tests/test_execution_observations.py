"""Generated keys, synthetic account rows and injected HTTP only."""
from dataclasses import replace, FrozenInstanceError
import base64
import json
from urllib.parse import parse_qs
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from research.kalshi.frankie_boss.execution_auth import CredentialReference, KalshiSecrets
from research.kalshi.frankie_boss.execution_contracts import AccountKey
from research.kalshi.frankie_boss.execution_transport import HTTPResponse, TransportError
from research.kalshi.frankie_boss.execution_observations import (
    KalshiObservationCapability, ObservationRequest, collect_kalshi_primary,
)


@pytest.fixture
def setup():
    account = AccountKey('kalshi', 'sandbox', 'synthetic-user')
    ref = CredentialReference(account, 'synthetic-file', 'v1')
    cap = KalshiObservationCapability(account, ref, 'https://external-api.demo.kalshi.co',
        'a'*64, 'frankie-test/1', 1000, 10_000_000_000, 2, 3, 65536)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    return cap, key, KalshiSecrets('synthetic-key-id', pem)


def balance():
    return {'balance': 123, 'portfolio_value': 345, 'updated_ts': 100,
            'balance_dollars': '1.2300'}


def order(identity='order-1', **updates):
    return dict(order_id=identity, user_id='synthetic-user', status='resting',
                subaccount_number=0, remaining_count_fp='3.00', **updates)


def page(rows=(), cursor=''):
    return {'orders': list(rows), 'cursor': cursor}


def run(setup, payloads, *, cap=None, clock=None, persist=None):
    base, key, secrets = setup
    cap = cap or base
    calls, retained = [], []
    def http(**kwargs):
        calls.append(kwargs)
        item = payloads[len(calls)-1]
        if isinstance(item, BaseException):
            raise item
        status, body = item if type(item) is tuple else (200, item)
        body = body if type(body) is bytes else json.dumps(body).encode()
        return HTTPResponse(status, body, kwargs['url'])
    result = collect_kalshi_primary(capability=cap, expected_capability_hash=cap.digest,
        expected_http_hash=cap.http_hash, resolve_secret=lambda ref: secrets,
        http=http, now=clock or (lambda: 1_000_000_000),
        retain_attempt=persist or retained.append)
    return result, calls, retained


def test_complete_pagination_signatures_and_frozen_evidence(setup):
    values = [balance(), page([order()], 'a+/=&?'), page([order('order-2')])]
    result, calls, retained = run(setup, values)
    assert result.complete and result.outcome == 'complete'
    assert result.attempts == tuple(retained) and len(calls) == 3
    cap, key, _ = setup
    for index, (call, attempt) in enumerate(zip(calls, result.attempts)):
        assert call['method'] == 'GET' and call['body'] == b''
        assert call['retries'] == 0 and call['follow_redirects'] is False
        assert parse_qs(attempt.request.query)['subaccount'] == ['0']
        headers = call['headers']
        message = headers['KALSHI-ACCESS-TIMESTAMP'] + 'GET' + attempt.request.path
        key.public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
            message.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        assert attempt.body == json.dumps(values[index]).encode()
    assert parse_qs(result.attempts[2].request.query)['cursor'] == ['a+/=&?']
    digest = result.digest
    values[0]['balance'] = 999
    assert result.digest == digest
    with pytest.raises(FrozenInstanceError):
        result.outcome = 'other'


def test_empty_resting_inventory_complete(setup):
    result, calls, _ = run(setup, [balance(), page()])
    assert result.complete and len(calls) == 2


@pytest.mark.parametrize('payloads,reason', [
    ([balance(), {'orders': []}], 'invalid_page'),
    ([balance(), page([], 'a'), page([], 'a')], 'cursor_cycle'),
    ([balance(), page([order()], 'a'), page([order()])], 'invalid_page'),
    ([balance(), page([dict(order(), status='executed')])], 'invalid_page'),
    ([balance(), page([dict(order(), user_id='other')])], 'invalid_page'),
    ([balance(), page([dict(order(), subaccount_number=1)])], 'invalid_page'),
    ([balance(), b'{"orders":[],"cursor":"","cursor":""}'], 'invalid_page'),
    ([dict(balance(), balance=True)], 'invalid_page'),
    ([dict(balance(), balance_dollars=1.23)], 'invalid_page'),
    ([balance(), (401, b'{"error":"no"}')], 'http_status'),
    ([balance(), (429, b'{"error":"no"}')], 'http_status'),
    ([balance(), (500, b'{"error":"no"}')], 'http_status'),
    ([balance(), TimeoutError('synthetic-sensitive-error')], 'transport_error'),
])
def test_incomplete_preserves_attempts_without_retry(setup, payloads, reason):
    result, calls, retained = run(setup, payloads)
    assert not result.complete and result.outcome == reason
    assert len(calls) == len(payloads) and result.attempts == tuple(retained)
    assert 'synthetic-sensitive-error' not in repr(result)
    if reason == 'http_status':
        assert result.attempts[-1].body == b'{"error":"no"}'


def test_page_budget_no_extra_get(setup):
    cap = replace(setup[0], max_order_pages=1)
    result, calls, _ = run(setup, [balance(), page([], 'a')], cap=cap)
    assert result.outcome == 'page_budget' and len(calls) == 2


def test_total_body_budget_drops_oversize_body_explicitly(setup):
    cap = replace(setup[0], max_total_response_bytes=4)
    result, calls, retained = run(setup, [balance()], cap=cap)
    assert result.outcome == 'byte_budget' and len(calls) == 1
    assert retained[0].body == b'' and retained[0].failure == 'byte_budget'


def test_secret_echo_never_reaches_retention(setup):
    result, calls, retained = run(setup, [b'synthetic-key-id'])
    assert result.outcome == 'secret_echo'
    assert retained[0].body == b''
    assert b'synthetic-key-id' not in repr(result).encode()


def test_capability_pin_failure_before_secret_resolution(setup):
    cap, _, _ = setup
    def forbidden(*args, **kwargs):
        raise AssertionError('must not call')
    with pytest.raises(TransportError):
        collect_kalshi_primary(capability=cap, expected_capability_hash='b'*64,
            expected_http_hash=cap.http_hash, resolve_secret=forbidden,
            http=forbidden, now=forbidden, retain_attempt=forbidden)


@pytest.mark.parametrize('changes', [dict(method='POST'), dict(path='/wrong'),
    dict(query='subaccount=1'), dict(query='subaccount=0&status=executed&limit=2'),
    dict(query='subaccount=0&subaccount=0'), dict(source='unknown')])
def test_request_refuses_method_path_scope_mutations(setup, changes):
    cap = setup[0]
    request = ObservationRequest(cap.account, cap.digest, 'kalshi.primary_balance',
        'GET', '/trade-api/v2/portfolio/balance', 'subaccount=0')
    with pytest.raises(ValueError):
        replace(request, **changes)


def test_persistence_failure_stops_collection(setup):
    def fail(attempt):
        raise RuntimeError('synthetic-sensitive-error')
    with pytest.raises(TransportError) as error:
        run(setup, [balance()], persist=fail)
    assert 'synthetic-sensitive-error' not in str(error.value)


@pytest.mark.parametrize('times,payloads,reason,calls_count', [
    ([0, 0, 10_000_000_000], [], 'time_budget', 0),
    ([0, 0, 0, 10_000_000_000], [balance()], 'time_budget', 1),
    ([100, 99], [], 'clock_error', 0),
    ([100, 100, 99], [], 'signing_or_clock_error', 0),
    ([100, 100, 100, 99], [balance()], 'clock_error', 1),
])
def test_expiry_and_backwards_clock_fail_closed(setup, times, payloads, reason, calls_count):
    clock = iter(times)
    result, calls, retained = run(setup, payloads, clock=lambda: next(clock))
    assert result.outcome == reason and not result.complete
    assert len(calls) == calls_count
    assert result.attempts == tuple(retained)


def test_incomplete_cannot_be_relabeled_complete(setup):
    result, _, _ = run(setup, [balance(), {'orders': []}])
    with pytest.raises(ValueError):
        replace(result, outcome='complete')


def test_complete_page_reordering_and_body_changes_refused(setup):
    result, _, _ = run(setup, [balance(), page([order()], 'a'), page()])
    with pytest.raises(ValueError):
        replace(result, attempts=tuple(reversed(result.attempts)))
    altered = replace(result.attempts[-1], body=json.dumps(page([], 'open')).encode())
    with pytest.raises(ValueError):
        replace(result, attempts=result.attempts[:-1] + (altered,))


def test_cancellation_text_sanitized(setup):
    retained = []
    with pytest.raises(KeyboardInterrupt) as error:
        run(setup, [KeyboardInterrupt('synthetic-secret')], persist=retained.append)
    assert str(error.value) == ''
    assert len(retained) == 1 and retained[0].failure == 'canceled'
    assert retained[0].body == b'' and retained[0].status == 0


def test_concrete_https_composition(setup, monkeypatch):
    from research.kalshi.frankie_boss.execution_providers import HTTPSExchange
    calls, retained = [], []
    payloads = [balance(), page()]
    class Connection:
        def __init__(self, host, **kwargs):
            self.sock = self
            self.length = None
            self.status = 200
        def set_debuglevel(self, level):
            assert level == 0
        def connect(self):
            pass
        def settimeout(self, seconds):
            assert 0 < seconds <= 1
        def shutdown(self, how):
            pass
        def request(self, method, target, *, body, headers):
            calls.append((method, target, body))
        def getresponse(self):
            return self
        def read(self, count):
            return json.dumps(payloads[len(calls)-1]).encode()
        def close(self):
            pass
    monkeypatch.setattr('http.client.HTTPSConnection', Connection)
    cap, _, secrets = setup
    result = collect_kalshi_primary(capability=cap, expected_capability_hash=cap.digest,
        expected_http_hash=cap.http_hash, resolve_secret=lambda _: secrets,
        http=HTTPSExchange(origin=cap.origin), now=lambda: 1000000000, retain_attempt=retained.append)
    assert result.complete and len(calls) == 2
    assert calls[0] == ('GET', '/trade-api/v2/portfolio/balance?subaccount=0', b'')
    assert calls[1] == ('GET', '/trade-api/v2/portfolio/orders?subaccount=0&status=resting&limit=2', b'')
