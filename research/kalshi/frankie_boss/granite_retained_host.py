"""GitHub independent watchdog and retained-Pod readiness; never inference.

The local controller reads the safe readiness artifact, obtains its own private
service credential in memory, performs its journaled critic call, then stops the
Pod. These GitHub jobs independently enforce the same bounded lease.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

from . import granite_run_artifacts as artifacts
from . import granite_runpod_cloud as cloud
from . import granite_runpod_cloud_control as control
from . import granite_cloud_resume as retained
from . import granite_retained_lifecycle as lifecycle
from .granite_runpod_tokenizer import LocalTokenizerAdmission, MAX_REQUEST_BYTES
from .granite_runpod_admission import TOKENIZER_FILES
from .granite_runpod_probe import https_exchange

OUT = Path('work/retained-granite')
INFO_SHA256 = 'c6c151ddc5ad252a04c34a533e8bc4d9f46c24778372c9bb84f34e748832020a'
PRIOR_RUN = '34928264918'
REQUEST_BUCKET = 'bento-568968024170-us-east-2-an'
REQUEST_PREFIX = 'nymex/ng_mbo_5y_v0/frankie/boss_requests/'


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_bytes(artifacts.canonical(value))


def info_from_journal(journal):
    prior = object.__new__(cloud.Journal)
    prior.client, prior.bucket = journal.client, journal.bucket
    prior.prefix = 'runpod-smoke/'+PRIOR_RUN+'/'
    raw = prior.get_bytes('pod-info.json')
    if raw is None or hashlib.sha256(raw).hexdigest() != INFO_SHA256:
        raise ValueError('accepted retained Pod receipt differs')
    return artifacts.strict_json(raw)


def request_digest():
    digest = os.environ.get('REQUEST_SHA256', '')
    if not digest:
        value = artifacts.strict_json(Path('.github/frankie-retained-lease-request.json').read_bytes())
        if set(value) != {'request_sha256'}:
            raise ValueError('explicit exact request digest required')
        digest = value['request_sha256']
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('exact actual request digest required')
    return digest


def read_object(journal, bucket, key, maximum):
    response = journal.client.get_object(Bucket=bucket, Key=key)
    with response['Body'] as stream:
        if response['ContentLength'] > maximum:
            raise ValueError('request or tokenizer object exceeds its explicit byte bound')
        raw = stream.read(maximum+1)
    if len(raw) != response['ContentLength']:
        raise ValueError('incomplete staged object')
    return raw


def tokenizer(journal, manifest):
    directory = Path('work/retained-tokenizer')
    directory.mkdir(parents=True, exist_ok=False)
    for row in manifest['files']:
        if row['path'] in TOKENIZER_FILES:
            raw = read_object(journal, journal.bucket,
                artifacts.prefix_for(manifest)+row['path'], row['size'])
            (directory/row['path']).write_bytes(raw)
            artifacts.verify_file(directory/row['path'], row)
    return LocalTokenizerAdmission(directory, served_model_name='granite42-smoke')


def watchdog_identity():
    """Get actual job ID/start from GitHub, not a caller-provided liveness label."""
    repository, run_id = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID']
    if repository != 'DavisAI1974/Markets' or not run_id.isdecimal():
        raise ValueError('authorized repository/run required')
    request = urllib.request.Request('https://api.github.com/repos/'+repository+'/actions/runs/'+run_id+'/jobs?per_page=100',
        headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(1024*1024+1)
    if len(raw) > 1024*1024:
        raise ValueError('oversized GitHub job response')
    jobs = [job for job in json.loads(raw)['jobs'] if job['name'] == 'retained-watchdog']
    if len(jobs) != 1 or jobs[0]['status'] != 'in_progress':
        raise ValueError('actual independent watchdog job is not running')
    job = jobs[0]
    started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00')).timestamp()
    return dict(run_id=run_id, job_id=str(job['id']), job_deadline=started+45*60)


def keep_startup_frame(records, frame, lease):
    # Runpod v2 OpenAPI defines SSE data {source,line,ts}; validate the
    # provider event timestamp as well as requesting its since-filter.
    if frame.get('source') != 'container' or type(frame.get('ts')) is not str:
        return
    stamp = datetime.fromisoformat(frame['ts'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or not lease['start'] <= stamp.timestamp() <= time.time():
        return
    line = frame.get('line', '')
    if not isinstance(line, str):
        return
    for prefix, key in [('GRANITE_RUNPOD_STARTUP ', 'startup'), ('GRANITE_DISK ', 'disk')]:
        if line.startswith(prefix):
            records[key] = artifacts.strict_json(line[len(prefix):].encode())
            records[key+'_event_at'] = stamp.timestamp()


def fresh_startup(api, lease):
    """Read only logs after lease start; keep only accepted non-secret receipts."""
    since = datetime.fromtimestamp(lease['start'], timezone.utc).isoformat().replace('+00:00', 'Z')
    path = '/v2/pods/'+lifecycle.POD_ID+'/logs?'+urllib.parse.urlencode(dict(source='container', since=since))
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=4)
    records, consumed, deadline = {}, 0, time.monotonic()+8
    try:
        connection.request('GET', path, headers={'Authorization':'Bearer '+api.key, 'Accept':'text/event-stream'})
        response = connection.getresponse()
        if response.status != 200:
            return records
        while time.monotonic() < deadline and consumed < 1024*1024:
            if connection.sock:
                connection.sock.settimeout(max(.05, min(1, deadline-time.monotonic())))
            raw = response.readline(65537)
            consumed += len(raw)
            if not raw or len(raw) > 65536:
                break
            if not raw.startswith(b'data:'):
                continue
            keep_startup_frame(records, json.loads(raw[5:]), lease)
    except (TimeoutError, OSError):
        pass
    finally:
        connection.close()
    return records


def prepare(journal, api, info, manifest):
    if os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise ValueError('interrupted start requires explicit recovery, not a rerun')
    digest = request_digest()
    body = read_object(journal, REQUEST_BUCKET, REQUEST_PREFIX+digest+'.json', MAX_REQUEST_BYTES)
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('actual staged request differs from its trusted digest')
    admit = tokenizer(journal, manifest)
    admission = admit(body)  # Actual full request, before any lease or paid start.
    lease = lifecycle.make_lease(info, start=time.time(), duration_seconds=1800, request_sha256=digest)
    journal.put('retained-lease.json', lease, once=True)
    save('pod-info.json', info)
    save('lease.json', lease)
    expected_watchdog = watchdog_identity()
    for _ in range(12):
        arm = journal.get('retained-armed.json')
        if arm and arm.get('watchdog_identity') == expected_watchdog:
            break
        time.sleep(3)
    else:
        raise ValueError('independent watchdog did not arm')
    started = lifecycle.resume_once(api, journal, info, manifest, lease, now=time.time(),
        request_body=body, tokenizer_admission=admit, expected_watchdog_identity=expected_watchdog)
    save('start.json', started)
    if started['status'] != 'start_submitted':
        raise ValueError('recover the previous start using its retained evidence')
    records = {}
    while time.time() < lease['deadline']-180:
        records.update(fresh_startup(api, lease))
        if {'startup', 'disk'} <= set(records):
            cloud.validate_runtime(records, dict(model_manifest_sha256=artifacts.manifest_digest(manifest)))
            pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
            key = pod['env']['RUNPOD_GRANITE_API_KEY']  # memory only; never written or printed
            observed = time.time()
            try:
                status, health = https_exchange(lifecycle.POD_ID, 'GET', '/health', b'', key, 10)
            except (TimeoutError, OSError):
                status, health = None, None
            if status == 200 and health == b'{"status":"ok"}':
                runtime = dict(outcome='service_ready', pod_id=lifecycle.POD_ID, model='granite42-smoke',
                    ready_at=time.time(), deadline=lease['deadline'], runtime=records,
                    startup_event_at=records['startup_event_at'],
                    startup_event_time_basis='Runpod v2 container SSE event ts',
                    health=dict(method='GET', path='/health', status=200, observed_at=observed), inference_sent=False)
                runtime_hash = hashlib.sha256(artifacts.canonical(runtime)).hexdigest()
                bindings = lifecycle.verified_service_inputs(info, manifest, lease, runtime_receipt=runtime,
                    expected_runtime_sha256=runtime_hash, tokenizer_admission=admit,
                    output_tokens=admission['output_tokens'])
                journal.put('service-ready.json', runtime, once=True)
                save('service-ready.json', runtime)
                save('service-pins.json', dict(runtime_sha256=runtime_hash,
                    config_hash=bindings['config'].config_hash, identity_hash=bindings['identity'].identity_hash,
                    request_sha256=digest, admission=admission))
                save('pod-info.json', info)
                return
        time.sleep(5)
    raise TimeoutError('retained startup did not finish within this bounded lease')


def watchdog(journal, api, info):
    started = time.time()
    lease = None
    while time.time()-started < 600:
        lease = journal.get('retained-lease.json')
        if lease:
            break
        time.sleep(3)
    if lease is None:
        save('watchdog.json', dict(status='no_lease_no_start'))
        return
    lifecycle._check(lease, info)
    save('pod-info.json', info)
    save('lease.json', lease)
    identity = watchdog_identity()
    while time.time() <= lease['deadline']+30:
        try:
            result = lifecycle.watchdog_tick(api, journal, info, lease, now=time.time(), watchdog_identity=identity)
            save('watchdog.json', result)
            if result.get('status') == 'confirmed_stopped':
                return
            if journal.get('service-ready.json'):
                pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
                if pod['status'] == 'EXITED':
                    journal.put('retained-finished.json', dict(lease_sha256=lifecycle._check(lease, info)))
        except Exception as error:
            # Cached lease/ownership survive S3 outages. Deadline ticks stop via
            # Runpod directly; a failed arm never authorizes a new start.
            save('watchdog-transient.json', dict(error_type=type(error).__name__, at=time.time()))
        time.sleep(10)
    raise TimeoutError('retained stop not confirmed by watchdog deadline')


def hold(journal, api, info):
    lease = journal.get('retained-lease.json')
    while lease and time.time() < lease['deadline']-120:
        pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
        if pod['status'] == 'EXITED':
            return
        time.sleep(10)


def cleanup(api):
    # Each independent job caches these BEFORE it can authorize/start compute.
    # Cleanup deliberately has no S3 dependency, including client construction.
    if not (OUT/'lease.json').exists():
        return
    info = artifacts.strict_json((OUT/'pod-info.json').read_bytes())
    if hashlib.sha256(artifacts.canonical(info)).hexdigest() != INFO_SHA256:
        raise ValueError('cached retained ownership receipt changed')
    lease = artifacts.strict_json((OUT/'lease.json').read_bytes())
    lifecycle._check(lease, info)
    result = retained.stop_owned_once(api, info['intent'], lifecycle.POD_ID)
    save('cleanup.json', result)
    if result['status'] != 'confirmed_stopped':
        raise RuntimeError('retained cleanup requires follow-up')


def main():
    role = sys.argv[1]
    api = control.Runpod(os.environ['RUNPOD_API_KEY'])
    if role == 'cleanup':
        cleanup(api)
        return
    journal = cloud.Journal()
    info = info_from_journal(journal)
    manifest = artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    if role == 'prepare':
        prepare(journal, api, info, manifest)
    elif role == 'watchdog':
        watchdog(journal, api, info)
    elif role == 'hold':
        hold(journal, api, info)
    else:
        raise ValueError('unknown retained host role')


if __name__ == '__main__':
    main()
