"""The AWS CPU Linux lane controller (SPEC-experiment-orchestrator.md; Frankie_30Day_AWS_Runbook_20261006.md "Three lane
layout": two held 16-CPU lanes on the main box plus ONE held 16-CPU Linux worker lane, i-0d17573dbce871520).

A LISTED, UNUSED FALLBACK (Greg, 2026-10-07: "NO days on the small box"): every day runs on the main box
i-035994afa8bdf66a5, on its two held 16-CPU lanes, and never leaves it; the worker box is not part of the default lane
set. This route is kept in code the way the GitHub voice route is kept: nothing starts it; an activating action (loop,
resume) refuses unless the operator names it explicitly (--fallback-route worker_box, on Greg's decision); plan, status,
stop, preflight and retained stay read-only/cooperative. The main lanes' own runs never require it. Pods are
retired (Greg, 2026-10-06): nothing here creates, registers, reaches or deletes a Pod, and every retired Pod argument is
refused before parsing. The same code runs on two hosts:

  runner  frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh (a legacy marker filename; the runner
          step "AWS CPU Linux lane controller"): a bounded GitHub job (--budget-minutes, 330) for plan, status, resume,
          stop and a bounded loop. The runner holds the AWS keys. A budget end is recorded as budget_expired with what was
          still pending; it is never completion and never starts a new scientific attempt.
  main    deploy/aws/box/frankie_box_cpu_controller.sh ACTION=start: a run-bound systemd unit on the main box, from the
          staged checkout (--host main --state-dir /opt/frankie-box/work/cpu-controller/<run> --budget-minutes 0), serving
          every Linux boundary of the run (claims, exports, mailbox renewal, coordination, retained-day accounting) until
          the run's Linux lane has no remaining work or a cooperative stop request is acknowledged. Main-box actions run
          locally (the same committed box script, the same preamble as over SSM); the worker is reached over SSM; S3 holds
          the job, the mailbox and the lease. The box's instance profile must therefore carry what the runner's keys carried
          (--action preflight names each prerequisite and refuses activation when one is absent; nothing is provisioned).

The state lives where it is durable, so the controller may be re-dispatched or restarted at any time:
  the claims on the main box (/opt/frankie-box/work/root-claims/<run>/<day>.json, frankie_box_root_claims.py);
  the jobs on the worker (/opt/frankie-box/pod-agent/jobs/<attempt>/state.json, pod_agent.py);
  the bytes in transit in s3://frankie-granite42-568968024170-us-east-1/pod-root/<run>/<attempt>/{in,out,rpc,job.json};
  the controller's lease and journals in s3://.../pod-root/<run>/controller/ (lease.json: one controller per run);
  on the main host, the state directory: controller.json (identity, write-once per start), status.json (every poll),
  events.jsonl (every event), calls/ (every local box call's whole output), stop-request.json / stop-ack.json (the
  cooperative stop and its acknowledgment), resume-request.json / resume-ack.json (a retained job's same-owner resume,
  served by the running service, which holds the lane), outcome-<start>.json (how a start ended; never 'complete').

Actions:
  plan       read-only: the run's queue from the main box (each day's state; ready = sealed ingest + day file attached +
             no ROOT + no claim), what a loop would start.
  status     read-only: claims and imports on the main box, the worker's jobs (live).
  loop       the queue worked: every poll, finished jobs are handled, retained days are held, a free slot takes the next
             ready day (claim -> inputs -> job); the held job's mailbox is renewed; coordination requests are answered.
  resume     one retained job (--job) renewed and resumed on its original owner; the controller serves that job only.
  stop       a cooperative save requested of one retained job (--job) on the worker; never a machine stop.
  preflight  (host main) the credential and reachability prerequisites checked read-only; refuses with the exact one.
  retained   (host main) the retained state directory and the run's claims, no AWS call: the controller process and the
             worker's last-seen job reported distinctly.
Rules kept: the day-file gate; one claim per day; the same committed ROOT script, commit and receipts as the box; zero
data dropped; counts, not averages; a claim is never cleared here; an interrupted or refused handoff keeps the original
claim and inputs; exactly one Linux lane (SLOTS=1); no new AWS service, booking or host. Ownership is established at
every effect boundary (claim, submission after an export, renewal, coordination, save relay, resume): the lease's last
successful conditional write must be fresh, else one is tried, else the effect is not made and the loop ends
(lease_lost / lease_unestablished). A resume whose transport step fails after it may have launched is UNKNOWN until the
worker's status settles it; it is never redispatched. Every unsuccessful outcome exits nonzero; a budget end, a stop and
a lane with no remaining work exit zero and are never day completion.
"""
import argparse
import fcntl
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

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
LINUX_LANE = 'i-0d17573dbce871520@us-east-1'            # the one Linux worker lane; SLOTS=1
BOX_SCRIPT = REPO / 'deploy' / 'aws' / 'box' / 'frankie_box_pod_root.sh'
STATE_PARENT = '/opt/frankie-box/work/cpu-controller'    # host main: <STATE_PARENT>/<run>
PLAN_PARENT = '/opt/frankie-box/work/experiment'          # the main's saved plan: <PLAN_PARENT>/<run>/plan.json
CLAIMS_PARENT = '/opt/frankie-box/work/root-claims'       # the claim store (frankie_box_root_claims.py)
FINISHED_FAILED = ('failed_setup', 'failed_inputs', 'failed_gate', 'refused')
ACTIVE = ('accepted', 'setup', 'inputs', 'root', 'finish', 'coordinate', 'scratch', 'ship')
LEASE_FRESH_SECONDS = 600                                 # a lease whose heartbeat is older than this is stale
HEARTBEAT_SECONDS = 60
RETIRED_POD_FLAGS = ('--pods', '--count', '--confirm', '--data-centers', '--volume-gb', '--container-gb', '--wait-minutes')
STATE_SCHEMA = 'FRANKIE_CPU_CONTROLLER_V1'
PRINT_LOCK = threading.Lock()
HOST = dict(host='runner', state=None)                    # set once in main(); read by box()


def say(*parts):
    with PRINT_LOCK:
        print(time.strftime('%H:%M:%SZ', time.gmtime()), *parts, flush=True)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


CLIENTS = {}
CLIENT_LOCK = threading.Lock()


