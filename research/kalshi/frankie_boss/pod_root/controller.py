"""The Pod ROOT loop's controller, on the GitHub runner (frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh,
its runner step "Pod ROOT loop"; SPEC-pod-day-runner.md).

Greg, 2026-09-29: "Agent work immediately, then A100s immediately after to start running ROOT; when that day is done, clean
up after the day by deleting garbage and moving data to the big box to be read by other processes"; "Just the pod
results. The pod stays and brings the next people in, and as space frees up on other boxes they do the same."

The runner holds the keys (AWS for S3 presigning and SSM; RUNPOD_API_KEY for Pod creation), the Pods and the box hold
none. The state lives where it is durable, so the controller is stateless and may be re-dispatched at any time (a GitHub
job lasts at most 6 h; a running ROOT does not care):
  the claims on the main box (/opt/frankie-box/work/root-claims/<run>/<day>.json, frankie_box_root_claims.py);
  the jobs on each Pod / worker (/opt/frankie-box/pod-agent/jobs/<attempt>/state.json, pod_agent.py);
  the bytes in transit in s3://frankie-granite42-568968024170-us-east-1/pod-root/<run>/<attempt>/{in,out}/ (deleted as
  soon as the box import verified every file);
  the Pod registry s3://.../pod-root/pods/<pod>.json (id and agent token; never printed).

Actions:
  plan    read-only: the run's queue from the main box (each day's state; ready = sealed ingest + day file attached +
          no ROOT + no claim), the registered Pods' status, what a loop would start.
  create  N new A100 SXM 80GB Pods (secure cloud, in-stock data centers, ubuntu:24.04, a persistent volume at
          /opt/frankie-box, port 8081/http); each boots pod_bootstrap.sh at the staged commit. Needs --confirm
          CREATE_<N>_PODS. Never stops or deletes anything.
  loop    the queue worked until the budget ends: every poll, per worker (Pod or worker box), finished jobs are imported
          into the main box and verified, then cleaned from the worker; free slots take the next ready day
          (claim -> inputs -> job). Nothing is started after --stop-starting-minutes before the budget ends; running
          ROOTs keep running after the controller exits and the next dispatch imports them.
  status  read-only: claims and imports on the box, every worker's jobs.
Rules kept: the day-file gate (a day is ready only with its day file attached beside its sealed ingest; the Pod re-checks
it before any calculation); one claim per day; the same committed ROOT script, commit and receipts as the box; zero data
dropped (the whole ROOT directory moves, an unfinished attempt is kept like the orchestrator keeps one); counts, not
averages; no Pod stopped or deleted here.
"""
import argparse
import http.client
import json
import os
import re
import secrets
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import urlencode

import boto3
from botocore.config import Config

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'deploy' / 'aws'))
import pod_transfer as T  # noqa: E402
import ssm_run_sh  # noqa: E402

TRANSFER_BUCKET = 'frankie-granite42-568968024170-us-east-1'
INGEST_BUCKET = 'bento-568968024170-us-east-2-an'
PREFIX = 'pod-root'
MAIN = dict(instance='i-035994afa8bdf66a5', region='us-east-1')
BOX_SCRIPT = REPO / 'deploy' / 'aws' / 'box' / 'frankie_box_pod_root.sh'
GPU = 'NVIDIA A100-SXM4-80GB'
MIN_VCPU, MIN_RAM = 16, 125          # the A100 SXM secure listing (operations/pod_prepare.py)
IMAGE = 'ubuntu:24.04'
PORT = 8081
BOOT = ('apt-get update -q >/dev/null && apt-get install -y -q curl ca-certificates >/dev/null && '
        'curl -fsSL "https://raw.githubusercontent.com/DavisAI1974/Markets/$MARKETS_SHA/research/kalshi/frankie_boss/'
        'pod_root/pod_bootstrap.sh" -o /tmp/pod_bootstrap.sh && exec bash /tmp/pod_bootstrap.sh')
FINISHED_FAILED = ('failed_setup', 'failed_inputs', 'failed_gate', 'refused')
ACTIVE = ('accepted', 'setup', 'inputs', 'root', 'finish', 'coordinate', 'scratch', 'ship')
PRINT_LOCK = threading.Lock()


def say(*parts):
    with PRINT_LOCK:
        print(time.strftime('%H:%M:%SZ', time.gmtime()), *parts, flush=True)


