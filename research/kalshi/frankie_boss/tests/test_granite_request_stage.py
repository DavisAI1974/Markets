import hashlib
import io

import boto3
from botocore.config import Config
from botocore.stub import Stubber
import pytest

from research.kalshi.frankie_boss import granite_request_stage as stage


def test_actual_sdk_signs_checksum_length_encryption_and_conditional_create():
    body = b'{"actual":true}'
    digest = hashlib.sha256(body).hexdigest()
    client = boto3.client('s3', region_name='us-east-2',
        aws_access_key_id='synthetic-key', aws_secret_access_key='synthetic-secret',
        config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
    with Stubber(client) as stub:
        stub.add_client_error('get_object', service_error_code='NoSuchKey', http_status_code=404,
                             expected_params={'Bucket': stage.BUCKET, 'Key': stage.PREFIX+digest+'.json'})
        receipt = stage.stage(client, digest, len(body), now=lambda: 1000.)
    assert receipt['status'] == 'put_required'
    assert receipt['headers']['if-none-match'] == '*'
    assert receipt['expires_at'] == 1900.
    assert receipt['overwrite_allowed'] is False
    client.close()


def test_existing_object_is_reused_only_after_full_byte_verification():
    body = b'{"actual":true}'
    digest = hashlib.sha256(body).hexdigest()
    class Client:
        def get_object(self, **kwargs):
            return dict(Body=io.BytesIO(body), ContentLength=len(body),
                        ServerSideEncryption='AES256', ContentType='application/json')
        def generate_presigned_url(self, *args, **kwargs):
            raise AssertionError('existing object must never receive overwrite capability')
    result = stage.stage(Client(), digest, len(body))
    assert result['status'] == 'existing_verified' and 'url' not in result
    with pytest.raises(ValueError, match='differs'):
        stage.stage(Client(), 'a'*64, len(body))


def test_public_artifact_hides_capability_and_binds_local_recipient_and_request():
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.exceptions import InvalidTag
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public_der = private.public_key().public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    receipt = {'request_sha256': 'a'*64, 'url': 'https://example.invalid/sensitive-capability',
               'headers': {'x-amz-checksum-sha256': 'bound-checksum'}}
    encrypted = stage.encrypt_receipt(receipt, base64.b64encode(public_der).decode())
    assert b'sensitive-capability' not in stage.canonical(encrypted)
    assert stage.decrypt_receipt(encrypted, private, 'a'*64) == receipt
    with pytest.raises(ValueError, match='binding differs'):
        stage.decrypt_receipt(encrypted, private, 'b'*64)
    altered = bytearray(base64.b64decode(encrypted['ciphertext']))
    altered[0] ^= 1
    with pytest.raises(InvalidTag):
        stage.decrypt_receipt(dict(encrypted, ciphertext=base64.b64encode(altered).decode()),
                              private, 'a'*64)
