"""Explicit, single-use ready transport; credentials resolved before policy clock.

The injected HTTP callable is trusted to verify TLS, disable redirects/retries,
honor timeouts and avoid logging secrets. Its identity is independently pinned;
this module does not pretend to prove the implementation behind a callable.
No concrete networking client is installed or invoked by this module itself.
"""
from dataclasses import dataclass, field
import json
import re
import threading
from typing import Protocol
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .execution_auth import CredentialReference, KalshiSecrets, TastytradeSecrets, kalshi_signature
from .execution_contracts import AccountKey, Contract
from .execution_ledger import WireRequest
from .execution_adapters import (KalshiPin, TastytradePin, TransportReceipt,
    KALSHI_CREATE_PATH, TASTYTRADE_ORDERS_PATH, preflight_request)

SECOND = 1_000_000_000
ORIGINS = {
    ('kalshi', 'live'): 'https://external-api.kalshi.com',
    ('kalshi', 'sandbox'): 'https://external-api.demo.kalshi.co',
    ('tastytrade', 'live'): 'https://api.tastyworks.com',
    ('tastytrade', 'sandbox'): 'https://api.cert.tastyworks.com',
}


class TransportError(ValueError):
    """Sanitized failure; no provider body, secret or callback exception text."""


@dataclass(frozen=True)
class TransportCapability(Contract):
    account: AccountKey
    adapter_hash: str
    credential: CredentialReference
    origin: str
    http_hash: str
    user_agent: str
    timeout_ms: int
    ready_lifetime_ns: int
    expiry_margin_ns: int

    def __post_init__(self):
        super().__post_init__()
        if ORIGINS.get((self.account.venue, self.account.environment)) != self.origin:
            raise ValueError('unsupported or mismatched official origin/environment')
        if self.credential.account != self.account:
            raise ValueError('credential account binding mismatch')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.user_agent):
            raise ValueError('product/version User-Agent required')
        if not 0 < self.timeout_ms <= 60_000 or not 0 < self.ready_lifetime_ns <= 30*SECOND:
            raise ValueError('bounded timeout and ready lifetime required')
        if not self.timeout_ms*1_000_000 <= self.expiry_margin_ns < 900*SECOND:
            raise ValueError('expiry margin must cover HTTP timeout and be below token lifetime')


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    body: bytes = field(repr=False)
    url: str

    def __post_init__(self):
        if type(self.status) is not int or not 100 <= self.status <= 599:
            raise ValueError('invalid HTTP status')
        if type(self.body) is not bytes or type(self.url) is not str:
            raise ValueError('HTTP bytes and final URL required')


class HTTPExchange(Protocol):
    def __call__(self, *, method: str, url: str, headers: dict[str, str], body: bytes,
                 timeout_ms: int, follow_redirects: bool, retries: int) -> HTTPResponse:
        """One TLS-verified exchange; never log headers/body or follow/retry."""


class SecretProvider(Protocol):
    def __call__(self, reference: CredentialReference) -> KalshiSecrets | TastytradeSecrets:
        """Resolve this exact public account/environment/version reference."""


def _clock(now):
    value = now()
    if type(value) is not int or value < 0:
        raise TransportError('invalid transport clock')
    return value


def _failure(message, error):
    # Cancellation remains cancellation, but callback messages may contain secrets.
    if isinstance(error, KeyboardInterrupt):
        raise KeyboardInterrupt() from None
    if isinstance(error, SystemExit):
        raise SystemExit() from None
    raise TransportError(message) from None


