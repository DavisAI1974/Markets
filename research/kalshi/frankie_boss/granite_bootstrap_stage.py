"""Stage a pinned committed bootstrap; no Pod operations or plaintext capabilities."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

try:
    from . import granite_runpod_package as package
    from .granite_request_stage import canonical, encrypt_receipt
except ImportError:
    import granite_runpod_package as package
    from granite_request_stage import canonical, encrypt_receipt

BUCKET = 'frankie-granite42-568968024170-us-east-1'
PREFIX = 'granite-bootstrap-open-run/'
DIRECTORY = '/opt/ml/additional-model-data-sources/bootstrap-open-run-v1'
EXPIRY = 900


def stage_bundle(client, directory, expected_sha256, *, now=time.time):
    directory = Path(directory)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('exact bundle digest required')
    raw = (directory/'runpod_bundle.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('bundle digest mismatch')
    manifest = json.loads(raw)
    if (set(manifest) != {'schema', 'files'} or manifest['schema'] != 'GRANITE_RUNPOD_BUNDLE_V1'
            or len(manifest['files']) != len(package.FILES)
            or {row['path'] for row in manifest['files']} != set(package.FILES)):
        raise ValueError('exact bootstrap roster required')
    values = {}
    for row in manifest['files']:
        path = directory/row['path']
        body = path.read_bytes()
        if (path.is_symlink() or set(row) != {'path', 'size', 'sha256'}
                or len(body) != row['size'] or not 0 < len(body) <= 65536
                or hashlib.sha256(body).hexdigest() != row['sha256']):
            raise ValueError('bootstrap file bytes differ')
        values[row['path']] = body
    values['runpod_bundle.json'] = raw
    # Validate every local byte before any external write.
    urls = {}
    issued = now()
    for name, body in values.items():
        key = PREFIX+expected_sha256+'/'+name
        checksum = base64.b64encode(hashlib.sha256(body).digest()).decode()
        try:
            existing = client.get_object(Bucket=BUCKET, Key=key)
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('NoSuchKey', '404'):
                raise
            try:
                client.put_object(Bucket=BUCKET, Key=key, Body=body, IfNoneMatch='*',
                    ChecksumSHA256=checksum, ServerSideEncryption='AES256', ContentType='application/octet-stream')
            except Exception as put_error:
                if getattr(put_error, 'response', {}).get('Error', {}).get('Code') != 'PreconditionFailed':
                    raise
            existing = client.get_object(Bucket=BUCKET, Key=key)
        with existing['Body'] as stream:
            stored = stream.read(len(body)+1)
        if (existing['ContentLength'] != len(body) or stored != body
                or existing.get('ServerSideEncryption') != 'AES256'):
            raise ValueError('stored bootstrap differs from committed bytes')
        url = client.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key},
            ExpiresIn=EXPIRY, HttpMethod='GET')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in (BUCKET+'.s3.us-east-1.amazonaws.com', BUCKET+'.s3.amazonaws.com')
                or parsed.path != '/'+key or parse_qs(parsed.query).get('X-Amz-Expires') != [str(EXPIRY)]):
            raise ValueError('unexpected bootstrap download capability')
        urls[name] = url
    return dict(schema='GRANITE_COMMITTED_BOOTSTRAP_STAGE_V1', request_sha256=expected_sha256,
        bundle_sha256=expected_sha256, bucket=BUCKET, runtime_directory=DIRECTORY,
        files=manifest['files'], urls=urls, issued_at=issued, expires_at=issued+EXPIRY, pod_actions=0)


def main():
    import boto3
    from botocore.config import Config
    client = None
    try:
        marker = json.loads(Path('.github/frankie-bootstrap-stage-request.json').read_bytes())
        if (set(marker) != {'source_commit', 'bundle_sha256', 'recipient_public_key_der_base64'}
                or not re.fullmatch('[0-9a-f]{40}', marker['source_commit'])):
            raise ValueError('exact committed bootstrap marker required')
        # Validate encryption recipient before writing remote objects.
        encrypt_receipt({'request_sha256': marker['bundle_sha256']}, marker['recipient_public_key_der_base64'])
        with tempfile.TemporaryDirectory(prefix='granite-bootstrap-') as scratch:
            root = Path(scratch); source = root/'source'; source.mkdir()
            for name in package.FILES:
                data = subprocess.check_output(['git', 'show', marker['source_commit']+':research/kalshi/frankie_boss/'+name])
                (source/name).write_bytes(data)
            packed = root/'package'
            receipt = package.package(source, packed, runtime_directory=DIRECTORY)
            if receipt['bundle_sha256'] != marker['bundle_sha256']:
                raise ValueError('committed package differs from independently supplied digest')
            client = boto3.client('s3', region_name='us-east-1', config=Config(signature_version='s3v4',
                s3={'addressing_style': 'virtual'}, connect_timeout=5, read_timeout=10,
                retries={'total_max_attempts': 1, 'mode': 'standard'}))
            result = stage_bundle(client, packed, marker['bundle_sha256'])
            result['source_commit'] = marker['source_commit']
            encrypted = encrypt_receipt(result, marker['recipient_public_key_der_base64'])
            output = Path('work/bootstrap-stage-sensitive'); output.mkdir(parents=True, exist_ok=False)
            (output/'bootstrap-stage.encrypted.json').write_bytes(canonical(encrypted))
            print('Pinned bootstrap staged and verified; no Pod action performed.')
    except Exception as error:
        print('Bootstrap staging failed: '+type(error).__name__)
        raise SystemExit(1) from None
    finally:
        if client is not None: client.close()


if __name__ == '__main__':
    main()
