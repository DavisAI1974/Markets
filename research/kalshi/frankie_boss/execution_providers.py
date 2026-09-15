"""Explicit concrete providers. Constructing them performs no I/O.

Use HTTPSExchange only behind the independently pinned transport capability.
FileSecretProvider reads an operator-provisioned private file; it does not grant
filesystem permissions, discover credentials, or certify venue account authority.
"""
import http.client
import os
from pathlib import Path
import re
import ssl
import stat
import socket
import threading
import time
from urllib.parse import unquote, urlsplit

from .execution_auth import CredentialReference, KalshiSecrets, TastytradeSecrets
from .execution_transport import HTTPResponse, ORIGINS, TransportError, _failure, _object


class HTTPSExchange:
    """One direct TLS exchange, with a network deadline and bounded body size.

No proxy environment, redirects, retries, pooling, auth refresh or HTTP debug
output. A watchdog interrupts the connected socket at the deadline, including
slow response headers/body. OS DNS resolution can outlive the timeout; an expired
connect is rejected before request transmission. Hard process-return deadlines
need an external runtime boundary and the ledger's uncertain outcome handling.
"""
    __slots__ = ('_origin', '_max_response_bytes')

    def __init__(self, *, origin: str, max_response_bytes: int = 4 * 1024 * 1024):
        if origin not in ORIGINS.values():
            raise TransportError('official HTTPS origin required')
        if type(max_response_bytes) is not int or not 0 < max_response_bytes <= 16 * 1024 * 1024:
            raise TransportError('bounded response size required')
        self._origin, self._max_response_bytes = origin, max_response_bytes

    def __call__(self, *, method, url, headers, body, timeout_ms, follow_redirects, retries):
        connection = None
        response = None
        timer = None
        try:
            entered = time.monotonic()
            if follow_redirects is not False or type(retries) is not int or retries != 0:
                raise TransportError('redirects and retries forbidden')
            if type(timeout_ms) is not int or not 0 < timeout_ms <= 60_000:
                raise TransportError('bounded socket timeout required')
            if method not in ('GET', 'POST', 'DELETE', 'PUT') or type(body) is not bytes:
                raise TransportError('supported method and exact bytes required')
            if type(url) is not str or any(ord(c) < 33 or ord(c) > 126 for c in url):
                raise TransportError('invalid URL characters')
            parsed = urlsplit(url)
            if parsed.scheme + '://' + parsed.netloc != self._origin or parsed.fragment or '#' in url:
                raise TransportError('exact origin and no fragment required')
            path = unquote(parsed.path)
            if (not path.startswith('/') or path.startswith('//') or '\\' in path
                    or any(p in ('.', '..') for p in path.split('/'))
                    or any(ord(c) < 33 or ord(c) > 126 for c in path)):
                raise TransportError('invalid relative request path')
            if type(headers) is not dict:
                raise TransportError('typed headers required')
            seen = set()
            for name, value in headers.items():
                if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9-]+', name)
                        or name.lower() in seen
                        or name.lower() in ('host', 'content-length', 'transfer-encoding',
                                           'connection', 'proxy-authorization', 'proxy-connection')
                        or type(value) is not str
                        or any(ord(c) < 32 or ord(c) > 126 for c in value)):
                    raise TransportError('invalid or reserved request header')
                seen.add(name.lower())
            context = ssl.create_default_context()
            context.set_alpn_protocols(['http/1.1'])
            deadline = entered + timeout_ms / 1000
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError('exchange preparation deadline exceeded')
            connection = http.client.HTTPSConnection(parsed.hostname,
                timeout=remaining, context=context)
            connection.set_debuglevel(0)
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError('connection deadline exceeded')
            connected_socket = connection.sock
            connected_socket.settimeout(remaining)
            def expire():
                try:
                    connected_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            timer = threading.Timer(remaining, expire)
            timer.daemon = True
            timer.start()
            target = parsed.path + ('?' + parsed.query if parsed.query else '')
            connection.request(method, target, body=body, headers=dict(headers))
            response = connection.getresponse()
            expected_length = response.length
            payload = response.read(self._max_response_bytes + 1)
            if len(payload) > self._max_response_bytes:
                raise TransportError('response byte budget exceeded')
            if expected_length is not None and len(payload) != expected_length:
                raise TransportError('incomplete response body')
            if time.monotonic() >= deadline:
                raise TransportError('exchange deadline exceeded')
            return HTTPResponse(response.status, payload, url)
        except BaseException as error:
            _failure('HTTPS exchange failed; do not resend', error)
        finally:
            if timer is not None:
                timer.cancel()
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            if connection is not None:
                # Cleanup errors cannot leak backend text or cause a second request.
                try:
                    connection.close()
                except Exception:
                    pass


class FileSecretProvider:
    """Explicit single-reference local store with a strict JSON envelope.

Envelope: {"credential_hash": <CredentialReference.digest>, "secrets": {...}}.
Kalshi fields: key_id, private_key_pem (PEM text); tastytrade fields:
refresh_token, client_secret. Exact fields only. No default path or environment
discovery. Provision outside Git with private filesystem ACLs. The reference
digest binds public identity, not secret bytes or an authentic rotation history.
"""
    __slots__ = ('_reference', '_path')

    def __init__(self, *, reference: CredentialReference, path: Path):
        if type(reference) is not CredentialReference or reference.account.venue not in ('kalshi', 'tastytrade'):
            raise TransportError('typed supported credential reference required')
        path = Path(path)
        if not path.is_absolute():
            raise TransportError('explicit absolute secret path required')
        self._reference, self._path = reference, path

    def __repr__(self):
        return 'FileSecretProvider(<redacted>)'

    def __call__(self, reference):
        try:
            if type(reference) is not CredentialReference or reference != self._reference:
                raise TransportError('secret reference mismatch')
            if self._path.is_symlink():
                raise TransportError('secret symlink forbidden')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            with os.fdopen(os.open(self._path, flags), 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                    raise TransportError('bounded regular secret file required')
                payload = stream.read(65537)
            if len(payload) > 65536:
                raise TransportError('secret byte budget exceeded')
            envelope = _object(payload)
            if set(envelope) != {'credential_hash', 'secrets'} or envelope['credential_hash'] != reference.digest:
                raise TransportError('secret envelope binding mismatch')
            values = envelope['secrets']
            expected = ({'key_id', 'private_key_pem'} if reference.account.venue == 'kalshi'
                        else {'refresh_token', 'client_secret'})
            if type(values) is not dict or set(values) != expected or any(type(v) is not str for v in values.values()):
                raise TransportError('exact typed secret fields required')
            if reference.account.venue == 'kalshi':
                return KalshiSecrets(values['key_id'], values['private_key_pem'].encode('ascii'))
            return TastytradeSecrets(values['refresh_token'], values['client_secret'])
        except BaseException as error:
            _failure('secret file resolution failed', error)
