import hashlib
import json

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from research.kalshi.frankie_boss.git_request_archive import read_request_archive, SCHEMA


class PrivateParameter:
    def __init__(self, key):
        self.key = key

    def get_parameter(self, **kwargs):
        assert kwargs == {'Name': '/markets/frankie/request-transport/test', 'WithDecryption': True}
        return {'Parameter': {'Type': 'SecureString', 'Value': self.key.hex()}}


def archive(tmp_path):
    key = b'k' * 32
    nonce = b'n' * 12
    body = b'{"messages":[{"role":"user","content":"exact admitted bytes"}]}'
    digest = hashlib.sha256(body).hexdigest()
    ciphertext = AESGCM(key).encrypt(nonce, body, digest.encode('ascii'))
    envelope = dict(schema=SCHEMA, request_sha256=digest,
                    ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
                    nonce_hex=nonce.hex(), key_parameter='/markets/frankie/request-transport/test',
                    key_region='us-east-2')
    (tmp_path / 'envelope.json').write_text(json.dumps(envelope))
    (tmp_path / 'request.enc').write_bytes(ciphertext)
    return body, digest, key


def test_git_transport_returns_exact_authenticated_request(tmp_path):
    body, digest, key = archive(tmp_path)
    assert read_request_archive(tmp_path, digest, PrivateParameter(key)) == body


def test_git_transport_rejects_changed_ciphertext(tmp_path):
    _, digest, key = archive(tmp_path)
    (tmp_path / 'request.enc').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='ciphertext differs'):
        read_request_archive(tmp_path, digest, PrivateParameter(key))


def test_git_transport_rejects_foreign_request_and_private_key_without_disclosure(tmp_path):
    _, digest, key = archive(tmp_path)
    with pytest.raises(ValueError, match='binding required'):
        read_request_archive(tmp_path, 'a' * 64, PrivateParameter(key))
    with pytest.raises(ValueError, match='decryption failed') as error:
        read_request_archive(tmp_path, digest, PrivateParameter(b'x' * 32))
    assert (b'x' * 32).hex() not in str(error.value)
