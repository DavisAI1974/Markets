"""Issue one short-lived, checksum-bound PUT capability; no Runpod operations.

Run directly to avoid loading the native model package on this staging host.
The capability artifact is sensitive. Never print its URL or exception text.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlsplit

BUCKET = 'bento-568968024170-us-east-2-an'
PREFIX = 'nymex/ng_mbo_5y_v0/frankie/boss_requests/'
MAXIMUM_BYTES = 1024 * 1024
EXPIRY_SECONDS = 900


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def encrypt_receipt(receipt, public_der_b64):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    public_der = base64.b64decode(public_der_b64, validate=True)
    public_key = serialization.load_der_public_key(public_der)
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 3072:
        raise ValueError('local recipient RSA public key of at least 3072 bits required')
    metadata = dict(schema='GRANITE_ENCRYPTED_STAGE_V1',
        algorithm='RSA-OAEP-SHA256+AES-256-GCM', request_sha256=receipt['request_sha256'],
        recipient_sha256=hashlib.sha256(public_der).hexdigest())
    aad = canonical(metadata)
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, canonical(receipt), aad)
    wrapped = public_key.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                algorithm=hashes.SHA256(), label=aad))
    return dict(metadata, nonce=base64.b64encode(nonce).decode(),
                ciphertext=base64.b64encode(ciphertext).decode(),
                wrapped_key=base64.b64encode(wrapped).decode())


def decrypt_receipt(envelope, private_key, expected_request_sha256):
    """Local memory-only helper; caller must never print the returned capability."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    public_der = private_key.public_key().public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    metadata = dict(schema='GRANITE_ENCRYPTED_STAGE_V1',
        algorithm='RSA-OAEP-SHA256+AES-256-GCM', request_sha256=expected_request_sha256,
        recipient_sha256=hashlib.sha256(public_der).hexdigest())
    if (set(envelope) != set(metadata) | {'nonce', 'ciphertext', 'wrapped_key'}
            or any(envelope[k] != v for k, v in metadata.items())):
        raise ValueError('encrypted staging recipient or request binding differs')
    aad = canonical(metadata)
    key = private_key.decrypt(base64.b64decode(envelope['wrapped_key'], validate=True),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=aad))
    raw = AESGCM(key).decrypt(base64.b64decode(envelope['nonce'], validate=True),
                             base64.b64decode(envelope['ciphertext'], validate=True), aad)
    receipt = json.loads(raw)
    if receipt['request_sha256'] != expected_request_sha256:
        raise ValueError('decrypted request binding differs')
    return receipt


def stage(client, digest, size, *, now=time.time):
    if (type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)
            or type(size) is not int or not 1 <= size <= MAXIMUM_BYTES):
        raise ValueError('exact request digest and accepted request byte count required')
    key = PREFIX+digest+'.json'
    receipt = dict(schema='GRANITE_EXACT_REQUEST_STAGE_V1', bucket=BUCKET,
                   key=key, request_sha256=digest, request_bytes=size)
    try:
        existing = client.get_object(Bucket=BUCKET, Key=key)
    except Exception as error:
        if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('NoSuchKey', '404'):
            raise
    else:
        with existing['Body'] as stream:
            if existing['ContentLength'] != size:
                raise ValueError('existing digest-key object has a different size')
            raw = stream.read(size+1)
        if (len(raw) != size or hashlib.sha256(raw).hexdigest() != digest
                or existing.get('ServerSideEncryption') != 'AES256'
                or existing.get('ContentType') != 'application/json'):
            raise ValueError('existing digest-key object differs from exact request contract')
        return dict(receipt, status='existing_verified', verified_at=now())
    checksum = base64.b64encode(bytes.fromhex(digest)).decode('ascii')
    headers = {'content-length': str(size), 'content-type': 'application/json',
               'if-none-match': '*', 'x-amz-checksum-sha256': checksum,
               'x-amz-server-side-encryption': 'AES256'}
    params = dict(Bucket=BUCKET, Key=key, ContentLength=size,
                  ContentType='application/json', IfNoneMatch='*',
                  ChecksumSHA256=checksum, ServerSideEncryption='AES256')
    issued = now()
    url = client.generate_presigned_url('put_object', Params=params,
        ExpiresIn=EXPIRY_SECONDS, HttpMethod='PUT')
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    signed = set(query.get('X-Amz-SignedHeaders', [''])[0].split(';'))
    if (parsed.scheme != 'https' or parsed.hostname != BUCKET+'.s3.us-east-2.amazonaws.com'
            or query.get('X-Amz-Expires') != [str(EXPIRY_SECONDS)]
            or not set(headers) <= signed):
        raise ValueError('presigned capability did not bind every required request header')
    return dict(receipt, status='put_required', method='PUT', url=url, headers=headers,
                issued_at=issued, expires_at=issued+EXPIRY_SECONDS,
                overwrite_allowed=False)


def main():
    import boto3
    from botocore.config import Config
    config = Config(signature_version='s3v4', s3={'addressing_style': 'virtual'},
                    connect_timeout=5, read_timeout=10,
                    retries={'total_max_attempts': 1, 'mode': 'standard'})
    client = boto3.client('s3', region_name='us-east-2', config=config)
    try:
        digest, size = os.environ.get('REQUEST_SHA256'), os.environ.get('REQUEST_BYTES')
        public_key = os.environ.get('RECIPIENT_PUBLIC_KEY_DER_BASE64')
        if not digest and not size:
            marker = json.loads(Path('.github/frankie-request-stage-request.json').read_bytes())
            if (set(marker) != {'request_sha256', 'request_bytes', 'recipient_public_key_der_base64'}
                    or type(marker['request_bytes']) is not int):
                raise ValueError('exact request staging marker required')
            digest, size = marker['request_sha256'], marker['request_bytes']
            public_key = marker['recipient_public_key_der_base64']
        else:
            size = int(size)
        result = stage(client, digest, size)
        encrypted = encrypt_receipt(result, public_key)
        directory = Path('work/request-stage-sensitive')
        directory.mkdir(parents=True, exist_ok=False)
        (directory/'request-stage.encrypted.json').write_bytes(canonical(encrypted))
        print('Exact request staging capability prepared; no Pod action performed.')
    except Exception as error:
        # SDK errors may include request URLs; only the error type is safe.
        print('Request staging failed: '+type(error).__name__)
        raise SystemExit(1) from None
    finally:
        client.close()


if __name__ == '__main__':
    main()
