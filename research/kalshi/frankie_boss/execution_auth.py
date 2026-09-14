"""Transient authentication material. No secret discovery, network or logging.

Credential references are public configuration; secret values must never enter
Contract/asdict/evidence storage. Python memory is not a secure erasure boundary.
"""
import base64
from dataclasses import dataclass
import re
from urllib.parse import urlsplit
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from .execution_contracts import AccountKey, Contract


@dataclass(frozen=True)
class CredentialReference(Contract):
    account: AccountKey
    reference: str
    version: str


class KalshiSecrets:
    __slots__ = ('key_id', 'private_key_pem')

    def __init__(self, key_id: str, private_key_pem: bytes):
        if type(key_id) is not str or not re.fullmatch(r'[A-Za-z0-9_-]+', key_id):
            raise ValueError('invalid key identifier')
        if type(private_key_pem) is not bytes or not private_key_pem:
            raise ValueError('PEM bytes required')
        self.key_id, self.private_key_pem = key_id, private_key_pem

    def __repr__(self):
        return 'KalshiSecrets(<redacted>)'


class TastytradeSecrets:
    __slots__ = ('refresh_token', 'client_secret')

    def __init__(self, refresh_token: str, client_secret: str):
        if any(type(v) is not str or not v or any(ord(c) < 33 or ord(c) > 126 for c in v)
               for v in (refresh_token, client_secret)):
            raise ValueError('nonempty ASCII OAuth secrets required')
        self.refresh_token, self.client_secret = refresh_token, client_secret

    def __repr__(self):
        return 'TastytradeSecrets(<redacted>)'


def kalshi_signature(key, timestamp_ms: int, method: str, path: str) -> str:
    """Sign the documented full path, excluding query (never hostname)."""
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError('RSA private key of at least 2048 bits required')
    if type(timestamp_ms) is not int or timestamp_ms < 0 or method not in ('GET', 'POST', 'DELETE', 'PUT'):
        raise ValueError('invalid signature clock or method')
    if type(path) is not str or not path.startswith('/') or path.startswith('//') or '\\' in path:
        raise ValueError('relative request path required')
    if any(ord(c) < 33 or ord(c) > 126 for c in path) or '#' in path:
        raise ValueError('invalid request path characters')
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or any(p in ('.', '..') for p in parsed.path.split('/')):
        raise ValueError('invalid signature path')
    message = (str(timestamp_ms) + method + parsed.path).encode('ascii')
    return base64.b64encode(key.sign(message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256())).decode('ascii')
