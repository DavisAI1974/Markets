"""Close a stale active-run claim on a retained Pod so a new observer startup can claim it (2026-09-20).

Why: granite_active_run.ActiveRunStore records which observer STARTUP owns a Pod
(retained-granite-pods/<pod>/active-run.json, phase active|stopping|closed) and releases it only through
the completion cleanup, i.e. after a confirmed Pod STOP. Observer run 35507527320 (request 6cd46f98...,
startup 132d8b71...) claimed 8vqdacl5t61rjx at 11:19Z; that world is dead (its readiness pinned a
request the host can no longer prepare, the run was cancelled, its readiness and trigger were moved
aside on the host with receipts), but its claim stays 'active' and observer run 35519228804 refused
with 'another active or stopping run owns this Pod'. Stopping the Pod to release it lawfully would
lose the GPU under LOW L40S stock (the standing lesson). Greg's rule for launch day: a provenance
guard that blocks the launch is overridden with a receipt, never silently.

What this does: reads the record with the same validation as the store, refuses unless its
startup_sha256 starts with the operator-supplied digest and its phase is active or stopping, COPIES
the record server-side to retained-granite-pods/<pod>/superseded/active-run-<stamp>-<digest12>.json
(never deletes), then writes phase 'closed' with the conditional ETag the store itself uses, reads it
back and prints one RECEIPT line. Starts, stops and restarts nothing; no Runpod call. Inspect mode
prints the record and exits.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys

import boto3

SCHEMA = 'FRANKIE_ACTIVE_RUN_SUPERSEDED_V1'
MAX_RECORD_BYTES = 2048


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read(s3, bucket, key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception as error:  # noqa: BLE001 - the store treats a missing key as no claim
        if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
            return None, None
        raise
    with response['Body'] as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES or len(raw) != response['ContentLength']:
        raise SystemExit('invalid active-run record size')
    value = json.loads(raw)
    if (set(value) != {'schema', 'pod_id', 'startup_sha256', 'phase'}
            or value['schema'] != 'GRANITE_POD_ACTIVE_RUN_V1'
            or value['phase'] not in ('active', 'stopping', 'closed')
            or type(value['startup_sha256']) is not str
            or not re.fullmatch('[0-9a-f]{64}', value['startup_sha256'])
            or not response.get('ETag')):
        raise SystemExit('invalid active-run identity')
    return value, response['ETag']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pod', required=True)
    parser.add_argument('--action', choices=('inspect', 'close'), default='inspect')
    parser.add_argument('--expect-startup-sha256', default='',
                        help='close only: the stale startup digest (at least 8 hex, prefix match)')
    parser.add_argument('--reason', default='')
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9]{1,64}', args.pod):
        raise SystemExit('exact Pod identity required')
    account = boto3.client('sts', region_name='us-east-1').get_caller_identity()['Account']
    bucket = 'frankie-granite42-' + account + '-us-east-1'
    key = 'retained-granite-pods/' + args.pod + '/active-run.json'
    s3 = boto3.client('s3', region_name='us-east-1')
    value, etag = read(s3, bucket, key)
    print('ACTIVE_RUN ' + json.dumps(dict(key=key, record=value)))
    if args.action == 'inspect':
        return 0
    if value is None:
        print('RECEIPT ' + json.dumps(dict(schema=SCHEMA, pod=args.pod, outcome='no_claim', key=key)))
        return 0
    if value['pod_id'] != args.pod:
        raise SystemExit('record names another Pod')
    expected = args.expect_startup_sha256.lower()
    if not re.fullmatch('[0-9a-f]{8,64}', expected) or not value['startup_sha256'].startswith(expected):
        raise SystemExit('refusing: --expect-startup-sha256 must name the stale startup (prefix of %s)'
                         % value['startup_sha256'])
    if value['phase'] == 'closed':
        print('RECEIPT ' + json.dumps(dict(schema=SCHEMA, pod=args.pod, outcome='already_closed',
                                          startup_sha256=value['startup_sha256'], key=key)))
        return 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    copy_key = ('retained-granite-pods/' + args.pod + '/superseded/active-run-' + stamp + '-'
                + value['startup_sha256'][:12] + '.json')
    s3.copy_object(Bucket=bucket, Key=copy_key, CopySource=dict(Bucket=bucket, Key=key),
                   ServerSideEncryption='AES256', MetadataDirective='COPY')
    copied, _ = read(s3, bucket, copy_key)
    if copied != value:
        raise SystemExit('superseded copy differs from the record; nothing was closed')
    closed = dict(value, phase='closed')
    s3.put_object(Bucket=bucket, Key=key, Body=canonical(closed), ServerSideEncryption='AES256',
                  ContentType='application/json', IfMatch=etag)
    actual, _ = read(s3, bucket, key)
    if actual != closed:
        raise SystemExit('active-run conditional write changed concurrently')
    print('RECEIPT ' + json.dumps(dict(schema=SCHEMA, pod=args.pod, outcome='closed', key=key,
                                      startup_sha256=value['startup_sha256'], phase_before=value['phase'],
                                      superseded_copy=copy_key, reason=args.reason, at=stamp)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