def _object(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate field')
            result[key] = value
        return result
    obj = json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite field')))
    if type(obj) is not dict:
        raise ValueError('object required')
    return obj


def _exchange(http, cap, path, headers, body):
    url = cap.origin + path
    response = http(method='POST', url=url, headers=dict(headers), body=body,
        timeout_ms=cap.timeout_ms, follow_redirects=False, retries=0)
    if type(response) is not HTTPResponse or response.url != url:
        raise TransportError('HTTP response origin/path mismatch')
    return response


def _validate(wire, pin, cap, expected_hash, http_hash):
    if type(cap) is not TransportCapability or cap.digest != expected_hash or cap.http_hash != http_hash:
        raise TransportError('transport capability pin mismatch')
    if type(wire) is not WireRequest or type(pin) not in (KalshiPin, TastytradePin):
        raise TransportError('typed wire and adapter pin required')
    if pin.account != cap.account or pin.digest != cap.adapter_hash or wire.adapter_hash != pin.digest:
        raise TransportError('transport account/adapter mismatch')
    expected_path = KALSHI_CREATE_PATH if type(pin) is KalshiPin else TASTYTRADE_ORDERS_PATH.format(account=pin.account.account_id)
    if wire.method != 'POST' or wire.path != expected_path:
        raise TransportError('unsupported order method/path')
    body = _object(wire.body)
    if type(pin) is KalshiPin and body.get('subaccount') != pin.subaccount:
        raise TransportError('Kalshi subaccount mismatch')


class ReadyTransport:
    """Opaque transient lease for one exact wire and at most one dry-run.

Call only through ExecutionController/ExecutionLedger for orders. Local reuse
protection supplements the durable ledger; it does not replace it on restart.
"""
    __slots__ = ('_wire', '_pin', '_cap', '_http', '_now', '_headers', '_sensitive',
                 '_start', '_until', '_lock', '_sent', '_preflight_sent', '_key')

    def __init__(self, wire, pin, cap, http, now, headers, sensitive, start, until, key):
        self._wire, self._pin, self._cap, self._http, self._now = wire, pin, cap, http, now
        self._headers, self._sensitive = dict(headers), tuple(sensitive)
        self._start, self._until = start, until
        self._key = key
        self._lock, self._sent, self._preflight_sent = threading.Lock(), False, False

    @property
    def digest(self):
        return self._cap.digest

    def __repr__(self):
        return 'ReadyTransport(<redacted>)'

    def _send(self, preflight):
        try:
            started = _clock(self._now)
            if not self._start <= started < self._until:
                raise TransportError('ready transport expired or clock moved backwards')
            path = preflight_request(self._wire, self._pin).path if preflight else self._wire.path
            headers = dict(self._headers)
            sensitive = self._sensitive
            if self._key is not None:
                # Key resolution/loading is already complete. Sign the actual request
                # clock now; a prepared signature would become stale while awaiting policy.
                timestamp = started//1_000_000
                signature = kalshi_signature(self._key, timestamp, self._wire.method, path)
                headers.update({'KALSHI-ACCESS-TIMESTAMP': str(timestamp),
                    'KALSHI-ACCESS-SIGNATURE': signature})
                sensitive += (signature.encode(),)
                signed = _clock(self._now)
                if not started <= signed < self._until:
                    raise TransportError('ready lease expired during signing or clock moved backwards')
                started = signed
            response = _exchange(self._http, self._cap, path, headers, self._wire.body)
            received = _clock(self._now)
            if received < started:
                raise TransportError('HTTP receive clock moved backwards')
            # Known credential echoes cannot enter durable generic receipts.
            if any(secret and secret in response.body for secret in sensitive):
                raise TransportError('HTTP response contains authentication material')
            source = ('tastytrade.dry_run' if preflight else
                      'kalshi.create_order' if type(self._pin) is KalshiPin else 'tastytrade.submit_order')
            return TransportReceipt(self._wire.digest, self._cap.account, source,
                response.status, response.body, received)
        except BaseException as error:
            _failure('authenticated HTTP exchange failed; do not resend', error)

    def __call__(self, wire):
        with self._lock:
            if type(wire) is not WireRequest or wire != self._wire or self._sent:
                raise TransportError('ready transport wire mismatch or already attempted')
            self._sent = True  # even timeout/exception cannot reuse this lease
            return self._send(False)

    def preflight(self):
        with self._lock:
            if type(self._pin) is not TastytradePin or self._preflight_sent or self._sent:
                raise TransportError('preflight unavailable or already attempted')
            self._preflight_sent = True
            return self._send(True)


def prepare_transport(*, wire: WireRequest, pin, capability: TransportCapability,
                      expected_capability_hash: str, resolve_secret: SecretProvider,
                      http: HTTPExchange, expected_http_hash: str, now) -> ReadyTransport:
    """Resolve/load/refresh before the controller takes its final clock.

No OAuth cache or in-sender refresh exists. Prepare a new lease for a new intent;
the ledger still forbids resending any previously attempted wire after restart.
"""
    try:
        _validate(wire, pin, capability, expected_capability_hash, expected_http_hash)
        if not callable(http) or not callable(resolve_secret):
            raise TransportError('explicit HTTP and secret capabilities required')
        start = _clock(now)
        secrets = resolve_secret(capability.credential)
        headers = {'User-Agent': capability.user_agent, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        until = start + capability.ready_lifetime_ns
        key = None
        if type(pin) is KalshiPin:
            if type(secrets) is not KalshiSecrets:
                raise TransportError('Kalshi credentials required')
            key = serialization.load_pem_private_key(secrets.private_key_pem, password=None)
            if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
                raise TransportError('RSA private key of at least 2048 bits required')
            headers['KALSHI-ACCESS-KEY'] = secrets.key_id
            sensitive = (secrets.private_key_pem, secrets.key_id.encode())
        else:
            if type(secrets) is not TastytradeSecrets:
                raise TransportError('tastytrade credentials required')
            body = json.dumps(dict(grant_type='refresh_token', refresh_token=secrets.refresh_token,
                client_secret=secrets.client_secret, scope='trade'), separators=(',', ':')).encode()
            response = _exchange(http, capability, '/oauth/token', headers, body)
            if response.status != 200:
                raise TransportError('OAuth refresh refused')
            payload = _object(response.body)
            token = payload.get('access_token')
            if type(token) is not str or not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', token):
                raise TransportError('invalid OAuth access token')
            seconds = payload.get('expires_in', 900)
            if type(seconds) is not int or seconds <= 0 or payload.get('token_type', 'Bearer') != 'Bearer':
                raise TransportError('invalid OAuth lifetime/type')
            if 'scope' in payload and (type(payload['scope']) is not str or 'trade' not in payload['scope'].split()):
                raise TransportError('OAuth trade scope absent')
            until = min(until, start + min(seconds, 900)*SECOND - capability.expiry_margin_ns)
            headers['Authorization'] = 'Bearer ' + token
            sensitive = tuple(s.encode() for s in (token, secrets.refresh_token, secrets.client_secret))
        finished = _clock(now)
        if not start <= finished < until:
            raise TransportError('authentication preparation expired')
        return ReadyTransport(wire, pin, capability, http, now, headers, sensitive, start, until, key)
    except BaseException as error:
        _failure('authentication preparation failed', error)
