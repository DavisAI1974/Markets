"""Refresh the retained Granite Pod's bootstrap download capabilities (runbook step 5, URLs only).

    python research/kalshi/frankie_boss/operations/refresh_bootstrap_urls.py --pod ycf4v6lmave6xw
        --runtime-configuration <json path> [--expires-seconds 518400]

granite_startup_pins.validate_url_freshness refuses a start unless RP_BOOTSTRAP_URLS holds one
presigned https URL per roster file plus runpod_bundle.json, each with X-Amz-Date/X-Amz-Expires
(span at most 7 days) and the earliest expiry at least 60 s ahead. This re-signs the EXACT objects
the Pod already references: it reads the current URLs from the Pod environment, verifies each object
in S3 against the reviewed roster (size and sha256), presigns the same bucket/key with a fresh span,
and patches ONLY RP_BOOTSTRAP_URLS, sending back every other environment value unchanged
(PATCH /v2/pods/{id} on api.runpod.io, env as a map). It reads the Pod back and compares. It never
prints a URL, a key, or any environment value.
"""
import argparse
import datetime
import hashlib
import http.client
import json
import os
from urllib.parse import parse_qs, urlsplit

import boto3

CONTROL = 'api.runpod.io'   # v2 control plane: GET /v2/pods/{id}; PATCH /v2/pods/{id} with env as a map


def control_call(key, method, path, body=None):
    connection = http.client.HTTPSConnection(CONTROL, timeout=20)
    try:
        raw = None if body is None else json.dumps(body, allow_nan=False).encode()
        connection.request(method, path, raw, {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                                               'Content-Type': 'application/json'})
        response = connection.getresponse()
        data = response.read(1048577)
        if response.status not in (200, 201, 204):
            raise SystemExit('control %s %s -> %d' % (method, path, response.status))
        return json.loads(data) if data else None
    finally:
        connection.close()


def bucket_key(url):
    parts = urlsplit(url)
    host = parts.hostname or ''
    if parts.scheme != 'https' or not host.endswith('.amazonaws.com'):
        raise SystemExit('existing bootstrap URL is not an S3 https URL')
    bucket = host.split('.s3')[0]
    key = parts.path.lstrip('/')
    if not bucket or not key:
        raise SystemExit('existing bootstrap URL lacks bucket or key')
    region = 'us-east-1'
    if '.s3.' in host:
        candidate = host.split('.s3.')[1].split('.')[0]
        if candidate and candidate != 'amazonaws':
            region = candidate
    return bucket, key, region


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pod', required=True)
    parser.add_argument('--runtime-configuration', required=True)
    parser.add_argument('--expires-seconds', type=int, default=518400)   # 6 days; validator allows up to 604800
    args = parser.parse_args()
    if not 60 < args.expires_seconds <= 604800:
        raise SystemExit('expiry span must be within (60, 604800]')
    key = os.environ['RUNPOD_API_KEY']
    configuration = json.load(open(args.runtime_configuration, 'rb'))
    expected = {row['path']: row for row in configuration['files']}
    expected['runpod_bundle.json'] = {'path': 'runpod_bundle.json', 'size': None, 'sha256': configuration['bundle_sha256']}

    pod = control_call(key, 'GET', '/v2/pods/' + args.pod)
    if pod.get('id') != args.pod:
        raise SystemExit('pod identity differs')
    status = pod.get('desiredStatus') or pod.get('status')
    environment = dict(pod['env'])
    if 'RP_BOOTSTRAP_URLS' not in environment:
        raise SystemExit('pod environment has no RP_BOOTSTRAP_URLS to refresh')
    current = json.loads(environment['RP_BOOTSTRAP_URLS'])
    if set(current) != set(expected):
        raise SystemExit('pod bootstrap roster differs from the reviewed roster: %s' % sorted(set(current) ^ set(expected)))
    if environment.get('RUNPOD_BUNDLE_SHA256') != configuration['bundle_sha256']:
        raise SystemExit('pod bundle sha differs from the reviewed runtime configuration')

    # SigV4, virtual-hosted: granite_startup_pins.validate_url_freshness requires X-Amz-Date and
    # X-Amz-Expires, and the Pod's bootstrap accepts only <bucket>.s3.amazonaws.com or
    # <bucket>.s3.us-east-1.amazonaws.com as the origin (granite_runpod_cloud.bootstrap_command).
    from botocore.config import Config
    signing = Config(signature_version='s3v4', s3={'addressing_style': 'virtual'})
    s3_by_region = {}
    fresh = {}
    earliest = None
    for name, url in current.items():
        bucket, s3key, region = bucket_key(url)
        s3 = s3_by_region.setdefault(region, boto3.client('s3', region_name=region, config=signing))
        data = s3.get_object(Bucket=bucket, Key=s3key)['Body'].read(65537)
        row = expected[name]
        if len(data) > 65536 or (row['size'] is not None and len(data) != row['size']) or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise SystemExit('staged object for %s differs from the reviewed roster' % name)
        signed = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': s3key},
                                           ExpiresIn=args.expires_seconds)
        parts = urlsplit(signed)
        if parts.scheme != 'https' or parts.hostname not in (bucket + '.s3.amazonaws.com', bucket + '.s3.us-east-1.amazonaws.com'):
            raise SystemExit('generated URL origin would be refused by the Pod bootstrap: %s' % (parts.hostname,))
        query = parse_qs(parts.query, strict_parsing=True)
        if 'X-Amz-Date' not in query or 'X-Amz-Expires' not in query:
            raise SystemExit('generated URL is not SigV4 (no X-Amz-Date/X-Amz-Expires); refusing')
        start = datetime.datetime.strptime(query['X-Amz-Date'][0], '%Y%m%dT%H%M%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
        expiry = start + int(query['X-Amz-Expires'][0])
        earliest = expiry if earliest is None else min(earliest, expiry)
        fresh[name] = signed

    patched = dict(environment)
    patched['RP_BOOTSTRAP_URLS'] = json.dumps(fresh)
    control_call(key, 'PATCH', '/v2/pods/' + args.pod, {'env': patched})

    after = control_call(key, 'GET', '/v2/pods/' + args.pod)
    got = dict(after['env'])
    unchanged = all(got.get(k) == v for k, v in environment.items() if k != 'RP_BOOTSTRAP_URLS')
    same_keys = set(got) == set(environment)
    applied = json.loads(got.get('RP_BOOTSTRAP_URLS', '{}')) == fresh
    if not (unchanged and same_keys and applied):
        raise SystemExit('readback differs: unchanged=%s same_keys=%s urls_applied=%s' % (unchanged, same_keys, applied))
    print(json.dumps(dict(status='bootstrap_urls_refreshed', pod=args.pod, pod_status=status,
                          files=sorted(fresh), verified_objects=len(fresh), other_env_keys_unchanged=len(environment) - 1,
                          earliest_expiry_utc=datetime.datetime.fromtimestamp(earliest, datetime.timezone.utc).isoformat(),
                          expires_seconds=args.expires_seconds)))


if __name__ == '__main__':
    main()
