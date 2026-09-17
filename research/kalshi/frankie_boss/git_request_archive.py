"""Read an authenticated, immutable Git request archive without S3 data copies."""
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'FRANKIE_GIT_REQUEST_ARCHIVE_V1'


def read_request_archive(directory, expected_sha256, client):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    directory = Path(directory)
    envelope = json.loads((directory / 'envelope.json').read_bytes())
    if (set(envelope) != {'schema', 'request_sha256', 'ciphertext_sha256', 'nonce_hex',
                         'key_parameter', 'key_region'}
            or envelope['schema'] != SCHEMA
            or envelope['request_sha256'] != expected_sha256
            or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            or not re.fullmatch(r'/markets/frankie/request-transport/[A-Za-z0-9_-]{1,80}',
                                envelope['key_parameter'])
            or envelope['key_region'] != 'us-east-2'
            or not re.fullmatch(r'[0-9a-f]{24}', envelope['nonce_hex'])):
        raise ValueError('exact Git request archive binding required')
    ciphertext = (directory / 'request.enc').read_bytes()
    if hashlib.sha256(ciphertext).hexdigest() != envelope['ciphertext_sha256']:
        raise ValueError('Git request ciphertext differs')
    try:
        parameter = client.get_parameter(Name=envelope['key_parameter'],
                                         WithDecryption=True)['Parameter']
        if parameter['Type'] != 'SecureString':
            raise ValueError()
        key = bytes.fromhex(parameter['Value'])
        if len(key) != 32:
            raise ValueError()
        body = AESGCM(key).decrypt(bytes.fromhex(envelope['nonce_hex']),
                                  ciphertext, expected_sha256.encode('ascii'))
    except Exception:
        raise ValueError('private Git request decryption failed') from None
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError('Git request plaintext differs')
    return body
