"""Distinct single-use DELETE lease; durable cancellation authority lives upstream."""
from dataclasses import dataclass
import threading
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .execution_auth import KalshiSecrets, kalshi_signature
from .execution_adapters import KalshiPin, TransportReceipt
from .execution_cancel_contracts import CancelWire
from .execution_transport import TransportCapability, HTTPResponse, TransportError, _clock, _failure


@dataclass(frozen=True)
class CancelTransportCapability(TransportCapability):
    operation: str = 'kalshi.cancel_order'

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi' or self.operation != 'kalshi.cancel_order':
            raise ValueError('Kalshi cancellation capability required')


class ReadyCancelTransport:
    """One exact cancel wire, no retry/renewal; call through cancellation controller."""
    __slots__ = ('_wire', '_cap', '_http', '_now', '_key', '_key_id', '_sensitive',
                 '_start', '_until', '_lock', '_sent')

    def __init__(self, wire, cap, http, now, key, secrets, start, until):
        self._wire, self._cap, self._http, self._now = wire, cap, http, now
        self._key, self._key_id = key, secrets.key_id
        self._sensitive = (secrets.key_id.encode(), secrets.private_key_pem)
        self._start, self._until = start, until
        self._lock, self._sent = threading.Lock(), False

    @property
    def digest(self):
        return self._cap.digest

    def __repr__(self):
        return 'ReadyCancelTransport(<redacted>)'

    def __call__(self, wire):
        with self._lock:
            if type(wire) is not CancelWire or wire != self._wire or self._sent:
                raise TransportError('cancel wire mismatch or lease already attempted')
            self._sent = True
            try:
                started = _clock(self._now)
                if not self._start <= started < self._until:
                    raise TransportError('cancel lease expired or clock moved backwards')
                timestamp = started//1_000_000
                signature = kalshi_signature(self._key, timestamp, 'DELETE', wire.path)
                signed = _clock(self._now)
                if not started <= signed < self._until:
                    raise TransportError('cancel lease expired during signing or clock moved backwards')
                timeout_ms = min(self._cap.timeout_ms, (self._until-signed)//1_000_000)
                if timeout_ms < 1:
                    raise TransportError('cancel lease has no complete millisecond remaining')
                url = self._cap.origin + wire.path
                response = self._http(method='DELETE', url=url, body=wire.body,
                    headers={'User-Agent': self._cap.user_agent, 'Accept': 'application/json',
                        'KALSHI-ACCESS-KEY': self._key_id, 'KALSHI-ACCESS-TIMESTAMP': str(timestamp),
                        'KALSHI-ACCESS-SIGNATURE': signature},
                    timeout_ms=timeout_ms, follow_redirects=False, retries=0)
                received = _clock(self._now)
                if received < signed:
                    raise TransportError('cancel response clock moved backwards')
                if type(response) is not HTTPResponse or response.url != url:
                    raise TransportError('cancel response URL mismatch')
                if any(secret in response.body for secret in self._sensitive + (signature.encode(),)):
                    raise TransportError('cancel response contains authentication material')
                return TransportReceipt(wire.digest, self._cap.account, 'kalshi.cancel_order',
                    response.status, response.body, received)
            except BaseException as error:
                _failure('authenticated cancellation failed; do not resend', error)


def prepare_cancel_transport(*, wire, pin, capability, expected_capability_hash,
                             resolve_secret, http, expected_http_hash, now):
    """Resolve/load once before controller authorization time; no network in preparation."""
    try:
        cap = capability
        if (type(cap) is not CancelTransportCapability or cap.digest != expected_capability_hash
                or cap.http_hash != expected_http_hash or type(wire) is not CancelWire
                or type(pin) is not KalshiPin):
            raise TransportError('cancel transport capability/type pin mismatch')
        cap.__post_init__()
        wire.__post_init__()
        pin.__post_init__()
        if (wire.account != cap.account or pin.account != cap.account
                or wire.adapter_hash != pin.digest or cap.adapter_hash != pin.digest
                or wire.market_ticker != pin.ticker or wire.subaccount != pin.subaccount):
            raise TransportError('cancel target/account/adapter binding mismatch')
        if not all(callable(c) for c in (resolve_secret, http, now)):
            raise TransportError('explicit cancel transport providers required')
        start = _clock(now)
        until = min(start + cap.ready_lifetime_ns, wire.expires_ns)
        if until <= start:
            raise TransportError('cancel wire already expired')
        secrets = resolve_secret(cap.credential)
        if type(secrets) is not KalshiSecrets:
            raise TransportError('Kalshi credentials required')
        key = serialization.load_pem_private_key(secrets.private_key_pem, password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise TransportError('RSA private key of at least 2048 bits required')
        finished = _clock(now)
        if not start <= finished < until:
            raise TransportError('cancel preparation expired or clock moved backwards')
        return ReadyCancelTransport(wire, cap, http, now, key, secrets, finished, until)
    except BaseException as error:
        _failure('cancellation transport preparation failed', error)
