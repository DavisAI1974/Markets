"""Pinned Granite bytes: sequential staging and mounted-file verification, no inference.

S3 uses whole-file streaming readback, never ETags as content checksums.
Sources: https://docs.aws.amazon.com/sagemaker/latest/dg/large-model-inference-uncompressed.html
https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/upload_file.html
https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html
"""
import hashlib
import json
from pathlib import Path
import re
import http.client
import urllib.error
import urllib.request

REPOSITORY = 'ibm-granite/granite-4.2-8b'
REVISION = 'f8de16cdcdbc6c779ca517604e050d82cc119e44'
DEFAULT_MANIFEST = Path(__file__).with_name('granite_artifacts_manifest.json')
SHARDS = {f'model-{i:05d}-of-00004.safetensors' for i in range(1, 5)}
FILES = SHARDS | {'config.json', 'generation_config.json', 'model.safetensors.index.json',
                 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja',
                 'special_tokens_map.json', 'vocab.json', 'merges.txt'}
BLOCK = 4 * 1024 * 1024
# Commitment to the account in the owner's private DROP_IN_CODEX.md. The raw
# private identifier remains outside Git; rotated credentials cannot change scope.
APPROVED_ACCOUNT_SHA256 = '3c7ffc6cc2835350849373c23a8e513bc07771ca2eceba2d683af17c5cb3fe26'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def validate_manifest(manifest):
    if (manifest.get('schema') != 'GRANITE_ARTIFACT_MANIFEST_V1' or
            manifest.get('repository') != REPOSITORY or manifest.get('revision') != REVISION):
        raise ValueError('unsupported artifact identity')
    rows = manifest.get('files')
    if type(rows) is not list or len(rows) != len(FILES):
        raise ValueError('exact artifact roster required')
    names = []
    for row in rows:
        if (type(row) is not dict or set(row) != {'path', 'size', 'sha256'} or
                row['path'] not in FILES or type(row['size']) is not int or row['size'] <= 0 or
                type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('invalid artifact entry')
        names.append(row['path'])
    if set(names) != FILES:
        raise ValueError('duplicate or missing artifact path')


def manifest_digest(manifest):
    validate_manifest(manifest)
    return hashlib.sha256(canonical(manifest)).hexdigest()


def verify_stream(stream, row, *, progress=None):
    digest, size = hashlib.sha256(), 0
    if progress is not None: progress('file_verify', row, 0)
    while chunk := stream.read(BLOCK):
        size += len(chunk)
        if size > row['size']:
            raise ValueError('artifact exceeds declared bytes: ' + row['path'])
        digest.update(chunk)
        if progress is not None: progress('file_verify', row, size)
    if size != row['size'] or digest.hexdigest() != row['sha256']:
        raise ValueError('artifact size/hash mismatch: ' + row['path'])
    return dict(row)


def verify_file(path, row, *, progress=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError('artifact must be a regular nonsymlink file')
    with path.open('rb') as stream:
        return verify_stream(stream, row, progress=progress)


def verify_index(data, manifest):
    validate_manifest(manifest)
    index = strict_json(data)
    mapping = index.get('weight_map')
    if type(mapping) is not dict or not mapping or any(type(v) is not str for v in mapping.values()) or set(mapping.values()) != SHARDS:
        raise ValueError('safetensors index shard roster mismatch')


def verify_directory(directory, manifest, *, progress=None):
    digest = manifest_digest(manifest)
    directory = Path(directory)
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != FILES:
        raise ValueError('mounted artifact roster mismatch')
    if progress is not None: progress('directory_verify')
    files = [verify_file(directory / row['path'], row, progress=progress) for row in manifest['files']]
    verify_index((directory / 'model.safetensors.index.json').read_bytes(), manifest)
    return {'schema': 'GRANITE_MOUNT_VERIFICATION_V1', 'manifest_sha256': digest,
            'files': files, 'bytes': sum(row['size'] for row in files),
            'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def prefix_for(manifest):
    return 'models/' + manifest_digest(manifest) + '/'


def listed_objects(client, bucket, prefix):
    result, seen, token = {}, set(), None
    for _ in range(100):
        args = {'Bucket': bucket, 'Prefix': prefix, 'MaxKeys': 1000}
        if token:
            args['ContinuationToken'] = token
        response = client.list_objects_v2(**args)
        for item in response.get('Contents', []):
            if item['Key'] in result:
                raise ValueError('duplicate S3 key')
            result[item['Key']] = item['Size']
        if not response.get('IsTruncated'):
            return result
        token = response.get('NextContinuationToken')
        if not token or token in seen:
            raise ValueError('invalid S3 pagination')
        seen.add(token)
    raise ValueError('S3 pagination bound exceeded')


def verify_s3_object(client, bucket, prefix, row):
    response = client.get_object(Bucket=bucket, Key=prefix + row['path'])
    body = response['Body']
    try:
        if response['ContentLength'] != row['size']:
            raise ValueError('S3 object size mismatch')
        result = verify_stream(body, row)
    finally:
        body.close()
    result.update(version_id=response.get('VersionId'), etag=response.get('ETag'))
    return result


def verify_s3(client, bucket, manifest):
    prefix = prefix_for(manifest)
    expected = {prefix + row['path']: row['size'] for row in manifest['files']}
    if listed_objects(client, bucket, prefix) != expected:
        raise ValueError('S3 artifact roster mismatch')
    files = [verify_s3_object(client, bucket, prefix, row) for row in manifest['files']]
    # A second listing detects size/roster changes during verification. Startup must
    # still rehash the mounted bytes: this is not immutable-storage attestation.
    if listed_objects(client, bucket, prefix) != expected:
        raise ValueError('S3 artifact roster changed')
    return {'schema': 'GRANITE_S3_VERIFICATION_V1', 'manifest_sha256': manifest_digest(manifest),
            'prefix': prefix, 'files': files, 'bytes': sum(row['size'] for row in files)}


def download_url(row):
    if row['path'] not in FILES:
        raise ValueError('unapproved artifact path')
    return f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{row["path"]}'


def download_file(row, directory, *, opener=urllib.request.urlopen, progress=None):
    """Resume only matching immutable URL + strong ETag; always rehash all bytes."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / row['path']
    url = download_url(row)
    partial = directory / (row['path'] + '.partial')
    metadata_path = directory / (row['path'] + '.partial.json')
    if directory.is_symlink() or any(p.is_symlink() for p in (path, partial, metadata_path)):
        raise ValueError('symlink staging path')
    if path.exists():
        verify_file(path, row, progress=progress)
        if progress is not None: progress('file_ready', row, row['size'])
        return path
    offset = partial.stat().st_size if partial.exists() else 0
    expected = {'url': url, 'sha256': row['sha256'], 'size': row['size']}
    headers = {'Accept-Encoding': 'identity'}
    if offset:
        metadata = strict_json(metadata_path.read_bytes())
        if any(metadata.get(k) != v for k, v in expected.items()) or not metadata.get('etag') or metadata['etag'].startswith('W/'):
            raise ValueError('partial download identity mismatch')
        if offset > row['size']:
            raise ValueError('partial file exceeds expected size')
        if offset == row['size']:
            verify_file(partial, row, progress=progress)
            partial.rename(path)
            metadata_path.unlink()
            if progress is not None: progress('file_ready', row, row['size'])
            return path
        headers.update(Range=f'bytes={offset}-', **{'If-Range': metadata['etag']})
    if progress is not None: progress('download_connect', row, offset)
    with opener(urllib.request.Request(url, headers=headers), timeout=60) as response:
        if offset:
            if (response.status != 206 or response.headers.get('ETag') != metadata['etag'] or
                    response.headers.get('Content-Range') != f'bytes {offset}-{row["size"]-1}/{row["size"]}'):
                raise ValueError('resume remote identity/range mismatch')
        elif response.status != 200:
            raise ValueError('download requires full successful response')
        etag = response.headers.get('ETag')
        metadata_path.write_bytes(canonical({**expected, 'etag': etag}))
        with partial.open('ab' if offset else ('wb' if partial.exists() else 'xb')) as stream:
            size = offset
            if progress is not None: progress('download', row, size)
            while chunk := response.read(BLOCK):
                size += len(chunk)
                if size > row['size']:
                    raise ValueError('download exceeds expected size')
                stream.write(chunk)
                if progress is not None: progress('download', row, size)
    verify_file(partial, row, progress=progress)
    partial.rename(path)
    metadata_path.unlink()
    if progress is not None: progress('file_ready', row, row['size'])
    return path


def save_receipt(path, receipt):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError('symlink receipt path')
    temporary.write_bytes(canonical(receipt))
    temporary.replace(path)


def download_verified_file(row, directory, *, attempts=3, downloader=None):
    """Bounded network recovery reuses the same pinned partial-file protocol."""
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError('one to five download attempts required')
    downloader = downloader or download_file
    for attempt in range(attempts):
        try:
            return downloader(row, directory)
        except (TimeoutError, ConnectionError, http.client.IncompleteRead, urllib.error.URLError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt + 1 == attempts:
                raise
            print('retrying immutable artifact download', row['path'], attempt + 2, flush=True)


def stage(client, bucket, manifest, directory, receipt_path, *, fetch=download_verified_file):
    """Upload one verified file at a time; existing objects are verified, not replaced."""
    prefix = prefix_for(manifest)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    expected = {prefix + row['path']: row['size'] for row in manifest['files']}
    existing = listed_objects(client, bucket, prefix)
    if any(key not in expected or expected[key] != size for key, size in existing.items()):
        raise ValueError('existing S3 artifact roster/size mismatch')
    receipt = {'schema': 'GRANITE_STAGING_RECEIPT_V1', 'manifest_sha256': manifest_digest(manifest),
               'prefix': prefix, 'status': 'staging', 'files': [],
               'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_receipt(receipt_path, receipt)
    # Verify any pre-existing bytes before performing new writes.
    for row in manifest['files']:
        if prefix + row['path'] in existing:
            receipt['files'].append(verify_s3_object(client, bucket, prefix, row))
            save_receipt(receipt_path, receipt)
    # Verify the index before staging the 17.6 GB weight set.
    ordered = sorted(manifest['files'], key=lambda row: (row['path'] != 'model.safetensors.index.json', row['path']))
    for row in ordered:
        if prefix + row['path'] in existing:
            continue
        path = fetch(row, directory)
        if path.resolve() != (directory / row['path']).resolve():
            raise ValueError('download escaped staging directory')
        verify_file(path, row)
        if row['path'] == 'model.safetensors.index.json':
            verify_index(path.read_bytes(), manifest)
        receipt['pending_upload'] = row['path']
        save_receipt(receipt_path, receipt)
        client.upload_file(str(path), bucket, prefix + row['path'],
                           ExtraArgs={'Metadata': {'sha256': row['sha256']}, 'ServerSideEncryption': 'AES256'})
        receipt['files'].append(verify_s3_object(client, bucket, prefix, row))
        del receipt['pending_upload']
        save_receipt(receipt_path, receipt)
        # Only this task-owned file is released, after complete S3 byte readback.
        path.unlink()
        print('verified', row['path'], row['size'], row['sha256'], flush=True)
    if listed_objects(client, bucket, prefix) != expected:
        raise ValueError('final S3 artifact roster mismatch')
    receipt['status'] = 'verified'
    receipt['bytes'] = sum(row['size'] for row in manifest['files'])
    save_receipt(receipt_path, receipt)
    return receipt


def ensure_scoped_bucket(client, account):
    if type(account) is not str or not re.fullmatch('[0-9]{12}', account):
        raise ValueError('valid caller account required')
    if hashlib.sha256(account.encode('ascii')).hexdigest() != APPROVED_ACCOUNT_SHA256:
        raise ValueError('caller must match the approved account')
    bucket = f'frankie-granite42-{account}-us-east-1'
    try:
        client.head_bucket(Bucket=bucket)
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in ('404', 'NoSuchBucket'):
            raise
        # us-east-1 requires no LocationConstraint. Never change an existing bucket.
        # https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html
        client.create_bucket(Bucket=bucket)
        client.head_bucket(Bucket=bucket)
    return bucket


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify-mount', 'stage', 'verify-s3'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--bucket')
    args = parser.parse_args(argv)
    manifest = strict_json(DEFAULT_MANIFEST.read_bytes())
    if args.command == 'verify-mount':
        save_receipt(args.receipt, verify_directory(args.directory, manifest))
        return 0
    import boto3
    from botocore.config import Config
    client = boto3.client('s3', region_name='us-east-1', config=Config(
        connect_timeout=10, read_timeout=60, retries={'total_max_attempts': 1, 'mode': 'standard'}))
    if not args.bucket:
        raise ValueError('explicit scoped bucket required')
    if args.command == 'stage':
        stage(client, args.bucket, manifest, args.directory, args.receipt)
    else:
        save_receipt(args.receipt, verify_s3(client, args.bucket, manifest))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
