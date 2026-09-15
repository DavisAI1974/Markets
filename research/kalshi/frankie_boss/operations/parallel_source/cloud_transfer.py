"""Private S3 snapshot transfer for one isolated GitHub verification job."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import time

BUCKET = 'bento-568968024170-us-east-2-an'
PREFIX = 'nymex/ng_mbo_5y_v0/frankie/parallel_source_verification/'

def load_request():
    request = json.loads(Path('.github/frankie-parallel-source-request.json').read_bytes())
    if (request['schema'] != 'FRANKIE_GITHUB_PARALLEL_VERIFY_REQUEST_V1'
            or len(request['archive_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in request['archive_sha256'])
            or type(request['archive_bytes']) is not int
            or not 0 < request['archive_bytes'] <= 5*1024**3
            or type(request['uncompressed_bytes']) is not int
            or not 0 < request['uncompressed_bytes'] <= 20*1024**3
            or type(request['bundle_manifest_sha256']) is not str
            or len(request['bundle_manifest_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in request['bundle_manifest_sha256'])):
        raise ValueError('invalid pinned snapshot request')
    return request

def client():
    import boto3
    from botocore.config import Config
    return boto3.client('s3', region_name='us-east-2', config=Config(
        signature_version='s3v4', s3={'addressing_style':'virtual'},
        connect_timeout=10, read_timeout=60, retries={'mode':'standard','max_attempts':3}))

def stage(request, destination):
    spec = importlib.util.spec_from_file_location('stage_crypto',
        'research/kalshi/frankie_boss/granite_request_stage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checksum = base64.b64encode(bytes.fromhex(request['archive_sha256'])).decode()
    key = PREFIX + request['archive_sha256'] + '.tar.gz'
    headers = {'content-length':str(request['archive_bytes']),
        'content-type':'application/gzip', 'if-none-match':'*',
        'x-amz-checksum-sha256':checksum, 'x-amz-server-side-encryption':'AES256'}
    s3 = client()
    try:
        url = s3.generate_presigned_url('put_object', Params=dict(Bucket=BUCKET, Key=key,
            ContentLength=request['archive_bytes'], ContentType='application/gzip',
            IfNoneMatch='*', ChecksumSHA256=checksum, ServerSideEncryption='AES256'),
            ExpiresIn=3600, HttpMethod='PUT')
        receipt = dict(request_sha256=request['archive_sha256'], method='PUT', url=url,
            headers=headers, bucket=BUCKET, key=key, expires_at=time.time()+3600)
        encrypted = module.encrypt_receipt(receipt, request['recipient_public_key_der_base64'])
        destination.mkdir(parents=True, exist_ok=False)
        (destination/'upload-capability.encrypted.json').write_text(json.dumps(encrypted), encoding='utf-8')
    finally:
        s3.close()
    print('Encrypted upload capability ready; original source and Pod untouched.', flush=True)

def safe_members(archive):
    seen = set()
    total = 0
    for member in archive:
        parts = Path(member.name).parts
        if (member.name in seen or not parts or parts[0] != 'bundle'
                or '..' in parts or member.name.startswith('/')
                or not (member.isfile() or member.isdir())):
            raise ValueError('unsafe snapshot archive member')
        seen.add(member.name)
        total += member.size
        if total > 20*1024**3:
            raise ValueError('snapshot archive exceeds accepted size')
        yield member

def fetch(request, destination):
    destination.mkdir(parents=True, exist_ok=False)
    required = request['uncompressed_bytes'] + request['archive_bytes'] + 512*1024**2
    available = shutil.disk_usage(destination).free
    print(json.dumps(dict(phase='runner_disk_admission', available_bytes=available, required_bytes=required)), flush=True)
    if available < required:
        raise ValueError('runner disk cannot hold exact snapshot')
    key = PREFIX + request['archive_sha256'] + '.tar.gz'
    s3 = client()
    try:
        # Only an absent object is retried here. An existing wrong object fails closed.
        while True:
            try:
                head = s3.head_object(Bucket=BUCKET, Key=key)
                break
            except Exception as error:
                if getattr(error,'response',{}).get('Error',{}).get('Code') not in ('404','NoSuchKey'):
                    raise
                print(json.dumps(dict(phase='waiting_for_exact_snapshot_upload', at=time.time())), flush=True)
                time.sleep(30)
        if (head['ContentLength'] != request['archive_bytes']
                or head.get('ServerSideEncryption') != 'AES256'):
            raise ValueError('private snapshot object identity differs')
        digest = hashlib.sha256()
        size = 0
        archive_path = destination/'source-snapshot.tar.gz'
        result = s3.get_object(Bucket=BUCKET, Key=key)
        with result['Body'] as source, archive_path.open('xb') as output:
            while chunk := source.read(8*1024**2):
                output.write(chunk)
                size += len(chunk)
                digest.update(chunk)
                if size > request['archive_bytes']:
                    raise ValueError('snapshot read exceeded pinned size')
        if size != request['archive_bytes'] or digest.hexdigest() != request['archive_sha256']:
            raise ValueError('snapshot transport digest differs')
        print(json.dumps(dict(phase='snapshot_download_verified', bytes=size)), flush=True)
        with tarfile.open(archive_path,'r:gz') as archive:
            archive.extractall(destination, members=safe_members(archive), filter='data')
        manifest_path = destination/'bundle/bundle-manifest.json'
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != request['bundle_manifest_sha256']:
            raise ValueError('snapshot manifest digest differs')
        # Only the disposable downloaded archive is removed, after verified extraction.
        archive_path.unlink()
        print('Exact private snapshot extracted; ready for independent verification.', flush=True)
    finally:
        s3.close()

if __name__ == '__main__':
    try:
        request = load_request()
        (stage if sys.argv[1] == 'stage' else fetch)(request, Path(sys.argv[2]))
    except Exception as error:
        print('Parallel source transfer failed: '+type(error).__name__, flush=True)
        raise SystemExit(1) from None
