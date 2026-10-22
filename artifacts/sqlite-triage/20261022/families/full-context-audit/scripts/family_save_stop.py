"""Fail-closed completion proof and durable save before an EC2 OS shutdown.

Separate from the numerical executors. No fit dispatch, deletion or EC2 API calls.
"""
import csv
import hashlib
import json
import math
import os
import pathlib

BUCKET = 'frankie-granite42-568968024170-us-east-1'
ACCOUNT = '568968024170'
GATE = 'NOT_PASSED'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def task_key(row):
    require(isinstance(row, (list, tuple)) and len(row) == 3, 'invalid task')
    kind, cohort, model = row
    require(kind in ('core', 'neural') and len(cohort) == 3 and bool(model), 'invalid task')
    return kind, tuple(map(str, cohort)), str(model)


def task_set(rows):
    keys = set(map(task_key, rows))
    require(len(keys) == len(rows) and bool(keys), 'empty or duplicate tasks')
    return keys


def validate_shard(config, plan, state, receipt):
    owner = config['owner']
    require(plan['instances'][owner] == config['instance'], 'instance ownership mismatch')
    cohorts = [tuple(r['cohort']) for r in plan['cohorts'] if r['owner'] == owner]
    if plan.get('reuse_enabled'):
        from family_reuse_support import cohorts_for_worker
        cohorts = cohorts_for_worker(None,plan,owner)
    require(len(set(cohorts)) == len(cohorts) and bool(cohorts), 'invalid owned cohorts')
    require(state['status'] == 'shard_fits_complete', 'mandatory fits incomplete')
    require(state['coverage_gate'] == receipt['coverage_gate'] == GATE, 'semantic gate changed')
    require(receipt['status'] == 'fits_complete' and receipt['worker'] == owner, 'wrong shard receipt')
    require(receipt['assignment_sha256'] == config['digest'], 'wrong assignment digest')
    require(len(receipt['cohorts']) == len(cohorts) and
            set(map(tuple, receipt['cohorts'])) == set(cohorts), 'cohort coverage mismatch')
    required = task_set(state['required_jobs'])
    require(required == task_set(state['committed_jobs']) == task_set(receipt['required_jobs']) ==
            task_set([r['task'] for r in receipt['locations']]), 'mandatory key mismatch')
    require({t for k, t, m in required} == set(cohorts), 'mandatory cohort mismatch')
    if plan.get('reuse_enabled'):
        from family_reuse_support import task_owner
        require(all(task_owner(plan,k)==owner for k in required),'receipt includes unowned delegated task')
    for row in receipt['locations']:
        p = pathlib.PurePosixPath(row['folder'])
        require(p.parent == pathlib.PurePosixPath('jobs') and '..' not in p.parts,
                'unsafe job location')
    require(receipt['archive_bytes'] > 0 and len(receipt['archive_sha256']) == 64,
            'missing archive identity')
    return required


def get_bytes(s3, key, limit=20 * 1024**2):
    response = s3.get_object(Bucket=BUCKET, Key=key, ExpectedBucketOwner=ACCOUNT)
    body = response['Body']
    try:
        require(response['ContentLength'] <= limit, 'oversized receipt')
        value = body.read(limit + 1)
        require(len(value) == response['ContentLength'] and len(value) <= limit, 'truncated receipt')
        return value
    finally:
        body.close()


def verify_remote(s3, key, sha256, expected_bytes):
    response = s3.get_object(Bucket=BUCKET, Key=key, ExpectedBucketOwner=ACCOUNT)
    body = response['Body']
    h, length = hashlib.sha256(), 0
    try:
        require(response['ContentLength'] == expected_bytes and expected_bytes > 0, 'archive length mismatch')
        for chunk in iter(lambda: body.read(8 * 1024**2), b''):
            h.update(chunk)
            length += len(chunk)
        require(length == expected_bytes and h.hexdigest() == sha256, 'archive integrity mismatch')
    finally:
        body.close()
    return dict(key=key, sha256=sha256, bytes=length, verified=True)


def validate_predictions(path, expected_counts):
    completed, samples, current, rows = set(), set(), None, 0
    def finish():
        if current is not None:
            require(len(samples) == expected_counts[current], 'prediction count mismatch')
            completed.add(current)
    with pathlib.Path(path).open(newline='') as f:
        for row in csv.DictReader(f):
            key = tuple(row[n] for n in ('outcome', 'horizon_s', 'fold', 'model'))
            require(key in expected_counts, 'undeclared prediction key')
            if key != current:
                finish()
                require(key not in completed, 'noncontiguous prediction block')
                current, samples = key, set()
            require(bool(row['sample_id']) and row['sample_id'] not in samples, 'duplicate/empty sample')
            require(all(math.isfinite(float(row[n])) for n in ('prediction', 'observed')), 'nonfinite prediction')
            samples.add(row['sample_id'])
            rows += 1
    finish()
    require(completed == set(expected_counts), 'missing prediction keys')
    return dict(rows=rows, models=len(completed))


def durable_json(path, value):
    path = pathlib.Path(path)
    body = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return body


def record_and_stop(s3, config, proof, stop_fn):
    require(proof.get('backup_verified') is True, 'backup not verified')
    body = durable_json(pathlib.Path(config['run']) / 'save-stop-proof.json', proof)
    s3.put_object(Bucket=BUCKET, Key=config['receipt_key'], Body=body,
                  ContentType='application/json', ServerSideEncryption='AES256', ExpectedBucketOwner=ACCOUNT)
    require(get_bytes(s3, config['receipt_key']) == body, 'stop proof read-back mismatch')
    if hasattr(os, 'sync'):
        os.sync()
    stop_fn()