def s3(bucket):
    region = 'us-east-1' if bucket.endswith('us-east-1') else 'us-east-2'
    return boto3.client('s3', region_name=region, endpoint_url='https://s3.%s.amazonaws.com' % region,
                        config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))


class Presigner:
    def __init__(self, hours):
        self.expires = int(hours * 3600)
        self.clients = {}

    def _c(self, bucket):
        if bucket not in self.clients:
            self.clients[bucket] = s3(bucket)
        return self.clients[bucket]

    def get(self, bucket, key):
        return self._c(bucket).generate_presigned_url('get_object', Params=dict(Bucket=bucket, Key=key), ExpiresIn=self.expires)

    def put(self, bucket, key):
        return self._c(bucket).generate_presigned_url('put_object', Params=dict(Bucket=bucket, Key=key), ExpiresIn=self.expires)


# ------------------------------------------------------------------------------------------------------ the box

class BoxError(RuntimeError):
    pass


def box(action, target=MAIN, timeout=1800, url_map=None, **variables):
    """frankie_box_pod_root.sh over SSM on an instance; returns its POD_ROOT_RESULT (dict). A presigned map travels as a
    private S3 object whose presigned GET is MAP_URL (as frankie_box_run.yml does); the map object is deleted after."""
    client = s3(TRANSFER_BUCKET)
    map_key = None
    if url_map is not None:
        map_key = 'box-runs/pod-root-%s-%s/presigned-map.json' % (os.environ.get('GITHUB_RUN_ID', 'local'), secrets.token_hex(6))
        client.put_object(Bucket=TRANSFER_BUCKET, Key=map_key, Body=json.dumps(url_map).encode(),
                          ServerSideEncryption='AES256', ContentType='application/json')
        variables['MAP_URL'] = client.generate_presigned_url('get_object', Params=dict(Bucket=TRANSFER_BUCKET, Key=map_key),
                                                             ExpiresIn=timeout + 3600)
    try:
        ssm = boto3.client('ssm', region_name=target['region'])
        pairs = ['ACTION=%s' % action] + ['%s=%s' % (k, v) for k, v in variables.items() if v not in (None, '')]
        path = '%s/%s.out' % (ssm_run_sh.OUTPUT_DIR, secrets.token_hex(16))
        script = ssm_run_sh.kept_whole(ssm_run_sh.preamble(pairs) + BOX_SCRIPT.read_text(encoding='utf-8'), path)
        command = ssm_run_sh.run(ssm, target['instance'], script, timeout, 'pod-root %s' % action)
        status, inv = ssm_run_sh.wait(ssm, target['instance'], command, timeout)
        text = inv.get('StandardOutputContent', '')
        if len(text) >= ssm_run_sh.PART:
            text = ''.join(t for n, t in ssm_run_sh.parts(ssm, target['instance'], path) if n is not None)
        lines = [l for l in text.splitlines() if l.startswith('POD_ROOT_RESULT ')]
        if status != 'Success' or not lines:
            raise BoxError('%s on %s: SSM %s; stdout tail: %s; stderr tail: %s' % (
                action, target['instance'], status, text[-1500:], inv.get('StandardErrorContent', '')[-1500:]))
        return json.loads(lines[-1][len('POD_ROOT_RESULT '):])
    finally:
        if map_key:
            client.delete_object(Bucket=TRANSFER_BUCKET, Key=map_key)


# -------------------------------------------------------------------------------------------------- Runpod API

def runpod(method, path, body=None):
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=30)
    try:
        connection.request(method, path, None if body is None else json.dumps(body).encode(),
                           {'Authorization': 'Bearer ' + os.environ['RUNPOD_API_KEY'], 'Accept': 'application/json',
                            'Content-Type': 'application/json'})
        response = connection.getresponse()
        return response.status, response.read(2000000)
    finally:
        connection.close()


def a100_centers():
    status, data = runpod('GET', '/v2/catalog/gpus?' + urlencode(dict(include='AVAILABILITY', product='POD', count=1, cloud='SECURE')))
    if status == 402:
        raise SystemExit('Runpod HTTP 402: the balance is empty; tell Greg')
    if status != 200:
        raise SystemExit('catalog -> HTTP %d: %s' % (status, data[:400]))
    for g in json.loads(data)['gpus']:
        if g['id'] == GPU:
            centers = [dc['id'] for dc in g.get('dataCenters') or [] if dc.get('availability') not in (None, 'NONE')]
            return centers, g.get('availability')
    return [], None