def s3(bucket):
    """One S3 client per bucket, created under a lock (the heartbeat and the worker thread both call this; a client is
    safe to share, its creation from the default session is not)."""
    region = 'us-east-1' if bucket.endswith('us-east-1') else 'us-east-2'
    with CLIENT_LOCK:
        if ('s3', bucket) not in CLIENTS:
            CLIENTS[('s3', bucket)] = boto3.client('s3', region_name=region, endpoint_url='https://s3.%s.amazonaws.com' % region,
                                                   config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
        return CLIENTS[('s3', bucket)]


def ssm_client(region):
    with CLIENT_LOCK:
        if ('ssm', region) not in CLIENTS:
            CLIENTS[('ssm', region)] = boto3.client('ssm', region_name=region)
        return CLIENTS[('ssm', region)]


def keep_running(instance, region, value, reason, by):
    """The box's KeepRunning tag (Greg, 2026-10-07: "keep running only when in use"): set 'true' when a run claims the
    lane, cleared to 'false' at finish, failed, lease-lost or stop; never silent: the result (or the failure to tag,
    named) is returned for the event journal and the receipt. The idle guard (deploy/aws/idle_instance_guard.py) stops a
    box whose tag is not 'true' and that holds no fresh lane lease. ec2:CreateTags on the instance is the one permission."""
    doc = dict(instance=instance, region=region, keep_running='true' if value else 'false', reason=reason, by=by, at=utc())
    try:
        boto3.client('ec2', region_name=region).create_tags(
            Resources=[instance], Tags=[dict(Key='KeepRunning', Value=doc['keep_running']),
                                        dict(Key='KeepRunningReason', Value=('%s: %s' % (by, reason))[:255])])
        doc['tagged'] = True
    except Exception as error:  # noqa: BLE001 - the tag is a cost guard, never the day's outcome; its failure is named
        doc.update(tagged=False, error='%s: %s' % (type(error).__name__, str(error)[:300]))
    return doc


_WINDOW = [0.0, None]


def signing_window():
    """Seconds the current credentials stay valid, or None when they do not expire (the runner's static keys). On the
    main host the credentials are the instance profile's session: a presigned URL dies with them, whatever its ExpiresIn,
    so the signer asks for fresh credentials first (botocore refreshes inside its advisory window) and bounds ExpiresIn
    to what remains."""
    now = time.time()
    if now - _WINDOW[0] < 30:
        return None if _WINDOW[1] is None else max(0, int(_WINDOW[1] - now))
    expiry = None
    try:
        credentials = boto3.DEFAULT_SESSION.get_credentials() if boto3.DEFAULT_SESSION else boto3.Session().get_credentials()
        if credentials is not None:
            credentials.get_frozen_credentials()
            stamp = getattr(credentials, '_expiry_time', None)
            expiry = stamp.timestamp() if stamp is not None else None
    except Exception:  # noqa: BLE001
        expiry = None
    _WINDOW[0], _WINDOW[1] = now, expiry
    return None if expiry is None else max(0, int(expiry - now))


def controller_id():
    """The journal name of this controller process: the GitHub run on the runner, main-<start epoch> on the main box
    (the start epoch is the unit's, so the unit name, controller.json, the outcome and the journal name one start)."""
    if os.environ.get('GITHUB_RUN_ID'):
        return os.environ['GITHUB_RUN_ID']
    return '%s-%d' % (HOST['host'], int(HOST.get('started') or time.time()))


def start_epoch():
    """The unit's epoch (frankie-cpu-controller-<run>-<epoch>) when the launcher gave it; the clock otherwise."""
    unit = os.environ.get('CPU_CONTROLLER_UNIT') or ''
    tail = unit.rpartition('-')[2]
    return int(tail) if tail.isdigit() else int(time.time())


class Presigner:
    def __init__(self, hours):
        self.expires = int(hours * 3600)

    def _c(self, bucket):
        return s3(bucket)

    def _expires(self):
        window = signing_window() if HOST['host'] == 'main' else None
        return self.expires if window is None else max(60, min(self.expires, window - 60))

    def get(self, bucket, key):
        return self._c(bucket).generate_presigned_url('get_object', Params=dict(Bucket=bucket, Key=key), ExpiresIn=self._expires())

    def put(self, bucket, key):
        return self._c(bucket).generate_presigned_url('put_object', Params=dict(Bucket=bucket, Key=key), ExpiresIn=self._expires())


# ------------------------------------------------------------------------------------------ the retained state (host main)

def write_json(path, doc, create_only=False):
    """One JSON document; atomic replace, or create-only (a write-once record is never overwritten)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n'
    if create_only:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        return
    tmp = path.with_name('%s.%d-%d.pending' % (path.name, os.getpid(), threading.get_ident()))
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path, tolerant=False):
    """The document, None when absent; with tolerant, an unreadable file is reported as a document, never raised."""
    try:
        return json.loads(Path(path).read_bytes())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        if tolerant:
            return dict(unreadable=str(path), error='%s: %s' % (type(error).__name__, str(error)[:200]))
        raise


def alive_pid(state_dir):
    """The pid of the controller holding <state_dir>/controller.lock, 'held' when the lock is held but the identity is
    unreadable, None when no controller holds it. The launcher calls this; retained() reports it."""
    lock = Path(state_dir) / 'controller.lock'
    if not lock.exists():
        return None
    with open(lock, 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
            return None
        except OSError:
            identity = read_json(Path(state_dir) / 'controller.json', tolerant=True) or {}
            return identity.get('pid') or 'held'


class State:
    """The state directory of a controller hosted on the main box: a lock held for the process lifetime (a second start
    of the same run is refused), the write-once identity, the per-poll status, the event journal, every local box call's
    whole output, the stop request and its acknowledgment, and the outcome of each start."""

    def __init__(self, directory, run):
        self.dir = Path(directory)
        self.run = run
        self.calls = self.dir / 'calls'
        self.seq = 0
        self.lock = threading.Lock()
        self.handle = None
        self.dir.mkdir(parents=True, exist_ok=True)
        self.calls.mkdir(exist_ok=True)

    def acquire(self):
        self.handle = open(self.dir / 'controller.lock', 'a')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = read_json(self.dir / 'controller.json') or {}
            raise SystemExit('a controller of %s holds %s (pid %s, unit %s, started %s): not started twice' % (
                self.run, self.dir / 'controller.lock', holder.get('pid'), holder.get('unit'), holder.get('started_utc')))

    def identity(self, doc):
        """controller.json: the running start's identity (replaced only by a start that holds the lock); the previous
        identity is kept as controller-<its start>.json."""
        previous = read_json(self.dir / 'controller.json')
        if previous and previous.get('started_epoch'):
            kept = self.dir / ('controller-%d.json' % int(previous['started_epoch']))
            if not kept.exists():
                write_json(kept, previous, create_only=True)
        write_json(self.dir / 'controller.json', doc)

    def status(self, doc):
        write_json(self.dir / 'status.json', dict(doc, schema=STATE_SCHEMA + '_STATUS', at=utc()))

    def event(self, fields):
        with self.lock:
            with open(self.dir / 'events.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps(fields, sort_keys=True, default=str) + '\n')

    def call_path(self, action):
        with self.lock:
            self.seq += 1
            return self.calls / ('%s-%04d-%s' % (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()), self.seq, action))

    def stop_request(self):
        return read_json(self.dir / 'stop-request.json')

    def stop_ack(self):
        return read_json(self.dir / 'stop-ack.json')

    def resume_request(self):
        return read_json(self.dir / 'resume-request.json', tolerant=True)

    def resume_pending(self):
        return read_json(self.dir / 'resume-pending.json', tolerant=True)

    def resume_pend(self, doc):
        write_json(self.dir / 'resume-pending.json', dict(doc, schema=STATE_SCHEMA + '_RESUME_PENDING'))

    def resume_settled(self):
        path = self.dir / 'resume-pending.json'
        if path.exists():
            os.rename(path, self.dir / ('resume-pending-%d.json' % int(time.time())))

    def resume_acknowledge(self, doc):
        """The request archived beside its acknowledgment (both kept; a request is consumed exactly once)."""
        stamp = int(time.time())
        write_json(self.dir / ('resume-ack-%d.json' % stamp), dict(doc, schema=STATE_SCHEMA + '_RESUME_ACK', acknowledged_utc=utc()),
                   create_only=True)
        os.rename(self.dir / 'resume-request.json', self.dir / ('resume-request-%d.json' % stamp))

    def acknowledge(self, doc):
        write_json(self.dir / 'stop-ack.json', dict(doc, schema=STATE_SCHEMA + '_STOP_ACK', acknowledged_utc=utc()), create_only=True)

    def outcome(self, started_epoch, doc):
        path = self.dir / ('outcome-%d.json' % int(started_epoch))
        if path.exists():
            return
        write_json(path, dict(doc, schema=STATE_SCHEMA + '_OUTCOME', at=utc()), create_only=True)


# ------------------------------------------------------------------------------------------------------ the box

class BoxError(RuntimeError):
    pass


class LeaseNotEstablished(RuntimeError):
    """Raised BEFORE any transport when lease ownership cannot be established at an effect boundary: nothing was sent."""


def _result(action, target, status, text, err):
    lines = [l for l in text.splitlines() if l.startswith('POD_ROOT_RESULT ')]
    if status != 'Success' or not lines:
        raise BoxError('%s on %s: %s; stdout tail: %s; stderr tail: %s' % (action, target, status, text[-1500:], err[-1500:]))
    return json.loads(lines[-1][len('POD_ROOT_RESULT '):])


def _local_box(action, timeout, pairs):
    """The box script run on THIS machine (the controller hosted on the main box): the same committed script and the same
    literal preamble as over SSM, under /bin/sh as the SSM document runs it; its whole stdout and stderr kept in calls/."""
    state = HOST['state']
    path = state.call_path(action)
    state.calls.mkdir(parents=True, exist_ok=True)
    script = ssm_run_sh.preamble(pairs) + BOX_SCRIPT.read_text(encoding='utf-8')
    try:
        proc = subprocess.run(['/bin/sh', '-c', script], capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        out = (error.stdout or b'').decode('utf-8', 'replace')
        err = (error.stderr or b'').decode('utf-8', 'replace')
        Path(str(path) + '.out').write_text(out, encoding='utf-8')
        Path(str(path) + '.err').write_text(err, encoding='utf-8')
        raise BoxError('%s on this host: local timeout after %d s (output kept at %s.out)' % (action, timeout, path))
    out = proc.stdout.decode('utf-8', 'replace')
    err = proc.stderr.decode('utf-8', 'replace')
    if action == 'queue' and proc.returncode == 0:
        path = state.calls / 'queue-latest'            # a poll every minute: only the latest successful one is kept
    Path(str(path) + '.out').write_text(out, encoding='utf-8')
    Path(str(path) + '.err').write_text(err, encoding='utf-8')
    return _result(action, 'this host (exit %d, %s.out)' % (proc.returncode, path), 'Success' if proc.returncode == 0 else
                   'exit %d' % proc.returncode, out, err)


def box(action, target=MAIN, timeout=1800, url_map=None, **variables):
    """frankie_box_pod_root.sh on an instance; returns its POD_ROOT_RESULT (dict). Over SSM, except that a controller
    hosted on the main box runs main-box actions locally. A presigned map travels as a private S3 object whose presigned
    GET is MAP_URL (as frankie_box_run.yml does); the map object is deleted after."""
    client = s3(TRANSFER_BUCKET)
    map_key = None
    if url_map is not None:
        map_key = 'box-runs/pod-root-%s-%s/presigned-map.json' % (controller_id(), secrets.token_hex(6))
        client.put_object(Bucket=TRANSFER_BUCKET, Key=map_key, Body=json.dumps(url_map).encode(),
                          ServerSideEncryption='AES256', ContentType='application/json')
        variables['MAP_URL'] = client.generate_presigned_url('get_object', Params=dict(Bucket=TRANSFER_BUCKET, Key=map_key),
                                                             ExpiresIn=timeout + 3600)
    try:
        pairs = ['ACTION=%s' % action] + ['%s=%s' % (k, v) for k, v in variables.items() if v not in (None, '')]
        if HOST['host'] == 'main' and target['instance'] == MAIN['instance']:
            return _local_box(action, timeout, pairs)
        ssm = ssm_client(target['region'])
        path = '%s/%s.out' % (ssm_run_sh.OUTPUT_DIR, secrets.token_hex(16))
        script = ssm_run_sh.kept_whole(ssm_run_sh.preamble(pairs) + BOX_SCRIPT.read_text(encoding='utf-8'), path)
        command = ssm_run_sh.run(ssm, target['instance'], script, timeout, 'pod-root %s' % action)
        status, inv = ssm_run_sh.wait(ssm, target['instance'], command, timeout)
        text = inv.get('StandardOutputContent', '')
        if len(text) >= ssm_run_sh.PART:
            text = ''.join(t for n, t in ssm_run_sh.parts(ssm, target['instance'], path) if n is not None)
        return _result(action, target['instance'], 'SSM ' + status if status != 'Success' else status, text,
                       inv.get('StandardErrorContent', ''))
    finally:
        if map_key:
            client.delete_object(Bucket=TRANSFER_BUCKET, Key=map_key)


# ------------------------------------------------------------------------------------------------------ workers

class BoxWorker:
    """The Linux worker box running pod_agent.py jobs detached, driven over SSM."""
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


# -------------------------------------------------------------------------------------------------------- the lease

def lease_key(run):
    return '%s/%s/controller/lease.json' % (PREFIX, run)


def read_lease(run):
    try:
        raw = s3(TRANSFER_BUCKET).get_object(Bucket=TRANSFER_BUCKET, Key=lease_key(run))['Body'].read()
    except Exception as error:  # noqa: BLE001
        if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    return json.loads(raw)


def lease_alive(lease):
    """A lease is alive while its holder's heartbeat is fresh and it was not released."""
    return bool(lease) and not lease.get('released_utc') and time.time() - float(lease.get('heartbeat_epoch') or 0) < LEASE_FRESH_SECONDS


# ---------------------------------------------------------------------------------------------------- the loop

class Controller:
    def __init__(self, a):
        self.a = a
        self.run = a.run
        self.started = float(HOST.get('started') or time.time())
        self.open_ended = a.budget_minutes == 0
        self.stop_starting = None if self.open_ended else self.started + (a.budget_minutes - a.stop_starting_minutes) * 60
        self.end = None if self.open_ended else self.started + a.budget_minutes * 60
        self.sign = Presigner(a.url_hours)
        self.lock = threading.Lock()
        self.events = []
        self.force_box = set()
        self.start_failures = {}
        self.tries = {}
        self.deferred = set()            # handle() keys whose last try was a lease deferral (F11: not counted as a try)
        self.commit = a.commit
        self.queue_state = None
        self.state = HOST['state']
        self.stop = None                 # the stop request once seen (host main) or the signal received
        self.stop_relayed = None         # {job_id: worker reply} once the cooperative save was relayed
        self.stop_seen = None
        self.outcome = None
        self.last_worker = None
        self.last_submit_at = None       # epoch just BEFORE the last job submit/resume to the worker (its outcome may be unknown)
        self.lease_identity = dict(host=HOST['host'], pid=os.getpid(), started_epoch=int(self.started),
                                   unit=os.environ.get('CPU_CONTROLLER_UNIT'), controller=controller_id(),
                                   scope=dict(run=a.run, days=a.days or 'the saved plan'))
        self.lease_etag = None
        self.lease_extra = {}
        self.lease_lock = threading.Lock()
        self.lease_lost = False
        self.lease_fresh_at = None       # epoch of the last SUCCESSFUL conditional lease write; ownership is established
        self.resume_pending = None       # a resume whose outcome is unknown until the worker's status settles it
        self.scope_noted = set()         # out-of-scope days already named once in the events
        self.heartbeat_thread = None
        self.finished = threading.Event()

    # ---- records

    def event(self, **fields):
        fields['at'] = utc()
        with self.lock:
            self.events.append(fields)
        if self.state:
            self.state.event(fields)
        say(' '.join('%s=%s' % (k, v) for k, v in fields.items() if k != 'at'))

    def snapshot(self, w=None, worker_status=None, held=None):
        if not self.state:
            return
        worker = None
        if w is not None:
            worker = dict(where=w.where, at=utc(), at_epoch=time.time(), jobs=worker_status.get('jobs') if worker_status else None,
                          unreachable=worker_status is None)
            self.last_worker = worker
        q = self.queue_state or {}
        self.state.status(dict(run=self.run, controller=dict(self.lease_identity, action=self.a.action, commit=self.commit,
                                                            code_root=self.a.code_root, budget_minutes=self.a.budget_minutes,
                                                            open_ended=self.open_ended, stop=self.stop,
                                                            stop_relayed=self.stop_relayed, resume_pending=self.resume_pending,
                                                            lease_fresh_at=self.lease_fresh_at, outcome=self.outcome),
                               queue=dict(counts=q.get('counts'), code_commit=q.get('code_commit'), active=q.get('active'),
                                          free_bytes=q.get('free_bytes')),
                               worker=worker or self.last_worker, held=held))

    def queue(self):
        q = box('queue', MAIN, 1800, CODE_ROOT=self.a.code_root, RUN=self.run)
        if self.a.commit and q.get('code_commit') != self.a.commit:
            # 2026-10-09 (Greg): the code version is recorded, never compared: the staged checkout's commit is used
            say('NOTE: the staged checkout is at %s, this dispatch is %s: the staged commit is used and recorded'
                % (q.get('code_commit'), self.a.commit))
        self.commit = q.get('code_commit')
        self.queue_state = q
        return q

    # ---- the lease (one controller per run, across hosts)

    def take_lease(self):
        """Create-only first (S3 refuses a second creator); an existing lease is taken over only when stale or released,
        conditionally on its ETag, so two takers of one stale lease cannot both win."""
        try:
            self.write_lease(IfNoneMatch='*')
            return
        except Exception as error:  # noqa: BLE001
            if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('PreconditionFailed', '412'):
                raise
        obj = s3(TRANSFER_BUCKET).get_object(Bucket=TRANSFER_BUCKET, Key=lease_key(self.run))
        lease, etag = json.loads(obj['Body'].read()), obj['ETag']
        if lease_alive(lease) and {k: lease.get(k) for k in ('host', 'pid', 'started_epoch')} != \
                {k: self.lease_identity[k] for k in ('host', 'pid', 'started_epoch')}:
            raise SystemExit('run %s is served by another controller (host %s, pid %s, unit %s, controller %s, heartbeat %s): '
                             'not a second one; a main-box service takes stop and resume requests through '
                             'frankie_box_cpu_controller.sh ACTION=stop|resume; a runner loop ends with its budget' % (
                                 self.run, lease.get('host'), lease.get('pid'), lease.get('unit'), lease.get('controller'),
                                 lease.get('heartbeat_utc')))
        self.lease_extra = dict(taken_over=dict(at=utc(), previous={k: lease.get(k) for k in ('host', 'pid', 'unit', 'controller',
                                                                                              'heartbeat_utc', 'released_utc')}))
        try:
            self.write_lease(IfMatch=etag)
        except Exception as error:  # noqa: BLE001
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('PreconditionFailed', '412'):
                raise SystemExit('the stale lease of %s was taken by another controller meanwhile; not a second one' % self.run)
            raise

    def write_lease(self, IfNoneMatch=None, IfMatch=None, **fields):
        """Every write after the first is conditional on the ETag this controller last wrote: a lease taken over by
        another controller (after a heartbeat gap longer than its freshness) is lost, never overwritten."""
        doc = dict(self.lease_identity, schema=STATE_SCHEMA + '_LEASE', run=self.run, action=self.a.action,
                   state_dir=str(self.state.dir) if self.state else None, heartbeat_epoch=time.time(), heartbeat_utc=utc(),
                   **self.lease_extra, **fields)
        conditions = {}
        if IfNoneMatch:
            conditions['IfNoneMatch'] = IfNoneMatch
        elif IfMatch or self.lease_etag:
            conditions['IfMatch'] = IfMatch or self.lease_etag
        else:
            raise RuntimeError('no lease held: an unconditional lease write is never made')
        with self.lease_lock:
            r = s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=lease_key(self.run), Body=json.dumps(doc, sort_keys=True).encode(),
                                               ServerSideEncryption='AES256', ContentType='application/json', **conditions)
            self.lease_etag = r.get('ETag')
            self.lease_fresh_at = time.time()

    def heartbeat(self):
        while not self.finished.wait(HEARTBEAT_SECONDS):
            try:
                self.write_lease()
            except Exception as error:  # noqa: BLE001
                if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('PreconditionFailed', '412'):
                    self.lease_lost = True
                    self.event(step='lease', result='lost', detail='another controller holds the lease now; this one ends '
                               'without touching the worker or any claim')
                    return
                self.event(step='lease', result='heartbeat failed', error='%s: %s' % (type(error).__name__, str(error)[:200]),
                           fresh_for=round(time.time() - (self.lease_fresh_at or 0)))

    def lease_established(self, boundary):
        """Ownership at an effect boundary (a claim, a submission after an export, a renewal, a coordination reply, a save
        relay, a resume): the last successful conditional write must be younger than the lease's freshness; otherwise one
        synchronous conditional write is tried now. False = ownership cannot be established (lost, or not renewed within
        the freshness): the effect is NOT made, the claim and any outstanding work stay as they are."""
        if self.lease_lost:
            return False
        if self.lease_fresh_at is not None and time.time() - self.lease_fresh_at < LEASE_FRESH_SECONDS:
            return True
        try:
            self.write_lease()
            return True
        except Exception as error:  # noqa: BLE001
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code in ('PreconditionFailed', '412'):
                self.lease_lost = True
                self.event(step='lease', result='lost', boundary=boundary,
                           detail='another controller holds the lease; the effect is not made')
            else:
                self.event(step='lease', result='not established', boundary=boundary,
                           error='%s: %s' % (type(error).__name__, str(error)[:200]),
                           detail='the lease could not be renewed within its freshness; the effect is not made')
            return False

    def release_lease(self):
        if self.lease_etag is None or self.lease_lost:
            return                                   # never held, or held by another controller now: nothing to release
        try:
            self.write_lease(released_utc=utc(), outcome=self.outcome)
        except Exception as error:  # noqa: BLE001
            self.event(step='lease', result='release failed', error='%s: %s' % (type(error).__name__, str(error)[:200]))

    # ---- the cooperative stop (host main: stop-request.json; any host: SIGTERM)

    def check_stop(self):
        if self.stop is not None or not self.state:
            return
        request = self.state.stop_request()
        if request is None:
            return
        ack = self.state.stop_ack()
        if ack is not None and (ack.get('request') or {}).get('requested_epoch') == request.get('requested_epoch'):
            return                                   # this request was acknowledged already (the launcher archives both)
        self.stop = dict(request, source='stop-request.json')
        self.stop_seen = time.time()
        self.event(step='stop', result='requested', save=request.get('save'), requested=request.get('requested_utc'))

    def check_resume(self, w, jobs):
        """A retained job's same-owner resume requested through the state directory, served once by the running service:
        the original job, claim and inputs (renew with resume), never a new attempt; refused with the reason otherwise."""
        if not self.state:
            return
        if self.resume_pending is None and self.state.resume_pending():
            # a previous controller left a resume unresolved (durable): reconciled, never re-sent; an unreadable record is
            # named and ends the service (nothing is guessed about a launch that may have happened)
            pending = self.state.resume_pending()
            if pending.get('unreadable') or not pending.get('job_id') or not pending.get('since'):
                raise SystemExit('resume-pending.json is unreadable or incomplete (%s): read it and move it aside by hand; '
                                 'nothing is re-sent' % (pending.get('error') or 'missing job_id/since'))
            self.resume_pending = pending
            self.event(step='resume', attempt=self.resume_pending.get('job_id'), result='pending from a previous controller',
                       detail='reconciled through the worker status; not redispatched')
            return
        if self.resume_pending is not None:
            return                                   # one request at a time; the pending one is reconciled first
        request = self.state.resume_request()
        if request is None:
            return
        job_id = str(request.get('job_id') or '')
        ack = dict(run=self.run, request=request, controller=self.lease_identity)
        before = next((dict(j) for j in jobs if j.get('job_id') == job_id), None)
        try:
            if self.stop is not None:
                raise ValueError('a stop is pending; no resume while stopping')
            if not re.fullmatch(re.escape(self.run) + r'-[0-9]{8}-a[0-9]+', job_id):
                raise ValueError('job_id must name the original run-day-attempt')
            q = self.queue()
            held = next((d.get('claim') for d in q['days'] if (d.get('claim') or {}).get('attempt') == job_id), None)
            if not held or held.get('where') != w.where:
                raise ValueError('the day must still be claimed by this Linux worker (original claim untouched)')
            if not self.authorized(held.get('day') or job_id[len(self.run) + 1:len(self.run) + 9]):
                raise ValueError('the day is outside this controller\'s authorized scope (--days); not resumed here')
            if before and (before.get('pid_alive') or before.get('state') == 'day_complete'):
                raise ValueError('the job is %s (pid alive %s): a live or completed day is not resumed' % (
                    before.get('state'), before.get('pid_alive')))
        except (Exception, SystemExit) as error:  # noqa: BLE001
            # refused BEFORE any transport or renewal: nothing was sent, nothing rewritten
            ack.update(resumed=False, refused='%s: %s' % (type(error).__name__, str(error)[:400]),
                       note='refused before any renewal or transport; original claim, job files and inputs untouched')
            self.event(worker=w.where, step='resume', attempt=job_id, result='refused', error=ack['refused'][:300])
            self.state.resume_acknowledge(ack)
            return
        try:
            result = self.renew(w, dict(job_id=job_id), resume=True)
        except LeaseNotEstablished as error:
            # refused before any transport: the lease could not be established, nothing was sent or rewritten
            ack.update(resumed=False, refused='%s: %s' % (type(error).__name__, str(error)[:400]),
                       note='refused before any renewal or transport; original claim, job files and inputs untouched')
            self.event(worker=w.where, step='resume', attempt=job_id, result='refused', error=ack['refused'][:300])
            self.state.resume_acknowledge(ack)
            return
        except (Exception, SystemExit) as error:  # noqa: BLE001
            # the renewal/transport step failed or timed out AFTER it may have rewritten transport metadata or launched
            # the job: the outcome is UNKNOWN until the worker's own status settles it; the request stays as evidence
            self.resume_pending = dict(job_id=job_id, since=time.time(), request=request, before=before,
                                       error='%s: %s' % (type(error).__name__, str(error)[:400]))
            self.state.resume_pend(self.resume_pending)
            self.event(worker=w.where, step='resume', attempt=job_id, result='unknown', error=self.resume_pending['error'][:300],
                       detail='reconciled through the worker status before any definite acknowledgment; no redispatch')
            self.snapshot()
            return
        ack.update(resumed=True, result=result)
        self.event(worker=w.where, step='resume', attempt=job_id, result='resumed', detail=result)
        self.state.resume_acknowledge(ack)

    def reconcile_resume(self, w, jobs):
        """An unknown resume settled by the worker's status: the job live (or advanced) = it resumed; the job unchanged
        for a whole lease freshness = no launch observed. Either way the original attempt is the one acknowledged; nothing
        is redispatched and the request evidence is archived only with its acknowledgment."""
        pending = self.resume_pending
        if pending is None:
            return
        now = next((dict(j) for j in jobs if j.get('job_id') == pending['job_id']), None)
        before = pending.get('before') or {}
        ack = dict(run=self.run, request=pending['request'], controller=self.lease_identity, transport_error=pending['error'],
                   observed_before=before, observed_now=now)
        if now and (now.get('pid_alive') or now.get('state') == 'day_complete' or
                    (now.get('updated') and now.get('updated') != before.get('updated'))):
            ack.update(resumed=True, reconciled='the worker reports the original attempt live or advanced after the '
                                                 'transport failure')
            self.event(worker=w.where, step='resume', attempt=pending['job_id'], result='reconciled resumed')
        elif time.time() - pending['since'] > LEASE_FRESH_SECONDS:
            ack.update(resumed=False, reconciled='no launch observed within %d s after the transport failure; the original '
                                                  'attempt, claim and inputs are retained; a new request may be made'
                                                  % LEASE_FRESH_SECONDS)
            self.event(worker=w.where, step='resume', attempt=pending['job_id'], result='reconciled not resumed')
        else:
            return
        self.resume_pending = None
        self.state.resume_settled()
        if (self.state.dir / 'resume-request.json').exists():
            self.state.resume_acknowledge(ack)
        else:                                        # the request was moved aside by hand: the acknowledgment still lands
            write_json(self.state.dir / ('resume-ack-%d.json' % int(time.time())),
                       dict(ack, schema=STATE_SCHEMA + '_RESUME_ACK', acknowledged_utc=utc()), create_only=True)

    def relay_save(self, w, jobs):
        """Once: the cooperative save requested of every live retained job of this run on the worker. Not made while the
        lease is not established (retried at the next poll; the stop is not settled before the relay is made)."""
        if self.stop_relayed is not None:
            return
        if not self.stop.get('save'):
            self.stop_relayed = {}
            return
        if not self.lease_established('stop relay'):
            self.event(worker=w.where, step='stop', result='relay deferred', detail='lease ownership not established; retried')
            return
        self.stop_relayed = {}
        for j in jobs:
            if j.get('workflow') == 'root-to-finish' and j.get('pid_alive'):
                try:
                    r = box('stop', w.target, 600, COMMIT=self.commit, JOB=j['job_id'])
                    self.stop_relayed[j['job_id']] = r.get('result')
                except Exception as error:  # noqa: BLE001
                    self.stop_relayed[j['job_id']] = 'relay failed: %s: %s' % (type(error).__name__, str(error)[:300])
                self.event(worker=w.where, day=j.get('day'), step='stop', attempt=j['job_id'], result=self.stop_relayed[j['job_id']])

    def stop_settled(self, jobs):
        """True once the relay was made and no relayed job is still active, or the stop wait elapsed (the job then
        continues unattended, or the save was never relayed; the acknowledgment says which)."""
        elapsed = time.time() - self.stop_seen > self.a.stop_wait_minutes * 60
        if self.stop_relayed is None:
            return elapsed                           # the relay is still to be made (the lease); settled only by the wait
        waiting = [j for j in jobs if j.get('job_id') in self.stop_relayed and j.get('state') in ACTIVE and j.get('pid_alive')]
        return not waiting or elapsed

    def acknowledge_stop(self, w, jobs):
        pending = [dict(job_id=j.get('job_id'), day=j.get('day'), state=j.get('state'), pid_alive=j.get('pid_alive'),
                        save_requested=j.get('save_requested'))
                   for j in jobs if j.get('run') == self.run and j.get('state') not in ('day_complete', 'cleaned')]
        unattended = [p for p in pending if p['pid_alive']]
        self.outcome = dict(outcome='stop_acknowledged', request=self.stop, relayed=self.stop_relayed, pending=pending,
                            jobs_continue_unattended=unattended, claims_untouched=True, complete=False,
                            save_never_relayed=bool(self.stop.get('save')) and self.stop_relayed is None)
        if self.state:
            self.state.acknowledge(dict(run=self.run, request=self.stop, relayed=self.stop_relayed, pending=pending,
                                        jobs_continue_unattended=unattended, controller=self.lease_identity))
        self.event(worker=w.where, step='stop', result='acknowledged', pending=len(pending), unattended=len(unattended))

    # ---- the days

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
        box need not upload it; the worker checks the sha256 either way."""
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

    def resign(self, inputs):
        """Every input part's GET re-signed now (an export can take hours; a URL signed before it would be the older one;
        on the main host the signing credentials are the instance profile's session, so URLs are signed as late as possible)."""
        for f in inputs:
            for part in f['parts']:
                part['url'] = self.sign.get(part['bucket'], part['key'])
        return inputs

    def start_day(self, w, st, retained=False):
        day = st['day']
        if not retained:
            c = box('claim', MAIN, 1800, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day, WHERE=w.where, COMMIT=self.commit)
            if not c.get('claimed'):
                self.event(worker=w.where, day=day, step='claim', result='not claimed', state=(c.get('state') or {}).get('state'),
                           holder=(c.get('claim') or {}).get('where'))
                return False
            st = c['state']
        attempt = st['attempt']
        self.event(worker=w.where, day=day, step='claim', result='claimed', attempt=attempt, role=st['role'], digest=st['digest'])
        try:
            inputs, need = [], []
            for f in st['files']:
                src = self.s3_source(st, f)
                if src:
                    inputs.append(dict(f, parts=[dict(url=None, bytes=f['bytes'], bucket=src[0], key=src[1])],
                                       source='s3://%s/%s' % src))
                else:
                    need.append(f)
            for f in need:
                # one file per export call, its PUT slots signed just before the call: a slot is never older than one
                # file's upload (on the main host the signing session is the instance profile's, bounded)
                slots = {}
                for i, (off, ln) in enumerate(T.plan_parts(f['bytes'])):
                    key = '%s/in/%s.part-%04d' % (self.prefix(attempt), f['name'], i)
                    slot = dict(url=self.sign.put(TRANSFER_BUCKET, key))
                    if retained:
                        try:
                            head = s3(TRANSFER_BUCKET).head_object(Bucket=TRANSFER_BUCKET, Key=key)
                        except Exception as error:
                            if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('404', 'NoSuchKey', 'NotFound'):
                                raise
                        else:
                            if head['ContentLength'] != ln:
                                raise ValueError('retained exported part has different size: %s' % key)
                            slot['present_bytes'] = ln
                    slots['put:' + key] = slot
                t0 = time.time()
                r = box('export', MAIN, 4 * 3600, url_map=slots, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day,
                        WHERE=w.where, ATTEMPT=attempt, FILES=f['name'])
                parts = r['files'][f['name']]['parts']
                inputs.append(dict(f, parts=[dict(url=None, bytes=p['bytes'], bucket=TRANSFER_BUCKET, key=p['key']) for p in parts],
                                   source='box export'))
                self.event(worker=w.where, day=day, step='export', file=f['name'], bytes=f['bytes'], parts=len(parts),
                           seconds=round(time.time() - t0))
            if not self.lease_established('submit'):
                raise LeaseNotEstablished('lease ownership not established after the export; the job is not submitted (the '
                                          'claim and the exported parts are retained for the owner that holds the lease)')
            self.resign(inputs)
            job = dict(schema='FRANKIE_POD_ROOT_JOB_V1', name=attempt, run=self.run, day=day, role=st['role'],
                       digest=st['digest'], commit=self.commit, data_workers=15,
                       ingest_dir=st['ingest_dir'], ingestion_receipt=st['ingestion_receipt'],
                       ingestion_receipt_sha256=st['ingestion_receipt_sha256'], day_external_sha256=st['day_external_sha256'],
                       frozen_survivors=st.get('frozen_survivors'),
                       inputs=[{k: f[k] for k in ('role', 'path', 'name', 'bytes', 'sha256', 'parts', 'source')} for f in inputs],
                       out={}, where=w.where, created=utc(), controller_run=controller_id(),
                       workflow='root-to-finish', plan=st['plan'], settings=dict(st['settings'], data_workers=15, search_workers=15),
                       mailbox=dict(request_put=self.sign.put(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/request.json'),
                                    response_get=self.sign.get(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/response.json')))
            key = '%s/job.json' % self.prefix(attempt)
            try:
                s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=key, Body=json.dumps(job).encode(),
                                               ServerSideEncryption='AES256', IfNoneMatch='*')
            except Exception as error:
                if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('PreconditionFailed', '412'):
                    raise
                existing = json.loads(s3(TRANSFER_BUCKET).get_object(Bucket=TRANSFER_BUCKET, Key=key)['Body'].read())

                def identity(body):
                    fields = {k: v for k, v in body.items() if k not in ('mailbox', 'created', 'controller_run')}
                    fields['inputs'] = [dict(f, parts=[{k: v for k, v in p.items() if k != 'url'}
                                                      for p in f['parts']]) for f in fields['inputs']]
                    return fields
                if identity(existing) != identity(job):
                    raise ValueError('retained job differs; S3 job not overwritten')
                # the retained job (same identity) is submitted with GETs and a mailbox signed NOW, not the ones signed
                # when it was first stored (a URL is not identity; the worker checks bucket/key and sha256)
                job = existing
                job['inputs'] = self.resign(job['inputs'])
                job['mailbox'] = dict(request_put=self.sign.put(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/request.json'),
                                      response_get=self.sign.get(TRANSFER_BUCKET, self.prefix(attempt) + '/rpc/response.json'))
                # F2 (second review): the worker reads the job BODY from _job_url (pod_agent: a presigned GET of this
                # key), not from the submitted dict, so the re-signed GETs and mailbox only take effect once stored. The
                # identity check above proved it is the same job; it is written back unconditionally, as renew() does.
                # The lease was established for 'submit' just above; this write is part of that submission.
                s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=key, Body=json.dumps(job).encode(),
                                               ServerSideEncryption='AES256')
            job['_job_url'] = self.sign.get(TRANSFER_BUCKET, key)
            self.last_submit_at = time.time()      # before the effect: an interrupted submit leaves the worker's state unknown
            job_id, why = w.submit(job)
            if not job_id:
                raise RuntimeError('the worker refused the job: %s' % why)
            self.event(worker=w.where, day=day, step='job', result='started', attempt=attempt,
                       s3_inputs=sum(1 for f in inputs if f['source'] != 'box export'))
            # the worker box is IN USE for this day's ROOT-to-finish window: KeepRunning=true, named (cleared at finish())
            self.event(worker=w.where, day=day, step='keep_running', **keep_running(
                w.target['instance'], w.target['region'], True, 'day %s attempt %s started on the Linux lane (run %s)' % (day, attempt, self.run),
                'pod_root/controller.py ' + controller_id()))
            return True
        except LeaseNotEstablished as e:
            # not a start defect: nothing was submitted; the claim and the exported parts stay for the lease holder
            self.event(worker=w.where, day=day, step='start', result='lease not established', attempt=attempt, error=str(e)[:300])
            return None
        except Exception as e:  # noqa: BLE001
            self.event(worker=w.where, day=day, step='start', result='failed', error='%s: %s' % (type(e).__name__, str(e)[:400]))
            # An SSM timeout can occur after acceptance. Keep ownership and input slots until status establishes what
            # happened; releasing here could dispatch the day twice.
            self.event(worker=w.where, day=day, step='held', attempt=attempt,
                       result='preparation/submission requires same-box status/resume; claim and inputs retained')
            return False

    def release(self, w, day, attempt, reason):
        try:
            r = box('release', MAIN, 600, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day, WHERE=w.where, ATTEMPT=attempt,
                    REASON=re.sub(r"[^A-Za-z0-9 _.,:()=-]", ' ', reason)[:300])
            self.event(worker=w.where, day=day, step='release', attempt=attempt, released=r.get('released'), detail=r.get('detail'))
        except BoxError as e:
            self.event(worker=w.where, day=day, step='release', attempt=attempt, result='failed', error=str(e)[:300])

    def handle(self, w, j):
        """One finished job of this run on the worker: a retained day is reported and held; a legacy shipping state is
        released and cleaned (no legacy job is started any more; an old one found on the worker is still accounted for)."""
        state, attempt, day = j.get('state'), j.get('job_id'), j.get('day')
        key = (w.where, attempt, state)
        if self.tries.get(key, 0) >= 2:
            self.tries[key] += 1
            if self.tries[key] == 3:
                self.event(worker=w.where, day=day, attempt=attempt, step='handle', result='gave up after 2 tries', state=state)
            return
        # F11 (second review): a LeaseNotEstablished deferral is not a try. It is recorded 'deferred' (once per streak),
        # never 'failed', and does not count toward the two-try give-up, so a lease re-established later in this same
        # process still releases and cleans the failed job. Every other outcome counts, as before.
        counted = True
        try:
            if j.get('workflow') == 'root-to-finish':
                self.event(worker=w.where, day=day, attempt=attempt, step='retained', result=state, detail=j.get('detail'))
                return
            if state in FINISHED_FAILED:
                if not self.lease_established('release'):
                    # the claim release, the worker clean and the S3 delete are effects: not made unless ownership is
                    # established at this boundary (the loop entrance ends the service when it stays unestablished)
                    raise LeaseNotEstablished('lease ownership not established; the failed job %s is left as found (claim, '
                                              'worker files and S3 parts retained for the lease holder)' % attempt)
                if state == 'failed_inputs':
                    self.force_box.add(day)                  # the next attempt takes every input from the box itself
                self.release(w, day, attempt, 'the worker job ended %s: %s' % (state, j.get('detail')))
                self.event(worker=w.where, day=day, attempt=attempt, step='clean', worker_result=w.clean(attempt, None),
                           s3_objects_deleted=self.delete_prefix(attempt))
            else:
                self.event(worker=w.where, day=day, attempt=attempt, step='legacy', result=state,
                           detail='a legacy shipping job state; no import or reupload route exists any more; left as found')
        except LeaseNotEstablished as e:
            counted = False
            if key not in self.deferred:
                self.deferred.add(key)
                self.event(worker=w.where, day=day, attempt=attempt, step='handle %s' % state, result='deferred',
                           error=str(e)[:500], detail='not counted as a try; retried when the lease is established')
        except Exception as e:  # noqa: BLE001
            self.event(worker=w.where, day=day, attempt=attempt, step='handle %s' % state, result='failed',
                       error='%s: %s' % (type(e).__name__, str(e)[:500]))
        finally:
            if counted:
                self.deferred.discard(key)
                self.tries[key] = self.tries.get(key, 0) + 1

    def authorized(self, day):
        """The authorized scope: the run's saved plan, narrowed by --days when given (a one-day scope admits one day)."""
        return not self.a.days or day in self.a.days

    def next_ready(self):
        """The front ready day of the line within the authorized scope: an out-of-scope day ahead that has not started
        makes the eligible days behind it wait (FIFO), and is never claimed by this controller."""
        with self.lock:
            q = self.queue()
            for d in q['days']:
                if d['state'] == 'ready' and not self.authorized(d['day']):
                    if d['day'] not in self.scope_noted:
                        self.scope_noted.add(d['day'])
                        self.event(day=d['day'], step='scope', result='out of scope ahead',
                                   detail='not claimed by this controller; the eligible days behind it wait (FIFO)')
                    return None
                if d['state'] == 'ready' and self.start_failures.get(d['day'], 0) < 2:
                    return d
            return None

    def coordinate(self, w, job):
        if not self.lease_established('coordinate'):
            raise LeaseNotEstablished('lease ownership not established; the coordination request is left for the lease holder')
        prefix = self.prefix(job['job_id']) + '/rpc'
        response = box('coordinate', MAIN, 1800, CODE_ROOT=self.a.code_root,
                       url_map=dict(rpc=dict(url=self.sign.get(TRANSFER_BUCKET, prefix + '/request.json')),
                                    reply=dict(url=self.sign.put(TRANSFER_BUCKET, prefix + '/response.json'))))
        self.event(worker=w.where, day=job['day'], step='coordinate', id=response.get('id'), error=response.get('error'))
        # 2026-10-09: the worker waits on its mailbox file being rewritten (frankie_box_lane_state._await_mailbox, no
        # interval): a renewal right after the answer wakes it at once. A failed renewal is named; the next one wakes it
        try:
            self.renew(w, job)
        except Exception as error:  # noqa: BLE001
            self.event(worker=w.where, day=job['day'], step='coordinate_wake', result='retry', error=type(error).__name__)

    def renew(self, w, job, resume=False):
        if not self.lease_established('resume' if resume else 'renew'):
            raise LeaseNotEstablished('lease ownership not established; the %s is not made' % ('resume' if resume else 'renewal'))
        prefix = self.prefix(job['job_id']) + '/rpc'
        update = dict(mailbox=dict(request_put=self.sign.put(TRANSFER_BUCKET, prefix + '/request.json'),
                                   response_get=self.sign.get(TRANSFER_BUCKET, prefix + '/response.json')))
        key = self.prefix(job['job_id']) + '/job.json'
        try:
            saved = json.loads(s3(TRANSFER_BUCKET).get_object(Bucket=TRANSFER_BUCKET, Key=key)['Body'].read())
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('404', 'NoSuchKey', 'NotFound'):
                raise
            saved = None
        if resume:
            if saved is None:
                if any(j['job_id'] == job['job_id'] for j in w.status()['jobs']):
                    raise ValueError('worker has this job but its stored source job is missing; retained files not overwritten')
                day = job['job_id'][len(self.run) + 1:len(self.run) + 9]
                prepared = box('prepare', MAIN, 1800, CODE_ROOT=self.a.code_root, RUN=self.run, DAY=day,
                               WHERE=w.where, ATTEMPT=job['job_id'], COMMIT=self.commit)
                started = self.start_day(w, prepared['state'], retained=True)
                if started is None:
                    raise LeaseNotEstablished('lease ownership not established before the retained submission; nothing '
                                              'sent; same claim and inputs kept')
                if not started:
                    raise RuntimeError('retained preparation did not complete; same claim and inputs kept')
                return dict(job_id=job['job_id'], resumed_preparation=True)
            if (saved['run'], saved['name'], saved['where']) != (self.run, job['job_id'], w.where):
                raise ValueError('resume must use the original job and owner')   # its commit recorded, never compared
        if saved is not None:
            # the inputs' GETs re-signed with the renewal (same bucket/key identity, which the worker checks), so a job
            # whose input stage outlives the signing session keeps readable sources
            saved['inputs'] = self.resign(saved['inputs'])
            saved['mailbox'] = update['mailbox']
            update['inputs'] = saved['inputs']
            s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, Key=key, Body=json.dumps(saved).encode(),
                                           ServerSideEncryption='AES256')
        if resume:
            status = w.status()
            if not any(j['job_id'] == job['job_id'] for j in status['jobs']):
                # Acceptance never reached the box, or its SSM answer was lost: retry the SAME claimed job.
                saved['_job_url'] = self.sign.get(TRANSFER_BUCKET, key)
                self.last_submit_at = time.time()
                return w.submit(saved)
            self.last_submit_at = time.time()
        return box('resume' if resume else 'renew', w.target, 600, COMMIT=self.commit, JOB=job['job_id'], url_map=update)

    def remaining_work(self, q, jobs, w):
        """What keeps an open-ended controller alive: a day the Linux lane could still take or is holding, or a worker job
        of this run that is not complete. Empty = the run's Linux lane has nothing left (which says nothing about the two
        main lanes or about any day's scientific completion)."""
        reasons, blocked = [], []
        for d in q['days']:
            claim = d.get('claim') or {}
            if not self.authorized(d['day']) and claim.get('where') != w.where:
                continue                                 # outside the authorization and not this lane's: not its work
            if d['state'] == 'ready' and self.start_failures.get(d['day'], 0) >= 2:
                blocked.append('%s ready but not started after 2 failed starts' % d['day'])
            elif d['state'] in ('ready', 'waiting_ingest', 'waiting_day_file', 'behind_in_root_line', 'not_in_root_line'):
                reasons.append('%s %s' % (d['day'], d['state']))
            elif claim.get('where') == w.where and not ((claim.get('done') or {}).get('lane_complete')):
                reasons.append('%s held by this lane (%s)' % (d['day'], claim.get('attempt')))
        for j in jobs:
            if j.get('run') == self.run and j.get('state') not in ('day_complete', 'cleaned'):
                reasons.append('job %s %s' % (j.get('job_id'), j.get('state')))
        return reasons, blocked

    def worker_loop(self, w, only_job=None):
        """The thread of one worker; any failure of the loop itself is recorded as the outcome, never lost in the thread."""
        try:
            self._worker_loop(w, only_job)
        except (Exception, SystemExit) as error:  # noqa: BLE001
            self.outcome = self.outcome or dict(outcome='failed', error='%s: %s' % (type(error).__name__, str(error)[:600]),
                                                complete=False, note='the controller loop failed; the worker keeps its job '
                                                'and claim; nothing was released')
            self.event(worker=w.where, step='loop', result='failed', error='%s: %s' % (type(error).__name__, str(error)[:400]))
            self.snapshot()

    def _worker_loop(self, w, only_job):
        failures = 0
        renewed = {}
        while True:
            if self.lease_lost:
                self.outcome = self.outcome or dict(outcome='lease_lost', complete=False,
                                                    note='another controller took the lease; the worker keeps its job and claim')
                self.snapshot()
                return
            if not self.lease_established('poll'):
                self.outcome = self.outcome or dict(outcome='lease_unestablished', complete=False,
                                                    note='the lease could not be renewed within its freshness and ownership '
                                                         'cannot be established; the worker keeps its job and claim; '
                                                         'outstanding effects are retained for the lease holder')
                self.snapshot()
                return
            self.check_stop()
            try:
                st = w.status()
                failures = 0
            except Exception as e:  # noqa: BLE001
                failures += 1
                self.event(worker=w.where, step='status', result='unreachable', error=str(e)[:200], failures=failures)
                self.snapshot(w, None)
                if failures >= 10:
                    self.outcome = self.outcome or dict(outcome='worker_unreachable', failures=failures, complete=False)
                    return
                time.sleep(self.a.poll_seconds)
                continue
            jobs = [j for j in st.get('jobs') or [] if j.get('run') == self.run]
            if only_job is None:
                self.reconcile_resume(w, jobs)
                self.check_resume(w, jobs)
            if self.stop is not None:
                self.relay_save(w, jobs)
                if self.stop_settled(jobs):
                    self.acknowledge_stop(w, jobs)
                    self.snapshot(w, st)
                    return
            if only_job and any(j.get('job_id') == only_job and j.get('state') == 'day_complete' for j in jobs):
                self.outcome = dict(outcome='resumed_job_complete', job=only_job, complete=False,
                                    note='the resumed job reports day_complete; the run itself is not judged here')
                self.snapshot(w, st)
                return
            for j in jobs:
                if j.get('workflow') == 'root-to-finish' and j.get('pid_alive') and \
                        time.time() - renewed.get(j['job_id'], 0) > 900:
                    try:
                        self.renew(w, j)
                        renewed[j['job_id']] = time.time()
                    except Exception as error:
                        self.event(worker=w.where, day=j['day'], step='renew', result='retry',
                                   error=type(error).__name__)
                if j.get('state') == 'coordinate':
                    try:
                        self.coordinate(w, j)
                    except Exception as error:
                        self.event(worker=w.where, day=j['day'], step='coordinate', result='retry',
                                   error=type(error).__name__)
                if j.get('state') not in ACTIVE + ('cleaned',):
                    self.handle(w, j)
            if self.end is not None and time.time() >= self.end:
                self.outcome = dict(outcome='budget_expired', budget_minutes=self.a.budget_minutes, complete=False,
                                    pending=[dict(job_id=j.get('job_id'), state=j.get('state')) for j in jobs
                                             if j.get('state') not in ('day_complete', 'cleaned')],
                                    note='a finite budget ended; the worker keeps its job and claim; a later loop or the '
                                         'main-box controller service continues the coordination')
                self.snapshot(w, st)
                return
            try:
                st = w.status()
            except Exception as e:  # noqa: BLE001
                self.event(worker=w.where, step='status', result='unreachable', error=str(e)[:200])
                self.snapshot(w, None)
                time.sleep(self.a.poll_seconds)
                continue
            jobs = [j for j in st.get('jobs') or []]
            # a job just launched carries its previous state until it writes its own: its live process makes it active
            active = [j for j in jobs if j.get('state') in ACTIVE or j.get('pid_alive')]
            retained = [j for j in jobs if j.get('workflow') == 'root-to-finish' and j not in active and j.get('state') != 'day_complete']
            held = None
            if retained:
                self.event(worker=w.where, step='held', result='failed/interrupted day requires same-box resume',
                           days=[j['day'] for j in retained])
                self.snapshot(w, st, held=[j['job_id'] for j in retained])
                if only_job and any(j.get('job_id') == only_job for j in retained):
                    state = next(j.get('state') for j in retained if j.get('job_id') == only_job)
                    self.outcome = dict(outcome='resumed_job_retained', job=only_job, state=state, complete=False,
                                        note='the resumed job left its active stages without day_complete; its files, '
                                             'claim and lane are retained for a later same-job resume')
                    return
                time.sleep(self.a.poll_seconds)
                continue
            free = int(st.get('slots') or 1) - len(active)
            may_start = self.stop is None and not only_job and (self.stop_starting is None or time.time() < self.stop_starting)
            if free > 0 and may_start:
                # A claim can outlive an interrupted accept/launcher handoff. An empty worker listing
                # does not free that lane or authorize assigning a second day to it.
                q = self.queue()
                held = [d for d in q['days'] if (d.get('claim') or {}).get('where') == w.where
                        and not ((d['claim'].get('done') or {}).get('lane_complete'))]
                if held:
                    self.event(worker=w.where, step='held', result='original claim requires same-job resume',
                               attempts=[d['claim']['attempt'] for d in held])
                    self.snapshot(w, st, held=[d['claim']['attempt'] for d in held])
                    time.sleep(self.a.poll_seconds)
                    continue
                d = self.next_ready()
                if d is not None:
                    if not self.lease_established('claim'):
                        # ownership not established: no claim is made and the day is NOT counted a failed start; the
                        # loop entrance ends the service on the next iteration if the lease stays unestablished
                        self.event(worker=w.where, day=d['day'], step='claim', result='not made',
                                   detail='lease ownership not established')
                        self.snapshot(w, st)
                        time.sleep(self.a.poll_seconds)
                        continue
                    started = self.start_day(w, d)
                    if started or started is None:       # None: the lease, not the start, was the obstacle (not counted)
                        self.snapshot(w, st)
                        continue
                    with self.lock:
                        self.start_failures[d['day']] = self.start_failures.get(d['day'], 0) + 1
                if not active and self.open_ended:
                    remaining, blocked = self.remaining_work(self.queue_state, jobs, w)
                    if not remaining:
                        if blocked:
                            self.outcome = dict(outcome='blocked_by_start_failures', complete=False, blocked=blocked,
                                                counts=(self.queue_state or {}).get('counts'),
                                                note='the only remaining Linux-lane work is days whose start failed twice '
                                                     '(events name why); the service ends so the cause can be read and fixed')
                        else:
                            self.outcome = dict(outcome='no_remaining_work', complete=False,
                                                counts=(self.queue_state or {}).get('counts'),
                                                note='no day the Linux lane could take or is holding and no worker job of the '
                                                     'run left incomplete; the main lanes and scientific completion are not '
                                                     'judged here')
                        self.event(worker=w.where, step='idle', result=self.outcome['outcome'] + '; the service ends')
                        self.snapshot(w, st)
                        return
                elif not active and not self.a.wait_for_days:
                    self.event(worker=w.where, step='idle', result='no ready day and nothing running: this worker is idle')
                    self.outcome = dict(outcome='idle', complete=False)
                    self.snapshot(w, st)
                    return
            self.snapshot(w, st, held=held)
            time.sleep(self.a.poll_seconds)

    def summary(self):
        counts = {}
        for e in self.events:
            k = '%s:%s' % (e.get('step'), e.get('result') or e.get('status') or '')
            counts[k] = counts.get(k, 0) + 1
        return dict(run=self.run, commit=self.commit, host=HOST['host'], minutes=round((time.time() - self.started) / 60, 1),
                    event_counts=counts, queue_counts=(self.queue_state or {}).get('counts'), outcome=self.outcome,
                    complete=False)


def workers_of(a, commit):
    return [BoxWorker(spec, commit) for spec in [b for b in (a.boxes or '').split(',') if b]]


# ------------------------------------------------------------------------------------------- host main: preflight

def preflight(a):
    """The prerequisites a controller hosted on the main box needs beyond its source, checked read-only, each named with
    the exact permission or path it stands for. Nothing is created, installed or provisioned; a missing one refuses."""
    worker = a.boxes.partition('@')[0]
    checks = []

    def check(name, needs, call):
        try:
            detail = call()
            checks.append(dict(prerequisite=name, needs=needs, established=True, detail=detail))
        except Exception as error:  # noqa: BLE001
            checks.append(dict(prerequisite=name, needs=needs, established=False,
                               error='%s: %s' % (type(error).__name__, str(error)[:300])))

    def saved_plan():
        path = Path(PLAN_PARENT, a.run, 'plan.json')
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return dict(bytes=path.stat().st_size)

    def staged():
        head = subprocess.run(['git', '-C', a.code_root, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', a.code_root, 'status', '--porcelain', '--untracked-files=no'], capture_output=True,
                               text=True, check=True).stdout
        if dirty:
            raise ValueError('HEAD %s has tracked changes' % head)
        # the dispatched --commit is recorded beside HEAD, never compared (2026-10-09)
        return dict(head=head, clean=True, dispatched=a.commit, same_as_dispatched=head == a.commit)

    check('saved main plan', '%s/%s/plan.json written by the main orchestrator\'s first start of this run' % (PLAN_PARENT, a.run),
          saved_plan)
    check('claim store route', '%s (frankie_box_root_claims.py; ACTION=enable creates it, which the loop does)' % CLAIMS_PARENT,
          lambda: dict(active=Path(CLAIMS_PARENT).is_dir()))
    check('staged checkout', '%s at --commit %s, tracked tree clean' % (a.code_root, a.commit), staged)
    check('box script', str(BOX_SCRIPT), lambda: dict(bytes=BOX_SCRIPT.stat().st_size))
    check('credentials', 'an AWS credential chain on this host (the instance profile): sts:GetCallerIdentity',
          lambda: dict(arn=boto3.client('sts', region_name=MAIN['region']).get_caller_identity().get('Arn')))
    check('transfer bucket', 's3:ListBucket on %s under %s/%s/ (and GetObject, PutObject, DeleteObject there and under '
          'box-runs/, which only the loop exercises)' % (TRANSFER_BUCKET, PREFIX, a.run),
          lambda: dict(keys=s3(TRANSFER_BUCKET).list_objects_v2(Bucket=TRANSFER_BUCKET, Prefix='%s/%s/' % (PREFIX, a.run),
                                                                MaxKeys=1).get('KeyCount')))
    check('ingest bucket', 's3:ListBucket on %s under frankie/ingest/ (HeadObject on runner ingests and day files)' % INGEST_BUCKET,
          lambda: dict(keys=s3(INGEST_BUCKET).list_objects_v2(Bucket=INGEST_BUCKET, Prefix='frankie/ingest/', MaxKeys=1).get('KeyCount')))
    check('worker over SSM', 'ssm:DescribeInstanceInformation now; ssm:SendCommand and ssm:GetCommandInvocation on %s for every '
          'worker call (exercised by the first status poll, not here)' % worker,
          lambda: dict(ping=[(x['PingStatus'], x.get('PlatformName')) for x in ssm_client(
              a.boxes.partition('@')[2] or 'us-east-1').describe_instance_information(
              Filters=[{'Key': 'InstanceIds', 'Values': [worker]}])['InstanceInformationList']]))
    check('worker KeepRunning tag', 'ec2:DescribeInstances now; ec2:CreateTags on %s for the KeepRunning tag at the day\'s start and '
          'at the controller\'s end (exercised by the loop, not here)' % worker,
          lambda: dict(tags={t['Key']: t['Value'] for t in boto3.client('ec2', region_name=a.boxes.partition('@')[2] or 'us-east-1')
                             .describe_instances(InstanceIds=[worker])['Reservations'][0]['Instances'][0].get('Tags', [])
                             if t['Key'] in ('KeepRunning', 'KeepRunningPolicy', 'KeepRunningReason')}))

    def lease_state():
        lease = read_lease(a.run)
        return dict(lease=lease, alive=lease_alive(lease))

    check('lease', 'no live controller of %s (s3:GetObject on %s)' % (a.run, lease_key(a.run)), lease_state)
    missing = [c for c in checks if not c['established']]
    worker_online = next((c for c in checks if c['prerequisite'] == 'worker over SSM'), {})
    if worker_online.get('established') and not any(p[0] == 'Online' for p in worker_online['detail']['ping']):
        missing.append(dict(prerequisite='worker Online', needs='%s Online in SSM' % worker, established=False,
                            error='ping %s' % worker_online['detail']['ping']))
    lease = next((c for c in checks if c['prerequisite'] == 'lease'), {})
    if lease.get('established') and lease['detail']['alive']:
        missing.append(dict(prerequisite='lease', needs='no live controller of the run', established=False,
                            error='a live lease: %s' % lease['detail']['lease']))
    return dict(schema=STATE_SCHEMA + '_PREFLIGHT', run=a.run, host='main', checks=checks, missing=missing,
                activation='refused' if missing else 'prerequisites established (SendCommand/PutObject are proven only by use)')


def retained(a):
    """The retained state directory and the run's claims, no AWS call. The controller process and the worker's last-seen
    job are reported distinctly (the worker's live state needs --action status)."""
    state = Path(a.state_dir)
    identity = read_json(state / 'controller.json', tolerant=True) or {}
    holder = alive_pid(state)
    status = read_json(state / 'status.json', tolerant=True) or {}
    outcomes = sorted(p.name for p in state.glob('outcome-*.json'))
    claims = []
    for p in sorted(Path(CLAIMS_PARENT, a.run).glob('*.json')) if Path(CLAIMS_PARENT, a.run).is_dir() else ():
        if p.name.endswith('.reason.json'):
            continue
        doc = read_json(p) or {}
        claims.append(dict(file=p.name, where=doc.get('where'), attempt=doc.get('attempt'), started_utc=doc.get('started_utc'),
                           done=p.name.endswith('.done.json'), released='.released-' in p.name))
    return dict(schema=STATE_SCHEMA + '_RETAINED', run=a.run, state_dir=str(state),
                controller=dict(identity=identity, lock_held=holder is not None, holder_pid=holder, status_at=status.get('at'),
                                outcome=(status.get('controller') or {}).get('outcome'), outcomes=outcomes,
                                stop_request=read_json(state / 'stop-request.json', tolerant=True),
                                stop_ack=read_json(state / 'stop-ack.json', tolerant=True),
                                resume_request=read_json(state / 'resume-request.json', tolerant=True),
                                resume_pending=read_json(state / 'resume-pending.json', tolerant=True),
                                resume_acks=sorted(p.name for p in state.glob('resume-ack-*.json'))),
                worker=dict(last_seen=status.get('worker'), held=status.get('held'),
                            note='the worker\'s last snapshot by the controller; --action status asks the worker itself'),
                queue=status.get('queue'), claims=claims)


# ---------------------------------------------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('plan', 'loop', 'status', 'resume', 'stop', 'preflight', 'retained'))
    p.add_argument('--host', choices=('runner', 'main'), default='runner',
                   help='runner: a bounded GitHub job; main: a run-bound service on the main box (--state-dir, --commit)')
    p.add_argument('--state-dir', default='', help='host main: %s/<run>' % STATE_PARENT)
    p.add_argument('--commit', default='', help='the dispatched commit, recorded beside the staged checkout\'s (never compared, 2026-10-09)')
    p.add_argument('--job', help='original retained Linux job/attempt, required for resume/stop')
    p.add_argument('--run', required=True, help='the orchestrator run (its plan.json lists the days, roles and arm)')
    p.add_argument('--days', default='', help='the authorized days (comma list YYYYMMDD) this controller may claim or '
                                              'resume; default: every day of the run\'s saved plan')
    p.add_argument('--code-root', required=True, help='a staged clean checkout on the main box holding this code')
    p.add_argument('--boxes', default='', help='the worker box instance@region (set up by frankie_box_worker_setup.sh)')
    p.add_argument('--slots', type=int, default=1, help='days at once on the worker: exactly 1 (one held 16-CPU lane)')
    p.add_argument('--data-workers', type=int, default=15, help='recorded only: the held lane runs 15 workers (the CPU ledger)')
    p.add_argument('--budget-minutes', type=int, default=330, help='0 = open-ended (host main only): until no remaining work or a stop')
    p.add_argument('--stop-starting-minutes', type=int, default=20)
    p.add_argument('--stop-wait-minutes', type=int, default=30, help='host main: how long a stop waits for the relayed save')
    p.add_argument('--poll-seconds', type=int, default=60)
    p.add_argument('--url-hours', type=float, default=72.0)
    p.add_argument('--disk-floor-gb', type=float, default=100.0)
    p.add_argument('--wait-for-days', choices=('yes', 'no'), default='yes')
    p.add_argument('--fallback-route', choices=('worker_box',),
                   help='the explicit opt-in to this listed, unused fallback (loop/resume refuse without it; Greg, 2026-10-07: '
                        'every day runs on the main box\'s two lanes)')
    a, extra = p.parse_known_args()
    if extra:
        retired = [x for x in extra if x.split('=', 1)[0] in RETIRED_POD_FLAGS]
        if retired:
            raise SystemExit('Pods are retired from the Frankie experiment; retired Pod argument(s) refused: %s' % retired)
        raise SystemExit('unsupported argument(s) refused: %s' % extra)
    a.wait_for_days = a.wait_for_days == 'yes'
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', a.run) or not a.code_root.startswith('/opt/frankie-box/code/'):
        raise SystemExit('--run [A-Za-z0-9_-] and --code-root /opt/frankie-box/code/... required')
    if a.commit and not re.fullmatch(r'[0-9a-f]{40}', a.commit):
        raise SystemExit('--commit must be the full 40-hex commit')
    a.days = [d for d in a.days.split(',') if d]
    if not all(re.fullmatch(r'[0-9]{8}', d) for d in a.days) or len(set(a.days)) != len(a.days):
        raise SystemExit('--days must be distinct YYYYMMDD values')
    if a.action in ('loop', 'resume') and a.fallback_route != 'worker_box':
        raise SystemExit('the worker-box lane is a listed, unused fallback: every day runs on the main box\'s two held lanes '
                         '(Greg, 2026-10-07); %s refuses without --fallback-route worker_box (an explicit decision); nothing '
                         'claimed or started' % a.action)
    if a.action in ('loop', 'resume', 'stop', 'preflight') and (a.slots != 1 or a.boxes != LINUX_LANE):
        raise SystemExit('the experiment uses exactly one Linux lane: --boxes %s --slots 1' % LINUX_LANE)
    if a.url_hours > 168:
        raise SystemExit('presigned URLs live at most 168 h')
    if a.budget_minutes < 0 or a.stop_wait_minutes < 1 or a.poll_seconds < 5:
        raise SystemExit('--budget-minutes >= 0, --stop-wait-minutes >= 1, --poll-seconds >= 5')
    if a.host == 'main':
        if a.state_dir != '%s/%s' % (STATE_PARENT, a.run):
            raise SystemExit('host main requires --state-dir %s/%s' % (STATE_PARENT, a.run))
        if a.action in ('loop', 'resume', 'preflight') and not a.commit:
            raise SystemExit('host main requires --commit (the staged checkout\'s commit)')
        if a.action in ('loop', 'resume') and not Path(PLAN_PARENT, a.run, 'plan.json').is_file():
            raise SystemExit('no saved main plan %s/%s/plan.json: the main orchestrator saves it at its first start of this '
                             'run; nothing claimed or started' % (PLAN_PARENT, a.run))
        if a.url_hours > 1:
            a.url_hours = 1.0           # signed with the instance profile's session: short, and renewed by the loop
    else:
        if a.state_dir or a.action in ('preflight', 'retained'):
            raise SystemExit('--state-dir, preflight and retained are for --host main')
        if a.budget_minutes == 0:
            raise SystemExit('a GitHub runner job is bounded: --budget-minutes >= 1 (0 is the main-box service)')
    if a.action == 'preflight':
        doc = preflight(a)
        say(json.dumps(doc, indent=1, sort_keys=True, default=str))
        raise SystemExit(0 if not doc['missing'] else 2)
    if a.action == 'retained':
        say(json.dumps(retained(a), indent=1, sort_keys=True, default=str))
        return
    if a.host == 'main':
        HOST.update(host='main', state=State(a.state_dir, a.run), started=start_epoch())
        if a.action in ('loop', 'resume'):
            HOST['state'].acquire()
    ctl = Controller(a)
    if a.action in ('loop', 'resume'):
        if ctl.state:
            ctl.state.identity(dict(ctl.lease_identity, schema=STATE_SCHEMA, run=a.run, action=a.action, job=a.job,
                                    commit=a.commit, code_root=a.code_root, boxes=a.boxes, slots=a.slots,
                                    budget_minutes=a.budget_minutes, open_ended=ctl.open_ended, started_utc=utc(),
                                    state_dir=a.state_dir, lease_key=lease_key(a.run)))
        try:
            serve(a, ctl)
        except SystemExit as error:
            if not ctl.finished.is_set():
                ctl.outcome = dict(outcome='refused', complete=False, error='SystemExit: %s' % str(error)[:600], note='nothing served')
                ctl.event(step=a.action, result='refused', error=ctl.outcome['error'][:300])
                finish(a, ctl)
            if error.code in (None, 0):
                raise SystemExit(1)
            raise                                    # the refusal's own message and nonzero status
        except Exception as error:  # noqa: BLE001
            if not ctl.finished.is_set():
                ctl.outcome = dict(outcome='failed', complete=False, error='%s: %s' % (type(error).__name__, str(error)[:600]),
                                   note='nothing served')
                ctl.event(step=a.action, result='failed', error=ctl.outcome['error'][:300])
                finish(a, ctl)
            raise
        return
    if a.action == 'status':
        say(json.dumps(box('status', MAIN, 600, CODE_ROOT=a.code_root, RUN=a.run), indent=1, sort_keys=True))
        ctl.queue()
        say('lease', json.dumps(read_lease(a.run), sort_keys=True, default=str))
        for w in workers_of(a, ctl.commit):
            try:
                say(w.where, json.dumps(w.status(), indent=1, sort_keys=True, default=str))
            except Exception as e:  # noqa: BLE001
                say(w.where, 'unreachable:', e)
        return
    q = ctl.queue()
    if a.action == 'stop':
        w = held_worker(a, ctl, q)
        say(json.dumps(box('stop', w.target, 600, COMMIT=ctl.commit, JOB=a.job), sort_keys=True))
        return
    say('queue of %s at %s: %s' % (a.run, q.get('code_commit'), q.get('counts')))
    for d in q['days']:
        say('  %s %s %s' % (d['day'], d['state'], d.get('attempt') or d.get('reason') or (d.get('claim') or {}).get('where') or ''))
    ready = [d for d in q['days'] if d['state'] == 'ready']
    say('%d ready day(s); %d worker(s) x %d slot(s) would start %d now; claim store active: %s; lease: %s' % (
        len(ready), len([b for b in a.boxes.split(',') if b]), a.slots,
        min(len(ready), len([b for b in a.boxes.split(',') if b]) * a.slots), q.get('active'),
        json.dumps(read_lease(a.run), sort_keys=True, default=str)))


def held_worker(a, ctl, q):
    """resume / stop: --job names the original run-day-attempt and the day is still claimed by the Linux worker."""
    if not a.job or not re.fullmatch(re.escape(a.run) + r'-[0-9]{8}-a[0-9]+', a.job):
        raise SystemExit('--job must name the original run-day-attempt')
    w = workers_of(a, ctl.commit)[0]
    held = next((d.get('claim') for d in q['days'] if (d.get('claim') or {}).get('attempt') == a.job), None)
    if not held or held['where'] != w.where:
        raise SystemExit('the day must still be claimed by this Linux worker (original claim untouched)')
    if not ctl.authorized(held.get('day') or a.job[len(a.run) + 1:len(a.run) + 9]):
        raise SystemExit('the day is outside this controller\'s authorized scope (--days); original claim untouched')
    return w


def serve(a, ctl):
    """loop / resume: the queue read (the commit bound), the worker chosen, the run served."""
    q = ctl.queue()
    say('queue of %s at %s: %s' % (a.run, q.get('code_commit'), q.get('counts')))
    for d in q['days']:
        say('  %s %s %s' % (d['day'], d['state'], d.get('attempt') or d.get('reason') or (d.get('claim') or {}).get('where') or ''))
    if a.action == 'resume':
        run_serving(a, ctl, [held_worker(a, ctl, q)], only_job=a.job)
        return
    workers = workers_of(a, ctl.commit)
    if not workers:
        raise SystemExit('no workers: give --boxes %s' % LINUX_LANE)
    run_serving(a, ctl, workers)


def run_serving(a, ctl, workers, only_job=None):
    """loop / resume: the lease taken, the identity recorded, the claim store enabled, the worker served, the outcome and
    journal written; the lease released on the way out (also on SIGTERM, with the outcome 'terminated_by_signal')."""
    try:
        ctl.take_lease()
    except (Exception, SystemExit) as error:
        ctl.outcome = dict(outcome='refused' if isinstance(error, SystemExit) else 'failed', complete=False,
                           error='%s: %s' % (type(error).__name__, str(error)[:600]), note='no lease taken; nothing served')
        ctl.event(step='lease', result=ctl.outcome['outcome'], error=ctl.outcome['error'][:300])
        finish(a, ctl)
        raise

    def on_term(signum, frame):
        ctl.outcome = ctl.outcome or dict(outcome='terminated_by_signal', signal=signum, complete=False,
                                          note='the process was signalled; the worker keeps its job and claim; the state '
                                               'directory shows the last poll; this was not the cooperative stop route')
        ctl.event(step='signal', result='received', signal=signum)
        finish(a, ctl)
        os._exit(143)
    signal.signal(signal.SIGTERM, on_term)
    ctl.heartbeat_thread = threading.Thread(target=ctl.heartbeat, name='lease-heartbeat', daemon=True)
    ctl.heartbeat_thread.start()
    try:
        if only_job is None:
            r = box('enable', MAIN, 600, CODE_ROOT=a.code_root)
            say('claim store', r)
            if not r.get('active'):
                raise SystemExit('the claim store is not active after enable: %s' % r)
        else:
            w = workers[0]
            result = ctl.renew(w, dict(job_id=only_job), resume=True)
            say(json.dumps(result, sort_keys=True))
    except (Exception, SystemExit) as error:
        ctl.outcome = dict(outcome='refused' if isinstance(error, SystemExit) else 'failed', complete=False,
                           error='%s: %s' % (type(error).__name__, str(error)[:600]),
                           note='nothing served; the worker keeps any job and claim it has')
        ctl.event(step=a.action, result=ctl.outcome['outcome'], error=ctl.outcome['error'][:300])
        finish(a, ctl)
        raise
    threads = [threading.Thread(target=ctl.worker_loop, args=(w,), kwargs=dict(only_job=only_job), name=w.where, daemon=True)
               for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        while t.is_alive():
            t.join(60)
    finish(a, ctl)
    if (ctl.outcome or {}).get('outcome') in UNSUCCESSFUL:
        raise SystemExit(1)


UNSUCCESSFUL = ('failed', 'refused', 'lease_lost', 'lease_unestablished', 'blocked_by_start_failures', 'worker_unreachable',
                'terminated_by_signal')


def finish(a, ctl):
    if ctl.finished.is_set():
        return
    ctl.finished.set()
    if ctl.resume_pending is not None:
        ctl.outcome = dict(ctl.outcome or dict(outcome='ended', complete=False), resume_unresolved=ctl.resume_pending,
                           note_resume='a resume request remains unresolved: resume-request.json is kept; the next '
                                       'controller reconciles it through the worker status before acknowledging')
    if ctl.heartbeat_thread is not None and ctl.heartbeat_thread is not threading.current_thread():
        ctl.heartbeat_thread.join(HEARTBEAT_SECONDS)       # no heartbeat lands after the release below
    ctl.outcome = ctl.outcome or dict(outcome='ended', complete=False)
    # every exit path (finished, failed, refused, lease lost/unestablished, budget, stop, signal): the worker box's
    # KeepRunning cleared to false, UNLESS the worker's last-seen status shows a live job of this run (a stop whose job
    # continues unattended, a budget end): then the tag is left true and the reason is recorded; never silent either way
    for w in workers_of(a, ctl.commit):
        seen = ctl.last_worker or {}
        live = [j.get('job_id') for j in (seen.get('jobs') or []) if j.get('run') == a.run and j.get('pid_alive')]
        # UNKNOWN keeps the tag on (8A: an uncertain state stays unknown, never read as idle): a submit or resume was
        # attempted and no reachable worker status newer than it was seen, or a resume is still unresolved
        unknown = None
        if ctl.resume_pending is not None:
            unknown = 'a resume request is unresolved (its worker outcome is unknown)'
        elif ctl.last_submit_at is not None and (not seen or seen.get('unreachable') or
                                                 float(seen.get('at_epoch') or 0) < ctl.last_submit_at):
            unknown = ('a job was submitted/resumed at %s and no reachable worker status newer than it was seen'
                       % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ctl.last_submit_at)))
        if live or unknown:
            ctl.outcome['keep_running'] = dict(instance=w.target['instance'], keep_running='true', changed=False,
                                               worker_state='live' if live else 'unknown',
                                               reason=('left true: live job(s) %s of the run continue on the worker (outcome %s)'
                                                       % (live, ctl.outcome.get('outcome'))) if live else
                                                      ('left true: the worker\'s job state is UNKNOWN (%s; outcome %s)'
                                                       % (unknown, ctl.outcome.get('outcome'))))
        else:
            ctl.outcome['keep_running'] = keep_running(w.target['instance'], w.target['region'], False,
                                                       'controller ended %s; no live job of run %s seen on the worker'
                                                       % (ctl.outcome.get('outcome'), a.run), 'pod_root/controller.py ' + controller_id())
        ctl.event(worker=w.where, step='keep_running', **ctl.outcome['keep_running'])
    out = ctl.summary()
    body = json.dumps(dict(out, events=ctl.events), indent=1, sort_keys=True, default=str)
    try:
        s3(TRANSFER_BUCKET).put_object(Bucket=TRANSFER_BUCKET, ServerSideEncryption='AES256', Body=body.encode(),
                                       Key='%s/%s/controller/%s.json' % (PREFIX, a.run, controller_id()))
    except Exception as e:  # noqa: BLE001
        say('controller journal not written to S3:', e)
    if ctl.state:
        ctl.state.outcome(ctl.started, dict(ctl.outcome, run=a.run, controller=ctl.lease_identity, summary=out))
        Path(ctl.state.dir, 'journal-%s.json' % controller_id()).write_text(body, encoding='utf-8')
        ctl.snapshot()
    else:
        Path('pod-root-controller.json').write_text(body)
    ctl.release_lease()
    say('SUMMARY', json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