# ------------------------------------------------------------------------------------------------------ workers

class PodWorker:
    """A Runpod Pod running pod_agent.py serve, reached through the Runpod HTTPS proxy with its bearer token."""
    kind = 'pod'

    def __init__(self, reg):
        self.id, self.token = reg['pod'], reg['token']
        self.where = 'pod:' + self.id
        self.host = '%s-%d.proxy.runpod.net' % (self.id, PORT)

    def _call(self, method, path, body=None, timeout=90):
        c = http.client.HTTPSConnection(self.host, timeout=timeout)
        try:
            c.request(method, path, None if body is None else json.dumps(body).encode(),
                      {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
            r = c.getresponse()
            data = r.read()
            if r.status not in (200, 409):
                # 503 = the Pod's bootstrap failed and serves its own report (failing step + log tail): printed whole
                raise RuntimeError('%s %s -> HTTP %d %s' % (method, path, r.status,
                                                            data.decode('utf-8', 'replace') if r.status == 503 else data[:300]))
            return json.loads(data)
        finally:
            c.close()

    def status(self):
        return self._call('GET', '/status')

    def submit(self, job):
        r = self._call('POST', '/job', job, timeout=120)
        return (r.get('job_id'), r.get('error'))

    def clean(self, job_id, verified):
        return self._call('POST', '/clean', dict(job_id=job_id, verified=verified)).get('result')

    def reupload(self, job_id, out):
        return self._call('POST', '/reupload', dict(job_id=job_id, out=out)).get('result')


class BoxWorker:
    """A worker box (the twin, i-08cee) running pod_agent.py jobs detached, driven over SSM."""
    kind = 'box'

    def __init__(self, spec, commit):
        instance, _, region = spec.partition('@')
        self.target = dict(instance=instance, region=region or 'us-east-1')
        self.where = 'worker:' + instance
        self.commit = commit

    def status(self):
        r = box('jobs', self.target, 600, COMMIT=self.commit)
        return dict(jobs=r['jobs'], host=r.get('host'), slots=1)

    def submit(self, job):
        r = box('work', self.target, 1800, url_map=dict(job=dict(url=job.pop('_job_url'))), COMMIT=self.commit)
        return (r.get('job_id'), r.get('error'))

    def clean(self, job_id, verified):
        return box('clean', self.target, 1800, COMMIT=self.commit, JOB=job_id, VERIFIED=verified or '').get('result')

    def reupload(self, job_id, out):
        return box('reupload', self.target, 6 * 3600, url_map=dict(out=out), COMMIT=self.commit, JOB=job_id).get('result')


def registry_key(pod):
    return '%s/pods/%s.json' % (PREFIX, pod)


def load_pod(pod):
    raw = s3(TRANSFER_BUCKET).get_object(Bucket=TRANSFER_BUCKET, Key=registry_key(pod))['Body'].read()
    return json.loads(raw)


# ---------------------------------------------------------------------------------------------------- the loop

class Controller:
    def __init__(self, a):
        self.a = a
        self.run = a.run
        self.started = time.time()
        self.stop_starting = self.started + (a.budget_minutes - a.stop_starting_minutes) * 60
        self.end = self.started + a.budget_minutes * 60
        self.sign = Presigner(a.url_hours)
        self.lock = threading.Lock()
        self.events = []
        self.force_box = set()
        self.start_failures = {}
        self.tries = {}
        self.commit = None
        self.queue_state = None

    def event(self, **fields):
        fields['at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with self.lock:
            self.events.append(fields)
        say(' '.join('%s=%s' % (k, v) for k, v in fields.items() if k != 'at'))

    def queue(self):
        q = box('queue', MAIN, 1800, CODE_ROOT=self.a.code_root, RUN=self.run)
        self.commit = self.commit or q.get('code_commit')
        self.queue_state = q
        return q

    def prefix(self, attempt):
        return '%s/%s/%s' % (PREFIX, self.run, attempt)

    def delete_prefix(self, attempt, sub=''):
        client = s3(TRANSFER_BUCKET)
        n = 0
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=TRANSFER_BUCKET, Prefix=self.prefix(attempt) + '/' + sub):
            for o in page.get('Contents', []):
                client.delete_object(Bucket=TRANSFER_BUCKET, Key=o['Key'])
                n += 1
        return n

    def s3_source(self, st, f):
        """An S3 copy of an input with the same size (the runner ingest's own objects; the day file's S3 key), so the
        box need not upload it; the Pod checks the sha256 either way."""
        if st['day'] in self.force_box:
            return None
        keys = []
        if st.get('runner_prefix') and f['role'] in ('receipt', 'completion', 'journal', 'opening_book'):
            keys.append((INGEST_BUCKET, st['runner_prefix'] + f['name']))
        if f['role'] in ('day_file', 'day_file_receipt'):
            keys.append((INGEST_BUCKET, 'frankie/day_external/%s/%s' % (st['day'], f['name'])))
        for bucket, key in keys:
            try:
                head = s3(bucket).head_object(Bucket=bucket, Key=key)
            except Exception:  # noqa: BLE001
                continue
            if head['ContentLength'] == f['bytes']:
                return bucket, key
        return None

    def start_day(self, w, st):
        day = st['day']
        c = box('claim', MAIN, 1800, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day, WHERE=w.where, COMMIT=self.commit)
        if not c.get('claimed'):
            self.event(worker=w.where, day=day, step='claim', result='not claimed', state=(c.get('state') or {}).get('state'),
                       holder=(c.get('claim') or {}).get('where'))
            return False
        st = c['state']
        attempt = st['attempt']
        self.event(worker=w.where, day=day, step='claim', result='claimed', attempt=attempt, role=st['role'], digest=st['digest'])
        submission_attempted = False
        try:
            inputs, need = [], []
            for f in st['files']:
                src = self.s3_source(st, f)
                if src:
                    inputs.append(dict(f, parts=[dict(url=self.sign.get(*src), bytes=f['bytes'])], source='s3://%s/%s' % src))
                else:
                    need.append(f)
            if need:
                slots = {}
                for f in need:
                    for i, (off, ln) in enumerate(T.plan_parts(f['bytes'])):
                        key = '%s/in/%s.part-%04d' % (self.prefix(attempt), f['name'], i)
                        slots['put:' + key] = dict(url=self.sign.put(TRANSFER_BUCKET, key))
                t0 = time.time()
                r = box('export', MAIN, 4 * 3600, url_map=slots, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day,
                        WHERE=w.where, ATTEMPT=attempt, FILES=','.join(f['name'] for f in need))
                for f in need:
                    parts = r['files'][f['name']]['parts']
                    inputs.append(dict(f, parts=[dict(url=self.sign.get(TRANSFER_BUCKET, p['key']), bytes=p['bytes']) for p in parts],
                                       source='box export'))
                self.event(worker=w.where, day=day, step='export', files=len(need), bytes=sum(f['bytes'] for f in need),
                           seconds=round(time.time() - t0))
            out = {} if w.kind == 'box' else self.out_slots(attempt)
            job = dict(schema='FRANKIE_POD_ROOT_JOB_V1', name=attempt, run=self.run, day=day, role=st['role'],
                       digest=st['digest'], commit=self.commit, data_workers=15 if w.kind == 'box' else self.a.data_workers,
                       ingest_dir=st['ingest_dir'], ingestion_receipt=st['ingestion_receipt'],
                       ingestion_receipt_sha256=st['ingestion_receipt_sha256'], day_external_sha256=st['day_external_sha256'],
                       frozen_survivors=st.get('frozen_survivors'),
                       inputs=[{k: f[k] for k in ('role', 'path', 'name', 'bytes', 'sha256', 'parts', 'source')} for f in inputs],
                       out=out, where=w.where, created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                       controller_run=os.environ.get('GITHUB_RUN_ID'))
            if w.kind == 'box':
                job.update(workflow='root-to-finish', plan=st['plan'], settings=st['settings'],
                           mailbox=dict(request_put=self.sign.put(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/request.json'),
                                        response_get=self.sign.get(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/response.json')))
                job['settings'] = dict(job['settings'], data_workers=15, search_workers=15)
                key = '%s/job.json' % self.prefix(attempt)
                s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=key, Body=json.dumps(job).encode(),
                                               ServerSideEncryption='AES256')
                job['_job_url'] = self.sign.get(TRANSFER_BUCKET, key)
            submission_attempted = True
            job_id, why = w.submit(job)
            if not job_id:
                raise RuntimeError('the worker refused the job: %s' % why)
            self.event(worker=w.where, day=day, step='job', result='started', attempt=attempt,
                       s3_inputs=sum(1 for f in inputs if f['source'] != 'box export'))
            return True
        except Exception as e:  # noqa: BLE001
            self.event(worker=w.where, day=day, step='start', result='failed', error='%s: %s' % (type(e).__name__, str(e)[:400]))
            if w.kind == 'box' and submission_attempted:
                # An SSM timeout can occur after acceptance. Keep ownership and input slots until
                # status establishes what happened; releasing here could dispatch the day twice.
                self.event(worker=w.where, day=day, step='held', attempt=attempt,
                           result='submission outcome requires same-box status/resume; claim and inputs retained')
                return False
            self.release(w, day, attempt, 'the controller could not start the job: %s: %s' % (type(e).__name__, str(e)[:300]))
            self.delete_prefix(attempt)
            return False

    def out_slots(self, attempt):
        return dict(chunk_urls=[self.sign.put(TRANSFER_BUCKET, '%s/out/chunk-%04d' % (self.prefix(attempt), i))
                                for i in range(self.a.out_chunks)],
                    manifest_url=self.sign.put(TRANSFER_BUCKET, '%s/out/manifest.json' % self.prefix(attempt)),
                    chunk_bytes=T.CHUNK_BYTES)

    def release(self, w, day, attempt, reason):
        try:
            r = box('release', MAIN, 600, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day, WHERE=w.where, ATTEMPT=attempt,
                    REASON=re.sub(r"[^A-Za-z0-9 _.,:()=-]", ' ', reason)[:300])
            self.event(worker=w.where, day=day, step='release', attempt=attempt, released=r.get('released'), detail=r.get('detail'))
        except BoxError as e:
            self.event(worker=w.where, day=day, step='release', attempt=attempt, result='failed', error=str(e)[:300])

    def import_job(self, w, j):
        attempt, day = j['job_id'], j['day']
        client = s3(TRANSFER_BUCKET)
        manifest = json.loads(client.get_object(Bucket=TRANSFER_BUCKET, Key='%s/out/manifest.json' % self.prefix(attempt))['Body'].read())
        url_map = dict(manifest=dict(url=self.sign.get(TRANSFER_BUCKET, '%s/out/manifest.json' % self.prefix(attempt))),
                       chunks=[dict(url=self.sign.get(TRANSFER_BUCKET, '%s/out/chunk-%04d' % (self.prefix(attempt), c['index'])))
                               for c in manifest['chunks']])
        t0 = time.time()
        r = box('import', MAIN, 6 * 3600, url_map=url_map, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day, WHERE=w.where,
                ATTEMPT=attempt, DISK_FLOOR_GB=self.a.disk_floor_gb)
        receipt = r['receipt']
        self.event(worker=w.where, day=day, step='import', attempt=attempt, status=receipt.get('status'),
                   files=receipt.get('files'), bytes=receipt.get('bytes'), compressed=receipt.get('compressed_bytes'),
                   seconds=round(time.time() - t0), root_exit=receipt.get('root_exit'),
                   verified=receipt['verification']['files_checked'], problems=receipt['verification']['problem_count'])
        cleaned = w.clean(attempt, receipt['manifest_sha256'])
        deleted = self.delete_prefix(attempt)
        self.event(worker=w.where, day=day, step='clean', attempt=attempt, worker_result=cleaned, s3_objects_deleted=deleted)

    def handle(self, w, j):
        """One finished job of this run on a worker: import, release, reupload or clean."""
        state, attempt, day = j.get('state'), j.get('job_id'), j.get('day')
        key = (w.where, attempt, state)
        self.tries[key] = self.tries.get(key, 0) + 1
        if self.tries[key] > 2:
            if self.tries[key] == 3:
                self.event(worker=w.where, day=day, attempt=attempt, step='handle', result='gave up after 2 tries', state=state)
            return
        try:
            if j.get('workflow') == 'root-to-finish':
                self.event(worker=w.where, day=day, attempt=attempt, step='retained', result=state, detail=j.get('detail'))
                return
            if state == 'uploaded':
                self.import_job(w, j)
            elif state in ('failed_ship', 'interrupted'):
                r = w.reupload(attempt, self.out_slots(attempt))
                self.event(worker=w.where, day=day, attempt=attempt, step='reupload', result=r, state=state)
            elif state in FINISHED_FAILED:
                if state == 'failed_inputs':
                    self.force_box.add(day)                  # the next attempt takes every input from the box itself
                self.release(w, day, attempt, 'the worker job ended %s: %s' % (state, j.get('detail')))
                self.event(worker=w.where, day=day, attempt=attempt, step='clean', worker_result=w.clean(attempt, None),
                           s3_objects_deleted=self.delete_prefix(attempt))
        except Exception as e:  # noqa: BLE001
            self.event(worker=w.where, day=day, attempt=attempt, step='handle %s' % state, result='failed',
                       error='%s: %s' % (type(e).__name__, str(e)[:500]))

    def next_ready(self):
        with self.lock:
            q = self.queue()
            for d in q['days']:
                if d['state'] == 'ready' and self.start_failures.get(d['day'], 0) < 2:
                    return d
            return None

    def coordinate(self, w, job):
        prefix = self.prefix(job['job_id']) + '/rpc'
        response = box('coordinate', MAIN, 1800, CODE_ROOT=self.a.code_root,
                       url_map=dict(rpc=dict(url=self.sign.get(TRANSFER_BUCKET, prefix + '/request.json')),
                                    reply=dict(url=self.sign.put(TRANSFER_BUCKET, prefix + '/response.json'))))
        self.event(worker=w.where, day=job['day'], step='coordinate', id=response.get('id'), error=response.get('error'))

    def renew(self, w, job):
        prefix = self.prefix(job['job_id']) + '/rpc'
        return box('renew', w.target, 600, COMMIT=self.commit, JOB=job['job_id'],
                   url_map=dict(mailbox=dict(request_put=self.sign.put(TRANSFER_BUCKET, prefix + '/request.json'),
                                             response_get=self.sign.get(TRANSFER_BUCKET, prefix + '/response.json'))))

    def worker_loop(self, w):
        failures = 0
        renewed = {}
        while time.time() < self.end:
            try:
                st = w.status()
                failures = 0
            except Exception as e:  # noqa: BLE001
                failures += 1
                self.event(worker=w.where, step='status', result='unreachable', error=str(e)[:200], failures=failures)
                if failures >= 10:
                    return
                time.sleep(self.a.poll_seconds)
                continue
            jobs = [j for j in st.get('jobs') or [] if j.get('run') == self.run]
            for j in jobs:
                if j.get('workflow') == 'root-to-finish' and j.get('pid_alive') and \
                        time.time() - renewed.get(j['job_id'], 0) > 900:
                    try:
                        self.renew(w, j)
                        renewed[j['job_id']] = time.time()
                    except Exception as error:
                        self.event(worker=w.where, day=j['day'], step='renew', result='retry',
                                   error=type(error).__name__)
                if w.kind == 'box' and j.get('state') == 'coordinate':
                    try:
                        self.coordinate(w, j)
                    except Exception as error:
                        self.event(worker=w.where, day=j['day'], step='coordinate', result='retry',
                                   error=type(error).__name__)
                if j.get('state') not in ACTIVE + ('cleaned',):
                    self.handle(w, j)
            try:
                st = w.status()
            except Exception as e:  # noqa: BLE001
                self.event(worker=w.where, step='status', result='unreachable', error=str(e)[:200])
                time.sleep(self.a.poll_seconds)
                continue
            active = [j for j in st.get('jobs') or [] if j.get('state') in ACTIVE]
            retained = [j for j in st.get('jobs') or [] if j.get('workflow') == 'root-to-finish'
                        and j.get('state') not in ACTIVE + ('day_complete',)]
            if retained:
                self.event(worker=w.where, step='held', result='failed/interrupted day requires same-box resume',
                           days=[j['day'] for j in retained])
                return
            free = int(st.get('slots') or 1) - len(active)
            if free > 0 and time.time() < self.stop_starting:
                d = self.next_ready()
                if d is not None:
                    if self.start_day(w, d):
                        continue
                    with self.lock:
                        self.start_failures[d['day']] = self.start_failures.get(d['day'], 0) + 1
                if not active and not self.a.wait_for_days:
                    self.event(worker=w.where, step='idle', result='no ready day and nothing running: this worker is idle '
                               '(the Pod keeps billing until it is stopped)')
                    return
            time.sleep(self.a.poll_seconds)

    def summary(self):
        counts = {}
        for e in self.events:
            k = '%s:%s' % (e.get('step'), e.get('result') or e.get('status') or '')
            counts[k] = counts.get(k, 0) + 1
        return dict(run=self.run, commit=self.commit, minutes=round((time.time() - self.started) / 60, 1),
                    event_counts=counts, queue_counts=(self.queue_state or {}).get('counts'))


def workers_of(a, commit):
    out = []
    if a.pods:
        raise ValueError('Pods are retired from the Frankie experiment; use AWS CPU boxes')
    for spec in [b for b in (a.boxes or '').split(',') if b]:
        out.append(BoxWorker(spec, commit))
    return out


def create(a, commit):
    if a.confirm != 'CREATE_%d_PODS' % a.count:
        raise SystemExit('create needs --confirm CREATE_%d_PODS (the parent asks Greg first)' % a.count)
    centers, level = a100_centers()
    if a.data_centers:
        centers = [c for c in a.data_centers.split(',') if c]
    if not centers:
        raise SystemExit('no data center reports %s stock (overall %s)' % (GPU, level))
    say('A100 SXM stock', level, 'data centers', centers)
    made = []
    for i in range(a.count):
        token = secrets.token_urlsafe(32)
        name = 'frankie-root-%s-%d' % (time.strftime('%m%d%H%M', time.gmtime()), i + 1)
        body = dict(name=name, image=IMAGE, cloud='SECURE',
                    gpu=dict(id=GPU, count=1, minRamPerGpu=MIN_RAM, minVcpuCountPerGpu=MIN_VCPU), dataCenterIds=centers,
                    disk=a.container_gb, mounts=dict(persistent=dict(path='/opt/frankie-box', size=a.volume_gb)),
                    ports=['%d/http' % PORT], env=dict(MARKETS_SHA=commit, POD_TOKEN=token, POD_SLOTS=str(a.slots)),
                    entrypoint=['bash', '-c', BOOT], startSsh=False, startJupyter=False)
        status, data = runpod('POST', '/v2/pods', body)
        if status == 402:
            raise SystemExit('Runpod HTTP 402: the balance is empty; tell Greg (%d Pod(s) created before)' % len(made))
        if status not in (200, 201):
            raise SystemExit('create -> HTTP %d: %s' % (status, data[:600].decode('utf-8', 'replace')))
        pod = json.loads(data)
        cost = {k: v for k, v in pod.items() if 'cost' in k.lower()}
        s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=registry_key(pod['id']), ServerSideEncryption='AES256',
                                       Body=json.dumps(dict(pod=pod['id'], name=name, token=token, commit=commit, gpu=GPU,
                                                            image=IMAGE, volume_gb=a.volume_gb, slots=a.slots, cost=cost,
                                                            data_centers=centers, created=time.time())).encode())
        made.append(pod['id'])
        say('POD %s created (%s) cost %s' % (pod['id'], name, cost))
        if cost and any(isinstance(v, (int, float)) and v > a.cost_ceiling for v in cost.values()):
            say('WARNING: Pod %s is priced above the ceiling %.2f/h; it is left as created (stop it with '
                'frankie_pod_control.yml if Greg says so)' % (pod['id'], a.cost_ceiling))
    say('watching the agents come up (bootstrap: apt, Python 3.13.15, 75 pins, checkouts): up to %d min' % a.wait_minutes)
    deadline = time.time() + a.wait_minutes * 60
    up = set()
    while time.time() < deadline and len(up) < len(made):
        time.sleep(60)
        for pod in made:
            if pod in up:
                continue
            try:
                s = PodWorker(load_pod(pod)).status()
                up.add(pod)
                say('POD %s agent up: %s cpus (affinity %s), %s GB RAM, disk free %s GB' % (
                    pod, s['host'].get('cpus'), s['host'].get('affinity'), round((s['host'].get('mem_total_kb') or 0) / 1e6),
                    round(s['host'].get('disk_free', 0) / 1e9)))
            except Exception as e:  # noqa: BLE001
                code, info = runpod('GET', '/v2/pods/' + pod)
                info = json.loads(info) if code == 200 else {}
                say('POD %s not up yet (%s); desired %s runtime %s' % (pod, str(e)[:80], info.get('desiredStatus'),
                                                                       'up' if info.get('runtime') else 'none'))
    say('CREATED %s; agents up %s; never started %s (left as they are: stop or terminate only on Greg\'s word)'
        % (made, sorted(up), sorted(set(made) - up)))
    return made


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('plan', 'create', 'loop', 'status'))
    p.add_argument('--run', required=True, help='the orchestrator run (its plan.json lists the days, roles and arm)')
    p.add_argument('--code-root', required=True, help='a staged clean checkout on the main box holding this code')
    p.add_argument('--pods', default='', help='comma list of registered Pod ids (pod-root/pods/<id>.json)')
    p.add_argument('--boxes', default='', help='comma list of worker boxes instance@region (set up by frankie_box_worker_setup.sh)')
    p.add_argument('--count', type=int, default=0)
    p.add_argument('--confirm', default='')
    p.add_argument('--slots', type=int, default=1,
                   help='days at once per Pod (Greg, 2026-09-29: one day per Pod, the day gets every CPU)')
    p.add_argument('--data-workers', type=int, default=48,
                   help='the ROOT reader worker cap, as Monday\'s ROOT (48): the reader runs min(cap, CPUs-1) workers')
    p.add_argument('--budget-minutes', type=int, default=330)
    p.add_argument('--stop-starting-minutes', type=int, default=20)
    p.add_argument('--poll-seconds', type=int, default=60)
    p.add_argument('--url-hours', type=float, default=72.0)
    p.add_argument('--out-chunks', type=int, default=64, help='4 GiB upload slots per day (64 = 256 GiB compressed)')
    p.add_argument('--disk-floor-gb', type=float, default=100.0)
    p.add_argument('--wait-for-days', choices=('yes', 'no'), default='yes')
    p.add_argument('--volume-gb', type=int, default=500)
    p.add_argument('--container-gb', type=int, default=50)
    p.add_argument('--data-centers', default='')
    p.add_argument('--cost-ceiling', type=float, default=1.75)
    p.add_argument('--wait-minutes', type=int, default=40)
    a = p.parse_args()
    if a.action == 'create' or a.pods:
        raise SystemExit('Pods are retired from the Frankie experiment; no Pod creation or dispatch')
    if a.action == 'loop' and (a.slots != 1 or a.boxes != 'i-0d17573dbce871520@us-east-1'):
        raise SystemExit('remote workflow uses exactly one Linux lane: --boxes i-0d17573dbce871520@us-east-1 --slots 1')
    a.wait_for_days = a.wait_for_days == 'yes'
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', a.run) or not a.code_root.startswith('/opt/frankie-box/code/'):
        raise SystemExit('--run [A-Za-z0-9_-] and --code-root /opt/frankie-box/code/... required')
    if a.url_hours > 168:
        raise SystemExit('presigned URLs live at most 168 h')
    ctl = Controller(a)
    if a.action == 'status':
        say(json.dumps(box('status', MAIN, 600, CODE_ROOT=a.code_root, RUN=a.run), indent=1, sort_keys=True))
        q = ctl.queue()
        for w in workers_of(a, ctl.commit):
            try:
                say(w.where, json.dumps(w.status(), indent=1, sort_keys=True, default=str))
            except Exception as e:  # noqa: BLE001
                say(w.where, 'unreachable:', e)
        return
    q = ctl.queue()
    say('queue of %s at %s: %s' % (a.run, q.get('code_commit'), q.get('counts')))
    for d in q['days']:
        say('  %s %s %s' % (d['day'], d['state'], d.get('attempt') or d.get('reason') or (d.get('claim') or {}).get('where') or ''))
    if a.action == 'plan':
        ready = [d for d in q['days'] if d['state'] == 'ready']
        say('%d ready day(s); %d worker(s) x %d slot(s) would start %d now; claim store active: %s' % (
            len(ready), len([b for b in a.boxes.split(',') if b]), a.slots,
            min(len(ready), len([b for b in a.boxes.split(',') if b]) * a.slots),
            q.get('active')))
        return
    if a.action == 'create':
        create(a, ctl.commit)
        return
    r = box('enable', MAIN, 600, CODE_ROOT=a.code_root)
    say('claim store', r)
    workers = workers_of(a, ctl.commit)
    if not workers:
        raise SystemExit('no workers: give --boxes i-0d17573dbce871520@us-east-1')
    threads = [threading.Thread(target=ctl.worker_loop, args=(w,), name=w.where, daemon=True) for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(max(1, ctl.end - time.time() + 60))
    out = ctl.summary()
    body = json.dumps(dict(out, events=ctl.events), indent=1, sort_keys=True, default=str)
    try:
        s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, ServerSideEncryption='AES256', Body=body.encode(),
                                       Key='%s/%s/controller/%s.json' % (PREFIX, a.run, os.environ.get('GITHUB_RUN_ID', int(time.time()))))
    except Exception as e:  # noqa: BLE001
        say('controller journal not written to S3:', e)
    Path('pod-root-controller.json').write_text(body)
    say('SUMMARY', json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
